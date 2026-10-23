"""Sampled calculation versions, member run requests and estimates over public HTTP.

The design and fit transports return data only: they do not establish numerical accuracy or
containment (the native groups prove the attested computation path). Runs are recorded
through the real submission, bundle and projection code; nothing is executed.
"""

import base64
import copy
import hashlib
import json
import time

import pytest

from criteria_free import bind_case, insert_case, record_run
from hyprn_mvp_app.calculation_designs import CalculationSamples
from hyprn_mvp_app.calculation_estimates import Estimates
from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.execution import executable_digest
from hyprn_mvp_app.store import digest, uid
from http_contract import assert_http
from test_assumptions_evidence_api import api, generated  # noqa: F401

RUNTIME = dict(
    image_digest='sha256:' + 'a' * 64,
    architecture='arm64',
    python_version='3.12.15',
    worker_entrypoint='hyprn_mvp_integration.worker',
    policy_digest='b' * 64,
)


class DesignTransport:
    """Seeded-design stand-in: appends distinct vectors 1, 2, 3, ... after retained rows."""

    def __init__(self):
        self.calls = []

    def explore(self, request):
        self.calls.append(request)
        groups = []
        for group in request['groups']:
            rows = copy.deepcopy(group['retained'])
            taken = {tuple(r['vector']) for r in rows}
            n = 0
            for partition, key in [('training', 'training_count'), ('check', 'check_count')]:
                while sum(r['partition'] == partition for r in rows) < group[key]:
                    n += 1
                    vector = [float(n)] * len(group['bounds'])
                    if tuple(vector) not in taken:
                        rows.append(dict(partition=partition, vector=vector))
            groups.append(rows)
        result = dict(
            schema_version='2',
            identity=request['identity'],
            groups=groups,
            scipy_version='fixture',
            compute_seconds=0,
        )
        return dict(
            result=result,
            runtime=RUNTIME,
            request_sha256=digest(request),
            result_sha256=digest(result),
            process_uuid=uid(),
            store_uuid=uid(),
            artifact_uuid=uid(),
            elapsed_seconds=0,
        )


class FitTransport:
    """Fit stand-in: every output is assessed and unusable (an estimate is never invented)."""

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
                failed_count=len(p['checks']),
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


def canary_source(frozen, canary):
    """Replace the reference's candidate source with one that marks ``canary`` if imported.
    Only the saved model snapshot is re-signed; nothing here prepares or executes it."""
    model = frozen['model_snapshot']
    (source_file,) = model['source_files']
    source = ('from pathlib import Path\nPath(' + repr(str(canary)) + ').touch()\n').encode()
    sha = hashlib.sha256(source).hexdigest()
    for definition in model['definitions']:
        definition['source_refs'] = [
            sha if ref == source_file['sha256'] else ref for ref in definition['source_refs']
        ]
    source_file.update(bytes=base64.b64encode(source).decode(), sha256=sha)
    model['digest'] = digest({k: v for k, v in model.items() if k != 'digest'})


def reference_env(api, tmp_path, *, canary=True):  # noqa: F811
    """A version-6 reference on a Model4 revision with two free dimensionless inputs (saved
    values 0 and 7) and one output; with ``canary`` its candidate source marks a file if it is
    ever imported (its captured preparation then no longer matches, so no run is recorded)."""
    e = dict(api)
    e['canary'] = tmp_path / 'candidate-executed'
    case = bind_case('unrelated', e['sid'], study_revision=e['study']['revision'])
    if canary:
        canary_source(case['frozen'], e['canary'])
    config = case['frozen']['configuration']
    for item, value in zip(config['inputs'], [0, 7], strict=True):
        item['value'] = value
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    insert_case(e['store'], e['sid'], case)
    e['store'].publish_execution_observation('ready', None, time.time(), RUNTIME)
    e.update(
        case=case,
        reference=config['configuration_revision_id'],
        samples=CalculationSamples(e['store'], Configurations(e['store'], None)),
        estimates=Estimates(e['store']),
        native=DesignTransport(),
    )
    return e


@pytest.fixture
def env(api, tmp_path):  # noqa: F811
    return reference_env(api, tmp_path)


@pytest.fixture
def recordable(api, tmp_path):  # noqa: F811
    return reference_env(api, tmp_path, canary=False)


def path(e, suffix):
    return '/api/1/studies/' + e['sid'] + '/' + suffix


def sample_request(e, *, training=3, check=2, calculation=None, expected=None, **changes):
    inputs = e['case']['frozen']['configuration']['inputs']
    return (
        dict(
            command_id=uid(),
            calculation_id=calculation,
            expected_version_id=expected,
            name='Response sweep',
            description='Seeded points around the reference.',
            method='latin_hypercube',
            seed=17,
            groups=[
                dict(
                    reference_configuration_revision_id=e['reference'],
                    dimensions=[
                        dict(
                            target=inputs[0]['target'],
                            lower=0,
                            upper=20,
                            units=inputs[0]['units'],
                            step=None,
                            covary_group=None,
                        )
                    ],
                    training_count=training,
                    check_count=check,
                )
            ],
            rationale='Explore the drive around the reference.',
        )
        | changes
    )


def accept(e, body):
    response = e['client'].post(path(e, 'calculation-samples'), json=body)
    assert response.status_code == 202, response.text
    return response.json()['data']


def operation(e, body):
    response = e['client'].get(path(e, 'calculation-samples/' + body['command_id']))
    assert response.status_code == 200, response.text
    return response.json()['data']


def complete(e, body):
    """Accept and advance through the design and configuration steps."""
    accept(e, body)
    assert e['samples'].process_one(e['native'])
    assert e['samples'].process_one(e['native'])
    result = operation(e, body)
    assert result['state'] == 'complete', result
    version = (
        e['client']
        .get(path(e, 'calculation-versions/' + result['calculation_version_id']))
        .json()['data']
    )
    return result, version


