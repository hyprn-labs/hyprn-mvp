-- Reasoning credential rotation does not revoke already accepted finite work.
-- A true revocation, narrower grant or lost human membership remains permanent.
CREATE TABLE analysis_authority_barriers(
 study_id TEXT NOT NULL REFERENCES studies(study_id), analysis_command TEXT NOT NULL,
 PRIMARY KEY(study_id,analysis_command)
);
ALTER TABLE analysis_authority_barriers ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_authority_barriers FORCE ROW LEVEL SECURITY;
CREATE POLICY analysis_barriers_owner ON analysis_authority_barriers TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE TRIGGER analysis_barriers_fixed BEFORE UPDATE OR DELETE ON analysis_authority_barriers
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
-- Old membership command outcomes omit the changed member and role. Any later
-- successful membership command therefore prevents automatic legacy recovery.
INSERT INTO analysis_authority_barriers
 SELECT r.scope,r.command_id FROM receipts r WHERE r.category='analysis_execution'
 AND EXISTS(SELECT 1 FROM receipts m WHERE m.scope=r.scope AND m.category='membership'
 AND m.state='committed' AND m.rowid>r.rowid);
CREATE FUNCTION hyprn_analysis_membership_barrier() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='DELETE' OR (OLD.role IN ('writer','owner') AND NEW.role NOT IN ('writer','owner')) THEN
 INSERT INTO public.analysis_authority_barriers
 SELECT r.scope,r.command_id FROM public.receipts r WHERE r.scope=OLD.study_id
 AND r.category='analysis_execution' AND (r.actor_id=OLD.actor_id OR r.actor_id IN
 (SELECT a.actor_id FROM public.agent_actors a WHERE a.delegator_actor_id=OLD.actor_id))
 ON CONFLICT DO NOTHING;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER analysis_membership_barrier AFTER UPDATE OR DELETE ON memberships
 FOR EACH ROW EXECUTE FUNCTION hyprn_analysis_membership_barrier();
REVOKE ALL ON FUNCTION hyprn_analysis_membership_barrier() FROM PUBLIC;

-- Future interruptions are recorded independently of wall-clock ordering.
CREATE FUNCTION hyprn_analysis_delegation_barrier() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF (TG_OP='UPDATE' AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL
     AND NEW.revoked_reason<>'replaced') OR
    (TG_OP='INSERT' AND (NEW.role_ceiling<>'writer' OR NOT (NEW.allowed_effects::jsonb ? 'submit'))) THEN
 INSERT INTO public.analysis_authority_barriers
 SELECT r.scope,r.command_id FROM public.receipts r WHERE r.scope=NEW.study_id
 AND r.actor_id=NEW.agent_actor_id AND r.category='analysis_execution'
 ON CONFLICT DO NOTHING;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER analysis_delegation_barrier AFTER INSERT OR UPDATE ON agent_delegations
 FOR EACH ROW EXECUTE FUNCTION hyprn_analysis_delegation_barrier();
REVOKE ALL ON FUNCTION hyprn_analysis_delegation_barrier() FROM PUBLIC;

CREATE FUNCTION hyprn_analysis_authorized(sid TEXT,parent TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.receipts r
 LEFT JOIN public.agent_actors a ON a.actor_id=r.actor_id
 WHERE r.scope=sid AND r.category='analysis_execution' AND r.command_id=parent
 AND (r.actor_id=public.hyprn_actor() OR a.delegator_actor_id=public.hyprn_actor())
 AND r.request::jsonb#>>'{authority,actor_id}'=r.actor_id
 AND EXISTS(SELECT 1 FROM public.memberships m WHERE m.study_id=sid
 AND m.actor_id=coalesce(a.delegator_actor_id,r.actor_id) AND m.role IN ('owner','writer'))
 AND NOT EXISTS(SELECT 1 FROM public.analysis_authority_barriers b
 WHERE b.study_id=sid AND b.analysis_command=parent)
 AND (a.actor_id IS NULL OR EXISTS(SELECT 1 FROM public.agent_delegations pinned
 WHERE pinned.delegation_id=r.request::jsonb#>>'{authority,delegation_id}'
 AND pinned.agent_actor_id=r.actor_id AND pinned.study_id=sid
 AND EXISTS(SELECT 1 FROM public.agent_delegations d WHERE d.agent_actor_id=r.actor_id
 AND d.study_id=sid AND d.created_at>=pinned.created_at AND d.revoked_at IS NULL)
 AND NOT EXISTS(SELECT 1 FROM public.agent_delegations d WHERE d.agent_actor_id=r.actor_id
 AND d.study_id=sid AND d.created_at>=pinned.created_at AND
 (d.role_ceiling<>'writer' OR NOT (d.allowed_effects::jsonb ? 'submit')
 OR (d.revoked_at IS NOT NULL AND d.revoked_reason IS DISTINCT FROM 'replaced'))))))
