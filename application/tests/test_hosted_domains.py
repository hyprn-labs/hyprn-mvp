"""The complete public application retains private scientific history on PostgreSQL."""

from test_hosted_postgres import hosted, live_api, headers
import httpx
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.database import Connection, DatabaseConflict, DatabasePermissionDenied, actor_scope
from hyprn_mvp_app.store import Store


def uid():
    return str(uuid4())


def study(store, actor):
    with actor_scope(actor):
        return store.create_study(actor, uid(), 'Private scientific history')['study_id']


def test_complete_application_exposes_scientific_routes(hosted):
    _, store, accounts = hosted
    with live_api(store) as origin:
        response = httpx.get(origin + '/api/1/studies/00000000-0000-4000-8000-000000000001/brief',
                             headers=headers(accounts[0], origin))
        assert response.status_code == 404
        assert store.schema_profile == 'full'


def test_every_domain_table_is_explicitly_migrated(hosted):
    fixture, _, _ = hosted
    from hyprn_mvp_app.database import Connection
    raw = fixture['admin'].connect()
    try:
        names = {row['tablename'] for row in Connection(raw).execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        assert {
            'evidence', 'configurations', 'run_associations', 'outbox',
            'computational_record_requests', 'study_brief_versions',
            'calculation_versions', 'model_explanation_versions', 'study_answer_versions',
            'agent_sessions', 'agent_actions', 'agent_attribution',
            'assistant_conversations', 'assistant_turns', 'assistant_events',
            'assistant_allowances', 'assistant_tool_results',
        } <= names
    finally:
        raw.close()


def test_http_saved_brief_replay_racing_revisions_and_foreign_reads(hosted):
    from test_brief_api import content
    _, store, accounts = hosted
    actor = accounts[0]['actor']
    sid = study(store, actor)
    with live_api(store) as origin:
        path = origin + '/api/1/studies/' + sid + '/brief'
        own, other = (headers(a, origin) for a in accounts)
        command = dict(command_id=uid(), expected_revision=None, content=content())
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda _: httpx.post(path + '/draft', headers=own, json=command), range(2)))
        assert [r.status_code for r in replies] == [200, 200], [r.text for r in replies]
        assert replies[0].json()['data'] == replies[1].json()['data']
        revision = replies[0].json()['data']['revision']
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda _: httpx.post(path + '/draft', headers=own,
                json=dict(command_id=uid(), expected_revision=revision, content=content())), range(2)))
        assert sorted(r.status_code for r in replies) == [200, 409], [r.text for r in replies]
        latest = next(r.json()['data'] for r in replies if r.status_code == 200)
        saved = httpx.post(path + '/versions', headers=own,
                          json=dict(command_id=uid(), expected_revision=latest['revision']))
        assert saved.status_code == 201, saved.text
        version = saved.json()['data']['version']
        exact = path + '/versions/' + version['brief_version_id']
        assert httpx.get(exact, headers=own).json()['data'] == version
        assert httpx.get(exact, headers=other).status_code == 404
        # A fresh application instance reads the exact saved object and timestamp.
    with live_api(store) as origin:
        result = httpx.get(origin + '/api/1/studies/' + sid + '/brief/versions/' + version['brief_version_id'],
                           headers=headers(accounts[0], origin))
        assert result.json()['data'] == version


def test_all_domain_rows_inherit_study_visibility_and_saved_bytes_are_immutable(hosted):
    from hyprn_mvp_app.assistant import records
    from hyprn_mvp_app.agent_runtime import journal
    from hyprn_mvp_app.agent_runtime.sessions import Sessions
    from hyprn_mvp_app.agent_tools.registry import REGISTRY
    fixture, store, accounts = hosted
    actor, foreign = (a['actor'] for a in accounts)
    sid = study(store, actor)
    ids = {name: uid() for name in ('evidence','family','config','config_family','run','calculation',
                                   'version','brief','answer','explanation','model','turn','request')}
    stamp = '{"exact":"µ, 1.000", "time":"2026-01-01T00:00:00.000Z"}'
    statements = [
        ('model_associations', (sid, ids['model'], uid())),
        ('evidence', (ids['evidence'], ids['family'], sid, stamp)),
        ('evidence_families', (ids['family'], sid, ids['evidence'])),
        ('configurations', (ids['config'], ids['config_family'], sid, stamp)),
        ('configuration_families', (ids['config_family'], sid, ids['config'])),
        ('run_associations', (ids['run'], sid, ids['config'], uid(), None, None, '2026-01-01T00:00:00Z')),
        ('outbox', (ids['run'], 'accepted_run', '{}')),
        ('study_brief_drafts', (sid, uid(), stamp)),
        ('study_brief_versions', (ids['brief'], sid, 1, stamp)),
        ('calculations', (ids['calculation'], sid)),
        ('calculation_versions', (ids['version'], ids['calculation'], sid, 1, stamp)),
        ('reference_marks', (ids['config'], sid, stamp)),
        ('model_explanation_drafts', (sid, ids['model'], uid(), stamp)),
        ('model_explanation_versions', (ids['explanation'], sid, ids['model'], uid(), 1, stamp)),
        ('study_answer_drafts', (sid, uid(), stamp)),
        ('study_answer_versions', (ids['answer'], sid, 1, stamp)),
        ('computational_record_requests', (ids['request'], sid, actor, 'preview', uid(), 'a'*64,
                                         '[]', None, None, 'queued', 0, '{}', None, None, None)),
    ]
    with actor_scope(actor):
        create_app(store, Auth(store, 'http://test'), None)
        with store.connection(write=True) as db:
            for table, values in statements:
                db.execute(f'INSERT INTO {table} VALUES({",".join("?" for _ in values)})', values)
            agent = store.ensure_agent_actor(db, actor, 'claude_managed', 'Assistant')
            grant = store.create_delegation(db, agent, sid, 'writer', {'read','draft','record','submit'}, time.time()+600)
        records.accept(store, actor, sid, ids['turn'], 'Private question', None)
        with store.connection(write=True) as db:
            records.save_event(db, sid, dict(id=uid(), type='private', value='private text'))
            db.execute('INSERT INTO assistant_allowances VALUES(?,?)', (ids['turn'], 100))
            db.execute('INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)', (sid, uid(), ids['turn'], '{}', 0, 'intended'))
        sessions = Sessions(store, Auth(store, 'http://test'), REGISTRY, {'HYPRN_MVP_AGENT_ENABLED': 'true'})
        handle = sessions.open(grant, dict(name='hyprn-claude-managed'), surface='claude_managed')
        journal.intend(store, dict(session_id=handle.session_id, delegation_id=grant['delegation_id'],
            study_id=sid, call_id=uid(), tool='list_studies', effect='read', args_sha256='a'*64), time.time())
        with store.connection(write=True) as db:
            db.execute('INSERT INTO agent_attribution VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (sid, 'brief_version', ids['brief'], ids['brief'], 'brief', uid(), agent, 'Assistant', actor,
                 '2026-01-01T00:00:00Z', 'Person'))
        tables = [t for t,_ in statements] + ['assistant_conversations','assistant_turns',
            'assistant_allowances','assistant_events','assistant_tool_results','agent_sessions','agent_actions','agent_attribution']
        with store.connection() as db:
            for table in tables:
                assert db.execute('SELECT * FROM ' + table).fetchall(), table
    with actor_scope(foreign):
        with store.connection() as db:
            for table in tables:
                assert db.execute('SELECT * FROM ' + table).fetchall() == [], table
    with store.connection() as db:
        for table in tables:
            assert db.execute('SELECT * FROM ' + table).fetchall() == [], table
    immutable = ['evidence','configurations','study_brief_versions','calculation_versions',
                 'model_explanation_versions','study_answer_versions']
    for table in immutable:
        for mutation in (f"UPDATE {table} SET payload='changed'", f'DELETE FROM {table}'):
            raw = fixture['admin'].connect()
            try:
                with pytest.raises(DatabaseConflict):
                    Connection(raw).execute(mutation)
                raw.rollback()
                assert stamp in [r['payload'] for r in Connection(raw).execute('SELECT payload FROM ' + table)]
            finally:
                raw.close()
    # Live delegated visibility is intersected with current membership on every statement.
    with actor_scope(agent):
        with store.connection() as db:
            assert db.execute('SELECT * FROM evidence').fetchall()
        created = store.create_study(agent, uid(), 'Delegated creation', delegation_id=grant['delegation_id'])
        with store.connection() as db:
            assert db.execute('SELECT * FROM studies WHERE study_id=?', (created['study_id'],)).fetchall() == []
            assert db.execute('SELECT * FROM memberships WHERE study_id=? AND actor_id=?',
                              (created['study_id'], agent)).fetchall() == []
    with actor_scope(actor):
        assert store.study(actor, created['study_id'])['name'] == 'Delegated creation'
    raw = fixture['admin'].connect()
    try:
        Connection(raw).execute('DELETE FROM memberships WHERE study_id=?', (sid,))
        raw.commit()
    finally:
        raw.close()
    with actor_scope(agent):
        with store.connection() as db:
            for table in tables:
                assert db.execute('SELECT * FROM ' + table).fetchall() == [], table


