"""Evidence family storage contracts on the runner's isolated, off-cloud store."""
import base64
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from contextlib import contextmanager
from pathlib import Path

import pytest
import scoped_fixture as guard
from checks import PROJECTION_SCOPE
from hyprn_mvp_app.store import DomainError, Store, canonical, digest, uid

SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)


@pytest.fixture
def env(tmp_path):
    assert guard.no_symlinks(tmp_path).is_relative_to(SCOPE.root)
    store = Store(tmp_path / 'evidence.sqlite')
    actor = uid()
    study = store.create_study(actor, uid(), 'Original study')
    return store, actor, study['study_id']


def note(sid, **changes):
    return dict(evidence_schema_version='3', title='Heat capacity report', kind='note',
                content='Exact observation', source_refs=['Report 4'],
                resource_scope=dict(scope_version='1', kind='study', study_id=sid), **changes)


def rows(store, table):
    with store.connection() as db:
        return [tuple(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]


def revise(env, old, command=None, **changes):
    store, actor, sid = env
    return store.revise_evidence(actor, sid, old['evidence_id'], command or uid(),
                                 old['evidence_version_id'], {**note(sid), **changes})


def test_create_revision_replay_and_immutable_rows(env):
    store, actor, sid = env
    command = uid(); first = store.add_evidence(actor, sid, command, note(sid))
    original = rows(store, 'evidence')
    assert first['parent_evidence_version_id'] is None
    assert first['recorded_context']['resource_labels'][0]['name'] == 'Original study'
    revision_command = uid(); second = revise(env, first, revision_command, title='New report')
    third = revise(env, second)
    assert second['parent_evidence_version_id'] == first['evidence_version_id']
    assert store.add_evidence(actor, sid, command, note(sid)) == first
    assert revise(env, first, revision_command, title='New report') == second
    assert store.evidence_family(actor, sid, first['evidence_id'])['head'] == third
    assert rows(store, 'evidence')[:1] == original
    assert store.evidence_version(actor, sid, first['evidence_version_id']) == first
    with pytest.raises(DomainError, match='command_payload_conflict'):
        revise(env, first, revision_command, content='Different')
    before = rows(store, 'evidence'), rows(store, 'evidence_families')
    with pytest.raises(DomainError, match='stale_revision') as error:
        revise(env, first)
    assert error.value.current_revision == third['evidence_version_id']
    assert (rows(store, 'evidence'), rows(store, 'evidence_families')) == before
    with pytest.raises(sqlite3.IntegrityError, match='immutable evidence'):
        with store.connection(write=True) as db:
            db.execute('UPDATE evidence SET payload=?', ('{}',))


def test_racing_revisions_and_duplicate_command(env):
    store, actor, sid = env
    first = store.add_evidence(actor, sid, uid(), note(sid))
    barrier = Barrier(2)
    def save(command):
        barrier.wait()
        try: return revise(env, first, command)
        except DomainError as error: return error.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(save, [uid(), uid()]))
    assert sum(isinstance(x, dict) for x in results) == 1
    assert 'stale_revision' in results
    head = store.evidence_family(actor, sid, first['evidence_id'])['head']
    barrier = Barrier(2); command = uid()
    def duplicate(_):
        barrier.wait()
        return revise(env, head, command)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(duplicate, range(2)))
    assert results[0] == results[1] and len(rows(store, 'evidence')) == 3


def test_legacy_rows_are_untouched_and_lazily_indexed(env):
    store, actor, sid = env
    old = store.add_evidence(actor, sid, uid(), dict(scope=None, kind='note', content='Original', source_refs=[]))
    before = rows(store, 'evidence')
    restarted = Store(store.path)
    assert rows(restarted, 'evidence_families') == []
    assert restarted.evidence_family(actor, sid, old['evidence_id'])['head'] == old
    assert restarted.list_evidence(actor, sid, [])['data'] == [old]
    new = revise(env, old)
    assert new['parent_evidence_version_id'] == old['evidence_version_id']
    assert rows(store, 'evidence')[:1] == before
    assert len(rows(store, 'evidence_families')) == 1


