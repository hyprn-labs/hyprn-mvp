"""Build-only finite catalog from the reviewed installed OpenMDAO engine.

No candidate, dynamic registration, runtime parser or network is involved.
"""

import hashlib
import inspect
import json
import math
from pathlib import Path

import openmdao
from openmdao.utils import units

VERSION = '3.45.1'
SOURCE_SHA256 = '9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92'
LIBRARY_SHA256 = '8094fb7d3e8cb65a56311c2ea5ccfbc9c29cb8b4160f1486c39c19dd779a43d3'
# Finite reviewed expressions; the engine verifies every dimension and scale.
MONETARY_DENOMINATORS = {
    'USD': '', 'kUSD': '', 'MUSD': '', 'USD/pax': 'pax', 'USD/kg': 'kg',
    'USD/m**3': 'm**3', 'USD/h': 'h', 'USD/kW': 'kW',
    'USD/(kW*h)': 'kW*h', 'USD/J': 'J', 'USD/MJ': 'MJ',
}
NAMES = [
    '',
    'm',
    'km',
    'cm',
    'mm',
    's',
    'min',
    'h',
    'kg',
    'g',
    'N',
    'Pa',
    'kPa',
    'MPa',
    'K',
    'degC',
    'degF',
    'rad',
    'deg',
    'm/s',
    'km/h',
    'J/kg',
    'kJ/kg',
    'MJ/kg',
    'kg/m**3',
    'g/cm**3',
    'm**2',
    'cm**2',
    'mm**2',
    'm**3',
    'cm**3',
    'mm**3',
    'kg/m**2',
    'g/m**2',
    '1/m**2',
    'J/(kg*K)',
    'kJ/(kg*K)',
    'J',
    'kJ',
    'MJ',
    'W',
    'kW',
    'MW',
    'm**3/s',
    'kg/s',
    'm/s**2',
    'N*m',
    'W/(m*K)',
    'W/(m**2*K)',
    'USD', 'kUSD', 'MUSD', 'pax', 'USD/pax', 'USD/kg', 'USD/m**3',
    'USD/h', 'USD/kW', 'USD/(kW*h)', 'USD/J', 'USD/MJ',
]


def generate():
    source = hashlib.sha256(Path(inspect.getfile(units)).read_bytes()).hexdigest()
    library = hashlib.sha256(Path(inspect.getfile(units)).with_name('unit_library.ini').read_bytes()).hexdigest()
    if openmdao.__version__ != VERSION or source != SOURCE_SHA256 or library != LIBRARY_SHA256:
        raise ValueError('Reviewed OpenMDAO version/source required')
    pairs = []
    for a in NAMES:
        for b in NAMES:
            if not a or not b:
                if a == b:
                    pairs.append([a, b, 1.0, 0.0])
                continue
            try:
                factor, offset = units.unit_conversion(a, b)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(factor) or not math.isfinite(offset) or factor <= 0:
                raise ValueError('Invalid trusted conversion')
            if offset == 0:
                pairs.append([a, b, factor, offset])
    if {a for a, b, _, _ in pairs if a == b} != set(NAMES):
        raise ValueError('Every advertised expression must be engine verified')
    monetary = []
    for expression, denominator in MONETARY_DENOMINATORS.items():
        canonical_unit = 'USD' if not denominator else 'USD/(' + denominator + ')'
        scale, offset = units.unit_conversion(expression, canonical_unit)
        if offset != 0 or not math.isfinite(scale) or scale <= 0:
            raise ValueError('Invalid monetary unit scale')
        monetary.append(dict(expression=expression, numerator='USD', scale=scale, denominator=denominator))
    catalog = dict(
        engine='OpenMDAO',
        version=VERSION,
        source_sha256=source,
        library_source_sha256=library,
        monetary_units=monetary,
        supported_units=NAMES,
        linear_pairs=pairs,
    )
    payload = json.dumps(catalog, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    catalog['catalog_digest'] = hashlib.sha256(payload).hexdigest()
    return catalog


if __name__ == '__main__':
    print(json.dumps(generate(), sort_keys=True, indent=2, allow_nan=False))
