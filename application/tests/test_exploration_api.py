"""Public exploration basis remains exact, source-free and purely observational.

Synthetic frozen models exercise contracts only; these tests do not claim fuel
calculation, fitted surrogate accuracy or real worker execution.
"""

import base64
from copy import deepcopy
import hashlib
import json

import pytest

from hyprn_mvp_app.contracts import digest, uid
from hyprn_mvp_app.exploration import Explorations, quantities
from test_assumptions_evidence_api import api, generated  # noqa: F401
from test_answers_api import answer_env, body, saved  # noqa: F401
from test_approach_api import assert_http, assert_shape
from test_approach_closure import D, config, model, sample, signed


def design_request(e):
    inputs, outputs = quantities(e['frozen'])
    axis = next(p for p in inputs if p['binding']['kind'] == 'free')['target']
    return dict(
        schema_version='1',
        command_id=uid(),
        selection_token=uid(),
        operation='design',
        answer_version_id=e['answer']['answer_version_id'],
        configuration_revision_id=e['frozen']['configuration']['configuration_revision_id'],
        axis=axis,
        lower=0,
        upper=2,
        seed=17,
        training_count=3,
        check_count=2,
        method='response_surface',
        training_run_ids=[],
        check_run_ids=[],
        query_values=[0, 1],
        tolerances=[dict(target=outputs[0]['target'], absolute=0.1, relative=0.01)],
        rationale='Explicit synthetic slice for API admission only',
    )


def test_design_admission_and_reads_do_not_execute_source_or_numerics(basis_env, generated):
    e = basis_env
    request = design_request(e)
    path = '/api/1/studies/' + e['sid'] + '/exploration-requests'
    reply = e['client'].post(path, json=request)
    assert reply.status_code == 202, reply.text
    assert_http(generated, '/studies/{study_id}/exploration-requests', 'post', reply)
    assert reply.json()['data']['state'] == 'pending'
    assert not e['canary'].exists()
    assert e['client'].post(path, json=request).json()['data'] == reply.json()['data']
    read = e['client'].get(path + '/' + request['command_id'])
    assert read.json()['data'] == reply.json()['data']
    conflict = e['client'].post(path, json=dict(request, seed=18))
    assert conflict.status_code == 409


@pytest.mark.parametrize(
    'changes',
    [
        {'seed': True},
        {'seed': 1.0},
        {'lower': float('inf')},
        {'lower': 3},
        {'query_values': [3]},
        {'training_count': 33},
        {'check_count': 0},
        {'pickle': 'forbidden'},
        {'operation': 'execute'},
        {'rationale': '   '},
        {'query_values': [True]},
        {'query_values': [9007199254740992]},
    ],
)
def test_invalid_design_never_queues_numerical_work(basis_env, changes):
    e = basis_env
    request = dict(design_request(e), **changes)
    reply = e['client'].post(
        '/api/1/studies/' + e['sid'] + '/exploration-requests',
        content=json.dumps(request),
        headers={'Content-Type': 'application/json'},
    )
    assert reply.status_code == 400, reply.text
    with e['store'].connection() as db:
        assert (
            db.execute("SELECT COUNT(*) FROM receipts WHERE category='exploration'").fetchone()[0]
            == 0
        )


def test_unknown_numerical_outcome_is_never_automatically_redispatched(basis_env):
    e = basis_env
    request = design_request(e)
    path = '/api/1/studies/' + e['sid'] + '/exploration-requests'
    assert e['client'].post(path, json=request).status_code == 202
    calls = []

    class LostResponse:
        def explore(self, request):
            calls.append(request)
            raise TimeoutError('Transport lost after possible native computation')

    owner = Explorations(e['store'], None)
    assert owner.process_one(LostResponse()) is True
    assert owner.process_one(LostResponse()) is False
    read = e['client'].get(path + '/' + request['command_id'])
    assert read.json()['data']['state'] == 'uncertain'
    assert e['client'].post(path, json=request).json()['data'] == read.json()['data']
    assert len(calls) == 1


@pytest.mark.parametrize('role, expected', [('reader', 403), ('absent', 404)])
def test_numerical_admission_requires_current_study_write_access(basis_env, role, expected):
    e = basis_env
    request = design_request(e)
    with e['store'].connection(write=True) as db:
        if role == 'absent':
            db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
        else:
            db.execute('UPDATE memberships SET role=? WHERE study_id=?', (role, e['sid']))
    reply = e['client'].post('/api/1/studies/' + e['sid'] + '/exploration-requests', json=request)
    assert reply.status_code == expected


