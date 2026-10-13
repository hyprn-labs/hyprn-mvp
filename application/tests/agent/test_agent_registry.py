"""Tool registry: every tool passes the schema, write-policy and ownership rules before the
registry builds, a session's tool list is a deterministic function of surface, stage, effects,
scope and advertised gates, input is validated before any call, and the agent route allowlist
is exactly the registry's operations plus the runtime's internal reads.
"""

import asyncio
from itertools import combinations
import json
from pathlib import Path
from uuid import uuid4

import pytest

from hyprn_mvp_app import agent_policy
from hyprn_mvp_app.agent_tools import catalogue, playbook, registry as registry_module
from hyprn_mvp_app.agent_tools.registry import (
    LOCAL_STAGE,
    PLAYBOOK_SHA256,
    REGISTRY,
    REGISTRY_VERSION,
    TOOL_DEFINITIONS_SHA256,
    Registry,
    RegistryError,
)
from hyprn_mvp_app.agent_tools.spec import (
    DELEGATION_EFFECTS,
    DESTRUCTIVE_TOOLS,
    SCOPES,
    STAGES,
    SURFACES,
    ToolContext,
    ToolError,
    ToolSpec,
)
from hyprn_mvp_app.contracts import digest

REPO = Path(__file__).resolve().parents[3]
CONTRACT = json.loads((REPO / 'contracts/hyprn-mvp.openapi.yaml').read_text())
S = '/api/1/studies/{study_id}'
EFFECT_SETS = [
    frozenset(c)
    for n in range(len(DELEGATION_EFFECTS) + 1)
    for c in combinations(sorted(DELEGATION_EFFECTS), n)
]
WRITER = frozenset({'read', 'draft', 'record', 'submit', 'outside_study'})
POINTER = ' Guidance: get_playbook("workflow").'


def contract_operations():
    methods = {'get', 'post', 'patch', 'put', 'delete'}
    return {
        (m.upper(), '/api/1' + p)
        for p, ops in CONTRACT['paths'].items()
        for m in ops
        if m in methods
    }


def concrete(template):
    parts = template.split('/')
    return '/'.join(str(uuid4()) if p.startswith('{') else p for p in parts)


async def handled(arguments, ctx):
    handled.calls.append(arguments)
    return {'received': sorted(arguments)}


handled.calls = []


def spec(**overrides):
    """A valid test-only tool; each test overrides what it exercises."""
    fields = dict(
        name='get_example',
        title='Read an example',
        description='Reads an example record of the study.' + POINTER,
        input_schema={'type': 'object', 'additionalProperties': False, 'properties': {}},
        effect='read',
        stage='read_only',
        surfaces=SURFACES,
        owners=('store',),
        outcome='none',
        activity_label='Read: example',
        handler=handled,
        api_operations=(('GET', S),),
    )
    fields.update(overrides)
    return ToolSpec(**fields)


def closed(properties, required=()):
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': list(required),
        'properties': properties,
    }


TEXT = {'type': 'string', 'maxLength': 64}


def ctx(**overrides):
    fields = dict(surface='local_mcp', stage=LOCAL_STAGE, effects=frozenset({'read'}))
    fields.update(overrides)
    return ToolContext(**fields)


# ---- Determinism, hashes and the schema rules of every registered tool ---------------


def test_definitions_are_byte_identical_across_builds_and_input_order():
    first, second = Registry(catalogue.TOOLS), Registry(tuple(reversed(catalogue.TOOLS)))
    for surface in SURFACES:
        for stage in STAGES:
            for scope in SCOPES:
                for effects in EFFECT_SETS:
                    a = first.definitions(surface, stage, effects, scope)
                    b = second.definitions(surface, stage, effects, scope)
                    assert json.dumps(a) == json.dumps(b)
    assert [t.name for t in REGISTRY.tools] == sorted(t.name for t in catalogue.TOOLS)
    assert first.definitions_sha256() == second.definitions_sha256() == TOOL_DEFINITIONS_SHA256