def test_authorization_scope_family_and_closed_input(env):
    store, actor, sid = env
    command = uid(); first = store.add_evidence(actor, sid, command, note(sid))
    other = store.create_study(actor, uid(), 'Other')['study_id']
    for call in [lambda: store.evidence_family(actor, other, first['evidence_id']),
                 lambda: store.evidence_version(actor, other, first['evidence_version_id']),
                 lambda: store.revise_evidence(actor, other, first['evidence_id'], uid(), first['evidence_version_id'], note(other)),
                 lambda: store.add_evidence(actor, other, uid(), note(sid))]:
        with pytest.raises(DomainError, match='resource_not_found'): call()
    for bad in [{**note(sid), 'title':' '}, {**note(sid), 'recorded_context':{}},
                {**note(sid), 'content':' '}, {**note(sid), 'title':'x'*201}]:
        with pytest.raises(DomainError, match='invalid_request'):
            store.add_evidence(actor, sid, uid(), bad)
    with store.connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE study_id=?", (sid,))
    with pytest.raises(DomainError, match='forbidden'):
        store.add_evidence(actor, sid, command, note(sid))
    with store.connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (sid,))
    for call in [lambda: store.add_evidence(actor, sid, command, note(sid)),
                 lambda: store.receipt(actor, sid, 'evidence', command),
                 lambda: store.list_evidence(actor, sid, [])]:
        with pytest.raises(DomainError, match='resource_not_found'): call()


def test_heads_and_version_pages_freeze_highwater_and_bind_query(env):
    store, actor, sid = env
    records = [store.add_evidence(actor, sid, uid(), note(sid)) for _ in range(4)]
    first = store.list_evidence(actor, sid, [('limit','2')])
    assert first['data'] == records[:2]
    updated = revise(env, records[2])
    store.add_evidence(actor, sid, uid(), note(sid))
    page = store.list_evidence(actor, sid, [('limit','2'), ('cursor',first['next_cursor'])])
    assert page['data'] == [updated, records[3]] and page['next_cursor'] is None
    versions = store.evidence_versions(actor, sid, updated['evidence_id'], [('limit','1')])
    revise(env, updated)
    assert versions['data'] == [updated]
    assert store.evidence_versions(actor, sid, updated['evidence_id'], [('cursor',versions['next_cursor'])])['data'] == [records[2]]
    for extra in [[('view','versions')], [('scope_kind','study')], [('cursor',first['next_cursor'])]]:
        with pytest.raises(DomainError, match='invalid_request'):
            store.list_evidence(actor, sid, [('cursor',first['next_cursor']), *extra])
    for cursor in ['bad', 'x'*2049, uid()]:
        with pytest.raises(DomainError, match='invalid_request'):
            store.list_evidence(actor, sid, [('cursor',cursor)])


