import numpy as np
from src.services.dea_solver import solve_dmu
def analyze_frontier(records,inputs,outputs,sensitivity_count=3):
    if len(records)<3:raise ValueError('至少需要3个同期场馆观察')
    if len({r['observation_id'] for r in records})!=len(records):raise ValueError('观察编号重复')
    x=np.array([[r[f] for f in inputs] for r in records],float);y=np.array([[r[f] for f in outputs] for r in records],float)
    xs=x.max(axis=0);ys=np.maximum(y.max(axis=0),1.)
    baseline=[]
    for i,r in enumerate(records):
        result=solve_dmu(x[i],y[i],x,y,xs,ys)
        if result['status']!='optimal':raise ValueError(f"基线求解失败 {r['venue_code']}: {result['status']}")
        result['observation_id']=r['observation_id'];result['venue_code']=r['venue_code'];result['venue_name']=r['venue_name'];result['source']={f:r[f] for f in inputs+outputs}
        result['peers']=[{'observation_id':records[j]['observation_id'],'venue_code':records[j]['venue_code'],'venue_name':records[j]['venue_name'],'lambda':weight} for j,weight in enumerate(result.pop('weights')) if weight>1e-7]
        result['input_slack']=dict(zip(inputs,result['input_slack']));result['output_slack']=dict(zip(outputs,result['output_slack']));result['projected_inputs']=dict(zip(inputs,result['projected_inputs']));result['projected_outputs']=dict(zip(outputs,result['projected_outputs']))
        baseline.append(result)
    influence={r['observation_id']:0. for r in records}
    for target in baseline:
        for peer in target['peers']:
            if peer['observation_id']!=target['observation_id']:influence[peer['observation_id']]+=peer['lambda']
    selected=sorted([r for r in records if influence[r['observation_id']]>1e-7],key=lambda r:(-influence[r['observation_id']],r['venue_code']))[:sensitivity_count]
    scenarios=[]
    for removed in selected:
        keep=[i for i,r in enumerate(records) if r['observation_id']!=removed['observation_id']]
        scores=[]
        for i,target in enumerate(records):
            solution=solve_dmu(x[i],y[i],x[keep],y[keep],xs,ys)
            theta=solution['theta'];base=baseline[i]['theta']
            if theta is not None and theta<base-1e-6:raise ValueError('移除参照后theta不应下降，请核验求解器')
            scores.append({'observation_id':target['observation_id'],'venue_code':target['venue_code'],'status':solution['status'],'theta':theta,'delta':None if theta is None else theta-base,'removed_target_self':target['observation_id']==removed['observation_id']})
        scenarios.append({'removed_observation_id':removed['observation_id'],'removed_code':removed['venue_code'],'removed_name':removed['venue_name'],'aggregate_external_lambda':influence[removed['observation_id']],'reference_ids':[records[i]['observation_id'] for i in keep],'scores':scores})
    return {'baseline':baseline,'scenarios':scenarios,'input_scales':dict(zip(inputs,xs.tolist())),'output_scales':dict(zip(outputs,ys.tolist())),'reference_ids':[r['observation_id'] for r in records],'self_included_baseline':True,'sensitivity_policy':'所有原目标统一使用R减去同一被移除标杆；不再逐目标排除自身','n':len(records),'inputs':inputs,'outputs':outputs,'efficient_count':sum(r['strong_efficient'] for r in baseline),'mean_theta':float(np.mean([r['theta'] for r in baseline]))}
