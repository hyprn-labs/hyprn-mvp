"""Runtime-owned tables of the agent records, created idempotently: the attribution index, the
agent sessions and the append-only action journal.

``ensure(store)`` runs this module's DDL on a connection of the one ``Store`` (its single
writer), called by the composition root until the store's own initialization runs the
registered schemas; ``store`` never imports this package. Every statement is ``IF NOT EXISTS``,
so a repeated call changes nothing.
"""

from .limits import RESULT_CAP_BYTES

RECORD_KINDS = (
    'study',
    'study_context',
    'evidence_version',
    'model_draft',
    'model_version',
    'approach_draft',
    'approach_version',
    'configuration_version',
    'run',
    'brief_draft',
    'brief_version',
    'answer_version',
    'answer_draft',
    'computational_record',
    'exploration_request',
    'exploration_design',
    'exploration_view',
    'exploration_sample',
    'exploration_surrogate',
    'calculation_version',
    'reference_mark',
    'calculation_sample',
    'calculation_estimate',
    'model_explanation_draft',
    'model_explanation_version',
)

_KINDS = ','.join(f"'{kind}'" for kind in RECORD_KINDS)

# Attribution index: which agent, for which delegating user, wrote which record through which
# command. It is a projection of the owners' receipts, cross-checked against the receipt actor
# on every read, and never used for authorization or writes. No column names a confirmer:
# agent writes are direct. A study an agent created carries the new study's id as ``study_id``
# and ``record_id`` with the category ``study_create``. Entries are never deleted.
_ATTRIBUTION_TABLE = f"""CREATE TABLE IF NOT EXISTS agent_attribution(
 study_id TEXT NOT NULL,
 record_kind TEXT NOT NULL CHECK(record_kind IN ({_KINDS})),
 record_id TEXT NOT NULL, version_id TEXT,
 command_category TEXT NOT NULL, command_id TEXT NOT NULL,
 agent_actor_id TEXT NOT NULL, agent_display_name TEXT NOT NULL,
 delegator_actor_id TEXT NOT NULL, recorded_at TEXT NOT NULL, delegator_display_name TEXT,
 PRIMARY KEY(study_id,command_category,command_id,record_kind,record_id)
)"""
_ATTRIBUTION_TRIGGER = """CREATE TRIGGER IF NOT EXISTS agent_attribution_no_delete
 BEFORE DELETE ON agent_attribution
 BEGIN SELECT RAISE(ABORT,'agent attribution is never deleted'); END"""
DDL = _ATTRIBUTION_TABLE + ';\n' + _ATTRIBUTION_TRIGGER + ';\n'


SURFACES = ('claude_managed', 'openai_agents')
SESSION_STATES = ('active', 'ended', 'access_lost')
ACTION_STATES = ('intended', 'completed', 'refused', 'reconciling', 'uncertain', 'failed')
# Effects a journaled call may carry (``NULL`` for a name the registry does not know).
ACTION_EFFECTS = ('read', 'draft', 'record', 'submit', 'outside_study')
# What a call returned to the agent: ``ok`` or the category of its error envelope.
OUTCOME_CLASSES = (
    'ok',
    'invalid_input',
    'too_large',
    'unsupported',
    'guard_blocked',
    'conflict',
    'not_ready',
    'not_found',
    'access_lost',
    'session_expired',
    'budget_exhausted',
    'busy',
    'pending',
    'uncertain',
    'unavailable',
    'internal',
)


def _closed(values):
    return ','.join(f"'{value}'" for value in values)


# Fixed at opening: everything but the state, its end time and the two counters.
_SESSION_FIXED = (
    'session_id',
    'delegation_id',
    'surface',
    'client_name',
    'client_version',
    'agent_display_name',
    'registry_version',
    'playbook_sha256',
    'tool_definitions_sha256',
    'started_at',
)
# Written once, when the call is journaled as intended (or refused at admission).
ACTION_INTENDED = (
    'action_id',
    'session_id',
    'delegation_id',
    'study_id',
    'call_id',
    'tool',
    'effect',
    'args_sha256',
    'command_ids',
    'created_at',
)


def _changed(columns):
    return ' OR '.join(f'NEW.{column} IS NOT OLD.{column}' for column in columns)


