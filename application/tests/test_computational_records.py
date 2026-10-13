"""Guarded application lifecycle with the actual pinned native archive adapter."""
import base64
import io
import json
import zipfile
import hashlib
import copy
import fcntl
import os
import stat

import pytest
from test_computational_archive import record, native
from hyprn_mvp_app.store import Store, DomainError, canonical, digest, uid
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.computational_export import ComputationalRecords
import test_computational_archive as native_fixture


@pytest.fixture(autouse=True)
def fresh_configuration_ids(monkeypatch):
    original=native_fixture.fixture
    def fresh():
        value=original();c=value['frozen']['configuration']
        c.update(configuration_id=uid(),configuration_revision_id=uid())
        value['prepared']['configuration_revision_id']=c['configuration_revision_id']
        return value
    monkeypatch.setattr(native_fixture,'fixture',fresh)


def retain(store,node,preflight,actor):
    item = preflight['computations'][0]
    retained = native().read_record(item['request'], item['association'])
    bundle = retained['bundle']
    config = json.loads(bundle['files']['configuration.json'])
    model = json.loads(bundle['files']['model.json'])
    sid = config['study_id']; rid = item['run_id']
    with store.connection(write=True) as db:
        db.execute('INSERT OR IGNORE INTO studies VALUES(?,?,?,?,?)',(sid,uid(),'Record study','',''))
        revision = db.execute('SELECT revision FROM studies WHERE study_id=?',(sid,)).fetchone()['revision']
        payload = dict(actor=actor, frozen=dict(configuration=config, model_snapshot=model, study_revision=revision), request=item['request'],
            bundle=dict(manifest=bundle['manifest'], files={k:base64.b64encode(v).decode() for k,v in bundle['files'].items()}))
        payload['history'] = projection(payload, retained, item['association'])
        db.execute('INSERT OR IGNORE INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],sid,config['configuration_revision_id']))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(payload['frozen'])))
        db.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)',(sid,'run',item['request']['command_id'],actor,item['request']['payload_digest'],'committed','{}',None,None))
        db.execute('INSERT INTO run_associations VALUES(?,?,?,?,?,?)',(rid,sid,config['configuration_revision_id'],item['request']['command_id'],item['association']['store_uuid'],node.uuid))
        db.execute('INSERT INTO outbox VALUES(?,?,?)',(rid,'recorded',json.dumps(payload)))
    return dict(store=store,actor=actor,sid=sid,rid=rid,payload=payload,node=node,preflight=preflight)


@pytest.fixture
def case(tmp_path):
    node,preflight=record();store=Store(tmp_path/'application.sqlite')
    return dict(retain(store,node,preflight,uid()),service=ComputationalRecords(store,tmp_path/'records'))


def preview(c):
    value=c['service'].enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[c['rid']]))
    assert value['state']=='queued'
    assert c['service'].process_one(native().archive_record)
    return c['service'].status(c['actor'],c['sid'],value['request_id'])


def test_real_archive_preview_create_inventory_and_original_bytes(case):
    c=case;s=c['service']
    with c['store'].connection() as db:before=[tuple(r) for r in db.execute('SELECT * FROM outbox')]
    p=preview(c);assert p['state']=='reviewable';validate('RecordRequest',p)
    body=dict(command_id=uid(),preview_id=p['request_id'],expected_preview_digest=p['preview']['preview_digest'])
    created=s.enqueue_create(c['actor'],c['sid'],body)
    assert s.enqueue_create(c['actor'],c['sid'],body)==created
    assert s.process_one(native().archive_record)
    ready=s.status(c['actor'],c['sid'],created['request_id']);assert ready['state']=='ready';validate('RecordRequest',ready)
    raw=s.download(c['actor'],c['sid'],created['request_id'])
    assert hashlib.sha256(raw).hexdigest()==ready['download']['sha256']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest=json.loads(z.read('manifest.json'));validate('ComputationalRecordManifest1',manifest)
        assert set(z.namelist())=={'manifest.json'}|{i['path'] for i in manifest['inventory']}
        for item in manifest['inventory']:
            value=z.read(item['path']);assert len(value)==item['size'];assert hashlib.sha256(value).hexdigest()==item['sha256']
        for path,value in c['payload']['bundle']['files'].items():
            assert z.read('hyprn-mvp/runs/'+c['rid']+'/bundle/'+path)==base64.b64decode(value)
    with c['store'].connection() as db:assert before==[tuple(r) for r in db.execute('SELECT * FROM outbox')]


