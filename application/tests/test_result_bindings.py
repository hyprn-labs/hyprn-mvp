"""App authority tests with real SQLite/History; native transport is a test double.

Captured producer programs remain inert. These tests do not prove native links
or worker conversion, which belong to subsequent checked tasks.
"""
import base64
import copy
import json
import pytest

from execution_fixtures import fixture, runtime_fixture
from hyprn_mvp_app.store import Store, DomainError, canonical, digest, uid
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.modeling import validate
from runs_criteria_free_support import ModelingDouble, bindings_env


@pytest.fixture
def env(tmp_path,request):
    store = Store(tmp_path / 'bindings.sqlite')
    actor = uid(); study = store.create_study(actor, uid(), 'Source study')
    case = fixture(getattr(request,'param','chain')); config = case['frozen']['configuration']
    config['study_id'] = study['study_id']
    config['context_snapshot'].update(description='', boundary='')
    config['digest'] = digest({k:v for k,v in config.items() if k != 'digest'})
    case['prepared']['configuration_digest'] = config['digest']
    case['prepared']['executable_content_digest'] = executable_digest(case['prepared'])
    case['prepared']['prepared_digest'] = digest({k:v for k,v in case['prepared'].items() if k != 'prepared_digest'})
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (config['configuration_revision_id'], config['configuration_id'], study['study_id'], json.dumps(case['frozen'])))
        db.execute('INSERT INTO model_associations VALUES(?,?,?)', (study['study_id'], config['model_id'], uid()))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],study['study_id'],config['configuration_revision_id']))
    service = Submissions(store, None, None)
    def source(*, current=False):
        run = service.submit(actor, study['study_id'], dict(command_id=uid(), configuration_revision_id=config['configuration_revision_id']))
        prepared = copy.deepcopy(case['prepared'])
        if current:
            prepared.update(schema_version='3', result_protocol_version='2')
            prepared['prepared_digest'] = digest(
                {k: v for k, v in prepared.items() if k != 'prepared_digest'}
            )
        rid = run['run_id']
        bundle = assemble_bundle(rid, prepared, case['files'], case['frozen'], runtime_fixture())
        request = dict(run_id=rid, scope=study['study_id'], command_id=run['command_id'], payload_digest=store.receipt(actor,study['study_id'],'run',run['command_id'])['payload_digest'], bundle_digest=bundle['manifest']['bundle_digest'])
        outputs = json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']
        results = dict(schema_version='1', run_id=rid, bundle_digest=request['bundle_digest'],
            execution=dict(state='finished',exit_code=0,message='Complete'), convergence=dict(state='not_applicable',diagnostics_ref=None),
            optimization=dict(termination='not_applicable',feasibility='not_applicable'), completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),
            outputs=[dict(target=o['target'],value=150+i,units=o['units'],availability='available',reason=None,producer_completed=True,assigned=True) for i,o in enumerate(outputs)],
            criteria=[], applicability=dict(state='unassessed',evidence_refs=[]), artifacts=[])
        if current:
            for key in ('convergence', 'optimization', 'completeness', 'applicability'):
                del results[key]
            results['schema_version'] = '2'
        association = dict(store_uuid=uid(),process_uuid=uid())
        payload = dict(actor=actor, frozen=copy.deepcopy(case['frozen']), request=request,
            bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()}))
        record = dict(request=request,bundle=bundle,results=results,assessment=None,artifacts={},errors=[])
        payload['history'] = projection(payload,record | association,association)
        with store.connection(write=True) as db:
            db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),rid))
            db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),rid))
        return rid, results
    rid, results = source()
    request = dict(schema_version='2', study_id=study['study_id'], model_id=config['model_id'], model_revision_id=config['model_revision_id'],name='Comparison',
        inputs=[dict(kind='run_result', target=config['inputs'][0]['target'], source_run_id=rid, source_output=results['outputs'][0]['target'], expected_results_digest=digest(results),provenance=config['inputs'][0]['provenance']),
            *[dict(kind='literal',**i) for i in config['inputs'][1:]]], criteria=[], numerical=config['numerical'],context_source=dict(kind='current_study',expected_study_revision=study['revision']),notes=[],evidence_version_ids=[],derivation=None)
    return dict(store=store,actor=actor,sid=study['study_id'],case=case,rid=rid,results=results,request=request,source=source)


