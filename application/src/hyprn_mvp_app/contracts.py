"""Wire-contract identity and schema validation, shared by application and integration.

Owns: canonical JSON bytes and digests (RFC 8785 plus exact large-integer handling),
fresh identifiers, strict bounded JSON parsing, the model-contract schema and its
validators, and the public ``Error`` envelope (``DomainError``) with the wire/schema
failure it carries (``ContractError``, field-level diagnostics).

Dependency-light by design: stdlib, ``rfc8785`` and ``jsonschema`` only. It must not
own or import SQLite, HTTP transport, authentication, workflow orchestration,
model-service coordination, runtime activation or candidate code. Importing it opens no schema.
Reviewed launch roots load only the generated
execution schema; other definitions load the authored namespace lazily. Each used
validator is compiled once per process.

Identity invariant: ``canonical`` and ``digest`` are byte-for-byte the canonical and digest
functions before the split; ``application/tests/fixtures/identity_golden.json`` proves it.
"""

from __future__ import annotations
from functools import cache, lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from uuid import uuid4

from collections import OrderedDict
from threading import Lock

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker, validators
from jsonschema.exceptions import best_match, ValidationError


# Execution budgets are operational bounds, never physical model defaults.
EXECUTION_WALL_DEFAULT = 300
EXECUTION_WALL_MAX = 3600
BATCH_RUN_LIMIT = 2


def execution_wall_seconds(value):
    if type(value) is not int or not 1 <= value <= EXECUTION_WALL_MAX:
        raise ValueError('Execution wall budget must be an integer from 1 to 3600 seconds')
    return value


def uid():
    return str(uuid4())


