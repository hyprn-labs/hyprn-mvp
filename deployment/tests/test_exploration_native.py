"""Actual isolated scalar source evaluations and bounded OpenMDAO estimation.

Fuel is evaluation data only. Product selection uses exact public port identities.
"""

import live_fence

live_runtime_fence = live_fence.pytest_fixture('baseline')

from copy import deepcopy
import json
from pathlib import Path
import time
import pytest

from aiida import orm
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from units_native_fixture import UnitsJourney, literal
from approach_native_fixture import step
from hyprn_mvp_app.contracts import uid
from hyprn_mvp_app.exploration import validate_public

REPO = Path(__file__).resolve().parents[2]


def author(j):
    fixture = json.loads((REPO / 'integration/tests/fixtures/exploration-fuel.json').read_text())
    model = fixture['model']
    sources = {s['sha256']: s for s in model['source_files']}
    versions = {d['definition_version_id']: d for d in model['definitions']}
    edits, definitions, instances, ports = [], {}, {}, {}
    for index, instance in enumerate(model['instances']):
        d = versions[instance['definition_version_id']]
        key = 'definition_' + str(index)
        assert len(d['source_refs']) == 1
        definitions[instance['instance_id']] = key
        instances[instance['instance_id']] = 'instance_' + str(index)
        rows = []
        for n, p in enumerate(d['ports']):
            port_key = 'port_' + str(n)
            ports[instance['instance_id'], p['port_id']] = (port_key, p['code_symbol'])
            rows.append(
                dict(
                    temp_key=port_key,
                    **{
                        k: p[k] for k in ('direction', 'name', 'code_symbol', 'value_type', 'units')
                    },
                )
            )
        edits += [
            dict(
                kind='create_definition',
                temp_key=key,
                definition_kind=d['kind'],
                name=d['name'],
                ports=rows,
                source=sources[d['source_refs'][0]],
            ),
            dict(
                kind='instantiate',
                temp_key=instances[instance['instance_id']],
                version_ref=dict(temp_key=key),
            ),
        ]

    def ref(target):
        inst, port = target['instance_id'], target['port_id']
        return dict(
            instance_temp_key=instances[inst],
            definition_temp_key=definitions[inst],
            port_temp_key=ports[inst, port][0],
        )

    for n, connection in enumerate(model['connections']):
        edits.append(
            dict(
                kind='connect',
                temp_key='connection_' + str(n),
                source_ref=ref(connection['source_ref']),
                target_ref=ref(connection['target_ref']),
            )
        )
    _, saved = j.model('Captured source scalar exploration', edits)
    assert {s['sha256'] for s in saved['source_files']} == {
        versions[i['definition_version_id']]['source_refs'][0] for i in model['instances']
    }
    remap = {}
    for original in model['instances']:
        d = versions[original['definition_version_id']]
        new_d = next(item for item in saved['definitions'] if item['name'] == d['name'])
        new_i = next(
            item
            for item in saved['instances']
            if item['definition_version_id'] == new_d['definition_version_id']
        )
        for p in d['ports']:
            new_p = next(item for item in new_d['ports'] if item['code_symbol'] == p['code_symbol'])
            remap[original['instance_id'], p['port_id']] = dict(
                instance_id=new_i['instance_id'], port_id=new_p['port_id']
            )
    evidence = j.evidence('Exact captured source and declared screening inputs')
    assignments = [
        literal(
            remap[i['target']['instance_id'], i['target']['port_id']],
            i['value'],
            i['units'],
            evidence['evidence_version_id'],
        )
        for i in fixture['inputs']
    ]
    binding = dict(
        binding_id=uid(), model_id=saved['model_id'], model_revision_id=saved['model_revision_id']
    )
    method = step('Evaluate the exact captured cruise screening source')
    method.update(
        implementation_state='linked',
        implementation_refs=[dict(kind='model', binding_id=binding['binding_id'])],
    )
    approach = j.save_approach(
        dict(
            schema_version='1',
            question='How does the recorded screening model respond?',
            scope='One explicit Mach slice; not physical validation',
            limitations='Original cruise-only assumptions remain',
            open_questions='Full mission and physical validation',
            model_bindings=[binding],
            steps=[method],
            assumptions=[],
            cases=[],
            basis_refs=[],
        )
    )
    baseline = j.configuration(
        saved,
        'Captured common comparison',
        assignments,
        [],
        dict(approach_version_id=approach['version']['approach_version_id'], case_id=None),
        evidence,
    )
    frozen = j.save_configuration(baseline)
    answer = j.request(
        'POST',
        'answers',
        dict(
            schema_version='1',
            command_id=uid(),
            expected_revision=None,
            approach_version_id=approach['version']['approach_version_id'],
            case_id=None,
            observations='A recorded screening configuration provides the explicit baseline.',
            interpretation='No physical feasibility conclusion is implied by a computed response.',
            qualifications=['One-dimensional tracer only.'],
            open_deliverables=['Full mission closure.'],
            basis=dict(
                configuration_revision_ids=[frozen['configuration']['configuration_revision_id']],
                run_ids=[],
                evidence_version_ids=[evidence['evidence_version_id']],
                case_answer_version_ids=[],
            ),
        ),
        201,
    )
    axis_old = next(
        (i['instance_id'], p['port_id'])
        for i in model['instances']
        for p in versions[i['definition_version_id']]['ports']
        if p['code_symbol'] == 'mach'
    )
    return fixture, baseline, frozen, answer, remap[axis_old]