@pytest.fixture
def env6(tmp_path,request):
    """Configuration 6 on a captured Model4 case with one protocol-3 source run; new
    configurations are authored only as version 6."""
    return bindings_env(tmp_path,getattr(request,'param','chain'))


def bindings(env):
    from hyprn_mvp_app.result_bindings import ResultBindings
    return ResultBindings(env['store'])


def test_source_resolves_exact_retained_labels_without_model_or_native(env):
    service = bindings(env); item = env['request']['inputs'][0]
    result = service.resolve(env['actor'],env['sid'],item)
    assert result['value']==150 and result['results_digest']==digest(env['results'])
    assert result['labels']['model_name'] is None
    assert result['labels']['run_name']==env['case']['frozen']['configuration']['name']
    assert result['native_availability']=='not_rechecked'
    page=service.inventory(env['actor'],env['sid'],limit=1)
    assert page['items']==[result] and page['next_cursor']
    assert len(service.inventory(env['actor'],env['sid'],limit=1,cursor=page['next_cursor'])['items'])==1


@pytest.mark.parametrize('change',['foreign','digest','target','corrupt','revoked','bool','nan','failed','unavailable'])
def test_source_rejects_unusable_or_unauthorized_records(env,change):
    item=copy.deepcopy(env['request']['inputs'][0]);sid=env['sid']
    if change=='foreign':sid=env['store'].create_study(env['actor'],uid(),'Other')['study_id']
    elif change=='digest':item['expected_results_digest']='a'*64
    elif change=='target':item['source_output']['port_id']=uid()
    else:
        with env['store'].connection(write=True) as db:
            if change=='revoked':db.execute('DELETE FROM memberships WHERE study_id=?',(sid,))
            else:
                p=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(env['rid'],)).fetchone()[0])
                if change=='corrupt':p['bundle']['files']['model.json']='e30='
                elif change=='failed':p['history']['results']['execution']['exit_code']=1
                elif change=='unavailable':p['history']['results']['outputs'][0]['availability']='unavailable'
                else:p['history']['results']['outputs'][0]['value']=True if change=='bool' else float('nan')
                if change not in ('corrupt','nan'):
                    p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'})
                    item['expected_results_digest']=digest(p['history']['results'])
                db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(p),env['rid']))
    with pytest.raises(DomainError):bindings(env).resolve(env['actor'],sid,item)


def test_cursor_rejects_cross_actor_study_query_and_malformed(env):
    service=bindings(env);cursor=service.inventory(env['actor'],env['sid'],limit=1)['next_cursor']
    for c,limit in [(cursor,2),('nonsense',1)]:
        with pytest.raises(DomainError):service.inventory(env['actor'],env['sid'],limit=limit,cursor=c)
    other=env['store'].create_study(env['actor'],uid(),'Other')['study_id']
    with pytest.raises(DomainError):service.inventory(env['actor'],other,limit=1,cursor=cursor)


def authoring(env):
    from hyprn_mvp_app.configuration import Configurations
    from hyprn_mvp_app.modeling import Coordinator
    model=ModelingDouble(env['case'])
    return Configurations(env['store'],Coordinator(env['store'],model)),model


def commit_body(env,service):
    preview,_,_=service.preview(env['actor'],env['sid'],env['request'])
    return dict(command_id=uid(),expected_revision=None,configuration_id=None,configuration=copy.deepcopy(env['request']),expected_preview_digest=preview['candidate_digest'])


