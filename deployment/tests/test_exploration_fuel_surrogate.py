"""Captured scientific fixture exercises generic joint preparation and retained anchors."""

from copy import deepcopy
import json
from pathlib import Path
import signal
import subprocess
import time

import live_fence
from checks import (
    PROJECTION_SCOPE as SCOPE,
    NATIVE_BACKEND as BACKEND,
    EXPLORATION_UI_RESUME as RESUME,
)
import scoped_fixture as guard
from units_native_fixture import UnitsJourney
from test_exploration_native import author
from test_exploration_surrogates_native import await_state
from hyprn_mvp_app.contracts import uid

REPO = Path(__file__).resolve().parents[2]
live_runtime_fence = live_fence.pytest_fixture('baseline')


def prepare(j):
    fixture, baseline, frozen, answer, _ = author(j, full=True)
    revision = frozen['configuration']['configuration_revision_id']
    basis = j.request(
        'GET', 'answers/' + answer['answer_version_id'] + '/exploration-basis/' + revision
    )
    dimensions = []
    # These ranges and correlations are evaluation-study data, never product rules.
    links = {1: 'volume', 8: 'volume', 5: 'mass', 6: 'mass'}
    for index, point in enumerate(baseline['inputs']):
        value = point['value']
        dimensions.append(
            dict(
                target=point['target'],
                units=point['units'],
                lower=value * (0.98 if index == 13 else 0.99),
                upper=value * (1 if index == 13 else 1.01),
                step=1 if index == 9 else None,
                common_key=None,
                covary_group=links.get(index),
            )
        )
    combo = dict(
        categories=[],
        configuration_revision_id=revision,
        model_id=basis['model_id'],
        model_revision_id=basis['model_revision_id'],
        dimensions=dimensions,
        initial_axis=dimensions[0]['target'],
    )
    rationale = (
        'Local source screening only: ±1% around captured inputs; load factor 0.98–1; '
        'integer passengers; equal paired mass and volume inputs. Twelve joint training points, '
        'four separate checks, and retained baseline/axis anchors. No physical validation claim.'
    )
    design = j.request(
        'POST',
        'exploration-designs',
        dict(
            schema_version='1',
            command_id=uid(),
            answer_version_id=answer['answer_version_id'],
            category_dimensions=[],
            combinations=[combo],
            rationale=rationale,
        ),
        201,
    )
    samples = dict(
        schema_version='2',
        command_id=uid(),
        previous_operation_id=None,
        seed=1741,
        category_dimensions=[],
        combinations=[
            dict(
                combo,
                answer_version_id=answer['answer_version_id'],
                training_count=12,
                check_count=4,
                tolerances=[
                    dict(target=o['target'], absolute=1e-6, relative=0.01) for o in basis['outputs']
                ],
            )
        ],
        budget=dict(
            additional_evaluations=16, wall_seconds=3600, point_wall_seconds=60, concurrency=1
        ),
        rationale=rationale,
    )
    vectors = [[i['value'] for i in baseline['inputs']]]
    seen_groups = set()
    for index, dimension in enumerate(dimensions):
        group = dimension['covary_group'] or str(index)
        if group in seen_groups:
            continue
        seen_groups.add(group)
        for endpoint in ('lower', 'upper'):
            vector = vectors[0][:]
            for n, other in enumerate(dimensions):
                if n == index or (dimension['covary_group'] and other['covary_group'] == group):
                    vector[n] = other[endpoint]
            if vector not in vectors:
                vectors.append(vector)
    assert len(seen_groups) == 12 and len(vectors) == 24
    return dict(
        study_id=j.sid,
        source_origin=fixture['origin'],
        baseline=baseline,
        design=design,
        samples=samples,
        anchors=[dict(vector=v, command_id=uid()) for v in vectors],
        build_id=uid(),
    )


