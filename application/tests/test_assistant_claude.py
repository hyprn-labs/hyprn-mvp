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


def test_agent_cannot_delegate_to_unlisted_or_inline_agents():
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
    assert value['multiagent']['subagents'] == {'type': 'disabled'}
    assert value['mcp_servers'] == [] and value['skills'] == []


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


def test_research_defaults_deny_every_other_builtin_and_pins_reviewers():
    from hyprn_mvp_app.assistant.claude import research_tools
    pin = {'type': 'agent', 'id': 'agent_source', 'version': 2}
    value = agent_definition('model', [], 'system', reviewers=[pin], research=True)
    assert value['tools'] == research_tools()
    toolset = value['tools'][0]
    assert toolset['default_config']['enabled'] is False
    assert {item['name'] for item in toolset['configs']} == {'read', 'web_search', 'web_fetch'}
    assert value['multiagent']['subagents'] == {
        'type': 'enabled', 'inline_agents': {'type': 'disabled'}, 'predefined_agents': [pin]}


def test_catalogue_refresh_preserves_research_and_rejects_unreviewed_builtins(key_file):
    from hyprn_mvp_app.assistant.claude import research_tools
    state = {'status': 'idle', 'agent': {'tools': research_tools()}}
    writes = []
    def handler(request):
        if request.method == 'POST':
            writes.append(json.loads(request.content))
            state['agent']['tools'] = writes[-1]['agent']['tools']
        return httpx.Response(200, json=state)
    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        await client.ensure_tools('session_test', [])
        assert not writes
        state['agent']['tools'].append({'type': 'agent_toolset_20260401'})
        with pytest.raises(ProviderError, match='provider_definition_drift'):
            await client.ensure_tools('session_test', [])
        await client.close()
    asyncio.run(exercise())


def test_skill_upload_uses_multipart_and_download_keeps_binary_bytes(key_file):
    requests = []
    def handler(request):
        requests.append(request)
        return (httpx.Response(200, content=b'archive') if request.method == 'GET'
                else httpx.Response(200, json={'id': 'skill_test', 'latest_version_id': 'skver_test'}))
    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        await client.upload_skill(b'archive', 'hyprn-digest')
        assert await client.skill_content('skill_test', 'skver_test') == b'archive'
        with pytest.raises(ProviderError, match='exact_skill_version_required'):
            await client.skill_content('skill_test', 'latest')
        await client.close()
    asyncio.run(exercise())
    assert len(requests) == 2
    assert requests[0].headers['content-type'].startswith('multipart/form-data;')
    assert b'name="files[]"; filename="hyprn.zip"' in requests[0].content
    assert b'application/zip' in requests[0].content
    assert requests[1].url.path == '/v1/skills/skill_test/versions/skver_test/content'


@pytest.mark.parametrize('session_id,thread_id', [
    ('session_test', 'thread_test'), ('session_other', 'thread_test'), ('session_test', 'thread_other')])
def test_thread_identity_is_authenticated_and_bound_to_the_requested_session(key_file, session_id, thread_id):
    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json={'id': thread_id, 'session_id': session_id,
                                      'parent_thread_id': 'thread_primary',
                                      'agent': {'id': 'agent_review', 'version': 3}})))
        if session_id == 'session_test' and thread_id == 'thread_test':
            result = await client.thread_agent('session_test', 'thread_test')
            assert result['agent'] == {'id': 'agent_review', 'version': 3}
        else:
            with pytest.raises(ProviderError, match='invalid_provider_record'):
                await client.thread_agent('session_test', 'thread_test')
        await client.close()
    asyncio.run(exercise())


@pytest.mark.parametrize('extra', [None, {'unexpected_permission': None},
                                   {'url_sources': {'type': 'all'}}])
def test_session_accepts_only_the_observed_optional_fetch_null(key_file, extra):
    from hyprn_mvp_app.assistant.claude import research_tools
    tools = research_tools()
    tools[0]['configs'][2]['url_sources'] = None
    if extra:
        tools[0]['configs'][2].update(extra)
    writes = []
    state = {'status': 'idle', 'agent': {'tools': tools}}

    def handler(request):
        if request.method != 'GET':
            writes.append(request.method)
        return httpx.Response(200, json=state)

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        try:
            if extra:
                with pytest.raises(ProviderError, match='provider_definition_drift'):
                    await client.ensure_tools('session_test', [])
            else:
                await client.ensure_tools('session_test', [])
            assert not writes
            assert 'url_sources' in tools[0]['configs'][2]
        finally:
            await client.close()
    asyncio.run(exercise())


