"""Public HTTP answer journeys in scoped synthetic stores; no numerical execution."""

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.store import Store, uid, digest
from test_assumptions_evidence_api import api, generated, ORIGIN, NoModeling
from test_approach_api import write, save, assert_http, assert_shape
from test_approach_closure import sample, D, model, config
from test_approach_service import run_env


@pytest.fixture
def answer_env(api):
    content = sample(D['ApproachContent1'])
    case = sample(D['ApproachCase1'])
    content['cases'] = [case]
    draft, _ = write(api, dict(schema_version='1', expected_revision=None, content=content))
    saved, _ = save(api, draft)
    api['version'] = saved.json()['data']['saved']['version']['approach_version_id']
    api['draft_revision'] = saved.json()['data']['draft_revision']
    api['case'] = case['case_id']
    return api


def path(e, suffix=''):
    return '/api/1/studies/' + e['sid'] + '/answers' + suffix


def body(e, **changes):
    return (
        dict(
            schema_version='1',
            command_id=uid(),
            expected_revision=None,
            approach_version_id=e['version'],
            case_id=e['case'],
            observations='The requested comparison has no recorded output.',
            interpretation='The engineering question remains unresolved.',
            qualifications=['No completed numerical basis is available.'],
            open_deliverables=['Evaluate the specified comparison.'],
            basis=dict(
                configuration_revision_ids=[],
                run_ids=[],
                evidence_version_ids=[],
                case_answer_version_ids=[],
            ),
        )
        | changes
    )


def post(e, request):
    return e['client'].post(path(e), json=request)


def heads(e, version=None):
    return e['client'].get(
        '/api/1/studies/'
        + e['sid']
        + '/approach/versions/'
        + (version or e['version'])
        + '/answers'
    )


def saved(e, request=None):
    response = post(e, request or body(e))
    assert response.status_code == 201, response.text
    return response.json()['data']


def add_basis(e, sid=None):
    """Synthetic saved inputs and accepted runs; never claimed as computed evidence."""
    sid = sid or e['sid']
    m = model()
    c = config(m)
    c['study_id'] = sid
    rid = uid()
    with e['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations VALUES(?,?,?,?)',
            (
                c['configuration_revision_id'],
                c['configuration_id'],
                sid,
                json.dumps(dict(configuration=c, model_snapshot=m)),
            ),
        )
        db.execute(
            'INSERT INTO run_associations '
            '(run_id,study_id,configuration_revision_id,command_id) VALUES(?,?,?,?)',
            (rid, sid, c['configuration_revision_id'], uid()),
        )
        db.execute('INSERT INTO outbox VALUES(?,?,?)', (rid, 'accepted_run', '{}'))
        command = db.execute(
            'SELECT command_id FROM run_associations WHERE run_id=?', (rid,)
        ).fetchone()[0]
    e['store'].command(
        e['actor'],
        sid,
        'run',
        command,
        {},
        lambda db: dict(run_id=rid),
        receipt_state='accepted_run',
    )
    return c['configuration_revision_id'], rid


def test_persistent_create_revise_exact_old_read_and_receipt(answer_env, generated):
    e = answer_env
    empty = heads(e)
    assert empty.status_code == 200
    assert empty.json()['data'] == dict(approach_version_id=e['version'], items=[])
    request = body(e)
    first = saved(e, request)
    assert_shape(generated, 'ScientificAnswer1', first)
    revised = saved(
        e,
        body(
            e,
            expected_revision=first['answer_version_id'],
            interpretation='Still unresolved after reviewing the missing basis.',
        ),
    )
    assert revised['answer_id'] == first['answer_id']
    assert revised['previous_version_id'] == first['answer_version_id']
    assert revised['version_number'] == 2
    assert revised['created_by'] == e['actor']
    assert heads(e).json()['data']['items'] == [revised]
    # Reopen the persistent Store and API, retaining the ordinary user session.
    reopened = Store(e['store'].path)
    client = TestClient(create_app(reopened, Auth(reopened, ORIGIN), NoModeling()), base_url=ORIGIN)
    client.cookies.update(e['client'].cookies)
    old = client.get(path(e, '/' + first['answer_version_id']))
    assert old.status_code == 200 and old.json()['data'] == first
    assert_http(generated, '/studies/{study_id}/answers/{answer_version_id}', 'get', old)
    receipt = client.get(
        '/api/1/studies/' + e['sid'] + '/commands/' + request['command_id'],
        params={'category': 'answer_save'},
    )
    assert receipt.status_code == 200 and receipt.json()['data']['result'] == first
    assert receipt.json()['data']['recovery'] == 'adopt'
    assert_shape(generated, 'PublicReceipt', receipt.json()['data'])
    # Recovery returns the original outcome even after another version became head.
    assert saved(e, request) == first


def test_replay_concurrency_payload_conflict_and_stale_head(answer_env):
    e = answer_env
    request = body(e)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post(e, request), range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()['data'] == responses[1].json()['data']
    first = responses[0].json()['data']
    conflict = post(e, request | dict(interpretation='A different payload.'))
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'command_payload_conflict'
    stale = post(e, body(e))
    assert stale.status_code == 409
    assert stale.json()['error']['code'] == 'stale_revision'
    assert stale.json()['error']['current_revision'] == first['answer_version_id']
    assert len(heads(e).json()['data']['items']) == 1


