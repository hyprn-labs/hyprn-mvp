"""Renewable provider reservations under the installation's single admission lock.

A reservation is not a study spending limit. Each turn can renew from unreserved
shared headroom. Count other active ceilings in full, including unknown delivery;
only confirmed idle, ended turns release unused headroom. Never erase usage.
"""
from dataclasses import replace

from .claude import ProviderError

# Small renewable headroom keeps room for concurrent studies. Cumulative usage is
# unrestricted up to the shared allowance, never a fixed lifetime per-study cap.
RESERVATION_CENTS = 100
RENEW_BELOW_CENTS = 25


async def prepare(store, provider, settings, current, turn, *, renewing=False):
    committed = settings.prior_cents
    own = 0
    own_cap = 0
    other_reservations = 0
    for row in map(dict, store.assistant_accounts()):
        is_current = row['study_id'] == current['study_id']
        provider_id = row['provider_id']
        if not provider_id and row['provision'] != 'new':
            found = await provider.find_session(row['conversation_id'])
            if not found:
                raise ProviderError('shared_allowance_unknown')
            provider_id = found['id']
        if not provider_id:
            # Admission and provisioning share the lock. A persisted reservation
            # with no provider intent has not yet authorized provider spending.
            continue
        account = await provider.session_account(provider_id)
        # Provider list cost rounds to the nearest cent. Round conservatively.
        spent = account['spent_cents'] + 1
        cap = account['cap_cents']
        if is_current:
            own, own_cap = spent, cap
            if not renewing and account['status'] != 'idle':
                raise ProviderError('provider_session_busy')
            continue
        active = bool(row['active_turn']) or account['status'] not in ('idle', 'terminated')
        if row['state'] == 'blocked' and row['active_turn']:
            # The provider ceiling still reserves the uncertain turn's headroom.
            active = True
        reserved = max(spent, cap) if active else spent
        committed += reserved
        other_reservations += max(0, reserved - spent)
    available = settings.total_cents - committed - own
    if (renewing and RENEW_BELOW_CENTS <= own_cap - own <= RESERVATION_CENTS
            and own_cap - own <= available):
        return replace(settings, session_cents=own_cap)
    if available <= 0:
        if other_reservations:
            raise ProviderError('shared_allowance_busy')
        raise ProviderError('shared_allowance_exhausted')
    cap = own + min(RESERVATION_CENTS, available)
    with store.connection(write=True) as db:
        db.execute('INSERT INTO assistant_allowances(turn_id,cap_cents) VALUES(?,?) '
                   'ON CONFLICT(turn_id) DO UPDATE SET cap_cents=excluded.cap_cents',
                   (turn['turn_id'], cap))
        db.execute('UPDATE assistant_conversations SET reserved_cents=? WHERE study_id=?',
                   (cap, current['study_id']))
    return replace(settings, session_cents=cap)
