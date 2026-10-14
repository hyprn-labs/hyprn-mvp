"""Fail-closed, stdlib-only test-group runner for the repository.

Every group has a class (``must-pass`` or ``opt-in``) and environment needs
(``docker``, ``browser``, ``fixtures``). A missing target, fixture capability or
environment need fails the group with a refusal; it never passes or silently skips.

    ./hyprn-mvp dev check --list [--class must-pass]
    ./hyprn-mvp dev check <group>
    ./hyprn-mvp dev check qualification [--jobs N]

``qualification`` is the phase gate: every must-pass group, each in its own scope, at most
``--jobs`` at once (default 3; ``--jobs 1`` runs them one after the other). Groups that share
an ordering dependency or a fixed resource are serialized (``SERIAL_LANES``,
``EXCLUSIVE_GROUPS``). After a failure no group starts; running groups finish. Results are
printed in qualification order, whatever order the groups finish in.
``./hyprn-mvp dev check`` provisions the locked environments of ``uv.lock`` and runs this
runner in the native one; a group run under any other interpreter is refused, and every
scoped child runs under the locked interpreter its group names.
"""
import argparse
import ast
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'deployment/tests'))
import scoped_fixture as fixture  # noqa: E402

FINDINGS_NATIVE_GROUPS = frozenset({"findings-native-guards", "findings-native-preflight", "findings-native", "findings-native-read"})

