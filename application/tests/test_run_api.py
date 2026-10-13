"""Public submission and exact static preparation against the private model service."""
import json
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_api import api, model_revision, candidate, post, uid, configuration_request, configuration_commit
from hyprn_mvp_app.store import DomainError
from test_submission import submission,accepted

def reseal(case):
    """Adversarial rehashing of data, never code generation."""
    from hyprn_mvp_app.store import digest
    from execution_fixtures import raw_hash
    p=case['prepared']
    for f in p['files']:
        raw=case['files'][f['path']];f.update(size=len(raw),sha256=raw_hash(raw))
    p['executable_content_digest']=digest(dict(protocol=p['entrypoint']['protocol'],model_digest=p['model_digest'],
        configuration_digest=p['configuration_digest'],generator_identity=p['generator_identity'],
        files=sorted([{k:f[k] for k in ('path','size','sha256')} for f in p['files'] if f['path'].startswith('generated/')],key=lambda f:f['path'])))
    p['prepared_digest']=digest({k:v for k,v in p.items() if k!='prepared_digest'})

@pytest.mark.parametrize('kind',['chain','chain3','unrelated','units','unwritten','nan','inf','throw','retained_throw','inplace','canary'])
def test_native_bundle_accepts_actual_generic_inventory_without_import(monkeypatch,kind):
    from execution_fixtures import fixture,runtime_fixture
    from hyprn_mvp_app.execution import assemble_bundle
    import builtins
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        assert not name.startswith(('generated','openmdao'))
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    case=fixture(kind);p=case['prepared']
    b=assemble_bundle(uid(),p,case['files'],case['frozen'],runtime_fixture())
    assert b['manifest']['schema_version']=='2'
    assert b['manifest']['entrypoint']==p['entrypoint']
    assert b['manifest']['executable_content_digest']==p['executable_content_digest']
    assert b['manifest']['generator']==p['generator_identity']
    assert all(b['files'][path]==raw for path,raw in case['files'].items())
    assert {'model_author','generated_code','runtime'} <= {n['kind'] for n in b['manifest']['licenses']}

def test_consumer_has_no_backend_name_or_exact_generated_inventory_dependency():
    from execution_fixtures import fixture,runtime_fixture,raw_hash
    from hyprn_mvp_app.execution import assemble_bundle
    case=fixture();p=case['prepared'];p['generator_identity']['name']='another-conforming-native-generator'
    path='generated/support/extra.json';raw=b'{"format":"inert support data"}'
    case['files'][path]=raw
    p['files'].append(dict(file_id=uid(),path=path,size=len(raw),sha256=raw_hash(raw),media_type='application/json',role='generated'))
    p['files'].sort(key=lambda f:f['path']);reseal(case)
    assert assemble_bundle(uid(),p,case['files'],case['frozen'],runtime_fixture())['files'][path]==raw

@pytest.mark.parametrize('part',['source','module','support','bindings','configuration','manifest'])
def test_native_raw_tamper_rejected(part):
    from execution_fixtures import fixture,runtime_fixture
    from hyprn_mvp_app.execution import assemble_bundle
    case=fixture();p=case['prepared'];files=case['files']
    paths={'source':next(n for n in files if n.startswith('sources/')),'module':p['entrypoint']['module_path'],
        'support':'generated/native_support.py','bindings':p['entrypoint']['bindings_path']}
    if part in paths:files[paths[part]]+=b'changed'
    elif part=='configuration':case['frozen']['configuration']['inputs'][0]['value']=987
    else:p['generator_identity']['version']='forged'
    with pytest.raises(ValueError):assemble_bundle(uid(),p,files,case['frozen'],runtime_fixture())

@pytest.mark.parametrize('part',['factory','path','unknown','version','duplicate_id','duplicate_path','missing_module',
    'binding_unit','binding_target','binding_component','binding_path','missing_input','missing_output','extra_input',
    'source_owner','source_line','source_bytes','provenance_hash','provenance_original','provenance_patched','notice',
    'configuration_coverage','content_digest'])