def receipts(e, category):
    with e['store'].connection() as db:
        return db.execute(
            'SELECT COUNT(*) FROM receipts WHERE category=?', (category,)
        ).fetchone()[0]


def test_a_sampled_version_freezes_generated_points_and_never_runs_candidate_code(
    env,
    generated,  # noqa: F811
):
    e = env
    body = sample_request(e)
    reply = e['client'].post(path(e, 'calculation-samples'), json=body)
    assert reply.status_code == 202, reply.text
    assert_http(generated, '/studies/{study_id}/calculation-samples', 'post', reply)
    accepted = reply.json()['data']
    assert accepted['state'] == 'pending' and accepted['point_count'] == 5
    # Acceptance is inert: no design call, no configuration, no candidate import.
    assert not e['native'].calls and not e['canary'].exists()
    assert (
        e['client'].post(path(e, 'calculation-samples'), json=body).json()['data'] == accepted
    )
    assert e['samples'].process_one(e['native'])
    assert operation(e, body)['state'] == 'configuring'
    assert e['samples'].process_one(e['native'])
    assert not e['samples'].process_one(e['native'])
    status = e['client'].get(path(e, 'calculation-samples/' + body['command_id']))
    assert_http(
        generated, '/studies/{study_id}/calculation-samples/{operation_id}', 'get', status
    )
    result = status.json()['data']
    assert result['state'] == 'complete' and result['calculation_version_id']
    listed = e['client'].get(path(e, 'calculation-samples'))
    assert_http(generated, '/studies/{study_id}/calculation-samples', 'get', listed)
    assert listed.json()['data']['items'] == [result]
    version = e['client'].get(
        path(e, 'calculation-versions/' + result['calculation_version_id'])
    )
    assert_http(
        generated, '/studies/{study_id}/calculation-versions/{version_id}', 'get', version
    )
    content = version.json()['data']['content']
    design = content['design']
    assert design['kind'] == 'sampled' and design['seed'] == 17
    assert design['runtime'] == RUNTIME and design['operation_id'] == body['command_id']
    assert [p['partition'] for p in design['points']].count('check') == 2
    assert content['configuration_revision_ids'] == [
        p['configuration_revision_id'] for p in design['points']
    ]
    reference = e['case']['frozen']['configuration']
    for index, point in enumerate(design['points'], start=1):
        frozen = (
            e['client']
            .get(path(e, 'configurations/' + point['configuration_revision_id']))
            .json()['data']
        )
        config = frozen['configuration']
        assert config['name'] == f"{body['name']} · Point {index}"
        assert config['name'] != reference['name']
        # Only the sampled input moves; the other keeps its saved value and every pin holds.
        assert [i['value'] for i in config['inputs']] == point['vector'] + [7]
        assert [i['units'] for i in config['inputs']] == [
            i['units'] for i in reference['inputs']
        ]
        assert config['model_revision_id'] == reference['model_revision_id']
        assert frozen['model_snapshot'] == e['case']['frozen']['model_snapshot']
    assert len(e['native'].calls) == 1 and e['native'].calls[0]['seed'] == 17
    assert not e['canary'].exists()


def test_adding_points_creates_a_version_that_keeps_every_existing_point(env):
    e = env
    first, version = complete(e, sample_request(e))
    more = sample_request(
        e,
        training=5,
        calculation=first['calculation_id'],
        expected=first['calculation_version_id'],
        name='Response sweep, denser',
    )
    second, extended = complete(e, more)
    assert extended['version_number'] == 2
    assert extended['predecessor_version_id'] == first['calculation_version_id']
    assert second['retained_count'] == 5 and second['point_count'] == 7
    before = {
        (p['identity'], p['partition'], p['configuration_revision_id'])
        for p in version['content']['design']['points']
    }
    after = {
        (p['identity'], p['partition'], p['configuration_revision_id'])
        for p in extended['content']['design']['points']
    }
    assert before < after and len(after) == 7
    # The design call received the kept points unchanged.
    assert len(e['native'].calls[1]['groups'][0]['retained']) == 5
    # The first version keeps its exact set.
    again = e['client'].get(
        path(e, 'calculation-versions/' + version['calculation_version_id'])
    )
    assert again.json()['data'] == version
    # A stale latest version is refused before acceptance.
    stale = e['client'].post(
        path(e, 'calculation-samples'),
        json=sample_request(
            e, calculation=first['calculation_id'], expected=first['calculation_version_id']
        ),
    )
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'