GROUPS = {
    "findings-native-guards": ("deployment/tests/test_findings_native_guards.py",),
    "findings-native-preflight": ("deployment/tests/findings_native_fixture.py",),
    "findings-native": ("deployment/tests/findings_native_fixture.py", "deployment/tests/test_findings_native.py::test_new_downstream_run_pins_retained_source_and_approach", "ui/tests/findings-native.spec.ts"),
    "findings-native-read": ("deployment/tests/findings_native_fixture.py", "deployment/tests/test_findings_native.py::test_recorded_findings_read_only", "ui/tests/findings-native.spec.ts"),
    'units-guards': ('deployment/tests/test_repository_guard.py', 'deployment/tests/test_units_fixture_guards.py'),
    'units-contracts': ('contracts/tests/test_unit_declaration_contracts.py',),
    'units-staging': ('deployment/tests/test_units_fixture_guards.py',),
    'units-model': ('modeling/tests/test_unit_declarations.py', 'modeling/tests/test_resolved_configuration.py', 'modeling/tests/test_native_generation.py'),
    'units-api': ('application/tests/test_unit_guidance_api.py',),
    'units-public-types': ('application/tests/test_unit_guidance_api.py',),
    'units-resolution': ('application/tests/test_unit_resolution.py',),
    'units-configuration': ('application/tests/test_unit_configuration.py',),
    'units-bundle': ('application/tests/test_unit_execution_admission.py',),
    'units-history': ('application/tests/test_unit_history.py',),
    'units-launcher': ('integration/tests/test_unit_execution.py',),
    'units-worker': ('integration/tests/test_unit_worker.py', 'integration/tests/test_native_program.py'),
    'units-attestation': ('deployment/tests/test_attestation.py',),
    'units-native': ('deployment/tests/units_native_fixture.py', 'deployment/tests/test_units_native.py'),
    'units-ui-authoring': ('deployment/tests/units_ui_fixture.py', 'ui/tests/unit-authoring.spec.ts'),
    'units-ui-configuration': ('deployment/tests/units_ui_fixture.py', 'ui/tests/unit-configuration.spec.ts'),
    'units-ui-reading': ('deployment/tests/units_ui_fixture.py', 'ui/tests/unit-model-reading.spec.ts'),
    'units-ui-history': ('deployment/tests/units_ui_fixture.py', 'ui/tests/unit-history.spec.ts'),
    'investigation-diagnostics': ('integration/tests/test_investigation_diagnostics.py',),
    'investigation-worker': ('integration/tests/test_approach_execution.py::test_failed_native_outputs_are_not_valid_zero[throw]',),
    'investigation-evidence': ('application/tests/test_assumption_configuration.py::test_duplicate_input_evidence_is_field_error_before_save',),
    'investigation-native': ('deployment/tests/test_investigation_native.py',),
    'fuel-platform': ('application/tests/test_fuel_platform.py',),
    'fuel-native-provenance': ('integration/tests/test_fuel_native_provenance.py',),
    # An owned modeling deployment set up by modeling_runtime inside the scope: no launcher,
    # container socket or foreign store.
    'modeling-isolation': ('deployment/tests/modeling_deployment_fixture.py', 'deployment/tests/test_modeling_isolation.py'),
    'approach-contracts': ('contracts/tests/test_approach_contracts.py', 'deployment/tests/test_repository_guard.py'),
    'approach-closure': ('application/tests/test_approach_closure.py', 'application/tests/test_approach_storage.py'),
    'approach-service': ('application/tests/test_approach_service.py',),
    'approach-api': ('application/tests/test_approach_api.py',),
    'approach-configuration': ('application/tests/test_approach_configuration.py', 'application/tests/test_scientific_configuration.py'),
    'approach-bundle': ('application/tests/test_approach_bundle.py', 'integration/tests/test_approach_submission.py'),
    'approach-worker': ('integration/tests/test_approach_execution.py', 'integration/tests/test_native_program.py'),
    'findings-history': ('application/tests/test_findings_history.py',),
    'approach-history': ('application/tests/test_approach_history.py', 'application/tests/test_approach_modified_runs.py'),
    'approach-export': ('application/tests/test_approach_export.py', 'integration/tests/test_approach_archive.py', 'contracts/tests/test_approach_portability.py'),
    'approach-native': ('deployment/tests/approach_native_fixture.py', 'deployment/tests/test_approach_native.py'),
    'approach-ui-controller': ('deployment/tests/approach_ui_fixture.py', 'ui/tests/approach.spec.ts'),
    'approach-ui-reading': ('deployment/tests/approach_ui_fixture.py', 'ui/tests/approach.spec.ts'),
    'approach-ui-method': ('deployment/tests/approach_ui_fixture.py', 'ui/tests/approach.spec.ts'),
    'approach-ui-assumptions': ('deployment/tests/approach_ui_fixture.py', 'ui/tests/approach.spec.ts'),
    'approach-ui-configuration': ('deployment/tests/approach_ui_fixture.py', 'ui/tests/approach.spec.ts'),
    'approach-ui-history': ('deployment/tests/approach_ui_fixture.py', 'ui/tests/approach.spec.ts'),

    'ae-contracts': ('contracts/tests/test_assumptions_evidence_contracts.py',),
    'ae-generated': ('application/tests/test_assumptions_evidence_api.py',),
    'ae-public': ('application/tests/test_assumptions_evidence_api.py',),
    'ae-evidence': ('application/tests/test_evidence_revisions.py',),
    'ae-model': ('modeling/tests/test_assumptions.py', 'modeling/tests/test_ui_discovery.py'),
    'ae-authoring': ('application/tests/test_assumption_authoring.py',),
    'ae-configuration': ('application/tests/test_assumption_configuration.py', 'application/tests/test_scientific_configuration.py'),
    'ae-execution': ('integration/tests/test_assumptions_execution.py',),
    'ae-history': ('application/tests/test_assumptions_history.py',),
    'ae-export': ('application/tests/test_assumptions_export.py',),
    'ae-native': ('deployment/tests/test_assumptions_evidence_journey.py',),
    'ae-ui-evidence': ('ui/tests/assumptions-evidence.spec.ts', 'deployment/tests/ae_ui_fixture.py'),
    'ae-ui-model': ('ui/tests/assumptions-evidence.spec.ts', 'deployment/tests/ae_ui_fixture.py'),
    'ae-ui-configuration': ('ui/tests/assumptions-evidence.spec.ts', 'deployment/tests/ae_ui_fixture.py'),
    'guard': ('deployment/tests/test_repository_guard.py',),
    'naming': ('deployment/tests/test_naming_guard.py',),
    'hygiene': ('deployment/tests/test_hygiene_guard.py',),
    # Readability ratchet (deployment/style_ratchet.py): ruff and prettier at their pins, no new
    # long or ;-chained line, every new file formatted. A missing tool or baseline fails.
    'style-ratchet': ('deployment/tests/test_style_ratchet.py',),
    'contracts': ('contracts/tests/test_reuse_contract.py', 'contracts/tests/test_ui_discovery_contract.py',
                  'contracts/tests/test_native_program_contract.py'),
    'projection': ('application/tests/test_scientific_configuration.py', 'modeling/tests/test_resolved_configuration.py'),
    'bindings': ('application/tests/test_result_bindings.py',
        'integration/tests/test_submission.py::test_fault_windows_never_blindly_redispatch',
        'integration/tests/test_submission.py::test_prepared_bundle_is_durable_before_claim_and_survives_model_outage',
        'integration/tests/test_submission.py::test_same_command_concurrency_restart_and_payload_conflict'),
    'native-bindings': ('integration/tests/test_result_dependencies.py',),
    'native-a': ('deployment/tests/test_native_journey.py::test_isolated_runtime_root_refusals', 'deployment/tests/test_native_journey.py::test_addition_a'),
    'native-b': ('deployment/tests/test_native_journey.py::test_isolated_runtime_root_refusals', 'deployment/tests/test_native_journey.py::test_addition_b'),
    'bridge-history': ('deployment/tests/test_bridge.py', 'application/tests/test_history_reuse.py',
        'integration/tests/test_results.py::test_retained_versions_read_without_worker_modeling_or_reassessment',
        'integration/tests/test_results.py::test_retained_reader_rejects_corruption_or_reports_unsupported',
        'integration/tests/test_results.py::test_unknown_stored_outcome_version_is_partial_diagnostic'),
    'runtime-observation': ('application/tests/test_readiness.py', 'application/tests/test_runtime_comparison.py'),
    'api-a': ('application/tests/test_reuse_api.py', 'application/tests/test_study_archive.py', 'application/tests/test_history.py',
              'application/tests/test_store_location.py',
              'application/tests/test_run_status.py',
              'application/tests/test_receipt_recovery.py'),
    'ui-a': ('ui/tests/result-bindings.spec.ts', 'ui/check_ui_contract.py'),
    'ui-a-retained': ('ui/tests/result-bindings.spec.ts', 'ui/check_ui_contract.py'),
    'modified': ('application/tests/test_modified_runs.py',),
    'ui-b': ('ui/tests/modified-runs.spec.ts',),
    'archive-accounting': tuple('integration/tests/test_computational_archive.py::'+n for n in ('test_accounting_duplicate_objects_keep_all_logical_paths','test_accounting_bounds_and_identity_are_not_deduplicated','test_accounting_nested_cache_is_separate_and_only_after_inspection','test_accounting_nested_archives_remain_bounded','test_accounting_same_bytes_still_require_authorized_occurrence','test_actual_archive_inventory_and_readback','test_bounds_before_transfer','test_exact_computational_closure_shared_code_no_unrelated_descendants')),
    'archive-diagnostics': ('integration/tests/test_computational_archive.py::test_actual_launcher_envelope_matches_stored_result', 'integration/tests/test_computational_archive.py::test_license_documentation_allowance_is_exact'),
    'archive-native': ('integration/tests/test_computational_archive.py',),
    'archive-service': ('application/tests/test_computational_records.py',),
    'archive-bridge': ('deployment/tests/test_bridge.py',),
    'api-c': ('application/tests/test_computational_api.py',),
    'ui-c': ('ui/tests/computational-records.spec.ts', 'ui/check_ui_contract.py'),
    'combined-security': (
        'application/tests/test_history_reuse.py::test_real_source_disappearance_across_bridge_fails_closed_without_redispatch',
        'application/tests/test_computational_records.py::test_owned_crash_rebuild_preserves_identity_and_inventory',
        'application/tests/test_computational_records.py::test_owned_lock_and_generation_cas',
        'application/tests/test_computational_records.py::test_rebuilt_native_inventory_change_requires_new_preview',
        'integration/tests/test_computational_archive.py::test_metadata_race_blocks_archive_release',
        'integration/tests/test_computational_archive.py::test_actual_archive_tampering_blocks_release'),
    'combined-native': ('deployment/tests/test_native_journey.py::test_combined',),
    'combined-static': ('ui/check_design_system.py','ui/design_tokens.py','ui/check_ui_contract.py','ui/control-map.json','ui/tests/criterion-record.test.cjs','ui/tsconfig.json','ui/vite.config.ts'),
    # Managers, release tooling and the backup tool against synthetic releases; no Git history.
    'deployment-hardening': ('deployment/tests/test_deployment_hardening.py', 'deployment/tests/test_initialize_stores.py',
                             'deployment/tests/test_term_scan.py', 'deployment/tests/test_topology.py'),
    # Isolated browser groups on the in-browser API double; never a served installation.
    'foundry-nav': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
                    'ui/tests/model-configuration-run.spec.ts', 'ui/tests/foundry-zoom.spec.ts'),
    'ported-isolated': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
                        'ui/tests/command-recovery.spec.ts', 'ui/tests/history-races-isolated.spec.ts'),
    'ui-navigation': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
                      'ui/tests/study-navigation.spec.ts'),
    'ui-reading': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
                   'ui/tests/screen-readability.spec.ts', 'ui/tests/evidence-workspace.spec.ts',
                   'ui/tests/record-labels.spec.ts'),
    # Opt-in: visual comparison with the design-system reference images; refused while
    # design-system/reference/ is absent.
    'ui-fidelity': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
                    'ui/tests/prototype-fidelity.spec.ts'),
    # Opt-in: specs that need a served installation named by HYPRN_MVP_UI_BASE_URL and
    # HYPRN_MVP_UI_PASSWORD_FILE. They write studies, so only an installation created for
    # testing may serve them; the development installation's port and live ports are refused.
    'ui-served': ('ui/playwright.config.ts', 'ui/tests/support/served.ts', 'ui/tests/evidence.ts',
                  *('ui/tests/' + name + '.spec.ts' for name in (
                      'authoring', 'authoring-dirty', 'authoring-evidence-records', 'batch-authoring',
                      'configuration-evidence', 'connected-views', 'model-revision-journey', 'overview',
                      'overview-states', 'paste-guard', 'run-history', 'served-read-only-inspection',
                      'source-editor', 'source-import-races', 'submission-scope', 'variables', 'workspace'))),
    # The public API against the modeling deployment owned by the scope (sessions, Origin and CSRF,
    # authorization and revocation, configuration, runs, contract conformance, static assets).
    'public-api': tuple('application/tests/' + name + '.py' for name in (
        'test_api', 'test_configuration', 'test_public_contract', 'test_run_api', 'test_security_regressions',
        'test_ui_static')),
    # Model revision discovery and scoped evidence through the public API, backed by the confined
    # private adapter in disposable Rails containers on the pinned producer image. Not selected:
    # the two accepted prepare-execution cases of the evidence snapshot pair test (legacy, paired),
    # whose native static generation fails inside the harness, which overlays an earlier
    # modeling_contract.rb on the current producer image; their refusal cases are selected.
    'public-discovery': ('application/tests/test_ui_discovery.py',
                         *('application/tests/test_scoped_evidence.py::' + name for name in (
                             'test_all_exact_scope_variants_survive_restart_and_offline_discovery',
                             'test_repeated_instance_ports_are_distinct_and_resolve_the_pinned_version',
                             'test_invalid_or_foreign_reference_creates_no_evidence_or_receipt',
                             'test_current_authority_closed_requests_and_original_command_replay',
                             'test_legacy_mixed_paging_filters_and_serialized_rows_are_unchanged',
                             'test_full_scope_freezes_and_tampering_cannot_strip_or_replace_it',
                             'test_scope_schema_pair_is_closed_and_snapshot_pair_is_all_or_neither',
                             'test_existing_foreign_resources_are_not_accepted_into_another_study',
                             'test_model_scoped_evidence_replay_is_local_after_restart_with_current_authority',
                             *('test_private_evidence_snapshot_pair_is_enforced_on_real_http[' + case + ']' for case in (
                                 'configuration-compatibility-legacy', 'configuration-compatibility-paired',
                                 'configuration-compatibility-version_only', 'configuration-compatibility-scope_only',
                                 'prepare-execution-version_only', 'prepare-execution-scope_only'))))),
    # Owner provisioning, sessions, Origin/CSRF, login throttling and recovery; study membership,
    # single-writer receipts, compare-and-swap and revocation in the application store.
    'access-control': ('application/tests/test_authorization.py', 'application/tests/test_ownership.py'),
    'local-edition': ('editions/local/tests/test_shim.py', 'editions/local/tests/test_paths.py'),
    # The installation configuration: closed schema, stdlib loader, file safety and location refusals.
    'installation-config': ('deployment/tests/test_installation_config.py',),
    # Operating-system folder layout only in the path policy; no absolute home path in tracked files.
    'portability': ('deployment/tests/test_portability_guard.py',),
    # The backend-independent modeling contract suite (authentication, atomic edits, stale replay,
    # preview purity, compatibility, preparation, portability into a fresh store) against two
    # private services owned by the scope (deployment/tests/modeling_contract_fixture.py).
    'modeling-contract': ('contracts/tests/test_contract_boundaries.py', 'contracts/tests/test_modeling_contract.py',
                          'contracts/tests/test_portability.py', 'modeling/tests/test_atomic_adapter.py'),
    # Native execution in the scope's own backend and attested worker: result parsing, profile and
    # store identity, containment canaries, scalar execution, and the read-only proof over the
    # failed record retained by the real run listed just before it. Not selected:
    # test_history_read.py::test_actual_schema1_remains_data_only_and_byte_identical, which needs a
    # historical schema1 native record that no fresh scope can contain.
    'native-execution': ('integration/tests/test_native_parser.py', 'integration/tests/test_profile_identity.py',
                         'integration/tests/test_isolation.py', 'integration/tests/test_execution.py',
                         'integration/tests/test_results.py::test_real_native_criteria_and_failed_raw_artifacts_are_retained',
                         'integration/tests/test_history_read.py::test_actual_retained_failed_record_exact_results_and_artifacts',
                         'integration/tests/test_history_read.py::test_native_read_rejects_every_forged_association_before_bytes'),
    # Golden identity corpus, contract dependency boundary and field-level contract errors.
    'locality-contracts': ('application/tests/test_identity_golden.py', 'application/tests/test_module_boundaries.py',
                           'application/tests/test_contract_errors.py'),
}