@pytest.fixture
def scoped(env):
    """Closed synthetic immutable adapter response; no native execution claim."""
    from test_reuse_contract import numerical
    from hyprn_mvp_app.modeling import validate
    store, actor, sid = env
    definition = dict(definition_id=uid(), definition_version_id=uid(), kind='explicit_component',
                      name='Exact definition', ports=[], source_refs=[], residual_port_ids=[],
                      child_instances=[], boundary_mappings=[], annotations=[])
    root_definition = {**definition, 'definition_id':uid(), 'definition_version_id':uid(),
                       'kind':'composite', 'name':'Root', 'ports':[]}
    port = dict(port_id=uid(), definition_version_id=definition['definition_version_id'], direction='output',
                name='Heat', code_symbol='heat', value_type='real_scalar', units='W')
    definition['ports'] = [port]
    root = dict(instance_id=uid(), definition_version_id=root_definition['definition_version_id'], name='Exact model')
    instance = dict(instance_id=uid(), definition_version_id=definition['definition_version_id'], name='Exact component')
    second = {**instance, 'instance_id':uid(), 'name':'Second component'}
    target = dict(instance_id=instance['instance_id'], port_id=port['port_id'])
    connection = dict(connection_id=uid(), source_ref=target,
                      target_ref=dict(instance_id=second['instance_id'], port_id=port['port_id']))
    model = dict(schema_version='1', model_id=uid(), model_revision_id=uid(), parent_model_revision_id=None,
                 originating_draft_revision=uid(), root_instance_id=root['instance_id'],
                 definitions=[root_definition, definition], instances=[root, instance, second], ports=[],
                 connections=[connection], boundary_mappings=[], annotations=[], source_files=[], required_capabilities=[])
    model['digest'] = digest(model)
    criterion = dict(criterion_id=uid(), target=target, operator='ge', threshold=1, units='W', evidence_version_ids=[])
    config = dict(schema_version='1', study_id=sid, model_id=model['model_id'], model_revision_id=model['model_revision_id'],
                  name='Exact configuration', inputs=[], criteria=[criterion], numerical=numerical(),
                  context_snapshot=dict(description='',boundary='',notes=[]), evidence_snapshots=[], required_capabilities=[],
                  configuration_id=uid(), configuration_revision_id=uid(), parent_revision_id=None)
    config['digest'] = digest(config)
    validate('ModelRevision', model); validate('ConfigurationRevision', config)
    frozen = dict(configuration=config, model_snapshot=model, study_revision=store.study(actor,sid)['revision'])
    run = uid()
    with store.connection(write=True) as db:
        db.execute('INSERT INTO model_associations VALUES(?,?,?)', (sid,model['model_id'],uid()))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',
                   (config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(frozen)))
        db.execute('INSERT INTO run_associations(run_id,study_id,configuration_revision_id,command_id) VALUES(?,?,?,?)',
                   (run,sid,config['configuration_revision_id'],uid()))
    base = dict(scope_version='1', study_id=sid)
    binding = dict(base, model_id=model['model_id'], model_revision_id=model['model_revision_id'])
    scopes = dict(study=dict(base,kind='study'), model_revision=dict(binding,kind='model_revision'),
                  definition_version=dict(binding,kind='definition_version',definition_id=definition['definition_id'],definition_version_id=definition['definition_version_id']),
                  instance=dict(binding,kind='instance',instance_id=instance['instance_id']),
                  port=dict(binding,kind='port',instance_id=instance['instance_id'],port_id=port['port_id']),
                  connection=dict(binding,kind='connection',connection_id=connection['connection_id']),
                  configuration=dict(base,kind='configuration',configuration_revision_id=config['configuration_revision_id']),
                  criterion=dict(base,kind='criterion',configuration_revision_id=config['configuration_revision_id'],criterion_id=criterion['criterion_id']),
                  run=dict(base,kind='run',run_id=run))
    class ExactCoordinator:
        def __init__(self): self.calls=0; self.before_return=None
        def read(self, who, study, mid, path, **kwargs):
            assert (who,study,mid,path)==(actor,sid,model['model_id'],'/revisions/'+model['model_revision_id'])
            self.calls += 1
            # Acquiring a separate writer here proves no write lock spans I/O.
            with store.connection(write=True): pass
            if self.before_return:self.before_return()
            return dict(data=copy.deepcopy(model))
    return scopes, model, config, ExactCoordinator()


