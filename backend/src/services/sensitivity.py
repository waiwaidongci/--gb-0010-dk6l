import hashlib
import json

import numpy as np

from src.services.dea_solver import solve_dmu

# Versioned checkpoint / algorithm identity. A run may only reuse progress
# written for the same observation sample and the same solving specification.
CHECKPOINT_VERSION = 1
ALGORITHM = 'ccr-input-two-stage-v1'
SENSITIVITY_POLICY = '所有原目标统一使用R减去同一被移除标杆；不再逐目标排除自身'
REMOVAL_POLICY = 'same_R_minus_b_for_all_original_targets'


class CheckpointMismatch(ValueError):
    """Progress belongs to a different sample or solving specification."""


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _benchmark_identity(benchmark):
    if benchmark is None:
        return None
    if isinstance(benchmark, dict):
        return {'id': benchmark.get('id'), 'code': benchmark.get('code'), 'period': benchmark.get('period'), 'source_file': benchmark.get('source_file')}
    return {'id': getattr(benchmark, 'id', None), 'code': getattr(benchmark, 'code', None), 'period': getattr(benchmark, 'period', None), 'source_file': getattr(benchmark, 'source_file', None)}


def checkpoint_identity(records, inputs, outputs, sensitivity_count=3, benchmark=None):
    """Return the stable identity a checkpoint is bound to.

    The sample digest covers the benchmark period/identity and every ordered
    observation value used by the solver. The config digest covers the model
    fields, sensitivity count and algorithm/removal policies. Either digest
    changing means resuming from the checkpoint would mix two different
    studies, so it must be rejected.
    """
    sample = {'benchmark': _benchmark_identity(benchmark), 'records': records}
    config = {
        'algorithm': ALGORITHM,
        'inputs': list(inputs),
        'outputs': list(outputs),
        'sensitivity_count': int(sensitivity_count),
        'baseline_self': True,
        'removal_policy': REMOVAL_POLICY,
        'sensitivity_policy': SENSITIVITY_POLICY,
        'solver': 'scipy-highs-two-stage',
    }
    return {
        'version': CHECKPOINT_VERSION,
        'algorithm': ALGORITHM,
        'sample_digest': canonical_digest(sample),
        'config_digest': canonical_digest(config),
        'benchmark_id': sample['benchmark']['id'] if sample['benchmark'] else None,
        'benchmark_code': sample['benchmark']['code'] if sample['benchmark'] else None,
        'period': sample['benchmark']['period'] if sample['benchmark'] else None,
        'inputs': list(inputs),
        'outputs': list(outputs),
        'sensitivity_count': int(sensitivity_count),
        'reference_ids': [r['observation_id'] for r in records],
        'n': len(records),
    }


def _validate_checkpoint(checkpoint, identity):
    keys=('version','algorithm','sample_digest','config_digest','inputs','outputs','sensitivity_count','reference_ids','n')
    if any(checkpoint.get(k)!=identity[k] for k in keys):
        raise CheckpointMismatch('断点绑定的同期样本或求解口径已变化，拒绝混用旧结果')


def _decorate_baseline(result, record, inputs, outputs, records):
    result['observation_id']=record['observation_id']
    result['venue_code']=record['venue_code']
    result['venue_name']=record['venue_name']
    result['source']={f:record[f] for f in inputs+outputs}
    result['peers']=[{'observation_id':records[j]['observation_id'],'venue_code':records[j]['venue_code'],'venue_name':records[j]['venue_name'],'lambda':weight} for j,weight in enumerate(result.pop('weights')) if weight>1e-7]
    result['input_slack']=dict(zip(inputs,result['input_slack']))
    result['output_slack']=dict(zip(outputs,result['output_slack']))
    result['projected_inputs']=dict(zip(inputs,result['projected_inputs']))
    result['projected_outputs']=dict(zip(outputs,result['projected_outputs']))
    return result