def test_registry_hashes_are_stable_sha256_digests_of_the_playbook_and_the_definitions():
    sections = [{'name': s.name, 'text': s.text} for s in playbook.SECTIONS]
    assert PLAYBOOK_SHA256 == digest(sections)
    definitions = [registry_module.definition(t) for t in REGISTRY.tools]
    assert TOOL_DEFINITIONS_SHA256 == digest(definitions)
    for value in (PLAYBOOK_SHA256, TOOL_DEFINITIONS_SHA256):
        assert len(value) == 64 and int(value, 16) >= 0
    assert REGISTRY_VERSION == '0.1.0' and LOCAL_STAGE == 'read_only'


def walk(node, path='input'):
    yield path, node
    for name, child in node.get('properties', {}).items():
        yield from walk(child, path + '.' + name)
    for key in ('items', 'contains', 'not', 'propertyNames'):
        if isinstance(node.get(key), dict):
            yield from walk(node[key], path + '/' + key)
    for key in ('anyOf', 'oneOf', 'allOf', 'prefixItems'):
        for index, child in enumerate(node.get(key, ())):
            yield from walk(child, path + '/' + key + '/' + str(index))


def test_every_registered_definition_follows_the_schema_rules():
    names = set()
    for surface in SURFACES:
        for scope in SCOPES:
            for item in REGISTRY.definitions(surface, 'runs', WRITER, scope):
                names.add(item['name'])
                assert registry_module.NAME.fullmatch(item['name'])
                assert len(item['description']) < 2048
                assert item['description'].endswith('").')
                assert 'outputSchema' not in item
                schema = item['inputSchema']
                assert schema['type'] == 'object'
                assert not {'anyOf', 'oneOf', 'allOf'} & set(schema)
                assert all(
                    registry_module.PROPERTY_NAME.fullmatch(n) for n in schema.get('properties', {})
                )
                for where, node in walk(schema):
                    assert '$ref' not in node, where
                    assert len(node.get('description', '')) < 2048, where
                    if node.get('type') == 'object':
                        assert node.get('additionalProperties') is False, where
                    if node.get('type') == 'string':
                        assert {'maxLength', 'enum', 'const'} & set(node), where
                    if node.get('type') == 'array':
                        assert 'maxItems' in node, where
                    assert 'study_id' not in node.get('properties', {}), where
    assert names == {t.name for t in REGISTRY.tools if t.gate is None}
    assert 'get_playbook' in names


def test_get_playbook_spec_equals_its_tool_ownership_row():
    # Row: | `get_playbook` | 3.8 | read | none | `agent_tools` (versioned playbook constants)
    #      | none | static guidance; nothing stored |
    tool = REGISTRY.tool('get_playbook')
    assert (tool.effect, tool.api_operations, tool.owners, tool.outcome) == (
        'read',
        (),
        ('agent_tools',),
        'none',
    )
    assert tool.stage == 'read_only' and tool.gate is None and tool.surfaces == SURFACES
    assert tool.activity_label == 'Read: playbook'


def test_every_api_operation_of_an_ungated_tool_and_every_internal_read_is_in_the_contract():
    operations = contract_operations()

    def missing(reg):
        return sorted(
            op
            for t in reg.tools
            if t.gate is None
            for op in t.api_operations
            if op not in operations
        )

    assert missing(REGISTRY) == []
    assert sorted(agent_policy.INTERNAL_READS - operations) == []
    bogus = Registry([spec(api_operations=(('GET', S + '/nowhere'),))])
    assert missing(bogus) == [('GET', S + '/nowhere')]


# ---- Build rules: a spec that breaks one makes the build fail ------------------------