@pytest.mark.parametrize('kind', ['study','model_revision','definition_version','instance','port','connection','configuration','criterion','run'])
def test_exact_labels_all_scopes_and_rename_immutability(env, scoped, kind):
    store, actor, sid = env; scopes, model, config, coordinator = scoped
    command = uid(); payload = {**note(sid), 'resource_scope':scopes[kind]}
    saved = store.add_evidence(actor,sid,command,payload,coordinator=coordinator)
    labels = saved['recorded_context']['resource_labels']
    assert labels[0] == dict(kind='study',resource_id=sid,version_id=None,name='Original study')
    expected_kind = {'model_revision':'model','definition_version':'definition'}.get(kind,kind)
    assert labels[-1]['kind'] == expected_kind
    if kind != 'study': assert labels[1]['name']=='Exact model'
    if kind in {'configuration','criterion','run'}:
        assert next(x for x in labels if x['kind']=='configuration')['name']=='Exact configuration'
        assert coordinator.calls==0
    if kind=='port': assert labels[-1]['name']=='Heat'
    if kind=='connection': assert labels[-1]['name']=='Exact component.Heat → Second component.Heat'
    before = rows(store,'evidence')
    study = store.study(actor,sid)
    store.update_study(actor,sid,uid(),study['revision'],dict(name='Renamed study'))
    model['instances'][0]['name']='Later live model'
    assert Store(store.path).evidence_version(actor,sid,saved['evidence_version_id'])==saved
    assert store.add_evidence(actor,sid,command,payload,coordinator=None)==saved
    assert rows(store,'evidence')==before


@pytest.mark.parametrize('kind,field', [('study','study_id'),('model_revision','model_id'),
    ('definition_version','definition_id'),('definition_version','definition_version_id'),
    ('instance','instance_id'),('port','port_id'),('connection','connection_id'),
    ('configuration','configuration_revision_id'),('criterion','criterion_id'),('run','run_id')])
def test_missing_immutable_target_never_writes(env, scoped, kind, field):
    store, actor, sid=env;scopes,_,_,coordinator=scoped
    before=rows(store,'evidence'),rows(store,'evidence_families'),rows(store,'receipts')
    with pytest.raises(DomainError,match='resource_not_found'):
        store.add_evidence(actor,sid,uid(),{**note(sid),'resource_scope':{**scopes[kind],field:uid()}},coordinator=coordinator)
    assert (rows(store,'evidence'),rows(store,'evidence_families'),rows(store,'receipts'))==before


@pytest.mark.parametrize('change', ['revoke','association','study','digest','duplicate','wrong_revision'])
def test_reference_and_authority_races_rechecked_before_commit(env,scoped,change):
    store,actor,sid=env;scopes,model,_,coordinator=scoped
    def mutate():
        with store.connection(write=True) as db:
            if change=='revoke':db.execute('DELETE FROM memberships WHERE study_id=?',(sid,))
            if change=='association':db.execute('DELETE FROM model_associations WHERE study_id=?',(sid,))
            if change=='study':db.execute("UPDATE studies SET name='Changed' WHERE study_id=?",(sid,))
        if change=='digest':model['instances'][0]['name']='Forged'
        if change=='duplicate':
            model['instances'].append(copy.deepcopy(model['instances'][1]))
            model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
        if change=='wrong_revision':
            model['model_revision_id']=uid()
            model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
    coordinator.before_return=mutate
    with pytest.raises(DomainError):
        store.add_evidence(actor,sid,uid(),{**note(sid),'resource_scope':scopes['instance']},coordinator=coordinator)
    assert rows(store,'evidence')==[] and rows(store,'evidence_families')==[]


def test_ambiguous_legacy_family_and_wrong_route_never_promote(env):
    store,actor,sid=env
    first=store.add_evidence(actor,sid,uid(),dict(scope=None,kind='note',content='Legacy',source_refs=[]))
    second={**first,'evidence_version_id':uid()}
    with store.connection(write=True) as db:
        db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(second['evidence_version_id'],first['evidence_id'],sid,json.dumps(second)))
    before=rows(store,'evidence')
    for call in [lambda:store.evidence_family(actor,sid,first['evidence_id']),
                 lambda:store.list_evidence(actor,sid,[]),lambda:revise(env,first)]:
        with pytest.raises(DomainError,match='reference_conflict'):call()
    assert rows(store,'evidence')==before and rows(store,'evidence_families')==[]
    a=store.add_evidence(actor,sid,uid(),note(sid));b=store.add_evidence(actor,sid,uid(),note(sid))
    with pytest.raises(DomainError,match='stale_revision'):
        store.revise_evidence(actor,sid,b['evidence_id'],uid(),a['evidence_version_id'],note(sid))


