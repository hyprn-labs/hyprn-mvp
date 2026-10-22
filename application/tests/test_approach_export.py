"""Portable approach records from isolated actual native-generated calculations."""
import base64,io,json,zipfile
from copy import deepcopy
from pathlib import Path
import pytest
from hyprn_mvp_app.store import Store,canonical,digest,uid,DomainError
from hyprn_mvp_app.computational_export import ComputationalRecords,LIMITS,zip_entries,sha
from hyprn_mvp_app.execution import assemble_bundle
from hyprn_mvp_app.approach_closure import build_closure
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_integration.calculation import NativeExecution
from checks import PROJECTION_SCOPE as SCOPE,NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from test_approach_bundle import case5
from test_approach_closure import resolution,signed,sample,D,link
from test_assumptions_execution import repin
from test_assumptions_history import retain,payload

_ENV=None
def export_env():
    global _ENV
    if _ENV is not None:return _ENV
    guard.prepare_worker_fixture(SCOPE,BACKEND)
    native=NativeExecution(backend=BACKEND,root=SCOPE.root)
    store=Store(SCOPE.root/'artifacts/approach-export.sqlite');actor=uid();study=store.create_study(actor,uid(),'Portable study');sid=study['study_id']
    env=dict(store=store,actor=actor,sid=sid,study=study,native=native)
    source_case,_=case5(False,sid=sid);source=retain(env,source_case)
    import test_assumptions_execution as fixtures
    from execution_fixtures import fixture
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fixtures,'fixture',lambda:fixture('throw'));failed_case,deps=case5(False,sid=sid)
    f=failed_case['frozen'];c=f['configuration'];b=assemble_bundle(uid(),failed_case['prepared'],failed_case['files'],f,native.bundle_runtime(),deps)
    request=dict(run_id=b['manifest']['run_id'],scope=sid,command_id=uid(),payload_digest='a'*64,bundle_digest=b['manifest']['bundle_digest'])
    failed=native.launch(b,request);association={k:failed[k] for k in ('store_uuid','process_uuid')};record=native.read_record(request,association)
    assert failed['exit_status']!=0 and record['results']['execution']['state']=='failed'
    basis=signed(dict(schema_version='1',run_id=request['run_id'],study_id=sid,request=request,association=association,
        configuration_revision_id=c['configuration_revision_id'],configuration_digest=c['digest'],model_revision_id=f['model_snapshot']['model_revision_id'],model_digest=f['model_snapshot']['digest'],context=c['context_snapshot'],results=record['results'],assessment=record['assessment'],runtime=b['manifest']['runtime'],errors=record['errors']))
    case=deepcopy(source_case);config=case['frozen']['configuration'];model=case['frozen']['model_snapshot']
    config.update(configuration_id=uid(),configuration_revision_id=uid())
    v=sample(D['ApproachVersion1']);v['study_id']=sid;binding,_=link(v,model)
    config['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest='f'*64)
    v['content']['basis_refs']=[dict(kind='run',run_id=basis['run_id'],reason='Investigate the retained failed method',relation='challenges')];signed(v)
    evidence={e['evidence_version_id']:e for e in config['evidence_snapshots']+c['evidence_snapshots']}
    closure=build_closure(v,resolution(models=[model,f['model_snapshot']],configurations=[c],run_contexts=[basis],evidence=list(evidence.values())),study_id=sid)
    case['frozen']['approach_closure']=closure;config['approach_binding'].update(approach_digest=v['digest'],closure_digest=closure['digest'])
    from hyprn_mvp_app.result_bindings import ResultBindings
    output=next(o for o in source['record']['results']['outputs'] if o['value']==7)
    resolved=ResultBindings(store).resolve(actor,sid,dict(source_run_id=source['rid'],source_output=output['target'],expected_results_digest=digest(source['record']['results'])))
    item=config['inputs'][0];item.update(value=resolved['value'],units=resolved['units'])
    item['result_binding']={k:resolved[k] for k in ('source_run_id','source_output','results_digest','source_configuration_digest','labels')}
    item['result_binding'].update(original_value=resolved['value'],original_units=resolved['units'],conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='c'*64,source_units=resolved['units'],destination_units=resolved['units'],factor=1,destination_value=resolved['value']))
    config['required_capabilities'].append('result_linked_inputs/1');repin(case)
    from test_approach_history import polish_case
    polish_case(case);closure=case['frozen']['approach_closure']
    child=retain(env,case);env.update(child,source=source,failed=basis,failed_case=failed_case,closure=closure)
    env['service']=ComputationalRecords(store,SCOPE.root/'artifacts/approach-records')
    _ENV=env;return env

