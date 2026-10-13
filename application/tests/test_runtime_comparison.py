"""Synthetic app persistence and actual producer/read paths; no scientific runs."""
import base64
import copy
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from hyprn_mvp_app.store import Store, DomainError, canonical, digest, uid
from hyprn_mvp_app.execution import Submissions
from hyprn_mvp_app.readiness import ObservationPublisher
from execution_fixtures import runtime_fixture
from test_result_bindings import env, prepared2
from test_submission import NativeDouble


class TrustedDouble:
    def __init__(self): self.selected=runtime_fixture(); self.calls=[]; self.error=None
    def require_attestation(self):
        self.calls.append('attest')
        if self.error: raise self.error
        return True
    def bundle_runtime(self):
        self.calls.append('runtime')
        return copy.deepcopy(self.selected)


@pytest.fixture
def observation(tmp_path,monkeypatch):
    import hyprn_mvp_app.readiness as readiness
    clock=[1000.];monkeypatch.setattr(readiness,'wall_time',lambda:clock[0])
    store=Store(tmp_path/'observation.sqlite');actor=uid();sid=store.create_study(actor,uid(),'Runtime')['study_id']
    native=TrustedDouble();publisher=ObservationPublisher(store,native,monotonic=lambda:clock[0])
    return store,actor,sid,native,publisher,clock


def compare(observation,source=None):
    from hyprn_mvp_app.readiness import runtime_comparison
    store,actor,sid,*_=observation
    return runtime_comparison(store,actor,sid,source or runtime_fixture()['runtime'])


def test_attested_producer_persists_only_closed_identity_and_reopens(observation):
    store,_,_,native,publisher,clock=observation
    assert publisher.refresh()
    assert native.calls==['attest','runtime']
    row=Store(store.path).execution_observation()
    assert row['runtime']==native.selected['runtime']
    with store.connection() as db: raw=db.execute('SELECT runtime_json FROM execution_observation').fetchone()[0]
    assert json.loads(raw)==native.selected['runtime']
    assert not any(word in raw for word in ('files','licenses','locks/','repository','attestation'))
    result=compare(observation)
    assert result==dict(source=runtime_fixture()['runtime'],current=native.selected['runtime'],state='same',
        basis='executor_observation',observed_at='1970-01-01T00:16:40Z',expires_at='1970-01-01T00:17:10Z')


@pytest.mark.parametrize('field,value',[
    ('image_digest','sha256:'+'g'*64),('image_digest','/private/token'),
    ('architecture','arm64 /private/secret'),('architecture','TOKEN=synthetic'),
    ('python_version','3.12.11 token=secret'),('python_version','/host/python'),
    ('worker_entrypoint','os.system'),('policy_digest','x'*64),('policy_digest',None),
    ('extra','synthetic-secret'),('files',{}),('architecture',True)])
def test_unsafe_selected_runtime_invalidates_previous_identity(observation,field,value):
    store,_,_,native,publisher,clock=observation
    publisher.refresh();clock[0]+=10
    native.selected['runtime'][field]=value
    publisher.refresh()
    row=store.execution_observation()
    assert row['status']=='unavailable' and row['runtime'] is None
    assert compare(observation)['state']=='unavailable'
    assert compare(observation)['current'] is None


def test_attestation_failure_stop_restart_throttle_and_slow_call(observation):
    store,_,_,native,publisher,clock=observation
    publisher.refresh();clock[0]=1009
    assert not publisher.refresh() and native.calls==['attest','runtime']
    publisher.stopped();assert store.execution_observation()['runtime'] is None
    clock[0]=1010;native.error=RuntimeError('/private/secret')
    assert publisher.refresh();assert native.calls==['attest','runtime','attest']
    assert compare(observation)['state']=='unavailable'
    native.error=None;clock[0]=1020
    original=native.bundle_runtime
    def slow(): clock[0]=1051;return original()
    native.bundle_runtime=slow;publisher.refresh()
    assert store.execution_observation()['observed_at']==1020
    assert compare(observation)['state']=='unavailable'
    native.bundle_runtime=original;clock[0]=1060;publisher.refresh()
    assert compare(observation)['state']=='same'
    publisher.stopped();assert compare(observation)['current'] is None


