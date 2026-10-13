"""APP-only exact retained identity; synthetic outcomes, no numerical execution."""
from copy import deepcopy
import base64
import json
from pathlib import Path
import sys
import pytest
import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)  # Before application/fixture imports.
from test_unit_execution_admission import catalog, case6, case8, repin, explanatory_model
from test_approach_closure import sample, D, link, resolution, signed
from hyprn_mvp_app.approach_closure import build_closure
from hyprn_mvp_app.store import Store, canonical, digest, uid
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.execution import Submissions, assemble_bundle
from hyprn_mvp_app.history import History, projection
from hyprn_mvp_app import history as history_module
from hyprn_mvp_app.modeling import validate
from execution_fixtures import runtime_fixture
from test_reuse_api import api  # Existing APP-only legacy History1 HTTP fixture.

ORIGIN='http://127.0.0.1:19999'
_PASSWORD_HASH=None

def metadata(rid,h):
    return history_module.retained_read_integrity(rid,h)

def _record(tmp_path,catalog,version='4',failed=False):
    store=Store(tmp_path/'findings.sqlite');auth=Auth(store,ORIGIN)
    global _PASSWORD_HASH
    from hyprn_mvp_app.auth import password_hash
    if _PASSWORD_HASH is None:_PASSWORD_HASH=password_hash('correct horse battery staple')
    actor=uid()
    with store.connection(write=True) as db:db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',(actor,'owner',_PASSWORD_HASH))
    study=store.create_study(actor,uid(),'Findings');sid=study['study_id']
    case=(case8(catalog,model_version='2' if version=='6model2' else '3' if version=='6model3' else '4',approach_version='2' if version in ('6linked','6model2','6model3') else None,legacy=version in ('6legacy','6model2'),mixed=version=='6mixed') if version.startswith('6') else case6(catalog,legacy=version!='4'));f=case['frozen'];c=f['configuration'];m=f['model_snapshot']
    c.update(study_id=sid,context_source=dict(kind='current_study',expected_study_revision=study['revision']))
    f['study_revision']=study['revision']
    if f.get('approach_closure'):
        v=deepcopy(f['approach_closure']['approach_versions'][0]);v['study_id']=sid
        v['content']['original_question']=dict(text='Recorded original',attribution=dict(kind='human',label=None))
        v['content']['elaboration']=dict(text='Recorded explanation',attribution=dict(kind='unknown',label=None))
        cs=sample(D['ApproachCase1']);cs.update(title='Repeated case name',binding_id=v['content']['model_bindings'][0]['binding_id'])
        v['content']['cases']=[cs];signed(v)
        closure=build_closure(v,resolution(models=[m]),study_id=sid)
        f['approach_closure']=closure;c['approach_binding'].update(approach_digest=v['digest'],closure_digest=closure['digest'],case_id=cs['case_id'])
    if version=='2':
        c['schema_version']='3';c.pop('approach_binding');f.pop('schema_version');f.pop('approach_closure')
    if version=='mixed':
        extra=explanatory_model(m,'unspecified');v=sample(D['ApproachVersion1']);v['study_id']=sid
        link(v,m);link(v,extra)
        closure=build_closure(v,resolution(models=[m,extra]),study_id=sid)
        f.update(schema_version='5',approach_closure=closure)
        c['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest=closure['digest'],case_id=None)
    repin(case)
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],sid,json.dumps(f)))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(c['configuration_id'],sid,c['configuration_revision_id']))
    run=Submissions(store,None,None).submit(actor,sid,dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    rid=run['run_id'];b=assemble_bundle(rid,case['prepared'],case['files'],f,runtime_fixture(),dict(schema_version='1',sources=[],mappings=[]))
    request=dict(run_id=rid,scope=sid,command_id=run['command_id'],payload_digest=store.receipt(actor,sid,'run',run['command_id'])['payload_digest'],bundle_digest=b['manifest']['bundle_digest'])
    outputs=json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']
    result=dict(schema_version='1',run_id=rid,bundle_digest=request['bundle_digest'],execution=dict(state='failed' if failed else 'finished',exit_code=int(failed),message='Synthetic fixture'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(outputs),available=0 if failed else len(outputs),failed=len(outputs) if failed else 0,unavailable=len(outputs) if failed else 0),
        outputs=[dict(target=o['target'],value=None if failed else 0,units=o['units'],availability='unavailable' if failed else 'available',reason='Synthetic failure' if failed else None,producer_completed=not failed,assigned=not failed) for o in outputs],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    assoc=dict(store_uuid=uid(),process_uuid=uid())
    p=dict(actor=actor,frozen=f,request=request,bundle=dict(manifest=b['manifest'],files={k:base64.b64encode(v).decode() for k,v in b['files'].items()}))
    p['history']=projection(p,dict(request=request,bundle=b,results=result,assessment=None,artifacts={},errors=[])|assoc,assoc)
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*assoc.values(),rid))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(p),rid))
    return dict(store=store,auth=auth,actor=actor,sid=sid,rid=rid,payload=p)


