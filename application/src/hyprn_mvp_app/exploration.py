"""Read-only exploration inputs from an exact answer and its frozen configuration.

This projection never chooses a current model, executes source, converts units or
infers ranges/co-variation from equal names. Numerical operations are separate.
"""

import json

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
_NUMBER = dict(type='number', minimum=-(2**53 - 1), maximum=2**53 - 1)
_POSITIVE = dict(type='number', minimum=0, maximum=2**53 - 1)
_PORT = dict(
    target=_ref('PortRef'),
    definition_version_id=_ID,
    name=_TEXT,
    instance_name=_TEXT,
    units=_TEXT,
)
DEFINITIONS = {
    'ExplorationRuntime1': definitions()['ExecutionBundle2']['properties']['runtime'],
    'ExplorationRequest1': _object(
        dict(
            schema_version=dict(const='1'),
            command_id=_ID,
            selection_token=_ID,
            operation=dict(enum=['design', 'fit_predict']),
            answer_version_id=_ID,
            configuration_revision_id=_ID,
            axis=_ref('PortRef'),
            lower=_NUMBER,
            upper=_NUMBER,
            seed=dict(type='integer', minimum=0, maximum=2**32 - 1),
            training_count=dict(type='integer', minimum=3, maximum=16),
            check_count=dict(type='integer', minimum=2, maximum=16),
            method=dict(enum=['response_surface', 'kriging']),
            training_run_ids=dict(type='array', items=_ID, uniqueItems=True, maxItems=16),
            check_run_ids=dict(type='array', items=_ID, uniqueItems=True, maxItems=16),
            query_values=dict(type='array', items=_NUMBER, minItems=1, maxItems=33),
            tolerances=dict(
                type='array',
                minItems=1,
                maxItems=32,
                items=_object(dict(target=_ref('PortRef'), absolute=_POSITIVE, relative=_POSITIVE)),
            ),
            rationale=dict(type='string', minLength=1, maxLength=4096),
        )
    ),
    'ExplorationOperation1': _object(
        dict(
            schema_version=dict(const='1'),
            request_id=_ID,
            selection_token=_ID,
            state=dict(enum=['pending', 'running', 'complete', 'uncertain']),
            result=dict(anyOf=[_ref('ExplorationPrediction1'), dict(type='null')]),
        )
    ),
    'ExplorationPrediction1': _object(
        dict(
            schema_version=dict(const='1'),
            basis=_ref('ExplorationBasis1'),
            request=_ref('ExplorationRequest1'),
            identity=_HASH,
            query_inputs=dict(
                type='array',
                minItems=1,
                maxItems=33,
                items=dict(
                    type='array',
                    maxItems=1000,
                    items=_object(dict(target=_ref('PortRef'), value=_NUMBER, units=_TEXT)),
                ),
            ),
            samples=dict(
                type='array',
                maxItems=32,
                items=_object(
                    dict(
                        run_id=_ID,
                        configuration_digest=_HASH,
                        bundle_digest=_HASH,
                        results_digest=_HASH,
                        runtime=_ref('ExplorationRuntime1'),
                        inputs=dict(
                            type='array',
                            items=dict(anyOf=[_ref('Input'), _ref('ResolvedInput2')]),
                            maxItems=1000,
                        ),
                    )
                ),
            ),
            numerical=_ref('ExplorationNumerical1'),
        )
    ),
    'ExplorationNumerical1': _object(
        dict(
            runtime=_ref('ExplorationRuntime1'),
            request_sha256=_HASH,
            result_sha256=_HASH,
            elapsed_seconds=_POSITIVE,
            process_uuid=_ID,
            store_uuid=_ID,
            artifact_uuid=_ID,
            result=_object(
                dict(
                    schema_version=dict(const='1'),
                    identity=_HASH,
                    method=dict(enum=['response_surface', 'kriging']),
                    versions=_object(dict(openmdao=_TEXT, scipy=_TEXT, numpy=_TEXT)),
                    training_vectors=dict(
                        type='array',
                        maxItems=16,
                        items=dict(type='array', items=_NUMBER, minItems=1, maxItems=1),
                    ),
                    check_vectors=dict(
                        type='array',
                        maxItems=16,
                        items=dict(type='array', items=_NUMBER, minItems=1, maxItems=1),
                    ),
                    outputs=dict(
                        type='array',
                        maxItems=32,
                        items=_object(
                            dict(
                                state=dict(enum=['estimated', 'unavailable']),
                                reason=dict(anyOf=[_TEXT, dict(type='null')]),
                                values=dict(
                                    type='array',
                                    maxItems=33,
                                    items=dict(anyOf=[_NUMBER, dict(type='null')]),
                                ),
                                assessed_count=dict(type='integer', minimum=0, maximum=16),
                                evaluable_count=dict(type='integer', minimum=0, maximum=16),
                                failed_count=dict(type='integer', minimum=0, maximum=16),
                                max_absolute_error=dict(anyOf=[_POSITIVE, dict(type='null')]),
                                rmse=dict(anyOf=[_POSITIVE, dict(type='null')]),
                                target_met=dict(type='boolean'),
                            )
                        ),
                    ),
                    compute_seconds=_POSITIVE,
                )
            ),
        )
    ),
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

    def submit(self, actor, sid, request):
        validate_public('ExplorationRequest1', request)
        if any(type(request[k]) is not int for k in ('seed', 'training_count', 'check_count')):
            raise DomainError('invalid_request', 400)
        previous = self.store.replay(actor, sid, 'exploration', request['command_id'], request)
        if previous:
            return self.status(actor, sid, request['command_id'])
        basis = self.basis(
            actor, sid, request['answer_version_id'], request['configuration_revision_id']
        )
        baseline = self.configurations.read(actor, sid, request['configuration_revision_id'])
        free = {_key(p['target']): p for p in basis['inputs'] if p['binding']['kind'] == 'free'}
        axis = _key(request['axis'])
        if (
            axis not in free
            or request['lower'] >= request['upper']
            or not request['rationale'].strip()
        ):
            raise DomainError('invalid_request', 400)
        if any(not request['lower'] <= v <= request['upper'] for v in request['query_values']):
            raise DomainError('invalid_request', 400)
        # Conversion is not approximated in application code. This initial slice
        # requires explicit assignments in the exact declared model units.
        if any(p['binding']['assignment']['units'] != p['units'] for p in free.values()):
            raise DomainError('invalid_request', 400)
        targets = [_key(t['target']) for t in request['tolerances']]
        if len(set(targets)) != len(targets) or not set(targets) <= {
            _key(p['target']) for p in basis['outputs']
        }:
            raise DomainError('invalid_request', 400)
        runs = request['training_run_ids'] + request['check_run_ids']
        expected = (
            0
            if request['operation'] == 'design'
            else request['training_count'] + request['check_count']
        )
        if (
            len(runs) != expected
            or len(set(runs)) != len(runs)
            or (
                request['operation'] == 'fit_predict'
                and len(request['training_run_ids']) != request['training_count']
            )
        ):
            raise DomainError('invalid_request', 400)
        history, samples, rows, tokens = History(self.store), [], [], []
        for rid in runs:
            retained = history.retained(actor, sid, rid)
            h, manifest = retained.history, retained.payload['bundle']['manifest']
            config, model = h['configuration'], h['model_snapshot']
            if (
                model['digest'] != basis['model_digest']
                or config['numerical'] != baseline['configuration']['numerical']
            ):
                raise DomainError('invalid_request', 400)
            values = {_key(i['target']): i for i in config['inputs']}
            if set(values) != set(free) or any(
                values[k]['units'] != p['units']
                or (k != axis and values[k]['value'] != p['binding']['assignment']['value'])
                for k, p in free.items()
            ):
                raise DomainError('invalid_request', 400)
            outputs = {_key(o['target']): o for o in (h['results'] or {}).get('outputs', [])}
            rows.append(
                dict(
                    x=[values[axis]['value']],
                    y=[
                        outputs[k]['value']
                        if k in outputs and outputs[k]['availability'] == 'available'
                        else None
                        for k in targets
                    ],
                )
            )
            samples.append(
                dict(
                    run_id=rid,
                    configuration_digest=config['digest'],
                    bundle_digest=manifest['bundle_digest'],
                    results_digest=digest(h['results']),
                    runtime=manifest['runtime'],
                    inputs=config['inputs'],
                )
            )
            tokens.append(retained.token)
        if samples and any(s['runtime'] != samples[0]['runtime'] for s in samples):
            raise DomainError('invalid_request', 400)
        identity = digest(dict(basis=basis, request=request, samples=samples))
        numerical = dict(
            schema_version='1',
            operation=request['operation'],
            identity=identity,
            bounds=[[request['lower'], request['upper']]],
            seed=request['seed'],
            training_count=request['training_count'],
            check_count=request['check_count'],
            training=rows[: request['training_count']],
            checks=rows[request['training_count'] :],
            queries=[[v] for v in request['query_values']],
            tolerances=[[t['absolute'], t['relative']] for t in request['tolerances']],
            method=request['method'],
        )
        prepared = dict(
            schema_version='1',
            basis=basis,
            request=request,
            identity=identity,
            samples=samples,
            query_inputs=[
                [
                    dict(
                        target=p['target'],
                        units=p['units'],
                        value=value if key == axis else p['binding']['assignment']['value'],
                    )
                    for key, p in free.items()
                ]
                for value in request['query_values']
            ],
        )

        def accept(db):
            history.recheck(db, actor, sid, tokens)
            if (
                db.execute(
                    "SELECT COUNT(*) FROM receipts WHERE scope=? AND category='exploration' "
                    "AND state IN ('pending_remote','dispatching')",
                    (sid,),
                ).fetchone()[0]
                >= 10
            ):
                raise DomainError('limit_exceeded', 429)
            return dict(
                schema_version='1',
                request_id=request['command_id'],
                selection_token=request['selection_token'],
                state='pending',
                result=None,
            )

        return self.store.command(
            actor,
            sid,
            'exploration',
            request['command_id'],
            request,
            accept,
            receipt_state='pending_remote',
            request=dict(prepared=prepared, numerical=numerical),
        )

    def status(self, actor, sid, request_id):
        receipt = self.store.receipt(actor, sid, 'exploration', request_id)
        result = receipt['result']
        validate_public('ExplorationOperation1', result)
        return result

    def process_one(self, native):
        """One existing command receipt owns a bounded operation; unknown never retries."""
        with self.store.connection(write=True) as db:
            row = db.execute(
                "SELECT scope,command_id,actor_id FROM receipts WHERE category='exploration' "
                "AND state='pending_remote' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return False
            sid, command, actor = row['scope'], row['command_id'], row['actor_id']
            receipt = self.store.command_receipt(db, sid, 'exploration', command)
            try:
                self.store.authorize(db, actor, sid, write=True)
            except DomainError:
                db.execute(
                    "UPDATE receipts SET state='uncertain',result=? WHERE scope=? "
                    "AND category='exploration' AND command_id=?",
                    (json.dumps(dict(receipt['result'], state='uncertain')), sid, command),
                )
                return True
            result = dict(receipt['result'], state='running')
            db.execute(
                "UPDATE receipts SET state='dispatching',result=? WHERE scope=? "
                "AND category='exploration' AND command_id=?",
                (json.dumps(result), sid, command),
            )
        try:
            payload = receipt['request']
            numerical = native.explore(payload['numerical'])
            prepared = payload['prepared']
            if prepared['samples'] and numerical['runtime'] != prepared['samples'][0]['runtime']:
                raise ValueError('Numerical runtime differs from sampled runtime')
            if numerical['result']['identity'] != prepared['identity']:
                raise ValueError('Prediction identity mismatch')
            if numerical['request_sha256'] != digest(payload['numerical']) or numerical[
                'result_sha256'
            ] != digest(numerical['result']):
                raise ValueError('Numerical artifact digest mismatch')
            outputs = numerical['result']['outputs']
            request = prepared['request']
            expected = 0 if request['operation'] == 'design' else len(request['tolerances'])
            if len(outputs) != expected or numerical['result']['method'] != request['method']:
                raise ValueError('Numerical output inventory mismatch')
            for output in outputs:
                if len(output['values']) != len(request['query_values']):
                    raise ValueError('Numerical vector mismatch')
                if output['state'] == 'estimated':
                    if (
                        not output['target_met']
                        or output['reason'] is not None
                        or output['assessed_count'] != request['check_count']
                        or any(value is None for value in output['values'])
                    ):
                        raise ValueError('Unassessed estimate')
                elif output['reason'] is None or any(
                    value is not None for value in output['values']
                ):
                    raise ValueError('Unavailable estimate must stay null with reason')
            prediction = dict(prepared, numerical=numerical)
            validate_public('ExplorationPrediction1', prediction)
            result = dict(result, state='complete', result=prediction)
            state = 'committed'
        except (ValueError, RuntimeError, OSError, DomainError):
            result = dict(result, state='uncertain')
            state = 'uncertain'
        with self.store.connection(write=True) as db:
            db.execute(
                "UPDATE receipts SET state=?,result=? WHERE scope=? AND category='exploration' "
                "AND command_id=? AND state='dispatching'",
                (state, json.dumps(result), sid, command),
            )
        return True


def validate_public(name, value):
    validator = Draft202012Validator(
        {'$defs': definitions() | DEFINITIONS, **DEFINITIONS[name]}, format_checker=FormatChecker()
    )
    if not validator.is_valid(value):
        raise DomainError('invalid_request', 400)