@pytest.fixture
def basis_env(answer_env, tmp_path):
    e = answer_env
    m = model()
    definition = m['definitions'][0]
    definition['kind'] = 'explicit_component'
    free, connected, output = [sample(D['Port']) for _ in range(3)]
    for port, direction in [(free, 'input'), (connected, 'input'), (output, 'output')]:
        port.update(
            definition_version_id=definition['definition_version_id'],
            direction=direction,
            units='m',
            name='Shared label',
        )
    definition['ports'] = [free, connected, output]
    m['ports'] = deepcopy(definition['ports'])
    # Repeated occurrences share a definition and labels, never input identity.
    m['instances'].append(dict(m['instances'][0], instance_id=uid(), name='Second'))
    targets = [dict(instance_id=i['instance_id'], port_id=free['port_id']) for i in m['instances']]
    m['connections'] = [
        dict(
            connection_id=uid(),
            source_ref=dict(instance_id=i['instance_id'], port_id=output['port_id']),
            target_ref=dict(instance_id=i['instance_id'], port_id=connected['port_id']),
        )
        for i in m['instances']
    ]
    canary = tmp_path / 'candidate-executed'
    source = ('from pathlib import Path\nPath(' + repr(str(canary)) + ').touch()\n').encode()
    m['source_files'] = [
        dict(
            encoding='base64',
            media_type='text/x-python',
            bytes=base64.b64encode(source).decode(),
            sha256=hashlib.sha256(source).hexdigest(),
        )
    ]
    definition['source_refs'] = [m['source_files'][0]['sha256']]
    signed(m)
    c = config(m)
    c['study_id'] = e['sid']
    c['inputs'] = [
        dict(sample(D['ResolvedInput2']), target=t, value=value, units='m')
        for t, value in zip(targets, [0, 7], strict=True)
    ]
    signed(c)
    frozen = dict(
        schema_version='4',
        configuration=c,
        model_snapshot=m,
        study_revision=e['study']['revision'],
        approach_closure=None,
    )
    with e['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations VALUES(?,?,?,?)',
            (c['configuration_revision_id'], c['configuration_id'], e['sid'], json.dumps(frozen)),
        )
    request = body(e)
    request['basis']['configuration_revision_ids'] = [c['configuration_revision_id']]
    answer = saved(e, request)
    e.update(frozen=frozen, answer=answer, canary=canary)
    return e


def url(e, *, answer=None, revision=None):
    return (
        '/api/1/studies/'
        + e['sid']
        + '/answers/'
        + (answer or e['answer']['answer_version_id'])
        + '/exploration-basis/'
        + (revision or e['frozen']['configuration']['configuration_revision_id'])
    )


def rewrite(e):
    c = e['frozen']['configuration']
    c['configuration_revision_id'] = uid()
    signed(c)
    with e['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations VALUES(?,?,?,?)',
            (
                c['configuration_revision_id'],
                c['configuration_id'],
                e['sid'],
                json.dumps(e['frozen']),
            ),
        )
    request = body(e, expected_revision=e['answer']['answer_version_id'])
    request['basis']['configuration_revision_ids'] = [c['configuration_revision_id']]
    e['answer'] = saved(e, request)


def test_exact_public_inventory_preserves_zero_units_occurrences_and_source_isolation(
    basis_env, generated
):
    e = basis_env
    before = deepcopy(e['frozen'])
    quantities(before)
    response = e['client'].get(url(e))
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert_shape(generated, 'ExplorationBasis1', result)
    assert_http(
        generated,
        '/studies/{study_id}/answers/{answer_version_id}'
        '/exploration-basis/{configuration_revision_id}',
        'get',
        response,
    )
    free = [p for p in result['inputs'] if p['binding']['kind'] == 'free']
    connected = [p for p in result['inputs'] if p['binding']['kind'] == 'connected']
    assert len(free) == len(connected) == len(result['outputs']) == 2
    assert [p['binding']['assignment']['value'] for p in free] == [0, 7]
    assert free[0]['target'] != free[1]['target']
    assert all(p['units'] == 'm' for p in result['inputs'] + result['outputs'])
    assert all('assignment' not in p['binding'] for p in connected)
    assert result['source_sha256s'] == [before['model_snapshot']['source_files'][0]['sha256']]
    assert result['model_revision_id'] == before['model_snapshot']['model_revision_id']
    assert result['answer_digest'] == e['answer']['digest']
    assert result['configuration_digest'] == before['configuration']['digest']
    assert result['digest'] == digest({k: v for k, v in result.items() if k != 'digest'})
    assert result['run_ids'] == []
    assert 'source_files' not in response.text and 'candidate-executed' not in response.text
    assert not e['canary'].exists()
    assert e['client'].get(url(e)).json()['data'] == result
    assert e['frozen'] == before