@pytest.mark.parametrize(
    'mutation',
    [
        'units',
        'connected_or_unknown',
        'empty_range',
        'off_grid',
        'grid_too_small',
        'bool_seed',
        'float_count',
        'non_finite',
        'duplicate_reference',
        'unknown_reference',
        'half_named_version',
        'covary_mismatch',
        'unknown_field',
    ],
)
def test_an_invalid_declaration_is_refused_before_any_receipt(env, mutation):
    e = env
    body = sample_request(e)
    dimension = body['groups'][0]['dimensions'][0]
    raw = None
    if mutation == 'units':
        dimension['units'] = 'm'
    elif mutation == 'connected_or_unknown':
        dimension['target'] = dict(dimension['target'], port_id=uid())
    elif mutation == 'empty_range':
        dimension['upper'] = 0
    elif mutation == 'off_grid':
        dimension['step'] = 3
    elif mutation == 'grid_too_small':
        dimension.update(upper=2, step=1)
    elif mutation == 'bool_seed':
        body['seed'] = True
    elif mutation == 'float_count':
        body['groups'][0]['training_count'] = 3.0
    elif mutation == 'non_finite':
        raw = json.dumps(body).replace('"upper": 20', '"upper": Infinity')
    elif mutation == 'duplicate_reference':
        body['groups'].append(copy.deepcopy(body['groups'][0]))
    elif mutation == 'unknown_reference':
        body['groups'][0]['reference_configuration_revision_id'] = uid()
    elif mutation == 'half_named_version':
        body['calculation_id'] = uid()
    elif mutation == 'covary_mismatch':
        other = e['case']['frozen']['configuration']['inputs'][1]
        dimension['covary_group'] = 'linked'
        body['groups'][0]['dimensions'].append(
            dict(dimension, target=other['target'], upper=10)
        )
    elif mutation == 'unknown_field':
        body['pickle'] = 'untrusted'
    response = (
        e['client'].post(
            path(e, 'calculation-samples'),
            content=raw,
            headers={'Content-Type': 'application/json'},
        )
        if raw
        else e['client'].post(path(e, 'calculation-samples'), json=body)
    )
    assert response.status_code in (400, 404, 422), response.text
    assert receipts(e, 'calculation_sample') == 0
    assert not e['native'].calls and not e['canary'].exists()


def test_sampling_needs_a_current_ready_execution_observation(env):
    e = env
    e['store'].publish_execution_observation('unavailable', 'executor_unavailable', time.time())
    response = e['client'].post(path(e, 'calculation-samples'), json=sample_request(e))
    assert response.status_code == 503
    assert receipts(e, 'calculation_sample') == 0


def test_an_unknown_design_outcome_is_never_redispatched(env):
    e = env
    body = sample_request(e)
    accept(e, body)

    class Unknown:
        calls = 0

        def explore(self, request):
            Unknown.calls += 1
            raise TimeoutError('Unknown artifact outcome')

    assert e['samples'].process_one(Unknown())
    result = operation(e, body)
    assert result['state'] == 'uncertain' and result['reason'] == 'design_outcome_unknown'
    assert not e['samples'].process_one(Unknown()) and Unknown.calls == 1
    with e['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM calculation_versions').fetchone()[0] == 0


def test_a_client_never_writes_a_sampled_design_but_may_carry_it_unchanged(env):
    e = env
    first, version = complete(e, sample_request(e))
    content = copy.deepcopy(version['content'])
    created = e['client'].post(
        path(e, 'calculations'), json=dict(command_id=uid(), content=content)
    )
    assert created.status_code == 422, created.text
    renamed = e['client'].post(
        path(e, 'calculations/' + first['calculation_id'] + '/versions'),
        json=dict(
            command_id=uid(),
            expected_version_id=first['calculation_version_id'],
            content=dict(content, name='Renamed sweep'),
        ),
    )
    assert renamed.status_code == 201, renamed.text
    assert renamed.json()['data']['content']['design'] == content['design']
    dropped = dict(
        content, configuration_revision_ids=content['configuration_revision_ids'][1:]
    )
    dropped['design'] = dict(content['design'], points=content['design']['points'][1:])
    refused = e['client'].post(
        path(e, 'calculations/' + first['calculation_id'] + '/versions'),
        json=dict(
            command_id=uid(),
            expected_version_id=renamed.json()['data']['calculation_version_id'],
            content=dropped,
        ),
    )
    assert refused.status_code == 422, refused.text
    # Removing a point by hand makes a hand-picked version.
    hand = e['client'].post(
        path(e, 'calculations/' + first['calculation_id'] + '/versions'),
        json=dict(
            command_id=uid(),
            expected_version_id=renamed.json()['data']['calculation_version_id'],
            content=dict(dropped, design=dict(kind='hand_picked')),
        ),
    )
    assert hand.status_code == 201, hand.text


def test_member_runs_attach_by_reference_and_never_create_a_version(env, generated):  # noqa: F811
    e = env
    first, version = complete(e, sample_request(e))
    members = version['content']['configuration_revision_ids']
    body = dict(command_id=uid(), configuration_revision_ids=members[:2])
    route = path(e, 'calculation-versions/' + first['calculation_version_id'] + '/run-requests')
    reply = e['client'].post(route, json=body)
    assert reply.status_code == 200, reply.text
    assert_http(
        generated,
        '/studies/{study_id}/calculation-versions/{version_id}/run-requests',
        'post',
        reply,
    )
    runs = reply.json()['data']['runs']
    assert [r['configuration_revision_id'] for r in runs] == members[:2]
    assert e['client'].post(route, json=body).json()['data']['runs'] == runs
    listed = (
        e['client']
        .get(path(e, 'calculation-versions/' + first['calculation_version_id'] + '/runs'))
        .json()['data']['items']
    )
    assert [r['run_id'] for r in listed] == [r['run_id'] for r in runs]
    versions = (
        e['client']
        .get(path(e, 'calculations/' + first['calculation_id'] + '/versions'))
        .json()['data']['items']
    )
    assert [v['version_number'] for v in versions] == [1]
    outsider = e['client'].post(
        route, json=dict(command_id=uid(), configuration_revision_ids=[e['reference']])
    )
    assert outsider.status_code == 422
    assert not e['canary'].exists()


def point_case(e, frozen):
    """The captured case re-bound to one generated configuration version, to record its run."""
    case = copy.deepcopy(e['case'])
    case['frozen'] = copy.deepcopy(frozen)
    config = case['frozen']['configuration']
    prepared = case['prepared']
    prepared.update(
        configuration_digest=project_scientific_configuration(copy.deepcopy(config))['digest'],
        configuration_revision_id=config['configuration_revision_id'],
    )
    prepared['executable_content_digest'] = executable_digest(prepared)
    prepared['prepared_digest'] = digest(
        {k: v for k, v in prepared.items() if k != 'prepared_digest'}
    )
    return case