def create_record(env):
    s=env['service'];p=s.enqueue_preview(env['actor'],env['sid'],dict(command_id=uid(),selected_run_ids=[env['rid']]))
    validate('RecordRequest2',p);assert p['approach_summary'] is None
    s.process_one(env['native'].archive_record,request_id=p['request_id']);p=s.status(env['actor'],env['sid'],p['request_id'])
    assert p['state']=='reviewable',p
    q=s.enqueue_create(env['actor'],env['sid'],dict(command_id=uid(),preview_id=p['request_id'],expected_preview_digest=p['preview']['preview_digest']))
    s.process_one(env['native'].archive_record,request_id=q['request_id']);q=s.status(env['actor'],env['sid'],q['request_id'])
    assert q['state']=='ready',q
    return p,q,s.download(env['actor'],env['sid'],q['request_id'])

def ready():
    e=export_env()
    if 'ready' not in e:e['ready']=create_record(e)
    return e,e['ready']

def test_typed_preview_manifest_and_basis_do_not_expand_native_ancestry(monkeypatch):
    from hyprn_mvp_app import computational_export as exports
    e=export_env()
    def denied(*a,**k):pytest.fail('Export reached current scientific or execution authority')
    monkeypatch.setattr(NativeExecution,'launch',denied)
    monkeypatch.setattr('hyprn_mvp_app.modeling.Coordinator.read',denied)
    monkeypatch.setattr(Store,'evidence_version',denied)
    e,(p,q,raw)=ready();manifest=exports.inspect_record(raw)
    validate('ComputationalRecordManifest2',manifest)
    summary=p['preview']['approach_summary']
    assert p['approach_summary']==q['approach_summary']==q['preview']['approach_summary']==manifest['approach_summary']==summary
    assert summary['basis_run_ids']==[e['failed']['run_id']]
    assert summary['basis_configuration_ids']==[e['failed_case']['frozen']['configuration']['configuration_revision_id']]
    assert manifest['computational_run_ids']==sorted([e['rid'],e['source']['rid']])
    assert e['failed']['run_id'] not in manifest['computational_run_ids']
    assert len(manifest['approaches'])==1
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        closure=json.loads(z.read(manifest['approaches'][0]['path']))
        assert closure==e['closure'] and closure['run_contexts'][0]['results']['execution']['state']=='failed'
        version=next(v for v in closure['approach_versions'] if v['approach_version_id']==closure['root_approach_version_id'])
        assert version['schema_version']=='2' and version['content']['original_question']['text']=='Original scientific question'
        assert version['content']['limit_items'][0]['evidence_links']
        assert json.loads(z.read('hyprn-mvp/runs/'+e['rid']+'/bundle/manifest.json'))['schema_version']=='8'
        assert json.loads(z.read('hyprn-mvp/runs/'+e['source']['rid']+'/bundle/manifest.json'))['schema_version']=='5'
    (SCOPE.root/'evidence/approach-record.zip').write_bytes(raw)
    (SCOPE.root/'evidence/approach-record-proof.json').write_text(json.dumps(dict(preview=p,status=q,manifest=manifest,failed_basis=e['failed']['run_id']),indent=2))

def rewrite(raw,change):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:files={p:z.read(p) for p in z.namelist()}
    m=json.loads(files['manifest.json']);change(m,files)
    for item in m['inventory']:
        if item['path'] in files:item.update(size=len(files[item['path']]),sha256=sha(files[item['path']]))
    m['manifest_digest']=digest({k:v for k,v in m.items() if k!='manifest_digest'});files['manifest.json']=canonical(m)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for path,data in files.items():z.writestr(path,data)
    return stream.getvalue()

@pytest.mark.parametrize('change',['summary','duplicate','role','path','closure','pin','model','extra'])
def test_offline_resealed_tampering_rejected(change):
    from hyprn_mvp_app.computational_export import inspect_record
    e,(_,_,raw)=ready()
    def alter(m,files):
        index=m['approaches'][0];path=index['path']
        if change=='summary':m['approach_summary']['basis_run_ids']=[]
        elif change=='duplicate':m['approaches'].append(deepcopy(index))
        elif change=='role':next(i for i in m['inventory'] if i['path']==path)['role']='runtime'
        elif change=='path':index['path']='../escape'
        elif change=='closure':
            value=json.loads(files[path]);value['run_contexts'][0]['results']['outputs'][0]['value']=0;files[path]=canonical(value)
        elif change in ('pin','model'):
            suffix='/bundle/configuration.json' if change=='pin' else '/bundle/model.json'
            p=next(p for p in files if e['rid'] in p and p.endswith(suffix));value=json.loads(files[p])
            if change=='pin':value['approach_binding']['approach_version_id']=uid()
            else:value['source_files'][0]['bytes']='eA=='
            signed(value);files[p]=canonical(value)
        else:files['unlisted.json']=b'{}'
    with pytest.raises((ValueError,DomainError,KeyError)):inspect_record(rewrite(raw,alter))


