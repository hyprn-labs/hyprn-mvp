"""Wire-contract identity and schema validation, shared by application and integration.

Owns: canonical JSON bytes and digests (RFC 8785 plus exact large-integer handling),
fresh identifiers, strict bounded JSON parsing, the model-contract schema and its
validators, and the public ``Error`` envelope (``DomainError``) with the wire/schema
failure it carries (``ContractError``, field-level diagnostics).

Dependency-light by design: stdlib, ``rfc8785`` and ``jsonschema`` only. It must not
own or import SQLite, HTTP transport, authentication, workflow orchestration,
model-service coordination, runtime activation or candidate code. Importing it opens no schema. Reviewed launch roots load only the generated
execution schema; other definitions load the authored namespace lazily. Each used
validator is compiled once per process.

Identity invariant: ``canonical`` and ``digest`` are byte-for-byte the canonical and digest functions before the split; ``application/tests/fixtures/identity_golden.json`` proves it.
"""
from __future__ import annotations
from functools import cache
import hashlib
import json
import math
from pathlib import Path
import re
from uuid import uuid4

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match


def uid(): return str(uuid4())


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


def raw_hash(raw): return hashlib.sha256(raw).hexdigest()


def check_digest(value,key='digest'):
    if value.get(key)!=digest({k:v for k,v in value.items() if k!=key}):
        raise ValueError('Frozen manifest digest mismatch')


def data_json(raw):
    """Strict bounded JSON: duplicate keys and non-finite numbers are refused."""
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        canonical(value)
        return value
    except (UnicodeError,RecursionError) as error:raise ValueError('Invalid bounded JSON') from error


class DomainError(Exception):
    """The public ``Error`` envelope: code, HTTP status, revision, field diagnostics, outcome.

    ``data()`` is persisted in command receipts and replayed with ``DomainError(**data)``;
    its shape must not change.
    """
    def __init__(self, code, status=409, *, current_revision=None, fields=None, outcome="unchanged"):
        super().__init__(code)
        self.code, self.status = code, status
        self.current_revision, self.fields, self.outcome = current_revision, fields or [], outcome

    def data(self):
        return dict(code=self.code, status=self.status, current_revision=self.current_revision,
                    fields=self.fields, outcome=self.outcome)


class ContractError(DomainError):
    """A value does not satisfy its named wire schema (``schema``).

    Local input: ``invalid_request`` 400 with one diagnostic per failing field
    (JSON-pointer ``path``, ``code`` ``invalid``, controlled ``message``).
    Remote (modeling backend) payload: ``backend_unavailable`` 503, outcome unknown,
    no diagnostics, so backend details never reach clients. As a ``DomainError`` it
    keeps the public envelope, receipts and every existing ``except DomainError``.
    """
    def __init__(self, schema, code, status, *, fields=None, outcome="unchanged"):
        super().__init__(code, status, fields=fields, outcome=outcome)
        self.schema = schema


EXECUTION_ROOTS = (
    'ApproachClosure3',
    'ApproachClosurePreUnits',
    'ApproachClosureRead3',
    'ApproachClosureWithModel3',
    'ApproachResolution1',
    'ApproachResolution3',
    'ApproachSavedRead3',
    'ApproachVersionRead2',
    'ConfigurationCandidate1',
    'ConfigurationCandidate2',
    'ConfigurationCandidate3',
    'ConfigurationCandidate4',
    'ConfigurationRevision',
    'ConfigurationRevision1',
    'ConfigurationRevision2',
    'ConfigurationRevision3',
    'ConfigurationRevision4',
    'ExecutionBundleRead8',
    'FrozenConfiguration4',
    'FrozenConfiguration5',
    'FrozenConfiguration7',
    'FrozenConfigurationLegacy',
    'ModelDraftRead4',
    'ModelRevision2',
    'ModelRevisionRead4',
    'ModelingConfiguration2',
    'ModelingConfiguration3',
    'ModelingConfigurationRevision2',
    'ModelingConfigurationRevision3',
    'NativeSource',
    'PortRef',
    'PreparedModelArtifact',
    'ProgramBindings',
    'ProgramProvenance',
    'ProgramSourceMap',
    'ResultDependencies1',
    'UnitDeclaration1',
)

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[3] / "contracts/schemas"


@cache
def _documents_schema():
    return json.loads((SCHEMA_DIRECTORY / "documents.schema.json").read_bytes())