@pytest.mark.parametrize('when',[999.,1030.,1031.])
def test_future_or_expired_observation_is_unavailable(observation,when):
    *_,publisher,clock=observation
    publisher.refresh();clock[0]=when
    result=compare(observation)
    assert result['state']=='unavailable' and result['current'] is None


def test_missing_identity_old_rows_and_corrupt_json_never_authorize(observation):
    store,_,_,_,publisher,_=observation
    assert compare(observation)['state']=='unavailable'
    store.publish_execution_observation('ready',None,1000.)
    assert compare(observation)['state']=='unavailable'
    publisher.refresh()
    for raw in ('not-json','null','[]','{"architecture":"/private/secret"}',
                json.dumps(runtime_fixture()['runtime'])[:-1]+',"architecture":"secret"}'):
        with store.connection(write=True) as db: db.execute('UPDATE execution_observation SET runtime_json=?',(raw,))
        assert compare(observation)['state']=='unavailable'


@pytest.mark.parametrize('when',[True,-1,float('nan'),float('inf'),10**1000,1e100])
def test_invalid_observation_times_refused_without_mutation(observation,when):
    store,_,_,_,publisher,_=observation
    publisher.refresh();before=store.execution_observation()
    with pytest.raises(ValueError): store.publish_execution_observation('ready',None,when,runtime_fixture()['runtime'])
    assert store.execution_observation()==before


def test_closed_store_write_and_read_freshness_recheck(observation,monkeypatch):
    store,_,_,_,publisher,clock=observation
    publisher.refresh();before=store.execution_observation()
    for status,reason,runtime in [('ready','executor_unavailable',None),('unavailable',None,None),
                                 ('unavailable','executor_unavailable',runtime_fixture()['runtime']),
                                 ('ready',None,runtime_fixture()['runtime']|{'secret':'no'})]:
        with pytest.raises(ValueError): store.publish_execution_observation(status,reason,1000.,runtime)
        assert store.execution_observation()==before
    read=store.execution_observation
    def delayed(): row=read();clock[0]=1031.;return row
    monkeypatch.setattr(store,'execution_observation',delayed)
    assert compare(observation)['current'] is None


def test_authorization_precedes_observation_read(observation,monkeypatch):
    store,actor,sid,*_=observation
    from hyprn_mvp_app.readiness import runtime_comparison
    monkeypatch.setattr(store,'execution_observation',lambda:pytest.fail('Unauthorized observation read'))
    with pytest.raises(DomainError,match='resource_not_found'):
        runtime_comparison(store,uid(),sid,runtime_fixture()['runtime'])


def test_additive_old_observation_migration_preserves_old_records(tmp_path):
    path=tmp_path/'old.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE execution_observation(singleton INTEGER PRIMARY KEY,status TEXT,reason TEXT,observed_at REAL,expires_at REAL)')
        db.execute("INSERT INTO execution_observation VALUES(1,'ready',NULL,1000,1030)")
        db.execute('CREATE TABLE historical_fixture(payload BLOB)')
        db.execute('INSERT INTO historical_fixture VALUES(?)',(b'old exact bytes\x00\xff',))
    for _ in range(2):
        store=Store(path)
        with store.connection() as db:
            assert [r['name'] for r in db.execute('PRAGMA table_info(execution_observation)')].count('runtime_json')==1
            assert db.execute('SELECT payload FROM historical_fixture').fetchone()[0]==b'old exact bytes\x00\xff'
        assert store.execution_observation()==dict(status='ready',reason=None,observed_at=1000.,expires_at=1030.,runtime=None)
    store.publish_execution_observation('ready',None,1010.,runtime_fixture()['runtime'])
    assert Store(path).execution_observation()['runtime']==runtime_fixture()['runtime']