# Documents groups are named after the capability their tests cover. Python targets
# select the functions named test_<group with underscores>_*; browser targets carry the
# @<group> tag. Registration never grants native privilege.
DOCUMENTS_ROUTES = {
    'documents-native-atomicity': {'mode': 'native',
        'targets': ('integration/tests/test_documents_native.py',),
        'selector': 'test_documents_native_atomicity_'},
    'documents-native-originals': {'mode': 'native',
        'targets': ('integration/tests/test_documents_native.py',),
        'selector': 'test_documents_native_originals_'},
    'documents-collection-protocol': {'mode': 'native',
        'targets': ('integration/tests/test_documents_collection_protocol.py',),
        'selector': 'test_documents_collection_protocol_'},
    'documents-parser-adoption': {'mode': 'application/contracts',
        'targets': ('contracts/tests/test_document_parser_adoption.py',),
        'selector': 'test_documents_parser_adoption_'},
    'documents-contracts': {'mode': 'application/contracts',
        'targets': ('contracts/tests/test_documents_contract.py',),
        'selector': 'test_documents_contracts_'},
    'documents-citation-contracts': {'mode': 'application/contracts',
        'targets': ('contracts/tests/test_documents_contract.py',),
        'selector': 'test_documents_citation_contracts_'},
}
GROUPS.update({group: route['targets'] for group, route in DOCUMENTS_ROUTES.items()})
# The collection protocol group must leave actual measurement artifacts, not only test counts.
DOCUMENTS_MEASURED_GROUP = 'documents-collection-protocol'


def documents_interpreter(group):
    if group not in DOCUMENTS_ROUTES:
        raise ValueError('Unknown Documents group')
    return (fixture.APPROVED_PYTHON if DOCUMENTS_ROUTES[group]['mode'] == 'native'
            else fixture.APPROVED_CONTRACT_PYTHON)


def documents_targets(group, *, repo=REPO):
    """Resolve exact test nodes without importing tests, pytest or native code."""
    if group not in DOCUMENTS_ROUTES:
        raise ValueError('Unknown Documents group')
    route = DOCUMENTS_ROUTES[group]
    python_prefix = 'test_' + group.replace('-', '_') + '_'
    selected = []
    for target in route['targets']:
        path = fixture.no_symlinks(repo / target)
        if not path.is_file():
            raise ValueError('Required Documents target missing: ' + target)
        if target.endswith('.ts'):
            # Playwright applies the complete boundary-aware regexp at runtime.
            if ('@' + group) not in path.read_text():
                raise ValueError('Required Documents browser selector missing: ' + target)
            selected.append(target)
            continue
        tree = ast.parse(path.read_text())
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name.startswith(python_prefix)]
        if not nodes:
            raise ValueError('Required Documents test selector missing: ' + target)
        marks = [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'pytestmark' for t in n.targets)]
        for node in nodes:
            if any(isinstance(n, ast.Attribute) and n.attr in {'skip', 'skipif', 'xfail'}
                   for item in [node, *marks] for n in ast.walk(item)):
                raise ValueError('Required Documents test skipped: ' + target)
            selected.append(target + '::' + node.name)
    if not selected:
        raise ValueError('Documents group has zero targets')
    return tuple(selected)


def documents_capabilities(group):
    route = DOCUMENTS_ROUTES[group]
    paths = []
    if route['mode'] == 'native':
        paths.append(('deployment/tests/documents_native_fixture.py', 'start'))
    if route['mode'] == 'browser':
        # A browser route needs an isolated API startup capability before it can run.
        paths.append(('deployment/tests/documents_ui_fixture.py', 'start_isolated_api'))
    for relative, name in paths:
        path = fixture.no_symlinks(REPO / relative)
        if not path.is_file():
            raise ValueError('Required Documents capability missing: ' + relative)
        tree = ast.parse(path.read_text())
        if not any(isinstance(n, ast.FunctionDef) and n.name == name for n in tree.body):
            raise ValueError('Required Documents capability missing: ' + relative + '::' + name)


def documents_results_passed(status, results, targets):
    return (status == 0 and bool(targets) and set(results) == set(targets)
            and all(value['passed'] > 0 and not value['failed'] and not value['skipped']
                    for value in results.values()))


def documents_report_passed(record):
    return (record.get('passed') is True and type(record.get('tests')) is int
            and record['tests'] > 0 and record.get('skipped') == 0
            and record.get('failures', 0) == 0 and record.get('errors', 0) == 0)


def documents_collection_evidence(scope):
    """The collection protocol requires actual measurement artifacts as well as passing test counts."""
    labels = ['logical-commit', 'historical-replay', 'capacity-0', 'capacity-10000',
              'hazard-clear', 'hazard-physical-delete']
    labels += ['exception-' + boundary for boundary in ('removed', 'metadata', 'witness')]
    labels += ['logical-kill-' + boundary for boundary in ('removed', 'metadata', 'witness', 'committed')]
    labels += ['integrity-' + fault for fault in ('foreign-study', 'foreign-store', 'reserved-id',
        'missing-group', 'unknown-lifecycle', 'missing-lifecycle', 'bad-revision', 'missing-witness',
        'bad-marker', 'nonempty-tombstone', 'duplicate-witness', 'conflicting-witness', 'wrong-witness-store')]
    for label in labels:
        path = fixture.scoped_path(scope, 'evidence/atomicity-' + label + '.json')
        if not path.is_file():
            raise ValueError('Missing logical protocol evidence: ' + label)
        record = json.loads(path.read_text())
        before = record.get('before')
        if not isinstance(before, dict) or not before:
            raise ValueError('Incomplete logical protocol evidence: ' + label)
        if label.startswith('logical-kill-'):
            killed = record.get('killed', {})
            if (killed.get('returncode') != -9 or killed.get('signal') != 'SIGKILL' or
                    killed.get('reply_received') is not False or
                    type(killed.get('pid')) is not int or killed['pid'] <= 0):
                raise ValueError('Missing actual logical protocol SIGKILL evidence')
        if label.startswith('capacity-'):
            count = int(label.split('-')[1])
            members = before.get('state', {}).get('members', [])
            after = record.get('after', {})
            if (len(members) != count or len(set(members)) != count or
                    after.get('state', {}).get('members') != [] or
                    len(after.get('sources', [])) != count or
                    before.get('sources') != after.get('sources') or
                    len(after.get('receipts', [])) != 1):
                raise ValueError('Incomplete actual logical protocol capacity evidence')


def documents_child(group):
    # This must precede target collection and fixture/application/native imports.
    scope = fixture.documents_scope(documents_interpreter(group))
    targets = documents_targets(group)
    documents_capabilities(group)
    if DOCUMENTS_ROUTES[group]['mode'] == 'browser':
        import documents_ui_fixture
        return documents_ui_fixture.run(group=group)
    global PROJECTION_SCOPE, NATIVE_BACKEND
    sys.modules['checks'] = sys.modules[__name__]
    PROJECTION_SCOPE = scope
    if DOCUMENTS_ROUTES[group]['mode'] == 'native':
        import documents_native_fixture
        scope, NATIVE_BACKEND = documents_native_fixture.start(group=group)
        PROJECTION_SCOPE = scope
    for relative in ('application/src', 'application/tests', 'integration/src',
                     'integration/tests', 'contracts/tests'):
        sys.path.insert(0, str(REPO / relative))
    # Pristine environment was validated above, before native setup/collection.
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    import pytest
    results = {}

    class Results:
        def pytest_runtest_logreport(self, report):
            filename = report.nodeid.split('::')[0]
            count = results.setdefault(filename, dict(passed=0, failed=0, skipped=0))
            if report.skipped or getattr(report, 'wasxfail', False):
                count['skipped'] += 1
            elif report.failed:
                count['failed'] += 1
            elif report.when == 'call' and report.passed:
                count['passed'] += 1
    status = pytest.main(['-q', '-p', 'no:cacheprovider', '--noconftest',
                          '--rootdir=' + str(REPO), '--basetemp=' + str(fixture.scoped_path(scope, 'tmp/pytest')),
                          *targets], plugins=[Results()])
    native = {name.split('.')[0] for name in sys.modules} & {'aiida', 'openmdao', 'openturns'}
    allowed = {'aiida'} if DOCUMENTS_ROUTES[group]['mode'] == 'native' else set()
    passed = documents_results_passed(status, results, {t.split('::')[0] for t in targets}) and not (native - allowed)
    fixture.scoped_path(scope, 'evidence/tests.json').write_text(json.dumps(dict(
        passed=passed, files=results, tests=sum(c['passed'] + c['failed'] + c['skipped'] for c in results.values()),
        failures=sum(c['failed'] for c in results.values()), skipped=sum(c['skipped'] for c in results.values()),
        native_imports=sorted(native)), indent=2) + '\n')
    return 0 if passed else 1


