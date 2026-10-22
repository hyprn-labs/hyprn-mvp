"""Public sample lifecycle over real app receipts; native execution is separate.

The synthetic transport returns data only. It does not establish numerical
accuracy or containment; exploration-native proves the restricted scalar path.
"""

import base64
from copy import deepcopy
import hashlib
import json
import time
from uuid import UUID, uuid5

import pytest

from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.contracts import digest, uid
from hyprn_mvp_app.execution import Submissions
from hyprn_mvp_app.sampling import Samples
from criteria_free import bind_case, insert_case
from test_exploration_api import basis_env  # noqa: F401
from test_assumptions_evidence_api import api, generated  # noqa: F401
from test_answers_api import answer_env, body as answer_body, saved  # noqa: F401
from test_approach_api import assert_http

RUNTIME = dict(
    image_digest='sha256:' + 'a' * 64,
    architecture='arm64',
    python_version='3.12.15',
    worker_entrypoint='hyprn_mvp_integration.worker',
    policy_digest='b' * 64,
)


def request(e):
    inputs = e['frozen']['configuration']['inputs']
    return dict(
        schema_version='1',
        command_id=uid(),
        previous_operation_id=None,
        seed=17,
        category_dimensions=[
            dict(name='material', values=['a', 'b']),
            dict(name='regime', values=['low', 'high']),
        ],
        combinations=[
            dict(
                categories=category,
                answer_version_id=e['answer']['answer_version_id'],
                configuration_revision_id=e['frozen']['configuration']['configuration_revision_id'],
                dimensions=[
                    dict(target=p['target'], lower=0, upper=10, units=p['units']) for p in inputs
                ],
                training_count=3,
                check_count=2,
                tolerances=[
                    dict(
                        target=dict(
                            instance_id=e['frozen']['model_snapshot']['instances'][0][
                                'instance_id'
                            ],
                            port_id=e['frozen']['model_snapshot']['definitions'][0]['ports'][2][
                                'port_id'
                            ],
                        ),
                        absolute=0.1,
                        relative=0.01,
                    )
                ],
            )
            for category in [['a', 'low'], ['b', 'high']]
        ],
        budget=dict(
            additional_evaluations=10, wall_seconds=3600, point_wall_seconds=10, concurrency=1
        ),
        rationale='Declared joint input experiment; categories are explicit tuples',
    )


class DesignTransport:
    def __init__(self):
        self.calls = []

    def explore(self, request):
        self.calls.append(request)
        groups = []
        for group in request['groups']:
            rows = deepcopy(group['retained'])
            for partition, key in [('training', 'training_count'), ('check', 'check_count')]:
                while sum(r['partition'] == partition for r in rows) < group[key]:
                    n = len(rows) + 1
                    rows.append(dict(partition=partition, vector=[float(n)] * len(group['bounds'])))
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