def derived_service(env):
    """Construct only a synthetic saved config2; no modified-seed/API implementation."""
    frozen=copy.deepcopy(env['case']['frozen']);c=frozen['configuration'];source=copy.deepcopy(c)
    c.update(schema_version='2',configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None,
        inputs=[i|dict(result_binding=None) for i in c['inputs']],
        context_source=dict(kind='current_study',expected_study_revision=env['store'].study(env['actor'],env['sid'])['revision']),
        derivation=dict(source_run_id=env['rid'],source_configuration_revision_id=source['configuration_revision_id'],
            source_configuration_digest=source['digest'],source_runtime=runtime_fixture()['runtime'],changes=[]))
    c['digest']=digest({k:v for k,v in c.items() if k!='digest'})
    with env['store'].connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],env['sid'],json.dumps(frozen)))
    native=NativeDouble();native.selected=runtime_fixture();native.bundle_runtime=lambda:copy.deepcopy(native.selected)
    service=Submissions(env['store'],lambda *args:prepared2(env,frozen),native)
    return service,native,c


def test_actual_frozen_runtime_supersedes_preview_without_restoring_source(env,monkeypatch):
    import hyprn_mvp_app.readiness as readiness
    monkeypatch.setattr(readiness,'wall_time',lambda:1000.)
    store=env['store'];service,native,c=derived_service(env)
    with store.connection() as db: before=db.execute('SELECT payload FROM outbox WHERE run_id=?',(env['rid'],)).fetchone()[0]
    publisher=ObservationPublisher(store,native);publisher.refresh()
    run=service.submit(env['actor'],env['sid'],dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    assert run['runtime_comparison']['state']=='same' and native.launches==0
    native.selected['runtime'].update(image_digest='sha256:'+'c'*64,python_version='3.13.5')
    service.dispatch(run['run_id'],prepare_only=True)
    actual=service.read(env['actor'],env['sid'],run['run_id'])['runtime_comparison']
    assert actual==dict(source=c['derivation']['source_runtime'],current=native.selected['runtime'],
        state='different',basis='prepared_bundle',observed_at=None,expires_at=None)
    with store.connection() as db:
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])
        retained=canonical(payload['bundle'])
        assert payload['bundle']['manifest']['runtime']==actual['current']
        assert json.loads(base64.b64decode(payload['bundle']['files']['configuration.json']))==c
    publisher.stopped()
    readonly=Submissions(Store(store.path),None,None)
    assert readonly.read(env['actor'],env['sid'],run['run_id'])['runtime_comparison']==actual
    service.dispatch(run['run_id'])  # Explicit in-memory NativeDouble, no candidate execution.
    assert service.read(env['actor'],env['sid'],run['run_id'])['runtime_comparison']==actual
    with store.connection() as db:
        assert db.execute('SELECT payload FROM outbox WHERE run_id=?',(env['rid'],)).fetchone()[0]==before
        assert canonical(json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])['bundle'])==retained


def test_corrupt_prepared_identity_never_falls_back_to_observation(env):
    service,native,c=derived_service(env)
    ObservationPublisher(env['store'],native).refresh()
    run=service.submit(env['actor'],env['sid'],dict(command_id=uid(),configuration_revision_id=c['configuration_revision_id']))
    service.dispatch(run['run_id'],prepare_only=True)
    with env['store'].connection(write=True) as db:
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])
        payload['bundle']['manifest']['runtime']['image_digest']='sha256:'+'f'*64
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),run['run_id']))
    result=service.read(env['actor'],env['sid'],run['run_id'])['runtime_comparison']
    assert result['basis']=='prepared_bundle' and result['current'] is None and result['state']=='unavailable'


def test_legacy_read_is_unchanged_without_derived_runtime(env):
    value=Submissions(env['store'],None,None).read(env['actor'],env['sid'],env['rid'])
    assert 'runtime_comparison' not in value


def test_runtime_group_interpreter_is_fixed_and_native_imports_stay_absent():
    import sys
    import checks as runner
    import scoped_fixture as fixture
    assert runner.GROUP_INTERPRETERS['runtime-observation']==fixture.APPROVED_CONTRACT_PYTHON
    assert sys.executable==fixture.APPROVED_CONTRACT_PYTHON
    assert not any(n.split('.')[0] in {'aiida','openmdao','openturns'} for n in sys.modules)


