-- Explicit full domain schema. Canonical scientific payloads remain TEXT, never JSONB.

ALTER TABLE users ADD COLUMN display_alias TEXT;
ALTER TABLE users ADD COLUMN profile_revision INTEGER NOT NULL DEFAULT 0;

CREATE TABLE model_associations(
 study_id TEXT NOT NULL REFERENCES studies(study_id), model_id TEXT NOT NULL,
 command_id TEXT NOT NULL, PRIMARY KEY(study_id,model_id)
);

CREATE TABLE evidence(
 evidence_version_id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL,
 study_id TEXT NOT NULL REFERENCES studies(study_id), payload TEXT NOT NULL
);

CREATE TABLE evidence_families(
 evidence_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 head TEXT NOT NULL REFERENCES evidence(evidence_version_id)
);

CREATE TABLE configuration_families(
 configuration_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 head TEXT NOT NULL
);

CREATE TABLE configurations(
 configuration_revision_id TEXT PRIMARY KEY, configuration_id TEXT NOT NULL,
 study_id TEXT NOT NULL REFERENCES studies(study_id), payload TEXT NOT NULL
);

CREATE TABLE run_associations(
 run_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 configuration_revision_id TEXT NOT NULL REFERENCES configurations(configuration_revision_id),
 command_id TEXT NOT NULL, store_uuid TEXT, process_uuid TEXT, accepted_at TEXT,
 UNIQUE(study_id,command_id), UNIQUE(store_uuid,process_uuid)
);

CREATE TABLE outbox(
 run_id TEXT PRIMARY KEY REFERENCES run_associations(run_id),
 state TEXT NOT NULL CHECK(state IN ('accepted_run','dispatching','recorded','uncertain')),
 payload TEXT NOT NULL
);

CREATE TABLE execution_observation(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 status TEXT NOT NULL CHECK(status IN ('ready','unavailable')),
 reason TEXT CHECK(reason IN ('executor_unavailable','attestation_invalid')),
 observed_at DOUBLE PRECISION NOT NULL, expires_at DOUBLE PRECISION NOT NULL, runtime_json TEXT,
 CHECK(expires_at=observed_at+30),
 CHECK((status='ready' AND reason IS NULL) OR (status='unavailable' AND reason IS NOT NULL))
);

CREATE TABLE computational_record_requests(
 request_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 actor_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('preview','create')),
 command_id TEXT NOT NULL, payload_digest TEXT NOT NULL, selected_ids_json TEXT NOT NULL,
 preview_id TEXT, expected_preview_digest TEXT,
 state TEXT NOT NULL CHECK(state IN ('queued','building','reviewable','ready','failed')),
 generation INTEGER NOT NULL, payload_json TEXT NOT NULL, error_json TEXT,
 artifact_path TEXT, artifact_sha256 TEXT,
 UNIQUE(study_id,kind,command_id)
);

CREATE FUNCTION immutable_evidence_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable evidence' USING ERRCODE='23514'; END $$;

CREATE TRIGGER immutable_evidence_update BEFORE UPDATE ON evidence FOR EACH ROW EXECUTE FUNCTION immutable_evidence_update_fn();

CREATE FUNCTION immutable_evidence_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable evidence' USING ERRCODE='23514'; END $$;

CREATE TRIGGER immutable_evidence_delete BEFORE DELETE ON evidence FOR EACH ROW EXECUTE FUNCTION immutable_evidence_delete_fn();

CREATE FUNCTION immutable_configuration_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable configuration' USING ERRCODE='23514'; END $$;

CREATE TRIGGER immutable_configuration_update BEFORE UPDATE ON configurations FOR EACH ROW EXECUTE FUNCTION immutable_configuration_update_fn();

CREATE FUNCTION immutable_configuration_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable configuration' USING ERRCODE='23514'; END $$;

CREATE TRIGGER immutable_configuration_delete BEFORE DELETE ON configurations FOR EACH ROW EXECUTE FUNCTION immutable_configuration_delete_fn();

CREATE TABLE study_brief_drafts(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 revision TEXT NOT NULL, payload TEXT NOT NULL
);

CREATE TABLE study_brief_versions(
 brief_version_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(study_id,version_number)
);

CREATE FUNCTION study_brief_versions_no_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved study brief versions are immutable' USING ERRCODE='23514'; END $$;

CREATE TRIGGER study_brief_versions_no_update BEFORE UPDATE ON study_brief_versions FOR EACH ROW EXECUTE FUNCTION study_brief_versions_no_update_fn();

CREATE FUNCTION study_brief_versions_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved study brief versions are never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER study_brief_versions_no_delete BEFORE DELETE ON study_brief_versions FOR EACH ROW EXECUTE FUNCTION study_brief_versions_no_delete_fn();

CREATE TABLE calculations(
 calculation_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id)
);

