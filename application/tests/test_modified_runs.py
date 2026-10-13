"""Actual fresh API/SQLite modified attempts; explicit private compatibility double.

Source bytes are inert captured artifacts. Native computation/UI journey is the
later checkpoint; these tests exercise retained authority and durable commands.
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
from test_reuse_api import api, path, ROOT, ORIGIN, commit_body
from hyprn_mvp_app.store import canonical, digest, uid, DomainError
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.history import History, projection
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from execution_fixtures import runtime_fixture


def seed(api,rid=None):
    r=api['client'].get(path(api,'runs/'+(rid or api['rid'])+'/modified-run-seed'))
    assert r.status_code==200,r.text
    value=r.json()['data'];validate('ModifiedRunSeed1',value);return value


def preview(api,request):
    r=api['client'].post(path(api,'configurations/preview'),json=request)
    assert r.status_code==200,r.text
    value=r.json()['data'];validate('ConfigurationPreview2',value);return value


def body(api,request):
    return dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=copy.deepcopy(request),expected_preview_digest=preview(api,request)['candidate_digest'])


def update_study(api,**changes):
    store=api['store'];study=store.study(api['actor'],api['sid'])
    return store.update_study(api['actor'],api['sid'],uid(),study['revision'],changes)


def payload(api,rid=None):
    with api['store'].connection() as db:return json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid or api['rid'],)).fetchone()[0])


def alter_projection(api,change):
    p=payload(api);change(p);p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'})
    with api['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(p),api['rid']))


def retain(api,frozen,*,dependencies=None):
    """Retain a new synthetic terminal run after real API save; never mutate its source."""
    store=api['store'];c=frozen['configuration'];run=Submissions(store,None,None).submit(api['actor'],api['sid'],dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    prepared=copy.deepcopy(api['case']['prepared']);private=project_scientific_configuration(c)
    prepared.update(configuration_revision_id=c['configuration_revision_id'],configuration_digest=private['digest'])
    prepared['executable_content_digest']=executable_digest(prepared);prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    bundle=assemble_bundle(run['run_id'],prepared,api['case']['files'],frozen,runtime_fixture(),dependencies or dict(schema_version='1',sources=[],mappings=[]))
    original=payload(api);results=copy.deepcopy(original['history']['results']);results.update(run_id=run['run_id'],bundle_digest=bundle['manifest']['bundle_digest'])
    request=dict(run_id=run['run_id'],scope=api['sid'],command_id=run['command_id'],payload_digest=store.receipt(api['actor'],api['sid'],'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    association=dict(store_uuid=uid(),process_uuid=uid());p=dict(actor=api['actor'],frozen=frozen,request=request,bundle=dict(manifest=bundle['manifest'],files={k:base64.b64encode(v).decode() for k,v in bundle['files'].items()}))
    p['history']=projection(p,dict(request=request,bundle=bundle,results=results,assessment=None,artifacts={},errors=[])|association,association)
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),run['run_id']))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(p),run['run_id']))
    return run['run_id']


def test_seed_is_exact_read_only_during_model_outage_and_cancel(api):
    api['model'].offline=True;before=api['store'].path.read_bytes();source=copy.deepcopy(payload(api))
    value=seed(api);config=api['case']['frozen']['configuration']
    assert api['store'].path.read_bytes()==before and payload(api)==source and not api['model'].calls
    assert value['configuration']['model_revision_id']==config['model_revision_id']
    assert value['configuration']['derivation']==dict(source_run_id=api['rid'],source_configuration_digest=config['digest'])
    assert value['configuration']['context_source']['kind']=='source_run'
    assert value['source_runtime']==api['bundle']['manifest']['runtime']
    assert value['runtime_comparison']['state']=='unavailable'
    assert not value['context_changed'] and not value['requires_context_choice']
    assert 'configuration_id' not in value['configuration']
    assert seed(api)==value and api['store'].path.read_bytes()==before


def test_changed_context_requires_explicit_choice_and_exact_observed_revision(api):
    current=update_study(api,description='New question',boundary='New boundary');value=seed(api);request=value['configuration']
    assert value['context_changed'] and value['requires_context_choice'] and not request['context_source']['choice_confirmed']
    assert value['source_context']['description']=='' and value['current_context']['description']=='New question'
    response=api['client'].post(path(api,'configurations/preview'),json=request)
    assert response.status_code==409 and response.json()['error']['code']=='context_choice_required'
    request['context_source']['choice_confirmed']=True
    historical=preview(api,request);assert historical['resolved_candidate']['context_snapshot']['description']==''
    request['context_source']=dict(kind='current_study',expected_study_revision=current['revision'])
    selected=preview(api,request);assert selected['resolved_candidate']['context_snapshot']['description']=='New question'
    assert any(c['path']=='/context_snapshot/description' for c in selected['changes'])
    command=body(api,request);update_study(api,boundary='Concurrent boundary')
    response=api['client'].post(path(api,'configurations'),json=command)
    assert response.status_code==409 and response.json()['error']['code']=='stale_revision'


def test_save_new_family_delta_runtime_and_independent_submission_replay(api):
    source=copy.deepcopy(payload(api));request=seed(api)['configuration'];request['name']='Modified price';request['inputs'][0]['value']+=1
    command=body(api,request);response=api['client'].post(path(api,'configurations'),json=command)
    assert response.status_code==201,response.text
    saved=response.json()['data'];c=saved['configuration'];original=source['frozen']['configuration']
    assert c['configuration_id']!=original['configuration_id'] and c['parent_revision_id'] is None
    assert c['derivation']['source_configuration_revision_id']==original['configuration_revision_id']
    changes={v['path']:v for v in c['derivation']['changes']}
    assert changes['/inputs/0/value']['before_digest']==digest(original['inputs'][0]['value'])
    assert changes['/inputs/0/value']['after_digest']==digest(request['inputs'][0]['value'])
    assert c['derivation']['source_runtime']==api['bundle']['manifest']['runtime']
    assert all(call[2]=='POST' for call in api['model'].calls),api['model'].calls
    api['model'].offline=True
    assert api['client'].post(path(api,'configurations'),json=command).json()['data']==saved
    assert api['client'].post(path(api,'configurations'),json=command|{'expected_preview_digest':'a'*64}).status_code==409
    submit=dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id'])
    first=api['client'].post(path(api,'runs'),json=submit);second=api['client'].post(path(api,'runs'),json=submit)
    assert first.status_code==202 and first.json()['data']==second.json()['data']
    assert first.json()['data']['run_id']!=api['rid']
    assert api['client'].post(path(api,'runs'),json=submit|{'configuration_revision_id':original['configuration_revision_id']}).status_code==409
    assert payload(api)==source


@pytest.mark.parametrize('change',['model','revision','digest','source','context_source','context_digest','snapshot','runtime','changes','numerical'])
def test_forged_derivation_context_model_and_metadata_rejected(api,change):
    request=seed(api)['configuration']
    if change=='model':request['model_id']=uid()
    elif change=='revision':request['model_revision_id']=uid()
    elif change=='digest':request['derivation']['source_configuration_digest']='a'*64
    elif change=='source':request['derivation']['source_run_id']=uid()
    elif change=='context_source':request['context_source']['source_run_id']=uid()
    elif change=='context_digest':request['context_source']['source_configuration_digest']='b'*64
    elif change=='snapshot':request['context_snapshot']={'description':'forged'}
    elif change=='runtime':request['derivation']['source_runtime']=runtime_fixture()['runtime']
    elif change=='changes':request['derivation']['changes']=[]
    else:request['numerical']['mode']='invented'
    response=api['client'].post(path(api,'configurations/preview'),json=request)
    assert response.status_code in (400,404,409,422),response.text
    with api['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==1


@pytest.mark.parametrize('change',['family','expected_revision'])
def test_derivation_cannot_advance_existing_family(api,change):
    command=body(api,seed(api)['configuration']);command['configuration_id' if change=='family' else 'expected_revision']=api['case']['frozen']['configuration']['configuration_id']
    r=api['client'].post(path(api,'configurations'),json=command);assert r.status_code==400 and r.json()['error']['code']=='invalid_request',r.text


@pytest.mark.parametrize('change',['uncertain','running','missing','corrupt','unsupported','results_missing','partial'])
def test_seed_rejects_nonterminal_incomplete_and_unsupported(api,change):
    if change in ('uncertain','running'):
        with api['store'].connection(write=True) as db:db.execute('UPDATE outbox SET state=? WHERE run_id=?',('uncertain' if change=='uncertain' else 'dispatching',api['rid']))
    else:
        def mutate(p):
            if change=='missing':p['history']['bundle_verified']=False
            elif change=='corrupt':p['bundle']['files']['configuration.json']='e30='
            elif change=='unsupported':p['frozen']['configuration']['schema_version']='99'
            elif change=='results_missing':p['history']['results']=None
            else:p['history']['errors']=[dict(code='missing_artifacts',partial=True)]
        alter_projection(api,mutate)
    response=api['client'].get(path(api,'runs/'+api['rid']+'/modified-run-seed'))
    assert response.status_code in (409,422),response.text
    if change=='unsupported':assert response.json()['error']['code']=='unsupported_record_version'


def test_complete_failed_record_is_eligible_and_does_not_supply_reusable_results(api):
    def fail(p):
        r=p['history']['results'];r['execution']=dict(state='failed',exit_code=1,message='Complete failure record')
        r['completeness']=dict(expected=len(r['outputs']),available=0,failed=len(r['outputs']),unavailable=len(r['outputs']))
        for o in r['outputs']:o.update(value=None,availability='unavailable',reason='failed',producer_completed=False,assigned=False)
    alter_projection(api,fail)
    assert seed(api)['source_run_id']==api['rid']
    assert api['client'].get(path(api,'result-sources')).json()['data']['items']==[]


def test_seed_authorization_queries_csrf_and_revoked_replay(api):
    route=path(api,'runs/'+api['rid']+'/modified-run-seed');c=api['client']
    assert TestClient(c.app,base_url=ORIGIN).get(route,headers={'X-Actor-ID':api['actor']}).status_code==401
    foreign=api['store'].create_study(uid(),uid(),'Other')['study_id']
    assert c.get(route.replace(api['sid'],foreign)).status_code==404
    assert c.get(route+'?process_uuid='+uid()).status_code==400
    command=body(api,seed(api)['configuration'])
    assert c.post(path(api,'configurations'),json=command,headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert c.post(path(api,'configurations'),json=command).status_code==201
    with api['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(api['sid'],))
    assert c.get(route).status_code==404 and c.post(path(api,'configurations'),json=command).status_code==404


def test_runtime_observation_changes_and_expires_without_changing_seed_authority(api,monkeypatch):
    import hyprn_mvp_app.readiness as readiness
    now=[1000.];monkeypatch.setattr(readiness,'wall_time',lambda:now[0]);runtime=runtime_fixture()['runtime']
    api['store'].publish_execution_observation('ready',None,1000.,runtime)
    value=seed(api);assert value['runtime_comparison']['state']=='same'
    other=runtime|dict(policy_digest='c'*64);assert other!=runtime;api['store'].publish_execution_observation('ready',None,1000.,other)
    assert preview(api,value['configuration'])['runtime_comparison']['state']=='different'
    now[0]=1030.;assert seed(api)['runtime_comparison']['state']=='unavailable'
    assert seed(api)['source_runtime']==runtime


def test_model_outage_at_compatibility_keeps_seed_and_request(api,monkeypatch):
    request=seed(api)['configuration'];before=copy.deepcopy(request)
    def offline(*a,**kw):raise DomainError('backend_unavailable',503,outcome='unknown')
    monkeypatch.setattr(api['model'],'call',offline)
    response=api['client'].post(path(api,'configurations/preview'),json=request)
    assert response.status_code==503 and request==before and seed(api)['configuration']==before


def test_generated_route_schema_and_types_match(api,tmp_path):
    specfile=tmp_path/'openapi.json';types=tmp_path/'contract.ts'
    subprocess.run([sys.executable,'-B',str(ROOT/'application/generate_contract.py'),'--output',str(specfile)],check=True,capture_output=True)
    assert specfile.read_bytes()==(ROOT/'contracts/hyprn-mvp.openapi.yaml').read_bytes()
    spec=json.loads(specfile.read_text());route=spec['paths']['/studies/{study_id}/runs/{run_id}/modified-run-seed']['get']
    schema=route['responses']['200']['content']['application/json']['schema']
    response=api['client'].get(path(api,'runs/'+api['rid']+'/modified-run-seed'))
    Draft202012Validator(dict(components=spec['components'],**schema),format_checker=FormatChecker()).validate(response.json())
    subprocess.run([sys.executable,'-B',str(ROOT/'ui/generate_types.py'),'--input',str(specfile),'--output',str(types)],check=True,capture_output=True)
    assert types.read_bytes()==(ROOT/'ui/src/contract.ts').read_bytes()


def test_preserves_binding_evidence_and_notes_until_explicit_replacement(api):
    from hyprn_mvp_app.result_bindings import ResultBindings
    note=api['client'].post(path(api,'evidence'),json=dict(command_id=uid(),evidence_schema_version='2',
        resource_scope=dict(scope_version='1',kind='study',study_id=api['sid']),kind='note',content='Historical evidence',source_refs=[]))
    assert note.status_code==201,note.text
    eid=note.json()['data']['evidence_version_id'];request=copy.deepcopy(api['candidate']);request['notes']=['Historical assumption']
    request['evidence_version_ids']=[eid];request['inputs'][0]['provenance']['evidence_version_ids']=[eid]
    saved_response=api['client'].post(path(api,'configurations'),json=body(api,request));assert saved_response.status_code==201,saved_response.text
    saved=saved_response.json()['data']
    class Resolver:
        def resolve_results(self,rows):return [dict(row,result_uuid=uid()) for row in rows]
    dependencies=ResultBindings(api['store']).dependencies(api['actor'],api['sid'],saved['configuration'],Resolver())
    rid=retain(api,saved,dependencies=dependencies);original=copy.deepcopy(payload(api,rid))
    request=seed(api,rid)['configuration']
    assert request['inputs'][0]['kind']=='run_result' and request['inputs'][0]['source_run_id']==api['rid']
    assert request['evidence_version_ids']==[eid] and request['notes']==['Historical assumption']
    request['name']='Modified linked attempt'
    resolved=preview(api,request)['resolved_candidate']
    assert resolved['inputs'][0]['result_binding']==saved['configuration']['inputs'][0]['result_binding']
    assert resolved['evidence_snapshots']==saved['configuration']['evidence_snapshots']
    linked=request['inputs'][0];request['inputs'][0]=dict(kind='literal',target=linked['target'],value=42,units='m',provenance=linked['provenance'])
    resolved=preview(api,request)['resolved_candidate'];assert resolved['inputs'][0]['result_binding'] is None
    assert any(c['path']=='/inputs/0/result_binding' for c in resolved['derivation']['changes'])
    assert payload(api,rid)==original
    request['evidence_version_ids']=[]
    assert api['client'].post(path(api,'configurations/preview'),json=request).status_code==409


@pytest.mark.parametrize('race',['study','source','membership'])
def test_commit_rechecks_origin_and_study_after_private_compatibility(api,monkeypatch,race):
    request=seed(api)['configuration'];command=body(api,request);original=api['model'].call
    def change(*a,**kw):
        result=original(*a,**kw)
        if race=='study':update_study(api,description='Concurrent edit')
        else:
            with api['store'].connection(write=True) as db:
                if race=='source':db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),api['rid']))
                else:db.execute('DELETE FROM memberships WHERE study_id=?',(api['sid'],))
        return result
    monkeypatch.setattr(api['model'],'call',change)
    response=api['client'].post(path(api,'configurations'),json=command)
    assert response.status_code in (404,409),response.text
    with api['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==1


def test_concurrent_identical_save_and_submit_allocate_once(api):
    from concurrent.futures import ThreadPoolExecutor
    from hyprn_mvp_app.configuration import Configurations
    from hyprn_mvp_app.modeling import Coordinator
    command=body(api,seed(api)['configuration']);service=Configurations(api['store'],Coordinator(api['store'],api['model']))
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:service.commit(api['actor'],api['sid'],copy.deepcopy(command)),range(2)))
    assert results[0]==results[1]
    submit=dict(command_id=uid(),configuration_revision_id=results[0]['configuration']['configuration_revision_id'])
    submissions=Submissions(api['store'],None,None)
    with ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(lambda _:submissions.submit(api['actor'],api['sid'],copy.deepcopy(submit)),range(2)))
    assert runs[0]==runs[1]
    with api['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==2
        assert db.execute('SELECT COUNT(*) FROM run_associations').fetchone()[0]==2


def test_failed_derivation_cannot_bypass_successful_result_eligibility(api):
    alter_projection(api,lambda p:p['history']['results']['execution'].update(state='failed',exit_code=1))
    request=seed(api)['configuration'];source=payload(api)['history']['results'];item=request['inputs'][0]
    request['inputs'][0]=dict(kind='run_result',target=item['target'],source_run_id=api['rid'],source_output=source['outputs'][0]['target'],expected_results_digest=digest(source),provenance=item['provenance'])
    response=api['client'].post(path(api,'configurations/preview'),json=request)
    assert response.status_code==409 and response.json()['error']['code']=='source_result_unavailable'


@pytest.mark.parametrize('change',['output_missing','wrong_total','invalid_value','nonterminal_result','malformed_completeness'])
def test_seed_requires_complete_valid_retained_outcome(api,change):
    def corrupt(p):
        result=p['history']['results']
        if change=='output_missing':result['outputs'].pop()
        elif change=='wrong_total':result['completeness']['expected']=999
        elif change=='invalid_value':result['outputs'][0]['value']=True
        elif change=='malformed_completeness':result['completeness']=None
        else:result['execution']['state']='running'
    alter_projection(api,corrupt)
    response=api['client'].get(path(api,'runs/'+api['rid']+'/modified-run-seed'))
    assert response.status_code==422 and response.json()['error']['code']=='incomplete_record'


def test_modified_runner_refuses_native_interpreter(monkeypatch):
    import checks
    from dataclasses import replace
    monkeypatch.setattr(checks.fixture,'scope_from_environment',lambda:replace(checks.PROJECTION_SCOPE,interpreter=checks.fixture.APPROVED_PYTHON))
    monkeypatch.setattr(checks.sys,'executable',checks.fixture.APPROVED_PYTHON)
    with pytest.raises(ValueError,match='reviewed interpreter'):checks.contracts_child('modified')


@pytest.fixture
def current_api(api,monkeypatch):
    """Current Model2/Configuration3 history; inert program and synthetic results.

    Reuses the existing guarded fixture builder. No native process or scientific
    execution is claimed; real public API, auth, SQLite and bundle readers apply.
    """
    from types import SimpleNamespace
    from ae_ui_fixture import configuration_case
    from test_assumptions_evidence_contracts import sample,D
    data=dict(api,transport=SimpleNamespace(revisions={}))
    source=configuration_case(data,'current');api['rid']=source['rid']
    retained=payload(api);files={k:base64.b64decode(v) for k,v in retained['bundle']['files'].items()}
    prepared=json.loads(files['preparation.json'])
    api['case']=dict(frozen=source['saved'],prepared=prepared,files={row['path']:files[row['path']] for row in prepared['files']})
    api['model'].case=api['case'];original=api['model'].call
    def call(actor,sid,method,route,body=None,**kwargs):
        if route!='/capabilities':return original(actor,sid,method,route,body,**kwargs)
        if api['model'].offline:raise AssertionError('Retained read contacted modeling')
        caps=sample(D['Capabilities']);cap=sample(D['Capabilities']['properties']['capabilities']['items'])
        cap.update(id='resolved_configuration',version='3',supported=True)
        caps.update(contract_versions=['1.2'],schema_versions=['1','2'],capabilities=[cap],
            generator_identity=copy.deepcopy(api['case']['prepared']['generator_identity']))
        validate('Capabilities',caps)
        return 200,dict(data=caps)
    monkeypatch.setattr(api['model'],'call',call)
    return api


def current_request(api):
    response=api['client'].get(path(api,'runs/'+api['rid']+'/modified-run-seed'))
    assert response.status_code==200,response.text
    value=response.json()['data'];validate('ModifiedRunSeed2',value)
    request=value['configuration'];request['context_source']['choice_confirmed']=True
    request['context_override']=dict(schema_version='1',description='Edited inherited question',boundary=value['source_context']['boundary'])
    request['notes']=['An explicit configuration note']
    return request


def current_preview(api,request):
    response=api['client'].post(path(api,'configurations/preview'),json=request)
    assert response.status_code==200,response.text
    value=response.json()['data'];validate('ConfigurationPreview3',value);return value


def test_modified_context_retains_exact_origin_and_next_seed_during_outage(current_api):
    api=current_api;original=canonical(payload(api));source=copy.deepcopy(api['case']['frozen'])
    current=update_study(api,description='Today\'s different study',boundary='Different scope')
    request=current_request(api);p=current_preview(api,request);candidate=p['resolved_candidate']
    expected=dict(description=request['context_override']['description'],boundary=source['configuration']['context_snapshot']['boundary'],notes=request['notes'])
    assert candidate['context_snapshot']==expected
    changes={v['path']:v for v in p['changes']}
    assert changes['/context_snapshot/description']['after']==expected['description']
    assert '/context_snapshot/boundary' not in changes
    assert candidate['evidence_snapshots']==source['configuration']['evidence_snapshots']
    command=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=request,expected_preview_digest=p['candidate_digest'])
    response=api['client'].post(path(api,'configurations'),json=command);assert response.status_code==201,response.text
    saved=response.json()['data'];assert saved['configuration']['context_snapshot']==expected
    assert api['client'].post(path(api,'configurations'),json=command).json()['data']==saved
    rid=retain(api,saved)
    api['model'].offline=True
    response=api['client'].get(path(api,'runs/'+rid+'/modified-run-seed'));assert response.status_code==200,response.text
    next_seed=response.json()['data'];validate('ModifiedRunSeed2',next_seed)
    assert next_seed['source_context']==expected and next_seed['configuration']['notes']==expected['notes']
    assert next_seed['configuration']['derivation']['source_configuration_digest']==saved['configuration']['digest']
    assert History(api['store']).read(api['actor'],api['sid'],rid)['configuration']==saved['configuration']
    assert canonical(payload(api))==original and api['store'].study(api['actor'],api['sid'])==current
    with api['store'].connection() as db:
        assert json.loads(db.execute('SELECT payload FROM configurations WHERE configuration_revision_id=?',(source['configuration']['configuration_revision_id'],)).fetchone()[0])==source


@pytest.mark.parametrize('failure',['unconfirmed','stale','forged_digest','foreign_run','revoked','source_race'])
def test_modified_override_preserves_source_guards_and_atomicity(current_api,monkeypatch,failure):
    api=current_api;update_study(api,description='Changed study');request=current_request(api)
    p=current_preview(api,request)
    command=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=request,expected_preview_digest=p['candidate_digest'])
    if failure=='unconfirmed':request['context_source']['choice_confirmed']=False
    elif failure=='stale':request['context_source']['observed_study_revision']='stale'
    elif failure=='forged_digest':request['derivation']['source_configuration_digest']='0'*64
    elif failure=='foreign_run':
        other=api['store'].create_study(api['actor'],uid(),'Other study')
        foreign=dict(api,sid=other['study_id'])
        from types import SimpleNamespace
        from ae_ui_fixture import configuration_case
        record=configuration_case(dict(foreign,transport=SimpleNamespace(revisions={})),'current')
        request['derivation']['source_run_id']=record['rid']
        request['context_source']['source_run_id']=record['rid']
    elif failure=='revoked':
        with api['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(api['sid'],))
    else:
        original=api['store'].command
        def command_race(*args,**kwargs):
            with api['store'].connection(write=True) as db:db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),api['rid']))
            return original(*args,**kwargs)
        monkeypatch.setattr(api['store'],'command',command_race)
    def counts():
        with api['store'].connection() as db:return tuple(db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('configurations','configuration_families','outbox'))
    before=counts();response=api['client'].post(path(api,'configurations'),json=command)
    assert response.status_code in (404,409),response.text
    assert counts()==before


# The ModifiedRuns evidence consistency check for earlier configurations. Configuration
# 1/2 bundles do not authenticate their citation closure, so the retained snapshot is
# compared with the immutable stored evidence version. The check is consistency-only: it
# refuses on any difference and never substitutes or merges the stored row.
SNAPSHOT_FIELDS = ('evidence_version_id', 'kind', 'content', 'source_refs', 'evidence_schema_version', 'resource_scope')


def legacy_evidence_source(api):
    """A deterministic configuration-2 retained run citing one stored evidence version."""
    note=api['client'].post(path(api,'evidence'),json=dict(command_id=uid(),evidence_schema_version='2',
        resource_scope=dict(scope_version='1',kind='study',study_id=api['sid']),kind='note',content='Historical evidence',source_refs=[]))
    assert note.status_code==201,note.text
    eid=note.json()['data']['evidence_version_id'];request=copy.deepcopy(api['candidate'])
    source=api['case']['frozen']['configuration']['inputs'][0]
    request['inputs'][0]=dict(kind='literal',**{k:copy.deepcopy(source[k]) for k in ('target','value','units','provenance')})
    request['evidence_version_ids']=[eid];request['inputs'][0]['provenance']['evidence_version_ids']=[eid]
    saved=api['client'].post(path(api,'configurations'),json=body(api,request));assert saved.status_code==201,saved.text
    saved=saved.json()['data'];assert saved['configuration']['schema_version']=='2'
    rid=retain(api,saved);snapshot=payload(api,rid)['frozen']['configuration']['evidence_snapshots']
    assert [s['evidence_version_id'] for s in snapshot]==[eid] and set(snapshot[0])==set(SNAPSHOT_FIELDS)
    return rid,eid


def change_stored_evidence(api,eid,change):
    """Out-of-band storage change; the application itself never updates evidence."""
    with api['store'].connection(write=True) as db:
        db.execute('DROP TRIGGER IF EXISTS immutable_evidence_update')
        stored=json.loads(db.execute('SELECT payload FROM evidence WHERE evidence_version_id=?',(eid,)).fetchone()[0])
        change(stored)
        db.execute('UPDATE evidence SET payload=? WHERE evidence_version_id=?',(json.dumps(stored),eid))


def test_legacy_evidence_check_returns_retained_snapshot_byte_identical_and_never_leaks_stored_fields(api):
    from hyprn_mvp_app.modified_runs import ModifiedRuns
    rid,eid=legacy_evidence_source(api);api['model'].offline=True;retained=copy.deepcopy(payload(api,rid))
    frozen=retained['frozen']['configuration']
    history,stored_payload,_=ModifiedRuns(api['store']).retained(api['actor'],api['sid'],rid)
    assert canonical(history['configuration'])==canonical(frozen)
    assert canonical(history['evidence'])==canonical(frozen['evidence_snapshots'])
    assert stored_payload==retained
    first=seed(api,rid);assert first['configuration']['evidence_version_ids']==[eid]
    # Fields present only in the current stored row (unchanged snapshot fields) are
    # ignored by the consistency check and never reach the returned record.
    change_stored_evidence(api,eid,lambda row:row.update(current_only_field='Current library text',
        current_only_object=dict(note='Current library object')))
    again,_,_=ModifiedRuns(api['store']).retained(api['actor'],api['sid'],rid)
    assert canonical(again)==canonical(history)
    response=api['client'].get(path(api,'runs/'+rid+'/modified-run-seed'));assert response.status_code==200,response.text
    assert 'Current library' not in response.text and 'current_only' not in response.text
    assert response.json()['data']==first
    assert payload(api,rid)==retained


@pytest.mark.parametrize('field',SNAPSHOT_FIELDS)
@pytest.mark.parametrize('mode',['changed','missing'])
def test_legacy_evidence_mismatch_in_any_snapshot_field_is_incomplete_record(api,field,mode):
    from hyprn_mvp_app.modified_runs import ModifiedRuns
    rid,eid=legacy_evidence_source(api);api['model'].offline=True;retained=copy.deepcopy(payload(api,rid))
    def change(row):
        if mode=='missing':row.pop(field)
        else:row[field]=dict(changed=row[field])
    change_stored_evidence(api,eid,change)
    with pytest.raises(DomainError) as error:ModifiedRuns(api['store']).retained(api['actor'],api['sid'],rid)
    assert (error.value.code,error.value.status)==('incomplete_record',422)
    response=api['client'].get(path(api,'runs/'+rid+'/modified-run-seed'))
    assert response.status_code==422 and response.json()['error']['code']=='incomplete_record',response.text
    assert 'Historical evidence' not in response.text
    assert payload(api,rid)==retained
