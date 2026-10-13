"""Exact Bundle5 history from a guarded native run; no live workspace access."""
import base64
from copy import deepcopy
import json
import pytest
from aiida import orm
from checks import PROJECTION_SCOPE as SCOPE,NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from hyprn_mvp_app.store import Store,canonical,digest,uid,DomainError
from hyprn_mvp_app.history import History,projection
from hyprn_mvp_app.modified_runs import ModifiedRuns
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_integration.calculation import NativeExecution
from test_approach_bundle import case5
from test_assumptions_history import retain,payload
from test_unit_execution_admission import catalog,case8,assemble,reseal as reseal_bundle

@pytest.fixture(scope='session')
def recorded():
    guard.prepare_worker_fixture(SCOPE,BACKEND)
    native=NativeExecution(backend=BACKEND,root=SCOPE.root)
    assert native.require_attestation()['passed']
    store=Store(SCOPE.root/'artifacts/approach-history.sqlite');actor=uid()
    study=store.create_study(actor,uid(),'Original study');sid=study['study_id']
    env=dict(store=store,actor=actor,sid=sid,native=native,study=study)
    case,_=case5(sid=sid);case['frozen']['study_revision']=study['revision']
    env.update(retain(env,case));env['original']=canonical(payload(env))
    return env

def test_actual_history3_retains_exact_approach_and_successful_scalar_source(recorded):
    e=recorded;h=History(e['store']).read(e['actor'],e['sid'],e['rid'])
    validate('RunHistory3',h)
    assert h['approach_closure']==e['case']['frozen']['approach_closure']
    assert sorted(o['value'] for o in h['results']['outputs'])==[7,49]
    assert h['bundle']['approach_closure_digest']==h['approach_closure']['digest']
    inventory=ResultBindings(e['store']).inventory(e['actor'],e['sid'])
    assert {x['source_run_id'] for x in inventory['items']}=={e['rid']}
    assert sorted(x['value'] for x in inventory['items'])==[7,49]

def test_restart_and_library_outage_never_replace_retained_context(recorded,monkeypatch):
    e=recorded;store=Store(e['store'].path)
    def unavailable(*a,**kw):pytest.fail('Retained reader consulted current scientific library')
    monkeypatch.setattr(store,'evidence_version',unavailable)
    monkeypatch.setattr('hyprn_mvp_app.approach.Approaches.read',unavailable)
    monkeypatch.setattr('hyprn_mvp_app.modeling.Coordinator.read',unavailable)
    h=History(store).read(e['actor'],e['sid'],e['rid']);validate('RunHistory3',h)
    seed=ModifiedRuns(store).seed(e['actor'],e['sid'],e['rid']);validate('ModifiedRunSeed3',seed)
    assert seed['source_configuration']==h['configuration'] and seed['approach_closure']==h['approach_closure']
    pin=h['configuration']['approach_binding']
    assert seed['configuration']['approach_selection']=={k:pin[k] for k in ('approach_version_id','case_id')}
    before=canonical(h);study=store.study(e['actor'],e['sid'])
    store.update_study(e['actor'],e['sid'],uid(),study['revision'],dict(description='Later study description'))
    assert canonical(History(Store(store.path)).read(e['actor'],e['sid'],e['rid']))==before
    assert canonical(payload(e))==e['original']

