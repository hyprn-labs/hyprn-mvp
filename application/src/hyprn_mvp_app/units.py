"""Data-only unit labels and exact active-occurrence admission for the app.

No physical parser, conversion factors, native imports or model mutation lives
here. Callers still own authorization, immutable digest/provenance validation,
connection compatibility and app/private configuration pairing.

Model-version interpretation owned here: ``port_units`` is the one rule for
which units a model port binds (Model1/2 exact literal, Model3/4/5 resolved engine
spelling, anything else unsupported); ``active_ports`` and ``resolved_model_units``
own active-occurrence readiness.
"""

from .contracts import definition, DomainError, canonical, validate

# Identity pins from the audited unit catalog table, not a fallback catalog or parser.
UNIT_CATALOG_DIGEST = '5abc0ae35d2e2fcc8beb1ca9267e709007c007d51f20f95d735122daeef54885'
# Historical artifacts authenticate their exact table; current discovery uses only the new pin.
RETAINED_UNIT_CATALOG_DIGESTS = frozenset(
    (UNIT_CATALOG_DIGEST, '9453b65bb997da3568956a53125f53ec83521c5b78d014fde8d15b4538c81f45', 'f9278b0e59aa2d410dcd14a2abc1306d3d18adcf9edbb433002f6466489939f3')
)
UNIT_ENGINE_SOURCE_SHA256 = '9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92'
UNIT_ENGINE_LIBRARY_SHA256 = '8094fb7d3e8cb65a56311c2ea5ccfbc9c29cb8b4160f1486c39c19dd779a43d3'
UNIT_CATALOG_BYTES = 16384

# The closed contract vocabulary is shared authority, not a fallback engine table.
_PHYSICAL = frozenset(
    definition('UnitDeclaration2')['oneOf'][2]['properties']['expression']['enum']
)

_MONETARY = frozenset(definition('MonetaryUnit1')['properties']['expression']['enum'])


def _meaning(value):
    if isinstance(value, str):
        if len(value) > 4096:
            raise DomainError('invalid_request', 400)
        canonical(value)
        return value
    validate('UnitDeclaration2', value)
    if value['kind'] == 'unspecified':
        return None
    return '' if value['kind'] == 'dimensionless' else value['expression']


def unit_label(value):
    """Inspect retained meaning without asserting execution readiness.

    A historical string is displayed exactly; only its empty representation has
    the established dimensionless meaning. A new unspecified unit stays distinct.
    """
    expression = _meaning(value)
    if expression is None:
        return 'Not specified'
    return expression if expression else 'Dimensionless'


def _issue(code, path, port_id):
    return dict(
        path=path,
        code=code,
        element_ref=port_id,
        message=(
            'Specify units before execution'
            if code == 'unit_unspecified'
            else 'Choose a supported physical unit'
        ),
    )


def require_engine_unit(value, *, path='/units', port_id=None):
    """Return exact supported engine spelling, or an actionable readiness error."""
    expression = _meaning(value)
    if expression is None or (expression and expression not in _PHYSICAL):
        code = 'unit_unspecified' if expression is None else 'unit_unsupported'
        raise DomainError('invalid_model', 422, fields=[_issue(code, path, port_id)])
    return expression


