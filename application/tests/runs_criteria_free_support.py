"""Authoring support for result-bound and modified configurations 6 (no criteria).

Built on ``criteria_free``: a captured Model4 case, its configuration 6 and protocol-3 source
runs. New configurations are authored only as ``ConfigurationRequest6``. Nothing here executes
candidate code; the private modeling boundary is an explicit double that validates every
request and response against the same schemas as the real client.

- ``ModelingDouble(case)``: answers capabilities, the exact model revision and configuration
  compatibility; records compatibility candidates in ``sent``; ``hook`` runs inside the
  compatibility call; ``offline`` makes any contact a failure.
- ``bindings_env(tmp_path, kind)``: a service-level store with one protocol-3 source run and a
  version-6 request whose first input is bound to that run's first output.
- ``reuse_api(tmp_path)``: the same over the real public API with a signed-in owner.
- ``prepared_for(case, frozen)``: the case's preparation 4 re-bound to a saved configuration.
- ``retain(store, actor, sid, case, frozen, dependencies=None)``: record a protocol-3 run of a
  saved configuration (results 3, no criteria); returns ``(run_id, results)``.
"""

from legacy_study_support import seed_legacy_context

import base64
import copy
import json

from criteria_free import (
    CRITERIA_FREE_CAPABILITY,
    bind_case,
    insert_case,
    outputs_of,
    record_run,
    request6,
)
from execution_fixtures import runtime_fixture
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.store import Store, digest, uid
from hyprn_mvp_app.units import UNIT_CATALOG_DIGEST, port_units

ORIGIN = 'http://127.0.0.1:19999'
PASSWORD = 'correct horse battery staple'


def capabilities(case):
    """Capabilities that resolve a configuration 6 on a Model4 revision with typed units."""
    from test_assumptions_evidence_contracts import sample, D

    caps = sample(D['Capabilities'])
    item = sample(D['Capabilities']['properties']['capabilities']['items'])
    caps.update(
        contract_versions=['1.2', '1.3'],
        schema_versions=['1', '2', '3', '4'],
        service_build='criteria-free-private-double',
        generator_identity=copy.deepcopy(case['prepared']['generator_identity']),
        capabilities=[
            dict(item, id=name, version=version, supported=True)
            for name, version in (
                ('resolved_configuration', '3'),
                ('unit_declarations', '1'),
                ('quantity_definitions', '1'),
            )
        ]
        + [copy.deepcopy(CRITERIA_FREE_CAPABILITY)],
    )
    return caps


class ModelingDouble:
    def __init__(self, case):
        self.case = case
        self.calls = []
        self.sent = []
        self.offline = False
        self.hook = lambda: None
        self.factor = 1
        self.destination_units = None

    def call(self, actor, sid, method, path, body=None, **kwargs):
        if self.offline:
            raise AssertionError('Retained read or replay contacted modeling')
        self.calls.append((actor, sid, method, path, copy.deepcopy(body), kwargs))
        model = copy.deepcopy(self.case['frozen']['model_snapshot'])
        if method == 'GET' and path == '/capabilities':
            result = capabilities(self.case)
        elif method == 'GET' and path.endswith('/revisions/' + model['model_revision_id']):
            result = model
        else:
            assert method == 'POST' and path.endswith('/configuration-compatibility'), path
            validate(kwargs['request_schema'], body)
            candidate = copy.deepcopy(body['configuration_candidate'])
            self.sent.append(candidate)
            self.hook()
            units = port_units(model)
            definitions = {i['instance_id']: i['definition_version_id'] for i in model['instances']}

            def destination(target):
                if self.destination_units is not None:
                    return self.destination_units
                return units[
                    (target['instance_id'], definitions[target['instance_id']], target['port_id'])
                ]

            result = dict(
                schema_version='2',
                model_revision_id=model['model_revision_id'],
                model_digest=model['digest'],
                candidate_digest=digest(candidate),
                compatible=True,
                diagnostics=[],
                required_capabilities=model['required_capabilities'],
                validator_identity='criteria-free-private-double',
                input_interpretations=[
                    dict(
                        target=i['target'],
                        conversion=dict(
                            policy='openmdao-linear-catalog-1',
                            catalog_digest=UNIT_CATALOG_DIGEST,
                            source_units=i['units'],
                            destination_units=destination(i['target']),
                            factor=self.factor,
                            destination_value=i['value'] * self.factor,
                        ),
                    )
                    for i in candidate['inputs']
                ],
            )
        validate(kwargs['response_schema'], dict(schema_version='1', request_id=uid(), data=result))
        return 200, dict(data=result)


def linked_request(case, sid, study_revision, rid, results, name):
    """A version-6 request whose first input is bound to the first output of run ``rid``."""
    config = case['frozen']['configuration']
    request = request6(case, sid, study_revision, name=name)
    request['inputs'][0] = dict(
        kind='run_result',
        target=copy.deepcopy(config['inputs'][0]['target']),
        source_run_id=rid,
        source_output=copy.deepcopy(results['outputs'][0]['target']),
        expected_results_digest=digest(results),
        provenance=copy.deepcopy(config['inputs'][0]['provenance']),
    )
    return request


