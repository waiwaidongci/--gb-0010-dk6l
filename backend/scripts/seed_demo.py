import random,json
from sqlalchemy import select,func
from src.config.database import Base,engine,Session
from src.models import User,BenchmarkSet,Venue,PeriodObservation,EfficiencyRun,ImprovementCase
from src.utils.security import hash_password
from src.services.run_service import execute_run

def seed():
    Base.metadata.create_all(engine);rng=random.Random(91)
    names=['松窗文化馆','南埠展演厅','苇桥阅读馆','砾园艺术馆','水岸青年馆','东里文化馆','栖岭剧场','青坪展览馆','石桥文化站','林间阅读馆','田畔艺术屋','河西文化馆','落霞展演厅','杉影文化馆','溪畔青少年馆','北园剧场','桂巷阅读馆','新桥文化站','云台展览馆','湖东艺术馆','榆荫文化馆','西埠文化馆','山房展演厅','麦田阅读馆']
    with Session() as db:
        for role,name in [('admin','许栖 · 评议负责人'),('analyst','沈原 · 场馆分析员'),('viewer','何禾 · 机构联络员')]:
            if not db.scalar(select(User).where(User.email==f'{role}@qiyuan.demo')):db.add(User(email=f'{role}@qiyuan.demo',name=name,role=role,password_hash=hash_password('Qiyuan2026!')))
        for i,name in enumerate(names):
            code=f'QY-{i+1:02d}'
            if not db.scalar(select(Venue).where(Venue.code==code)):db.add(Venue(code=code,name=name,district=['东岸片区','南林片区','西桥片区','北园片区'][i%4],kind='综合文化场馆'))
        db.commit();venues=db.scalars(select(Venue).order_by(Venue.code)).all()
        for p,period in enumerate(['2026Q2','2026Q3']):
            code='QY-'+period;benchmark=db.scalar(select(BenchmarkSet).where(BenchmarkSet.code==code))
            if not benchmark:
                benchmark=BenchmarkSet(code=code,name=f'栖原24场馆 · {period}同期参照',period=period,source_file='qy-venues-2026.csv',note='机构级季度汇总；投入单位为工时/元，产出为到访人次/项目场次；各季度独立比较。');db.add(benchmark);db.flush()
                for i,v in enumerate(venues):
                    size=.7+(i%6)*.22;efficiency=1. if i<3 else rng.uniform(.46,.88)
                    staff=(1600+180*(i%3))*size/efficiency;energy=(28000+7000*((i+1)%3))*size/efficiency
                    visits=(18000+4000*(i%3))*size*(1+.03*p);programs=(54+15*((i+2)%3))*size*(1+.025*p)
                    db.add(PeriodObservation(benchmark_id=benchmark.id,venue_id=v.id,staff_hours=round(staff,2),energy_cost=round(energy,2),visits=round(visits,0),programs=round(programs,0)))
                db.commit()
            runname=period+' · 双投入双产出CCR'
            if not db.scalar(select(EfficiencyRun).where(EfficiencyRun.name==runname)):
                run=EfficiencyRun(name=runname,benchmark_id=benchmark.id,inputs=['staff_hours','energy_cost'],outputs=['visits','programs'],sensitivity_count=3,status='queued');db.add(run);db.commit();execute_run(db,run.id)
        latest=db.scalar(select(EfficiencyRun).order_by(EfficiencyRun.id.desc()))
        if latest and latest.status=='completed' and not db.scalar(select(ImprovementCase).where(ImprovementCase.title=='水岸青年馆 · 开放时段与照明排程复核')):
            target=next(r for r in latest.result['baseline'] if r['venue_code']=='QY-05')
            db.add(ImprovementCase(title='水岸青年馆 · 开放时段与照明排程复核',run_id=latest.id,observation_id=target['observation_id'],hypothesis='先复核同期开馆工时与照明排程的统计边界，再用活动日观察验证投入缩减假设。',verification='由机构联络员核对季度口径，安排两周现场观察；不作为个人绩效、自动拨款或直接预算削减依据。',status='approved',approved_by='admin@qiyuan.demo'))
        db.commit();print(json.dumps({m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in (User,BenchmarkSet,Venue,PeriodObservation,EfficiencyRun,ImprovementCase)},ensure_ascii=False))
if __name__=='__main__':seed()
