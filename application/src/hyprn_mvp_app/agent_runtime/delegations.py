"""Delegated Assistant authority and the agent access state of a study.

Only a human's current study permissions can establish a delegation. Agent writes
remain attributed to their agent actor and bounded by that human's authority.
"""

import time

from ..contracts import DomainError
from . import records

# Effects admitted by the delegating human's role ceiling.
ROLE_EFFECTS = {
    'writer': frozenset({'read', 'draft', 'record', 'submit', 'outside_study'}),
    'reader': frozenset({'read', 'outside_study'}),
}


def iso(epoch):
    """An epoch time as an RFC 3339 UTC date-time with microseconds; ``None`` stays ``None``."""
    if epoch is None:
        return None
    seconds = int(epoch)
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(seconds))
    return f'{stamp}.{int(round((epoch - seconds) * 1_000_000)) % 1_000_000:06d}Z'


def person(actor_id, display_name):
    """The public reference to an actor: its id and display name, two separate fields."""
    return dict(actor_id=actor_id, display_name=display_name)


def ceiling_for(store, db, actor_id, study_id):
    """The role ceiling the user's current study role admits: ``writer`` for an Owner or a
    writer, ``reader`` for a reader; a non-member is the undisclosed 404."""
    store.authorize(db, actor_id, study_id)
    try:
        store.authorize(db, actor_id, study_id, write=True)
    except DomainError as error:
        if error.status != 403:
            raise
        return 'reader'
    return 'writer'


def _admitted(store, db, delegation):
    """Whether the delegating user's current role still admits the delegation's ceiling."""
    try:
        store.authorize(
            db,
            delegation['delegator_actor_id'],
            delegation['study_id'],
            write=delegation['role_ceiling'] == 'writer',
        )
    except DomainError:
        return False
    return True


def _state(store, db, delegation, now):
    if delegation['revoked_at'] is not None:
        return 'ended', 'revoked', delegation['revoked_at']
    if delegation['expires_at'] <= now:
        return 'ended', 'expired', delegation['expires_at']
    if not _admitted(store, db, delegation):
        # The membership change itself carries no time, so none is claimed.
        return 'ended', 'membership_changed', None
    return 'active', 'none', None


def access(store, actor, study_id, *, enabled, now=None):
    """The agent access state of ``study_id`` for a member: whether agent access is on for the
    installation and, for each agent delegated this study, the state of its latest delegation
    (``active``, or ``ended`` with ``revoked``, ``expired`` or ``membership_changed``)."""
    now = time.time() if now is None else now
    with store.connection() as db:
        store.authorize(db, actor, study_id)
        latest = {}
        for delegation in records.study_delegations(db, study_id):
            latest.setdefault(delegation['agent_actor_id'], delegation)
        agents = []
        for delegation in latest.values():
            state, reason, ended_at = _state(store, db, delegation, now)
            delegator = delegation['delegator_actor_id']
            agents.append(
                dict(
                    agent=person(delegation['agent_actor_id'], delegation['agent_display_name']),
                    delegator=person(delegator, records.user_name(db, delegator)),
                    state=state,
                    reason=reason,
                    expires_at=iso(delegation['expires_at']),
                    ended_at=iso(ended_at),
                )
            )
        return dict(installation_enabled=bool(enabled), agents=agents)