@cache
def authored_schema():
    """One authored namespace, preserving public definition order across source files."""
    model = json.loads((SCHEMA_DIRECTORY / "model.schema.json").read_bytes())
    documents = _documents_schema()
    model_defs, document_defs = model["$defs"], documents["$defs"]
    if model_defs.keys() & document_defs.keys():
        raise ValueError("Duplicate authored definition")
    groups = documents["x-hyprn-mvp-definition-order"]
    ordered = [name for names in groups.values() for name in names]
    if (len(ordered) != len(set(ordered)) or set(ordered) != set(document_defs)
            or set(groups) - (set(model_defs) | {""})):
        raise ValueError("Invalid authored definition order")
    merged = {name: document_defs[name] for name in groups.get("", ())}
    for name, body in model_defs.items():
        merged[name] = body
        merged.update((child, document_defs[child]) for child in groups.get(name, ()))
    return {**model, "$defs": merged,
            "x-hyprn-mvp-documents-contract": documents_contract()}


def definitions():
    """All authored definitions in stable source order, loaded on first use."""
    return authored_schema()["$defs"]


def documents_contract():
    """Normative Documents metadata, independent of the execution schema."""
    return _documents_schema()["x-hyprn-mvp-documents-contract"]


def definition(name):
    """Launch roots read exclusively from the attested execution schema."""
    return (_execution_schema()["$defs"] if name in EXECUTION_ROOTS else definitions())[name]


@cache
def validator(name):
    """Compile a named definition without loading unrelated authored schemas."""
    if name in EXECUTION_ROOTS:
        return _execution_validator(name)
    schema = authored_schema()
    if name not in schema["$defs"]:
        raise KeyError(name)
    return Draft202012Validator({**schema, "$ref": "#/$defs/" + name},
                                format_checker=FormatChecker())


MAX_DIAGNOSTICS = 20
TEXT_LIMIT = 4096  # Diagnostic path/message bound in the public Error schema.


def validate(name,value,*,remote=False):
    """Validate ``value`` against the model-contract definition ``name``; return it unchanged.

    Raises ``ContractError``: ``invalid_request`` 400 with field diagnostics, or
    ``backend_unavailable`` 503 without diagnostics when ``remote``.
    """
    fields=_violations(lambda:validator(name),value)
    if fields:
        if remote:raise ContractError(name,"backend_unavailable",503,outcome="unknown")
        raise ContractError(name,"invalid_request",400,fields=fields)
    return value


EXECUTION_CONTRACT = SCHEMA_DIRECTORY / "execution.schema.json"


@cache
def _execution_schema():
    return json.loads(EXECUTION_CONTRACT.read_bytes())


@cache
def _execution_validator(name):
    schema=_execution_schema()
    if name not in schema["$defs"]:raise KeyError(name)
    return Draft202012Validator({**schema,"$ref":"#/$defs/"+name},format_checker=FormatChecker())


def validate_execution(name,value):
    """Validate ``value`` against the execution-contract definition ``name``; return it unchanged.

    The execution contract is read and each used definition compiled once per process.
    Raises ``ContractError`` ``invalid_request`` 400 with field diagnostics (the same
    controlled, bounded messages as ``validate``); callers with their own error mapping
    (``execution_bundle``) translate it. ``KeyError`` for an unknown definition.
    """
    fields=_violations(lambda:_execution_validator(name),value)
    if fields:raise ContractError(name,"invalid_request",400,fields=fields)
    return value


def _violations(validator,value):
    """Field diagnostics for ``value``: encoding first, then the schema ``validator()``."""
    try:
        canonical(value)
    except (ValueError,UnicodeError,RecursionError):
        return [encoding_issue(value)]
    try:
        return diagnostics(validator().iter_errors(value))
    except RecursionError:
        return [issue((),'Value is nested too deeply.')]


def pointer(parts):
    """RFC 6901 JSON pointer; the whole value keeps the established ``/``."""
    return "/"+"/".join(str(p).replace("~","~0").replace("/","~1") for p in parts)


def issue(parts, message):
    """One public Diagnostic for a field; text is bounded to the Error schema."""
    return dict(path=pointer(parts)[:TEXT_LIMIT], code="invalid", message=message[:TEXT_LIMIT], element_ref=None)


