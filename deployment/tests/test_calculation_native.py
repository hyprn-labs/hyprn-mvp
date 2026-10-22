"""Real public configuration/run batching, without any retired approach records."""

from pathlib import Path
import json
import time
import live_fence
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from units_native_fixture import UnitsJourney, literal
from approach_native_fixture import source
from hyprn_mvp_app.contracts import uid

REPO = Path(__file__).resolve().parents[2]
live_runtime_fence = live_fence.pytest_fixture('baseline')


def references(journey):
    """Two independent vectors in one explicitly defined multiplication model."""
    edits = [
        dict(
            kind='create_definition',
            temp_key='d',
            definition_kind='explicit_component',
            name='Product',
            ports=[
                dict(
                    temp_key=n,
                    direction='output' if n == 'product' else 'input',
                    name=n,
                    code_symbol=n,
                    value_type='real_scalar',
                    units=dict(kind='dimensionless'),
                )
                for n in ['x', 'y', 'product']
            ],
            source=source(b"outputs['product'] = inputs['x'] * inputs['y']\n"),
        ),
        dict(kind='instantiate', temp_key='i', version_ref=dict(temp_key='d')),
    ]
    _, model = journey.model('Independent multiplication', edits)
    instance = model['instances'][0]
    definition = next(
        d
        for d in model['definitions']
        if d['definition_version_id'] == instance['definition_version_id']
    )
    ports = {
        p['code_symbol']: dict(instance_id=instance['instance_id'], port_id=p['port_id'])
        for p in definition['ports']
    }
    evidence = journey.evidence('Synthetic multiplication; no physical inference.')
    configurations = []
    for x, y in [(2, 3), (5, 7)]:
        body = journey.configuration(
            model,
            'Explicit inputs',
            [
                literal(ports['x'], x, '', evidence['evidence_version_id']),
                literal(ports['y'], y, '', evidence['evidence_version_id']),
            ],
            evidence,
        )
        configurations.append(journey.save_configuration(body)['configuration'])
    return configurations


def test_public_independent_runs_cross_batched_dispatch_and_retain_exact_results():
    import combined_fixture
    import dispatch_runtime

    journey = UnitsJourney(SCOPE, BACKEND)
    try:
        journey.start()
        configurations = references(journey)
        calls = []
        original = journey.native.launch_batch

        def traced(items):
            calls.append(len(items))
            return original(items)

        journey.native.launch_batch = traced
        runs = [
            journey.request(
                'POST',
                'runs',
                dict(
                    command_id=uid(),
                    configuration_revision_id=c['configuration_revision_id'],
                    execution_budget=dict(wall_seconds=60),
                ),
                202,
            )
            for c in configurations
        ]
        started = time.monotonic()
        command = [
            guard.APPROVED_CONTRACT_PYTHON,
            '-B',
            combined_fixture.__file__,
            'dispatch',
            '--once',
        ]
        with (SCOPE.root / 'evidence/batch-public-dispatch.log').open('wb') as log:
            status = dispatch_runtime.bridge_child(
                journey.native,
                command,
                env=guard.clean_environment(SCOPE),
                cwd=REPO,
                stderr=log,
            )
        elapsed = time.monotonic() - started
        assert status == 0
        assert calls == [2]
        for run, expected in zip(runs, (6, 35), strict=True):
            record = journey.request('GET', 'runs/' + run['run_id'])
            assert record['state'] == 'recorded' and record['exit_status'] == 0
            assert record['history']['errors'] == []
            assert [o['value'] for o in record['history']['results']['outputs']] == [expected]
        measurements = dict(cold_batch_seconds=elapsed)
        for mode in ('warm_batch', 'sequential'):
            pending = [
                journey.request(
                    'POST',
                    'runs',
                    dict(
                        command_id=uid(),
                        configuration_revision_id=c['configuration_revision_id'],
                        execution_budget=dict(wall_seconds=60),
                    ),
                    202,
                )
                for c in configurations
            ]
            started = time.monotonic()
            commands = (
                [command]
                if mode == 'warm_batch'
                else [command[:-1] + ['--run-id', run['run_id']] for run in pending]
            )
            for invocation in commands:
                with (SCOPE.root / ('evidence/batch-' + mode + '.log')).open('ab') as log:
                    assert (
                        dispatch_runtime.bridge_child(
                            journey.native,
                            invocation,
                            env=guard.clean_environment(SCOPE),
                            cwd=REPO,
                            stderr=log,
                        )
                        == 0
                    )
            measurements[mode + '_seconds'] = time.monotonic() - started
            for run, expected in zip(pending, (6, 35), strict=True):
                record = journey.request('GET', 'runs/' + run['run_id'])
                assert record['state'] == 'recorded' and record['exit_status'] == 0
                assert record['history']['errors'] == []
                assert [o['value'] for o in record['history']['results']['outputs']] == [
                    expected
                ]
        (SCOPE.root / 'evidence/batch-public-timing.json').write_text(
            json.dumps(
                dict(
                    measurements,
                    seconds_per_point=measurements['warm_batch_seconds'] / 2,
                    runs=[r['run_id'] for r in runs],
                    outputs=[6, 35],
                    batch_sizes=calls,
                )
            )
        )
    finally:
        journey.close()
