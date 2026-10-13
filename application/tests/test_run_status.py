"""The light run-status read is a projection of the stored run state that its owner serves:
it agrees with the full run read, never loads an outbox payload whole, keeps unavailable values
null with a reason, and answers for all requested runs of the study or for none."""
import base64
import json
import re
import sqlite3
import time
import pytest
from hyprn_mvp_app.store import Store, uid
from test_submission import Crash, submission, accepted
from test_history import client, recording

FACETS = ('execution', 'convergence', 'optimization', 'completeness', 'applicability')


def status(c, sid, *run_ids, extra=''):
    query = '&'.join('run_id=' + r for r in run_ids) + extra
    return c.get(f'/api/1/studies/{sid}/run-status?' + query)


def full(c, sid, rid):
    response = c.get(f'/api/1/studies/{sid}/runs/{rid}')
    assert response.status_code == 200, response.text
    return response.json()['data']


def with_results(submission, criteria):
    """A recorded run whose retained results hold every facet and the given criterion outcomes."""
    service, store, actor, sid, _, native = submission
    run = recording(submission)
    native.record['results'] = dict(schema_version='1', run_id=run['run_id'], bundle_digest=native.record['request']['bundle_digest'],
        execution=dict(state='failed', exit_code=3, message='retained failure'),
        convergence=dict(state='not_applicable', diagnostics_ref=None),
        optimization=dict(termination='not_applicable', feasibility='not_applicable'),
        completeness=dict(expected=2, available=0, failed=2, unavailable=2),
        outputs=[], criteria=criteria, applicability=dict(state='unassessed', evidence_refs=[]), artifacts=[])
    native.record['errors'] = []
    service.hydrate(actor, sid, run['run_id'])
    return run


def runs_in_every_state(submission):
    service, store, actor, sid, _, native = submission
    runs = {'accepted_run': accepted(submission)}
    runs['prepared'] = accepted(submission)
    service.dispatch(runs['prepared']['run_id'], prepare_only=True)
    runs['preparation_failed'] = accepted(submission)
    prepare = service.prepare
    def invalid(*args): raise ValueError('Controlled invalid preparation')
    service.prepare = invalid
    service.dispatch(runs['preparation_failed']['run_id'], prepare_only=True)
    service.prepare = prepare
    runs['dispatching'] = accepted(submission)
    def fault(point):
        if point == 'after_claim': raise Crash(point)
    service.fault = fault
    with pytest.raises(Crash): service.dispatch(runs['dispatching']['run_id'])
    service.fault = lambda point: None
    runs['uncertain'] = accepted(submission)
    native.mode = 'before_node'
    with pytest.raises(Crash): service.dispatch(runs['uncertain']['run_id'])
    native.mode = 'none'
    service.dispatch(runs['uncertain']['run_id'])
    native.mode = None
    runs['recorded_without_results'] = recording(submission)
    runs['recorded'] = with_results(submission, [dict(criterion_id=uid(), outcome='violated', reason='Retained claim')])
    return runs


def test_each_item_equals_the_full_run_read_in_every_run_state(submission):
    runs = runs_in_every_state(submission)
    service, store, actor, sid, _, native = submission
    c, actor = client(store, actor)
    ids = [run['run_id'] for run in runs.values()]
    response = status(c, sid, *ids)
    assert response.status_code == 200, response.text
    items = response.json()['data']
    assert [item['run_id'] for item in items] == ids
    listed = {item['run_id']: item for item in c.get(f'/api/1/studies/{sid}/runs').json()['data']}
    for (label, run), item in zip(runs.items(), items):
        detail = full(c, sid, run['run_id'])
        assert item['state'] == detail['state'] == listed[run['run_id']]['state'], label
        assert item['configuration_revision_id'] == listed[run['run_id']]['configuration_revision_id']
        assert item['configuration_name'] == listed[run['run_id']]['configuration_name']
        assert item['process_state'] == detail.get('process_state') and item['exit_status'] == detail.get('exit_status'), label
        results = (detail.get('history') or {}).get('results')
        if results is None:
            assert all(item['facets'][k] == dict(value=None, reason='not_recorded') for k in FACETS), label
            assert item['criteria'] == dict(value=None, reason='not_recorded'), label
        else:
            assert {k: item['facets'][k] for k in FACETS} == {k: dict(value=results[k], reason=None) for k in FACETS}
            assert item['criteria'] == dict(value=results['criteria'], reason=None)
    assert [item['state'] for item in items] == ['accepted_run', 'prepared', 'preparation_failed', 'dispatching',
                                                'uncertain', 'recorded', 'recorded']


def test_unavailable_outcome_is_null_with_its_reason_never_zero(submission):
    service, store, actor, sid, _, native = submission
    pending, failed = accepted(submission), with_results(submission, [])
    c, actor = client(store, actor)
    first, second = status(c, sid, pending['run_id'], failed['run_id']).json()['data']
    assert first['process_state'] is None and first['exit_status'] is None
    assert first['facets']['completeness'] == dict(value=None, reason='not_recorded')
    assert first['criteria'] == dict(value=None, reason='not_recorded')
    # Recorded zeros are explicit values, kept exactly as stored.
    assert second['facets']['completeness'] == dict(value=dict(expected=2, available=0, failed=2, unavailable=2), reason=None)
    assert second['criteria'] == dict(value=[], reason=None)
    for item in (first, second):
        assert item['times']['started_at'] == item['times']['finished_at'] == dict(value=None, reason='not_projected')


