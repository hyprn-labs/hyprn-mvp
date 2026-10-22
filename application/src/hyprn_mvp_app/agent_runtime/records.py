"""The agent records store module: every SQL statement over the agent records (attribution,
sessions and the action journal).

Each function runs on a connection or transaction that ``Store.connection`` handed out, so the
store stays the single transaction owner and gains no method for agent records. Nothing here
authorizes: callers authorize through ``Store.authorize`` in the same transaction first.
"""

ATTRIBUTION_COLUMNS = (
    'study_id',
    'record_kind',
    'record_id',
    'version_id',
    'command_category',
    'command_id',
    'agent_actor_id',
    'agent_display_name',
    'delegator_actor_id',
    'recorded_at',
    'delegator_display_name',
)
# Newest first; the key orders entries recorded at the same instant.
ATTRIBUTION_ORDER = ('recorded_at', 'command_category', 'command_id', 'record_kind', 'record_id')
_ORDER_SQL = ','.join(f'{column} DESC' for column in ATTRIBUTION_ORDER)
_AFTER_SQL = f'({",".join(ATTRIBUTION_ORDER)})<(?,?,?,?,?)'
_SELECT = f'SELECT {",".join(ATTRIBUTION_COLUMNS)} FROM agent_attribution'


def insert_attribution(db, entry):
    """Add one attribution entry; a repeat of the same key is ignored (idempotent)."""
    db.execute(
        f'INSERT INTO agent_attribution({",".join(ATTRIBUTION_COLUMNS)}) '
        f'VALUES({",".join("?" * len(ATTRIBUTION_COLUMNS))}) ON CONFLICT DO NOTHING',
        tuple(entry[column] for column in ATTRIBUTION_COLUMNS),
    )


def study_attribution(db, study_id, after=None):
    """The entries of ``study_id``, newest first, strictly after key ``after`` when given."""
    where, args = 'WHERE study_id=?', [study_id]
    if after is not None:
        where += ' AND ' + _AFTER_SQL
        args += list(after)
    return (dict(row) for row in db.execute(f'{_SELECT} {where} ORDER BY {_ORDER_SQL}', args))


def created_study_attribution(db, after=None):
    """The entries of studies an agent created, newest first, strictly after ``after``."""
    where, args = "WHERE record_kind='study'", []
    if after is not None:
        where += ' AND ' + _AFTER_SQL
        args += list(after)
    return (dict(row) for row in db.execute(f'{_SELECT} {where} ORDER BY {_ORDER_SQL}', args))


def user_by_name(db, username):
    """The actor id of the user ``username``; ``None`` when there is none."""
    row = db.execute('SELECT actor_id FROM users WHERE username=?', (username,)).fetchone()
    return row['actor_id'] if row else None


def user_name(db, actor_id):
    """The display name (user name) of user ``actor_id``; ``None`` when there is none."""
    from ..identity import display_name
    return display_name(db, actor_id)


def study_delegations(db, study_id):
    """Every delegation of ``study_id`` with its agent's display name, newest first."""
    return [
        dict(row)
        for row in db.execute(
            'SELECT d.*,a.display_name AS agent_display_name FROM agent_delegations d '
            'JOIN agent_actors a ON a.actor_id=d.agent_actor_id WHERE d.study_id=? '
            'ORDER BY d.created_at DESC,d.delegation_id DESC',
            (study_id,),
        )
    ]


# ---- Agent sessions ----------------------------------------------------------------------

SESSION_COLUMNS = (
    'session_id',
    'delegation_id',
    'surface',
    'client_name',
    'client_version',
    'agent_display_name',
    'registry_version',
    'playbook_sha256',
    'tool_definitions_sha256',
    'state',
    'api_calls',
    'runs_submitted',
    'started_at',
    'ended_at',
)


def insert_session(db, session):
    """Add one agent session (state ``active``, counters at zero)."""
    db.execute(
        f'INSERT INTO agent_sessions({",".join(SESSION_COLUMNS)}) '
        f'VALUES({",".join("?" * len(SESSION_COLUMNS))})',
        tuple(session[column] for column in SESSION_COLUMNS),
    )


def session(db, session_id):
    """Agent session ``session_id``; ``None`` when there is none."""
    row = db.execute('SELECT * FROM agent_sessions WHERE session_id=?', (session_id,)).fetchone()
    return dict(row) if row else None


def delegation_study(db, delegation_id):
    """The study of delegation ``delegation_id`` (live or not); ``None`` when there is none."""
    row = db.execute(
        'SELECT study_id FROM agent_delegations WHERE delegation_id=?', (delegation_id,)
    ).fetchone()
    return row['study_id'] if row else None


