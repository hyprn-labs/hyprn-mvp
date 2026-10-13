"""Human-only effects (ADR-0003): no agent tool, on any surface or stage, for any delegation or
advertised gate, deletes a saved record, archives, restores or manages access, by name or by
API operation; every human-only route of the public contract is refused for every agent effect
set, whatever a registry declares; study creation and approach draft restore are not human-only
and are reachable exactly when a registered tool of the session's effects uses them; working
material (draft annotations) may be deleted only once a registered tool declares its route.
"""

from itertools import combinations, product
import json
from pathlib import Path
from uuid import uuid4

import pytest

from hyprn_mvp_app import agent_policy
from hyprn_mvp_app.agent_tools import catalogue
from hyprn_mvp_app.agent_tools.registry import REGISTRY, Registry, RegistryError, forbidden_name
from hyprn_mvp_app.agent_tools.spec import DELEGATION_EFFECTS, SCOPES, STAGES, SURFACES, ToolSpec
from hyprn_mvp_app.agent_tools.write_policy import (
    ACCESS_MANAGEMENT,
    BACKUP_AND_IMPORT,
    HUMAN_ONLY,
    LIFECYCLE,
    SAVED_RECORD_DELETION,
    WORKING_MATERIAL,
    is_human_only,
    route_category,
)

REPO = Path(__file__).resolve().parents[3]
CONTRACT = json.loads((REPO / 'contracts/hyprn-mvp.openapi.yaml').read_text())
DOCUMENT_ROUTES = json.loads((REPO / 'contracts/schemas/model.schema.json').read_text())[
    'x-hyprn-mvp-documents-contract'
]['routes']
S = '/api/1/studies/{study_id}'
EFFECT_SETS = [
    frozenset(c)
    for n in range(len(DELEGATION_EFFECTS) + 1)
    for c in combinations(sorted(DELEGATION_EFFECTS), n)
]
WRITER = frozenset({'read', 'draft', 'record', 'submit', 'outside_study'})
DRAFT_RESTORE = ('POST', S + '/approach/draft/restore')
STUDY_CREATION = ('POST', '/api/1/studies')
ANNOTATION_DELETE = ('DELETE', S + '/document-versions/{version_id}/annotations/{annotation_id}')


def contract_operations():
    methods = {'get', 'post', 'patch', 'put', 'delete'}
    return {
        (m.upper(), '/api/1' + p)
        for p, ops in CONTRACT['paths'].items()
        for m in ops
        if m in methods
    }


def concrete(template):
    return '/'.join(str(uuid4()) if p.startswith('{') else p for p in template.split('/'))


async def handled(arguments, ctx):
    return {}


def tool(name, effect, operation, owner, outcome):
    return ToolSpec(
        name=name,
        title='Test tool',
        description='A test-only tool. Guidance: get_playbook("workflow").',
        input_schema={'type': 'object', 'additionalProperties': False, 'properties': {}},
        effect=effect,
        stage='read_only',
        surfaces=SURFACES,
        owners=(owner,),
        outcome=outcome,
        activity_label='Test',
        handler=handled,
        api_operations=(operation,),
    )


class DeclaresEverything:
    """Stands in for a registry that (wrongly) declares every human-only route."""

    def __init__(self, operations):
        self.operations = frozenset(operations)

    def api_operations(self, effects, capabilities=frozenset()):
        return self.operations


def test_no_tool_on_any_surface_or_stage_deletes_saved_records_archives_restores_or_grants():
    gates = frozenset(t.gate for t in REGISTRY.tools if t.gate is not None)
    offered = 0
    for surface, stage, scope, effects, capabilities in product(
        SURFACES, STAGES, SCOPES, EFFECT_SETS, (frozenset(), gates)
    ):
        for item in REGISTRY.offered(surface, stage, effects, scope, capabilities):
            offered += 1
            assert not forbidden_name(item.name), item.name
            assert not [op for op in item.api_operations if is_human_only(*op)], item.name
        operations = REGISTRY.api_operations(effects, capabilities, scope)
        assert not [op for op in operations if is_human_only(*op)]
    assert offered > 0
    for item in REGISTRY.offered('local_mcp', 'runs', WRITER, 'study', gates):
        assert item.effect in {'read', 'draft', 'record', 'submit', 'outside_study'}