def _baseline_from_checkpoint(saved, record, inputs, outputs):
    if not isinstance(saved, dict) or saved.get('observation_id')!=record['observation_id']:
        raise CheckpointMismatch('断点中的场馆基线与当前同期样本不一致，拒绝混用旧结果')
    required=('theta','peers','input_slack','output_slack','projected_inputs','projected_outputs','strong_efficient','source')
    if any(k not in saved for k in required):
        raise CheckpointMismatch('断点中的场馆基线不完整，拒绝混用旧结果')
    expected={f:record[f] for f in inputs+outputs}
    if saved['source']!=expected:
        raise CheckpointMismatch('断点中的场馆基线与当前同期样本不一致，拒绝混用旧结果')
    return saved


def analyze_frontier_resumable(records, inputs, outputs, sensitivity_count=3, checkpoint=None, on_checkpoint=None, benchmark=None):
    """Solve the frontier, persisting/reusing per-venue progress.

    ``checkpoint`` is the last persisted checkpoint (or an empty dict). After
    every baseline venue and every benchmark-removal scenario score the
    (possibly mutated) checkpoint is passed to ``on_checkpoint`` so the caller
    can persist it. The returned result is assembled in exactly the same order
    as a one-shot ``analyze_frontier`` run, so scores, reference weights and
    fingerprints are identical whether or not a resume happened.
    """
    if len(records)<3:raise ValueError('至少需要3个同期场馆观察')
    if len({r['observation_id'] for r in records})!=len(records):raise ValueError('观察编号重复')
    x=np.array([[r[f] for f in inputs] for r in records],float);y=np.array([[r[f] for f in outputs] for r in records],float)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):raise ValueError('投入产出必须为有限值')
    xs=x.max(axis=0);ys=np.maximum(y.max(axis=0),1.)
    identity=checkpoint_identity(records,inputs,outputs,sensitivity_count,benchmark=benchmark)

    if checkpoint:
        _validate_checkpoint(checkpoint,identity)
        state=checkpoint
    else:
        state={'baseline':{},'scenarios':{},'scenario_order':[],'phase':'baseline'}

    # Always refresh the bound identity in the stored checkpoint.
    state.update(identity)

    def emit():
        if on_checkpoint is not None:on_checkpoint(state)

    def progress(phase,scenario_index=None,scenario_total=None,scenario_target=None,scenario_target_total=None):
        state['progress']={
            'phase':phase,
            'baseline_completed':len(state.get('baseline',{})),
            'baseline_total':len(records),
            'scenario_index':scenario_index,
            'scenario_total':scenario_total,
            'scenario_target_completed':scenario_target,
            'scenario_target_total':scenario_target_total,
        }

    progress('baseline')
    emit()

    baseline_map=state.setdefault('baseline',{})
    if not isinstance(baseline_map,dict):
        raise CheckpointMismatch('断点中的基线进度无效，拒绝混用旧结果')
    baseline=[]
    for i,r in enumerate(records):
        key=str(r['observation_id'])
        saved=baseline_map.get(key)
        if saved is not None:
            baseline.append(_baseline_from_checkpoint(saved,r,inputs,outputs))
            continue
        result=solve_dmu(x[i],y[i],x,y,xs,ys)
        if result['status']!='optimal':raise ValueError(f"基线求解失败 {r['venue_code']}: {result['status']}")
        result=_decorate_baseline(result,r,inputs,outputs,records)
        baseline_map[key]=result
        baseline.append(result)
        progress('baseline')
        emit()

    influence={r['observation_id']:0. for r in records}
    for target in baseline:
        for peer in target['peers']:
            if peer['observation_id']!=target['observation_id']:influence[peer['observation_id']]+=peer['lambda']
    selected=sorted([r for r in records if influence[r['observation_id']]>1e-7],key=lambda r:(-influence[r['observation_id']],r['venue_code']))[:sensitivity_count]
    selected_ids=[r['observation_id'] for r in selected]
    stored_order=state.get('scenario_order') or []
    if stored_order and stored_order!=selected_ids:
        raise CheckpointMismatch('断点中的标杆移除顺序与当前同期样本不一致，拒绝混用旧结果')
    state['scenario_order']=selected_ids
    state['influence']={str(r['observation_id']):influence[r['observation_id']] for r in records}
    state['phase']='scenarios'

    scenario_map=state.setdefault('scenarios',{})
    if not isinstance(scenario_map,dict):
        raise CheckpointMismatch('断点中的标杆移除进度无效，拒绝混用旧结果')
    scenarios=[]
    for scenario_index,removed in enumerate(selected):
        removed_id=removed['observation_id']
        keep=[i for i,r in enumerate(records) if r['observation_id']!=removed_id]
        scenario_key=str(removed_id)
        saved_scenario=scenario_map.get(scenario_key)
        if saved_scenario is None:
            saved_scenario={
                'removed_observation_id':removed_id,
                'removed_code':removed['venue_code'],
                'removed_name':removed['venue_name'],
                'aggregate_external_lambda':influence[removed_id],
                'reference_ids':[records[i]['observation_id'] for i in keep],
                'scores':{},
            }
            scenario_map[scenario_key]=saved_scenario
            progress('scenarios',scenario_index,len(selected),0,len(records))
            emit()
        if not isinstance(saved_scenario,dict) or not isinstance(saved_scenario.get('scores'),dict):
            raise CheckpointMismatch('断点中的标杆移除进度无效，拒绝混用旧结果')
        if saved_scenario.get('removed_observation_id')!=removed_id or saved_scenario.get('reference_ids')!= [records[i]['observation_id'] for i in keep]:
            raise CheckpointMismatch('断点中的标杆移除进度与当前同期样本不一致，拒绝混用旧结果')
        score_map=saved_scenario['scores']
        scores=[]
        for i,target in enumerate(records):
            target_key=str(target['observation_id'])
            saved_score=score_map.get(target_key)
            if saved_score is not None:
                if not isinstance(saved_score,dict) or saved_score.get('observation_id')!=target['observation_id']:
                    raise CheckpointMismatch('断点中的标杆移除分数与当前同期样本不一致，拒绝混用旧结果')
                scores.append(saved_score)
                continue
            solution=solve_dmu(x[i],y[i],x[keep],y[keep],xs,ys)
            theta=solution['theta'];base=baseline[i]['theta']
            if theta is not None and theta<base-1e-6:raise ValueError('移除参照后theta不应下降，请核验求解器')
            saved_score={'observation_id':target['observation_id'],'venue_code':target['venue_code'],'status':solution['status'],'theta':theta,'delta':None if theta is None else theta-base,'removed_target_self':target['observation_id']==removed_id}
            score_map[target_key]=saved_score
            scores.append(saved_score)
            progress('scenarios',scenario_index,len(selected),len(score_map),len(records))
            emit()
        scenarios.append({
            'removed_observation_id':saved_scenario['removed_observation_id'],
            'removed_code':saved_scenario['removed_code'],
            'removed_name':saved_scenario['removed_name'],
            'aggregate_external_lambda':influence[removed_id],
            'reference_ids':[records[i]['observation_id'] for i in keep],
            'scores':scores,
        })

    state['phase']='completed'
    progress('completed',len(selected),len(selected),len(records),len(records))
    emit()
    result={
        'baseline':baseline,
        'scenarios':scenarios,
        'input_scales':dict(zip(inputs,xs.tolist())),
        'output_scales':dict(zip(outputs,ys.tolist())),
        'reference_ids':[r['observation_id'] for r in records],
        'self_included_baseline':True,
        'sensitivity_policy':SENSITIVITY_POLICY,
        'n':len(records),
        'inputs':inputs,
        'outputs':outputs,
        'efficient_count':sum(r['strong_efficient'] for r in baseline),
        'mean_theta':float(np.mean([r['theta'] for r in baseline])),
    }
    return result,state


def analyze_frontier(records,inputs,outputs,sensitivity_count=3):
    return analyze_frontier_resumable(records,inputs,outputs,sensitivity_count)[0]
