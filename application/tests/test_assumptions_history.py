"""Bundle4 history from actual parsed CalcJobs in the guarded AE native scope.

The program is the captured native producer artifact, executed unchanged by the
attested restricted worker. No result, parser or native process is synthesized.
"""

from legacy_study_support import seed_legacy_context
import base64
from copy import deepcopy
import hashlib
import json

import pytest
from aiida import orm
from aiida.common.links import LinkType
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from hyprn_mvp_app.store import Store, canonical, digest, uid, DomainError
from hyprn_mvp_app.execution import Submissions, assemble_bundle
from hyprn_mvp_app.history import History, projection
from hyprn_mvp_app.modified_runs import ModifiedRuns, changes
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_integration.calculation import NativeExecution
from hyprn_mvp_integration.results import retained_bundle
from test_assumptions_execution import case4, repin
from criteria_free import CRITERIA_FREE_CAPABILITY


def payload(env,rid=None):
    with env['store'].connection() as db:
        return json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid or env['rid'],)).fetchone()[0])


def retain(env,case):
    store=env['store'];actor=env['actor'];sid=env['sid'];native=env['native']
    config=case['frozen']['configuration']
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(case['frozen'])))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],sid,config['configuration_revision_id']))
    run=Submissions(store,None,None).submit(actor,sid,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
    dependencies=ResultBindings(store).dependencies(actor,sid,config,native)
    bundle=assemble_bundle(run['run_id'],case['prepared'],case['files'],case['frozen'],native.bundle_runtime(),dependencies)
    request=dict(run_id=run['run_id'],scope=sid,command_id=run['command_id'],payload_digest=store.receipt(actor,sid,'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    response=native.launch(bundle,request)
    association={k:response[k] for k in ('store_uuid','process_uuid')}
    node=orm.load_node(response['process_uuid'])
    assert node.is_finished_ok and node.exit_status==0
    assert node.outputs.results.creator.uuid==node.uuid
    assert not node.base.caching.is_created_from_cache
    assert node.base.attributes.get('metadata_inputs')['metadata']['disable_cache'] is True
    record=native.read_record(request,association)
    assert record['results']['execution']['state']=='finished' and not record['errors'],record
    assert record['bundle']==retained_bundle(node.inputs.frozen_bundle.base.repository,request)
    p=dict(actor=actor,frozen=deepcopy(case['frozen']),request=request,bundle=dict(manifest=bundle['manifest'],files={k:base64.b64encode(v).decode() for k,v in bundle['files'].items()}))
    p['history']=projection(p,record,association)
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),run['run_id']))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(p),run['run_id']))
    return dict(rid=run['run_id'],node=node,record=record,bundle=bundle,request=request,dependencies=dependencies,case=case)


@pytest.fixture(scope='module')
def actual():
    guard.prepare_worker_fixture(SCOPE,BACKEND)
    native=NativeExecution(backend=BACKEND,root=SCOPE.root)
    assert native.require_attestation()['passed']
    from hyprn_mvp_app.auth import Auth
    store=Store(SCOPE.root/'artifacts/ae-history.sqlite');auth=Auth(store,'http://127.0.0.1:19999')
    actor=auth.provision('owner','correct horse battery staple')
    study=store.create_study(actor,uid(),'Original study');sid=study['study_id']
    case,_=case4();config=case['frozen']['configuration']
    config['study_id']=sid;config['context_source']['expected_study_revision']=study['revision']
    case['frozen']['study_revision']=study['revision']
    evidence=store.add_evidence(actor,sid,uid(),dict(evidence_schema_version='3',title='Original calibration',
        kind='note',content='Recorded observation',source_refs=['Inert report reference'],
        resource_scope=dict(scope_version='1',kind='study',study_id=sid)))
    eid=evidence['evidence_version_id'];config['evidence_snapshots']=[evidence]
    config['general_context_evidence_version_ids']=[eid]
    config['inputs'][0]['provenance']['evidence_version_ids']=[eid]
    for assumption in config['assumptions']+case['frozen']['model_snapshot']['assumptions']:
        for link in assumption['evidence_links']:link['evidence_version_id']=eid
    repin(case)
    env=dict(store=store,actor=actor,sid=sid,native=native,study=study,auth=auth)
    env.update(retain(env,case))
    env['original']=canonical(payload(env))
    env['source_result']=canonical(env['node'].outputs.results.get_dict())
    return env