def test_background_purpose_is_explicit_and_cannot_read_scientific_rows(hosted):
    fixture, store, accounts = hosted
    for purpose in ('assistant', 'dispatcher'):
        worker = Store.postgres(fixture['request'], fixture['auth'], background=fixture[purpose])
        with pytest.raises(DatabasePermissionDenied):
            with worker.database.background_connection() as db:
                db.execute('SELECT * FROM evidence')
        permitted = 'assistant' if purpose == 'assistant' else 'calculation_estimate'
        assert isinstance(worker.background_jobs(permitted), list)
        forbidden = 'run' if purpose == 'assistant' else 'assistant'
        with pytest.raises(DatabasePermissionDenied):
            worker.background_jobs(forbidden)
    unconfigured = Store.postgres(fixture['request'], fixture['auth'])
    with pytest.raises(DatabasePermissionDenied):
        unconfigured.background_jobs('assistant')


def test_public_scientific_lists_and_every_foreign_study_get_route(hosted):
    import re
    from calculation_fixture import seed
    from test_calculations_api import body
    _, store, accounts = hosted
    actor = accounts[0]['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
    with live_api(store) as origin:
        own = headers(accounts[0], origin)
        path = origin + '/api/1/studies/' + sid
        saved = httpx.post(path + '/calculations', headers=own,
                          json=dict(command_id=uid(), content=body(sample)))
        assert saved.status_code == 201, saved.text
        for action in ('set', 'clear'):
            marked = httpx.post(path + '/reference-marks', headers=own, json=dict(command_id=uid(),
                configuration_revision_id=sample['config']['configuration_revision_id'], action=action))
            assert marked.status_code == 200, marked.text
            visible = httpx.get(path + '/reference-marks', headers=own,
                                params={'model_id': sample['config']['model_id']})
            assert visible.status_code == 200, visible.text
            expected = [marked.json()['data']['mark']] if action == 'set' else []
            assert visible.json()['data']['items'] == expected
        for suffix in ('/calculations', '/configuration-summaries', '/configurations', '/runs', '/evidence'):
            result = httpx.get(path + suffix, headers=own)
            assert result.status_code == 200, (suffix, result.text)
        app = create_app(store, Auth(store, origin), None)
        count = 0
        for route in app.routes:
            if 'GET' not in getattr(route, 'methods', ()) or '{study_id}' not in route.path:
                continue
            resource = route.path.replace('{study_id}', sid)
            resource = re.sub(r'\{[^}]+\}', uid(), resource)
            response = httpx.get(origin + resource, headers=headers(accounts[1], origin))
            assert response.status_code in (400, 403, 404, 422), (resource, response.status_code, response.text)
            count += 1
        assert count >= 35


def test_dispatcher_discovers_then_processes_one_actor_scoped_prediction(hosted):
    from hyprn_mvp_app.calculation_exploration import CalculationExploration
    fixture, store, accounts = hosted
    worker = Store.postgres(fixture['request'], fixture['auth'], background=fixture['dispatcher'])
    command, actor = uid(), accounts[0]['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        store.command(actor, sid, 'calculation_prediction', command, {}, lambda db: {},
            receipt_state='pending_remote', request=dict(deadline=time.time()+60,
                numerical=dict(identity='synthetic'), runtime=dict(identity='captured')))

    class Numerical:
        def surrogate(self, request, runtime):
            # The adapter receives the exact persisted request; no production execution.
            assert request == dict(identity='synthetic')
            assert runtime == dict(identity='captured')
            with worker.connection() as db:
                assert {r['actor_id'] for r in db.execute('SELECT * FROM receipts')} == {actor}
            return dict(values=[0.0, 7.25])

    assert CalculationExploration(worker).process_one(Numerical())
    with actor_scope(actor):
        receipt = store.receipt(actor, sid, 'calculation_prediction', command)
        assert receipt['state'] == 'committed'
        assert receipt['result'] == dict(values=[0.0, 7.25])
    with worker.connection() as db:
        assert db.execute('SELECT * FROM receipts').fetchall() == []


def test_saved_run_names_and_light_status_are_readable_on_postgres(hosted):
    from calculation_fixture import seed
    _, store, accounts = hosted
    actor = accounts[0]['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
        run = sample['submit']()
    with live_api(store) as origin:
        base = origin + '/api/1/studies/' + sid
        for suffix in ('/runs', '/run-status?run_id=' + run['run_id']):
            result = httpx.get(base + suffix, headers=headers(accounts[0], origin))
            assert result.status_code == 200, result.text
            assert run['run_id'] in result.text
            assert sample['config']['name'] in result.text
            foreign = httpx.get(base + suffix, headers=headers(accounts[1], origin))
            assert foreign.status_code == 404, foreign.text


def test_assistant_restart_uses_real_delegated_api_and_retains_one_message(hosted):
    import asyncio
    from test_assistant_conversation import Provider, Settings, NoModeling
    from hyprn_mvp_app.agent_runtime.delegations import ROLE_EFFECTS
    from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, REGISTRY
    from hyprn_mvp_app.contracts import digest
    from hyprn_mvp_app.assistant import records
    _, store, accounts = hosted
    actor = accounts[0]['actor']
    sid = study(store, actor)
    origin = 'http://127.0.0.1:18001'
    app = create_app(store, Auth(store, origin), NoModeling(), environ={'HYPRN_MVP_AGENT_ENABLED': 'true'})
    owner = app.state.assistant
    owner.provider = provider = Provider()
    owner.settings = Settings(store.artifact_root / 'unused-key', 'agent_test', 1, 'env_test', 100, 200,
        digest(REGISTRY.definitions('claude_managed', LOCAL_STAGE, ROLE_EFFECTS['writer'])))
    command = uid()
    # Persist acceptance, then start recovery outside any request identity scope.
    with actor_scope(actor):
        records.accept(store, actor, sid, command, 'Read the saved study.', owner.settings)

    async def drained():
        # Real PostgreSQL connections cross the fixture's container boundary.
        deadline = time.monotonic() + 20
        while owner._tasks and time.monotonic() < deadline:
            await asyncio.sleep(0.03)
        assert not owner._tasks, 'The persisted conversation did not settle'

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin,
                                     headers=headers(accounts[0], origin)) as client:
            await owner.start()
            await drained()
            base = '/api/1/studies/' + sid + '/assistant'
            result = await client.get(base)
            assert result.status_code == 200, result.text
            assert result.json()['data']['state'] == 'idle', result.text
            assert provider.results[0]['ok'], provider.results
            assert result.json()['data']['messages'][-1]['text'] == 'Read confirmed.'
            repeat = await client.post(base + '/messages', json=dict(command_id=command, text='Read the saved study.'))
            assert repeat.status_code == 202, repeat.text
            await drained()
            assert len(provider.sent) == 1
            foreign = await client.get(base, headers=headers(accounts[1], origin))
            assert foreign.status_code == 404
        await owner.close()

    asyncio.run(exercise())


def test_aborted_migration_is_atomic_and_partial_schema_refuses_startup(hosted, tmp_path, monkeypatch):
    from dataclasses import replace
    from hyprn_mvp_app import migrations
    fixture, _, _ = hosted
    name = 'aborted_' + uuid4().hex
    raw = fixture['admin'].connect()
    raw.autocommit = True
    try:
        Connection(raw).execute('CREATE DATABASE ' + name)
    finally:
        raw.close()
    admin = replace(fixture['admin'], database=name)
    migration = replace(fixture['migration'], database=name)
    request = replace(fixture['request'], database=name)
    auth = replace(fixture['auth'], database=name)
    raw = admin.connect()
    try:
        Connection(raw).execute('GRANT CREATE ON SCHEMA public TO hyprn_migration')
        raw.commit()
    finally:
        raw.close()
    good = migrations.MIGRATIONS
    bad = tmp_path / '0002_domains.sql'
    bad.write_text(good[1].read_text() + '\nSELECT deliberately_missing_migration_function();')
    monkeypatch.setattr(migrations, 'MIGRATIONS', (good[0], bad))
    with pytest.raises(Exception):
        migrations.initialize(migration)
    raw = admin.connect()
    try:
        assert Connection(raw).execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall() == []
    finally:
        raw.close()
    monkeypatch.setattr(migrations, 'MIGRATIONS', (good[0],))
    migrations.initialize(migration)
    monkeypatch.setattr(migrations, 'MIGRATIONS', good)
    with pytest.raises(ValueError, match='incompatible'):
        Store.postgres(request, auth)
    # Adding a derived fingerprint preserves existing payload bytes exactly.
    from hashlib import sha256

    monkeypatch.setattr(migrations, 'MIGRATIONS', good[:-1])
    migrations.initialize(migration)
    retained = '{"retained": "λ", "value": 1.000} \n'
    rid = uid()
    raw = admin.connect()
    try:
        db = Connection(raw)
        actor, sid, config = uid(), uid(), uid()
        db.execute('INSERT INTO users(actor_id,username) VALUES(?,?)', (actor, actor))
        db.execute('INSERT INTO studies(study_id,revision,name,description,boundary,owner_actor_id) '
                   'VALUES(?,?,?,?,?,?)', (sid, uid(), 'Retained', '', '', actor))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (config, uid(), sid, '{}'))
        db.execute('INSERT INTO run_associations VALUES(?,?,?,?,?,?,?)',
                   (rid, sid, config, uid(), None, None, '2026-01-01T00:00:00Z'))
        db.execute('INSERT INTO outbox VALUES(?,?,?)', (rid, 'recorded', retained))
        raw.commit()
    finally:
        raw.close()
    monkeypatch.setattr(migrations, 'MIGRATIONS', good)
    migrations.initialize(migration)
    raw = admin.connect()
    try:
        row = Connection(raw).execute(
            'SELECT payload,payload_sha256 FROM outbox WHERE run_id=?', (rid,)
        ).fetchone()
        assert row == dict(payload=retained, payload_sha256=sha256(retained.encode()).hexdigest())
    finally:
        raw.close()
    assert Store.postgres(request, auth).schema_profile == 'full'


