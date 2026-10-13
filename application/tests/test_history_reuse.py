"""Data-only bundle3 native/app readers using a real isolated native repository."""
import io
import json
import base64
import copy
import subprocess
import sys
import pytest
from aiida import orm
from checks import NATIVE_BACKEND, PROJECTION_SCOPE
from test_result_dependencies import source, native, linked_bundle, rehash
from test_results import retained_record
from test_result_bindings import env, saved2, prepared2
from test_bridge import wire
from hyprn_mvp_app.store import canonical, digest, Store, uid, DomainError
from hyprn_mvp_app.history import History, projection
from hyprn_mvp_app.execution import Submissions
from hyprn_mvp_integration.results import retained_bundle
from aiida.common.links import LinkType


def repository(bundle):
    folder=orm.FolderData(backend=NATIVE_BACKEND)
    for path,raw in {**bundle['files'],'manifest.json':canonical(bundle['manifest'])}.items():
        folder.base.repository.put_object_from_filelike(io.BytesIO(raw),path)
    return folder.base.repository


def test_bundle3_native_reader_retains_full_private_and_mapping_bytes(source):
    bundle,request=linked_bundle(source)
    assert retained_bundle(repository(bundle),request)==bundle


def native_record(bundle,request,result=None,*,raw=b'Synthetic retained diagnostic\n'):
    node=orm.CalcJobNode(process_type='aiida.calculations:hyprn_mvp.scalar',backend=NATIVE_BACKEND)
    req=orm.Dict(dict=request,backend=NATIVE_BACKEND).store()
    frozen=orm.FolderData(backend=NATIVE_BACKEND)
    for path,data in {**bundle['files'],'manifest.json':canonical(bundle['manifest'])}.items():
        frozen.base.repository.put_object_from_filelike(io.BytesIO(data),path)
    frozen.store()
    node.base.links.add_incoming(req,link_type=LinkType.INPUT_CALC,link_label='request')
    node.base.links.add_incoming(frozen,link_type=LinkType.INPUT_CALC,link_label='frozen_bundle')
    node.store()
    if result is not None:
        result=copy.deepcopy(result);result.update(run_id=request['run_id'],bundle_digest=request['bundle_digest'])
        data=orm.Dict(dict=result,backend=NATIVE_BACKEND)
        data.base.links.add_incoming(node,link_type=LinkType.CREATE,link_label='results');data.store()
    retrieved=orm.FolderData(backend=NATIVE_BACKEND)
    for path in ('result.json','launcher.stderr'):retrieved.base.repository.put_object_from_filelike(io.BytesIO(raw),path)
    retrieved.base.links.add_incoming(node,link_type=LinkType.CREATE,link_label='retrieved');retrieved.store()
    node.set_process_state('finished');node.set_exit_status(0);node.seal()
    return node


def stage_app(tmp_path,bundle):
    store=Store(tmp_path/'history.sqlite');config=json.loads(bundle['files']['configuration.json'])
    model=json.loads(bundle['files']['model.json']);sid=config['study_id'];actor=uid()
    frozen=dict(configuration=config,model_snapshot=model,study_revision=uid())
    with store.connection(write=True) as db:
        db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(sid,uid(),'Current renamed study','today','today'))
        db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(frozen)))
    service=Submissions(store,None,None)
    run=service.submit(actor,sid,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
    bundle['manifest']['run_id']=run['run_id'];rehash(bundle,{})
    request=dict(run_id=run['run_id'],scope=sid,command_id=run['command_id'],
        payload_digest=store.receipt(actor,sid,'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    payload=dict(actor=actor,frozen=frozen,request=request,bundle=dict(manifest=bundle['manifest'],
        files={p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()}))
    return store,actor,sid,run,payload


def save_record(store,rid,payload,association):
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),rid))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),rid))


