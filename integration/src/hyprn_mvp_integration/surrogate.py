"""Data-only, version-pinned OpenMDAO metamodel adapter in the restricted worker.

OpenMDAO owns every fit and prediction. Its public surrogate classes have no common
serialization API. The closed adapter copies only documented numeric attributes
used by 3.45.1 predict; it never loads pickle, paths, classes or user callbacks.
"""

import math
import time


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 2**53 - 1


def vector(value, size):
    return isinstance(value, list) and len(value) == size and all(map(finite, value))


def check_fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError('Closed numerical data required')


def admit(request):
    check_fields(request, 'schema_version operation identity payload')
    if request['schema_version'] != '3' or request['operation'] not in ('build', 'warm', 'predict'):
        raise ValueError('Unsupported surrogate operation')
    identity = request['identity']
    if (
        not isinstance(identity, str)
        or len(identity) != 64
        or any(c not in '0123456789abcdef' for c in identity)
    ):
        raise ValueError('Exact surrogate identity required')
    payload = request['payload']
    if request['operation'] == 'build':
        check_fields(payload, 'bounds training checks tolerances')
        bounds = payload['bounds']
        if (
            not isinstance(bounds, list)
            or not 1 <= len(bounds) <= 32
            or any(not vector(b, 2) or b[0] >= b[1] for b in bounds)
        ):
            raise ValueError('Explicit finite normalization required')
        tolerances = payload['tolerances']
        if (
            not isinstance(tolerances, list)
            or not 1 <= len(tolerances) <= 32
            or any(not vector(t, 2) or min(t) < 0 for t in tolerances)
        ):
            raise ValueError('Finite per-output tolerances required')
        seen = set()
        for partition, minimum in [('training', 3), ('checks', 2)]:
            rows = payload[partition]
            if not isinstance(rows, list) or not minimum <= len(rows) <= 64:
                raise ValueError('Bounded independent partitions required')
            for row in rows:
                check_fields(row, 'x y')
                if not vector(row['x'], len(bounds)) or tuple(row['x']) in seen:
                    raise ValueError('Distinct complete input vectors required')
                seen.add(tuple(row['x']))
                if any(not lo <= x <= hi for x, (lo, hi) in zip(row['x'], bounds)):
                    raise ValueError('Training domain mismatch')
                if (
                    not isinstance(row['y'], list)
                    or len(row['y']) != len(tolerances)
                    or any(y is not None and not finite(y) for y in row['y'])
                ):
                    raise ValueError('Finite or explicitly missing outputs required')
    elif request['operation'] == 'predict':
        check_fields(payload, 'queries')
        if not isinstance(payload['queries'], list) or not 1 <= len(payload['queries']) <= 33:
            raise ValueError('Bounded query batch required')
    else:
        check_fields(payload, 'artifact')
        admit_artifact(payload['artifact'])
    return request


STATE_KEYS = {
    'response_surface': ('m', 'n', 'betas'),
    'kriging': (
        'n_samples',
        'n_dims',
        'X',
        'X_mean',
        'X_std',
        'Y_mean',
        'Y_std',
        'thetas',
        'alpha',
    ),
}


def encode_state(surrogate, method):
    import numpy as np

    if method == 'response_surface':
        state = dict(m=surrogate.m, n=surrogate.n, betas=surrogate.betas)
    else:
        state = dict(
            n_samples=surrogate.n_samples,
            n_dims=surrogate.n_dims,
            X=surrogate.X,
            X_mean=surrogate.X_mean,
            X_std=surrogate.X_std,
            Y_mean=surrogate.Y_mean,
            Y_std=surrogate.Y_std,
            thetas=surrogate.thetas,
            alpha=surrogate.alpha,
        )
    return {
        name: value.tolist() if isinstance(value, np.ndarray) else value
        for name, value in state.items()
    }


def decode_state(state, method):
    import numpy as np
    import openmdao.api as om

    check_fields(state, ' '.join(STATE_KEYS[method]))
    surrogate = om.ResponseSurface() if method == 'response_surface' else om.KrigingSurrogate()
    if method == 'response_surface':
        surrogate.m, surrogate.n = state['m'], state['n']
        surrogate.betas = np.asarray(state['betas'], dtype=float)
    else:
        surrogate.n_samples, surrogate.n_dims = state['n_samples'], state['n_dims']
        surrogate.X = np.asarray(state['X'], dtype=float)
        surrogate.X_mean = np.asarray(state['X_mean'], dtype=float)
        surrogate.X_std = np.asarray(state['X_std'], dtype=float)
        surrogate.Y_mean = np.asarray(state['Y_mean'], dtype=float)
        surrogate.Y_std = np.asarray(state['Y_std'], dtype=float)
        surrogate.thetas = np.asarray(state['thetas'], dtype=float)
        surrogate.alpha = np.asarray(state['alpha'], dtype=float)
    surrogate.trained = True
    return surrogate


