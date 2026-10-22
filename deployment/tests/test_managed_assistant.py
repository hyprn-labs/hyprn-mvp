"""The setup command never repeats an uncertain provider mutation."""

import json
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'application/src'))
import live_fence  # noqa: E402
import managed_assistant as setup  # noqa: E402

setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')


def offline_plan(tmp_path):
    plan = tmp_path / 'plan.json'
    result = setup.main(
        [
            'plan',
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
    assert all(tool['type'] == 'custom' for tool in value['agent']['tools'])
    assert value['environment']['config']['networking'] == {
        'type': 'limited',
        'allowed_hosts': [],
        'allow_mcp_servers': False,
        'allow_package_managers': False,
    }
    assert len(value['configuration_sha256']) == 64


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
        self.assertEqual(self.command('plan', *flattened)[0], 0)
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
            any(url.endswith('/agents/agent_1?version=1') for _, url in self.provider.calls)
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

    def test_changed_release_uses_new_agent_and_preserves_existing_environment(self):
        plan = self.plan()
        self.assertEqual(self.apply(plan)[0], 0)
        self.plan_path = self.root / 'next-review.json'
        self.assertEqual(
            self.command(
                'plan', '--deployment', 'staging', '--model', 'claude-opus-5-5', '--effort', 'high'
            )[0],
            0,
        )
        following = json.loads(self.plan_path.read_text())
        self.assertNotEqual(plan['configuration_sha256'], following['configuration_sha256'])
        self.assertEqual(self.apply(following)[0], 0)
        self.assertEqual(len(self.provider.writes), 3)
        self.assertEqual(len(self.provider.resources['environments']), 1)
        self.assertEqual(len(self.provider.resources['agents']), 2)

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
        self.assertIn(setup.playbook.render_document(), plan['agent']['system'])
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
            copy.deepcopy(self.provider.resources['agents'][0])
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


class ProviderDouble:
    """Official resource shapes through the real HTTP adapter, with controllable lost replies."""

    def __init__(self):
        self.resources = {'agents': [], 'environments': []}
        self.calls, self.writes = [], []
        self.interrupt_kind = None
        self.commit_before_interrupt = True
        self.before_write = lambda: None
        self.reject = self.paginate = False

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
            body = json.loads(request.content)
            self.writes.append((kind, body))
            if self.reject:
                return httpx.Response(401, json={'error': 'upstream-secret-body'})
            resource = copy.deepcopy(body)
            resource.update(
                id=('agent_' if kind == 'agents' else 'env_') + str(len(self.resources[kind]) + 1),
                archived_at=None,
            )
            if kind == 'agents':
                resource['version'] = 1
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
        if kind == 'agents':
            assert request.url.params['version'] == '1'
        return httpx.Response(200, json=resource)