_RECORD_TEMPLATES={}
def record(tmp_path,catalog,version='4',failed=False):
    """Clone a pristine validated fixture, keeping each corruption test isolated."""
    import shutil
    key=(version,failed)
    if key not in _RECORD_TEMPLATES:
        root=tmp_path.parent/('findings-template-'+version+'-'+str(failed));root.mkdir()
        _RECORD_TEMPLATES[key]=_record(root,catalog,version,failed)
    template=_RECORD_TEMPLATES[key]
    shutil.copy2(template['store'].path,tmp_path/'findings.sqlite')
    store=Store(tmp_path/'findings.sqlite')
    return {**{k:deepcopy(v) for k,v in template.items() if k not in ('store','auth')},
            'store':store,'auth':Auth(store,ORIGIN)}


def replace_configuration(store,revision_id,raw):
    """Inject corruption only into an isolated fixture; restore its exact trigger."""
    with store.connection(write=True) as db:
        triggers=db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='configurations'").fetchall()
        for row in triggers:db.execute('DROP TRIGGER "'+row['name']+'"')
        db.execute('UPDATE configurations SET payload=? WHERE configuration_revision_id=?',(raw,revision_id))
        for row in triggers:db.execute(row['sql'])

def read(e):return History(e['store']).read(e['actor'],e['sid'],e['rid'])
def save(e):
    with e['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(e['payload']),e['rid']))
def reseal(e):
    p=e['payload']['history'];p['digest']=digest({k:v for k,v in p.items() if k!='digest'});save(e)
def logical_rows(store):
    with store.connection() as db:
        names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {n:[tuple(r) for r in db.execute('SELECT * FROM "'+n+'" ORDER BY rowid')] for n in names}

@pytest.mark.parametrize('version',['2','3','4','mixed','6','6legacy','6mixed','6linked','6model2','6model3'])
@pytest.mark.parametrize('failed',[False,True])
def test_exact_history_pairings_zero_failed_and_no_mutation(tmp_path,catalog,version,failed):
    e=record(tmp_path,catalog,version,failed);h=read(e);before=deepcopy(h);rows=logical_rows(e['store'])
    validate('RunHistory'+('6' if version.startswith('6') else '4' if version=='mixed' else version),h)
    assert metadata(e['rid'],h)==dict(schema_version='1',results_digest=digest(h['results']))
    assert h==before and logical_rows(e['store'])==rows
    if not failed:assert h['results']['outputs'][0]['value']==0
    assert not any(n.split('.')[0] in {'aiida','openmdao','openturns'} for n in sys.modules)

@pytest.mark.parametrize('code,valid',[('missing_artifacts',True),('missing_or_invalid_artifact',True),('missing_results',False),('unsupported_record_version',False),('corrupt_retained_record',False),('history_not_recorded',False),('unknown_error',False)])
def test_explicit_integrity_error_allowlist(tmp_path,catalog,code,valid):
    e=record(tmp_path,catalog);e['payload']['history']['errors']=[dict(code=code,partial=True)];reseal(e)
    h=read(e);before=deepcopy(h)
    assert metadata(e['rid'],h)['results_digest']==(digest(h['results']) if valid else None)
    assert h==before and h['errors']==[dict(code=code,partial=True)]

@pytest.mark.parametrize('change',['run','bundle','config_digest','model_digest','config_model_id','config_model_revision','config_bytes','model_bytes','result_version','missing_results','missing_model','missing_config','missing_bundle','bad_output_units','duplicate_output','missing_output','nonfinite','false_zero','unassigned','bad_counts','history_version','bundle_version','swapped_model','swapped_config','unknown_field','unspecified','malformed_unit'])
def test_exact_mismatches_never_authenticate(tmp_path,catalog,change):
    e=record(tmp_path,catalog);h=read(e)
    if change=='run':h['results']['run_id']=uid()
    elif change=='bundle':h['results']['bundle_digest']='f'*64
    elif change.endswith('_digest'):h['bundle'][change.replace('config_','configuration_')]='f'*64
    elif change=='config_model_id':h['configuration']['model_id']=uid()
    elif change=='config_model_revision':h['configuration']['model_revision_id']=uid()
    elif change=='config_bytes':h['configuration']['name']='changed'
    elif change=='model_bytes':h['model_snapshot']['originating_draft_revision']='changed'
    elif change=='result_version':h['results']['schema_version']='2'
    elif change.startswith('missing_') and change!='missing_output':h[{'missing_results':'results','missing_model':'model_snapshot','missing_config':'configuration','missing_bundle':'bundle'}[change]]=None
    elif change=='bad_output_units':h['results']['outputs'][0]['units']='m'
    elif change=='duplicate_output':h['results']['outputs'].append(deepcopy(h['results']['outputs'][0]))
    elif change=='missing_output':h['results']['outputs'].pop()
    elif change=='nonfinite':h['results']['outputs'][0]['value']=float('inf')
    elif change=='false_zero':h['results']['outputs'][0]['value']=False
    elif change=='unassigned':h['results']['outputs'][0]['assigned']=False
    elif change=='bad_counts':h['results']['completeness']['available']=999
    elif change=='history_version':h['history_schema_version']='5'
    elif change=='bundle_version':h['bundle']['schema_version']='5'
    elif change=='swapped_model':h['model_snapshot']['schema_version']='2'
    elif change=='swapped_config':h['configuration']['schema_version']='3'
    elif change=='unknown_field':h['results']['future']=True
    else:
        for p in h['model_snapshot']['definitions'][0]['ports']:p['units']={'kind':'unspecified'} if change=='unspecified' else {'kind':'dimensionless','expression':''}
    before=deepcopy(h);assert metadata(e['rid'],h)['results_digest'] is None;assert h==before

@pytest.mark.parametrize('change',['digest','association','raw','unrecorded'])
def test_stored_corruption_retains_history_errors(tmp_path,catalog,change):
    e=record(tmp_path,catalog);p=e['payload']
    if change=='digest':p['history']['results']['outputs'][0]['value']=18
    elif change=='association':p['history']['association']['process_uuid']=uid()
    elif change=='raw':p['bundle']['files']['model.json']=base64.b64encode(b'{}').decode()
    else:del p['history']
    save(e);h=read(e);assert metadata(e['rid'],h)['results_digest'] is None
    assert h['errors']==[dict(code='history_not_recorded' if change=='unrecorded' else 'corrupt_retained_record',partial=True)]

# ---- One retained pairing table, explicit unsupported versions --------------------------

@pytest.mark.parametrize('version',['2','3','4','mixed','6','6legacy','6model2','6model3'])
def test_retained_integrity_consults_only_the_single_pairing_table(tmp_path,catalog,version,monkeypatch):
    """The reader keeps no copy: withdrawing a record's own pairing from the owner's table makes
    the same authentic record explicitly unsupported (no digest), and nothing else changes."""
    from hyprn_mvp_app import execution_bundle
    e=record(tmp_path,catalog,version);h=read(e);before=deepcopy(h)
    pair=(h.get('history_schema_version','1'),h['bundle']['schema_version'],h['configuration']['schema_version'],h['model_snapshot']['schema_version'])
    assert pair in execution_bundle.RETAINED_PAIRINGS
    assert metadata(e['rid'],h)==dict(schema_version='1',results_digest=digest(h['results']))
    monkeypatch.setattr(history_module,'RETAINED_PAIRINGS',execution_bundle.RETAINED_PAIRINGS-{pair})
    assert metadata(e['rid'],h)==dict(schema_version='1',results_digest=None)
    assert h==before

def restamp_bundle(e,version):
    """Relabel the stored manifest version and re-seal every outer digest, so that only the
    version pairing (never a digest) can refuse the stored record."""
    p=e['payload'];m=p['bundle']['manifest'];m['schema_version']=version
    m['bundle_digest']=digest({k:v for k,v in m.items() if k!='bundle_digest'})
    p['request']['bundle_digest']=m['bundle_digest'];p['history']['request']=deepcopy(p['request'])
    reseal(e)

@pytest.mark.parametrize('version',['7','9','10',''])
def test_unlisted_stored_bundle_version_is_unsupported_never_read_as_history1(tmp_path,catalog,version):
    e=record(tmp_path,catalog,'2');restamp_bundle(e,version)
    h=read(e)
    assert h['errors']==[dict(code='unsupported_record_version',partial=True)]
    assert 'history_schema_version' not in h and h['configuration'] is None and h['bundle'] is None and h['artifacts']==[]
    assert metadata(e['rid'],h)['results_digest'] is None
    from hyprn_mvp_app.execution_bundle import UnsupportedRetainedVersion
    with pytest.raises(UnsupportedRetainedVersion):
        history_module.projection(e['payload'],dict(request=e['payload']['request'],bundle=dict(manifest=e['payload']['bundle']['manifest'],
            files={k:base64.b64decode(v) for k,v in e['payload']['bundle']['files'].items()}),results=None,assessment=None,artifacts={},errors=[],
            **e['payload']['history']['association']),e['payload']['history']['association'])

@pytest.mark.parametrize('version',['1','2','3'])
def test_listed_bundle_carrying_another_configuration_version_is_corrupt_not_relabelled(tmp_path,catalog,version):
    """Bundles 1-3 carry configurations 1/1/2 only; a configuration 3 record relabelled as one of
    them is refused rather than projected as history 1."""
    e=record(tmp_path,catalog,'2');restamp_bundle(e,version)
    h=read(e)
    assert h['errors']==[dict(code='corrupt_retained_record',partial=True)]
    assert 'history_schema_version' not in h and h['configuration'] is None

def test_legacy_http_same_read_outage_auth_and_repeat_preservation(api,monkeypatch):
    e=api;e['model'].offline=True;client=e['client'];url=f"/api/1/studies/{e['sid']}/runs/{e['rid']}"
    original=History.read;seen=[]
    def once(self,*args,**kw):
        h=original(self,*args,**kw);seen.append(h);return h
    monkeypatch.setattr(History,'read',once)
    from hyprn_mvp_app.result_bindings import ResultBindings
    monkeypatch.setattr(ResultBindings,'retained',lambda *a,**k:pytest.fail('Eligibility filter used'))
    before=logical_rows(e['store'])
    files={str(p):p.read_bytes() for p in e['store'].path.parent.rglob('*') if p.is_file()}
    first=client.get(url);assert first.status_code==200
    data=first.json()['data'];assert len(seen)==1 and data['history']==seen[0]
    assert data['retained_integrity']==dict(schema_version='1',results_digest=digest(seen[0]['results']))
    assert client.get(url).json()['data']==data and len(seen)==2
    assert logical_rows(e['store'])==before
    assert {str(p):p.read_bytes() for p in e['store'].path.parent.rglob('*') if p.is_file()}==files
    from jsonschema import Draft202012Validator,FormatChecker
    schemas=json.loads((Path(__file__).resolve().parents[2]/'contracts/hyprn-mvp.openapi.yaml').read_text())['components']['schemas']
    schema=dict(schemas['PublicRunDetail'],components={'schemas':schemas})
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(data)
    foreign=e['store'].create_study(uid(),uid(),'Foreign')['study_id']
    denied=client.get(url.replace(e['sid'],foreign));assert denied.status_code in (403,404) and 'retained_integrity' not in denied.text
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(e['actor'],))
    denied=client.get(url);assert denied.status_code in (403,404) and 'retained_integrity' not in denied.text
    client.cookies.clear();denied=client.get(url);assert denied.status_code==401 and 'retained_integrity' not in denied.text
    assert len(seen)==2


