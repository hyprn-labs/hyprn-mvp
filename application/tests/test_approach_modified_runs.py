"""Modified-run approach semantics; exact source context and explicit deltas."""
from copy import deepcopy
import base64
import json
import pytest
from hyprn_mvp_app.modified_runs import changes,ModifiedRuns
from hyprn_mvp_app.store import uid,Store,canonical,digest,DomainError
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.history import History,projection
from hyprn_mvp_app.execution import Submissions,assemble_bundle
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.approach import Approaches
from hyprn_mvp_app.result_bindings import ResultBindings
if __name__!='__main__':
    from test_approach_bundle import case5
from test_approach_closure import sample,D
from execution_fixtures import runtime_fixture
ORIGIN='http://127.0.0.1:19999'
def path(e,suffix):return '/api/1/studies/'+e['sid']+'/'+suffix

@pytest.mark.parametrize('choice',['preserve','change','remove','case'])
def test_approach_selection_changes_are_explicit_scientific_delta(choice):
    source=case5()[0]['frozen']['configuration'];candidate=deepcopy(source)
    if choice=='change':candidate['approach_binding']['approach_version_id']=uid()
    elif choice=='remove':candidate['approach_binding']=None
    elif choice=='case':candidate['approach_binding']['case_id']=None
    records,summaries=changes(source,candidate)
    if choice=='preserve':assert records==summaries==[]
    else:
        assert records and all(r['path'].startswith('/approach_binding') for r in records)
        assert [r['path'] for r in records]==[r['path'] for r in summaries]

def check_seed3_preserves_all_editable_context_and_assumptions(e):
    seed=ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid'])
    validate('ModifiedRunSeed3',seed);c=e['case']['frozen']['configuration']
    for key in ('assumptions','general_context_evidence_version_ids','criteria','notes'):
        expected=c['context_snapshot']['notes'] if key=='notes' else c[key]
        assert seed['configuration'][key]==expected
    assert seed['configuration']['context_override']==dict(schema_version='1',**{k:c['context_snapshot'][k] for k in ('description','boundary')})

def retain_api(e,frozen,*,failed=False):
    """Synthetic retained result, real API/store/bundle validation; not a native run."""
    case=deepcopy(e['case']);case['frozen']=deepcopy(frozen);c=frozen['configuration']
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    from hyprn_mvp_app.execution import executable_digest
    prepared=case['prepared'];prepared.update(configuration_revision_id=c['configuration_revision_id'],configuration_digest=project_scientific_configuration(c)['digest'])
    prepared['executable_content_digest']=executable_digest(prepared);prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    run=Submissions(e['store'],None,None).submit(e['actor'],e['sid'],dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    bundle=assemble_bundle(run['run_id'],case['prepared'],case['files'],frozen,runtime_fixture(),dict(schema_version='1',sources=[],mappings=[]))
    request=dict(run_id=run['run_id'],scope=e['sid'],command_id=run['command_id'],payload_digest=e['store'].receipt(e['actor'],e['sid'],'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    outputs=json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']
    result=dict(schema_version='1',run_id=run['run_id'],bundle_digest=request['bundle_digest'],execution=dict(state='failed' if failed else 'finished',exit_code=1 if failed else 0,message='Synthetic terminal fixture'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(outputs),available=0 if failed else len(outputs),failed=len(outputs) if failed else 0,unavailable=len(outputs) if failed else 0),
        outputs=[dict(target=o['target'],value=None if failed else 7+i,units=o['units'],availability='unavailable' if failed else 'available',reason='Synthetic failure' if failed else None,producer_completed=not failed,assigned=not failed) for i,o in enumerate(outputs)],
        criteria=[dict(criterion_id=k['criterion_id'],outcome='unresolved',reason='Synthetic fixture') for k in c['criteria']],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    association=dict(store_uuid=uid(),process_uuid=uid())
    p=dict(actor=e['actor'],frozen=frozen,request=request,bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(v).decode() for p,v in bundle['files'].items()}))
    p['history']=projection(p,dict(request=request,bundle=bundle,results=result,assessment=None,artifacts={},errors=[])|association,association)
    with e['store'].connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),run['run_id']))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(p),run['run_id']))
    return run['run_id']