def run_documents(group):
    if sys.executable != fixture.APPROVED_PYTHON:
        raise ValueError('Reviewed Documents parent interpreter required')
    targets = documents_targets(group)
    documents_capabilities(group)  # Missing capabilities fail before allocation.
    require_environment(group)
    scope = fixture.allocate_scope(replace(fixture.new_scope(), interpreter=documents_interpreter(group)))
    command = [scope.interpreter, '-B', str(REPO / 'deployment/checks.py'), '--' + group + '-child']
    timeout = 60 if DOCUMENTS_ROUTES[group]['mode'] == 'application/contracts' else 300
    started = time.monotonic()
    # A bounded child owns its process group, including future fixture servers.
    import signal
    with subprocess.Popen(command, cwd=REPO, env=fixture.clean_environment(scope),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          start_new_session=True) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
            status = child.returncode
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
            status = 124
    scope = fixture.Scope(**{**json.loads((scope.root / 'scope.json').read_text()), 'root': scope.root})
    fixture.validate_scope(scope)
    evidence = fixture.scoped_path(scope, 'evidence')
    if status == 0 and group == DOCUMENTS_MEASURED_GROUP:
        try:
            documents_collection_evidence(scope)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            status = 1
            stderr += '\nLogical evidence refusal: ' + str(error) + '\n'
    (evidence / 'stdout.log').write_text(stdout)
    (evidence / 'stderr.log').write_text(stderr)
    # A child exit without measured results is never accepted.
    result_path = evidence / 'tests.json'
    if status == 0:
        if not result_path.is_file() or not documents_report_passed(json.loads(result_path.read_text())):
            status = 1
    source_paths = {*DOCUMENTS_ROUTES[group]['targets'], 'deployment/checks.py',
                    'deployment/tests/scoped_fixture.py',
                    'deployment/tests/documents_native_fixture.py',
                    'deployment/tests/documents_ui_fixture.py'}
    source_index = []
    for relative in sorted(source_paths):
        raw = (REPO / relative).read_bytes()
        snapshot = fixture.scoped_path(scope, 'evidence/source/' + relative)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        source_index.append(dict(path=str(REPO / relative), snapshot_path=str(snapshot),
                                 size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    record = dict(group=group, command=command, exit=status,
                  duration_seconds=time.monotonic() - started, timeout_seconds=timeout,
                  scope=scope.record(), targets=targets, source_index=source_index,
                  evidence=str(evidence))
    (evidence / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(stdout, end='')
    print(stderr, end='', file=sys.stderr)
    print(json.dumps(dict(group=group, exit=status, evidence=str(evidence))))
    return status


UNITS_MIXED_REPAIR_TARGETS = (
    'deployment/tests/test_units_native.py::test_native_mixed_legacy_selected_repair',
    'deployment/tests/test_units_native.py::test_http_fixture_response_disconnect_boundary',
)


def validate_units_mixed_repair(group, enabled):
    if enabled and group != 'units-native':
        raise ValueError('Mixed repair requires the existing units-native group')


def targets_for(group, *, repo=REPO, units_mixed_repair=False):
    validate_units_mixed_repair(group, units_mixed_repair)
    if group not in GROUPS:
        raise ValueError('Unknown check group')
    targets = UNITS_MIXED_REPAIR_TARGETS if units_mixed_repair else GROUPS[group]
    for target in targets:
        path = fixture.no_symlinks(repo / target.split('::')[0])
        if target.endswith('/'):
            directory_target(group, target, path)
            continue
        if not path.is_file():
            raise ValueError('Required target missing: ' + target)
        if units_mixed_repair or (group in FINDINGS_NATIVE_GROUPS and '::' in target):
            name = target.split('::')[1]
            tree = ast.parse(path.read_text())
            node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
            if node is None:
                raise ValueError('Required test missing: ' + target)
            # Fixed qualification nodes may not be skipped before native setup.
            marks = [node, *node.decorator_list, *(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'pytestmark' for t in n.targets))]
            if any(isinstance(n, ast.Attribute) and n.attr in {'skip', 'skipif'}
                   for mark in marks for n in ast.walk(mark)):
                raise ValueError('Required test skipped: ' + target)
    return targets


def successful(result):
    return result.testsRun > 0 and result.wasSuccessful() and not result.skipped


# Stdlib unittest guard modules, run in a scoped child under the reviewed native interpreter.
UNITTEST_GUARD_MODULES = {
    'guard': 'test_repository_guard',
    'naming': 'test_naming_guard',
    'hygiene': 'test_hygiene_guard',
    'style-ratchet': 'test_style_ratchet',
}


def guard_child(group='guard'):
    scope = fixture.scope_from_environment()  # Before test collection/import.
    expected = documents_interpreter(group) if group in DOCUMENTS_ROUTES else fixture.APPROVED_PYTHON
    if sys.executable != scope.interpreter or scope.interpreter != expected:
        raise ValueError('Child must use the reviewed interpreter')
    targets_for(group)
    module = UNITTEST_GUARD_MODULES.get(group, UNITTEST_GUARD_MODULES['guard'])
    suite = unittest.defaultTestLoader.discover(str(REPO / 'deployment/tests'), pattern=module + '.py')
    if group == 'units-guards':
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_units_fixture_guards.UnitsGuardTests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    fixture.scoped_path(scope, 'evidence/tests.json').write_text(json.dumps({
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'passed': successful(result),
    }, indent=2) + '\n')
    return 0 if successful(result) else 1


PROJECTION_SCOPE = None
NATIVE_BACKEND = None

# Application-only groups run under the reviewed application interpreter.
GROUP_INTERPRETERS = {'api-c': fixture.APPROVED_CONTRACT_PYTHON, 'runtime-observation': fixture.APPROVED_CONTRACT_PYTHON, 'api-a': fixture.APPROVED_CONTRACT_PYTHON, 'modified': fixture.APPROVED_CONTRACT_PYTHON, 'ui-a': fixture.APPROVED_CONTRACT_PYTHON, 'ui-a-retained': fixture.APPROVED_CONTRACT_PYTHON, 'ui-c': fixture.APPROVED_CONTRACT_PYTHON, 'ui-b': fixture.APPROVED_CONTRACT_PYTHON}

# Closed routing: a group cannot request arbitrary modules or native privileges.
AE_BROWSER_GROUPS = {
    'ae-ui-evidence': '@ae-evidence', 'ae-ui-model': '@ae-model',
    'ae-ui-configuration': '@ae-configuration',
}
AE_NATIVE_GROUPS = frozenset({'ae-execution', 'ae-history', 'ae-export', 'ae-native'})
AE_APP_GROUPS = frozenset({'ae-generated', 'ae-public', 'ae-evidence', 'ae-authoring', 'ae-configuration'})
AE_PYTEST_GROUPS = AE_NATIVE_GROUPS | AE_APP_GROUPS | {'ae-contracts', 'ae-model'}
AE_SELECTIONS = {'ae-generated': ['-k', 'test_generated_'], 'ae-public': ['-k', 'test_public_']}
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON
                          for group in AE_APP_GROUPS | set(AE_BROWSER_GROUPS)})


# Registration is not a test pass: targets_for refuses missing files before scope allocation.
APPROACH_BROWSER_GROUPS = {
    'approach-ui-controller': '@approach-controller',
    'approach-ui-reading': '@approach-reading',
    'approach-ui-method': '@approach-method',
    'approach-ui-assumptions': '@approach-assumptions',
    'approach-ui-configuration': '@approach-configuration',
    'approach-ui-history': '@approach-history',
}
APPROACH_NATIVE_GROUPS = frozenset({'approach-bundle', 'approach-worker', 'approach-history', 'approach-export', 'approach-native', 'investigation-native', 'investigation-worker', 'fuel-native-provenance'})
APPROACH_APP_GROUPS = frozenset({'findings-history', 'approach-closure', 'approach-service', 'approach-api', 'approach-configuration', 'fuel-platform', 'investigation-evidence', 'investigation-diagnostics'})
APPROACH_PYTEST_GROUPS = APPROACH_NATIVE_GROUPS | APPROACH_APP_GROUPS | {'approach-contracts'}
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON
                          for group in APPROACH_APP_GROUPS | set(APPROACH_BROWSER_GROUPS)})