@pytest.mark.parametrize('role,status', [('reader', 403), ('writer', 201), ('absent', 404)])
def test_actual_http_membership_controls_writes_and_reads(answer_env, role, status):
    e = answer_env
    old = saved(e)
    with e['store'].connection(write=True) as db:
        if role == 'absent':
            db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
        else:
            db.execute('UPDATE memberships SET role=? WHERE study_id=?', (role, e['sid']))
    response = post(e, body(e, expected_revision=old['answer_version_id']))
    assert response.status_code == status
    assert heads(e).status_code == (404 if role == 'absent' else 200)
    assert e['client'].get(path(e, '/' + old['answer_version_id'])).status_code == (
        404 if role == 'absent' else 200
    )


@pytest.mark.parametrize('field', ['configuration_revision_ids', 'run_ids', 'evidence_version_ids'])
@pytest.mark.parametrize('foreign', [False, True])
def test_missing_or_foreign_basis_is_refused_without_answer(answer_env, field, foreign):
    e = answer_env
    request = body(e)
    identity = uid()
    if foreign:
        sid = e['store'].create_study(e['actor'], uid(), 'Separate study')['study_id']
        config_id, run_id = add_basis(e, sid)
        if field == 'evidence_version_ids':
            # Existing evidence authoring owner; saved evidence remains in its own study.
            evidence = e['store'].add_evidence(
                e['actor'],
                sid,
                uid(),
                {
                    'kind': 'note',
                    'content': 'A separate observation.',
                    'scope': None,
                    'source_refs': [],
                },
            )
            identity = evidence['evidence_version_id']
        else:
            identity = config_id if field == 'configuration_revision_ids' else run_id
    request['basis'][field] = [identity]
    response = post(e, request)
    assert response.status_code == 409, response.text
    assert response.json()['error']['code'] == 'reference_conflict'
    assert heads(e).json()['data']['items'] == []


def test_multiple_exact_inputs_and_uncomputed_runs_are_allowed_as_explicit_qualified_basis(
    answer_env,
):
    e = answer_env
    pairs = [add_basis(e), add_basis(e)]
    request = body(e)
    request['basis']['configuration_revision_ids'] = [p[0] for p in pairs]
    request['basis']['run_ids'] = [p[1] for p in pairs]
    value = saved(e, request)
    assert value['basis'] == request['basis']
    assert value['interpretation'] == request['interpretation']
    assert value['qualifications'] == request['qualifications']


def test_synthesis_keeps_exact_case_answer_version_after_revision(answer_env):
    e = answer_env
    case_answer = saved(e)
    request = body(e, case_id=None)
    request['basis']['case_answer_version_ids'] = [case_answer['answer_version_id']]
    study_answer = saved(e, request)
    revised = saved(e, body(e, expected_revision=case_answer['answer_version_id']))
    assert revised['answer_version_id'] != case_answer['answer_version_id']
    read = e['client'].get(path(e, '/' + study_answer['answer_version_id']))
    assert read.json()['data']['basis']['case_answer_version_ids'] == [
        case_answer['answer_version_id']
    ]
    assert len(heads(e).json()['data']['items']) == 2


def test_case_missing_or_other_approach_answer_is_not_substituted(answer_env):
    e = answer_env
    assert post(e, body(e, case_id=uid())).status_code == 409
    assert post(e, body(e, approach_version_id=uid())).status_code == 404
    old = saved(e)
    content = sample(D['ApproachContent1'])
    content['cases'] = [sample(D['ApproachCase1'])]
    draft, _ = write(
        e, dict(schema_version='1', expected_revision=e['draft_revision'], content=content)
    )
    version, _ = save(e, draft)
    other_version = version.json()['data']['saved']['version']['approach_version_id']
    assert heads(e, other_version).json()['data']['items'] == []
    request = body(e, case_id=None, approach_version_id=other_version)
    request['basis']['case_answer_version_ids'] = [old['answer_version_id']]
    assert post(e, request).status_code == 409
    assert heads(e).json()['data']['items'] == [old]


@pytest.mark.parametrize(
    'change',
    [
        {'extra': 'rejected'},
        {'interpretation': '  '},
        {'case_id': 'latest'},
        {'observations': True},
        {'schema_version': '2'},
        {'expected_revision': 'latest'},
    ],
)
def test_closed_commands_reject_missing_or_untyped_content(answer_env, change):
    response = post(answer_env, body(answer_env) | change)
    assert response.status_code == 400, response.text


def test_case_cannot_cite_another_answer_and_study_cannot_cite_synthesis(answer_env):
    e = answer_env
    case = saved(e)
    request = body(e, expected_revision=case['answer_version_id'])
    request['basis']['case_answer_version_ids'] = [case['answer_version_id']]
    assert post(e, request).status_code == 400
    synthesis = saved(e, body(e, case_id=None))
    request = body(e, case_id=None, expected_revision=synthesis['answer_version_id'])
    request['basis']['case_answer_version_ids'] = [synthesis['answer_version_id']]
    assert post(e, request).status_code == 409