@pytest.mark.parametrize('declaration,units,valid',[
    ({'kind':'dimensionless'},'',True), ({'kind':'physical','expression':'m'},'m',True),
    ({'kind':'physical','expression':'m'},'km',False), ({'kind':'unspecified'},'',False),
    ({'kind':'dimensionless','expression':''},'',False)])
def test_resolved_output_unit_semantics_with_resealed_model(tmp_path,catalog,declaration,units,valid):
    e=record(tmp_path,catalog);h=read(e);model=h['model_snapshot']
    for d in model['definitions']:
        for port in d['ports']:
            if port['direction']=='output':port['units']=deepcopy(declaration)
    model['ports']=deepcopy([p for d in model['definitions'] for p in d['ports']])
    model['digest']=digest({k:v for k,v in model.items() if k!='digest'});h['bundle']['model_digest']=model['digest']
    for o in h['results']['outputs']:o['units']=units
    assert metadata(e['rid'],h)['results_digest']==(digest(h['results']) if valid else None)

@pytest.mark.parametrize('outcome',['violated','unresolved'])
def test_criterion_outcomes_are_not_source_eligibility(tmp_path,catalog,outcome):
    e=record(tmp_path,catalog);h=read(e);c=h['configuration'];cid=uid()
    c['criteria']=[dict(criterion_id=cid,target=h['results']['outputs'][0]['target'],operator='gt',threshold=10,units='',evidence_version_ids=[])]
    c['digest']=digest({k:v for k,v in c.items() if k!='digest'});h['bundle']['configuration_digest']=c['digest']
    h['results']['criteria']=[dict(criterion_id=cid,outcome=outcome,reason='Recorded qualification')]
    before=deepcopy(h);assert metadata(e['rid'],h)['results_digest']==digest(h['results']);assert h==before