def test_actual_parsed_bundle4_and_second_original_native_result_input(actual,monkeypatch):
    env=actual;store=env['store'];sid=env['sid'];actor=env['actor']
    outputs=env['record']['results']['outputs']
    assert sorted(o['value'] for o in outputs)==[7,49]
    selected=next(o for o in outputs if o['value']==7)
    resolved=ResultBindings(store).resolve(actor,sid,dict(source_run_id=env['rid'],source_output=selected['target'],expected_results_digest=digest(env['record']['results'])))
    case=deepcopy(env['case']);config=case['frozen']['configuration']
    config.update(configuration_id=uid(),configuration_revision_id=uid(),name='Second actual Bundle4 run')
    item=config['inputs'][0];item['value']=resolved['value'];item['units']=resolved['units']
    item['result_binding']={k:resolved[k] for k in ('source_run_id','source_output','results_digest','source_configuration_digest','labels')}
    item['result_binding'].update(original_value=resolved['value'],original_units=resolved['units'],
        conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='c'*64,source_units=resolved['units'],destination_units=resolved['units'],factor=1,destination_value=resolved['value']))
    config['required_capabilities'].append('result_linked_inputs/1');repin(case)
    seen=[];original=orm.CalcJobNode.store
    def inspect(node,*args,**kwargs):
        links=[(l.link_label,l.node.uuid) for l in node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all() if l.link_label.startswith('upstream_results__')]
        assert links==[('upstream_results__r'+env['node'].outputs.results.uuid.replace('-',''),env['node'].outputs.results.uuid)]
        seen.append(links)
        return original(node,*args,**kwargs)
    monkeypatch.setattr(orm.CalcJobNode,'store',inspect)
    second=retain(env,case)
    assert len(seen)==1 and second['node'].uuid!=env['node'].uuid
    # The captured native chain computes u=2*x+z, y=u**2.
    original_inputs=env['case']['frozen']['configuration']['inputs']
    assert [i['value'] for i in original_inputs]==[2,3]
    assert sorted(o['value'] for o in second['record']['results']['outputs'])==[17,289]
    assert canonical(payload(env))==env['original']
    assert canonical(env['node'].outputs.results.get_dict())==env['source_result']
    assert env['native'].read_record(env['request'],{k:env['record'][k] for k in ('store_uuid','process_uuid')})['bundle']==env['record']['bundle']
    (SCOPE.root/'evidence/actual-bundle4-reuse.json').write_text(json.dumps(dict(
        source_run=env['rid'],source_process=env['node'].uuid,source_result=env['node'].outputs.results.uuid,
        downstream_run=second['rid'],downstream_process=second['node'].uuid,dependencies=second['dependencies'],
        source_results=env['record']['results'],downstream_results=second['record']['results'],
        prestore_links=seen,original_payload_sha256=hashlib.sha256(env['original']).hexdigest(),
        parser='hyprn_mvp.scalar',actual_restricted_worker=True,cache_disabled=True),indent=2))


def test_retained_history_seed_restart_outage_and_changed_study(actual,monkeypatch):
    env=actual;store=Store(env['store'].path)
    monkeypatch.setattr(store,'evidence_version',lambda *a:pytest.fail('Retained read consulted current library'))
    before=canonical(payload(env));history=History(store).read(env['actor'],env['sid'],env['rid'])
    validate('RunHistory2',history)
    seed=ModifiedRuns(store).seed(env['actor'],env['sid'],env['rid']);validate('ModifiedRunSeed2',seed)
    config=env['case']['frozen']['configuration']
    assert history['configuration']==config and history['evidence']==config['evidence_snapshots']
    assert seed['model_snapshot']==env['case']['frozen']['model_snapshot']
    for key in ('assumptions','general_context_evidence_version_ids','criteria'):
        assert seed['configuration'][key]==config[key]
    assert seed['configuration']['inputs'][0]['provenance']==config['inputs'][0]['provenance']
    study=store.study(env['actor'],env['sid'])
    seed_legacy_context(
        store,
        env['actor'],
        env['sid'],
        uid(),
        study['revision'],
        dict(description='New study context'),
    )
    later=ModifiedRuns(store).seed(env['actor'],env['sid'],env['rid'])
    assert later['context_changed'] and later['requires_context_choice']
    assert later['source_context']==config['context_snapshot'] and later['current_context']['description']=='New study context'
    assert canonical(payload(env))==before