BAD_SPECS = {
    'name not verb_object': dict(name='Get-Example'),
    'name too long': dict(name='get_' + 'x' * 61),
    'forbidden name delete_': dict(name='delete_model', effect='draft', outcome='receipt:model'),
    'forbidden name archive_study': dict(
        name='archive_study', effect='record', outcome='receipt:study'
    ),
    'forbidden name restore_study': dict(
        name='restore_study', effect='record', outcome='receipt:study'
    ),
    'forbidden name unarchive_document': dict(
        name='unarchive_document', effect='record', outcome='receipt:x'
    ),
    'forbidden name remove_member': dict(
        name='remove_member', effect='record', outcome='receipt:x'
    ),
    'forbidden name invite_': dict(name='invite_reviewer', effect='record', outcome='receipt:x'),
    'forbidden name grant_': dict(name='grant_access', effect='record', outcome='receipt:x'),
    'forbidden name mint_': dict(name='mint_token', effect='record', outcome='receipt:x'),
    'forbidden name revoke_': dict(name='revoke_token', effect='record', outcome='receipt:x'),
    'forbidden name change_role': dict(name='change_role', effect='record', outcome='receipt:x'),
    'human-only route archive': dict(
        name='close_study',
        effect='record',
        outcome='receipt:study',
        api_operations=(('POST', S + '/archive'),),
    ),
    'human-only route delete': dict(api_operations=(('DELETE', S + '/evidence/{evidence_id}'),)),
    'human-only route session': dict(api_operations=(('GET', '/api/1/session'),)),
    'open object': dict(input_schema={'type': 'object', 'properties': {}}),
    'nested open object': dict(
        input_schema=closed({'filter': {'type': 'object', 'properties': {}}})
    ),
    '$ref': dict(input_schema=closed({'x': {'$ref': '#/$defs/x'}})),
    'root anyOf': dict(input_schema={**closed({}), 'anyOf': [{'required': []}]}),
    'root oneOf': dict(input_schema={**closed({}), 'oneOf': [{'required': []}]}),
    'root allOf': dict(input_schema={**closed({}), 'allOf': [{'required': []}]}),
    'long top-level property name': dict(input_schema=closed({'p' * 65: TEXT})),
    'bad top-level property characters': dict(input_schema=closed({'a b': TEXT})),
    'unbounded string': dict(input_schema=closed({'name': {'type': 'string'}})),
    'unbounded array': dict(input_schema=closed({'ids': {'type': 'array', 'items': TEXT}})),
    'untyped property': dict(input_schema=closed({'anything': {}})),
    'study_id at the top': dict(input_schema=closed({'study_id': TEXT})),
    'study_id nested': dict(input_schema=closed({'target': closed({'study_id': TEXT})})),
    'revision named expected_version': dict(input_schema=closed({'expected_version': TEXT})),
    'revision named version': dict(input_schema=closed({'version': TEXT})),
    'schema description too long': dict(
        input_schema=closed({'x': {**TEXT, 'description': 'd' * 2048}})
    ),
    'description too long': dict(description='d' * 2048 + POINTER),
    'description without pointer': dict(description='Reads an example record of the study.'),
    'pointer to no section': dict(
        description='Reads an example. Guidance: get_playbook("field_map").'
    ),
    'two pointers': dict(description='Reads an example.' + POINTER + POINTER),
    'no owner': dict(owners=()),
    'no outcome': dict(outcome=None),
    'unknown owner': dict(owners=('scheduler',)),
    'outcome outside the vocabulary': dict(outcome='journal'),
    'read with a receipt outcome': dict(outcome='receipt:study'),
    'write with outcome none': dict(name='add_example', effect='record', outcome='none'),
    'read sending PATCH': dict(api_operations=(('PATCH', S),)),
    'path outside /api/1': dict(api_operations=(('GET', '/mcp'),)),
    'unknown method': dict(api_operations=(('TRACE', S),)),
    'unknown effect': dict(effect='delete'),
    'lifecycle effect': dict(effect='archive'),
    'unknown stage': dict(stage='cloud'),
    'unknown surface': dict(surfaces=('browser',)),
    'no surface': dict(surfaces=()),
    'unknown scope': dict(scopes=('installation',)),
    'approval-forcing client meta': dict(
        client_meta=(('anthropic/requiresUserInteraction', True),)
    ),
    'destructive read': dict(name='edit_model'),
    'synchronous handler': dict(handler=lambda arguments, ctx: None),
    'no handler or runtime operation': dict(handler=None),
    'runtime operation with an API operation': dict(runtime_operation='post_note'),
    'unknown record label': dict(record_label='approved'),
    'since after the registry version': dict(since='9.0.0'),
    'empty activity label': dict(activity_label=''),
}