@pytest.mark.parametrize('version',['2','3','4','mixed','6','6legacy','6mixed','6linked','6model2','6model3'])
def test_current_and_historical_http_share_exact_history(tmp_path,catalog,version,monkeypatch):
    from fastapi.testclient import TestClient
    from hyprn_mvp_app.api import create_app
    e=record(tmp_path,catalog,version)
    class Offline:
        def call(self,*a,**kw):pytest.fail('History fetched model service')
    client=TestClient(create_app(e['store'],e['auth'],Offline()),base_url=ORIGIN)
    assert client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN}).status_code==200
    expected=read(e);rows=logical_rows(e['store']);calls=[];original=History.read
    def capture(self,*args,**kw):
        h=original(self,*args,**kw);calls.append(h);return h
    monkeypatch.setattr(History,'read',capture)
    response=client.get(f"/api/1/studies/{e['sid']}/runs/{e['rid']}")
    assert response.status_code==200
    if version.startswith('6'):
        seed_response=client.get(f"/api/1/studies/{e['sid']}/runs/{e['rid']}/modified-run-seed")
        assert seed_response.status_code==200,seed_response.text
        seed=seed_response.json()['data'];validate('ModifiedRunSeed6',seed)
        assert seed['source_configuration']==expected['configuration'] and seed['approach_closure']==expected['approach_closure']
        assert calls==[expected,expected];calls.pop()
    data=response.json()['data'];assert calls==[expected] and data['history']==expected
    assert data['retained_integrity']['results_digest']==digest(expected['results']) and logical_rows(e['store'])==rows
    from jsonschema import Draft202012Validator,FormatChecker
    schemas=json.loads((Path(__file__).resolve().parents[2]/'contracts/hyprn-mvp.openapi.yaml').read_text())['components']['schemas']
    Draft202012Validator(dict(schemas['PublicRunDetail'],components={'schemas':schemas}),format_checker=FormatChecker()).validate(data)

