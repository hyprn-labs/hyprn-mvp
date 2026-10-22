"""Disposable answer interaction over exact calculation versions and assessed estimates.

The application projects retained calculations and bounds an interaction queue. Numerical
prediction stays in the existing attested worker. Renewal reloads the immutable assessed
artifact; it never samples, fits or runs candidate source. Full input vectors are checked,
including the assignments that were not varied by the design.
"""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
from threading import BoundedSemaphore, Lock
from fractions import Fraction
import json
import math
import time
from weakref import WeakKeyDictionary, WeakValueDictionary

from jsonschema import Draft202012Validator, FormatChecker

from .calculation_estimates import CATEGORY as ESTIMATES, Estimates
from .calculations import (
    DEFINITIONS as CALCULATIONS,
    Calculations,
    _frozen_configuration,
    independent_dimensions,
)
from .contracts import DomainError, canonical, definitions, digest, issue
from .history import History, calculation_runs
from .quantity_projection import _key, quantities

CATEGORY = 'calculation_prediction'
TIMEOUT = 40


def _object(properties):
    return dict(
        type='object',
        properties=properties,
        required=list(properties),
        additionalProperties=False,
    )


def _ref(name):
    return {'$ref': '#/$defs/' + name}


def _array(items, maximum, minimum=0):
    return dict(type='array', items=items, minItems=minimum, maxItems=maximum)


def _nullable(value):
    return dict(anyOf=[value, dict(type='null')])


_ID = CALCULATIONS['CalculationVersion1']['properties']['calculation_id']
_NUMBER = dict(type='number', minimum=-(2**53 - 1), maximum=2**53 - 1)
_TEXT = dict(type='string', maxLength=4096)
_PORT = dict(
    target=_ref('PortRef'),
    definition_version_id=_ID,
    name=_TEXT,
    instance_name=_TEXT,
    units=_TEXT,
)
_INPUTS = _array(_object(dict(target=_ref('PortRef'), value=_NUMBER, units=_TEXT)), 1000)
DEFINITIONS = {
    'CalculationInput1': _object(
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
    'CalculationOutput1': _object(_PORT),
    'CalculationPointValue1': _object(
        dict(
            target=_ref('PortRef'),
            units=_TEXT,
            value=_nullable(_NUMBER),
            reason=_nullable(_TEXT),
            kind=dict(enum=['calculated', 'estimated', 'unavailable']),
            run_id=_nullable(_ID),
        )
    ),
    'CalculationPoint1': _object(
        dict(inputs=_INPUTS, outputs=_array(_ref('CalculationPointValue1'), 1000))
    ),
    'CalculationExploration1': _object(
        dict(
            calculation_version_id=_ID,
            model_id=_ID,
            model_revision_id=_ID,
            configuration_revision_id=_ID,
            group=dict(type='integer', minimum=0, maximum=9999),
            dimensions=_array(_ref('SampledDimension1'), 32),
            inputs=_array(_ref('CalculationInput1'), 1000),
            outputs=_array(_ref('CalculationOutput1'), 1000),
            points=_array(_ref('CalculationPoint1'), 1024),
        )
    ),
    'CalculationPredictionRequest1': _object(
        dict(
            selection_token=_ID,
            group=dict(type='integer', minimum=0, maximum=7),
            inputs=_INPUTS,
            axis=_nullable(_ref('PortRef')),
            curve_points=dict(type='integer', minimum=0, maximum=32),
        )
    ),
    'CalculationPrediction1': _object(
        dict(
            selection_token=_ID,
            estimate_id=_ID,
            identity=dict(type='string', pattern='^[0-9a-f]{64}$'),
            points=_array(_ref('CalculationPoint1'), 33, 1),
        )
    ),
}
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
            fields=[
                issue(list(e.absolute_path), 'Invalid exploration field.') for e in errors[:20]
            ],
        )
    return value


def _reject(path, text):
    raise DomainError('invalid_request', 422, fields=[issue(path, text)])


def _vector(inputs):
    return [
        dict(
            target=p['target'],
            value=p['binding']['assignment']['value'],
            units=p['binding']['assignment']['units'],
        )
        for p in inputs
        if p['binding']['kind'] == 'free'
    ]


def _same(a, b):
    return sorted(a, key=lambda v: _key(v['target'])) == sorted(
        b, key=lambda v: _key(v['target'])
    )


_store_caches = WeakKeyDictionary()
_store_caches_lock = Lock()
_retained_read_slots = BoundedSemaphore(4)


