"""The tool registry: build rules, the tools a session is offered, and validated invocation.

A registry is built from ``ToolSpec`` values and refuses to build when any spec breaks a rule:

- schema rules: ``verb_object`` names of at most 64 characters, closed objects, no ``$ref``, no
  root ``anyOf``/``oneOf``/``allOf``, top-level property names of 1 to 64 characters, every
  string and array bounded, descriptions under 2,048 characters, no ``study_id`` property
  anywhere (the study is the session's, D-09) and revision fields named ``expected_revision``
  and ``revision_token`` (OQ-6); every description ends with one playbook pointer (D-P1);
- write policy (ADR-0003): no tool declares a route of the human-only classification and no
  tool carries a name from the closed forbidden list (deletion, archive, restore, access);
- ownership (ADR-0004): every tool without a gate declares its owners and its stored outcome
  from closed vocabularies, ``none`` exactly for reads.

The offered list is a pure function of surface, stage, delegation effects, scope and advertised
capability gates, returned in registry order (tool names in sorted order) with canonical,
byte-stable definitions, so a session's list is fixed and a client's prompt-cache prefix stays
valid (D-P9). No further per-session or per-skill scoping applies. The registry holds no state
between calls.
"""

import inspect
import json
import re

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from ..contracts import canonical, digest
from . import catalogue, playbook, write_policy
from .spec import (
    CLIENT_META_KEYS,
    DELEGATION_EFFECTS,
    DESTRUCTIVE_TOOLS,
    EFFECTS,
    OUTCOME_PATTERN,
    OWNERS,
    RECORD_LABELS,
    SCOPES,
    STAGES,
    SURFACES,
    WRITE_EFFECTS,
    ToolError,
)

REGISTRY_VERSION = '0.1.1'
# The stage the local edition serves: the last one, so every tool a delegation's effects admit
# is offered.
LOCAL_STAGE = STAGES[-1]
MAX_INPUT_BYTES = 256 * 1024
MAX_FIELDS = 20
MAX_DESCRIPTION = 2047
NAME = re.compile(r'[a-z][a-z0-9_]{0,63}')
PROPERTY_NAME = re.compile(r'[A-Za-z0-9_.-]{1,64}')
GATE = re.compile(r'[a-z][a-z0-9_.]{0,63}')
SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
OUTCOME = re.compile(OUTCOME_PATTERN)
POINTER = re.compile(r' Guidance: get_playbook\("([a-z_]+)"\)\.')
POINTER_AT_END = re.compile(POINTER.pattern + r'\Z')
METHODS = ('GET', 'POST', 'PATCH', 'PUT', 'DELETE')
TEMPLATE = re.compile(r'/api/1(?:/(?:[a-z0-9-]+|\{[a-z_]+\}))+')
# Human-only effects never have a tool, by name on any surface and stage (ADR-0003).
FORBIDDEN_NAMES = frozenset(
    {
        'archive_study',
        'restore_study',
        'archive_document',
        'unarchive_document',
        'remove_member',
        'change_role',
    }
)
FORBIDDEN_PREFIXES = ('delete_', 'invite_', 'grant_', 'mint_', 'revoke_')
REVISION_FIELDS = frozenset({'expected_revision', 'revision_token'})
REVISION_WORD = re.compile(r'(?:^|_)(?:revision|version|etag)s?(?:_|$)')
IDENTIFIER_SUFFIX = re.compile(r'_(?:id|ids|number|numbers)$')
FORBIDDEN_KEYWORDS = frozenset(
    {
        '$ref',
        '$dynamicRef',
        '$defs',
        'definitions',
        '$id',
        '$anchor',
        '$dynamicAnchor',
        'patternProperties',
        'unevaluatedProperties',
        'dependentSchemas',
    }
)
ROOT_COMBINATORS = ('anyOf', 'oneOf', 'allOf')
SUBSCHEMA_KEYS = ('items', 'contains', 'not', 'if', 'then', 'else', 'propertyNames')
SUBSCHEMA_LISTS = ('anyOf', 'oneOf', 'allOf', 'prefixItems')


