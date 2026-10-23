"""Claude Managed Agents wire adapter; no reasoning loop or scientific effects.

Custom HYPRN tools and an explicitly constrained research toolset are exposed. Requests never retry mutations automatically.
Callers own durable intent and reconcile unknown delivery against provider records.
The endpoint is fixed: a configured credential cannot be redirected to another host.
"""

from dataclasses import dataclass, field
import copy
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import httpx

API = 'https://api.anthropic.com'
BETA = 'managed-agents-2026-04-01'
MAX_RESPONSE = 8 * 1024 * 1024
MAX_ATTACHMENT_RESPONSE = 48 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024
MAX_RETAINED_EVENT = 1024 * 1024
IDENTITY = re.compile(r'[a-zA-Z0-9_-]{1,128}')


class ProviderError(Exception):
    """Safe, fixed diagnostic; provider bodies and request headers are never surfaced."""

    def __init__(self, code, *, uncertain=False, status=None):
        self.code, self.uncertain, self.status = code, uncertain, status
        super().__init__(code)


def retained_event(event):
    """Retain binary retrieval identity, not provider-owned bytes or a verified excerpt.

    Only built-in result attachments are projected. Custom tool arguments/results and
    fetched text retain their exact content and the ordinary event-size boundary.
    """
    value = copy.deepcopy(event)
    total = 0
    if value.get('type') == 'agent.tool_result':
        content = value.get('content')
        if isinstance(content, list):
            content = value['content'] = [copy.deepcopy(block) for block in content]
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get('type') not in ('document', 'image'):
                continue
            source = block.get('source')
            if not isinstance(source, dict) or source.get('type') != 'base64':
                continue
            data, media = source.get('data'), source.get('media_type')
            if not isinstance(data, str) or not isinstance(media, str) or len(media) > 128:
                raise ProviderError('invalid_provider_attachment')
            if len(data) > 4 * ((MAX_ATTACHMENT_BYTES + 2) // 3):
                raise ProviderError('provider_attachment_too_large')
            try:
                raw = base64.b64decode(data, validate=True)
            except (ValueError, binascii.Error):
                raise ProviderError('invalid_provider_attachment') from None
            total += len(raw)
            if total > MAX_ATTACHMENT_BYTES:
                raise ProviderError('provider_attachment_too_large')
            block['source'] = dict(type='provider_attachment', media_type=media,
                byte_length=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                provider_event_id=identity(value.get('id')))
    size = len(json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':'), sort_keys=True).encode())
    if size > MAX_RETAINED_EVENT:
        raise ProviderError('provider_response_too_large')
    return value