# The rule each bad spec breaks, as the build names it.
RULES = {
    'name': 'a tool name must match',
    'forbidden': 'the name names a human-only effect',
    'human-only': 'declares a human-only route',
    'closed': 'objects must be closed',
    'ref': '$ref is not allowed',
    'root': 'at the schema root',
    'top-level': 'top-level property name outside',
    'string': 'strings must be bounded',
    'array': 'arrays must be bounded',
    'typed': 'a subschema needs a type, enum or const',
    'study_id': 'no property may be named study_id',
    'revision': 'revision fields are expected_revision or revision_token',
    'schema description': 'description of 2,048 characters or more',
    'description': 'the description must be 1 to 2,047 characters',
    'pointer': 'the description must end with one get_playbook pointer',
    'section': 'the playbook pointer names no section',
    'owner': 'a tool declares at least one owner and its stored outcome',
    'owner vocabulary': 'owners outside the closed owner vocabulary',
    'outcome vocabulary': 'outcome outside the closed outcome vocabulary',
    'read outcome': 'the outcome is none exactly for a read',
    'read method': 'a read tool calls only GET',
    'template': 'an API operation template is a /api/1 route template',
    'method': 'an API operation has a known method',
    'effect': 'unknown effect',
    'stage': 'unknown stage',
    'surfaces': 'surfaces must be a non-empty tuple',
    'scopes': 'scopes must be a non-empty tuple',
    'meta': 'client metadata is only anthropic/alwaysLoad',
    'destructive': 'a tool that replaces shared state or drafts must write',
    'async': 'the handler must be an async function',
    'handler': 'a tool needs a handler or a runtime operation',
    'runtime': 'a runtime operation calls no API operation',
    'label': 'unknown record label',
    'since': 'since is later than the registry version',
    'activity': 'the activity label must be 1 to 64 characters',
}
EXPECTED_RULE = {
    'name not verb_object': 'name',
    'name too long': 'name',
    'human-only route archive': 'human-only',
    'human-only route delete': 'human-only',
    'human-only route session': 'human-only',
    'open object': 'closed',
    'nested open object': 'closed',
    '$ref': 'ref',
    'root anyOf': 'root',
    'root oneOf': 'root',
    'root allOf': 'root',
    'long top-level property name': 'top-level',
    'bad top-level property characters': 'top-level',
    'unbounded string': 'string',
    'unbounded array': 'array',
    'untyped property': 'typed',
    'study_id at the top': 'study_id',
    'study_id nested': 'study_id',
    'revision named expected_version': 'revision',
    'revision named version': 'revision',
    'schema description too long': 'schema description',
    'description too long': 'description',
    'description without pointer': 'pointer',
    'pointer to no section': 'section',
    'two pointers': 'pointer',
    'no owner': 'owner',
    'no outcome': 'owner',
    'unknown owner': 'owner vocabulary',
    'outcome outside the vocabulary': 'outcome vocabulary',
    'read with a receipt outcome': 'read outcome',
    'write with outcome none': 'read outcome',
    'read sending PATCH': 'read method',
    'path outside /api/1': 'template',
    'unknown method': 'method',
    'unknown effect': 'effect',
    'lifecycle effect': 'effect',
    'unknown stage': 'stage',
    'unknown surface': 'surfaces',
    'no surface': 'surfaces',
    'unknown scope': 'scopes',
    'approval-forcing client meta': 'meta',
    'destructive read': 'destructive',
    'synchronous handler': 'async',
    'no handler or runtime operation': 'handler',
    'runtime operation with an API operation': 'runtime',
    'unknown record label': 'label',
    'since after the registry version': 'since',
    'empty activity label': 'activity',
}


