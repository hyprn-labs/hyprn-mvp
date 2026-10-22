"""Served-browser seed: fresh SQLite records behind the real public API.

- The result source is a retained record in an earlier format (configuration 2, results 1),
  stored as history and never re-saved: every read must show it unchanged.
- The configurable model is the captured Model4 case (typed dimensionless units). New
  configurations are version 6: no criteria and no approach selection.
- The private modeling service is an explicit typed test double. It advertises exactly the
  capabilities a configuration 6 needs and answers compatibility with identity unit
  interpretations; it never prepares, executes or judges anything.

Captured scientific bytes stay inert. Nothing here imports or runs candidate code.
"""

import base64
import copy
import json

from fastapi.testclient import TestClient

from criteria_free import CRITERIA_FREE_CAPABILITY, bind_case
from execution_fixtures import fixture, runtime_fixture
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.modeling import UNIT_CATALOG_DIGEST, validate
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.store import Store, digest, uid
from hyprn_mvp_app.units import port_units

OWNER = ('owner', 'correct horse battery staple')


def capabilities(generator_identity, build):
    """Everything a configuration 6 on a Model4 version needs, each entry explicit."""
    from test_assumptions_evidence_contracts import sample, D

    caps = sample(D['Capabilities'])
    item = sample(D['Capabilities']['properties']['capabilities']['items'])
    caps.update(
        contract_versions=['1.1', '1.2', '1.3'],
        schema_versions=['1', '2', '3', '4'],
        service_build=build,
        generator_identity=copy.deepcopy(generator_identity),
        capabilities=[
            dict(item, id='resolved_configuration', version='3', supported=True),
            dict(item, id='unit_declarations', version='1', supported=True),
            dict(item, id='quantity_definitions', version='1', supported=True),
            copy.deepcopy(CRITERIA_FREE_CAPABILITY),
        ],
    )
    return caps


def compatibility(candidate, model, validator):
    """A compatible private answer for exactly this candidate: identity interpretation of
    every input into the bound units of its port."""
    from test_assumptions_evidence_contracts import sample, D

    bound = port_units(model)
    versions = {i['instance_id']: i['definition_version_id'] for i in model['instances']}
    proof = sample(D['CompatibilityResult2'])
    proof.update(
        compatible=True,
        diagnostics=[],
        candidate_digest=digest(candidate),
        model_digest=model['digest'],
        model_revision_id=model['model_revision_id'],
        required_capabilities=candidate['required_capabilities'],
        validator_identity=validator,
        input_interpretations=[
            dict(
                target=copy.deepcopy(i['target']),
                conversion=dict(
                    policy='openmdao-linear-catalog-1',
                    catalog_digest=UNIT_CATALOG_DIGEST,
                    source_units=i['units'],
                    destination_units=bound[
                        (
                            i['target']['instance_id'],
                            versions[i['target']['instance_id']],
                            i['target']['port_id'],
                        )
                    ],
                    factor=1,
                    destination_value=i['value'],
                ),
            )
            for i in candidate['inputs']
        ],
    )
    return proof


class PrivateModelDouble:
    """Typed private modeling double for one Model4 revision. ``offline`` models a retained
    read that must never contact modeling."""

    def __init__(self, case):
        self.case = case
        self.calls = []
        self.offline = False

    def call(self, actor, sid, method, path, body=None, **kwargs):
        if self.offline:
            raise AssertionError('Retained read/replay contacted modeling')
        self.calls.append((actor, sid, method, path, copy.deepcopy(body)))
        model = copy.deepcopy(self.case['frozen']['model_snapshot'])
        if method == 'GET' and path == '/capabilities':
            result = capabilities(
                self.case['prepared']['generator_identity'], 'served-private-double'
            )
        elif method == 'GET' and path == '/unit-catalog':
            from test_unit_guidance_api import CATALOG

            result = copy.deepcopy(CATALOG)
        elif method == 'GET' and path.endswith('/revisions/' + model['model_revision_id']):
            result = model
        else:
            assert method == 'POST' and path.endswith('/configuration-compatibility'), (
                method,
                path,
            )
            validate(kwargs['request_schema'], body)
            result = compatibility(body['configuration_candidate'], model, 'served-private-double')
        validate(kwargs['response_schema'], dict(schema_version='1', request_id=uid(), data=result))
        return 200, dict(data=copy.deepcopy(result))