CREATE TABLE calculation_versions(
 calculation_version_id TEXT PRIMARY KEY,
 calculation_id TEXT NOT NULL REFERENCES calculations(calculation_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(calculation_id,version_number)
);

CREATE TABLE reference_marks(
 configuration_revision_id TEXT PRIMARY KEY
  REFERENCES configurations(configuration_revision_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 payload TEXT NOT NULL
);

CREATE FUNCTION calculations_no_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'calculation identities are immutable' USING ERRCODE='23514'; END $$;

CREATE TRIGGER calculations_no_update BEFORE UPDATE ON calculations FOR EACH ROW EXECUTE FUNCTION calculations_no_update_fn();

CREATE FUNCTION calculations_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'calculations are never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER calculations_no_delete BEFORE DELETE ON calculations FOR EACH ROW EXECUTE FUNCTION calculations_no_delete_fn();

CREATE FUNCTION calculation_versions_no_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved calculation versions are immutable' USING ERRCODE='23514'; END $$;

CREATE TRIGGER calculation_versions_no_update BEFORE UPDATE ON calculation_versions FOR EACH ROW EXECUTE FUNCTION calculation_versions_no_update_fn();

CREATE FUNCTION calculation_versions_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved calculation versions are never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER calculation_versions_no_delete BEFORE DELETE ON calculation_versions FOR EACH ROW EXECUTE FUNCTION calculation_versions_no_delete_fn();

CREATE TABLE model_explanation_drafts(
 study_id TEXT NOT NULL REFERENCES studies(study_id), model_id TEXT NOT NULL,
 revision TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(study_id,model_id)
);

CREATE TABLE model_explanation_versions(
 explanation_version_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id), model_id TEXT NOT NULL,
 model_revision_id TEXT NOT NULL UNIQUE,
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(study_id,model_id,version_number)
);

CREATE FUNCTION model_explanation_versions_no_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved model explanations are immutable' USING ERRCODE='23514'; END $$;

CREATE TRIGGER model_explanation_versions_no_update BEFORE UPDATE ON model_explanation_versions FOR EACH ROW EXECUTE FUNCTION model_explanation_versions_no_update_fn();

CREATE FUNCTION model_explanation_versions_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved model explanations are never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER model_explanation_versions_no_delete BEFORE DELETE ON model_explanation_versions FOR EACH ROW EXECUTE FUNCTION model_explanation_versions_no_delete_fn();

CREATE TABLE study_answer_drafts(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 revision TEXT NOT NULL, payload TEXT NOT NULL
);

CREATE TABLE study_answer_versions(
 answer_version_id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 version_number INTEGER NOT NULL, payload TEXT NOT NULL,
 UNIQUE(study_id,version_number)
);

CREATE FUNCTION study_answer_versions_no_update_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved study answer versions are immutable' USING ERRCODE='23514'; END $$;

CREATE TRIGGER study_answer_versions_no_update BEFORE UPDATE ON study_answer_versions FOR EACH ROW EXECUTE FUNCTION study_answer_versions_no_update_fn();

CREATE FUNCTION study_answer_versions_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'saved study answer versions are never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER study_answer_versions_no_delete BEFORE DELETE ON study_answer_versions FOR EACH ROW EXECUTE FUNCTION study_answer_versions_no_delete_fn();

CREATE TABLE assistant_conversations (
            study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
            conversation_id TEXT NOT NULL UNIQUE,
            provider_id TEXT,
            provision TEXT NOT NULL,
            reserved_cents INTEGER NOT NULL,
            active_turn TEXT,
            state TEXT NOT NULL,
            error TEXT,
            created_at DOUBLE PRECISION NOT NULL
        );

CREATE TABLE assistant_turns (
            turn_id TEXT PRIMARY KEY,
            study_id TEXT NOT NULL REFERENCES studies(study_id),
            actor_id TEXT NOT NULL,
            text TEXT NOT NULL,
            runtime_session TEXT,
            delivery TEXT NOT NULL,
            provider_event TEXT,
            stopped INTEGER NOT NULL DEFAULT 0,
            created_at DOUBLE PRECISION NOT NULL, author_display_name TEXT
        );

CREATE TABLE assistant_allowances (
            turn_id TEXT PRIMARY KEY REFERENCES assistant_turns(turn_id),
            cap_cents INTEGER NOT NULL CHECK(cap_cents > 0)
        );

CREATE TABLE assistant_events (
            study_id TEXT NOT NULL REFERENCES studies(study_id),
            event_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            position BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            UNIQUE(study_id,event_id)
        );

CREATE TABLE assistant_tool_results (
            study_id TEXT NOT NULL REFERENCES studies(study_id),
            event_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            content TEXT,
            is_error INTEGER NOT NULL DEFAULT 0,
            delivery TEXT NOT NULL,
            PRIMARY KEY(study_id,event_id)
        );

CREATE TABLE agent_attribution(
 study_id TEXT NOT NULL,
 record_kind TEXT NOT NULL CHECK(record_kind IN ('study','study_context','evidence_version','model_draft','model_version','approach_draft','approach_version','configuration_version','run','brief_draft','brief_version','answer_version','answer_draft','computational_record','exploration_request','exploration_design','exploration_view','exploration_sample','exploration_surrogate','calculation_version','reference_mark','calculation_sample','calculation_estimate','model_explanation_draft','model_explanation_version')),
 record_id TEXT NOT NULL, version_id TEXT,
 command_category TEXT NOT NULL, command_id TEXT NOT NULL,
 agent_actor_id TEXT NOT NULL, agent_display_name TEXT NOT NULL,
 delegator_actor_id TEXT NOT NULL, recorded_at TEXT NOT NULL, delegator_display_name TEXT,
 PRIMARY KEY(study_id,command_category,command_id,record_kind,record_id)
);

CREATE FUNCTION agent_attribution_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'agent attribution is never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER agent_attribution_no_delete BEFORE DELETE ON agent_attribution FOR EACH ROW EXECUTE FUNCTION agent_attribution_no_delete_fn();

CREATE TABLE agent_sessions(
 session_id TEXT PRIMARY KEY,
 delegation_id TEXT NOT NULL REFERENCES agent_delegations(delegation_id),
 surface TEXT NOT NULL CHECK(surface IN ('claude_managed','openai_agents')),
 client_name TEXT CHECK(client_name IS NULL OR length(client_name) BETWEEN 1 AND 64),
 client_version TEXT CHECK(client_version IS NULL OR length(client_version) BETWEEN 1 AND 64),
 agent_display_name TEXT NOT NULL, registry_version TEXT NOT NULL,
 playbook_sha256 TEXT NOT NULL, tool_definitions_sha256 TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('active','ended','access_lost')),
 api_calls INTEGER NOT NULL DEFAULT 0 CHECK(api_calls>=0),
 runs_submitted INTEGER NOT NULL DEFAULT 0 CHECK(runs_submitted>=0),
 started_at TEXT NOT NULL, ended_at TEXT,
 CHECK((state='active')=(ended_at IS NULL))
);

