from sqlalchemy import ForeignKey,String,JSON,DateTime,Integer
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from src.config.database import Base
class EfficiencyRun(Base):
    __tablename__='efficiency_runs'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(160),unique=True)
    benchmark_id:Mapped[int]=mapped_column(ForeignKey('benchmark_sets.id'))
    inputs:Mapped[list]=mapped_column(JSON)
    outputs:Mapped[list]=mapped_column(JSON)
    sensitivity_count:Mapped[int]=mapped_column(default=3)
    status:Mapped[str]=mapped_column(String(20),default='queued')
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    error:Mapped[str]=mapped_column(String(600),default='')
    # Per-venue progress. The checkpoint is bound to the exact concurrent
    # observation sample and solving specification through the two digests.
    checkpoint:Mapped[dict]=mapped_column(JSON,default=dict)
    checkpoint_version:Mapped[int]=mapped_column(Integer,default=0)
    checkpoint_sample_digest:Mapped[str]=mapped_column(String(64),default='')
    checkpoint_config_digest:Mapped[str]=mapped_column(String(64),default='')
    # Lease/fencing coordinates. Only the executor holding the current
    # (owner_token, claim_generation) pair may persist progress or the result.
    owner_token:Mapped[str]=mapped_column(String(128),default='')
    claim_generation:Mapped[int]=mapped_column(Integer,default=0)
    lease_expires_at:Mapped[datetime]=mapped_column(DateTime,nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
