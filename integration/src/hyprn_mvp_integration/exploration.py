"""Bounded, data-only exploration calculations inside the restricted worker.

No candidate source, path, serialized estimator or executable payload is accepted.
Original-model evaluations remain separate fresh scalar calculations.
"""

import hashlib
import json
import math
from pathlib import Path
import sys
import time


def finite(value):
    return type(value) in (int, float) and abs(value) <= 2**53 - 1 and math.isfinite(value)


def admit_request(request):
    if isinstance(request, dict) and request.get('schema_version') == '3':
        from .surrogate import admit

        return admit(request)
    if isinstance(request, dict) and request.get('schema_version') == '2':
        return admit_extension(request)
    if not isinstance(request, dict) or set(request) != {
        'schema_version',
        'operation',
        'identity',
        'bounds',
        'seed',
        'training_count',
        'check_count',
        'training',
        'checks',
        'queries',
        'tolerances',
        'method',
    }:
        raise ValueError('Closed exploration request required')
    if request['schema_version'] != '1' or request['operation'] not in ('design', 'fit_predict'):
        raise ValueError('Unsupported exploration operation')
    if request['method'] not in ('response_surface', 'kriging'):
        raise ValueError('Unsupported surrogate method')
    if (
        not isinstance(request['identity'], str)
        or len(request['identity']) != 64
        or any(c not in '0123456789abcdef' for c in request['identity'])
    ):
        raise ValueError('Exact input identity required')
    if type(request['seed']) is not int or not 0 <= request['seed'] < 2**32:
        raise ValueError('Explicit bounded seed required')
    bounds = request['bounds']
    # This tracer supports an assessed one-dimensional slice, never a claim of
    # coverage of a multidimensional box. Other free inputs remain exactly fixed.
    if (
        not isinstance(bounds, list)
        or len(bounds) != 1
        or any(
            not isinstance(b, list) or len(b) != 2 or not all(map(finite, b)) or b[0] >= b[1]
            for b in bounds
        )
    ):
        raise ValueError('One finite increasing slice bound required')
    for key, low in (('training_count', 3), ('check_count', 2)):
        if type(request[key]) is not int or not low <= request[key] <= 16:
            raise ValueError('Explicit bounded sample counts required')
    tolerances = request['tolerances']
    if (
        not isinstance(tolerances, list)
        or not 1 <= len(tolerances) <= 32
        or any(
            not isinstance(t, list) or len(t) != 2 or not all(map(finite, t)) or min(t) < 0
            for t in tolerances
        )
    ):
        raise ValueError('Per-output absolute and relative tolerances required')
    for partition in ('training', 'checks'):
        rows = request[partition]
        count = request['training_count' if partition == 'training' else 'check_count']
        if not isinstance(rows, list) or len(rows) != (
            0 if request['operation'] == 'design' else count
        ):
            raise ValueError('Exact partition count required')
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'x', 'y'}:
                raise ValueError('Closed sample row required')
            if (
                not isinstance(row['y'], list)
                or len(row['y']) != len(tolerances)
                or any(y is not None and not finite(y) for y in row['y'])
            ):
                raise ValueError('Finite or explicitly unavailable outputs required')
    queries = request['queries']
    if not isinstance(queries, list) or not 1 <= len(queries) <= 33:
        raise ValueError('Bounded query batch required')
    vectors = queries + [r['x'] for p in ('training', 'checks') for r in request[p]]
    for x in vectors:
        if not isinstance(x, list) or len(x) != 1 or not finite(x[0]):
            raise ValueError('Finite explicit slice vector required')
        if not bounds[0][0] <= x[0] <= bounds[0][1]:
            raise ValueError('Extrapolation is unavailable')
    samples = [r['x'][0] for p in ('training', 'checks') for r in request[p]]
    if len(samples) != len(set(samples)):
        raise ValueError('Training and independent checks must be distinct')
    return request


