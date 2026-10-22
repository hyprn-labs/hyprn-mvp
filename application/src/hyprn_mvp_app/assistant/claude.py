"""Claude Managed Agents wire adapter; no reasoning loop or scientific effects.

Only custom HYPRN tools are exposed. Requests never retry mutations automatically.
Callers own durable intent and reconcile unknown delivery against provider records.
The endpoint is fixed: a configured credential cannot be redirected to another host.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat

import httpx

API = 'https://api.anthropic.com'
BETA = 'managed-agents-2026-04-01'
MAX_RESPONSE = 8 * 1024 * 1024
IDENTITY = re.compile(r'[a-zA-Z0-9_-]{1,128}')


class ProviderError(Exception):
    """Safe, fixed diagnostic; provider bodies and request headers are never surfaced."""

    def __init__(self, code, *, uncertain=False, status=None):
        self.code, self.uncertain, self.status = code, uncertain, status
        super().__init__(code)


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
            )
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


def agent_definition(model, definitions, system):
    """The shared tool catalogue, without shell, network or MCP servers; children inherit only these tools."""
    return {
        'name': 'HYPRN study assistant',
        'model': model,
        'system': system,
        'multiagent': {
            'type': 'multiagent_20261001',
            'advisor': {'type': 'disabled'},
            'subagents': {'type': 'enabled', 'inline_agents': {'type': 'enabled'}},
            'workflows': {'type': 'disabled'},
        },
        'tools': custom_tools(definitions),
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

    async def request(self, method, path, *, body=None, params=None):
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
                method, path, json=body, params=params, headers=headers
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
                    if len(raw) > MAX_RESPONSE:
                        raise ProviderError('provider_response_too_large', uncertain=uncertain)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except httpx.HTTPError:
            raise ProviderError('provider_unavailable', uncertain=uncertain) from None
        except (ValueError, UnicodeError):
            raise ProviderError('invalid_provider_record', uncertain=uncertain) from None

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
                'budget': {
                    'type': 'limit',
                    'max_list_cost': {'amount': str(settings.session_cents), 'currency': 'USD'},
                },
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
        cost = result.get('usage', {}).get('list_cost')
        if (not isinstance(cost, dict) or cost.get('currency') != 'USD'
                or not isinstance(cost.get('amount'), str)
                or not re.fullmatch(r'[0-9]{1,12}', cost['amount'])
                or result.get('status') not in ('idle', 'running', 'rescheduling', 'terminated')):
            raise ProviderError('invalid_provider_record')
        return dict(spent_cents=int(cost['amount']), status=result['status'])

    async def ensure_allowance(self, session_id, cents):
        """Reconcile a durable absolute cap before a new message; never remove the budget."""
        path = '/v1/sessions/' + identity(session_id)
        expected = {'type': 'limit', 'max_list_cost': {'amount': str(cents), 'currency': 'USD'}}
        current = await self.request('GET', path)
        if current.get('budget') == expected:
            return
        if current.get('status') != 'idle':
            raise ProviderError('provider_session_busy')
        # A budget update can resume a paused turn. Such a turn requires explicit recovery,
        # not a new user message borrowing a different delegation.
        if (current.get('stop_reason') or {}).get('type') == 'budget_reached':
            raise ProviderError('provider_budget_reached')
        try:
            await self.request('POST', path, body={'budget': expected})
        except ProviderError as error:
            if not error.uncertain:
                raise
            observed = await self.request('GET', path)
            if observed.get('budget') != expected:
                raise

    async def ensure_tools(self, session_id, definitions):
        """Upgrade idle sessions in place. Preserve history, budget and multiagent policy."""
        path = '/v1/sessions/' + identity(session_id)
        expected = custom_tools(definitions)
        current = await self.request('GET', path)
        if current.get('agent', {}).get('tools') == expected:
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
            if observed.get('agent', {}).get('tools') != expected:
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
        for _ in range(100):
            result = await self.request('GET', path, params=params)
            for event in result.get('data', []):
                yield event
            page = result.get('next_page')
            if not page:
                return
            params['page'] = page
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