def test_findings_guard_is_closed_app_only_and_fail_closed(tmp_path):
    from types import SimpleNamespace
    import checks
    assert checks.GROUPS['findings-history']==('application/tests/test_findings_history.py',)
    assert checks.GROUP_INTERPRETERS['findings-history']==guard.APPROVED_CONTRACT_PYTHON==sys.executable
    assert 'findings-history' in checks.APPROACH_APP_GROUPS and 'findings-history' not in checks.APPROACH_NATIVE_GROUPS
    assert checks.NATIVE_BACKEND is None
    with pytest.raises(ValueError,match='Required target missing'):checks.targets_for('findings-history',repo=tmp_path)
    with pytest.raises(ValueError,match='Unknown check group'):checks.targets_for('findings-future')
    for passed,failed,skipped,status,forbidden in [(0,0,0,0,[]),(1,0,1,0,[]),(1,1,0,0,[]),(1,0,0,1,[]),(1,0,0,0,['aiida'])]:
        assert not checks.pytest_qualification_passed(status,SimpleNamespace(passed=passed,failed=failed,skipped=skipped),forbidden)


@pytest.mark.parametrize('version',['3','4','6','6legacy','6mixed'])
def test_case_context_authoritative_absence_without_history_fetch(tmp_path,catalog,version,monkeypatch):
    e=record(tmp_path,catalog,version)
    monkeypatch.setattr(History,'read',lambda *a,**k:pytest.fail('Run list fetched full history'))
    rows=History(e['store']).list(e['actor'],e['sid'])
    assert len(rows)==1 and rows[0]['case_context']==dict(state='unlinked')
    replace_configuration(e['store'],e['payload']['frozen']['configuration']['configuration_revision_id'],'{}')
    assert History(e['store']).list(e['actor'],e['sid'])[0]['case_context']==dict(state='unavailable')