$$;
REVOKE ALL ON FUNCTION hyprn_analysis_authorized(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_analysis_authorized(TEXT,TEXT) TO hyprn_request;
CREATE OR REPLACE FUNCTION hyprn_analysis_active(sid TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM (SELECT public.hyprn_analysis_receipt(sid) AS r) x
 WHERE r IS NOT NULL
 AND (r->>'state'='pending_remote' OR current_setting('hyprn.analysis_child',true)='true')
 AND public.hyprn_analysis_authorized(sid,r->>'command_id'))
$$;

-- Operational resumption is explicit and independently audited; frozen requests
-- and scientific records never change. It cannot reopen cancellations or failures
-- from calculation/validation. Replaying launch never requests a resumption.
CREATE TABLE analysis_execution_resumptions(
 study_id TEXT NOT NULL REFERENCES studies(study_id), command_id TEXT NOT NULL,
 analysis_command TEXT NOT NULL, actor_id TEXT NOT NULL,
 previous_result TEXT NOT NULL, resumed_result TEXT NOT NULL,
 PRIMARY KEY(study_id,command_id)
);
ALTER TABLE analysis_execution_resumptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_execution_resumptions FORCE ROW LEVEL SECURITY;
CREATE POLICY analysis_resumptions_owner ON analysis_execution_resumptions TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE POLICY analysis_resumptions_read ON analysis_execution_resumptions FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id));
CREATE POLICY analysis_resumptions_insert ON analysis_execution_resumptions FOR INSERT TO hyprn_request
 WITH CHECK(actor_id=hyprn_actor() AND hyprn_member(study_id,true)
 AND hyprn_analysis_authorized(study_id,analysis_command)
 AND (hyprn_human()=hyprn_actor() OR EXISTS(SELECT 1 FROM agent_delegations d
 WHERE d.agent_actor_id=hyprn_actor() AND d.study_id=analysis_execution_resumptions.study_id
 AND d.revoked_at IS NULL AND d.expires_at>extract(epoch FROM statement_timestamp())
 AND d.role_ceiling='writer' AND d.allowed_effects::jsonb ? 'submit'))
 AND previous_result::jsonb->>'state'='failed'
 AND previous_result::jsonb->>'admission_state'='revoked'
 AND resumed_result::jsonb=previous_result::jsonb ||
 '{"state":"calculating","admission_state":"ready","reason":null}'::jsonb);
CREATE TRIGGER analysis_resumptions_fixed BEFORE UPDATE OR DELETE ON analysis_execution_resumptions
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
GRANT SELECT,INSERT ON analysis_execution_resumptions TO hyprn_request;
CREATE OR REPLACE FUNCTION hyprn_receipt_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.scope,NEW.category,NEW.command_id,NEW.actor_id,NEW.payload_digest)
 IS DISTINCT FROM (OLD.scope,OLD.category,OLD.command_id,OLD.actor_id,OLD.payload_digest) THEN
 RAISE EXCEPTION 'accepted command identity is immutable' USING ERRCODE='23514';
 END IF;
 IF OLD.state IN ('committed','rejected') AND NEW IS DISTINCT FROM OLD AND NOT (
 OLD.category='analysis_execution' AND OLD.state='committed' AND NEW.state='pending_remote'
 AND NEW.request IS NOT DISTINCT FROM OLD.request AND NEW.error IS NOT DISTINCT FROM OLD.error
 AND public.hyprn_analysis_authorized(OLD.scope,OLD.command_id)
 AND EXISTS(SELECT 1 FROM public.analysis_execution_resumptions a
 WHERE a.study_id=OLD.scope AND a.analysis_command=OLD.command_id
 AND a.actor_id=public.hyprn_actor() AND a.previous_result=OLD.result AND a.resumed_result=NEW.result)) THEN
 RAISE EXCEPTION 'terminal command outcome is immutable without authorized recovery' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