def calculate(request):
    admit_request(request)
    if request['schema_version'] == '3':
        from .surrogate import build

        if request['operation'] != 'build':
            raise ValueError('Warm operations require an existing bounded session')
        return dict(identity=request['identity'], artifact=build(request['payload']))
    if request['schema_version'] == '2':
        return extend_design(request)
    import numpy as np
    import openmdao.api as om
    import openmdao
    import scipy
    from scipy.stats import qmc

    if openmdao.__version__ != '3.45.1':
        raise ValueError('Unqualified OpenMDAO version')
    start = time.monotonic()
    lo, hi = request['bounds'][0]
    count = request['training_count'] + request['check_count']
    # One seeded design is partitioned before any physics evaluation. Endpoints
    # belong to training so predictions never extend beyond sampled coordinates.
    design = qmc.LatinHypercube(d=1, seed=request['seed']).random(count - 2)
    vectors = [[lo], [hi]] + qmc.scale(design, [lo], [hi]).tolist()
    result = dict(
        schema_version='1',
        identity=request['identity'],
        method=request['method'],
        versions=dict(openmdao=openmdao.__version__, scipy=scipy.__version__, numpy=np.__version__),
        training_vectors=vectors[: request['training_count']],
        check_vectors=vectors[request['training_count'] :],
        outputs=[],
    )
    if request['operation'] == 'fit_predict':
        if [r['x'] for r in request['training']] != result['training_vectors'] or [
            r['x'] for r in request['checks']
        ] != result['check_vectors']:
            raise ValueError('Samples must match the exact seeded partition')
        x = np.array([r['x'] for r in request['training']])
        x = (x - lo) / (hi - lo)
        for index, (absolute, relative) in enumerate(request['tolerances']):
            output = dict(
                state='unavailable',
                reason=None,
                values=[None] * len(request['queries']),
                assessed_count=0,
                evaluable_count=0,
                failed_count=0,
                max_absolute_error=None,
                rmse=None,
                target_met=False,
            )
            result['outputs'].append(output)
            output['evaluable_count'] = sum(
                row['y'][index] is not None for row in request['checks']
            )
            output['failed_count'] = sum(row['y'][index] is None for row in request['checks'])
            all_rows = request['training'] + request['checks']
            if any(row['y'][index] is None for row in all_rows):
                output['reason'] = 'incomplete_samples'
                output['failed_count'] = sum(row['y'][index] is None for row in request['checks'])
                continue
            problem = om.Problem(reports=False)
            try:
                surrogate = (
                    om.ResponseSurface()
                    if request['method'] == 'response_surface'
                    else om.KrigingSurrogate(eval_rmse=False)
                )
                component = om.MetaModelUnStructuredComp(default_surrogate=surrogate)
                component.add_input('x', 0.0, training_data=x[:, 0])
                component.add_output(
                    'y', 0.0, training_data=[r['y'][index] for r in request['training']]
                )
                problem.model.add_subsystem('estimate', component)
                problem.setup()

                def predict(vector):
                    problem.set_val('estimate.x', (vector[0] - lo) / (hi - lo))
                    problem.run_model()
                    value = float(problem.get_val('estimate.y').item())
                    if not finite(value):
                        raise ValueError('Nonfinite prediction')
                    return value

                errors, met = [], []
                for row in request['checks']:
                    reference = row['y'][index]
                    error = abs(predict(row['x']) - reference)
                    errors.append(error)
                    met.append(error <= absolute + relative * abs(reference))
                output.update(
                    assessed_count=len(errors),
                    evaluable_count=len(errors),
                    max_absolute_error=max(errors),
                    rmse=float(np.sqrt(np.mean(np.square(errors)))),
                    target_met=all(met),
                )
                if not all(met):
                    output['reason'] = 'observed_tolerance_unmet'
                    continue
                output.update(state='estimated', values=[predict(q) for q in request['queries']])
            except (ValueError, RuntimeError, np.linalg.LinAlgError):
                output.update(
                    state='unavailable',
                    reason='fit_or_prediction_failed',
                    values=[None] * len(request['queries']),
                    target_met=False,
                )
            finally:
                problem.cleanup()
    result['compute_seconds'] = time.monotonic() - start
    return result