def active_ports(model):
    """Validate every retained shape, then select each instance's exact version."""
    validate(
        'ModelRevisionRead5'
        if isinstance(model, dict) and 'model_revision_id' in model
        else 'ModelDraftRead5',
        model,
    )
    definitions = {}
    flattened = []
    for definition in model['definitions']:
        version = definition['definition_version_id']
        if version in definitions:
            raise DomainError('invalid_model', 422)
        definitions[version] = definition
        quantities = definition.get('quantity_definitions', [])
        quantity_ids = [q['port_id'] for q in quantities]
        if len(quantity_ids) != len(set(quantity_ids)) or not set(quantity_ids) <= {
            p['port_id'] for p in definition['ports']
        }:
            raise DomainError('invalid_model', 422)
        ids = set()
        for port in definition['ports']:
            if port['definition_version_id'] != version or port['port_id'] in ids:
                raise DomainError('invalid_model', 422)
            ids.add(port['port_id'])
            if (model['schema_version'] != '5' or isinstance(port['units'], str)) and _meaning(port['units']) in {
                *_MONETARY, 'pax'
            }:
                raise DomainError('invalid_model', 422)
            # Unused unspecified is valid. Unsupported retained engine spellings
            # are not silently repaired or interpreted as dimensionless.
            if _meaning(port['units']) is not None:
                require_engine_unit(port['units'])
            flattened.append(port)
    if flattened != model['ports']:
        raise DomainError('invalid_model', 422)
    instance_ids = set()
    active = []
    for instance in model['instances']:
        iid = instance['instance_id']
        version = instance['definition_version_id']
        if iid in instance_ids or version not in definitions:
            raise DomainError('invalid_model', 422)
        instance_ids.add(iid)
        for port in definitions[version]['ports']:
            key = (iid, version, port['port_id'])
            path = f'/instances/{iid}/definitions/{version}/ports/{port["port_id"]}/units'
            active.append((key, path, port['units']))
    return active


def _readiness(active):
    return [
        _issue('unit_unspecified', path, key[2])
        for key, path, value in active
        if _meaning(value) is None
    ][:1000]


def unit_readiness(model):
    """Bounded diagnostics for every unresolved active input/output/internal port."""
    return _readiness(active_ports(model))


def resolved_model_units(model):
    """Map (instance_id, definition_version_id, port_id) to exact engine units.

    Raises before returning any mapping when the active closure is incomplete.
    Valid retained, uninstantiated versions do not participate in readiness.
    """
    active = active_ports(model)
    issues = _readiness(active)
    if issues:
        raise DomainError('invalid_model', 422, fields=issues)
    return {
        key: require_engine_unit(value, path=path, port_id=key[2]) for key, path, value in active
    }


# the single port-units rule. Model1/2 bind the exact retained literal; Model3/4/5
# bind the resolved engine spelling. No other module repeats this choice.
LITERAL_UNIT_MODELS = frozenset({'1', '2'})
RESOLVED_UNIT_MODELS = frozenset({'3', '4', '5'})


def port_units(model):
    """Map every instance port (instance_id, definition_version_id, port_id) to its bound units.

    - Model1/2: the exact retained literal, never parsed, resolved or repaired. An instance
      whose definition version is absent raises ``KeyError`` (it is never skipped).
    - Model3/4/5: ``resolved_model_units``; an incomplete or unsupported active unit raises
      its ``invalid_model`` 422.
    - Any other model version: ``unsupported_record_version`` 422. Nothing is guessed.

    Consumers (retained outcome completeness, scalar result sources, configuration preview
    conversions, frozen program bindings) map these errors to their own public outcome.
    """
    version = model.get('schema_version') if isinstance(model, dict) else None
    if isinstance(version, str) and version in RESOLVED_UNIT_MODELS:
        return resolved_model_units(model)
    if not (isinstance(version, str) and version in LITERAL_UNIT_MODELS):
        raise DomainError('unsupported_record_version', 422)
    definitions = {d['definition_version_id']: d for d in model['definitions']}
    return {
        (i['instance_id'], i['definition_version_id'], p['port_id']): p['units']
        for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports']
    }


def monetary_expression(value):
    """Return the exact finite monetary spelling, never infer money from labels."""
    expression = _meaning(value)
    return expression if expression in _MONETARY else None


def monetary_basis_key(basis):
    """Comparable declared money, including exact scale; no FX, inflation or unit conversion."""
    if basis is None:
        return None
    expression = basis['catalogue_expression']
    if expression not in _MONETARY:
        raise DomainError('invalid_request', 422)
    return expression, basis['price_year'], basis['economic_basis']