def process(j, request):
    accepted = j.request('POST', 'exploration-requests', request, 202)
    assert accepted['state'] == 'pending'
    # Exercise the production app-side dispatcher and its fixed stdio bridge.
    import dispatch_runtime
    import combined_fixture

    command = [
        guard.APPROVED_CONTRACT_PYTHON,
        '-B',
        combined_fixture.__file__,
        'dispatch',
        '--once',
    ]
    with (SCOPE.root / 'evidence' / ('exploration-' + request['command_id'] + '.log')).open(
        'wb'
    ) as log:
        status = dispatch_runtime.bridge_child(
            j.native, command, env=guard.clean_environment(SCOPE), cwd=REPO, stderr=log
        )
    assert status == 0
    result = j.request('GET', 'exploration-requests/' + request['command_id'])
    assert result['state'] == 'complete', result
    validate_public('ExplorationOperation1', result)
    assert j.request('POST', 'exploration-requests', request, 202) == result
    return result['result']


def test_real_scalar_samples_assessed_predictions_and_retained_identity():
    j = UnitsJourney(SCOPE, BACKEND)
    proof = dict(passed=False)
    try:
        j.start()
        fixture, baseline, frozen, answer, axis = author(j)
        path = (
            'answers/'
            + answer['answer_version_id']
            + '/exploration-basis/'
            + frozen['configuration']['configuration_revision_id']
        )
        basis = j.request('GET', path)
        assert len([p for p in basis['inputs'] if p['binding']['kind'] == 'free']) == 14
        assert len(basis['outputs']) == 11
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
            rationale=(
                'Explicit small local slice around the captured Mach 6 baseline; '
                '1% observed tolerance, not a bound.'
            ),
        )
        assert j.process_count() == 0
        design = process(j, request)
        assert j.process_count() == 0
        vectors = (
            design['numerical']['result']['training_vectors']
            + design['numerical']['result']['check_vectors']
        )
        records = []
        for index, vector in enumerate(vectors):
            configuration = deepcopy(baseline)
            configuration['name'] = 'Explicit sample ' + str(index)
            next(i for i in configuration['inputs'] if i['target'] == axis)['value'] = vector[0]
            # Author against the current study revision through ordinary public APIs.
            configuration['context_source']['expected_study_revision'] = j.http.get(
                '/api/1/studies/' + j.sid
            ).json()['data']['revision']
            saved = j.save_configuration(configuration)
            start = time.monotonic()
            rid, detail, node = j.execute(saved)
            records.append(
                dict(
                    run_id=rid,
                    history=detail,
                    elapsed_seconds=time.monotonic() - start,
                    process_uuid=node.uuid,
                )
            )
        fits = []
        for method in ('response_surface', 'kriging'):
            fitted = process(
                j,
                dict(
                    request,
                    command_id=uid(),
                    operation='fit_predict',
                    method=method,
                    training_run_ids=[r['run_id'] for r in records[:5]],
                    check_run_ids=[r['run_id'] for r in records[5:]],
                ),
            )
            outputs = fitted['numerical']['result']['outputs']
            assert len(outputs) == 11
            assert all(o['assessed_count'] == 2 for o in outputs)
            assert any(o['state'] == 'estimated' for o in outputs)
            assert (
                fitted['samples'][0]['inputs']
                == records[0]['history']['history']['configuration']['inputs']
            )
            node = orm.load_node(fitted['numerical']['artifact_uuid'])
            assert node.creator.uuid == fitted['numerical']['process_uuid']
            with node.open(mode='rb') as stream:
                assert json.load(stream)['result'] == fitted['numerical']['result']
            fits.append(fitted)
        # Fault injection changes only copied data artifacts, never original runs.
        # A missing independent reference stays a failed row, never a zero or
        # a silently reduced assessment denominator.
        process_node = orm.load_node(fits[0]['numerical']['process_uuid'])
        with process_node.inputs.request.open(mode='rb') as stream:
            numerical_request = json.load(stream)
        numerical_request['checks'][0]['y'][0] = None
        unavailable = j.native.explore(numerical_request)['result']['outputs'][0]
        assert unavailable['state'] == 'unavailable'
        assert unavailable['failed_count'] == 1 and unavailable['evaluable_count'] == 1
        assert unavailable['values'] == [None, None, None]
        assert unavailable['reason'] == 'incomplete_samples'
        # Raw JSON files, unlike Dict nodes, preserve the exact sampling floats.
        assert numerical_request['training'][2]['x'] == vectors[2]
        # Even tiny drift in an independent coordinate invalidates the declared
        # seeded partition; a different holdout is never silently substituted.
        mismatched = deepcopy(numerical_request)
        mismatched['checks'][0]['x'][0] += 1e-9
        before = set((SCOPE.root / 'evidence').glob('*-worker-*.json'))
        with pytest.raises(RuntimeError, match='Bounded exploration computation failed'):
            j.native.explore(mismatched)
        reports = set((SCOPE.root / 'evidence').glob('*-worker-*.json')) - before
        assert len(reports) == 1
        assert (
            'Samples must match the exact seeded partition'
            in json.loads(reports.pop().read_text())['output']
        )
        assert j.process_count() == 7
        # Unsupported requests do not start scientific or numerical processes.
        bad = dict(request, command_id=uid(), query_values=[6.3])
        j.request('POST', 'exploration-requests', bad, 400)
        j.offline()
        for fitted in fits:
            assert (
                j.request('GET', 'exploration-requests/' + fitted['request']['command_id'])[
                    'result'
                ]
                == fitted
            )
        proof.update(
            passed=True,
            origin=fixture['origin'],
            baseline=frozen,
            design=design,
            records=records,
            fits=fits,
            lifecycle_events=j.events,
            attestation=j.native.require_attestation(),
            physical_validation=False,
            human_acceptance=False,
        )
    finally:
        (SCOPE.root / 'evidence/exploration-native-proof.json').write_text(
            json.dumps(proof, indent=2)
        )
        j.close()