def new_app(tmp_path,base_case):
    from fastapi.testclient import TestClient
    from hyprn_mvp_app.api import create_app
    from test_reuse_api import PrivateModelDouble
    store=Store(tmp_path/'approach-modified.sqlite');auth=Auth(store,ORIGIN)
    actor=auth.provision('owner','correct horse battery staple');study=store.create_study(actor,uid(),'Source study');sid=study['study_id']
    case=deepcopy(base_case);c=case['frozen']['configuration'];closure=case['frozen']['approach_closure'];v=closure['approach_versions'][0]
    # Each child store adopts this independently generated fixture's study ID.
    with store.connection(write=True) as db:
        db.execute('PRAGMA defer_foreign_keys=ON')
        db.execute('UPDATE studies SET study_id=? WHERE study_id=?',(c['study_id'],sid))
        db.execute('UPDATE memberships SET study_id=? WHERE study_id=?',(c['study_id'],sid))
    sid=c['study_id']
    draft=sample(D['ApproachDraft2' if v['schema_version']=='2' else 'ApproachDraft1']);draft.update(approach_id=v['approach_id'],study_id=sid,base_version_id=v['approach_version_id'],content=deepcopy(v['content']))
    with store.connection(write=True) as db:
        db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,c['model_id'],uid()))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],sid,json.dumps(case['frozen'])))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(c['configuration_id'],sid,c['configuration_revision_id']))
        for e in c['evidence_snapshots']:db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(e['evidence_version_id'],e['evidence_id'],sid,json.dumps(e)))
        db.execute('INSERT INTO approach_drafts VALUES(?,?,?,?)',(v['approach_id'],sid,draft['revision'],json.dumps(draft)))
        db.execute('INSERT INTO approach_versions VALUES(?,?,?,?,?)',(v['approach_version_id'],v['approach_id'],sid,v['version_number'],json.dumps(dict(version=v,closure=closure))))
    class Model(PrivateModelDouble):
        def call(self,actor,sid,method,route,body=None,**kw):
            if route!='/capabilities':return super().call(actor,sid,method,route,body,**kw)
            if self.offline:raise AssertionError('Retained read contacted modeling')
            caps=sample(D['Capabilities']);cap=sample(D['Capabilities']['properties']['capabilities']['items'])
            cap.update(id='resolved_configuration',version='3',supported=True)
            caps.update(contract_versions=['1.2'],schema_versions=['1','2'],capabilities=[cap],generator_identity=deepcopy(self.case['prepared']['generator_identity']))
            if self.case['frozen']['model_snapshot']['schema_version']=='4':
                caps['schema_versions'].append('4');caps['capabilities'].append(dict(cap,id='quantity_definitions',version='1'))
            return 200,dict(data=caps)
    model=Model(case);client=TestClient(create_app(store,auth,model),base_url=ORIGIN)
    login=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':login.json()['data']['csrf_token']})
    e=dict(store=store,actor=actor,sid=sid,case=case,model=model,client=client)
    e['rid']=retain_api(e,case['frozen']);return e

def seed(e):
    r=e['client'].get(path(e,'runs/'+e['rid']+'/modified-run-seed'));assert r.status_code==200,r.text
    value=r.json()['data'];validate('ModifiedRunSeed3',value)
    value['configuration']['context_source']['choice_confirmed']=True
    return value

def check_real_api_preview_commit_replay_and_next_seed(app,choice):
    e=app;original=History(e['store']).read(e['actor'],e['sid'],e['rid']);request=seed(e)['configuration']
    if choice=='remove':request['approach_selection']=None
    elif choice=='change':
        base=path(e,'approach');state=e['client'].get(base).json()['data']['draft'];content=state['content'];content['question']='New interpretation'
        q=dict(schema_version='1',expected_revision=state['revision'],content=content)
        p=e['client'].post(base+'/preview',json=q);assert p.status_code==200,p.text
        d=e['client'].post(base+'/draft',json=dict(q,command_id=uid(),expected_preview_digest=p.json()['data']['preview_digest']));assert d.status_code in (200,201),d.text
        revision=d.json()['data']['revision'];q['expected_revision']=revision
        p=e['client'].post(base+'/preview',json=q)
        v=e['client'].post(base+'/versions',json=dict(schema_version='1',command_id=uid(),expected_revision=revision,expected_preview_digest=p.json()['data']['preview_digest']));assert v.status_code in (200,201),v.text
        request['approach_selection']['approach_version_id']=v.json()['data']['saved']['version']['approach_version_id']
    request['context_override']['description']='Edited inherited rationale'
    p=e['client'].post(path(e,'configurations/preview'),json=request);assert p.status_code==200,p.text
    p=p.json()['data'];validate('ConfigurationPreview4',p)
    pin_changes=[d for d in p['changes'] if d['path'].startswith('/approach_binding')]
    assert bool(pin_changes)==(choice!='preserve')
    command=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=request,expected_preview_digest=p['candidate_digest'])
    r=e['client'].post(path(e,'configurations'),json=command);assert r.status_code==201,r.text
    frozen=r.json()['data'];validate('FrozenConfiguration4',frozen)
    e['model'].offline=True
    assert e['client'].post(path(e,'configurations'),json=command).json()['data']==frozen
    e['rid']=retain_api(e,frozen);next_seed=seed(e)
    assert next_seed['source_configuration']==frozen['configuration']
    assert next_seed['approach_closure']==frozen['approach_closure']
    assert next_seed['configuration']['approach_selection']==request['approach_selection']
    assert next_seed['source_context']['description']=='Edited inherited rationale'
    assert History(e['store']).read(e['actor'],e['sid'],original['results']['run_id'])==original

