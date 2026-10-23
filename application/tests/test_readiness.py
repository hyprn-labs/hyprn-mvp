"""Sanitized observations are advisory; authoritative dispatch remains separate."""
import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from hyprn_mvp_app.store import Store, DomainError, uid
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.api import create_app
from execution_fixtures import runtime_fixture

ORIGIN = 'http://127.0.0.1:19999'

class CapabilitiesDouble:
    """No network transport, private credentials or deployed fixture defaults."""
    def __init__(self): self.calls=[]; self.fail_before=False
    def call(self, actor, sid, method, path, **kwargs):
        self.calls.append((method, '/modeling/1'+path))
        assert (method,path)==('GET','/capabilities')
        if self.fail_before: raise DomainError('backend_unavailable',503)
        return 200,dict(data=dict(capabilities=[dict(id='flat_explicit_scalar',supported=True)]))

@pytest.fixture
def api(tmp_path):
    store=Store(tmp_path/'readiness.sqlite');auth=Auth(store,ORIGIN)
    actor=auth.provision('owner','correct horse battery staple')
    model=CapabilitiesDouble();client=TestClient(create_app(store,auth,model),base_url=ORIGIN)
    session=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    assert session.status_code==200
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':session.json()['data']['csrf_token']})
    return client,store,auth,model,model,actor

def study(api):
    response=api[0].post('/api/1/studies',json=dict(command_id=uid(),name='Isolated readiness'))
    assert response.status_code==201
    return response.json()['data']

class Native:
    def __init__(self): self.calls=0; self.error=None
    def require_attestation(self):
        self.calls+=1
        if self.error: raise self.error
        return True
    def bundle_runtime(self): return runtime_fixture()

def data(api):
    sid=study(api)['study_id']
    r=api[0].get(f'/api/1/studies/{sid}/execution-readiness')
    assert r.status_code==200,r.text
    return sid,r.json()['data']

def test_stopped_executor_unknown_support_unchanged_and_real_private_scope(api):
    sid,value=data(api)
    assert value==dict(readiness_schema_version='1',capability='flat_explicit_scalar',status='unknown',
                      reasons=['observation_stale'],observed_at=None,expires_at=None)
    assert api[4].calls==[('GET','/modeling/1/capabilities')]
    assert 'flat_explicit_scalar' in api[0].get('/api/1/capabilities').json()['data']['engineering']

def test_public_auth_cross_study_and_no_forged_observation(api):
    c,store,auth,model,transport,actor=api; sid=study(api)['study_id']; path=f'/api/1/studies/{sid}/execution-readiness'
    assert TestClient(c.app,base_url=ORIGIN).get(path,headers={'X-Actor-ID':actor}).status_code==401
    foreign=store.create_study(uid(),uid(),'foreign')['study_id']
    assert c.get(f'/api/1/studies/{foreign}/execution-readiness').status_code==404
    assert not transport.calls
    assert c.post(path,json={'status':'ready','observed_at':time.time()}).status_code==405
    assert c.get(path+'?status=ready').status_code==400
    assert store.execution_observation() is None

def test_trusted_observation_throttle_expiry_stop_and_restart(api,monkeypatch):
    from hyprn_mvp_app.readiness import ObservationPublisher
    import hyprn_mvp_app.readiness as readiness
    now=[1000.0]; monkeypatch.setattr(readiness,'wall_time',lambda:now[0]); native=Native()
    publisher=ObservationPublisher(api[1],native,monotonic=lambda:now[0])
    assert publisher.refresh(); assert native.calls==1
    now[0]=1009; assert not publisher.refresh(); assert native.calls==1
    now[0]=1010; assert publisher.refresh(); assert native.calls==2
    sid,value=data(api); assert value['status']=='ready' and value['reasons']==[]
    assert value['observed_at']=='1970-01-01T00:16:50Z' and value['expires_at']=='1970-01-01T00:17:20Z'
    now[0]=1040; value=api[0].get(f'/api/1/studies/{sid}/execution-readiness').json()['data']
    assert value['status']=='unknown' and value['reasons']==['observation_stale']
    publisher.stopped(); row=Store(api[1].path).execution_observation()
    assert row['reason']=='executor_unavailable'
    value=api[0].get(f'/api/1/studies/{sid}/execution-readiness').json()['data']
    assert value['status']=='unavailable' and value['reasons']==['executor_unavailable']