@pytest.mark.parametrize('fault',['unit','value','model_tag','manifest_tag','missing_manifest_tag','quantities','claim','closure'])
def test_history6_integrity_never_promotes_tampered_metadata(tmp_path,catalog,fault):
    e=record(tmp_path,catalog,'6');h=read(e)
    assert h.get('history_schema_version')=='6'
    if fault=='unit':h['results']['outputs'][0]['units']='m'
    elif fault=='value':h['results']['outputs'][0]['value']=False
    elif fault=='model_tag':h['model_snapshot']['schema_version']='3'
    elif fault=='manifest_tag':h['bundle']['model_schema_version']='2'
    elif fault=='missing_manifest_tag':h['bundle'].pop('model_schema_version')
    elif fault=='quantities':h['model_snapshot']['definitions'][0]['quantity_definitions']=[]
    elif fault=='claim':h['approach_closure']={}
    else:h['bundle']['approach_closure_digest']='f'*64
    assert metadata(e['rid'],h)['results_digest'] is None


def test_history6_case_versions_and_null_are_distinct_from_missing(tmp_path,catalog,monkeypatch):
    from hyprn_mvp_app.history import case_projection
    e=record(tmp_path,catalog,'6linked');f=e['payload']['frozen'];c=f['configuration']
    monkeypatch.setattr(History,'read',lambda *a,**k:pytest.fail('Full history in list'))
    first=History(e['store']).list(e['actor'],e['sid'])[0]['case_context']
    assert first['case_name']=='Repeated case name' and first['case_id']==c['approach_binding']['case_id']
    changed=deepcopy(f);v=changed['approach_closure']['approach_versions'][0]
    v['approach_version_id']=uid();v['version_number']+=1;signed(v)
    closure=build_closure(v,resolution(models=[f['model_snapshot']]),study_id=e['sid'])
    changed['approach_closure']=closure;cc=changed['configuration']
    cc['approach_binding'].update(approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest=closure['digest'])
    cc['digest']=digest({k:v for k,v in cc.items() if k!='digest'})
    second=case_projection(json.dumps(changed),e['sid'],c['configuration_revision_id'])[1]
    assert second['case_name']==first['case_name'] and second['approach_version_id']!=first['approach_version_id']
    cc['approach_binding']['case_id']=None;cc['digest']=digest({k:v for k,v in cc.items() if k!='digest'})
    empty=case_projection(json.dumps(changed),e['sid'],c['configuration_revision_id'])[1]
    assert empty['state']=='linked' and empty['case_id'] is empty['case_name'] is None
    assert case_projection(None,e['sid'],c['configuration_revision_id'])[1]==dict(state='unavailable')
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(e['actor'],))
    from hyprn_mvp_app.store import DomainError
    with pytest.raises(DomainError):History(e['store']).list(e['actor'],e['sid'])