def test_preview_commit_independently_resolve_and_replay_without_model_or_source(env6):
    env=env6;service,coordinator=authoring(env);before=env['store'].path.read_bytes()
    body=commit_body(env,service)
    assert env['store'].path.read_bytes()==before
    saved=service.commit(env['actor'],env['sid'],body)
    assert len(coordinator.sent)==2
    for sent in coordinator.sent:
        assert sent['schema_version']=='5'
        assert not set(sent)&{'context_source','derivation','criteria'}
        assert all('result_binding' not in i for i in sent['inputs'])
        assert 'result_linked_inputs/1' not in sent['required_capabilities']
    # A configuration carries no criteria; they are evaluated through calculation bindings.
    assert saved['schema_version']=='9' and saved['configuration']['schema_version']=='6'
    assert not set(saved)&{'criteria','approach_closure'} and not set(saved['configuration'])&{'criteria','approach_binding'}
    linked=saved['configuration']['inputs'][0]
    assert linked['value']==linked['result_binding']['original_value']==150
    coordinator.offline=True
    with env['store'].connection(write=True) as db:
        db.execute("UPDATE outbox SET payload='{}' WHERE run_id=?",(env['rid'],))
    assert service.commit(env['actor'],env['sid'],body)==saved
    with pytest.raises(DomainError,match='command_payload_conflict'):
        service.commit(env['actor'],env['sid'],body|dict(expected_preview_digest='b'*64))
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(env['sid'],))
    with pytest.raises(DomainError):service.commit(env['actor'],env['sid'],body)


@pytest.mark.parametrize('change',['preview','source','study','model','evidence','family','revoked'])
def test_commit_races_fail_without_partial_configuration(env6,change):
    env=env6;service,coordinator=authoring(env)
    if change=='evidence':
        note=env['store'].add_evidence(env['actor'],env['sid'],uid(),dict(evidence_schema_version='3',title='Pinned',kind='note',content='Pinned',
            source_refs=[],resource_scope=dict(scope_version='1',kind='study',study_id=env['sid'])))
        env['request']['general_context_evidence_version_ids']=[note['evidence_version_id']]
    body=commit_body(env,service)
    if change=='preview':body['expected_preview_digest']='b'*64
    if change=='family':body.update(configuration_id=env['case']['frozen']['configuration']['configuration_id'],expected_revision='stale')
    def race():
        with env['store'].connection(write=True) as db:
            if change=='source':db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),env['rid']))
            elif change=='study':db.execute('UPDATE studies SET revision=? WHERE study_id=?',(uid(),env['sid']))
            elif change=='model':db.execute('DELETE FROM model_associations WHERE study_id=?',(env['sid'],))
            elif change=='revoked':db.execute('DELETE FROM memberships WHERE study_id=?',(env['sid'],))
            elif change=='evidence':
                # Controlled corruption bypasses immutability only in synthetic fixture.
                db.execute('DROP TRIGGER immutable_evidence_update')
                db.execute("UPDATE evidence SET payload=json_set(payload,'$.content','tampered')")
    coordinator.hook=race
    with pytest.raises(DomainError):service.commit(env['actor'],env['sid'],body)
    with env['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==1


@pytest.mark.parametrize('kind',['number','resolved','duplicate','missing_evidence','stale_context','criteria'])
def test_public_request_cannot_forge_resolved_authority(env6,kind):
    env=env6;service,coordinator=authoring(env);r=env['request']
    if kind=='number':r['inputs'][0]['value']=123
    elif kind=='resolved':r['inputs'][0]['result_binding']={}
    elif kind=='duplicate':r['inputs'].append(copy.deepcopy(r['inputs'][0]))
    elif kind=='missing_evidence':r['inputs'][0]['provenance']['evidence_version_ids']=[uid()]
    elif kind=='criteria':r['criteria']=[]
    else:r['context_source']['expected_study_revision']='stale'
    with pytest.raises(DomainError):service.preview(env['actor'],env['sid'],r)
    assert not coordinator.sent


def test_criterion_failed_source_and_labels_survive_rename_and_model_outage(env):
    criterion=dict(criterion_id=uid(),outcome='violated',reason='Limit exceeded')
    with env['store'].connection(write=True) as db:
        p=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(env['rid'],)).fetchone()[0])
        p['history']['results']['criteria']=[criterion]
        p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'})
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(p),env['rid']))
        db.execute("UPDATE studies SET name='Renamed' WHERE study_id=?",(env['sid'],))
        db.execute('DELETE FROM model_associations WHERE study_id=?',(env['sid'],))
    r=copy.deepcopy(env['request']['inputs'][0]);r['expected_results_digest']=digest(p['history']['results'])
    item=bindings(env).resolve(env['actor'],env['sid'],r)
    assert item['outcomes']['criteria']==[criterion]
    assert set(item['outcomes'])=={'execution','criteria'}
    assert item['labels']['model_name'] is None and item['labels']['run_name']==env['case']['frozen']['configuration']['name']