@pytest.mark.parametrize('error,reason',[(RuntimeError('/private/secret token password'),'attestation_invalid'),(OSError('container-id socket-secret'),'executor_unavailable')])
def test_invalid_attestation_never_leaks_and_never_launches(api,error,reason):
    from hyprn_mvp_app.readiness import ObservationPublisher
    native=Native();native.error=error;publisher=ObservationPublisher(api[1],native);publisher.refresh()
    _,value=data(api); assert value['status']=='unavailable' and value['reasons']==[reason]
    assert set(value)=={'readiness_schema_version','capability','status','reasons','observed_at','expires_at'}
    assert not any(x in json.dumps(value) for x in ('private','secret','password','socket','container'))

def test_model_outage_and_unsupported_are_sanitized(api,monkeypatch):
    from hyprn_mvp_app.readiness import ObservationPublisher
    ObservationPublisher(api[1],Native()).refresh();sid=study(api)['study_id'];path=f'/api/1/studies/{sid}/execution-readiness'
    original=api[3].call; calls=[]
    def capture(actor,study_id,method,route,**kwargs):
        calls.append((actor,study_id,method,route,kwargs)); status,body=original(actor,study_id,method,route,**kwargs)
        for cap in body['data']['capabilities']:
            if cap['id']=='flat_explicit_scalar':cap['supported']=False
        return status,body
    monkeypatch.setattr(api[3],'call',capture)
    value=api[0].get(path).json()['data'];assert value['status']=='unavailable' and value['reasons']==['capability_unsupported']
    assert calls[0][:4]==(api[5],sid,'GET','/capabilities') and calls[0][4]['resources']==[sid]
    monkeypatch.setattr(api[3],'call',original);api[4].fail_before=True
    value=api[0].get(path).json()['data'];assert value['status']=='unavailable' and value['reasons']==['modeling_unavailable']
    assert api[0].get(f'/api/1/studies/{sid}/runs').status_code==200

def test_model_wait_cannot_extend_expired_attestation(api,monkeypatch):
    from hyprn_mvp_app.readiness import ObservationPublisher
    import hyprn_mvp_app.readiness as readiness
    clock=[1000.];monkeypatch.setattr(readiness,'wall_time',lambda:clock[0]);ObservationPublisher(api[1],Native()).refresh()
    original=api[3].call
    def delayed(*a,**kw):
        result=original(*a,**kw);clock[0]=1031.;return result
    monkeypatch.setattr(api[3],'call',delayed);_,value=data(api)
    assert value['status']=='unknown' and value['reasons']==['observation_stale']
    monkeypatch.setattr(api[3],'call',original);clock[0]=1000.
    stored=api[1].execution_observation
    def delayed_storage():
        row=stored();clock[0]=1031.;return row
    monkeypatch.setattr(api[1],'execution_observation',delayed_storage)
    _,value=data(api);assert value['status']=='unknown' and value['reasons']==['observation_stale']

def test_missing_or_malformed_observation_cannot_be_ready(api,monkeypatch):
    from hyprn_mvp_app.readiness import ObservationPublisher
    publisher=ObservationPublisher(api[1],Native());publisher.refresh()
    monkeypatch.setattr(api[1],'execution_observation',lambda:{'status':'ready','reason':None,'observed_at':float('nan'),'expires_at':float('inf')})
    _,value=data(api);assert value['status']=='unknown' and value['observed_at'] is None
    monkeypatch.setattr(api[1],'execution_observation',lambda:{'status':'ready','reason':None,'observed_at':time.time()+60,'expires_at':time.time()+90})
    _,value=data(api);assert value['status']=='unknown'