@pytest.mark.parametrize('version',['1','2','3'])
def test_native_hydration_to_app_restart_retains_exact_bytes_without_model(source,native,tmp_path,monkeypatch,version):
    bundle=linked_bundle(source)[0] if version=='3' else retained_record(version)
    store,actor,sid,run,payload=stage_app(tmp_path,bundle);rid=run['run_id']
    node=native_record(bundle,payload['request'],source['results'].get_dict() if version=='3' else None)
    association=dict(store_uuid=native.store_uuid,process_uuid=node.uuid)
    save_record(store,rid,payload,association)
    with wire(monkeypatch,native,read_only=True) as (bridge,calls):
        Submissions(store,None,bridge).hydrate(actor,sid,rid)
    assert calls==['read_record']
    with store.connection() as db:before=db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]
    saved=json.loads(before)['history'];assert saved['schema_version']=='1'
    history=History(Store(store.path)).read(actor,sid,rid)
    assert history['configuration']==payload['frozen']['configuration']
    assert history['bundle']['schema_version']==version
    if version=='3':
        assert history['errors']==[]
        assert history['configuration']['inputs'][0]['result_binding']==payload['frozen']['configuration']['inputs'][0]['result_binding']
        assert history['configuration']['derivation'] is None
        assert node.uuid not in json.dumps(history) and native.store_uuid not in json.dumps(history)
    else:
        assert history['errors']==[dict(code='missing_results',partial=True)]
        assert all('result_binding' not in i for i in history['configuration']['inputs'])
        assert 'derivation' not in history['configuration']
    for artifact in history['artifacts']:
        raw,descriptor=History(store).read(actor,sid,rid,artifact['artifact_id'])
        if artifact['name'] in bundle['files']:assert raw==bundle['files'][artifact['name']]
        assert descriptor==artifact
    with store.connection(write=True) as db:db.execute('UPDATE studies SET description=? WHERE study_id=?',('Changed today',sid))
    assert History(Store(store.path)).read(actor,sid,rid)==history
    with store.connection() as db:assert db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]==before
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(sid,))
    with pytest.raises(DomainError):History(store).read(actor,sid,rid)
    with pytest.raises(DomainError):History(store).read(actor,sid,rid,history['artifacts'][0]['artifact_id'])


@pytest.mark.parametrize('field',['private','mapping','source','descriptor','prepared','full','missing'])
def test_rehashed_bundle3_semantic_corruption_rejected_native_and_app(source,tmp_path,field):
    bundle,request=linked_bundle(source);changes={}
    store,actor,sid,run,payload=stage_app(tmp_path,bundle)
    association=dict(store_uuid=uid(),process_uuid=uid())
    good=projection(payload,dict(request=payload['request'],bundle=bundle,results=None,assessment=None,artifacts={},errors=[],**association),association)
    payload['history']=good
    if field=='private':
        private=json.loads(bundle['files']['modeling-configuration.json']);private['inputs'][0]['value']=999
        private['digest']=digest({k:v for k,v in private.items() if k!='digest'})
        bundle['manifest']['modeling_configuration_digest']=private['digest'];changes['modeling-configuration.json']=private
    elif field in ('mapping','source'):
        deps=json.loads(bundle['files']['result-dependencies.json'])
        if field=='mapping':deps['mappings'][0]['original_value']=999
        else:deps['sources'][0]['request']['scope']=uid()
        changes['result-dependencies.json']=deps;raw=canonical(deps)
        bundle['manifest']['result_dependencies'].update(size=len(raw),sha256=__import__('hashlib').sha256(raw).hexdigest())
    elif field=='descriptor':bundle['manifest']['result_dependencies']['size']+=1
    elif field=='prepared':bundle['manifest']['prepared_digest']='f'*64
    elif field=='full':bundle['manifest']['configuration_digest']='f'*64
    else:
        bundle['files'].pop('result-dependencies.json')
        bundle['manifest']['files']=[f for f in bundle['manifest']['files'] if f['path']!='result-dependencies.json']
    rehash(bundle,changes);payload['request']['bundle_digest']=bundle['manifest']['bundle_digest']
    request=payload['request']
    with pytest.raises((ValueError,KeyError)):retained_bundle(repository(bundle),request)
    payload['bundle']=dict(manifest=bundle['manifest'],files={p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()})
    payload['history']['request']=request
    payload['history']['digest']=digest({k:v for k,v in payload['history'].items() if k!='digest'})
    with pytest.raises((ValueError,KeyError)):projection(payload,dict(request=request,bundle=bundle,results=None,assessment=None,artifacts={},errors=[],**association),association)
    save_record(store,run['run_id'],payload,association)
    history=History(store).read(actor,sid,run['run_id'])
    assert history['errors']==[dict(code='corrupt_retained_record',partial=True)]
    assert history['configuration'] is None and history['artifacts']==[]


