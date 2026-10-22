"""Configuration 6 authoring with assumptions and evidence on a captured Model4 case.

The model is the captured protocol-3 case (typed unit declarations, quantity definitions)
with one model-owned assumption citing a real evidence version of the study. The modeling
service is the explicit in-process private transport of ``test_assumption_authoring``; its
configuration compatibility answer is a typed test double, not native numerical proof, and
every call proves no application SQLite write lock spans private I/O.
"""

from copy import deepcopy
import json
import sqlite3

from criteria_free import CRITERIA_FREE_CAPABILITY, bind_case, request6
from test_assumption_authoring import evidence, statement
from test_assumptions_evidence_contracts import sample, D
from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.store import digest, uid
from hyprn_mvp_app.units import UNIT_CATALOG_DIGEST, port_units


def signed(model):
    model['digest'] = digest({k: v for k, v in model.items() if k != 'digest'})
    return model


def criteria_free_capabilities(caps):
    """Advertise everything a configuration 6 on a Model4 version needs, each entry explicit."""
    template = deepcopy(caps['capabilities'][0])
    caps.update(contract_versions=['1.2', '1.3'], schema_versions=['1', '2', '3', '4'])
    for name, version in (
        ('unit_declarations', '1'),
        ('quantity_definitions', '1'),
        ('resolved_configuration', '3'),
    ):
        caps['capabilities'].append(
            dict(deepcopy(template), id=name, version=version, supported=True)
        )
    caps['capabilities'].append(deepcopy(CRITERIA_FREE_CAPABILITY))
    return caps


def compatibility_proof(candidate, model):
    """A compatible private answer for exactly this candidate: identity unit interpretation of
    every input into the bound units of its port."""
    bound = port_units(model)
    definitions = {i['instance_id']: i['definition_version_id'] for i in model['instances']}
    interpretations = [
        dict(
            target=deepcopy(i['target']),
            conversion=dict(
                policy='openmdao-linear-catalog-1',
                catalog_digest=UNIT_CATALOG_DIGEST,
                source_units=i['units'],
                destination_units=bound[
                    (
                        i['target']['instance_id'],
                        definitions[i['target']['instance_id']],
                        i['target']['port_id'],
                    )
                ],
                factor=1,
                destination_value=i['value'],
            ),
        )
        for i in candidate['inputs']
    ]
    proof = sample(D['CompatibilityResult2'])
    proof.update(
        compatible=True,
        diagnostics=[],
        candidate_digest=digest(candidate),
        model_digest=model['digest'],
        model_revision_id=model['model_revision_id'],
        required_capabilities=candidate['required_capabilities'],
        validator_identity='explicit-private-transport',
        input_interpretations=interpretations,
    )
    return proof


def configuration6(env):
    """``(env, Configurations, request6, model, evidence record)`` for a configuration 6 whose
    request assumption and general context cite one evidence version that the model
    assumption also cites. Compatibility bodies are recorded in ``transport.calls``."""
    t = env['transport']
    criteria_free_capabilities(t.caps)
    record = evidence(env)
    eid = record['evidence_version_id']
    case = bind_case('chain', env['sid'], study_revision=env['study']['revision'])
    model = deepcopy(case['frozen']['model_snapshot'])
    model['assumptions'] = [statement(eid)]
    signed(model)
    t.revisions[model['model_revision_id']] = model
    with env['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO model_associations VALUES(?,?,?)', (env['sid'], model['model_id'], uid())
        )
    original = t.__call__

    def transport(method, path, raw, headers):
        if not path.endswith('/configuration-compatibility'):
            return original(method, path, raw, headers)
        with sqlite3.connect(env['store'].path, timeout=0) as db:
            db.execute('BEGIN IMMEDIATE')
            db.rollback()
        body = json.loads(raw)
        t.calls.append((method, path, deepcopy(body)))
        if t.hook:
            t.hook(method, path, body)
        return 200, dict(
            schema_version='1',
            request_id=uid(),
            data=compatibility_proof(body['configuration_candidate'], model),
        )

    env['coord'].model.transport = transport
    request = request6(
        case,
        env['sid'],
        env['study']['revision'],
        assumptions=[{k: v for k, v in statement(eid).items() if k != 'owner'}],
        general_context_evidence_version_ids=[eid],
    )
    env['case'] = case
    return env, Configurations(env['store'], env['coord']), request, model, record
