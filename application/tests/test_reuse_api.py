"""Fresh SQLite/API records and an explicit private compatibility double.

Captured scientific bytes stay inert. This verifies public authority and retained
reads, not native numerical execution or the later result-picker journey.
"""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from execution_fixtures import fixture, runtime_fixture
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.store import Store, DomainError, canonical, digest, uid

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = 'http://127.0.0.1:19999'


class PrivateModelDouble:
    def __init__(self, case): self.case=case; self.calls=[]; self.offline=False
    def call(self, actor, sid, method, path, body=None, **kwargs):
        if self.offline: raise AssertionError('Retained read/replay contacted modeling')
        self.calls.append((actor,sid,method,path,copy.deepcopy(body),kwargs))
        model=copy.deepcopy(self.case['frozen']['model_snapshot'])
        if method=='GET' and path=='/capabilities':
            # AE discovery probes the private producer. This legacy double must
            # explicitly advertise only its existing configuration support.
            from test_assumptions_evidence_contracts import sample,D
            result=sample(D['Capabilities'])
            result.update(contract_versions=['1.1'],schema_versions=['1'],service_build='isolated-api-private-double',
                generator_identity=copy.deepcopy(self.case['prepared']['generator_identity']))
        elif method=='GET' and path.endswith('/revisions/'+model['model_revision_id']):
            result=model
        else:
            assert method=='POST' and path.endswith('/configuration-compatibility')
            validate(kwargs['request_schema'],body)
            candidate=body['configuration_candidate']
            result=dict(schema_version='2',model_revision_id=model['model_revision_id'],model_digest=model['digest'],
                candidate_digest=digest(candidate),compatible=True,diagnostics=[],required_capabilities=model['required_capabilities'],
                validator_identity='isolated-api-private-double',input_interpretations=[dict(target=i['target'],conversion=dict(
                    policy='openmdao-linear-catalog-1',catalog_digest='a'*64,source_units=i['units'],destination_units=i['units'],
                    factor=1,destination_value=i['value'])) for i in candidate['inputs']])
        validate(kwargs['response_schema'],dict(schema_version='1',request_id=uid(),data=result))
        return 200,dict(data=result)


@pytest.fixture
def api(tmp_path):
    store=Store(tmp_path/'reuse.sqlite');auth=Auth(store,ORIGIN)
    actor=auth.provision('owner','correct horse battery staple')
    study=store.create_study(actor,uid(),'Fresh source study');sid=study['study_id']
    case=fixture('chain');config=case['frozen']['configuration']
    config.update(schema_version='2',study_id=sid,context_source=dict(kind='current_study',expected_study_revision=study['revision']),derivation=None)
    config['context_snapshot'].update(description='',boundary='')
    for item in config['inputs']:item['result_binding']=None
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    validate('ConfigurationRevision2',config)
    prepared=case['prepared'];prepared['configuration_digest']=project_scientific_configuration(config)['digest']
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(case['frozen'])))
        db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,config['model_id'],uid()))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],sid,config['configuration_revision_id']))
    run=Submissions(store,None,None).submit(actor,sid,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
    rid=run['run_id'];bundle=assemble_bundle(rid,prepared,case['files'],case['frozen'],runtime_fixture(),dict(schema_version='1',sources=[],mappings=[]))
    request=dict(run_id=rid,scope=sid,command_id=run['command_id'],payload_digest=store.receipt(actor,sid,'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    outputs=json.loads(case['files'][prepared['entrypoint']['bindings_path']])['outputs']
    results=dict(schema_version='1',run_id=rid,bundle_digest=request['bundle_digest'],execution=dict(state='finished',exit_code=0,message='Complete'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),
        outputs=[dict(target=o['target'],value=150+i,units=o['units'],availability='available',reason=None,producer_completed=True,assigned=True) for i,o in enumerate(outputs)],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    association=dict(store_uuid=uid(),process_uuid=uid())
    payload=dict(actor=actor,frozen=copy.deepcopy(case['frozen']),request=request,
        bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()}))
    payload['history']=projection(payload,dict(request=request,bundle=bundle,results=results,assessment=None,artifacts={},errors=[])|association,association)
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),rid))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),rid))
    model=PrivateModelDouble(case);client=TestClient(create_app(store,auth,model),base_url=ORIGIN)
    session=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    assert session.status_code==200
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':session.json()['data']['csrf_token']})
    candidate=dict(schema_version='2',study_id=sid,model_id=config['model_id'],model_revision_id=config['model_revision_id'],name='Linked comparison',
        inputs=[dict(kind='run_result',target=config['inputs'][0]['target'],source_run_id=rid,source_output=results['outputs'][0]['target'],expected_results_digest=digest(results),provenance=config['inputs'][0]['provenance']),
            *[dict(kind='literal',**{k:v for k,v in i.items() if k!='result_binding'}) for i in config['inputs'][1:]]],
        criteria=[],numerical=config['numerical'],context_source=config['context_source'],notes=[],evidence_version_ids=[],derivation=None)
    return dict(client=client,store=store,auth=auth,actor=actor,sid=sid,rid=rid,case=case,model=model,candidate=candidate,bundle=bundle)