def encoding_issue(value):
    """Locate the first value that cannot be canonically encoded, iteratively."""
    stack=[((),value)]
    while stack:
        parts,item=stack.pop()
        if len(parts)>256:
            return issue((),'Value is nested too deeply.')
        if isinstance(item,dict):
            for key in reversed(list(item)):
                if not isinstance(key,str) or not _encodable(key):
                    return issue((*parts,key) if isinstance(key,str) else parts,'Field name must be valid Unicode text.')
                stack.append(((*parts,key),item[key]))
        elif isinstance(item,(list,tuple)):
            stack.extend(((*parts,i),child) for i,child in reversed(list(enumerate(item))))
        elif not _encodable(item):
            if isinstance(item,float):return issue(parts,'Number must be finite.')
            if isinstance(item,int):return issue(parts,'Integer is outside the exactly representable range.')
            if isinstance(item,str):return issue(parts,'Text must be valid Unicode.')
            return issue(parts,'Value is not a JSON value.')
    return issue((),'Value is nested too deeply.')


def _encodable(item):
    try:
        canonical(item)
        return True
    except (ValueError,UnicodeError,TypeError,RecursionError):
        return False


def diagnostics(errors):
    """Field-level diagnostics in schema order, de-duplicated and bounded."""
    fields=[]
    for error in errors:
        for field in _explain(error):
            if field not in fields:fields.append(field)
        if len(fields)>=MAX_DIAGNOSTICS:break
    return fields[:MAX_DIAGNOSTICS]


def _quote(value):
    text=json.dumps(value,ensure_ascii=False)
    return text if len(text)<=200 else text[:197]+'...'


_BOUNDS={
    'minLength':'Must be at least {} characters.','maxLength':'Must be at most {} characters.',
    'minItems':'Must contain at least {} items.','maxItems':'Must contain at most {} items.',
    'minProperties':'Must contain at least {} fields.','maxProperties':'Must contain at most {} fields.',
    'minimum':'Must be at least {}.','maximum':'Must be at most {}.',
    'exclusiveMinimum':'Must be greater than {}.','exclusiveMaximum':'Must be less than {}.',
    'multipleOf':'Must be a multiple of {}.',
}


def _explain(error):
    """Controlled messages from schema facts only; submitted values are never echoed.

    A union (oneOf/anyOf) failure reports the closest alternative when one is
    clearly closest, marked as such; otherwise it stays at the union's own path.
    """
    if error.validator in ('oneOf','anyOf') and error.context:
        closest=best_match([error])
        if closest is not error:
            return [dict(f,message=(f['message'].rstrip('.')+' (closest allowed form).')[:TEXT_LIMIT]) for f in _explain(closest)]
    parts,keyword,expected,instance=tuple(error.absolute_path),error.validator,error.validator_value,error.instance
    if keyword in ('required','dependentRequired') and isinstance(instance,dict):
        names=expected if keyword=='required' else sorted({n for group in expected.values() for n in group})
        missing=[n for n in names if n not in instance]
        return [issue((*parts,n),'Required field is missing.') for n in missing] or [issue(parts,'Required field is missing.')]
    if keyword in ('additionalProperties','unevaluatedProperties') and isinstance(instance,dict):
        if keyword=='additionalProperties' and expected is False:
            patterns=[re.compile(p) for p in error.schema.get('patternProperties',{})]
            known=error.schema.get('properties',{})
            extra=[k for k in instance if k not in known and not any(p.search(k) for p in patterns)]
            if extra:return [issue((*parts,k),'Field is not allowed here.') for k in extra]
        return [issue(parts,'Contains fields that are not allowed here.')]
    if keyword=='type':
        return [issue(parts,'Expected '+' or '.join(expected if isinstance(expected,list) else [expected])+'.')]
    if keyword=='const':
        return [issue(parts,'Must be '+_quote(expected)+'.')]
    if keyword=='enum':
        more=f' (and {len(expected)-20} more)' if len(expected)>20 else ''
        return [issue(parts,'Must be one of: '+', '.join(_quote(v) for v in expected[:20])+more+'.')]
    if keyword=='pattern':
        return [issue(parts,'Must match the pattern '+_quote(expected)+'.')]
    if keyword=='format':
        return [issue(parts,'Must be a valid '+str(expected)+'.')]
    if keyword in _BOUNDS:
        return [issue(parts,_BOUNDS[keyword].format(expected))]
    if keyword=='uniqueItems':
        return [issue(parts,'Items must be unique.')]
    if keyword=='oneOf' and not error.context:
        return [issue(parts,'Matches more than one allowed form.')]
    if keyword in ('oneOf','anyOf'):
        return [issue(parts,'Does not match any allowed form.')]
    if keyword=='contains':
        return [issue(parts,'Must contain a matching item.')]
    if keyword=='propertyNames':
        return [issue(parts,'Contains a field name that is not allowed.')]
    if keyword in ('not',None,False):
        return [issue(parts,'Value is not allowed here.')]
    return [issue(parts,'Invalid value.')]