@pytest.mark.parametrize('label', sorted(BAD_SPECS))
def test_a_spec_breaking_a_registry_rule_makes_the_build_fail(label):
    bad = spec(**BAD_SPECS[label])
    rule = RULES[EXPECTED_RULE.get(label, 'forbidden')]
    with pytest.raises(RegistryError) as caught:
        Registry([bad])
    assert rule in str(caught.value)
    with pytest.raises(RegistryError) as caught:
        Registry(catalogue.TOOLS + (bad,))
    assert rule in str(caught.value)


def test_every_bad_spec_names_the_rule_it_breaks():
    forbidden = {label for label in BAD_SPECS if label.startswith('forbidden name')}
    assert set(EXPECTED_RULE) | forbidden == set(BAD_SPECS)
    assert set(EXPECTED_RULE.values()) | {'forbidden'} == set(RULES)


def test_duplicate_tool_names_make_the_build_fail():
    with pytest.raises(RegistryError, match='duplicate'):
        Registry([spec(), spec()])


def test_a_valid_test_spec_builds_so_each_bad_case_fails_for_its_own_rule():
    built = Registry(
        [
            spec(),
            spec(
                name='list_examples',
                input_schema=closed(
                    {
                        'cursor': TEXT,
                        'ids': {
                            'type': 'array',
                            'maxItems': 20,
                            'items': {'type': 'string', 'maxLength': 36},
                        },
                    }
                ),
            ),
        ]
    )
    assert [t.name for t in built.tools] == ['get_example', 'list_examples']


# ---- Annotations ----------------------------------------------------------------------


def test_every_tool_emits_all_four_annotations_and_destructive_exactly_for_the_closed_set():
    writes = [
        spec(
            name=name,
            effect='draft',
            outcome='receipt:example',
            api_operations=(('POST', S + '/approach/draft'),),
        )
        for name in sorted(DESTRUCTIVE_TOOLS)
    ]
    additive = spec(
        name='add_example',
        effect='record',
        outcome='receipt:evidence',
        api_operations=(('POST', S + '/evidence'),),
    )
    note = spec(
        name='post_example_note',
        effect='outside_study',
        outcome='runtime:agent_progress_notes',
        api_operations=(),
        handler=None,
        runtime_operation='note',
    )
    built = Registry([*writes, additive, note, spec()])
    hints = {'readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint'}
    for item in built.definitions('local_mcp', 'runs', WRITER):
        assert set(item['annotations']) == hints
        tool = built.tool(item['name'])
        assert item['annotations']['readOnlyHint'] is (tool.effect == 'read')
        assert item['annotations']['destructiveHint'] is (item['name'] in DESTRUCTIVE_TOOLS)
        assert item['annotations']['openWorldHint'] is False
        assert item['annotations']['idempotentHint'] is (tool.effect == 'read')
    for item in REGISTRY.definitions('local_mcp', 'runs', WRITER):
        assert set(item['annotations']) == hints
        assert set(item.get('_meta', {})) <= {'anthropic/alwaysLoad'}
    assert REGISTRY.definitions('local_mcp', LOCAL_STAGE, {'read'})[0]['_meta'] == {
        'anthropic/alwaysLoad': True
    }


# ---- What a session is offered --------------------------------------------------------