def path(api,suffix):return '/api/1/studies/'+api['sid']+'/'+suffix


def preview(api,candidate=None):
    response=api['client'].post(path(api,'configurations/preview'),json=candidate or api['candidate'])
    assert response.status_code==200,response.text
    validate('ConfigurationPreview2',response.json()['data'])
    return response.json()['data']


def commit_body(api):
    return dict(command_id=uid(),expected_revision=None,configuration_id=None,configuration=copy.deepcopy(api['candidate']),expected_preview_digest=preview(api)['candidate_digest'])


def test_inventory_reads_fresh_retained_bytes_offline_and_pages(api):
    api['model'].offline=True;c=api['client'];route=path(api,'result-sources')
    page=c.get(route,params={'limit':1});assert page.status_code==200,page.text
    data=page.json()['data'];validate('ResultSourcePage',data)
    assert len(data['items'])==1 and data['next_cursor']
    item=data['items'][0];assert item['source_run_id']==api['rid'] and item['labels']['model_name'] is None
    assert item['native_availability']=='not_rechecked' and item['value']==150
    next_page=c.get(route,params={'limit':1,'cursor':data['next_cursor']}).json()['data']
    assert next_page['items'][0]['source_output']!=item['source_output'] and next_page['next_cursor'] is None
    assert not api['model'].calls


@pytest.mark.parametrize('query',['limit=0','limit=51','limit=true','limit=1.0','limit=01','limit=1&limit=2','process_uuid=x','cursor=bad','cursor='+('a'*2049)])
def test_inventory_closed_bounded_query(api,query):
    response=api['client'].get(path(api,'result-sources')+'?'+query)
    assert response.status_code==400 and response.json()['error']['code']=='invalid_request'
    assert len(response.content)<4096 and not api['model'].calls