def canonical(value):
    def exact_numbers(item):
        # RFC8785 can encode a float as integer-looking JSON (e.g. 1e20).
        # json.loads then returns int. Preserve that exact numeric value during
        # encoding only; never round inexact integers or mutate parsed records.
        if type(item) is int and abs(item) > 2**53 - 1:
            try:
                number = float(item)
                if math.isfinite(number) and int(number) == item:
                    return number
            except OverflowError:
                pass  # Let rfc8785 raise its normal IntegerDomainError.
        if isinstance(item, dict):
            return {key: exact_numbers(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [exact_numbers(child) for child in item]
        return item

    return rfc8785.dumps(exact_numbers(value))


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def raw_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_json_items(validator, required, instance, schema):
    """Exact JSON equality without quadratic comparisons of retained file arrays.

    Canonical bytes preserve object-key independence and numeric equality while
    distinguishing booleans. Invalid/non-JSON values retain the library's behavior;
    the ordinary encoding gate still rejects them before boundary validation.
    """
    if not required or not validator.is_type(instance, 'array'):
        return
    try:
        encoded = [canonical(item) for item in instance]
    except (ValueError, TypeError, UnicodeError, RecursionError):
        yield from Draft202012Validator.VALIDATORS['uniqueItems'](
            validator, required, instance, schema
        )
        return
    if len(set(encoded)) != len(encoded):
        yield ValidationError(f'{instance!r} has non-unique elements')


JsonValidator = validators.extend(Draft202012Validator, {'uniqueItems': unique_json_items})


def check_digest(value, key='digest'):
    if value.get(key) != digest({k: v for k, v in value.items() if k != key}):
        raise ValueError('Frozen manifest digest mismatch')


def data_json(raw):
    """Strict bounded JSON: duplicate keys and non-finite numbers are refused."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')),
        )
        canonical(value)
        return value
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Invalid bounded JSON') from error


class DomainError(Exception):
    """The public ``Error`` envelope: code, HTTP status, revision, field diagnostics, outcome.

    ``data()`` is persisted in command receipts and replayed with ``DomainError(**data)``;
    its shape must not change.
    """

    def __init__(
        self, code, status=409, *, current_revision=None, fields=None, outcome='unchanged'
    ):
        super().__init__(code)
        self.code, self.status = code, status
        self.current_revision, self.fields, self.outcome = current_revision, fields or [], outcome

    def data(self):
        return dict(
            code=self.code,
            status=self.status,
            current_revision=self.current_revision,
            fields=self.fields,
            outcome=self.outcome,
        )


class ContractError(DomainError):
    """A value does not satisfy its named wire schema (``schema``).

    Local input: ``invalid_request`` 400 with one diagnostic per failing field
    (JSON-pointer ``path``, ``code`` ``invalid``, controlled ``message``).
    Remote (modeling backend) payload: ``backend_unavailable`` 503, outcome unknown,
    no diagnostics, so backend details never reach clients. As a ``DomainError`` it
    keeps the public envelope, receipts and every existing ``except DomainError``.
    """

    def __init__(self, schema, code, status, *, fields=None, outcome='unchanged'):
        super().__init__(code, status, fields=fields, outcome=outcome)
        self.schema = schema


EXECUTION_ROOTS = (
    'ApproachClosure3',
    'ApproachClosure4',
    'ApproachClosurePreUnits',
    'ApproachClosureRead4',
    'ApproachClosureWithModel3',
    'ApproachResolution1',
    'ApproachResolution4',
    'ApproachSavedRead4',
    'ApproachVersionRead2',
    'ConfigurationCandidate1',
    'ConfigurationCandidate2',
    'ConfigurationCandidate3',
    'ConfigurationCandidate4',
    'ConfigurationCandidate6',
    'ConfigurationRevision1',
    'ConfigurationRevision2',
    'ConfigurationRevision3',
    'ConfigurationRevision4',
    'ConfigurationRevision6',
    'ConfigurationRevisionRead6',
    'ExecutionBundleRead12',
    'FrozenConfiguration10',
    'FrozenConfiguration4',
    'FrozenConfiguration5',
    'FrozenConfiguration7',
    'FrozenConfiguration8',
    'FrozenConfiguration9',
    'FrozenConfigurationLegacy',
    'ModelDraftRead5',
    'ModelRevision2',
    'ModelRevisionRead5',
    'ModelingConfiguration2',
    'ModelingConfiguration3',
    'ModelingConfiguration5',
    'ModelingConfigurationRevision2',
    'ModelingConfigurationRevision3',
    'ModelingConfigurationRevision5',
    'MonetaryUnit1',
    'NativeSource',
    'PortRef',
    'PreparedModelArtifactRead5',
    'ProgramBindings',
    'ProgramProvenance',
    'ProgramSourceMap',
    'ResultDependencies1',
    'UnitDeclaration2',
)

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[3] / 'contracts/schemas'


@cache
def _documents_schema():
    return json.loads((SCHEMA_DIRECTORY / 'documents.schema.json').read_bytes())


@cache
def authored_schema():
    """One authored namespace, preserving public definition order across source files."""
    model = json.loads((SCHEMA_DIRECTORY / 'model.schema.json').read_bytes())
    documents = _documents_schema()
    model_defs, document_defs = model['$defs'], documents['$defs']
    if model_defs.keys() & document_defs.keys():
        raise ValueError('Duplicate authored definition')
    groups = documents['x-hyprn-mvp-definition-order']
    ordered = [name for names in groups.values() for name in names]
    if (
        len(ordered) != len(set(ordered))
        or set(ordered) != set(document_defs)
        or set(groups) - (set(model_defs) | {''})
    ):
        raise ValueError('Invalid authored definition order')
    merged = {name: document_defs[name] for name in groups.get('', ())}
    for name, body in model_defs.items():
        merged[name] = body
        merged.update((child, document_defs[child]) for child in groups.get(name, ()))
    return {**model, '$defs': merged, 'x-hyprn-mvp-documents-contract': documents_contract()}


def definitions():
    """All authored definitions in stable source order, loaded on first use."""
    return authored_schema()['$defs']


def documents_contract():
    """Normative Documents metadata, independent of the execution schema."""
    return _documents_schema()['x-hyprn-mvp-documents-contract']


def definition(name):
    """Launch roots read exclusively from the attested execution schema."""
    return (_execution_schema()['$defs'] if name in EXECUTION_ROOTS else definitions())[name]


@cache
def validator(name):
    """Compile a named definition without loading unrelated authored schemas."""
    if name in EXECUTION_ROOTS:
        return _execution_validator(name)
    schema = authored_schema()
    if name not in schema['$defs']:
        raise KeyError(name)
    return JsonValidator({**schema, '$ref': '#/$defs/' + name}, format_checker=FormatChecker())


MAX_DIAGNOSTICS = 20
TEXT_LIMIT = 4096  # Diagnostic path/message bound in the public Error schema.


def validate(name, value, *, remote=False):
    """Validate ``value`` against the model-contract definition ``name``; return it unchanged.

    Raises ``ContractError``: ``invalid_request`` 400 with field diagnostics, or
    ``backend_unavailable`` 503 without diagnostics when ``remote``.
    """
    version = value.get('schema_version') if isinstance(value, dict) else None
    selected = (lambda: _execution_version_validator(name, version)) if (
        name in EXECUTION_ROOTS and type(version) is str
    ) else (lambda: validator(name))
    fields = _violations(selected, value)
    if fields:
        if remote:
            raise ContractError(name, 'backend_unavailable', 503, outcome='unknown')
        raise ContractError(name, 'invalid_request', 400, fields=fields)
    return value


EXECUTION_CONTRACT = SCHEMA_DIRECTORY / 'execution.schema.json'


@cache
def _execution_schema():
    return json.loads(EXECUTION_CONTRACT.read_bytes())


@cache
def _execution_validator(name):
    schema = _execution_schema()
    if name not in schema['$defs']:
        raise KeyError(name)
    return JsonValidator({**schema, '$ref': '#/$defs/' + name}, format_checker=FormatChecker())


def _schema_versions(schema, node, seen=frozenset()):
    """Required version tags a branch may accept, or None when not provably tagged."""
    if not isinstance(node, dict):
        return None
    if '$ref' in node and set(node) == {'$ref'}:
        ref = node['$ref']
        if not ref.startswith('#/$defs/') or ref in seen:
            return None
        return _schema_versions(schema, schema['$defs'][ref.rsplit('/', 1)[1]], seen | {ref})
    validation = {
        k for k in node if not k.startswith('x-') and k not in ('title', 'description')
    }
    if validation == {'oneOf'}:
        branches = [_schema_versions(schema, child, seen) for child in node['oneOf']]
        return None if any(v is None for v in branches) else frozenset().union(*branches)
    if node.get('type') == 'object' and 'schema_version' in node.get('required', []):
        tag = node.get('properties', {}).get('schema_version', {})
        values = [tag['const']] if 'const' in tag else tag.get('enum')
        if values and all(type(v) is str for v in values):
            return frozenset(values)
    return None


@lru_cache(maxsize=128)
def _execution_version_validator(name, version):
    """Select only provably disjoint version branches; retain all other validation.

    Nested oneOf is not flattened. If multiple branches can accept the tag, or any
    branch's tag is unknown, validate the original union at that level.
    """
    schema = _execution_schema()
    node = {'$ref': '#/$defs/' + name}
    visited = set()
    while isinstance(node, dict):
        if '$ref' in node and set(node) == {'$ref'}:
            ref = node['$ref']
            if not ref.startswith('#/$defs/') or ref in visited:
                break
            visited.add(ref)
            node = schema['$defs'][ref.rsplit('/', 1)[1]]
            continue
        validation = {
            k for k in node if not k.startswith('x-') and k not in ('title', 'description')
        }
        if validation != {'oneOf'}:
            break
        tags = [_schema_versions(schema, child) for child in node['oneOf']]
        if any(values is None for values in tags):
            break
        candidates = [child for child, values in zip(node['oneOf'], tags) if version in values]
        if len(candidates) != 1:
            break
        node = candidates[0]
    if not isinstance(node, dict):
        return _execution_validator(name)
    return JsonValidator({'$defs': schema['$defs'], **node}, format_checker=FormatChecker())


def validate_execution(name, value):
    """Validate ``value`` against the execution-contract definition ``name``; return it unchanged.

    The execution contract is read and each used definition compiled once per process.
    Raises ``ContractError`` ``invalid_request`` 400 with field diagnostics (the same
    controlled, bounded messages as ``validate``); callers with their own error mapping
    (``execution_bundle``) translate it. ``KeyError`` for an unknown definition.
    """
    version = value.get('schema_version') if isinstance(value, dict) else None
    selected = (
        (lambda: _execution_version_validator(name, version))
        if type(version) is str
        else (lambda: _execution_validator(name))
    )
    fields = _violations(selected, value)
    if fields:
        raise ContractError(name, 'invalid_request', 400, fields=fields)
    return value

# Only successful pure schema checks are reusable. Authority, signatures, runtime
# admission and semantic checks remain with their owners on every operation.
_VALIDATED = OrderedDict()
_VALIDATED_LOCK = Lock()
_VALIDATED_BYTES = 0
_VALIDATED_MAX_BYTES = 16 * 1024 * 1024
_VALIDATED_MAX_ITEM = 1024 * 1024
_VALIDATED_MAX_ITEMS = 256


def _json_types(value):
    # Canonical JSON deliberately accepts tuples; JSON Schema does not treat them
    # as arrays. Only ordinary decoded JSON values share a validation cache key.
    if type(value) is dict:
        return all(type(k) is str and _json_types(v) for k, v in value.items())
    if type(value) is list:
        return all(_json_types(v) for v in value)
    return type(value) in (str, int, float, bool, type(None))


def _violations(validator, value):
    """Field diagnostics for ``value``: encoding first, then the schema ``validator()``."""
    try:
        raw = canonical(value)
    except (ValueError, UnicodeError, RecursionError):
        return [encoding_issue(value)]
    compiled = validator()
    cacheable = len(raw) <= _VALIDATED_MAX_ITEM and _json_types(value)
    if cacheable:
        # Retain exact JSON types and validate the snapshot used as the key.
        raw = json.dumps(value, sort_keys=True, ensure_ascii=True,
                         allow_nan=False, separators=(',', ':')).encode()
        cacheable = len(raw) <= _VALIDATED_MAX_ITEM
    key = (id(compiled), raw)
    if cacheable:
        with _VALIDATED_LOCK:
            if _VALIDATED.get(key) is compiled:
                _VALIDATED.move_to_end(key)
                return []
    try:
        errors = diagnostics(compiled.iter_errors(json.loads(raw) if cacheable else value))
    except RecursionError:
        return [issue((), 'Value is nested too deeply.')]
    if cacheable and not errors:
        global _VALIDATED_BYTES
        with _VALIDATED_LOCK:
            if key not in _VALIDATED:
                _VALIDATED[key] = compiled
                _VALIDATED_BYTES += len(raw)
            _VALIDATED.move_to_end(key)
            while (_VALIDATED_BYTES > _VALIDATED_MAX_BYTES
                   or len(_VALIDATED) > _VALIDATED_MAX_ITEMS):
                (_, removed), _ = _VALIDATED.popitem(last=False)
                _VALIDATED_BYTES -= len(removed)
    return errors


def pointer(parts):
    """RFC 6901 JSON pointer; the whole value keeps the established ``/``."""
    return '/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def issue(parts, message):
    """One public Diagnostic for a field; text is bounded to the Error schema."""
    return dict(
        path=pointer(parts)[:TEXT_LIMIT],
        code='invalid',
        message=message[:TEXT_LIMIT],
        element_ref=None,
    )


def encoding_issue(value):
    """Locate the first value that cannot be canonically encoded, iteratively."""
    stack = [((), value)]
    while stack:
        parts, item = stack.pop()
        if len(parts) > 256:
            return issue((), 'Value is nested too deeply.')
        if isinstance(item, dict):
            for key in reversed(list(item)):
                if not isinstance(key, str) or not _encodable(key):
                    return issue(
                        (*parts, key) if isinstance(key, str) else parts,
                        'Field name must be valid Unicode text.',
                    )
                stack.append(((*parts, key), item[key]))
        elif isinstance(item, (list, tuple)):
            stack.extend(((*parts, i), child) for i, child in reversed(list(enumerate(item))))
        elif not _encodable(item):
            if isinstance(item, float):
                return issue(parts, 'Number must be finite.')
            if isinstance(item, int):
                return issue(parts, 'Integer is outside the exactly representable range.')
            if isinstance(item, str):
                return issue(parts, 'Text must be valid Unicode.')
            return issue(parts, 'Value is not a JSON value.')
    return issue((), 'Value is nested too deeply.')


def _encodable(item):
    try:
        canonical(item)
        return True
    except (ValueError, UnicodeError, TypeError, RecursionError):
        return False


def diagnostics(errors):
    """Field-level diagnostics in schema order, de-duplicated and bounded."""
    fields = []
    for error in errors:
        for field in _explain(error):
            if field not in fields:
                fields.append(field)
        if len(fields) >= MAX_DIAGNOSTICS:
            break
    return fields[:MAX_DIAGNOSTICS]


def _quote(value):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 200 else text[:197] + '...'


_BOUNDS = {
    'minLength': 'Must be at least {} characters.',
    'maxLength': 'Must be at most {} characters.',
    'minItems': 'Must contain at least {} items.',
    'maxItems': 'Must contain at most {} items.',
    'minProperties': 'Must contain at least {} fields.',
    'maxProperties': 'Must contain at most {} fields.',
    'minimum': 'Must be at least {}.',
    'maximum': 'Must be at most {}.',
    'exclusiveMinimum': 'Must be greater than {}.',
    'exclusiveMaximum': 'Must be less than {}.',
    'multipleOf': 'Must be a multiple of {}.',
}


def _selected_union_errors(error):
    """Follow an explicit wire discriminator or the submitted JSON type.

    Do not guess a version from the number of failing fields. A branch can be
    excluded only by its own type or kind/schema_version constraint. An envelope
    may carry its version inside content; follow that explicit nested version too.
    Ambiguous alternatives keep the ordinary closest-form diagnostic.
    """

    def branches(union):
        grouped = {}
        for child in union.context:
            index = next(iter(child.schema_path), None)
            if not isinstance(index, int):
                return {}
            grouped.setdefault(index, []).append(child)
        return grouped

    def contradicted(child):
        if (
            child.validator == 'additionalProperties'
            and child.validator_value is False
            and not child.path
            and isinstance(child.instance, dict)
        ):
            properties = child.schema.get('properties', {})
            patterns = child.schema.get('patternProperties', {})
            if any(
                key in child.instance
                and key not in properties
                and not any(re.search(pattern, key) for pattern in patterns)
                for key in ('kind', 'schema_version')
            ):
                return True
        if child.validator == 'type' and not child.path:
            return True
        if (
            child.validator in ('const', 'enum')
            and child.path
            and (child.path[-1] == 'schema_version'
                 or (len(child.path) == 1 and child.path[0] == 'kind'))
        ):
            return True
        if child.validator in ('oneOf', 'anyOf') and not child.path:
            nested = branches(child)
            return bool(nested) and all(
                any(contradicted(item) for item in children) for children in nested.values()
            )
        return False

    candidates = [
        children
        for children in branches(error).values()
        if not any(contradicted(child) for child in children)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _explain(error):
    """Controlled messages from schema facts only; submitted values are never echoed.

    A union (oneOf/anyOf) failure reports the closest alternative when one is
    clearly closest, marked as such; otherwise it stays at the union's own path.
    """
    if error.validator in ('oneOf', 'anyOf') and error.context:
        if all(child.validator == 'type' and not child.path for child in error.context):
            forms = []
            for child in error.context:
                expected = child.validator_value
                if not isinstance(expected, str):
                    break
                if expected == 'object' and child.schema.get('required'):
                    expected += ' with required fields ' + ', '.join(
                        _quote(name) for name in child.schema['required'][:20]
                    )
                if expected not in forms:
                    forms.append(expected)
            else:
                return [issue(error.absolute_path, 'Expected ' + ' or '.join(forms) + '.')]
        selected = _selected_union_errors(error)
        if selected is not None:
            return diagnostics(selected)
        closest = best_match([error])
        if closest is not error:
            return [
                dict(
                    f, message=(f['message'].rstrip('.') + ' (closest allowed form).')[:TEXT_LIMIT]
                )
                for f in _explain(closest)
            ]
    parts, keyword, expected, instance = (
        tuple(error.absolute_path),
        error.validator,
        error.validator_value,
        error.instance,
    )
    if keyword in ('required', 'dependentRequired') and isinstance(instance, dict):
        names = (
            expected
            if keyword == 'required'
            else sorted({n for group in expected.values() for n in group})
        )
        missing = [n for n in names if n not in instance]
        return [issue((*parts, n), 'Required field is missing.') for n in missing] or [
            issue(parts, 'Required field is missing.')
        ]
    if keyword in ('additionalProperties', 'unevaluatedProperties') and isinstance(instance, dict):
        if keyword == 'additionalProperties' and expected is False:
            patterns = [re.compile(p) for p in error.schema.get('patternProperties', {})]
            known = error.schema.get('properties', {})
            extra = [
                k for k in instance if k not in known and not any(p.search(k) for p in patterns)
            ]
            if extra:
                return [issue((*parts, k), 'Field is not allowed here.') for k in extra]
        return [issue(parts, 'Contains fields that are not allowed here.')]
    if keyword == 'type':
        return [
            issue(
                parts,
                'Expected '
                + ' or '.join(expected if isinstance(expected, list) else [expected])
                + '.',
            )
        ]
    if keyword == 'const':
        return [issue(parts, 'Must be ' + _quote(expected) + '.')]
    if keyword == 'enum':
        more = f' (and {len(expected) - 20} more)' if len(expected) > 20 else ''
        return [
            issue(
                parts, 'Must be one of: ' + ', '.join(_quote(v) for v in expected[:20]) + more + '.'
            )
        ]
    if keyword == 'pattern':
        return [issue(parts, 'Must match the pattern ' + _quote(expected) + '.')]
    if keyword == 'format':
        return [issue(parts, 'Must be a valid ' + str(expected) + '.')]
    if keyword in _BOUNDS:
        return [issue(parts, _BOUNDS[keyword].format(expected))]
    if keyword == 'uniqueItems':
        return [issue(parts, 'Items must be unique.')]
    if keyword == 'oneOf' and not error.context:
        return [issue(parts, 'Matches more than one allowed form.')]
    if keyword in ('oneOf', 'anyOf'):
        return [issue(parts, 'Does not match any allowed form.')]
    if keyword == 'contains':
        return [issue(parts, 'Must contain a matching item.')]
    if keyword == 'propertyNames':
        return [issue(parts, 'Contains a field name that is not allowed.')]
    if keyword in ('not', None, False):
        return [issue(parts, 'Value is not allowed here.')]
    return [issue(parts, 'Invalid value.')]


# These fields existed only in the first HYPRN deterministic result format.
LEGACY_RESULT_FIELDS = frozenset({'convergence', 'optimization', 'completeness', 'applicability'})


def public_record_view(value):
    """Project historical results without changing their retained source identities.

    Every changed enclosing object carries both source and view canonical JSON hashes.
    Existing digest fields still identify their exact retained sources; they never
    claim to authenticate this projection. Exact artifacts and exports bypass this
    HTTP presentation projection and remain independently verifiable.
    """
    if isinstance(value, list):
        return [public_record_view(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: public_record_view(item) for key, item in value.items()}
    if (
        value.get('schema_version') == '1'
        and {'run_id', 'bundle_digest', 'outputs', 'execution', 'criteria', 'artifacts'}
        <= value.keys()
        and LEGACY_RESULT_FIELDS <= value.keys()
    ):
        # Closed validation prevents applying a scientific projection to an
        # arbitrary object that happens to contain similarly named keys.
        validate('RetainedResults', value)
        result = {key: item for key, item in result.items() if key not in LEGACY_RESULT_FIELDS}
    if result != value:
        result['record_view'] = dict(
            schema_version='1', source_sha256=digest(value), view_sha256=digest(result)
        )
    return result
