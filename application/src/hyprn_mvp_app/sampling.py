"""Retained sample manifests over the existing configuration and run owners.

The dispatcher advances one manifest step; scalar receipts remain the only
launch authority. Reads never dispatch or hydrate native records.
"""

from copy import deepcopy
import json
import math
import time
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import DomainError, definitions, digest
from .exploration import (
    DEFINITIONS as EXPLORATION,
    Explorations,
    _object,
    _ref,
    _ID,
    _HASH,
    _TEXT,
    _NUMBER,
    _key,
)
from .history import History
from .readiness import OBSERVATION_LIFETIME
from .exploration_design import (
    DEFINITIONS as DESIGN_DEFINITIONS,
    DIMENSION,
    Designs,
    independent_dimensions,
    grid_size,
    mapped_values,
    receipt_page,
    on_step,
    invalid,
)


def array(item, maximum=128, minimum=0):
    return dict(type='array', items=item, minItems=minimum, maxItems=maximum)


def nullable(schema):
    return dict(anyOf=[schema, dict(type='null')])


COUNT = dict(type='integer', minimum=0, maximum=128)
VALUE = _object(dict(target=_ref('PortRef'), value=_NUMBER, units=_TEXT))
# A cancelled operation can still own an unresolved original process. Its slot
# remains occupied until lookup establishes a terminal outcome.
ACTIVE = (
    "(state IN ('pending_remote','dispatching','uncertain') OR EXISTS "
    "(SELECT 1 FROM json_each(receipts.result,'$.points') "
    "WHERE json_extract(value,'$.state') IN ('submitted','uncertain')))"
)
DEFINITIONS = {
    'ExplorationSelectedPoint1': _object(
        dict(command_id=_ID, run_id=_ID, combination=dict(type='integer', minimum=0, maximum=7))
    ),
    'ExplorationSampleRequest1': _object(
        dict(
            schema_version=dict(const='1'),
            command_id=_ID,
            previous_operation_id=nullable(_ID),
            seed=dict(type='integer', minimum=0, maximum=2**32 - 1),
            category_dimensions=array(
                _object(
                    dict(
                        name=dict(type='string', minLength=1, maxLength=100),
                        values=array(dict(type='string', minLength=1, maxLength=100), 32, 1),
                    )
                ),
                8,
            ),
            combinations=array(
                _object(
                    dict(
                        categories=array(dict(type='string', minLength=1, maxLength=100), 8),
                        answer_version_id=_ID,
                        configuration_revision_id=_ID,
                        dimensions=array(
                            _object(
                                dict(
                                    target=_ref('PortRef'),
                                    lower=_NUMBER,
                                    upper=_NUMBER,
                                    units=_TEXT,
                                )
                            ),
                            32,
                            1,
                        ),
                        training_count=dict(type='integer', minimum=3, maximum=64),
                        check_count=dict(type='integer', minimum=2, maximum=64),
                        tolerances=EXPLORATION['ExplorationRequest1']['properties']['tolerances'],
                    )
                ),
                8,
                1,
            ),
            budget=_object(
                dict(
                    additional_evaluations=COUNT,
                    wall_seconds=dict(type='integer', minimum=1, maximum=86400),
                    point_wall_seconds=dict(type='integer', minimum=1, maximum=3600),
                    concurrency=dict(const=1, type='integer'),
                )
            ),
            rationale=dict(type='string', minLength=1, maxLength=4096),
        )
    ),
    'ExplorationSampleControl1': _object(
        dict(command_id=_ID, action=dict(enum=['cancel', 'reconcile', 'resume']))
    ),
    'ExplorationSamplePoint1': _object(
        dict(
            identity=_HASH,
            combination=dict(type='integer', minimum=0, maximum=7),
            partition=dict(enum=['training', 'check']),
            inputs=array(VALUE, 1000),
            state=dict(
                enum=['pending', 'submitted', 'uncertain', 'recorded', 'failed', 'cancelled']
            ),
            run_id=nullable(_ID),
            configuration_revision_id=nullable(_ID),
            reused=dict(type='boolean'),
            reason=nullable(_TEXT),
            results_digest=nullable(_HASH),
        )
    ),
    'ExplorationSamplePreview1': _object(
        dict(
            retained_count=COUNT,
            new_count=COUNT,
            total_count=COUNT,
            maximum_execution_seconds=dict(type='integer', minimum=0, maximum=460800),
            allocation=array(
                _object(
                    dict(
                        combination=dict(type='integer', minimum=0, maximum=7),
                        retained_count=COUNT,
                        new_count=COUNT,
                        training_count=COUNT,
                        check_count=COUNT,
                    )
                ),
                8,
            ),
        )
    ),
    'ExplorationSampleOperation1': _object(
        dict(
            schema_version=dict(const='1'),
            operation_id=_ID,
            request=_ref('ExplorationSampleRequest1'),
            state=dict(
                enum=[
                    'pending',
                    'designing',
                    'sampling',
                    'uncertain',
                    'complete',
                    'cancelled',
                    'limited',
                    'failed',
                ]
            ),
            reason=nullable(_TEXT),
            runtime=_ref('ExplorationRuntime1'),
            design_digest=nullable(_HASH),
            design_artifact=nullable(
                _object(
                    dict(
                        process_uuid=_ID,
                        store_uuid=_ID,
                        artifact_uuid=_ID,
                        request_sha256=_HASH,
                        result_sha256=_HASH,
                    )
                )
            ),
            points=array(_ref('ExplorationSamplePoint1')),
            allocation=_ref('ExplorationSamplePreview1'),
            attempted_count=COUNT,
            completed_count=COUNT,
            failed_count=COUNT,
            started_at=_NUMBER,
            elapsed_seconds=dict(type='number', minimum=0, maximum=2**53 - 1),
            cancel_requested=dict(type='boolean'),
        )
    ),
}