def test_rehashed_semantic_tamper_rejected(part):
    from execution_fixtures import fixture,runtime_fixture
    from hyprn_mvp_app.execution import assemble_bundle
    from hyprn_mvp_app.store import canonical,digest
    case=fixture();p=case['prepared'];files=case['files'];entry=p['entrypoint']
    bindings=json.loads(files[entry['bindings_path']]);mapping=json.loads(files[entry['source_map_path']])
    prov=json.loads(files[p['generator_identity']['provenance_path']])
    if part=='factory':entry['factory']='eval'
    elif part=='path':entry['module_path']='../entry.py'
    elif part=='unknown':p['native_payload']={}
    elif part=='version':p['schema_version']='1'
    elif part=='duplicate_id':p['files'][1]['file_id']=p['files'][0]['file_id']
    elif part=='duplicate_path':p['files'].append(copy.deepcopy(p['files'][0]))
    elif part=='missing_module':files.pop(entry['module_path']);p['files']=[f for f in p['files'] if f['path']!=entry['module_path']]
    elif part=='binding_unit':bindings['inputs'][0]['units']='m'
    elif part=='binding_target':bindings['inputs'][0]['target']['port_id']=uid()
    elif part=='binding_component':bindings['inputs'][0]['component_id']=uid()
    elif part=='binding_path':bindings['inputs'][0]['path']='other.x'
    elif part=='missing_input':bindings['inputs'].pop()
    elif part=='missing_output':bindings['outputs'].pop()
    elif part=='extra_input':bindings['inputs'].append(copy.deepcopy(bindings['outputs'][0]))
    elif part=='source_owner':mapping['entries'][0]['definition_version_id']=uid()
    elif part=='source_line':mapping['entries'][0]['generated_line_end']=999999
    elif part=='source_bytes':files[mapping['entries'][0]['source_path']]+=b'forged'
    elif part=='provenance_hash':prov['source_archive']['sha256']='0'*64
    elif part=='provenance_original':prov['upstream_files'][0]['path']=prov['patched_files'][0]['path']
    elif part=='provenance_patched':prov['patched_files'][0]['sha256']='1'*64
    elif part=='notice':p['license_notices'][0]['path']='licenses/missing.txt'
    elif part=='configuration_coverage':
        cfg=case['frozen']['configuration'];cfg['inputs'].pop();cfg['digest']=digest({k:v for k,v in cfg.items() if k!='digest'});p['configuration_digest']=cfg['digest']
    files[entry['bindings_path']]=canonical(bindings)
    files[entry['source_map_path']]=canonical(mapping)
    files[p['generator_identity']['provenance_path']]=canonical(prov)
    reseal(case)
    if part=='content_digest':p['executable_content_digest']='f'*64;p['prepared_digest']=digest({k:v for k,v in p.items() if k!='prepared_digest'})
    with pytest.raises(ValueError):assemble_bundle(uid(),p,files,case['frozen'],runtime_fixture())

def test_obsolete_preparation_has_actionable_error():
    from execution_fixtures import legacy_fixture,runtime_fixture
    from hyprn_mvp_app.execution import assemble_bundle
    case=legacy_fixture()
    with pytest.raises(ValueError,match='Unsupported.*version'):
        assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],runtime_fixture())

def stored_bundle(store,run):
    with store.connection() as db:return json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run,)).fetchone()[0])

def set_payload(store,run,payload):
    with store.connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),run))

def test_rehashed_inner_program_cannot_replace_trusted_request_digest(submission):
    from hyprn_mvp_app.store import canonical,digest
    from execution_fixtures import raw_hash
    service,store,actor,sid,_,native=submission;run=accepted(submission)['run_id']
    service.dispatch(run,prepare_only=True)
    payload=stored_bundle(store,run);bundle=payload['bundle'];files={p:base64.b64decode(b) for p,b in bundle['files'].items()}
    prepared=json.loads(files['preparation.json']);path=prepared['entrypoint']['module_path']
    files[path]+=b'\n# attacker replaced program\n'
    reseal(dict(prepared=prepared,files=files))
    files['preparation.json']=canonical(prepared)
    manifest=bundle['manifest'];manifest['prepared_digest']=prepared['prepared_digest'];manifest['executable_content_digest']=prepared['executable_content_digest']
    for f in manifest['files']:f.update(size=len(files[f['path']]),sha256=raw_hash(files[f['path']]))
    manifest['bundle_digest']=digest({k:v for k,v in manifest.items() if k!='bundle_digest'})
    bundle['files']={p:base64.b64encode(raw).decode() for p,raw in files.items()};set_payload(store,run,payload)
    with pytest.raises(ValueError,match='immutable request'):service.dispatch(run)
    assert native.launches==0 and service.read(actor,sid,run)['state']=='prepared'

def test_historical_pending_bundle_refused_without_prepare_attestation_or_claim(submission):
    service,store,actor,sid,_,native=submission;run=accepted(submission)['run_id'];service.dispatch(run,prepare_only=True)
    payload=stored_bundle(store,run);payload['bundle']['manifest']['schema_version']='1';set_payload(store,run,payload)
    def forbidden(*args):raise AssertionError('Historical pending preparation must not contact services')
    service.prepare=forbidden;native.require_attestation=forbidden
    service.dispatch(run);service.dispatch(run)
    assert service.read(actor,sid,run)['state']=='preparation_failed' and native.launches==0
    receipt=store.receipt(actor,sid,'run',service.read(actor,sid,run)['command_id'])
    assert receipt['error']['code']=='unsupported_execution_version'
    assert stored_bundle(store,run)['bundle']==payload['bundle']

def test_historical_recorded_replay_is_read_only_and_currently_authorized(submission):
    service,store,actor,sid,_,native=submission;result=accepted(submission);run=result['run_id'];service.dispatch(run)
    payload=stored_bundle(store,run);payload['bundle']['manifest']['schema_version']='1';set_payload(store,run,payload)
    def forbidden(*args):raise AssertionError('Recorded historical replay crossed native boundary')
    native.require_attestation=forbidden;native.matches=forbidden;service.prepare=forbidden
    assert accepted(submission,result['command_id'])['state']=='recorded'
    service.dispatch(run)
    assert stored_bundle(store,run)==payload and native.launches==1
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    with pytest.raises(DomainError):accepted(submission,result['command_id'])