def test_dispatcher_publishes_on_idle_and_stops_without_launch(tmp_path,monkeypatch):
    from hyprn_mvp_app import dispatcher
    from hyprn_mvp_app.readiness import ObservationPublisher
    store=Store(tmp_path/'dispatcher.sqlite');native=Native();states=[];ticks=[0]
    monkeypatch.setenv('HYPRN_MVP_APP_STORE',str(store.path)); key=tmp_path/'key';key.write_bytes(b'synthetic-key')
    monkeypatch.setenv('HYPRN_MVP_MODEL_KEY_FILE',str(key));monkeypatch.setenv('HYPRN_MVP_MODEL_URL','http://unused')
    native.concurrent = False
    monkeypatch.setattr(dispatcher, 'NativeBridge', lambda **kwargs: native)
    monkeypatch.setattr(dispatcher, 'ModelingClient', lambda *a: None)
    monkeypatch.setattr(dispatcher,'ObservationPublisher',lambda s,n:ObservationPublisher(s,n,monotonic=lambda:ticks[0]))
    def idle(*args):
        states.append(store.execution_observation());ticks[0]+=10
        return ([1] if len(states)==3 else [],[],[])
    monkeypatch.setattr(dispatcher.select,'select',idle);monkeypatch.setattr('sys.argv',['dispatcher'])
    dispatcher.main();assert native.calls==3 and all(row['status']=='ready' for row in states)
    assert store.execution_observation()['reason']=='executor_unavailable'

def test_readiness_does_not_replace_authoritative_dispatch(submission):
    from hyprn_mvp_app.readiness import ObservationPublisher
    from test_submission import accepted
    service,store,actor,sid,revision,native=submission
    ObservationPublisher(store,Native()).refresh();run=accepted(submission)
    def failed():raise RuntimeError('fresh authoritative failure')
    native.require_attestation=failed
    with pytest.raises(RuntimeError,match='authoritative'):service.dispatch(run['run_id'])
    assert native.launches==0 and service.read(actor,sid,run['run_id'])['state']=='accepted_run'

from test_submission import submission

