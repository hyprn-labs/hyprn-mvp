"""The provider transport preserves budget, scope and uncertain-delivery boundaries."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from hyprn_mvp_app.assistant.claude import (
    Claude,
    ProviderError,
    Settings,
    agent_definition,
    credential,
)


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / 'provider-key'
    path.write_text('test-key-not-a-real-credential')
    path.chmod(0o600)
    return path


def test_private_credential_is_not_in_representations(key_file):
    assert credential(key_file) == 'test-key-not-a-real-credential'
    client = Claude(key_file)
    assert 'test-key' not in repr(client)
    asyncio.run(client.close())


@pytest.mark.parametrize('mode', [0o644, 0o640, 0o606])
def test_shared_credential_permissions_are_rejected(key_file, mode):
    key_file.chmod(mode)
    with pytest.raises(ProviderError, match='credential_unavailable'):
        credential(key_file)


def test_credential_symlinks_and_multiline_values_are_rejected(key_file):
    link = key_file.with_name('link')
    link.symlink_to(key_file)
    with pytest.raises(ProviderError):
        credential(link)
    key_file.write_text('first\nsecond')
    with pytest.raises(ProviderError):
        credential(key_file)


def test_agent_has_only_registered_custom_tools():
    value = agent_definition(
        'explicit-model',
        [
            {
                'name': 'read_study',
                'description': 'Read the current study.',
                'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
            }
        ],
        'Study guidance',
    )
    assert value['tools'][0]['type'] == 'custom'
    assert value['tools'][0]['input_schema']['additionalProperties'] is False
    assert all(value['multiagent'][name]['type'] == 'disabled' for name in ('advisor', 'workflows'))
    assert value['multiagent']['subagents'] == {
        'type': 'enabled',
        'inline_agents': {'type': 'enabled'},
    }
    assert 'mcp_servers' not in value and 'skills' not in value


def test_session_creation_pins_agent_without_a_session_budget(key_file):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'id': 'session_test'})

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        settings = Settings(key_file, 'agent_test', 3, 'env_test', 100, 500, 'a' * 64)
        result = await client.create_session(settings, 'conversation-test')
        assert result['id'] == 'session_test'
        await client.close()

    asyncio.run(exercise())
    body = json.loads(requests[0].content)
    assert 'budget' not in body
    assert body['agent'] == {'type': 'agent', 'id': 'agent_test', 'version': 3}
    assert body['metadata'] == {'hyprn_conversation_id': 'conversation-test'}
    assert requests[0].headers['anthropic-beta'] == 'managed-agents-2026-04-01'


@pytest.mark.parametrize(
    'status,uncertain', [(400, False), (401, False), (429, False), (503, True)]
)
def test_errors_are_redacted_and_mutations_never_retry(key_file, status, uncertain):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={'error': 'secret-provider-body'})

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        with pytest.raises(ProviderError) as caught:
            await client.send('session_test', {'type': 'user.interrupt'})
        assert caught.value.uncertain is uncertain
        assert 'secret' not in str(caught.value)
        await client.close()

    asyncio.run(exercise())
    assert len(requests) == 1


def test_transport_timeout_is_unknown_not_an_automatic_retry(key_file):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout('response with sensitive context', request=request)

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        with pytest.raises(ProviderError) as caught:
            await client.send('session_test', {'type': 'user.message', 'content': []})
        assert caught.value.uncertain
        assert str(caught.value) == 'provider_unavailable'
        await client.close()

    asyncio.run(exercise())
    assert len(requests) == 1


def test_empty_configuration_disables_integration_and_partial_configuration_fails():
    assert Settings.from_environment({}) is None
    with pytest.raises(ProviderError, match='configuration_invalid'):
        Settings.from_environment({'HYPRN_MVP_ASSISTANT_KEY_FILE': str(Path('/private/key'))})


def test_tool_result_reuses_original_event_identity(key_file):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={'data': []})

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        await client.tool_result('session_test', 'event_test', '{"ok":false}', is_error=True)
        await client.close()

    asyncio.run(exercise())
    assert requests[0]['events'] == [
        {
            'type': 'user.custom_tool_result',
            'custom_tool_use_id': 'event_test',
            'content': [{'type': 'text', 'text': '{"ok":false}'}],
            'is_error': True,
        }
    ]


def test_idle_tool_upgrade_preserves_session_and_budget_and_reconciles_unknown_delivery(key_file):
    requests = []
    state = {'status': 'idle', 'agent': {'tools': []}, 'budget': {'unchanged': True}}

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == 'POST':
            body = json.loads(request.content)
            assert set(body) == {'agent'} and set(body['agent']) == {'tools'}
            state['agent']['tools'] = body['agent']['tools']
            return httpx.Response(503)
        return httpx.Response(200, json=state)

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        definitions = [
            {
                'name': 'read_study',
                'description': 'Read',
                'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
            }
        ]
        await client.ensure_tools('session_existing', definitions)
        await client.ensure_tools('session_existing', definitions)
        await client.close()

    asyncio.run(exercise())
    assert requests.count(('POST', '/v1/sessions/session_existing')) == 1
    assert state['budget'] == {'unchanged': True}


@pytest.mark.parametrize('cost', [None, {}, {'amount': True, 'currency': 'USD'},
    {'amount': '-1', 'currency': 'USD'}, {'amount': '1.5', 'currency': 'USD'},
    {'amount': '20', 'currency': 'EUR'}, {'amount': '20', 'currency': 'USD'}])
def test_spending_uses_only_valid_usd_cent_snapshots(key_file, cost):
    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'usage': {'list_cost': cost}})))
        if cost == {'amount': '20', 'currency': 'USD'}:
            assert await client.spending('session_test') == 20
        else:
            with pytest.raises(ProviderError):
                await client.spending('session_test')
        await client.close()
    asyncio.run(exercise())


def test_removing_legacy_cap_reconciles_unknown_delivery_without_repeating_mutation(key_file):
    cap = {'type': 'limit', 'max_list_cost': {'amount': '500', 'currency': 'USD'}}
    writes = []

    def handler(request):
        nonlocal cap
        if request.method == 'POST':
            writes.append(json.loads(request.content))
            cap = writes[-1]['budget']
            raise httpx.ReadTimeout('uncertain response', request=request)
        return httpx.Response(200, json={'status': 'idle', 'budget': cap})

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        await client.remove_session_cap('session_test')
        await client.remove_session_cap('session_test')
        await client.close()

    asyncio.run(exercise())
    assert writes == [{'budget': None}]



@pytest.mark.parametrize('usage', [None, {}, {'list_cost': None}])
def test_missing_usage_is_actionable_not_an_internal_attribute_error(key_file, usage):
    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json={'status':'running','budget':None,'usage':usage})))
        with pytest.raises(ProviderError,match='invalid_provider_record'):
            await client.session_account('session_test')
        await client.close()
    asyncio.run(exercise())