# Units routing is deliberately closed. Targets and selectors must exist and collect tests.
UNITS_BROWSER_GROUPS = {
    'units-ui-authoring': '@units-authoring',
    'units-ui-configuration': '@units-configuration',
    'units-ui-reading': '@units-reading',
    'units-ui-history': '@units-history',
}
UNITS_NATIVE_GROUPS = frozenset({'units-history', 'units-launcher', 'units-worker',
                                 'units-attestation', 'units-native'})
UNITS_APP_GROUPS = frozenset({'units-api', 'units-public-types', 'units-resolution',
                            'units-configuration', 'units-bundle'})
UNITS_PYTEST_GROUPS = UNITS_NATIVE_GROUPS | UNITS_APP_GROUPS | {
    'units-guards', 'units-contracts', 'units-staging', 'units-model',
}
UNITS_SELECTIONS = {
    'units-staging': ['-k', 'test_units_staging_'],
    'units-public-types': ['-k', 'test_generated_'],
    'units-attestation': ['-k', 'test_units_attestation_'],
}
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON
                          for group in UNITS_APP_GROUPS | set(UNITS_BROWSER_GROUPS)})

# Release tooling runs under the reviewed native interpreter. Closed: one fixed target,
# no arbitrary module/target argument, no native import in-process.
RELEASE_PYTEST_GROUPS = frozenset({'deployment-hardening'})

# Closed isolated browser groups: fixed specs, in-browser API double, reviewed application
# interpreter, scope-bound build and evidence. No pytest collection and no native import.
FOUNDRY_BROWSER_GROUPS = frozenset({'foundry-nav', 'ported-isolated', 'ui-navigation', 'ui-reading', 'ui-fidelity'})
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON for group in FOUNDRY_BROWSER_GROUPS})

# Data-only application tests under the reviewed application interpreter (no checkout binding,
# no native import, no runtime access).
LOCALITY_PYTEST_GROUPS = frozenset({'locality-contracts'})
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON for group in LOCALITY_PYTEST_GROUPS})
# The local edition entry point and its pinned toolchain: standard-library tests of the shim,
# the tool locks and the audit record, under the reviewed application interpreter.
LOCAL_EDITION_PYTEST_GROUPS = frozenset({'local-edition'})
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON for group in LOCAL_EDITION_PYTEST_GROUPS})
# The public API, its discovery and the application store's access control run under the reviewed
# application interpreter; none imports native code in-process.
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON
                           for group in ('public-api', 'public-discovery', 'access-control')})

# Pytest groups that create one fresh native (AiiDA) test backend in their scope.
NATIVE_PYTEST_GROUPS = frozenset({'native-execution', 'native-a', 'native-b', 'combined-security', 'combined-native', 'native-bindings',
                                  'archive-native', 'archive-accounting', 'archive-diagnostics', 'archive-service',
                                  'archive-bridge', 'bridge-history'})
# Pytest groups that import application, integration and contract test roots without a native backend.
APPLICATION_PYTEST_GROUPS = frozenset({'public-discovery', 'access-control', 'projection', 'bindings', 'runtime-observation', 'api-a', 'api-c', 'modified'})
# Pytest groups that set up an owned modeling deployment in their scope (no native backend).
MODELING_PYTEST_GROUPS = frozenset({'modeling-isolation', 'public-api', 'modeling-contract'})
NATIVE_BACKEND_GROUPS = AE_NATIVE_GROUPS | APPROACH_NATIVE_GROUPS | UNITS_NATIVE_GROUPS | NATIVE_PYTEST_GROUPS
PROJECT_PYTEST_GROUPS = (AE_PYTEST_GROUPS | APPROACH_PYTEST_GROUPS | UNITS_PYTEST_GROUPS | RELEASE_PYTEST_GROUPS
                         | LOCALITY_PYTEST_GROUPS | LOCAL_EDITION_PYTEST_GROUPS | NATIVE_PYTEST_GROUPS | APPLICATION_PYTEST_GROUPS
                         | MODELING_PYTEST_GROUPS)
SERVED_BROWSER_GROUPS = frozenset({'ui-a', 'ui-a-retained', 'ui-b', 'ui-c'})
GUARD_GROUPS = frozenset(UNITTEST_GUARD_MODULES)
# Every group that run_group launches as one scoped child with a --<group>-child entry flag.
CHILD_GROUPS = (PROJECT_PYTEST_GROUPS | FOUNDRY_BROWSER_GROUPS | SERVED_BROWSER_GROUPS | GUARD_GROUPS
                | set(AE_BROWSER_GROUPS) | set(APPROACH_BROWSER_GROUPS) | set(UNITS_BROWSER_GROUPS) | {'contracts'})

# Agent groups: a closed set of application pytest groups under the reviewed application
# interpreter, no environment needs. Each takes exactly one directory target, which must exist
# and hold at least one test module and is passed whole to pytest, so a later test module joins
# its group without a runner edit. No other group accepts a directory target.
AGENT_PYTEST_GROUPS = frozenset({'agent-tools'})
AGENT_DIRECTORY_TARGETS = {'agent-tools': 'application/tests/agent/'}
GROUPS.update({group: (target,) for group, target in AGENT_DIRECTORY_TARGETS.items()})
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON for group in AGENT_PYTEST_GROUPS})
PROJECT_PYTEST_GROUPS = PROJECT_PYTEST_GROUPS | AGENT_PYTEST_GROUPS
CHILD_GROUPS = CHILD_GROUPS | AGENT_PYTEST_GROUPS

# The installation configuration and the portability guard: data-only tests under the reviewed
# application interpreter, no environment needs, no native import.
INSTALLATION_PYTEST_GROUPS = frozenset({'installation-config', 'portability'})
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON for group in INSTALLATION_PYTEST_GROUPS})
PROJECT_PYTEST_GROUPS = PROJECT_PYTEST_GROUPS | INSTALLATION_PYTEST_GROUPS
CHILD_GROUPS = CHILD_GROUPS | INSTALLATION_PYTEST_GROUPS


def directory_target(group, target, path):
    """Validate an agent group's directory target: closed set, existing, with test modules."""
    if group not in AGENT_PYTEST_GROUPS or AGENT_DIRECTORY_TARGETS.get(group) != target:
        raise ValueError('Directory target not allowed: ' + target)
    if not path.is_dir() or not any(path.glob('test_*.py')):
        raise ValueError('Required target missing: ' + target)


def target_sources(targets):
    """Source files of ``targets`` for the evidence record: a directory target contributes
    every Python file below it."""
    files = []
    for target in targets:
        relative = target.split('::')[0]
        if relative.endswith('/'):
            files.extend(str(p.relative_to(REPO)) for p in sorted((REPO / relative).rglob('*.py')))
        else:
            files.append(relative)
    return files


# Group registry: class and environment needs. A group whose need is absent fails with
# "environment absent: <need>" before any scope is allocated.
CLASSES = ('must-pass', 'opt-in')
NEEDS = ('docker', 'browser', 'fixtures', 'installation')
# Served-installation browser groups: the specs talk to an installation named explicitly.
SERVED_INSTALLATION_GROUPS = frozenset({'ui-served'})
UI_BASE_URL = 'HYPRN_MVP_UI_BASE_URL'
UI_PASSWORD_FILE = 'HYPRN_MVP_UI_PASSWORD_FILE'
# Groups that are run only on request: they need a served installation or reference images
# that a development host does not provide by default.
OPT_IN_GROUPS = SERVED_INSTALLATION_GROUPS | {'ui-fidelity'}
# Native groups need the container engine for the attested worker or the modeling image.
DOCKER_GROUPS = (NATIVE_BACKEND_GROUPS | MODELING_PYTEST_GROUPS | {'units-model', 'ae-model', 'public-discovery', 'findings-native-preflight',
                 'findings-native', 'findings-native-read'}
                 | {g for g, route in DOCUMENTS_ROUTES.items() if route['mode'] == 'native'})
# Browser groups need Node.js and the installed UI toolchain (ui/node_modules with Playwright).
BROWSER_GROUPS = (FOUNDRY_BROWSER_GROUPS | SERVED_BROWSER_GROUPS | SERVED_INSTALLATION_GROUPS | set(AE_BROWSER_GROUPS)
                  | set(APPROACH_BROWSER_GROUPS) | set(UNITS_BROWSER_GROUPS)
                  | {'combined-static', 'findings-native', 'findings-native-read'}
                  | {g for g, route in DOCUMENTS_ROUTES.items() if route['mode'] == 'browser'})
# Durable-fixture groups read manifest-verified fixtures below the development data root.
FIXTURE_GROUPS = frozenset({'findings-native-preflight', 'findings-native', 'findings-native-read',
                            'approach-ui-history'})
