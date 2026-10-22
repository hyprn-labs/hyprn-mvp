"""Pinned read-only reviewer authority, bounded independently of the provider prompt."""

import json
import time

from ..contracts import canonical, digest
from . import records
from .claude import ProviderError, identity

LIMITS = {'max_threads': 3, 'max_calls_per_thread': 24,
          'max_task_characters': 12000, 'max_result_characters': 16000}
ROLES = frozenset({'source-reviewer', 'model-reviewer', 'answer-reviewer'})


def configured(bindings, limits):
    if not isinstance(bindings, dict) or set(bindings) != ROLES or limits != LIMITS:
        raise ProviderError('reviewer_configuration_invalid')
    pins = {}
    for role, pin in bindings.items():
        if (not isinstance(pin, dict) or set(pin) != {'id', 'version'}
                or type(pin['version']) is not int or pin['version'] < 1):
            raise ProviderError('reviewer_configuration_invalid')
        key = (identity(pin['id']), pin['version'])
        if key in pins:
            raise ProviderError('reviewer_configuration_invalid')
        pins[key] = role
    return pins


async def admit(owner, study, turn, provider_id, event):
    thread_id = event.get('session_thread_id')
    if thread_id is None:
        return False
    identity(thread_id)
    try:
        tool = owner.runtime.registry.tool(event.get('name'))
    except KeyError:
        raise ProviderError('reviewer_tool_unavailable') from None
    if tool.effect != 'read':
        raise ProviderError('reviewer_write_forbidden')
    if len(canonical(event.get('input')).decode()) > LIMITS['max_task_characters']:
        raise ProviderError('reviewer_input_limit')
    marker = 'review_' + digest({'turn': turn['turn_id'], 'event': event['id']})
    with owner.store.connection() as db:
        rows = db.execute('SELECT payload FROM assistant_events WHERE study_id=? '
                          'AND event_type=? AND reference_id=? ORDER BY position',
                          (study, 'hyprn.reviewer_admitted', turn['turn_id'])).fetchall()
    admitted = [json.loads(row['payload']) for row in rows]
    prior = next((row for row in admitted if row['id'] == marker), None)
    same_thread = next((row for row in admitted if row['session_thread_id'] == thread_id), None)
    if same_thread:
        pin = same_thread['agent']
    else:
        remote = await owner.provider.thread_agent(provider_id, thread_id)
        pin = remote['agent']
    if type(pin.get('version')) is not int:
        raise ProviderError('reviewer_identity_unapproved')
    key = (identity(pin.get('id')), pin['version'])
    role = owner.reviewer_policy(study).get(key)
    if role is None:
        raise ProviderError('reviewer_identity_unapproved')
    if prior:
        return True
    if (sum(row['session_thread_id'] == thread_id for row in admitted) >= LIMITS['max_calls_per_thread']
            or (not same_thread and len({row['session_thread_id'] for row in admitted})
                >= LIMITS['max_threads'])):
        raise ProviderError('reviewer_call_limit')
    owner.authorize_turn(turn)
    with owner.store.connection(write=True) as db:
        records.save_event(db, study, dict(id=marker, type='hyprn.reviewer_admitted',
            turn_id=turn['turn_id'], session_thread_id=thread_id, agent=pin, role=role,
            _received_at=time.time()))
    return True