def test_background_roles_cannot_inherit_each_others_authority(hosted):
    fixture, _, _ = hosted
    raw = fixture['admin'].connect()
    try:
        db = Connection(raw)
        db.execute('GRANT hyprn_assistant_background TO hyprn_dispatcher_background')
        raw.commit()
        with pytest.raises(ValueError, match='purpose function access'):
            Store.postgres(fixture['request'], fixture['auth'], background=fixture['dispatcher'])
    finally:
        db.execute('REVOKE hyprn_assistant_background FROM hyprn_dispatcher_background')
        raw.commit()
        raw.close()


def test_reader_grant_never_becomes_writer_and_accepted_inputs_never_change(hosted):
    _, store, accounts = hosted
    owner, reader = (a['actor'] for a in accounts)
    sid = study(store, owner)
    cid, rid = uid(), uid()
    with actor_scope(owner):
        current = store.study(owner, sid)
        store.set_membership(owner, sid, uid(), current['revision'], reader, 'reader')
        with store.connection(write=True) as db:
            db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (cid, uid(), sid, '{}'))
            db.execute('INSERT INTO run_associations VALUES(?,?,?,?,?,?,?)', (rid, sid, cid, uid(), None, None, None))
            db.execute('INSERT INTO outbox VALUES(?,?,?)', (rid, 'accepted_run', json.dumps(dict(actor=owner,
                frozen=dict(exact=1.0), request=dict(command=uid())))))
        with pytest.raises(DatabaseConflict):
            with store.connection(write=True) as db:
                db.execute('UPDATE outbox SET payload=? WHERE run_id=?', ('{}', rid))
    with actor_scope(reader):
        assert store.study(reader, sid)['study_id'] == sid
        with pytest.raises(DatabasePermissionDenied):
            with store.connection(write=True) as db:
                db.execute('INSERT INTO evidence VALUES(?,?,?,?)', (uid(), uid(), sid, '{}'))
    with actor_scope(owner):
        current = store.study(owner, sid)
        store.set_membership(owner, sid, uid(), current['revision'], reader, None)
    with actor_scope(reader):
        with store.connection() as db:
            assert db.execute('SELECT * FROM configurations WHERE study_id=?', (sid,)).fetchall() == []


def test_revoked_delegation_cannot_create_a_study_through_raw_request_sql(hosted):
    fixture, store, _ = hosted
    # No other test's live delegation may supply this actor's authority.
    owner = uid()
    raw = fixture['admin'].connect()
    try:
        Connection(raw).execute('INSERT INTO users(actor_id,username) VALUES(?,?)', (owner, owner))
        raw.commit()
    finally:
        raw.close()
    sid = study(store, owner)
    with actor_scope(owner):
        with store.connection(write=True) as db:
            agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Assistant')
            grant = store.create_delegation(db, agent, sid, 'writer', {'read', 'record'}, time.time() + 600)
            assert store.revoke_delegation(db, grant['delegation_id'], 'revoked')
    with actor_scope(agent):
        with store.connection() as db:
            assert db.execute('SELECT hyprn_human() AS human,hyprn_actor() AS actor').fetchone() == dict(human=owner, actor=agent)
            assert db.execute('SELECT * FROM agent_delegations').fetchall() == []
        with pytest.raises(DatabasePermissionDenied):
            with store.connection(write=True) as db:
                db.execute('INSERT INTO studies(study_id,revision,name,description,boundary) VALUES(?,?,?,?,?)',
                           (uid(), uid(), 'Revoked delegation', '', ''))


