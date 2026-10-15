"""Read-only exploration inputs from an exact answer and its frozen configuration.

This projection never chooses a current model, executes source, converts units or
infers ranges/co-variation from equal names. Numerical operations are separate.
"""

from jsonschema import Draft202012Validator, FormatChecker

from .answers import Answers
from .contracts import DomainError, definitions, digest
from .execution_bundle import validate_frozen_configuration
from .history import History
from .units import port_units


def _object(properties):
    return dict(
        type='object', properties=properties, required=list(properties), additionalProperties=False
    )


def _ref(name):
    return {'$ref': '#/$defs/' + name}


_ID = dict(type='string', format='uuid', pattern='^[0-9a-f-]{36}$')
_HASH = dict(type='string', pattern='^[0-9a-f]{64}$')
_TEXT = dict(type='string', maxLength=4096)
_PORT = dict(
    target=_ref('PortRef'),
    definition_version_id=_ID,
    name=_TEXT,
    instance_name=_TEXT,
    units=_TEXT,
)
DEFINITIONS = {
    'ExplorationInput1': _object(
        dict(
            **_PORT,
            binding=dict(
                oneOf=[
                    _object(
                        dict(
                            kind=dict(const='free'),
                            assignment=dict(anyOf=[_ref('Input'), _ref('ResolvedInput2')]),
                        )
                    ),
                    _object(dict(kind=dict(const='connected'), source=_ref('PortRef'))),
                ]
            ),
        )
    ),
    'ExplorationOutput1': _object(_PORT),
    'ExplorationBasis1': _object(
        dict(
            schema_version=dict(const='1'),
            study_id=_ID,
            answer_version_id=_ID,
            answer_digest=_HASH,
            configuration_revision_id=_ID,
            configuration_digest=_HASH,
            model_id=_ID,
            model_revision_id=_ID,
            model_digest=_HASH,
            source_sha256s=dict(type='array', items=_HASH, uniqueItems=True, maxItems=1000),
            inputs=dict(type='array', items=_ref('ExplorationInput1'), maxItems=1000),
            outputs=dict(type='array', items=_ref('ExplorationOutput1'), maxItems=1000),
            run_ids=dict(type='array', items=_ID, uniqueItems=True, maxItems=1000),
            digest=_HASH,
        )
    ),
}
_VALIDATOR = Draft202012Validator(
    {'$defs': definitions() | DEFINITIONS, **DEFINITIONS['ExplorationBasis1']},
    format_checker=FormatChecker(),
)


def _key(target):
    return target['instance_id'], target['port_id']


def quantities(frozen):
    """Project active occurrences only; reject ambiguous or incomplete assignments."""
    validate_frozen_configuration(frozen)
    model, configuration = frozen['model_snapshot'], frozen['configuration']
    units = port_units(model)
    versions = {d['definition_version_id']: d for d in model['definitions']}
    ports = {}
    for instance in model['instances']:
        version = instance['definition_version_id']
        for port in versions[version]['ports']:
            target = dict(instance_id=instance['instance_id'], port_id=port['port_id'])
            key = _key(target)
            if key in ports:
                raise ValueError('Duplicate port occurrence')
            ports[key] = (
                port['direction'],
                dict(
                    target=target,
                    definition_version_id=version,
                    name=port['name'],
                    instance_name=instance['name'],
                    units=units[(key[0], version, key[1])],
                ),
            )
    connected = {}
    for connection in model['connections']:
        target, source = _key(connection['target_ref']), _key(connection['source_ref'])
        if (
            target in connected
            or target not in ports
            or source not in ports
            or ports[target][0] != 'input'
            or ports[source][0] != 'output'
        ):
            raise ValueError('Invalid connection occurrence')
        connected[target] = connection['source_ref']
    assignments = {}
    for item in configuration['inputs']:
        key = _key(item['target'])
        if key in assignments:
            raise ValueError('Duplicate input assignment')
        assignments[key] = item
    free = {key for key, (direction, _) in ports.items() if direction == 'input'} - set(connected)
    if free != set(assignments):
        raise ValueError('Exactly one explicit assignment per free input is required')
    inputs, outputs = [], []
    for key, (direction, port) in ports.items():
        if direction == 'input':
            binding = (
                dict(kind='connected', source=connected[key])
                if key in connected
                else dict(kind='free', assignment=assignments[key])
            )
            inputs.append(dict(**port, binding=binding))
        elif direction == 'output':
            outputs.append(port)
    return inputs, outputs


class Explorations:
    def __init__(self, store, configurations):
        self.store, self.configurations = store, configurations
        self.answers = Answers(store)

    def basis(self, actor, sid, answer_version_id, configuration_revision_id):
        answer = self.answers.read(actor, sid, answer_version_id)
        # Synthesis references are exact saved case answers, never today's heads.
        answers = [answer] + [
            self.answers.read(actor, sid, version)
            for version in answer['basis']['case_answer_version_ids']
        ]
        configurations = {
            version for a in answers for version in a['basis']['configuration_revision_ids']
        }
        runs = {run for a in answers for run in a['basis']['run_ids']}
        if len(runs) > 1000:
            raise DomainError('limit_exceeded', 413)
        matched_runs = []
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            for run in sorted(runs):
                row, receipt = History(self.store).run_row(db, actor, sid, run, payload=False)
                if receipt is None or receipt['result'].get('run_id') != run:
                    raise DomainError('corrupt_retained_record', 409)
                configurations.add(row['configuration_revision_id'])
                if row['configuration_revision_id'] == configuration_revision_id:
                    matched_runs.append(run)
        if configuration_revision_id not in configurations:
            raise DomainError('resource_not_found', 404)
        frozen = self.configurations.read(actor, sid, configuration_revision_id)
        try:
            inputs, outputs = quantities(frozen)
            model, configuration = frozen['model_snapshot'], frozen['configuration']
            if (
                configuration['study_id'] != sid
                or configuration['configuration_revision_id'] != configuration_revision_id
            ):
                raise ValueError('Frozen identity mismatch')
            result = dict(
                schema_version='1',
                study_id=sid,
                answer_version_id=answer_version_id,
                answer_digest=answer['digest'],
                configuration_revision_id=configuration_revision_id,
                configuration_digest=configuration['digest'],
                model_id=model['model_id'],
                model_revision_id=model['model_revision_id'],
                model_digest=model['digest'],
                source_sha256s=sorted({s['sha256'] for s in model['source_files']}),
                inputs=inputs,
                outputs=outputs,
                run_ids=matched_runs,
            )
            result['digest'] = digest(result)
            if not _VALIDATOR.is_valid(result):
                raise ValueError('Invalid exploration projection')
        except (ValueError, KeyError, TypeError, DomainError) as exc:
            raise DomainError('corrupt_retained_record', 409) from exc
        # Recheck current authorization after the complete retained read.
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
        return result