@pytest.mark.parametrize('kind',['unsupported','missing','corrupt'])
def test_partial_bundle3_native_record_keeps_diagnostic_without_fallback(source,native,tmp_path,monkeypatch,kind):
    bundle,_=linked_bundle(source)
    if kind=='unsupported':bundle['manifest']['schema_version']='99'
    store,actor,sid,run,payload=stage_app(tmp_path,bundle)
    if kind=='missing':bundle['files'].pop('modeling-configuration.json')
    elif kind=='corrupt':bundle['files']['modeling-configuration.json']=b'{}'
    node=native_record(bundle,payload['request'])
    association=dict(store_uuid=native.store_uuid,process_uuid=node.uuid)
    save_record(store,run['run_id'],payload,association)
    with wire(monkeypatch,native,read_only=True) as (bridge,calls):
        Submissions(store,None,bridge).hydrate(actor,sid,run['run_id'])
    history=History(Store(store.path)).read(actor,sid,run['run_id'])
    assert history['errors']==[dict(code='unsupported_record_version' if kind=='unsupported' else 'corrupt_retained_record',partial=True)]
    assert history['configuration'] is None and history['results'] is None
    assert len(history['artifacts'])==2 and calls==['read_record']
    for artifact in history['artifacts']:
        assert History(store).read(actor,sid,run['run_id'],artifact['artifact_id'])[0]==b'Synthetic retained diagnostic\n'


def test_results_module_stays_stdlib_at_worker_import_time():
    import scoped_fixture
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/'integration/src/hyprn_mvp_integration/results.py'
    code="import builtins,runpy; original=builtins.__import__\ndef guarded(name,*a,**k):\n if name.split('.')[0] in ('hyprn_mvp_app','aiida','openmdao','jsonschema'): raise AssertionError(name)\n return original(name,*a,**k)\nbuiltins.__import__=guarded\nrunpy.run_path("+repr(str(path))+")\n"
    result=subprocess.run([sys.executable,'-I','-B','-c',code],env=scoped_fixture.clean_environment(PROJECTION_SCOPE),capture_output=True,text=True)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('point',['before_claim','after_claim'])
def test_real_source_disappearance_across_bridge_fails_closed_without_redispatch(env,native,monkeypatch,point):
    from aiida.tools.graph.deletions import delete_nodes
    import scoped_fixture
    store=env['store'];rid=env['rid'];actor=env['actor'];sid=env['sid']
    with store.connection() as db:payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])
    bundle=dict(manifest=payload['bundle']['manifest'],files={p:base64.b64decode(b) for p,b in payload['bundle']['files'].items()})
    node=native_record(bundle,payload['request'],env['results'])
    association=dict(store_uuid=native.store_uuid,process_uuid=node.uuid)
    payload['history']['association']=association
    payload['history']['digest']=digest({k:v for k,v in payload['history'].items() if k!='digest'})
    save_record(store,rid,payload,association)
    with store.connection() as db:original=db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]
    frozen=saved2(env);prepared,files=prepared2(env,frozen)
    count_before=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()
    removed=[];native_uuid=node.uuid
    def disappear(actual):
        if actual!=point or removed:return
        scoped_fixture.validate_scope(PROJECTION_SCOPE)
        expected={node.pk,node.outputs.results.pk,node.outputs.retrieved.pk}
        observed,did_delete=delete_nodes([node.pk],dry_run=True,backend=NATIVE_BACKEND)
        assert observed==expected and did_delete is False
        observed,did_delete=delete_nodes([node.pk],dry_run=False,backend=NATIVE_BACKEND)
        assert observed==expected and did_delete is True
        removed.append(native_uuid)
    with wire(monkeypatch,native) as (bridge,calls):
        service=Submissions(store,lambda *args:(prepared,files),bridge);service.fault=disappear
        body=dict(command_id=uid(),configuration_revision_id=frozen['configuration']['configuration_revision_id'])
        run=service.submit(actor,sid,body)
        service.dispatch(run['run_id']);service.dispatch(run['run_id'])
        if point=='before_claim':
            with pytest.raises(DomainError,match='source_result_unavailable'):service.submit(actor,sid,body)
        else:assert service.submit(actor,sid,body)['run_id']==run['run_id']
        state=service.read(actor,sid,run['run_id'])['state']
    assert len(removed)==1
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()==count_before-1
    assert calls.count('launch')==(1 if point=='after_claim' else 0)
    assert calls.count('matches')==(1 if point=='after_claim' else 0)
    assert state==('uncertain' if point=='after_claim' else 'preparation_failed')
    if point=='before_claim':assert store.receipt(actor,sid,'run',body['command_id'])['error']['code']=='source_result_unavailable'
    with store.connection() as db:
        assert db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]==original
        assert db.execute('SELECT count(*) FROM run_associations WHERE command_id=?',(body['command_id'],)).fetchone()[0]==1
    # App history remains exact data even after the native test source disappears.
    assert History(Store(store.path)).read(actor,sid,rid)['results']==env['results']