def credential(path):
    """Read one private, owner-controlled regular file without following a final symlink."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(Path(path), flags)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) & 0o077
                or (hasattr(os, 'getuid') and info.st_uid != os.getuid())
            ):
                raise ValueError()
            raw = stream.read(4097)
        value = raw.decode('ascii').strip()
        if not value or len(raw) > 4096 or not value.isprintable() or ' ' in value:
            raise ValueError()
        return value
    except (OSError, ValueError, UnicodeError):
        raise ProviderError('credential_unavailable') from None


@dataclass(frozen=True)
class Settings:
    key_file: Path = field(repr=False)
    agent_id: str
    agent_version: int
    environment_id: str
    session_cents: int
    total_cents: int
    definitions_sha256: str
    prior_cents: int = 0
    approved_minor: int | None = None
    approved_currency: str | None = None
    conversion_date: str | None = None
    user_limits_cents: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_environment(cls, environ):
        """Explicit configuration only; an absent credential setting leaves this disabled."""
        prefix = 'HYPRN_MVP_ASSISTANT_'
        if not environ.get(prefix + 'KEY_FILE'):
            return None
        try:
            value = cls(
                Path(environ[prefix + 'KEY_FILE']),
                environ[prefix + 'AGENT_ID'],
                int(environ[prefix + 'AGENT_VERSION']),
                environ[prefix + 'ENVIRONMENT_ID'],
                int(environ[prefix + 'TOTAL_CENTS']),
                int(environ[prefix + 'TOTAL_CENTS']),
                environ[prefix + 'DEFINITIONS_SHA256'],
                int(environ.get(prefix + 'PRIOR_CENTS', '0')),
                int(environ[prefix + 'APPROVED_MINOR'])
                if prefix + 'APPROVED_MINOR' in environ else None,
                environ.get(prefix + 'APPROVED_CURRENCY'),
                environ.get(prefix + 'CONVERSION_DATE'),
                json.loads(environ.get(prefix + 'USER_LIMITS_CENTS', '{}')),
            )
            if (not isinstance(value.user_limits_cents, dict)
                or len(value.user_limits_cents) > 1000
                or any(not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', actor)
                       or type(limit) is not int or not 0 < limit <= 1_000_000
                       for actor, limit in value.user_limits_cents.items())):
                raise ValueError()
            if (
                not value.key_file.is_absolute()
                or not IDENTITY.fullmatch(value.agent_id)
                or not IDENTITY.fullmatch(value.environment_id)
                or value.agent_version < 1
                or not 0 < value.session_cents <= value.total_cents <= 1_000_000
                or not re.fullmatch('[0-9a-f]{64}', value.definitions_sha256)
                or not 0 <= value.prior_cents < value.total_cents
                or (value.approved_minor is not None and not 0 < value.approved_minor <= 1_000_000)
                or ((value.approved_minor is None) != (value.approved_currency is None))
                or (value.approved_currency is not None
                    and not re.fullmatch('[A-Z]{3}', value.approved_currency))
                or (value.conversion_date is not None
                    and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.conversion_date))
            ):
                raise ValueError()
            return value
        except (KeyError, TypeError, ValueError):
            raise ProviderError('configuration_invalid') from None


def identity(value):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise ProviderError('invalid_provider_record')
    return value


def research_tools():
    """No shell, writing, repository mounts, MCP servers or arbitrary network client."""
    return [{
        'type': 'agent_toolset_20260401',
        'default_config': {'enabled': False, 'permission_policy': {'type': 'always_allow'}},
        'configs': [
            {'name': 'read', 'type': 'read', 'enabled': True,
             'permission_policy': {'type': 'always_allow'}},
            {'name': 'web_search', 'type': 'web_search', 'enabled': True,
             'permission_policy': {'type': 'always_allow'}},
            {'name': 'web_fetch', 'type': 'web_fetch', 'enabled': True,
             'max_content_tokens': 12000,
             'permission_policy': {'type': 'always_allow'}},
        ],
    }]


def readback_tools(tools):
    """Only the observed optional web-fetch null default is equivalent to omission.

    Do not drop arbitrary unknown/null properties: tool additions and actual URL-source
    restrictions must still differ from the exact reviewed definition.
    """
    value = copy.deepcopy(tools)
    if not isinstance(value, list):
        return value
    for tool in value:
        if not isinstance(tool, dict) or tool.get('type') != 'agent_toolset_20260401':
            continue
        configs = tool.get('configs')
        if not isinstance(configs, list):
            continue
        for config in configs:
            if (isinstance(config, dict) and config.get('type') == 'web_fetch'
                    and config.get('name') == 'web_fetch' and config.get('url_sources') is None):
                config.pop('url_sources', None)
    return value


def agent_definition(model, definitions, system, *, skills=(), reviewers=(), research=False):
    """Explicit capabilities; unlisted and inline delegates are never available."""
    return {
        'name': 'HYPRN study assistant',
        'model': model,
        'system': system,
        'multiagent': {
            'type': 'multiagent_20261001',
            'advisor': {'type': 'disabled'},
            'subagents': ({'type': 'enabled', 'inline_agents': {'type': 'disabled'},
                           'predefined_agents': list(reviewers)}
                          if reviewers else {'type': 'disabled'}),
            'workflows': {'type': 'disabled'},
        },
        'tools': custom_tools(definitions) + (research_tools() if research else []),
        'mcp_servers': [],
        'skills': list(skills),
    }


def custom_tools(definitions):
    return [
        dict(
            type='custom',
            name=item['name'],
            description=item['description'],
            input_schema=item['inputSchema'],
        )
        for item in definitions
    ]


class Claude:
    def __init__(self, key_file, *, transport=None):
        self._key_file = key_file
        self._client = httpx.AsyncClient(
            base_url=API,
            timeout=30,
            follow_redirects=False,
            transport=transport,
        )

    def __repr__(self):
        return 'Claude()'

    async def close(self):
        await self._client.aclose()

    async def request(self, method, path, *, body=None, params=None, files=None,
                      data=None, binary=False, response_limit=MAX_RESPONSE):
        if not path.startswith('/v1/') or '..' in path or '?' in path:
            raise ValueError('A provider path must be fixed by the adapter')
        headers = {
            'x-api-key': credential(self._key_file),
            'anthropic-version': '2023-06-01',
            'anthropic-beta': BETA,
        }
        uncertain = method != 'GET'
        try:
            async with self._client.stream(
                method, path, json=body, params=params, headers=headers, files=files, data=data
            ) as reply:
                if reply.status_code >= 300:
                    code = {
                        401: 'provider_authentication',
                        403: 'provider_access',
                        429: 'provider_rate_limit',
                    }.get(reply.status_code, 'provider_request_failed')
                    raise ProviderError(
                        code,
                        status=reply.status_code,
                        uncertain=uncertain and reply.status_code >= 500,
                    )
                raw = bytearray()
                async for chunk in reply.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > response_limit:
                        raise ProviderError('provider_response_too_large', uncertain=uncertain)
            if binary:
                return bytes(raw)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except httpx.HTTPError:
            raise ProviderError('provider_unavailable', uncertain=uncertain) from None
        except (ValueError, UnicodeError):
            raise ProviderError('invalid_provider_record', uncertain=uncertain) from None

    async def thread_agent(self, session_id, thread_id):
        """Provider-authenticated thread identity for the application's role ceiling."""
        result = await self.request('GET', '/v1/sessions/' + identity(session_id)
                                    + '/threads/' + identity(thread_id))
        if (result.get('id') != thread_id or result.get('session_id') != session_id
                or not isinstance(result.get('agent'), dict)):
            raise ProviderError('invalid_provider_record')
        return result

    async def upload_skill(self, archive, display_name):
        return await self.request('POST', '/v1/skills', data={'display_name': display_name},
                                  files=[('files[]', ('hyprn.zip', archive, 'application/zip'))])

    async def skill_content(self, skill_id, version):
        if version == 'latest':
            raise ProviderError('exact_skill_version_required')
        return await self.request('GET', '/v1/skills/' + identity(skill_id) + '/versions/'
                                  + identity(version) + '/content', binary=True)

    async def create_session(self, settings, conversation_id):
        return await self.request(
            'POST',
            '/v1/sessions',
            body={
                'agent': {
                    'type': 'agent',
                    'id': settings.agent_id,
                    'version': settings.agent_version,
                },
                'environment_id': settings.environment_id,
                'title': 'HYPRN study',
                'metadata': {'hyprn_conversation_id': conversation_id},
            },
        )

    async def spending(self, session_id):
        """Provider list cost, including child agents; unknown is never zero."""
        result = await self.request('GET', '/v1/sessions/' + identity(session_id))
        usage = result.get('usage')
        cost = usage.get('list_cost') if isinstance(usage, dict) else None
        if (not isinstance(cost, dict) or cost.get('currency') != 'USD'
                or not isinstance(cost.get('amount'), str)
                or not re.fullmatch(r'[0-9]{1,12}', cost['amount'])):
            raise ProviderError('invalid_provider_record')
        return int(cost['amount'])

    async def session_account(self, session_id):
        result = await self.request('GET', '/v1/sessions/' + identity(session_id))
        usage = result.get('usage')
        cost = usage.get('list_cost') if isinstance(usage, dict) else None
        if (not isinstance(cost, dict) or cost.get('currency') != 'USD'
                or not isinstance(cost.get('amount'), str)
                or not re.fullmatch(r'[0-9]{1,12}', cost['amount'])
                or result.get('status') not in ('idle', 'running', 'rescheduling', 'terminated')):
            raise ProviderError('invalid_provider_record')
        return dict(spent_cents=int(cost['amount']), status=result['status'])

    async def remove_session_cap(self, session_id):
        """Remove a legacy cap once; reconcile uncertain delivery without resending."""
        path = '/v1/sessions/' + identity(session_id)
        current = await self.request('GET', path)
        if current.get('budget') is None:
            return
        try:
            await self.request('POST', path, body={'budget': None})
        except ProviderError as error:
            if not error.uncertain:
                raise
            observed = await self.request('GET', path)
            if observed.get('budget') is not None:
                raise

    async def ensure_tools(self, session_id, definitions):
        """Upgrade idle sessions in place. Preserve history, budget and multiagent policy."""
        path = '/v1/sessions/' + identity(session_id)
        current = await self.request('GET', path)
        # Preserve only the reviewed built-in research toolset during catalogue refresh.
        builtins = [item for item in current.get('agent', {}).get('tools', [])
                    if item.get('type') != 'custom']
        if builtins and readback_tools(builtins) != research_tools():
            raise ProviderError('provider_definition_drift')
        expected = custom_tools(definitions) + builtins
        if readback_tools(current.get('agent', {}).get('tools')) == readback_tools(expected):
            return
        if current.get('status') != 'idle':
            raise ProviderError('provider_session_busy')
        try:
            await self.request('POST', path, body={'agent': {'tools': expected}})
        except ProviderError as error:
            if not error.uncertain:
                raise
            # Reconcile a full-replacement setting; never repeat an uncertain mutation.
            observed = await self.request('GET', path)
            if readback_tools(observed.get('agent', {}).get('tools')) != readback_tools(expected):
                raise

    async def find_session(self, conversation_id):
        """Reconcile an uncertain creation by its private correlation, never its title."""
        page = None
        for _ in range(100):
            params = {'limit': 100}
            if page:
                params['page'] = page
            result = await self.request('GET', '/v1/sessions', params=params)
            found = [
                item
                for item in result.get('data', [])
                if item.get('metadata', {}).get('hyprn_conversation_id') == conversation_id
            ]
            if len(found) > 1:
                raise ProviderError('ambiguous_provider_record')
            if found:
                return found[0]
            page = result.get('next_page')
            if not page:
                return None
        raise ProviderError('provider_history_limit')

    async def events(self, session_id, since=None):
        path = '/v1/sessions/' + identity(session_id) + '/events'
        params = {'limit': 100, 'order': 'asc'}
        if since:
            params['created_at[gte]'] = since
        response_limit = MAX_RESPONSE
        received_count = 0
        # Only idempotent reads shrink/retry; one attachment has a separate hard cap.
        # Keep the exact page/cursor until the complete page has been accepted.
        for _ in range(800):
            try:
                result = await self.request('GET', path, params=params,
                                            response_limit=response_limit)
            except ProviderError as error:
                if error.code != 'provider_response_too_large':
                    raise
                if params['limit'] > 1:
                    params['limit'] = max(1, params['limit'] // 2)
                    continue
                if response_limit == MAX_RESPONSE:
                    response_limit = MAX_ATTACHMENT_RESPONSE
                    continue
                raise ProviderError('provider_attachment_too_large') from None
            events = result.get('data')
            if not isinstance(events, list) or len(events) > params['limit']:
                raise ProviderError('invalid_provider_record')
            received_count += len(events)
            if received_count > 10_000:
                raise ProviderError('provider_history_limit')
            for event in events:
                yield event
            page = result.get('next_page')
            if not page:
                return
            if page == params.get('page'):
                raise ProviderError('invalid_provider_record')
            params['page'] = page
            response_limit = MAX_RESPONSE
        raise ProviderError('provider_history_limit')

    async def send(self, session_id, event):
        return await self.request(
            'POST',
            '/v1/sessions/' + identity(session_id) + '/events',
            body={'events': [event]},
        )

    async def interrupt(self, session_id):
        return await self.send(session_id, {'type': 'user.interrupt'})

    async def tool_result(self, session_id, event_id, content, *, is_error=False):
        return await self.send(
            session_id,
            {
                'type': 'user.custom_tool_result',
                'custom_tool_use_id': identity(event_id),
                'content': [{'type': 'text', 'text': content}],
                'is_error': is_error,
            },
        )
