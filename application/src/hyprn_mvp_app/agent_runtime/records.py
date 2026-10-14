"""The agent records store module: every SQL statement over the agent records.

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
)
# Newest first; the key orders entries recorded at the same instant.
ATTRIBUTION_ORDER = ('recorded_at', 'command_category', 'command_id', 'record_kind', 'record_id')
_ORDER_SQL = ','.join(f'{column} DESC' for column in ATTRIBUTION_ORDER)
_AFTER_SQL = f'({",".join(ATTRIBUTION_ORDER)})<(?,?,?,?,?)'
_SELECT = f'SELECT {",".join(ATTRIBUTION_COLUMNS)} FROM agent_attribution'


def insert_attribution(db, entry):
    """Add one attribution entry; a repeat of the same key is ignored (idempotent)."""
    db.execute(
        f'INSERT OR IGNORE INTO agent_attribution({",".join(ATTRIBUTION_COLUMNS)}) '
        f'VALUES({",".join("?" * len(ATTRIBUTION_COLUMNS))})',
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
    row = db.execute('SELECT username FROM users WHERE actor_id=?', (actor_id,)).fetchone()
    return row['username'] if row else None


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


def live_surface_delegations(db, study_id, surface):
    """The ids of the unrevoked delegations of ``study_id`` on ``surface``."""
    return [
        row['delegation_id']
        for row in db.execute(
            'SELECT delegation_id FROM agent_delegations WHERE study_id=? AND surface=? '
            'AND revoked_at IS NULL ORDER BY delegation_id',
            (study_id, surface),
        )
    ]


_TOKENS = (
    'SELECT t.token_id,t.client_label,t.created_at,t.expires_at,t.revoked_at,t.delegation_id,'
    'd.allowed_effects,d.agent_actor_id,d.delegator_actor_id,a.display_name AS agent_display_name '
    'FROM agent_tool_tokens t JOIN agent_delegations d ON d.delegation_id=t.delegation_id '
    'JOIN agent_actors a ON a.actor_id=d.agent_actor_id WHERE d.study_id=?'
)


def study_tokens(db, study_id):
    """Metadata of every tool token of ``study_id`` (never a hash), newest first."""
    return [
        dict(row)
        for row in db.execute(_TOKENS + ' ORDER BY t.created_at DESC,t.token_id DESC', (study_id,))
    ]


def study_token(db, study_id, token_id):
    """Metadata of tool token ``token_id`` when it belongs to ``study_id``; ``None`` otherwise."""
    row = db.execute(_TOKENS + ' AND t.token_id=?', (study_id, token_id)).fetchone()
    return dict(row) if row else None