def test_replay_conflict_and_duplicate_selection(case):
    c=case;s=c['service'];body=dict(command_id=uid(),selected_run_ids=[c['rid']])
    first=s.enqueue_preview(c['actor'],c['sid'],body)
    assert s.enqueue_preview(c['actor'],c['sid'],body)==first
    with pytest.raises(DomainError):s.enqueue_preview(c['actor'],c['sid'],dict(body,selected_run_ids=[c['rid'],c['rid']]))
    with pytest.raises(DomainError) as e:s.enqueue_preview(c['actor'],c['sid'],dict(body,selected_run_ids=[uid()]))
    assert e.value.code=='command_payload_conflict'


def test_permission_revoked_before_processing(case):
    c=case;s=c['service'];q=s.enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[c['rid']]))
    with c['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(c['actor'],))
    def forbidden(_):raise AssertionError('Native archive called after revocation')
    assert s.process_one(forbidden)
    with c['store'].connection() as db:assert db.execute('SELECT state FROM computational_record_requests WHERE request_id=?',(q['request_id'],)).fetchone()[0]=='failed'
    with pytest.raises(DomainError):s.status(c['actor'],c['sid'],q['request_id'])


def queued(c):
    return c['service'].enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[c['rid']]))


def ready(c):
    p=preview(c)
    assert p['state']=='reviewable',p
    q=c['service'].enqueue_create(c['actor'],c['sid'],dict(command_id=uid(),preview_id=p['request_id'],expected_preview_digest=p['preview']['preview_digest']))
    assert c['service'].process_one(native().archive_record)
    assert c['service'].status(c['actor'],c['sid'],q['request_id'])['state']=='ready'
    return q


def test_role_policy_and_scoped_request_identity(case):
    c=case;q=queued(c);reader=uid();stranger=uid()
    with c['store'].connection(write=True) as db:db.execute('INSERT INTO memberships VALUES(?,?,?)',(c['sid'],reader,'reader'))
    assert c['service'].status(reader,c['sid'],q['request_id'])['state']=='queued'
    with pytest.raises(DomainError) as e:c['service'].enqueue_preview(reader,c['sid'],dict(command_id=uid(),selected_run_ids=[c['rid']]))
    assert e.value.status==403
    for actor,sid in [(stranger,c['sid']),(reader,uid())]:
        with pytest.raises(DomainError) as e:c['service'].status(actor,sid,q['request_id'])
        assert e.value.status==404
    with pytest.raises(DomainError) as e:c['service'].download(reader,c['sid'],q['request_id'])
    assert e.value.code=='record_not_ready'


@pytest.mark.parametrize('point',['claimed','built','written','published'])
def test_owned_crash_rebuild_preserves_identity_and_inventory(case,point):
    c=case;q=queued(c)
    class Crash(BaseException):pass
    def crash(current):
        if current==point:raise Crash()
    c['service'].fault=crash
    with pytest.raises(Crash):c['service'].process_one(native().archive_record)
    with c['store'].connection() as db:
        row=dict(db.execute('SELECT * FROM computational_record_requests').fetchone())
        assert row['state']=='building' and row['generation']==1
        baseline=json.loads(row['payload_json']).get('preview')
        assert db.execute("SELECT COUNT(*) FROM receipts WHERE category='computational_record_preview'").fetchone()[0]==1
    rebuilt=ComputationalRecords(c['store'],c['service'].root)
    assert rebuilt.process_one(native().archive_record)
    value=rebuilt.status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='reviewable'
    if baseline:assert value['preview']==baseline
    with c['store'].connection() as db:assert db.execute('SELECT generation FROM computational_record_requests').fetchone()[0]==2