def test_cursor_tampering_actor_study_family_and_sql_bounds(env,monkeypatch):
    store,actor,sid=env
    first=store.add_evidence(actor,sid,uid(),note(sid))
    for _ in range(4):store.add_evidence(actor,sid,uid(),note(sid))
    page=store.list_evidence(actor,sid,[('limit','1')]);cursor=page['next_cursor']
    decoded=json.loads(base64.urlsafe_b64decode(cursor+'='*(-len(cursor)%4)))
    for alteration in [dict(study_id=uid()),dict(actor_id=uid()),dict(family_id=uid()),dict(high_water=-1),
                       dict(last_rowid=True),dict(last_rowid=2**63),dict(cursor_version='2'),dict(extra=0)]:
        token=store._evidence_cursor({**decoded,**alteration})
        with pytest.raises(DomainError,match='invalid_request'):
            store.list_evidence(actor,sid,[('cursor',token)])
    other_actor=uid();other=store.create_study(actor,uid(),'Foreign')['study_id']
    store.add_evidence(actor,other,uid(),note(other))
    with store.connection(write=True) as db:db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,other_actor,'reader'))
    for who,study in [(other_actor,sid),(actor,other)]:
        with pytest.raises(DomainError,match='invalid_request'):store.list_evidence(who,study,[('cursor',cursor)])
    # Positions are navigation, not a credential: edited offsets stay scoped.
    token=store._evidence_cursor({**decoded,'last_rowid':0,'high_water':1000})
    assert all(x['study_id']==sid for x in store.list_evidence(actor,sid,[('cursor',token)])['data'])
    statements=[];connection=store.connection
    @contextmanager
    def traced(*args,**kwargs):
        with connection(*args,**kwargs) as db:
            db.set_trace_callback(statements.append);yield db
    monkeypatch.setattr(store,'connection',traced)
    store.list_evidence(actor,sid,[('limit','2')])
    queries=[q for q in statements if q.startswith('SELECT e.payload,')]
    assert len(queries)==1 and queries[0].endswith('LIMIT 3')
    v2=revise(env,first);revise(env,v2)
    versions=store.evidence_versions(actor,sid,first['evidence_id'],[('limit','1')])
    other_family=store.add_evidence(actor,sid,uid(),note(sid))
    with pytest.raises(DomainError,match='invalid_request'):
        store.evidence_versions(actor,sid,other_family['evidence_id'],[('cursor',versions['next_cursor'])])


def test_receipt_failure_rolls_back_version_and_family(env,monkeypatch):
    store,actor,sid=env
    first=store.add_evidence(actor,sid,uid(),note(sid))
    before=rows(store,'evidence'),rows(store,'evidence_families')
    with store.connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT,'receipt fault'); END")
    with pytest.raises(sqlite3.IntegrityError,match='receipt fault'):revise(env,first)
    assert (rows(store,'evidence'),rows(store,'evidence_families'))==before


@pytest.mark.parametrize('kind', ['model_revision','definition_version','instance','port','connection','configuration','criterion','run'])
def test_existing_foreign_resources_cannot_be_relabelled_into_study(env,scoped,kind):
    store,actor,sid=env;scopes,_,_,coordinator=scoped
    other=store.create_study(actor,uid(),'Other study')['study_id']
    with pytest.raises(DomainError,match='resource_not_found'):
        store.add_evidence(actor,other,uid(),{**note(other),'resource_scope':{**scopes[kind],'study_id':other}},coordinator=coordinator)
    assert rows(store,'evidence')==[] and coordinator.calls==0


