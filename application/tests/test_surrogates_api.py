"""Public immutable publication/authorization; numerical truth has native coverage."""

from copy import deepcopy
import base64
import hashlib
import json
import threading
import time

import pytest

from hyprn_mvp_app.contracts import digest, uid
from hyprn_mvp_app.surrogates import Surrogates
from hyprn_mvp_app.exploration import quantities
from test_exploration_design_api import design
from test_sampling_api import (
    sample_env,
    basis_env,
    answer_env,
    api,
    generated,
    request,
    submit,
    read,
    RUNTIME,
)  # noqa: F401
from test_approach_api import assert_http


def build_request(e):
    d = design(e)
    d['combinations'] = d['combinations'][:1]
    # The synthetic design transport retains full vectors, without executing them.
    for item in d['combinations'][0]['dimensions']:
        item['step'] = None
    root = '/api/1/studies/' + e['sid']
    saved = e['client'].post(root + '/exploration-designs', json=d)
    assert saved.status_code == 201, saved.text
    body = request(e)
    body.update(schema_version='2', category_dimensions=d['category_dimensions'])
    body['combinations'] = [dict(body['combinations'][0], **d['combinations'][0])]
    body['combinations'][0]['tolerances'] = [
        dict(target=o['target'], absolute=0.1, relative=0.01) for o in quantities(e['frozen'])[1]
    ]
    submit(e, body)
    e['samples'].process_one(e['native'])
    e['samples'].control(
        e['actor'], e['sid'], body['command_id'], dict(command_id=uid(), action='cancel')
    )
    e['samples'].process_one(e['native'])
    return dict(
        schema_version='1',
        command_id=uid(),
        design_id=d['command_id'],
        sample_operation_id=body['command_id'],
    )


class NumericTransport:
    def __init__(self):
        self.calls = []

    def explore(self, request):
        self.calls.append(request)
        p = request['payload']
        output = dict(
            method=None,
            state=None,
            reason='incomplete_samples',
            metrics=dict(
                assessed_count=0,
                evaluable_count=0,
                failed_count=1,
                max_absolute_error=None,
                rmse=None,
                target_met=False,
            ),
            comparisons=[],
        )
        artifact = dict(
            schema_version='1',
            openmdao_version='3.45.1',
            bounds=p['bounds'],
            training_vectors=[r['x'] for r in p['training']],
            outputs=[output for _ in p['tolerances']],
        )
        result = dict(identity=request['identity'], artifact=artifact)
        return dict(
            result=result,
            runtime=dict(RUNTIME, image_digest='sha256:' + 'c' * 64),
            request_sha256=digest(request),
            result_sha256=digest(result),
            process_uuid=uid(),
            store_uuid=uid(),
            artifact_uuid=uid(),
        )

    def surrogate(self, request, runtime):
        self.calls.append(request)
        if request['operation'] == 'warm':
            return dict(identity=request['identity'], warmed=True)
        return dict(
            identity=request['identity'],
            values=[
                [dict(value=None, reason='incomplete_samples')]
                for _ in request['payload']['queries']
            ],
        )