def test_retained_run_and_raw_artifact_survive_unknown_model_outage(submission):
    from test_history import recording
    service,store,actor,sid,_,native=submission
    run=recording(submission)
    auth=Auth(Store(store.path),ORIGIN)
    provisioned=auth.provision('history-owner','correct horse battery staple')
    with store.connection(write=True) as db: db.execute('UPDATE memberships SET actor_id=? WHERE actor_id=?',(provisioned,actor))
    actor=provisioned
    c=TestClient(create_app(store,auth,CapabilitiesDouble()),base_url=ORIGIN)
    session=c.post('/api/1/session',json=dict(username='history-owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    c.headers.update({'Origin':ORIGIN,'X-CSRF-Token':session.json()['data']['csrf_token']})
    def offline(*args,**kwargs):raise OSError('private endpoint secret unavailable')
    c.app.state.model.call=offline
    path=f'/api/1/studies/{sid}/runs/{run["run_id"]}'
    before=c.get(path).json()['data']; launches=native.launches
    readiness=c.get(f'/api/1/studies/{sid}/execution-readiness').json()['data']
    assert readiness['status']=='unknown' and readiness['reasons']==['observation_stale','modeling_unavailable']
    assert c.get(path).json()['data']==before
    raw=next(a for a in before['history']['artifacts'] if a['name']=='result.json')
    assert c.get(path+'/artifacts/'+raw['artifact_id']).content==b'raw retained failure\n'
    assert native.launches==launches

def test_revoked_during_private_read_is_not_returned(api,monkeypatch):
    c,store,_,model,_,actor=api;sid=study(api)['study_id'];original=model.call
    def revoked(*args,**kwargs):
        result=original(*args,**kwargs)
        with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?',(actor,sid))
        return result
    monkeypatch.setattr(model,'call',revoked)
    assert c.get(f'/api/1/studies/{sid}/execution-readiness').status_code==404


# --- The executor survives SQLite lock contention -------------------------------------------
# The live store is one rollback-journal SQLite file shared by the API process and the
# executor's dispatcher child. A commit needs every other connection's SHARED lock to clear
# within the 15 s busy timeout. On 2026-10-11 two dispatch commits failed with "database is
# locked", the fallback unavailable observation hit the same lock, and the service exited.
# These tests shrink the busy timeout and hold a real SHARED lock from another connection.
import sqlite3
import threading
import hyprn_mvp_app.store as store_module

class SharedLockHolder:
    """Another connection paused inside a multi-row read keeps SQLite's SHARED lock."""
    def __init__(self, path, connect):
        self.db = connect(str(path), timeout=0.2, isolation_level=None, check_same_thread=False)
        self.cursor = self.db.execute('SELECT name FROM sqlite_master')
        assert self.cursor.fetchone() is not None  # more rows remain: the statement stays active
        self.released = False
    def release(self):
        if not self.released:
            self.cursor.close(); self.db.close(); self.released = True

@pytest.fixture
def short_busy(monkeypatch):
    """Every new store connection waits 0.2 s (live: 15 s) before reporting a lock error."""
    real = sqlite3.connect
    def connect(*args, **kwargs):
        kwargs['timeout'] = 0.2
        return real(*args, **kwargs)
    monkeypatch.setattr(store_module.sqlite3, 'connect', connect)
    return real

def dispatcher_for(monkeypatch, tmp_path, store, service, native, argv=('dispatcher',)):
    from hyprn_mvp_app import dispatcher
    monkeypatch.setenv('HYPRN_MVP_APP_STORE', str(store.path)); key = tmp_path/'key'; key.write_bytes(b'synthetic-key')
    monkeypatch.setenv('HYPRN_MVP_MODEL_KEY_FILE', str(key)); monkeypatch.setenv('HYPRN_MVP_MODEL_URL', 'http://unused')
    native.concurrent = False
    monkeypatch.setattr(dispatcher, 'NativeBridge', lambda **kwargs: native)
    monkeypatch.setattr(dispatcher, 'ModelingClient', lambda *a: None)
    monkeypatch.setattr(dispatcher, 'Submissions', lambda *a: service)
    monkeypatch.setattr('sys.argv', list(argv))
    return dispatcher

@pytest.mark.parametrize('window', ['prepared_commit', 'claim_commit'])
def test_dispatch_commit_lock_backs_off_without_exit_or_double_launch(submission, short_busy, monkeypatch, tmp_path, capsys, window):
    """Crash 21:07Z (execution.py prepared commit) and 21:37Z (claim commit), reproduced."""
    from test_submission import accepted
    service, store, actor, sid, revision, native = submission
    run = accepted(submission)['run_id']; holder = []; waits = []
    def contend():
        if not holder: holder.append(SharedLockHolder(store.path, short_busy))
    if window == 'prepared_commit':
        prepare = service.prepare
        def contended_prepare(*args):
            result = prepare(*args); contend(); return result
        service.prepare = contended_prepare
    else:
        service.fault = lambda point: contend() if point == 'before_claim' else None
    def select(read, write, error, timeout):
        # The first wait follows the failed commit: no claim crossed, nothing launched yet.
        waits.append(dict(timeout=timeout, launches=native.launches, state=service.read(actor, sid, run)['state']))
        if holder: holder[0].release()
        return ([1] if service.read(actor, sid, run)['state'] == 'recorded' else [], [], [])
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native)
    monkeypatch.setattr(dispatcher.select, 'select', select)
    dispatcher.main()  # Must not raise sqlite3.OperationalError 'database is locked' and exit the service.
    assert holder and holder[0].released
    assert waits[0]['launches'] == 0 and 0 < waits[0]['timeout'] <= 30
    assert waits[0]['state'] == ('accepted_run' if window == 'prepared_commit' else 'prepared')  # the failed commit rolled back
    assert native.launches == 1 and service.read(actor, sid, run)['state'] == 'recorded'
    assert store.execution_observation()['reason'] == 'executor_unavailable'
    assert 'database is locked' in capsys.readouterr().err

def test_one_shot_dispatch_lock_retries_are_bounded(submission, short_busy, monkeypatch, tmp_path):
    from test_submission import accepted
    service, store, actor, sid, revision, native = submission
    run = accepted(submission)['run_id']; holder = SharedLockHolder(store.path, short_busy); waits = []
    def select(read, write, error, timeout):
        waits.append(timeout); return ([], [], [])
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native, ('dispatcher', '--run-id', run))
    monkeypatch.setattr(dispatcher.select, 'select', select)
    monkeypatch.setattr(dispatcher.ObservationPublisher, 'stopped', lambda self: True)
    try:
        with pytest.raises(sqlite3.OperationalError, match='database is locked'):
            dispatcher.main()
    finally:
        holder.release()
    assert len(waits) == dispatcher.ONE_SHOT_LOCK_ATTEMPTS - 1 and waits == sorted(waits) and max(waits) <= 30
    assert native.launches == 0 and service.read(actor, sid, run)['state'] == 'accepted_run'