def test_revoked_after_preparation_cannot_cross_claim(submission):
    service,store,actor,sid,_,native=submission;run=accepted(submission)['run_id'];service.dispatch(run,prepare_only=True)
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    service.dispatch(run)
    with store.connection() as db:
        receipt=store._receipt(db,sid,'run',db.execute('SELECT command_id FROM run_associations WHERE run_id=?',(run,)).fetchone()[0])
        assert receipt['state']=='preparation_failed' and receipt['error']['code']=='resource_not_found'
    assert native.launches==0

def test_authorization_is_rechecked_in_claim_transaction(submission):
    service,store,actor,sid,_,native=submission;run=accepted(submission)['run_id']
    def revoke(point):
        if point=='before_claim':
            with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    service.fault=revoke
    service.dispatch(run)
    with store.connection() as db:
        receipt=store._receipt(db,sid,'run',db.execute('SELECT command_id FROM run_associations WHERE run_id=?',(run,)).fetchone()[0])
        assert receipt['state']=='preparation_failed' and receipt['error']['code']=='resource_not_found'
    assert native.launches==0

def test_native_preparation_command_namespace_and_old_response_refusal():
    from execution_fixtures import legacy_fixture
    from hyprn_mvp_app.execution import StaticPreparation
    from uuid import UUID,uuid5
    case=legacy_fixture();command=uid();sid=uid();calls=[]
    class OldProducer:
        def call(self,*args,**kwargs):calls.append(args);return 200,dict(data=case['prepared'])
    with pytest.raises(ValueError,match='Unsupported preparation version'):
        StaticPreparation(OldProducer())(uid(),sid,command,case['frozen'])
    assert len(calls)==1
    assert calls[0][4]['command_id']==str(uuid5(UUID(command),'hyprn_mvp.prepare.artifact2:'+sid))
    assert calls[0][4]['command_id']!=str(uuid5(UUID(command),'hyprn_mvp.prepare.v1:'+sid))

def test_capabilities_declare_verified_native_program_versions(api):
    capabilities=api[0].get('/api/1/capabilities').json()['data']
    assert {'prepared_artifact/2','execution_bundle/2','hyprn_mvp.openmdao.program/1'}<=set(capabilities['contract_versions'])
    assert 'native_program_execution_pending_attestation' not in capabilities['unavailable']

def configured(api):
    s,m=model_revision(api);sid=s['study_id']
    frozen=post(api[0],f'/studies/{sid}/configurations',configuration_commit(api,configuration_request(api,s,m)),201)['data']
    return sid,frozen

def test_public_run_atomic_replay_conflict_authorization_and_status(api):
    from test_public_contract import check
    c,store,_,_,transport,actor=api;sid,frozen=configured(api)
    body=dict(command_id=uid(),configuration_revision_id=frozen['configuration']['configuration_revision_id'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:post(c,f'/studies/{sid}/runs',body,202)['data'],range(8)))
    assert len({r['run_id'] for r in results})==1
    run=results[0]
    assert run['state']=='accepted_run'
    status_response=c.get(f"/api/1/studies/{sid}/runs/{run['run_id']}")
    check(status_response)
    assert status_response.json()['data']==run
    check(c.get(run['receipt_url']))
    assert c.get(run['receipt_url']).json()['data']['result']['run_id']==run['run_id']
    post(c,f'/studies/{sid}/runs',{**body,'configuration_revision_id':uid()},409)
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]==1
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    before=len(transport.calls)
    post(c,f'/studies/{sid}/runs',body,404)
    assert c.get(f"/api/1/studies/{sid}/runs/{run['run_id']}").status_code==404
    assert c.get(run['receipt_url']).status_code==404
    assert len(transport.calls)==before

def test_static_prepare_exact_manifest_same_command_response_loss(api):
    from hyprn_mvp_app.execution import StaticPreparation,validate_preparation
    c,store,_,model,transport,actor=api;sid,frozen=configured(api)
    prepare=StaticPreparation(model);command=uid()
    transport.fail_after=True
    with pytest.raises(DomainError):prepare(actor,sid,command,frozen)
    first,files=prepare(actor,sid,command,frozen)
    second,again=prepare(actor,sid,command,frozen)
    assert first==second and files==again
    assert first['model_package_manifest']['revisions'][-1]==frozen['model_snapshot']
    validate_preparation(first,files,frozen)
    from hyprn_mvp_app.store import digest
    tampered=json.loads(json.dumps(first));tampered['model_package_manifest']['license_notices'].append('invented')
    tampered['prepared_digest']=digest({k:v for k,v in tampered.items() if k!='prepared_digest'})
    with pytest.raises(ValueError):validate_preparation(tampered,files,frozen)