def test_captured_joint_domain_with_independent_checks_and_retained_axis_support():
    j = UnitsJourney(SCOPE, BACKEND)
    bridge = None
    proof = dict(passed=False, human_acceptance=False)
    manifest_path = SCOPE.root / 'artifacts/fuel-surrogate-input.json'
    try:
        original_attestation = (
            (SCOPE.root / 'evidence/containment.json').read_bytes() if RESUME else None
        )
        j.start(resume=RESUME, historical=RESUME)
        manifest = json.loads(manifest_path.read_text()) if RESUME else prepare(j)
        if RESUME:
            from exploration_bridge_fixture import prepare_numerical_runtime

            numerical_root = prepare_numerical_runtime(SCOPE)
            if manifest.get('computation_root') != str(numerical_root):
                manifest['prior_build_id'] = manifest['build_id']
                manifest.update(build_id=uid(), computation_root=str(numerical_root))
        manifest_path.write_text(json.dumps(manifest))
        (SCOPE.root / 'artifacts/exploration-browser-input.json').write_text(
            json.dumps(dict(study_id=j.sid))
        )
        log = (SCOPE.root / 'evidence/fuel-surrogate-bridge.log').open('wb')
        bridge_ready = SCOPE.root / 'artifacts/exploration-bridge-ready.json'
        bridge_ready.unlink(missing_ok=True)
        bridge = subprocess.Popen(
            [
                guard.APPROVED_PYTHON,
                '-B',
                str(Path(__file__).with_name('exploration_bridge_fixture.py')),
            ],
            env=guard.clean_environment(SCOPE),
            cwd=REPO,
            stdout=log,
            stderr=log,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if bridge_ready.exists():
                break
            assert bridge.poll() is None
            time.sleep(0.1)
        sample = j.request('POST', 'exploration-samples', manifest['samples'], 202)
        sample = await_state(j, 'exploration-samples/' + sample['operation_id'], ['complete'])
        manifest.setdefault('retained_operation', sample['operation_id'])
        for index, anchor in enumerate(manifest['anchors']):
            if anchor.get('adopted'):
                continue
            if 'configuration_revision_id' not in anchor:
                config = deepcopy(manifest['baseline'])
                config['name'] = 'Explicit local domain anchor ' + str(index)
                for point, value in zip(config['inputs'], anchor['vector'], strict=True):
                    point['value'] = value
                config['context_source']['expected_study_revision'] = j.http.get(
                    '/api/1/studies/' + j.sid
                ).json()['data']['revision']
                saved = j.save_configuration(config)
                anchor['configuration_revision_id'] = saved['configuration'][
                    'configuration_revision_id'
                ]
                manifest_path.write_text(json.dumps(manifest))
            if 'run_id' not in anchor:
                run = j.request(
                    'POST',
                    'runs',
                    dict(
                        command_id=anchor['command_id'],
                        configuration_revision_id=anchor['configuration_revision_id'],
                    ),
                    202,
                )
                anchor['run_id'] = run['run_id']
                manifest_path.write_text(json.dumps(manifest))
            run = await_state(j, 'runs/' + anchor['run_id'], ['recorded'], limit=180)
            assert (
                run['history']['configuration']['inputs']
                == j.request('GET', 'configurations/' + anchor['configuration_revision_id'])[
                    'configuration'
                ]['inputs']
            )
            sample = j.request(
                'POST',
                'exploration-samples/' + manifest['retained_operation'] + '/points',
                dict(command_id=anchor['command_id'], run_id=anchor['run_id'], combination=0),
                201,
            )
            manifest['retained_operation'] = sample['operation_id']
            anchor['adopted'] = True
            manifest_path.write_text(json.dumps(manifest))
            print(
                json.dumps(dict(anchor=index + 1, anchors=24, completed=sample['completed_count'])),
                flush=True,
            )
        sample = j.request('GET', 'exploration-samples/' + manifest['retained_operation'])
        assert sample['completed_count'] == 40 and len(sample['points']) == 40
        build = j.request(
            'POST',
            'exploration-surrogates',
            dict(
                schema_version='1',
                command_id=manifest['build_id'],
                design_id=manifest['design']['design_id'],
                sample_operation_id=manifest['retained_operation'],
            ),
            202,
        )
        build = await_state(
            j, 'exploration-surrogates/' + build['surrogate_version_id'], ['ready', 'assessed']
        )
        proof.update(build=build, samples=sample, source_origin=manifest['source_origin'])
        assert build['state'] == 'ready', build
        assessed_outputs = build['groups'][0]['outputs']
        assert any(o['reason'] is None for o in assessed_outputs), build
        assert all(
            o['reason'] is None
            or (o['reason'] == 'observed_tolerance_unmet' and not o['metrics']['target_met'])
            for o in assessed_outputs
        ), build
        proof['eligible_output_count'] = sum(o['reason'] is None for o in assessed_outputs)
        proof['unmet_output_count'] = sum(o['reason'] is not None for o in assessed_outputs)
        warm = j.request(
            'POST',
            'exploration-surrogates/' + build['surrogate_version_id'] + '/warm',
            dict(command_id=uid()),
            202,
        )
        await_state(j, 'exploration-warm/' + warm['command_id'], ['ready'])
        dimensions = manifest['design']['request']['combinations'][0]['dimensions']
        queries = []
        for axis in dimensions:
            inputs = [
                dict(target=d['target'], units=d['units'], value=v)
                for d, v in zip(dimensions, manifest['anchors'][0]['vector'], strict=True)
            ]
            response = j.request(
                'POST',
                'exploration-surrogates/' + build['surrogate_version_id'] + '/predictions',
                dict(
                    schema_version='1',
                    selection_token=uid(),
                    combination=0,
                    inputs=inputs,
                    axis=axis['target'],
                    curve_points=9,
                ),
            )
            assert all(o['values'][0]['kind'] == 'calculated' for o in response['outputs'])
            for output, assessed in zip(response['outputs'], assessed_outputs, strict=True):
                assert all(
                    v['kind'] in ('calculated', 'estimated')
                    if assessed['reason'] is None
                    else v['kind'] == 'calculated'
                    or (
                        v['kind'] == 'unavailable'
                        and v['value'] is None
                        and v['reason'] == assessed['reason']
                    )
                    for v in output['values'][1:]
                ), output
            queries.append(response)
        proof.update(passed=True, queries=queries, process_count=j.process_count())
        assert j.process_count() == 40
        if RESUME:
            assert (SCOPE.root / 'evidence/containment.json').read_bytes() == original_attestation
            assert (
                build['groups'][0]['original_runtime'] != build['groups'][0]['computation_runtime']
            )
    finally:
        (
            SCOPE.root
            / (
                'evidence/fuel-surrogate-replay-proof.json'
                if RESUME
                else 'evidence/fuel-surrogate-proof.json'
            )
        ).write_text(json.dumps(proof, indent=2))
        if bridge is not None:
            bridge.send_signal(signal.SIGINT)
            bridge.wait(timeout=30)
            log.close()
        j.close()
