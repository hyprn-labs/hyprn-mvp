"""Immutable declared controls; saving a design never prepares or executes code."""

from copy import deepcopy
from fractions import Fraction
import json
import math

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


def nullable(value):
    return dict(anyOf=[value, dict(type='null')])


def array(value, maximum=1000, minimum=0):
    return dict(type='array', items=value, minItems=minimum, maxItems=maximum)


DIMENSION = _object(
    dict(
        target=_ref('PortRef'),
        lower=nullable(_NUMBER),
        upper=nullable(_NUMBER),
        units=_TEXT,
        step=nullable(dict(type='number', exclusiveMinimum=0, maximum=2**53 - 1)),
        covary_group=nullable(dict(type='string', minLength=1, maxLength=100)),
        common_key=nullable(dict(type='string', minLength=1, maxLength=100)),
    )
)
DEFINITIONS = {
    'ExplorationDesignRequest1': _object(
        dict(
            schema_version=dict(const='1'),
            command_id=_ID,
            answer_version_id=_ID,
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
                        configuration_revision_id=_ID,
                        model_id=_ID,
                        model_revision_id=_ID,
                        initial_axis=_ref('PortRef'),
                        dimensions=array(DIMENSION, 32, 1),
                    )
                ),
                8,
                1,
            ),
            rationale=dict(type='string', minLength=1, maxLength=4096),
        )
    ),
    'ExplorationDesign1': _object(
        dict(
            design_id=_ID,
            digest=_HASH,
            request=_ref('ExplorationDesignRequest1'),
        )
    ),
}


def validate(name, value):
    v = Draft202012Validator(
        {'$defs': definitions() | EXPLORATION | DEFINITIONS, **DEFINITIONS[name]},
        format_checker=FormatChecker(),
    )
    error = next(v.iter_errors(value), None)
    if error:
        invalid(
            '/' + '/'.join(map(str, error.absolute_path)),
            'invalid_declaration',
            'Use the declared field type and supported bounds.',
        )


def invalid(path, code, message):
    raise DomainError(
        'invalid_request',
        400,
        fields=[dict(path=path, code=code, message=message, element_ref=None)],
    )


def on_step(value, dimension):
    if dimension['step'] is None:
        return True
    lower = dimension['lower']
    if lower is None:
        return False
    return (
        (Fraction(str(value)) - Fraction(str(lower))) / Fraction(str(dimension['step']))
    ).denominator == 1


def grid_size(dimension):
    return (
        int(
            (Fraction(str(dimension['upper'])) - Fraction(str(dimension['lower'])))
            / Fraction(str(dimension['step']))
        )
        + 1
    )


def independent_dimensions(dimensions):
    seen, result = set(), []
    for dimension in dimensions:
        group = dimension['covary_group']
        if group is None or group not in seen:
            result.append(dimension)
        if group is not None:
            seen.add(group)
    return result


def mapped_values(dimensions, vector):
    """Explicit design mapping only, in saved assignment units; no unit conversion."""
    leaders = independent_dimensions(dimensions)
    if len(vector) != len(leaders):
        raise ValueError('Malformed design vector')
    values, groups = {}, {}
    for d, value in zip(leaders, vector, strict=True):
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not d['lower'] <= value <= d['upper']
        ):
            raise ValueError('Generated vector outside design')
        if d['step'] is not None:
            lo, step = Fraction(str(d['lower'])), Fraction(str(d['step']))
            value = float(lo + round((Fraction(str(value)) - lo) / step) * step)
        values[_key(d['target'])] = value
        if d['covary_group'] is not None:
            groups[d['covary_group']] = value
    for d in dimensions:
        if d['covary_group'] is not None:
            values[_key(d['target'])] = groups[d['covary_group']]
    return values


