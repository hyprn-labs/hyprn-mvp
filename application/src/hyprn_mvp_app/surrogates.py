"""Immutable assessed metamodel versions over retained original-model samples.

The application owns authorization, identities and receipts. Only the existing
native bridge computes; interaction queries never train or submit original runs.
"""

from copy import deepcopy
import base64
import json
import time

from jsonschema import Draft202012Validator, FormatChecker

from .contracts import DomainError, definitions, digest, canonical
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
from .exploration_design import DEFINITIONS as DESIGNS, Designs, independent_dimensions, on_step
from .sampling import DEFINITIONS as SAMPLES, Samples, array, nullable, VALUE
from .history import History


METRICS = _object(
    dict(
        assessed_count=dict(type='integer', minimum=0, maximum=64),
        evaluable_count=dict(type='integer', minimum=0, maximum=64),
        failed_count=dict(type='integer', minimum=0, maximum=64),
        max_absolute_error=nullable(_NUMBER),
        rmse=nullable(_NUMBER),
        target_met=dict(type='boolean'),
    )
)
OUTPUT = _object(
    dict(
        target=_ref('PortRef'),
        units=_TEXT,
        method=nullable(dict(enum=['response_surface', 'kriging'])),
        reason=nullable(_TEXT),
        metrics=nullable(METRICS),
        comparisons=array(
            _object(
                dict(
                    method=dict(enum=['response_surface', 'kriging']),
                    reason=nullable(_TEXT),
                    error=nullable(_NUMBER),
                )
            ),
            2,
        ),
    )
)
DEFINITIONS = {
    'ExplorationSurrogateArtifact1': _object(
        dict(
            surrogate_version_id=_ID,
            combination=dict(type='integer', minimum=0, maximum=7),
            sha256=_HASH,
            size=dict(type='integer', minimum=0, maximum=1048576),
            media_type=dict(const='application/json'),
            bytes_base64=dict(type='string', maxLength=1398104),
        )
    ),
    'ExplorationBuildRequest1': _object(
        dict(schema_version=dict(const='1'), command_id=_ID, design_id=_ID, sample_operation_id=_ID)
    ),
    'ExplorationWarmRequest1': _object(dict(command_id=_ID)),
    'ExplorationWarmOperation1': _object(
        dict(
            command_id=_ID,
            surrogate_version_id=_ID,
            state=dict(enum=['pending', 'ready', 'failed']),
            reason=nullable(_TEXT),
        )
    ),
    'ExplorationSurrogate1': _object(
        dict(
            schema_version=dict(const='1'),
            surrogate_version_id=_ID,
            design_id=_ID,
            sample_operation_id=_ID,
            answer_version_id=_ID,
            identity=_HASH,
            state=dict(enum=['pending', 'building', 'ready', 'assessed', 'failed', 'cancelled']),
            reason=nullable(_TEXT),
            completed_groups=dict(type='integer', minimum=0, maximum=8),
            total_groups=dict(type='integer', minimum=1, maximum=8),
            groups=array(
                _object(
                    dict(
                        combination=dict(type='integer', minimum=0, maximum=7),
                        identity=_HASH,
                        original_runtime=_ref('ExplorationRuntime1'),
                        computation_runtime=_ref('ExplorationRuntime1'),
                        process_uuid=_ID,
                        store_uuid=_ID,
                        artifact_uuid=_ID,
                        request_sha256=_HASH,
                        result_sha256=_HASH,
                        artifact_sha256=_HASH,
                        outputs=array(OUTPUT, 32, 1),
                    )
                ),
                8,
            ),
        )
    ),
    'ExplorationQuery1': _object(
        dict(
            schema_version=dict(const='1'),
            selection_token=_ID,
            combination=dict(type='integer', minimum=0, maximum=7),
            inputs=array(VALUE, 32, 1),
            axis=nullable(_ref('PortRef')),
            curve_points=dict(type='integer', minimum=0, maximum=32),
        )
    ),
    'ExplorationQueryResult1': _object(
        dict(
            schema_version=dict(const='1'),
            selection_token=_ID,
            surrogate_version_id=_ID,
            identity=_HASH,
            vectors=array(array(VALUE, 32, 1), 33, 1),
            outputs=array(
                _object(
                    dict(
                        target=_ref('PortRef'),
                        units=_TEXT,
                        values=array(
                            _object(
                                dict(
                                    value=nullable(_NUMBER),
                                    reason=nullable(_TEXT),
                                    kind=dict(enum=['estimated', 'calculated', 'unavailable']),
                                    run_id=nullable(_ID),
                                )
                            ),
                            33,
                            1,
                        ),
                    )
                ),
                32,
                1,
            ),
        )
    ),
}


