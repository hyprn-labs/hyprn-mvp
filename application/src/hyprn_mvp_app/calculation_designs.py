"""Sampled calculation versions and run requests for a version's members (ADR-0009).

A sampled version is generated, never written by a client. A sampling operation declares
reference configurations, the input ranges around each, a method and a seed. Accepting it is
inert: it checks the declaration against the saved references and records a receipt. The
dispatcher then asks the current attested computation environment for the seeded Latin
hypercube (the same retained design artifact the answer exploration used), freezes each new
point as a configuration version copied from its reference with only the sampled inputs
changed, and saves the calculation version whose members are exactly those points.

Nothing here imports or executes candidate code and no unit is converted: every range is in
its reference input's saved unit. Points of the calculation's latest sampled version that
still fit the declaration are kept with their configuration versions, so adding points never
moves an existing one. Runs attach by reference: requesting runs for members submits ordinary
runs and never creates a version.
"""

from copy import deepcopy
import json
from itertools import product
import math
import time
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from .calculations import (
    DEFINITIONS as CALCULATIONS,
    MAX_MEMBERS,
    MAX_SAMPLED,
    Calculations,
    _frozen_configuration,
    independent_dimensions,
)
from .contracts import diagnostics
from .contracts import DomainError, definitions, digest, issue
from .quantity_projection import _key, quantities
from .sampling_coordinates import grid_size, mapped_values, on_step
from .readiness import OBSERVATION_LIFETIME

CATEGORY = 'calculation_sample'
SAMPLE_PAGE = 20


def _object(properties, optional=()):
    return dict(
        type='object',
        properties=properties,
        required=[name for name in properties if name not in optional],
        additionalProperties=False,
    )


def _ref(name):
    return {'$ref': '#/$defs/' + name}


_ID = CALCULATIONS['CalculationVersion1']['properties']['calculation_id']
_NULL_ID = dict(anyOf=[_ID, dict(type='null')])
_COUNT = dict(type='integer', minimum=0, maximum=MAX_SAMPLED)
DEFINITIONS = {
    'CalculationSampleRequest1': _object(
        dict(
            command_id=_ID,
            calculation_id=dict(
                **_NULL_ID,
                description='The calculation that gets the new version; null creates one.',
            ),
            expected_version_id=dict(
                **_NULL_ID,
                description="The calculation's latest version id; null for a new calculation.",
            ),
            name=CALCULATIONS['CalculationContent1']['properties']['name'],
            description=CALCULATIONS['CalculationContent1']['properties']['description'],
            method=dict(const='latin_hypercube'),
            seed=CALCULATIONS['SampledDesign1']['properties']['seed'],
            groups=dict(type='array', items=_ref('SampledGroup1'), minItems=1, maxItems=8),
            rationale=CALCULATIONS['SampledDesign1']['properties']['rationale'],
        )
    ),
    'CalculationSampleOperation1': _object(
        dict(
            schema_version=dict(const='1'),
            operation_id=_ID,
            request=_ref('CalculationSampleRequest1'),
            state=dict(
                enum=['pending', 'designing', 'configuring', 'complete', 'failed', 'uncertain']
            ),
            reason=dict(anyOf=[dict(type='string', maxLength=4096), dict(type='null')]),
            runtime=CALCULATIONS['SampledDesign1']['properties']['runtime'],
            point_count=_COUNT,
            retained_count=_COUNT,
            calculation_id=_NULL_ID,
            calculation_version_id=_NULL_ID,
        )
    ),
    'CalculationSamplePage1': _object(
        dict(
            items=dict(
                type='array', items=_ref('CalculationSampleOperation1'), maxItems=SAMPLE_PAGE
            )
        )
    ),
    'CalculationRunRequest1': _object(
        dict(
            command_id=_ID,
            configuration_revision_ids=dict(
                type='array', items=_ID, minItems=1, maxItems=MAX_MEMBERS, uniqueItems=True
            ),
        )
    ),
    'CalculationRunRequestResult1': _object(
        dict(
            calculation_version_id=_ID,
            runs=dict(
                type='array',
                maxItems=MAX_MEMBERS,
                items=_object(dict(configuration_revision_id=_ID, run_id=_ID, command_id=_ID)),
            ),
        )
    ),
}

