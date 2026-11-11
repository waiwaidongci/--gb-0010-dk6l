import hashlib
import json
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import and_, or_, select, update

from src.config.settings import REDIS_URL, RUN_LEASE_SECONDS
from src.constants.enums import RunStatus
from src.models import BenchmarkSet, EfficiencyRun
from src.services.observation_service import list_observations
from src.services.sensitivity import (
    ALGORITHM,
    REMOVAL_POLICY,
    CheckpointMismatch,
    analyze_frontier,  # kept importable for callers of the original one-shot helper
    analyze_frontier_resumable,
    checkpoint_identity,
)

redis = Redis.from_url(REDIS_URL)


class StaleExecutor(RuntimeError):
    """The executor no longer owns the run and must not persist anything."""


def list_runs(db):
    return db.scalars(select(EfficiencyRun).order_by(EfficiencyRun.id.desc())).all()


def get_run(db, id):
    run = db.get(EfficiencyRun, id)
    if not run:
        raise HTTPException(404, '研究不存在')
    return run


def create_run(db, data):
    if not db.get(BenchmarkSet, data.benchmark_id):
        raise HTTPException(404, '参照集不存在')
    if db.scalar(select(EfficiencyRun).where(EfficiencyRun.name == data.name)):
        raise HTTPException(409, '研究名称已存在')
    item = EfficiencyRun(**data.model_dump(), status=RunStatus.QUEUED)
    db.add(item)
    db.commit()
    redis.lpush('frontier:runs', str(item.id))
    return item


def _claim_run(db, run_id, token, lease_seconds=RUN_LEASE_SECONDS, allow_failed=False):
    """Atomically take ownership of a run.

    Queued runs are claimable immediately. A running run is claimable only
    when its lease has expired (its previous executor stopped renewing it).
    A failed run is claimable only when an explicit retry asks for it and it
    has usable per-venue progress. ``claim_generation`` is incremented on
    every takeover; it is the fencing token used by all later writes.
    """
    now = datetime.utcnow()
    claimable = or_(
        EfficiencyRun.status == RunStatus.QUEUED,
        and_(
            EfficiencyRun.status == RunStatus.RUNNING,
            or_(EfficiencyRun.lease_expires_at.is_(None), EfficiencyRun.lease_expires_at <= now),
        ),
    )
    if allow_failed:
        claimable = or_(claimable, EfficiencyRun.status == RunStatus.FAILED)
    result = db.execute(
        update(EfficiencyRun)
        .where(EfficiencyRun.id == run_id, claimable)
        .values(
            status=RunStatus.RUNNING,
            owner_token=token,
            claim_generation=EfficiencyRun.claim_generation + 1,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            error='',
        ),
        execution_options={'synchronize_session': False},
    )
    db.commit()
    if result.rowcount == 1:
        db.expire_all()
    return result.rowcount == 1


def _owned_write(db, run_id, token, generation, lease_seconds=RUN_LEASE_SECONDS, **values):
    """Write only while this executor still holds the current claim."""
    if 'lease_expires_at' not in values:
        values['lease_expires_at'] = datetime.utcnow() + timedelta(seconds=lease_seconds)
    values.setdefault('updated_at', datetime.utcnow())
    result = db.execute(
        update(EfficiencyRun)
        .where(
            EfficiencyRun.id == run_id,
            EfficiencyRun.owner_token == token,
            EfficiencyRun.claim_generation == generation,
            EfficiencyRun.status == RunStatus.RUNNING,
        )
        .values(**values),
        execution_options={'synchronize_session': False},
    )
    db.commit()
    if result.rowcount == 1:
        db.expire_all()
    return result.rowcount == 1


