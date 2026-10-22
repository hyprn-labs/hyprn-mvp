"""Execution budgets bind command identity; diagnostics never manufacture scientific results."""

import json

import pytest
from hyprn_mvp_app.contracts import DomainError, uid
from hyprn_mvp_app.dispatcher import bridge_request
from test_submission import submission
from test_history import client, recording


@pytest.mark.parametrize('value', [0, -1, 3601, True, 2.5, '30'])
def test_invalid_budget_rejected_before_acceptance(submission, value):
    _, store, actor, sid, revision, native = submission
    c, _ = client(store, actor)
    reply = c.post(
        f'/api/1/studies/{sid}/runs',
        json=dict(
            command_id=uid(),
            configuration_revision_id=revision,
            execution_budget=dict(wall_seconds=value),
        ),
    )
    assert reply.status_code == 400
    assert reply.json()['error']['fields'][0]['path'] == '/execution_budget/wall_seconds'
    assert native.launches == 0
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM run_associations').fetchone()[0] == 0


def test_budget_is_retained_and_cannot_change_on_command_replay(submission):
    service, store, actor, sid, revision, native = submission
    body = dict(
        command_id=uid(), configuration_revision_id=revision, execution_budget=dict(wall_seconds=90)
    )
    run = service.submit(actor, sid, body)
    assert service.submit(actor, sid, body)['run_id'] == run['run_id']
    with pytest.raises(DomainError, match='command_payload_conflict'):
        service.submit(actor, sid, dict(body, execution_budget=dict(wall_seconds=100)))
    observed = []

    def launch(bundle, request, seconds):
        observed.append(seconds)
        return native.launch(bundle, request)

    native.launch_budgeted = launch
    service.dispatch(run['run_id'])
    service.dispatch(run['run_id'])
    assert observed == [90] and native.launches == 1
    with store.connection() as db:
        payload = json.loads(
            db.execute('SELECT payload FROM outbox WHERE run_id=?', (run['run_id'],)).fetchone()[0]
        )
        assert payload['execution_budget'] == {'wall_seconds': 90}


@pytest.mark.parametrize('seconds', [0, True, 3601, '30'])
def test_private_bridge_also_bounds_budget(seconds):
    with pytest.raises(ValueError):
        bridge_request('launch_budgeted', [{}, {}, seconds])


def test_timeout_diagnostic_uses_retained_artifact_without_results(submission):
    service, store, actor, sid, _, native = submission
    run = recording(submission)
    native.record['artifacts']['result.json'] = json.dumps(
        dict(
            reason='wall_limit',
            exit_code=-9,
            seconds=1.3,
            wall_seconds=1,
            state={'OOMKilled': False},
            output='do not expose candidate stdout',
        )
    ).encode()
    service.hydrate(actor, sid, run['run_id'])
    c, _ = client(store, actor)
    reply = c.get(f'/api/1/studies/{sid}/runs/' + run['run_id'])
    assert reply.status_code == 200
    detail = reply.json()['data']
    assert detail['history']['results'] is None
    diagnostic = detail['execution_summary']
    assert diagnostic['status'] == 'timed_out'
    assert diagnostic == dict(status='timed_out', duration_seconds=1.3)
    assert 'execution_diagnostic' not in detail
    assert 'stdout' not in json.dumps(diagnostic)
    assert detail['history']['artifacts']
    listed = c.get(f'/api/1/studies/{sid}/runs').json()['data']
    assert listed[0]['execution_summary'] == diagnostic


def test_default_budget_is_frozen_at_api_acceptance(submission):
    _, store, actor, sid, revision, _ = submission
    c, _ = client(store, actor)
    body = dict(command_id=uid(), configuration_revision_id=revision)
    first = c.post(f'/api/1/studies/{sid}/runs', json=body)
    assert first.status_code == 202
    rid = first.json()['data']['run_id']
    replay = c.post(f'/api/1/studies/{sid}/runs', json=body)
    assert replay.json()['data']['run_id'] == rid
    with store.connection() as db:
        payload = json.loads(
            db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
        )
    assert payload['execution_budget'] == {'wall_seconds': 300}