class Designs:
    def __init__(self, store, configurations):
        self.store = store
        self.explorations = Explorations(store, configurations)

    def resolve(self, actor, sid, body):
        validate('ExplorationDesignRequest1', body)
        categories = body['category_dimensions']
        if not body['rationale'].strip() or len({c['name'] for c in categories}) != len(categories):
            raise DomainError('invalid_request', 400)
        if any(len(set(c['values'])) != len(c['values']) for c in categories):
            raise DomainError('invalid_request', 400)
        tuples, common = set(), {}
        for combo in body['combinations']:
            category = tuple(combo['categories'])
            if (
                category in tuples
                or len(category) != len(categories)
                or any(value not in categories[i]['values'] for i, value in enumerate(category))
            ):
                invalid(
                    '/combinations',
                    'unsupported_tuple',
                    'Use one unique tuple of declared category values.',
                )
            tuples.add(category)
            basis = self.explorations.basis(
                actor, sid, body['answer_version_id'], combo['configuration_revision_id']
            )
            if any(combo[k] != basis[k] for k in ('model_id', 'model_revision_id')):
                raise DomainError('reference_conflict', 409)
            free = {
                _key(p['target']): p['binding']['assignment']
                for p in basis['inputs']
                if p['binding']['kind'] == 'free'
            }
            controls = combo['dimensions']
            if (
                len(controls) != len(free)
                or {_key(d['target']) for d in controls} != set(free)
                or _key(combo['initial_axis']) not in free
            ):
                invalid(
                    '/combinations/dimensions',
                    'incomplete_free_inputs',
                    'Declare every free input once and select a free input as the initial axis.',
                )
            groups, common_seen = {}, set()
            for d in controls:
                saved = free[_key(d['target'])]
                if d['units'] != saved['units']:
                    invalid(
                        '/combinations/dimensions/units',
                        'incompatible_units',
                        'Keep each saved value with its saved assignment unit; '
                        'convert through configuration authoring.',
                    )
                lo, hi, step = d['lower'], d['upper'], d['step']
                if any(
                    v is not None and (type(v) not in (float, int) or not math.isfinite(v))
                    for v in (lo, hi, step)
                ):
                    invalid(
                        '/combinations/dimensions',
                        'finite_number_required',
                        'Use finite real numeric bounds and steps.',
                    )
                if (lo is None) != (hi is None) or (
                    lo is not None and (lo >= hi or not lo <= saved['value'] <= hi)
                ):
                    invalid(
                        '/combinations/dimensions',
                        'invalid_range',
                        'Declare increasing lower and upper bounds containing the saved value, '
                        'or leave both unassigned.',
                    )
                if step is not None and (
                    lo is None or not on_step(hi, d) or not on_step(saved['value'], d)
                ):
                    invalid(
                        '/combinations/dimensions/step',
                        'invalid_step',
                        'The saved value and upper bound must lie on the declared step grid '
                        'from the lower bound.',
                    )
                signature = (d['units'], lo, hi, step, saved['value'])
                if d['covary_group'] is not None:
                    group = d['covary_group']
                    if group in groups and groups[group] != signature:
                        invalid(
                            '/combinations/dimensions/covary_group',
                            'incompatible_binding',
                            'Linked inputs need equal saved values, units, bounds and steps.',
                        )
                    groups[group] = signature
                if d['common_key'] is not None:
                    name = d['common_key']
                    # Common identity is authored explicitly; differing units/steps never carry.
                    compatible = (d['units'], step)
                    if name in common_seen or (name in common and common[name] != compatible):
                        invalid(
                            '/combinations/dimensions/common_key',
                            'incompatible_common_selection',
                            'Common keys must be unique per tuple and retain compatible '
                            'units and steps.',
                        )
                    common_seen.add(name)
                    common[name] = compatible
        return body

    def save(self, actor, sid, body):
        self.resolve(actor, sid, body)
        result = dict(design_id=body['command_id'], digest=digest(body), request=deepcopy(body))
        return self.store.command(
            actor, sid, 'exploration_design', body['command_id'], body, lambda db: result
        )

    def read(self, actor, sid, identity):
        result = self.store.receipt(actor, sid, 'exploration_design', identity)['result']
        validate('ExplorationDesign1', result)
        if result['digest'] != digest(result['request']):
            raise DomainError('corrupt_retained_record', 409)
        return result

    def page(self, actor, sid, answer, cursor=None):
        items, next_cursor = receipt_page(
            self.store, actor, sid, 'exploration_design', answer, cursor
        )
        for item in items:
            validate('ExplorationDesign1', item)
            if item['digest'] != digest(item['request']):
                raise DomainError('corrupt_retained_record', 409)
        return items, next_cursor


def receipt_page(store, actor, sid, category, answer, cursor=None):
    """Twenty exact answer-bound receipts per page, newest acceptance first."""
    with store.connection() as db:
        store.authorize(db, actor, sid)
        boundary = None
        if cursor:
            row = db.execute(
                'SELECT rowid FROM receipts WHERE scope=? AND category=? AND command_id=?',
                (sid, category, cursor),
            ).fetchone()
            if row is None:
                raise DomainError('invalid_request', 400)
            boundary = row[0]
        rows = db.execute(
            'SELECT command_id,result FROM receipts WHERE scope=? AND category=? '
            'AND (? IS NULL OR rowid<?) AND ('
            "json_extract(result,'$.request.answer_version_id')=? OR EXISTS ("
            "SELECT 1 FROM json_each(receipts.result,'$.request.combinations') "
            "WHERE json_extract(value,'$.answer_version_id')=?)) ORDER BY rowid DESC LIMIT 21",
            (sid, category, boundary, boundary, answer, answer),
        )
        matches = []
        for row in rows:
            result = json.loads(row['result'])
            request = result['request']
            answers = (
                [request['answer_version_id']]
                if category == 'exploration_design'
                else [c['answer_version_id'] for c in request['combinations']]
            )
            if answer in answers:
                matches.append(result)
                if len(matches) == 21:
                    break
    return matches[:20], matches[19]['request']['command_id'] if len(matches) > 20 else None