def test_an_estimate_is_fitted_to_one_sampled_version_and_pins_its_runs(
    recordable,
    generated,  # noqa: F811
):
    e = recordable
    first, version = complete(e, sample_request(e))
    target = next(
        dict(instance_id=i['instance_id'], port_id=p['port_id'])
        for i in e['case']['frozen']['model_snapshot']['instances']
        for d in e['case']['frozen']['model_snapshot']['definitions']
        if d['definition_version_id'] == i['definition_version_id']
        for p in d['ports']
        if p['direction'] == 'output'
    )
    # One member gets a recorded run; the others have none and stay unavailable.
    member = version['content']['configuration_revision_ids'][0]
    frozen = e['client'].get(path(e, 'configurations/' + member)).json()['data']
    recorded, _ = record_run(e['store'], e['actor'], e['sid'], point_case(e, frozen), [42])
    body = dict(
        command_id=uid(),
        calculation_version_id=first['calculation_version_id'],
        tolerances=[dict(target=target, absolute=0.1, relative=0.01)],
    )
    reply = e['client'].post(path(e, 'calculation-estimates'), json=body)
    assert reply.status_code == 202, reply.text
    assert_http(generated, '/studies/{study_id}/calculation-estimates', 'post', reply)
    pending = reply.json()['data']
    assert pending['state'] == 'pending'
    pinned = [s for s in pending['samples'] if s['run_id']]
    assert [s['run_id'] for s in pinned] == [recorded]
    assert pinned[0]['configuration_revision_id'] == member
    assert all(s['results_digest'] is None for s in pending['samples'] if not s['run_id'])
    native = FitTransport()
    assert e['estimates'].process_one(native)
    assert not e['estimates'].process_one(native)
    payload = native.calls[0]['payload']
    rows = payload['training'] + payload['checks']
    assert sorted((r['y'] for r in rows), key=str) == sorted([[42]] + [[None]] * 4, key=str)
    read = e['client'].get(path(e, 'calculation-estimates/' + body['command_id']))
    assert_http(
        generated, '/studies/{study_id}/calculation-estimates/{estimate_id}', 'get', read
    )
    estimate = read.json()['data']
    # Every output is assessed and none passed its checks: nothing reads as an estimate.
    assert estimate['state'] == 'assessed'
    assert estimate['groups'][0]['outputs'][0]['reason'] == 'incomplete_samples'
    assert estimate['groups'][0]['computation_runtime'] != estimate['original_runtime']
    page = e['client'].get(
        path(e, 'calculation-versions/' + first['calculation_version_id'] + '/estimates')
    )
    assert_http(
        generated,
        '/studies/{study_id}/calculation-versions/{version_id}/estimates',
        'get',
        page,
    )
    assert page.json()['data']['items'] == [estimate]
    assert (
        e['client'].post(path(e, 'calculation-estimates'), json=body).json()['data'] == estimate
    )
    assert not e['canary'].exists()


def test_an_estimate_needs_a_sampled_version_and_model_outputs(env):
    e = env
    hand = e['client'].post(
        path(e, 'calculations'),
        json=dict(
            command_id=uid(),
            content=dict(
                schema_version='1',
                name='Reference only',
                description='',
                model_id=e['case']['frozen']['configuration']['model_id'],
                model_revision_id=e['case']['frozen']['configuration']['model_revision_id'],
                configuration_revision_ids=[e['reference']],
                design=dict(kind='hand_picked'),
                brief_version_id=None,
                criterion_bindings=[],
            ),
        ),
    )
    assert hand.status_code == 201, hand.text
    port = e['case']['frozen']['configuration']['inputs'][0]['target']
    refused = e['client'].post(
        path(e, 'calculation-estimates'),
        json=dict(
            command_id=uid(),
            calculation_version_id=hand.json()['data']['calculation_version_id'],
            tolerances=[dict(target=port, absolute=0.1, relative=0.01)],
        ),
    )
    assert refused.status_code == 422
    first, _ = complete(e, sample_request(e))
    not_output = e['client'].post(
        path(e, 'calculation-estimates'),
        json=dict(
            command_id=uid(),
            calculation_version_id=first['calculation_version_id'],
            tolerances=[dict(target=port, absolute=0.1, relative=0.01)],
        ),
    )
    assert not_output.status_code == 422
    assert receipts(e, 'calculation_estimate') == 0


