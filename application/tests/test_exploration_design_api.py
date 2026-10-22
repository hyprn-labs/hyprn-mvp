"""Declared tuples, complete free inputs and stepped independent samples at HTTP."""

from copy import deepcopy

import pytest

from hyprn_mvp_app.contracts import uid
from test_sampling_api import (
    sample_env,
    basis_env,
    answer_env,
    api,
    generated,
    request,
    submit,
    read,
)  # noqa: F401
from test_approach_api import assert_http


def design(e):
    c = e['frozen']['configuration']
    dims = [
        dict(
            target=p['target'],
            units=p['units'],
            lower=0,
            upper=10,
            step=1,
            covary_group=None,
            common_key='common' if i == 0 else None,
        )
        for i, p in enumerate(c['inputs'])
    ]
    return dict(
        schema_version='1',
        command_id=uid(),
        answer_version_id=e['answer']['answer_version_id'],
        category_dimensions=[
            dict(name='material', values=['a', 'b']),
            dict(name='regime', values=['low', 'high', 'unsupported']),
        ],
        combinations=[
            dict(
                categories=[m, r],
                configuration_revision_id=c['configuration_revision_id'],
                model_id=c['model_id'],
                model_revision_id=c['model_revision_id'],
                initial_axis=dims[0]['target'],
                dimensions=deepcopy(dims),
            )
            for m in ('a', 'b')
            for r in ('low', 'high')
        ],
        rationale='Explicit generic combinations and independent integer coordinates',
    )


def test_design_save_read_list_is_inert_pinned_and_supports_all_four_tuples(sample_env, generated):
    e = sample_env
    body = design(e)
    path = '/api/1/studies/' + e['sid'] + '/exploration-designs'
    reply = e['client'].post(path, json=body)
    assert reply.status_code == 201, reply.text
    assert_http(generated, '/studies/{study_id}/exploration-designs', 'post', reply)
    assert e['client'].post(path, json=body).json()['data'] == reply.json()['data']
    assert e['client'].get(path + '/' + body['command_id']).json()['data']['request'] == body
    page = e['client'].get(path, params=dict(answer_version_id=body['answer_version_id']))
    assert_http(generated, '/studies/{study_id}/exploration-designs', 'get', page)
    assert len(page.json()['data'][0]['request']['combinations']) == 4
    assert not e['native'].calls and not e['canary'].exists()
    bad = deepcopy(body)
    bad['rationale'] = 'changed'
    assert e['client'].post(path, json=bad).status_code == 409
    for _ in range(21):
        assert e['client'].post(path, json=dict(body, command_id=uid())).status_code == 201
    page = e['client'].get(path, params=dict(answer_version_id=body['answer_version_id'])).json()
    assert len(page['data']) == 20
    tail = (
        e['client']
        .get(
            path,
            params=dict(answer_version_id=body['answer_version_id'], cursor=page['next_cursor']),
        )
        .json()
    )
    assert len(tail['data']) == 2 and tail['next_cursor'] is None
    with e['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    assert (
        e['client'].get(path, params=dict(answer_version_id=body['answer_version_id'])).status_code
        == 404
    )


@pytest.mark.parametrize(
    'change',
    [
        'unknown_tuple',
        'duplicate_tuple',
        'model_pin',
        'missing_input',
        'connected',
        'units',
        'step',
        'bool',
        'covary',
        'common',
    ],
)
def test_invalid_design_reports_no_execution_or_record(sample_env, change):
    e = sample_env
    body = design(e)
    combo = body['combinations'][0]
    d = combo['dimensions'][0]
    if change == 'unknown_tuple':
        combo['categories'][0] = 'unknown'
    elif change == 'duplicate_tuple':
        body['combinations'][1]['categories'] = combo['categories']
    elif change == 'model_pin':
        combo['model_revision_id'] = uid()
    elif change == 'missing_input':
        combo['dimensions'].pop()
    elif change == 'connected':
        d['target']['port_id'] = uid()
    elif change == 'units':
        d['units'] = 'km'
    elif change == 'step':
        d['step'] = 3
    elif change == 'bool':
        d['lower'] = False
    elif change == 'covary':
        for p in combo['dimensions']:
            p['covary_group'] = 'explicit'
    elif change == 'common':
        combo['dimensions'][1]['common_key'] = 'common'
    path = '/api/1/studies/' + e['sid'] + '/exploration-designs'
    reply = e['client'].post(path, json=body)
    assert reply.status_code in (400, 409), reply.text
    if change != 'model_pin':
        assert reply.json()['error']['fields'][0]['path'].startswith('/combinations')
    assert not e['native'].calls and not e['canary'].exists()


def sample2(e):
    body = request(e)
    d = design(e)
    body.update(schema_version='2', category_dimensions=d['category_dimensions'])
    body['combinations'] = [dict(body['combinations'][0], **d['combinations'][0])]
    return body


def test_explicit_step_vectors_survive_sample_receipt_and_listing(sample_env, generated):
    e = sample_env
    body = sample2(e)
    submit(e, body)
    assert e['samples'].process_one(e['native'])
    result = read(e, body)
    assert result['schema_version'] == '2' and result['state'] == 'sampling'
    assert len(result['points']) == 5
    assert all(v['value'].is_integer() for p in result['points'] for v in p['inputs'])
    assert len({p['identity'] for p in result['points']}) == 5
    page = e['client'].get(
        e['path'], params=dict(answer_version_id=e['answer']['answer_version_id'])
    )
    assert_http(generated, '/studies/{study_id}/exploration-samples', 'get', page)
    assert page.json()['data'] == [result]