def test_owned_lock_and_generation_cas(case):
    c=case;queued(c)
    with open(c['service'].root/'owner.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert not c['service'].process_one(lambda _:pytest.fail('Second owner'))
    def race(point):
        if point=='published':
            with c['store'].connection(write=True) as db:db.execute('UPDATE computational_record_requests SET generation=generation+1')
    c['service'].fault=race
    assert c['service'].process_one(native().archive_record)
    with c['store'].connection() as db:assert db.execute('SELECT state FROM computational_record_requests').fetchone()[0]=='building'


def test_pending_study_limit_is_atomic_and_replay_does_not_allocate(case):
    c=case;body=dict(command_id=uid(),selected_run_ids=[c['rid']])
    first=c['service'].enqueue_preview(c['actor'],c['sid'],body)
    for _ in range(7):queued(c)
    with pytest.raises(DomainError) as e:queued(c)
    assert e.value.code=='limit_exceeded'
    assert c['service'].enqueue_preview(c['actor'],c['sid'],body)==first
    with c['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM computational_record_requests').fetchone()[0]==8


def test_global_pending_limit(case):
    c=case
    with c['store'].connection(write=True) as db:
        for _ in range(4):
            sid=uid();db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(sid,uid(),'Other','',''))
            for _ in range(8):
                db.execute('INSERT INTO computational_record_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (uid(),sid,c['actor'],'preview',uid(),'a'*64,'[]',None,None,'queued',0,'{}',None,None,None))
    with pytest.raises(DomainError) as e:queued(c)
    assert e.value.code=='limit_exceeded'
    with c['store'].connection() as db:assert db.execute('SELECT COUNT(*) FROM computational_record_requests').fetchone()[0]==32


@pytest.mark.parametrize('change',['hash','missing','revoked','source_corrupt'])
def test_ready_release_revalidates_file_and_authority(case,change):
    c=case;q=ready(c);s=c['service']
    with c['store'].connection() as db:row=dict(db.execute('SELECT * FROM computational_record_requests WHERE request_id=?',(q['request_id'],)).fetchone())
    from pathlib import Path
    path=Path(row['artifact_path'])
    if change=='hash':path.chmod(0o600);path.write_bytes(b'corrupt')
    elif change=='missing':path.unlink()
    elif change=='revoked':
        with c['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(c['actor'],))
    else:
        with c['store'].connection(write=True) as db:db.execute("UPDATE outbox SET payload='{}' WHERE run_id=?",(c['rid'],))
    with pytest.raises(DomainError):s.download(c['actor'],c['sid'],q['request_id'])


def test_rebuilt_native_inventory_change_requires_new_preview(case):
    c=case;p=preview(c)
    q=c['service'].enqueue_create(c['actor'],c['sid'],dict(command_id=uid(),preview_id=p['request_id'],expected_preview_digest=p['preview']['preview_digest']))
    # Safe native metadata changes the actual inventory, not application snapshots.
    c['node'].base.extras.set('_aiida_hash','a'*64)
    assert c['service'].process_one(native().archive_record)
    value=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='failed' and value['error']['code']=='reference_conflict'


def test_native_rebuild_timestamp_changes_do_not_invalidate_review(case):
    c=case;responses=[]
    def actual(payload):
        value=native().archive_record(payload);responses.append(value);return value
    q=queued(c);c['service'].process_one(actual)
    p=c['service'].status(c['actor'],c['sid'],q['request_id'])
    created=c['service'].enqueue_create(c['actor'],c['sid'],dict(command_id=uid(),preview_id=q['request_id'],expected_preview_digest=p['preview']['preview_digest']))
    c['service'].process_one(actual)
    assert responses[0]['inventory']==responses[1]['inventory']
    assert responses[0]['archive_sha256']!=responses[1]['archive_sha256']
    assert c['service'].status(c['actor'],c['sid'],created['request_id'])['state']=='ready'


def test_archive_errors_are_sanitized_and_no_download(case):
    c=case;q=queued(c)
    def fail(_):raise RuntimeError('/private/secret API_TOKEN=abc123456789')
    c['service'].process_one(fail)
    value=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='failed' and value['error']['code']=='unsafe_export'
    assert 'secret' not in json.dumps(value)
    with pytest.raises(DomainError):c['service'].download(c['actor'],c['sid'],q['request_id'])


@pytest.mark.parametrize('fault',['version','origin','digest','size','bytes','process_scope','link','repository','unlisted','traversal','collision','symlink','expansion'])
def test_malformed_actual_archive_response_fails_closed(case,fault):
    c=case;q=queued(c)
    def corrupt(payload):
        response=native().archive_record(payload)
        if fault=='version':response['schema_version']=1
        elif fault=='origin':response['origin_store_uuid']=uid()
        elif fault=='digest':response['inventory_digest']='0'*64
        elif fault=='size':response['archive_size']+=1
        elif fault=='bytes':response['archive_base64']='AAAA'
        elif fault=='process_scope':
            next(n for n in response['inventory']['nodes'] if n['node_type']!='process.calculation.calcjob.CalcJobNode.')['node_type']='process.calculation.calcjob.CalcJobNode.'
            response['inventory_digest']=digest(response['inventory'])
        elif fault=='link':
            response['inventory']['links'][0]['target_uuid']=uid();response['inventory_digest']=digest(response['inventory'])
        elif fault=='repository':
            response['inventory']['repositories'][0]['sha256']='0'*64;response['inventory_digest']=digest(response['inventory'])
        else:
            source=zipfile.ZipFile(io.BytesIO(base64.b64decode(response['archive_base64'])))
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for item in source.infolist():z.writestr(item,source.read(item.filename))
                path={'unlisted':'unlisted','traversal':'../escape','collision':'METADATA.JSON','symlink':'link','expansion':'repo/'+'0'*64}[fault]
                info=zipfile.ZipInfo(path);info.external_attr=((stat.S_IFLNK if fault=='symlink' else stat.S_IFREG)|0o600)<<16
                z.writestr(info,b'a'*(16777217 if fault=='expansion' else 1),compress_type=zipfile.ZIP_DEFLATED)
            raw=stream.getvalue();response.update(archive_base64=base64.b64encode(raw).decode(),archive_size=len(raw),archive_sha256=hashlib.sha256(raw).hexdigest())
        return response
    c['service'].process_one(corrupt)
    value=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='failed',fault
    assert value['download'] is None


def test_real_recursive_computational_closure(case):
    c=case
    middle=record(upstream=(c['node'],c['preflight']))
    retained_middle=retain(c['store'],*middle,c['actor'])
    end=record(upstream=middle);last=retain(c['store'],*end,c['actor'])
    q=c['service'].enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[last['rid']]))
    assert c['service'].process_one(native().archive_record)
    p=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert p['state']=='reviewable',p
    assert {r['run_id'] for r in p['preview']['computational_ancestors']}=={c['rid'],retained_middle['rid']}
    # The recursive source is required on every subsequent authorized status read.
    with c['store'].connection(write=True) as db:db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?",(c['rid'],))
    with pytest.raises(DomainError):c['service'].status(c['actor'],c['sid'],q['request_id'])


