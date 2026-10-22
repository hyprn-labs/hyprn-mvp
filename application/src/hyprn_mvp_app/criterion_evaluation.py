"""Criterion evaluation: a run's recorded outputs against study criteria (ADR-0010).

Pure and dependency-free. The comparison is the worker's ``evaluate_criteria`` without unit
conversion, which a criterion binding makes unnecessary (units must be equal); a parity test
pins the two. Constraints read met, not met or unresolved; objectives report the measured
value or are unresolved. Nothing here infers convergence, applicability or validity.
"""

import math
import operator

COMPARE = {
    'lt': operator.lt,
    'le': operator.le,
    'eq': operator.eq,
    'ge': operator.ge,
    'gt': operator.gt,
}


def _evaluation(criterion, outcome, reason, value=None):
    return dict(
        criterion_id=criterion['criterion_id'],
        kind=criterion['kind'],
        outcome=outcome,
        reason=reason,
        value=value,
        units=criterion['units'],
    )


def unresolved(criteria, reason):
    """Every criterion unresolved for one reason (a run without a usable record)."""
    return [_evaluation(c, 'unresolved', reason) for c in criteria]


def evaluate_run(results, criteria, bindings):
    """Evaluate one run's retained results against brief criteria through bindings.

    Comparison in the criterion's own units, which the binding guarantees equal to the
    output's; tolerance applies to equality only. Nothing is converted, and no
    convergence, applicability or validity is inferred from a threshold being met.
    """
    outputs = {(o['target']['instance_id'], o['target']['port_id']): o for o in results['outputs']}
    converged = results['schema_version'] != '1' or results['convergence']['state'] in (
        'converged',
        'not_applicable',
    )
    evaluations = []
    for criterion in criteria:
        binding = bindings.get(criterion['criterion_id'])
        if binding is None:
            evaluations.append(_evaluation(criterion, 'unresolved', 'criterion_not_bound'))
            continue
        output = outputs.get((binding['instance_id'], binding['port_id']))
        if not converged:
            evaluations.append(_evaluation(criterion, 'unresolved', 'convergence_unresolved'))
            continue
        if output is None or output['availability'] != 'available':
            evaluations.append(_evaluation(criterion, 'unresolved', 'required_output_unavailable'))
            continue
        value = output['value']
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or output['units'] != criterion['units']
        ):
            evaluations.append(_evaluation(criterion, 'unresolved', 'invalid_criterion_or_units'))
            continue
        if criterion['kind'] == 'objective':
            evaluations.append(_evaluation(criterion, 'measured', 'measured', value))
            continue
        threshold = criterion['threshold']
        absolute = criterion.get('absolute_tolerance', 0)
        relative = criterion.get('relative_tolerance', 0)
        allowance = absolute + relative * abs(threshold)
        if (
            any(
                type(v) not in (int, float) or not math.isfinite(v)
                for v in (threshold, absolute, relative)
            )
            or min(absolute, relative) < 0
            or not math.isfinite(allowance)
        ):
            evaluations.append(_evaluation(criterion, 'unresolved', 'invalid_criterion_or_units'))
            continue
        met = (
            abs(value - threshold) <= allowance
            if criterion['operator'] == 'eq'
            else COMPARE[criterion['operator']](value, threshold)
        )
        evaluations.append(
            _evaluation(criterion, 'met' if met else 'not_met', 'threshold_comparison', value)
        )
    return evaluations