def test_filters_apply_to_current_head_and_versions_remain_exact(env,scoped):
    store,actor,sid=env;scopes,_,_,coordinator=scoped
    v1=store.add_evidence(actor,sid,uid(),{**note(sid),'resource_scope':scopes['port']},coordinator=coordinator)
    v2=revise(env,v1)
    assert store.list_evidence(actor,sid,[('scope_kind','port')])['data']==[]
    assert store.list_evidence(actor,sid,[('scope_kind','study')])['data']==[v2]
    assert store.list_evidence(actor,sid,[('scope_kind','port'),('view','versions')])['data']==[v1]
    assert store.evidence_versions(actor,sid,v1['evidence_id'],[])['data']==[v2,v1]
    legacy=store.add_evidence(actor,sid,uid(),dict(scope=None,kind='note',content='Legacy',source_refs=[]))
    typed=store.add_evidence(actor,sid,uid(),{k:v for k,v in note(sid).items() if k!='title'} | {'evidence_schema_version':'2'})
    assert store.list_evidence(actor,sid,[('legacy_scope','null')])['data']==[legacy]
    assert store.list_evidence(actor,sid,[('scope_kind','study')])['data']==[v2,typed]
    original=rows(store,'evidence')
    store.revise_evidence(actor,sid,typed['evidence_id'],uid(),typed['evidence_version_id'],note(sid))
    assert rows(store,'evidence')[:len(original)]==original


def test_noncanonical_cursor_and_duplicate_query_rejected(env):
    store,actor,sid=env
    for _ in range(2):store.add_evidence(actor,sid,uid(),note(sid))
    cursor=store.list_evidence(actor,sid,[('limit','1')])['next_cursor']
    decoded=json.loads(base64.urlsafe_b64decode(cursor+'='*(-len(cursor)%4)))
    noncanonical=base64.urlsafe_b64encode(json.dumps(decoded,indent=2).encode()).decode().rstrip('=')
    nested=base64.urlsafe_b64encode(('['*750+'0'+']'*750).encode()).decode().rstrip('=')
    for query in [[('cursor',noncanonical)],[('cursor',nested)], [('limit','1'),('limit','2')],
                  [('limit','0')],[('limit','101')],[('view','bad')],[('scope_kind','model_revision'),('model_revision_id',uid())]]:
        with pytest.raises(DomainError,match='invalid_request'):store.list_evidence(actor,sid,query)


def test_revision_replay_rechecks_current_membership_and_route(env):
    store,actor,sid=env
    first=store.add_evidence(actor,sid,uid(),note(sid));command=uid();saved=revise(env,first,command)
    second=store.add_evidence(actor,sid,uid(),note(sid))
    with pytest.raises(DomainError,match='command_payload_conflict'):
        store.revise_evidence(actor,sid,second['evidence_id'],command,first['evidence_version_id'],note(sid))
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=?',(sid,))
    with pytest.raises(DomainError,match='resource_not_found'):revise(env,first,command)
    assert store.path.is_file() and saved['parent_evidence_version_id']==first['evidence_version_id']


# ---- Store owns the exact evidence read and snapshot creation -------------------------

GOLDEN = json.loads((Path(__file__).resolve().parent / 'fixtures/identity_golden.json').read_bytes())


def tamper(store, version, change):
    """Out-of-band storage change; the application itself never updates evidence."""
    with store.connection(write=True) as db:
        db.execute('DROP TRIGGER IF EXISTS immutable_evidence_update')
        stored = json.loads(db.execute('SELECT payload FROM evidence WHERE evidence_version_id=?', (version,)).fetchone()[0])
        change(stored)
        db.execute('UPDATE evidence SET payload=? WHERE evidence_version_id=?', (json.dumps(stored), version))