def admit_artifact(artifact):
    check_fields(artifact, 'schema_version openmdao_version bounds training_vectors outputs')
    if artifact['schema_version'] != '1' or artifact['openmdao_version'] != '3.45.1':
        raise ValueError('Unqualified trained-state version')
    bounds, vectors, outputs = artifact['bounds'], artifact['training_vectors'], artifact['outputs']
    if (
        not isinstance(bounds, list)
        or not 1 <= len(bounds) <= 32
        or any(not vector(b, 2) or b[0] >= b[1] for b in bounds)
        or not isinstance(vectors, list)
        or not 3 <= len(vectors) <= 64
        or any(not vector(v, len(bounds)) for v in vectors)
        or len({tuple(v) for v in vectors}) != len(vectors)
    ):
        raise ValueError('Bounded finite training domain required')
    if not isinstance(outputs, list) or not 1 <= len(outputs) <= 32:
        raise ValueError('Output inventory bound')
    for output in outputs:
        check_fields(output, 'method state reason metrics comparisons')
        if output['state'] is None:
            if not isinstance(output['reason'], str):
                raise ValueError('Unavailable output requires reason')
            continue
        method = output['method']
        if method not in STATE_KEYS or output['reason'] is not None:
            raise ValueError('Unassessed state')
        state = output['state']
        check_fields(state, ' '.join(STATE_KEYS[method]))
        n, m = len(bounds), len(vectors)
        shapes = (
            dict(betas=((n + 1) * (n + 2) // 2, 1))
            if method == 'response_surface'
            else dict(
                X=(m, n),
                X_mean=(n,),
                X_std=(n,),
                Y_mean=(1,),
                Y_std=(1,),
                thetas=(n,),
                alpha=(m, 1),
            )
        )
        scalars = dict(m=m, n=n) if method == 'response_surface' else dict(n_samples=m, n_dims=n)
        if any(type(state[k]) is not int or state[k] != v for k, v in scalars.items()):
            raise ValueError('Trained-state dimension mismatch')
        for key, shape in shapes.items():
            data = state[key]
            valid = (
                vector(data, shape[0])
                if len(shape) == 1
                else (
                    isinstance(data, list)
                    and len(data) == shape[0]
                    and all(vector(row, shape[1]) for row in data)
                )
            )
            if not valid:
                raise ValueError('Finite fixed-shape trained arrays required')
        if method == 'kriging' and (min(state['X_std']) <= 0 or min(state['Y_std']) <= 0):
            raise ValueError('Positive trained normalization required')


def build(payload):
    import numpy as np
    import openmdao
    import openmdao.api as om

    if openmdao.__version__ != '3.45.1':
        raise ValueError('Unqualified OpenMDAO version')
    bounds = np.asarray(payload['bounds'])
    lo, scale = bounds[:, 0], bounds[:, 1] - bounds[:, 0]
    training, checks = payload['training'], payload['checks']
    x = (np.asarray([row['x'] for row in training]) - lo) / scale
    # Method comparison uses the first pre-reserved check only. Remaining checks
    # are untouched until selection is frozen; they alone assess publication.
    selection, assessment = checks[:1], checks[1:]
    outputs = []
    for index, (absolute, relative) in enumerate(payload['tolerances']):
        output = dict(
            method=None, state=None, reason='incomplete_samples', metrics=None, comparisons=[]
        )
        outputs.append(output)
        if any(row['y'][index] is None for row in training + checks):
            output['metrics'] = dict(
                assessed_count=0,
                evaluable_count=sum(r['y'][index] is not None for r in assessment),
                failed_count=sum(r['y'][index] is None for r in assessment),
                target_met=False,
                max_absolute_error=None,
                rmse=None,
            )
            continue
        candidates = []
        for method in ('response_surface', 'kriging'):
            minimum = (
                (len(lo) + 1) * (len(lo) + 2) // 2 if method == 'response_surface' else len(lo) + 1
            )
            if len(training) < minimum:
                output['comparisons'].append(
                    dict(method=method, reason='underfunded_design', error=None)
                )
                continue
            problem = om.Problem(reports=False)
            try:
                surrogate = (
                    om.ResponseSurface() if method == 'response_surface' else om.KrigingSurrogate()
                )
                component = om.MetaModelUnStructuredComp()
                for dim in range(len(lo)):
                    component.add_input('x' + str(dim), 0.0, training_data=x[:, dim])
                component.add_output(
                    'y', 0.0, surrogate=surrogate, training_data=[r['y'][index] for r in training]
                )
                problem.model.add_subsystem('estimate', component)
                problem.setup()
                problem.run_model()
                state = encode_state(surrogate, method)
                predicted = float(
                    np.asarray(
                        surrogate.predict((np.asarray(selection[0]['x']) - lo) / scale)
                    ).item()
                )
                error = abs(predicted - selection[0]['y'][index])
                if not finite(predicted) or not finite(error):
                    raise ValueError('Nonfinite selection prediction')
                output['comparisons'].append(dict(method=method, reason=None, error=error))
                candidates.append((error, method, state))
            except (ValueError, RuntimeError, np.linalg.LinAlgError):
                output['comparisons'].append(dict(method=method, reason='fit_failed', error=None))
            finally:
                problem.cleanup()
        if not candidates:
            output['reason'] = 'underfunded_or_failed_fits'
            continue
        _, method, state = min(candidates, key=lambda c: c[0])
        predictor = decode_state(state, method)
        errors, met = [], []
        for row in assessment:
            predicted = float(
                np.asarray(predictor.predict((np.asarray(row['x']) - lo) / scale)).item()
            )
            error = abs(predicted - row['y'][index])
            if not finite(predicted) or not finite(error):
                raise ValueError('Nonfinite assessment')
            errors.append(error)
            met.append(error <= absolute + relative * abs(row['y'][index]))
        output.update(
            method=method,
            metrics=dict(
                assessed_count=len(errors),
                evaluable_count=len(errors),
                failed_count=0,
                max_absolute_error=max(errors),
                rmse=float(np.sqrt(np.mean(np.square(errors)))),
                target_met=all(met),
            ),
        )
        if all(met):
            output.update(state=state, reason=None)
        else:
            output['reason'] = 'observed_tolerance_unmet'
    return dict(
        schema_version='1',
        openmdao_version=openmdao.__version__,
        bounds=payload['bounds'],
        training_vectors=[r['x'] for r in training],
        outputs=outputs,
    )


class WarmModel:
    """Immutable numeric state; no candidate Python modules or cross-case globals."""

    def __init__(self, artifact):
        import numpy as np

        admit_artifact(artifact)
        self.artifact = artifact
        self.bounds = np.asarray(artifact['bounds'])
        self.lo = self.bounds[:, 0]
        self.scale = self.bounds[:, 1] - self.lo
        self.points = (np.asarray(artifact['training_vectors']) - self.lo) / self.scale
        self.predictors = [
            decode_state(o['state'], o['method']) if o['state'] else None
            for o in artifact['outputs']
        ]

    def predict(self, queries):
        import numpy as np
        from scipy.optimize import linprog

        results = []
        for query in queries:
            if not vector(query, len(self.lo)):
                raise ValueError('Full finite input vector required')
            normalized = (np.asarray(query) - self.lo) / self.scale
            reason = None
            if np.any(normalized < 0) or np.any(normalized > 1):
                reason = 'outside_bounds'
            else:
                # Actual convex support, not an enclosing box. This is an
                # eligibility condition, never a universal accuracy guarantee.
                support = linprog(
                    np.zeros(len(self.points)),
                    A_eq=np.vstack([self.points.T, np.ones(len(self.points))]),
                    b_eq=np.append(normalized, 1),
                    bounds=(0, None),
                    method='highs',
                )
                if not support.success:
                    reason = 'outside_sampled_coverage'
            values = []
            for output, predictor in zip(self.artifact['outputs'], self.predictors):
                unavailable = output['reason'] or reason
                value = None
                if unavailable is None:
                    value = float(np.asarray(predictor.predict(normalized)).item())
                    if not finite(value):
                        value, unavailable = None, 'nonfinite_prediction'
                values.append(dict(value=value, reason=unavailable))
            results.append(values)
        return results


def serve():
    """At most eight explicitly warmed immutable groups, 15 minute hard lifetime.

    Transport is the launcher's private stdin/stdout, not a network listener.
    Closing its owning bridge tears down the container. No implicit cold warm.
    """
    import json
    import signal
    import sys
    from .results import _bounded_json

    signal.alarm(900)
    models = {}
    for _ in range(4096):
        raw = sys.stdin.buffer.readline(1048577)
        if not raw:
            return
        try:
            request = _bounded_json(
                raw, size=1048576, depth_limit=16, collection_limit=10000, kind='surrogate'
            )
            admit(request)
            if request['operation'] == 'warm':
                identity = request['identity']
                if identity not in models and len(models) >= 8:
                    raise ValueError('Warm version capacity reached')
                models[identity] = WarmModel(request['payload']['artifact'])
                result = dict(identity=identity, warmed=True)
            elif request['operation'] == 'predict' and request['identity'] in models:
                result = dict(
                    identity=request['identity'],
                    values=models[request['identity']].predict(request['payload']['queries']),
                )
            else:
                raise ValueError('Explicit warm required for this exact version')
            response = dict(data=result)
        except (ValueError, TypeError, KeyError, RuntimeError):
            response = dict(error='surrogate_unavailable')
        print(json.dumps(response, allow_nan=False), flush=True)


if __name__ == '__main__':
    serve()
