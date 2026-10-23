"""Estimates: assessed surrogates fitted to exactly one calculation version and its runs.

An estimate is built from one sampled calculation version, whose design names the input axes
and keeps check points apart from training points. Each point contributes the latest recorded
run of its configuration version, read from its integrity-checked retained record and pinned
by run id and results digest; a point without a recorded run is unavailable, never zero. The
fitting is the existing bounded native build: the application owns identities, receipts and
authorization, and only the native bridge computes. An estimate's values are estimates, never
calculated results; a failed build publishes no usable output.
"""

from copy import deepcopy
import json

from jsonschema import Draft202012Validator, FormatChecker

from .calculation_designs import DEFINITIONS as SAMPLING
from .calculations import (
    DEFINITIONS as CALCULATIONS,
    MAX_SAMPLED,
    Calculations,
    _frozen_configuration,
    independent_dimensions,
)
from .contracts import diagnostics
from .contracts import DomainError, definitions, digest, issue
from .quantity_projection import _key, quantities
from .history import History, calculation_runs

CATEGORY = 'calculation_estimate'
ESTIMATE_PAGE = 20
# Runs read to pick each point's latest recorded run.
RUN_SCAN = 10000


def _object(properties):
    return dict(
        type='object', properties=properties, required=list(properties), additionalProperties=False
    )


def _ref(name):
    return {'$ref': '#/$defs/' + name}


def _nullable(schema):
    return dict(anyOf=[schema, dict(type='null')])


_ID = CALCULATIONS['CalculationVersion1']['properties']['calculation_id']
_HASH = dict(type='string', pattern='^[0-9a-f]{64}$')
_TEXT = dict(type='string', maxLength=4096)
_NUMBER = dict(type='number', minimum=-(2**53 - 1), maximum=2**53 - 1)
_POSITIVE = dict(type='number', minimum=0, maximum=2**53 - 1)
_RUNTIME = CALCULATIONS['SampledDesign1']['properties']['runtime']
_METHOD = dict(enum=['response_surface', 'kriging'])
DEFINITIONS = {
    'CalculationEstimateRequest1': _object(
        dict(
            command_id=_ID,
            calculation_version_id=_ID,
            tolerances=dict(
                type='array',
                minItems=1,
                maxItems=32,
                items=_object(dict(target=_ref('PortRef'), absolute=_POSITIVE, relative=_POSITIVE)),
            ),
        )
    ),
    # One design point as the estimate used it: the run pinned for it, or none.
    'CalculationEstimateSample1': _object(
        dict(
            group=dict(type='integer', minimum=0, maximum=7),
            partition=dict(enum=['training', 'check']),
            configuration_revision_id=_ID,
            run_id=_nullable(_ID),
            results_digest=_nullable(_HASH),
        )
    ),
    # One output's assessment: usable (reason null) only when its check points met the
    # declared tolerance; otherwise the reason says why it is not an estimate.
    'CalculationEstimateOutput1': _object(
        dict(
            target=_ref('PortRef'),
            units=_TEXT,
            method=_nullable(_METHOD),
            reason=_nullable(_TEXT),
            metrics=_nullable(
                _object(
                    dict(
                        assessed_count=dict(type='integer', minimum=0, maximum=64),
                        evaluable_count=dict(type='integer', minimum=0, maximum=64),
                        failed_count=dict(type='integer', minimum=0, maximum=64),
                        max_absolute_error=_nullable(_NUMBER),
                        rmse=_nullable(_NUMBER),
                        target_met=dict(type='boolean'),
                    )
                )
            ),
            comparisons=dict(
                type='array',
                maxItems=2,
                items=_object(
                    dict(method=_METHOD, reason=_nullable(_TEXT), error=_nullable(_NUMBER))
                ),
            ),
        )
    ),
    'CalculationEstimate1': _object(
        dict(
            schema_version=dict(const='1'),
            estimate_id=_ID,
            calculation_id=_ID,
            calculation_version_id=_ID,
            request=_ref('CalculationEstimateRequest1'),
            state=dict(enum=['pending', 'building', 'ready', 'assessed', 'failed']),
            reason=_nullable(_TEXT),
            original_runtime=_nullable(_RUNTIME),
            samples=dict(
                type='array', items=_ref('CalculationEstimateSample1'), maxItems=MAX_SAMPLED
            ),
            completed_groups=dict(type='integer', minimum=0, maximum=8),
            total_groups=dict(type='integer', minimum=1, maximum=8),
            groups=dict(
                type='array',
                maxItems=8,
                items=_object(
                    dict(
                        group=dict(type='integer', minimum=0, maximum=7),
                        identity=_HASH,
                        computation_runtime=_RUNTIME,
                        process_uuid=_ID,
                        store_uuid=_ID,
                        artifact_uuid=_ID,
                        request_sha256=_HASH,
                        result_sha256=_HASH,
                        artifact_sha256=_HASH,
                        outputs=dict(
                            type='array',
                            items=_ref('CalculationEstimateOutput1'),
                            minItems=1,
                            maxItems=32,
                        ),
                    )
                ),
            ),
        )
    ),
    'CalculationEstimatePage1': _object(
        dict(
            calculation_version_id=_ID,
            items=dict(type='array', items=_ref('CalculationEstimate1'), maxItems=ESTIMATE_PAGE),
            next_cursor=_nullable(_ID),
        )
    ),
}