def test_dispatcher_skips_invisible_delegated_runs_without_stopping_other_work(hosted):
    """A queued identity is not permission to read or run after delegation ends."""
    from calculation_fixture import seed
    from hyprn_mvp_app.contracts import DomainError
    from hyprn_mvp_app.execution import Submissions

    fixture, store, accounts = hosted
    owner = accounts[0]['actor']
    sid = study(store, owner)
    with actor_scope(owner):
        with store.connection(write=True) as db:
            agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Assistant')
            grant = store.create_delegation(
                db, agent, sid, 'writer', {'read', 'draft', 'record', 'submit'},
                time.time() + 600,
            )
    with actor_scope(agent):
        sample = dict(store=store, actor=agent, sid=sid)
        sample.update(seed(sample))
        blocked = [sample['submit']()['run_id'] for _ in range(2)]
    with actor_scope(owner):
        allowed = Submissions(store, None, None).submit(owner, sid, dict(
            command_id=uid(), configuration_revision_id=sample['config']['configuration_revision_id'],
        ))['run_id']
        with store.connection(write=True) as db:
            store.revoke_delegation(db, grant['delegation_id'], 'owner_revoked')
    worker = Store.postgres(fixture['request'], fixture['auth'],
                            artifact_root=store.artifact_root, background=fixture['dispatcher'])
    prepared = []

    class Native:
        def require_attestation(self):
            pass

    def prepare(actor, study_id, command_id, frozen):
        prepared.append(actor)
        raise DomainError('modeling_unavailable', 503)

    service = Submissions(worker, prepare, Native())
    service.dispatch_batch(blocked + [allowed])
    service.dispatch(blocked[0])
    assert prepared == [owner]
    with actor_scope(owner):
        with store.connection() as db:
            assert {r['state'] for r in db.execute(
                'SELECT o.state FROM outbox o JOIN run_associations r USING(run_id) '
                'WHERE r.study_id=?', (sid,),
            )} == {'accepted_run'}
        with store.connection(write=True) as db:
            store.create_delegation(db, agent, sid, 'writer',
                                    {'read', 'draft', 'record', 'submit'}, time.time() + 600)
    # Only a fresh authorized grant allows the original pending requests to proceed.
    service.dispatch_batch(blocked)
    assert prepared == [owner, agent, agent]


def test_run_summaries_keep_pagination_status_and_privacy_with_large_artifacts(hosted):
    from calculation_fixture import seed
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner, foreign = (a['actor'] for a in accounts)
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        runs = [sample['record']([1.0, 2.0]) for _ in range(3)]
        ids = [r if isinstance(r, str) else r['run_id'] for r in runs]
        # Summary reads must not return unrelated retained artifact contents.
        with store.connection(write=True) as db:
            for rid in ids:
                row = db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()
                payload = json.loads(row['payload'])
                payload['summary_read_fixture'] = 'x' * (2 * 1024 * 1024)
                db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(payload), rid))
        history = History(store)
        listed = history.list(owner, sid)
        assert [r['run_id'] for r in listed] == ids
        assert all(r['execution_summary']['status'] == 'completed' for r in listed)
        page, cursor = history.list_page(owner, sid, limit=2)
        assert page == listed[:2] and cursor == ids[1]
        page, cursor = history.list_page(owner, sid, limit=2, cursor=cursor)
        assert page == listed[2:] and cursor is None
        statuses = history.status(owner, sid, ids[::-1])
        assert [r['run_id'] for r in statuses] == ids[::-1]
        assert len(json.dumps(listed)) < 10000
    with actor_scope(foreign):
        with pytest.raises(Exception) as refused:
            History(store).list(foreign, sid)
        assert getattr(refused.value, 'code', None) == 'resource_not_found'


def test_retained_witness_checks_every_byte_without_reloading_artifacts(hosted, monkeypatch):
    from calculation_fixture import seed
    from hyprn_mvp_app.contracts import DomainError
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner, foreign = (a['actor'] for a in accounts)
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        rid = sample['record']([1.0, 2.0])
        rid = rid if isinstance(rid, str) else rid['run_id']
        # PostgreSQL owns this exact-byte fingerprint; callers cannot forge it.
        from hashlib import sha256

        with store.connection() as db:
            row = db.execute(
                'SELECT payload,payload_sha256 FROM outbox WHERE run_id=?', (rid,)
            ).fetchone()
            assert row['payload_sha256'] == sha256(row['payload'].encode('utf-8')).hexdigest()
        with pytest.raises(Exception), store.connection(write=True) as db:
            db.execute('UPDATE outbox SET payload_sha256=? WHERE run_id=?', ('0' * 64, rid))
        service = History(store)
        retained = service.retained(owner, sid, rid)
        assert 'row_fingerprint' in retained.token
        monkeypatch.setattr(service, 'run_row', lambda *a, **k: pytest.fail('Reloaded full payload'))
        with store.connection() as db:
            service.recheck(db, owner, sid, [retained.token])
        # Whitespace and non-ASCII changes invalidate the exact-byte witness.
        with store.connection(write=True) as db:
            updated = dict(json.loads(row['payload']), witness_fixture='λ')
            db.execute('UPDATE outbox SET payload=? WHERE run_id=?',
                       (json.dumps(updated, ensure_ascii=False) + ' \n', rid))
        with store.connection() as db:
            changed = db.execute(
                'SELECT payload,payload_sha256 FROM outbox WHERE run_id=?', (rid,)
            ).fetchone()
            assert changed['payload_sha256'] == sha256(changed['payload'].encode('utf-8')).hexdigest()
            assert changed['payload_sha256'] != row['payload_sha256']
        with store.connection() as db, pytest.raises(DomainError) as refused:
            service.recheck(db, owner, sid, [retained.token])
        assert refused.value.code == 'reference_conflict'
    with actor_scope(foreign), store.connection() as db, pytest.raises(DomainError) as refused:
        service.recheck(db, foreign, sid, [retained.token])
    assert refused.value.code == 'resource_not_found'


def test_parallel_retained_reads_preserve_actor_scope_order_and_results(hosted, monkeypatch):
    from calculation_fixture import seed
    from hyprn_mvp_app.calculation_exploration import _retained_many
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner, foreign = (a['actor'] for a in accounts)
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        runs = [sample['record']([float(n), 2.0]) for n in range(6)]
        ids = [r if isinstance(r, str) else r['run_id'] for r in runs]
        history = History(store)
        read, calls = history.retained, []
        def tracked(*args):
            calls.append(args[-1])
            return read(*args)
        monkeypatch.setattr(history, 'retained', tracked)
        pending = _retained_many(history, owner, sid, ids)
        first = next(pending)
        assert len(calls) <= 4
        records = [first, *pending]
        assert [r.token['run_id'] for r in records] == ids
        assert [r.history['results']['outputs'][0]['value'] for r in records] == list(range(6))
    with actor_scope(foreign), pytest.raises(Exception) as refused:
        list(_retained_many(History(store), foreign, sid, ids))
    assert getattr(refused.value, 'code', None) == 'resource_not_found'


def test_retained_projection_survives_reader_restart_and_rechecks_sources(hosted, monkeypatch):
    from calculation_fixture import seed
    from hyprn_mvp_app.contracts import DomainError
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner, foreign = (a['actor'] for a in accounts)
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        rid = sample['record']([1.0, 2.0])
        rid = rid if isinstance(rid, str) else rid['run_id']
        first = History(store).retained_projection(owner, sid, rid)
        reader = History(store)
        monkeypatch.setattr(reader, 'retained', lambda *a, **k: pytest.fail('Reloaded archive'))
        second = reader.retained_projection(owner, sid, rid)
        assert second == first
        with store.connection(write=True) as db:
            db.execute("UPDATE outbox SET payload=payload||' ' WHERE run_id=?", (rid,))
        with pytest.raises(DomainError) as refused:
            reader.retained_projection(owner, sid, rid)
        assert refused.value.code == 'reference_conflict'
    with actor_scope(foreign), pytest.raises(DomainError) as refused:
        History(store).retained_projection(foreign, sid, rid)
    assert refused.value.code == 'resource_not_found'


