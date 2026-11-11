import time
from datetime import datetime
from pathlib import Path

from redis import Redis
from sqlalchemy import and_, or_, select

from src.config.database import Session
from src.config.settings import REDIS_URL
from src.constants.enums import RunStatus
from src.models import EfficiencyRun
from src.services.run_service import execute_run

redis = Redis.from_url(REDIS_URL)

while True:
    Path('/tmp/heartbeat').touch()
    with Session() as db:
        now = datetime.utcnow()
        # Queued work, plus interrupted runs whose lease has expired. Runs
        # actively owned by another executor are left alone; their lease will
        # ultimately expire if that executor stopped.
        claimable = or_(
            EfficiencyRun.status == RunStatus.QUEUED,
            and_(
                EfficiencyRun.status == RunStatus.RUNNING,
                or_(EfficiencyRun.lease_expires_at.is_(None), EfficiencyRun.lease_expires_at <= now),
            ),
        )
        runs = db.scalars(select(EfficiencyRun).where(claimable).order_by(EfficiencyRun.id)).all()
        did_work = False
        for run in runs:
            if execute_run(db, run.id):
                did_work = True
                break
        if not did_work:
            redis.brpop('frontier:runs', timeout=2)
    time.sleep(.1)
