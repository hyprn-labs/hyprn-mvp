-- The migration authority owns all objects. The runtime roles are created by
-- infrastructure; neither role inherits the migration login or BYPASSRLS.
CREATE TABLE users(
 actor_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT,
 failures INTEGER NOT NULL DEFAULT 0, locked_until DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE TABLE sessions(
 token_hash TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(actor_id),
 csrf_hash TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE studies(
 study_id TEXT PRIMARY KEY, revision TEXT NOT NULL, name TEXT NOT NULL,
 description TEXT NOT NULL, boundary TEXT NOT NULL,
 owner_actor_id TEXT NOT NULL DEFAULT current_setting('hyprn.actor_id',true)
 REFERENCES users(actor_id),
 created_transaction BIGINT NOT NULL DEFAULT txid_current()
);
CREATE TABLE memberships(
 study_id TEXT NOT NULL REFERENCES studies(study_id), actor_id TEXT NOT NULL REFERENCES users(actor_id),
 role TEXT NOT NULL CHECK(role IN ('owner','writer','reader')),
 PRIMARY KEY(study_id,actor_id)
);
CREATE TABLE receipts(
 scope TEXT NOT NULL, category TEXT NOT NULL, command_id TEXT NOT NULL,
 actor_id TEXT NOT NULL, payload_digest TEXT NOT NULL, state TEXT NOT NULL,
 result TEXT, error TEXT, request TEXT, PRIMARY KEY(scope,category,command_id)
);
CREATE TABLE study_archive(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 archived INTEGER NOT NULL CHECK(archived IN (0,1)),
 command_id TEXT NOT NULL, actor_id TEXT NOT NULL, changed_at TEXT NOT NULL
);
CREATE TABLE agent_actors(
 actor_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='agent'),
 delegator_actor_id TEXT NOT NULL REFERENCES users(actor_id),
 surface TEXT NOT NULL CHECK(surface IN ('claude_managed','openai_agents')),
 display_name TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
 UNIQUE(delegator_actor_id,surface)
);
CREATE TABLE agent_delegations(
 delegation_id TEXT PRIMARY KEY, agent_actor_id TEXT NOT NULL REFERENCES agent_actors(actor_id),
 delegator_actor_id TEXT NOT NULL REFERENCES users(actor_id),
 surface TEXT NOT NULL CHECK(surface IN ('claude_managed','openai_agents')),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 role_ceiling TEXT NOT NULL CHECK(role_ceiling IN ('reader','writer')),
 allowed_effects TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
 expires_at DOUBLE PRECISION NOT NULL, revoked_at DOUBLE PRECISION, revoked_reason TEXT,
 CHECK((revoked_at IS NULL)=(revoked_reason IS NULL))
);
CREATE UNIQUE INDEX agent_delegations_one_live
 ON agent_delegations(agent_actor_id,study_id) WHERE revoked_at IS NULL;
CREATE TABLE agent_api_sessions(
 token_hash TEXT PRIMARY KEY, csrf_hash TEXT NOT NULL,
 delegation_id TEXT NOT NULL REFERENCES agent_delegations(delegation_id),
 actor_id TEXT NOT NULL REFERENCES agent_actors(actor_id),
 read_only INTEGER NOT NULL CHECK(read_only IN (0,1)), expires_at DOUBLE PRECISION NOT NULL
);

CREATE FUNCTION hyprn_actor() RETURNS TEXT LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('hyprn.actor_id',true),'') $$;
REVOKE ALL ON FUNCTION hyprn_actor() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_actor() TO hyprn_request;

ALTER TABLE studies ENABLE ROW LEVEL SECURITY;
ALTER TABLE studies FORCE ROW LEVEL SECURITY;
CREATE POLICY studies_read ON studies FOR SELECT TO hyprn_request
 USING ((owner_actor_id=hyprn_actor() AND created_transaction=txid_current()) OR EXISTS(
 SELECT 1 FROM memberships m WHERE m.study_id=studies.study_id AND m.actor_id=hyprn_actor()));
CREATE POLICY studies_create ON studies FOR INSERT TO hyprn_request
 WITH CHECK(owner_actor_id=hyprn_actor());
CREATE POLICY studies_update ON studies FOR UPDATE TO hyprn_request
 USING(EXISTS(SELECT 1 FROM memberships m WHERE m.study_id=studies.study_id
 AND m.actor_id=hyprn_actor() AND m.role IN ('owner','writer')));
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY memberships_read ON memberships FOR SELECT TO hyprn_request
 USING(actor_id=hyprn_actor());
CREATE POLICY memberships_create ON memberships FOR INSERT TO hyprn_request
 WITH CHECK(EXISTS(SELECT 1 FROM studies s
 WHERE s.study_id=memberships.study_id AND
 ((s.owner_actor_id=hyprn_actor() AND s.created_transaction=txid_current())
 OR EXISTS(SELECT 1 FROM memberships m WHERE m.study_id=s.study_id
 AND m.actor_id=hyprn_actor() AND m.role='owner'))));
ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY receipts_scope ON receipts TO hyprn_request
 USING(actor_id=hyprn_actor()) WITH CHECK(actor_id=hyprn_actor());
ALTER TABLE study_archive ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_archive FORCE ROW LEVEL SECURITY;
CREATE POLICY archive_scope ON study_archive TO hyprn_request
 USING(EXISTS(SELECT 1 FROM studies s WHERE s.study_id=study_archive.study_id))
 WITH CHECK(EXISTS(SELECT 1 FROM memberships m WHERE m.study_id=study_archive.study_id
 AND m.actor_id=hyprn_actor() AND m.role IN ('owner','writer')));
ALTER TABLE agent_actors ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_actors FORCE ROW LEVEL SECURITY;
CREATE POLICY actors_read ON agent_actors FOR SELECT TO hyprn_request
 USING(actor_id=hyprn_actor() OR delegator_actor_id=hyprn_actor());
ALTER TABLE agent_delegations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_delegations FORCE ROW LEVEL SECURITY;
CREATE POLICY delegations_read ON agent_delegations FOR SELECT TO hyprn_request
 USING(agent_actor_id=hyprn_actor() OR delegator_actor_id=hyprn_actor());
CREATE POLICY delegations_auth ON agent_delegations FOR SELECT TO hyprn_auth USING(true);

CREATE FUNCTION hyprn_reject_delete() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'record deletion forbidden'; END $$;
CREATE TRIGGER archive_no_delete BEFORE DELETE ON study_archive
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT SELECT ON hyprn_schema_versions TO hyprn_request;
GRANT SELECT,INSERT ON studies,memberships,receipts,study_archive TO hyprn_request;
GRANT UPDATE(revision,name,description,boundary) ON studies TO hyprn_request;
GRANT UPDATE ON study_archive TO hyprn_request;
GRANT SELECT ON agent_actors,agent_delegations TO hyprn_request;
GRANT SELECT ON sessions,agent_api_sessions,agent_delegations TO hyprn_auth;
