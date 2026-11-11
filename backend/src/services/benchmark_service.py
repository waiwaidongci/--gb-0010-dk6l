import csv,io
from sqlalchemy import select,func
from fastapi import HTTPException
from pydantic import ValidationError
from src.models import BenchmarkSet,Venue,PeriodObservation
from src.schemas.observation import ObservationInput
def list_benchmarks(db):
    rows=db.execute(select(BenchmarkSet,func.count(PeriodObservation.id)).outerjoin(PeriodObservation,PeriodObservation.benchmark_id==BenchmarkSet.id).group_by(BenchmarkSet.id).order_by(BenchmarkSet.id)).all()
    return [{'id':b.id,'code':b.code,'name':b.name,'period':b.period,'source_file':b.source_file,'note':b.note,'row_count':n} for b,n in rows]
def create_benchmark(db,data):
    if db.scalar(select(BenchmarkSet).where(BenchmarkSet.code==data.code)):raise HTTPException(409,'参照集编号已存在')
    try:rows=[ObservationInput.model_validate(r) for r in csv.DictReader(io.StringIO(data.csv_text))]
    except (ValidationError,ValueError,csv.Error) as exc:raise HTTPException(422,f'CSV校验失败：{str(exc)[:300]}')
    if not 3<=len(rows)<=100:raise HTTPException(422,'每个同期参照集需要3–100个机构观察')
    if len({r.venue_code for r in rows})!=len(rows):raise HTTPException(422,'同一参照集每个场馆只能出现一次')
    venues={v.code:v for v in db.scalars(select(Venue)).all()}
    if any(r.venue_code not in venues for r in rows):raise HTTPException(422,'请先登记CSV中的全部场馆编号')
    item=BenchmarkSet(**data.model_dump(exclude={'csv_text'}));db.add(item);db.flush();db.add_all([PeriodObservation(benchmark_id=item.id,venue_id=venues[r.venue_code].id,**r.model_dump(exclude={'venue_code'})) for r in rows]);db.commit();return {'id':item.id,'row_count':len(rows)}