def test_saved_answers_are_immutable_and_queries_closed(answer_env):
    e = answer_env
    value = saved(e)
    for sql in (
        'UPDATE scientific_answer_versions SET payload=? WHERE answer_version_id=?',
        'DELETE FROM scientific_answer_versions WHERE payload=? AND answer_version_id=?',
    ):
        with pytest.raises(sqlite3.IntegrityError), e['store'].connection(write=True) as db:
            db.execute(
                sql,
                (
                    json.dumps(value, separators=(',', ':'), sort_keys=True),
                    value['answer_version_id'],
                ),
            )
    assert heads(e).status_code == 200
    assert (
        e['client'].get(path(e, '/' + value['answer_version_id']) + '?extra=1').status_code == 400
    )


def test_delegated_writer_and_unauthenticated_sessions_cannot_save_answers(answer_env):
    e = answer_env
    auth = Auth(e['store'], ORIGIN)
    with e['store'].connection(write=True) as db:
        agent = e['store'].ensure_agent_actor(db, e['actor'], 'local_mcp', 'Test author')
        delegation = e['store'].create_delegation(
            db, agent, e['sid'], 'writer', ('read', 'draft', 'record'), time.time() + 300
        )
    session = auth.mint_agent_session(delegation['delegation_id'])
    client = TestClient(create_app(e['store'], auth, NoModeling()), base_url=ORIGIN)
    assert client.get(path(e, '/' + uid())).status_code == 401
    client.cookies.set('hyprn_mvp_session', session['token'])
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session['csrf_token']})
    assert client.post(path(e), json=body(e)).status_code == 403
    assert heads(e).json()['data']['items'] == []


def test_successful_same_study_evidence_basis_is_exact_and_not_rewritten(answer_env):
    e = answer_env
    evidence = e['store'].add_evidence(
        e['actor'],
        e['sid'],
        uid(),
        dict(
            kind='note',
            content='Observed limitation of the comparison.',
            scope=None,
            source_refs=[],
        ),
    )
    request = body(e)
    request['basis']['evidence_version_ids'] = [evidence['evidence_version_id']]
    answer = saved(e, request)
    assert answer['basis'] == request['basis']
    read = e['client'].get(
        '/api/1/studies/' + e['sid'] + '/evidence/' + evidence['evidence_version_id']
    )
    assert read.status_code == 200 and read.json()['data'] == evidence


def test_failed_retained_run_remains_citeable_without_promoting_it_to_an_answer(run_env):
    """An authored limitation may cite failure; execution does not author an interpretation."""
    e = run_env
    rid, _ = e['source'](current=True)
    with e['store'].connection(write=True) as db:
        payload = json.loads(
            db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
        )
        result = payload['history']['results']
        result['execution'].update(
            state='failed', exit_code=1, message='Synthetic component failure'
        )
        for output in result['outputs']:
            output.update(
                value=None,
                availability='unavailable',
                reason='not computed',
                producer_completed=False,
                assigned=False,
            )
        payload['history']['digest'] = digest(
            {key: value for key, value in payload['history'].items() if key != 'digest'}
        )
        raw = json.dumps(payload)
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (raw, rid))
    auth = Auth(e['store'], ORIGIN)
    actor = auth.provision('answer-owner', 'correct horse battery staple')
    with e['store'].connection(write=True) as db:
        db.execute('UPDATE memberships SET actor_id=? WHERE study_id=?', (actor, e['sid']))
    client = TestClient(create_app(e['store'], auth, NoModeling()), base_url=ORIGIN)
    session = client.post(
        '/api/1/session',
        json=dict(username='answer-owner', password='correct horse battery staple'),
        headers={'Origin': ORIGIN},
    )
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    e['client'] = client
    content = sample(D['ApproachContent1'])
    case = sample(D['ApproachCase1'])
    content['cases'] = [case]
    draft, _ = write(e, dict(schema_version='1', expected_revision=None, content=content))
    version, _ = save(e, draft)
    e['version'] = version.json()['data']['saved']['version']['approach_version_id']
    e['case'] = case['case_id']
    read = client.get('/api/1/studies/' + e['sid'] + '/runs/' + rid)
    assert read.status_code == 200, read.text
    results = read.json()['data']['history']['results']
    assert results['execution']['state'] == 'failed'
    assert all(output['value'] is None for output in results['outputs'])
    assert heads(e).json()['data']['items'] == []
    request = body(
        e,
        observations='The retained execution failed; its outputs are not computed.',
        interpretation='This run cannot support the requested comparison.',
        qualifications=['The failed run leaves the comparison unresolved.'],
    )
    request['basis']['run_ids'] = [rid]
    answer = saved(e, request)
    assert answer['basis']['run_ids'] == [rid]
    assert answer['interpretation'] == request['interpretation']
    with e['store'].connection() as db:
        assert db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0] == raw