# Browser specs a group's fixture runs without listing them as targets.
FIXTURE_BROWSER_SPECS = {'units-native': ('ui/tests/unit-native-journey.spec.ts',)}


def browser_specs():
    """Every registered browser spec and the groups that run it (targets and fixture specs)."""
    specs = {}
    for group, targets in (*GROUPS.items(), *FIXTURE_BROWSER_SPECS.items()):
        for target in targets:
            if target.startswith('ui/tests/') and target.endswith('.spec.ts'):
                specs.setdefault(target, set()).add(group)
    return specs


# Python test modules that no group runs, each with the one-line reason it cannot run in any
# scope. Closed: a module listed here may not also be a group target, and every other tracked
# */tests/test_*.py module must be a target of a must-pass group.
RETIRED_TEST_MODULES = {
    'integration/tests/test_configuration.py': 'Exercises the native-port validator, which imports OpenMDAO in-process; every group refuses in-process OpenMDAO.',
}


def python_test_modules():
    """Every Python test module named by a group target (whole file or file::test node) and the
    groups that run it."""
    modules = {}
    for group, targets in GROUPS.items():
        for target in targets:
            path = target.split('::')[0]
            if '/tests/' in path and path.rsplit('/', 1)[-1].startswith('test_') and path.endswith('.py'):
                modules.setdefault(path, set()).add(group)
    return modules


def group_class(group):
    if group not in GROUPS:
        raise ValueError('Unknown check group')
    return 'opt-in' if group in OPT_IN_GROUPS else 'must-pass'


def group_needs(group):
    if group not in GROUPS:
        raise ValueError('Unknown check group')
    return tuple(need for need, members in (('docker', DOCKER_GROUPS), ('browser', BROWSER_GROUPS),
                                            ('fixtures', FIXTURE_GROUPS),
                                            ('installation', SERVED_INSTALLATION_GROUPS)) if group in members)