class RegistryError(ValueError):
    """A tool specification breaks a registry rule; the registry is not built."""


def forbidden_name(name):
    """Whether ``name`` names a human-only effect (deletion, archive, restore or access)."""
    return name in FORBIDDEN_NAMES or name.startswith(FORBIDDEN_PREFIXES)


def schema_problems(schema):
    """Every break of the schema rules in one tool input schema."""
    problems = []
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        return ['the input schema must be an object schema']
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        problems.append('the input schema is not a valid JSON Schema 2020-12 document')
    problems += [k + ' at the schema root' for k in ROOT_COMBINATORS if k in schema]
    for name in schema.get('properties', {}):
        if not PROPERTY_NAME.fullmatch(name):
            problems.append('top-level property name outside 1 to 64 of [A-Za-z0-9_.-]')
    _walk(schema, 'input', problems)
    return problems


def _walk(node, where, problems):
    if not isinstance(node, dict):
        problems.append(where + ': a subschema must be an object')
        return
    for key in sorted(FORBIDDEN_KEYWORDS.intersection(node)):
        problems.append(where + ': ' + key + ' is not allowed')
    description = node.get('description')
    if isinstance(description, str) and len(description) > MAX_DESCRIPTION:
        problems.append(where + ': description of 2,048 characters or more')
    types = node.get('type')
    types = set(types) if isinstance(types, list) else {types}
    if types == {None} and 'enum' not in node and 'const' not in node:
        if not any(k in node for k in SUBSCHEMA_LISTS):
            problems.append(where + ': a subschema needs a type, enum or const')
    if 'object' in types or 'properties' in node:
        if node.get('additionalProperties') is not False:
            problems.append(where + ': objects must be closed (additionalProperties false)')
    if 'string' in types and not any(k in node for k in ('maxLength', 'enum', 'const')):
        problems.append(where + ': strings must be bounded (maxLength, enum or const)')
    if 'array' in types and 'maxItems' not in node:
        problems.append(where + ': arrays must be bounded (maxItems)')
    for name, child in node.get('properties', {}).items():
        if name == 'study_id':
            problems.append(where + ': no property may be named study_id')
        elif REVISION_WORD.search(name) and not IDENTIFIER_SUFFIX.search(name):
            if name not in REVISION_FIELDS:
                problems.append(where + ': revision fields are expected_revision or revision_token')
        _walk(child, where + '.' + name, problems)
    for key in SUBSCHEMA_KEYS:
        if key in node:
            _walk(node[key], where + '/' + key, problems)
    for key in SUBSCHEMA_LISTS:
        for index, child in enumerate(node.get(key, ())):
            _walk(child, where + '/' + key + '/' + str(index), problems)


