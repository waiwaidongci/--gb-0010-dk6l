from sqlalchemy import String,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from src.config.database import Base
class BenchmarkSet(Base):
    __tablename__='benchmark_sets'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(80),unique=True)
    name:Mapped[str]=mapped_column(String(160))
    period:Mapped[str]=mapped_column(String(40))
    source_file:Mapped[str]=mapped_column(String(160))
    note:Mapped[str]=mapped_column(String(600),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
