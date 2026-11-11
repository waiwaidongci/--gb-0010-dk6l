from sqlalchemy import select
from fastapi import HTTPException
from src.models import Venue
def list_venues(db):return db.scalars(select(Venue).order_by(Venue.code)).all()
def create_venue(db,data):
    if db.scalar(select(Venue).where(Venue.code==data.code)):raise HTTPException(409,'场馆编号已存在')
    row=Venue(**data.model_dump());db.add(row);db.commit();return row
