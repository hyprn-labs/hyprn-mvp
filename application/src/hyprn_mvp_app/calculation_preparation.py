"""Publication readiness for a declared joint exploration domain.

This is a read of exact calculation/estimate artifacts, not a second scientific record.
Complete convex support and independent numerical checks are separate requirements; neither
establishes physical validity or an error bound at every unsampled continuous coordinate.
"""

from .calculation_estimates import CATEGORY, Estimates
from .calculation_exploration import CalculationExploration
from .calculations import Calculations, independent_dimensions, DEFINITIONS as CALCULATIONS
from .contracts import DomainError, digest, issue, definitions, diagnostics
from jsonschema import Draft202012Validator, FormatChecker
from .quantity_projection import _key

_ID = CALCULATIONS['CalculationVersion1']['properties']['calculation_id']


def _ref(name):
    return {'$ref': '#/$defs/' + name}


def _array(items, maximum, minimum=0):
    return dict(type='array', items=items, maxItems=maximum, minItems=minimum)


def _object(properties):
    return dict(
        type='object',
        properties=properties,
        required=list(properties),
        additionalProperties=False,
    )


DEFINITIONS = {
    'CalculationPreparationRequest1': _object(
        dict(
            shown_outputs=_array(_ref('PortRef'), 32, 1),
        )
    ),
    'CalculationPreparation1': _object(
        dict(
            estimate_id=_ID,
            calculation_version_id=_ID,
            ready=dict(type='boolean'),
            groups=_array(
                _object(
                    dict(
                        group=dict(type='integer', minimum=0, maximum=7),
                        covered=dict(type='boolean'),
                        problems=_array(_ref('Diagnostic'), 64),
                    )
                ),
                8,
            ),
        )
    ),
}


def validate(name, value, *, retained=False):
    errors = list(
        Draft202012Validator(
            {'$defs': definitions() | DEFINITIONS, **DEFINITIONS[name]},
            format_checker=FormatChecker(),
        ).iter_errors(value)
    )
    if errors:
        raise DomainError(
            'corrupt_retained_record' if retained else 'invalid_request',
            409 if retained else 400,
            fields=diagnostics(errors),
        )
    return value


def box_supported(bounds, vectors):
    """All box corners must occur in training, not merely in the combined sample extrema."""
    corners = set()
    for vector in vectors:
        if len(vector) == len(bounds) and all(x in b for x, b in zip(vector, bounds)):
            corners.add(tuple(vector))
    return bool(bounds) and len(corners) == 2 ** len(bounds)


def preparation(store, actor, sid, estimate_id, body):
    validate('CalculationPreparationRequest1', body)
    targets = body['shown_outputs']
    if len({_key(t) for t in targets}) != len(targets):
        raise DomainError(
            'invalid_request',
            422,
            fields=[
                issue(['shown_outputs'], 'Select each output only once.'),
            ],
        )
    estimate = Estimates(store).read(actor, sid, estimate_id)
    version = Calculations(store).version(actor, sid, estimate['calculation_version_id'])
    design = version['content']['design']
    if design['kind'] != 'sampled':
        raise DomainError(
            'invalid_request',
            422,
            fields=[
                issue([], 'Joint exploration needs a sampled calculation.'),
            ],
        )
    receipt = store.receipt(actor, sid, CATEGORY, estimate_id)
    artifacts = receipt['request'].get('artifacts', [])
    groups = []
    for index, group in enumerate(design['groups']):
        problems = []
        axes = independent_dimensions(group['dimensions'])
        bounds = [[d['lower'], d['upper']] for d in axes]
        public = next((g for g in estimate['groups'] if g['group'] == index), None)
        covered = False
        if public and len(artifacts) > index:
            artifact = artifacts[index]
            if digest(artifact) != public['artifact_sha256']:
                raise DomainError('corrupt_retained_record', 409)
            covered = artifact['bounds'] == bounds and box_supported(
                bounds,
                artifact['training_vectors'],
            )
        if not covered:
            problems.append(
                issue(
                    ['groups', index, 'coverage'],
                    'Training does not cover every joint boundary. Generate a boundary-supported '
                    'design and run its missing members before publishing exploration.',
                )
            )
        for target_index, target in enumerate(targets):
            output = (
                next((o for o in public['outputs'] if o['target'] == target), None)
                if public
                else None
            )
            metrics = output.get('metrics') if output else None
            if (
                not output
                or output['reason'] is not None
                or not metrics
                or not metrics['target_met']
                or metrics['assessed_count'] < 1
                or metrics['evaluable_count'] != metrics['assessed_count']
                or metrics['failed_count']
            ):
                problems.append(
                    issue(
                        ['groups', index, 'shown_outputs', target_index],
                        'This output has no passing independent assessment. Refine training and '
                        'reassess with the declared tolerances; do not loosen them to publish.',
                    )
                )
        if public and estimate['state'] in ('ready', 'assessed'):
            basis = CalculationExploration(store).basis(
                actor,
                sid,
                version['calculation_version_id'],
                group=index,
                estimate_id=estimate_id,
            )
            if any(
                o['value'] is None
                for p in basis['points']
                for o in p['outputs']
                if o['target'] in targets
            ):
                problems.append(
                    issue(
                        ['groups', index, 'originals'],
                        'A displayed output is unavailable at a calculated sample. Resolve the '
                        'model failure before publishing this exploration domain.',
                    )
                )
        groups.append(dict(group=index, covered=covered, problems=problems))
    result = dict(
        estimate_id=estimate_id,
        calculation_version_id=version['calculation_version_id'],
        ready=all(not g['problems'] for g in groups),
        groups=groups,
    )
    return validate('CalculationPreparation1', result, retained=True)