def need_present(need):
    """Probe one environment need without touching any store or container."""
    if need == 'docker':
        docker = shutil.which('docker', path=fixture.PATH)
        if docker is None:
            return False
        try:
            result = subprocess.run([docker, 'info', '--format', '{{.ServerVersion}}'],
                                    capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 and bool(result.stdout.strip())
    if need == 'browser':
        return (shutil.which('node', path=fixture.PATH) is not None
                and (REPO / 'ui/node_modules/playwright/cli.js').is_file())
    if need == 'fixtures':
        root = fixture.local_paths.fixtures_root(required=False)
        return root is not None and root.is_dir()
    if need == 'installation':
        return bool(os.environ.get(UI_BASE_URL)) and bool(os.environ.get(UI_PASSWORD_FILE))
    raise ValueError('Unknown environment need: ' + need)


def require_environment(group):
    for need in group_needs(group):
        if not need_present(need):
            raise ValueError('environment absent: ' + need)


def must_pass_groups():
    """Must-pass groups in qualification order: static, then fixtures, docker and browser needs."""
    rank = {(): 0, ('fixtures',): 1, ('docker',): 2}
    groups = [g for g in GROUPS if group_class(g) == 'must-pass']
    return sorted(groups, key=lambda g: (rank.get(group_needs(g), 3 + len(group_needs(g))), list(GROUPS).index(g)))


def list_groups(selected_class=None):
    lines = []
    for group in GROUPS:
        if selected_class is None or group_class(group) == selected_class:
            lines.append('\t'.join((group, group_class(group), ','.join(group_needs(group)) or '-')))
    if selected_class is None:
        needs = sorted({n for g in must_pass_groups() for n in group_needs(g)}, key=NEEDS.index)
        lines.append('\t'.join(('qualification', 'aggregate', ','.join(needs))))
    for line in lines:
        print(line)
    return 0


def served_installation():
    """The installation named for the served groups, validated before any scope or browser.

    Served specs write studies: the URL must be an explicit loopback origin that is neither a
    live installation port nor the development installation's port (HYPRN_MVP_PORT), and the
    owner password file must lie outside the development stores and every live root.
    """
    url = os.environ.get(UI_BASE_URL, '')
    fixture.validate_url(url or None)
    if not url:
        raise ValueError('environment absent: installation')
    port = fixture.local_paths.port(required=False)
    if port is not None and url.rstrip('/').endswith(':' + str(port)):
        raise ValueError(UI_BASE_URL + ' names the development installation; serve a test installation instead')
    raw = os.environ.get(UI_PASSWORD_FILE, '')
    password = Path(raw)
    if not raw or not password.is_absolute() or password.is_symlink() or not password.is_file():
        raise ValueError(UI_PASSWORD_FILE + ' must name an existing owner password file by absolute path')
    resolved = password.resolve()
    for root in (*fixture.local_paths.store_roots(required=False), *fixture.local_paths.live_roots()):
        if resolved.is_relative_to(Path(root).resolve()):
            raise ValueError(UI_PASSWORD_FILE + ' is inside a development store or live root; refused')
    return url.rstrip('/'), str(password)


def served_child_environment(scope, url, password):
    """The scoped environment plus the two served-installation variables, nothing else."""
    return {**fixture.clean_environment(scope), UI_BASE_URL: url, UI_PASSWORD_FILE: password}


def run_served(group, targets):
    """Run a served group's specs against the named installation; evidence stays in the scope."""
    require_environment(group)
    url, password = served_installation()
    specs = [t for t in targets if t.endswith('.spec.ts')]
    scope = fixture.allocate_scope(fixture.new_scope())
    evidence = fixture.scoped_path(scope, 'evidence')
    command = ['node', str(REPO / 'ui/node_modules/playwright/cli.js'), 'test', '--config', 'playwright.config.ts',
               '--forbid-only', '--retries=0', '--reporter=json', *(spec.removeprefix('ui/') for spec in specs)]
    started = time.monotonic()
    tested = subprocess.run(command, cwd=REPO / 'ui', env=served_child_environment(scope, url, password),
                            capture_output=True, text=True, timeout=3600)
    (evidence / 'browser-report.json').write_text(tested.stdout)
    (evidence / 'browser-stderr.log').write_text(tested.stderr)
    try:
        stats = json.loads(tested.stdout[tested.stdout.index('{'):])['stats']
    except (ValueError, KeyError):
        stats = {}
    passed = (tested.returncode == 0 and stats.get('expected', 0) > 0
              and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky')))
    record = dict(group=group, passed=passed, tests=stats.get('expected', 0) + stats.get('unexpected', 0),
                  failures=stats.get('unexpected', 0), skipped=stats.get('skipped', 0), flaky=stats.get('flaky', 0),
                  specs=specs, command=command, duration_seconds=time.monotonic() - started)
    (evidence / 'tests.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(evidence=str(evidence), exit=0 if passed else 1, **record)))
    return 0 if passed else 1


# Phase gate pool. Every group already runs in its own scope: scratch folder, AiiDA profile,
# container, network and image names derived from the scope's identifier, ports chosen by the
# operating system. Groups may therefore overlap, with two exceptions that every change to a
# group must keep current:
# - a serialization lane holds the groups that depend on another group's outcome or share a
#   fixed resource that no scope owns. Members of one lane never overlap and start in
#   qualification order, each only after every earlier member has finished;
# - an exclusive group runs alone: it starts only after every earlier group has finished, and
#   no later group starts before it finishes. A group is exclusive when its runner bounds its
#   wall-clock time close to its duration alone, so contention could turn a pass into a timeout.
QUALIFICATION_JOBS = 3
QUALIFICATION_MAX_JOBS = 8
SERIAL_LANES = {
    # The fixed scratch root (HYPRN_MVP_SCRATCH_ROOT) and the durable native fixture's one
    # working copy there. units-native is the producer run a fixture is captured from; the
    # findings guards materialize a synthetic working root below the same root; preflight
    # materializes the working copy, the continuation runs once per working copy and the read
    # follows it, each proving the copy quiescent by scanning every process and container;
    # approach-ui-history reads the fixture's application store.
    'fixed-scratch-root': frozenset({'units-native', 'findings-native-guards', 'findings-native-preflight',
                                     'findings-native', 'findings-native-read', 'approach-ui-history'}),
}
# run_documents bounds the measured collection protocol at 300 s; alone it takes about 265 s.
EXCLUSIVE_GROUPS = frozenset({DOCUMENTS_MEASURED_GROUP})


def lane_of(group, lanes=SERIAL_LANES):
    return next((name for name, members in lanes.items() if group in members), None)


def valid_jobs(jobs):
    if type(jobs) is not int or not 1 <= jobs <= QUALIFICATION_MAX_JOBS:
        raise ValueError('--jobs must be an integer from 1 to ' + str(QUALIFICATION_MAX_JOBS))
    return jobs


def pool_qualification(groups, run, report, *, jobs, lanes=SERIAL_LANES, exclusive=EXCLUSIVE_GROUPS):
    """Run ``groups`` (in qualification order) with at most ``jobs`` at once.

    ``run(group)`` runs on a worker thread and returns the group's result (a dict with ``exit``);
    an exception becomes exit 2 with the refusal as output. ``report(result)`` runs on the calling
    thread exactly once per started group, in qualification order: a result is held until every
    earlier started group has been reported. After the first failure no group starts; running
    groups finish and are reported. Returns the results in qualification order and the groups
    that never started.
    """
    valid_jobs(jobs)
    if len(set(groups)) != len(groups):
        raise ValueError('Qualification groups must be distinct')
    order = {group: index for index, group in enumerate(groups)}
    pending, running, done, reported = list(groups), {}, {}, set()
    failed = False

    def guarded(group):
        try:
            return run(group)
        except Exception as error:  # A launch failure fails the group; it never passes.
            return dict(group=group, exit=2, duration_seconds=0.0, output='Check refused: ' + str(error) + '\n')

    def startable(group, active):
        if active & exclusive:
            return False
        if group in exclusive:
            return not active
        lane = lane_of(group, lanes)
        if lane is None:
            return True
        members = [g for g in groups if lane_of(g, lanes) == lane]
        return (not any(g in active for g in members)
                and all(g in done for g in members if order[g] < order[group]))

    def flush():
        # Report the completed prefix; a group that will never start does not hold later results.
        for group in groups:
            if group in reported:
                continue
            if group not in done:
                if group in running.values() or (group in pending and not failed):
                    return
                continue
            report(done[group])
            reported.add(group)

    with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix='qualification') as pool:
        while True:
            if not failed:
                for group in list(pending):
                    if len(running) >= jobs:
                        break
                    if startable(group, set(running.values())):
                        pending.remove(group)
                        running[pool.submit(guarded, group)] = group
                    elif group in exclusive:
                        break  # Nothing after an exclusive group starts before it.
            if not running:
                if pending and not failed:
                    raise RuntimeError('Qualification pool stalled with groups pending')
                break
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in sorted(finished, key=lambda f: order[running[f]]):
                group = running.pop(future)
                done[group] = future.result()
                failed = failed or done[group]['exit'] != 0
            flush()
    flush()
    return [done[g] for g in groups if g in done], [g for g in groups if g not in done]


def qualification_command(group):
    # Documents parents must run under the reviewed native interpreter.
    python = fixture.APPROVED_PYTHON if group in DOCUMENTS_ROUTES else sys.executable
    if python is None:
        raise fixture.local_paths.LocationUnset(fixture.local_paths.unset_message())
    return [python, '-B', str(Path(__file__).resolve()), '--group', group]


def run_qualification(jobs=QUALIFICATION_JOBS):
    """Every must-pass group in its own scoped run, at most ``jobs`` at once (see SERIAL_LANES);
    after a failure no group starts. With one job each group's output streams as it runs; with
    more, each group's output is held and printed whole with its result, in qualification order."""
    valid_jobs(jobs)
    groups = must_pass_groups()
    commands = {group: qualification_command(group) for group in groups}  # Refuse before any start.

    def run(group):
        before = time.monotonic()
        if jobs == 1:
            child, output = subprocess.run(commands[group], cwd=REPO), ''
        else:
            child = subprocess.run(commands[group], cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = (child.stdout or b'').decode('utf-8', errors='replace')
        return dict(group=group, exit=child.returncode, duration_seconds=time.monotonic() - before, output=output)

    def report(result):
        if result['output']:
            sys.stdout.write(result['output'] if result['output'].endswith('\n') else result['output'] + '\n')
        print(json.dumps(dict(qualification=result['group'], exit=result['exit'],
                              duration_seconds=result['duration_seconds'])), flush=True)

    started = time.monotonic()
    results, not_started = pool_qualification(groups, run, report, jobs=jobs)
    records = [{key: value for key, value in result.items() if key != 'output'} for result in results]
    counts = dict(groups=len(groups), passed=sum(r['exit'] == 0 for r in records),
                  failed=sum(r['exit'] != 0 for r in records), not_started=len(not_started))
    passed = counts['passed'] == len(groups)
    print(json.dumps(dict(group='qualification', passed=passed, jobs=jobs, counts=counts, groups=records,
                          not_started=not_started, duration_seconds=time.monotonic() - started)), flush=True)
    return 0 if passed else 1


def foundry_browser_child(group):
    scope = fixture.scope_from_environment()  # Before fixture import, build or writes.
    if group not in FOUNDRY_BROWSER_GROUPS:
        raise ValueError('Unknown foundry browser group')
    if sys.executable != scope.interpreter or scope.interpreter != GROUP_INTERPRETERS[group]:
        raise ValueError('Child must use the reviewed interpreter')
    targets_for(group)
    import foundry_ui_fixture
    return foundry_ui_fixture.run(group=group)


def units_browser_child(group):
    scope = fixture.scope_from_environment()  # Before fixture import or writes.
    if group not in UNITS_BROWSER_GROUPS:
        raise ValueError('Unknown units browser group')
    if sys.executable != scope.interpreter or scope.interpreter != GROUP_INTERPRETERS[group]:
        raise ValueError('Child must use the reviewed interpreter')
    targets_for(group)
    import units_ui_fixture
    return units_ui_fixture.run(group=group)


def pytest_qualification_passed(status, results, forbidden, *, mixed=False):
    return (not mixed or results.passed == 5) and status == 0 and results.passed > 0 and not results.failed and not results.skipped and not forbidden


def contracts_child(group='contracts', *, units_mixed_repair=False):
    """Collect only data-only contracts after validating the full isolation scope."""
    validate_units_mixed_repair(group, units_mixed_repair)
    scope = fixture.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != GROUP_INTERPRETERS.get(group, fixture.APPROVED_PYTHON):
        raise ValueError('Child must use the reviewed interpreter')
    targets = targets_for(group, units_mixed_repair=units_mixed_repair)
    if group == 'units-guards':
        return guard_child(group)  # stdlib guards require an exact pristine environment.
    if group == 'approach-contracts':
        status = guard_child()
        fixture.scoped_path(scope, 'evidence/tests.json').rename(fixture.scoped_path(scope, 'evidence/guard-tests.json'))
        if status:
            return status
        targets = tuple(p for p in targets if p != 'deployment/tests/test_repository_guard.py')
    if group in PROJECT_PYTEST_GROUPS:
        global PROJECTION_SCOPE
        PROJECTION_SCOPE = scope
        sys.modules['checks'] = sys.modules[__name__]
        sys.path.insert(0, str(REPO / 'application/src'))
        sys.path.insert(0, str(REPO / 'contracts/tests'))
        sys.path.insert(0, str(REPO / 'integration/tests'))
        sys.path.insert(0, str(REPO / 'integration/src'))
        sys.path.insert(0, str(REPO / 'application/tests'))
    if group in NATIVE_BACKEND_GROUPS:
        global NATIVE_BACKEND
        scope, NATIVE_BACKEND = fixture.create_native_fixture(scope)
        PROJECTION_SCOPE = scope
    # Explicit plugins only: installed native pytest entry points must not load.
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    import pytest

    class Results:
        def __init__(self):
            self.passed = self.failed = self.skipped = 0

        def pytest_runtest_logreport(self, report):
            if report.failed:
                self.failed += 1
            elif report.skipped:
                self.skipped += 1
            elif report.when == 'call' and report.passed:
                self.passed += 1

    results = Results()
    # The two native journeys require separate fresh stores. Never append the
    # mixed-only journey to the ordinary compound qualification.
    deselect = ['--deselect=' + UNITS_MIXED_REPAIR_TARGETS[0]] if group == 'units-native' and not units_mixed_repair else []
    status = pytest.main(['-q', '-p', 'no:cacheprovider', '--noconftest',
                          '--basetemp=' + str(fixture.scoped_path(scope, 'tmp/pytest')),
                          *UNITS_SELECTIONS.get(group, AE_SELECTIONS.get(group, [])), *deselect, *targets], plugins=[results])
    native_imports = [name for name in sys.modules if name.split('.')[0] in {'aiida', 'openmdao', 'openturns'}]
    forbidden = [n for n in native_imports if group not in NATIVE_BACKEND_GROUPS or n.split('.')[0] != 'aiida']
    passed = pytest_qualification_passed(status, results, forbidden, mixed=units_mixed_repair)
    fixture.scoped_path(scope, 'evidence/tests.json').write_text(json.dumps({
        'tests': results.passed + results.failed + results.skipped, 'passed': passed,
        'failures': results.failed, 'skipped': results.skipped, 'native_imports': native_imports,
    }, indent=2) + '\n')
    return 0 if passed else 1


def run_group(group, *, units_mixed_repair=False, jobs=QUALIFICATION_JOBS):
    validate_units_mixed_repair(group, units_mixed_repair)
    if group == 'qualification':
        return run_qualification(jobs)
    if group in DOCUMENTS_ROUTES:
        return run_documents(group)
    targets = targets_for(group, units_mixed_repair=units_mixed_repair)  # No allocation/import if missing/unknown.
    if group in SERVED_INSTALLATION_GROUPS:
        return run_served(group, targets)
    if group == 'ui-fidelity' and not (REPO / 'design-system/reference').is_dir():
        raise ValueError('reference absent: design-system/reference')
    if group == 'findings-native-guards':
        require_environment(group)
        return run_findings_guards()
    if group in FINDINGS_NATIVE_GROUPS:
        require_environment(group)
        import findings_native_fixture
        return findings_native_fixture.run_retained(group)

    if group == 'combined-static':
        require_environment(group)
        scope = fixture.allocate_scope(fixture.new_scope())
        env = fixture.clean_environment(scope)
        commands = [
            [scope.interpreter, '-B', 'ui/check_design_system.py'],
            [scope.interpreter, '-B', 'ui/design_tokens.py', '--check'],
            [scope.interpreter, '-B', 'ui/check_ui_contract.py'],
            ['node', '--test', 'ui/tests/criterion-record.test.cjs'],
            ['node', str(REPO/'ui/node_modules/typescript/bin/tsc'), '--noEmit', '-p', 'ui/tsconfig.json'],
            ['node', str(REPO/'ui/node_modules/vite/bin/vite.js'), 'build', str(REPO/'ui'), '--config', str(REPO/'ui/vite.config.ts'), '--configLoader', 'runner', '--outDir', str(scope.root/'artifacts/ui')],
        ]
        started = time.monotonic()
        checks = []
        for index, command in enumerate(commands):
            before = time.monotonic()
            result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            (scope.root/'evidence'/f'check-{index}.log').write_text(result.stdout+result.stderr)
            checks.append(dict(command=command, exit=result.returncode, duration_seconds=time.monotonic()-before))
            if result.returncode:
                break
        passed = len(checks) == len(commands) and all(c['exit'] == 0 for c in checks)
        record = dict(group=group, passed=passed, checks=checks, duration_seconds=time.monotonic()-started)
        (scope.root/'evidence/result.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(dict(evidence=str(scope.root/'evidence'), exit=0 if passed else 1, **record)))
        return 0 if passed else 1

    if group not in CHILD_GROUPS:
        raise ValueError('Group fixture/runner not implemented yet: ' + group)
    require_environment(group)
    scope = fixture.allocate_scope(replace(fixture.new_scope(), interpreter=GROUP_INTERPRETERS.get(group, fixture.APPROVED_PYTHON)))
    env = fixture.clean_environment(scope)
    command = [scope.interpreter, '-B', str(Path(__file__).resolve()), '--' + group + '-child']
    if units_mixed_repair:
        command.append('--units-mixed-repair')
    started = time.monotonic()
    result = subprocess.run(command, env=env, cwd=REPO, capture_output=True, text=True)
    scope = fixture.Scope(**{**json.loads((scope.root / 'scope.json').read_text()), 'root': scope.root})
    evidence = fixture.scoped_path(scope, 'evidence')
    (evidence / 'stdout.log').write_text(result.stdout)
    (evidence / 'stderr.log').write_text(result.stderr)
    scope = fixture.Scope(**{**json.loads((scope.root / 'scope.json').read_text()), 'root': scope.root})
    fixture.validate_scope(scope)
    record = {'group': group, 'command': command, 'cwd': str(REPO),
              'exit': result.returncode, 'duration_seconds': time.monotonic() - started,
              'scope': scope.record(), 'targets': targets,
              'source_sha256': {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest()
                  for p in (*target_sources(targets), 'deployment/checks.py', 'deployment/tests/scoped_fixture.py', 'ui/playwright.isolated.config.ts')}}
    (evidence / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    print(json.dumps({'evidence': str(evidence), 'exit': result.returncode,
                      'duration_seconds': record['duration_seconds']}))
    return result.returncode


def findings_guards_passed(result):
    return result.testsRun == 17 and successful(result) and not any(name.split('.')[0] in {'aiida', 'openmdao', 'openturns'} for name in sys.modules)


def run_findings_guards():
    scope = fixture.allocate_scope(fixture.new_scope())
    command = [scope.interpreter, '-B', str(Path(__file__).resolve()), '--findings-native-guards-child']
    result = subprocess.run(command, cwd=REPO, env=fixture.clean_environment(scope), capture_output=True, text=True)
    (scope.root / 'evidence/stdout.log').write_text(result.stdout)
    (scope.root / 'evidence/stderr.log').write_text(result.stderr)
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    print(json.dumps(dict(evidence=str(scope.root/'evidence'), exit=result.returncode)))
    return result.returncode


def findings_child(group):
    if group != 'findings-native-guards':
        import findings_native_fixture
        return findings_native_fixture.child(group)
    scope = fixture.scope_from_environment()
    if sys.executable != fixture.APPROVED_PYTHON or scope.interpreter != fixture.APPROVED_PYTHON:
        raise ValueError('Child must use the reviewed interpreter')
    targets_for(group)
    suite = unittest.defaultTestLoader.loadTestsFromName('test_findings_native_guards.FindingsNativeGuards')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = findings_guards_passed(result)
    (scope.root/'evidence/tests.json').write_text(json.dumps(dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped), passed=passed), indent=2))
    return 0 if passed else 1


def child(group, *, units_mixed_repair=False):
    """Route one scoped child entry; the routing table is closed."""
    if group in DOCUMENTS_ROUTES:
        return documents_child(group)
    if group in FINDINGS_NATIVE_GROUPS:
        return findings_child(group)
    if group in FOUNDRY_BROWSER_GROUPS:
        return foundry_browser_child(group)
    if group in UNITS_BROWSER_GROUPS:
        return units_browser_child(group)
    if group in APPROACH_BROWSER_GROUPS:
        scope = fixture.scope_from_environment()
        if sys.executable != scope.interpreter or scope.interpreter != GROUP_INTERPRETERS[group]:
            raise ValueError('Child must use the reviewed interpreter')
        targets_for(group)
        import approach_ui_fixture
        return approach_ui_fixture.run(group=group)
    if group in AE_BROWSER_GROUPS:
        fixture.scope_from_environment()  # Guard before fixture import.
        targets_for(group)
        import ae_ui_fixture
        return ae_ui_fixture.run(group=group)
    if group in GUARD_GROUPS:
        return guard_child(group)
    if group in SERVED_BROWSER_GROUPS:
        from ui_fixture import run
        return run(retained=group == 'ui-a-retained', exported=group == 'ui-c', modified=group == 'ui-b')
    if group in CHILD_GROUPS:
        return contracts_child(group, units_mixed_repair=units_mixed_repair)
    raise ValueError('Unknown child group')


def flag(group, suffix='child'):
    return group.replace('-', '_') + '_' + suffix


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument('--group', choices=(*GROUPS, 'qualification'))
    commands.add_argument('--list', action='store_true', help='list every group with its class and environment needs')
    child_groups = sorted(CHILD_GROUPS | set(DOCUMENTS_ROUTES) | FINDINGS_NATIVE_GROUPS)
    for group in child_groups:
        commands.add_argument('--' + group + '-child', action='store_true', help=argparse.SUPPRESS)
    commands.add_argument('--validate-browser', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--class', dest='group_class', choices=CLASSES, help='with --list: only this class')
    parser.add_argument('--units-mixed-repair', action='store_true')
    parser.add_argument('--jobs', type=int, help='with --group qualification: groups run at once (default '
                        + str(QUALIFICATION_JOBS) + '; 1 runs them one after the other)')
    args = parser.parse_args()
    try:
        if args.group_class is not None and not args.list:
            raise ValueError('--class is valid only with --list')
        if args.jobs is not None and args.group != 'qualification':
            raise ValueError('--jobs is valid only with --group qualification')
        if args.units_mixed_repair and not (args.group == 'units-native' or args.units_native_child):
            raise ValueError('Mixed repair requires the existing units-native group or trusted child')
        if args.list:
            return list_groups(args.group_class)
        if args.group is not None and (fixture.APPROVED_PYTHON is None or sys.executable != fixture.APPROVED_PYTHON):
            raise ValueError('group runs need the locked native environment: run ./hyprn-mvp dev check '
                             + args.group)
        for group in child_groups:
            if getattr(args, flag(group)):
                return child(group, units_mixed_repair=args.units_mixed_repair)
        if args.validate_browser:
            scope = fixture.scope_from_environment()
            if scope.url is None:
                raise ValueError('Explicit browser fixture URL required')
            fixture.scoped_path(scope, 'evidence/browser')
            fixture.scoped_path(scope, 'evidence/snapshots')
            print(json.dumps({'root': str(scope.root), 'url': scope.url}))
            return 0
        return run_group(args.group, units_mixed_repair=args.units_mixed_repair,
                         jobs=QUALIFICATION_JOBS if args.jobs is None else args.jobs)
    except (ValueError, OSError, TypeError) as error:
        print('Check refused: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