def test_old_answer_keeps_exact_basis_after_new_answer_replaces_head(basis_env):
    e = basis_env
    first = e['client'].get(url(e)).json()['data']
    newer = saved(e, body(e, expected_revision=e['answer']['answer_version_id']))
    assert e['client'].get(url(e)).json()['data'] == first
    assert e['client'].get(url(e, answer=newer['answer_version_id'])).status_code == 404


def test_synthesis_resolves_exact_case_answer_reference(basis_env):
    e = basis_env
    request = body(e, case_id=None)
    request['basis']['case_answer_version_ids'] = [e['answer']['answer_version_id']]
    synthesis = saved(e, request)
    response = e['client'].get(url(e, answer=synthesis['answer_version_id']))
    assert response.status_code == 200, response.text
    assert response.json()['data']['answer_digest'] == synthesis['digest']


def test_run_only_basis_resolves_its_exact_configuration_without_claiming_calculated(basis_env):
    e = basis_env
    revision = e['frozen']['configuration']['configuration_revision_id']
    run_id, command_id = uid(), uid()
    with e['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO run_associations '
            '(run_id,study_id,configuration_revision_id,command_id) VALUES(?,?,?,?)',
            (run_id, e['sid'], revision, command_id),
        )
        db.execute('INSERT INTO outbox VALUES(?,?,?)', (run_id, 'accepted_run', '{}'))
    e['store'].command(
        e['actor'],
        e['sid'],
        'run',
        command_id,
        {},
        lambda db: dict(run_id=run_id),
        receipt_state='accepted_run',
    )
    request = body(e, expected_revision=e['answer']['answer_version_id'])
    request['basis']['run_ids'] = [run_id]
    e['answer'] = saved(e, request)
    response = e['client'].get(url(e))
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['run_ids'] == [run_id]
    assert all('value' not in output for output in result['outputs'])
    assert 'calculated' not in response.text.lower()


@pytest.mark.parametrize('role,status', [('reader', 200), ('writer', 200), ('absent', 404)])
def test_current_membership_controls_basis_reads(basis_env, role, status):
    e = basis_env
    with e['store'].connection(write=True) as db:
        if role == 'absent':
            db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
        else:
            db.execute('UPDATE memberships SET role=? WHERE study_id=?', (role, e['sid']))
    assert e['client'].get(url(e)).status_code == status


def test_absent_resources_and_unknown_query_are_refused(basis_env):
    e = basis_env
    assert e['client'].get(url(e, answer=uid())).status_code == 404
    assert e['client'].get(url(e, revision=uid())).status_code == 404
    assert e['client'].get(url(e) + '?latest=true').status_code == 400


@pytest.mark.parametrize(
    'change', ['missing', 'duplicate', 'connected_assignment', 'boolean', 'source', 'pin']
)
def test_corrupt_or_incomplete_frozen_basis_never_projects_defaults(basis_env, change):
    e = basis_env
    c, m = e['frozen']['configuration'], e['frozen']['model_snapshot']
    if change == 'missing':
        c['inputs'].pop()
    elif change == 'duplicate':
        c['inputs'].append(deepcopy(c['inputs'][0]))
    elif change == 'connected_assignment':
        c['inputs'][0]['target'] = m['connections'][0]['target_ref']
    elif change == 'boolean':
        c['inputs'][0]['value'] = True
    elif change == 'source':
        m['source_files'][0]['sha256'] = 'b' * 64
    elif change == 'pin':
        c['model_revision_id'] = uid()
    signed(c)
    signed(m)
    rewrite(e)
    response = e['client'].get(url(e))
    assert response.status_code == 409, response.text
    assert response.json()['error']['code'] == 'corrupt_retained_record'
    assert not e['canary'].exists()