DEFINITIONS['CalculationSampleRequest2'] = deepcopy(DEFINITIONS['CalculationSampleRequest1'])
DEFINITIONS['CalculationSampleRequest2']['properties']['method'] = dict(
    const='boundary_latin_hypercube'
)
DEFINITIONS['CalculationSampleRequestRead2'] = dict(
    oneOf=[
        _ref('CalculationSampleRequest1'),
        _ref('CalculationSampleRequest2'),
    ]
)
DEFINITIONS['CalculationSampleOperation2'] = deepcopy(
    DEFINITIONS['CalculationSampleOperation1']
)
DEFINITIONS['CalculationSampleOperation2']['properties'].update(
    schema_version=dict(const='2'),
    request=_ref('CalculationSampleRequest2'),
)
DEFINITIONS['CalculationSampleOperationRead2'] = dict(
    oneOf=[
        _ref('CalculationSampleOperation1'),
        _ref('CalculationSampleOperation2'),
    ]
)
DEFINITIONS['CalculationSamplePage2'] = deepcopy(DEFINITIONS['CalculationSamplePage1'])
DEFINITIONS['CalculationSamplePage2']['properties']['items']['items'] = _ref(
    'CalculationSampleOperationRead2'
)


for previous, current in ((1, 3), (2, 4)):
    request_name = 'CalculationSampleRequest' + str(current)
    operation_name = 'CalculationSampleOperation' + str(current)
    DEFINITIONS[request_name] = deepcopy(DEFINITIONS['CalculationSampleRequest' + str(previous)])
    DEFINITIONS[request_name]['properties']['groups']['items'] = _ref('SampledGroup2')
    DEFINITIONS[operation_name] = deepcopy(
        DEFINITIONS['CalculationSampleOperation' + str(previous)]
    )
    DEFINITIONS[operation_name]['properties'].update(
        schema_version=dict(const=str(current)), request=_ref(request_name),
    )
for name in ('CalculationSampleRequest', 'CalculationSampleOperation'):
    DEFINITIONS[name + 'Read3'] = dict(oneOf=[_ref(name + str(v)) for v in (1, 2, 3, 4)])
DEFINITIONS['CalculationSamplePage3'] = deepcopy(DEFINITIONS['CalculationSamplePage2'])
DEFINITIONS['CalculationSamplePage3']['properties']['items']['items'] = _ref(
    'CalculationSampleOperationRead3'
)


for previous, current in ((3, 5), (4, 6)):
    req, op = 'CalculationSampleRequest' + str(current), 'CalculationSampleOperation' + str(current)
    DEFINITIONS[req] = deepcopy(DEFINITIONS['CalculationSampleRequest' + str(previous)])
    DEFINITIONS[req]['properties']['estimate_plan'] = deepcopy(
        CALCULATIONS['CalculationContent4']['properties']['estimate_plan'])
    DEFINITIONS[req]['required'].append('estimate_plan')
    DEFINITIONS[op] = deepcopy(DEFINITIONS['CalculationSampleOperation' + str(previous)])
    DEFINITIONS[op]['properties'].update(schema_version=dict(const=str(current)), request=_ref(req))
for name in ('CalculationSampleRequest', 'CalculationSampleOperation'):
    DEFINITIONS[name + 'Read4'] = dict(oneOf=[_ref(name + str(v)) for v in range(1, 7)])
DEFINITIONS['CalculationSamplePage4'] = deepcopy(DEFINITIONS['CalculationSamplePage3'])
DEFINITIONS['CalculationSamplePage4']['properties']['items']['items'] = _ref(
    'CalculationSampleOperationRead4')


def _worker_request(request):
    """Adapter to the frozen sampling protocol; never rewrite a retained public record."""
    result = deepcopy(request)
    result.pop('estimate_plan', None)
    for group in result['groups']:
        if 'validation_count' in group:
            group['check_count'] = group.pop('validation_count')
    return result


def _request_version(request):
    modern = 'validation_count' in request['groups'][0]
    return str((5 if 'estimate_plan' in request else 3 if modern else 1) + (request['method'] == 'boundary_latin_hypercube'))