def spec_problems(tool):
    """Every rule one ``ToolSpec`` breaks, prefixed with its name."""
    problems = []
    name = tool.name
    if not isinstance(name, str) or not NAME.fullmatch(name):
        return ['a tool name must match ' + NAME.pattern]
    if forbidden_name(name):
        problems.append('the name names a human-only effect')
    if not isinstance(tool.title, str) or not 0 < len(tool.title) <= 128:
        problems.append('the title must be 1 to 128 characters')
    description = tool.description
    if not isinstance(description, str) or not 0 < len(description) <= MAX_DESCRIPTION:
        problems.append('the description must be 1 to 2,047 characters')
    else:
        pointers = POINTER.findall(description)
        if len(pointers) != 1 or not POINTER_AT_END.search(description):
            problems.append('the description must end with one get_playbook pointer')
        elif pointers[0] not in playbook.SECTION_NAMES:
            problems.append('the playbook pointer names no section')
    problems += schema_problems(tool.input_schema)
    if tool.effect not in EFFECTS:
        problems.append('unknown effect')
    if tool.stage not in STAGES:
        problems.append('unknown stage')
    if not _closed_tuple(tool.surfaces, SURFACES):
        problems.append('surfaces must be a non-empty tuple of known surfaces')
    if not _closed_tuple(tool.scopes, SCOPES):
        problems.append('scopes must be a non-empty tuple of known scopes')
    problems += _operation_problems(tool)
    problems += _ownership_problems(tool)
    if tool.gate is not None and not (isinstance(tool.gate, str) and GATE.fullmatch(tool.gate)):
        problems.append('a gate is a capability name')
    if tool.record_label not in RECORD_LABELS:
        problems.append('unknown record label')
    meta = dict(tool.client_meta) if isinstance(tool.client_meta, tuple) else None
    if (
        meta is None
        or not set(meta) <= CLIENT_META_KEYS
        or any(v is not True for v in meta.values())
    ):
        problems.append('client metadata is only anthropic/alwaysLoad set to true')
    if name in DESTRUCTIVE_TOOLS and tool.effect not in WRITE_EFFECTS:
        problems.append('a tool that replaces shared state or drafts must write')
    if not isinstance(tool.activity_label, str) or not 0 < len(tool.activity_label) <= 64:
        problems.append('the activity label must be 1 to 64 characters')
    if tool.attribution_kind is not None and not NAME.fullmatch(str(tool.attribution_kind)):
        problems.append('the attribution kind is a record kind name')
    if not (isinstance(tool.since, str) and SEMVER.fullmatch(tool.since)):
        problems.append('since must be a registry version')
    elif _version(tool.since) > _version(REGISTRY_VERSION):
        problems.append('since is later than the registry version')
    if tool.handler is not None and not inspect.iscoroutinefunction(tool.handler):
        problems.append('the handler must be an async function')
    if tool.gate is None and tool.handler is None and tool.runtime_operation is None:
        problems.append('a tool needs a handler or a runtime operation')
    if tool.runtime_operation is not None and tool.api_operations:
        problems.append('a runtime operation calls no API operation')
    return [name + ': ' + p for p in problems]


def _closed_tuple(values, vocabulary):
    return (
        isinstance(values, tuple)
        and len(values) > 0
        and len(set(values)) == len(values)
        and set(values) <= set(vocabulary)
    )


def _version(text):
    return tuple(int(part) for part in text.split('.'))


def _operation_problems(tool):
    problems = []
    operations = tool.api_operations
    if not isinstance(operations, tuple) or len(set(operations)) != len(operations):
        return ['api_operations must be a tuple of distinct (method, template) pairs']
    for operation in operations:
        if not (isinstance(operation, tuple) and len(operation) == 2):
            problems.append('an API operation is a (method, template) pair')
            continue
        method, template = operation
        if method not in METHODS or not isinstance(template, str):
            problems.append('an API operation has a known method and a template')
            continue
        if not TEMPLATE.fullmatch(template):
            problems.append('an API operation template is a /api/1 route template')
        elif write_policy.is_human_only(method, template):
            problems.append('declares a human-only route: ' + method + ' ' + template)
        if tool.effect == 'read' and method not in ('GET', 'POST'):
            problems.append('a read tool calls only GET and, for checks, POST')
    return problems


def _ownership_problems(tool):
    problems = []
    owners, outcome = tool.owners, tool.outcome
    if not isinstance(owners, tuple) or len(set(owners)) != len(owners):
        return ['owners must be a tuple of distinct owner names']
    if not set(owners) <= OWNERS:
        problems.append('owners outside the closed owner vocabulary')
    if outcome is not None and not (isinstance(outcome, str) and OUTCOME.fullmatch(outcome)):
        problems.append('outcome outside the closed outcome vocabulary')
    declared = tool.gate is None or tool.api_operations
    if declared and (not owners or outcome is None):
        problems.append('a tool declares at least one owner and its stored outcome')
    if outcome is not None and (outcome == 'none') != (tool.effect == 'read'):
        problems.append('the outcome is none exactly for a read')
    return problems


