"""A served canonical-graph journey over real scalar and OpenMDAO results."""

import live_fence

live_runtime_fence = live_fence.pytest_fixture('baseline')

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import time

from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND, EXPLORATION_UI_RESUME
import scoped_fixture as guard
from units_native_fixture import UnitsJourney
from test_exploration_native import author, process
from hyprn_mvp_app.contracts import uid

REPO = Path(__file__).resolve().parents[2]


def test_served_graph_preserves_calculated_and_estimated_identity():
    j = UnitsJourney(SCOPE, BACKEND)
    proof = dict(passed=False, human_acceptance=False, physical_validation=False)
    capture_only = False
    try:
        if EXPLORATION_UI_RESUME:
            # Replay validates today's product source, while retaining scientific records.
            guard.validate_scope(SCOPE)
            product = guard.scoped_path(SCOPE, 'artifacts/units-product-ui')
            if product.exists():
                shutil.rmtree(product)
        j.start(resume=EXPLORATION_UI_RESUME)
        if EXPLORATION_UI_RESUME:
            proof = json.loads((SCOPE.root / 'evidence/exploration-ui-proof.json').read_text())
            manifest = json.loads(
                (SCOPE.root / 'artifacts/exploration-browser-input.json').read_text()
            )
            fixture = dict(origin=proof['origin'])
            baseline_detail, fit = proof['baseline'], proof['fit']
            capture_only = proof['passed']
            if not capture_only:
                assert not (SCOPE.root / 'artifacts/exploration-submitted.json').exists(), (
                    'Reconcile the previous selected-point command before resubmitting'
                )
            if capture_only:
                manifest['selected_run_id'] = proof['selected']['run_id']
                (SCOPE.root / 'artifacts/exploration-browser-input.json').write_text(
                    json.dumps(manifest)
                )
        else:
            fixture, baseline, frozen, answer, axis = author(j)
            baseline_id, baseline_detail, _ = j.execute(frozen)
            update = {
                k: deepcopy(answer[k])
                for k in (
                    'approach_version_id',
                    'case_id',
                    'observations',
                    'interpretation',
                    'qualifications',
                    'open_deliverables',
                    'basis',
                )
            }
            update['basis']['run_ids'] = [baseline_id]
            answer = j.request(
                'POST',
                'answers',
                dict(
                    update,
                    schema_version='1',
                    command_id=uid(),
                    expected_revision=answer['answer_version_id'],
                ),
                201,
            )
            basis = j.request(
                'GET',
                'answers/'
                + answer['answer_version_id']
                + '/exploration-basis/'
                + frozen['configuration']['configuration_revision_id'],
            )
            request = dict(
                schema_version='1',
                command_id=uid(),
                selection_token=uid(),
                operation='design',
                answer_version_id=answer['answer_version_id'],
                configuration_revision_id=frozen['configuration']['configuration_revision_id'],
                axis=axis,
                lower=5.8,
                upper=6.2,
                seed=1729,
                training_count=5,
                check_count=2,
                method='response_surface',
                training_run_ids=[],
                check_run_ids=[],
                query_values=[5.9, 6.0, 6.1],
                tolerances=[
                    dict(target=o['target'], absolute=1e-6, relative=0.01) for o in basis['outputs']
                ],
                rationale='Explicit local screening slice; observed 1% agreement, not validation.',
            )
            design = process(j, request)
            numerical = design['numerical']['result']
            records = []
            for index, vector in enumerate(
                numerical['training_vectors'] + numerical['check_vectors']
            ):
                candidate = deepcopy(baseline)
                candidate['name'] = 'Browser reference ' + str(index)
                next(i for i in candidate['inputs'] if i['target'] == axis)['value'] = vector[0]
                candidate['context_source']['expected_study_revision'] = j.http.get(
                    '/api/1/studies/' + j.sid
                ).json()['data']['revision']
                saved = j.save_configuration(candidate)
                rid, detail, _ = j.execute(saved)
                records.append(dict(run_id=rid, history=detail))
            fit = process(
                j,
                dict(
                    request,
                    command_id=uid(),
                    operation='fit_predict',
                    training_run_ids=[r['run_id'] for r in records[:5]],
                    check_run_ids=[r['run_id'] for r in records[5:]],
                ),
            )
            manifest = dict(
                study_id=j.sid,
                answer=answer,
                fit=fit,
                baseline=baseline_detail,
                password=j.setup['password'],
            )
            proof.update(
                origin=fixture['origin'], baseline=baseline_detail, fit=fit, records=records
            )
            (SCOPE.root / 'artifacts/exploration-browser-input.json').write_text(
                json.dumps(manifest)
            )
        env = guard.clean_environment(j.scope)
        env['HYPRN_MVP_UI_BASE_URL'] = j.url
        env['HYPRN_MVP_UI_EVIDENCE_ROOT'] = str(SCOPE.root / 'evidence/browser')
        command = [
            'node',
            str(REPO / 'ui/node_modules/playwright/cli.js'),
            'test',
            '--config',
            str(REPO / 'ui/playwright.config.ts'),
            'exploration.spec.ts',
            '--grep',
            'retained graph' if capture_only else 'canonical graph',
            '--reporter=json',
        ]
        submitted = SCOPE.root / 'artifacts/exploration-submitted.json'
        with (
            (
                SCOPE.root
                / (
                    'evidence/exploration-capture.json'
                    if capture_only
                    else 'evidence/exploration-browser.json'
                )
            ).open('w') as out,
            (SCOPE.root / 'evidence/exploration-browser.stderr.log').open('w') as err,
        ):
            browser = subprocess.Popen(command, cwd=REPO / 'ui', env=env, stdout=out, stderr=err)
            deadline = time.monotonic() + 240
            dispatched = None
            while browser.poll() is None and time.monotonic() < deadline:
                if not capture_only and submitted.exists() and dispatched is None:
                    dispatched = json.loads(submitted.read_text())['run_id']
                    j.dispatch(dispatched, prepare_only=True)
                    j.dispatch(dispatched)
                time.sleep(0.2)
            if browser.poll() is None:
                browser.terminate()
                browser.wait(timeout=10)
            assert browser.returncode == 0, 'Inspect exploration-browser.json and stderr'
        if capture_only:
            assert j.process_count() == 9
            assert j.request('GET', 'runs/' + proof['selected']['run_id']) == proof['selected']
            proof['retained_browser_replay'] = True
            return
        assert dispatched is not None
        detail = j.request('GET', 'runs/' + dispatched)
        assert detail['history']['results']['execution']['state'] == 'finished'
        assert j.process_count() == 9
        proof.update(
            passed=True,
            origin=fixture['origin'],
            baseline=baseline_detail,
            fit=fit,
            selected=detail,
            attestation=j.native.require_attestation(),
            lifecycle_events=j.events,
        )
    finally:
        (SCOPE.root / 'evidence/exploration-ui-proof.json').write_text(json.dumps(proof, indent=2))
        j.close()