@pytest.mark.parametrize('query', ['21_ids', 'repeated', 'unknown_parameter', 'no_id', 'malformed_id'])
def test_malformed_requests_are_refused(submission, query):
    service, store, actor, sid, _, native = submission
    run = accepted(submission)
    c, actor = client(store, actor)
    ids = {'21_ids': [uid() for _ in range(21)], 'repeated': [run['run_id'], run['run_id']],
           'unknown_parameter': [run['run_id']], 'no_id': [], 'malformed_id': [run['run_id'].upper()]}[query]
    response = status(c, sid, *ids, extra='&limit=5' if query == 'unknown_parameter' else '')
    assert response.status_code == 400, response.text
    assert response.json()['error']['code'] == 'invalid_request'


def test_twenty_ids_are_admitted(submission):
    service, store, actor, sid, _, native = submission
    ids = [accepted(submission)['run_id'] for _ in range(20)]
    c, actor = client(store, actor)
    response = status(c, sid, *reversed(ids))
    assert response.status_code == 200 and [i['run_id'] for i in response.json()['data']] == ids[::-1]


def test_a_run_of_another_study_or_a_non_member_gets_the_scoped_404_without_partial_answer(submission):
    service, store, actor, sid, _, native = submission
    run = accepted(submission)
    c, actor = client(store, actor)
    other = store.create_study(actor, uid(), 'Other study')['study_id']
    for study, ids in ((other, [run['run_id']]), (sid, [run['run_id'], uid()])):
        response = status(c, study, *ids)
        assert response.status_code == 404 and response.json()['error']['code'] == 'resource_not_found'
        assert 'data' not in response.json()
    with store.connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?', (actor, sid))
    response = status(c, sid, run['run_id'])
    assert response.status_code == 404 and response.json()['error']['code'] == 'resource_not_found'


def test_acceptance_time_is_recorded_once_and_absent_for_runs_accepted_before_it(submission):
    service, store, actor, sid, _, native = submission
    old = accepted(submission)
    # A store from before the acceptance time: the column is gone, and reopening adds it
    # back through the additive migration with NULL for the existing run.
    with store.connection(write=True) as db:
        db.execute('ALTER TABLE run_associations DROP COLUMN accepted_at')
    store = Store(store.path)
    service.store = store
    new = recording(submission)
    with store.connection() as db:
        stored = {r['run_id']: r['accepted_at'] for r in db.execute('SELECT run_id,accepted_at FROM run_associations')}
        receipt = db.execute("SELECT result FROM receipts WHERE category='run' AND command_id=?", (new['command_id'],)).fetchone()[0]
        payload = db.execute('SELECT payload FROM outbox WHERE run_id=?', (new['run_id'],)).fetchone()[0]
    assert stored[old['run_id']] is None and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z', stored[new['run_id']])
    assert 'accepted_at' not in receipt and 'accepted_at' not in payload
    c, actor = client(store, actor)
    before, after = status(c, sid, old['run_id'], new['run_id']).json()['data']
    assert before['times']['submitted_at'] == dict(value=None, reason='not_recorded')
    assert after['times']['submitted_at'] == dict(value=stored[new['run_id']], reason=None)
    service.hydrate(actor, sid, new['run_id'])
    with store.connection() as db:
        assert db.execute('SELECT accepted_at FROM run_associations WHERE run_id=?', (new['run_id'],)).fetchone()[0] == stored[new['run_id']]


def traced(monkeypatch):
    """Every statement executed on application store connections opened from now on."""
    statements, connect = [], sqlite3.connect
    def tracing(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_trace_callback(statements.append)
        return db
    monkeypatch.setattr(sqlite3, 'connect', tracing)
    return statements


def whole_outbox_payload(statement):
    """Whether a statement selects the outbox payload column itself rather than paths inside it."""
    if 'outbox' not in statement:
        return False
    return 'payload' in re.sub(r"json_(?:extract|type)\(o\.payload,'[^']*'\)", '', statement)


def test_the_read_never_selects_the_outbox_payload_whole(submission, monkeypatch):
    service, store, actor, sid, _, native = submission
    runs = [recording(submission)['run_id'], accepted(submission)['run_id']]
    c, actor = client(store, actor)
    statements = traced(monkeypatch)
    assert status(c, sid, *runs).status_code == 200
    reads = [s for s in statements if 'outbox' in s]
    assert len(reads) == 1 and not any(map(whole_outbox_payload, statements)), reads
    # The detector is not vacuous: the full run read selects the payload whole.
    statements.clear()
    full(c, sid, runs[0])
    assert any(map(whole_outbox_payload, statements))


def test_twenty_runs_with_large_retained_payloads_read_under_one_second_at_p95(submission):
    service, store, actor, sid, _, native = submission
    runs = [recording(submission)['run_id']]
    for _ in range(19):
        runs.append(accepted(submission)['run_id'])
        service.dispatch(runs[-1])
    filler = base64.b64encode(bytes(range(256)) * 4096).decode()  # about 1.3 MiB per run
    with store.connection(write=True) as db:
        for rid in runs:
            payload = json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0])
            payload['bundle']['files']['retained-filler.bin'] = filler
            db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(payload), rid))
    c, actor = client(store, actor)
    durations = []
    for _ in range(20):
        start = time.perf_counter()
        response = status(c, sid, *runs)
        durations.append(time.perf_counter() - start)
        assert response.status_code == 200 and len(response.json()['data']) == 20
    durations.sort()
    assert durations[18] < 1.0, durations
