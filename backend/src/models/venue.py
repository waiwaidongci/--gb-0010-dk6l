from sqlalchemy import String
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class Venue(Base):
    __tablename__='venues'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(60),unique=True)
    name:Mapped[str]=mapped_column(String(140))
    district:Mapped[str]=mapped_column(String(80))
    kind:Mapped[str]=mapped_column(String(60),default='综合文化场馆')