@pytest.mark.parametrize('field',['request','creator','digest','value','association'])
def test_forged_actual_source_allocates_zero_process(actual,field):
    env=actual;record=env['record'];output=record['results']['outputs'][0]
    approved=dict(source_run_id=env['rid'],request=deepcopy(env['request']),
        association={k:record[k] for k in ('store_uuid','process_uuid')},results_digest=digest(record['results']),
        outputs=[{k:output[k] for k in ('target','value','units')}])
    if field=='request':approved['request']['payload_digest']='a'*64
    elif field=='creator':approved['association']['process_uuid']=uid()
    elif field=='association':approved['association']['store_uuid']=uid()
    elif field=='digest':approved['results_digest']='b'*64
    else:approved['outputs'][0]['value']+=1
    before=orm.QueryBuilder(backend=BACKEND).append(orm.ProcessNode).count()
    with pytest.raises(ValueError):env['native'].resolve_results([approved])
    # Exercise launch too: even a consistently rehashed forged descriptor must
    # fail native creator/request/value verification before downstream storage.
    case=deepcopy(env['case']);config=case['frozen']['configuration']
    config.update(configuration_id=uid(),configuration_revision_id=uid())
    item=config['inputs'][0];item['value']=approved['outputs'][0]['value'];item['units']=output['units']
    binding=dict(source_run_id=env['rid'],source_output=output['target'],results_digest=approved['results_digest'],
        source_configuration_digest=env['case']['frozen']['configuration']['digest'],original_value=item['value'],original_units=item['units'],
        labels=ResultBindings(env['store'])._output(env['rid'],History(env['store']).read(env['actor'],env['sid'],env['rid']),output['target'])['labels'],
        conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='c'*64,source_units=item['units'],destination_units=item['units'],factor=1,destination_value=item['value']))
    item['result_binding']=binding;config['required_capabilities'].append('result_linked_inputs/1');repin(case)
    source={k:deepcopy(v) for k,v in approved.items() if k!='outputs'}
    source.update(result_uuid=env['node'].outputs.results.uuid,label='r'+env['node'].outputs.results.uuid.replace('-',''))
    deps=dict(schema_version='1',sources=[source],mappings=[dict(target=item['target'],source_label=source['label'],
        **{k:binding[k] for k in ('source_output','results_digest','original_value','original_units','conversion')})])
    bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],env['native'].bundle_runtime(),deps)
    request=dict(run_id=bundle['manifest']['run_id'],scope=env['sid'],command_id=uid(),payload_digest='d'*64,bundle_digest=bundle['manifest']['bundle_digest'])
    with pytest.raises(ValueError):env['native'].launch(bundle,request)
    assert orm.QueryBuilder(backend=BACKEND).append(orm.ProcessNode).count()==before


