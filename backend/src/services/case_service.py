import json,csv,io
from sqlalchemy import select
from fastapi import HTTPException
from src.models import ImprovementCase,EfficiencyRun
from src.constants.enums import RunStatus,CaseStatus
def list_cases(db):return db.scalars(select(ImprovementCase).order_by(ImprovementCase.id.desc())).all()
def create_case(db,data):
    run=db.get(EfficiencyRun,data.run_id)
    if not run or run.status!=RunStatus.COMPLETED:raise HTTPException(422,'请选择已完成研究')
    target=next((r for r in run.result['baseline'] if r['observation_id']==data.observation_id),None)
    if not target:raise HTTPException(422,'机构观察不属于该研究的同期目标集')
    if db.scalar(select(ImprovementCase).where(ImprovementCase.title==data.title)):raise HTTPException(409,'假设标题已存在')
    item=ImprovementCase(**data.model_dump(),status=CaseStatus.DRAFT);db.add(item);db.commit();return item
def approve_case(db,id,user):
    item=db.get(ImprovementCase,id)
    if not item:raise HTTPException(404,'评议假设不存在')
    item.status=CaseStatus.APPROVED;item.approved_by=user.email;db.commit();return item
def export_case(db,id):
    item=db.get(ImprovementCase,id)
    if not item:raise HTTPException(404,'评议假设不存在')
    if item.status!=CaseStatus.APPROVED:raise HTTPException(409,'负责人批准后才能交付')
    run=db.get(EfficiencyRun,item.run_id);row=next(r for r in run.result['baseline'] if r['observation_id']==item.observation_id)
    def safe(value):
        text=str(value)
        return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
    out=io.StringIO();out.write('\ufeff');writer=csv.writer(out);writer.writerow(['venue_code','venue_name','period','theta','input_slack','output_surplus','projected_inputs','peer_lambdas','hypothesis','verification','approved_by','run_fingerprint'])
    writer.writerow([safe(row['venue_code']),safe(row['venue_name']),safe(run.result['period']),row['theta'],json.dumps(row['input_slack'],ensure_ascii=False),json.dumps(row['output_slack'],ensure_ascii=False),json.dumps(row['projected_inputs'],ensure_ascii=False),json.dumps(row['peers'],ensure_ascii=False),safe(item.hypothesis),safe(item.verification),safe(item.approved_by),run.result['fingerprint']]);return out.getvalue()
