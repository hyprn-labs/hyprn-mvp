"""Application-owned conversation projection and delivery intents, never scientific records."""

import json
import hashlib
import time
from uuid import UUID

from ..contracts import DomainError, uid
from ..identity import display_name
from .provider_sessions import SQLITE_SCHEMA


def ensure(store):
    if store.verify_schema():
        return
    with store.connection(write=True) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS assistant_conversations (
            study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
            conversation_id TEXT NOT NULL UNIQUE,
            provider_id TEXT,
            provision TEXT NOT NULL,
            reserved_cents INTEGER NOT NULL,
            active_turn TEXT,
            state TEXT NOT NULL,
            error TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assistant_turns (
            turn_id TEXT PRIMARY KEY,
            study_id TEXT NOT NULL REFERENCES studies(study_id),
            actor_id TEXT NOT NULL,
            text TEXT NOT NULL,
            runtime_session TEXT,
            delivery TEXT NOT NULL,
            provider_event TEXT,
            stopped INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assistant_allowances (
            turn_id TEXT PRIMARY KEY REFERENCES assistant_turns(turn_id),
            cap_cents INTEGER NOT NULL CHECK(cap_cents > 0)
        );
        CREATE TABLE IF NOT EXISTS assistant_events (
            study_id TEXT NOT NULL REFERENCES studies(study_id),
            event_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            position INTEGER PRIMARY KEY AUTOINCREMENT,
            UNIQUE(study_id,event_id)
        );
        CREATE TABLE IF NOT EXISTS assistant_tool_results (
            study_id TEXT NOT NULL REFERENCES studies(study_id),
            event_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            content TEXT,
            is_error INTEGER NOT NULL DEFAULT 0,
            delivery TEXT NOT NULL,
            PRIMARY KEY(study_id,event_id)
        );
        """)
        db.executescript(SQLITE_SCHEMA)
        columns = {row['name'] for row in db.execute('PRAGMA table_info(assistant_turns)')}
        if 'author_display_name' not in columns:
            db.execute('ALTER TABLE assistant_turns ADD COLUMN author_display_name TEXT')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(assistant_conversations)')}
        if 'provider_cursor' not in columns:
            db.execute('ALTER TABLE assistant_conversations ADD COLUMN provider_cursor TEXT')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(assistant_events)')}
        upgrade = 'event_type' not in columns
        if upgrade:
            for name in ('event_type', 'processed_at', 'reference_id'):
                db.execute('ALTER TABLE assistant_events ADD COLUMN ' + name + ' TEXT')
        db.executescript('''
        CREATE INDEX IF NOT EXISTS assistant_events_study_position
          ON assistant_events(study_id,position);
        CREATE INDEX IF NOT EXISTS assistant_events_study_type_position
          ON assistant_events(study_id,event_type,position);
        CREATE INDEX IF NOT EXISTS assistant_events_study_reference
          ON assistant_events(study_id,reference_id,event_type);
        CREATE TABLE IF NOT EXISTS assistant_public_messages (
          position INTEGER PRIMARY KEY AUTOINCREMENT,
          study_id TEXT NOT NULL REFERENCES studies(study_id),
          message_id TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
          text TEXT NOT NULL, actor_id TEXT, author_display_name TEXT,
          created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS assistant_public_messages_study_position
          ON assistant_public_messages(study_id,position);
        ''')
        if upgrade:
            projected = []
            for value in db.execute('SELECT study_id,event_id,payload FROM assistant_events'):
                event = json.loads(value['payload'])
                kind, stamp, reference = event_metadata(event)
                db.execute('UPDATE assistant_events SET event_type=?,processed_at=?,reference_id=? '
                    'WHERE study_id=? AND event_id=?',
                    (kind, stamp, reference, value['study_id'], value['event_id']))
                message = public_event(value['study_id'], event)
                if message:
                    projected.append((value['study_id'], message))
            for value in db.execute('SELECT * FROM assistant_turns'):
                projected.append((value['study_id'], public_turn(db, value)))
            for study, message in sorted(projected, key=lambda pair: (
                    pair[1]['created_at'], pair[1]['message_id'])):
                save_public(db, study, message)
            db.execute('UPDATE assistant_conversations SET provider_cursor=(SELECT max(processed_at) '
                'FROM assistant_events WHERE study_id=assistant_conversations.study_id)')


def row(db, study):
    value = db.execute(
        'SELECT * FROM assistant_conversations WHERE study_id=?', (study,)
    ).fetchone()
    return dict(value) if value else None


def turn(db, turn_id):
    value = db.execute('SELECT * FROM assistant_turns WHERE turn_id=?', (turn_id,)).fetchone()
    return dict(value) if value else None


def failure(db, current):
    """Project a safe actionable cause from a completed provider failure, never raw text."""
    if not current:
        return None
    code = current['error']
    if code == 'provider_retries_exhausted' and not current['active_turn']:
        event = latest_event(db, current['study_id'], ('user.message', 'session.error'))
        if event and event.get('error', {}).get('type') == 'billing_error':
            return 'provider_billing_error'
    return code


RECOVERABLE = frozenset({'assistant_internal_error', 'provider_unavailable',
    'provider_rate_limit', 'turn_time_limit', 'invalid_provider_record',
    'user_allowance_unknown', 'shared_allowance_unknown', 'provider_session_busy',
    'session_delivery_unknown'})


def may_resume(db, current, actor):
    if not current or current['state'] != 'blocked' or current['error'] not in RECOVERABLE:
        return False
    active = turn(db, current['active_turn']) if current['active_turn'] else None
    return bool(active and active['actor_id'] == actor and not active['stopped']
                and (active['delivery'] == 'accepted' or
                     (active['delivery'] == 'new' and not active['runtime_session'])))


def may_send(db, current):
    # A confirmed ended billing failure may receive a fresh human request after funding.
    # This never resumes or repeats the failed turn, nor admits uncertain active work.
    return not current or (not current['active_turn'] and (
        current['state'] == 'idle' or failure(db, current) == 'provider_billing_error'))


def accept(store, actor, study, command, text, settings):
    """Admit a durable turn; provider allowance is reconciled before dispatch."""
    with store.connection(write=True) as db:
        store.authorize(db, actor, study)
        prior = turn(db, command)
        if prior:
            if prior['study_id'] != study or prior['actor_id'] != actor or prior['text'] != text:
                raise DomainError('conflict', 409)
            return
        current = row(db, study)
        if not may_send(db, current):
            raise DomainError('conflict', 409)
        if not current:
            db.execute(
                'INSERT INTO assistant_conversations(study_id,conversation_id,provider_id,provision,'
                'reserved_cents,active_turn,state,error,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                (
                    study,
                    uid(),
                    None,
                    'new',
                    0,
                    None,
                    'idle',
                    None,
                    time.time(),
                ),
            )
        db.execute(
            'INSERT INTO assistant_turns VALUES(?,?,?,?,?,?,?,?,?,?)',
            (command, study, actor, text, None, 'new', None, 0, time.time(), display_name(db, actor)),
        )
        save_public(db, study, public_turn(db, turn(db, command)))
        db.execute(
            "UPDATE assistant_conversations SET active_turn=?,state='queued',error=NULL "
            'WHERE study_id=?',
            (command, study),
        )


def update(db, study, **values):
    allowed = {'provider_id', 'provision', 'active_turn', 'state', 'error', 'provider_cursor'}
    if not values or not values.keys() <= allowed:
        raise ValueError('Unknown conversation field')
    assignments = ','.join(key + '=?' for key in values)
    db.execute(
        'UPDATE assistant_conversations SET ' + assignments + ' WHERE study_id=?',
        (*values.values(), study),
    )


def event_metadata(event):
    kind = event.get('type', '')
    # Provider filtering is by creation time, not processing time.
    stamp = event.get('created_at') or event.get('processed_at')
    reference = None
    if kind == 'user.custom_tool_result':
        reference = event.get('custom_tool_use_id')
    elif kind == 'agent.tool_result':
        reference = event.get('tool_use_id')
    elif kind in ('hyprn.turn_started', 'hyprn.turn_resumed', 'hyprn.reviewer_admitted'):
        reference = event.get('turn_id') or event['id'].removeprefix('turn_started_')
    elif kind == 'user.message':
        prefix = 'HYPRN request reference: '
        for item in event.get('content', []):
            if item.get('type') == 'text' and str(item.get('text', '')).startswith(prefix):
                reference = item['text'][len(prefix):]
    return kind, stamp, reference


def public_turn(db, value):
    return dict(message_id=value['turn_id'], role='user', text=value['text'],
        actor_id=value['actor_id'], author_display_name=value['author_display_name'] or
        display_name(db, value['actor_id'], legacy=True), created_at=value['created_at'])


def public_event(study, event):
    if event.get('type') != 'agent.message' or event.get('session_thread_id'):
        return None
    text = '\n'.join(item['text'] for item in event.get('content', [])
        if item.get('type') == 'text' and isinstance(item.get('text'), str))
    if not text:
        return None
    message_id = str(UUID(hashlib.sha256((study + ':' + event['id']).encode()).hexdigest()[:32]))
    return dict(message_id=message_id, role='assistant', text=text[:65536],
        actor_id=None, author_display_name=None, created_at=event['_received_at'])


def save_public(db, study, message):
    db.execute('INSERT INTO assistant_public_messages(study_id,message_id,role,text,actor_id,'
        'author_display_name,created_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT DO NOTHING',
        (study, *(message[k] for k in ('message_id', 'role', 'text', 'actor_id',
                                     'author_display_name', 'created_at'))))


def save_event(db, study, event):
    kind, stamp, reference = event_metadata(event)
    accepted = db.execute(
        'INSERT INTO assistant_events(study_id,event_id,payload,event_type,processed_at,reference_id) '
        'VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING',
        (study, event['id'], json.dumps(event, ensure_ascii=False, allow_nan=False),
         kind, stamp, reference),
    ).rowcount
    if accepted:
        message = public_event(study, event)
        if message:
            save_public(db, study, message)
        if stamp:
            db.execute('UPDATE assistant_conversations SET provider_cursor=? WHERE study_id=? '
                'AND (provider_cursor IS NULL OR provider_cursor<?)', (stamp, study, stamp))
    return bool(accepted)


def event(db, study, event_id):
    value = db.execute('SELECT payload FROM assistant_events WHERE study_id=? AND event_id=?',
                       (study, event_id)).fetchone()
    return json.loads(value[0]) if value else None


def latest_event(db, study, kinds, *, reference=None, after=0):
    marks = ','.join('?' for _ in kinds)
    suffix = ' AND reference_id=?' if reference else ''
    args = (study, *kinds, after, *((reference,) if reference else ()))
    value = db.execute('SELECT payload FROM assistant_events WHERE study_id=? '
        'AND event_type IN (' + marks + ') AND position>?' + suffix +
        ' ORDER BY position DESC LIMIT 1', args).fetchone()
    return json.loads(value[0]) if value else None


def pending_events(db, study, provider_event):
    start = db.execute('SELECT position FROM assistant_events WHERE study_id=? AND event_id=?',
                       (study, provider_event)).fetchone()
    if not start:
        return [], None
    pending = [json.loads(value[0]) for value in db.execute(
        'SELECT e.payload FROM assistant_events e LEFT JOIN assistant_tool_results t '
        'ON t.study_id=e.study_id AND t.event_id=e.event_id '
        "WHERE e.study_id=? AND e.event_type='agent.custom_tool_use' AND e.position>? "
        "AND (t.delivery IS NULL OR t.delivery<>'accepted') ORDER BY e.position LIMIT 100",
        (study, start[0]))]
    status = latest_event(db, study, ('session.status_idle', 'session.status_running'), after=start[0])
    return pending, status


def events(db, study):
    return [
        json.loads(value[0])
        for value in db.execute(
            'SELECT payload FROM assistant_events WHERE study_id=? ORDER BY position', (study,)
        )
    ]


def public(store, actor, study, *, available, after=None, before=None):
    """Study-authorized read; no provider identities, credentials, raw tool inputs or thinking."""
    with store.connection() as db:
        store.authorize(db, actor, study)
        current = row(db, study)
        if after is not None and before is not None:
            raise DomainError('invalid_request', 400)
        cursor = after if after is not None else before
        position = None
        if cursor is not None:
            found = db.execute('SELECT position FROM assistant_public_messages '
                'WHERE study_id=? AND message_id=?', (study, cursor)).fetchone()
            if not found:
                raise DomainError('invalid_request', 400)
            position = found[0]
        condition = (' AND position>?' if after is not None else ' AND position<?') if cursor else ''
        values = (study, position) if cursor else (study,)
        direction = 'ASC' if after is not None else 'DESC'
        selected = [dict(r) for r in db.execute('SELECT * FROM assistant_public_messages '
            'WHERE study_id=?' + condition + ' ORDER BY position ' + direction + ' LIMIT 201', values)]
        extra = len(selected) > 200
        selected = selected[:200]
        if after is None:
            selected.reverse()
        earlier = bool(selected and db.execute('SELECT 1 FROM assistant_public_messages '
            'WHERE study_id=? AND position<? LIMIT 1', (study, selected[0]['position'])).fetchone())
        messages = [{k: v for k, v in r.items() if k not in ('study_id', 'position')} for r in selected]
        return dict(
            state=(current['state'] if current else 'idle') if available else 'unavailable',
            error=failure(db, current),
            can_send=bool(available and may_send(db, current)),
            can_stop=bool(current and current['active_turn']),
            can_resume=bool(available and may_resume(db, current, actor)),
            messages=messages,
            has_earlier_messages=earlier,
            next_cursor=messages[-1]['message_id'] if messages else after,
            earlier_cursor=messages[0]['message_id'] if messages else before,
            has_more_messages=extra if after is not None else False,
        )