def check_incompatible_or_implicit_pin_changes_fail_without_new_configuration(app,change):
    e=app;r=seed(e)['configuration']
    if change=='model':r['model_revision_id']=uid()
    elif change=='version':r['approach_selection']['approach_version_id']=uid()
    elif change=='case':r['approach_selection']['case_id']=uid()
    else:
        del r['approach_selection']
        if change=='downgrade':r['schema_version']='3'
    with e['store'].connection() as db:before=db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]
    response=e['client'].post(path(e,'configurations/preview'),json=r);assert response.status_code in (400,404,409,422),response.text
    with e['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==before

def check_failed_basis_remains_inspectable_but_not_a_scalar_source(app):
    e=app;rid=retain_api(e,e['case']['frozen'],failed=True)
    history=History(e['store']).read(e['actor'],e['sid'],rid);validate('RunHistory3',history)
    assert history['results']['execution']['state']=='failed'
    assert ModifiedRuns(e['store']).seed(e['actor'],e['sid'],rid)['schema_version']=='3'
    with pytest.raises(DomainError,match='source_result_unavailable'):ResultBindings(e['store']).retained(e['actor'],e['sid'],rid)
    base=path(e,'approach');draft=e['client'].get(base).json()['data']['draft'];content=draft['content']
    content['basis_refs']=[dict(kind='run',run_id=rid,reason='The failed attempt limits applicability',relation='challenges')]
    q=dict(schema_version='1',expected_revision=draft['revision'],content=content)
    p=e['client'].post(base+'/preview',json=q);assert p.status_code==200,p.text
    assert not p.json()['data']['issues']
    d=e['client'].post(base+'/draft',json=dict(q,command_id=uid(),expected_preview_digest=p.json()['data']['preview_digest']));assert d.status_code in (200,201),d.text
    q['expected_revision']=d.json()['data']['revision'];p=e['client'].post(base+'/preview',json=q)
    saved=e['client'].post(base+'/versions',json=dict(schema_version='1',command_id=uid(),expected_revision=q['expected_revision'],expected_preview_digest=p.json()['data']['preview_digest']));assert saved.status_code in (200,201),saved.text
    retained=saved.json()['data']['saved']['closure']['run_contexts']
    assert len(retained)==1 and retained[0]['run_id']==rid and retained[0]['results']['execution']['state']=='failed'

def check_complete_result_guards(e,change):
    with e['store'].connection() as db:p=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(e['rid'],)).fetchone()[0])
    result=p['history']['results']
    if change=='missing_output':result['outputs'].pop()
    elif change=='bool_value':result['outputs'][0]['value']=True
    else:result['outputs'][0].update(availability='unavailable',value=None,reason='Unassigned',assigned=False)
    p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'})
    with e['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(p),e['rid']))
    with pytest.raises(DomainError,match='source_result_unavailable'):ResultBindings(e['store']).retained(e['actor'],e['sid'],e['rid'])

def test_public_modified_run_operations_in_reviewed_application_interpreter():
    from pathlib import Path
    import subprocess
    import scoped_fixture as guard
    from checks import PROJECTION_SCOPE as scope
    case,_=case5();target=guard.scoped_path(scope,'artifacts/modified-case.json')
    wire=deepcopy(case);wire['files']={p:base64.b64encode(raw).decode() for p,raw in wire['files'].items()}
    target.write_text(json.dumps(wire))
    from test_approach_history import polish_case
    newer=polish_case(deepcopy(case));newer['files']={p:base64.b64encode(raw).decode() for p,raw in newer['files'].items()}
    guard.scoped_path(scope,'artifacts/modified-polish-case.json').write_text(json.dumps(newer))
    repo=Path(__file__).resolve().parents[2]
    script="import sys;from pathlib import Path;r=Path(sys.argv[1]);sys.path[:0]=[str(r/p) for p in ('deployment','deployment/tests','application/src','application/tests','integration/src','integration/tests','contracts/tests')];import runpy;runpy.run_path(str(r/'application/tests/test_approach_modified_runs.py'),run_name='__main__')"
    command=[guard.APPROVED_CONTRACT_PYTHON,'-B','-c',script,str(repo)]
    result=subprocess.run(command,env=guard.clean_environment(scope),capture_output=True,text=True)
    guard.scoped_path(scope,'evidence/modified-api.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    assert result.returncode==0,result.stderr


def check_polish_seed_copy_replay_and_current_authorization(e):
    before=History(e['store']).read(e['actor'],e['sid'],e['rid'])
    url=path(e,'runs/'+e['rid']+'/modified-run-seed')
    response=e['client'].get(url);assert response.status_code==200,response.text
    value=response.json()['data'];validate('ModifiedRunSeed6',value)
    assert value['source_configuration']==before['configuration']
    assert value['approach_closure']==before['approach_closure']
    request=value['configuration'];request['context_source']['choice_confirmed']=True
    request['context_override']['description']='Explicitly edited source context'
    preview=e['client'].post(path(e,'configurations/preview'),json=request)
    assert preview.status_code==200,preview.text
    validate('ConfigurationPreview6',preview.json()['data'])
    command=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=request,expected_preview_digest=preview.json()['data']['candidate_digest'])
    response=e['client'].post(path(e,'configurations'),json=command);assert response.status_code==201,response.text
    frozen=response.json()['data'];validate('FrozenConfiguration7',frozen)
    e['model'].offline=True
    assert e['client'].post(path(e,'configurations'),json=command).json()['data']==frozen
    assert History(e['store']).read(e['actor'],e['sid'],e['rid'])==before
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(e['actor'],))
    assert e['client'].get(url).status_code in (403,404)
    assert e['client'].post(path(e,'configurations'),json=command).status_code in (403,404)