# Agent sessions: one active session per delegation. The delegated API
# session's cookie and cross-site request values are never columns: they live only in the
# runtime's memory. The identity of a session never changes; its state only leaves ``active``
# and its counters only grow. Sessions are never deleted.
#
# The action journal: one row per tool call, keyed by (session, surface call id). It keeps the
# argument digest, never the arguments; the reason message is HYPRN MVP text from the closed
# reason list, never client or agent text. The intended columns never change, a row is inserted
# only as ``intended`` (or ``refused`` at admission), its state only moves out of ``intended``
# or ``reconciling`` and never back to ``intended``, and rows are never deleted.
RUNTIME_DDL = f"""
CREATE TABLE IF NOT EXISTS agent_sessions(
 session_id TEXT PRIMARY KEY,
 delegation_id TEXT NOT NULL REFERENCES agent_delegations(delegation_id),
 surface TEXT NOT NULL CHECK(surface IN ({_closed(SURFACES)})),
 client_name TEXT CHECK(client_name IS NULL OR length(client_name) BETWEEN 1 AND 64),
 client_version TEXT CHECK(client_version IS NULL OR length(client_version) BETWEEN 1 AND 64),
 agent_display_name TEXT NOT NULL, registry_version TEXT NOT NULL,
 playbook_sha256 TEXT NOT NULL, tool_definitions_sha256 TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ({_closed(SESSION_STATES)})),
 api_calls INTEGER NOT NULL DEFAULT 0 CHECK(api_calls>=0),
 runs_submitted INTEGER NOT NULL DEFAULT 0 CHECK(runs_submitted>=0),
 started_at TEXT NOT NULL, ended_at TEXT,
 CHECK((state='active')=(ended_at IS NULL))
);
CREATE TRIGGER IF NOT EXISTS agent_sessions_no_delete BEFORE DELETE ON agent_sessions
 BEGIN SELECT RAISE(ABORT,'agent sessions are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS agent_sessions_fixed BEFORE UPDATE ON agent_sessions
 WHEN {_changed(_SESSION_FIXED)}
  OR (OLD.state<>'active' AND (NEW.state IS NOT OLD.state OR NEW.ended_at IS NOT OLD.ended_at))
  OR NEW.api_calls<OLD.api_calls OR NEW.runs_submitted<OLD.runs_submitted
 BEGIN SELECT RAISE(ABORT,'an agent session only ends and only counts up'); END;
CREATE TABLE IF NOT EXISTS agent_actions(
 action_id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL REFERENCES agent_sessions(session_id),
 delegation_id TEXT NOT NULL REFERENCES agent_delegations(delegation_id),
 study_id TEXT NOT NULL,
 call_id TEXT NOT NULL CHECK(length(call_id) BETWEEN 1 AND 160),
 tool TEXT NOT NULL CHECK(length(tool) BETWEEN 1 AND 64),
 effect TEXT CHECK(effect IS NULL OR effect IN ({_closed(ACTION_EFFECTS)})),
 args_sha256 TEXT NOT NULL CHECK(length(args_sha256)=64),
 command_ids TEXT NOT NULL, api_operations TEXT NOT NULL DEFAULT '[]',
 outcome_class TEXT CHECK(outcome_class IS NULL OR outcome_class IN ({_closed(OUTCOME_CLASSES)})),
 reason_code TEXT, reason_message TEXT CHECK(reason_message IS NULL OR length(reason_message)<=512),
 warnings TEXT NOT NULL DEFAULT '[]', records TEXT NOT NULL DEFAULT '[]',
 result_json TEXT
  CHECK(result_json IS NULL OR length(CAST(result_json AS BLOB))<={RESULT_CAP_BYTES}),
 state TEXT NOT NULL CHECK(state IN ({_closed(ACTION_STATES)})),
 created_at TEXT NOT NULL, completed_at TEXT,
 UNIQUE(session_id,call_id),
 CHECK((reason_code IS NULL)=(reason_message IS NULL)),
 CHECK(result_json IS NULL OR effect IN ('draft','record','submit','outside_study')),
 CHECK(state<>'completed' OR (reason_code IS NULL AND outcome_class='ok'))
);
CREATE INDEX IF NOT EXISTS agent_actions_study ON agent_actions(study_id,created_at);
CREATE TRIGGER IF NOT EXISTS agent_actions_no_delete BEFORE DELETE ON agent_actions
 BEGIN SELECT RAISE(ABORT,'the agent action journal is append-only'); END;
CREATE TRIGGER IF NOT EXISTS agent_actions_inserted BEFORE INSERT ON agent_actions
 WHEN NEW.state NOT IN ('intended','refused')
 BEGIN SELECT RAISE(ABORT,'a journal row starts intended or refused'); END;
CREATE TRIGGER IF NOT EXISTS agent_actions_outcome_once BEFORE UPDATE ON agent_actions
 WHEN OLD.state NOT IN ('intended','reconciling') OR NEW.state='intended'
  OR {_changed(ACTION_INTENDED)}
 BEGIN SELECT RAISE(ABORT,'a journal row records one outcome and its intent never changes'); END;
"""


def _admits_every_kind(db):
    """Whether the stored attribution table's kind check names every record kind."""
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_attribution'"
    ).fetchone()
    return row is None or all(f"'{kind}'" in row[0] for kind in RECORD_KINDS)


def ensure(store):
    """Create the runtime-owned tables in ``store`` (idempotent). An attribution table made
    before a record kind was added is rebuilt with every entry kept: its rows move to a table
    whose check admits the current kinds (a dropped table fires no delete trigger)."""
    if store.verify_schema():
        return
    with store.connection(write=True) as db:
        # One statement at a time: a script would commit the transaction part-way.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(agent_attribution)')}
        if columns and 'delegator_display_name' not in columns:
            db.execute('ALTER TABLE agent_attribution ADD COLUMN delegator_display_name TEXT')
        if not _admits_every_kind(db):
            db.execute('ALTER TABLE agent_attribution RENAME TO agent_attribution_previous')
            db.execute('DROP TRIGGER IF EXISTS agent_attribution_no_delete')
            db.execute(_ATTRIBUTION_TABLE)
            db.execute(_ATTRIBUTION_TRIGGER)
            db.execute('INSERT INTO agent_attribution SELECT * FROM agent_attribution_previous')
            db.execute('DROP TABLE agent_attribution_previous')
    with store.connection() as db:
        db.executescript(DDL)
        db.executescript(RUNTIME_DDL)