def test_every_human_only_contract_operation_is_refused_for_every_agent_effect_set():
    operations = contract_operations()
    human = {op for op in operations if is_human_only(*op)}
    # Never vacuous: the archive, restore and session routes are in the contract and human-only.
    required = {('POST', S + '/archive'), ('POST', S + '/restore'), ('POST', '/api/1/session')}
    assert required <= operations and required <= human
    assert ('DELETE', '/api/1/session') in human
    assert {op for op in operations if op[0] == 'DELETE'} <= human
    stub = DeclaresEverything(human)
    for effects in EFFECT_SETS:
        assert not agent_policy.allowed_operations(effects) & human
        assert not agent_policy.allowed_operations(effects, registry=stub) & human
        for method, template in sorted(human):
            path = concrete(template)
            assert not agent_policy.route_allowed(method, path, effects), (method, template)
            assert not agent_policy.route_allowed(method, path, effects, registry=stub)


def test_study_creation_and_approach_draft_restore_are_not_human_only():
    operations = contract_operations()
    for operation in (STUDY_CREATION, DRAFT_RESTORE, ('GET', '/api/1/commands/{command_id}')):
        assert operation in operations
        assert route_category(*operation) is None


def test_approach_draft_restore_is_allowed_exactly_when_the_effects_include_draft():
    restore = tool(
        'restore_approach_draft', 'draft', DRAFT_RESTORE, 'approach', 'receipt:approach_restore'
    )
    built = Registry([restore])
    for effects in EFFECT_SETS:
        path = concrete(DRAFT_RESTORE[1])
        allowed = agent_policy.route_allowed('POST', path, effects, registry=built)
        assert allowed is ('draft' in effects)
        packaged = agent_policy.route_allowed('POST', path, effects)
        assert packaged is (DRAFT_RESTORE in REGISTRY.api_operations(effects))


def test_study_creation_is_allowed_exactly_when_a_registered_record_tool_uses_it():
    create = tool('create_study', 'record', STUDY_CREATION, 'store', 'receipt:study_create')
    built = Registry([create])
    for effects in EFFECT_SETS:
        allowed = agent_policy.route_allowed('POST', '/api/1/studies', effects, registry=built)
        assert allowed is ('record' in effects)
        packaged = agent_policy.route_allowed('POST', '/api/1/studies', effects)
        assert packaged is (STUDY_CREATION in REGISTRY.api_operations(effects))


def test_draft_annotation_deletion_is_working_material_and_refused_until_a_tool_declares_it():
    assert route_category(*ANNOTATION_DELETE) == WORKING_MATERIAL
    assert not is_human_only(*ANNOTATION_DELETE)
    declared = any(ANNOTATION_DELETE in t.api_operations for t in REGISTRY.tools)
    path = concrete(ANNOTATION_DELETE[1])
    for effects in EFFECT_SETS:
        assert agent_policy.route_allowed('DELETE', path, effects) is (
            declared and ANNOTATION_DELETE in REGISTRY.api_operations(effects)
        )
    annotate = tool(
        'remove_draft_annotation', 'draft', ANNOTATION_DELETE, 'store', 'receipt:annotation'
    )
    built = Registry([annotate])
    for effects in EFFECT_SETS:
        allowed = agent_policy.route_allowed('DELETE', path, effects, registry=built)
        assert allowed is ('draft' in effects)


def test_document_routes_are_classified_by_the_closed_human_only_classification():
    expected_families = {
        'delete': SAVED_RECORD_DELETION,
        'restore': BACKUP_AND_IMPORT,
        'import': BACKUP_AND_IMPORT,
    }
    seen = set()
    for route in DOCUMENT_ROUTES:
        operation = (route['method'], S + '/' + route['path'])
        category = route_category(*operation)
        seen.add(category)
        if route['family'] in expected_families:
            assert category == expected_families[route['family']], operation
        elif operation == ('DELETE', S + '/document-collections/{collection_id}'):
            assert category == SAVED_RECORD_DELETION
        elif operation in {
            ('POST', S + '/documents/{document_id}/archive'),
            ('POST', S + '/documents/{document_id}/unarchive'),
        }:
            assert category == LIFECYCLE
        elif operation == ANNOTATION_DELETE:
            assert category == WORKING_MATERIAL
        else:
            assert category is None, operation
    assert {SAVED_RECORD_DELETION, LIFECYCLE, BACKUP_AND_IMPORT, WORKING_MATERIAL, None} <= seen