def test_protocol3_source_reports_execution_only_and_labels_survive_rename_and_model_outage(env6):
    env=env6
    with env['store'].connection(write=True) as db:
        db.execute("UPDATE studies SET name='Renamed' WHERE study_id=?",(env['sid'],))
        db.execute('DELETE FROM model_associations WHERE study_id=?',(env['sid'],))
    item=bindings(env).resolve(env['actor'],env['sid'],env['request']['inputs'][0])
    validate('ResultSource3',item)
    assert set(item['outcomes'])=={'execution'} and item['outcomes']['execution']==env['results']['execution']
    assert 'criteria' not in env['results'] and item['value']==150 and item['results_digest']==digest(env['results'])
    assert item['labels']['model_name'] is None and item['labels']['run_name']==env['case']['frozen']['configuration']['name']
    page=bindings(env).inventory(env['actor'],env['sid'],limit=50)
    validate('ResultSourcePage3',page)
    assert item in page['items'] and all(set(i['outcomes'])=={'execution'} for i in page['items'])


class NativeResolverDouble:
    def __init__(self):self.ids={};self.calls=[];self.launches=0;self.nodes={};self.fail=False
    def resolve_results(self,sources):
        self.calls.append(copy.deepcopy(sources))
        if self.fail:raise ValueError('Missing original Dict')
        return [s|dict(result_uuid=self.ids.setdefault(s['source_run_id'],uid())) for s in sources]
    def require_attestation(self):return True
    def bundle_runtime(self):return runtime_fixture()
    def launch(self,bundle,request):
        self.launches+=1
        raise RuntimeError('Controlled postclaim ambiguity')
    def matches(self,request):return []


def saved2(env,mode='one'):
    request=env['request']
    if mode in ('two','fanout','multi'):
        second=copy.deepcopy(request['inputs'][0]);second['target']=request['inputs'][1]['target']
        if mode=='two':second['source_output']=env['results']['outputs'][1]['target']
        if mode=='multi':
            rid,results=env['source']();second.update(source_run_id=rid,source_output=results['outputs'][0]['target'],expected_results_digest=digest(results))
        request['inputs'][1]=second
    service,_=authoring(env)
    saved=service.commit(env['actor'],env['sid'],commit_body(env,service))
    return saved


def prepared2(env,frozen):
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    prepared=copy.deepcopy(env['case']['prepared']);c=project_scientific_configuration(frozen['configuration'])
    prepared.update(configuration_revision_id=c['configuration_revision_id'],configuration_digest=c['digest'])
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    return prepared,env['case']['files']


@pytest.mark.parametrize('mode',['one','two','fanout','multi'])
def test_bundle11_freezes_full_private_and_dependency_domains(env6,mode):
    from hyprn_mvp_app.execution import validate_retained_bundle
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    env=env6;frozen=saved2(env,mode);native=NativeResolverDouble()
    deps=bindings(env).dependencies(env['actor'],env['sid'],frozen['configuration'],native)
    assert len(deps['sources'])==(2 if mode=='multi' else 1)
    assert len(deps['mappings'])==(1 if mode=='one' else 2)
    prepared,files=prepared2(env,frozen)
    bundle=assemble_bundle(uid(),prepared,files,frozen,runtime_fixture(),deps)
    m=bundle['manifest'];c=frozen['configuration'];private=project_scientific_configuration(c)
    assert m['schema_version']=='11' and m['configuration_digest']==c['digest']!=m['modeling_configuration_digest']
    assert private['schema_version']=='5' and 'criteria' not in private and 'criteria' not in c
    assert m['modeling_configuration_digest']==prepared['configuration_digest']==private['digest']
    assert bundle['files']['configuration.json']==canonical(c)
    assert bundle['files']['modeling-configuration.json']==canonical(private)
    assert bundle['files']['result-dependencies.json']==canonical(deps)
    request=dict(run_id=m['run_id'],bundle_digest=m['bundle_digest'])
    validate_retained_bundle(bundle,request,frozen)
    for path in ('configuration.json','modeling-configuration.json','result-dependencies.json'):
        bad=copy.deepcopy(bundle);bad['files'][path]=b'{}'
        with pytest.raises(ValueError):validate_retained_bundle(bad,request,frozen)


