"""Cumulative user spending, with no provider session ceilings or reservations.

Provider list cost includes child agents. Existing conversations retain their first
human billing owner even if study membership changes. A fresh read is required for
admission; active work is checked periodically. In-flight requests can overshoot.
"""
from .claude import ProviderError

USER_LIMIT_CENTS = 2000


async def account(store, provider, actor):
    spent = 0
    sessions = []
    for row in map(dict, store.assistant_user_accounts()):
        if row['actor_id'] != actor:
            continue
        provider_id = row['provider_id']
        if not provider_id and row['provision'] != 'new':
            found = await provider.find_session(row['conversation_id'])
            if not found:
                raise ProviderError('user_allowance_unknown')
            provider_id = found['id']
        if not provider_id:
            continue
        if provider_id in sessions:
            continue
        usage = await provider.session_account(provider_id)
        spent += usage['spent_cents']
        sessions.append(provider_id)
    return spent, sessions


def owner(store, study):
    row = next((r for r in store.assistant_user_accounts() if r['study_id'] == study), None)
    if not row or not row['actor_id']:
        raise ProviderError('user_allowance_unknown')
    return row['actor_id']


def limit(actor, settings=None):
    """Explicit operator overrides change the ceiling, never recorded spending."""
    return settings.user_limits_cents.get(actor, USER_LIMIT_CENTS) if settings else USER_LIMIT_CENTS


async def check(store, provider, actor, settings=None):
    spent, sessions = await account(store, provider, actor)
    if spent >= limit(actor, settings):
        raise ProviderError('user_allowance_exhausted')
    return spent, sessions