@pytest.mark.parametrize(
    'method, path, category',
    [
        ('POST', S + '/archive', LIFECYCLE),
        ('POST', S + '/restore', LIFECYCLE),
        ('POST', '/api/1/session', ACCESS_MANAGEMENT),
        ('DELETE', '/api/1/session', ACCESS_MANAGEMENT),
        ('PUT', S + '/memberships/{actor_id}', ACCESS_MANAGEMENT),
        ('POST', S + '/invitations', ACCESS_MANAGEMENT),
        ('POST', S + '/grants', ACCESS_MANAGEMENT),
        ('GET', S + '/delegations', ACCESS_MANAGEMENT),
        ('GET', S + '/agent/attribution', ACCESS_MANAGEMENT),
        ('POST', S + '/agent/tokens/{token_id}/revoke', ACCESS_MANAGEMENT),
        ('GET', '/api/1/agent/attribution/studies', ACCESS_MANAGEMENT),
        ('POST', '/api/1/agent/sessions', ACCESS_MANAGEMENT),
        ('DELETE', S + '/evidence/{evidence_id}', SAVED_RECORD_DELETION),
        ('DELETE', S + '/models/{model_id}', SAVED_RECORD_DELETION),
        ('POST', S + '/document-deletions/commit', SAVED_RECORD_DELETION),
        ('POST', S + '/document-restores', BACKUP_AND_IMPORT),
        ('PUT', S + '/document-imports/{upload_id}/chunks/{offset}', BACKUP_AND_IMPORT),
        ('GET', S, None),
        ('PATCH', S, None),
        ('POST', S + '/evidence', None),
        ('POST', S + '/runs', None),
        ('GET', '/api/1/sessions', None),
    ],
)
def test_route_category_classifies_templates_and_concrete_paths_alike(method, path, category):
    assert route_category(method, path) == category
    assert route_category(method.lower(), concrete(path)) == category
    assert is_human_only(method, path) is (category in HUMAN_ONLY)


def test_a_mis_registered_tool_with_a_human_only_route_or_a_forbidden_name_fails_the_build():
    bad = [
        tool('close_study', 'record', ('POST', S + '/archive'), 'store', 'receipt:study_archive'),
        tool(
            'reopen_document',
            'record',
            ('POST', S + '/documents/{document_id}/unarchive'),
            'store',
            'receipt:x',
        ),
        tool(
            'drop_collection',
            'record',
            ('DELETE', S + '/document-collections/{collection_id}'),
            'store',
            'receipt:x',
        ),
        tool(
            'share_study',
            'record',
            ('PUT', S + '/memberships/{actor_id}'),
            'store',
            'receipt:membership',
        ),
        tool('restore_backup', 'record', ('POST', S + '/document-restores'), 'store', 'receipt:x'),
        tool('import_documents', 'record', ('POST', S + '/document-imports'), 'store', 'receipt:x'),
        tool('sign_out', 'record', ('DELETE', '/api/1/session'), 'store', 'receipt:x'),
    ]
    names = [
        'archive_study',
        'restore_study',
        'archive_document',
        'unarchive_document',
        'delete_evidence',
        'remove_member',
        'invite_member',
        'grant_role',
        'mint_token',
        'revoke_token',
        'change_role',
    ]
    bad += [
        tool(name, 'record', ('POST', S + '/evidence'), 'store', 'receipt:evidence')
        for name in names
    ]
    for item in bad:
        with pytest.raises(RegistryError):
            Registry(catalogue.TOOLS + (item,))
    for name in (
        'create_study',
        'restore_approach_draft',
        'record_scientific_review',
        'request_scientific_review',
    ):
        assert not forbidden_name(name)