def definition(tool):
    """The client-visible definition of ``tool`` as canonical JSON data. Field names follow the
    Provider-neutral tool shape; the bridges translate it for their providers."""
    value = {
        'name': tool.name,
        'title': tool.title,
        'description': tool.description,
        'inputSchema': tool.input_schema,
        'annotations': tool.annotations,
    }
    if tool.client_meta:
        value['_meta'] = dict(tool.client_meta)
    return json.loads(canonical(value))


class Registry:
    """An immutable set of tools that passed every build rule."""

    def __init__(self, tools):
        tools = tuple(tools)
        problems = []
        names = [t.name for t in tools]
        problems += [
            'duplicate tool name: ' + n for n in sorted({n for n in names if names.count(n) > 1})
        ]
        for tool in tools:
            problems += spec_problems(tool)
        if problems:
            raise RegistryError('; '.join(problems))
        self._tools = tuple(sorted(tools, key=lambda t: t.name))
        self._by_name = {t.name: t for t in self._tools}
        self._definitions = {t.name: canonical(definition(t)) for t in self._tools}
        self._validators = {
            t.name: Draft202012Validator(t.input_schema, format_checker=FormatChecker())
            for t in self._tools
        }

    @property
    def tools(self):
        """Every tool, in registry order (whatever its surface, stage, effect or gate)."""
        return self._tools

    def tool(self, name):
        return self._by_name[name]

    def offered(self, surface, stage, effects, scope='study', capabilities=frozenset()):
        """The tools a session is offered, in registry order: the tool lists the surface, its
        stage is reached, its effect is held, its scopes include the session's and its gate,
        if any, is advertised. A check (a read that sends a POST) needs a write effect."""
        if surface not in SURFACES or stage not in STAGES or scope not in SCOPES:
            raise ValueError('Unknown surface, stage or scope')
        effects = _effects(effects)
        capabilities = frozenset(capabilities)
        reached = STAGES.index(stage)
        writer = bool(effects & WRITE_EFFECTS)
        return tuple(
            t
            for t in self._tools
            if surface in t.surfaces
            and STAGES.index(t.stage) <= reached
            and t.effect in effects
            and scope in t.scopes
            and (t.gate is None or t.gate in capabilities)
            and (writer or not t.is_check)
        )

    def definitions(self, surface, stage, effects, scope='study', capabilities=frozenset()):
        """The offered tools' definitions, fresh copies of byte-stable canonical JSON."""
        offered = self.offered(surface, stage, effects, scope, capabilities)
        return [json.loads(self._definitions[t.name]) for t in offered]

    def api_operations(self, effects, capabilities=frozenset(), scope='study'):
        """The ``(method, template)`` pairs the tools of ``effects`` call: the registry part of
        the agent route allowlist. A gated tool contributes only when its gate is advertised."""
        effects = _effects(effects)
        capabilities = frozenset(capabilities)
        writer = bool(effects & WRITE_EFFECTS)
        return frozenset(
            operation
            for t in self._tools
            if t.effect in effects
            and scope in t.scopes
            and (t.gate is None or t.gate in capabilities)
            and (writer or not t.is_check)
            for operation in t.api_operations
        )

    def definitions_sha256(self):
        """The digest of every tool definition in registry order (gated tools included)."""
        return digest([json.loads(self._definitions[t.name]) for t in self._tools])

    async def invoke(self, name, arguments, ctx):
        """Run tool ``name`` under ``ctx`` after validating ``arguments``: a tool not offered in
        the session, input above 256 KB or input that breaks the schema is refused before any
        API call. Problems never echo a submitted value."""
        offered = self.offered(ctx.surface, ctx.stage, ctx.effects, ctx.scope, ctx.capabilities)
        tool = next((t for t in offered if t.name == name), None)
        if tool is None:
            raise ToolError(
                'invalid_input',
                'No tool of that name is available in this session.',
                next_step='Call only the tools listed for this session.',
            )
        try:
            size = len(canonical(arguments))
        except (ValueError, TypeError, RecursionError):
            raise ToolError(
                'invalid_input', 'Tool input must be JSON with finite numbers.'
            ) from None
        if size > MAX_INPUT_BYTES:
            raise ToolError(
                'too_large',
                'Tool input is larger than 256 KB.',
                next_step='Split the work into smaller calls.',
            )
        if not isinstance(arguments, dict):
            raise ToolError('invalid_input', 'Tool input must be a JSON object.')
        fields = input_problems(self._validators[name], arguments)
        if fields:
            raise ToolError(
                'invalid_input',
                'The input does not match the tool schema.',
                fields=fields,
                next_step='Fix the listed fields and call ' + name + ' again.',
            )
        if tool.handler is None:
            raise ToolError('unsupported', 'This tool is not served here.')
        return await tool.handler(arguments, ctx)