def test_a_gated_tool_is_absent_until_its_gate_is_advertised_and_present_after():
    gated = spec(
        name='get_gated_example', gate='example_records', api_operations=(('GET', S + '/approach'),)
    )
    built = Registry([spec(), gated])
    for surface in SURFACES:
        names = [d['name'] for d in built.definitions(surface, LOCAL_STAGE, {'read'})]
        assert names == ['get_example']
        names = [
            d['name']
            for d in built.definitions(
                surface, LOCAL_STAGE, {'read'}, capabilities={'example_records'}
            )
        ]
        assert names == ['get_example', 'get_gated_example']
    assert ('GET', S + '/approach') not in built.api_operations({'read'})
    assert ('GET', S + '/approach') in built.api_operations({'read'}, {'example_records'})
    # A gated tool may carry no API operation (and no owner) until its gate's phase binds one.
    Registry(
        [
            spec(
                name='record_example_review',
                effect='record',
                gate='review_records',
                owners=(),
                outcome=None,
                api_operations=(),
                handler=None,
                record_label='agent-recorded',
            )
        ]
    )


def test_a_workspace_scope_tool_is_listed_only_for_a_workspace_session():
    workspace = spec(
        name='list_example_studies',
        scopes=('workspace',),
        api_operations=(('GET', '/api/1/studies'),),
    )
    built = Registry([spec(), workspace])
    assert [d['name'] for d in built.definitions('claude_managed', LOCAL_STAGE, {'read'})] == [
        'get_example'
    ]
    listed = built.definitions('claude_managed', LOCAL_STAGE, {'read'}, scope='workspace')
    assert [d['name'] for d in listed] == ['list_example_studies']
    assert ('GET', '/api/1/studies') not in built.api_operations({'read'})


def test_a_check_that_sends_a_post_is_offered_only_to_a_delegation_with_a_write_effect():
    check = spec(
        name='validate_example', api_operations=(('POST', S + '/models/{model_id}/validate'),)
    )
    built = Registry([spec(), check])
    for effects in EFFECT_SETS:
        names = [d['name'] for d in built.definitions('local_mcp', 'runs', effects)]
        writer = bool(effects & {'draft', 'record', 'submit'})
        assert ('validate_example' in names) is ('read' in effects and writer)
        assert (('POST', S + '/models/{model_id}/validate') in built.api_operations(effects)) is (
            'read' in effects and writer
        )


def test_stage_surface_and_effect_each_narrow_the_offered_list():
    authoring = spec(
        name='edit_example',
        effect='draft',
        stage='authoring',
        outcome='receipt:model',
        api_operations=(('POST', S + '/models/{model_id}/edits'),),
        surfaces=('claude_managed',),
    )
    built = Registry([spec(), authoring])
    assert [d['name'] for d in built.definitions('claude_managed', 'read_only', WRITER)] == [
        'get_example'
    ]
    assert [d['name'] for d in built.definitions('claude_managed', 'authoring', WRITER)] == [
        'edit_example',
        'get_example',
    ]
    assert [d['name'] for d in built.definitions('local_mcp', 'runs', WRITER)] == ['get_example']
    assert [d['name'] for d in built.definitions('claude_managed', 'runs', {'read'})] == [
        'get_example'
    ]
    for surface, stage, effects, scope in (
        ('browser', 'read_only', {'read'}, 'study'),
        ('local_mcp', 'cloud', {'read'}, 'study'),
        ('local_mcp', 'read_only', {'read'}, 'installation'),
        ('local_mcp', 'read_only', {'delete'}, 'study'),
    ):
        with pytest.raises(ValueError):
            built.definitions(surface, stage, effects, scope)


# ---- The agent route allowlist follows the registry -----------------------------------