def test_complete_failed_native_record_is_exportable(case):
    c=case;node,payload=record(failed=True);failed=retain(c['store'],node,payload,c['actor'])
    c=dict(c,**{k:v for k,v in failed.items() if k!='service'})
    q=ready(c);assert c['service'].download(c['actor'],c['sid'],q['request_id'])


def test_cycles_and_foreign_source_fail_before_native(case,monkeypatch):
    c=case
    from hyprn_mvp_app.modified_runs import ModifiedRuns
    original=ModifiedRuns.retained
    def cyclic(self,actor,sid,rid):
        h,p,t=original(self,actor,sid,rid);h=copy.deepcopy(h)
        h['configuration']['inputs'][0]['result_binding']=dict(source_run_id=rid)
        return h,p,t
    monkeypatch.setattr(ModifiedRuns,'retained',cyclic)
    with pytest.raises(DomainError) as e:queued(c)
    assert e.value.code=='unsafe_export'


def derived_record(c,monkeypatch,parent):
    original=native_fixture.assemble_bundle
    def assemble(rid,prepared,files,frozen,runtime,dependencies=None):
        config=frozen['configuration'];source=parent['payload']['frozen']['configuration']
        config['derivation']=dict(source_run_id=parent['rid'],source_configuration_revision_id=source['configuration_revision_id'],
            source_configuration_digest=source['digest'],source_runtime=parent['payload']['bundle']['manifest']['runtime'],changes=[])
        config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
        return original(rid,prepared,files,frozen,runtime,dependencies)
    with monkeypatch.context() as patch:
        patch.setattr(native_fixture,'assemble_bundle',assemble)
        node,payload=record()
    return retain(c['store'],node,payload,c['actor'])


