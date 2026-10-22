"""Shared seeding for calculation tests: one saved configuration of a captured producer model
in an existing study, and runs recorded through the real submission, bundle and projection
code. Nothing is executed and no modeling service is called."""

import base64
import copy
import json

from execution_fixtures import fixture, runtime_fixture
from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
from hyprn_mvp_app.history import projection
from hyprn_mvp_app.store import digest, uid


def insert_configuration(e, frozen):
    config = frozen['configuration']
    with e['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations VALUES(?,?,?,?)',
            (
                config['configuration_revision_id'],
                config['configuration_id'],
                e['sid'],
                json.dumps(frozen),
            ),
        )
        db.execute(
            'INSERT INTO configuration_families VALUES(?,?,?)',
            (config['configuration_id'], e['sid'], config['configuration_revision_id']),
        )


def sibling(e, frozen, **changes):
    """Another saved configuration version of the same study, with its own identity."""
    frozen = copy.deepcopy(frozen)
    config = frozen['configuration']
    config.update(configuration_id=uid(), configuration_revision_id=uid(), **changes)
    if 'model_revision_id' in changes:
        # Another saved model version: the frozen snapshot carries the same pin.
        model = frozen['model_snapshot']
        model['model_revision_id'] = changes['model_revision_id']
        model['digest'] = digest({k: v for k, v in model.items() if k != 'digest'})
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    insert_configuration(e, frozen)
    return config['configuration_revision_id']


def seed(api):
    """Give the study ``api['sid']`` one saved configuration of a captured two-output model,
    with ``record(values)`` to record a run of it and ``submit()`` to leave one unrecorded."""
    case = fixture('chain')
    config = case['frozen']['configuration']
    config['study_id'] = api['sid']
    # Each seeded study holds its own configuration identity.
    config.update(configuration_id=uid(), configuration_revision_id=uid())
    config['context_snapshot'].update(description='', boundary='')
    config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
    case['prepared']['configuration_digest'] = config['digest']
    case['prepared']['configuration_revision_id'] = config['configuration_revision_id']
    case['prepared']['executable_content_digest'] = executable_digest(case['prepared'])
    case['prepared']['prepared_digest'] = digest(
        {k: v for k, v in case['prepared'].items() if k != 'prepared_digest'}
    )
    insert_configuration(api, case['frozen'])
    with api['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO model_associations VALUES(?,?,?)', (api['sid'], config['model_id'], uid())
        )
    service = Submissions(api['store'], None, None)
    outputs = json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']

    def submit():
        return service.submit(
            api['actor'],
            api['sid'],
            dict(command_id=uid(), configuration_revision_id=config['configuration_revision_id']),
        )

    def record(values):
        """Submit and record one run whose outputs take ``values`` in bindings order."""
        run = submit()
        rid, store = run['run_id'], api['store']
        bundle = assemble_bundle(
            rid, copy.deepcopy(case['prepared']), case['files'], case['frozen'], runtime_fixture()
        )
        request = dict(
            run_id=rid,
            scope=api['sid'],
            command_id=run['command_id'],
            payload_digest=store.receipt(api['actor'], api['sid'], 'run', run['command_id'])[
                'payload_digest'
            ],
            bundle_digest=bundle['manifest']['bundle_digest'],
        )
        results = dict(
            schema_version='1',
            run_id=rid,
            bundle_digest=request['bundle_digest'],
            execution=dict(state='finished', exit_code=0, message='Complete'),
            convergence=dict(state='not_applicable', diagnostics_ref=None),
            optimization=dict(termination='not_applicable', feasibility='not_applicable'),
            completeness=dict(
                expected=len(outputs), available=len(outputs), failed=0, unavailable=0
            ),
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
            criteria=[],
            applicability=dict(state='unassessed', evidence_refs=[]),
            artifacts=[],
        )
        association = dict(store_uuid=uid(), process_uuid=uid())
        payload = dict(
            actor=api['actor'],
            frozen=copy.deepcopy(case['frozen']),
            request=request,
            bundle=dict(
                manifest=bundle['manifest'],
                files={p: base64.b64encode(raw).decode() for p, raw in bundle['files'].items()},
            ),
        )
        retained = dict(
            request=request,
            bundle=bundle,
            results=results,
            assessment=None,
            artifacts={},
            errors=[],
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
        return rid

    model = case['frozen']['model_snapshot']
    input_ref = next(
        dict(instance_id=i['instance_id'], port_id=p['port_id'])
        for i in model['instances']
        for d in model['definitions']
        if d['definition_version_id'] == i['definition_version_id']
        for p in d['ports']
        if p['direction'] == 'input'
    )
    return dict(
        frozen=case['frozen'],
        config=config,
        outputs=[o['target'] for o in outputs],
        input_ref=input_ref,
        submit=submit,
        record=record,
    )
