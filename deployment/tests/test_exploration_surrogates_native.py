"""Public sample/build/warm/query journey using fresh scalar state for every point."""

from copy import deepcopy
import json
from pathlib import Path
import signal
import subprocess
import time
import shutil

import live_fence
from checks import (
    PROJECTION_SCOPE as SCOPE,
    NATIVE_BACKEND as BACKEND,
    EXPLORATION_UI_RESUME as RESUME,
)
import scoped_fixture as guard
from units_native_fixture import UnitsJourney
from test_exploration_native import joint_fixture
from hyprn_mvp_app.contracts import uid

REPO = Path(__file__).resolve().parents[2]
live_runtime_fence = live_fence.pytest_fixture('baseline')


def await_state(j, path, terminal, limit=2400):
    deadline = time.monotonic() + limit
    last = -1
    while time.monotonic() < deadline:
        value = j.request('GET', path)
        if 'completed_count' in value and value['completed_count'] != last:
            last = value['completed_count']
            progress = dict(
                completed=last,
                attempted=value['attempted_count'],
                elapsed_seconds=value['elapsed_seconds'],
                state=value['state'],
            )
            (SCOPE.root / 'evidence/surrogate-sampling-progress.json').write_text(
                json.dumps(progress)
            )
            print(json.dumps(progress), flush=True)
        if value['state'] in terminal:
            return value
        if value['state'] in ('failed', 'uncertain', 'limited', 'cancelled'):
            raise AssertionError(value)
        time.sleep(0.15)
    raise AssertionError('Bounded native journey deadline')


