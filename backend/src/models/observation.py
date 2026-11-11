from sqlalchemy import ForeignKey,Float,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class PeriodObservation(Base):
    __tablename__='period_observations'
    __table_args__=(UniqueConstraint('benchmark_id','venue_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    benchmark_id:Mapped[int]=mapped_column(ForeignKey('benchmark_sets.id'))
    venue_id:Mapped[int]=mapped_column(ForeignKey('venues.id'))
    staff_hours:Mapped[float]=mapped_column(Float)
    energy_cost:Mapped[float]=mapped_column(Float)
    visits:Mapped[float]=mapped_column(Float)
    programs:Mapped[float]=mapped_column(Float)