def test_evidence_record_is_the_authorized_validated_identity_checked_exact_read(env):
    from hyprn_mvp_app.store import ForeignEvidence
    store, actor, sid = env
    first = store.add_evidence(actor, sid, uid(), note(sid))
    version = first['evidence_version_id']
    other = store.create_study(actor, uid(), 'Other')['study_id']
    with store.connection() as db:
        assert store.evidence_record(db, actor, sid, version) == first
        # Unknown to the application: absent, never an error.
        assert store.evidence_record(db, actor, sid, uid()) is None
        # Held by another study: never returned, a typed resource_not_found 404.
        with pytest.raises(ForeignEvidence) as error:
            store.evidence_record(db, actor, other, version)
        assert (error.value.code, error.value.status) == ('resource_not_found', 404)
        assert isinstance(error.value, DomainError) and error.value.data()['fields'] == []
        # Authorization precedes any disclosure, for known and unknown versions alike.
        for candidate in (version, uid()):
            with pytest.raises(DomainError) as error:
                store.evidence_record(db, uid(), sid, candidate)
            assert (error.value.code, error.value.status) == ('resource_not_found', 404)
            assert not isinstance(error.value, ForeignEvidence)
    # A detached record: mutating the result never changes the next read.
    with store.connection() as db:
        store.evidence_record(db, actor, sid, version)['content'] = 'Mutated'
        assert store.evidence_record(db, actor, sid, version) == first


@pytest.mark.parametrize('change,code,status', [
    (lambda row: row.update(study_id=uid()), 'reference_conflict', 409),
    (lambda row: row.update(evidence_version_id=uid()), 'reference_conflict', 409),
    (lambda row: row['resource_scope'].update(study_id=uid()), 'reference_conflict', 409),
    (lambda row: row.update(current_only_field='Current library text'), 'backend_unavailable', 503),
    (lambda row: row.pop('content'), 'backend_unavailable', 503),
])
def test_evidence_record_refuses_stored_integrity_failures(env, change, code, status):
    store, actor, sid = env
    first = store.add_evidence(actor, sid, uid(), note(sid))
    tamper(store, first['evidence_version_id'], change)
    with store.connection() as db:
        with pytest.raises(DomainError) as error:
            store.evidence_record(db, actor, sid, first['evidence_version_id'])
    assert (error.value.code, error.value.status) == (code, status)
    assert 'Exact observation' not in str(error.value) and error.value.data()['fields'] == []


def test_evidence_version_stays_the_as_stored_read(env):
    """The public stored-version read (GET, legacy consistency checks) is not re-validated;
    snapshot creation must use ``evidence_record``."""
    store, actor, sid = env
    first = store.add_evidence(actor, sid, uid(), note(sid))
    tamper(store, first['evidence_version_id'], lambda row: row.update(current_only_field='Current'))
    assert store.evidence_version(actor, sid, first['evidence_version_id']) == dict(first, current_only_field='Current')
    other = store.create_study(actor, uid(), 'Other')['study_id']
    for call in (lambda: store.evidence_version(actor, other, first['evidence_version_id']),
                 lambda: store.evidence_version(actor, sid, uid())):
        with pytest.raises(DomainError) as error: call()
        assert (error.value.code, error.value.status) == ('resource_not_found', 404)


@pytest.mark.parametrize('case', GOLDEN['evidence_snapshots'], ids=lambda case: case['name'])
def test_evidence_snapshot_bytes_per_schema_and_legacy_configuration_projection(case):
    from hyprn_mvp_app.store import evidence_snapshot
    record = case['record']
    original = copy.deepcopy(record)
    snapshot = evidence_snapshot(record)
    assert canonical(snapshot) == base64.b64decode(case['snapshot_base64']) and digest(snapshot) == case['digest']
    legacy = evidence_snapshot(record, legacy_configuration=True)
    # Configuration 1/2 never retain a whole EvidenceRecord3: the four common fields
    # (plus the EvidenceRecord2 scope fields), exactly the former inline projection.
    expected = {k: record[k] for k in ('evidence_version_id', 'kind', 'content', 'source_refs')}
    if record.get('evidence_schema_version') == '2':
        expected.update({k: record[k] for k in ('evidence_schema_version', 'resource_scope')})
    assert canonical(legacy) == canonical(expected)
    if record.get('evidence_schema_version') != '3':
        assert canonical(legacy) == canonical(snapshot)
    for value in (snapshot, legacy):
        value['source_refs'].append('Mutated')
    assert record == original
