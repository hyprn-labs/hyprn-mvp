"""The setup command never repeats an uncertain provider mutation."""

import json
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import email
import zipfile
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'application/src'))
import live_fence  # noqa: E402
import managed_assistant as setup  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'editions/cloud/src'))
from hyprn_mvp_cloud.assistant_startup import reconcile
from hyprn_mvp_cloud.runtime import host_record
from hyprn_mvp_app.assistant.claude import ProviderError
from installed_hosted_app import assistant_plan

setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')


def test_bindings():
    return {'skill': {'id': 'skill_test', 'version': 'skver_test',
                      'sha256': setup.managed_skill.bundle()[1]['sha256']},
            'reviewers': {role: {'id': 'agent_' + str(i), 'version': 1}
                          for i, role in enumerate(setup.REVIEW_ROLES, 1)}}


def offline_plan(tmp_path):
    bindings = tmp_path / 'bindings.json'
    setup.save(bindings, test_bindings())
    plan = tmp_path / 'plan.json'
    result = setup.main(
        [
            'plan',
            '--bindings', str(bindings),
            '--plan',
            str(plan),
            '--deployment',
            'staging',
            '--model',
            'claude-sonnet-5-5',
            '--effort',
            'high',
        ]
    )
    assert result == 0
    value = json.loads(plan.read_text())
    assert value['agent']['model'] == {
        'id': 'claude-sonnet-5-5',
        'effort': {'type': 'high'},
        'speed': 'standard',
    }
    assert value['agent']['tools'][-1]['default_config']['enabled'] is False
    assert value['agent']['skills'][0]['version'] == 'skver_test'
    assert value['environment']['config']['networking'] == {
        'type': 'limited',
        'allowed_hosts': sorted(set(setup.DEFAULT_RESEARCH_HOSTS)),
        'allow_mcp_servers': False,
        'allow_package_managers': False,
    }
    assert len(value['configuration_sha256']) == 64
    print(json.dumps({'system_characters': len(value['agent']['system']),
                      'playbook_characters': len(setup.playbook.render_document()),
                      'bundle_sha256': value['skill_bundle']['sha256'],
                      'scenario_sha256': value['skill_bundle']['inputs'][
                          'docs/agents/scientific-engineering/references/behavioral-scenarios.md']}))


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.plan_path = self.root / 'review.json'
        self.state_path = self.root / 'state.json'
        self.key = self.root / 'key'
        self.key.write_text('synthetic-private-test-key')
        self.key.chmod(0o600)
        self.provider = ProviderDouble()
        self.bindings_path = self.root / 'bindings.json'
        setup.save(self.bindings_path, test_bindings())
        self.transport = httpx.MockTransport(self.provider)

    def command(self, command, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = setup.main(
                [command, '--plan', str(self.plan_path), *args], transport=self.transport
            )
        return code, out.getvalue(), err.getvalue()

    def plan(self, **changes):
        args = dict(deployment='staging', model='claude-sonnet-5-5', effort='high', **changes)
        flattened = [part for key, value in args.items() for part in ('--' + key, value)]
        prepared = setup.bootstrap(**args)
        self.provider.seed(prepared, test_bindings())
        self.assertEqual(self.command('plan', '--bindings', str(self.bindings_path), *flattened)[0], 0)
        return json.loads(self.plan_path.read_text())

    def apply(self, plan, command='apply'):
        return self.command(
            command,
            '--state',
            str(self.state_path),
            '--key-file',
            str(self.key),
            '--approve',
            plan['configuration_sha256'],
        )

    def test_offline_plan_is_release_bound_and_has_no_remote_effects(self):
        with tempfile.TemporaryDirectory() as root:
            offline_plan(Path(root))

    def test_public_command_creates_reads_exact_version_and_repeats_without_mutation(self):
        plan = self.plan()
        code, output, error = self.apply(plan)
        self.assertEqual((code, error), (0, ''))
        bindings = json.loads(output)
        self.assertEqual(bindings['HYPRN_MVP_ASSISTANT_AGENT_VERSION'], '1')
        self.assertEqual(
            bindings['HYPRN_MVP_ASSISTANT_DEFINITIONS_SHA256'], plan['definitions_sha256']
        )
        self.assertEqual(len(self.provider.writes), 2)
        self.assertEqual(self.apply(plan)[0], 0)
        self.assertEqual(len(self.provider.writes), 2)
        self.assertTrue(
            any(url.endswith('/agents/agent_4?version=1') for _, url in self.provider.calls)
        )
        self.assertNotIn(self.key.read_text(), self.state_path.read_text() + output)
        self.assertEqual(self.state_path.stat().st_mode & 0o777, 0o600)

    def test_durable_intent_exists_before_every_mutation(self):
        plan = self.plan()

        def inspect():
            state = json.loads(self.state_path.read_text())
            self.assertIn('intent', [item['status'] for item in state['resources'].values()])

        self.provider.before_write = inspect
        self.assertEqual(self.apply(plan)[0], 0)

    def test_unknown_create_is_reconciled_and_never_reposted(self):
        plan = self.plan()
        self.provider.interrupt_kind = 'agents'
        self.assertEqual(self.apply(plan)[0], 2)
        self.assertEqual(len(self.provider.writes), 2)
        self.assertEqual(self.apply(plan, 'reconcile')[0], 0)
        self.assertEqual(self.apply(plan)[0], 0)
        self.assertEqual(len(self.provider.writes), 2)

    def test_unknown_absent_create_blocks_all_further_writes(self):
        plan = self.plan()
        self.provider.interrupt_kind = 'environments'
        self.provider.commit_before_interrupt = False
        self.assertEqual(self.apply(plan)[0], 2)
        result = self.apply(plan)
        self.assertIn('creation_uncertain_requires_reconciliation', result[2])
        self.assertEqual(len(self.provider.writes), 1)

    def test_partial_setup_read_recovery_does_not_create_missing_agent(self):
        plan = self.plan()
        self.provider.interrupt_kind = 'environments'
        self.assertEqual(self.apply(plan)[0], 2)
        self.assertIn('setup_incomplete', self.apply(plan, 'reconcile')[2])
        self.assertEqual(len(self.provider.writes), 1)
        self.assertEqual(self.apply(plan)[0], 0)
        self.assertEqual(len(self.provider.writes), 2)

    def test_changed_skill_pin_refuses_existing_provider_content(self):
        plan = self.plan()
        self.assertEqual(self.apply(plan)[0], 0)
        self.provider.skill_archive = self.provider.skill_archive + b'trailer'
        # ZIP container metadata can change without changing scientific contents.
        self.assertEqual(self.apply(plan)[0], 0)
        self.provider.skill_archive = b'invalid archive'
        self.assertIn('provider_skill_drift', self.apply(plan)[2])
        self.assertEqual(len(self.provider.writes), 2)

    def test_drift_in_unversioned_environment_refuses_binding(self):
        plan = self.plan()
        self.assertEqual(self.apply(plan)[0], 0)
        self.provider.resources['environments'][0]['config']['networking']['allowed_hosts'] = [
            'evil.invalid'
        ]
        self.assertIn('provider_definition_drift', self.apply(plan)[2])
        self.assertEqual(len(self.provider.writes), 2)

    def test_added_execution_tool_or_changed_version_refuses_binding(self):
        plan = self.plan()
        self.assertEqual(self.apply(plan)[0], 0)
        agent = self.provider.resources['agents'][0]
        agent['tools'].append({'type': 'agent_toolset_20260401'})
        self.assertIn('provider_definition_drift', self.apply(plan)[2])
        agent['tools'].pop()
        agent['version'] = 2
        self.assertIn('provider_definition_drift', self.apply(plan)[2])

    def test_review_digest_and_current_release_are_required(self):
        plan = self.plan()
        changed = copy.deepcopy(plan)
        changed['configuration_sha256'] = '0' * 64
        self.assertIn('reviewed_digest_required', self.apply(changed)[2])
        plan['agent']['tools'].append({'type': 'agent_toolset_20260401'})
        setup.save(self.plan_path, plan)
        self.assertIn('release_definition_changed', self.apply(plan)[2])
        self.assertEqual(self.provider.calls, [])

    def test_packaged_playbook_and_registry_are_the_source_of_truth(self):
        plan = self.plan()
        definitions = setup.Registry(setup.catalogue.TOOLS).definitions(
            'claude_managed', setup.LOCAL_STAGE, setup.ROLE_EFFECTS['writer']
        )
        self.assertEqual(plan['definitions_sha256'], setup.digest(definitions))
        self.assertNotIn(setup.playbook.render_document(), plan['agent']['system'])
        self.assertLess(len(plan['agent']['system']), 2500)
        self.assertIn('Load the attached', plan['agent']['system'])
        with patch.object(
            setup.playbook, 'render_document', return_value='changed release guidance'
        ):
            self.assertIn('release_definition_changed', self.apply(plan)[2])
        self.assertEqual(self.provider.calls, [])

    def test_missing_insecure_or_symlinked_key_does_not_create_intent(self):
        plan = self.plan()
        self.key.unlink()
        self.assertIn('credential_unavailable', self.apply(plan)[2])
        self.assertFalse(self.state_path.exists())
        self.key.write_text('synthetic-private-test-key')
        self.key.chmod(0o644)
        self.assertIn('private_file_required', self.apply(plan)[2])
        other = self.root / 'other-key'
        self.key.rename(other)
        self.key.symlink_to(other)
        self.assertIn('private_path_required', self.apply(plan)[2])
        self.assertEqual(self.provider.calls, [])

    def test_credential_provider_body_and_request_headers_never_enter_diagnostics(self):
        plan = self.plan()
        self.provider.reject = True
        code, out, err = self.apply(plan)
        self.assertEqual(code, 2)
        self.assertIn('provider_authentication', err)
        self.assertNotIn('synthetic-private-test-key', out + err + self.state_path.read_text())
        self.assertNotIn('upstream-secret-body', out + err)
        self.provider.reject = False
        self.assertEqual(self.apply(plan)[0], 0)

    def test_private_locations_and_path_aliases_are_required(self):
        plan = self.plan()
        with patch.object(setup, 'REPO', self.root):
            self.assertIn('private_path_required', self.apply(plan)[2])
        self.root.chmod(0o777)
        try:
            self.assertIn('private_directory_required', self.apply(plan)[2])
        finally:
            self.root.chmod(0o700)
        self.assertIn(
            'paths_must_be_distinct',
            self.command(
                'apply',
                '--state',
                str(self.plan_path),
                '--key-file',
                str(self.key),
                '--approve',
                plan['configuration_sha256'],
            )[2],
        )
        self.assertEqual(self.provider.calls, [])

    def test_pagination_duplicate_match_and_concurrent_writer_are_closed(self):
        plan = self.plan()
        self.assertEqual(self.apply(plan)[0], 0)
        self.state_path.unlink()
        self.provider.paginate = True
        self.assertEqual(self.apply(plan, 'reconcile')[0], 0)
        self.state_path.unlink()
        self.provider.resources['agents'].append(
            copy.deepcopy(self.provider.resources['agents'][-1])
        )
        self.assertIn('ambiguous_resource', self.apply(plan, 'reconcile')[2])
        with setup.locked(self.state_path):
            self.assertIn('setup_already_running', self.apply(plan)[2])
        self.assertEqual(len(self.provider.writes), 2)

    def test_shared_allowance_and_sessions_are_outside_setup_ownership(self):
        plan = self.plan()
        with patch.dict(
            os.environ,
            {'HYPRN_MVP_ASSISTANT_TOTAL_CENTS': '11000', 'HYPRN_MVP_ASSISTANT_PRIOR_CENTS': '3500'},
        ):
            self.assertEqual(self.apply(plan)[0], 0)
            self.assertEqual(os.environ['HYPRN_MVP_ASSISTANT_PRIOR_CENTS'], '3500')
        self.assertTrue(all('/sessions' not in url for _, url in self.provider.calls))
        self.assertTrue(all('budget' not in body for _, body in self.provider.writes))


    def test_public_research_allowlist_is_configurable_and_plan_pinned(self):
        pins = test_bindings()
        plan = setup.definition('staging', 'claude-sonnet-5-5', 'high', bindings=pins,
                                public_hosts=['nasa.gov', '*.nasa.gov'])
        self.assertEqual(plan['environment']['config']['networking']['allowed_hosts'],
                         ['*.nasa.gov', 'nasa.gov'])
        self.assertEqual(setup.validate_plan(plan), plan)
        self.assertIn('url_not_allowed', plan['agent']['system'])
        altered = copy.deepcopy(plan)
        altered['research_hosts'].append('nist.gov')
        with self.assertRaisesRegex(setup.ProviderError, 'release_definition_changed'):
            setup.validate_plan(altered)
        for hosts in ([], ['*'], ['127.0.0.1'], ['metadata.internal'], ['localhost'], ['https://nasa.gov']):
            with self.assertRaises(setup.ProviderError):
                setup.bootstrap('staging', 'claude-sonnet-5-5', 'high', public_hosts=hosts)

    def bootstrap_plan(self):
        self.assertEqual(self.command('bootstrap', '--deployment', 'staging',
                                    '--model', 'claude-sonnet-5-5', '--effort', 'high')[0], 0)
        return json.loads(self.plan_path.read_text())

    def test_bootstrap_uploads_curated_archive_and_returns_exact_pins(self):
        plan = self.bootstrap_plan()
        code, output, error = self.apply(plan)
        self.assertEqual((code, error), (0, ''))
        bindings = json.loads(output)
        self.assertEqual(bindings['skill']['version'], 'skver_test')
        self.assertEqual(bindings['skill']['sha256'], plan['skill_bundle']['sha256'])
        self.assertEqual(set(bindings['reviewers']), set(setup.REVIEW_ROLES))
        self.assertEqual(len(self.provider.writes), 4)
        self.assertEqual(self.apply(plan)[0], 0)
        self.assertEqual(len(self.provider.writes), 4)
        final = setup.definition('staging', 'claude-sonnet-5-5', 'high', bindings=bindings)
        self.assertEqual(final['agent']['multiagent']['subagents']['inline_agents'], {'type': 'disabled'})
        for reviewer in final['reviewers'].values():
            self.assertNotIn('multiagent', reviewer)
            self.assertEqual(reviewer['skills'], final['agent']['skills'])
            reads = setup.Registry(setup.catalogue.TOOLS).definitions(
                'claude_managed', setup.LOCAL_STAGE, frozenset({'read'}))
            self.assertEqual([tool['name'] for tool in reviewer['tools'] if tool['type'] == 'custom'],
                             [tool['name'] for tool in reads])

    def test_unknown_skill_upload_is_reconciled_without_duplicate(self):
        plan = self.bootstrap_plan()
        self.provider.interrupt_kind = 'skills'
        self.assertEqual(self.apply(plan)[0], 2)
        self.assertEqual(len(self.provider.writes), 1)
        self.assertIn('setup_incomplete', self.apply(plan, 'reconcile')[2])
        self.assertEqual(len(self.provider.writes), 1)
        self.assertEqual(self.apply(plan)[0], 0)
        self.assertEqual(len(self.provider.resources['skills']), 1)
        self.assertEqual(len(self.provider.writes), 4)

    def test_known_null_fetch_default_reconciles_intent_without_creation(self):
        plan = self.bootstrap_plan()
        self.assertEqual(self.apply(plan)[0], 0)
        state = json.loads(self.state_path.read_text())
        resource = next(key for key in state['resources'] if key.startswith('agent:'))
        state['resources'][resource] = {'status': 'intent'}
        setup.save(self.state_path, state)
        before = len(self.provider.writes)
        self.assertEqual(self.apply(plan, 'reconcile')[0], 0)
        self.assertEqual(len(self.provider.writes), before)
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state['resources'][resource]['status'], 'confirmed')

    def test_reviewer_readback_refuses_any_nested_delegation_configuration(self):
        plan = self.bootstrap_plan()
        self.assertEqual(self.apply(plan)[0], 0)
        reviewer = self.provider.resources['agents'][0]
        reviewer['multiagent'] = {'type': 'multiagent_20261001',
                                 'subagents': {'type': 'disabled'}}
        self.assertIn('provider_definition_drift', self.apply(plan, 'reconcile')[2])
        self.assertEqual(len(self.provider.writes), 4)

    def test_fetch_normalization_never_ignores_policy_or_unknown_fields(self):
        plan = self.bootstrap_plan()
        self.assertEqual(self.apply(plan)[0], 0)
        agent = self.provider.resources['agents'][0]
        toolset = next(tool for tool in agent['tools'] if tool['type'] == 'agent_toolset_20260401')
        fetch = next(config for config in toolset['configs'] if config['name'] == 'web_fetch')
        self.assertIsNone(fetch['url_sources'])
        for field, value in [('url_sources', {'user_input': {'type': 'none'}}),
                             ('unknown_permission', None), ('enabled', False)]:
            original = copy.deepcopy(fetch)
            fetch[field] = value
            self.assertIn('provider_definition_drift', self.apply(plan, 'reconcile')[2])
            fetch.clear()
            fetch.update(original)
        self.assertEqual(len(self.provider.writes), 4)

    def test_uncertain_absent_skill_upload_is_never_repeated(self):
        plan = self.bootstrap_plan()
        self.provider.interrupt_kind = 'skills'
        self.provider.commit_before_interrupt = False
        self.assertEqual(self.apply(plan)[0], 2)
        self.assertIn('creation_uncertain_requires_reconciliation', self.apply(plan)[2])
        self.assertEqual(len(self.provider.writes), 1)

    def test_unpinned_skill_or_reviewer_cannot_be_a_production_plan(self):
        with self.assertRaisesRegex(setup.ProviderError, 'exact_bootstrap_bindings_required'):
            setup.definition('staging', 'claude-sonnet-5-5', 'high')
        for field, value in [('version', 'latest'), ('sha256', '0' * 64)]:
            pins = test_bindings()
            pins['skill'][field] = value
            with self.assertRaises(setup.ProviderError):
                setup.definition('staging', 'claude-sonnet-5-5', 'high', bindings=pins)
        pins = test_bindings()
        pins['reviewers']['source-reviewer']['version'] = True
        with self.assertRaises(setup.ProviderError):
            setup.definition('staging', 'claude-sonnet-5-5', 'high', bindings=pins)

    def test_reproducible_bundle_has_only_curated_files_and_detects_extra_content(self):
        first, manifest = setup.managed_skill.bundle()
        self.assertEqual((first, manifest), setup.managed_skill.bundle())
        setup.managed_skill.verify_archive(first, manifest)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(set(archive.namelist()), set(manifest['files']) | {'hyprn/manifest.json'})
            self.assertTrue(all(name.endswith(('.md', '.json')) for name in archive.namelist()))
            self.assertEqual(archive.read('hyprn/references/playbook.md').decode(), setup.playbook.render_document())
        changed = io.BytesIO(first)
        with zipfile.ZipFile(changed, 'a') as archive:
            archive.writestr('hyprn/secret', b'secret')
        with self.assertRaisesRegex(setup.ProviderError, 'provider_skill_drift'):
            setup.managed_skill.verify_archive(changed.getvalue(), manifest)

    def test_bundle_never_follows_source_symlinks_outside_curated_tree(self):
        import shutil
        root = self.root / 'source'
        for relative in setup.managed_skill.FILES:
            source = setup.managed_skill.REPO / (setup.managed_skill.SOURCE + relative)
            target = root / (setup.managed_skill.SOURCE + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        target = root / (setup.managed_skill.SOURCE + 'references/primary-sources.md')
        target.unlink()
        target.symlink_to(self.key)
        with self.assertRaisesRegex(setup.ProviderError, 'skill_source_invalid'):
            setup.managed_skill.bundle(root)

    def test_effort_comparison_freezes_same_guidance_and_scenarios(self):
        high = setup.bootstrap('staging', 'claude-sonnet-5-5', 'high')
        medium = setup.bootstrap('staging', 'claude-sonnet-5-5', 'medium')
        self.assertEqual(high['skill_bundle'], medium['skill_bundle'])
        self.assertIn('docs/agents/scientific-engineering/references/behavioral-scenarios.md',
                      high['skill_bundle']['inputs'])
        # This checks frozen inputs only. Quality, tokens, cost and latency need live evaluation.


class ProviderDouble:
    """Official resource shapes through the real HTTP adapter, with controllable lost replies."""

    def __init__(self):
        self.resources = {'agents': [], 'environments': [], 'skills': []}
        self.skill_archive = setup.managed_skill.bundle()[0]
        self.calls, self.writes = [], []
        self.interrupt_kind = None
        self.commit_before_interrupt = True
        self.before_write = lambda: None
        self.reject = self.paginate = False

    def seed(self, prepared, bindings):
        self.resources['skills'] = [{'id': bindings['skill']['id'], 'latest_version_id': bindings['skill']['version'],
                                     'display_name': 'hyprn-' + bindings['skill']['sha256']}]
        self.resources['agents'] = [{**value, **bindings['reviewers'][role], 'archived_at': None}
                                   for role, value in setup.reviewer_resources(prepared, bindings['skill']).items()]

    def __call__(self, request):
        self.calls.append((request.method, str(request.url)))
        assert request.url.host == 'api.anthropic.com'
        assert request.headers['x-api-key'] == 'synthetic-private-test-key'
        assert request.headers['anthropic-beta'] == 'managed-agents-2026-04-01'
        pieces = request.url.path.split('/')
        kind = pieces[2]
        assert kind in self.resources
        if request.method == 'POST':
            assert len(pieces) == 3
            self.before_write()
            if kind == 'skills':
                message = email.message_from_bytes(('Content-Type: ' + request.headers['content-type']
                                                     + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + request.content)
                parts = {part.get_param('name', header='content-disposition'): part.get_payload(decode=True)
                         for part in message.walk() if part.get_content_maintype() != 'multipart'}
                self.skill_archive = parts['files[]']
                body = {'display_name': parts['display_name'].decode()}
            else:
                body = json.loads(request.content)
            self.writes.append((kind, body))
            if kind == 'agents':
                delegation = body.get('multiagent') or {}
                references = delegation.get('subagents', {}).get('predefined_agents', [])
                for reference in references:
                    referenced = next(row for row in self.resources['agents']
                                      if row['id'] == reference['id'])
                    if referenced.get('multiagent') is not None:
                        return httpx.Response(400, json={'error': {
                            'type': 'invalid_request_error',
                            'message': ('Referenced agent has its own subagents; '
                                        'maximum depth is 1')}})
            if self.reject:
                return httpx.Response(401, json={'error': 'upstream-secret-body'})
            resource = copy.deepcopy(body)
            resource.update(
                id=({'agents': 'agent_', 'environments': 'env_', 'skills': 'skill_'}[kind]) + str(len(self.resources[kind]) + 1),
                archived_at=None,
            )
            if kind == 'agents':
                resource['version'] = 1
                resource.setdefault('multiagent', None)
                for tool in resource.get('tools', []):
                    if tool.get('type') == 'agent_toolset_20260401':
                        for config in tool.get('configs', []):
                            if config.get('type') == 'web_fetch':
                                config.setdefault('url_sources', None)
            elif kind == 'skills':
                resource['latest_version_id'] = 'skver_test'
            else:
                assert 'packages' not in resource['config']
                resource['config']['packages'] = {
                    'type': 'packages',
                    **{manager: [] for manager in setup.MANAGERS},
                }
            interrupted = kind == self.interrupt_kind
            if not interrupted or self.commit_before_interrupt:
                self.resources[kind].append(resource)
            if interrupted:
                self.interrupt_kind = None
                raise httpx.ReadTimeout('synthetic-private-test-key', request=request)
            return httpx.Response(200, json=resource)
        assert request.method == 'GET'
        if len(pieces) == 3:
            if self.paginate and 'page' not in request.url.params:
                return httpx.Response(200, json={'data': [], 'next_page': 'second'})
            return httpx.Response(200, json={'data': self.resources[kind], 'next_page': None})
        resource = next(item for item in self.resources[kind] if item['id'] == pieces[3])
        if kind == 'skills' and len(pieces) >= 6:
            if pieces[-1] == 'content':
                return httpx.Response(200, content=self.skill_archive)
            return httpx.Response(200, json={'id': pieces[5], 'skill_id': pieces[3]})
        if kind == 'agents':
            assert request.url.params['version'] == '1'
        return httpx.Response(200, json=resource)


class HostedAssistantStartupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plan = assistant_plan()
        self.identity = dict(installation_id='fixture', release_sha256='a' * 64,
                             config_sha256='b' * 64)
        self.settings = SimpleNamespace(definitions_sha256=self.plan['definitions_sha256'],
                                        agent_id='agent_fixture', agent_version=1,
                                        environment_id='environment_fixture',
                                        prior_cents=7, total_cents=100)
        self.continuity = dict(schema='hyprn-assistant-continuity/v1', **self.identity,
                               configuration_sha256=self.plan['configuration_sha256'],
                               prior_cents=7, total_cents=100, carried_sessions={'session_old': 5},
                               untracked_cents=2, review_sha256='c' * 64)
        self.rows = [dict(provider_id='session_retained',
                          conversation_id='conversation_fixture', provision='ready')]
        self.store = SimpleNamespace(assistant_user_accounts=lambda: self.rows)
        self.correlations = {'conversation_fixture': 'session_retained'}
        test = self
        class ReadOnlyProvider:
            sessions = ['session_old', 'session_retained']
            status = 'idle'
            drift = False
            skill_drift = False
            reviewer_drift = False

            async def request(self, method, path, params=None):
                test.assertEqual(method, 'GET')
                if path == '/v1/sessions':
                    test.assertEqual(params, {'limit': 100, 'include_archived': 'true'})
                    return {'data': [{'id': sid} for sid in self.sessions], 'next_page': None}
                skill = test.plan['bindings']['skill']
                if path == '/v1/skills/' + skill['id'] + '/versions/' + skill['version']:
                    return {'id': skill['version'], 'skill_id': skill['id']}
                for role, binding in test.plan['bindings']['reviewers'].items():
                    if path == '/v1/agents/' + binding['id']:
                        test.assertEqual(params, {'version': binding['version']})
                        result = dict(copy.deepcopy(test.plan['reviewers'][role]), **binding)
                        if self.reviewer_drift:
                            result['tools'] = test.plan['agent']['tools']
                        return result
                if path == '/v1/agents/agent_fixture':
                    test.assertEqual(params, {'version': 1})
                    result = dict(copy.deepcopy(test.plan['agent']), id='agent_fixture', version=1)
                    if self.drift:
                        result['tools'] = []
                    return result
                if path == '/v1/environments/environment_fixture':
                    result = dict(copy.deepcopy(test.plan['environment']), id='environment_fixture')
                    result['config']['packages'] = {'type': 'packages',
                        **{manager: [] for manager in setup.MANAGERS}}
                    return result
                raise AssertionError('Unexpected provider request')

            async def skill_content(self, skill_id, version):
                test.assertEqual((skill_id, version), ('skill_fixture', 'skver_fixture'))
                return b'wrong archive' if self.skill_drift else setup.managed_skill.bundle()[0]

            async def find_session(self, correlation):
                found = test.correlations.get(correlation)
                return {'id': found} if found else None

            async def session_account(self, session_id):
                return {'status': self.status,
                        'spent_cents': 5 if session_id == 'session_old' else 11}
        self.provider = ReadOnlyProvider()

    async def check(self):
        return await reconcile(self.store, self.provider, self.settings, self.plan,
                               self.continuity, self.identity)

    async def test_old_release_continuity_is_refused_before_provider_calls(self):
        self.continuity['release_sha256'] = 'f' * 64
        with patch.object(self.provider, 'request') as request:
            with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
                await self.check()
            request.assert_not_called()

    async def test_exact_full_definition_and_archived_prior_spend_are_checked(self):
        result = await self.check()
        self.assertEqual(result['spent_cents'], 18)
        self.assertEqual(result['sessions'], 2)

    async def test_unknown_busy_or_changed_provider_records_refuse_startup(self):
        self.provider.sessions.append('session_unknown')
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()
        self.provider.sessions.pop()
        self.provider.status = 'running'
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_busy'):
            await self.check()
        self.provider.status = 'idle'
        self.provider.drift = True
        with self.assertRaisesRegex(ProviderError, 'provider_definition_drift'):
            await self.check()

    async def test_changed_native_skill_or_reviewer_write_authority_blocks_startup(self):
        self.provider.skill_drift = True
        with self.assertRaisesRegex(ProviderError, 'provider_skill_drift'):
            await self.check()
        self.provider.skill_drift = False
        self.provider.reviewer_drift = True
        with self.assertRaisesRegex(ProviderError, 'provider_definition_drift'):
            await self.check()

    async def test_bootstrap_or_missing_pins_cannot_start_delivery(self):
        original = self.plan
        for invalid in (setup.bootstrap('staging', 'claude-sonnet-5-5', 'high'),
                        {key: value for key, value in original.items() if key != 'bindings'}):
            self.plan = invalid
            with patch.object(self.provider, 'request') as request:
                with self.assertRaises(ProviderError):
                    await self.check()
                request.assert_not_called()
        self.plan = original

    async def test_missing_prior_evidence_never_becomes_zero(self):
        self.continuity['untracked_cents'] = 0
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()

    def test_complete_released_assistant_plan_has_explicit_bounded_size(self):
        plan = assistant_plan()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / 'plan.json'
            path.write_text(json.dumps(plan))
            self.assertGreater(path.stat().st_size, 65536)
            self.assertEqual(host_record(path, owner=os.getuid(), max_bytes=1024 * 1024), plan)
            with self.assertRaises(ValueError):
                host_record(path, owner=os.getuid())


    async def test_successor_generations_use_each_pinned_correlation_and_retain_all_usage(self):
        self.rows.append(dict(provider_id='session_successor', conversation_id='generation_two',
                              provision='accepted'))
        self.correlations['generation_two'] = 'session_successor'
        self.provider.sessions = [*self.provider.sessions, 'session_successor']
        # The retired current-pointer reader would pair the first correlation with
        # the successor ID. Startup must use the full per-user generation ledger.
        self.store.assistant_accounts = lambda: [dict(
            provider_id='session_successor', conversation_id='conversation_fixture',
            provision='accepted')]
        result = await self.check()
        self.assertEqual(result['sessions'], 3)
        self.assertEqual(result['spent_cents'], 29)

    async def test_missing_or_mismatched_successor_identity_still_refuses_startup(self):
        self.provider.sessions = [*self.provider.sessions, 'session_successor']
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()
        self.rows.append(dict(provider_id='session_successor', conversation_id='generation_two',
                              provision='accepted'))
        self.correlations['generation_two'] = 'session_retained'
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()
        self.correlations['generation_two'] = 'session_successor'
        self.rows.append(dict(self.rows[-1]))
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()

    async def test_uncertain_successor_creation_is_reconciled_without_mutation(self):
        self.rows.append(dict(provider_id=None, conversation_id='generation_two',
                              provision='intended'))
        self.correlations['generation_two'] = 'session_successor'
        self.provider.sessions = [*self.provider.sessions, 'session_successor']
        result = await self.check()
        self.assertEqual(result['sessions'], 3)
        self.assertEqual(result['spent_cents'], 29)
        self.assertIsNone(self.rows[-1]['provider_id'])
