"""Application-owned records and local transactions. Editable models live remotely."""
from __future__ import annotations
from .evidence_content import read_content
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import base64
import json
import os
import re
from pathlib import Path
import sqlite3
import time
from uuid import UUID, uuid5
# Identity, validation and the Error envelope are owned by .contracts. Re-exporting
# canonical/digest/uid/DomainError here is a temporary test-import alias; production code
# imports them from contracts (test_module_boundaries.py).
from .contracts import DomainError, canonical, data_json, digest, uid, validate
from .locations import refuse_location
from . import identity


_analysis_authority = ContextVar('hyprn_analysis_authority', default=None)


# ---- Exact evidence: one owner for the stored-version read and snapshot creation.
# Store owns the ``evidence`` table and its study scope; ``exact_evidence`` is the single
# integrity check, ``evidence_snapshot`` the single snapshot shape. Configurations, approach
# resolution and model citations call these; they never re-implement them.

EVIDENCE_SNAPSHOT_FIELDS=('evidence_version_id','kind','content','source_refs')


class ForeignEvidence(DomainError):
    """The evidence version exists but another study holds it: ``resource_not_found`` 404.

    Never discloses the record. Distinct from an authorization 404 so a caller whose policy
    treats another study's version like an unavailable one can say so precisely.
    """
    def __init__(self):
        super().__init__('resource_not_found',404)


def exact_evidence(payload,sid,version):
    """Interpret stored evidence ``payload`` text as exact evidence version ``version`` of ``sid``.

    Pure; shared by ``Store.evidence_record`` and readers that pin the raw row themselves as a
    write-time witness (approach resolution). Returns the decoded record. Raises ``ValueError``
    for undecodable text, ``ContractError`` ``backend_unavailable`` 503 when the payload is not
    an ``EvidenceRecordRead``, and ``DomainError`` ``reference_conflict`` when its study,
    version or resource-scope study disagrees with the exact reference.
    """
    record=json.loads(payload)
    validate('EvidenceRecordRead',record,remote=True)
    if (record['study_id']!=sid or record['evidence_version_id']!=version
            or record.get('resource_scope',{}).get('study_id',sid)!=sid):
        raise DomainError('reference_conflict')
    return record


