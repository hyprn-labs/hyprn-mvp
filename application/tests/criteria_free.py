"""Shared test support for configurations without criteria (configuration 6, result protocol 3).

Built on captured producer bytes (``execution_fixtures.criteria_free_fixture``): a Model4
revision with typed units, its configuration 6, and preparation 4 pinning result protocol 3.
Nothing here executes candidate code or calls a modeling service.

- ``bind_case(kind, sid)``: the captured case re-bound to study ``sid`` with fresh
  configuration identities; every digest the bundle checks is recomputed.
- ``insert_case(store, sid, case)``: store its frozen configuration 9 and the model association.
- ``record_run(store, actor, sid, case, values=None)``: submit and record one protocol-3 run
  (results 3, no criteria, no evaluator identity); returns ``(run_id, results)``.
- ``request6(case, sid, study_revision, **changes)``: a ConfigurationRequest6 for the case.
- ``CRITERIA_FREE_CAPABILITY``: the modeling capability entry a configuration 6 needs, to add
  to a test double's capability list beside ``resolved_configuration`` version 3.
"""

import base64
import copy
import json

from execution_fixtures import criteria_free_fixture, runtime_fixture
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.store import digest, uid

CRITERIA_FREE_CAPABILITY = dict(
    id='criteria_free_configuration',
    version='1',
    supported=True,
    limits=dict(json_bytes=2097152, source_bytes=262144, edits=256, elements=1000, depth=32),
)


def _rehash(value):
    value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
    return value


def bind_case(kind='chain', sid=None, *, study_revision=None):
    """The captured case for study ``sid``: fresh configuration identities, the context source
    pinned to ``study_revision`` when given, and the preparation re-bound to the new private
    projection digest."""
    case = criteria_free_fixture(kind)
    frozen = case['frozen']
    config = frozen['configuration']
    config.update(configuration_id=uid(), configuration_revision_id=uid())
    if sid is not None:
        config['study_id'] = sid
    if study_revision is not None:
        config['context_source']['expected_study_revision'] = study_revision
        frozen['study_revision'] = study_revision
    _rehash(config)
    private = project_scientific_configuration(copy.deepcopy(config))
    prepared = case['prepared']
    prepared.update(
        configuration_digest=private['digest'],
        configuration_revision_id=config['configuration_revision_id'],
    )
    prepared['executable_content_digest'] = executable_digest(prepared)
    prepared['prepared_digest'] = digest(
        {k: v for k, v in prepared.items() if k != 'prepared_digest'}
    )
    return case


def insert_case(store, sid, case):
    config = case['frozen']['configuration']
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
        db.execute(
            'INSERT INTO configuration_families VALUES(?,?,?)',
            (config['configuration_id'], sid, config['configuration_revision_id']),
        )
        if not db.execute(
            'SELECT 1 FROM model_associations WHERE study_id=? AND model_id=?',
            (sid, config['model_id']),
        ).fetchone():
            db.execute(
                'INSERT INTO model_associations VALUES(?,?,?)', (sid, config['model_id'], uid())
            )


def outputs_of(case):
    return json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']


def record_run(store, actor, sid, case, values=None, *, failed=False):
    """Submit and record one run of the case's configuration under result protocol 3."""
    config = case['frozen']['configuration']
    run = Submissions(store, None, None).submit(
        actor,
        sid,
        dict(command_id=uid(), configuration_revision_id=config['configuration_revision_id']),
    )
    rid = run['run_id']
    bundle = assemble_bundle(
        rid,
        copy.deepcopy(case['prepared']),
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
    outputs = outputs_of(case)
    values = list(values) if values is not None else [150 + i for i in range(len(outputs))]
    results = dict(
        schema_version='3',
        run_id=rid,
        bundle_digest=request['bundle_digest'],
        execution=dict(
            state='failed' if failed else 'finished',
            exit_code=1 if failed else 0,
            message='incomplete_outputs' if failed else 'completed',
        ),
        outputs=[
            dict(
                target=o['target'],
                value=None if failed else value,
                units=o['units'],
                availability='unavailable' if failed else 'available',
                reason='Producer failed' if failed else None,
                producer_completed=not failed,
                assigned=not failed,
            )
            for o, value in zip(outputs, values)
        ],
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


def request6(case, sid, study_revision, **changes):
    """A ConfigurationRequest6 that supplies the case's literal inputs."""
    config = case['frozen']['configuration']
    request = dict(
        schema_version='6',
        study_id=sid,
        model_id=config['model_id'],
        model_revision_id=config['model_revision_id'],
        name=config['name'],
        inputs=[
            dict(
                kind='literal',
                **{k: copy.deepcopy(i[k]) for k in ('target', 'value', 'units', 'provenance')},
            )
            for i in config['inputs']
        ],
        numerical=copy.deepcopy(config['numerical']),
        context_source=dict(kind='current_study', expected_study_revision=study_revision),
        notes=[],
        derivation=None,
        assumptions=[],
        general_context_evidence_version_ids=[],
    )
    request.update(changes)
    return request