def test_agent_policy_allows_only_registry_pairs_and_internal_reads_never_human_only():
    operations = contract_operations()
    reads = spec(api_operations=(('GET', S), ('GET', S + '/evidence')))
    built = Registry([reads])
    for reg in (None, built):
        source = REGISTRY if reg is None else reg
        for effects in EFFECT_SETS:
            allowed = agent_policy.allowed_operations(effects, registry=reg)
            assert allowed == source.api_operations(effects) | agent_policy.INTERNAL_READS
            for method, template in operations:
                expected = (method, template) in allowed
                assert (
                    agent_policy.route_allowed(method, concrete(template), effects, registry=reg)
                    is expected
                )
                if registry_module.write_policy.is_human_only(method, template):
                    assert not expected
    assert agent_policy.route_allowed(
        'GET', '/api/1/studies/' + str(uuid4()), {'read'}, registry=built
    )
    assert not agent_policy.route_allowed(
        'GET', '/api/1/studies/' + str(uuid4()), {'outside_study'}, registry=built
    )
    assert not agent_policy.route_allowed('GET', '/api/1/studies/' + str(uuid4()), {'read'})
    with pytest.raises(ValueError):
        agent_policy.route_allowed('GET', '/api/1/capabilities', {'delete'})


# ---- Invocation validates before any call ---------------------------------------------


def test_invoke_validates_the_input_before_the_handler_runs_and_never_echoes_a_value():
    secret = 'value-' + uuid4().hex
    schema = closed(
        {'name': TEXT, 'items': {'type': 'array', 'maxItems': 2, 'items': {'type': 'integer'}}},
        ['name'],
    )
    big = closed({'blob': {'type': 'string', 'maxLength': 600000}})
    built = Registry([spec(input_schema=schema), spec(name='get_blob', input_schema=big)])
    handled.calls.clear()
    assert asyncio.run(built.invoke('get_example', {'name': 'ok'}, ctx())) == {'received': ['name']}
    assert handled.calls == [{'name': 'ok'}]
    handled.calls.clear()
    cases = {
        'wrong type': ({'name': 7}, {'name'}),
        'missing field': ({}, {'name'}),
        'unknown field': ({'name': 'ok', secret: secret}, {'(unknown field)'}),
        'unknown field named study_id': ({'name': 'ok', 'study_id': secret}, {'(unknown field)'}),
        'too long': ({'name': secret * 10}, {'name'}),
        'nested item': ({'name': 'ok', 'items': [1, secret]}, {'items[1]'}),
        'boolean posing as a number': ({'name': 'ok', 'items': [True]}, {'items[0]'}),
    }
    for label, (arguments, paths) in cases.items():
        with pytest.raises(ToolError) as caught:
            asyncio.run(built.invoke('get_example', arguments, ctx()))
        error = caught.value
        assert error.category == 'invalid_input', label
        assert {f['path'] for f in error.fields} == paths, label
        assert secret not in json.dumps(error.envelope()), label
    for arguments in ([], 'text', {'name': float('nan')}):
        with pytest.raises(ToolError) as caught:
            asyncio.run(built.invoke('get_example', arguments, ctx()))
        assert caught.value.category == 'invalid_input'
    with pytest.raises(ToolError) as caught:
        asyncio.run(built.invoke('get_blob', {'blob': 'x' * (256 * 1024)}, ctx()))
    assert caught.value.category == 'too_large'
    assert handled.calls == []


def test_invoke_refuses_a_tool_the_session_is_not_offered():
    authoring = spec(
        name='edit_example',
        effect='draft',
        stage='authoring',
        outcome='receipt:model',
        api_operations=(('POST', S + '/models/{model_id}/edits'),),
    )
    built = Registry([spec(), authoring])
    handled.calls.clear()
    refused = [
        ('edit_example', ctx(effects=WRITER)),
        ('edit_example', ctx(stage='authoring')),
        ('unknown_tool', ctx()),
        ('get_example', ctx(effects=frozenset({'outside_study'}))),
    ]
    for name, context in refused:
        with pytest.raises(ToolError) as caught:
            asyncio.run(built.invoke(name, {}, context))
        assert caught.value.category == 'invalid_input'
    assert handled.calls == []
    assert asyncio.run(
        built.invoke('edit_example', {}, ctx(stage='authoring', effects=WRITER))
    ) == {'received': []}