# Existing records remain unchanged; explicit steps and co-variation use a new shape.
DEFINITIONS['ExplorationSampleRequest2'] = deepcopy(DEFINITIONS['ExplorationSampleRequest1'])
_request2 = DEFINITIONS['ExplorationSampleRequest2']['properties']
_request2['schema_version'] = dict(const='2')
_combo2 = _request2['combinations']['items']
_combo2['properties'].update(
    model_id=_ID,
    model_revision_id=_ID,
    initial_axis=_ref('PortRef'),
    dimensions=array(DIMENSION, 32, 1),
)
_combo2['required'] = list(_combo2['properties'])
DEFINITIONS['ExplorationSampleOperation2'] = deepcopy(DEFINITIONS['ExplorationSampleOperation1'])
DEFINITIONS['ExplorationSampleOperation2']['properties'].update(
    schema_version=dict(const='2'),
    request=_ref('ExplorationSampleRequest2'),
)


def validate(name, value):
    validator = Draft202012Validator(
        {
            '$defs': definitions() | EXPLORATION | DESIGN_DEFINITIONS | DEFINITIONS,
            **DEFINITIONS[name],
        },
        format_checker=FormatChecker(),
    )
    if not validator.is_valid(value):
        raise DomainError('invalid_request', 400)


def point_identity(basis, frozen, runtime, categories, inputs):
    """Operational targets/density/budget never change original-result identity."""
    return digest(
        dict(
            model_digest=basis['model_digest'],
            sources=basis['source_sha256s'],
            numerical=frozen['configuration']['numerical'],
            runtime=runtime,
            categories=categories,
            inputs=sorted(inputs, key=lambda p: _key(p['target'])),
        )
    )