def test_corrupt_projection_cache_is_rebuilt_from_original_bytes(hosted, monkeypatch):
    from calculation_fixture import seed
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner = accounts[0]['actor']
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        rid = sample['record']([1.0, 2.0])
        rid = rid if isinstance(rid, str) else rid['run_id']
        reader = History(store)
        expected = reader.retained_projection(owner, sid, rid)
        with store.connection(write=True) as db:
            db.execute("UPDATE retained_read_cache SET payload='{}' WHERE run_id=?", (rid,))
        calls = []
        original = reader.retained
        def tracked(*args):
            calls.append(args[-1])
            return original(*args)
        monkeypatch.setattr(reader, 'retained', tracked)
        assert reader.retained_projection(owner, sid, rid) == expected
        assert calls == [rid]


def test_changed_admission_code_revalidates_cached_projection(hosted, monkeypatch):
    from calculation_fixture import seed
    from hyprn_mvp_app import history

    _, store, accounts = hosted
    owner = accounts[0]['actor']
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        rid = sample['record']([1.0, 2.0])
        rid = rid if isinstance(rid, str) else rid['run_id']
        reader = history.History(store)
        expected = reader.retained_projection(owner, sid, rid)
        calls, original = [], reader.retained
        def tracked(*args):
            calls.append(args[-1])
            return original(*args)
        monkeypatch.setattr(reader, 'retained', tracked)
        monkeypatch.setattr(history, '_reader_identity', lambda: 'a' * 64)
        assert reader.retained_projection(owner, sid, rid) == expected
        assert calls == [rid]


def test_public_run_reader_reuses_verified_projection_without_archive_reads(hosted, monkeypatch):
    from calculation_fixture import seed
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner = accounts[0]['actor']
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        rid = sample['record']([1.0, 2.0])
        rid = rid if isinstance(rid, str) else rid['run_id']
    with live_api(store) as origin:
        path = origin + '/api/1/studies/' + sid + '/runs/' + rid
        own = headers(accounts[0], origin)
        first = httpx.get(path, headers=own)
        assert first.status_code == 200, first.text
        from hyprn_mvp_app.calculations import Analyses
        from test_calculations_api import body
        with actor_scope(owner):
            History(store).retained_projection(owner, sid, rid)
            analyses = Analyses(store)
            version = analyses.create(owner, sid, dict(command_id=uid(), content=body(sample)))
            expected_runs = analyses.runs(owner, sid, version['calculation_version_id'])
        monkeypatch.setattr(History, '_read_saved',
                            lambda *a, **k: pytest.fail('Reopened verified archive'))
        second = httpx.get(path, headers=own)
        assert second.status_code == 200, second.text
        assert second.json()['data'] == first.json()['data']
        with actor_scope(owner):
            assert analyses.runs(owner, sid, version['calculation_version_id']) == expected_runs
        assert httpx.get(path, headers=headers(accounts[1], origin)).status_code == 404


def test_run_listing_projection_is_database_maintained_from_exact_payload(hosted):
    from calculation_fixture import seed
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    owner = accounts[0]['actor']
    sid = study(store, owner)
    with actor_scope(owner):
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        rid = sample['record']([1.0, 2.0])
        rid = rid if isinstance(rid, str) else rid['run_id']
        with store.connection() as db:
            row = db.execute('SELECT payload,read_summary::text AS summary '
                             'FROM outbox WHERE run_id=?', (rid,)).fetchone()
        source, summary = json.loads(row['payload']), json.loads(row['summary'])
        assert 'bundle' not in summary and 'frozen' not in summary
        assert summary['status'] == source.get('status')
        assert summary['history']['results'] == source['history']['results']
        expected = History(store).list_page(owner, sid)[0]
        assert expected[0]['state'] == 'recorded'
        with store.connection(write=True) as db:
            source.setdefault('status', {})['process_state'] = 'excepted'
            db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(source), rid))
        with store.connection() as db:
            changed = db.execute('SELECT read_summary::text AS summary FROM outbox '
                                 'WHERE run_id=?', (rid,)).fetchone()
        assert json.loads(changed['summary'])['status']['process_state'] == 'excepted'
        with pytest.raises(Exception), store.connection(write=True) as db:
            db.execute("UPDATE outbox SET read_summary='{}'::jsonb WHERE run_id=?", (rid,))


def test_user_spending_crosses_studies_without_crossing_accounts_on_postgres(hosted):
    import asyncio
    from hyprn_mvp_app.assistant import allowance, records
    from hyprn_mvp_app.assistant.claude import ProviderError
    _, store, accounts = hosted
    subjects = [a['actor'] for a in accounts]
    sids = [study(store, subjects[i]) for i in (0, 0, 1)]
    for index, sid in enumerate(sids):
        actor = subjects[0 if index < 2 else 1]
        with actor_scope(actor):
            records.accept(store, actor, sid, uid(), 'Synthetic accounting record.', None)
            with store.connection(write=True) as db:
                records.update(db, sid, provider_id='cost_'+str(index), provision='accepted')
    class Costs:
        async def session_account(self, session):
            return {'spent_cents': {'cost_0':1900,'cost_1':150,'cost_2':30}.get(session,0),
                    'status':'idle'}
        async def find_session(self, correlation):
            return None
    async def exercise():
        with pytest.raises(ProviderError, match='user_allowance_exhausted'):
            await allowance.check(store, Costs(), subjects[0])
        assert (await allowance.check(store, Costs(), subjects[1]))[0] == 30
    asyncio.run(exercise())


def test_lifecycle_transition_does_not_rewrite_retained_bytes(hosted):
    from calculation_fixture import seed
    from hyprn_mvp_app.execution import Submissions
    from hyprn_mvp_app.history import History

    _, store, accounts = hosted
    actor = accounts[0]['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
        run = sample['submit']()
        with store.connection(write=True) as db:
            row = db.execute('SELECT payload FROM outbox WHERE run_id=?', (run['run_id'],)).fetchone()
            document = json.loads(row['payload'])
            document['retained_fixture'] = 'x' * (2 * 1024 * 1024)
            db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(document), run['run_id']))
        with store.connection() as db:
            before = db.execute('SELECT xmin::text AS revision,payload,payload_sha256 FROM outbox WHERE run_id=?',
                                (run['run_id'],)).fetchone()
        with store.connection(write=True) as db:
            Submissions(store, None, None)._state(db, sid, run['command_id'], run['run_id'], 'dispatching')
        with store.connection() as db:
            after = db.execute('SELECT xmin::text AS revision,payload,payload_sha256 FROM outbox WHERE run_id=?',
                               (run['run_id'],)).fetchone()
        assert after == before, 'Lifecycle transitions must never write the immutable payload row'
        assert History(store).submission_read(actor, sid, run['run_id'])['state'] == 'dispatching'


