"""Runtime-owned tables of the agent records, created idempotently.

``ensure(store)`` runs this module's DDL on a connection of the one ``Store`` (its single
writer), called by the composition root until the store's own initialization runs the
registered schemas; ``store`` never imports this package. Every statement is ``IF NOT EXISTS``,
so a repeated call changes nothing.
"""

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
)

_KINDS = ','.join(f"'{kind}'" for kind in RECORD_KINDS)

# Attribution index: which agent, for which delegating user, wrote which record through which
# command. It is a projection of the owners' receipts, cross-checked against the receipt actor
# on every read, and never used for authorization or writes. No column names a confirmer:
# agent writes are direct. A study an agent created carries the new study's id as ``study_id``
# and ``record_id`` with the category ``study_create``. Entries are never deleted.
DDL = f"""
CREATE TABLE IF NOT EXISTS agent_attribution(
 study_id TEXT NOT NULL,
 record_kind TEXT NOT NULL CHECK(record_kind IN ({_KINDS})),
 record_id TEXT NOT NULL, version_id TEXT,
 command_category TEXT NOT NULL, command_id TEXT NOT NULL,
 agent_actor_id TEXT NOT NULL, agent_display_name TEXT NOT NULL,
 delegator_actor_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 PRIMARY KEY(study_id,command_category,command_id,record_kind,record_id)
);
CREATE TRIGGER IF NOT EXISTS agent_attribution_no_delete BEFORE DELETE ON agent_attribution
 BEGIN SELECT RAISE(ABORT,'agent attribution is never deleted'); END;
"""


def ensure(store):
    """Create the runtime-owned tables in ``store`` (idempotent)."""
    with store.connection() as db:
        db.executescript(DDL)
