"""Explicit sampled coordinates, step grids and linked input mappings."""

from fractions import Fraction
import math

from .quantity_projection import _key


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