if __name__=='__main__':
    import sys
    import scoped_fixture as guard
    scope=guard.scope_from_environment();assert sys.executable==guard.APPROVED_CONTRACT_PYTHON
    wire=json.loads(guard.scoped_path(scope,'artifacts/modified-case.json').read_text())
    wire['files']={p:base64.b64decode(raw) for p,raw in wire['files'].items()}
    checks=[]
    for choice in ('preserve','change','remove'):
        tmp=guard.scoped_path(scope,'artifacts/api-'+choice);tmp.mkdir()
        check_real_api_preview_commit_replay_and_next_seed(new_app(tmp,wire),choice);checks.append(choice)
    for choice in ('model','version','case','downgrade','omit'):
        tmp=guard.scoped_path(scope,'artifacts/api-'+choice);tmp.mkdir()
        check_incompatible_or_implicit_pin_changes_fail_without_new_configuration(new_app(tmp,wire),choice);checks.append(choice)
    tmp=guard.scoped_path(scope,'artifacts/api-failed');tmp.mkdir()
    check_failed_basis_remains_inspectable_but_not_a_scalar_source(new_app(tmp,wire));checks.append('failed_basis')
    tmp=guard.scoped_path(scope,'artifacts/api-seed');tmp.mkdir()
    check_seed3_preserves_all_editable_context_and_assumptions(new_app(tmp,wire));checks.append('seed_context')
    for choice in ('missing_output','bool_value','unavailable'):
        tmp=guard.scoped_path(scope,'artifacts/api-'+choice);tmp.mkdir()
        check_complete_result_guards(new_app(tmp,wire),choice);checks.append(choice)
    newer=json.loads(guard.scoped_path(scope,'artifacts/modified-polish-case.json').read_text())
    newer['files']={p:base64.b64decode(raw) for p,raw in newer['files'].items()}
    tmp=guard.scoped_path(scope,'artifacts/api-polish');tmp.mkdir()
    check_polish_seed_copy_replay_and_current_authorization(new_app(tmp,newer));checks.append('polish_seed_copy_replay_authorization')
    assert not any(n.split('.')[0] in ('aiida','openmdao','openturns') for n in sys.modules)
    print(json.dumps(dict(checks=checks,native_imports=[])))