def test_inventory_session_current_membership_scoped_cursor(api):
    c=api['client'];route=path(api,'result-sources')
    assert TestClient(c.app,base_url=ORIGIN).get(route,headers={'X-Actor-ID':api['actor']}).status_code==401
    foreign=api['store'].create_study(uid(),uid(),'Foreign')['study_id']
    assert c.get(route.replace(api['sid'],foreign)).status_code==404
    cursor=c.get(route,params={'limit':1}).json()['data']['next_cursor']
    assert c.get(route,params={'limit':2,'cursor':cursor}).status_code==400
    other=api['store'].create_study(api['actor'],uid(),'Other')['study_id']
    assert c.get(route.replace(api['sid'],other),params={'limit':1,'cursor':cursor}).status_code==400
    with api['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(api['sid'],))
    assert c.get(route).status_code==404


def test_preview_commit_replay_receipt_and_retained_run_schema(api):
    c=api['client'];body=commit_body(api);before=copy.deepcopy(api['bundle'])
    response=c.post(path(api,'configurations'),json=body);assert response.status_code==201,response.text
    saved=response.json()['data'];linked=saved['configuration']['inputs'][0]
    assert linked['value']==linked['result_binding']['original_value']==150
    assert linked['result_binding']['labels']['model_name'] is None
    api['model'].offline=True
    assert c.post(path(api,'configurations'),json=body).json()['data']==saved
    receipt=c.get(path(api,'commands/'+body['command_id']),params={'category':'configuration'})
    assert receipt.status_code==200 and receipt.json()['data']['result']==saved
    assert c.post(path(api,'configurations'),json=body|{'expected_preview_digest':'b'*64}).status_code==409
    assert api['bundle']==before
    detail=c.get(path(api,'runs/'+api['rid']));assert detail.status_code==200 and detail.json()['data']['history']['bundle']['schema_version']=='3'


@pytest.mark.parametrize('forgery',['value','units','result_binding','process_uuid','source_study','source_run','digest','duplicate','stale_context'])
def test_public_request_rejects_forged_authority(api,forgery):
    candidate=copy.deepcopy(api['candidate']);item=candidate['inputs'][0]
    if forgery in ('value','units','result_binding','process_uuid'):item[forgery]=150 if forgery=='value' else 'forged'
    elif forgery=='source_study':candidate['study_id']=uid()
    elif forgery=='source_run':item['source_run_id']=uid()
    elif forgery=='digest':item['expected_results_digest']='a'*64
    elif forgery=='duplicate':candidate['inputs'].append(copy.deepcopy(item))
    else:candidate['context_source']['expected_study_revision']=uid()
    response=api['client'].post(path(api,'configurations/preview'),json=candidate)
    assert response.status_code in (400,404,409),response.text
    assert len(response.json()['error']['fields'])<=20


def test_commit_requires_exact_preview_and_current_authorization(api):
    c=api['client'];body=commit_body(api)
    assert c.post(path(api,'configurations'),json=body|{'expected_preview_digest':'a'*64}).status_code==409
    assert c.post(path(api,'configurations'),json={k:v for k,v in body.items() if k!='expected_preview_digest'}).status_code==400
    assert c.post(path(api,'configurations'),json=body,headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert c.post(path(api,'configurations/preview'),json=api['candidate'],headers={'Origin':'http://foreign.invalid'}).status_code==403
    saved=c.post(path(api,'configurations'),json=body);assert saved.status_code==201,saved.text
    with api['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(api['sid'],))
    assert c.post(path(api,'configurations'),json=body).status_code==404


def test_inventory_run_scan_bound_and_stable_high_water(api,monkeypatch):
    from hyprn_mvp_app.result_bindings import ResultBindings
    service=Submissions(api['store'],None,None);revision=api['case']['frozen']['configuration']['configuration_revision_id']
    for _ in range(103):service.submit(api['actor'],api['sid'],dict(command_id=uid(),configuration_revision_id=revision))
    calls=[];original=ResultBindings.retained
    def counted(self,actor,sid,rid):calls.append(rid);return original(self,actor,sid,rid)
    monkeypatch.setattr(ResultBindings,'retained',counted)
    c=api['client'];route=path(api,'result-sources');page=c.get(route).json()['data']
    assert len(calls)==100 and len(page['items'])==2 and page['next_cursor']
    later=service.submit(api['actor'],api['sid'],dict(command_id=uid(),configuration_revision_id=revision))
    calls.clear();page=c.get(route,params={'cursor':page['next_cursor']}).json()['data']
    assert len(calls)==4 and later['run_id'] not in calls and page==dict(items=[],next_cursor=None)


@pytest.mark.parametrize('change',['source_changed','source_missing','revoke','foreign_source'])
def test_save_rechecks_sources_after_preview(api,change):
    body=commit_body(api)
    with api['store'].connection(write=True) as db:
        if change=='source_changed':db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),api['rid']))
        elif change=='source_missing':db.execute("UPDATE outbox SET payload='{}' WHERE run_id=?",(api['rid'],))
        elif change=='revoke':db.execute('DELETE FROM memberships WHERE study_id=?',(api['sid'],))
    if change=='foreign_source':body['configuration']['inputs'][0]['source_run_id']=uid()
    response=api['client'].post(path(api,'configurations'),json=body)
    assert response.status_code in (404,409),response.text
    with api['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==1


def test_acknowledgement_loss_reopens_same_command_and_immutable_saved_binding(api):
    c=api['client'];body=commit_body(api)
    result=c.post(path(api,'configurations'),json=body);assert result.status_code==201
    # Drop acknowledgement, recreate the application, then reconcile exact receipt.
    reopened=Store(api['store'].path);api['model'].offline=True
    restarted=TestClient(create_app(reopened,Auth(reopened,ORIGIN),api['model']),base_url=ORIGIN)
    restarted.cookies.update(c.cookies);restarted.headers.update(c.headers)
    receipt=restarted.get(path(api,'commands/'+body['command_id']),params={'category':'configuration'})
    assert receipt.json()['data']['result']==result.json()['data']
    with reopened.connection(write=True) as db:db.execute("UPDATE outbox SET payload='{}' WHERE run_id=?",(api['rid'],))
    assert restarted.post(path(api,'configurations'),json=body).json()['data']==result.json()['data']
    with reopened.connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==2


def test_typed_client_preserves_exact_save_and_submit_on_uncertainty(tmp_path):
    script=r'''
const fs=require('node:fs'), assert=require('node:assert/strict');
const root=process.argv[1], ts=require(root+'/ui/node_modules/typescript');
const source=fs.readFileSync(root+'/ui/src/api.ts','utf8');
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
(async()=>{
 const client=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
 const [[,PublicApi],...otherApis]=Object.entries(client).filter(([name,value])=>typeof value==='function'&&/Api$/.test(name));assert.equal(otherApis.length,0);
 const api=new PublicApi();api.actor='owner';api.csrf='csrf';const calls=[];
 const command={command_id:'original-command',expected_revision:null,configuration_id:null,expected_preview_digest:'a'.repeat(64),configuration:{schema_version:'2',study_id:'study',name:'Exact original',inputs:[{kind:'run_result',source_run_id:'source'}]}};
 const original=structuredClone(command);let retry=false;
 global.fetch=async(url,options)=>{calls.push({url,body:options.body});if(options.method==='GET')return new Response(JSON.stringify({error:{code:'resource_not_found',outcome:'unchanged'}}),{status:404});if(!retry)throw new Error('Lost acknowledgement');return new Response(JSON.stringify({data:{configuration:{}}}),{status:201});};
 await assert.rejects(api.commitConfiguration2(command),/Lost acknowledgement/);
 command.configuration.name='Edited after request';command.command_id='replacement';
 assert.deepEqual(api.pending.body,original);await api.reconcile();assert.equal(api.retryReady,true);
 retry=true;await api.retryOriginal();const writes=calls.filter(c=>c.body);
 assert.equal(writes.length,2);assert.equal(writes[0].body,writes[1].body);assert.equal(api.pending,null);
 retry=false;calls.length=0;await assert.rejects(api.submitRun('study','revision'),/Lost acknowledgement/);
 const accepted=structuredClone(api.pending.body);assert.equal(accepted.configuration_revision_id,'revision');
 global.fetch=async(url,options)=>{calls.push({url,body:options.body});return new Response(JSON.stringify({data:{command_id:accepted.command_id,state:'uncertain',result:{run_id:'run'},error:null}}));};
 await api.reconcile();assert.deepEqual(api.pending.body,accepted);assert.equal(api.retryReady,false);
 await assert.rejects(api.retryOriginal(),/Check the original/);assert.equal(calls.filter(c=>c.body).length,1);
 console.log('Exact save retry and uncertain-run no redispatch verified');
})().catch(e=>{console.error(e);process.exit(1)});
'''
    result=subprocess.run(['/opt/homebrew/bin/node','-e',script,str(ROOT)],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert 'verified' in result.stdout


def test_literal_request2_remains_supported_and_capabilities_are_bounded(api):
    candidate=copy.deepcopy(api['candidate']);config=api['case']['frozen']['configuration']
    candidate['inputs']=[dict(kind='literal',**{k:v for k,v in i.items() if k!='result_binding'}) for i in config['inputs']]
    result=preview(api,candidate);assert all(i['result_binding'] is None for i in result['resolved_candidate']['inputs'])
    caps=api['client'].get('/api/1/capabilities').json()['data']
    assert 'result_linked_inputs/1' in caps['engineering']
    assert caps['limits']['result_source_outputs']==50 and caps['limits']['result_source_runs']==100
    # Study archive is advertised as a capability and never listed as unavailable.
    assert 'study_archive/1' in caps['engineering'] and 'archive' not in caps['unavailable']
    assert not any('modified' in x for x in caps['engineering'])


def test_generated_public_schemas_match_actual_responses_and_are_reproducible(api,tmp_path):
    output=tmp_path/'openapi.json';result=subprocess.run([sys.executable,'-B',str(ROOT/'application/generate_contract.py'),'--output',str(output)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert output.read_bytes()==(ROOT/'contracts/hyprn-mvp.openapi.yaml').read_bytes()
    spec=json.loads(output.read_text());schemas=spec['components']['schemas']
    assert schemas['PublicRunDetail']['properties']['runtime_comparison']=={'$ref':'#/components/schemas/RuntimeComparison'}
    validator=lambda schema:Draft202012Validator({'components':spec['components'],**schema},format_checker=FormatChecker())
    cases=[('/studies/{study_id}/result-sources','get',api['client'].get(path(api,'result-sources'))),
        ('/studies/{study_id}/configurations/preview','post',api['client'].post(path(api,'configurations/preview'),json=api['candidate'])),
        ('/studies/{study_id}/runs/{run_id}','get',api['client'].get(path(api,'runs/'+api['rid']))),
        ('/capabilities','get',api['client'].get('/api/1/capabilities'))]
    body=commit_body(api);cases.append(('/studies/{study_id}/configurations','post',api['client'].post(path(api,'configurations'),json=body)))
    cases.append(('/studies/{study_id}/commands/{command_id}','get',api['client'].get(path(api,'commands/'+body['command_id']),params={'category':'configuration'})))
    for route,method,response in cases:
        assert response.status_code<300,response.text
        schema=spec['paths'][route][method]['responses'][str(response.status_code)]['content']['application/json']['schema']
        assert not list(validator(schema).iter_errors(response.json())),(route,response.text)
    commit_schema=spec['paths']['/studies/{study_id}/configurations']['post']['requestBody']['content']['application/json']['schema']
    assert not list(validator(commit_schema).iter_errors(body))
    assert list(validator(commit_schema).iter_errors(body|{'process_uuid':uid()}))
    generated=tmp_path/'contract.ts'
    result=subprocess.run([sys.executable,'-B',str(ROOT/'ui/generate_types.py'),'--input',str(output),'--output',str(generated)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert generated.read_bytes()==(ROOT/'ui/src/contract.ts').read_bytes()


@pytest.mark.parametrize('group,interpreter',[('api-a','/usr/bin/python3'),('api-a','native'),('contracts','application')])
def test_runner_rejects_unapproved_group_interpreter(monkeypatch,group,interpreter):
    import checks
    from dataclasses import replace
    actual={'native':checks.fixture.APPROVED_PYTHON,'application':checks.fixture.APPROVED_CONTRACT_PYTHON}.get(interpreter,interpreter)
    monkeypatch.setattr(checks.fixture,'scope_from_environment',lambda:replace(checks.PROJECTION_SCOPE,interpreter=actual))
    monkeypatch.setattr(checks.sys,'executable',actual)
    with pytest.raises(ValueError,match='reviewed interpreter'):checks.contracts_child(group)


def test_combined_manifest_has_separate_real_journey_and_app_boundaries():
    import checks
    assert checks.GROUPS['combined-native'] == (
        'deployment/tests/test_native_journey.py::test_combined',)
    assert checks.GROUP_INTERPRETERS.get('combined-native',checks.fixture.APPROVED_PYTHON)==checks.fixture.APPROVED_PYTHON
    assert checks.GROUP_INTERPRETERS['api-a']==checks.fixture.APPROVED_CONTRACT_PYTHON
    assert (ROOT/'deployment/tests/combined_fixture.py').is_file()