@pytest.mark.parametrize('state',['pending','partial','failed'])
def test_history6_error_and_partial_inspection_preserves_scientific_status(tmp_path,catalog,state):
    e=record(tmp_path,catalog,'6linked',failed=state=='failed');p=e['payload']
    if state=='pending':del p['history'];save(e)
    if state=='partial':p['history']['results']=None;p['history']['errors']=[dict(code='missing_results',partial=True)];reseal(e)
    h=read(e)
    if state=='pending':assert h['errors']==[dict(code='history_not_recorded',partial=True)]
    else:
        validate('RunHistory6',h);assert h['approach_closure']==p['frozen']['approach_closure']
    assert (metadata(e['rid'],h)['results_digest'] is not None)==(state=='failed')


@pytest.mark.parametrize('fault',['typed_unspecified','bad_units','mixed_in_definition'])
def test_history6_exact_definition_unit_semantics_fail_closed(tmp_path,catalog,fault):
    e=record(tmp_path,catalog,'6');h=read(e);m=h['model_snapshot']
    if fault=='typed_unspecified':m['definitions'][0]['ports'][0]['units']={'kind':'unspecified'}
    elif fault=='mixed_in_definition':m['definitions'][0]['ports'][0]['units']=''
    else:h['results']['outputs'][0]['units']='km'
    m['ports']=[p for d in m['definitions'] for p in d['ports']]
    m['digest']=digest({k:v for k,v in m.items() if k!='digest'});h['bundle']['model_digest']=m['digest']
    assert metadata(e['rid'],h)['results_digest'] is None


@pytest.mark.parametrize('declaration,units,valid',[
    ({'kind':'physical','expression':'m'},'m',True),
    ({'kind':'physical','expression':'m'},'km',False),
    ({'kind':'dimensionless'},'',True),
    ({'kind':'unspecified'},'',False)])
def test_model4_physical_output_declarations_match_native_retained_reader(tmp_path,catalog,declaration,units,valid):
    """Data-only native parser agreement; these values are not calculated."""
    from hyprn_mvp_integration.results import read_stored_result
    e=record(tmp_path,catalog,'6');h=read(e);m=h['model_snapshot']
    for d in m['definitions']:
        for port in d['ports']:
            if port['direction']=='output':port['units']=deepcopy(declaration)
    m['ports']=[p for d in m['definitions'] for p in d['ports']]
    signed(m);h['bundle']['model_digest']=m['digest']
    for output in h['results']['outputs']:output['units']=units
    if valid:assert read_stored_result(h['results'],e['payload']['request'],m)==h['results']
    else:
        with pytest.raises(ValueError):read_stored_result(h['results'],e['payload']['request'],m)
    assert metadata(e['rid'],h)['results_digest']==(digest(h['results']) if valid else None)
    assert not any(n.split('.')[0] in {'aiida','openmdao','openturns'} for n in sys.modules)
