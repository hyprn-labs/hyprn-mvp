"""Untrusted numerical result rejection without executing any candidate."""
import copy
import json
import pytest
from execution_fixtures import fixture,uid

pytestmark=pytest.mark.integration

def record():
    case=fixture('unrelated');target=case['targets']['response']['response']
    request=dict(run_id=uid(),bundle_digest='a'*64)
    result=dict(schema_version='1',**request,
        execution=dict(state='finished',exit_code=0,message='completed'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),
        optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=1,available=1,failed=0,unavailable=0),
        outputs=[dict(target=target,value=3,units='',availability='available',reason=None,producer_completed=True,assigned=True)],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    return case,request,result

def envelope(result):
    return json.dumps(dict(reason='exited',exit_code=0,output='HYPRN_MVP_RESULT_V1 '+json.dumps(result)))

def test_data_only_result_is_accepted():
    from hyprn_mvp_integration.calculation import validate_result
    case,request,result=record()
    assert validate_result(envelope(result),request,case['frozen']['model_snapshot'])==result

@pytest.mark.parametrize('mode',['identity','nan','infinity','unassigned','incomplete','duplicate','missing','count','path','applicability','units','native_field','depth','oversize','duplicate_key'])
def test_malformed_candidate_data_is_rejected(mode):
    from hyprn_mvp_integration.calculation import validate_result
    case,request,result=record();o=result['outputs'][0]
    if mode=='identity':result['run_id']=uid()
    elif mode=='nan':o['value']=float('nan')
    elif mode=='infinity':o['value']=float('inf')
    elif mode=='unassigned':o['assigned']=False
    elif mode=='incomplete':o['producer_completed']=False
    elif mode=='duplicate':result['outputs'].append(copy.deepcopy(o))
    elif mode=='missing':result['outputs']=[]
    elif mode=='count':result['completeness']['available']=2
    elif mode=='path':result['artifacts']=[dict(path='../secret',sha256='a'*64,size=1,media_type='text/plain')]
    elif mode=='applicability':result['applicability']['state']='supported'
    elif mode=='units':o['units']='m'
    elif mode=='native_field':o['native_process_uuid']=uid()
    elif mode=='depth':
        v={};result['extra']=v
        for _ in range(30):v['x']={};v=v['x']
    elif mode=='oversize':result['execution']['message']='x'*140000
    raw=envelope(result)
    if mode=='duplicate_key':raw=raw.replace('"reason": "exited"','"reason": "exited", "reason": "exited"')
    with pytest.raises((ValueError,TypeError,KeyError)):
        validate_result(raw,request,case['frozen']['model_snapshot'])