# New estimates name the held-out partition validation, including estimates of old designs.
DEFINITIONS['CalculationEstimateSample2'] = deepcopy(DEFINITIONS['CalculationEstimateSample1'])
DEFINITIONS['CalculationEstimateSample2']['properties']['partition'] = dict(
    enum=['training', 'validation']
)
DEFINITIONS['CalculationEstimate2'] = deepcopy(DEFINITIONS['CalculationEstimate1'])
DEFINITIONS['CalculationEstimate2']['properties']['schema_version'] = dict(const='2')
DEFINITIONS['CalculationEstimate2']['properties']['samples']['items'] = _ref(
    'CalculationEstimateSample2'
)
DEFINITIONS['CalculationEstimateRead2'] = dict(oneOf=[
    _ref('CalculationEstimate1'), _ref('CalculationEstimate2'),
])
DEFINITIONS['CalculationEstimatePage2'] = deepcopy(DEFINITIONS['CalculationEstimatePage1'])
DEFINITIONS['CalculationEstimatePage2']['properties']['items']['items'] = _ref(
    'CalculationEstimateRead2'
)

_VALIDATORS = {}


def validate(name, value, *, retained=False):
    if name not in _VALIDATORS:
        _VALIDATORS[name] = Draft202012Validator(
            {'$defs': definitions() | CALCULATIONS | SAMPLING | DEFINITIONS, **DEFINITIONS[name]},
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


def _refuse(path, message):
    raise DomainError('invalid_request', 422, fields=[issue(path, message)])


class Estimates:
    def __init__(self, store):
        self.store = store
        self.calculations = Calculations(store)

    def read(self, actor, sid, estimate_id):
        result = self.store.receipt(actor, sid, CATEGORY, estimate_id)['result']
        return validate('CalculationEstimateRead2', result, retained=True)

    def page(self, actor, sid, version_id, cursor=None):
        """A calculation version's estimates, newest first, twenty a page."""
        self.calculations.version(actor, sid, version_id)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            boundary = None
            if cursor:
                row = db.execute(
                    'SELECT rowid FROM receipts WHERE scope=? AND category=? AND command_id=?',
                    (sid, CATEGORY, cursor),
                ).fetchone()
                if row is None:
                    raise DomainError('invalid_request', 400)
                boundary = row[0]
            rows = db.execute(
                'SELECT command_id,result FROM receipts WHERE scope=? AND category=? '
                "AND result IS NOT NULL AND json_extract(result,'$.calculation_version_id')=? "
                'AND (CAST(? AS TEXT) IS NULL OR rowid<?) ORDER BY rowid DESC LIMIT ?',
                (sid, CATEGORY, version_id, boundary, boundary, ESTIMATE_PAGE + 1),
            ).fetchall()
        items = [json.loads(row['result']) for row in rows[:ESTIMATE_PAGE]]
        for item in items:
            validate('CalculationEstimateRead2', item, retained=True)
        return dict(
            calculation_version_id=version_id,
            items=items,
            next_cursor=items[-1]['estimate_id'] if len(rows) > ESTIMATE_PAGE else None,
        )

    def build(self, actor, sid, request, *, pinned_runs=None):
        validate('CalculationEstimateRequest1', request)
        version = self.calculations.version(actor, sid, request['calculation_version_id'])
        if version['schema_version'] == '4' and pinned_runs is None:
            _refuse(['calculation_version_id'],
                    'Launch the analysis to build its saved surrogate plan automatically.')
        if self.store.replay(actor, sid, CATEGORY, request['command_id'], request):
            return self.read(actor, sid, request['command_id'])
        content = version['content']
        design = content['design']
        if design['kind'] != 'sampled':
            _refuse(
                ['calculation_version_id'],
                'An estimate needs a sampled calculation version: its design names the input '
                'axes and keeps check points apart.',
            )
        history = History(self.store)
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid, write=True)
            reference = _frozen_configuration(
                db, sid, design['groups'][0]['reference_configuration_revision_id']
            )
            members = content['configuration_revision_ids']
            rows = calculation_runs(db, sid, members, 0, RUN_SCAN + 1)
        if len(rows) > RUN_SCAN:
            raise DomainError('limit_exceeded', 413)
        try:
            outputs = {_key(o['target']): o for o in quantities(reference)[1]}
        except (ValueError, KeyError, TypeError) as exc:
            raise DomainError('corrupt_retained_record', 409) from exc
        targets = [_key(t['target']) for t in request['tolerances']]
        if len(set(targets)) != len(targets) or not set(targets) <= set(outputs):
            _refuse(['tolerances'], 'Name each output of the model version at most once.')
        # The latest recorded run of each member; runs never change the version.
        latest = {}
        for row in rows:
            if row['state'] == 'recorded':
                latest[row['configuration_revision_id']] = row['run_id']
        if pinned_runs is not None:
            available = {r['run_id']: r['configuration_revision_id'] for r in rows
                         if r['state'] == 'recorded'}
            if set(pinned_runs) != set(members) or any(
                available.get(rid) != revision for revision, rid in pinned_runs.items()
            ):
                _refuse(['calculation_version_id'], 'Every pinned member run must be recorded.')
            latest = pinned_runs
        samples, tokens, runtimes = [], [], set()
        groups = [dict(training=[], checks=[]) for _ in design['groups']]
        for point in design['points']:
            revision = point['configuration_revision_id']
            run_id, results_digest, values = latest.get(revision), None, [None] * len(targets)
            if run_id is not None:
                retained = history.retained_projection(actor, sid, run_id)
                results = retained.history['results'] or {}
                results_digest = digest(retained.history['results'])
                runtimes.add(
                    json.dumps(retained.runtime, sort_keys=True)
                )
                tokens.append(retained.token)
                recorded = {_key(o['target']): o for o in results.get('outputs', [])}
                values = [
                    recorded[k]['value']
                    if k in recorded and recorded[k]['availability'] == 'available'
                    else None
                    for k in targets
                ]
            samples.append(
                dict(
                    group=point['group'],
                    partition='training' if point['partition'] == 'training' else 'validation',
                    configuration_revision_id=revision,
                    run_id=run_id,
                    results_digest=results_digest,
                )
            )
            partition = 'training' if point['partition'] == 'training' else 'checks'
            groups[point['group']][partition].append(dict(x=list(point['vector']), y=values))
        if len(runtimes) > 1:
            _refuse(
                ['calculation_version_id'],
                "The version's latest runs used different execution runtimes; an estimate "
                'fits runs of one runtime.',
            )
        tolerances = [[t['absolute'], t['relative']] for t in request['tolerances']]
        work = []
        for index, (group, rows) in enumerate(zip(design['groups'], groups, strict=True)):
            axes = independent_dimensions(group['dimensions'])
            payload = dict(
                bounds=[[d['lower'], d['upper']] for d in axes], **rows, tolerances=tolerances
            )
            identity = digest(
                dict(
                    study_id=sid,
                    calculation_version=version['digest'],
                    group=index,
                    payload=payload,
                    samples=[s for s in samples if s['group'] == index],
                )
            )
            work.append(dict(identity=identity, payload=payload))
        result = dict(
            schema_version='2',
            estimate_id=request['command_id'],
            calculation_id=version['calculation_id'],
            calculation_version_id=version['calculation_version_id'],
            request=deepcopy(request),
            state='pending',
            reason=None,
            original_runtime=json.loads(next(iter(runtimes))) if runtimes else None,
            samples=samples,
            completed_groups=0,
            total_groups=len(work),
            groups=[],
        )
        validate('CalculationEstimateRead2', result, retained=True)
        units = [outputs[k]['units'] for k in targets]

        def accept(db):
            history.recheck(db, actor, sid, tokens)
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
            request=dict(groups=work, units=units),
            attribute=lambda accepted: [('calculation_estimate', accepted['estimate_id'], None)],
        )

    def process_one(self, native):
        with self.store.background_actor(CATEGORY) as admitted:
            return self._process_one(native) if admitted else False

    def _process_one(self, native):
        """Fit one group of the oldest pending estimate; a group is published only with its
        complete assessed output inventory."""
        with self.store.connection(write=True) as db:
            row = db.execute(
                'SELECT scope,command_id,actor_id FROM receipts WHERE category=? '
                "AND state='pending_remote' ORDER BY rowid LIMIT 1",
                (CATEGORY,),
            ).fetchone()
            if row is None:
                return False
            sid, command, actor = row['scope'], row['command_id'], row['actor_id']
            receipt = self.store.command_receipt(db, sid, CATEGORY, command)
            result, saved = receipt['result'], receipt['request']
            try:
                self.store.authorize(db, actor, sid, write=True)
            except DomainError:
                result.update(state='failed', reason='access_lost')
                db.execute(
                    "UPDATE receipts SET state='committed',result=? WHERE scope=? AND category=? "
                    'AND command_id=?',
                    (json.dumps(result), sid, CATEGORY, command),
                )
                return True
            db.execute(
                "UPDATE receipts SET state='dispatching' WHERE scope=? AND category=? "
                'AND command_id=?',
                (sid, CATEGORY, command),
            )
        state = 'committed'
        try:
            index = result['completed_groups']
            group = saved['groups'][index]
            numerical = dict(
                schema_version='3',
                operation='build',
                identity=group['identity'],
                payload=group['payload'],
            )
            computed = native.explore(numerical)
            if (
                computed['request_sha256'] != digest(numerical)
                or computed['result_sha256'] != digest(computed['result'])
                or computed['result']['identity'] != group['identity']
            ):
                raise ValueError('Estimate artifact identity mismatch')
            artifact = computed['result']['artifact']
            if len(artifact['outputs']) != len(result['request']['tolerances']):
                raise ValueError('Complete assessed output inventory required')
            result['groups'].append(
                dict(
                    group=index,
                    identity=group['identity'],
                    computation_runtime=computed['runtime'],
                    artifact_sha256=digest(artifact),
                    outputs=[
                        dict(
                            target=t['target'],
                            units=units,
                            **{k: o[k] for k in ('method', 'reason', 'metrics', 'comparisons')},
                        )
                        for t, units, o in zip(
                            result['request']['tolerances'],
                            saved['units'],
                            artifact['outputs'],
                            strict=True,
                        )
                    ],
                    **{
                        k: computed[k]
                        for k in (
                            'process_uuid',
                            'store_uuid',
                            'artifact_uuid',
                            'request_sha256',
                            'result_sha256',
                        )
                    },
                )
            )
            saved.setdefault('artifacts', []).append(artifact)
            result['completed_groups'] += 1
            if result['completed_groups'] == result['total_groups']:
                result['state'] = (
                    'ready'
                    if any(o['reason'] is None for g in result['groups'] for o in g['outputs'])
                    else 'assessed'
                )
            else:
                result['state'], state = 'building', 'pending_remote'
            validate('CalculationEstimateRead2', result, retained=True)
        except (ValueError, KeyError, TypeError, RuntimeError, OSError, DomainError):
            result.update(state='failed', reason='numerical_unavailable')
            state = 'committed'
        with self.store.connection(write=True) as db:
            db.execute(
                'UPDATE receipts SET state=?,result=?,request=? WHERE scope=? AND category=? '
                "AND command_id=? AND state='dispatching'",
                (state, json.dumps(result), json.dumps(saved), sid, CATEGORY, command),
            )
        return True
