"""Durable command fault windows; test doubles never stand in for native proof."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from execution_fixtures import fixture, runtime_fixture, uid
from hyprn_mvp_app.store import Store,DomainError,digest

class Crash(BaseException): pass

class NativeDouble:
    def __init__(self):self.nodes={};self.bundles={};self.launches=0;self.mode=None
    def bundle_runtime(self):return runtime_fixture()
    def require_attestation(self):return True
    def launch(self,bundle,request):
        self.launches+=1
        if self.mode=='before_node':raise Crash('before durable node')
        process=uid();self.nodes[process]=dict(request)
        self.bundles[process]=bundle
        if self.mode in ('after_node','continuation','response'):raise Crash(self.mode)
        return dict(process_uuid=process,store_uuid='new-test-store',process_state='finished',exit_status=0)
    def matches(self,request):
        if self.mode=='lookup_timeout':raise TimeoutError('native lookup unavailable')
        exact=[p for p,r in self.nodes.items() if r==request]
        return exact+[uid()] if self.mode=='multiple' else exact
    def inspect(self,process):return dict(process_uuid=process,store_uuid='new-test-store',process_state='created',exit_status=None)
    def read_record(self,request,association):
        process=association['process_uuid']
        assert association['store_uuid']=='new-test-store' and self.nodes[process]==request
        return dict(self.inspect(process),request=request,bundle=self.bundles[process],results=None,assessment=None,
                    artifacts={},errors=[dict(code='missing_results',partial=True)])

@pytest.fixture
def submission(tmp_path):
    from hyprn_mvp_app.execution import Submissions
    store=Store(tmp_path/'application.sqlite');actor=uid();s=store.create_study(actor,uid(),'Dispatch faults')
    case=fixture();c=case['frozen']['configuration'];c['study_id']=s['study_id'];c['digest']=digest({k:v for k,v in c.items() if k!='digest'})
    from hyprn_mvp_app.execution import executable_digest
    case['prepared']['configuration_digest']=c['digest']
    case['prepared']['executable_content_digest']=executable_digest(case['prepared'])
    case['prepared']['prepared_digest']=digest({k:v for k,v in case['prepared'].items() if k!='prepared_digest'})
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],s['study_id'],json.dumps(case['frozen'])))
    native=NativeDouble()
    def prepare(actor,sid,command,frozen):return case['prepared'],case['files']
    return Submissions(store,prepare,native),store,actor,s['study_id'],c['configuration_revision_id'],native

def accepted(env,command=None):
    service,_,actor,sid,revision,_=env
    return service.submit(actor,sid,dict(command_id=command or uid(),configuration_revision_id=revision))

@pytest.mark.quick
def test_receipt_run_outbox_commit_together_before_claim(submission):
    service,store,actor,sid,_,native=submission;r=accepted(submission)
    assert native.launches==0 and r['state']=='accepted_run'
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM run_associations').fetchone()[0]==1
        assert db.execute('SELECT state FROM outbox WHERE run_id=?',(r['run_id'],)).fetchone()[0]=='accepted_run'
    assert store.receipt(actor,sid,'run',r['command_id'])['result']['run_id']==r['run_id']

@pytest.mark.quick
@pytest.mark.parametrize('window',['before_receipt','after_receipt','before_claim','after_claim','before_node','after_node','continuation','response'])
def test_fault_windows_never_blindly_redispatch(submission,window):
    from hyprn_mvp_app.execution import Submissions
    service,store,actor,sid,revision,native=submission;command=uid()
    def fault(point):
        if point==window:raise Crash(point)
    service.fault=fault;native.mode=window
    try:
        r=accepted(submission,command);service.dispatch(r['run_id'])
    except Crash:pass
    restarted=Submissions(store,service.prepare,native)
    native.mode=None;r=restarted.submit(actor,sid,dict(command_id=command,configuration_revision_id=revision))
    if window in ('before_receipt','after_receipt','before_claim'):
        restarted.dispatch(r['run_id']);assert native.launches==1
    else:
        previous=native.launches;restarted.dispatch(r['run_id']);assert native.launches==previous
        result=restarted.read(actor,sid,r['run_id'])
        assert result['state']==('recorded' if native.nodes else 'uncertain')

@pytest.mark.quick
def test_same_command_concurrency_restart_and_payload_conflict(submission):
    service,store,actor,sid,revision,native=submission;command=uid()
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:accepted(submission,command),range(12)))
    assert len({r['run_id'] for r in results})==1
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:service.dispatch(results[0]['run_id']),range(4)))
    assert native.launches==1
    with pytest.raises(DomainError,match='command_payload_conflict'):
        service.submit(actor,sid,dict(command_id=command,configuration_revision_id=uid()))

@pytest.mark.quick
@pytest.mark.parametrize('lookup',['none','multiple','lookup_timeout'])
def test_unprovable_native_association_stays_uncertain(submission,lookup):
    service,store,actor,sid,_,native=submission;r=accepted(submission)
    native.mode='before_node' if lookup=='none' else 'after_node'
    with pytest.raises(Crash):service.dispatch(r['run_id'])
    native.mode=lookup
    service.dispatch(r['run_id']);service.dispatch(r['run_id'])
    assert service.read(actor,sid,r['run_id'])['state']=='uncertain' and native.launches==1

@pytest.mark.quick
def test_revoked_authorization_checked_before_replay_and_native_access(submission):
    service,store,actor,sid,_,native=submission;r=accepted(submission)
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    with pytest.raises(DomainError):accepted(submission,r['command_id'])
    with pytest.raises(DomainError):service.read(actor,sid,r['run_id'])
    assert native.launches==0

@pytest.mark.quick
def test_model_outage_before_preparation_preserves_visible_pending(submission):
    service,store,actor,sid,_,native=submission;r=accepted(submission)
    def offline(*args):raise DomainError('backend_unavailable',503)
    service.prepare=offline;service.dispatch(r['run_id'])
    assert service.read(actor,sid,r['run_id'])['state']=='accepted_run' and native.launches==0

@pytest.mark.quick
def test_prepared_bundle_is_durable_before_claim_and_survives_model_outage(submission):
    from hyprn_mvp_app.execution import Submissions
    service,store,actor,sid,_,native=submission;r=accepted(submission)
    service.dispatch(r['run_id'],prepare_only=True)
    assert service.read(actor,sid,r['run_id'])['state']=='prepared' and native.launches==0
    def offline(*args):raise AssertionError('Prepared run must never fetch model again')
    restarted=Submissions(Store(store.path),offline,native)
    restarted.dispatch(r['run_id'])
    assert native.launches==1 and restarted.read(actor,sid,r['run_id'])['state']=='recorded'

@pytest.mark.quick
def test_invalid_preparation_is_terminal_before_claim(submission):
    service,_,actor,sid,_,native=submission;r=accepted(submission)
    def invalid(*args):raise ValueError('Inconsistent package bytes')
    service.prepare=invalid;service.dispatch(r['run_id'])
    assert service.read(actor,sid,r['run_id'])['state']=='preparation_failed'
    def forbidden(*args):raise AssertionError('Terminal preparation retried')
    service.prepare=forbidden;service.dispatch(r['run_id'])
    assert native.launches==0


@pytest.mark.quick
def test_dispatcher_drains_authorized_study_after_revoked_queued_actor(submission,monkeypatch):
    from hyprn_mvp_app import dispatcher
    service,store,actor,sid,revision,native=submission
    revoked=accepted(submission)
    other_actor=uid();other=store.create_study(other_actor,uid(),'Authorized queue')['study_id']
    # A distinct valid fixture in the same application store.
    case=fixture();config=case['frozen']['configuration'];config.update(study_id=other,configuration_id=uid(),configuration_revision_id=uid())
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    from hyprn_mvp_app.execution import executable_digest
    prepared=case['prepared'];prepared.update(configuration_digest=config['digest'],configuration_revision_id=config['configuration_revision_id'])
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],other,json.dumps(case['frozen'])))
        db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    authorized=service.submit(other_actor,other,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
    service.prepare=lambda *args:(prepared,case['files'])
    monkeypatch.setattr(dispatcher,'Submissions',lambda *args:service)
    monkeypatch.setattr(dispatcher,'ModelingClient',lambda *args:None)
    key=store.path.with_suffix('.key');key.write_bytes(b'fixture')
    monkeypatch.setenv('HYPRN_MVP_APP_STORE',str(store.path));monkeypatch.setenv('HYPRN_MVP_MODEL_KEY_FILE',str(key));monkeypatch.setenv('HYPRN_MVP_MODEL_URL','http://unused')
    monkeypatch.setattr('sys.argv',['dispatcher','--once'])
    dispatcher.main();dispatcher.main()
    assert native.launches==1 and service.read(other_actor,other,authorized['run_id'])['state']=='recorded'
    with store.connection() as db:
        receipt=store._receipt(db,sid,'run',revoked['command_id'])
        assert receipt['state']=='preparation_failed' and receipt['error']['status']==404
        assert db.execute("SELECT COUNT(*) FROM outbox WHERE state='accepted_run' AND COALESCE(json_extract(payload,'$.preparation_state'),'')!='preparation_failed'").fetchone()[0]==0


@pytest.mark.quick
def test_revoked_claimed_work_only_reconciles_without_resubmission(submission):
    service,store,actor,sid,_,native=submission;run=accepted(submission)
    native.mode='after_node'
    with pytest.raises(Crash):service.dispatch(run['run_id'])
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    native.mode=None
    service.dispatch(run['run_id']);service.dispatch(run['run_id'])
    assert native.launches==1
    with store.connection() as db:assert store._receipt(db,sid,'run',run['command_id'])['state']=='recorded'