def _retained_many(history, actor, sid, ids):
    """Bound cold PostgreSQL reads and carry the caller's authority into each thread."""
    if getattr(getattr(history.store, 'database', None), 'dialect', None) != 'postgresql':
        yield from (history.retained(actor, sid, rid) for rid in ids)
        return
    def read(rid):
        with _retained_read_slots:
            return history.retained_projection(actor, sid, rid)
    with ThreadPoolExecutor(max_workers=4) as pool:
        # Do not retain every embedded source archive while projecting a large analysis.
        for start in range(0, len(ids), 4):
            futures = [
                pool.submit(copy_context().run, read, rid) for rid in ids[start:start + 4]
            ]
            for future in futures:
                yield future.result()


class CalculationExploration:
    def __init__(self, store):
        self.store = store
        self.calculations = Calculations(store)
        self.estimates = Estimates(store)
        # Publication and HTTP readers share checked projections for this Store only.
        # Neither actor authority nor integrity witnesses are accepted from the cache.
        with _store_caches_lock:
            caches = _store_caches.get(store) if store is not None else None
            if caches is None:
                caches = (OrderedDict(), OrderedDict(), Lock(), WeakValueDictionary())
                if store is not None:
                    _store_caches[store] = caches
        self._basis_cache, self._pinned_cache, self._basis_lock, self._basis_reads = caches

    def _pinned_bytes(self, db, sid, version_id, estimate_id, members=None):
        """Cheap identity of immutable owner bytes; admission still happens on cache miss.

        Re-reading raw bytes detects corruption without revalidating the same embedded model
        for every configuration on every drag. Authorization and run tokens are never cached.
        """
        version = db.execute(
            'SELECT * FROM calculation_versions WHERE study_id=? AND calculation_version_id=?',
            (sid, version_id),
        ).fetchone()
        estimate = db.execute(
            'SELECT * FROM receipts WHERE scope=? AND category=? AND command_id=?',
            (sid, ESTIMATES, estimate_id),
        ).fetchone()
        if version is None or estimate is None:
            return None
        if members is None:
            try:
                content = json.loads(version['payload'])['content']
            except (ValueError, KeyError, TypeError) as error:
                raise DomainError('corrupt_retained_record', 409) from error
            members = set(content['configuration_revision_ids'])
            if content['design']['kind'] == 'sampled':
                members.update(
                    g['reference_configuration_revision_id']
                    for g in content['design']['groups']
                )
        rows = db.execute(
            'SELECT configuration_revision_id,payload FROM configurations WHERE study_id=? '
            'AND configuration_revision_id IN (SELECT value FROM json_each(?)) '
            'ORDER BY configuration_revision_id',
            (sid, json.dumps(sorted(members))),
        ).fetchall()
        return digest(
            dict(
                version=dict(version),
                estimate=dict(estimate),
                configurations=[dict(r) for r in rows],
            )
        )

    def basis(self, actor, sid, version_id, *, group=0, estimate_id=None):
        # Share verification work, never authority. Waiters reauthorize and recheck
        # current bytes inside _basis; unused per-key locks disappear automatically.
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
        key = (sid, version_id, estimate_id, group)
        with self._basis_lock:
            pending = self._basis_reads.get(key)
            if pending is None:
                pending = Lock()
                self._basis_reads[key] = pending
        with pending:
            return self._basis(actor, sid, version_id, group=group, estimate_id=estimate_id)

    def _basis(self, actor, sid, version_id, *, group=0, estimate_id=None):
        pinned_key = (sid, version_id, estimate_id, group)
        fingerprint = None
        if estimate_id:
            with self._basis_lock:
                cached = deepcopy(self._pinned_cache.get(pinned_key))
            if cached is not None:
                expected, result, tokens = cached
                with self.store.connection() as db:
                    self.store.authorize(db, actor, sid)
                    fingerprint = self._pinned_bytes(db, sid, version_id, estimate_id)
                    if fingerprint == expected:
                        History(self.store).recheck(db, actor, sid, tokens)
                        return result
        if estimate_id and fingerprint is None:
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid)
                fingerprint = self._pinned_bytes(db, sid, version_id, estimate_id)
        version = self.calculations.version(actor, sid, version_id)
        content = version['content']
        design = content['design']
        sampled = design['kind'] == 'sampled'
        groups = design['groups'] if sampled else content['configuration_revision_ids']
        if type(group) is not int or not 0 <= group < len(groups):
            _reject(['group'], 'Choose a group in this calculation version.')
        reference_id = (
            groups[group]['reference_configuration_revision_id'] if sampled else groups[group]
        )
        dimensions = groups[group]['dimensions'] if sampled else []
        estimate = self.estimates.read(actor, sid, estimate_id) if estimate_id else None
        if estimate and (
            estimate['calculation_version_id'] != version_id
            or estimate['state'] not in ('ready', 'assessed')
        ):
            _reject(['estimate_id'], 'Choose a finished estimate of this calculation version.')
        members = (
            [p['configuration_revision_id'] for p in design['points'] if p['group'] == group]
            if sampled
            else [reference_id]
        )
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            frozen = _frozen_configuration(db, sid, reference_id)
            snapshots = {cid: _frozen_configuration(db, sid, cid) for cid in members}
            latest = {}
            if not estimate:
                runs = calculation_runs(db, sid, members, 0, 10001)
                if len(runs) > 10000:
                    raise DomainError('limit_exceeded', 413)
                for run in runs:
                    if run['state'] == 'recorded':
                        latest[run['configuration_revision_id']] = (run['run_id'], None)
        if estimate:
            latest = {
                p['configuration_revision_id']: (p['run_id'], p['results_digest'])
                for p in estimate['samples']
                if p['group'] == group and p['run_id']
            }
        # Reuse only the disposable projection of the exact current bytes. Authorization,
        # frozen-record admission and retained run/receipt checks still run on every read.
        cache_key = digest(
            dict(
                study_id=sid,
                version=version,
                estimate=estimate,
                group=group,
                frozen=frozen,
                snapshots=snapshots,
                latest=latest,
            )
        )
        history = History(self.store)
        with self._basis_lock:
            cached = self._basis_cache.get(cache_key)
            if cached is not None:
                self._basis_cache.move_to_end(cache_key)
                cached = deepcopy(cached)
        if cached is not None:
            result, tokens = cached
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid)
                history.recheck(db, actor, sid, tokens)
            return result
        inputs, outputs = quantities(frozen)
        points, tokens = [], []
        retained_runs = _retained_many(
            history, actor, sid, [run_id for run_id, _ in latest.values()]
        )
        for (cid, (run_id, results_digest)), retained in zip(
            latest.items(), retained_runs, strict=True
        ):
            if retained.history['configuration']['configuration_revision_id'] != cid or (
                results_digest and digest(retained.history['results']) != results_digest
            ):
                raise DomainError('corrupt_retained_record', 409)
            tokens.append(retained.token)
            values = {
                _key(o['target']): o
                for o in (retained.history['results'] or {}).get('outputs', [])
            }
            point_outputs = []
            for output in outputs:
                original = values.get(_key(output['target']))
                available = original and original['availability'] == 'available'
                point_outputs.append(
                    dict(
                        target=output['target'],
                        units=output['units'],
                        value=original['value'] if available else None,
                        reason=None if available else 'original_unavailable',
                        kind='calculated' if available else 'unavailable',
                        run_id=run_id,
                    )
                )
            points.append(
                dict(inputs=_vector(quantities(snapshots[cid])[0]), outputs=point_outputs)
            )
        with self.store.connection() as db:
            history.recheck(db, actor, sid, tokens)
        result = validate(
            'CalculationExploration1',
            dict(
                calculation_version_id=version_id,
                model_id=content['model_id'],
                model_revision_id=content['model_revision_id'],
                configuration_revision_id=reference_id,
                group=group,
                dimensions=dimensions,
                inputs=inputs,
                outputs=outputs,
                points=points,
            ),
            retained=True,
        )
        if len(canonical(result)) <= 1024 * 1024:
            with self._basis_lock:
                if fingerprint:
                    self._pinned_cache[pinned_key] = (
                        fingerprint,
                        deepcopy(result),
                        deepcopy(tokens),
                    )
                    self._pinned_cache.move_to_end(pinned_key)
                    while len(self._pinned_cache) > 8:
                        self._pinned_cache.popitem(last=False)
                self._basis_cache[cache_key] = (deepcopy(result), deepcopy(tokens))
                self._basis_cache.move_to_end(cache_key)
                while len(self._basis_cache) > 8:
                    self._basis_cache.popitem(last=False)
        return result

    def query(self, actor, sid, estimate_id, request):
        validate('CalculationPredictionRequest1', request)
        estimate = self.estimates.read(actor, sid, estimate_id)
        index = request['group']
        basis = self.basis(
            actor, sid, estimate['calculation_version_id'], group=index, estimate_id=estimate_id
        )
        dimensions = basis['dimensions']
        baseline = {_key(v['target']): v for v in _vector(basis['inputs'])}
        values = {_key(v['target']): v for v in request['inputs']}
        if len(values) != len(request['inputs']) or set(values) != set(baseline):
            _reject(['inputs'], 'Supply each independent input exactly once.')
        varied = {_key(d['target']): d for d in dimensions}
        for key, value in values.items():
            if (
                type(value['value']) not in (int, float)
                or not math.isfinite(value['value'])
                or value['units'] != baseline[key]['units']
            ):
                _reject(['inputs'], 'Use finite values in the saved input units.')
            dimension = varied.get(key)
            if dimension is None and value != baseline[key]:
                _reject(
                    ['inputs'], 'An input outside the sampled design must keep its saved value.'
                )
            if dimension and dimension['step'] is not None:
                step = (
                    Fraction(str(value['value'])) - Fraction(str(dimension['lower']))
                ) / Fraction(str(dimension['step']))
                if step.denominator != 1:
                    _reject(['inputs'], 'Use the declared input step grid.')
        axes = independent_dimensions(dimensions)
        for axis in axes:
            if axis['covary_group']:
                fraction = (values[_key(axis['target'])]['value'] - axis['lower']) / (
                    axis['upper'] - axis['lower']
                )
                for d in dimensions:
                    if d['covary_group'] == axis['covary_group']:
                        expected = d['lower'] + fraction * (d['upper'] - d['lower'])
                        if not math.isclose(
                            values[_key(d['target'])]['value'],
                            expected,
                            rel_tol=1e-10,
                            abs_tol=1e-10,
                        ):
                            _reject(
                                ['inputs'], 'Linked inputs must follow their declared mapping.'
                            )
        vectors = [request['inputs']]
        if request['axis'] is not None:
            axis = varied.get(_key(request['axis']))
            if axis is None or request['curve_points'] < 2:
                _reject(['axis'], 'Choose a sampled input and at least two curve points.')
            changing = {
                _key(d['target'])
                for d in dimensions
                if d == axis
                or (axis['covary_group'] and d['covary_group'] == axis['covary_group'])
            }
            for n in range(request['curve_points']):
                fraction = n / (request['curve_points'] - 1)
                point = deepcopy(request['inputs'])
                for v in point:
                    d = varied.get(_key(v['target']))
                    if _key(v['target']) in changing:
                        number = d['lower'] + fraction * (d['upper'] - d['lower'])
                        if d['step'] is not None:
                            number = float(
                                Fraction(str(d['lower']))
                                + round(
                                    (Fraction(str(number)) - Fraction(str(d['lower'])))
                                    / Fraction(str(d['step']))
                                )
                                * Fraction(str(d['step']))
                            )
                        v['value'] = number
                if not any(_same(point, existing) for existing in vectors):
                    vectors.append(point)

        public = next(g for g in estimate['groups'] if g['group'] == index)
        numerical = dict(
            schema_version='3',
            operation='predict',
            identity=public['identity'],
            payload=dict(
                queries=[
                    [next(v['value'] for v in p if v['target'] == d['target']) for d in axes]
                    for p in vectors
                ]
            ),
        )
        response = self._predict(actor, sid, estimate_id, index, request, numerical, public)
        if response.get('identity') != public['identity'] or len(
            response.get('values', [])
        ) != len(vectors):
            raise DomainError('backend_unavailable', 503)
        points = []
        for vector, row in zip(vectors, response['values'], strict=True):
            if len(row) != len(public['outputs']):
                raise DomainError('backend_unavailable', 503)
            exact = next((p for p in basis['points'] if _same(p['inputs'], vector)), None)
            outputs = []
            for port, value in zip(public['outputs'], row, strict=True):
                if (
                    not isinstance(value, dict)
                    or set(value) != {'value', 'reason'}
                    or (
                        value['value'] is not None
                        and (
                            type(value['value']) not in (int, float)
                            or not math.isfinite(value['value'])
                            or abs(value['value']) > 2**53 - 1
                        )
                    )
                ):
                    raise DomainError('backend_unavailable', 503)
                if port['reason'] is not None:
                    value = dict(value=None, reason=port['reason'])
                original = (
                    next((o for o in exact['outputs'] if o['target'] == port['target']), None)
                    if exact
                    else None
                )
                outputs.append(
                    original
                    if original
                    else dict(
                        target=port['target'],
                        units=port['units'],
                        **value,
                        kind='estimated' if value['value'] is not None else 'unavailable',
                        run_id=None,
                    )
                )
            points.append(dict(inputs=vector, outputs=outputs))
        return validate(
            'CalculationPrediction1',
            dict(
                selection_token=request['selection_token'],
                estimate_id=estimate_id,
                identity=public['identity'],
                points=points,
            ),
            retained=True,
        )

    def _predict(self, actor, sid, estimate_id, group, request, numerical, public):
        command, deadline = request['selection_token'], time.time() + TIMEOUT
        with self.store.connection(write=True) as db:
            self.store.authorize(db, actor, sid)
            # A prediction is a pure read with its own interaction identity.
            # Other tabs and late HTTP requests must not delete an active read.
            db.execute(
                'DELETE FROM receipts WHERE category=? AND '
                "CAST(json_extract(request,'$.deadline') AS DOUBLE PRECISION)<?",
                (CATEGORY, time.time()),
            )
            db.execute(
                'INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)',
                (
                    sid,
                    CATEGORY,
                    command,
                    actor,
                    digest(request),
                    'pending_remote',
                    None,
                    None,
                    json.dumps(
                        dict(
                            numerical=numerical,
                            estimate_id=estimate_id,
                            group=group,
                            deadline=deadline,
                            runtime=public['computation_runtime'],
                        )
                    ),
                ),
            )
        result = None
        try:
            while time.time() < deadline:
                with self.store.connection() as db:
                    self.store.authorize(db, actor, sid)
                    row = self.store.command_receipt(db, sid, CATEGORY, command)
                if row is None or row['state'] == 'rejected':
                    break
                if row['state'] == 'committed':
                    result = row['result']
                    break
                time.sleep(0.01)
        finally:
            with self.store.connection(write=True) as db:
                db.execute(
                    'DELETE FROM receipts WHERE scope=? AND category=? AND command_id=?',
                    (sid, CATEGORY, command),
                )
        if result is None:
            raise DomainError(
                'backend_unavailable',
                503,
                fields=[
                    issue(
                        [],
                        'Prediction did not complete within the interaction budget. '
                        'Retry the selection; saved samples and estimates are unchanged.',
                    )
                ],
            )
        return result

    def process_one(self, native):
        with self.store.background_actor(CATEGORY) as admitted:
            return self._process_one(native) if admitted else False

    def _process_one(self, native):
        with self.store.connection(write=True) as db:
            row = db.execute(
                'SELECT * FROM receipts WHERE category=? '
                "AND state='pending_remote' ORDER BY rowid LIMIT 1",
                (CATEGORY,),
            ).fetchone()
            if row is None:
                return False
            sid, actor, command = (row[k] for k in ('scope', 'actor_id', 'command_id'))
            saved = self.store.command_receipt(db, sid, CATEGORY, command)['request']
            try:
                self.store.authorize(db, actor, sid)
            except DomainError:
                db.execute(
                    "UPDATE receipts SET state='rejected' WHERE scope=? AND category=? "
                    'AND command_id=?',
                    (sid, CATEGORY, command),
                )
                return True
            db.execute(
                "UPDATE receipts SET state='dispatching' WHERE scope=? AND category=? "
                'AND command_id=?',
                (sid, CATEGORY, command),
            )
        state, result = 'committed', None
        try:
            if time.time() > saved['deadline']:
                raise RuntimeError('Expired interaction')
            try:
                result = native.surrogate(saved['numerical'], saved['runtime'])
            except RuntimeError:
                receipt = self.store.receipt(actor, sid, ESTIMATES, saved['estimate_id'])
                index = saved['group']
                public = receipt['result']['groups'][index]
                artifact = receipt['request']['artifacts'][index]
                if (
                    public['identity'] != saved['numerical']['identity']
                    or public['computation_runtime'] != saved['runtime']
                    or digest(artifact) != public['artifact_sha256']
                ):
                    raise ValueError('Estimate renewal identity mismatch')
                native.surrogate(
                    dict(
                        schema_version='3',
                        operation='warm',
                        identity=public['identity'],
                        payload=dict(artifact=artifact),
                    ),
                    saved['runtime'],
                )
                with self.store.connection() as db:
                    self.store.authorize(db, actor, sid)
                    current = self.store.command_receipt(db, sid, CATEGORY, command)
                if (
                    time.time() > saved['deadline']
                    or current is None
                    or current['state'] != 'dispatching'
                ):
                    return True
                result = native.surrogate(saved['numerical'], saved['runtime'])
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError, DomainError):
            state = 'rejected'
        with self.store.connection(write=True) as db:
            db.execute(
                'UPDATE receipts SET state=?,result=? WHERE scope=? AND category=? '
                "AND command_id=? AND state='dispatching'",
                (state, json.dumps(result), sid, CATEGORY, command),
            )
        return True