def test_assessed_artifact_keeps_original_runtime_and_never_invents_ready(sample_env, generated):
    e = sample_env
    body = build_request(e)
    path = '/api/1/studies/' + e['sid'] + '/exploration-surrogates'
    reply = e['client'].post(path, json=body)
    assert reply.status_code == 202, reply.text
    assert_http(generated, '/studies/{study_id}/exploration-surrogates', 'post', reply)
    native, owner = NumericTransport(), Surrogates(e['store'])
    assert owner.process_one(native)
    assert not owner.process_one(native)
    result = e['client'].get(path + '/' + body['command_id'])
    assert_http(generated, '/studies/{study_id}/exploration-surrogates/{version_id}', 'get', result)
    result = result.json()['data']
    assert result['state'] == 'assessed'
    assert result['groups'][0]['original_runtime'] == RUNTIME
    assert result['groups'][0]['computation_runtime'] != RUNTIME
    assert result['groups'][0]['outputs'][0]['reason'] == 'incomplete_samples'
    assert e['client'].post(path, json=body).json()['data'] == result
    page = e['client'].get(path, params=dict(answer_version_id=e['answer']['answer_version_id']))
    assert page.json()['data'] == [result]
    artifact = e['client'].get(path + '/' + body['command_id'] + '/artifacts/0')
    assert artifact.status_code == 200
    content = artifact.json()['data']
    raw = base64.b64decode(content['bytes_base64'])
    assert len(raw) == content['size']
    assert hashlib.sha256(raw).hexdigest() == content['sha256']
    assert json.loads(raw)['openmdao_version'] == '3.45.1'
    assert e['client'].get(path + '/' + body['command_id'] + '/artifacts/1').status_code == 404
    warm = e['client'].post(path + '/' + body['command_id'] + '/warm', json=dict(command_id=uid()))
    assert warm.status_code == 202
    assert (
        e['client']
        .post(path + '/' + body['command_id'] + '/warm', json=dict(command_id=uid()))
        .status_code
        == 429
    )
    assert owner.process_one(native)
    warmed = e['client'].get(
        '/api/1/studies/' + e['sid'] + '/exploration-warm/' + warm.json()['data']['command_id']
    )
    assert warmed.json()['data']['state'] == 'ready'
    assert [c['operation'] for c in native.calls] == ['build', 'warm']
    refinement = dict(body, command_id=uid())
    assert e['client'].post(path, json=refinement).status_code == 202
    assert e['client'].get(path + '/' + body['command_id']).json()['data'] == result
    cancelled = e['client'].post(
        path + '/' + refinement['command_id'] + '/cancel', json=dict(command_id=uid())
    )
    assert cancelled.json()['data']['state'] == 'cancelled'
    assert not owner.process_one(native)
    assert e['client'].get(path + '/' + body['command_id']).json()['data'] == result
    with e['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    assert e['client'].get(path + '/' + body['command_id'] + '/artifacts/0').status_code == 404
    denied = e['client'].post(
        path + '/' + body['command_id'] + '/predictions',
        json=dict(
            schema_version='1',
            selection_token=uid(),
            combination=0,
            inputs=[
                dict(target=p['target'], value=1, units=p['units'])
                for p in e['frozen']['configuration']['inputs']
            ],
            axis=None,
            curve_points=0,
        ),
    )
    assert denied.status_code == 404
    assert not owner.process_one(native)
    assert [c['operation'] for c in native.calls] == ['build', 'warm']


@pytest.mark.parametrize('operation', ['build', 'cancel', 'query'])
def test_cancelled_or_unauthorized_versions_never_reach_numerical_work(sample_env, operation):
    e = sample_env
    body = build_request(e)
    path = '/api/1/studies/' + e['sid'] + '/exploration-surrogates'
    assert e['client'].post(path, json=body).status_code == 202
    owner, native = Surrogates(e['store']), NumericTransport()
    if operation == 'cancel':
        reply = e['client'].post(
            path + '/' + body['command_id'] + '/cancel', json=dict(command_id=uid())
        )
        assert reply.json()['data']['state'] == 'cancelled'
    else:
        with e['store'].connection(write=True) as db:
            db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    owner.process_one(native)
    assert not native.calls


@pytest.mark.parametrize('change', ['pickle', 'source', 'bool', 'unsafe', 'extra', 'missing'])
def test_closed_prediction_rejects_untrusted_or_incomplete_data(sample_env, change):
    e = sample_env
    body = dict(
        schema_version='1',
        selection_token=uid(),
        combination=0,
        inputs=[
            dict(target=p['target'], value=1, units=p['units'])
            for p in e['frozen']['configuration']['inputs']
        ],
        axis=None,
        curve_points=0,
    )
    if change in ('pickle', 'source', 'extra'):
        body[change] = '__import__("os")'
    elif change == 'bool':
        body['inputs'][0]['value'] = True
    elif change == 'unsafe':
        body['inputs'][0]['value'] = 2**53
    else:
        del body['inputs']
    response = e['client'].post(
        '/api/1/studies/' + e['sid'] + '/exploration-surrogates/' + uid() + '/predictions',
        json=body,
    )
    assert response.status_code == 400, response.text