CREATE TABLE agent_actions(
 action_id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL REFERENCES agent_sessions(session_id),
 delegation_id TEXT NOT NULL REFERENCES agent_delegations(delegation_id),
 study_id TEXT NOT NULL,
 call_id TEXT NOT NULL CHECK(length(call_id) BETWEEN 1 AND 160),
 tool TEXT NOT NULL CHECK(length(tool) BETWEEN 1 AND 64),
 effect TEXT CHECK(effect IS NULL OR effect IN ('read','draft','record','submit','outside_study')),
 args_sha256 TEXT NOT NULL CHECK(length(args_sha256)=64),
 command_ids TEXT NOT NULL, api_operations TEXT NOT NULL DEFAULT '[]',
 outcome_class TEXT CHECK(outcome_class IS NULL OR outcome_class IN ('ok','invalid_input','too_large','unsupported','guard_blocked','conflict','not_ready','not_found','access_lost','session_expired','budget_exhausted','busy','pending','uncertain','unavailable','internal')),
 reason_code TEXT, reason_message TEXT CHECK(reason_message IS NULL OR length(reason_message)<=512),
 warnings TEXT NOT NULL DEFAULT '[]', records TEXT NOT NULL DEFAULT '[]',
 result_json TEXT
  CHECK(result_json IS NULL OR octet_length(result_json)<=24576),
 state TEXT NOT NULL CHECK(state IN ('intended','completed','refused','reconciling','uncertain','failed')),
 created_at TEXT NOT NULL, completed_at TEXT,
 UNIQUE(session_id,call_id),
 CHECK((reason_code IS NULL)=(reason_message IS NULL)),
 CHECK(result_json IS NULL OR effect IN ('draft','record','submit','outside_study')),
 CHECK(state<>'completed' OR (reason_code IS NULL AND outcome_class='ok'))
);

CREATE FUNCTION agent_sessions_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'agent sessions are never deleted' USING ERRCODE='23514'; END $$;

CREATE TRIGGER agent_sessions_no_delete BEFORE DELETE ON agent_sessions FOR EACH ROW EXECUTE FUNCTION agent_sessions_no_delete_fn();

CREATE FUNCTION agent_sessions_fixed_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'an agent session only ends and only counts up' USING ERRCODE='23514'; END $$;

CREATE TRIGGER agent_sessions_fixed BEFORE UPDATE ON agent_sessions FOR EACH ROW WHEN (NEW.session_id IS DISTINCT FROM OLD.session_id OR NEW.delegation_id IS DISTINCT FROM OLD.delegation_id OR NEW.surface IS DISTINCT FROM OLD.surface OR NEW.client_name IS DISTINCT FROM OLD.client_name OR NEW.client_version IS DISTINCT FROM OLD.client_version OR NEW.agent_display_name IS DISTINCT FROM OLD.agent_display_name OR NEW.registry_version IS DISTINCT FROM OLD.registry_version OR NEW.playbook_sha256 IS DISTINCT FROM OLD.playbook_sha256 OR NEW.tool_definitions_sha256 IS DISTINCT FROM OLD.tool_definitions_sha256 OR NEW.started_at IS DISTINCT FROM OLD.started_at
  OR (OLD.state<>'active' AND (NEW.state IS DISTINCT FROM OLD.state OR NEW.ended_at IS DISTINCT FROM OLD.ended_at))
  OR NEW.api_calls<OLD.api_calls OR NEW.runs_submitted<OLD.runs_submitted) EXECUTE FUNCTION agent_sessions_fixed_fn();

CREATE FUNCTION agent_actions_no_delete_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'the agent action journal is append-only' USING ERRCODE='23514'; END $$;

CREATE TRIGGER agent_actions_no_delete BEFORE DELETE ON agent_actions FOR EACH ROW EXECUTE FUNCTION agent_actions_no_delete_fn();

CREATE FUNCTION agent_actions_inserted_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'a journal row starts intended or refused' USING ERRCODE='23514'; END $$;

CREATE TRIGGER agent_actions_inserted BEFORE INSERT ON agent_actions FOR EACH ROW WHEN (NEW.state NOT IN ('intended','refused')) EXECUTE FUNCTION agent_actions_inserted_fn();

CREATE FUNCTION agent_actions_outcome_once_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'a journal row records one outcome and its intent never changes' USING ERRCODE='23514'; END $$;

CREATE TRIGGER agent_actions_outcome_once BEFORE UPDATE ON agent_actions FOR EACH ROW WHEN (OLD.state NOT IN ('intended','reconciling') OR NEW.state='intended'
  OR NEW.action_id IS DISTINCT FROM OLD.action_id OR NEW.session_id IS DISTINCT FROM OLD.session_id OR NEW.delegation_id IS DISTINCT FROM OLD.delegation_id OR NEW.study_id IS DISTINCT FROM OLD.study_id OR NEW.call_id IS DISTINCT FROM OLD.call_id OR NEW.tool IS DISTINCT FROM OLD.tool OR NEW.effect IS DISTINCT FROM OLD.effect OR NEW.args_sha256 IS DISTINCT FROM OLD.args_sha256 OR NEW.command_ids IS DISTINCT FROM OLD.command_ids OR NEW.created_at IS DISTINCT FROM OLD.created_at) EXECUTE FUNCTION agent_actions_outcome_once_fn();

ALTER TABLE evidence ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;
ALTER TABLE configurations ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;
ALTER TABLE run_associations ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;
ALTER TABLE outbox ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;
ALTER TABLE receipts ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;
ALTER TABLE calculations ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;
ALTER TABLE computational_record_requests ADD COLUMN rowid BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE;