def evidence_snapshot(record,*,legacy_configuration=False):
    """The exact evidence snapshot retained for ``record``: a detached copy, pure.

    Configuration 3/4 and approach closures retain a whole ``EvidenceRecord3``. Configuration
    1/2 (``legacy_configuration``) retain only the common fields of any record. ``EvidenceRecord2``
    adds ``evidence_schema_version`` and ``resource_scope``; ``EvidenceRecord1`` has the common
    fields only. Bytes are pinned by ``application/tests/fixtures/identity_golden.json``.
    """
    version=record.get('evidence_schema_version')
    if version=='3' and not legacy_configuration:return deepcopy(record)
    result={k:deepcopy(record[k]) for k in EVIDENCE_SNAPSHOT_FIELDS}
    if version=='2':
        result.update({k:deepcopy(record[k]) for k in ('evidence_schema_version','resource_scope')})
    return result

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 actor_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 failures INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(actor_id),
 csrf_hash TEXT NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS studies(
 study_id TEXT PRIMARY KEY, revision TEXT NOT NULL, name TEXT NOT NULL,
 description TEXT NOT NULL, boundary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships(
 study_id TEXT NOT NULL REFERENCES studies(study_id), actor_id TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('owner','writer','reader')),
 PRIMARY KEY(study_id,actor_id)
);
CREATE TABLE IF NOT EXISTS model_associations(
 study_id TEXT NOT NULL REFERENCES studies(study_id), model_id TEXT NOT NULL,
 command_id TEXT NOT NULL, PRIMARY KEY(study_id,model_id)
);
CREATE TABLE IF NOT EXISTS evidence(
 evidence_version_id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL,
 study_id TEXT NOT NULL REFERENCES studies(study_id), payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_families(
 evidence_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 head TEXT NOT NULL REFERENCES evidence(evidence_version_id)
);
CREATE INDEX IF NOT EXISTS evidence_study_family ON evidence(study_id,evidence_id);
CREATE TABLE IF NOT EXISTS configuration_families(
 configuration_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 head TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS configurations(
 configuration_revision_id TEXT PRIMARY KEY, configuration_id TEXT NOT NULL,
 study_id TEXT NOT NULL REFERENCES studies(study_id), payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts(
 scope TEXT NOT NULL, category TEXT NOT NULL, command_id TEXT NOT NULL,
 actor_id TEXT NOT NULL, payload_digest TEXT NOT NULL, state TEXT NOT NULL,
 result TEXT, error TEXT, request TEXT, PRIMARY KEY(scope,category,command_id)
);
CREATE TABLE IF NOT EXISTS run_associations(
 run_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 configuration_revision_id TEXT NOT NULL REFERENCES configurations(configuration_revision_id),
 command_id TEXT NOT NULL, store_uuid TEXT, process_uuid TEXT, accepted_at TEXT,
 UNIQUE(study_id,command_id), UNIQUE(store_uuid,process_uuid)
);
CREATE TABLE IF NOT EXISTS outbox(
 run_id TEXT PRIMARY KEY REFERENCES run_associations(run_id),
 state TEXT NOT NULL CHECK(state IN ('accepted_run','dispatching','recorded','uncertain')),
 payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS execution_operations(
 run_id TEXT PRIMARY KEY REFERENCES run_associations(run_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id), actor_id TEXT NOT NULL,
 command_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('accepted_run','dispatching','recorded','uncertain')),
 preparation_state TEXT CHECK(preparation_state IN ('prepared','preparation_failed')),
 payload TEXT NOT NULL DEFAULT '{}' CHECK(json_type(payload)='object'
   AND json_remove(payload,'$.status','$.history')='{}')
);
CREATE INDEX IF NOT EXISTS execution_pending ON execution_operations(run_id)
 WHERE state IN ('accepted_run','dispatching')
 AND (preparation_state IS NULL OR preparation_state<>'preparation_failed');
CREATE INDEX IF NOT EXISTS execution_actor_pending ON execution_operations(actor_id,state)
 WHERE state IN ('accepted_run','dispatching','uncertain')
 AND (preparation_state IS NULL OR preparation_state<>'preparation_failed');
CREATE TRIGGER IF NOT EXISTS execution_insert AFTER INSERT ON outbox BEGIN
 INSERT INTO execution_operations
 SELECT r.run_id,r.study_id,coalesce(json_extract(NEW.payload,'$.actor'),''),r.command_id,
 NEW.state,json_extract(NEW.payload,'$.preparation_state'),
 hyprn_execution_projection(NEW.payload,'{}')
 FROM run_associations r WHERE r.run_id=NEW.run_id;
END;
CREATE TRIGGER IF NOT EXISTS execution_source_update AFTER UPDATE OF payload,state ON outbox BEGIN
 UPDATE execution_operations SET state=CASE WHEN NEW.state=OLD.state THEN state ELSE NEW.state END,
 preparation_state=coalesce(json_extract(NEW.payload,'$.preparation_state'),preparation_state),
 payload=hyprn_execution_projection(NEW.payload,payload)
 WHERE run_id=NEW.run_id;
END;
CREATE TRIGGER IF NOT EXISTS execution_fixed BEFORE UPDATE ON execution_operations
 WHEN NEW.run_id<>OLD.run_id OR NEW.study_id<>OLD.study_id OR NEW.actor_id<>OLD.actor_id
 OR NEW.command_id<>OLD.command_id
 BEGIN SELECT RAISE(ABORT,'execution identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS execution_no_delete BEFORE DELETE ON execution_operations
 BEGIN SELECT RAISE(ABORT,'execution records are never deleted'); END;
CREATE TABLE IF NOT EXISTS execution_observation(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 status TEXT NOT NULL CHECK(status IN ('ready','unavailable')),
 reason TEXT CHECK(reason IN ('executor_unavailable','attestation_invalid')),
 observed_at REAL NOT NULL, expires_at REAL NOT NULL, runtime_json TEXT,
 CHECK(expires_at=observed_at+30),
 CHECK((status='ready' AND reason IS NULL) OR (status='unavailable' AND reason IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS computational_record_requests(
 request_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 actor_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('preview','create')),
 command_id TEXT NOT NULL, payload_digest TEXT NOT NULL, selected_ids_json TEXT NOT NULL,
 preview_id TEXT, expected_preview_digest TEXT,
 state TEXT NOT NULL CHECK(state IN ('queued','building','reviewable','ready','failed')),
 generation INTEGER NOT NULL, payload_json TEXT NOT NULL, error_json TEXT,
 artifact_path TEXT, artifact_sha256 TEXT,
 UNIQUE(study_id,kind,command_id)
);
CREATE TRIGGER IF NOT EXISTS immutable_evidence_update BEFORE UPDATE ON evidence
 BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER IF NOT EXISTS immutable_evidence_delete BEFORE DELETE ON evidence
 BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER IF NOT EXISTS immutable_configuration_update BEFORE UPDATE ON configurations
 BEGIN SELECT RAISE(ABORT,'immutable configuration'); END;
CREATE TRIGGER IF NOT EXISTS immutable_configuration_delete BEFORE DELETE ON configurations
 BEGIN SELECT RAISE(ABORT,'immutable configuration'); END;
-- Study-wide archive (presentation) state. Additive: no column on populated
-- ``studies``, no revision change. A study without a row is not archived. Restore sets
-- archived=0; rows are never deleted. Every transition's actor and outcome is also the
-- immutable ``study_archive`` receipt named by ``command_id``.
CREATE TABLE IF NOT EXISTS study_archive(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 archived INTEGER NOT NULL CHECK(archived IN (0,1)),
 command_id TEXT NOT NULL, actor_id TEXT NOT NULL, changed_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS study_archive_no_delete BEFORE DELETE ON study_archive
 BEGIN SELECT RAISE(ABORT,'study archive state is never deleted'); END;
-- Agent principals. An agent actor is never a row of ``users``, so it can never sign in; the
-- only reference to ``users`` is the delegating user. One agent actor per (user, surface).
CREATE TRIGGER IF NOT EXISTS analysis_execution_request_fixed BEFORE UPDATE ON receipts
 WHEN OLD.category='analysis_execution' AND NEW.request IS NOT OLD.request
 BEGIN SELECT RAISE(ABORT,'accepted finite authority never changes'); END;
CREATE TABLE IF NOT EXISTS analysis_execution_children(
 study_id TEXT NOT NULL REFERENCES studies(study_id), analysis_command TEXT NOT NULL,
 child_category TEXT NOT NULL CHECK(child_category IN ('run','calculation_estimate')),
 child_command TEXT NOT NULL, run_id TEXT,
 PRIMARY KEY(study_id,child_category,child_command), UNIQUE(run_id)
);
CREATE TRIGGER IF NOT EXISTS analysis_execution_children_no_update BEFORE UPDATE ON analysis_execution_children
 BEGIN SELECT RAISE(ABORT,'accepted analysis child identity never changes'); END;
CREATE TRIGGER IF NOT EXISTS analysis_execution_children_no_delete BEFORE DELETE ON analysis_execution_children
 BEGIN SELECT RAISE(ABORT,'accepted analysis child identity never changes'); END;
CREATE TABLE IF NOT EXISTS analysis_authority_barriers(
 study_id TEXT NOT NULL, analysis_command TEXT NOT NULL,
 PRIMARY KEY(study_id,analysis_command)
);
CREATE TRIGGER IF NOT EXISTS analysis_membership_downgrade AFTER UPDATE OF role ON memberships
 WHEN OLD.role IN ('writer','owner') AND NEW.role NOT IN ('writer','owner') BEGIN
 INSERT OR IGNORE INTO analysis_authority_barriers
 SELECT r.scope,r.command_id FROM receipts r WHERE r.scope=OLD.study_id
 AND r.category='analysis_execution' AND (r.actor_id=OLD.actor_id OR r.actor_id IN
 (SELECT actor_id FROM agent_actors WHERE delegator_actor_id=OLD.actor_id));
END;
CREATE TRIGGER IF NOT EXISTS analysis_membership_removal AFTER DELETE ON memberships BEGIN
 INSERT OR IGNORE INTO analysis_authority_barriers
 SELECT r.scope,r.command_id FROM receipts r WHERE r.scope=OLD.study_id
 AND r.category='analysis_execution' AND (r.actor_id=OLD.actor_id OR r.actor_id IN
 (SELECT actor_id FROM agent_actors WHERE delegator_actor_id=OLD.actor_id));
END;
CREATE TRIGGER IF NOT EXISTS analysis_barriers_fixed BEFORE UPDATE ON analysis_authority_barriers
 BEGIN SELECT RAISE(ABORT,'analysis authority loss is permanent'); END;
CREATE TRIGGER IF NOT EXISTS analysis_barriers_no_delete BEFORE DELETE ON analysis_authority_barriers
 BEGIN SELECT RAISE(ABORT,'analysis authority loss is permanent'); END;
CREATE TABLE IF NOT EXISTS analysis_execution_resumptions(
 study_id TEXT NOT NULL, command_id TEXT NOT NULL, analysis_command TEXT NOT NULL,
 actor_id TEXT NOT NULL, previous_result TEXT NOT NULL, resumed_result TEXT NOT NULL,
 PRIMARY KEY(study_id,command_id)
);
CREATE TRIGGER IF NOT EXISTS analysis_resumptions_fixed BEFORE UPDATE ON analysis_execution_resumptions
 BEGIN SELECT RAISE(ABORT,'analysis recovery audit is immutable'); END;
CREATE TRIGGER IF NOT EXISTS analysis_resumptions_no_delete BEFORE DELETE ON analysis_execution_resumptions
 BEGIN SELECT RAISE(ABORT,'analysis recovery audit is immutable'); END;
CREATE TABLE IF NOT EXISTS analysis_run_resumptions(
 study_id TEXT NOT NULL, command_id TEXT NOT NULL, analysis_command TEXT NOT NULL,
 run_id TEXT NOT NULL, child_command TEXT NOT NULL, actor_id TEXT NOT NULL,
 source_sha256 TEXT NOT NULL, previous_receipt TEXT NOT NULL, previous_operation TEXT NOT NULL,
 PRIMARY KEY(study_id,command_id,run_id),
 FOREIGN KEY(study_id,command_id) REFERENCES analysis_execution_resumptions(study_id,command_id)
);
CREATE TRIGGER IF NOT EXISTS analysis_run_resumptions_fixed BEFORE UPDATE ON analysis_run_resumptions
 BEGIN SELECT RAISE(ABORT,'analysis child recovery audit is immutable'); END;
CREATE TRIGGER IF NOT EXISTS analysis_run_resumptions_no_delete BEFORE DELETE ON analysis_run_resumptions
 BEGIN SELECT RAISE(ABORT,'analysis child recovery audit is immutable'); END;
CREATE TABLE IF NOT EXISTS analysis_reconciliation_intents(
 study_id TEXT NOT NULL, command_id TEXT NOT NULL, analysis_command TEXT NOT NULL,
 actor_id TEXT NOT NULL, runs TEXT NOT NULL, previous_result TEXT NOT NULL,
 PRIMARY KEY(study_id,command_id)
);
CREATE TABLE IF NOT EXISTS analysis_reconciliation_results(
 study_id TEXT NOT NULL, command_id TEXT NOT NULL, outcome TEXT NOT NULL, proof TEXT NOT NULL,
 PRIMARY KEY(study_id,command_id),
 FOREIGN KEY(study_id,command_id) REFERENCES analysis_reconciliation_intents(study_id,command_id)
);
CREATE TRIGGER IF NOT EXISTS reconciliation_intent_fixed BEFORE UPDATE ON analysis_reconciliation_intents
 BEGIN SELECT RAISE(ABORT,'reconciliation intent is immutable'); END;
CREATE TRIGGER IF NOT EXISTS reconciliation_intent_retained BEFORE DELETE ON analysis_reconciliation_intents
 BEGIN SELECT RAISE(ABORT,'reconciliation intent is immutable'); END;
CREATE TRIGGER IF NOT EXISTS reconciliation_result_fixed BEFORE UPDATE ON analysis_reconciliation_results
 BEGIN SELECT RAISE(ABORT,'reconciliation proof is immutable'); END;
CREATE TRIGGER IF NOT EXISTS reconciliation_result_retained BEFORE DELETE ON analysis_reconciliation_results
 BEGIN SELECT RAISE(ABORT,'reconciliation proof is immutable'); END;
CREATE TABLE IF NOT EXISTS agent_actors(
 actor_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='agent'),
 delegator_actor_id TEXT NOT NULL REFERENCES users(actor_id),
 surface TEXT NOT NULL CHECK(surface IN ('claude_managed','openai_agents')),
 display_name TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(delegator_actor_id,surface)
);
-- A delegation binds one agent actor to one study under a role ceiling and a closed set of
-- effects (canonical JSON array). Its fields never change; it ends only by revocation or
-- expiry. At most one live (unrevoked) delegation per (agent actor, study): renewal replaces it.
CREATE TABLE IF NOT EXISTS agent_delegations(
 delegation_id TEXT PRIMARY KEY, agent_actor_id TEXT NOT NULL REFERENCES agent_actors(actor_id),
 delegator_actor_id TEXT NOT NULL REFERENCES users(actor_id),
 surface TEXT NOT NULL CHECK(surface IN ('claude_managed','openai_agents')),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 role_ceiling TEXT NOT NULL CHECK(role_ceiling IN ('reader','writer')),
 allowed_effects TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
 revoked_at REAL, revoked_reason TEXT,
 CHECK((revoked_at IS NULL)=(revoked_reason IS NULL))
);
-- Persist authority interruptions even if subsequent grant clocks move backwards.
CREATE TRIGGER IF NOT EXISTS analysis_delegation_revoked AFTER UPDATE OF revoked_at ON agent_delegations
 WHEN OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL AND NEW.revoked_reason<>'replaced' BEGIN
 INSERT OR IGNORE INTO analysis_authority_barriers
 SELECT scope,command_id FROM receipts WHERE scope=NEW.study_id AND actor_id=NEW.agent_actor_id
 AND category='analysis_execution';
END;
CREATE TRIGGER IF NOT EXISTS analysis_delegation_narrowed AFTER INSERT ON agent_delegations
 WHEN NEW.role_ceiling<>'writer' OR NOT EXISTS(
 SELECT 1 FROM json_each(NEW.allowed_effects) WHERE value='submit') BEGIN
 INSERT OR IGNORE INTO analysis_authority_barriers
 SELECT scope,command_id FROM receipts WHERE scope=NEW.study_id AND actor_id=NEW.agent_actor_id
 AND category='analysis_execution';
END;
CREATE UNIQUE INDEX IF NOT EXISTS agent_delegations_one_live
 ON agent_delegations(agent_actor_id,study_id) WHERE revoked_at IS NULL;
-- Delegated agent API sessions: hashes only; the cookie and cross-site request values are
-- returned once to the in-process caller and never stored.
CREATE TABLE IF NOT EXISTS agent_api_sessions(
 token_hash TEXT PRIMARY KEY, csrf_hash TEXT NOT NULL,
 delegation_id TEXT NOT NULL REFERENCES agent_delegations(delegation_id),
 actor_id TEXT NOT NULL REFERENCES agent_actors(actor_id),
 read_only INTEGER NOT NULL CHECK(read_only IN (0,1)), expires_at REAL NOT NULL
);
"""


def _execution_projection(source, existing):
    """Copy lifecycle fields without dropping nested nulls in scientific records."""
    original = json.loads(source)
    result = json.loads(existing)
    result.update({key: original[key] for key in ('status', 'history') if key in original})
    return json.dumps(result)

# ---- Agent principals: closed vocabularies shared by ``store`` and ``auth``.
AGENT_SURFACES=frozenset({'claude_managed','openai_agents'})
# Effects a delegation may hold. No effect deletes a saved record, archives, restores or
# manages access: those are human-only and have no effect name at all.
AGENT_EFFECTS=frozenset({'read','draft','record','submit','outside_study','review'})
# Effects that change study state through the write path of ``authorize``.
AGENT_WRITE_EFFECTS=frozenset({'draft','record','submit'})
# Effects each role ceiling admits. An agent for a reader (Reviewer) may read, post notes and
# issue reports and record scientific reviews, and nothing else.
AGENT_CEILING_EFFECTS={'reader':frozenset({'read','outside_study','review'}),'writer':AGENT_EFFECTS}
# The study roles each ceiling requires of the delegating user.
_CEILING_ROLES={'reader':frozenset({'reader','writer','owner'}),'writer':frozenset({'writer','owner'})}


def agent_effects(raw):
    """The effects of a stored delegation (canonical JSON array) as a frozenset."""
    return frozenset(json.loads(raw))

# ---- Receipt recovery: how a client recovers after a lost reply, decided once, here. Every
# receipt read carries one ``recovery`` value; no client keeps a table of receipt states or
# categories (ADR-0004). A run is never resent: its lifecycle is read from the run.
RECEIPT_RETRY_AFTER_S=2
RECOVERY_VALUES=("adopt","wait","resend_same_command","uncertain","refused")
# Run receipt states whose result is the run (its lifecycle is read from the run itself).
RUN_RESULT_STATES=frozenset({"accepted_run","prepared","preparation_failed","dispatching","recorded"})

def receipt_recovery(category,receipt):
    """The recovery of a reader who may see the scope, for the receipt of ``category``
    (``None`` when it is missing): ``recovery`` and, with ``wait``, ``retry_after_s``.

    ``adopt``: the result is the outcome (``committed``; a run's accepted states);
    ``refused``: the stored rejection is the outcome; ``uncertain``: never resend (an
    uncertain run, or any state this table does not name); ``resend_same_command``: send the
    same command id and body again (a model ``pending_remote`` receipt, whose owner re-queries
    the modeling service first; a missing receipt of any category but ``run``, the mutation
    route re-checking authorization and exact idempotency); ``wait``: read again after
    ``retry_after_s`` (another ``pending_remote`` receipt; a missing run receipt, since a
    run is never resent)."""
    wait=dict(recovery="wait",retry_after_s=RECEIPT_RETRY_AFTER_S)
    if receipt is None:
        return wait if category=="run" else dict(recovery="resend_same_command")
    state=receipt["state"]
    if state=="committed" or category=="run" and state in RUN_RESULT_STATES:
        return dict(recovery="adopt")
    if state=="rejected":return dict(recovery="refused")
    if state=="pending_remote" and category!="run":
        return dict(recovery="resend_same_command") if category=="model" else wait
    return dict(recovery="uncertain")

class ReceiptMissing(DomainError):
    """No receipt in a scope the reader may see: today's ``resource_not_found`` 404 (code,
    message and outcome unchanged), carrying the recovery for the error envelope. ``data()`` is
    unchanged, so nothing new is ever persisted from it."""
    def __init__(self,category):
        super().__init__("resource_not_found",404)
        self.recovery=receipt_recovery(category,None)

def _evidence_written(record):
    """The evidence version an evidence command wrote, for attribution."""
    return [("evidence_version",record["evidence_id"],record["evidence_version_id"])]


class Store:
    schema_profile = "full"

    @classmethod
    def postgres(cls, request, authentication, *, background=None, artifact_root=None):
        """Complete hosted composition; never initializes or migrates a schema."""
        from .database import PostgreSQL
        from .migrations import verify
        result = cls.__new__(cls)
        result.database = PostgreSQL(request, authentication, background)
        result.artifact_root = artifact_root
        try:
            with result.database.connection() as db:
                verify(db)
        except BaseException:
            result.database.close()
            raise
        result.schema_profile = result.database.schema_profile
        return result

    def verify_schema(self):
        """Owners verify the entire migration ledger instead of performing startup DDL."""
        from .migrations import verify
        if hasattr(self, 'database'):
            with self.connection() as db:
                verify(db)
            return True
        return False

    def __init__(self, path):
        original=Path(path).absolute()
        # The one location rule (synced folders on every operating system, symbolic links in
        # the path or a parent, Windows-mounted drives), the same the installation loader
        # applies to the data root; refused before anything is created.
        refuse_location(original, what='Application storage')
        self.path = original.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd=os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        os.chmod(self.path,0o600)
        with self.connection() as db:
            operational_exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='execution_operations'").fetchone()
            authority_exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_authority_barriers'").fetchone()
            db.executescript(SCHEMA)
            if not authority_exists:
                db.execute("""INSERT OR IGNORE INTO analysis_authority_barriers
                    SELECT r.scope,r.command_id FROM receipts r WHERE r.category='analysis_execution'
                    AND EXISTS(SELECT 1 FROM receipts m WHERE m.scope=r.scope
                    AND m.category='membership' AND m.state='committed' AND m.rowid>r.rowid)""")
        # Additive, idempotent migration. Historical records and observation
        # values remain untouched; pre-existing rows simply have no runtime.
        with self.connection(write=True) as db:
            if not operational_exists:
                db.execute("""INSERT OR IGNORE INTO execution_operations
                    SELECT r.run_id,r.study_id,coalesce(json_extract(o.payload,'$.actor'),''),r.command_id,
                    o.state,json_extract(o.payload,'$.preparation_state'),
                    hyprn_execution_projection(o.payload,'{}')
                    FROM outbox o JOIN run_associations r USING(run_id)""")
            identity.ensure(db)
            columns={row['name'] for row in db.execute('PRAGMA table_info(execution_observation)')}
            if 'runtime_json' not in columns:
                db.execute('ALTER TABLE execution_observation ADD COLUMN runtime_json TEXT')
            # Runs accepted before the acceptance time was recorded keep NULL.
            association_columns={
                row['name'] for row in db.execute('PRAGMA table_info(run_associations)')}
            if 'accepted_at' not in association_columns:
                db.execute('ALTER TABLE run_associations ADD COLUMN accepted_at TEXT')

    @contextmanager
    def connection(self, write=False):
        if hasattr(self, "database"):
            with self.database.connection(write=write) as db:
                yield db
            return
        db=sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory=sqlite3.Row
        db.create_function('hyprn_execution_projection', 2, _execution_projection, deterministic=True)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write: db.execute("BEGIN IMMEDIATE")
            yield db
            if write: db.commit()
        except BaseException:
            if write: db.rollback()
            raise
        finally: db.close()

    @contextmanager
    def authentication_connection(self, *, write=False):
        """Read-only hosted credential authority; local edition retains its owner store."""
        if hasattr(self, "database"):
            with self.database.connection(authentication=True, write=write) as db:
                yield db
        else:
            with self.connection(write=write) as db:
                yield db

    def background_jobs(self, category, identity=None, *, after=None, limit=None):
        """Discover identity only through the process's narrowly granted queue function."""
        if limit is not None and (type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError('Queue page must contain 1 to 100 identities')
        with self.database.background_connection() as db:
            if after is not None or limit is not None:
                return db.execute('SELECT * FROM hyprn_background_jobs_page(?,?,?,?)',
                                  (category, identity, after, limit or 100)).fetchall()
            return db.execute('SELECT * FROM hyprn_background_jobs(?,?)',
                              (category, identity)).fetchall()

    def background_analysis_parent(self, category, identity):
        """Discover an immutable parent identity, without loading scientific payloads."""
        if hasattr(self, 'database'):
            with self.database.background_connection() as db:
                return db.execute('SELECT * FROM hyprn_analysis_child_job(?,?)',
                                  (category, identity)).fetchone()
        with self.connection() as db:
            return db.execute(
                'SELECT c.study_id,c.analysis_command,r.actor_id '
                'FROM analysis_execution_children c JOIN receipts r '
                "ON r.scope=c.study_id AND r.category='analysis_execution' "
                'AND r.command_id=c.analysis_command WHERE c.child_category=? AND '
                + ('c.run_id' if category == 'run' else 'c.child_command') + '=?',
                (category, identity)).fetchone()

    @contextmanager
    def background_actor(self, category, identity=None):
        """Bind discovered actor and, for a child, its immutable accepted-plan identity."""
        from .database import actor_scope, analysis_child_scope
        from contextlib import nullcontext
        child = None
        if hasattr(self, 'database'):
            jobs = self.background_jobs(category, identity)
            if not jobs:
                yield False
                return
            job = jobs[0]
            if category in ('run', 'calculation_estimate'):
                child = self.background_analysis_parent(category, job['work_id'])
            actor_context = actor_scope(job['actor_id'], request_boundary=True)
        else:
            actor_context = nullcontext()
            if category in ('run', 'calculation_estimate'):
                with self.connection() as db:
                    query = ('SELECT c.study_id,c.analysis_command,r.actor_id '
                             'FROM analysis_execution_children c JOIN receipts r '
                             "ON r.scope=c.study_id AND r.category='analysis_execution' "
                             'AND r.command_id=c.analysis_command WHERE c.child_category=? ')
                    if identity is not None:
                        query += 'AND ' + ('c.run_id' if category == 'run' else 'c.child_command') + '=?'
                        child = db.execute(query, (category, identity)).fetchone()
                    else:
                        query += ("AND c.child_command=(SELECT command_id FROM receipts "
                                  "WHERE category=? AND state='pending_remote' ORDER BY rowid LIMIT 1)")
                        child = db.execute(query, (category, category)).fetchone()
        with actor_context:
            if child is None:
                yield True
            else:
                token = _analysis_authority.set((self, child['actor_id'], child['study_id'],
                                                 child['analysis_command'], True))
                try:
                    with self.analysis_scope(child['study_id'], child['analysis_command']):
                        with analysis_child_scope():
                            yield True
                finally:
                    _analysis_authority.reset(token)

    def assistant_accounts(self):
        """Provider-account metadata for server-side accounting, never conversation text."""
        if hasattr(self, 'database'):
            with self.database.background_connection() as db:
                return db.execute('SELECT * FROM hyprn_assistant_accounts()').fetchall()
        with self.connection() as db:
            return db.execute('SELECT * FROM assistant_conversations').fetchall()

    def assistant_user_accounts(self):
        """Stable human billing owners, independent of current study membership."""
        if hasattr(self, 'database'):
            with self.database.background_connection() as db:
                return db.execute('SELECT * FROM hyprn_assistant_user_accounts()').fetchall()
        with self.connection() as db:
            return db.execute('''
 SELECT p.study_id,p.session_key AS conversation_id,p.provider_id,p.provision,
 c.reserved_cents,c.active_turn,c.state,p.billing_actor AS actor_id
 FROM assistant_provider_sessions p JOIN assistant_conversations c ON c.study_id=p.study_id
 UNION ALL
 SELECT c.study_id,c.conversation_id,c.provider_id,c.provision,
 c.reserved_cents,c.active_turn,c.state,
 (SELECT t.actor_id FROM assistant_turns t WHERE t.study_id=c.study_id
 ORDER BY t.created_at,t.turn_id LIMIT 1) AS actor_id
 FROM assistant_conversations c WHERE NOT EXISTS (
 SELECT 1 FROM assistant_provider_sessions p WHERE p.study_id=c.study_id AND
 (p.provider_id=c.provider_id OR (c.provider_id IS NULL AND p.provision<>'accepted')))
''').fetchall()

    def lock_path(self, suffix):
        """Fixed process lock names share the explicitly configured storage root."""
        if suffix not in {'.dispatch.lock', '.calculation-samples.lock'}:
            raise ValueError('Unknown owner lock')
        if not hasattr(self, 'database'):
            return self.path.with_suffix(suffix)
        if self.artifact_root is None:
            raise ValueError('Hosted artifact root must be configured explicitly')
        root = refuse_location(Path(self.artifact_root).absolute(), what='Application artifacts')
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return root / suffix

    def publish_execution_observation(self, status, reason, observed_at, runtime=None):
        """Trusted dispatcher only; no public write route or arbitrary payload."""
        from .readiness import runtime_identity, valid_observation_time
        if not valid_observation_time(observed_at):
            raise ValueError('Invalid observation time')
        if not ((status=='ready' and reason is None) or
                (status=='unavailable' and reason in ('executor_unavailable','attestation_invalid') and runtime is None)):
            raise ValueError('Invalid observation status')
        raw=canonical(runtime_identity(runtime)).decode() if runtime is not None else None
        if hasattr(self, 'database'):
            with self.database.background_connection(write=True) as db:
                db.execute('SELECT hyprn_publish_observation(?,?,?,?)',
                           (status, reason, observed_at, raw))
            return
        with self.connection(write=True) as db:
            db.execute('INSERT INTO execution_observation(singleton,status,reason,observed_at,expires_at,runtime_json) VALUES(1,?,?,?,?,?) '
                       'ON CONFLICT(singleton) DO UPDATE SET status=excluded.status,reason=excluded.reason,'
                       'observed_at=excluded.observed_at,expires_at=excluded.expires_at,runtime_json=excluded.runtime_json',
                       (status,reason,observed_at,observed_at+30,raw))

    def execution_observation(self):
        with self.connection() as db:
            row=db.execute('SELECT status,reason,observed_at,expires_at,runtime_json FROM execution_observation WHERE singleton=1').fetchone()
            if row is None:return None
            result=dict(row);raw=result.pop('runtime_json');result['runtime']=None
            if isinstance(raw,str) and len(raw)<=1024:
                from .readiness import runtime_identity
                try: result['runtime']=runtime_identity(data_json(raw))
                except (ValueError,TypeError): pass
            return result

    # ---- In-transaction interface. The caller holds ``db`` (from ``connection``) and
    # therefore the transaction; these never open, commit or roll back a connection. Other
    # modules use these public names, never Store's private helpers: ``authorize``,
    # ``study_row``, ``command_receipt``, ``model_association``, ``evidence_record`` and ``cas``.

    @contextmanager
    def analysis_scope(self, study, command):
        from .database import analysis_scope
        with analysis_scope(study, command):
            yield

    @contextmanager
    def analysis_authority(self, actor, study, command, *, child=False):
        """Scope dispatcher work to one accepted finite plan; never renew a session."""
        token = _analysis_authority.set((self, actor, study, command, child))
        try:
            with self.analysis_scope(study, command):
                with self.connection() as db:
                    self._analysis_permission(db, actor, study)
                yield
        finally:
            _analysis_authority.reset(token)

    def _analysis_permission(self, db, actor, study):
        scope = _analysis_authority.get()
        if scope is None:
            return None
        if scope[:3] != (self, actor, study):
            raise DomainError('forbidden', 403)
        receipt = self.command_receipt(db, study, 'analysis_execution', scope[3])
        if (not receipt or receipt['actor_id'] != actor
                or (receipt['state'] != 'pending_remote' and not scope[4])):
            raise DomainError('analysis_authority_revoked', 403)
        if not self.analysis_authorized(db, receipt, study):
            raise DomainError('analysis_authority_revoked', 403)
        return receipt

    def analysis_authorized(self, db, receipt, study):
        """Verify uninterrupted finite authority, including historical replacement grants.

        Expiry ends reasoning credentials, not an accepted finite plan. A narrower grant,
        explicit revocation or membership loss permanently interrupts that plan's authority.
        """
        actor = receipt['actor_id']
        authority = (receipt['request'] or {}).get('authority')
        if not authority or authority.get('actor_id') != actor:
            return False
        if hasattr(self, 'database'):
            return bool(db.execute('SELECT hyprn_analysis_authorized(?,?) AS allowed',
                                   (study, receipt['command_id'])).fetchone()['allowed'])
        if db.execute('SELECT 1 FROM analysis_authority_barriers WHERE study_id=? '
                      'AND analysis_command=?', (study, receipt['command_id'])).fetchone():
            return False
        agent = self.agent_actor(db, actor)
        subject = agent['delegator_actor_id'] if agent else actor
        if self._membership_role(db, study, subject) not in ('owner', 'writer'):
            return False
        if agent is None:
            return True
        pinned = db.execute('SELECT * FROM agent_delegations WHERE delegation_id=? '
                            'AND agent_actor_id=? AND study_id=?',
                            (authority.get('delegation_id'), actor, study)).fetchone()
        if not pinned:
            return False
        rows = db.execute('SELECT * FROM agent_delegations WHERE agent_actor_id=? '
                          'AND study_id=? AND created_at>=?',
                          (actor, study, pinned['created_at'])).fetchall()
        return all(row['role_ceiling'] == 'writer'
                   and 'submit' in json.loads(row['allowed_effects'])
                   and (row['revoked_at'] is None or row['revoked_reason'] == 'replaced')
                   for row in rows) and any(row['revoked_at'] is None for row in rows)

    def _analysis_command(self, db, actor, study, category, command, payload):
        receipt = self._analysis_permission(db, actor, study)
        if receipt is None:
            return
        if _analysis_authority.get()[4]:
            raise DomainError('forbidden', 403)
        request = receipt['request']
        namespace = UUID(receipt['command_id'])
        if category == 'run':
            member = payload.get('configuration_revision_id')
            allowed = (member in request['members']
                       and command == str(uuid5(namespace, member))
                       and payload == dict(operation='submit_run', target=study,
                                           configuration_revision_id=member))
        elif category == 'calculation_estimate':
            allowed = (request['estimate_plan'] is not None
                       and command == str(uuid5(namespace, 'estimate'))
                       and payload == dict(command_id=command,
                           calculation_version_id=request['calculation_version_id'],
                           tolerances=request['estimate_plan']['tolerances']))
        else:
            allowed = False
        if not allowed:
            raise DomainError('forbidden', 403)

    def authorize(self, db, actor, study, write=False, owner=False):
        """Authorize ``actor`` on ``study`` in the caller's ``db``.

        A human actor's own membership decides. An agent actor acts only through a live,
        unexpired delegation for exactly this study (otherwise the same undisclosed 404); it
        never holds owner authority (403), it writes only when its delegation holds a write
        effect under the writer ceiling (403), and then the delegating user's *current*
        membership and role decide exactly as for that user, so access loss applies on the
        next call.
        """
        if _analysis_authority.get() is not None:
            if owner:
                raise DomainError('forbidden', 403)
            self._analysis_permission(db, actor, study)
            return
        subject=actor
        agent=self.agent_actor(db,actor)
        if agent is not None:
            delegation=self._live_study_delegation(db,actor,study)
            if delegation is None: raise DomainError("resource_not_found",404)
            if owner: raise DomainError("forbidden",403)
            if write and not (delegation["role_ceiling"]=="writer" and delegation["effects"]&AGENT_WRITE_EFFECTS):
                raise DomainError("forbidden",403)
            subject=agent["delegator_actor_id"]
        role=self._membership_role(db,study,subject)
        if role is None: raise DomainError("resource_not_found",404)
        if owner and role!="owner" or write and role=="reader":
            raise DomainError("forbidden",403)

    def _membership_role(self,db,study,actor):
        row=db.execute("SELECT role FROM memberships WHERE study_id=? AND actor_id=?",(study,actor)).fetchone()
        return row["role"] if row else None

    # ---- Agent principals. An agent actor acts for exactly one delegating user; its
    # authority is the intersection of a live delegation (study, ceiling, effects) with that
    # user's current membership. Every function here runs in the caller's ``db``.

    def agent_actor(self,db,actor_id):
        """The agent actor row (``actor_id``, ``delegator_actor_id``, ``surface``,
        ``display_name``) of ``actor_id``, or ``None`` for any other actor (a human)."""
        row=db.execute("SELECT actor_id,delegator_actor_id,surface,display_name FROM agent_actors WHERE actor_id=?",
                       (actor_id,)).fetchone()
        return dict(row) if row else None

    def ensure_agent_actor(self,db,delegator_actor_id,surface,display_name):
        """The agent actor id of (``delegator_actor_id``, ``surface``), created on first use.

        The delegating user must exist; the display name is fixed at creation."""
        if surface not in AGENT_SURFACES or not isinstance(display_name,str) or not 1<=len(display_name)<=128:
            raise DomainError("invalid_request",400)
        row=db.execute("SELECT actor_id FROM agent_actors WHERE delegator_actor_id=? AND surface=?",
                       (delegator_actor_id,surface)).fetchone()
        if row:return row["actor_id"]
        if not db.execute("SELECT 1 FROM users WHERE actor_id=?",(delegator_actor_id,)).fetchone():
            raise DomainError("resource_not_found",404)
        actor=uid()
        db.execute("INSERT INTO agent_actors VALUES(?,?,?,?,?,?)",
                   (actor,"agent",delegator_actor_id,surface,display_name,time.time()))
        return actor

    def _delegation_row(self,row):
        result=dict(row);result["effects"]=agent_effects(result["allowed_effects"])
        return result

    def _live_study_delegation(self,db,agent_actor_id,study):
        row=db.execute("SELECT * FROM agent_delegations WHERE agent_actor_id=? AND study_id=? AND revoked_at IS NULL "
                       "AND expires_at>?",(agent_actor_id,study,time.time())).fetchone()
        return self._delegation_row(row) if row else None

    def live_delegation(self,db,delegation_id):
        """Delegation ``delegation_id`` with its ``effects`` while it is unrevoked and
        unexpired; ``None`` otherwise."""
        row=db.execute("SELECT * FROM agent_delegations WHERE delegation_id=? AND revoked_at IS NULL AND expires_at>?",
                       (delegation_id,time.time())).fetchone()
        return self._delegation_row(row) if row else None

    def create_delegation(self,db,agent_actor_id,study_id,role_ceiling,effects,expires_at):
        """Delegate ``study_id`` to the agent actor under ``role_ceiling`` and ``effects``.

        Created only for a human: the delegating user must be a member of the study (404
        otherwise), the ceiling may not exceed the user's role and the effects may not exceed
        the ceiling (403); unknown ceilings or effects and a past expiry are invalid (400).
        A live delegation of the same agent and study is replaced (revoked with its tokens
        and sessions), so at most one is live. Returns the new delegation."""
        agent=self.agent_actor(db,agent_actor_id)
        if agent is None:raise DomainError("resource_not_found",404)
        if (role_ceiling not in AGENT_CEILING_EFFECTS or isinstance(effects,(str,bytes)) or isinstance(expires_at,bool)
                or not isinstance(expires_at,(int,float)) or not expires_at>time.time()):
            raise DomainError("invalid_request",400)
        effects=frozenset(effects)
        if not effects or not effects<=AGENT_EFFECTS or "read" not in effects:raise DomainError("invalid_request",400)
        role=self._membership_role(db,study_id,agent["delegator_actor_id"])
        if role is None:raise DomainError("resource_not_found",404)
        if role not in _CEILING_ROLES[role_ceiling] or not effects<=AGENT_CEILING_EFFECTS[role_ceiling]:
            raise DomainError("forbidden",403)
        for row in db.execute("SELECT delegation_id FROM agent_delegations WHERE agent_actor_id=? AND study_id=? "
                              "AND revoked_at IS NULL",(agent_actor_id,study_id)).fetchall():
            self.revoke_delegation(db,row["delegation_id"],"replaced")
        delegation=uid()
        db.execute("INSERT INTO agent_delegations VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (delegation,agent_actor_id,agent["delegator_actor_id"],agent["surface"],study_id,role_ceiling,
                    json.dumps(sorted(effects),separators=(",",":")),time.time(),float(expires_at),None,None))
        return self._delegation_row(db.execute("SELECT * FROM agent_delegations WHERE delegation_id=?",(delegation,)).fetchone())

    def revoke_delegation(self,db,delegation_id,reason):
        """End delegation ``delegation_id``: its agent API
        sessions deleted in the same transaction. Idempotent; returns whether it was live."""
        if not isinstance(reason,str) or not 1<=len(reason)<=64:raise DomainError("invalid_request",400)
        now=time.time()
        changed=db.execute("UPDATE agent_delegations SET revoked_at=?,revoked_reason=? WHERE delegation_id=? AND revoked_at IS NULL",
                           (now,reason,delegation_id)).rowcount
        db.execute("DELETE FROM agent_api_sessions WHERE delegation_id=?",(delegation_id,))
        return bool(changed)

    def revoke_all_agent_credentials(self,db,reason):
        """End every live delegation with its agent API sessions (owner
        recovery)."""
        for row in db.execute("SELECT delegation_id FROM agent_delegations WHERE revoked_at IS NULL").fetchall():
            self.revoke_delegation(db,row["delegation_id"],reason)
        db.execute("DELETE FROM agent_api_sessions")

    def _delegated_studies(self,db,agent_actor_id):
        return [r["study_id"] for r in db.execute(
            "SELECT study_id FROM agent_delegations WHERE agent_actor_id=? AND revoked_at IS NULL AND expires_at>? "
            "ORDER BY study_id",(agent_actor_id,time.time()))]

    def _agent_listing_ids(self,db,actor):
        """For an agent actor, the delegated studies its delegating user is still a member of;
        ``None`` for a human."""
        agent=self.agent_actor(db,actor)
        if agent is None:return None
        return [sid for sid in self._delegated_studies(db,actor)
                if self._membership_role(db,sid,agent["delegator_actor_id"]) is not None]

    def _study_creation_delegation(self,db,agent,delegation_id):
        """Admit the one pre-study command of an agent actor, study creation: ``delegation_id``
        must be a live delegation of this agent holding ``record`` under the writer ceiling,
        and the delegating user must still be a writer or owner of the delegation's study."""
        delegation=self.live_delegation(db,delegation_id) if isinstance(delegation_id,str) else None
        if (delegation is None or delegation["agent_actor_id"]!=agent["actor_id"] or delegation["role_ceiling"]!="writer"
                or "record" not in delegation["effects"]
                or self._membership_role(db,delegation["study_id"],agent["delegator_actor_id"]) not in ("writer","owner")):
            raise DomainError("forbidden",403)
        return delegation

    def _agent_pre_study_outcome(self,db,agent,row):
        """The stored pre-study outcome for an agent actor, never authorizing the agent on the
        study it created: the receipt must be this agent's and, when it created a study, the
        delegating user must still be a member of it (404 otherwise)."""
        if row is None or row["actor_id"]!=agent["actor_id"]:raise DomainError("resource_not_found",404)
        if row["result"] and "study_id" in row["result"]:
            if self._membership_role(db,row["result"]["study_id"],agent["delegator_actor_id"]) is None:
                raise DomainError("resource_not_found",404)
        return row

    def study_row(self,db,sid):
        """The ``studies`` row of ``sid`` as a dict, read in the caller's ``db`` (for CAS on the
        study revision inside a command). Not authorized here: the caller has already
        authorized in the same transaction. Unknown studies are ``resource_not_found`` 404."""
        row=db.execute(
            "SELECT study_id,revision,name,description,boundary FROM studies WHERE study_id=?",
            (sid,)).fetchone()
        if row is None: raise DomainError("resource_not_found",404)
        return dict(row)

    def model_count(self, db, actor, sid):
        """Count associated models without reading or hydrating model versions."""
        self.authorize(db, actor, sid)
        return db.execute('SELECT count(*) FROM model_associations WHERE study_id=?',
                          (sid,)).fetchone()[0]

    def model_association(self,db,actor,sid,mid,*,write=False):
        """Authorized association of study ``sid`` with remote model ``mid``, read in ``db``.

        Authorizes ``actor`` first (``write`` requires a non-reader role: ``forbidden`` 403),
        then returns the ``model_associations`` row (``study_id``, ``model_id``,
        ``command_id``) as a dict. An unknown model and another study's model are the same
        undisclosed ``resource_not_found`` 404. The Coordinator writes associations; Store
        holds them and owns this read (Coordinator authorization, Configurations pins and
        write-time rechecks).
        """
        self.authorize(db,actor,sid,write=write)
        return self._association(db,sid,mid)

    def _association(self,db,sid,mid):
        row=db.execute("SELECT * FROM model_associations WHERE study_id=? AND model_id=?",(sid,mid)).fetchone()
        if row is None: raise DomainError("resource_not_found",404)
        return dict(row)

    def study(self,actor,sid):
        with self.connection() as db:
            self.authorize(db,actor,sid)
            return self.study_row(db,sid)

    def list_studies(self,actor):
        """The actor's studies by study id. An agent actor lists exactly its delegated
        studies its delegating user is still a member of, never the user's other studies."""
        with self.connection() as db:
            delegated=self._agent_listing_ids(db,actor)
            if delegated is not None:
                return [self.study_row(db,sid) for sid in delegated]
            return [dict(r) for r in db.execute(
                "SELECT s.study_id,s.revision,s.name,s.description,s.boundary FROM studies s "
                "JOIN memberships m USING(study_id) WHERE m.actor_id=? ORDER BY s.study_id",
                (actor,))]

    # ---- Study archive. Archive is study-wide presentation state: it hides a study
    # from the default listing and nothing else. It is not access control (every read and
    # command keeps its current authorization) and not deletion. ``study`` and
    # ``list_studies`` keep their exact recorded shape for internal callers and receipts; the
    # public reads ``study_read``/``study_listing`` add ``archived``.

    def study_archived(self,db,sid):
        """Whether ``sid`` is archived, read in the caller's ``db`` (no row: not archived).
        Not authorized here: the caller authorizes in the same transaction."""
        row=db.execute("SELECT archived FROM study_archive WHERE study_id=?",(sid,)).fetchone()
        return bool(row and row["archived"])

    def study_read(self,actor,sid):
        """Public study read: the study record plus its ``archived`` state (any member)."""
        with self.connection() as db:
            self.authorize(db,actor,sid)
            return dict(self.study_row(db,sid),archived=self.study_archived(db,sid))

    def study_listing(self,actor,archived):
        """The actor's studies whose archive state equals ``archived``, by study id."""
        with self.connection() as db:
            delegated=self._agent_listing_ids(db,actor)
            if delegated is not None:
                return [dict(self.study_row(db,sid),archived=self.study_archived(db,sid)) for sid in delegated
                        if self.study_archived(db,sid)==bool(archived)]
            return [dict(r,archived=bool(r["archived"])) for r in db.execute(
                "SELECT s.study_id,s.revision,s.name,s.description,s.boundary,"
                "COALESCE(a.archived,0) AS archived FROM studies s JOIN memberships m USING(study_id) "
                "LEFT JOIN study_archive a USING(study_id) WHERE m.actor_id=? AND COALESCE(a.archived,0)=? "
                "ORDER BY s.study_id",(actor,int(bool(archived))))]

    def set_study_archived(self,actor,sid,command,archived):
        """``archive_study`` (``archived=True``) or ``restore_study`` as one idempotent command.

        Same authorization as ``update_study`` (owner or writer; reader 403; non-member and
        unknown study the same undisclosed 404). Idempotent by ``command_id`` in category
        ``study_archive``: a replay returns the original outcome; the same id for the other
        operation is ``command_payload_conflict``. Target-state semantics: when the study is
        already in the requested state the command commits without touching the row, which
        keeps the command, actor and time of the transition that actually happened. The
        study record and its revision never change. Returns the study with ``archived``.
        """
        archived=bool(archived)
        def apply(db):
            if self.study_archived(db,sid)!=archived:
                at=datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
                db.execute("INSERT INTO study_archive VALUES(?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET "
                           "archived=excluded.archived,command_id=excluded.command_id,actor_id=excluded.actor_id,"
                           "changed_at=excluded.changed_at",(sid,int(archived),command,actor,at))
            return dict(self.study_row(db,sid),archived=archived)
        return self.command(actor,sid,"study_archive",command,
                            dict(operation="archive_study" if archived else "restore_study",target=sid),apply)

    def _scope(self,actor,study):return study or "actor:"+actor

    def command_receipt(self,db,scope,category,command):
        """The receipt of ``command`` in ``scope`` (a study id, or ``actor:<id>`` before a study
        exists) and ``category``, read in the caller's ``db``, with ``result``, ``error`` and
        ``request`` decoded; ``None`` when absent. Not authorized here: the caller authorizes in
        the same transaction (public reads use ``receipt``)."""
        row=db.execute("SELECT * FROM receipts WHERE scope=? AND category=? AND command_id=?",(scope,category,command)).fetchone()
        if row is None:return None
        result=dict(row)
        for key in ("result","error","request"):
            result[key]=json.loads(result[key]) if result[key] is not None else None
        return result

    # Temporary test-only alias (receipt assertions in tests); production code
    # uses ``command_receipt`` (test_module_boundaries pins both facts).
    _receipt=command_receipt

    def command_receipts(self, db, scope, category, commands):
        """Read a bounded set in one transaction; callers authorize the scope first."""
        commands = list(dict.fromkeys(commands))
        if len(commands) > 10000:
            raise DomainError('limit_exceeded', 413)
        rows = db.execute(
            'SELECT * FROM receipts WHERE scope=? AND category=? '
            'AND command_id IN (SELECT value FROM json_each(?))',
            (scope, category, json.dumps(commands)),
        ).fetchall()
        result = {}
        for row in rows:
            value = dict(row)
            for key in ('result', 'error', 'request'):
                value[key] = json.loads(value[key]) if value[key] is not None else None
            result[value['command_id']] = value
        return result

    def receipt(self,actor,study,category,command):
        row=self.visible_receipt(actor,study,category,command)
        if row is None:raise DomainError("resource_not_found",404)
        return row

    def visible_receipt(self,actor,study,category,command):
        """``receipt`` for the receipt reads: the same authorization and the same scoped 404
        for a reader who may not see the scope (a non-member, a foreign study, an agent outside
        its pre-study rules, a created study the reader no longer belongs to), but ``None``
        for a missing receipt in a scope the reader may see."""
        with self.connection() as db:
            if study:self.authorize(db,actor,study)
            agent=None if study else self.agent_actor(db,actor)
            if agent is not None and category!="study_create":
                raise DomainError("resource_not_found",404)
            row=self.command_receipt(db,self._scope(actor,study),category,command)
            if row is None:return None
            if agent is not None:return self._agent_pre_study_outcome(db,agent,row)
            # Pre-study receipts also re-check membership in the created study.
            if not study and row["result"] and "study_id" in row["result"]:
                self.authorize(db,actor,row["result"]["study_id"])
            return row

    def replay(self,actor,study,category,command,payload,owner=False):
        with self.connection() as db:
            if study:self.authorize(db,actor,study,write=True,owner=owner)
            self._analysis_command(db,actor,study,category,command,payload)
            agent=None if study else self.agent_actor(db,actor)
            if agent is not None and category!="study_create":raise DomainError("forbidden",403)
            row=self.command_receipt(db,self._scope(actor,study),category,command)
            if row:
                if row["payload_digest"]!=digest(dict(major="1",scope=self._scope(actor,study),category=category,payload=payload)):raise DomainError("command_payload_conflict")
                if agent is not None:self._agent_pre_study_outcome(db,agent,row)
                elif not study and row["result"] and "study_id" in row["result"]:
                    self.authorize(db,actor,row["result"]["study_id"],write=True)
                if row["error"]:raise DomainError(**row["error"])
            return row

    # The agent runtime's attribution recorder, set by the composition root (``api``), which
    # ``store`` cannot import. An agent actor's write is refused while it is unset, so no
    # agent-written record is ever stored without saying which agent wrote it.
    attribution_recorder=None

    def attribute(self,db,actor,study,category,command,records):
        """Record in the caller's transaction that the agent ``actor`` wrote ``records``
        (``(record_kind, record_id, version_id)`` triples) through receipt (``study``,
        ``category``, ``command``); a human actor's write records nothing. The entry names the
        agent and its delegating user, so an agent-written record never reads as person-written."""
        agent=self.agent_actor(db,actor)
        if agent is None:return
        if self.attribution_recorder is None:
            raise DomainError("internal_error",500,outcome="unknown")
        for kind,record_id,version_id in records:
            # A pre-study command (``study`` None) creates one study: the entry's study is it.
            self.attribution_recorder(db,dict(
                study_id=study or record_id,record_kind=kind,record_id=record_id,
                version_id=version_id,command_category=category,command_id=command,
                agent_actor_id=actor,agent_display_name=agent["display_name"],
                delegator_actor_id=agent["delegator_actor_id"]))

    def command(self,actor,study,category,command,payload,operation,*,owner=False,receipt_state="committed",request=None,
                delegation_id=None,attribute=None,admission=None):
        """Run ``operation(db)`` once under receipt (scope, ``category``, ``command``) and return
        its result; a repeat with the same payload returns the stored outcome. ``attribute``
        maps an accepted result to the ``(record_kind, record_id, version_id)`` triples an agent
        actor wrote, recorded in the same transaction (``attribute``)."""
        error=None
        with self.connection(write=True) as db:
            if study:self.authorize(db,actor,study,write=True,owner=owner)
            self._analysis_command(db,actor,study,category,command,payload)
            agent=None if study else self.agent_actor(db,actor)
            if agent is not None:
                # The only pre-study command an agent actor may issue is study creation under
                # its session's live writer delegation; every other one is refused before any
                # receipt is read.
                if category!="study_create":raise DomainError("forbidden",403)
                self._study_creation_delegation(db,agent,delegation_id)
            scope=self._scope(actor,study)
            old=self.command_receipt(db,scope,category,command)
            if old:
                if old["payload_digest"]!=digest(dict(major="1",scope=scope,category=category,payload=payload)):raise DomainError("command_payload_conflict")
                if agent is not None:self._agent_pre_study_outcome(db,agent,old)
                elif not study and old["result"] and "study_id" in old["result"]:
                    self.authorize(db,actor,old["result"]["study_id"],write=True)
                if old["error"]:raise DomainError(**old["error"])
                return old["result"]
            if admission is not None:
                admission(db)
            db.execute("SAVEPOINT domain_write")
            try:
                result=operation(db)
                state=receipt_state
            except DomainError as exc:
                db.execute("ROLLBACK TO domain_write")
                error=exc;result=None;state="rejected"
            db.execute("RELEASE domain_write")
            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)",
                (scope,category,command,actor,digest(dict(major="1",scope=scope,category=category,payload=payload)),state,
                 json.dumps(result) if result is not None else None,
                 json.dumps(error.data()) if error else None,json.dumps(request) if request else None))
            if error is None and category == 'analysis_execution':
                for child_command, run_id in (request or {}).get('reused_runs', {}).items():
                    db.execute('INSERT INTO analysis_execution_children '
                               '(study_id,analysis_command,child_category,child_command,run_id) '
                               "VALUES(?,?,'run',?,?) ON CONFLICT DO NOTHING",
                               (study,command,child_command,run_id))
            if error is None and _analysis_authority.get() is not None:
                authority = _analysis_authority.get()
                db.execute('INSERT INTO analysis_execution_children '
                           '(study_id,analysis_command,child_category,child_command,run_id) '
                           'VALUES(?,?,?,?,?)',
                           (study,authority[3],category,command,result.get('run_id')))
            if error is None and attribute is not None:
                self.attribute(db,actor,study,category,command,attribute(result))
        if error:raise error
        return result

    def cas(self,current,expected):
        if expected!=current:raise DomainError("stale_revision",current_revision=current)

    def create_study(self,actor,command,name,*,delegation_id=None):
        """Create a study owned by ``actor``, or, for an agent actor, by its delegating user.

        An agent actor needs ``delegation_id``: its session's live delegation holding
        ``record`` under the writer ceiling while the delegating user is a writer or owner of
        that delegation's study (403 otherwise). The Owner membership goes to the delegating
        user and none to the agent; the receipt keeps the agent as actor in its pre-study
        scope; the delegation is unchanged, so the agent gains no access to the new study."""
        def apply(db):
            agent=self.agent_actor(db,actor)
            sid=uid()
            db.execute(
                "INSERT INTO studies(study_id,revision,name,description,boundary) VALUES(?,?,?,?,?)",
                (sid,uid(),name,"",""))
            db.execute("INSERT INTO memberships VALUES(?,?,?)",(sid,agent["delegator_actor_id"] if agent else actor,"owner"))
            return self.study_row(db,sid)
        return self.command(actor,None,"study_create",command,dict(operation="create_study",name=name),apply,
                            delegation_id=delegation_id,
                            attribute=lambda r:[("study",r["study_id"],None)])

    def set_membership(self,actor,sid,command,expected,target,role):
        if role not in {"owner","writer","reader",None}:raise DomainError("invalid_request",400)
        def apply(db):
            row=self.study_row(db,sid);self.cas(row["revision"],expected)
            if role is None:db.execute("DELETE FROM memberships WHERE study_id=? AND actor_id=?",(sid,target))
            else:db.execute("INSERT INTO memberships VALUES(?,?,?) ON CONFLICT(study_id,actor_id) DO UPDATE SET role=excluded.role",(sid,target,role))
            if not db.execute("SELECT 1 FROM memberships WHERE study_id=? AND role='owner'",(sid,)).fetchone():
                raise DomainError("reference_conflict")
            db.execute("UPDATE studies SET revision=? WHERE study_id=?",(uid(),sid))
            return self.study_row(db,sid)
        return self.command(actor,sid,"membership",command,
                            dict(operation="membership",target=target,expected_revision=expected,role=role),apply,owner=True)

    def resolve_evidence_scope(self,actor,sid,scope,coordinator):
        """Resolve immutable owner records; never substitute a current model draft."""
        kind=scope['kind']
        with self.connection() as db:
            self.authorize(db,actor,sid,write=True)
            if scope['study_id']!=sid:raise DomainError('resource_not_found',404)
            if kind=='study':return
            if kind in {'configuration','criterion'}:
                row=db.execute('SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?',
                    (sid,scope['configuration_revision_id'])).fetchone()
                if row is None:raise DomainError('resource_not_found',404)
                configuration=json.loads(row['payload'])['configuration']
                # Configuration 6 carries no criteria to scope evidence to.
                if kind=='criterion' and (configuration['schema_version']=='6' or not any(c['criterion_id']==scope['criterion_id'] for c in configuration['criteria'])):
                    raise DomainError('resource_not_found',404)
                return
            if kind=='run':
                if not db.execute('SELECT 1 FROM run_associations WHERE study_id=? AND run_id=?',(sid,scope['run_id'])).fetchone():
                    raise DomainError('resource_not_found',404)
                return
            self._association(db,sid,scope['model_id'])
        # The exact remote revision is immutable. No local write lock spans I/O.
        if coordinator is None:raise DomainError('backend_unavailable',503,outcome='unknown')
        model=coordinator.read(actor,sid,scope['model_id'],'/revisions/'+scope['model_revision_id'],response_schema='ModelRevisionResponse5')['data']
        if (model['model_id']!=scope['model_id'] or model['model_revision_id']!=scope['model_revision_id']
            or model['digest']!=digest({k:v for k,v in model.items() if k!='digest'})):
            raise DomainError('backend_unavailable',503,outcome='unknown')
        found=kind=='model_revision'
        if kind=='definition_version':
            found=any(d['definition_id']==scope['definition_id'] and d['definition_version_id']==scope['definition_version_id'] for d in model['definitions'])
        if kind in {'instance','port'}:
            instance=next((i for i in model['instances'] if i['instance_id']==scope['instance_id']),None)
            found=instance is not None
            if found and kind=='port':
                found=any(d['definition_version_id']==instance['definition_version_id'] and
                    any(p['port_id']==scope['port_id'] for p in d['ports']) for d in model['definitions'])
        if kind=='connection':found=any(c['connection_id']==scope['connection_id'] for c in model['connections'])
        if not found:raise DomainError('resource_not_found',404)

    def _evidence_scope_local(self,db,sid,scope):
        """Capture only locally authoritative references; also used under CAS."""
        if scope['study_id']!=sid:raise DomainError('resource_not_found',404)
        result=dict(study=self.study_row(db,sid))
        kind=scope['kind']
        if kind in {'configuration','criterion','run'}:
            revision=scope.get('configuration_revision_id')
            if kind=='run':
                row=db.execute('SELECT configuration_revision_id FROM run_associations WHERE study_id=? AND run_id=?',
                               (sid,scope['run_id'])).fetchone()
                if row is None:raise DomainError('resource_not_found',404)
                revision=row['configuration_revision_id'];result['run_revision']=revision
            row=db.execute('SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?',
                           (sid,revision)).fetchone()
            if row is None:raise DomainError('resource_not_found',404)
            result['frozen']=json.loads(row['payload'])
        elif kind!='study':
            self._association(db,sid,scope['model_id'])
            result['model_id']=scope['model_id']
        return result

    def _evidence_context(self,actor,sid,scope,coordinator):
        """Resolve immutable labels without a local write transaction or live names."""
        with self.connection() as db:
            self.authorize(db,actor,sid,write=True)
            local=self._evidence_scope_local(db,sid,scope)
        labels=[]
        def label(kind,resource,version,name):
            labels.append(dict(kind=kind,resource_id=resource,version_id=version,name=name))
        label('study',sid,None,local['study']['name'])
        kind=scope['kind'];model=None;config=None
        if 'frozen' in local:
            config=local['frozen']['configuration'];model=local['frozen']['model_snapshot']
            validate('ConfigurationRevisionRead6',config)
            if (config['study_id']!=sid or config['configuration_revision_id']!=
                scope.get('configuration_revision_id',local.get('run_revision')) or
                config['digest']!=digest({k:v for k,v in config.items() if k!='digest'})):
                raise DomainError('reference_conflict')
        elif 'model_id' in local:
            if coordinator is None:raise DomainError('backend_unavailable',503,outcome='unknown')
            model=coordinator.read(actor,sid,scope['model_id'],'/revisions/'+scope['model_revision_id'],
                                   response_schema='ModelRevisionResponse5')['data']
            # Own a detached immutable copy, never a mutable adapter response alias.
            model=json.loads(canonical(model))
        if model is not None:
            validate('ModelRevisionRead5',model,remote=True)
            expected=config if config is not None else scope
            if (model['model_id']!=expected['model_id'] or model['model_revision_id']!=expected['model_revision_id'] or
                model['digest']!=digest({k:v for k,v in model.items() if k!='digest'})):
                raise DomainError('reference_conflict')
            def exact(items,**keys):
                found=[item for item in items if all(item.get(k)==v for k,v in keys.items())]
                if len(found)!=1:raise DomainError('resource_not_found',404)
                return found[0]
            root=exact(model['instances'],instance_id=model['root_instance_id'])
            label('model',model['model_id'],model['model_revision_id'],root['name'])
            if kind=='definition_version':
                definition=exact(model['definitions'],definition_id=scope['definition_id'],definition_version_id=scope['definition_version_id'])
                label('definition',definition['definition_id'],definition['definition_version_id'],definition['name'])
            if kind in {'instance','port'}:
                instance=exact(model['instances'],instance_id=scope['instance_id'])
                definition=exact(model['definitions'],definition_version_id=instance['definition_version_id'])
                label('definition',definition['definition_id'],definition['definition_version_id'],definition['name'])
                label('instance',instance['instance_id'],model['model_revision_id'],instance['name'])
                if kind=='port':
                    port=exact(definition['ports'],port_id=scope['port_id'])
                    label('port',port['port_id'],definition['definition_version_id'],port['name'])
            if kind=='connection' or kind=='criterion':
                def endpoint(ref):
                    instance=exact(model['instances'],instance_id=ref['instance_id'])
                    definition=exact(model['definitions'],definition_version_id=instance['definition_version_id'])
                    port=exact(definition['ports'],port_id=ref['port_id'])
                    return instance['name']+'.'+port['name']
            if kind=='connection':
                connection=exact(model['connections'],connection_id=scope['connection_id'])
                label('connection',connection['connection_id'],model['model_revision_id'],
                      endpoint(connection['source_ref'])+' → '+endpoint(connection['target_ref']))
            if config is not None:
                label('configuration',config['configuration_id'],config['configuration_revision_id'],config['name'])
                if kind=='criterion':
                    criterion=exact([] if config['schema_version']=='6' else config['criteria'],criterion_id=scope['criterion_id'])
                    label('criterion',criterion['criterion_id'],config['configuration_revision_id'],
                          endpoint(criterion['target'])+' '+criterion['operator']+' '+str(criterion['threshold'])+' '+criterion['units'])
                if kind=='run':
                    label('run',scope['run_id'],None,'Run '+scope['run_id'])
        context=dict(schema_version='1',label=' / '.join(item['name'] for item in labels),resource_labels=labels)
        validate('RecordedEvidenceContext1',context)
        return context,local,model

    def _recheck_evidence_context(self,db,sid,scope,resolved):
        _,local,model=resolved
        if self._evidence_scope_local(db,sid,scope)!=local:raise DomainError('reference_conflict')
        if model is not None and model['digest']!=digest({k:v for k,v in model.items() if k!='digest'}):
            raise DomainError('reference_conflict')

    def _evidence_head(self,db,sid,family):
        row=db.execute('SELECT head FROM evidence_families WHERE study_id=? AND evidence_id=?',(sid,family)).fetchone()
        if row:
            head=db.execute('SELECT payload FROM evidence WHERE study_id=? AND evidence_id=? AND evidence_version_id=?',
                            (sid,family,row['head'])).fetchone()
            if head is None:raise DomainError('reference_conflict')
            return json.loads(head['payload'])
        legacy=db.execute('SELECT payload FROM evidence WHERE study_id=? AND evidence_id=? LIMIT 2',(sid,family)).fetchall()
        if not legacy:raise DomainError('resource_not_found',404)
        if len(legacy)!=1:raise DomainError('reference_conflict')
        return json.loads(legacy[0]['payload'])

    def evidence_family(self,actor,sid,family):
        with self.connection() as db:
            self.authorize(db,actor,sid)
            head=self._evidence_head(db,sid,family)
            return dict(family_schema_version='3',evidence_id=family,study_id=sid,
                        head_evidence_version_id=head['evidence_version_id'],head=head)

    def evidence_versions(self,actor,sid,family,query):
        return self.list_evidence(actor,sid,query,family_id=family)

    @staticmethod
    def _evidence_cursor(value):
        return base64.urlsafe_b64encode(canonical(value)).decode().rstrip('=')

    def list_evidence(self,actor,sid,query,*,family_id=None):
        """Bound the selected SQL page; filters compare exact immutable IDs offline."""
        pairs=list(query)
        with self.connection() as db:
            self.authorize(db,actor,sid)
            ids={'model_id','model_revision_id','instance_id','port_id','configuration_revision_id','run_id'}
            allowed=ids|{'cursor','limit','scope_kind','legacy_scope','view'}
            if any(k not in allowed for k,_ in pairs) or len({k for k,_ in pairs})!=len(pairs):
                raise DomainError('invalid_request',400)
            values=dict(pairs);limit=values.pop('limit','50');cursor=values.pop('cursor',None)
            view=values.pop('view','versions' if family_id else 'heads')
            if view not in {'heads','versions'} or family_id and (view!='versions' or values):raise DomainError('invalid_request',400)
            if not re.fullmatch(r'(?:[1-9]|[1-9][0-9]|100)',limit):raise DomainError('invalid_request',400)
            def identifier(value):
                try:
                    if str(UUID(value))!=value:raise ValueError()
                except ValueError:raise DomainError('invalid_request',400) from None
            if family_id is not None:
                identifier(family_id);self._evidence_head(db,sid,family_id)
            for key in ids&values.keys():identifier(values[key])
            kind=values.get('scope_kind')
            model_ids={'model_id','model_revision_id'}
            permitted={'study':set(),'model_revision':model_ids,'definition_version':model_ids,
                'instance':model_ids|{'instance_id'},'port':model_ids|{'instance_id','port_id'},
                'connection':model_ids,'configuration':{'configuration_revision_id'},'criterion':{'configuration_revision_id'},
                'run':{'run_id'},'legacy':set()}
            selected=ids&values.keys()
            if kind is not None and (kind not in permitted or not selected<=permitted[kind]):raise DomainError('invalid_request',400)
            if ('model_revision_id' in selected and 'model_id' not in selected
                or 'instance_id' in selected and not model_ids<=selected
                or 'port_id' in selected and not model_ids|{'instance_id'}<=selected
                or 'configuration_revision_id' in selected and bool(selected-{'configuration_revision_id'})
                or 'run_id' in selected and bool(selected-{'run_id'})):
                raise DomainError('invalid_request',400)
            clauses=['e.study_id=?'];params=[sid]
            if family_id is not None:
                clauses.append('e.evidence_id=?');params.append(family_id)
            if 'legacy_scope' in values or kind=='legacy':
                if selected or kind not in {None,'legacy'}:raise DomainError('invalid_request',400)
                clauses.append("json_type(payload,'$.evidence_schema_version') IS NULL")
                if 'legacy_scope' in values:
                    legacy=values['legacy_scope']
                    if legacy!='null':identifier(legacy)
                    clauses.append("json_extract(payload,'$.scope') IS NOT DISTINCT FROM ?");params.append(None if legacy=='null' else legacy)
            elif kind is not None or selected:
                clauses.append("json_extract(payload,'$.evidence_schema_version') IN ('2','3')")
                if kind is not None:
                    clauses.append("json_extract(payload,'$.resource_scope.kind')=?");params.append(kind)
                for key in sorted(selected):
                    # Keys are from the fixed allowlist above; values are bound parameters.
                    clauses.append("json_extract(payload,'$.resource_scope."+key+"')=?");params.append(values[key])
            binding=dict(cursor_version='1',study_id=sid,actor_id=actor,view=view,family_id=family_id,filter_digest=digest(values))
            high=db.execute('SELECT COALESCE(MAX(rowid),0) FROM evidence WHERE study_id=?',(sid,)).fetchone()[0]
            descending=view=='versions';position=high+1 if descending else 0
            if cursor is not None:
                try:
                    if not isinstance(cursor,str) or len(cursor)>2048:raise ValueError()
                    token=json.loads(base64.b64decode(cursor+'='*(-len(cursor)%4),altchars=b'-_',validate=True))
                    if (not isinstance(token,dict) or set(token)!=set(binding)|{'high_water','last_rowid'} or
                        any(token[k]!=v for k,v in binding.items()) or self._evidence_cursor(token)!=cursor or
                        any(type(token[k]) is not int or not 0<=token[k]<=2**63-1 for k in ('high_water','last_rowid')) or
                        token['last_rowid']>token['high_water']):raise ValueError()
                    high=token['high_water'];position=token['last_rowid']
                except (ValueError,TypeError,UnicodeError,OverflowError,RecursionError):raise DomainError('invalid_request',400) from None
            if view=='heads':
                # Stable family creation order; the selected head may advance after
                # page one. All filtering and ordering remains inside bounded SQL.
                origin='(SELECT MIN(o.rowid) FROM evidence o WHERE o.study_id=e.study_id AND o.evidence_id=e.evidence_id)'
                source='evidence e LEFT JOIN evidence_families f ON f.study_id=e.study_id AND f.evidence_id=e.evidence_id'
                clauses.append('(e.evidence_version_id=f.head OR (f.head IS NULL AND e.rowid='+origin+'))')
                # Reject ambiguous unindexed families, never invent a latest head.
                ambiguous=db.execute('SELECT 1 FROM evidence e LEFT JOIN evidence_families f ON f.study_id=e.study_id AND f.evidence_id=e.evidence_id '
                    'WHERE e.study_id=? AND f.head IS NULL AND e.rowid<=? AND EXISTS '
                    '(SELECT 1 FROM evidence o WHERE o.study_id=e.study_id AND o.evidence_id=e.evidence_id AND o.rowid!=e.rowid) LIMIT 1',(sid,high)).fetchone()
                if ambiguous:raise DomainError('reference_conflict')
            else:origin='e.rowid';source='evidence e'
            clauses.extend([origin+'<=?',origin+(' < ?' if descending else ' > ?')]);params.extend([high,position])
            where=' AND '.join(clauses)
            selected_rows=db.execute('SELECT e.payload,'+origin+' AS position FROM '+source+' WHERE '+where+
                ' ORDER BY position '+('DESC' if descending else 'ASC')+' LIMIT ?',[*params,int(limit)+1]).fetchall()
            page=selected_rows[:int(limit)]
            return dict(data=[json.loads(row['payload']) for row in page],
                next_cursor=self._evidence_cursor(dict(binding,high_water=high,last_rowid=page[-1]['position']))
                if len(selected_rows)>int(limit) else None)

    def add_evidence(self,actor,sid,command,note,*,coordinator=None):
        with self.connection() as db:self.authorize(db,actor,sid,write=True)
        validate('EvidenceCreate3' if note.get('evidence_schema_version')=='3' else 'EvidenceCreate',dict(command_id=command,**note))
        read_content(note["content"])
        payload=dict(operation="create_evidence",note=note)
        previous=self.replay(actor,sid,"evidence",command,payload)
        if previous:return previous["result"]
        if note.get('evidence_schema_version')=='2':
            self.resolve_evidence_scope(actor,sid,note['resource_scope'],coordinator)
        resolved=self._evidence_context(actor,sid,note['resource_scope'],coordinator) if note.get('evidence_schema_version')=='3' else None
        def apply(db):
            if resolved:self._recheck_evidence_context(db,sid,note['resource_scope'],resolved)
            result=dict(note,evidence_id=uid(),evidence_version_id=uid(),study_id=sid)
            if resolved:
                result.update(parent_evidence_version_id=None,recorded_context=resolved[0])
                validate('EvidenceRecord3',result)
            db.execute("INSERT INTO evidence VALUES(?,?,?,?)",
                       (result["evidence_version_id"],result["evidence_id"],sid,json.dumps(result)))
            if resolved:db.execute('INSERT INTO evidence_families VALUES(?,?,?)',(result['evidence_id'],sid,result['evidence_version_id']))
            return result
        return self.command(actor,sid,"evidence",command,payload,apply,
                            attribute=_evidence_written)

    def revise_evidence(self,actor,sid,family,command,expected,note,*,coordinator=None):
        with self.connection() as db:self.authorize(db,actor,sid,write=True)
        validate('EvidenceRevise3',dict(note,command_id=command,expected_revision=expected))
        read_content(note['content'])
        payload=dict(operation='revise_evidence',family_id=family,expected_revision=expected,note=note)
        previous=self.replay(actor,sid,'evidence',command,payload)
        if previous:return previous['result']
        self.evidence_family(actor,sid,family)
        resolved=self._evidence_context(actor,sid,note['resource_scope'],coordinator)
        def apply(db):
            old=self._evidence_head(db,sid,family)
            self.cas(old['evidence_version_id'],expected)
            self._recheck_evidence_context(db,sid,note['resource_scope'],resolved)
            result=dict(note,evidence_id=family,evidence_version_id=uid(),study_id=sid,
                        parent_evidence_version_id=old['evidence_version_id'],recorded_context=resolved[0])
            validate('EvidenceRecord3',result)
            db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(result['evidence_version_id'],family,sid,json.dumps(result)))
            db.execute('INSERT INTO evidence_families VALUES(?,?,?) ON CONFLICT(evidence_id) DO UPDATE SET head=excluded.head',
                       (family,sid,result['evidence_version_id']))
            return result
        return self.command(actor,sid,'evidence',command,payload,apply,
                            attribute=_evidence_written)

    def _evidence_payload(self,db,sid,version):
        """Stored payload text of ``version`` in the caller's authorized connection.

        ``None`` when no study holds ``version``; ``ForeignEvidence`` when another study does.
        """
        row=db.execute('SELECT study_id,payload FROM evidence WHERE evidence_version_id=?',(version,)).fetchone()
        if row is None:return None
        if row['study_id']!=sid:raise ForeignEvidence()
        return row['payload']

    def evidence_record(self,db,actor,sid,version):
        """Exact immutable evidence version ``version`` of study ``sid``, for snapshot creation
        and citation checks. The caller holds ``db`` and coordinates the transaction.

        Authorizes ``actor`` (read) in ``db`` before any lookup. Returns the validated record
        (``exact_evidence``), or ``None`` when no study holds ``version``. Raises the
        authorization ``DomainError``, ``ForeignEvidence`` (404) when another study holds it,
        and ``exact_evidence``'s integrity errors.
        """
        self.authorize(db,actor,sid)
        payload=self._evidence_payload(db,sid,version)
        return None if payload is None else exact_evidence(payload,sid,version)

    def evidence_version(self,actor,sid,version):
        """The stored evidence version exactly as recorded (public read, legacy consistency
        checks). Not re-validated: snapshot creation uses ``evidence_record``. Absent and
        another study's versions are both ``resource_not_found`` 404."""
        with self.connection() as db:
            self.authorize(db,actor,sid)
            payload=self._evidence_payload(db,sid,version)
            if payload is None:raise DomainError("resource_not_found",404)
            return json.loads(payload)