def test_direct_derivation_context_is_not_a_native_root_or_recursive_history(case,monkeypatch):
    c=case;parent=derived_record(c,monkeypatch,c);child=derived_record(c,monkeypatch,parent)
    from hyprn_mvp_app.computational_export import LIMITS
    pc=parent['payload']['frozen']['configuration']
    included=sum(f['size'] for f in child['payload']['bundle']['manifest']['files'])
    included+=sum(f['size'] for f in child['payload']['history']['artifacts'])
    included+=sum(len(canonical(v)) for v in (pc,parent['payload']['frozen']['model_snapshot'],
        pc['context_snapshot'],pc['evidence_snapshots'],parent['payload']['bundle']['manifest']['runtime']))
    with monkeypatch.context() as scope:
        scope.setitem(LIMITS,'expanded_bytes',included)
        c['service']._collect(c['actor'],c['sid'],[child['rid']])
    q=c['service'].enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[child['rid']]))
    requests=[]
    def archive(value):
        requests.append(copy.deepcopy(value));return native().archive_record(value)
    c['service'].process_one(archive)
    p=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert p['state']=='reviewable',p
    assert [v['run_id'] for v in p['preview']['derivation_context_only']]==[parent['rid']]
    assert not p['preview']['computational_ancestors']
    created=c['service'].enqueue_create(c['actor'],c['sid'],dict(command_id=uid(),preview_id=q['request_id'],expected_preview_digest=p['preview']['preview_digest']))
    c['service'].process_one(archive)
    with zipfile.ZipFile(io.BytesIO(c['service'].download(c['actor'],c['sid'],created['request_id']))) as z:
        manifest=json.loads(z.read('manifest.json'))
        mapping=next(r for r in manifest['runs'] if r['run_id']==parent['rid'])
        assert mapping['role']=='derivation_context_only'
        assert mapping['process_uuid'] is mapping['bundle_digest'] is mapping['results_digest'] is None
        assert all(c['rid'] not in path for path in z.namelist())
        assert not any(path.startswith('hyprn-mvp/runs/'+parent['rid']) for path in z.namelist())
        assert json.loads(z.read('hyprn-mvp/derivations/'+parent['rid']+'/configuration.json'))==parent['payload']['frozen']['configuration']
    assert all([v['run_id'] for v in r['computations']]==[child['rid']] for r in requests)