def test_group_interpreter_mismatch_refused_before_collection():
    from dataclasses import replace
    import checks as runner
    import scoped_fixture as fixture
    for interpreter,flag in [(fixture.APPROVED_PYTHON,'--runtime-observation-child'),
                             (fixture.APPROVED_CONTRACT_PYTHON,'--guard-child')]:
        scope=fixture.allocate_scope(replace(fixture.new_scope(),interpreter=interpreter))
        command=[interpreter,'-B',str(runner.REPO/'deployment/checks.py'),flag]
        result=subprocess.run(command,cwd=runner.REPO,env=fixture.clean_environment(scope),capture_output=True,text=True)
        assert result.returncode!=0 and 'reviewed interpreter' in result.stderr
        assert not (scope.root/'evidence/tests.json').exists()


def test_actual_native_selection_checks_attestation_identity(tmp_path):
    import scoped_fixture as fixture
    import checks as runner
    scope=fixture.allocate_scope(fixture.new_scope())
    script='''
import sys,json,copy
from pathlib import Path
repo=Path.cwd()
sys.path.insert(0,str(repo/'deployment/tests'))
import scoped_fixture
scope=scoped_fixture.scope_from_environment()
sys.path[:0]=[str(repo/'application/src'),str(repo/'integration/src'),str(repo/'integration/tests')]
from hyprn_mvp_integration.calculation import NativeExecution
from hyprn_mvp_integration import launcher
from hyprn_mvp_app.store import digest
from execution_fixtures import runtime_fixture
selection=runtime_fixture();policy={'fixture':'contained'}
selection['runtime']['policy_digest']=digest(policy)
runtime=selection['runtime']
evidence={'passed':True,'fingerprint':{'image':runtime['image_digest'],'policy':policy,
    'runtime':{'worker_image':runtime['image_digest'],'architecture':runtime['architecture'],
               'python_version':runtime['python_version']}}}
from types import SimpleNamespace
# Both reads are bound to the explicit isolated runtime root of this scope, never a default root.
owner=SimpleNamespace(root=scope.root)
def scoped(value):
    def read(*,root):
        assert root==scope.root,root
        return copy.deepcopy(value() if callable(value) else value)
    return read
launcher.require_attestation=scoped(lambda:evidence)
launcher.bundle_runtime=scoped(lambda:selection)
def forbidden(*args,**kwargs):raise AssertionError('Workload or host service accessed')
launcher.command=forbidden;launcher.isolated=forbidden
assert NativeExecution.bundle_runtime(owner)==selection
for key,value in [('image_digest','sha256:'+'c'*64),('architecture','amd64'),('python_version','3.13.5'),
                  ('worker_entrypoint','other.worker'),('policy_digest','d'*64)]:
    original=selection['runtime'][key];selection['runtime'][key]=value
    try:NativeExecution.bundle_runtime(owner)
    except (RuntimeError,ValueError):pass
    else:raise AssertionError('Unattested selected '+key+' accepted')
    selection['runtime'][key]=original
for bad in [True,{}, {'passed':False,'fingerprint':evidence['fingerprint']},
            {'passed':True,'fingerprint':{}}]:
    launcher.require_attestation=scoped(bad)
    try:NativeExecution.bundle_runtime(owner)
    except (RuntimeError,ValueError):pass
    else:raise AssertionError('Incomplete attestation accepted')
assert not (scope.root/'aiida/.aiida/config.json').exists()
print(json.dumps({'identity_checks':10,'native_profile_created':False,'workloads':0}))
'''
    command=[scope.interpreter,'-B','-c',script]
    result=subprocess.run(command,cwd=runner.REPO,env=fixture.clean_environment(scope),capture_output=True,text=True)
    (scope.root/'evidence/native-identity.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    (tmp_path/'native-evidence.json').write_text(json.dumps({'root':str(scope.root)}))
    assert result.returncode==0,result.stdout+result.stderr