def test_unavailable_observation_survives_a_transient_lock(tmp_path, short_busy):
    from hyprn_mvp_app.readiness import ObservationPublisher
    store = Store(tmp_path/'observation.sqlite'); publisher = ObservationPublisher(store, Native())
    assert publisher.refresh() and store.execution_observation()['status'] == 'ready'
    holder = SharedLockHolder(store.path, short_busy)
    timer = threading.Timer(0.5, holder.release); timer.start()
    try:
        assert publisher.stopped() is True  # Readiness must not stay 'ready' until stale after an OperationalError.
    finally:
        timer.cancel(); holder.release()
    assert store.execution_observation()['reason'] == 'executor_unavailable'

def test_unavailable_observation_retry_is_bounded_and_never_masks_the_exit(tmp_path, short_busy):
    from hyprn_mvp_app.readiness import ObservationPublisher
    store = Store(tmp_path/'observation.sqlite'); publisher = ObservationPublisher(store, Native())
    publisher.refresh(); holder = SharedLockHolder(store.path, short_busy); started = time.monotonic()
    try:
        assert publisher.stopped() is False
    finally:
        holder.release()
    assert time.monotonic() - started < 10
    assert store.execution_observation()['status'] == 'ready'  # the 30 s lifetime still expires it

def test_refresh_lock_error_retries_on_the_next_iteration(tmp_path, short_busy):
    from hyprn_mvp_app.readiness import ObservationPublisher
    store = Store(tmp_path/'observation.sqlite'); native = Native(); tick = [0.0]
    publisher = ObservationPublisher(store, native, monotonic=lambda: tick[0])
    holder = SharedLockHolder(store.path, short_busy)
    try:
        with pytest.raises(sqlite3.OperationalError, match='database is locked'):
            publisher.refresh()
    finally:
        holder.release()
    tick[0] = 1.0  # well inside the 10 s publication throttle
    assert publisher.refresh() is True and store.execution_observation()['status'] == 'ready'

def test_run_history_projection_holds_no_store_lock(submission, short_busy, monkeypatch):
    """Root cause: History.list validated each frozen configuration while its read statement
    was still open, so the API process held SHARED for the whole projection."""
    import hyprn_mvp_app.history as history
    from test_submission import accepted
    service, store, actor, sid, revision, native = submission
    second = uid()
    with store.connection(write=True) as db:
        payload = db.execute('SELECT payload FROM configurations WHERE configuration_revision_id=?', (revision,)).fetchone()[0]
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (second, uid(), sid, payload))
    accepted(submission); service.submit(actor, sid, dict(command_id=uid(), configuration_revision_id=second))
    expected = history.History(store).list(actor, sid)
    assert [r['configuration_revision_id'] for r in expected] == [revision, second]
    entered, proceed = threading.Event(), threading.Event()
    original = history.configuration_name_projection

    def slow(raw, study, revision_id, **options):
        entered.set()
        assert proceed.wait(10)
        return original(raw, study, revision_id, **options)

    monkeypatch.setattr(history, 'configuration_name_projection', slow)
    listed = []; worker = threading.Thread(target=lambda: listed.append(history.History(store).list(actor, sid)))
    worker.start()
    try:
        assert entered.wait(10)
        # The executor's write commits while the API is still projecting.
        store.publish_execution_observation('unavailable', 'executor_unavailable', time.time())
    finally:
        proceed.set(); worker.join(10)
    assert listed == [expected]
    assert store.execution_observation()['reason'] == 'executor_unavailable'

def test_executor_start_waits_out_a_locked_store(submission, short_busy, monkeypatch, tmp_path):
    """Opening the store commits the additive migration's (empty) write transaction, which in
    rollback-journal mode also waits for every reader: start must back off, not exit."""
    service, store, actor, sid, revision, native = submission
    holder = SharedLockHolder(store.path, short_busy); waits = []
    def select(read, write, error, timeout):
        waits.append(timeout); holder.release()
        return ([1] if len(waits) > 1 else [], [], [])
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native)
    monkeypatch.setattr(dispatcher.select, 'select', select)
    try:
        dispatcher.main()
    finally:
        holder.release()
    assert waits == [dispatcher.LOCK_BACKOFF_INITIAL, 1]  # one backoff at start, then the normal idle wait
    assert store.execution_observation()['reason'] == 'executor_unavailable' and native.launches == 0