def test_public_joint_build_warm_predict_and_retained_failure():
    j = UnitsJourney(SCOPE, BACKEND)
    bridge = None
    proof = dict(passed=False, human_acceptance=False)
    try:
        if RESUME:
            product = guard.scoped_path(SCOPE, 'artifacts/units-product-ui')
            if product.exists():
                shutil.rmtree(product)
        j.start(resume=RESUME, historical=RESUME)
        manifest_path = SCOPE.root / 'artifacts/surrogate-native-input.json'
        if RESUME:
            manifest = json.loads(manifest_path.read_text())
            body, design = manifest['samples'], manifest['design']
            combinations = design['request']['combinations']
        else:
            body, _ = joint_fixture(j, all_combinations=True, product_only=True)
            combinations = []
            for combo in body['combinations']:
                basis = j.request(
                    'GET',
                    'answers/'
                    + combo['answer_version_id']
                    + '/exploration-basis/'
                    + combo['configuration_revision_id'],
                )
                dimensions = []
                for port in basis['inputs']:
                    if port['binding']['kind'] != 'free':
                        continue
                    baseline = port['binding']['assignment']['value']
                    dims = dict(
                        target=port['target'],
                        units=port['units'],
                        step=None,
                        common_key=None,
                        covary_group=None,
                    )
                    if port['name'] == 'x':
                        dims.update(
                            lower=0.5, upper=2, step=0.01, covary_group=None, common_key='x'
                        )
                    elif port['name'] == 'y':
                        dims.update(lower=0.5, upper=2, common_key='y')
                    else:
                        dims.update(lower=baseline * 0.995, upper=baseline * 1.01)
                    dimensions.append(dims)
                combo.update(
                    model_id=basis['model_id'],
                    model_revision_id=basis['model_revision_id'],
                    dimensions=dimensions,
                    initial_axis=dimensions[0]['target'],
                    training_count=8,
                    check_count=3,
                    tolerances=[
                        dict(target=p['target'], absolute=1e-6, relative=0.02)
                        for p in basis['outputs']
                    ],
                )
                combinations.append(
                    {
                        k: combo[k]
                        for k in (
                            'categories',
                            'configuration_revision_id',
                            'model_id',
                            'model_revision_id',
                            'initial_axis',
                            'dimensions',
                        )
                    }
                )
            design = j.request(
                'POST',
                'exploration-designs',
                dict(
                    schema_version='1',
                    command_id=uid(),
                    answer_version_id=body['combinations'][0]['answer_version_id'],
                    category_dimensions=body['category_dimensions'],
                    combinations=combinations,
                    rationale='Generic joint interaction with explicit linked properties.',
                ),
                201,
            )
            body.update(schema_version='2')
            body['budget'].update(additional_evaluations=44, wall_seconds=7200)
            (SCOPE.root / 'artifacts/surrogate-native-input.json').write_text(
                json.dumps(
                    dict(study_id=j.sid, design=design, samples=body, password=j.setup['password'])
                )
            )
            (SCOPE.root / 'artifacts/exploration-browser-input.json').write_text(
                json.dumps(dict(study_id=j.sid))
            )
        manifest = json.loads(manifest_path.read_text())
        if RESUME:
            from exploration_bridge_fixture import prepare_numerical_runtime

            numerical_root = prepare_numerical_runtime(SCOPE)
            if manifest.get('computation_root') != str(numerical_root):
                manifest['prior_build_id'] = manifest.get('build_id')
                manifest.update(build_id=uid(), computation_root=str(numerical_root))
                manifest.pop('refinement_id', None)
                manifest_path.write_text(json.dumps(manifest))
        log = (SCOPE.root / 'evidence/surrogate-bridge.log').open('wb')
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
        started = time.monotonic()
        operation = j.request('POST', 'exploration-samples', body, 202)
        if RESUME and operation['state'] == 'cancelled':
            operation = j.request(
                'POST',
                'exploration-samples/' + operation['operation_id'] + '/controls',
                dict(command_id=uid(), action='resume'),
            )
        operation = await_state(j, 'exploration-samples/' + operation['operation_id'], ['complete'])
        proof.update(samples=operation, sampling_seconds=time.monotonic() - started)
        (
            SCOPE.root
            / (
                'evidence/surrogate-native-replay-proof.json'
                if RESUME
                else 'evidence/surrogate-native-proof.json'
            )
        ).write_text(json.dumps(proof, indent=2))
        assert operation['attempted_count'] == 44 and operation['completed_count'] == 44
        manifest.setdefault('build_id', uid())
        manifest_path.write_text(json.dumps(manifest))
        build = j.request(
            'POST',
            'exploration-surrogates',
            dict(
                schema_version='1',
                command_id=manifest.setdefault('build_id', uid()),
                design_id=design['design_id'],
                sample_operation_id=operation['operation_id'],
            ),
            202,
        )
        manifest_path.write_text(json.dumps(manifest))
        build = await_state(
            j, 'exploration-surrogates/' + build['surrogate_version_id'], ['ready', 'assessed']
        )
        proof['build'] = build
        assert build['state'] == 'ready', build
        assert all(o['reason'] is None for g in build['groups'] for o in g['outputs']), build
        warm_started = time.monotonic()
        warm = j.request(
            'POST',
            'exploration-surrogates/' + build['surrogate_version_id'] + '/warm',
            dict(command_id=uid()),
            202,
        )
        warm = await_state(j, 'exploration-warm/' + warm['command_id'], ['ready'])
        proof['explicit_warm_seconds'] = time.monotonic() - warm_started
        if manifest.get('refinement_id'):
            retained = j.request('GET', 'exploration-surrogates/' + manifest['refinement_id'])
            if retained['state'] == 'ready':
                warm = j.request(
                    'POST',
                    'exploration-surrogates/' + manifest['refinement_id'] + '/warm',
                    dict(command_id=uid()),
                    202,
                )
                await_state(j, 'exploration-warm/' + warm['command_id'], ['ready'])
        latencies = []
        for index in range(50):
            combo = combinations[index % 4]
            dimensions = combo['dimensions']
            x = (115 + index % 20) / 100
            fraction = (1.2 + 0.002 * index - 0.5) / 1.5
            inputs = [
                dict(
                    target=d['target'],
                    units=d['units'],
                    value=x
                    if d['common_key'] == 'x'
                    else d['lower'] + fraction * (d['upper'] - d['lower']),
                )
                for d in dimensions
            ]
            query = dict(
                schema_version='1',
                selection_token=uid(),
                combination=index % 4,
                inputs=inputs,
                axis=dimensions[index % 2]['target'],
                curve_points=17,
            )
            started = time.monotonic()
            prediction = j.request(
                'POST',
                'exploration-surrogates/' + build['surrogate_version_id'] + '/predictions',
                query,
            )
            latencies.append((time.monotonic() - started) * 1000)
            assert prediction['selection_token'] == query['selection_token']
            original = 1
            for point in inputs:
                original *= point['value']
            value = prediction['outputs'][0]['values'][0]
            assert value['kind'] == 'estimated', value
            assert abs(value['value'] - original) <= 0.02 * abs(original) + 1e-6
        proof.update(api_latency_ms=latencies, api_p95_ms=sorted(latencies)[47])
        assert proof['api_p95_ms'] <= 250, proof['api_p95_ms']
        reordered = dict(query, selection_token=uid(), inputs=list(reversed(query['inputs'])))
        invariant = j.request(
            'POST',
            'exploration-surrogates/' + build['surrogate_version_id'] + '/predictions',
            reordered,
        )
        assert invariant['outputs'] == prediction['outputs']
        proof['input_order_invariant'] = True
        outside = deepcopy(query)
        outside.update(selection_token=uid(), axis=None, curve_points=0)
        outside['inputs'][0]['value'] = 3
        unavailable = j.request(
            'POST',
            'exploration-surrogates/' + build['surrogate_version_id'] + '/predictions',
            outside,
        )
        assert all(
            output['values'][0]['value'] is None
            and output['values'][0]['reason'] == 'outside_bounds'
            for output in unavailable['outputs']
        )
        proof['outside_domain'] = unavailable
        env = guard.clean_environment(SCOPE)
        env['HYPRN_MVP_UI_BASE_URL'] = j.url
        env['HYPRN_MVP_UI_EVIDENCE_ROOT'] = str(SCOPE.root / 'evidence/surrogate-browser')
        with (SCOPE.root / 'evidence/surrogate-browser.log').open('w') as out:
            browser = subprocess.run(
                [
                    'node',
                    str(REPO / 'ui/node_modules/playwright/cli.js'),
                    'test',
                    '--config',
                    str(REPO / 'ui/playwright.config.ts'),
                    'exploration-surrogates.spec.ts',
                    '--reporter=json',
                ],
                cwd=REPO / 'ui',
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=190,
            )
        assert browser.returncode == 0, 'Inspect surrogate-browser.log'
        proof['browser'] = json.loads(
            (SCOPE.root / 'evidence/surrogate-browser-latency.json').read_text()
        )
        selected = json.loads(
            (SCOPE.root / 'artifacts/surrogate-selected-ui-point.json').read_text()
        )
        detail = await_state(j, 'runs/' + selected['run_id'], ['recorded'], limit=180)
        assert detail['state'] == 'recorded'
        page = j.request(
            'GET',
            'exploration-samples',
            params=dict(answer_version_id=design['request']['answer_version_id']),
        )
        enriched = next(
            (op for op in page if any(p['run_id'] == selected['run_id'] for p in op['points'])),
            None,
        )
        if enriched is None:
            enriched = j.request(
                'POST',
                'exploration-samples/' + operation['operation_id'] + '/points',
                dict(command_id=uid(), run_id=selected['run_id'], combination=0),
                201,
            )
        original_count = j.process_count()
        assert (
            len(enriched['points']) == original_count
            and enriched['completed_count'] == original_count
        )
        proof['selected_point_enrichment'] = enriched
        if manifest.get('refinement_id'):
            existing = j.request('GET', 'exploration-surrogates/' + manifest['refinement_id'])
            if existing['state'] == 'ready':
                manifest['refinement_id'] = uid()
        manifest.setdefault('refinement_id', uid())
        manifest_path.write_text(json.dumps(manifest))
        refined = j.request(
            'POST',
            'exploration-surrogates',
            dict(
                schema_version='1',
                command_id=manifest['refinement_id'],
                design_id=design['design_id'],
                sample_operation_id=enriched['operation_id'],
            ),
            202,
        )
        # The old immutable version stays queryable while a replacement is constructed.
        previous = j.request(
            'POST',
            'exploration-surrogates/' + build['surrogate_version_id'] + '/predictions',
            query,
        )
        assert previous['identity'] == prediction['identity']
        assert j.request('GET', 'exploration-surrogates/' + build['surrogate_version_id']) == build
        if refined['state'] in ('pending', 'building'):
            env['HYPRN_MVP_TEST_REFINEMENT_ID'] = refined['surrogate_version_id']
            with (SCOPE.root / 'evidence/surrogate-browser-refinement.log').open('w') as out:
                active_browser = subprocess.run(
                    browser.args,
                    cwd=REPO / 'ui',
                    env=env,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    timeout=190,
                )
            assert active_browser.returncode == 0, 'Inspect surrogate-browser-refinement.log'
            proof['browser_during_refinement'] = json.loads(
                (SCOPE.root / 'evidence/surrogate-browser-refinement-latency.json').read_text()
            )
        refined = await_state(
            j, 'exploration-surrogates/' + refined['surrogate_version_id'], ['ready', 'assessed']
        )
        assert refined['state'] == 'ready' and refined['identity'] != build['identity']
        proof['refinement'] = refined
        assert j.process_count() == original_count
        proof['passed'] = True
    finally:
        (
            SCOPE.root
            / (
                'evidence/surrogate-native-replay-proof.json'
                if RESUME
                else 'evidence/surrogate-native-proof.json'
            )
        ).write_text(json.dumps(proof, indent=2))
        if bridge is not None:
            bridge.send_signal(signal.SIGINT)
            bridge.wait(timeout=30)
            log.close()
        j.close()