def test_public_run_restart_records_without_rewriting_prepared_document(hosted):
    import base64
    from execution_fixtures import fixture, runtime_fixture
    from hyprn_mvp_app.contracts import digest
    from hyprn_mvp_app.execution import Submissions, executable_digest

    fixture_db, store, accounts = hosted
    actor = accounts[0]['actor']
    sid = study(store, actor)
    case = fixture('chain')
    config = case['frozen']['configuration']
    config['study_id'] = sid
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    prepared = case['prepared']
    prepared['configuration_digest'] = config['digest']
    prepared['executable_content_digest'] = executable_digest(prepared)
    prepared['prepared_digest'] = digest({k: v for k, v in prepared.items() if k != 'prepared_digest'})
    with actor_scope(actor), store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',
                   (config['configuration_revision_id'], config['configuration_id'], sid, json.dumps(case['frozen'])))
    outputs = json.loads(case['files'][prepared['entrypoint']['bindings_path']])['outputs']

    class Native:
        launches = 0

        def require_attestation(self):
            return True

        def bundle_runtime(self):
            return runtime_fixture()

        def launch(self, bundle, request):
            self.launches += 1
            self.bundle, self.request = bundle, request
            self.association = dict(store_uuid=uid(), process_uuid=uid())
            return self.association

        def launch_budgeted(self, bundle, request, wall_seconds):
            return self.launch(bundle, request)

        def read_record(self, request, association):
            assert request == self.request and association == self.association
            results = dict(schema_version='1', run_id=request['run_id'], bundle_digest=request['bundle_digest'],
                execution=dict(state='finished', exit_code=0, message='Retained fixture'),
                convergence=dict(state='not_applicable', diagnostics_ref=None),
                optimization=dict(termination='not_applicable', feasibility='not_applicable'),
                completeness=dict(expected=len(outputs), available=len(outputs), failed=0, unavailable=0),
                outputs=[dict(target=o['target'], value=2.0, units=o['units'], availability='available',
                    reason=None, producer_completed=True, assigned=True) for o in outputs],
                criteria=[], applicability=dict(state='unassessed', evidence_refs=[]), artifacts=[])
            return dict(association, request=request, bundle=self.bundle, results=results,
                        assessment=None, artifacts={}, errors=[], process_state='finished', exit_status=0)

    native = Native()
    worker = Store.postgres(fixture_db['request'], fixture_db['auth'],
                            artifact_root=store.artifact_root, background=fixture_db['dispatcher'])
    body = dict(command_id=uid(), configuration_revision_id=config['configuration_revision_id'])
    try:
        with live_api(store) as origin:
            path = origin + '/api/1/studies/' + sid + '/runs'
            own = headers(accounts[0], origin)
            reply = httpx.post(path, headers=own, json=body)
            assert reply.status_code == 202, reply.text
            rid = reply.json()['data']['run_id']
            Submissions(worker, lambda *args: (prepared, case['files']), native).dispatch(rid, prepare_only=True)
            with actor_scope(actor), store.connection() as db:
                original = db.execute('SELECT xmin::text AS revision,payload,payload_sha256 FROM outbox WHERE run_id=?', (rid,)).fetchone()
            # Restart uses precisely the original prepared command and bytes.
            Submissions(worker, None, native).dispatch(rid)
            result = httpx.get(path + '/' + rid, headers=own)
            assert result.status_code == 200, result.text
            assert result.json()['data']['state'] == 'recorded'
            assert [o['value'] for o in result.json()['data']['history']['results']['outputs']] == [2.0, 2.0]
            assert httpx.post(path, headers=own, json=body).json()['data']['run_id'] == rid
            assert httpx.get(path + '/' + rid, headers=headers(accounts[1], origin)).status_code == 404
            with actor_scope(actor), store.connection() as db:
                retained = db.execute('SELECT xmin::text AS revision,payload,payload_sha256 FROM outbox WHERE run_id=?', (rid,)).fetchone()
            assert retained == original
            document = json.loads(retained['payload'])
            assert document['request'] == native.request
            assert {p: base64.b64decode(b) for p, b in document['bundle']['files'].items()} == native.bundle['files']
            assert native.launches == 1
    finally:
        worker.database.close()


def test_admission_capacity_is_atomic_replayable_and_never_retains_busy_rejection(hosted):
    from calculation_fixture import seed
    from hyprn_mvp_app.contracts import DomainError
    from hyprn_mvp_app.execution import Submissions

    _, store, accounts = hosted
    actor = accounts[1]['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
    bodies = [dict(command_id=uid(), configuration_revision_id=sample['config']['configuration_revision_id']) for _ in range(2)]
    def accept(body):
        with actor_scope(actor):
            try:
                return Submissions(store, None, None).submit(actor, sid, body, admission_limit=1)
            except DomainError as error:
                assert error.status == 429
                return None
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(accept, bodies))
    assert sum(r is not None for r in replies) == 1
    admitted = next(i for i, r in enumerate(replies) if r is not None)
    assert accept(bodies[admitted])['run_id'] == replies[admitted]['run_id']
    with actor_scope(actor), store.connection() as db:
        assert store.command_receipt(db, sid, 'run', bodies[1-admitted]['command_id']) is None


def test_operational_queue_is_bounded_indexed_private_and_cursor_reachable(hosted, capsys):
    from calculation_fixture import seed

    fixture_db, store, accounts = hosted
    actor, foreign = (a['actor'] for a in accounts)
    sid = study(store, actor)
    with actor_scope(actor):
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
    raw = fixture_db['admin'].connect()
    try:
        db = Connection(raw)
        prefix = uid()
        db.execute("""INSERT INTO run_associations(run_id,study_id,configuration_revision_id,command_id)
            SELECT md5(? || i::text)::uuid::text,?,?,md5(? || 'command' || i::text)::uuid::text
            FROM generate_series(1,2000) i""", (prefix,sid,sample['config']['configuration_revision_id'],prefix))
        db.execute("""INSERT INTO outbox(run_id,state,payload)
            SELECT run_id,'recorded',? FROM run_associations WHERE study_id=?""", (json.dumps(dict(actor=actor)),sid))
        db.execute("""UPDATE execution_operations SET state='accepted_run' WHERE run_id IN
            (SELECT run_id FROM execution_operations WHERE study_id=? ORDER BY run_id LIMIT 3)""", (sid,))
        db.execute('ANALYZE execution_operations')
        plan = db.execute("""EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)
            SELECT study_id,actor_id,run_id FROM execution_operations
            WHERE state IN ('accepted_run','dispatching')
            AND (preparation_state IS NULL OR preparation_state<>'preparation_failed')
            ORDER BY run_id LIMIT 2""").fetchone()[0]
        raw.commit()
        plan_text = json.dumps(plan)
        assert 'execution_pending' in plan_text, plan_text
        quota_plan = db.execute("""EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)
            SELECT count(*) FROM execution_operations WHERE actor_id=?
            AND state IN ('accepted_run','dispatching','uncertain')
            AND (preparation_state IS NULL OR preparation_state<>'preparation_failed')""",
            (actor,)).fetchone()[0]
        assert 'execution_actor_pending' in json.dumps(quota_plan)
        db.execute("""INSERT INTO receipts(scope,category,command_id,actor_id,payload_digest,state)
            SELECT study_id,'analysis_execution',command_id,?,?,
                CASE WHEN row_number() OVER (ORDER BY command_id)<=3
                    THEN 'pending_remote' ELSE 'committed' END
            FROM run_associations WHERE study_id=?""",(actor,'a'*64,sid))
        db.execute('ANALYZE receipts')
        receipt_plan = db.execute("""EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)
            SELECT scope,actor_id,command_id FROM receipts WHERE category='analysis_execution'
            AND state='pending_remote' ORDER BY command_id LIMIT 2""").fetchone()[0]
        assert 'receipts_background_pending' in json.dumps(receipt_plan)
        raw.commit()
        worker = Store.postgres(fixture_db['request'],fixture_db['auth'],background=fixture_db['dispatcher'])
        try:
            seen = []
            actors_seen = set()
            after = None
            while True:
                page = worker.background_jobs('run',after=after,limit=2)
                if not page:
                    break
                assert len(page) <= 2 and len(json.dumps(page).encode()) < 1024
                assert all(set(row) == {'study_id','actor_id','work_id'} for row in page)
                seen.extend(row['work_id'] for row in page if row['study_id']==sid)
                actors_seen.update(row['actor_id'] for row in page)
                after = page[-1]['work_id']
            assert len(seen) == 3 and len(set(seen)) == 3
            assert {actor, foreign} <= actors_seen
            with pytest.raises(DatabasePermissionDenied), worker.database.background_connection() as background:
                background.execute('SELECT payload FROM execution_operations')
            with actor_scope(foreign), store.connection() as scoped:
                assert scoped.execute('SELECT * FROM execution_operations WHERE study_id=?',(sid,)).fetchall() == []
            with actor_scope(actor), pytest.raises(DatabaseConflict), store.connection(write=True) as scoped:
                scoped.execute('UPDATE execution_operations SET payload=? WHERE run_id=?',
                               ('{"frozen":{"replacement":true}}', seen[0]))
            with capsys.disabled():
                print('\nOperational discovery evidence: '+plan_text)
                print('Admission plan evidence: '+json.dumps(quota_plan))
                print('Receipt discovery evidence: '+json.dumps(receipt_plan))
        finally:
            worker.database.close()
            # This fixture's synthetic queue entries must not become another
            # test's executable analysis; pending receipts may finish once.
            db.execute("UPDATE receipts SET state='committed' WHERE scope=? "
                       "AND category='analysis_execution' AND state='pending_remote'", (sid,))
            raw.commit()
    finally:
        raw.close()