@pytest.mark.parametrize('field',['missing','relationship','title','label','model','projection','pair'])
def test_missing_or_tampered_retained_closure_has_no_current_fallback(actual,field):
    env=actual;p=payload(env);original=deepcopy(p)
    if field=='missing':p['bundle']['files'].pop('evidence/index.json')
    elif field=='pair':p['bundle']['manifest']['schema_version']='3'
    else:
        path='model.json' if field=='model' else 'modeling-configuration.json' if field=='projection' else 'configuration.json'
        raw=json.loads(base64.b64decode(p['bundle']['files'][path]))
        if field=='relationship':raw['assumptions'][0]['evidence_links'][0]['relation']='context'
        elif field=='title':raw['evidence_snapshots'][0]['title']='New title'
        elif field=='label':raw['evidence_snapshots'][0]['recorded_context']['label']='Current label'
        elif field=='model':raw['assumptions'][0]['statement']='Current model'
        else:raw['name']='Changed projection'
        p['bundle']['files'][path]=base64.b64encode(canonical(raw)).decode()
    def write(value):
        with env['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(value),env['rid']))
    try:
        write(p)
        assert History(env['store']).read(env['actor'],env['sid'],env['rid'])['errors']==[dict(code='corrupt_retained_record',partial=True)]
        with pytest.raises(DomainError):ModifiedRuns(env['store']).seed(env['actor'],env['sid'],env['rid'])
        with pytest.raises(DomainError):ResultBindings(env['store']).retained(env['actor'],env['sid'],env['rid'])
    finally:write(original)
    assert canonical(payload(env))==env['original']


def test_stable_assumption_and_relation_change_summaries(actual):
    source=actual['case']['frozen']['configuration'];candidate=deepcopy(source)
    candidate['assumptions'].reverse();candidate['assumptions'][0]['evidence_links'].reverse()
    assert changes(source,candidate)==([],[])
    aid=candidate['assumptions'][0]['assumption_id'];old=candidate['general_context_evidence_version_ids'][0];new=uid()
    candidate['assumptions'][0]['statement']='Explicit replacement'
    candidate['assumptions'][0]['evidence_links']=[dict(evidence_version_id=new,relation='context')]
    candidate['general_context_evidence_version_ids']=[new]
    records,summary=changes(source,candidate);paths={r['path'] for r in records}
    assert '/assumptions/'+aid+'/statement' in paths
    assert '/assumptions/'+aid+'/evidence_links/'+old+':supports' in paths
    assert '/assumptions/'+aid+'/evidence_links/'+new+':context' in paths
    assert '/general_context_evidence_version_ids/'+new in paths
    assert len(records)==len(summary)


@pytest.mark.parametrize('field',['missing','incomplete','duplicate'])
def test_new_source_eligibility_requires_complete_retained_outcome(actual,field):
    env=actual;p=payload(env);original=deepcopy(p)
    if field=='missing':p['history']['results']=None
    elif field=='incomplete':p['history']['results']['outputs'].pop()
    else:p['history']['results']['outputs'].append(deepcopy(p['history']['results']['outputs'][0]))
    p['history']['digest']=digest({k:v for k,v in p['history'].items() if k!='digest'})
    def write(value):
        with env['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(value),env['rid']))
    try:
        write(p)
        with pytest.raises(DomainError) as error:ResultBindings(env['store']).retained(env['actor'],env['sid'],env['rid'])
        assert error.value.code=='source_result_unavailable'
        with pytest.raises(DomainError):ModifiedRuns(env['store']).seed(env['actor'],env['sid'],env['rid'])
    finally:write(original)


def test_revoked_or_foreign_access_reveals_no_retained_bytes(actual):
    env=actual
    for service in (History(env['store']).read,ModifiedRuns(env['store']).seed,ResultBindings(env['store']).retained):
        with pytest.raises(DomainError) as error:service(uid(),env['sid'],env['rid'])
        assert error.value.status in (403,404)
    assert canonical(payload(env))==env['original']


def configuration_count(store):
    with store.connection() as db:
        return db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]


def save_command(request, preview_digest):
    return dict(
        command_id=uid(),
        configuration_id=None,
        expected_revision=None,
        configuration=request,
        expected_preview_digest=preview_digest,
    )


def test_retained_bundle4_seed_reads_exactly_and_its_earlier_request_is_refused(actual):
    """New configurations are version 6 only. The seed of the actual retained bundle4 run still
    reads the exact retained model and evidence, but its configuration 3 request is refused at
    preview and save: nothing is written and the private modeling service is never contacted."""
    from hyprn_mvp_app.configuration import Configurations
    from hyprn_mvp_app.modeling import Coordinator
    from runs_criteria_free_support import ModelingDouble

    env = actual
    store, actor, sid, case = env['store'], env['actor'], env['sid'], env['case']
    old = case['frozen']['configuration']['evidence_snapshots'][0]
    offline = ModelingDouble(case)
    offline.offline = True
    configs = Configurations(store, Coordinator(store, offline))
    seed = ModifiedRuns(store).seed(actor, sid, env['rid'])
    assert seed['model_snapshot'] == case['frozen']['model_snapshot']
    assert History(store).read(actor, sid, env['rid'])['evidence'] == [old]
    request = deepcopy(seed['configuration'])
    request['context_source']['choice_confirmed'] = True
    request['assumptions'][0]['statement'] = 'Explicit modified statement'
    before = configuration_count(store)
    with pytest.raises(DomainError, match='unsupported_record_version'):
        configs.preview(actor, sid, request)
    with pytest.raises(DomainError, match='unsupported_record_version'):
        configs.commit(actor, sid, save_command(request, '0' * 64))
    assert configuration_count(store) == before and not offline.calls
    assert ModifiedRuns(store).seed(actor, sid, env['rid']) == seed
    assert canonical(payload(env)) == env['original']


def test_new_evidence_head_and_assumption_edit_require_explicit_modified_replacement(actual):
    """A configuration 6 modified from a criteria-free run records an edited assumption and a
    new evidence head as explicit derivation changes, keeps the exact source model without a
    model fetch, and leaves both retained source runs unchanged.

    The criteria-free source run is a recorded protocol-3 record, not a native process, and the
    private compatibility transport is an explicit typed double: nothing here executes.
    """
    from hyprn_mvp_app.configuration import Configurations
    from hyprn_mvp_app.modeling import Coordinator
    from criteria_free import bind_case, request6
    from runs_criteria_free_support import ModelingDouble, retain as retain6

    env = actual
    store, actor, sid = env['store'], env['actor'], env['sid']
    old = env['case']['frozen']['configuration']['evidence_snapshots'][0]
    oid = old['evidence_version_id']
    study = store.study(actor, sid)
    case = bind_case('chain', sid, study_revision=study['revision'])
    model = ModelingDouble(case)
    configs = Configurations(store, Coordinator(store, model))
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO model_associations VALUES(?,?,?)',
            (sid, case['frozen']['model_snapshot']['model_id'], uid()),
        )
    aid = uid()
    assumption = dict(
        assumption_id=aid,
        statement='Calibrated against the original observation',
        evidence_links=[dict(evidence_version_id=oid, relation='supports')],
    )
    source = request6(
        case,
        sid,
        study['revision'],
        name='Criteria-free calibrated source',
        assumptions=[assumption],
        general_context_evidence_version_ids=[oid],
    )
    source['inputs'][0]['provenance']['evidence_version_ids'] = [oid]
    preview = configs.preview(actor, sid, source)[0]
    frozen = configs.commit(actor, sid, save_command(source, preview['candidate_digest']))
    rid, _ = retain6(store, actor, sid, case, frozen)
    original = canonical(payload(env, rid))
    fields = ('evidence_schema_version', 'title', 'kind', 'content', 'source_refs')
    note = {k: deepcopy(old[k]) for k in (*fields, 'resource_scope')}
    note.update(title='New calibration title', content='New observation')
    new = store.revise_evidence(actor, sid, old['evidence_id'], uid(), oid, note)
    nid = new['evidence_version_id']
    model.calls.clear()
    seed = ModifiedRuns(store).seed(actor, sid, rid)
    validate('ModifiedRunSeed8', seed)
    assert seed['model_snapshot'] == frozen['model_snapshot']
    assert seed['source_configuration'] == frozen['configuration']
    request = seed['configuration']
    request['context_source']['choice_confirmed'] = True
    request['assumptions'][0]['statement'] = 'Explicit modified statement'
    link = dict(evidence_version_id=nid, relation='context')
    request['assumptions'][0]['evidence_links'] = [link]
    request['general_context_evidence_version_ids'] = [nid]
    preview = configs.preview(actor, sid, request)[0]
    saved = configs.commit(actor, sid, save_command(request, preview['candidate_digest']))
    fetched = [c for c in model.calls if c[2] == 'GET' and '/revisions/' in c[3]]
    assert not fetched, 'Modified origin fetched the current model'
    config, src = saved['configuration'], frozen['configuration']
    assert config['schema_version'] == '6'
    assert not set(config) & {'criteria', 'approach_binding'}
    assert config['configuration_id'] != src['configuration_id']
    assert config['parent_revision_id'] is None
    assert saved['model_snapshot'] == frozen['model_snapshot']
    assert config['model_revision_id'] == src['model_revision_id']
    snapshots = config['evidence_snapshots']
    assert [r['evidence_version_id'] for r in snapshots] == sorted([oid, nid])
    assert [r for r in snapshots if r['evidence_version_id'] == oid] == src['evidence_snapshots']
    paths = {r['path'] for r in config['derivation']['changes']}
    assert '/assumptions/' + aid + '/statement' in paths
    assert '/assumptions/' + aid + '/evidence_links/' + oid + ':supports' in paths
    assert '/assumptions/' + aid + '/evidence_links/' + nid + ':context' in paths
    assert '/general_context_evidence_version_ids/' + nid in paths
    assert canonical(payload(env, rid)) == original
    assert canonical(payload(env)) == env['original']