@pytest.mark.parametrize('kind', [
    'agent.custom_tool_use', 'user.custom_tool_result', 'agent.message'])
def test_large_non_attachment_content_is_never_silently_truncated(kind):
    from hyprn_mvp_app.assistant.claude import retained_event
    event = dict(id='event_test', type=kind, input={'data': 'x' * 1_100_000})
    with pytest.raises(ProviderError, match='provider_response_too_large'):
        retained_event(event)


@pytest.mark.parametrize('data', ['not base64!', '\u00e9', True])
def test_corrupt_attachment_cannot_be_retained_as_success(data):
    from hyprn_mvp_app.assistant.claude import retained_event
    event = dict(id='event_test', type='agent.tool_result', content=[dict(
        type='document', source=dict(type='base64', media_type='application/pdf', data=data))])
    with pytest.raises(ProviderError, match='invalid_provider_attachment'):
        retained_event(event)


def test_attachment_decoded_total_is_bounded(monkeypatch):
    import base64
    from hyprn_mvp_app.assistant import claude
    monkeypatch.setattr(claude, 'MAX_ATTACHMENT_BYTES', 8)
    block = dict(type='document', source=dict(type='base64', media_type='application/pdf',
                                            data=base64.b64encode(b'12345').decode()))
    with pytest.raises(ProviderError, match='provider_attachment_too_large'):
        claude.retained_event(dict(id='event_test', type='agent.tool_result',
                                   content=[block, block]))


def test_large_event_pages_shrink_without_skipping_cursor_and_remain_bounded(key_file, monkeypatch):
    from hyprn_mvp_app.assistant import claude
    monkeypatch.setattr(claude, 'MAX_RESPONSE', 100)
    monkeypatch.setattr(claude, 'MAX_ATTACHMENT_RESPONSE', 1000)
    seen = []

    def handler(request):
        params = dict(request.url.params)
        seen.append(params)
        if params.get('page') == 'page_two':
            return httpx.Response(200, json={'data': [dict(id='event_next')], 'next_page': None})
        if int(params['limit']) > 1:
            return httpx.Response(200, content=b' ' * 1001)
        return httpx.Response(200, json={'data': [dict(id='event_large', data='x' * 200)],
                                        'next_page': 'page_two'})

    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        events = [event async for event in client.events('session_test', 'original_cursor')]
        assert [event['id'] for event in events] == ['event_large', 'event_next']
        await client.close()
    asyncio.run(exercise())
    assert [int(p['limit']) for p in seen] == [100, 50, 25, 12, 6, 3, 1, 1, 1]
    assert all(p['created_at[gte]'] == 'original_cursor' for p in seen)
    assert all('page' not in p for p in seen[:-1])


def test_single_oversized_event_has_a_finite_transport_ceiling(key_file, monkeypatch):
    from hyprn_mvp_app.assistant import claude
    monkeypatch.setattr(claude, 'MAX_RESPONSE', 100)
    monkeypatch.setattr(claude, 'MAX_ATTACHMENT_RESPONSE', 1000)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=b'x' * 1001)
    async def exercise():
        client = Claude(key_file, transport=httpx.MockTransport(handler))
        with pytest.raises(ProviderError, match='provider_attachment_too_large'):
            [event async for event in client.events('session_test')]
        await client.close()
    asyncio.run(exercise())
    assert len(calls) == 8


def test_attachment_page_retries_do_not_expand_total_history_admission(key_file):
    count = 0
    async def exercise():
        nonlocal count
        client = Claude(key_file)
        async def request(method, path, **kwargs):
            page = int(kwargs['params'].get('page', '0'))
            return {'data': [dict(id='event_' + str(i + page * 100)) for i in range(100)],
                    'next_page': str(page + 1)}
        client.request = request
        with pytest.raises(ProviderError, match='provider_history_limit'):
            async for _ in client.events('session_test'):
                count += 1
        await client.close()
    asyncio.run(exercise())
    assert count == 10_000