def test_null_pin_is_portable_without_mandatory_approach():
    from hyprn_mvp_app.computational_export import inspect_record
    e=export_env();p,q,raw=create_record(dict(e,rid=e['source']['rid']))
    manifest=inspect_record(raw)
    assert manifest['schema_version']=='2' and manifest['approach_summary'] is None and manifest['approaches']==[]
    assert p['approach_summary'] is None and q['approach_summary'] is None
    assert not any(i['role']=='approach' for i in manifest['inventory'])

def test_payloads_deduplicate_exact_identity_and_reject_conflicting_closure():
    from hyprn_mvp_app.computational_export import approach_payloads
    e=export_env();records,_,_,_=e['service']._collect(e['actor'],e['sid'],[e['rid']])
    records['second-occurrence']=deepcopy(records[e['rid']])
    indices,summary,files=approach_payloads(records)
    assert len(indices)==len(files)==1 and summary['model_count']==2
    records['second-occurrence'][0]['approach_closure']['models'][0]['name']='Changed retained model'
    with pytest.raises(ValueError):approach_payloads(records)

def test_replay_status_download_reauthorize_and_recheck_saved_closure():
    e,(_,q,_)=ready();s=e['service'];actor=e['actor'];sid=e['sid']
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?',(actor,sid))
    try:
        for action in (lambda:s.status(actor,sid,q['request_id']),lambda:s.download(actor,sid,q['request_id']),lambda:s.enqueue_preview(actor,sid,dict(command_id=uid(),selected_run_ids=[e['rid']]))):
            with pytest.raises(DomainError):action()
    finally:
        with e['store'].connection(write=True) as db:db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))
    original=payload(e);changed=deepcopy(original);changed['frozen']['approach_closure']['digest']='f'*64
    with e['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(changed),e['rid']))
    try:
        for action in (lambda:s.status(actor,sid,q['request_id']),lambda:s.download(actor,sid,q['request_id'])):
            with pytest.raises(DomainError):action()
    finally:
        with e['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(original),e['rid']))


def test_native_archive_root_order_is_not_authority_but_membership_and_policy_are():
    """Actual native metadata may use either set order; no root/policy relaxation."""
    from hyprn_mvp_app.computational_export import verify_native
    e=export_env();selected=sorted([e['rid'],e['source']['rid']])
    preflight=e['service']._collect(e['actor'],e['sid'],selected)[2]
    response=e['native'].archive_record(preflight)
    roots=sorted(c['association']['process_uuid'] for c in preflight['computations'] if c['role']=='selected')
    assert len(roots)==2
    raw=base64.b64decode(response['archive_base64'])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:files={p:z.read(p) for p in z.namelist()}
    for fault in ('sorted','reversed','duplicate','missing','foreign','extra_kind','traversal','admin','extra_field','wrong_type'):
        metadata=json.loads(files['metadata.json']);parameters=metadata['creation_parameters']
        parameters['entities_starting_set']['node']=list(roots)
        if fault=='reversed':parameters['entities_starting_set']['node'].reverse()
        elif fault=='duplicate':parameters['entities_starting_set']['node'].append(roots[0])
        elif fault=='missing':parameters['entities_starting_set']['node'].pop()
        elif fault=='foreign':parameters['entities_starting_set']['node'][0]=uid()
        elif fault=='extra_kind':parameters['entities_starting_set']['group']=[]
        elif fault=='traversal':parameters['graph_traversal_rules']['input_calc_forward']=True
        elif fault=='admin':parameters['include_authinfos']=True
        elif fault=='extra_field':parameters['unexpected']=False
        elif fault=='wrong_type':parameters['entities_starting_set']['node']=[None,roots[1]]
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path,value in files.items():z.writestr(path,canonical(metadata) if path=='metadata.json' else value)
        changed=stream.getvalue();candidate=deepcopy(response)
        candidate.update(archive_base64=base64.b64encode(changed).decode(),archive_size=len(changed),archive_sha256=sha(changed))
        if fault in ('sorted','reversed'):
            assert verify_native(candidate,preflight)[0]==changed
        else:
            with pytest.raises(ValueError,match='Native archive traversal authority'):verify_native(candidate,preflight)
        assert base64.b64decode(candidate['archive_base64'])==changed