_VALIDATORS = {}


def validate(name, value, *, retained=False):
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(
            {'$defs': definitions() | CALCULATIONS | DEFINITIONS, **DEFINITIONS[name]},
            format_checker=FormatChecker(),
        )
    errors = list(_VALIDATORS[name].iter_errors(value))
    if errors:
        if retained:
            raise DomainError('corrupt_retained_record', 409)
        raise DomainError(
            'invalid_request',
            400,
            fields=diagnostics(errors),
        )
    return value


def _refuse(path, message, status=422):
    raise DomainError('invalid_request', status, fields=[issue(path, message)])


def point_identity(reference, inputs):
    """A point is its reference configuration and its complete input vector."""
    return digest(
        dict(reference=reference, inputs=sorted(inputs, key=lambda v: _key(v['target'])))
    )


def point_inputs(free, dimensions, vector):
    """The complete input vector of one design coordinate: the reference's saved values with
    the sampled inputs replaced, in the saved units. Raises ``ValueError`` off the design."""
    varying = mapped_values(dimensions, vector)
    return [
        dict(
            target=p['target'],
            units=p['units'],
            value=varying.get(_key(p['target']), p['value']),
        )
        for p in free
    ]


class CalculationSamples:
    """Sampling operations: inert acceptance, then dispatcher steps (design, configure)."""

    def __init__(self, store, configurations):
        self.store, self.configurations = store, configurations
        self.calculations = Calculations(store)

    # Reads ---------------------------------------------------------------------------

    def status(self, actor, sid, operation):
        result = self.store.receipt(actor, sid, CATEGORY, operation)['result']
        return validate('CalculationSampleOperationRead4', result, retained=True)

    def page(self, actor, sid):
        """The study's newest sampling operations, newest first."""
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            rows = db.execute(
                'SELECT result FROM receipts WHERE scope=? AND category=? AND result IS NOT NULL '
                'ORDER BY rowid DESC LIMIT ?',
                (sid, CATEGORY, SAMPLE_PAGE),
            ).fetchall()
        items = [json.loads(row['result']) for row in rows]
        for item in items:
            validate('CalculationSampleOperationRead4', item, retained=True)
        return dict(items=items)

    # Acceptance ----------------------------------------------------------------------

    def _group(self, db, sid, index, group):
        """One group's reference and its free inputs, with every declaration problem."""
        path = ['groups', index]
        frozen = _frozen_configuration(db, sid, group['reference_configuration_revision_id'])
        if frozen is None:
            _refuse(
                path + ['reference_configuration_revision_id'],
                'The reference must be a saved configuration version of this study.',
            )
        if frozen['configuration']['schema_version'] != '6':
            _refuse(
                path + ['reference_configuration_revision_id'],
                'Only a configuration without criteria (version 6) can be a sampling reference.',
            )
        try:
            inputs, _ = quantities(frozen)
        except (ValueError, KeyError, TypeError) as exc:
            raise DomainError('corrupt_retained_record', 409) from exc
        free = [
            dict(
                target=p['target'],
                units=p['binding']['assignment']['units'],
                value=p['binding']['assignment']['value'],
            )
            for p in inputs
            if p['binding']['kind'] == 'free'
        ]
        saved = {_key(p['target']): p for p in free}
        dimensions, seen, signatures = group['dimensions'], set(), {}
        for n, d in enumerate(dimensions):
            where = path + ['dimensions', n]
            key = _key(d['target'])
            if key in seen or key not in saved:
                _refuse(where, 'Declare each sampled input once; it must be a free input.')
            seen.add(key)
            if d['units'] != saved[key]['units']:
                _refuse(
                    where + ['units'],
                    "Use the reference input's saved units; units are never converted.",
                )
            if not d['lower'] < d['upper']:
                _refuse(where, 'The lower bound must be below the upper bound.')
            if d['step'] is not None and not on_step(d['upper'], d):
                _refuse(
                    where + ['step'],
                    'The upper bound must lie on the step grid from the lower bound.',
                )
            if d['covary_group'] is not None:
                signature = (d['units'], d['lower'], d['upper'], d['step'])
                if signatures.setdefault(d['covary_group'], signature) != signature:
                    _refuse(
                        where + ['covary_group'],
                        'Inputs that move together need equal units, bounds and steps.',
                    )
        axes = independent_dimensions(dimensions)
        if all(d['step'] is not None for d in axes):
            size = math.prod(grid_size(d) for d in axes)
            if size < group['training_count'] + group['check_count']:
                _refuse(
                    path,
                    'The step grid has fewer points than requested; widen it or ask for fewer.',
                )
        return frozen, free

    def _retained(self, group, index, free, latest):
        """Points of the latest sampled version on this reference that still fit the
        declaration, keeping their partition and configuration version."""
        if latest is None or latest['content']['design']['kind'] != 'sampled':
            return []
        design = latest['content']['design']
        axes = independent_dimensions(group['dimensions'])
        kept = []
        for point in design['points']:
            old = design['groups'][point['group']]
            if (
                old['reference_configuration_revision_id']
                != (group['reference_configuration_revision_id'])
            ):
                continue
            try:
                values = {
                    _key(v['target']): v['value']
                    for v in point_inputs(free, old['dimensions'], point['vector'])
                }
                vector = [values[_key(d['target'])] for d in axes]
                if any(
                    not d['lower'] <= v <= d['upper'] or not on_step(v, d)
                    for d, v in zip(axes, vector, strict=True)
                ):
                    continue
                inputs = point_inputs(free, group['dimensions'], vector)
            except (ValueError, KeyError):
                continue
            reference = group['reference_configuration_revision_id']
            if point_identity(reference, inputs) != point['identity']:
                continue
            kept.append(dict(
                point, group=index, vector=vector,
                partition='check' if point['partition'] == 'validation' else point['partition'],
            ))
        return kept

    def resolve(self, actor, sid, request):
        validate('CalculationSampleRequestRead4', request)
        plan = request.get('estimate_plan')
        request = _worker_request(request)
        counts = [request['seed']] + [
            g[k] for g in request['groups'] for k in ('training_count', 'check_count')
        ]
        if any(type(value) is not int for value in counts):
            raise DomainError('invalid_request', 400)
        if (request['calculation_id'] is None) != (request['expected_version_id'] is None):
            _refuse(
                ['expected_version_id'],
                'A new version names the latest version; a new calculation names neither.',
                400,
            )
        observation = self.store.execution_observation()
        if (
            not observation
            or observation['status'] != 'ready'
            or time.time() - observation['observed_at'] > OBSERVATION_LIFETIME
            or not observation.get('runtime')
        ):
            raise DomainError('backend_unavailable', 503)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
            latest = None
            if request['calculation_id'] is not None:
                latest = self.calculations.latest(db, sid, request['calculation_id'])
                self.store.cas(latest['calculation_version_id'], request['expected_version_id'])
            groups, retained, model = [], [], None
            references = [g['reference_configuration_revision_id'] for g in request['groups']]
            if len(set(references)) != len(references):
                _refuse(['groups'], 'Each reference configuration is one group.')
            for index, group in enumerate(request['groups']):
                frozen, free = self._group(db, sid, index, group)
                if plan is not None:
                    outputs = {_key(o['target']) for o in quantities(frozen)[1]}
                    targets = [_key(t['target']) for t in plan['tolerances']]
                    if len(set(targets)) != len(targets) or not set(targets) <= outputs:
                        _refuse(['estimate_plan', 'tolerances'],
                                'Choose each output of this model version at most once.')
                pins = {
                    k: frozen['configuration'][k] for k in ('model_id', 'model_revision_id')
                }
                if model is None:
                    model = pins
                if pins != model or (
                    latest is not None
                    and pins
                    != {k: latest['content'][k] for k in ('model_id', 'model_revision_id')}
                ):
                    _refuse(
                        ['groups', index, 'reference_configuration_revision_id'],
                        "Every reference must use the calculation's one model version.",
                    )
                if request['method'] == 'boundary_latin_hypercube':
                    axes = independent_dimensions(group['dimensions'])
                    corners = 2 ** len(axes)
                    if corners >= group['training_count']:
                        _refuse(
                            ['groups', index, 'training_count'],
                            f'Joint boundary coverage needs {corners} training corners plus '
                            'interior training points. Increase the count within the limit '
                            'of 64, or revise the declared exploration domain explicitly.',
                        )
                kept = self._retained(group, index, free, latest)
                if request['method'] == 'boundary_latin_hypercube':
                    corners = set(product(*[(a['lower'], a['upper']) for a in axes]))
                    if any(
                        tuple(p['vector']) in corners and p['partition'] == 'check'
                        for p in kept
                    ):
                        _refuse(
                            ['groups', index],
                            'A retained check occupies a required training corner. '
                            'Create a new calculation; check points cannot become training.',
                        )
                    training = {
                        tuple(p['vector']) for p in kept if p['partition'] == 'training'
                    }
                    needed = len(training | corners)
                    if needed > max(group['training_count'], len(training)):
                        _refuse(
                            ['groups', index, 'training_count'],
                            f'Keeping existing training and adding the missing corners '
                            f'needs at least {needed} training points, within the limit of 64.',
                        )
                retained += kept
                groups.append(
                    dict(
                        free=free,
                        training_count=max(
                            group['training_count'],
                            sum(p['partition'] == 'training' for p in kept),
                        ),
                        check_count=max(
                            group['check_count'], sum(p['partition'] == 'check' for p in kept)
                        ),
                    )
                )
        total = sum(g['training_count'] + g['check_count'] for g in groups)
        if total > MAX_SAMPLED:
            _refuse(['groups'], f'A sampled version holds at most {MAX_SAMPLED} points.')
        return dict(
            runtime=observation['runtime'],
            model=model,
            groups=groups,
            retained=retained,
            total=total,
            points=None,
            design=None,
        )

    def submit(self, actor, sid, request):
        validate('CalculationSampleRequestRead4', request)
        if self.store.replay(actor, sid, CATEGORY, request['command_id'], request):
            return self.status(actor, sid, request['command_id'])
        work = self.resolve(actor, sid, request)
        result = dict(
            schema_version=_request_version(request),
            operation_id=request['command_id'],
            request=deepcopy(request),
            state='pending',
            reason=None,
            runtime=work['runtime'],
            point_count=work['total'],
            retained_count=len(work['retained']),
            calculation_id=request['calculation_id'],
            calculation_version_id=None,
        )
        validate('CalculationSampleOperationRead4', result, retained=True)

        def accept(db):
            if db.execute(
                'SELECT 1 FROM receipts WHERE scope=? AND category=? '
                "AND state IN ('pending_remote','dispatching')",
                (sid, CATEGORY),
            ).fetchone():
                raise DomainError('limit_exceeded', 429)
            return result

        return self.store.command(
            actor,
            sid,
            CATEGORY,
            request['command_id'],
            request,
            accept,
            receipt_state='pending_remote',
            request=work,
            attribute=lambda accepted: [('calculation_sample', accepted['operation_id'], None)],
        )

    # Dispatcher steps ----------------------------------------------------------------

    def process_one(self, native):
        """Advance the oldest pending operation by one step. A separate short OS lock
        serializes advancement; no database transaction spans the native call."""
        with self.store.background_actor(CATEGORY) as admitted:
            return self._process_one(native) if admitted else False

    def _process_one(self, native):
        import fcntl
        import os

        fd = os.open(
            self.store.lock_path('.calculation-samples.lock'),
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return self._advance(native)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _save(self, db, sid, result, work):
        validate('CalculationSampleOperationRead4', result, retained=True)
        state = {'complete': 'committed', 'failed': 'committed', 'uncertain': 'uncertain'}.get(
            result['state'], 'pending_remote'
        )
        db.execute(
            'UPDATE receipts SET state=?,result=?,request=? WHERE scope=? AND category=? '
            'AND command_id=?',
            (
                state,
                json.dumps(result),
                json.dumps(work),
                sid,
                CATEGORY,
                result['operation_id'],
            ),
        )

    def _advance(self, native):
        with self.store.connection(write=True) as db:
            row = db.execute(
                'SELECT scope,command_id,actor_id FROM receipts WHERE category=? '
                "AND state='pending_remote' ORDER BY rowid LIMIT 1",
                (CATEGORY,),
            ).fetchone()
            if row is None:
                return False
            sid, operation, actor = row['scope'], row['command_id'], row['actor_id']
            receipt = self.store.command_receipt(db, sid, CATEGORY, operation)
            result, work = receipt['result'], receipt['request']
            try:
                self.store.authorize(db, actor, sid, write=True)
            except DomainError:
                result.update(state='failed', reason='access_lost')
                self._save(db, sid, result, work)
                return True
            if result['state'] == 'designing':
                # A design call whose outcome is unknown is never re-dispatched.
                result.update(state='uncertain', reason='design_outcome_unknown')
                self._save(db, sid, result, work)
                return True
            if result['state'] == 'pending':
                result['state'] = 'designing'
                self._save(db, sid, result, work)
        if result['state'] == 'designing':
            try:
                self._design(native, result, work)
            except (ValueError, KeyError, TypeError, OSError, RuntimeError, DomainError):
                result.update(state='uncertain', reason='design_outcome_unknown')
        else:
            try:
                self._configure(actor, sid, result, work)
                return True
            except DomainError as error:
                result.update(state='failed', reason=error.code)
            except (ValueError, KeyError, TypeError, OSError, RuntimeError):
                result.update(state='uncertain', reason='configuration_outcome_unknown')
        with self.store.connection(write=True) as db:
            self._save(db, sid, result, work)
        return True

    def _design(self, native, result, work):
        request = _worker_request(result['request'])
        retained = {}
        for point in work['retained']:
            retained.setdefault(point['group'], []).append(point)
        groups = []
        for index, group in enumerate(request['groups']):
            axes = independent_dimensions(group['dimensions'])
            groups.append(
                dict(
                    bounds=[[d['lower'], d['upper']] for d in axes],
                    training_count=work['groups'][index]['training_count'],
                    check_count=work['groups'][index]['check_count'],
                    retained=[
                        dict(partition=p['partition'], vector=p['vector'])
                        for p in retained.get(index, [])
                    ],
                )
            )
        numerical = dict(
            schema_version='4' if request['method'] == 'boundary_latin_hypercube' else '2',
            operation='extend_design',
            identity=digest(dict(request=request, retained=work['retained'])),
            seed=request['seed'],
            groups=groups,
        )
        artifact = native.explore(numerical)
        design = artifact['result']
        if (
            artifact['runtime'] != work['runtime']
            or artifact['request_sha256'] != digest(numerical)
            or artifact['result_sha256'] != digest(design)
            or design['identity'] != numerical['identity']
            or len(design['groups']) != len(groups)
        ):
            raise ValueError('Exact retained design artifact required')
        points = []
        for index, rows in enumerate(design['groups']):
            group, expected = request['groups'][index], groups[index]
            if any(
                sum(r['partition'] == partition for r in rows) != expected[count]
                for partition, count in [
                    ('training', 'training_count'),
                    ('check', 'check_count'),
                ]
            ):
                raise ValueError('Independent partition allocation changed')
            kept = {tuple(p['vector']): p for p in retained.get(index, [])}
            reference = group['reference_configuration_revision_id']
            for row in rows:
                if row['partition'] not in ('training', 'check'):
                    raise ValueError('Malformed design row')
                point = kept.get(tuple(row['vector']))
                if point is not None:
                    if point['partition'] != row['partition']:
                        raise ValueError('Retained partition changed')
                    points.append(point)
                    continue
                inputs = point_inputs(
                    work['groups'][index]['free'], group['dimensions'], row['vector']
                )
                axes = independent_dimensions(group['dimensions'])
                values = {_key(v['target']): v['value'] for v in inputs}
                points.append(
                    dict(
                        group=index,
                        partition=row['partition'],
                        identity=point_identity(reference, inputs),
                        # Stepped coordinates are recorded as snapped to their grid.
                        vector=[values[_key(d['target'])] for d in axes],
                        configuration_revision_id=None,
                        inputs=inputs,
                    )
                )
        if len({p['identity'] for p in points}) != len(points) or len(points) != work['total']:
            result.update(
                state='failed',
                reason=(
                    'The stepped design repeats a point. Widen the ranges, ask for fewer '
                    'points or choose another seed.'
                ),
            )
            return
        work['points'] = points
        work['design'] = dict(
            design_digest=digest(dict(mapping_version='1', numerical=design, points=points)),
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
        )
        result['state'] = 'configuring'

    def _configure(self, actor, sid, result, work):
        """Freeze every new point as a configuration version (stable command identities make
        a repeated step return the same versions), then save the calculation version in one
        transaction with the operation's completion."""
        request, operation = result['request'], result['operation_id']
        for point in work['points']:
            if point['configuration_revision_id'] is None:
                saved = self.configurations.exploration_point(
                    actor,
                    sid,
                    str(uuid5(UUID(operation), point['identity'])),
                    request['groups'][point['group']]['reference_configuration_revision_id'],
                    point['inputs'],
                    request['rationale'],
                )
                point['configuration_revision_id'] = saved['configuration_revision_id']
        design = dict(
            kind='sampled',
            operation_id=operation,
            method=request['method'],
            seed=request['seed'],
            groups=deepcopy(request['groups']),
            points=[
                {
                    k: p[k]
                    for k in (
                        'group',
                        'partition',
                        'identity',
                        'vector',
                        'configuration_revision_id',
                    )
                }
                for p in work['points']
            ],
            rationale=request['rationale'],
            runtime=work['runtime'],
            **work['design'],
        )
        modern = 'validation_count' in request['groups'][0]
        if modern:
            for point in design['points']:
                if point['partition'] == 'check':
                    point['partition'] = 'validation'
        with self.store.connection(write=True) as db:
            current = self.store.command_receipt(db, sid, CATEGORY, operation)
            if current is None or current['result']['state'] != 'configuring':
                return
            self.store.authorize(db, actor, sid, write=True)
            cid = request['calculation_id'] or str(uuid5(UUID(operation), 'calculation'))
            latest = (
                self.calculations.latest(db, sid, cid) if request['calculation_id'] else None
            )
            content = dict(
                schema_version='4' if 'estimate_plan' in request else '3' if modern else (
                    '2' if request['method'] == 'boundary_latin_hypercube' else '1'
                ),
                name=request['name'],
                description=request['description'],
                model_id=work['model']['model_id'],
                model_revision_id=work['model']['model_revision_id'],
                configuration_revision_ids=[
                    p['configuration_revision_id'] for p in design['points']
                ],
                design=design,
                brief_version_id=latest['content']['brief_version_id'] if latest else None,
                criterion_bindings=deepcopy(latest['content']['criterion_bindings'])
                if latest
                else [],
            )
            if 'estimate_plan' in request:
                content['estimate_plan'] = deepcopy(request['estimate_plan'])
            version = self.calculations.insert_generated(
                db, actor, sid, cid, content, request['expected_version_id']
            )
            result.update(
                state='complete',
                reason=None,
                calculation_id=cid,
                calculation_version_id=version['calculation_version_id'],
            )
            self._save(db, sid, result, work)

    # Member runs ---------------------------------------------------------------------

    def request_runs(self, actor, sid, version_id, body, submissions):
        """Submit one ordinary run for each named member. Each run's command id derives from
        this request and the member, so a repeated request returns the same runs; the version
        never changes."""
        validate('CalculationRunRequest1', body)
        version = self.calculations.version(actor, sid, version_id)
        if version['schema_version'] == '4':
            _refuse(['calculation_version_id'], 'Launch the analysis to calculate its points.')
        members = set(version['content']['configuration_revision_ids'])
        for index, revision in enumerate(body['configuration_revision_ids']):
            if revision not in members:
                _refuse(
                    ['configuration_revision_ids', index],
                    'Every configuration version must be a member of this calculation version.',
                )
        runs = []
        for revision in body['configuration_revision_ids']:
            command = str(uuid5(UUID(body['command_id']), revision))
            run = submissions.submit(
                actor, sid, dict(command_id=command, configuration_revision_id=revision)
            )
            runs.append(
                dict(
                    configuration_revision_id=revision, run_id=run['run_id'], command_id=command
                )
            )
        return dict(calculation_version_id=version_id, runs=runs)