def test_existing_member_revocation_blocks_history_seed_and_inventory(actual):
    env=actual;store=env['store'];sid=env['sid'];actor=env['actor']
    with store.connection(write=True) as db:
        member=dict(db.execute('SELECT * FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor)).fetchone())
        db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    try:
        for service in (History(store).read,ModifiedRuns(store).seed,ResultBindings(store).retained):
            with pytest.raises(DomainError) as error:service(actor,sid,env['rid'])
            assert error.value.status==404
        with pytest.raises(DomainError):ResultBindings(store).inventory(actor,sid)
    finally:
        with store.connection(write=True) as db:
            db.execute('INSERT INTO memberships ('+','.join(member)+') VALUES ('+','.join('?' for _ in member)+')',tuple(member.values()))


@pytest.mark.parametrize('supported',[True,False])
def test_public_history_view_seed_and_checked_configuration6_capability(actual, supported):
    import subprocess
    from pathlib import Path
    from test_assumptions_evidence_contracts import sample,D
    env=actual;caps=sample(D['Capabilities'])
    caps['generator_identity'].update(source_commit='a'*40,provenance_path='provenance/fixture.json')
    cap=sample(D['Capabilities']['properties']['capabilities']['items'])
    cap.update(id='resolved_configuration',version='3',supported=supported)
    caps.update(contract_versions=['1.2'],schema_versions=['1','2'],capabilities=[cap])
    if supported:
        caps['capabilities'].append(deepcopy(CRITERIA_FREE_CAPABILITY))
    # The reviewed native interpreter intentionally has no web stack. The
    # approved application interpreter reads the same isolated retained store,
    # with the full existing scope/env guard and no AiiDA imports or allocation.
    repo=Path(__file__).resolve().parents[2]
    target=guard.scoped_path(SCOPE,'artifacts/api-'+str(supported)+'.json')
    data = dict(caps=caps, actor=env['actor'], sid=env['sid'], rid=env['rid'], supported=supported)
    target.write_text(json.dumps(data))
    script='''import json,sys
from pathlib import Path
repo=Path(sys.argv[1])
sys.path[:0]=[str(repo/p) for p in ('deployment/tests','application/src','integration/src')]
import scoped_fixture as guard
scope=guard.scope_from_environment()
assert sys.executable==guard.APPROVED_CONTRACT_PYTHON
data=json.loads(guard.scoped_path(scope,sys.argv[2]).read_text())
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.store import Store
from hyprn_mvp_app.modeling import validate
store=Store(guard.scoped_path(scope,'artifacts/ae-history.sqlite'))
class Private:
    def call(self,actor,sid,method,path,**kwargs):
        assert method=='GET' and path=='/capabilities','Retained API called modeling'
        return 200,dict(data=data['caps'])
origin='http://127.0.0.1:19999'
client=TestClient(create_app(store,Auth(store,origin),Private()),base_url=origin)
session=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':origin})
assert session.status_code==200
response=client.get('/api/1/capabilities');assert response.status_code==200
versions = response.json()['data']['contract_versions']
# New configurations are version 6 only: earlier configuration and bundle versions are never
# advertised, and version 6 only when the private service supports it.
assert ('configuration/6' in versions) is data['supported']
assert ('execution_bundle/11' in versions) is data['supported']
assert not {'configuration/3', 'execution_bundle/4'} & set(versions)
route='/api/1/studies/'+data['sid']+'/runs/'+data['rid']
detail=client.get(route);assert detail.status_code==200,detail.text
# The public read is the record view of the exact retained history: obsolete result facets are
# projected out and both source and view hashes are carried; the stored record is unchanged.
from jsonschema import Draft202012Validator, FormatChecker
from hyprn_mvp_app.contracts import public_record_view
from hyprn_mvp_app.history import History
public = json.loads((repo / 'contracts/hyprn-mvp.openapi.yaml').read_text())
schema = {**public, '$ref': '#/components/schemas/RunHistory2'}
viewed = detail.json()['data']['history']
Draft202012Validator(schema, format_checker=FormatChecker()).validate(viewed)
retained = History(store).read(data['actor'], data['sid'], data['rid'])
validate('RunHistory2', retained)
assert viewed == public_record_view(retained)
seed=client.get(route+'/modified-run-seed');assert seed.status_code==200,seed.text
validate('ModifiedRunSeed2',seed.json()['data'])
assert not any(n.split('.')[0] in ('aiida','openmdao','openturns') for n in sys.modules)
print(json.dumps(dict(capabilities=response.json()['data'],history=detail.json()['data']['history'],seed=seed.json()['data'],native_imports=[])))
'''
    command=[guard.APPROVED_CONTRACT_PYTHON,'-B','-c',script,str(repo),str(target.relative_to(SCOPE.root))]
    result=subprocess.run(command,env=guard.clean_environment(SCOPE),capture_output=True,text=True)
    guard.scoped_path(SCOPE,'evidence/api-'+str(supported)+'.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    assert result.returncode==0,result.stderr