# --- Dispatcher and readiness hardening: bounded backoff, lock conflicts and stalls ---------------

def lock_error(code, message='database is locked'):
    error = sqlite3.OperationalError(message)
    error.sqlite_errorcode = code
    return error

def test_lock_backoff_exponent_is_capped():
    """The backoff 0.5*2**(attempt-1) must never overflow float conversion at attempt >= 1025 (~13 h)."""
    from hyprn_mvp_app import dispatcher
    for attempt in (1, 2, 7, 1024, 1025, 10**6):
        assert 0 < dispatcher.lock_backoff(attempt) <= dispatcher.LOCK_BACKOFF_MAX
    assert dispatcher.lock_backoff(1) == dispatcher.LOCK_BACKOFF_INITIAL
    assert dispatcher.lock_backoff(1025) == dispatcher.LOCK_BACKOFF_MAX

def test_only_sqlite_busy_is_transient_never_sqlite_locked():
    """SQLITE_LOCKED (base 6) is a same-connection/shared-cache conflict that retrying
    cannot clear; only SQLITE_BUSY (base 5, incl. extended codes) is waited out."""
    from hyprn_mvp_app.readiness import transient_lock_error
    assert transient_lock_error(lock_error(5)) and transient_lock_error(lock_error(5 | 1 << 8))
    assert not transient_lock_error(lock_error(6, 'database table is locked'))
    assert not transient_lock_error(lock_error(6 | 1 << 8, 'database table is locked'))
    assert transient_lock_error(sqlite3.OperationalError('database is locked'))
    assert not transient_lock_error(sqlite3.OperationalError('database table is locked'))
    assert not transient_lock_error(sqlite3.OperationalError('no such table: outbox'))

class ScriptedService:
    """Submissions double: each dispatch, single or batched, takes the next scripted outcome
    (an exception or None)."""
    def __init__(self, outcomes): self.outcomes = list(outcomes); self.calls = 0
    def dispatch(self, run, prepare_only=False):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None: raise outcome
    def dispatch_batch(self, runs):
        self.dispatch(runs)

def test_sqlite_locked_exits_without_backoff(submission, monkeypatch, tmp_path):
    from test_submission import accepted
    _, store, actor, sid, revision, native = submission
    accepted(submission); waits = []
    service = ScriptedService([lock_error(6, 'database table is locked')])
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native)
    # Any wait ends the loop, so a regression (backoff on code 6) fails instead of hanging.
    monkeypatch.setattr(dispatcher.select, 'select', lambda *a: waits.append(a[-1]) or ([1], [], []))
    with pytest.raises(sqlite3.OperationalError, match='table is locked'):
        dispatcher.main()
    assert waits == [] and service.calls == 1
    assert store.execution_observation()['reason'] == 'executor_unavailable'

def test_persistent_contention_publishes_unavailable_then_recovers(submission, monkeypatch, tmp_path, capsys):
    """A stall that lasts STALL_ITERATIONS consecutive iterations must not keep readiness
    'ready' (refresh used to republish ready every iteration while every dispatch failed)."""
    from test_submission import accepted
    _, store, actor, sid, revision, native = submission
    accepted(submission)
    from hyprn_mvp_app import dispatcher as module
    stall = getattr(module, 'STALL_ITERATIONS', 3)
    service = ScriptedService([lock_error(5)] * stall)
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native)
    seen = []
    def select(read, write, error, timeout):
        seen.append((service.calls, store.execution_observation()['status']))
        return ([1] if len(seen) == stall + 2 else [], [], [])
    monkeypatch.setattr(dispatcher.select, 'select', select)
    dispatcher.main()
    statuses = [status for _, status in seen]
    assert 2 <= stall <= 5
    assert statuses[:stall - 1] == ['ready'] * (stall - 1)  # transient contention is not yet a stall
    assert statuses[stall - 1] == 'unavailable'  # published as soon as the stall threshold is reached
    assert statuses[stall + 1] == 'ready'  # the first successful iteration republishes ready
    err = capsys.readouterr().err
    assert err.count('dispatcher: ERROR') == 1 and 'consecutive' in err
    assert store.execution_observation()['reason'] == 'executor_unavailable'  # stopped() at exit