def _effects(effects):
    effects = frozenset(effects)
    if not effects <= DELEGATION_EFFECTS:
        raise ValueError('Unknown agent effect')
    return effects


def input_problems(validator, arguments):
    """Field problems for ``arguments``, keyed by the tool's own input paths, sorted and
    bounded; the text comes from the schema, never from the submitted values."""
    found = set()
    for error in validator.iter_errors(arguments):
        parts = list(error.absolute_path)
        keyword = error.validator
        instance = error.instance
        if keyword == 'required' and isinstance(instance, dict):
            for key in error.validator_value:
                if key not in instance:
                    found.add((_path(parts + [key]), 'required field is missing'))
        elif keyword == 'additionalProperties' and isinstance(instance, dict):
            # A submitted key may carry data, so it is never named; the allowed names are.
            known = sorted(error.schema.get('properties', {}))
            allowed = ('; allowed fields: ' + ', '.join(known)) if known else ''
            path = _path(parts) + '.(unknown field)' if parts else '(unknown field)'
            found.add((path, ('field is not allowed here' + allowed)[:512]))
        else:
            found.add((_path(parts), _problem(keyword, error.validator_value)))
    ordered = sorted(found)[:MAX_FIELDS]
    return tuple({'path': path, 'problem': problem} for path, problem in ordered)


def _path(parts):
    text = ''
    for part in parts:
        if isinstance(part, int):
            text += '[' + str(part) + ']'
        else:
            name = part if PROPERTY_NAME.fullmatch(str(part)) else '(field)'
            text += ('.' if text else '') + name
    return text or '(input)'


def _problem(keyword, expected):
    if keyword == 'type':
        kinds = expected if isinstance(expected, list) else [expected]
        return 'must be of type ' + ' or '.join(kinds)
    if keyword == 'enum':
        return ('must be one of: ' + ', '.join(json.dumps(v) for v in expected))[:512]
    if keyword == 'const':
        return ('must be ' + json.dumps(expected))[:512]
    bounds = {
        'maxLength': 'must be at most {} characters',
        'minLength': 'must be at least {} characters',
        'maxItems': 'must have at most {} items',
        'minItems': 'must have at least {} items',
        'maxProperties': 'must have at most {} fields',
        'minProperties': 'must have at least {} fields',
        'maximum': 'must be at most {}',
        'minimum': 'must be at least {}',
        'exclusiveMaximum': 'must be less than {}',
        'exclusiveMinimum': 'must be greater than {}',
        'format': 'must be a valid {}',
    }
    if keyword in bounds:
        return bounds[keyword].format(expected)
    if keyword == 'pattern':
        return 'does not have the required form'
    if keyword == 'uniqueItems':
        return 'items must be unique'
    return 'is not valid'


# The registry the application is composed with: the packaged catalogue.
REGISTRY = Registry(catalogue.TOOLS)
PLAYBOOK_SHA256 = digest([{'name': s.name, 'text': s.text} for s in playbook.SECTIONS])
TOOL_DEFINITIONS_SHA256 = REGISTRY.definitions_sha256()