@pytest.mark.parametrize('fault',['missing','changed','revoked','source_race','uncertain'])
def test_preclaim_failure_is_zero_launch_and_uncertain_never_relaunched(env6,fault):
    env=env6
    frozen=saved2(env);native=NativeResolverDouble();prepared,files=prepared2(env,frozen)
    service=Submissions(env['store'],lambda *args:(prepared,files),native)
    run=service.submit(env['actor'],env['sid'],dict(command_id=uid(),configuration_revision_id=frozen['configuration']['configuration_revision_id']))
    if fault=='missing':native.fail=True
    def before(point):
        if point!='before_claim':return
        if fault=='changed':native.ids[env['rid']]=uid()
        if fault in ('revoked','source_race'):
            with env['store'].connection(write=True) as db:
                if fault=='revoked':db.execute('DELETE FROM memberships WHERE study_id=?',(env['sid'],))
                else:db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),env['rid']))
    service.fault=before
    service.dispatch(run['run_id']);service.dispatch(run['run_id'])
    with env['store'].connection() as db:
        row=db.execute('SELECT state,payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()
    if fault=='uncertain':assert row['state']=='uncertain' and native.launches==1
    else:assert json.loads(row['payload'])['preparation_state']=='preparation_failed' and native.launches==0
    # Result-bound inputs are always resolved through the exact retained source before a claim.
    if fault!='revoked':assert native.calls and native.calls[0][0]['source_run_id']==env['rid']


@pytest.mark.parametrize('version',['1','2','3','4'])
def test_older_requests_are_refused_and_original_source_bytes_are_unchanged(env6,version):
    # New configurations are written only as version 6; older request versions are refused
    # before any modeling contact and leave the retained source run untouched.
    env=env6;service,coordinator=authoring(env)
    with env['store'].connection() as db:
        original=db.execute('SELECT payload FROM outbox WHERE run_id=?',(env['rid'],)).fetchone()[0]
    candidate=dict(copy.deepcopy(env['request']),schema_version=version,criteria=[])
    body=dict(command_id=uid(),expected_revision=None,configuration_id=None,configuration=candidate,expected_preview_digest='a'*64)
    for call in (lambda:service.preview(env['actor'],env['sid'],candidate),lambda:service.commit(env['actor'],env['sid'],body)):
        with pytest.raises(DomainError) as error:call()
        assert (error.value.code,error.value.status)==('unsupported_record_version',422)
    assert not coordinator.calls
    with env['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==1
    saved2(env)
    with env['store'].connection() as db:
        assert db.execute('SELECT payload FROM outbox WHERE run_id=?',(env['rid'],)).fetchone()[0]==original


@pytest.mark.parametrize('fault',['association','value','digest','output','extra','uuid','count','alias'])
def test_native_resolver_response_cannot_supply_new_authority(env6,fault):
    env=env6
    frozen=saved2(env,'multi' if fault=='alias' else 'one');native=NativeResolverDouble();resolve=native.resolve_results
    def forged(sources):
        result=resolve(sources)
        if fault=='association':result[0]['association']['process_uuid']=uid()
        elif fault=='value':result[0]['outputs'][0]['value']=999
        elif fault=='digest':result[0]['results_digest']='f'*64
        elif fault=='output':result[0]['outputs'][0]['target']['port_id']=uid()
        elif fault=='extra':result[0]['native_pk']=12
        elif fault=='uuid':result[0]['result_uuid']='../../escape'
        elif fault=='count':result=[]
        else:
            result[1]['result_uuid']=result[0]['result_uuid']
            result[1]['association']['store_uuid']=result[0]['association']['store_uuid']
        return result
    native.resolve_results=forged
    with pytest.raises((DomainError,ValueError)):
        bindings(env).dependencies(env['actor'],env['sid'],frozen['configuration'],native)
    assert native.launches==0


def test_inventory_highwater_and_100_projection_page_budget(env):
    resolver=bindings(env);first=resolver.inventory(env['actor'],env['sid'],limit=1)
    newer,_=env['source']()
    second=resolver.inventory(env['actor'],env['sid'],limit=1,cursor=first['next_cursor'])
    assert second['next_cursor'] is None and second['items'][0]['source_run_id']!=newer
    service=Submissions(env['store'],None,None)
    for _ in range(100):
        service.submit(env['actor'],env['sid'],dict(command_id=uid(),configuration_revision_id=env['case']['frozen']['configuration']['configuration_revision_id']))
    last,_=env['source']()
    page=resolver.inventory(env['actor'],env['sid'],limit=50)
    assert len(page['items'])==4 and page['next_cursor']
    next_page=resolver.inventory(env['actor'],env['sid'],limit=50,cursor=page['next_cursor'])
    assert len(next_page['items'])==2 and next_page['items'][0]['source_run_id']==last
    assert next_page['next_cursor'] is None


@pytest.mark.parametrize('limit',[True,0,51,'25'])
def test_inventory_limit_is_bounded_integer(env,limit):
    with pytest.raises(DomainError):bindings(env).inventory(env['actor'],env['sid'],limit=limit)


def test_result_requests_bound_distinct_sources_before_fetch(env6):
    env=env6
    service,coordinator=authoring(env)
    env['request']['inputs']=[env['request']['inputs'][0]|dict(target=dict(instance_id=uid(),port_id=uid()),source_run_id=uid()) for _ in range(65)]
    with pytest.raises(DomainError,match='limit_exceeded'):service.preview(env['actor'],env['sid'],env['request'])
    assert not coordinator.sent


def test_concurrent_save_and_dispatch_replays_allocate_once(env6):
    env=env6
    from concurrent.futures import ThreadPoolExecutor
    service,_=authoring(env);body=commit_body(env,service)
    with ThreadPoolExecutor(max_workers=3) as pool:
        saved=list(pool.map(lambda _:service.commit(env['actor'],env['sid'],body),range(3)))
    assert saved[0]==saved[1]==saved[2]
    native=NativeResolverDouble();prepared,files=prepared2(env,saved[0]);runs=Submissions(env['store'],lambda *args:(prepared,files),native)
    body=dict(command_id=uid(),configuration_revision_id=saved[0]['configuration']['configuration_revision_id'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        accepted=list(pool.map(lambda _:runs.submit(env['actor'],env['sid'],body),range(3)))
    assert len({r['run_id'] for r in accepted})==1
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:runs.dispatch(accepted[0]['run_id']),range(3)))
    assert native.launches==1


def test_static_preparation_sends_only_exact_private_snapshot(env6):
    from hyprn_mvp_app.execution import StaticPreparation
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    from runs_criteria_free_support import capabilities
    env=env6;frozen=saved2(env);prepared,files=prepared2(env,frozen)
    class ModelBoundary:
        def call(self,actor,sid,method,path,body=None,**kwargs):
            if path=='/capabilities':
                # The criteria-free modeling service advertises bundle 10/11 and artifact 3/4.
                caps=capabilities(env['case']);caps['execution_versions']=dict(artifact_versions=['3','4'],bundle_versions=['10','11'],
                    program_protocols=['hyprn_mvp.openmdao.program/1'],historical_artifact_versions=['1','2'],historical_bundle_versions=['1','2','3','4','5','6','8'])
                caps['capabilities'].append(dict(caps['capabilities'][0],id='flat_explicit_scalar',version='1'))
                validate('Capabilities3',caps);return 200,dict(data=caps)
            if method=='POST':
                self.body=body;self.request_schema=kwargs['request_schema']
                assert body['configuration_snapshot']==project_scientific_configuration(frozen['configuration'])
                assert body['configuration_digest']==body['configuration_snapshot']['digest']==prepared['configuration_digest']
                return 200,dict(data=prepared)
            item=next(f for f in prepared['files'] if f['file_id']==path.rsplit('/',1)[-1])
            return 200,dict(data=dict(bytes=base64.b64encode(files[item['path']]).decode(),sha256=item['sha256'],media_type=item['media_type']))
    model=ModelBoundary()
    assert StaticPreparation(model)(env['actor'],env['sid'],uid(),frozen)==(prepared,files)
    assert model.body['configuration_digest']!=frozen['configuration']['digest']
    assert model.request_schema=='Prepare2' and model.body['configuration_snapshot']['schema_version']=='5'
    assert 'criteria' not in model.body['configuration_snapshot'] and prepared['schema_version']=='4'


def test_literal_request6_has_empty_hashed_dependency_file(env6):
    env=env6;r=env['request'];r['inputs']=[dict(kind='literal',**{k:i[k] for k in ('target','value','units','provenance')}) for i in env['case']['frozen']['configuration']['inputs']]
    frozen=saved2(env);deps=bindings(env).dependencies(env['actor'],env['sid'],frozen['configuration'],None)
    assert deps==dict(schema_version='1',sources=[],mappings=[])
    prepared,files=prepared2(env,frozen);bundle=assemble_bundle(uid(),prepared,files,frozen,runtime_fixture(),deps)
    assert bundle['files']['result-dependencies.json']==canonical(deps)


def test_prepared_resume_rechecks_sources_without_regeneration(env6):
    env=env6
    frozen=saved2(env);native=NativeResolverDouble();prepared,files=prepared2(env,frozen)
    service=Submissions(env['store'],lambda *args:(prepared,files),native)
    run=service.submit(env['actor'],env['sid'],dict(command_id=uid(),configuration_revision_id=frozen['configuration']['configuration_revision_id']))
    service.dispatch(run['run_id'],prepare_only=True)
    assert service.read(env['actor'],env['sid'],run['run_id'])['state']=='prepared'
    def offline(*args):raise AssertionError('Prepared work fetched modeling')
    service.prepare=offline;native.fail=True
    service.dispatch(run['run_id'])
    assert service.read(env['actor'],env['sid'],run['run_id'])['state']=='preparation_failed' and native.launches==0


@pytest.mark.parametrize('env6',['units'],indirect=True)
def test_original_scalar_and_units_remain_unchanged_under_trusted_linear_conversion(env6):
    # Change only the current destination fixture port; retained source bytes are
    # independently frozen in SQLite. This test exercises app interpretation,
    # not the catalog producer or actual OpenMDAO conversion.
    env=env6;model=env['case']['frozen']['model_snapshot']
    for port in [*model['ports'],*(p for definition in model['definitions'] for p in definition['ports'])]:
        if port['direction']=='input':port['units']=dict(kind='physical',expression='m')
    model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
    service,coordinator=authoring(env);coordinator.factor=1000;coordinator.destination_units='m'
    saved=service.commit(env['actor'],env['sid'],commit_body(env,service))
    item=saved['configuration']['inputs'][0]
    assert item['value']==150 and item['units']=='km'
    assert item['result_binding']['conversion']['destination_value']==150000
    assert item['result_binding']['conversion']['factor']==1000
    assert coordinator.sent[-1]['inputs'][0]['value']==150 and coordinator.sent[-1]['inputs'][0]['units']=='km'


# History owns retained-run reading. Public interface: run_row, retained, recheck.
# Source eligibility (finished, exit 0) stays with ResultBindings, never with History.

def retained_history(env):
    from hyprn_mvp_app.history import History
    return History(env['store'])


def stored_run(env, rid=None):
    with env['store'].connection() as db:
        return retained_history(env).run_row(db, env['actor'], env['sid'], rid or env['rid'])


def receipt_where(env):
    with env['store'].connection() as db:
        command = db.execute('SELECT command_id FROM run_associations WHERE run_id=?', (env['rid'],)).fetchone()[0]
    return "WHERE scope=? AND category='run' AND command_id=?", (env['sid'], command)


def test_history_retained_is_exact_from_stored_bytes_and_never_reads_current_records(env, monkeypatch):
    from hyprn_mvp_app.history import RetainedRun
    store = env['store']
    monkeypatch.setattr(store, 'evidence_version', lambda *a, **k: pytest.fail('Retained read consulted current evidence'))
    run = retained_history(env).retained(env['actor'], env['sid'], env['rid'])
    assert isinstance(run, RetainedRun)
    history, payload, token = run
    with store.connection() as db:
        stored = json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?', (env['rid'],)).fetchone()[0])
    row, receipt = stored_run(env)
    assert payload == stored and history['configuration'] == stored['frozen']['configuration']
    assert canonical(history) == canonical(retained_history(env).read(env['actor'], env['sid'], env['rid']))
    assert history['results'] == env['results']
    assert token == dict(run_id=env['rid'], row_digest=digest(row), receipt_digest=digest(receipt))


def test_history_retained_keeps_failed_outcomes_readable_and_leaves_eligibility_to_consumers(env):
    with env['store'].connection(write=True) as db:
        p = json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?', (env['rid'],)).fetchone()[0])
        p['history']['results']['execution'].update(state='failed', exit_code=1)
        p['history']['digest'] = digest({k: v for k, v in p['history'].items() if k != 'digest'})
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(p), env['rid']))
    history, _, _ = retained_history(env).retained(env['actor'], env['sid'], env['rid'])
    assert history['results']['execution']['state'] == 'failed'
    with pytest.raises(DomainError) as error:
        bindings(env).retained(env['actor'], env['sid'], env['rid'])
    assert (error.value.code, error.value.status) == ('source_result_unavailable', 409)