def test_exit_cause_is_not_masked_by_a_failing_unavailable_publication(submission, monkeypatch, tmp_path, capsys):
    """IN-01: stopped() raising (e.g. non-transient SQLITE_LOCKED) must not replace the exit cause."""
    from test_submission import accepted
    _, store, actor, sid, revision, native = submission
    accepted(submission)
    service = ScriptedService([RuntimeError('original exit cause')])
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native)
    def failing(self): raise lock_error(6, 'database table is locked')
    monkeypatch.setattr(dispatcher.ObservationPublisher, 'stopped', failing)
    with pytest.raises(RuntimeError, match='original exit cause'):
        dispatcher.main()
    assert 'unavailable observation not published' in capsys.readouterr().err

@pytest.mark.parametrize('attested', [True, False])
def test_export_dispatch_loop_uses_its_published_state_without_actor_read(
        submission, monkeypatch, tmp_path, attested):
    from test_submission import accepted
    _, store, actor, sid, revision, native = submission
    accepted(submission)
    service = ScriptedService([])
    dispatcher = dispatcher_for(monkeypatch, tmp_path, store, service, native,
                                ('dispatcher', '--with-exports'))
    monkeypatch.setattr(native, 'require_attestation', lambda: attested)
    monkeypatch.setattr(native, 'bundle_runtime', runtime_fixture)
    # Hosted row policies hide observations outside a user scope. The owner must
    # use its own publication, not impersonate a user or widen database access.
    monkeypatch.setattr(Store, 'execution_observation', lambda self: None)
    monkeypatch.setattr(dispatcher, 'export_once', lambda *a, **kw: None)
    monkeypatch.setattr(dispatcher.select, 'select', lambda *a: ([1], [], []))
    dispatcher.main()
    assert service.calls == int(attested)


def test_dispatch_readiness_expires_and_failed_publication_clears_it(api, monkeypatch):
    from hyprn_mvp_app import readiness
    clock = [1000.]
    monkeypatch.setattr(readiness, 'wall_time', lambda: clock[0])
    publisher = readiness.ObservationPublisher(api[1], Native(), monotonic=lambda: clock[0])
    assert not publisher.ready()
    publisher.refresh()
    assert publisher.ready()
    clock[0] = 1030.
    assert not publisher.ready()
    publisher.refresh()
    assert publisher.ready()
    clock[0] = 1029.
    assert not publisher.ready()
    clock[0] = 1040.
    def unavailable(*args):
        raise sqlite3.OperationalError('publication failed')
    monkeypatch.setattr(api[1], 'publish_execution_observation', unavailable)
    with pytest.raises(sqlite3.OperationalError):
        publisher.refresh()
    assert not publisher.ready()


def test_idle_polling_is_bounded_and_work_resets_the_delay():
    from hyprn_mvp_app.dispatcher import IdleBackoff

    idle = IdleBackoff()
    elapsed = 0
    polls = 0
    while elapsed < 60:
        elapsed += idle.delay(False)
        polls += 1
    assert polls <= 65
    assert idle.delay(True) == 0.05
    assert idle.delay(False) == 0.1
    interactive = IdleBackoff(maximum=0.25)
    elapsed = polls = 0
    while elapsed < 60:
        delay = interactive.delay(False)
        assert delay <= 0.25
        elapsed += delay
        polls += 1
    assert polls <= 242


def test_dispatch_discovery_uses_operational_state_without_reading_bundle(submission):
    from hyprn_mvp_app.dispatcher import pending_runs
    from test_submission import accepted

    _, store, _, _, _, _ = submission
    run = accepted(submission)['run_id']
    statements = []
    with store.connection() as db:
        db.set_trace_callback(statements.append)
        assert pending_runs(db) == [run]
    assert not any('outbox' in statement.lower() for statement in statements)
    assert any('execution_operations' in statement for statement in statements)