-- Private helpers have an explicit owner policy to avoid recursive RLS. Only the
-- migration login owns these functions; runtime logins cannot replace them.
CREATE POLICY memberships_owner ON memberships TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY delegations_owner ON agent_delegations TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY actors_owner ON agent_actors TO hyprn_migration USING(true) WITH CHECK(true);
CREATE FUNCTION hyprn_human() RETURNS TEXT LANGUAGE sql STABLE SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$
 SELECT coalesce((SELECT delegator_actor_id FROM public.agent_actors
 WHERE actor_id=public.hyprn_actor()),public.hyprn_actor()) $$;
CREATE FUNCTION hyprn_member(sid TEXT, writable BOOLEAN DEFAULT false) RETURNS BOOLEAN
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.memberships m WHERE m.study_id=sid
 AND m.actor_id=public.hyprn_human() AND (NOT writable OR m.role IN ('owner','writer')))
 AND (public.hyprn_human()=public.hyprn_actor() OR EXISTS(
 SELECT 1 FROM public.agent_delegations d WHERE d.study_id=sid
 AND d.agent_actor_id=public.hyprn_actor() AND d.revoked_at IS NULL
 AND d.expires_at>extract(epoch FROM statement_timestamp())
 AND (NOT writable OR (d.role_ceiling='writer' AND
 d.allowed_effects::jsonb ?| ARRAY['draft','record','submit'])))) $$;
CREATE FUNCTION hyprn_owner(sid TEXT) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$
 SELECT public.hyprn_human()=public.hyprn_actor() AND EXISTS(SELECT 1 FROM public.memberships
 WHERE study_id=sid AND actor_id=public.hyprn_actor() AND role='owner') $$;
CREATE FUNCTION hyprn_created_study(sid TEXT) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.memberships WHERE study_id=sid AND actor_id=public.hyprn_human()) $$;
DROP POLICY studies_read ON studies;
DROP POLICY studies_create ON studies;
DROP POLICY studies_update ON studies;
ALTER TABLE studies ALTER COLUMN owner_actor_id SET DEFAULT hyprn_human();
CREATE POLICY studies_read ON studies FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id) OR (owner_actor_id=hyprn_human() AND created_transaction=txid_current()));
CREATE POLICY studies_create ON studies FOR INSERT TO hyprn_request
 WITH CHECK(owner_actor_id=hyprn_human() AND hyprn_actor() IS NOT NULL AND
 (hyprn_human()=hyprn_actor() OR EXISTS(SELECT 1 FROM agent_delegations d
 WHERE d.agent_actor_id=hyprn_actor() AND d.revoked_at IS NULL
 AND d.expires_at>extract(epoch FROM statement_timestamp()) AND d.role_ceiling='writer'
 AND d.allowed_effects::jsonb ? 'record' AND hyprn_member(d.study_id,true))));
CREATE POLICY studies_update ON studies FOR UPDATE TO hyprn_request
 USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
DROP POLICY memberships_read ON memberships;
DROP POLICY memberships_create ON memberships;
CREATE POLICY memberships_read ON memberships FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id) OR actor_id=hyprn_actor());
CREATE POLICY memberships_insert ON memberships FOR INSERT TO hyprn_request
 WITH CHECK(hyprn_owner(study_id) OR (actor_id=hyprn_human() AND role='owner' AND EXISTS(
 SELECT 1 FROM studies s WHERE s.study_id=memberships.study_id
 AND s.owner_actor_id=hyprn_human() AND s.created_transaction=txid_current())));
CREATE POLICY memberships_update ON memberships FOR UPDATE TO hyprn_request
 USING(hyprn_owner(study_id)) WITH CHECK(hyprn_owner(study_id));
CREATE POLICY memberships_delete ON memberships FOR DELETE TO hyprn_request USING(hyprn_owner(study_id));
GRANT UPDATE,DELETE ON memberships TO hyprn_request;
DROP POLICY receipts_scope ON receipts;
CREATE POLICY receipts_read ON receipts FOR SELECT TO hyprn_request
 USING(hyprn_member(scope) OR (scope='actor:'||hyprn_actor() AND actor_id=hyprn_actor()
 AND (result IS NULL OR result::jsonb->>'study_id' IS NULL OR hyprn_created_study(result::jsonb->>'study_id'))));
CREATE POLICY receipts_insert ON receipts FOR INSERT TO hyprn_request
 WITH CHECK(actor_id=hyprn_actor() AND (hyprn_member(scope) OR scope='actor:'||hyprn_actor()));
CREATE POLICY receipts_update ON receipts FOR UPDATE TO hyprn_request
 USING(hyprn_member(scope)) WITH CHECK(hyprn_member(scope));
-- Interaction predictions are temporary reads, never saved scientific receipts.
CREATE POLICY receipts_delete ON receipts FOR DELETE TO hyprn_request
 USING(hyprn_member(scope) AND category='calculation_prediction');
GRANT UPDATE,DELETE ON receipts TO hyprn_request;
CREATE POLICY actors_insert ON agent_actors FOR INSERT TO hyprn_request
 WITH CHECK(delegator_actor_id=hyprn_actor());
CREATE POLICY delegations_insert ON agent_delegations FOR INSERT TO hyprn_request
 WITH CHECK(delegator_actor_id=hyprn_actor() AND hyprn_member(study_id,role_ceiling='writer')
 AND EXISTS(SELECT 1 FROM agent_actors a WHERE a.actor_id=agent_actor_id
 AND a.delegator_actor_id=hyprn_actor()));
DROP POLICY delegations_read ON agent_delegations;
CREATE POLICY delegations_read ON agent_delegations FOR SELECT TO hyprn_request
 USING((agent_actor_id=hyprn_actor() OR delegator_actor_id=hyprn_actor()) AND hyprn_member(study_id));
CREATE POLICY delegations_update ON agent_delegations FOR UPDATE TO hyprn_request
 USING(delegator_actor_id=hyprn_actor()) WITH CHECK(delegator_actor_id=hyprn_actor());