def test_missing_range_can_be_saved_but_never_sampled(sample_env):
    e = sample_env
    d = design(e)
    d['combinations'][0]['dimensions'][0].update(lower=None, upper=None, step=None, common_key=None)
    path = '/api/1/studies/' + e['sid'] + '/exploration-designs'
    assert e['client'].post(path, json=d).status_code == 201
    body = sample2(e)
    body['combinations'][0]['dimensions'] = d['combinations'][0]['dimensions']
    reply = e['client'].post(e['path'] + '/preview', json=body)
    assert reply.status_code == 400
    assert reply.json()['error']['fields'][0]['code'] == 'missing_range'


def test_quantization_collision_never_relabels_an_independent_check(sample_env):
    e = sample_env
    body = sample2(e)
    # Six representable vectors exist, but the synthetic transport maps two
    # generated rows onto one; no scalar configuration may be submitted.
    body['combinations'][0]['dimensions'][0].update(upper=20, step=10)
    body['combinations'][0]['dimensions'][1].update(upper=14, step=7)
    submit(e, body)
    e['samples'].process_one(e['native'])
    result = read(e, body)
    assert result['state'] != 'sampling'
    assert result['attempted_count'] == 0 and result['points'] == []


def test_declared_covary_mapping_keeps_distinct_port_occurrences_equal(sample_env):
    from test_exploration_api import rewrite

    e = sample_env
    e['frozen']['configuration']['inputs'][1]['value'] = 0
    rewrite(e)
    body = sample2(e)
    for dimension in body['combinations'][0]['dimensions']:
        dimension['covary_group'] = 'explicit'
    submit(e, body)
    e['samples'].process_one(e['native'])
    result = read(e, body)
    assert result['state'] == 'sampling'
    assert len(e['native'].calls[0]['groups'][0]['bounds']) == 1
    for point in result['points']:
        assert point['inputs'][0]['target'] != point['inputs'][1]['target']
        assert point['inputs'][0]['value'] == point['inputs'][1]['value']
    assert not e['canary'].exists()


def test_insufficient_integer_domain_is_actionable_before_design(sample_env):
    from test_exploration_api import rewrite

    e = sample_env
    for p in e['frozen']['configuration']['inputs']:
        p['value'] = 0
    rewrite(e)
    body = sample2(e)
    for d in body['combinations'][0]['dimensions']:
        d.update(lower=0, upper=1, step=1)
    reply = e['client'].post(e['path'] + '/preview', json=body)
    assert reply.status_code == 400
    assert reply.json()['error']['fields'][0]['code'] == 'insufficient_distinct_points'
    assert not e['native'].calls


def test_small_explicit_step_does_not_overflow_domain_cardinality(sample_env):
    e = sample_env
    body = sample2(e)
    for d in body['combinations'][0]['dimensions']:
        d['step'] = 1e-300
    reply = e['client'].post(e['path'] + '/preview', json=body)
    assert reply.status_code == 200, reply.text
    assert reply.json()['data']['new_count'] == 5
    assert not e['native'].calls


def test_display_selection_is_answer_bound_versioned_and_never_prepares(sample_env, generated):
    e = sample_env
    a = e['answer']['answer_version_id']
    c = e['frozen']['configuration']['configuration_revision_id']
    root = '/api/1/studies/' + e['sid'] + '/answers/' + a
    path = root + '/exploration-view/' + c
    template = '/studies/{study_id}/answers/{answer_version_id}/exploration-view/{configuration_revision_id}'
    basis = e['client'].get(root + '/exploration-basis/' + c).json()['data']
    assert e['client'].get(path).json()['data'] is None
    body = dict(schema_version='1', command_id=uid(), expected_revision=None,
                input_targets=[p['target'] for p in basis['inputs'] if p['binding']['kind'] == 'free'],
                output_targets=[basis['outputs'][0]['target']])
    r = e['client'].post(path, json=body)
    assert r.status_code == 201, r.text
    assert_http(generated, template, 'post', r)
    saved = r.json()['data']
    assert e['client'].post(path, json=body).json()['data'] == saved
    readback = e['client'].get(path)
    assert_http(generated, template, 'get', readback)
    assert readback.json()['data'] == saved
    stale = dict(body, command_id=uid(), input_targets=[])
    assert e['client'].post(path, json=stale).status_code == 409
    next_body = dict(stale, command_id=uid(), expected_revision=saved['view_revision_id'])
    assert e['client'].post(path, json=next_body).status_code == 201
    assert e['client'].get(path).json()['data']['request']['input_targets'] == []
    assert e['client'].get(root + '/exploration-basis/' + c).json()['data'] == basis
    for field, values in [('input_targets', body['output_targets']),
                          ('output_targets', body['output_targets'] * 2),
                          ('output_targets', []),
                          ('output_targets', [dict(instance_id=uid(), port_id=uid())])]:
        bad = dict(next_body, command_id=uid(), **{field: values})
        assert e['client'].post(path, json=bad).status_code == 400
    assert e['client'].get(path + '?unknown=1').status_code == 400
    with e['store'].connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE study_id=?", (e['sid'],))
    assert e['client'].get(path).status_code == 200
    assert e['client'].post(path, json=dict(body, command_id=uid())).status_code == 403
    with e['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    assert e['client'].get(path).status_code == 404
    assert e['client'].post(path, json=dict(body, command_id=uid())).status_code == 404
    assert not e['native'].calls and not e['canary'].exists()