class Samples:
    def __init__(self, store, configurations, submissions):
        self.store, self.configurations, self.submissions = store, configurations, submissions
        self.explorations = Explorations(store, configurations)
        self.fault = lambda point: None

    def status(self, actor, sid, operation):
        result = self.store.receipt(actor, sid, 'exploration_sample', operation)['result']
        validate('ExplorationSampleOperation' + result['schema_version'], result)
        return result

    def page(self, actor, sid, answer, cursor=None):
        return receipt_page(self.store, actor, sid, 'exploration_sample', answer, cursor)

    def adopt(self, actor, sid, operation, body):
        """Explicitly enrich a retained partition with a separately calculated point.

        It never reassigns an independent check or launches another computation.
        Original runtime/model/units must match; build versions remain immutable.
        """
        validate('ExplorationSelectedPoint1', body)
        if type(body['combination']) is not int:
            raise DomainError('invalid_request', 400)
        previous = self.status(actor, sid, operation)
        if previous['state'] not in ('complete', 'limited', 'cancelled'):
            raise DomainError('reference_conflict', 409)
        index = body['combination']
        if index >= len(previous['request']['combinations']):
            raise DomainError('invalid_request', 400)
        combo = previous['request']['combinations'][index]
        retained = History(self.store).retained(actor, sid, body['run_id'])
        h, manifest = retained.history, retained.payload['bundle']['manifest']
        basis = self.explorations.basis(
            actor, sid, combo['answer_version_id'], combo['configuration_revision_id']
        )
        frozen = self.configurations.read(actor, sid, combo['configuration_revision_id'])
        if (
            manifest['runtime'] != previous['runtime']
            or h['model_snapshot']['digest'] != basis['model_digest']
            or h['configuration']['numerical'] != frozen['configuration']['numerical']
        ):
            raise DomainError('reference_conflict', 409)
        inputs = [
            dict(target=v['target'], value=v['value'], units=v['units'])
            for v in h['configuration']['inputs']
        ]
        values = {_key(v['target']): v for v in inputs}
        free = {_key(p['target']): p for p in basis['inputs'] if p['binding']['kind'] == 'free'}
        if set(values) != set(free) or any(
            values[k]['units'] != p['binding']['assignment']['units'] for k, p in free.items()
        ):
            raise DomainError('invalid_request', 400)
        for d in combo['dimensions']:
            v = values[_key(d['target'])]['value']
            if not d['lower'] <= v <= d['upper'] or (
                previous['schema_version'] == '2' and not on_step(v, d)
            ):
                raise DomainError('invalid_request', 400)
        declared = {_key(d['target']) for d in combo['dimensions']}
        if any(
            values[k]['value'] != p['binding']['assignment']['value']
            for k, p in free.items()
            if k not in declared
        ):
            raise DomainError('reference_conflict', 409)
        if previous['schema_version'] == '2':
            for axis in independent_dimensions(combo['dimensions']):
                if axis['covary_group'] and any(
                    values[_key(d['target'])]['value'] != values[_key(axis['target'])]['value']
                    for d in combo['dimensions']
                    if d['covary_group'] == axis['covary_group']
                ):
                    raise DomainError('invalid_request', 400)
        identity = point_identity(basis, frozen, previous['runtime'], combo['categories'], inputs)
        if any(p['identity'] == identity for p in previous['points']):
            return previous
        result = deepcopy(previous)
        if len(result['points']) >= 128 or combo['training_count'] >= 64:
            raise DomainError('limit_exceeded', 429)
        result.update(
            operation_id=body['command_id'],
            state=previous['state'],
            reason=previous['reason'],
            attempted_count=0,
            elapsed_seconds=0,
            started_at=time.time(),
            cancel_requested=False,
        )
        result['request'].update(command_id=body['command_id'], previous_operation_id=operation)
        result['request']['combinations'][index]['training_count'] += 1
        result['request']['budget']['additional_evaluations'] = 0
        result['points'].append(
            dict(
                identity=identity,
                combination=index,
                partition='training',
                inputs=inputs,
                state='recorded',
                run_id=body['run_id'],
                configuration_revision_id=h['configuration']['configuration_revision_id'],
                reused=True,
                reason=None,
                results_digest=digest(h['results']),
            )
        )
        result['completed_count'] += 1
        result['allocation'].update(
            retained_count=len(result['points']),
            new_count=0,
            total_count=len(result['points']),
            maximum_execution_seconds=0,
        )
        for allocation in result['allocation']['allocation']:
            count = sum(p['combination'] == allocation['combination'] for p in result['points'])
            allocation.update(retained_count=count, new_count=0)
            if allocation['combination'] == index:
                allocation['training_count'] += 1
        result['design_digest'] = digest(
            dict(previous=previous['design_digest'], added_identity=identity, run_id=body['run_id'])
        )
        validate('ExplorationSampleOperation' + result['schema_version'], result)

        def accept(db):
            History(self.store).recheck(db, actor, sid, [retained.token])
            return result

        return self.store.command(
            actor,
            sid,
            'exploration_sample',
            body['command_id'],
            dict(operation=operation, **body),
            accept,
        )

    def resolve(self, actor, sid, request):
        validate(
            'ExplorationSampleRequest2'
            if request.get('schema_version') == '2'
            else 'ExplorationSampleRequest1',
            request,
        )
        if request['schema_version'] == '2':
            answers = {c['answer_version_id'] for c in request['combinations']}
            if len(answers) != 1:
                raise DomainError('invalid_request', 400)
            Designs(self.store, self.configurations).resolve(
                actor,
                sid,
                dict(
                    schema_version='1',
                    command_id=request['command_id'],
                    answer_version_id=next(iter(answers)),
                    category_dimensions=request['category_dimensions'],
                    rationale=request['rationale'],
                    combinations=[
                        {
                            k: c[k]
                            for k in (
                                'categories',
                                'configuration_revision_id',
                                'model_id',
                                'model_revision_id',
                                'initial_axis',
                                'dimensions',
                            )
                        }
                        for c in request['combinations']
                    ],
                ),
            )
            for combo in request['combinations']:
                if any(d['lower'] is None for d in combo['dimensions']):
                    raise DomainError(
                        'invalid_request',
                        400,
                        fields=[
                            dict(
                                path='/combinations',
                                code='missing_range',
                                message='Declare every input range before sampling.',
                                element_ref=None,
                            )
                        ],
                    )
                axes = independent_dimensions(combo['dimensions'])
                if all(d['step'] is not None for d in axes):
                    size = math.prod(grid_size(d) for d in axes)
                    if size < combo['training_count'] + combo['check_count']:
                        invalid(
                            '/combinations/dimensions/step',
                            'insufficient_distinct_points',
                            'Widen the declared grid or reduce training and check counts; '
                            'each needs a distinct vector.',
                        )
        integers = [
            request['seed'],
            *request['budget'].values(),
            *[c[k] for c in request['combinations'] for k in ('training_count', 'check_count')],
        ]
        if any(type(value) is not int for value in integers):
            raise DomainError('invalid_request', 400)
        if not request['rationale'].strip():
            raise DomainError('invalid_request', 400)
        dimensions = request['category_dimensions']
        if len({d['name'] for d in dimensions}) != len(dimensions) or any(
            len(set(d['values'])) != len(d['values']) for d in dimensions
        ):
            raise DomainError('invalid_request', 400)
        tuples = [tuple(c['categories']) for c in request['combinations']]
        if len(set(tuples)) != len(tuples) or any(
            len(t) != len(dimensions)
            or any(v not in dimensions[i]['values'] for i, v in enumerate(t))
            for t in tuples
        ):
            raise DomainError('invalid_request', 400)
        observation = self.store.execution_observation()
        if (
            not observation
            or observation['status'] != 'ready'
            or time.time() - observation['observed_at'] > OBSERVATION_LIFETIME
            or not observation.get('runtime')
        ):
            raise DomainError('backend_unavailable', 503)
        runtime = observation['runtime']
        previous = None
        if request['previous_operation_id']:
            previous = self.status(actor, sid, request['previous_operation_id'])
            if previous['state'] not in ('complete', 'cancelled', 'limited', 'failed'):
                raise DomainError('reference_conflict', 409)
        bases, frozen, retained, allocation = [], [], [], []
        for index, combination in enumerate(request['combinations']):
            basis = self.explorations.basis(
                actor,
                sid,
                combination['answer_version_id'],
                combination['configuration_revision_id'],
            )
            config = self.configurations.read(actor, sid, combination['configuration_revision_id'])
            free = {_key(p['target']): p for p in basis['inputs'] if p['binding']['kind'] == 'free'}
            axes = combination['dimensions']
            if len({_key(d['target']) for d in axes}) != len(axes) or any(
                _key(d['target']) not in free
                or d['lower'] >= d['upper']
                or d['units'] != free[_key(d['target'])]['binding']['assignment']['units']
                for d in axes
            ):
                raise DomainError('invalid_request', 400)
            targets = [_key(t['target']) for t in combination['tolerances']]
            if len(set(targets)) != len(targets) or not set(targets) <= {
                _key(p['target']) for p in basis['outputs']
            }:
                raise DomainError('invalid_request', 400)
            bases.append(basis)
            frozen.append(config)
            rows = []
            if (
                previous
                and previous['runtime'] == runtime
                and [d['name'] for d in previous['request']['category_dimensions']]
                == [d['name'] for d in dimensions]
            ):
                for old in previous['points']:
                    old_combo = previous['request']['combinations'][old['combination']]
                    if old_combo['categories'] != combination['categories']:
                        continue
                    values = {_key(p['target']): p for p in old['inputs']}
                    axis_keys = {_key(d['target']) for d in axes}
                    if set(values) != set(free) or any(
                        values[k]['units'] != p['binding']['assignment']['units']
                        or (
                            k not in axis_keys
                            and values[k]['value'] != p['binding']['assignment']['value']
                        )
                        for k, p in free.items()
                    ):
                        continue
                    if request['schema_version'] == '2':
                        if any(not on_step(values[_key(d['target'])]['value'], d) for d in axes):
                            continue
                        groups = {}
                        compatible = True
                        for d in axes:
                            group = d['covary_group']
                            if group is None:
                                continue
                            value = values[_key(d['target'])]['value']
                            if group in groups and groups[group] != value:
                                compatible = False
                            groups[group] = value
                        if not compatible:
                            continue
                    if old['identity'] != point_identity(
                        basis, config, runtime, combination['categories'], old['inputs']
                    ):
                        continue
                    if old['state'] == 'recorded':
                        history = History(self.store).retained(actor, sid, old['run_id'])
                        if digest(history.history['results']) != old['results_digest']:
                            raise DomainError('corrupt_retained_record', 409)
                    # Failed and unresolved points are retained, never retried or
                    # relabelled as independent successful evidence.
                    rows.append(
                        dict(deepcopy(old), combination=index, reused=old['run_id'] is not None)
                    )
            if len({p['identity'] for p in rows}) != len(rows):
                raise DomainError('corrupt_retained_record', 409)
            retained.extend(rows)
            training = max(
                combination['training_count'], sum(p['partition'] == 'training' for p in rows)
            )
            checks = max(combination['check_count'], sum(p['partition'] == 'check' for p in rows))
            new = training + checks - len(rows) + sum(p['run_id'] is None for p in rows)
            allocation.append(
                dict(
                    combination=index,
                    retained_count=len(rows),
                    new_count=new,
                    training_count=training,
                    check_count=checks,
                )
            )
        total = sum(a['training_count'] + a['check_count'] for a in allocation)
        new = sum(a['new_count'] for a in allocation)
        budget = request['budget']
        seconds = new * budget['point_wall_seconds']
        if (
            total > 128
            or new > budget['additional_evaluations']
            or seconds > budget['wall_seconds']
        ):
            raise DomainError(
                'limit_exceeded',
                422,
                fields=[
                    dict(
                        path='/budget',
                        code='underfunded_design',
                        message=(
                            'Increase the additional evaluation/time budget '
                            'or reduce category and partition counts.'
                        ),
                        element_ref=None,
                    )
                ],
            )
        preview = dict(
            retained_count=len(retained),
            new_count=new,
            total_count=total,
            maximum_execution_seconds=seconds,
            allocation=allocation,
        )
        return dict(bases=bases, frozen=frozen, retained=retained, runtime=runtime, preview=preview)

    def preview(self, actor, sid, request):
        return self.resolve(actor, sid, request)['preview']

    def submit(self, actor, sid, request):
        validate(
            'ExplorationSampleRequest2'
            if request.get('schema_version') == '2'
            else 'ExplorationSampleRequest1',
            request,
        )
        previous = self.store.replay(
            actor, sid, 'exploration_sample', request['command_id'], request
        )
        if previous:
            return self.status(actor, sid, request['command_id'])
        resolved = self.resolve(actor, sid, request)
        result = dict(
            schema_version=request['schema_version'],
            operation_id=request['command_id'],
            request=request,
            state='pending',
            reason=None,
            runtime=resolved['runtime'],
            design_digest=None,
            design_artifact=None,
            points=resolved['retained'],
            allocation=resolved['preview'],
            attempted_count=0,
            completed_count=0,
            failed_count=0,
            started_at=time.time(),
            elapsed_seconds=0,
            cancel_requested=False,
        )

        def accept(db):
            if (
                db.execute(
                    "SELECT COUNT(*) FROM receipts WHERE scope=? AND category='exploration_sample' "
                    'AND ' + ACTIVE,
                    (sid,),
                ).fetchone()[0]
                >= 1
            ):
                raise DomainError('limit_exceeded', 429)
            return result

        return self.store.command(
            actor,
            sid,
            'exploration_sample',
            request['command_id'],
            request,
            accept,
            receipt_state='pending_remote',
            request=resolved,
        )

    def control(self, actor, sid, operation, body):
        validate('ExplorationSampleControl1', body)

        def apply(db):
            row = self.store.command_receipt(db, sid, 'exploration_sample', operation)
            if row is None:
                raise DomainError('resource_not_found', 404)
            result = row['result']
            # Recover the acceptance-to-manifest crash window before cancelling.
            # Otherwise a cancelled extension could lose an accepted original and
            # allocate a new command for that same point.
            for point in result['points']:
                if point['run_id'] is not None:
                    continue
                command = str(uuid5(UUID(operation), point['identity']))
                accepted = self.store.command_receipt(db, sid, 'run', command)
                if accepted is not None:
                    revision = str(uuid5(UUID(command), 'version'))
                    expected = dict(
                        operation='submit_run',
                        target=sid,
                        configuration_revision_id=revision,
                        expected_runtime=result['runtime'],
                        execution_budget=dict(
                            wall_seconds=result['request']['budget']['point_wall_seconds']
                        ),
                    )
                    if (
                        accepted['payload_digest']
                        != digest(dict(major='1', scope=sid, category='run', payload=expected))
                        or not accepted['result']
                    ):
                        raise DomainError('command_payload_conflict', 409)
                    point.update(
                        run_id=accepted['result']['run_id'],
                        configuration_revision_id=revision,
                        state='submitted',
                    )
                    result['attempted_count'] += 1
            if body['action'] == 'cancel':
                result['cancel_requested'] = True
                if result['state'] in ('pending', 'limited', 'failed', 'uncertain'):
                    result['state'] = 'cancelled'
            elif body['action'] == 'resume':
                if result['state'] not in ('cancelled', 'limited'):
                    raise DomainError('reference_conflict', 409)
                if not result['design_digest'] and result['reason'] is not None:
                    raise DomainError('reference_conflict', 409)
                if db.execute(
                    "SELECT 1 FROM receipts WHERE scope=? AND category='exploration_sample' "
                    'AND command_id!=? AND ' + ACTIVE,
                    (sid, operation),
                ).fetchone():
                    raise DomainError('limit_exceeded', 429)
                # Resume has the same wall deadline and additional-evaluation cap.
                result['cancel_requested'] = False
                result['state'] = 'sampling' if result['design_digest'] else 'pending'
            elif result['state'] in ('uncertain', 'cancelled') and result['design_digest']:
                result['state'] = 'sampling'
            self._save(db, sid, result)
            return result

        return self.store.command(
            actor,
            sid,
            'exploration_sample_control',
            body['command_id'],
            dict(operation_id=operation, **body),
            apply,
        )

    def _save(self, db, sid, result):
        result['completed_count'] = sum(p['state'] == 'recorded' for p in result['points'])
        result['failed_count'] = sum(p['state'] == 'failed' for p in result['points'])
        result['elapsed_seconds'] = max(0, time.time() - result['started_at'])
        validate('ExplorationSampleOperation' + result['schema_version'], result)
        state = (
            'committed'
            if result['state'] in ('complete', 'cancelled', 'limited', 'failed')
            else 'uncertain'
            if result['state'] == 'uncertain'
            else 'pending_remote'
        )
        db.execute(
            'UPDATE receipts SET state=?,result=? WHERE scope=? '
            "AND category='exploration_sample' AND command_id=?",
            (state, json.dumps(result), sid, result['operation_id']),
        )

    def process_one(self, native):
        # A separate short OS lock serializes manifest advancement, never the
        # scalar launcher lock or a database transaction across native execution.
        import fcntl
        import os

        fd = os.open(
            self.store.path.with_suffix('.samples.lock'),
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return self._advance(native)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _advance(self, native):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM receipts WHERE category='exploration_sample' "
                "AND state IN ('pending_remote','dispatching') ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return False
            sid, actor = row['scope'], row['actor_id']
            receipt = self.store.command_receipt(db, sid, 'exploration_sample', row['command_id'])
            result, resolved = receipt['result'], receipt['request']
        request = result['request']
        try:
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid, write=True)
            if result['state'] == 'designing':
                # Pure design transport may be unknown; no scalar launch occurred.
                result.update(state='uncertain', reason='design_outcome_unknown')
            elif result['state'] == 'pending':
                self._design(native, sid, result, resolved)
            else:
                self._sample(actor, sid, result, resolved)
        except (DomainError, ValueError, OSError, RuntimeError) as error:
            result.update(
                state='uncertain',
                reason=error.code
                if isinstance(error, DomainError)
                else 'operation_outcome_unknown',
            )
        with self.store.connection(write=True) as db:
            # A cancellation received during a native step must survive its return.
            current = self.store.command_receipt(
                db, sid, 'exploration_sample', result['operation_id']
            )['result']
            result['cancel_requested'] |= current['cancel_requested']
            self._save(db, sid, result)
        return True

    def _design(self, native, sid, result, resolved):
        groups = []
        for i, combination in enumerate(result['request']['combinations']):
            axes = (
                independent_dimensions(combination['dimensions'])
                if result['schema_version'] == '2'
                else combination['dimensions']
            )
            rows = []
            for point in result['points']:
                if point['combination'] != i:
                    continue
                values = {_key(p['target']): p['value'] for p in point['inputs']}
                rows.append(
                    dict(
                        partition=point['partition'],
                        vector=[values[_key(d['target'])] for d in axes],
                    )
                )
            groups.append(
                dict(
                    bounds=[[d['lower'], d['upper']] for d in axes],
                    training_count=combination['training_count'],
                    check_count=combination['check_count'],
                    retained=rows,
                )
            )
        numerical = dict(
            schema_version='2',
            operation='extend_design',
            identity=digest(result['request']),
            seed=result['request']['seed'],
            groups=groups,
        )
        result['state'] = 'designing'
        with self.store.connection(write=True) as db:
            self._save(db, sid, result)
        artifact = native.explore(numerical)
        design = artifact['result']
        if (
            artifact['runtime'] != result['runtime']
            or artifact['request_sha256'] != digest(numerical)
            or artifact['result_sha256'] != digest(design)
            or design['identity'] != numerical['identity']
            or len(design['groups']) != len(groups)
        ):
            raise ValueError('Exact retained design artifact required')
        points = []
        old = {p['identity']: p for p in result['points']}
        for i, rows in enumerate(design['groups']):
            combination = result['request']['combinations'][i]
            allocation = result['allocation']['allocation'][i]
            if any(
                sum(r['partition'] == partition for r in rows) != allocation[count]
                for partition, count in [('training', 'training_count'), ('check', 'check_count')]
            ):
                raise ValueError('Independent partition allocation changed')
            free = [p for p in resolved['bases'][i]['inputs'] if p['binding']['kind'] == 'free']
            for row in rows:
                vector = row['vector']
                axes = (
                    independent_dimensions(combination['dimensions'])
                    if result['schema_version'] == '2'
                    else combination['dimensions']
                )
                if len(vector) != len(axes) or row['partition'] not in (
                    'training',
                    'check',
                ):
                    raise ValueError('Malformed design vector')
                varying = (
                    mapped_values(combination['dimensions'], vector)
                    if result['schema_version'] == '2'
                    else {
                        _key(d['target']): v
                        for d, v in zip(combination['dimensions'], vector, strict=True)
                    }
                )
                values = [
                    dict(
                        target=p['target'],
                        units=p['binding']['assignment']['units'],
                        value=varying.get(_key(p['target']), p['binding']['assignment']['value']),
                    )
                    for p in free
                ]
                identity = point_identity(
                    resolved['bases'][i],
                    resolved['frozen'][i],
                    result['runtime'],
                    combination['categories'],
                    values,
                )
                point = old.get(identity)
                if point:
                    if point['partition'] != row['partition']:
                        raise ValueError('Retained partition changed')
                    point = (
                        dict(point, state='pending', reason=None)
                        if point['run_id'] is None
                        else point
                    )
                else:
                    if any(
                        not d['lower'] <= v <= d['upper'] for d, v in zip(axes, vector, strict=True)
                    ):
                        raise ValueError('Generated vector outside design')
                    point = dict(
                        identity=identity,
                        combination=i,
                        partition=row['partition'],
                        inputs=values,
                        state='pending',
                        run_id=None,
                        configuration_revision_id=None,
                        reused=False,
                        reason=None,
                        results_digest=None,
                    )
                points.append(point)
        if (
            len(points) != result['allocation']['total_count']
            or len({p['identity'] for p in points}) != len(points)
            or not set(old) <= {p['identity'] for p in points}
        ):
            if result['schema_version'] == '2':
                result.update(
                    state='failed',
                    reason=(
                        'Stepped design repeats a vector or cannot preserve independent '
                        'partitions. Widen ranges, reduce counts or declare another seed.'
                    ),
                )
                return
            raise ValueError('Design retention or count mismatch')
        result.update(
            points=points,
            design_digest=digest(dict(mapping_version='1', numerical=design, points=points))
            if result['schema_version'] == '2'
            else digest(design),
            design_artifact={
                k: artifact[k]
                for k in (
                    'process_uuid',
                    'store_uuid',
                    'artifact_uuid',
                    'request_sha256',
                    'result_sha256',
                )
            },
            state='sampling',
        )

    def _sample(self, actor, sid, result, resolved):
        request = result['request']
        # Reconcile only the existing scalar receipt; never allocate a replacement.
        for point in result['points']:
            if point['run_id'] is None or point['state'] in ('recorded', 'failed', 'cancelled'):
                continue
            run = self.submissions.read(actor, sid, point['run_id'])
            if run['state'] in ('dispatching', 'uncertain'):
                self.submissions.dispatch(point['run_id'])
                run = self.submissions.read(actor, sid, point['run_id'])
            if run['state'] == 'recorded':
                retained = History(self.store).retained(actor, sid, point['run_id'])
                history = retained.history
                if retained.payload['bundle']['manifest']['runtime'] != result['runtime']:
                    raise ValueError('Original point runtime mismatch')
                outputs = (history['results'] or {}).get('outputs', [])
                point.update(
                    state='recorded' if outputs else 'failed',
                    results_digest=digest(history['results']),
                    reason=None if outputs else 'no_recorded_outputs',
                )
            elif run['state'] == 'preparation_failed':
                point.update(state='failed', reason='preparation_failed')
            elif run['state'] in ('dispatching', 'uncertain'):
                point.update(state='uncertain', reason='scalar_outcome_unknown')
                result.update(state='uncertain', reason='scalar_outcome_unknown')
                return
            else:
                return
        if result['cancel_requested']:
            result.update(state='cancelled', reason='cancelled_before_next_evaluation')
            return
        pending = next((p for p in result['points'] if p['run_id'] is None), None)
        if pending is None:
            result.update(state='complete', reason=None)
            return
        budget = request['budget']
        if (
            result['attempted_count'] >= budget['additional_evaluations']
            or time.time() - result['started_at'] + budget['point_wall_seconds']
            > budget['wall_seconds']
        ):
            result.update(state='limited', reason='evaluation_or_wall_budget_exhausted')
            return
        combination = request['combinations'][pending['combination']]
        command = str(uuid5(UUID(result['operation_id']), pending['identity']))
        revision = self.configurations.exploration_point(
            actor,
            sid,
            command,
            combination['configuration_revision_id'],
            pending['inputs'],
            request['rationale'],
        )['configuration_revision_id']
        # Stable command identity closes a crash after either configuration or
        # run acceptance and before this manifest writes the association.
        run = self.submissions.submit(
            actor,
            sid,
            dict(
                command_id=command,
                configuration_revision_id=revision,
                execution_budget=dict(wall_seconds=budget['point_wall_seconds']),
            ),
            expected_runtime=result['runtime'],
        )
        self.fault('after_run_acceptance')
        pending.update(run_id=run['run_id'], configuration_revision_id=revision, state='submitted')
        result['attempted_count'] += 1