def test_readers_read_sampling_and_estimates_but_never_start_them(env):
    e = env
    first, _ = complete(e, sample_request(e))
    with e['store'].connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE study_id=?", (e['sid'],))
    assert e['client'].get(path(e, 'calculation-samples')).status_code == 200
    assert (
        e['client'].post(path(e, 'calculation-samples'), json=sample_request(e)).status_code
        == 403
    )
    with e['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    assert e['client'].get(path(e, 'calculation-samples')).status_code == 404
    assert (
        e['client']
        .get(path(e, 'calculation-versions/' + first['calculation_version_id'] + '/estimates'))
        .status_code
        == 404
    )


class PredictionTransport:
    """Disposable worker stand-in; asserts that renewal loads an artifact, never a fit."""

    def __init__(self):
        self.calls = []
        self.warm = False

    def surrogate(self, request, runtime):
        self.calls.append(request)
        if request['operation'] == 'warm':
            self.warm = True
            return dict(identity=request['identity'], warmed=True)
        assert request['operation'] == 'predict'
        if not self.warm:
            raise RuntimeError('Worker restarted')
        return dict(
            identity=request['identity'],
            values=[
                [dict(value=None, reason='incomplete_samples')]
                for _ in request['payload']['queries']
            ],
        )


def prediction_fixture(e, *, joint=False):
    body = sample_request(e)
    if joint:
        second = e['case']['frozen']['configuration']['inputs'][1]
        body['groups'][0]['dimensions'].append(
            dict(
                target=second['target'],
                units=second['units'],
                lower=0,
                upper=20,
                step=None,
                covary_group=None,
            )
        )
    first, version = complete(e, body)
    member = version['content']['configuration_revision_ids'][0]
    frozen = e['client'].get(path(e, 'configurations/' + member)).json()['data']
    run, _ = record_run(e['store'], e['actor'], e['sid'], point_case(e, frozen), [42])
    from hyprn_mvp_app.quantity_projection import quantities

    target = quantities(frozen)[1][0]['target']
    body = dict(
        command_id=uid(),
        calculation_version_id=first['calculation_version_id'],
        tolerances=[dict(target=target, absolute=0.1, relative=0.01)],
    )
    reply = e['client'].post(path(e, 'calculation-estimates'), json=body)
    assert reply.status_code == 202, reply.text
    assert e['estimates'].process_one(UsableFitTransport() if joint else FitTransport())
    return version, body['command_id'], run, frozen


def test_exploration_pins_runs_and_renews_without_sampling(recordable, generated):  # noqa: F811
    from concurrent.futures import ThreadPoolExecutor
    from hyprn_mvp_app.calculation_exploration import CalculationExploration

    e = recordable
    version, estimate, run, frozen = prediction_fixture(e)
    # A later run cannot replace the assessment's exact original.
    record_run(e['store'], e['actor'], e['sid'], point_case(e, frozen), [99])
    url = path(e, 'calculation-versions/' + version['calculation_version_id'] + '/exploration')
    reply = e['client'].get(url + '?estimate_id=' + estimate)
    assert reply.status_code == 200, reply.text
    assert_http(
        generated,
        '/studies/{study_id}/calculation-versions/{version_id}/exploration',
        'get',
        reply,
    )
    basis = reply.json()['data']
    assert basis['points'][0]['outputs'][0]['value'] == 42
    assert basis['points'][0]['outputs'][0]['run_id'] == run
    request = dict(
        selection_token=uid(),
        group=0,
        inputs=basis['points'][0]['inputs'],
        axis=basis['dimensions'][0]['target'],
        curve_points=5,
    )
    native = PredictionTransport()
    owner = CalculationExploration(e['store'])
    with ThreadPoolExecutor() as pool:
        future = pool.submit(
            e['client'].post,
            path(e, 'calculation-estimates/' + estimate + '/predictions'),
            json=request,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not owner.process_one(native):
            time.sleep(0.01)
        result = future.result(timeout=5)
    assert result.status_code == 200, result.text
    assert_http(
        generated,
        '/studies/{study_id}/calculation-estimates/{estimate_id}/predictions',
        'post',
        result,
    )
    points = result.json()['data']['points']
    assert points[0]['outputs'][0]['kind'] == 'calculated'
    assert points[0]['outputs'][0]['value'] == 42
    assert any(p['outputs'][0]['kind'] == 'unavailable' for p in points[1:])
    assert [c['operation'] for c in native.calls] == ['predict', 'warm', 'predict']
    assert receipts(e, 'calculation_prediction') == 0
    assert receipts(e, 'calculation_sample') == 1
    assert len(e['native'].calls) == 1
    assert not e['canary'].exists()


def test_overlapping_predictions_keep_independent_receipts_and_never_run_models(recordable):
    from concurrent.futures import ThreadPoolExecutor
    from hyprn_mvp_app.calculation_exploration import CalculationExploration

    e = recordable
    version, estimate, _, _ = prediction_fixture(e)
    basis = e['client'].get(
        path(e, 'calculation-versions/' + version['calculation_version_id'] + '/exploration')
        + '?estimate_id=' + estimate
    ).json()['data']
    owner, native = CalculationExploration(e['store']), PredictionTransport()
    request = dict(
        selection_token=uid(), group=0, inputs=basis['points'][0]['inputs'],
        axis=None, curve_points=0,
    )
    url = path(e, 'calculation-estimates/' + estimate + '/predictions')
    with ThreadPoolExecutor() as pool:
        first = pool.submit(e['client'].post, url, json=request)
        deadline = time.monotonic() + 5
        while not receipts(e, 'calculation_prediction') and time.monotonic() < deadline:
            time.sleep(0.01)
        assert receipts(e, 'calculation_prediction') == 1
        second = pool.submit(e['client'].post, url, json=dict(request, selection_token=uid()))
        while (receipts(e, 'calculation_prediction') < 2 and not first.done()
               and time.monotonic() < deadline):
            time.sleep(0.01)
        while time.monotonic() < deadline and not (first.done() and second.done()):
            owner.process_one(native)
            time.sleep(0.01)
        replies = [first.result(timeout=5), second.result(timeout=5)]
    assert [r.status_code for r in replies] == [200, 200], [r.text for r in replies]
    assert all(r.json()['data']['points'][0]['outputs'][0]['kind'] == 'calculated'
               for r in replies)
    assert receipts(e, 'calculation_prediction') == 0
    assert receipts(e, 'calculation_sample') == 1
    assert len(e['native'].calls) == 1 and not e['canary'].exists()
    assert [c['operation'] for c in native.calls].count('warm') == 1


@pytest.mark.parametrize(
    'fault', ['missing', 'duplicate', 'constant', 'units', 'boolean', 'axis']
)
def test_prediction_rejects_incomplete_or_changed_basis(recordable, fault):
    e = recordable
    version, estimate, _, frozen = prediction_fixture(e)
    request = dict(
        selection_token=uid(),
        group=0,
        inputs=[
            dict(target=p['target'], value=p['value'], units=p['units'])
            for p in frozen['configuration']['inputs']
        ],
        axis=None,
        curve_points=0,
    )
    if fault == 'missing':
        request['inputs'].pop()
    elif fault == 'duplicate':
        request['inputs'].append(request['inputs'][0])
    elif fault == 'constant':
        request['inputs'][1]['value'] += 1
    elif fault == 'units':
        request['inputs'][0]['units'] = 'kg'
    elif fault == 'boolean':
        request['inputs'][0]['value'] = True
    else:
        request.update(axis=request['inputs'][1]['target'], curve_points=5)
    reply = e['client'].post(
        path(e, 'calculation-estimates/' + estimate + '/predictions'), json=request
    )
    assert reply.status_code in (400, 422), reply.text
    assert receipts(e, 'calculation_prediction') == 0


class UsableFitTransport(FitTransport):
    """Declared assessed transport double for interaction wiring; not numerical evidence."""

    def explore(self, request):
        result = super().explore(request)
        for output in result['result']['artifact']['outputs']:
            output.update(reason=None, method='response_surface')
            output['metrics'].update(
                target_met=True,
                failed_count=0,
                evaluable_count=2,
                assessed_count=2,
                max_absolute_error=0,
                rmse=0,
            )
        result['result_sha256'] = digest(result['result'])
        return result


class AssessedPredictionTransport(PredictionTransport):
    """Deterministic numerical stand-in for testing full-vector routing, not fit accuracy."""

    def surrogate(self, request, runtime):
        result = super().surrogate(request, runtime)
        if request['operation'] == 'predict':
            result['values'] = [
                [
                    dict(value=sum(row), reason=None)
                    if all(0 <= x <= 20 for x in row)
                    else dict(value=None, reason='outside_bounds')
                ]
                for row in request['payload']['queries']
            ]
        return result


def test_joint_predictions_keep_axis_independent_and_never_extrapolate(recordable):
    from concurrent.futures import ThreadPoolExecutor
    from hyprn_mvp_app.calculation_exploration import CalculationExploration

    e = recordable
    version, estimate, _, frozen = prediction_fixture(e, joint=True)
    owner = CalculationExploration(e['store'])
    native = AssessedPredictionTransport()
    vector = [
        dict(target=p['target'], value=v, units=p['units'])
        for p, v in zip(frozen['configuration']['inputs'], [8, 9], strict=True)
    ]
    for first in (8, 30):
        vector[0]['value'] = first
        request = dict(
            selection_token=uid(),
            group=0,
            inputs=copy.deepcopy(vector),
            axis=vector[1]['target'],
            curve_points=5,
        )
        with ThreadPoolExecutor() as pool:
            future = pool.submit(
                e['client'].post,
                path(e, 'calculation-estimates/' + estimate + '/predictions'),
                json=request,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not owner.process_one(native):
                time.sleep(0.01)
            reply = future.result(timeout=5)
        assert reply.status_code == 200, reply.text
        result = reply.json()['data']['points']
        assert result[0]['outputs'][0]['value'] == (17 if first == 8 else None)
        assert result[0]['outputs'][0]['kind'] == ('estimated' if first == 8 else 'unavailable')
        assert all(p['inputs'][0]['value'] == first for p in result)
        assert {p['inputs'][1]['value'] for p in result[1:]} == {0, 5, 10, 15, 20}
    assert receipts(e, 'calculation_sample') == 1


@pytest.mark.parametrize('mutation', ['run', 'receipt', 'configuration', 'access'])
def test_reused_exploration_rechecks_saved_bytes_and_authority(
    recordable, monkeypatch, mutation
):
    from hyprn_mvp_app.history import History

    e = recordable
    version, estimate, run, frozen = prediction_fixture(e)
    url = path(e, 'calculation-versions/' + version['calculation_version_id'] + '/exploration')
    url += '?estimate_id=' + estimate
    calls = []
    original = History.retained

    def tracked(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(History, 'retained', tracked)
    first = e['client'].get(url)
    assert first.status_code == 200, first.text
    again = e['client'].get(url)
    assert again.json()['data'] == first.json()['data']
    # Publication and HTTP readers use separate owner instances of the same store.
    from hyprn_mvp_app.calculation_exploration import CalculationExploration
    shared = CalculationExploration(e['store']).basis(
        e['actor'], e['sid'], version['calculation_version_id'], estimate_id=estimate
    )
    assert shared == first.json()['data']
    assert len(calls) == 1  # The checked projection is reusable, not its authority.
    if mutation == 'access':
        e['client'].cookies.clear()
    else:
        with e['store'].connection(write=True) as db:
            if mutation == 'run':
                raw = db.execute(
                    'SELECT payload FROM outbox WHERE run_id=?', (run,)
                ).fetchone()[0]
                payload = json.loads(raw)
                payload['history']['results']['outputs'][0]['value'] = 999
                db.execute(
                    'UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(payload), run)
                )
            elif mutation == 'receipt':
                db.execute(
                    "UPDATE receipts SET payload_digest=? WHERE scope=? AND category='run'",
                    ('0' * 64, e['sid']),
                )
            else:
                cid = frozen['configuration']['configuration_revision_id']
                # Simulate damaged storage after bypassing the ordinary immutable writer.
                db.execute('DROP TRIGGER immutable_configuration_update')
                db.execute(
                    "UPDATE configurations SET payload='{}' WHERE configuration_revision_id=?",
                    (cid,),
                )
    refused = e['client'].get(url)
    assert refused.status_code in (401, 404, 409), refused.text
    assert 'points' not in refused.json().get('data', {})


def test_boundary_sampling_versions_and_budget_diagnostics(env):
    e = env
    body = sample_request(e, training=5, method='boundary_latin_hypercube')
    accepted, version = complete(e, body)
    assert accepted['schema_version'] == version['schema_version'] == '2'
    assert version['content']['schema_version'] == '2'
    assert e['native'].calls[0]['schema_version'] == '4'
    assert version['content']['design']['method'] == 'boundary_latin_hypercube'
    # A second independent coordinate needs four corners plus interior training.
    bad = sample_request(e, training=3, method='boundary_latin_hypercube')
    extra = copy.deepcopy(bad['groups'][0]['dimensions'][0])
    extra['target'] = e['case']['frozen']['configuration']['inputs'][1]['target']
    bad['groups'][0]['dimensions'].append(extra)
    refused = e['client'].post(path(e, 'calculation-samples'), json=bad)
    assert refused.status_code == 422
    assert '4 training corners' in refused.text
    assert 'training_count' in refused.text


def test_preparation_reports_coverage_and_accuracy_separately(recordable):
    e = recordable
    _, estimate, _, frozen = prediction_fixture(e)
    from hyprn_mvp_app.quantity_projection import quantities

    target = quantities(frozen)[1][0]['target']
    response = e['client'].post(
        path(e, 'calculation-estimates/' + estimate + '/preparation'),
        json=dict(shown_outputs=[target]),
    )
    assert response.status_code == 200, response.text
    value = response.json()['data']
    assert value['ready'] is False
    assert value['groups'][0]['covered'] is False
    problems = value['groups'][0]['problems']
    assert any('/coverage' in p['path'] for p in problems)
    assert any('/shown_outputs/0' in p['path'] for p in problems)
    with e['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    assert (
        e['client']
        .post(
            path(e, 'calculation-estimates/' + estimate + '/preparation'),
            json=dict(shown_outputs=[target]),
        )
        .status_code
        == 404
    )


def test_box_support_requires_joint_corners_not_marginal_extrema():
    from hyprn_mvp_app.calculation_preparation import box_supported

    bounds = [[0, 1], [0, 1]]
    assert not box_supported(bounds, [[0, 0.5], [1, 0.5], [0.5, 0], [0.5, 1]])
    assert not box_supported(bounds, [[0, 0], [1, 0], [0, 1]])
    assert box_supported(bounds, [[0, 0], [1, 0], [0, 1], [1, 1]])


def test_validation_format_keeps_old_points_and_pins_the_new_estimate(env, generated):
    """Renaming a role never rewrites old records or moves held-out points into training."""
    e = env
    _, old = complete(e, sample_request(e))
    request = sample_request(
        e, training=5, calculation=old['calculation_id'],
        expected=old['calculation_version_id'],
    )
    group = request['groups'][0]
    group['validation_count'] = group.pop('check_count')
    operation, saved = complete(e, request)
    assert operation['schema_version'] == '3'
    assert saved['schema_version'] == saved['content']['schema_version'] == '3'
    design = saved['content']['design']
    assert design['groups'][0]['validation_count'] == 2
    assert 'check_count' not in design['groups'][0]
    assert {p['partition'] for p in design['points']} == {'training', 'validation'}
    before = {p['identity']: p for p in old['content']['design']['points']}
    for point in design['points']:
        if point['identity'] in before:
            previous = before[point['identity']]
            assert point['configuration_revision_id'] == previous['configuration_revision_id']
            assert (point['partition'] == 'validation') == (previous['partition'] == 'check')
    assert e['client'].get(path(e, 'analysis-versions/' + old['calculation_version_id'])).json()[
        'data'
    ] == old
    response = e['client'].get(path(e, 'analysis-versions/' + saved['calculation_version_id']))
    assert_http(generated, '/studies/{study_id}/analysis-versions/{version_id}', 'get', response)
    target = next(
        dict(instance_id=i['instance_id'], port_id=p['port_id'])
        for i in e['case']['frozen']['model_snapshot']['instances']
        for d in e['case']['frozen']['model_snapshot']['definitions']
        if d['definition_version_id'] == i['definition_version_id']
        for p in d['ports'] if p['direction'] == 'output'
    )
    estimate_request = dict(
        command_id=uid(), calculation_version_id=saved['calculation_version_id'],
        tolerances=[dict(target=target, absolute=0.1, relative=0.01)],
    )
    reply = e['client'].post(path(e, 'analysis-estimates'), json=estimate_request)
    assert reply.status_code == 202, reply.text
    assert_http(generated, '/studies/{study_id}/analysis-estimates', 'post', reply)
    estimate = reply.json()['data']
    assert estimate['schema_version'] == '2'
    assert {p['partition'] for p in estimate['samples']} == {'training', 'validation'}
    assert e['estimates'].process_one(FitTransport())
    # No invented values: this transport has no actual model runs or usable estimates.
    result = e['estimates'].read(e['actor'], e['sid'], estimate['estimate_id'])
    assert result['state'] == 'assessed'
    assert not e['canary'].exists()


def execution_fixture(e, *, recorded=True):
    from hyprn_mvp_app.quantity_projection import quantities
    target = quantities(e['case']['frozen'])[1][0]['target']
    request = sample_request(e, estimate_plan=dict(
        tolerances=[dict(target=target, absolute=0.1, relative=0.01)]))
    group = request['groups'][0]
    group['validation_count'] = group.pop('check_count')
    _, version = complete(e, request)
    assert version['schema_version'] == '4'
    if recorded:
        for member in version['content']['configuration_revision_ids']:
            frozen = e['client'].get(path(e, 'configurations/' + member)).json()['data']
            record_run(e['store'], e['actor'], e['sid'], point_case(e, frozen), [42])
    endpoint = path(e, 'analysis-versions/' + version['calculation_version_id'] + '/execution')
    return version, endpoint


@pytest.mark.parametrize('usable', [True, False])
def test_analysis_launch_pins_runs_and_automatically_assesses_all_outputs(recordable, usable):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    e = recordable
    version, endpoint = execution_fixture(e)
    assert e['client'].get(endpoint).json()['data'] is None
    first = e['client'].post(endpoint, json={})
    assert first.status_code == 202, first.text
    accepted = first.json()['data']
    assert all(m['reused'] for m in accepted['runs'])
    # A later run cannot silently replace a launch-time pin.
    member = version['content']['configuration_revision_ids'][0]
    frozen = e['client'].get(path(e, 'configurations/' + member)).json()['data']
    later, _ = record_run(e['store'], e['actor'], e['sid'], point_case(e, frozen), [99])
    runner = AnalysisExecution(e['store'])
    runner.process_one(Submissions(e['store'], None, None))
    progress = e['client'].get(endpoint).json()['data']
    assert progress['state'] == 'validating'
    estimate = e['estimates'].read(e['actor'], e['sid'], progress['estimate_id'])
    assert later not in {s['run_id'] for s in estimate['samples']}
    assert {s['run_id'] for s in estimate['samples']} == {m['run_id'] for m in accepted['runs']}
    e['estimates'].process_one(UsableFitTransport() if usable else FitTransport())
    runner.process_one(Submissions(e['store'], None, None))
    final = e['client'].get(endpoint).json()['data']
    assert final['state'] == ('complete' if usable else 'failed'), final
    assert e['client'].post(endpoint, json={}).json()['data'] == final
    assert not runner.process_one(Submissions(e['store'], None, None))
    assert receipts(e, 'calculation_estimate') == 1
    direct = e['client'].post(path(e, 'analysis-estimates'), json=dict(
        command_id=uid(), calculation_version_id=version['calculation_version_id'],
        tolerances=version['content']['estimate_plan']['tolerances']))
    assert direct.status_code == 422
    assert e['client'].get(path(e, 'analysis-versions/' + version['calculation_version_id'])).json()['data'] == version


def test_analysis_launch_recovers_accepted_run_without_duplicate_submission(recordable):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    e = recordable
    _, endpoint = execution_fixture(e, recorded=False)
    assert e['client'].post(endpoint, json={}).status_code == 202
    submissions = Submissions(e['store'], None, None)
    actual = submissions.submit

    def interrupted(*args, **kwargs):
        actual(*args, **kwargs)
        raise RuntimeError('Dispatcher interrupted after acceptance')

    submissions.submit = interrupted
    with pytest.raises(RuntimeError):
        AnalysisExecution(e['store']).process_one(submissions)
    assert receipts(e, 'run') == 1
    submissions.submit = actual
    AnalysisExecution(e['store']).process_one(submissions)
    state = e['client'].get(endpoint).json()['data']
    assert state['state'] == 'calculating'
    assert state['completed_count'] == 0
    assert receipts(e, 'run') == 5
    AnalysisExecution(e['store']).process_one(submissions)
    assert receipts(e, 'run') == 5
    assert receipts(e, 'calculation_estimate') == 0


def test_analysis_launch_requires_write_access_and_an_explicit_saved_plan(recordable):
    e = recordable
    _, old = complete(e, sample_request(e))
    old_endpoint = path(e, 'analysis-versions/' + old['calculation_version_id'] + '/execution')
    assert e['client'].post(old_endpoint, json={}).status_code == 422
    _, endpoint = execution_fixture(e)
    assert e['client'].post(endpoint, json={'estimate_plan': None}).status_code == 400
    with e['store'].connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE study_id=?", (e['sid'],))
    assert e['client'].get(endpoint).status_code == 200
    assert e['client'].post(endpoint, json={}).status_code == 403


def test_concurrent_exploration_shares_verification_but_rechecks_each_reader(
    recordable, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from hyprn_mvp_app.calculation_exploration import CalculationExploration
    from hyprn_mvp_app.history import History

    e = recordable
    version, estimate, _, _ = prediction_fixture(e)
    owners = [CalculationExploration(e['store']) for _ in range(2)]
    entered, release = Event(), Event()
    reads, rechecks = [], []
    retained, recheck = History.retained, History.recheck

    def held(self, *args, **kwargs):
        reads.append(args)
        entered.set()
        assert release.wait(5)
        return retained(self, *args, **kwargs)

    def checked(self, *args, **kwargs):
        rechecks.append(args)
        return recheck(self, *args, **kwargs)

    monkeypatch.setattr(History, 'retained', held)
    monkeypatch.setattr(History, 'recheck', checked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(owners[0].basis, e['actor'], e['sid'],
                            version['calculation_version_id'], estimate_id=estimate)
        assert entered.wait(5)
        second = pool.submit(owners[1].basis, e['actor'], e['sid'],
                             version['calculation_version_id'], estimate_id=estimate)
        release.set()
        assert first.result(timeout=10) == second.result(timeout=10)
    assert len(reads) == 1
    assert len(rechecks) >= 2
    assert not owners[0]._basis_reads


def test_replayed_generated_point_retains_its_original_name_and_exact_snapshot(env):
    owner = Configurations(env['store'], None)
    original = env['case']['frozen']['configuration']
    values = [{key: item[key] for key in ('target', 'value', 'units')}
              for item in original['inputs']]
    args = (env['actor'], env['sid'], uid(), env['reference'], values, 'Declared range.')
    saved = owner.exploration_point(*args)
    before = owner.read(env['actor'], env['sid'], saved['configuration_revision_id'])
    assert owner.exploration_point(*args, name='Response sweep · Point 1') == saved
    assert owner.read(env['actor'], env['sid'], saved['configuration_revision_id']) == before
    assert before['configuration']['name'] == original['name']
