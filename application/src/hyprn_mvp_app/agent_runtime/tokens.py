"""Local tool tokens: minted only by the operator command, listed and revoked by the Owner.

No HTTP route mints a token. A token is returned once to the caller; only its SHA-256 is stored
(``Auth.mint_tool_token``). Listings carry metadata only, never a token or a hash.
"""

import os
import time

from ..contracts import DomainError
from ..store import agent_effects
from . import control, delegations, records
from .delegations import iso, person

DEFAULT_TTL_HOURS = 8
REVOKED = 'revoked'


def mint_local(
    store,
    auth,
    owner_username,
    study_id,
    *,
    ttl_hours=DEFAULT_TTL_HOURS,
    client_label='local',
    environ=None,
):
    """Delegate ``study_id`` to the local coding agent of ``owner_username`` and mint its tool
    token. Returns ``(token_id, token)``; the token is never stored, logged or printed here.

    Refused (403) while agent access is off for the installation. Renewal for the same study
    replaces the previous delegation, whose tokens are revoked."""
    if not control.agent_enabled(os.environ if environ is None else environ):
        raise DomainError('forbidden', 403)
    if isinstance(ttl_hours, bool) or not isinstance(ttl_hours, int) or not 1 <= ttl_hours <= 24:
        raise DomainError('invalid_request', 400)
    if not isinstance(client_label, str) or not 1 <= len(client_label) <= 128:
        raise DomainError('invalid_request', 400)
    with store.connection(write=True) as db:
        owner = records.user_by_name(db, owner_username)
        if owner is None:
            raise DomainError('resource_not_found', 404)
        delegation = delegations.issue_local(
            store, db, owner, study_id, expires_at=time.time() + ttl_hours * 60 * 60
        )
    try:
        minted = auth.mint_tool_token(
            delegation['delegation_id'], ttl_hours=ttl_hours, client_label=client_label
        )
    except BaseException:
        # A delegation without its token gives no access; end it rather than leave it live.
        auth.revoke_delegation(delegation['delegation_id'], REVOKED)
        raise
    return minted['token_id'], minted['token']


def describe(db, row):
    """The public metadata of one token row (``records.study_tokens``)."""
    return dict(
        token_id=row['token_id'],
        client_label=row['client_label'],
        created_at=iso(row['created_at']),
        expires_at=iso(row['expires_at']),
        revoked_at=iso(row['revoked_at']),
        effects=sorted(agent_effects(row['allowed_effects'])),
        agent=person(row['agent_actor_id'], row['agent_display_name']),
        delegator=person(
            row['delegator_actor_id'], records.user_name(db, row['delegator_actor_id'])
        ),
    )


def list_for_study(store, study_id):
    """Metadata of every tool token of ``study_id``, newest first (no authorization: the
    operator command and the Owner-only route authorize first)."""
    with store.connection() as db:
        return [describe(db, row) for row in records.study_tokens(db, study_id)]


def owner_list(store, actor, study_id):
    """Metadata of every tool token of ``study_id`` for the study Owner (writers and readers
    403, non-members the undisclosed 404), newest first."""
    with store.connection() as db:
        store.authorize(db, actor, study_id, owner=True)
        return [describe(db, row) for row in records.study_tokens(db, study_id)]


def revoke_in(store, db, study_id, token_id):
    """Revoke tool token ``token_id`` of ``study_id`` and end its delegation (reason
    ``revoked``) in the caller's transaction, so the agent's next call is refused. Unknown
    tokens and other studies' tokens are the undisclosed 404. Idempotent."""
    row = records.study_token(db, study_id, token_id)
    if row is None:
        raise DomainError('resource_not_found', 404)
    store.revoke_delegation(db, row['delegation_id'], REVOKED)
    return describe(db, records.study_token(db, study_id, token_id))


def revoke(store, study_id, token_id=None):
    """Revoke one tool token of ``study_id`` with its delegation, or, without ``token_id``,
    every live local delegation of the study with its tokens. Returns the revoked token ids."""
    with store.connection(write=True) as db:
        if token_id is not None:
            return [revoke_in(store, db, study_id, token_id)['token_id']]
        live = set(records.live_surface_delegations(db, study_id, delegations.LOCAL_SURFACE))
        for delegation_id in sorted(live):
            store.revoke_delegation(db, delegation_id, REVOKED)
        return sorted(
            row['token_id']
            for row in records.study_tokens(db, study_id)
            if row['delegation_id'] in live
        )
