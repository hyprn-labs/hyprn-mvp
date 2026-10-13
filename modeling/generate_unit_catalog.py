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
NAMES = ['', 'm', 'km', 'cm', 'mm', 's', 'min', 'h', 'kg', 'g', 'N', 'Pa',
         'kPa', 'MPa', 'K', 'degC', 'degF', 'rad', 'deg', 'm/s', 'km/h',
         'J/kg', 'kJ/kg', 'MJ/kg', 'kg/m**3', 'g/cm**3', 'm**2', 'cm**2', 'mm**2']


def generate():
    source = hashlib.sha256(Path(inspect.getfile(units)).read_bytes()).hexdigest()
    if openmdao.__version__ != VERSION or source != SOURCE_SHA256:
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
    catalog = dict(engine='OpenMDAO', version=VERSION, source_sha256=source,
                   supported_units=NAMES, linear_pairs=pairs)
    payload = json.dumps(catalog, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    catalog['catalog_digest'] = hashlib.sha256(payload).hexdigest()
    return catalog


if __name__ == '__main__':
    print(json.dumps(generate(), sort_keys=True, indent=2, allow_nan=False))
