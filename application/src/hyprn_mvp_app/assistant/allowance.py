"""Shared allowance admission, independent of scientific execution and reasoning.

One provider turn at a time may draw the remaining allowance. Child agents share that
turn's provider cap. Before transferring headroom, read every existing session afresh;
unknown creation, non-idleness or unavailable usage fails closed. Never erase usage.
"""
from dataclasses import replace

from .claude import ProviderError


async def prepare(store, provider, settings, current, turn):
    rows = [dict(r) for r in store.assistant_accounts()]
    spent = settings.prior_cents
    own = 0
    for row in rows:
        if (row['study_id'] != current['study_id'] and row['active_turn']
                and row['state'] == 'blocked'):
            raise ProviderError('shared_allowance_unknown')
        provider_id = row['provider_id']
        if not provider_id and row['provision'] != 'new':
            found = await provider.find_session(row['conversation_id'])
            if not found:
                raise ProviderError('shared_allowance_unknown')
            provider_id = found['id']
        if not provider_id:
            continue
        state = await provider.session_account(provider_id)
        if row['study_id'] != current['study_id']:
            if state['status'] not in ('idle', 'terminated'):
                raise ProviderError('shared_allowance_busy')
        elif state['status'] != 'idle':
            raise ProviderError('provider_session_busy')
        spent += state['spent_cents']
        if row['study_id'] == current['study_id']:
            own = state['spent_cents']
    remaining = settings.total_cents - spent
    if remaining <= 0:
        raise ProviderError('shared_allowance_exhausted')
    cap = own + remaining
    with store.connection(write=True) as db:
        db.execute('INSERT INTO assistant_allowances(turn_id,cap_cents) VALUES(?,?) '
                   'ON CONFLICT(turn_id) DO UPDATE SET cap_cents=excluded.cap_cents',
                   (turn['turn_id'], cap))
        db.execute('UPDATE assistant_conversations SET reserved_cents=? WHERE study_id=?',
                   (cap, current['study_id']))
    return replace(settings, session_cents=cap)