def canary_source(frozen, canary):
    """Replace the baseline's candidate source with one that marks ``canary`` if imported.

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


@pytest.fixture
def sample_env(answer_env, tmp_path):
    """A version-6 baseline on a Model4 revision with two free dimensionless inputs (saved
    values 0 and 7) and one output, cited by a saved answer: the only baseline an exploration
    point may copy."""
    e = answer_env
    canary = tmp_path / 'candidate-executed'
    case = bind_case('unrelated', e['sid'], study_revision=e['study']['revision'])
    canary_source(case['frozen'], canary)
    config = case['frozen']['configuration']
    for item, value in zip(config['inputs'], [0, 7], strict=True):
        item['value'] = value
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    insert_case(e['store'], e['sid'], case)
    request = answer_body(e)
    request['basis']['configuration_revision_ids'] = [config['configuration_revision_id']]
    e.update(frozen=case['frozen'], answer=saved(e, request), canary=canary)
    e['store'].publish_execution_observation('ready', None, time.time(), RUNTIME)
    e['samples'] = Samples(
        e['store'], Configurations(e['store'], None), Submissions(e['store'], None, None)
    )
    e['path'] = '/api/1/studies/' + e['sid'] + '/exploration-samples'
    e['native'] = DesignTransport()
    return e


def submit(e, body):
    response = e['client'].post(e['path'], json=body)
    assert response.status_code == 202, response.text
    return response.json()['data']


def read(e, body):
    response = e['client'].get(e['path'] + '/' + body['command_id'])
    assert response.status_code == 200, response.text
    return response.json()['data']


def control(e, body, action):
    return e['client'].post(
        e['path'] + '/' + body['command_id'] + '/controls',
        json=dict(command_id=uid(), action=action),
    )


def test_joint_preview_is_inert_and_budget_partition_precedes_work(sample_env, generated):
    e = sample_env
    body = request(e)
    preview = e['client'].post(e['path'] + '/preview', json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()['data']['new_count'] == 10
    assert len(preview.json()['data']['allocation']) == 2
    assert_http(generated, '/studies/{study_id}/exploration-samples/preview', 'post', preview)
    assert not e['canary'].exists() and not e['native'].calls
    first = submit(e, body)
    assert submit(e, body) == first
    assert e['samples'].process_one(e['native'])
    result = read(e, body)
    assert result['state'] == 'sampling' and len(result['points']) == 10
    assert all(len(p['inputs']) == 2 for p in result['points'])
    assert sum(p['partition'] == 'check' for p in result['points']) == 4
    assert len({p['identity'] for p in result['points']}) == 10
    assert not e['canary'].exists()


@pytest.mark.parametrize(
    'mutation',
    [
        'budget',
        'time',
        'bool',
        'unsafe',
        'unknown',
        'duplicate_tuple',
        'unknown_tuple',
        'axis',
        'zero_width',
        'concurrency',
        'pickle',
    ],
)
def test_invalid_or_underfunded_design_never_allocates(sample_env, mutation):
    e = sample_env
    body = request(e)
    if mutation == 'budget':
        body['budget']['additional_evaluations'] = 9
    elif mutation == 'time':
        body['budget']['wall_seconds'] = 99
    elif mutation == 'bool':
        body['seed'] = True
    elif mutation == 'unsafe':
        body['combinations'][0]['dimensions'][0]['upper'] = 2**53
    elif mutation == 'unknown':
        body['unknown'] = 'x'
    elif mutation == 'duplicate_tuple':
        body['combinations'][1]['categories'] = ['a', 'low']
    elif mutation == 'unknown_tuple':
        body['combinations'][0]['categories'] = ['c', 'low']
    elif mutation == 'axis':
        body['combinations'][0]['dimensions'][0]['target']['port_id'] = uid()
    elif mutation == 'zero_width':
        body['combinations'][0]['dimensions'][0]['upper'] = 0
    elif mutation == 'concurrency':
        body['budget']['concurrency'] = 2
    elif mutation == 'pickle':
        body['pickle'] = 'untrusted'
    reply = e['client'].post(e['path'], json=body)
    assert reply.status_code in (400, 422), reply.text
    with e['store'].connection() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM receipts WHERE category='exploration_sample'"
            ).fetchone()[0]
            == 0
        )


def test_cancel_retains_design_and_resume_keeps_exact_partition(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    before = read(e, body)['points']
    assert control(e, body, 'cancel').status_code == 200
    e['samples'].process_one(e['native'])
    assert read(e, body)['state'] == 'cancelled'
    assert read(e, body)['points'] == before
    assert control(e, body, 'resume').status_code == 200
    e['samples'].process_one(e['native'])
    after = read(e, body)
    assert after['attempted_count'] == 1
    assert [(p['identity'], p['partition']) for p in after['points']] == [
        (p['identity'], p['partition']) for p in before
    ]
    assert len(e['native'].calls) == 1 and not e['canary'].exists()
    point = after['points'][0]
    frozen = e['client'].get(
        '/api/1/studies/' + e['sid'] + '/configurations/' + point['configuration_revision_id']
    )
    assert frozen.status_code == 200
    with e['store'].connection() as db:
        row = db.execute(
            'SELECT head FROM configuration_families WHERE configuration_id=?',
            (frozen.json()['data']['configuration']['configuration_id'],),
        ).fetchone()
        assert row['head'] == point['configuration_revision_id']


@pytest.mark.parametrize(
    'literal', ['NaN', 'Infinity', '-Infinity', '1e999', '9007199254740992', 'true']
)
def test_nonfinite_unsafe_or_boolean_coordinate_refuses_before_receipt(sample_env, literal):
    e = sample_env
    body = request(e)
    raw = json.dumps(body).replace('"lower": 0', '"lower": ' + literal)
    response = e['client'].post(
        e['path'], content=raw, headers={'Content-Type': 'application/json'}
    )
    assert response.status_code == 400
    assert e['client'].get(e['path'] + '/' + body['command_id']).status_code == 404
    assert not e['canary'].exists() and not e['native'].calls


def test_crash_after_scalar_acceptance_recovers_same_run_and_configuration(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])

    def crash(point):
        raise RuntimeError('Lost response after durable scalar acceptance')

    e['samples'].fault = crash
    e['samples'].process_one(e['native'])
    assert read(e, body)['state'] == 'uncertain'
    with e['store'].connection() as db:
        runs = [dict(r) for r in db.execute('SELECT * FROM run_associations')]
        assert len(runs) == 1
    owner = Samples(
        e['store'], Configurations(e['store'], None), Submissions(e['store'], None, None)
    )
    assert control(e, body, 'reconcile').status_code == 200
    owner.process_one(e['native'])
    result = read(e, body)
    assert result['points'][0]['run_id'] == runs[0]['run_id']
    assert result['attempted_count'] == 1
    with e['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM run_associations').fetchone()[0] == 1
    assert not e['canary'].exists()


def test_extension_preserves_points_when_density_targets_and_budget_change(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    original = read(e, body)
    control(e, body, 'cancel')
    e['samples'].process_one(e['native'])
    extension = deepcopy(body)
    extension.update(command_id=uid(), previous_operation_id=body['command_id'])
    for combination in extension['combinations']:
        combination['training_count'] = 4
        combination['tolerances'][0]['absolute'] = 0.001
        combination['dimensions'][0]['upper'] = 12
    extension['budget']['additional_evaluations'] = 12
    preview = e['client'].post(e['path'] + '/preview', json=extension)
    assert preview.status_code == 200, preview.text
    assert preview.json()['data']['retained_count'] == 10
    assert preview.json()['data']['new_count'] == 12  # cancelled before any evaluation
    submit(e, extension)
    e['samples'].process_one(e['native'])
    after = read(e, extension)
    identities = {(p['identity'], p['partition']) for p in original['points']}
    assert identities <= {(p['identity'], p['partition']) for p in after['points']}
    assert len(after['points']) == 12


def test_cancel_recovers_accepted_run_before_permitting_any_extension(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])

    def crash(point):
        raise RuntimeError('Lost manifest update after scalar acceptance')

    e['samples'].fault = crash
    e['samples'].process_one(e['native'])
    assert read(e, body)['points'][0]['run_id'] is None
    assert control(e, body, 'cancel').status_code == 200
    cancelled = read(e, body)
    assert cancelled['attempted_count'] == 1
    assert cancelled['points'][0]['run_id'] is not None
    extension = dict(body, command_id=uid(), previous_operation_id=body['command_id'])
    assert e['client'].post(e['path'], json=extension).status_code == 429
    with e['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM run_associations').fetchone()[0] == 1


def test_recovery_never_adopts_a_conflicting_run_command(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    point = read(e, body)['points'][0]
    command = str(uuid5(UUID(body['command_id']), point['identity']))
    response = e['client'].post(
        '/api/1/studies/' + e['sid'] + '/runs',
        json=dict(
            command_id=command,
            configuration_revision_id=e['frozen']['configuration']['configuration_revision_id'],
        ),
    )
    assert response.status_code == 202
    e['samples'].process_one(e['native'])
    assert read(e, body)['state'] == 'uncertain'
    assert control(e, body, 'cancel').status_code == 409
    assert read(e, body)['points'][0]['run_id'] is None


def test_unknown_design_is_not_redispatched_and_access_is_current(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)

    class Unknown:
        def explore(self, request):
            raise TimeoutError('Unknown artifact outcome')

    assert e['samples'].process_one(Unknown())
    assert read(e, body)['state'] == 'uncertain'
    assert not e['samples'].process_one(Unknown())
    assert control(e, body, 'cancel').status_code == 200
    assert control(e, body, 'resume').status_code == 409
    assert not e['samples'].process_one(Unknown())
    with e['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=?', (e['sid'],))
    assert e['client'].get(e['path'] + '/' + body['command_id']).status_code == 404
    assert control(e, body, 'cancel').status_code == 404


def test_reader_cannot_sample_or_cancel_and_preview_does_not_write(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    with e['store'].connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE study_id=?", (e['sid'],))
    assert e['client'].get(e['path'] + '/' + body['command_id']).status_code == 200
    assert e['client'].post(e['path'], json=dict(body, command_id=uid())).status_code == 403
    assert control(e, body, 'cancel').status_code == 403


def test_resume_cannot_overlap_another_active_design(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    control(e, body, 'cancel')
    submit(e, dict(body, command_id=uid()))
    assert control(e, body, 'resume').status_code == 429


def test_category_dimension_names_are_part_of_compatible_tuple_mapping(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    control(e, body, 'cancel')
    e['samples'].process_one(e['native'])
    changed = deepcopy(body)
    changed.update(command_id=uid(), previous_operation_id=body['command_id'])
    changed['category_dimensions'][0]['name'] = 'different category meaning'
    preview = e['client'].post(e['path'] + '/preview', json=changed)
    assert preview.status_code == 200
    assert preview.json()['data']['retained_count'] == 0


def test_uncertain_scalar_lookup_never_submits_a_replacement(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    e['samples'].process_one(e['native'])
    point = read(e, body)['points'][0]

    class UnknownScalar:
        def __init__(self):
            self.lookups = []

        def read(self, *args):
            return dict(state='uncertain')

        def dispatch(self, run_id):
            self.lookups.append(run_id)

        def submit(self, *args, **kwargs):
            raise AssertionError('Unknown launch must not be replaced')

    scalar = UnknownScalar()
    owner = Samples(e['store'], Configurations(e['store'], None), scalar)
    owner.process_one(e['native'])
    assert read(e, body)['state'] == 'uncertain'
    assert not owner.process_one(e['native'])
    control(e, body, 'reconcile')
    owner.process_one(e['native'])
    assert scalar.lookups == [point['run_id'], point['run_id']]
    assert read(e, body)['attempted_count'] == 1
    assert control(e, body, 'cancel').status_code == 200
    cancelled = read(e, body)
    assert cancelled['state'] == 'cancelled'
    assert cancelled['points'][0]['state'] == 'uncertain'
    assert cancelled['points'][0]['run_id'] == point['run_id']
    assert e['client'].post(e['path'], json=dict(body, command_id=uid())).status_code == 429
    assert control(e, body, 'reconcile').status_code == 200
    owner.process_one(e['native'])
    assert scalar.lookups == [point['run_id']] * 3
    assert read(e, body)['cancel_requested'] is True


def test_wall_deadline_stops_before_any_new_original_run(sample_env, monkeypatch):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    start = read(e, body)['started_at']
    monkeypatch.setattr('hyprn_mvp_app.sampling.time.time', lambda: start + 3601)
    e['samples'].process_one(e['native'])
    result = read(e, body)
    assert result['state'] == 'limited' and result['attempted_count'] == 0
    assert len(result['points']) == 10


def test_failed_point_keeps_its_partition_and_is_not_retried_on_extension(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)
    e['samples'].process_one(e['native'])
    e['samples'].process_one(e['native'])
    first = read(e, body)['points'][0]

    class PreparationFailed:
        def read(self, *args):
            return dict(state='preparation_failed')

        def submit(self, *args, **kwargs):
            raise AssertionError('Cancelled failure must not launch another point')

    control(e, body, 'cancel')
    owner = Samples(e['store'], Configurations(e['store'], None), PreparationFailed())
    owner.process_one(e['native'])
    result = read(e, body)
    assert result['state'] == 'cancelled' and result['failed_count'] == 1
    failed = result['points'][0]
    assert failed['run_id'] == first['run_id'] and failed['partition'] == first['partition']
    assert failed['reason'] == 'preparation_failed' and failed['results_digest'] is None
    extension = deepcopy(body)
    extension.update(command_id=uid(), previous_operation_id=body['command_id'])
    extension['budget']['additional_evaluations'] = 9
    assert e['client'].post(e['path'] + '/preview', json=extension).json()['data']['new_count'] == 9
    submit(e, extension)
    owner.process_one(e['native'])
    retained = next(p for p in read(e, extension)['points'] if p['identity'] == first['identity'])
    assert retained['state'] == 'failed' and retained['run_id'] == first['run_id']


def test_native_partition_tampering_never_launches_originals(sample_env):
    e = sample_env
    body = request(e)
    submit(e, body)

    class Tampered(DesignTransport):
        def explore(self, request):
            artifact = super().explore(request)
            artifact['result']['groups'][0][-1]['partition'] = 'training'
            artifact['result_sha256'] = digest(artifact['result'])
            return artifact

    e['samples'].process_one(Tampered())
    assert read(e, body)['state'] == 'uncertain'
    assert read(e, body)['attempted_count'] == 0
