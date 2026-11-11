import numpy as np
from scipy.optimize import linprog
STATUSES={0:'optimal',1:'iteration_limit',2:'infeasible',3:'unbounded',4:'numerical_error'}
def solver_status(code):return STATUSES.get(int(code),'solver_error')
def solve_dmu(x0,y0,x_ref,y_ref,input_scale=None,output_scale=None):
    x0=np.asarray(x0,float);y0=np.asarray(y0,float);x_ref=np.asarray(x_ref,float);y_ref=np.asarray(y_ref,float)
    if x_ref.ndim!=2 or y_ref.ndim!=2 or len(x_ref)!=len(y_ref) or len(x_ref)==0:raise ValueError('参照集为空或形状不匹配')
    if x_ref.shape[1]!=len(x0) or y_ref.shape[1]!=len(y0):raise ValueError('投入产出维度不匹配')
    if not all(np.isfinite(v).all() for v in (x0,y0,x_ref,y_ref)):raise ValueError('投入产出必须为有限值')
    if (x0<=0).any() or (x_ref<=0).any():raise ValueError('零或负投入不允许进入CCR研究')
    if (y0<0).any() or (y_ref<0).any():raise ValueError('产出不得为负')
    xs=np.asarray(input_scale if input_scale is not None else x_ref.max(axis=0),float)
    ys=np.asarray(output_scale if output_scale is not None else np.maximum(y_ref.max(axis=0),1),float)
    if (xs<=0).any() or (ys<=0).any():raise ValueError('缩放因子必须为正')
    x=x_ref/xs;y=y_ref/ys;targetx=x0/xs;targety=y0/ys;n=len(x)
    # Variables lambda_1..lambda_n, theta. CRS: no sum(lambda)=1 constraint.
    a=np.vstack([np.column_stack([x.T,-targetx]),np.column_stack([-y.T,np.zeros(len(y0))])]);b=np.r_[np.zeros(len(x0)),-targety]
    objective=np.r_[np.zeros(n),1.]
    first=linprog(objective,A_ub=a,b_ub=b,bounds=[(0,None)]*(n+1),method='highs',options={'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
    if first.status!=0:return {'status':solver_status(first.status),'theta':None,'message':first.message,'stage2_status':'not_run'}
    theta=float(first.x[-1]);theta=1. if abs(theta-1)<1e-8 else theta
    # With theta fixed, maximize standardized input excess + output surplus.
    second=linprog(x.sum(axis=1)-y.sum(axis=1),A_ub=np.vstack([x.T,-y.T]),b_ub=np.r_[theta*targetx,-targety],bounds=[(0,None)]*n,method='highs',options={'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
    if second.status!=0:return {'status':solver_status(second.status),'theta':None,'message':'固定theta的松弛阶段失败：'+second.message,'stage2_status':solver_status(second.status)}
    weights=np.maximum(second.x,0);projected_x=weights@x_ref;projected_y=weights@y_ref
    slack_x=theta*x0-projected_x;slack_y=projected_y-y0
    if (slack_x/xs < -1e-6).any() or (slack_y/ys < -1e-6).any():raise ValueError('求解结果未满足投入产出约束容差')
    slack_x=np.maximum(slack_x,0);slack_y=np.maximum(slack_y,0)
    strong=abs(theta-1)<1e-7 and max(np.max(slack_x/xs),np.max(slack_y/ys))<1e-6
    return {'status':'optimal','theta':theta,'weights':weights.tolist(),'input_slack':slack_x.tolist(),'output_slack':slack_y.tolist(),'projected_inputs':projected_x.tolist(),'projected_outputs':projected_y.tolist(),'strong_efficient':bool(strong),'zero_output':bool(np.all(y0==0)),'stage2_status':'optimal'}
