"""Application-owned conversation projection and delivery intents, never scientific records."""

import json
import time

from ..contracts import DomainError, uid
from ..identity import display_name


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
        columns = {row['name'] for row in db.execute('PRAGMA table_info(assistant_turns)')}
        if 'author_display_name' not in columns:
            db.execute('ALTER TABLE assistant_turns ADD COLUMN author_display_name TEXT')


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
        for event in reversed(events(db, current['study_id'])):
            if event.get('type') == 'user.message':
                break
            if event.get('type') == 'session.error':
                if event.get('error', {}).get('type') == 'billing_error':
                    return 'provider_billing_error'
                break
    return code


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
                'INSERT INTO assistant_conversations VALUES(?,?,?,?,?,?,?,?,?)',
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
        db.execute(
            "UPDATE assistant_conversations SET active_turn=?,state='queued',error=NULL "
            'WHERE study_id=?',
            (command, study),
        )


def update(db, study, **values):
    allowed = {'provider_id', 'provision', 'active_turn', 'state', 'error'}
    if not values or not values.keys() <= allowed:
        raise ValueError('Unknown conversation field')
    assignments = ','.join(key + '=?' for key in values)
    db.execute(
        'UPDATE assistant_conversations SET ' + assignments + ' WHERE study_id=?',
        (*values.values(), study),
    )


def save_event(db, study, event):
    db.execute(
        'INSERT INTO assistant_events(study_id,event_id,payload) VALUES(?,?,?) ON CONFLICT DO NOTHING',
        (study, event['id'], json.dumps(event, ensure_ascii=False, allow_nan=False)),
    )


def events(db, study):
    return [
        json.loads(value[0])
        for value in db.execute(
            'SELECT payload FROM assistant_events WHERE study_id=? ORDER BY position', (study,)
        )
    ]


def public(store, actor, study, *, available):
    """Study-authorized read; no provider identities, credentials, raw tool inputs or thinking."""
    with store.connection() as db:
        store.authorize(db, actor, study)
        current = row(db, study)
        messages = [
            dict(
                message_id=r['turn_id'],
                role='user',
                text=r['text'],
                actor_id=r['actor_id'],
                author_display_name=r['author_display_name'] or display_name(
                    db, r['actor_id'], legacy=True),
                created_at=r['created_at'],
            )
            for r in db.execute(
                'SELECT * FROM assistant_turns WHERE study_id=? ORDER BY created_at', (study,)
            )
        ]
        for event in events(db, study):
            if event.get('type') == 'agent.message' and not event.get('session_thread_id'):
                text = '\n'.join(
                    item['text']
                    for item in event.get('content', [])
                    if item.get('type') == 'text' and isinstance(item.get('text'), str)
                )
                if text:
                    messages.append(
                        dict(
                            message_id=event['id'],
                            role='assistant',
                            text=text[:65536],
                            actor_id=None,
                            author_display_name=None,
                            created_at=event['_received_at'],
                        )
                    )
        messages.sort(key=lambda item: item['created_at'])
        return dict(
            state=(current['state'] if current else 'idle') if available else 'unavailable',
            error=failure(db, current),
            can_send=bool(available and may_send(db, current)),
            can_stop=bool(current and current['active_turn']),
            messages=messages[-200:],
            has_earlier_messages=len(messages) > 200,
        )
