from sqlalchemy import ForeignKey,String,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from src.config.database import Base
class ImprovementCase(Base):
    __tablename__='improvement_cases'
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(160),unique=True)
    run_id:Mapped[int]=mapped_column(ForeignKey('efficiency_runs.id'))
    observation_id:Mapped[int]=mapped_column(ForeignKey('period_observations.id'))
    hypothesis:Mapped[str]=mapped_column(String(1200))
    verification:Mapped[str]=mapped_column(String(1000))
    status:Mapped[str]=mapped_column(String(20),default='draft')
    approved_by:Mapped[str]=mapped_column(String(160),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