def execute_run(db, id, executor_token=None):
    """Execute or resume one run.

    Returns True when this executor completed the run, False when the run was
    already finished, actively owned by another executor, or lost ownership
    through a takeover. Every write is fenced by (owner_token,
    claim_generation), so a resumed old executor cannot overwrite a newer
    executor's checkpoint or final result.
    """
    token = executor_token or uuid.uuid4().hex
    run = db.get(EfficiencyRun, id)
    checkpoint = (run.checkpoint or {}) if run else {}
    has_progress = bool(checkpoint.get('baseline') or checkpoint.get('scenarios'))
    resumable_failure = bool(run and run.status == RunStatus.FAILED and has_progress)
    if not run or (run.status not in (RunStatus.QUEUED, RunStatus.RUNNING) and not resumable_failure):
        return False
    if not _claim_run(db, id, token, allow_failed=resumable_failure):
        return False
    db.refresh(run)
    generation = run.claim_generation

    try:
        benchmark = db.get(BenchmarkSet, run.benchmark_id)
        if not benchmark:
            raise ValueError('参照集不存在')
        records = list_observations(db, benchmark.id)
        identity = checkpoint_identity(records, run.inputs, run.outputs, run.sensitivity_count, benchmark=benchmark)
        checkpoint = run.checkpoint or {}

        def save_progress(state):
            if not _owned_write(
                db,
                id,
                token,
                generation,
                checkpoint=state,
                checkpoint_version=EfficiencyRun.checkpoint_version + 1,
                checkpoint_sample_digest=state.get('sample_digest', identity['sample_digest']),
                checkpoint_config_digest=state.get('config_digest', identity['config_digest']),
            ):
                raise StaleExecutor('研究已被其他执行者接管，停止写入旧结果')

        result, final_checkpoint = analyze_frontier_resumable(
            records,
            run.inputs,
            run.outputs,
            run.sensitivity_count,
            checkpoint=checkpoint,
            on_checkpoint=save_progress,
            benchmark=benchmark,
        )

        # Guard the last crash window too: if observations or run settings
        # changed while this executor was working, do not publish a result
        # assembled from the old sample.
        current_records = list_observations(db, benchmark.id)
        current_identity = checkpoint_identity(current_records, run.inputs, run.outputs, run.sensitivity_count, benchmark=benchmark)
        if any(current_identity[k] != identity[k] for k in ('sample_digest', 'config_digest', 'inputs', 'outputs', 'sensitivity_count', 'reference_ids', 'n')):
            raise CheckpointMismatch('执行期间同期样本或求解口径发生变化，拒绝写入混用结果')

        snapshot = {
            'algorithm': ALGORITHM,
            'benchmark': {'id': benchmark.id, 'code': benchmark.code, 'period': benchmark.period},
            'records': records,
            'inputs': run.inputs,
            'outputs': run.outputs,
            'sensitivity_count': run.sensitivity_count,
            'baseline_self': True,
            'removal_policy': REMOVAL_POLICY,
        }
        result['fingerprint'] = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        ).hexdigest()
        result['period'] = benchmark.period
        result['benchmark_name'] = benchmark.name

        if not _owned_write(
            db,
            id,
            token,
            generation,
            result=result,
            status=RunStatus.COMPLETED,
            error='',
            checkpoint=final_checkpoint,
            checkpoint_version=EfficiencyRun.checkpoint_version + 1,
            checkpoint_sample_digest=identity['sample_digest'],
            checkpoint_config_digest=identity['config_digest'],
            lease_expires_at=None,
        ):
            raise StaleExecutor('研究已被其他执行者接管，丢弃旧结果')
        return True
    except StaleExecutor:
        # Deliberately do not touch status/result: the new owner is authoritative.
        db.rollback()
        return False
    except CheckpointMismatch as exc:
        db.rollback()
        _fail_ownership(db, id, token, generation, str(exc))
        return False
    except Exception as exc:
        db.rollback()
        _fail_ownership(db, id, token, generation, str(exc))
        return False


def _fail_ownership(db, run_id, token, generation, message):
    try:
        _owned_write(
            db,
            run_id,
            token,
            generation,
            status=RunStatus.FAILED,
            error=message[:600],
            lease_expires_at=None,
        )
    except Exception:
        db.rollback()
