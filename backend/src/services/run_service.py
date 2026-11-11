import json,hashlib
from sqlalchemy import select
from fastapi import HTTPException
from redis import Redis
from src.config.settings import REDIS_URL
from src.models import BenchmarkSet,EfficiencyRun
from src.services.observation_service import list_observations
from src.services.sensitivity import analyze_frontier
from src.constants.enums import RunStatus
redis=Redis.from_url(REDIS_URL)
def list_runs(db):return db.scalars(select(EfficiencyRun).order_by(EfficiencyRun.id.desc())).all()
def get_run(db,id):
    run=db.get(EfficiencyRun,id)
    if not run:raise HTTPException(404,'研究不存在')
    return run
def create_run(db,data):
    if not db.get(BenchmarkSet,data.benchmark_id):raise HTTPException(404,'参照集不存在')
    if db.scalar(select(EfficiencyRun).where(EfficiencyRun.name==data.name)):raise HTTPException(409,'研究名称已存在')
    item=EfficiencyRun(**data.model_dump(),status=RunStatus.QUEUED);db.add(item);db.commit();redis.lpush('frontier:runs',str(item.id));return item
def execute_run(db,id):
    run=db.get(EfficiencyRun,id)
    if not run or run.status not in (RunStatus.QUEUED,RunStatus.RUNNING):return
    run.status=RunStatus.RUNNING;db.commit()
    try:
        benchmark=db.get(BenchmarkSet,run.benchmark_id);records=list_observations(db,benchmark.id)
        result=analyze_frontier(records,run.inputs,run.outputs,run.sensitivity_count)
        snapshot={'algorithm':'ccr-input-two-stage-v1','benchmark':{'id':benchmark.id,'code':benchmark.code,'period':benchmark.period},'records':records,'inputs':run.inputs,'outputs':run.outputs,'sensitivity_count':run.sensitivity_count,'baseline_self':True,'removal_policy':'same_R_minus_b_for_all_original_targets'}
        result['fingerprint']=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();result['period']=benchmark.period;result['benchmark_name']=benchmark.name
        run.result=result;run.status=RunStatus.COMPLETED;run.error='';db.commit()
    except Exception as exc:
        db.rollback();run=db.get(EfficiencyRun,id);run.status=RunStatus.FAILED;run.error=str(exc)[:600];db.commit()