@pytest.mark.parametrize('fixture_name',['recorded','polished'])
@pytest.mark.parametrize('change',['missing','bytes','frozen','role','manifest','downgrade'])
def test_corrupt_approach_is_honestly_unavailable(request,fixture_name,change):
    e=request.getfixturevalue(fixture_name);p=payload(e);original=deepcopy(p)
    if change=='missing':p['bundle']['files'].pop('approach/closure.json')
    elif change=='bytes':p['bundle']['files']['approach/closure.json']=base64.b64encode(b'{}').decode()
    elif change=='frozen':p['frozen']['approach_closure']['root_approach_digest']='f'*64
    elif change=='role':next(d for d in p['bundle']['manifest']['files'] if d['path']=='approach/closure.json')['role']='evidence'
    elif change=='manifest':p['bundle']['manifest']['approach_digest']='e'*64
    else:
        m=p['bundle']['manifest'];m['schema_version']='2'
        for key in ('approach_digest','approach_closure_digest','modeling_configuration_digest','result_dependencies'):m.pop(key)
        m['bundle_digest']=digest({k:v for k,v in m.items() if k!='bundle_digest'})
        for value in (p['request'],p['history']['request'],p['history']['results']):value['bundle_digest']=m['bundle_digest']
        p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'})
    def write(v):
        with e['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(v),e['rid']))
    try:
        write(p);h=History(e['store']).read(e['actor'],e['sid'],e['rid']);validate('RunHistory',h)
        assert h['errors']==[dict(code='corrupt_retained_record',partial=True)] and h['configuration'] is None
        assert h.get('approach_closure') is None
        for service in (ModifiedRuns(e['store']),ResultBindings(e['store'])):
            with pytest.raises(DomainError):service.retained(e['actor'],e['sid'],e['rid'])
    finally:write(original)

def test_history_and_seed_deny_foreign_reader(recorded):
    e=recorded
    for service,method in ((History(e['store']),'read'),(ModifiedRuns(e['store']),'seed'),(ResultBindings(e['store']),'inventory')):
        args=(uid(),e['sid'])+(() if method=='inventory' else (e['rid'],))
        with pytest.raises(DomainError):getattr(service,method)(*args)

def test_projection_validates_approach_before_retaining_native_record(recorded):
    e=recorded;p=payload(e);p['frozen']['approach_closure']['digest']='f'*64
    with pytest.raises(ValueError):projection(p,e['record'],{k:e['record'][k] for k in ('store_uuid','process_uuid')})


def polish_case(case):
    """Descriptor-only revision of captured native bytes; generation is unchanged."""
    from test_approach_closure import signed,resolution
    from test_unit_execution_admission import repin
    from hyprn_mvp_app.approach_closure import build_closure
    f=case['frozen'];m=f['model_snapshot'];c=f['configuration']
    old_revision=m['model_revision_id'];new_revision=uid()
    m['model_revision_id']=new_revision;c['model_revision_id']=new_revision
    c.update(configuration_id=uid(),configuration_revision_id=uid())
    prepared=case['prepared'];prepared.update(model_revision_id=new_revision,configuration_revision_id=c['configuration_revision_id'])
    package=prepared['model_package_manifest'];package['model_revision_id']=new_revision
    for row in package['files']:
        if row['path']=='revisions/'+old_revision+'.json':row['path']='revisions/'+new_revision+'.json'
    m['schema_version']='4';m['required_capabilities'].append('quantity_definitions/1')
    for d in m['definitions']:
        d['quantity_definitions']=[dict(port_id=p['port_id'],statement='Exact '+p['name']+' quantity') for p in d['ports']]
    case['prepared']['required_capabilities']=list(m['required_capabilities'])
    c['required_capabilities'].append('quantity_definitions/1')
    f['schema_version']='7';repin(case)
    if f['approach_closure']:
        old=f['approach_closure'];v=deepcopy(next(v for v in old['approach_versions'] if v['approach_version_id']==old['root_approach_version_id']))
        v['schema_version']='2';v['content'].update(schema_version='2',
            original_question=dict(text='Original scientific question',attribution=dict(kind='human',label='Supplied origin')),
            elaboration=dict(text='Recorded interpretation',attribution=dict(kind='agent',label='Supplied explanation')),
            limit_items=[dict(limit_id=uid(),statement='Only this retained example is covered',evidence_links=[dict(evidence_version_id=c['evidence_snapshots'][0]['evidence_version_id'],relation='challenges')])])
        for binding in v['content']['model_bindings']:
            if binding['model_revision_id']==old_revision:binding['model_revision_id']=new_revision
        signed(v)
        models=[m if row['model_revision_id']==old_revision else row for row in old['models']]
        closure=build_closure(v,resolution(models=models,evidence=old['evidence'],configurations=old['configurations'],run_contexts=old['run_contexts'],approach_versions=[row for row in old['approach_versions'] if row['approach_version_id']!=v['approach_version_id']]),study_id=c['study_id'])
        f['approach_closure']=closure;c['approach_binding'].update(approach_digest=v['digest'],closure_digest=closure['digest'])
        repin(case)
    return case


@pytest.fixture(scope='session')
def polished(recorded):
    e=recorded;case,_=case5(sid=e['sid']);polish_case(case)
    return {**e,**retain(e,case)}


def test_native_bundle8_history6_seed6_exact_outage_and_scalar_source(polished,monkeypatch):
    from hyprn_mvp_app.history import retained_read_integrity
    from hyprn_mvp_integration.results import retained_bundle,validate_result
    e=polished;bundle=retained_bundle(e['node'].inputs.frozen_bundle.base.repository,e['request'])
    assert bundle==e['bundle'] and bundle['manifest']['model_schema_version']=='4'
    raw=e['node'].outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')
    parsed=validate_result(raw,e['request'],e['case']['frozen']['model_snapshot'])
    assert sorted(o['value'] for o in parsed['outputs'])==[7,49]
    def denied(*a,**k):pytest.fail('Retained read consulted current library')
    monkeypatch.setattr(e['store'],'evidence_version',denied)
    monkeypatch.setattr('hyprn_mvp_app.approach.Approaches.read',denied)
    monkeypatch.setattr('hyprn_mvp_app.modeling.Coordinator.read',denied)
    h=History(e['store']).read(e['actor'],e['sid'],e['rid']);validate('RunHistory6',h)
    assert h['model_snapshot']==e['case']['frozen']['model_snapshot']
    assert h['approach_closure']==e['case']['frozen']['approach_closure']
    assert retained_read_integrity(e['rid'],h)['results_digest']==digest(h['results'])
    seed=ModifiedRuns(e['store']).seed(e['actor'],e['sid'],e['rid']);validate('ModifiedRunSeed6',seed)
    assert seed['source_configuration']==h['configuration'] and seed['approach_closure']==h['approach_closure']
    assert sorted(o['value'] for o in ResultBindings(e['store']).inventory(e['actor'],e['sid'])['items'] if o['source_run_id']==e['rid'])==[7,49]


@pytest.mark.parametrize('fault',['missing','foreign_case','foreign_study','closure','config_digest'])
def test_list_case_context_fails_closed_and_does_not_read_history(polished,monkeypatch,fault):
    e=polished;c=e['case']['frozen']['configuration'];f=deepcopy(e['case']['frozen'])
    monkeypatch.setattr(History,'read',lambda *a,**k:pytest.fail('Full history read in list'))
    actual=next(r for r in History(e['store']).list(e['actor'],e['sid']) if r['run_id']==e['rid'])['case_context']
    assert actual['state']=='linked' and actual['approach_version_id']==c['approach_binding']['approach_version_id']
    if fault=='missing':f={}
    elif fault=='foreign_case':f['configuration']['approach_binding']['case_id']=uid()
    elif fault=='foreign_study':f['configuration']['study_id']=uid()
    elif fault=='closure':f['approach_closure']['approach_versions'][0]['content']['question']='Changed'
    else:f['configuration']['digest']='f'*64
    with e['store'].connection() as db:
        original=db.execute('SELECT payload FROM configurations WHERE configuration_revision_id=?',(c['configuration_revision_id'],)).fetchone()[0]
    replace_configuration(e['store'],c['configuration_revision_id'],json.dumps(f))
    try:
        assert next(r for r in History(e['store']).list(e['actor'],e['sid']) if r['run_id']==e['rid'])['case_context']==dict(state='unavailable')
    finally:
        replace_configuration(e['store'],c['configuration_revision_id'],original)


def replace_configuration(store,revision_id,raw):
    """Inject corruption only into an isolated fixture; restore its exact trigger."""
    with store.connection(write=True) as db:
        triggers=db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='configurations'").fetchall()
        for row in triggers:db.execute('DROP TRIGGER "'+row['name']+'"')
        db.execute('UPDATE configurations SET payload=? WHERE configuration_revision_id=?',(raw,revision_id))
        for row in triggers:db.execute(row['sql'])


class RetainedBytes:
    def __init__(self,bundle):self.files={**bundle['files'],'manifest.json':canonical(bundle['manifest'])}
    def open(self,path,mode='rb'):
        import io
        assert mode=='rb';return io.BytesIO(self.files[path])


@pytest.mark.parametrize('version,approach,legacy,mixed',[
    ('4',None,False,False),('4','1',True,False),('4','2',False,True),
    ('3','2',False,False),('2','2',True,False)])
def test_real_retained_parser_matrix_before_history_and_seed(catalog,version,approach,legacy,mixed):
    """Real data-only parsing of synthetic sealed inputs, not extra calculations."""
    from hyprn_mvp_integration.results import retained_bundle,validate_result,read_stored_result
    from hyprn_mvp_app.modified_runs import complete_outcome
    case=case8(catalog,version,approach,legacy,mixed);bundle,request=assemble(case)
    assert retained_bundle(RetainedBytes(bundle),request)==bundle
    bindings=json.loads(bundle['files'][bundle['manifest']['entrypoint']['bindings_path']])
    result=dict(schema_version='1',run_id=request['run_id'],bundle_digest=request['bundle_digest'],
        execution=dict(state='finished',exit_code=0,message='Synthetic parser fixture'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(bindings['outputs']),available=len(bindings['outputs']),failed=0,unavailable=0),
        outputs=[dict(target=o['target'],value=0,units=o['units'],availability='available',reason=None,producer_completed=True,assigned=True) for o in bindings['outputs']],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    model=case['frozen']['model_snapshot']
    envelope=canonical(dict(reason='exited',exit_code=0,output='HYPRN_MVP_RESULT_V1 '+canonical(result).decode()))
    assert validate_result(envelope,request,model)==result
    assert read_stored_result(result,request,model)==result
    complete_outcome(result,model,case['frozen']['configuration'])
    for fault in ('unit','false_zero','active_unspecified'):
        value=deepcopy(result);changed=deepcopy(model)
        if fault=='unit':value['outputs'][0]['units']='km'
        elif fault=='false_zero':value['outputs'][0]['value']=False
        else:
            d=next(d for d in changed['definitions'] if d['definition_version_id']==changed['instances'][0]['definition_version_id'])
            for port in d['ports']:port['units']={'kind':'unspecified'}
            changed['ports']=[p for d in changed['definitions'] for p in d['ports']]
        with pytest.raises(ValueError):read_stored_result(value,request,changed)


@pytest.mark.parametrize('fault',['missing_model_tag','wrong_model_tag','downgrade','quantity','question','limit','foreign_study'])
def test_bundle8_native_retained_parser_rejects_resealed_tampering(polished,fault):
    from hyprn_mvp_integration.results import retained_bundle
    e=polished;b=deepcopy(e['bundle']);r=deepcopy(e['request'])
    if fault=='missing_model_tag':b['manifest'].pop('model_schema_version')
    elif fault=='wrong_model_tag':b['manifest']['model_schema_version']='3'
    elif fault=='downgrade':b['manifest']['schema_version']='6';b['manifest'].pop('model_schema_version')
    elif fault=='foreign_study':r['scope']=uid()
    else:
        path='model.json' if fault=='quantity' else 'approach/closure.json';v=json.loads(b['files'][path])
        if fault=='quantity':v['definitions'][0].pop('quantity_definitions')
        else:
            content=next(vv for vv in v['approach_versions'] if vv['approach_version_id']==v['root_approach_version_id'])['content']
            if fault=='question':content.pop('original_question')
            else:content['limit_items'][0]['evidence_links'][0]['evidence_version_id']=uid()
        b['files'][path]=canonical(v)
    reseal_bundle(b,r)
    with pytest.raises(ValueError):retained_bundle(RetainedBytes(b),r)