def test_analysis_authority_survives_expiry_and_is_finite_revocable_and_private(hosted):
    from calculation_fixture import seed, sibling
    from test_calculations_api import body
    from hyprn_mvp_app.analysis_execution import AnalysisExecution, identity
    from hyprn_mvp_app.calculations import Analyses
    from hyprn_mvp_app.contracts import DomainError
    from hyprn_mvp_app.execution import Submissions

    fixture, store, accounts = hosted
    owner, foreign = (a['actor'] for a in accounts)
    sid = study(store, owner)
    with actor_scope(owner):
        create_app(store, Auth(store, 'http://test'), None)
        sample = dict(store=store, actor=owner, sid=sid)
        sample.update(seed(sample))
        members = [sample['config']['configuration_revision_id'], sibling(sample, sample['frozen'])]
        version = Analyses(store).create(owner, sid, dict(command_id=uid(),
            content=body(sample, members=members, schema_version='4', estimate_plan=None)))
        with store.connection(write=True) as db:
            agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Assistant')
            grant = store.create_delegation(db, agent, sid, 'writer', {'read','record','submit'}, time.time()+600)
    vid = version['calculation_version_id']
    with actor_scope(agent):
        existing = Submissions(store, None, None).submit(agent, sid, dict(
            command_id=uid(), configuration_revision_id=members[0]))
        AnalysisExecution(store).launch(agent, sid, vid, {})
    raw = fixture['admin'].connect()
    try:
        Connection(raw).execute('UPDATE agent_delegations SET expires_at=? WHERE delegation_id=?',
                                (time.time()-1, grant['delegation_id']))
        raw.commit()
    finally:
        raw.close()
    worker = Store.postgres(fixture['request'], fixture['auth'], artifact_root=store.artifact_root,
                            background=fixture['dispatcher'])
    create_app(worker, Auth(worker, 'http://test'), None)
    # Ordinary SQL remains hidden after expiry; accepted scope is not a session.
    with actor_scope(agent), store.connection() as db:
        with pytest.raises(DomainError):
            store.authorize(db, agent, sid)
        assert db.execute('SELECT * FROM configurations WHERE study_id=?', (sid,)).fetchall() == []
    try:
        runner = AnalysisExecution(worker)
        assert runner.process_one(Submissions(worker, None, None))
        with actor_scope(owner):
            state = AnalysisExecution(store).read(owner, sid, vid)
            assert all(m['run_id'] for m in state['runs']), state
            assert state['runs'][0]['run_id'] == existing['run_id']
            assert state['runs'][0]['reused']
        with actor_scope(agent), worker.analysis_authority(agent, sid, identity(vid)):
            with pytest.raises(DomainError):
                worker.command(agent, sid, 'run', uid(), {}, lambda db: {})
            with pytest.raises(DatabasePermissionDenied):
                with worker.connection(write=True) as db:
                    db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (uid(),uid(),sid,'{}'))
            with pytest.raises(DatabaseConflict):
                with worker.connection(write=True) as db:
                    db.execute("UPDATE receipts SET request='{}' WHERE scope=? AND category='analysis_execution' AND command_id=?",
                               (sid,identity(vid)))
        with actor_scope(foreign), worker.analysis_scope(sid, identity(vid)), worker.connection() as db:
            assert db.execute('SELECT * FROM receipts WHERE scope=?', (sid,)).fetchall() == []
        # The child owner can still prepare already accepted work after session expiry.
        prepared = []
        class Native:
            def require_attestation(self):
                pass
        def prepare(actor, study_id, command, frozen):
            prepared.append(actor)
            raise DomainError('modeling_unavailable', 503)
        Submissions(worker, prepare, Native()).dispatch(state['runs'][0]['run_id'])
        assert prepared == [agent]
        with actor_scope(owner), store.connection(write=True) as db:
            store.revoke_delegation(db, grant['delegation_id'], 'owner_revoked')
        assert runner.process_one(Submissions(worker, None, None))
        with actor_scope(owner):
            assert AnalysisExecution(store).read(owner, sid, vid)['admission_state'] == 'revoked'
    finally:
        worker.database.close()


def isolated_analysis_account(fixture):
    from hyprn_mvp_app.auth import token_hash
    actor, token, csrf = uid(), uid(), uid()
    raw = fixture['admin'].connect()
    try:
        db = Connection(raw)
        db.execute('INSERT INTO users(actor_id,username) VALUES(?,?)', (actor, actor))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                   (token_hash(token), actor, token_hash(csrf), time.time()+600))
        raw.commit()
    finally:
        raw.close()
    return dict(actor=actor, token=token, csrf=csrf)


