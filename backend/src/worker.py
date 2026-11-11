import time
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import EfficiencyRun
from src.constants.enums import RunStatus
from src.services.run_service import execute_run
redis=Redis.from_url(REDIS_URL)
while True:
    Path('/tmp/heartbeat').touch()
    with Session() as db:
        run=db.scalar(select(EfficiencyRun).where(EfficiencyRun.status.in_([RunStatus.QUEUED,RunStatus.RUNNING])).order_by(EfficiencyRun.id))
        if run:execute_run(db,run.id)
        else:redis.brpop('frontier:runs',timeout=2)
    time.sleep(.1)