GRANT INSERT ON agent_actors,agent_delegations TO hyprn_request;
GRANT UPDATE(revoked_at,revoked_reason) ON agent_delegations TO hyprn_request;
ALTER TABLE agent_api_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_api_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_api_auth ON agent_api_sessions FOR SELECT TO hyprn_auth USING(true);
CREATE POLICY agent_api_scope ON agent_api_sessions TO hyprn_request
 USING(EXISTS(SELECT 1 FROM agent_delegations d WHERE d.delegation_id=agent_api_sessions.delegation_id
 AND d.delegator_actor_id=hyprn_actor()))
 WITH CHECK(EXISTS(SELECT 1 FROM agent_delegations d WHERE d.delegation_id=agent_api_sessions.delegation_id
 AND d.agent_actor_id=agent_api_sessions.actor_id AND d.delegator_actor_id=hyprn_actor()
 AND d.revoked_at IS NULL AND d.expires_at>extract(epoch FROM statement_timestamp())));
GRANT SELECT,INSERT,DELETE ON agent_api_sessions TO hyprn_request;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_owner ON users TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY users_read ON users FOR SELECT TO hyprn_request USING(actor_id=hyprn_human() OR EXISTS(
 SELECT 1 FROM memberships m WHERE m.actor_id=users.actor_id AND hyprn_member(m.study_id)));
CREATE POLICY users_update ON users FOR UPDATE TO hyprn_request
 USING(actor_id=hyprn_actor()) WITH CHECK(actor_id=hyprn_actor());
GRANT SELECT(actor_id,username,display_alias,profile_revision),UPDATE(display_alias,profile_revision) ON users TO hyprn_request;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY sessions_auth ON sessions FOR SELECT TO hyprn_auth USING(true);
CREATE POLICY sessions_logout ON sessions FOR DELETE TO hyprn_request USING(actor_id=hyprn_actor());
GRANT DELETE ON sessions TO hyprn_request;

-- Explicit JSON projection helpers. Stored canonical text is never rewritten.
CREATE FUNCTION json_extract(doc TEXT,path TEXT) RETURNS TEXT LANGUAGE sql IMMUTABLE STRICT
 AS $$ SELECT doc::jsonb #>> string_to_array(substr(path,3),'.') $$;