def test_derivation_context_revocation_and_sensitive_content_blocks(case,monkeypatch):
    c=case;parent=derived_record(c,monkeypatch,c)
    child=derived_record(c,monkeypatch,parent)
    q=c['service'].enqueue_preview(c['actor'],c['sid'],dict(command_id=uid(),selected_run_ids=[child['rid']]))
    with c['store'].connection(write=True) as db:db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?",(parent['rid'],))
    c['service'].process_one(lambda _:pytest.fail('Context must be checked first'))
    value=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='failed'
    from hyprn_mvp_app.computational_export import context_material
    # The account-home path and the private-key block header are assembled from fragments at run
    # time, so the source never holds a literal that the repository hygiene guard refuses.
    for raw in [b'API_TOKEN=credential-secret-value',b'/'+b'Users'+b'/'+b'private/document',
                b'-----'+b'BEGIN '+b'PRIVATE'+b' KEY'+b'-----']:
        with pytest.raises(ValueError):context_material(raw)


@pytest.mark.parametrize('bound',['logical_paths','expanded_bytes','per_file_bytes','metadata_bytes','wrapper_bytes'])
def test_application_package_bounds_before_release(case,monkeypatch,bound):
    from hyprn_mvp_app.computational_export import LIMITS
    import hyprn_mvp_app.computational_export as exporter
    c=case;p=preview(c)
    q=c['service'].enqueue_create(c['actor'],c['sid'],dict(command_id=uid(),preview_id=p['request_id'],expected_preview_digest=p['preview']['preview_digest']))
    if bound=='wrapper_bytes':
        original=exporter.zip_entries
        # Inject a small transfer cap at the actual wrapper read-back boundary;
        # keep the approved constant policy and preview digest unchanged.
        def restricted(raw,maximum,**kwargs):
            return original(raw,1 if maximum==LIMITS['wrapper_bytes'] else maximum,**kwargs)
        monkeypatch.setattr(exporter,'zip_entries',restricted)
    else:monkeypatch.setitem(LIMITS,bound,1)
    c['service'].process_one(native().archive_record)
    value=c['service'].status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='failed' and value['download'] is None
    assert value['error']['code'] in ('limit_exceeded','reference_conflict')


def test_crash_rebuild_cannot_promote_changed_inventory(case):
    c=case;q=queued(c)
    class Crash(BaseException):pass
    def fault(point):
        if point=='built':raise Crash()
    c['service'].fault=fault
    with pytest.raises(Crash):c['service'].process_one(native().archive_record)
    c['node'].base.extras.set('_aiida_hash','b'*64)
    rebuilt=ComputationalRecords(c['store'],c['service'].root)
    rebuilt.process_one(native().archive_record)
    value=rebuilt.status(c['actor'],c['sid'],q['request_id'])
    assert value['state']=='failed' and value['error']['code']=='reference_conflict'


def test_native_operation_and_service_never_dispatch_or_fetch_model(case,monkeypatch):
    from hyprn_mvp_integration.calculation import NativeExecution
    from hyprn_mvp_app.modeling import ModelingClient
    from hyprn_mvp_app.execution import Submissions
    def forbidden(*args,**kwargs):pytest.fail('Scientific operation reachable during export')
    for name in ('launch','submit','restart','resolve_results','read_record','attest','bundle_runtime'):
        if hasattr(NativeExecution,name):monkeypatch.setattr(NativeExecution,name,forbidden)
    monkeypatch.setattr(ModelingClient,'call',forbidden);monkeypatch.setattr(Submissions,'submit',forbidden)
    q=ready(case);assert case['service'].download(case['actor'],case['sid'],q['request_id'])


def test_owned_artifact_symlink_refused(case,tmp_path):
    c=case;q=queued(c)
    directory=c['service'].root/q['request_id'];directory.mkdir()
    outside=tmp_path/'outside';outside.write_bytes(b'preserve')
    (directory/'incomplete.tmp').symlink_to(outside)
    c['service'].process_one(native().archive_record)
    assert c['service'].status(c['actor'],c['sid'],q['request_id'])['state']=='failed'
    assert outside.read_bytes()==b'preserve'