@pytest.mark.parametrize('interruption', [None, 'revoke', 'narrow', 'membership'])
def test_analysis_recovery_proves_continuity_and_preserves_frozen_work_on_postgres(hosted, interruption):
    from calculation_fixture import seed
    from test_calculations_api import agent_analysis, replace_analysis_grant, legacy_interrupted_analysis
    from hyprn_mvp_app.analysis_execution import AnalysisExecution, identity
    from hyprn_mvp_app.execution import Submissions
    fixture, store, accounts = hosted
    accounts = [isolated_analysis_account(fixture), accounts[1]]
    actor, foreign = (a['actor'] for a in accounts)
    sid = study(store, actor)
    with actor_scope(actor):
        create_app(store, Auth(store, 'http://test'), None)
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
    agent, grant, vid = agent_analysis(store, actor, sid, sample, 2)
    worker = Store.postgres(fixture['request'], fixture['auth'], artifact_root=store.artifact_root,
                            background=fixture['dispatcher'])
    create_app(worker, Auth(worker, 'http://test'), None)
    runner = AnalysisExecution(worker)
    try:
        for _ in range(3):
            replace_analysis_grant(store, actor, agent, sid)
        assert runner.process_one(Submissions(worker, None, None))
        with actor_scope(actor):
            progress = AnalysisExecution(store).read(actor, sid, vid)
            assert progress['state'] == 'calculating', progress
            assert sum(bool(r['run_id']) for r in progress['runs']) == 2
        request, failed = legacy_interrupted_analysis(store, actor, sid, vid)
        if interruption == 'membership':
            with actor_scope(actor), store.connection(write=True) as db:
                db.execute("UPDATE memberships SET role='reader' WHERE study_id=? AND actor_id=?", (sid, actor))
            raw = fixture['admin'].connect()
            try:
                Connection(raw).execute("UPDATE memberships SET role='owner' WHERE study_id=? AND actor_id=?", (sid, actor))
                raw.commit()
            finally:
                raw.close()
        elif interruption:
            replace_analysis_grant(store, actor, agent, sid,
                                   narrow=interruption == 'narrow', revoke=interruption == 'revoke')
        current_grant = replace_analysis_grant(store, actor, agent, sid)
        with actor_scope(actor), pytest.raises(DatabaseConflict):
            with store.connection(write=True) as db:
                db.execute("UPDATE receipts SET state='pending_remote' WHERE scope=? "
                           "AND category='analysis_execution' AND command_id=?", (sid, identity(vid)))
        with live_api(store) as origin:
            path = origin + '/api/1/studies/' + sid + '/analysis-versions/' + vid + '/execution'
            own, other = (headers(a, origin) for a in accounts)
            if interruption is None:
                with actor_scope(actor):
                    session = Auth(store, origin).mint_agent_session(current_grant['delegation_id'])
                own = headers(dict(token=session['token'], csrf=session['csrf_token']), origin)
            assert httpx.get(path + '/recovery', headers=other).status_code == 404
            recovery = httpx.get(path + '/recovery', headers=own)
            assert recovery.status_code == 200, recovery.text
            assert recovery.json()['data']['can_resume'] is (interruption is None), recovery.text
            assert httpx.post(path, headers=own, json={}).json()['data'] == failed
            command = dict(command_id=uid())
            if interruption:
                refused = httpx.post(path + '/resume', headers=own, json=command)
                assert refused.status_code == 409, refused.text
            else:
                with ThreadPoolExecutor(2) as pool:
                    replies = list(pool.map(lambda _: httpx.post(path + '/resume', headers=own, json=command), range(2)))
                assert [r.status_code for r in replies] == [202, 202], [r.text for r in replies]
                assert replies[0].json()['data'] == replies[1].json()['data']
                assert replies[0].json()['data']['runs'] == failed['runs']
                assert httpx.post(path + '/resume', headers=own, json=dict(command_id=uid())).status_code == 409
        with actor_scope(actor), store.connection() as db:
            saved = store.command_receipt(db, sid, 'analysis_execution', identity(vid))
            assert saved['request'] == request
            assert db.execute('SELECT count(*) FROM run_associations WHERE study_id=?', (sid,)).fetchone()[0] == 2
        if interruption is None:
            runner.process_one(Submissions(worker, None, None))
            with actor_scope(actor):
                progress = AnalysisExecution(store).read(actor, sid, vid)
                assert progress['runs'] == failed['runs']
                assert progress['admission_state'] == 'ready'
                AnalysisExecution(store).cancel(actor, sid, vid)
    finally:
        worker.database.close()


def test_recovery_reconciles_uncertain_unprojected_child_on_postgres(hosted):
    from calculation_fixture import seed
    from test_calculations_api import interrupted_analysis_with_unprojected_uncertain_child
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    fixture, store, accounts = hosted
    accounts = [isolated_analysis_account(fixture), accounts[1]]
    actor = accounts[0]['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        create_app(store, Auth(store, 'http://test'), None)
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
    vid, run_id = interrupted_analysis_with_unprojected_uncertain_child(store, actor, sid, sample)
    with live_api(store) as origin:
        path = origin + '/api/1/studies/' + sid + '/analysis-versions/' + vid + '/execution'
        response = httpx.post(path + '/resume', headers=headers(accounts[0], origin), json=dict(command_id=uid()))
        assert response.status_code == 202, response.text
    worker = Store.postgres(fixture['request'], fixture['auth'], artifact_root=store.artifact_root,
                            background=fixture['dispatcher'])
    create_app(worker, Auth(worker, 'http://test'), None)
    try:
        AnalysisExecution(worker).process_one(Submissions(worker, None, None))
        with actor_scope(actor):
            state = AnalysisExecution(store).read(actor, sid, vid)
            assert state['state'] == 'needs_review', state
            assert [r['run_id'] for r in state['runs']] == [None, None, run_id]
            with store.connection() as db:
                assert db.execute('SELECT count(*) FROM run_associations WHERE study_id=?', (sid,)).fetchone()[0] == 1
            AnalysisExecution(store).cancel(actor, sid, vid)
    finally:
        worker.database.close()


@pytest.fixture
def recovery_hosted(tmp_path):
    # Full frozen sources and their audits use a fresh bounded database per case.
    from hosted_fixture import postgres_fixture
    with postgres_fixture() as fixture:
        store = Store.postgres(fixture['request'], fixture['auth'],
                               artifact_root=tmp_path / 'artifacts', background=fixture['assistant'])
        try:
            yield fixture, store
        finally:
            store.database.close()


@pytest.mark.parametrize('revoked_parent', [False, True, False])
def test_public_agent_resume_recovers_unprepared_child_and_crosses_claim_once_on_postgres(
        recovery_hosted, monkeypatch, revoked_parent):
    from calculation_fixture import seed
    from test_calculations_api import analysis_with_unprepared_authority_failure, recovered_submission_owner
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    failures = []
    resume = AnalysisExecution.resume
    def diagnostic_resume(self, *args, **kwargs):
        try:
            return resume(self, *args, **kwargs)
        except Exception as error:
            import traceback
            failures.append(''.join(traceback.format_exception(error)))
            raise
    monkeypatch.setattr(AnalysisExecution, 'resume', diagnostic_resume)
    fixture, store = recovery_hosted
    account = isolated_analysis_account(fixture)
    actor = account['actor']
    sid = study(store, actor)
    with actor_scope(actor):
        create_app(store, Auth(store, 'http://test'), None)
        sample = dict(store=store, actor=actor, sid=sid)
        sample.update(seed(sample))
    worker = Store.postgres(fixture['request'], fixture['auth'], artifact_root=store.artifact_root,
                            background=fixture['dispatcher'])
    create_app(worker, Auth(worker, 'http://test'), None)
    try:
        agent, grant, vid, rid = analysis_with_unprepared_authority_failure(store, actor, sid, sample, worker, revoked_parent=revoked_parent)
        with actor_scope(actor), store.connection() as db:
            source = db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
        with actor_scope(actor), pytest.raises(DatabaseConflict):
            with store.connection(write=True) as db:
                db.execute('UPDATE execution_operations SET preparation_state=NULL WHERE run_id=?', (rid,))
        with live_api(store) as origin:
            with actor_scope(actor):
                session = Auth(store, origin).mint_agent_session(grant['delegation_id'])
            own = headers(dict(token=session['token'], csrf=session['csrf_token']), origin)
            path = origin + '/api/1/studies/' + sid + '/analysis-versions/' + vid + '/execution'
            recovery = httpx.get(path + '/recovery', headers=own)
            assert recovery.status_code == 200 and recovery.json()['data']['can_resume'], recovery.text
            command = dict(command_id=uid())
            with ThreadPoolExecutor(2) as pool:
                replies = list(pool.map(lambda _: httpx.post(path + '/resume', headers=own, json=command), range(2)))
            assert [r.status_code for r in replies] == [202, 202], '\n'.join([r.text for r in replies] + failures)
            assert replies[0].json()['data'] == replies[1].json()['data']
            with actor_scope(actor), store.connection() as db:
                assert db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0] == source
                audit = db.execute('SELECT previous_receipt FROM analysis_run_resumptions WHERE run_id=?', (rid,)).fetchall()
                assert len(audit) == 1
                assert json.loads(audit[0]['previous_receipt'])['error']['code'] == 'analysis_authority_revoked'
            submissions, native = recovered_submission_owner(worker)
            submissions.dispatch(rid)
            with actor_scope(actor):
                assert Submissions(store, None, None).read(actor, sid, rid)['state'] == 'uncertain'
            assert native.launches == 1
            replay = httpx.post(path + '/resume', headers=own, json=command)
            assert replay.status_code == 202 and replay.json()['data'] == replies[0].json()['data'], replay.text
            submissions.dispatch(rid)
            assert native.launches == 1
            with actor_scope(actor):
                AnalysisExecution(store).cancel(actor, sid, vid)
    finally:
        worker.database.close()
