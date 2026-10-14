"""Who wrote what: the attribution index read for people, cross-checked against the receipts.

An entry is a projection of an owner's receipt; it is never used for authorization or writes.
Every entry returned is checked against its receipt (scope, category, command id) and withheld
when the receipt's actor is not the entry's agent or the agent does not act for the entry's
delegating user. A study an agent created is checked against the agent's pre-study receipt
(category ``study_create``) and shown only to current members of that study.
"""

import base64
import binascii
from datetime import datetime, timezone
import json

from ..contracts import DomainError
from . import records
from .schema import RECORD_KINDS

STUDY_CREATE = 'study_create'
MAX_CURSOR = 512
MAX_TEXT = 4096


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def _text(value, maximum=MAX_TEXT, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise DomainError('invalid_request', 400)
    return value


def record(db, entry):
    """Add one attribution entry in the caller's transaction (idempotent by its key).

    ``entry`` names ``study_id``, ``record_kind``, ``record_id``, optional ``version_id``,
    ``command_category``, ``command_id``, ``agent_actor_id``, ``agent_display_name`` and
    ``delegator_actor_id``; ``recorded_at`` defaults to now."""
    if entry.get('record_kind') not in RECORD_KINDS:
        raise DomainError('invalid_request', 400)
    if entry['record_kind'] == 'study' and (
        entry.get('command_category') != STUDY_CREATE
        or entry.get('record_id') != entry.get('study_id')
    ):
        raise DomainError('invalid_request', 400)
    row = {
        'study_id': _text(entry.get('study_id')),
        'record_kind': entry['record_kind'],
        'record_id': _text(entry.get('record_id')),
        'version_id': _text(entry.get('version_id'), optional=True),
        'command_category': _text(entry.get('command_category'), 64),
        'command_id': _text(entry.get('command_id')),
        'agent_actor_id': _text(entry.get('agent_actor_id')),
        'agent_display_name': _text(entry.get('agent_display_name'), 128),
        'delegator_actor_id': _text(entry.get('delegator_actor_id')),
        'recorded_at': _text(entry.get('recorded_at') or now(), 64),
    }
    records.insert_attribution(db, row)
    return row


def encode_cursor(row):
    raw = json.dumps([row[column] for column in records.ATTRIBUTION_ORDER], separators=(',', ':'))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')


def decode_cursor(cursor):
    """The entry key of an opaque cursor; anything else is ``invalid_request`` 400."""
    if not isinstance(cursor, str) or not 1 <= len(cursor) <= MAX_CURSOR:
        raise DomainError('invalid_request', 400)
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)).decode())
    except (ValueError, UnicodeError, binascii.Error):
        raise DomainError('invalid_request', 400) from None
    if (
        not isinstance(key, list)
        or len(key) != len(records.ATTRIBUTION_ORDER)
        or not all(isinstance(part, str) for part in key)
    ):
        raise DomainError('invalid_request', 400)
    return key


def consistent(store, db, row):
    """Whether entry ``row`` agrees with its receipt and its agent's delegating user."""
    agent = store.agent_actor(db, row['agent_actor_id'])
    if agent is None or agent['delegator_actor_id'] != row['delegator_actor_id']:
        return False
    if row['record_kind'] == 'study':
        receipt = store.command_receipt(
            db, 'actor:' + row['agent_actor_id'], STUDY_CREATE, row['command_id']
        )
        result = receipt['result'] if receipt else None
        if not isinstance(result, dict) or result.get('study_id') != row['study_id']:
            return False
    else:
        receipt = store.command_receipt(
            db, row['study_id'], row['command_category'], row['command_id']
        )
    return (
        receipt is not None
        and receipt['state'] != 'rejected'
        and receipt['actor_id'] == row['agent_actor_id']
    )


def public(db, row):
    return dict(
        study_id=row['study_id'],
        record_kind=row['record_kind'],
        record_id=row['record_id'],
        version_id=row['version_id'],
        command_category=row['command_category'],
        command_id=row['command_id'],
        agent=dict(actor_id=row['agent_actor_id'], display_name=row['agent_display_name']),
        delegator=dict(
            actor_id=row['delegator_actor_id'],
            display_name=records.user_name(db, row['delegator_actor_id']),
        ),
        recorded_at=row['recorded_at'],
    )


def _limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise DomainError('invalid_request', 400)
    return limit


def _collect(store, db, rows, limit, admitted=lambda row: True):
    shown = []
    for row in rows:
        if admitted(row) and consistent(store, db, row):
            shown.append(row)
            if len(shown) > limit:
                break
    more = len(shown) > limit
    shown = shown[:limit]
    return dict(
        items=[public(db, row) for row in shown],
        next_cursor=encode_cursor(shown[-1]) if more else None,
    )


def page(store, actor, study_id, cursor, limit):
    """One page of the attribution entries of ``study_id`` for a member, newest first."""
    limit = _limit(limit)
    after = decode_cursor(cursor) if cursor is not None else None
    with store.connection() as db:
        store.authorize(db, actor, study_id)
        return _collect(store, db, records.study_attribution(db, study_id, after), limit)


def created_studies(store, actor, cursor, limit):
    """One page of the studies an agent created that ``actor`` is a current member of."""
    limit = _limit(limit)
    after = decode_cursor(cursor) if cursor is not None else None

    with store.connection() as db:

        def member(row):
            try:
                store.authorize(db, actor, row['study_id'])
            except DomainError:
                return False
            return True

        rows = records.created_study_attribution(db, after)
        return _collect(store, db, rows, limit, member)