def validate(name, value):
    validator = Draft202012Validator(
        {
            '$defs': definitions() | EXPLORATION | DESIGNS | SAMPLES | DEFINITIONS,
            **DEFINITIONS[name],
        },
        format_checker=FormatChecker(),
    )
    if not validator.is_valid(value):
        raise DomainError('invalid_request', 400)


class Surrogates:
    def __init__(self, store, configurations=None):
        self.store, self.configurations = store, configurations

    def read(self, actor, sid, version):
        result = self.store.receipt(actor, sid, 'exploration_surrogate', version)['result']
        validate('ExplorationSurrogate1', result)
        return result

    def page(self, actor, sid, answer, cursor=None):
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            boundary = None
            if cursor:
                row = db.execute(
                    "SELECT rowid FROM receipts WHERE scope=? AND category='exploration_surrogate' "
                    'AND command_id=?',
                    (sid, cursor),
                ).fetchone()
                if row is None:
                    raise DomainError('invalid_request', 400)
                boundary = row[0]
            rows = db.execute(
                'SELECT command_id,result FROM receipts WHERE scope=? '
                "AND category='exploration_surrogate' "
                "AND json_extract(result,'$.answer_version_id')=? "
                'AND (? IS NULL OR rowid<?) ORDER BY rowid DESC LIMIT 21',
                (sid, answer, boundary, boundary),
            ).fetchall()
            return [json.loads(r['result']) for r in rows[:20]], rows[19]['command_id'] if len(
                rows
            ) > 20 else None

    def artifact(self, actor, sid, version, combination):
        receipt = self.store.receipt(actor, sid, 'exploration_surrogate', version)
        if receipt['result']['state'] not in ('ready', 'assessed') or not 0 <= combination < len(
            receipt['request']['artifacts']
        ):
            raise DomainError('resource_not_found', 404)
        artifact = receipt['request']['artifacts'][combination]
        expected = receipt['result']['groups'][combination]['artifact_sha256']
        raw = canonical(artifact)
        if digest(artifact) != expected or len(raw) > 1048576:
            raise DomainError('corrupt_retained_record', 409)
        return dict(
            surrogate_version_id=version,
            combination=combination,
            sha256=expected,
            size=len(raw),
            media_type='application/json',
            bytes_base64=base64.b64encode(raw).decode(),
        )

    def build(self, actor, sid, request):
        validate('ExplorationBuildRequest1', request)
        old = self.store.replay(actor, sid, 'exploration_surrogate', request['command_id'], request)
        if old:
            return self.read(actor, sid, request['command_id'])
        design = Designs(self.store, self.configurations).read(actor, sid, request['design_id'])
        samples = Samples(self.store, self.configurations, None).status(
            actor, sid, request['sample_operation_id']
        )
        if samples['state'] not in ('complete', 'limited', 'cancelled'):
            raise DomainError('reference_conflict', 409)
        combos = design['request']['combinations']
        original_combos = samples['request']['combinations']
        if len(combos) != len(original_combos):
            raise DomainError('reference_conflict', 409)
        resolved, tokens = [], []
        history = History(self.store)
        for index, (combo, sampled) in enumerate(zip(combos, original_combos)):
            if any(
                combo[k] != sampled[k]
                for k in ('categories', 'configuration_revision_id', 'dimensions')
            ):
                raise DomainError('reference_conflict', 409)
            basis = Explorations(self.store, self.configurations).basis(
                actor,
                sid,
                design['request']['answer_version_id'],
                combo['configuration_revision_id'],
            )
            axes = independent_dimensions(combo['dimensions'])
            frozen = self.configurations.read(actor, sid, combo['configuration_revision_id'])
            targets = [_key(t['target']) for t in sampled['tolerances']]
            if set(targets) != {_key(o['target']) for o in basis['outputs']}:
                raise DomainError('invalid_request', 400)
            rows = dict(training=[], checks=[])
            originals = []
            for point in samples['points']:
                if point['combination'] != index:
                    continue
                values = {_key(v['target']): v for v in point['inputs']}
                if any(
                    not d['lower'] <= values[_key(d['target'])]['value'] <= d['upper'] for d in axes
                ):
                    continue
                outputs = {}
                if point['run_id'] and point['state'] == 'recorded':
                    retained = history.retained(actor, sid, point['run_id'])
                    manifest, h = retained.payload['bundle']['manifest'], retained.history
                    if (
                        manifest['runtime'] != samples['runtime']
                        or h['model_snapshot']['digest'] != basis['model_digest']
                        or h['configuration']['numerical'] != frozen['configuration']['numerical']
                        or digest(h['results']) != point['results_digest']
                    ):
                        raise DomainError('corrupt_retained_record', 409)
                    actual = sorted(
                        [
                            dict(target=v['target'], value=v['value'], units=v['units'])
                            for v in h['configuration']['inputs']
                        ],
                        key=lambda v: _key(v['target']),
                    )
                    if actual != sorted(point['inputs'], key=lambda v: _key(v['target'])):
                        raise DomainError('corrupt_retained_record', 409)
                    outputs = {
                        _key(o['target']): o for o in (h['results'] or {}).get('outputs', [])
                    }
                    tokens.append(retained.token)
                y = [
                    outputs[k]['value']
                    if k in outputs and outputs[k]['availability'] == 'available'
                    else None
                    for k in targets
                ]
                rows['training' if point['partition'] == 'training' else 'checks'].append(
                    dict(x=[values[_key(d['target'])]['value'] for d in axes], y=y)
                )
                originals.append(
                    dict(
                        inputs=point['inputs'],
                        values=y,
                        run_id=point['run_id'],
                        state=point['state'],
                        identity=point['identity'],
                    )
                )
            if len(rows['training']) < 3 or len(rows['checks']) < 2:
                raise DomainError('invalid_request', 400)
            payload = dict(
                bounds=[[d['lower'], d['upper']] for d in axes],
                **rows,
                tolerances=[[t['absolute'], t['relative']] for t in sampled['tolerances']],
            )
            identity = digest(
                dict(
                    study_id=sid,
                    design=design['digest'],
                    sample_operation=samples,
                    combination=index,
                    basis=basis,
                    payload=payload,
                )
            )
            resolved.append(
                dict(
                    identity=identity,
                    payload=payload,
                    basis=basis,
                    combination=combo,
                    targets=sampled['tolerances'],
                    originals=originals,
                )
            )
        result = dict(
            schema_version='1',
            surrogate_version_id=request['command_id'],
            design_id=request['design_id'],
            sample_operation_id=request['sample_operation_id'],
            answer_version_id=design['request']['answer_version_id'],
            identity=digest([r['identity'] for r in resolved]),
            state='pending',
            reason=None,
            completed_groups=0,
            total_groups=len(resolved),
            groups=[],
        )

        def accept(db):
            history.recheck(db, actor, sid, tokens)
            if db.execute(
                "SELECT 1 FROM receipts WHERE scope=? AND category='exploration_surrogate' "
                "AND state IN ('pending_remote','dispatching')",
                (sid,),
            ).fetchone():
                raise DomainError('limit_exceeded', 429)
            return result

        return self.store.command(
            actor,
            sid,
            'exploration_surrogate',
            request['command_id'],
            request,
            accept,
            receipt_state='pending_remote',
            request=dict(groups=resolved, original_runtime=samples['runtime'], artifacts=[]),
        )

    def warm(self, actor, sid, version, body):
        validate('ExplorationWarmRequest1', body)
        value = self.read(actor, sid, version)
        if value['state'] not in ('ready', 'assessed'):
            raise DomainError('reference_conflict', 409)

        def accept(db):
            if db.execute(
                "SELECT 1 FROM receipts WHERE scope=? AND category='exploration_warm' "
                "AND state IN ('pending_remote','dispatching')",
                (sid,),
            ).fetchone():
                raise DomainError('limit_exceeded', 429)
            return dict(
                command_id=body['command_id'],
                surrogate_version_id=version,
                state='pending',
                reason=None,
            )

        return self.store.command(
            actor,
            sid,
            'exploration_warm',
            body['command_id'],
            dict(version=version, **body),
            accept,
            receipt_state='pending_remote',
            request=dict(version=version),
        )

    def warm_status(self, actor, sid, command):
        return self.store.receipt(actor, sid, 'exploration_warm', command)['result']

    def cancel(self, actor, sid, version, body):
        validate('ExplorationWarmRequest1', body)

        def apply(db):
            row = self.store.command_receipt(db, sid, 'exploration_surrogate', version)
            if row is None:
                raise DomainError('resource_not_found', 404)
            result = row['result']
            if result['state'] in ('pending', 'building'):
                result.update(state='cancelled', reason='cancelled')
                db.execute(
                    "UPDATE receipts SET state='committed',result=? WHERE scope=? "
                    "AND category='exploration_surrogate' AND command_id=?",
                    (json.dumps(result), sid, version),
                )
            return result

        return self.store.command(
            actor,
            sid,
            'exploration_cancel',
            body['command_id'],
            dict(version=version, **body),
            apply,
        )

    def query(self, actor, sid, version, request):
        validate('ExplorationQuery1', request)
        if type(request['combination']) is not int or type(request['curve_points']) is not int:
            raise DomainError('invalid_request', 400)
        receipt = self.store.receipt(actor, sid, 'exploration_surrogate', version)
        result, saved = receipt['result'], receipt['request']
        index = request['combination']
        if result['state'] not in ('ready', 'assessed') or index >= len(saved['groups']):
            raise DomainError('reference_conflict', 409)
        group = saved['groups'][index]
        dimensions = group['combination']['dimensions']
        values = {_key(v['target']): v for v in request['inputs']}
        if len(values) != len(request['inputs']) or set(values) != {
            _key(d['target']) for d in dimensions
        }:
            raise DomainError('invalid_request', 400)
        if any(
            values[_key(d['target'])]['units'] != d['units']
            or not on_step(values[_key(d['target'])]['value'], d)
            for d in dimensions
        ):
            raise DomainError('invalid_request', 400)
        # Declared covary controls describe one independent coordinate. A full
        # vector inconsistent with that mapping is rejected, never silently fixed.
        axes = independent_dimensions(dimensions)
        for axis in axes:
            if axis['covary_group']:
                fraction = (values[_key(axis['target'])]['value'] - axis['lower']) / (
                    axis['upper'] - axis['lower']
                )
                for d in dimensions:
                    if d['covary_group'] == axis['covary_group']:
                        expected = d['lower'] + fraction * (d['upper'] - d['lower'])
                        if abs(values[_key(d['target'])]['value'] - expected) > 1e-10 * max(
                            1, abs(expected)
                        ):
                            raise DomainError('invalid_request', 400)
        vectors = [request['inputs']]
        if request['axis'] is not None and request['curve_points']:
            axis = next((d for d in dimensions if d['target'] == request['axis']), None)
            if axis is None or request['curve_points'] < 2:
                raise DomainError('invalid_request', 400)
            for n in range(request['curve_points']):
                fraction = n / (request['curve_points'] - 1)
                point = deepcopy(request['inputs'])
                for value in point:
                    d = next(d for d in dimensions if d['target'] == value['target'])
                    if d is axis or (
                        axis['covary_group'] and d['covary_group'] == axis['covary_group']
                    ):
                        v = d['lower'] + fraction * (d['upper'] - d['lower'])
                        if d['step'] is not None:
                            v = d['lower'] + round((v - d['lower']) / d['step']) * d['step']
                        value['value'] = v
                vectors.append(point)
        queries = [
            [next(v['value'] for v in point if v['target'] == d['target']) for d in axes]
            for point in vectors
        ]
        numerical = dict(
            schema_version='3',
            operation='predict',
            identity=group['identity'],
            payload=dict(queries=queries),
        )
        query_id = request['selection_token']
        deadline = time.time() + 2
        with self.store.connection(write=True) as db:
            self.store.authorize(db, actor, sid)
            # These interaction messages are explicitly disposable, unlike build
            # receipts and original records. Bound pending work by actor/study.
            db.execute(
                "DELETE FROM receipts WHERE category='exploration_query' AND "
                "(json_extract(request,'$.deadline')<? OR (scope=? AND actor_id=?))",
                (time.time(), sid, actor),
            )
            db.execute(
                'INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)',
                (
                    sid,
                    'exploration_query',
                    query_id,
                    actor,
                    digest(request),
                    'pending_remote',
                    None,
                    None,
                    json.dumps(
                        dict(
                            numerical=numerical,
                            deadline=deadline,
                            runtime=result['groups'][index]['computation_runtime'],
                        )
                    ),
                ),
            )
        response = None
        while time.time() < deadline:
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid)
                row = self.store.command_receipt(db, sid, 'exploration_query', query_id)
                if row is None:
                    raise DomainError('backend_unavailable', 503)
                if row['state'] == 'committed':
                    response = row['result']
                    break
                if row['state'] == 'rejected':
                    break
            time.sleep(0.005)
        with self.store.connection(write=True) as db:
            db.execute(
                "DELETE FROM receipts WHERE scope=? AND category='exploration_query' "
                'AND command_id=?',
                (sid, query_id),
            )
        if response is None:
            raise DomainError('backend_unavailable', 503)
        outputs = []
        for n, target in enumerate(group['targets']):
            port = next(o for o in group['basis']['outputs'] if o['target'] == target['target'])
            output = dict(target=target['target'], units=port['units'], values=[])
            outputs.append(output)
            for vi, point in enumerate(vectors):
                exact = next(
                    (
                        p
                        for p in group['originals']
                        if sorted(p['inputs'], key=lambda v: _key(v['target']))
                        == sorted(point, key=lambda v: _key(v['target']))
                    ),
                    None,
                )
                if exact is not None:
                    value = exact['values'][n]
                    output['values'].append(
                        dict(
                            value=value,
                            reason=None if value is not None else 'original_unavailable',
                            kind='calculated' if value is not None else 'unavailable',
                            run_id=exact['run_id'],
                        )
                    )
                else:
                    numerical_value = response['values'][vi][n]
                    output['values'].append(
                        dict(
                            **numerical_value,
                            kind='estimated'
                            if numerical_value['value'] is not None
                            else 'unavailable',
                            run_id=None,
                        )
                    )
        value = dict(
            schema_version='1',
            selection_token=query_id,
            surrogate_version_id=version,
            identity=group['identity'],
            vectors=vectors,
            outputs=outputs,
        )
        validate('ExplorationQueryResult1', value)
        return value

    def process_one(self, native, *, lane=None):
        with self.store.connection(write=True) as db:
            categories = (
                "('exploration_query','exploration_warm')"
                if lane == 'query'
                else "('exploration_surrogate')"
                if lane == 'build'
                else "('exploration_query','exploration_warm','exploration_surrogate')"
            )
            row = db.execute(
                'SELECT * FROM receipts WHERE category IN '
                + categories
                + " AND state='pending_remote' "
                "ORDER BY CASE category WHEN 'exploration_query' THEN 0 "
                "WHEN 'exploration_warm' THEN 1 ELSE 2 END,rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return False
            sid, actor, category, command = (
                row[k] for k in ('scope', 'actor_id', 'category', 'command_id')
            )
            receipt = self.store.command_receipt(db, sid, category, command)
            result, saved = receipt['result'], receipt['request']
            try:
                self.store.authorize(db, actor, sid, write=category != 'exploration_query')
            except DomainError:
                db.execute(
                    'UPDATE receipts SET state=? WHERE scope=? AND category=? AND command_id=?',
                    ('rejected', sid, category, command),
                )
                return True
            db.execute(
                'UPDATE receipts SET state=? WHERE scope=? AND category=? AND command_id=?',
                ('dispatching', sid, category, command),
            )
        state = 'committed'
        try:
            if category == 'exploration_query':
                if time.time() > saved['deadline']:
                    raise RuntimeError('Superseded interaction')
                result = native.surrogate(saved['numerical'], saved['runtime'])
            elif category == 'exploration_warm':
                version = self.store.receipt(actor, sid, 'exploration_surrogate', saved['version'])
                for group, artifact, public in zip(
                    version['request']['groups'],
                    version['request']['artifacts'],
                    version['result']['groups'],
                ):
                    if digest(artifact) != public['artifact_sha256']:
                        raise ValueError('Corrupt surrogate artifact')
                    native.surrogate(
                        dict(
                            schema_version='3',
                            operation='warm',
                            identity=group['identity'],
                            payload=dict(artifact=artifact),
                        ),
                        public['computation_runtime'],
                    )
                result.update(state='ready')
            else:
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
                    raise ValueError('Surrogate artifact identity mismatch')
                artifact = computed['result']['artifact']
                if len(artifact['outputs']) != len(group['targets']):
                    raise ValueError('Complete assessed output inventory required')
                saved['artifacts'].append(artifact)
                outputs = [
                    dict(
                        target=t['target'],
                        units=next(
                            o['units']
                            for o in group['basis']['outputs']
                            if o['target'] == t['target']
                        ),
                        **{k: o[k] for k in ('method', 'reason', 'metrics', 'comparisons')},
                    )
                    for t, o in zip(group['targets'], artifact['outputs'])
                ]
                result['groups'].append(
                    dict(
                        combination=index,
                        identity=group['identity'],
                        original_runtime=saved['original_runtime'],
                        computation_runtime=computed['runtime'],
                        artifact_sha256=digest(artifact),
                        outputs=outputs,
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
                result['completed_groups'] += 1
                if result['completed_groups'] == result['total_groups']:
                    result['state'] = (
                        'ready'
                        if any(o['reason'] is None for g in result['groups'] for o in g['outputs'])
                        else 'assessed'
                    )
                else:
                    result['state'], state = 'building', 'pending_remote'
                validate('ExplorationSurrogate1', result)
        except (ValueError, RuntimeError, OSError, DomainError):
            if result is not None:
                result.update(state='failed', reason='numerical_unavailable')
            state = 'rejected' if category == 'exploration_query' else 'committed'
        with self.store.connection(write=True) as db:
            # A cancellation during fitting wins; no partial publication.
            db.execute(
                'UPDATE receipts SET state=?,result=?,request=? WHERE scope=? AND category=? '
                "AND command_id=? AND state='dispatching'",
                (state, json.dumps(result), json.dumps(saved), sid, category, command),
            )
        return True