def test_rollback_failure_preserves_primary_transaction_failure(monkeypatch):
    from hyprn_mvp_app.database import PostgreSQL
    import hyprn_mvp_app.database as module

    class Raw:
        def rollback(self):
            raise ConnectionError('transport lost during rollback')

    class Connection:
        def __init__(self, raw):
            pass

        def execute(self, *args):
            pass

    monkeypatch.setattr(module, 'Connection', Connection)
    primary = TimeoutError('statement exceeded its deadline')
    with pytest.raises(module.DatabaseUnavailable) as failure:
        with PostgreSQL._transaction(None, Raw(), write=False):
            raise primary
    assert failure.value.__cause__ is primary
    assert primary.__notes__ == ['Transaction rollback also failed: ConnectionError']


def test_actual_attestation_does_not_certify_an_expired_executor_stage(api, monkeypatch):
    import hyprn_mvp_app.readiness as readiness

    clock = [1000.]
    monkeypatch.setattr(readiness, 'wall_time', lambda: clock[0])
    native = Native()
    owner = readiness.ObservationPublisher(api[1], native, monotonic=lambda: clock[0])
    assert owner.refresh(progressing=True)
    clock[0] += 31
    assert owner.refresh(progressing=False)
    assert api[1].execution_observation()['reason'] == 'executor_unavailable'
    assert native.calls == 1
    clock[0] += 10
    native.error = ValueError('Changed runtime')
    owner.refresh(progressing=True)
    assert api[1].execution_observation()['reason'] == 'attestation_invalid'


def test_stopped_owner_cannot_publish_late_ready_from_native_reply(api):
    import threading
    from hyprn_mvp_app.readiness import ObservationPublisher

    entered, release = threading.Event(), threading.Event()
    native = Native()
    original = native.require_attestation

    def delayed():
        entered.set()
        assert release.wait(5)
        return original()

    native.require_attestation = delayed
    owner = ObservationPublisher(api[1], native)
    thread = threading.Thread(target=owner.refresh)
    thread.start()
    try:
        assert entered.wait(5)
        owner.stopping()
        assert not owner.ready()
    finally:
        release.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert owner.stopped()
    assert api[1].execution_observation()['reason'] == 'executor_unavailable'


def test_contention_unavailability_is_not_overwritten_by_inflight_attestation(api):
    import threading
    from hyprn_mvp_app.readiness import ObservationPublisher

    entered, release = threading.Event(), threading.Event()
    native = Native()
    original = native.require_attestation

    def delayed():
        entered.set()
        assert release.wait(5)
        return original()

    native.require_attestation = delayed
    owner = ObservationPublisher(api[1], native)
    thread = threading.Thread(target=owner.refresh)
    thread.start()
    try:
        assert entered.wait(5)
        owner.stall(3, RuntimeError('Synthetic contention'))
    finally:
        release.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert not owner.ready()
    assert api[1].execution_observation()['reason'] == 'executor_unavailable'

@pytest.mark.parametrize('failure', [TimeoutError('read timed out'), OSError('connection lost')])
def test_transport_loss_reaches_dispatcher_reconciliation_not_process_exit(failure):
    from hyprn_mvp_app.database import Connection, DatabaseUnavailable
    from hyprn_mvp_app.readiness import transient_lock_error
    class Raw:
        def cursor(self):
            return self
        def execute(self, statement, parameters):
            raise failure
    with pytest.raises(DatabaseUnavailable) as caught:
        Connection(Raw()).execute('SELECT pg_advisory_xact_lock(68272601)')
    assert transient_lock_error(caught.value)


def test_concurrent_bridge_contention_waits_on_owner_stop_not_response_stdin(monkeypatch):
    from hyprn_mvp_app import dispatcher
    from hyprn_mvp_app.database import DatabaseUnavailable
    class Stop:
        def wait(self, seconds):
            assert seconds == dispatcher.LOCK_BACKOFF_INITIAL
            return False
    def forbidden(*args):
        pytest.fail('The response reader owns stdin while the bridge is concurrent')
    monkeypatch.setattr(dispatcher.select, 'select', forbidden)
    assert not dispatcher.wait_out_lock(DatabaseUnavailable('busy'), 1,
                                        bounded=False, stop_event=Stop())