def bindings_env(tmp_path, kind='chain'):
    store = Store(tmp_path / 'bindings.sqlite')
    actor = uid()
    study = store.create_study(actor, uid(), 'Source study')
    sid = study['study_id']
    case = bind_case(kind, sid, study_revision=study['revision'])
    insert_case(store, sid, case)

    def source(**kwargs):
        return record_run(store, actor, sid, case, **kwargs)

    rid, results = source()
    request = linked_request(case, sid, study['revision'], rid, results, 'Comparison')
    return dict(
        store=store,
        actor=actor,
        sid=sid,
        case=case,
        rid=rid,
        results=results,
        request=request,
        source=source,
    )


def prepared_for(case, frozen):
    prepared = copy.deepcopy(case['prepared'])
    private = project_scientific_configuration(copy.deepcopy(frozen['configuration']))
    prepared.update(
        configuration_revision_id=frozen['configuration']['configuration_revision_id'],
        configuration_digest=private['digest'],
    )
    prepared['executable_content_digest'] = executable_digest(prepared)
    prepared['prepared_digest'] = digest(
        {k: v for k, v in prepared.items() if k != 'prepared_digest'}
    )
    return prepared


def retain(store, actor, sid, case, frozen, dependencies=None, values=None):
    """Record a finished protocol-3 run of a saved configuration; never touches its sources."""
    config = frozen['configuration']
    run = Submissions(store, None, None).submit(
        actor,
        sid,
        dict(command_id=uid(), configuration_revision_id=config['configuration_revision_id']),
    )
    rid = run['run_id']
    bundle = assemble_bundle(
        rid,
        prepared_for(case, frozen),
        case['files'],
        copy.deepcopy(frozen),
        runtime_fixture(),
        dependencies or dict(schema_version='1', sources=[], mappings=[]),
    )
    request = dict(
        run_id=rid,
        scope=sid,
        command_id=run['command_id'],
        payload_digest=store.receipt(actor, sid, 'run', run['command_id'])['payload_digest'],
        bundle_digest=bundle['manifest']['bundle_digest'],
    )
    outputs = outputs_of(case)
    values = list(values) if values is not None else [150 + i for i in range(len(outputs))]
    results = dict(
        schema_version='3',
        run_id=rid,
        bundle_digest=request['bundle_digest'],
        execution=dict(state='finished', exit_code=0, message='completed'),
        outputs=[
            dict(
                target=o['target'],
                value=value,
                units=o['units'],
                availability='available',
                reason=None,
                producer_completed=True,
                assigned=True,
            )
            for o, value in zip(outputs, values)
        ],
        artifacts=[],
    )
    association = dict(store_uuid=uid(), process_uuid=uid())
    payload = dict(
        actor=actor,
        frozen=copy.deepcopy(frozen),
        request=request,
        bundle=dict(
            manifest=bundle['manifest'],
            files={p: base64.b64encode(raw).decode() for p, raw in bundle['files'].items()},
        ),
    )
    retained = dict(
        request=request, bundle=bundle, results=results, assessment=None, artifacts={}, errors=[]
    )
    payload['history'] = projection(payload, retained | association, association)
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


def reuse_api(tmp_path, origin=ORIGIN):
    # The public API environment is imported only by the groups that serve it.
    from fastapi.testclient import TestClient
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth

    store = Store(tmp_path / 'reuse.sqlite')
    auth = Auth(store, origin)
    actor = auth.provision('owner', PASSWORD)
    study = store.create_study(actor, uid(), 'Fresh source study')
    sid = study['study_id']
    # The source configuration keeps the study's own context, so its seed starts unchanged.
    study = seed_legacy_context(store,
        actor, sid, uid(), study['revision'], dict(description='Retained context')
    )
    case = bind_case('chain', sid, study_revision=study['revision'])
    insert_case(store, sid, case)
    rid, results = record_run(store, actor, sid, case)
    with store.connection() as db:
        manifest = json.loads(
            db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
        )['bundle']['manifest']
    model = ModelingDouble(case)
    client = TestClient(create_app(store, auth, model), base_url=origin)
    session = client.post(
        '/api/1/session', json=dict(username='owner', password=PASSWORD), headers={'Origin': origin}
    )
    assert session.status_code == 200, session.text
    client.headers.update({'Origin': origin, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    candidate = linked_request(case, sid, study['revision'], rid, results, 'Linked comparison')
    return dict(
        client=client,
        store=store,
        auth=auth,
        actor=actor,
        sid=sid,
        rid=rid,
        results=results,
        case=case,
        model=model,
        candidate=candidate,
        bundle=dict(manifest=manifest),
    )
