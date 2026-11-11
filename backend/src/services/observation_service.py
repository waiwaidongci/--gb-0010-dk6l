from sqlalchemy import select
from fastapi import HTTPException
from src.models import BenchmarkSet,PeriodObservation,Venue
def list_observations(db,benchmark_id):
    if not db.get(BenchmarkSet,benchmark_id):raise HTTPException(404,'参照集不存在')
    rows=db.execute(select(PeriodObservation,Venue).join(Venue,Venue.id==PeriodObservation.venue_id).where(PeriodObservation.benchmark_id==benchmark_id).order_by(Venue.code)).all()
    return [{'observation_id':o.id,'venue_id':v.id,'venue_code':v.code,'venue_name':v.name,'district':v.district,'staff_hours':o.staff_hours,'energy_cost':o.energy_cost,'visits':o.visits,'programs':o.programs} for o,v in rows]