def end_delegation_sessions(db, delegation_id, ended_at):
    """End every active session of delegation ``delegation_id``; returns their ids."""
    ids = [
        row['session_id']
        for row in db.execute(
            "SELECT session_id FROM agent_sessions WHERE delegation_id=? AND state='active' "
            'ORDER BY session_id',
            (delegation_id,),
        ).fetchall()
    ]
    for session_id in ids:
        end_session(db, session_id, 'ended', ended_at)
    return ids


def end_session(db, session_id, state, ended_at):
    """Move session ``session_id`` from ``active`` to ``state``; whether it was active."""
    cursor = db.execute(
        "UPDATE agent_sessions SET state=?,ended_at=? WHERE session_id=? AND state='active'",
        (state, ended_at, session_id),
    )
    return cursor.rowcount == 1


def count_api_call(db, session_id, limit):
    """Count one API call of active session ``session_id`` unless it already made ``limit``;
    whether it was counted (the check and the count are one statement)."""
    cursor = db.execute(
        'UPDATE agent_sessions SET api_calls=api_calls+1 '
        "WHERE session_id=? AND state='active' AND api_calls<?",
        (session_id, limit),
    )
    return cursor.rowcount == 1


def add_runs_submitted(db, session_id, count):
    """Add ``count`` journaled runs to the session's submitted-run counter."""
    db.execute(
        'UPDATE agent_sessions SET runs_submitted=runs_submitted+? WHERE session_id=?',
        (count, session_id),
    )


# ---- The action journal ------------------------------------------------------------------

ACTION_COLUMNS = (
    'action_id',
    'session_id',
    'delegation_id',
    'study_id',
    'call_id',
    'tool',
    'effect',
    'args_sha256',
    'command_ids',
    'state',
    'created_at',
)
OUTCOME_COLUMNS = (
    'api_operations',
    'outcome_class',
    'reason_code',
    'reason_message',
    'warnings',
    'records',
    'result_json',
    'state',
    'completed_at',
)


def insert_action(db, row):
    """Add one journal row: ``intended``, or ``refused`` at admission with its outcome."""
    columns = ACTION_COLUMNS + tuple(c for c in OUTCOME_COLUMNS if c in row and c != 'state')
    db.execute(
        f'INSERT INTO agent_actions({",".join(columns)}) VALUES({",".join("?" * len(columns))})',
        tuple(row[column] for column in columns),
    )


def action(db, session_id, call_id):
    """The journal row of call ``call_id`` in session ``session_id``; ``None`` when none."""
    row = db.execute(
        'SELECT * FROM agent_actions WHERE session_id=? AND call_id=?', (session_id, call_id)
    ).fetchone()
    return dict(row) if row else None


def action_by_id(db, action_id):
    """Journal row ``action_id``; ``None`` when there is none."""
    row = db.execute('SELECT * FROM agent_actions WHERE action_id=?', (action_id,)).fetchone()
    return dict(row) if row else None


def finish_action(db, action_id, outcome):
    """Record the outcome of journal row ``action_id`` while it is ``intended`` or
    ``reconciling``; whether a row moved (the journal's triggers refuse any other change)."""
    cursor = db.execute(
        f'UPDATE agent_actions SET {",".join(c + "=?" for c in OUTCOME_COLUMNS)} '
        "WHERE action_id=? AND state IN ('intended','reconciling')",
        tuple(outcome[column] for column in OUTCOME_COLUMNS) + (action_id,),
    )
    return cursor.rowcount == 1


def identical_refusals(db, session_id, tool, args_sha256, reason_code, since):
    """How many calls of ``tool`` with the same argument digest in session ``session_id`` were
    refused with ``reason_code`` at or after ``since``."""
    return db.execute(
        'SELECT count(*) FROM agent_actions WHERE session_id=? AND tool=? AND args_sha256=? '
        "AND state='refused' AND reason_code=? AND created_at>=?",
        (session_id, tool, args_sha256, reason_code, since),
    ).fetchone()[0]


_RUN_RECORDS = (
    "SELECT DISTINCT json_extract(r.value,'$.record_id') AS run_id FROM agent_actions a, "
    "json_each(a.records) r WHERE json_extract(r.value,'$.kind')='run' AND "
)


def session_runs(db, session_id):
    """The ids of the runs journaled as records of session ``session_id``."""
    return [
        row['run_id']
        for row in db.execute(_RUN_RECORDS + 'a.session_id=? ORDER BY 1', (session_id,))
    ]


def actor_runs(db, agent_actor_id, study_id):
    """The ids of the runs journaled as records of agent ``agent_actor_id`` in ``study_id``,
    across its sessions and delegations."""
    return [
        row['run_id']
        for row in db.execute(
            _RUN_RECORDS + 'a.study_id=? AND a.delegation_id IN (SELECT delegation_id FROM '
            'agent_delegations WHERE agent_actor_id=? AND study_id=?) ORDER BY 1',
            (study_id, agent_actor_id, study_id),
        )
    ]
