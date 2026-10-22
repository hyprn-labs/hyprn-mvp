"""Pinned OpenMDAO state reuse in the actual attested restricted container."""

from copy import deepcopy
import json
import time
import pytest

import live_fence
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
from units_native_fixture import UnitsJourney
from hyprn_mvp_integration import launcher
from hyprn_mvp_app.contracts import digest

live_runtime_fence = live_fence.pytest_fixture('baseline')


def test_joint_state_reuse_and_bounded_warm_latency():
    j = UnitsJourney(SCOPE, BACKEND)
    session = None
    proof = dict(passed=False, human_acceptance=False, original_evaluations=0)
    try:
        j.start()
        design_request = dict(
            schema_version='4',
            operation='extend_design',
            identity='c' * 64,
            seed=17,
            groups=[
                dict(bounds=[[0, 1], [0, 1]], training_count=9, check_count=5, retained=[])
            ],
        )
        generated = j.native.explore(design_request)['result']['groups'][0]
        training = {tuple(r['vector']) for r in generated if r['partition'] == 'training'}
        checks = {tuple(r['vector']) for r in generated if r['partition'] == 'check'}
        assert {(0, 0), (0, 1), (1, 0), (1, 1)} <= training
        assert len(training) == 9 and len(checks) == 5 and not training & checks
        # Seeded coordinates and disjoint partitions are stable under regeneration.
        assert j.native.explore(design_request)['result']['groups'][0] == generated
        payload = dict(
            bounds=[[0, 1], [0, 1]],
            training=[
                dict(x=[x, y], y=[x * y, 0.0, (x - 0.5) * (y - 0.5)])
                for x, y in [
                    (0, 0),
                    (1, 0),
                    (0, 1),
                    (1, 1),
                    (0.25, 0.7),
                    (0.8, 0.3),
                    (0.4, 0.4),
                    (0.6, 0.9),
                ]
            ],
            checks=[
                dict(x=[x, y], y=[x * y, 0.0, (x - 0.5) * (y - 0.5)])
                for x, y in [(0.3, 0.6), (0.7, 0.8), (0.2, 0.3)]
            ],
            tolerances=[[1e-10, 1e-10], [1e-10, 0], [1e-10, 1e-10]],
        )
        request = dict(
            schema_version='3', operation='build', identity=digest(payload), payload=payload
        )
        started = time.monotonic()
        built = j.native.explore(request)
        proof['build_seconds'] = time.monotonic() - started
        artifact = built['result']['artifact']
        proof['build'] = built
        assert all(o['metrics']['target_met'] for o in artifact['outputs'])
        session = launcher.WarmExploration(j.native.root)
        identity = digest(artifact)
        session.call(
            dict(
                schema_version='3',
                operation='warm',
                identity=identity,
                payload=dict(artifact=artifact),
            )
        )
        latencies = []
        for index in range(50):
            x, y = 0.1 + 0.8 * index / 50, 0.9 - 0.8 * index / 50
            queries = [[x, y]] + [[n / 32, y] for n in range(33 - 1)]
            started = time.monotonic()
            response = session.call(
                dict(
                    schema_version='3',
                    operation='predict',
                    identity=identity,
                    payload=dict(queries=queries),
                )
            )
            latencies.append((time.monotonic() - started) * 1000)
            assert abs(response['values'][0][0]['value'] - x * y) < 1e-10
            assert response['values'][0][1]['value'] == 0
            assert abs(response['values'][0][2]['value'] - (x - 0.5) * (y - 0.5)) < 1e-10
        proof['warm_transport_ms'] = latencies
        proof['warm_transport_p95_ms'] = sorted(latencies)[47]
        assert proof['warm_transport_p95_ms'] <= 250, proof['warm_transport_p95_ms']
        denied = session.call(
            dict(
                schema_version='3',
                operation='predict',
                identity=identity,
                payload=dict(queries=[[1.1, 0.5]]),
            )
        )
        assert denied['values'][0][0] == dict(value=None, reason='outside_bounds')
        # A changed original row makes just that output unavailable; no fitted gap.
        failed = deepcopy(payload)
        failed['training'][0]['y'][0] = None
        result = j.native.explore(
            dict(schema_version='3', operation='build', identity=digest(failed), payload=failed)
        )
        assert result['result']['artifact']['outputs'][0]['reason'] == 'incomplete_samples'
        assert result['result']['artifact']['outputs'][1]['metrics']['target_met']
        impossible = deepcopy(payload)
        for row in impossible['checks'][1:]:
            row['y'][0] = 100
        rejected = j.native.explore(
            dict(
                schema_version='3',
                operation='build',
                identity=digest(impossible),
                payload=impossible,
            )
        )['result']['artifact']
        assert rejected['outputs'][0]['reason'] == 'observed_tolerance_unmet'
        assert rejected['outputs'][0]['state'] is None
        underfunded = dict(
            bounds=[[0, 1]] * 5,
            tolerances=[[0, 0]],
            training=[dict(x=[v] * 5, y=[v]) for v in [0, 0.5, 1]],
            checks=[dict(x=[v] * 5, y=[v]) for v in [0.25, 0.75]],
        )
        rejected = j.native.explore(
            dict(
                schema_version='3',
                operation='build',
                identity=digest(underfunded),
                payload=underfunded,
            )
        )['result']['artifact']
        assert rejected['outputs'][0]['reason'] == 'underfunded_or_failed_fits'
        assert all(
            c['reason'] == 'underfunded_design' for c in rejected['outputs'][0]['comparisons']
        )
        # Fewer than six points preclude a 2D quadratic, proving Kriging restoration.
        kriging = dict(
            bounds=[[0, 1], [0, 1]],
            tolerances=[[0.1, 0.01]],
            training=[
                dict(x=[x, y], y=[x + y])
                for x, y in [(0, 0), (0.9, 0), (0, 0.9), (0.2, 0.2), (0.3, 0.3)]
            ],
            checks=[
                dict(x=[x, y], y=[x + y]) for x, y in [(0.1, 0.2), (0.2, 0.3), (0.25, 0.25)]
            ],
        )
        kriging_artifact = j.native.explore(
            dict(
                schema_version='3', operation='build', identity=digest(kriging), payload=kriging
            )
        )['result']['artifact']
        assert kriging_artifact['outputs'][0]['method'] == 'kriging'
        assert kriging_artifact['outputs'][0]['reason'] is None
        second_identity = digest(kriging_artifact)
        session.call(
            dict(
                schema_version='3',
                operation='warm',
                identity=second_identity,
                payload=dict(artifact=kriging_artifact),
            )
        )
        queries = [[0.25, 0.25], [0.8, 0.8], [0.3, 0.2]]
        forward = session.call(
            dict(
                schema_version='3',
                operation='predict',
                identity=second_identity,
                payload=dict(queries=queries),
            )
        )['values']
        backward = session.call(
            dict(
                schema_version='3',
                operation='predict',
                identity=second_identity,
                payload=dict(queries=list(reversed(queries))),
            )
        )['values']
        assert forward == list(reversed(backward))
        assert abs(forward[0][0]['value'] - 0.5) < 0.1
        assert (
            forward[1][0]['value'] is None
            and forward[1][0]['reason'] == 'outside_sampled_coverage'
        )
        session.close()
        # Restart restores only explicitly warmed immutable state; never trains.
        session = launcher.WarmExploration(j.native.root)
        with pytest.raises(RuntimeError, match='Warm session absent'):
            session.call(
                dict(
                    schema_version='3',
                    operation='predict',
                    identity=second_identity,
                    payload=dict(queries=queries),
                )
            )
        assert session.proc is None
        session.call(
            dict(
                schema_version='3',
                operation='warm',
                identity=second_identity,
                payload=dict(artifact=kriging_artifact),
            )
        )
        restored = session.call(
            dict(
                schema_version='3',
                operation='predict',
                identity=second_identity,
                payload=dict(queries=queries),
            )
        )['values']
        assert restored == forward
        proof['kriging_restart_values'] = restored
        # An explicit reload replaces an expired child in one call, never fits.
        previous_pid = session.proc.pid
        session.started -= 901
        session.call(
            dict(
                schema_version='3',
                operation='warm',
                identity=second_identity,
                payload=dict(artifact=kriging_artifact),
            )
        )
        assert session.proc.pid != previous_pid
        renewed = session.call(
            dict(
                schema_version='3',
                operation='predict',
                identity=second_identity,
                payload=dict(queries=queries),
            )
        )
        assert renewed['values'] == forward

        # A dominant nonlinear coordinate plus weak joint contributions must
        # not collapse to a constant predictor in a many-input fit.
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]

        def row(index):
            x = [((index * prime) % 101) / 100 for prime in primes]
            return dict(x=x, y=[10 + 9 * x[0] ** 2 + 0.01 * sum(x[1:])])

        joint = dict(
            bounds=[[0, 1]] * len(primes),
            training=[row(i) for i in range(1, 41)],
            checks=[row(i) for i in range(61, 67)],
            tolerances=[[1e-6, 0.01]],
        )
        joint_artifact = j.native.explore(
            dict(schema_version='3', operation='build', identity=digest(joint), payload=joint)
        )['result']['artifact']
        joint_output = joint_artifact['outputs'][0]
        assert joint_output['method'] == 'kriging'
        assert joint_output['metrics']['assessed_count'] == 5
        assert joint_output['metrics']['target_met'], joint_output
        assert len(joint_output['comparisons']) == 2
        proof['many_input_assessment'] = joint_output
        proof['passed'] = True
    finally:
        if session is not None:
            session.close()
        (SCOPE.root / 'evidence/exploration-numerics-proof.json').write_text(
            json.dumps(proof, indent=2)
        )
        j.close()
