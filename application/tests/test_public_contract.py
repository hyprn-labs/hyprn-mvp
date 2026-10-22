"""Every public operation documents closed typed responses and aligns with actual routes."""
from hyprn_mvp_app.contracts import authored_schema
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator,FormatChecker
from test_api import api,study,model_revision,post,uid,ORIGIN
from test_submission import submission

SPEC=json.loads((Path(__file__).resolve().parents[2]/"contracts/hyprn-mvp.openapi.yaml").read_text())
def check(response):
    path=urlsplit(str(response.url)).path.removeprefix("/api/1")
    method=response.request.method.lower()
    route=next(v for p,v in SPEC["paths"].items() if re.fullmatch(re.sub(r"\{[^}]+\}","[^/]+",p),path))
    schema=route[method]["responses"][str(response.status_code)]["content"]["application/json"]["schema"]
    Draft202012Validator({**SPEC,**schema},format_checker=FormatChecker()).validate(response.json())

def test_all_routes_and_representative_responses_match_contract(api):
    c=api[0]
    actual={(r.path.removeprefix("/api/1"),m.lower()) for r in c.app.routes for m in r.methods}
    described={(p,m) for p,ops in SPEC["paths"].items() for m in ops}
    assert actual==described
    for method,ops in SPEC["paths"].items():
        for op in ops.values():
            assert set(("400","401","403","404","409","413","422","503"))<=op["responses"].keys()
    s=study(api);sid=s["study_id"]
    for path in ["/studies","/capabilities",f"/studies/{sid}",f"/studies/{sid}/models",f"/studies/{sid}/configurations"]:
        check(c.get("/api/1"+path))
    response=c.post("/api/1/studies",json=dict(command_id=uid(),name="Contract"))
    check(response)
    response=c.patch(f"/api/1/studies/{sid}",json=dict(command_id=uid(),expected_revision="stale",name="Changed"))
    assert response.status_code == 405
    assert 'patch' not in SPEC['paths']['/studies/{study_id}']
    check(c.post(f"/api/1/studies/{sid}/runs",json=dict(command_id=uid(),configuration_revision_id=uid())))

def test_history_list_detail_and_binary_download_match_contract(submission):
    from test_history import recording,client
    run=recording(submission)
    _,store,actor,sid,_,_=submission
    c,_=client(store,actor)
    url=f"/api/1/studies/{sid}/runs"
    check(c.get(url))
    response=c.get(url+'/'+run['run_id']);check(response)
    artifact=response.json()['data']['history']['artifacts'][0]
    downloaded=c.get(url+'/'+run['run_id']+'/artifacts/'+artifact['artifact_id'])
    route=SPEC['paths']['/studies/{study_id}/runs/{run_id}/artifacts/{artifact_id}']['get']['responses']['200']
    assert route['content']['application/octet-stream']['schema']==dict(type='string',format='binary')
    assert downloaded.headers['x-content-sha256']==artifact['sha256']
    assert downloaded.headers['content-disposition'].startswith('attachment;')


def test_evidence_discovery_old_new_receipts_and_filters_match_closed_contract(api):
    c=api[0];s=study(api);sid=s['study_id'];path=f'/api/1/studies/{sid}/evidence'
    old=dict(command_id=uid(),scope=None,kind='note',content='Legacy note',source_refs=[])
    new=dict(command_id=uid(),evidence_schema_version='2',resource_scope=dict(scope_version='1',kind='study',study_id=sid),kind='note',content='Typed note',source_refs=[])
    records=[]
    for body in [old,new]:
        answer=c.post(path,json=body);assert answer.status_code==201;check(answer);records.append(answer.json()['data'])
        check(c.get(path+'/'+records[-1]['evidence_version_id']))
        check(c.get(f"/api/1/studies/{sid}/commands/{body['command_id']}?category=evidence"))
    page=c.get(path+'?limit=1');check(page)
    following=c.get(path,params={'cursor':page.json()['next_cursor'],'limit':100});check(following)
    assert page.json()['data']+following.json()['data']==records
    for query in ['scope_kind=study','legacy_scope=null','limit=0','scope_kind=run&model_id='+uid(),'cursor='+uid()]:check(c.get(path+'?'+query))
    operation=SPEC['paths']['/studies/{study_id}/evidence']
    # The public request names its own definition, which stays identical to the private-mirrored one.
    assert operation['post']['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/PublicEvidenceCreate'}
    assert SPEC['components']['schemas']['PublicEvidenceCreate']==SPEC['components']['schemas']['EvidenceCreate']
    parameters={p['name']:p['schema'] for p in operation['get']['parameters']}
    assert parameters['limit']==dict(type='integer',minimum=1,maximum=100,default=50)
    assert 'legacy' in parameters['scope_kind']['enum']
    assert parameters['model_revision_id']['format']=='uuid'
    # Closed union of every evidence record version; later versions are added beside the earlier ones.
    assert SPEC['components']['schemas']['EvidenceRecord']=={'oneOf':[{'$ref':'#/components/schemas/EvidenceRecord'+n} for n in '123']}


def test_readiness_and_scope_snapshot_contracts_are_closed_and_typed(api):
    import time
    c,store,_,_,transport,_=api;s=study(api);sid=s['study_id'];path=f'/api/1/studies/{sid}/execution-readiness'
    for state,reason in [(None,None),('ready',None),('unavailable','executor_unavailable')]:
        if state:store.publish_execution_observation(state,reason,time.time())
        answer=c.get(path);assert answer.status_code==200;check(answer)
    transport.fail_before=True;check(c.get(path));check(c.get(path+'?status=ready'))
    assert c.get(path.replace(sid,uid())).status_code==404
    model=authored_schema()
    def rewrite(value):
        if isinstance(value,dict):return {k:v.replace('#/$defs/','#/components/schemas/') if k=='$ref' else rewrite(v) for k,v in value.items()}
        if isinstance(value,list):return [rewrite(v) for v in value]
        return value
    for name in ['EvidenceResourceRef1','EvidenceCreate','EvidenceRecord','EvidenceRecord1','EvidenceRecord2']:
        assert SPEC['components']['schemas'][name]==rewrite(model['$defs'][name])
    public=Draft202012Validator({**SPEC,'$ref':'#/components/schemas/EvidenceSnapshot'},format_checker=FormatChecker())
    private=Draft202012Validator({**model,'$ref':'#/$defs/EvidenceSnapshot'},format_checker=FormatChecker())
    basic=dict(evidence_version_id=uid(),kind='note',content='',source_refs=[])
    scope=dict(scope_version='1',kind='study',study_id=sid)
    for value in [basic,dict(basic,evidence_schema_version='2',resource_scope=scope),dict(basic,evidence_schema_version='2'),dict(basic,resource_scope=scope)]:
        assert public.is_valid(value)==private.is_valid(value)
    readiness=SPEC['components']['schemas']['ExecutionReadiness']
    assert readiness['additionalProperties'] is False
    assert readiness['properties']['status']['enum']==['ready','unavailable','unknown']
    assert readiness['properties']['reasons']['items']['enum']==['executor_unavailable','attestation_invalid','modeling_unavailable','observation_stale','capability_unsupported']