CREATE FUNCTION json_type(doc TEXT,path TEXT) RETURNS TEXT LANGUAGE sql IMMUTABLE STRICT
 AS $$ SELECT jsonb_typeof(doc::jsonb #> string_to_array(substr(path,3),'.')) $$;
CREATE FUNCTION json_array_length(doc TEXT,path TEXT) RETURNS INTEGER LANGUAGE sql IMMUTABLE STRICT
 AS $$ SELECT jsonb_array_length(doc::jsonb #> string_to_array(substr(path,3),'.')) $$;
CREATE FUNCTION json_each(doc TEXT,path TEXT DEFAULT '$') RETURNS TABLE(value TEXT)
 LANGUAGE sql IMMUTABLE STRICT AS $$ SELECT jsonb_array_elements_text(
 CASE WHEN path='$' THEN doc::jsonb ELSE doc::jsonb #> string_to_array(substr(path,3),'.') END) $$;

ALTER TABLE model_associations ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_associations FORCE ROW LEVEL SECURITY;
CREATE POLICY model_associations_read ON model_associations FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY model_associations_insert ON model_associations FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY model_associations_update ON model_associations FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON model_associations TO hyprn_request;
ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_read ON evidence FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY evidence_insert ON evidence FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY evidence_update ON evidence FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON evidence TO hyprn_request;
ALTER TABLE evidence_families ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_families FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_families_read ON evidence_families FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY evidence_families_insert ON evidence_families FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY evidence_families_update ON evidence_families FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON evidence_families TO hyprn_request;
ALTER TABLE configuration_families ENABLE ROW LEVEL SECURITY;
ALTER TABLE configuration_families FORCE ROW LEVEL SECURITY;
CREATE POLICY configuration_families_read ON configuration_families FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY configuration_families_insert ON configuration_families FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY configuration_families_update ON configuration_families FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON configuration_families TO hyprn_request;
ALTER TABLE configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE configurations FORCE ROW LEVEL SECURITY;
CREATE POLICY configurations_read ON configurations FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY configurations_insert ON configurations FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY configurations_update ON configurations FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON configurations TO hyprn_request;
ALTER TABLE run_associations ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_associations FORCE ROW LEVEL SECURITY;
CREATE POLICY run_associations_read ON run_associations FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY run_associations_insert ON run_associations FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY run_associations_update ON run_associations FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON run_associations TO hyprn_request;
ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY outbox_read ON outbox FOR SELECT TO hyprn_request USING(EXISTS(SELECT 1 FROM run_associations r WHERE r.run_id=outbox.run_id AND hyprn_member(r.study_id,false)));
CREATE POLICY outbox_insert ON outbox FOR INSERT TO hyprn_request WITH CHECK(EXISTS(SELECT 1 FROM run_associations r WHERE r.run_id=outbox.run_id AND hyprn_member(r.study_id,true)));
CREATE POLICY outbox_update ON outbox FOR UPDATE TO hyprn_request USING(EXISTS(SELECT 1 FROM run_associations r WHERE r.run_id=outbox.run_id AND hyprn_member(r.study_id,true))) WITH CHECK(EXISTS(SELECT 1 FROM run_associations r WHERE r.run_id=outbox.run_id AND hyprn_member(r.study_id,true)));
GRANT SELECT,INSERT,UPDATE ON outbox TO hyprn_request;
ALTER TABLE execution_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_observation FORCE ROW LEVEL SECURITY;
CREATE POLICY observation_read ON execution_observation FOR SELECT TO hyprn_request USING(hyprn_actor() IS NOT NULL);
GRANT SELECT ON execution_observation TO hyprn_request;
ALTER TABLE computational_record_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE computational_record_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY computational_record_requests_read ON computational_record_requests FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY computational_record_requests_insert ON computational_record_requests FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY computational_record_requests_update ON computational_record_requests FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON computational_record_requests TO hyprn_request;
ALTER TABLE study_brief_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_brief_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY study_brief_drafts_read ON study_brief_drafts FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY study_brief_drafts_insert ON study_brief_drafts FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY study_brief_drafts_update ON study_brief_drafts FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON study_brief_drafts TO hyprn_request;
ALTER TABLE study_brief_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_brief_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY study_brief_versions_read ON study_brief_versions FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY study_brief_versions_insert ON study_brief_versions FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY study_brief_versions_update ON study_brief_versions FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON study_brief_versions TO hyprn_request;
ALTER TABLE calculations ENABLE ROW LEVEL SECURITY;
ALTER TABLE calculations FORCE ROW LEVEL SECURITY;
CREATE POLICY calculations_read ON calculations FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY calculations_insert ON calculations FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY calculations_update ON calculations FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON calculations TO hyprn_request;
ALTER TABLE calculation_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE calculation_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY calculation_versions_read ON calculation_versions FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY calculation_versions_insert ON calculation_versions FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY calculation_versions_update ON calculation_versions FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON calculation_versions TO hyprn_request;
ALTER TABLE reference_marks ENABLE ROW LEVEL SECURITY;
ALTER TABLE reference_marks FORCE ROW LEVEL SECURITY;
CREATE POLICY reference_marks_read ON reference_marks FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY reference_marks_insert ON reference_marks FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY reference_marks_update ON reference_marks FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON reference_marks TO hyprn_request;
CREATE POLICY reference_marks_delete ON reference_marks FOR DELETE TO hyprn_request USING(hyprn_member(study_id,true));
GRANT DELETE ON reference_marks TO hyprn_request;
ALTER TABLE model_explanation_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_explanation_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY model_explanation_drafts_read ON model_explanation_drafts FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY model_explanation_drafts_insert ON model_explanation_drafts FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY model_explanation_drafts_update ON model_explanation_drafts FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON model_explanation_drafts TO hyprn_request;
ALTER TABLE model_explanation_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_explanation_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY model_explanation_versions_read ON model_explanation_versions FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY model_explanation_versions_insert ON model_explanation_versions FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY model_explanation_versions_update ON model_explanation_versions FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
GRANT SELECT,INSERT,UPDATE ON model_explanation_versions TO hyprn_request;
ALTER TABLE study_answer_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_answer_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY study_answer_drafts_read ON study_answer_drafts FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY study_answer_drafts_insert ON study_answer_drafts FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY study_answer_drafts_update ON study_answer_drafts FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON study_answer_drafts TO hyprn_request;
ALTER TABLE study_answer_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_answer_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY study_answer_versions_read ON study_answer_versions FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY study_answer_versions_insert ON study_answer_versions FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY study_answer_versions_update ON study_answer_versions FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON study_answer_versions TO hyprn_request;
ALTER TABLE assistant_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_conversations FORCE ROW LEVEL SECURITY;
CREATE POLICY assistant_conversations_read ON assistant_conversations FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY assistant_conversations_insert ON assistant_conversations FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY assistant_conversations_update ON assistant_conversations FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON assistant_conversations TO hyprn_request;
ALTER TABLE assistant_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_turns FORCE ROW LEVEL SECURITY;
CREATE POLICY assistant_turns_read ON assistant_turns FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY assistant_turns_insert ON assistant_turns FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY assistant_turns_update ON assistant_turns FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON assistant_turns TO hyprn_request;
ALTER TABLE assistant_allowances ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_allowances FORCE ROW LEVEL SECURITY;
CREATE POLICY assistant_allowances_read ON assistant_allowances FOR SELECT TO hyprn_request USING(EXISTS(SELECT 1 FROM assistant_turns t WHERE t.turn_id=assistant_allowances.turn_id AND hyprn_member(t.study_id,false)));
CREATE POLICY assistant_allowances_insert ON assistant_allowances FOR INSERT TO hyprn_request WITH CHECK(EXISTS(SELECT 1 FROM assistant_turns t WHERE t.turn_id=assistant_allowances.turn_id AND hyprn_member(t.study_id,false)));
CREATE POLICY assistant_allowances_update ON assistant_allowances FOR UPDATE TO hyprn_request USING(EXISTS(SELECT 1 FROM assistant_turns t WHERE t.turn_id=assistant_allowances.turn_id AND hyprn_member(t.study_id,false))) WITH CHECK(EXISTS(SELECT 1 FROM assistant_turns t WHERE t.turn_id=assistant_allowances.turn_id AND hyprn_member(t.study_id,false)));
GRANT SELECT,INSERT,UPDATE ON assistant_allowances TO hyprn_request;
ALTER TABLE assistant_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_events FORCE ROW LEVEL SECURITY;
CREATE POLICY assistant_events_read ON assistant_events FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY assistant_events_insert ON assistant_events FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY assistant_events_update ON assistant_events FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON assistant_events TO hyprn_request;
ALTER TABLE assistant_tool_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_tool_results FORCE ROW LEVEL SECURITY;
CREATE POLICY assistant_tool_results_read ON assistant_tool_results FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY assistant_tool_results_insert ON assistant_tool_results FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY assistant_tool_results_update ON assistant_tool_results FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON assistant_tool_results TO hyprn_request;
ALTER TABLE agent_attribution ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_attribution FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_attribution_read ON agent_attribution FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY agent_attribution_insert ON agent_attribution FOR INSERT TO hyprn_request
 WITH CHECK(hyprn_member(study_id,false) OR (
 agent_actor_id=hyprn_actor() AND delegator_actor_id=hyprn_human() AND
 record_kind='study' AND record_id=study_id AND version_id IS NULL AND
 command_category='study_create' AND EXISTS(SELECT 1 FROM studies s
 WHERE s.study_id=agent_attribution.study_id AND s.owner_actor_id=hyprn_human()
 AND s.created_transaction=txid_current())));
CREATE POLICY agent_attribution_update ON agent_attribution FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON agent_attribution TO hyprn_request;
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_sessions_read ON agent_sessions FOR SELECT TO hyprn_request USING(EXISTS(SELECT 1 FROM agent_delegations d WHERE d.delegation_id=agent_sessions.delegation_id AND hyprn_member(d.study_id,false)));
CREATE POLICY agent_sessions_insert ON agent_sessions FOR INSERT TO hyprn_request WITH CHECK(EXISTS(SELECT 1 FROM agent_delegations d WHERE d.delegation_id=agent_sessions.delegation_id AND hyprn_member(d.study_id,false)));
CREATE POLICY agent_sessions_update ON agent_sessions FOR UPDATE TO hyprn_request USING(EXISTS(SELECT 1 FROM agent_delegations d WHERE d.delegation_id=agent_sessions.delegation_id AND hyprn_member(d.study_id,false))) WITH CHECK(EXISTS(SELECT 1 FROM agent_delegations d WHERE d.delegation_id=agent_sessions.delegation_id AND hyprn_member(d.study_id,false)));
GRANT SELECT,INSERT,UPDATE ON agent_sessions TO hyprn_request;
ALTER TABLE agent_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_actions FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_actions_read ON agent_actions FOR SELECT TO hyprn_request USING(hyprn_member(study_id,false));
CREATE POLICY agent_actions_insert ON agent_actions FOR INSERT TO hyprn_request WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY agent_actions_update ON agent_actions FOR UPDATE TO hyprn_request USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
GRANT SELECT,INSERT,UPDATE ON agent_actions TO hyprn_request;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO hyprn_request;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_actor(),hyprn_human(),hyprn_member(TEXT,BOOLEAN),hyprn_owner(TEXT),json_extract(TEXT,TEXT),json_type(TEXT,TEXT),json_array_length(TEXT,TEXT),json_each(TEXT,TEXT) TO hyprn_request;
GRANT EXECUTE ON FUNCTION hyprn_created_study(TEXT) TO hyprn_request;

-- Background credentials have no row authority. These fixed functions reveal
-- only queue identities and provider-account metadata, never scientific payloads.
CREATE POLICY conversations_owner ON assistant_conversations TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY turns_owner ON assistant_turns TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY receipts_owner ON receipts TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY exports_owner ON computational_record_requests TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY runs_owner ON run_associations TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY outbox_owner ON outbox TO hyprn_migration USING(true) WITH CHECK(true);
CREATE POLICY observation_owner ON execution_observation TO hyprn_migration USING(true) WITH CHECK(true);
CREATE FUNCTION hyprn_background_jobs(category TEXT, identity TEXT DEFAULT NULL)
 RETURNS TABLE(study_id TEXT,actor_id TEXT,work_id TEXT) LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$
 BEGIN
 IF category='assistant' AND session_user='hyprn_assistant_background' THEN
   RETURN QUERY SELECT c.study_id,t.actor_id,c.study_id FROM public.assistant_conversations c
   JOIN public.assistant_turns t ON t.turn_id=c.active_turn
   WHERE identity IS NULL OR c.study_id=identity ORDER BY (t.delivery='new'),t.created_at;
 ELSIF category IN ('analysis_execution','calculation_sample','calculation_estimate','calculation_prediction')
 AND session_user='hyprn_dispatcher_background' THEN
   RETURN QUERY SELECT r.scope,r.actor_id,r.command_id FROM public.receipts r
   WHERE r.category=hyprn_background_jobs.category AND r.state='pending_remote'
   AND (identity IS NULL OR r.command_id=identity) ORDER BY r.rowid LIMIT 1;
 ELSIF category='run' AND session_user='hyprn_dispatcher_background' THEN
   RETURN QUERY SELECT r.study_id,c.actor_id,r.run_id FROM public.run_associations r
   JOIN public.outbox o USING(run_id) JOIN public.receipts c ON c.scope=r.study_id
   AND c.category='run' AND c.command_id=r.command_id
   WHERE o.state IN ('accepted_run','dispatching')
   AND coalesce(public.json_extract(o.payload,'$.preparation_state'),'')<>'preparation_failed'
   AND (identity IS NULL OR r.run_id=identity) ORDER BY r.rowid LIMIT 100;
 ELSIF category='export' AND session_user='hyprn_dispatcher_background' THEN
   RETURN QUERY SELECT r.study_id,r.actor_id,r.request_id FROM public.computational_record_requests r
   WHERE r.state IN ('queued','building') AND (identity IS NULL OR r.request_id=identity)
   ORDER BY r.rowid LIMIT 1;
 ELSE RAISE EXCEPTION 'background purpose not permitted' USING ERRCODE='42501';
 END IF;
 END $$;
CREATE FUNCTION hyprn_assistant_accounts() RETURNS TABLE(
 study_id TEXT,conversation_id TEXT,provider_id TEXT,provision TEXT,
 reserved_cents INTEGER,active_turn TEXT,state TEXT)
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT study_id,conversation_id,provider_id,provision,reserved_cents,active_turn,state
 FROM public.assistant_conversations $$;
CREATE FUNCTION hyprn_publish_observation(status TEXT,reason TEXT,observed DOUBLE PRECISION,runtime TEXT)
 RETURNS VOID LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 INSERT INTO public.execution_observation(singleton,status,reason,observed_at,expires_at,runtime_json)
 VALUES(1,status,reason,observed,observed+30,runtime)
 ON CONFLICT(singleton) DO UPDATE SET status=excluded.status,reason=excluded.reason,
 observed_at=excluded.observed_at,expires_at=excluded.expires_at,runtime_json=excluded.runtime_json $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_background_jobs(TEXT,TEXT) TO hyprn_assistant_background,hyprn_dispatcher_background;
GRANT EXECUTE ON FUNCTION hyprn_assistant_accounts() TO hyprn_assistant_background;
GRANT EXECUTE ON FUNCTION hyprn_publish_observation(TEXT,TEXT,DOUBLE PRECISION,TEXT) TO hyprn_dispatcher_background;

-- Foreign keys preserve the same study through every persisted indirect link.
ALTER TABLE evidence ADD UNIQUE(study_id,evidence_version_id);
ALTER TABLE evidence_families ADD FOREIGN KEY(study_id,head) REFERENCES evidence(study_id,evidence_version_id);
ALTER TABLE configurations ADD UNIQUE(study_id,configuration_revision_id);
ALTER TABLE configuration_families ADD FOREIGN KEY(study_id,head) REFERENCES configurations(study_id,configuration_revision_id);
ALTER TABLE run_associations ADD FOREIGN KEY(study_id,configuration_revision_id) REFERENCES configurations(study_id,configuration_revision_id);
ALTER TABLE reference_marks ADD FOREIGN KEY(study_id,configuration_revision_id) REFERENCES configurations(study_id,configuration_revision_id);
ALTER TABLE calculations ADD UNIQUE(study_id,calculation_id);
ALTER TABLE calculation_versions ADD FOREIGN KEY(study_id,calculation_id) REFERENCES calculations(study_id,calculation_id);
ALTER TABLE assistant_turns ADD UNIQUE(study_id,turn_id);
ALTER TABLE assistant_tool_results ADD FOREIGN KEY(study_id,turn_id) REFERENCES assistant_turns(study_id,turn_id);
ALTER TABLE agent_delegations ADD UNIQUE(study_id,delegation_id);
ALTER TABLE agent_actions ADD FOREIGN KEY(study_id,delegation_id) REFERENCES agent_delegations(study_id,delegation_id);
CREATE INDEX evidence_study_family ON evidence(study_id,evidence_id);
CREATE INDEX agent_actions_study ON agent_actions(study_id,created_at);

CREATE FUNCTION hyprn_fixed_scope() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN
 IF NEW.study_id IS DISTINCT FROM OLD.study_id THEN
 RAISE EXCEPTION 'record study never changes' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
 END $$;
CREATE FUNCTION hyprn_receipt_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN
 IF (NEW.scope,NEW.category,NEW.command_id,NEW.actor_id,NEW.payload_digest)
 IS DISTINCT FROM (OLD.scope,OLD.category,OLD.command_id,OLD.actor_id,OLD.payload_digest)
 OR (OLD.state IN ('committed','rejected') AND NEW IS DISTINCT FROM OLD) THEN
 RAISE EXCEPTION 'accepted command identity and terminal outcome are immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
 END $$;
CREATE TRIGGER receipts_fixed BEFORE UPDATE ON receipts FOR EACH ROW EXECUTE FUNCTION hyprn_receipt_fixed();
CREATE FUNCTION hyprn_run_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN
 IF (NEW.run_id,NEW.study_id,NEW.configuration_revision_id,NEW.command_id,NEW.accepted_at)
 IS DISTINCT FROM (OLD.run_id,OLD.study_id,OLD.configuration_revision_id,OLD.command_id,OLD.accepted_at)
 OR (OLD.process_uuid IS NOT NULL AND (NEW.process_uuid,NEW.store_uuid) IS DISTINCT FROM (OLD.process_uuid,OLD.store_uuid)) THEN
 RAISE EXCEPTION 'accepted run identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
 END $$;
CREATE TRIGGER runs_fixed BEFORE UPDATE ON run_associations FOR EACH ROW EXECUTE FUNCTION hyprn_run_fixed();
CREATE FUNCTION hyprn_outbox_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE field TEXT;
 BEGIN
 IF NEW.run_id IS DISTINCT FROM OLD.run_id THEN
 RAISE EXCEPTION 'run identity is immutable' USING ERRCODE='23514';
 END IF;
 FOREACH field IN ARRAY ARRAY['actor','frozen','request','bundle','expected_runtime','execution_budget'] LOOP
 IF OLD.payload::jsonb ? field AND (OLD.payload::json->field)::text IS DISTINCT FROM (NEW.payload::json->field)::text THEN
 RAISE EXCEPTION 'accepted run inputs are immutable' USING ERRCODE='23514';
 END IF;
 END LOOP;
 IF OLD.payload::jsonb->'history'->'errors'='[]'::jsonb AND
 (OLD.payload::json->'history')::text IS DISTINCT FROM (NEW.payload::json->'history')::text THEN
 RAISE EXCEPTION 'completed retained projection is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
 END $$;
CREATE TRIGGER outbox_fixed BEFORE UPDATE ON outbox FOR EACH ROW EXECUTE FUNCTION hyprn_outbox_fixed();
CREATE TRIGGER outbox_no_delete BEFORE DELETE ON outbox FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
CREATE TRIGGER runs_no_delete BEFORE DELETE ON run_associations FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
CREATE FUNCTION hyprn_delegation_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN
 IF OLD.revoked_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
 RAISE EXCEPTION 'revoked delegation never resumes' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
 END $$;
CREATE TRIGGER delegations_fixed BEFORE UPDATE ON agent_delegations FOR EACH ROW EXECUTE FUNCTION hyprn_delegation_fixed();
DO $$ DECLARE name TEXT; BEGIN
 FOREACH name IN ARRAY ARRAY['model_associations','evidence_families','configuration_families',
 'study_brief_drafts','model_explanation_drafts','study_answer_drafts','reference_marks',
 'assistant_conversations','assistant_turns','assistant_tool_results','computational_record_requests'] LOOP
 EXECUTE format('CREATE TRIGGER fixed_scope BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION hyprn_fixed_scope()',name);
 END LOOP;
 FOREACH name IN ARRAY ARRAY['model_associations','assistant_events','agent_attribution'] LOOP
 EXECUTE format('CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION immutable_evidence_update_fn()',name);
 END LOOP;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