def _legacy_source(store, actor, sid, study):
    """One finished run recorded under configuration 2 and results 1 (outputs 150, 151)."""
    case = fixture('chain')
    config = case['frozen']['configuration']
    config.update(
        schema_version='2',
        study_id=sid,
        derivation=None,
        context_source=dict(kind='current_study', expected_study_revision=study['revision']),
    )
    config['context_snapshot'].update(description='', boundary='')
    for item in config['inputs']:
        item['result_binding'] = None
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    validate('ConfigurationRevision2', config)
    prepared = case['prepared']
    prepared['configuration_digest'] = project_scientific_configuration(config)['digest']
    prepared['executable_content_digest'] = executable_digest(prepared)
    prepared['prepared_digest'] = digest(
        {k: v for k, v in prepared.items() if k != 'prepared_digest'}
    )
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations VALUES(?,?,?,?)',
            (
                config['configuration_revision_id'],
                config['configuration_id'],
                sid,
                json.dumps(case['frozen']),
            ),
        )
        db.execute('INSERT INTO model_associations VALUES(?,?,?)', (sid, config['model_id'], uid()))
        db.execute(
            'INSERT INTO configuration_families VALUES(?,?,?)',
            (config['configuration_id'], sid, config['configuration_revision_id']),
        )
    run = Submissions(store, None, None).submit(
        actor,
        sid,
        dict(command_id=uid(), configuration_revision_id=config['configuration_revision_id']),
    )
    rid = run['run_id']
    bundle = assemble_bundle(
        rid,
        prepared,
        case['files'],
        case['frozen'],
        runtime_fixture(),
        dict(schema_version='1', sources=[], mappings=[]),
    )
    request = dict(
        run_id=rid,
        scope=sid,
        command_id=run['command_id'],
        payload_digest=store.receipt(actor, sid, 'run', run['command_id'])['payload_digest'],
        bundle_digest=bundle['manifest']['bundle_digest'],
    )
    outputs = json.loads(case['files'][prepared['entrypoint']['bindings_path']])['outputs']
    results = dict(
        schema_version='1',
        run_id=rid,
        bundle_digest=request['bundle_digest'],
        execution=dict(state='finished', exit_code=0, message='Complete'),
        convergence=dict(state='not_applicable', diagnostics_ref=None),
        optimization=dict(termination='not_applicable', feasibility='not_applicable'),
        completeness=dict(expected=len(outputs), available=len(outputs), failed=0, unavailable=0),
        outputs=[
            dict(
                target=o['target'],
                value=150 + i,
                units=o['units'],
                availability='available',
                reason=None,
                producer_completed=True,
                assigned=True,
            )
            for i, o in enumerate(outputs)
        ],
        criteria=[],
        applicability=dict(state='unassessed', evidence_refs=[]),
        artifacts=[],
    )
    association = dict(store_uuid=uid(), process_uuid=uid())
    payload = dict(
        actor=actor,
        frozen=copy.deepcopy(case['frozen']),
        request=request,
        bundle=dict(
            manifest=bundle['manifest'],
            files={p: base64.b64encode(raw).decode() for p, raw in bundle['files'].items()},
        ),
    )
    payload['history'] = projection(
        payload,
        dict(
            request=request,
            bundle=bundle,
            results=results,
            assessment=None,
            artifacts={},
            errors=[],
        )
        | association,
        association,
    )
    with store.connection(write=True) as db:
        db.execute(
            'UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',
            (*association.values(), rid),
        )
        db.execute(
            "UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",
            (json.dumps(payload), rid),
        )
    return rid, results


def seed(root, origin):
    """Fresh store, owner session and a configuration 6 request whose first input uses the
    retained source's first output; the remaining inputs are explicit literals."""
    store = Store(root / 'served.sqlite')
    auth = Auth(store, origin)
    actor = auth.provision(*OWNER)
    study = store.create_study(actor, uid(), 'Fresh source study')
    sid = study['study_id']
    rid, results = _legacy_source(store, actor, sid, study)
    case = bind_case('chain', sid, study_revision=study['revision'])
    config = case['frozen']['configuration']
    with store.connection(write=True) as db:
        db.execute('INSERT INTO model_associations VALUES(?,?,?)', (sid, config['model_id'], uid()))
    model = PrivateModelDouble(case)
    client = TestClient(create_app(store, auth, model), base_url=origin)
    session = client.post(
        '/api/1/session',
        json=dict(username=OWNER[0], password=OWNER[1]),
        headers={'Origin': origin},
    )
    assert session.status_code == 200, session.text
    client.headers.update({'Origin': origin, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    first, *rest = config['inputs']
    candidate = dict(
        schema_version='6',
        study_id=sid,
        model_id=config['model_id'],
        model_revision_id=config['model_revision_id'],
        name='Linked comparison',
        inputs=[
            dict(
                kind='run_result',
                target=first['target'],
                source_run_id=rid,
                source_output=results['outputs'][0]['target'],
                expected_results_digest=digest(results),
                provenance=first['provenance'],
            ),
            *[
                dict(
                    kind='literal',
                    **{k: copy.deepcopy(i[k]) for k in ('target', 'value', 'units', 'provenance')},
                )
                for i in rest
            ],
        ],
        numerical=copy.deepcopy(config['numerical']),
        context_source=dict(kind='current_study', expected_study_revision=study['revision']),
        notes=[],
        derivation=None,
        assumptions=[],
        general_context_evidence_version_ids=[],
    )
    validate('ConfigurationRequest6', candidate)
    return dict(
        client=client,
        store=store,
        auth=auth,
        actor=actor,
        sid=sid,
        rid=rid,
        case=case,
        model=model,
        candidate=candidate,
    )


def path(data, suffix):
    return '/api/1/studies/' + data['sid'] + '/' + suffix


def commit_body(data):
    """An exact ConfigurationCommit6 for the seeded request, pinned to its public preview."""
    response = data['client'].post(path(data, 'configurations/preview'), json=data['candidate'])
    assert response.status_code == 200, response.text
    validate('ConfigurationPreview8', response.json()['data'])
    return dict(
        command_id=uid(),
        expected_revision=None,
        configuration_id=None,
        configuration=copy.deepcopy(data['candidate']),
        expected_preview_digest=response.json()['data']['candidate_digest'],
    )