def admit_extension(request):
    """Closed bounded joint designs; no source, paths or executable model state."""
    if set(request) != {'schema_version', 'operation', 'identity', 'seed', 'groups'}:
        raise ValueError('Closed extension request required')
    if (
        request['operation'] != 'extend_design'
        or type(request['seed']) is not int
        or not 0 <= request['seed'] < 2**32
    ):
        raise ValueError('Explicit extension seed required')
    if (
        not isinstance(request['identity'], str)
        or len(request['identity']) != 64
        or any(c not in '0123456789abcdef' for c in request['identity'])
    ):
        raise ValueError('Exact design identity required')
    groups = request['groups']
    if not isinstance(groups, list) or not 1 <= len(groups) <= 8:
        raise ValueError('Bounded category groups required')
    total = 0
    for group in groups:
        if not isinstance(group, dict) or set(group) != {
            'bounds',
            'training_count',
            'check_count',
            'retained',
        }:
            raise ValueError('Closed design group required')
        bounds = group['bounds']
        if (
            not isinstance(bounds, list)
            or not 1 <= len(bounds) <= 32
            or any(
                not isinstance(b, list) or len(b) != 2 or not all(map(finite, b)) or b[0] >= b[1]
                for b in bounds
            )
        ):
            raise ValueError('Finite joint bounds required')
        for name, minimum in [('training_count', 3), ('check_count', 2)]:
            if type(group[name]) is not int or not minimum <= group[name] <= 64:
                raise ValueError('Bounded partition counts required')
        retained = group['retained']
        if not isinstance(retained, list) or len(retained) > 128:
            raise ValueError('Bounded retained design required')
        vectors = set()
        for row in retained:
            if (
                not isinstance(row, dict)
                or set(row) != {'partition', 'vector'}
                or row['partition'] not in ('training', 'check')
            ):
                raise ValueError('Exact retained partition required')
            vector = row['vector']
            if (
                not isinstance(vector, list)
                or len(vector) != len(bounds)
                or not all(map(finite, vector))
                or tuple(vector) in vectors
            ):
                raise ValueError('Distinct finite retained vector required')
            vectors.add(tuple(vector))
        total += sum(
            max(group[count], sum(r['partition'] == partition for r in retained))
            for partition, count in [('training', 'training_count'), ('check', 'check_count')]
        )
    if total > 128:
        raise ValueError('Design point cap exceeded')
    return request


def extend_design(request):
    """Append seeded LHS batches; retained coordinates/partitions never change.

    The union is a sequence of LHS batches, not a claim of one re-stratified LHS.
    Independent check points are reserved before any original evaluation.
    """
    from scipy.stats import qmc
    import scipy
    import numpy as np

    start = time.monotonic()
    groups = []
    for index, group in enumerate(request['groups']):
        rows = list(group['retained'])
        seen = {tuple(r['vector']) for r in rows}
        seed = np.random.SeedSequence([request['seed'], index, len(rows)])
        sampler = qmc.LatinHypercube(d=len(group['bounds']), rng=np.random.default_rng(seed))
        lo, hi = zip(*group['bounds'], strict=True)
        for partition, count in [
            ('training', group['training_count']),
            ('check', group['check_count']),
        ]:
            missing = max(0, count - sum(r['partition'] == partition for r in rows))
            for _ in range(4):
                if not missing:
                    break
                for vector in qmc.scale(sampler.random(missing), lo, hi).tolist():
                    if tuple(vector) not in seen:
                        seen.add(tuple(vector))
                        rows.append(dict(partition=partition, vector=vector))
                        missing -= 1
            if missing:
                raise ValueError('Representable distinct sample space exhausted')
        groups.append(rows)
    return dict(
        schema_version='2',
        identity=request['identity'],
        groups=groups,
        scipy_version=scipy.__version__,
        compute_seconds=time.monotonic() - start,
    )


def main():
    raw = Path(sys.argv[1]).read_bytes()
    if len(raw) > 131072 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
        raise ValueError('Exact bounded data artifact required')
    # The independent strict worker JSON reader rejects duplicate keys/nonfinite
    # data before numerical imports, including for direct container invocation.
    from .results import _bounded_json

    request = _bounded_json(
        raw, size=131072, depth_limit=12, collection_limit=2000, kind='exploration'
    )
    print('EXPLORATION_RESULT=' + json.dumps(calculate(request), allow_nan=False))


if __name__ == '__main__':
    main()