def test_history_retained_foreign_study_or_run_is_not_found(env):
    store = env['store']; service = retained_history(env)
    foreign = store.create_study(uid(), uid(), 'Foreign')['study_id']
    member = store.create_study(env['actor'], uid(), 'Other')['study_id']
    for sid, rid in ((foreign, env['rid']), (member, env['rid']), (env['sid'], uid())):
        with pytest.raises(DomainError) as error:
            service.retained(env['actor'], sid, rid)
        assert (error.value.code, error.value.status) == ('resource_not_found', 404)
        with store.connection() as db, pytest.raises(DomainError) as error:
            service.run_row(db, env['actor'], sid, rid)
        assert (error.value.code, error.value.status) == ('resource_not_found', 404)


def test_history_retained_refuses_unrecorded_and_tampered_receipts(env, monkeypatch):
    from hyprn_mvp_app.history import History, RetainedRecordError
    store = env['store']; service = retained_history(env); where, params = receipt_where(env)
    with store.connection(write=True) as db:
        db.execute("UPDATE outbox SET state='dispatching' WHERE run_id=?", (env['rid'],))
    with pytest.raises(DomainError) as error:
        service.retained(env['actor'], env['sid'], env['rid'])
    assert (error.value.code, error.value.status) == ('record_not_ready', 409)
    with store.connection(write=True) as db:
        db.execute("UPDATE outbox SET state='recorded' WHERE run_id=?", (env['rid'],))
        original = db.execute('SELECT payload_digest,result FROM receipts ' + where, params).fetchone()
        # A stored receipt that no longer authenticates the immutable request is an
        # integrity failure, never a record.
        db.execute('UPDATE receipts SET payload_digest=? ' + where, ('0' * 64, *params))
    with pytest.raises(RetainedRecordError):
        service.retained(env['actor'], env['sid'], env['rid'])
    with store.connection(write=True) as db:
        db.execute('UPDATE receipts SET payload_digest=? ' + where, (original[0], *params))
    assert service.retained(env['actor'], env['sid'], env['rid']).history['results'] == env['results']
    # A receipt changed while the retained context is being verified is a conflict.
    read = History._read_saved
    def tampered(self, *args, **kwargs):
        value = read(self, *args, **kwargs)
        with store.connection(write=True) as db:
            db.execute('UPDATE receipts SET result=? ' + where, (json.dumps(dict(tampered=True)), *params))
        return value
    monkeypatch.setattr(History, '_read_saved', tampered)
    with pytest.raises(DomainError) as error:
        service.retained(env['actor'], env['sid'], env['rid'])
    assert (error.value.code, error.value.status) == ('reference_conflict', 409)


def test_history_recheck_rejects_stale_token_after_concurrent_change(env):
    store = env['store']; service = retained_history(env)
    _, _, token = service.retained(env['actor'], env['sid'], env['rid'])
    with store.connection(write=True) as db:
        service.recheck(db, env['actor'], env['sid'], [token])
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?', (uid(), env['rid']))
    with store.connection(write=True) as db, pytest.raises(DomainError) as error:
        service.recheck(db, env['actor'], env['sid'], [token])
    assert (error.value.code, error.value.status) == ('reference_conflict', 409)
    with store.connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (env['sid'],))
    with store.connection(write=True) as db, pytest.raises(DomainError) as error:
        service.recheck(db, env['actor'], env['sid'], [token])
    assert (error.value.code, error.value.status) == ('resource_not_found', 404)
