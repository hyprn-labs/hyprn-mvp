-- Repair only the operational refusal before preparation/claim, preserving its audit.
-- Source inputs, prepared bundles and recorded/uncertain executions never reset.
CREATE FUNCTION hyprn_analysis_unprepared(sid TEXT,parent TEXT,rid TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT public.hyprn_analysis_authorized(sid,parent) AND EXISTS(
 SELECT 1 FROM public.analysis_execution_children child
 JOIN public.receipts a ON a.scope=child.study_id AND a.category='analysis_execution'
 AND a.command_id=child.analysis_command
 JOIN public.run_associations r ON r.run_id=child.run_id AND r.study_id=child.study_id
 AND r.command_id=child.child_command
 JOIN public.outbox o ON o.run_id=r.run_id
 JOIN public.execution_operations x ON x.run_id=r.run_id
 JOIN public.receipts c ON c.scope=r.study_id AND c.category='run' AND c.command_id=r.command_id
 WHERE child.study_id=sid AND child.analysis_command=parent AND child.run_id=rid
 AND child.child_category='run' AND c.actor_id=a.actor_id AND x.actor_id=a.actor_id
 AND o.payload::jsonb->>'actor'=a.actor_id
 AND x.state='accepted_run' AND o.state='accepted_run' AND x.preparation_state='preparation_failed'
 AND r.store_uuid IS NULL AND r.process_uuid IS NULL AND x.payload::jsonb='{}'::jsonb
 AND o.payload::jsonb ?& ARRAY['actor','frozen']
 AND o.payload::jsonb - ARRAY['actor','frozen','expected_runtime','execution_budget']='{}'::jsonb
 AND c.state='preparation_failed' AND c.error::jsonb=
 '{"code":"analysis_authority_revoked","status":403,"current_revision":null,"fields":[],"outcome":"unchanged"}'::jsonb)
$$;
REVOKE ALL ON FUNCTION hyprn_analysis_unprepared(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_analysis_unprepared(TEXT,TEXT,TEXT) TO hyprn_request;

CREATE TABLE analysis_run_resumptions(
 study_id TEXT NOT NULL, command_id TEXT NOT NULL, analysis_command TEXT NOT NULL,
 run_id TEXT NOT NULL REFERENCES run_associations(run_id), child_command TEXT NOT NULL,
 actor_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, previous_receipt TEXT NOT NULL,
 previous_operation TEXT NOT NULL, created_transaction BIGINT NOT NULL DEFAULT txid_current(),
 PRIMARY KEY(study_id,command_id,run_id),
 FOREIGN KEY(study_id,command_id) REFERENCES analysis_execution_resumptions(study_id,command_id)
);
ALTER TABLE analysis_run_resumptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_run_resumptions FORCE ROW LEVEL SECURITY;
CREATE POLICY analysis_run_resumptions_owner ON analysis_run_resumptions TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE POLICY analysis_run_resumptions_read ON analysis_run_resumptions FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id));
CREATE POLICY analysis_run_resumptions_insert ON analysis_run_resumptions FOR INSERT TO hyprn_request
 WITH CHECK(actor_id=hyprn_actor() AND created_transaction=txid_current()
 AND hyprn_analysis_unprepared(study_id,analysis_command,run_id)
 AND EXISTS(SELECT 1 FROM analysis_execution_resumptions a
 WHERE a.study_id=analysis_run_resumptions.study_id AND a.command_id=analysis_run_resumptions.command_id
 AND a.analysis_command=analysis_run_resumptions.analysis_command AND a.actor_id=hyprn_actor())
 AND EXISTS(SELECT 1 FROM execution_operations x JOIN outbox o USING(run_id)
 JOIN receipts c ON c.scope=x.study_id AND c.category='run' AND c.command_id=x.command_id
 WHERE x.run_id=analysis_run_resumptions.run_id AND x.command_id=child_command
 AND o.payload_sha256=source_sha256
 AND previous_operation::jsonb=jsonb_build_object('state',x.state,
 'preparation_state',x.preparation_state,'payload',x.payload)
 AND previous_receipt::jsonb->>'scope'=c.scope
 AND previous_receipt::jsonb->>'category'=c.category
 AND previous_receipt::jsonb->>'command_id'=c.command_id
 AND previous_receipt::jsonb->>'actor_id'=c.actor_id
 AND previous_receipt::jsonb->>'state'=c.state
 AND previous_receipt::jsonb->>'payload_digest'=c.payload_digest
 AND previous_receipt::jsonb->'error'=c.error::jsonb
 AND previous_receipt::jsonb->'result'=c.result::jsonb
 AND previous_receipt::jsonb->'request'=coalesce(c.request::jsonb,'null'::jsonb)));
GRANT SELECT,INSERT ON analysis_run_resumptions TO hyprn_request;
CREATE TRIGGER analysis_run_resumptions_fixed BEFORE UPDATE OR DELETE ON analysis_run_resumptions
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();

-- Recovery audits also cover the parent stopped by these child refusals. No
-- validation failure or unrelated preparation failure becomes resumable here.
DROP POLICY analysis_resumptions_insert ON analysis_execution_resumptions;
CREATE POLICY analysis_resumptions_insert ON analysis_execution_resumptions FOR INSERT TO hyprn_request
 WITH CHECK(actor_id=hyprn_actor() AND hyprn_member(study_id,true)
 AND hyprn_analysis_authorized(study_id,analysis_command)
 AND (hyprn_human()=hyprn_actor() OR EXISTS(SELECT 1 FROM agent_delegations d
 WHERE d.agent_actor_id=hyprn_actor() AND d.study_id=analysis_execution_resumptions.study_id
 AND d.revoked_at IS NULL AND d.expires_at>extract(epoch FROM statement_timestamp())
 AND d.role_ceiling='writer' AND d.allowed_effects::jsonb ? 'submit'))
 AND previous_result::jsonb->>'state'='failed'
 AND (previous_result::jsonb->>'admission_state'='revoked' OR (
 previous_result::jsonb->>'admission_state'='stopped'
 AND previous_result::jsonb->>'reason'='A calculation could not start. Review its run diagnostics.'
 AND EXISTS(SELECT 1 FROM analysis_execution_children c
 WHERE c.study_id=analysis_execution_resumptions.study_id
 AND c.analysis_command=analysis_execution_resumptions.analysis_command
 AND c.child_category='run' AND hyprn_analysis_unprepared(c.study_id,c.analysis_command,c.run_id))))
 AND resumed_result::jsonb=previous_result::jsonb ||
 '{"state":"calculating","admission_state":"ready","reason":null}'::jsonb);

CREATE FUNCTION hyprn_analysis_preparation_reset() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.preparation_state='preparation_failed' AND NEW.preparation_state IS DISTINCT FROM OLD.preparation_state THEN
 IF NEW.state<>'accepted_run' OR NEW.preparation_state IS NOT NULL OR NEW.payload IS DISTINCT FROM OLD.payload
 OR NOT EXISTS(SELECT 1 FROM public.analysis_run_resumptions a
 WHERE a.run_id=OLD.run_id AND a.actor_id=public.hyprn_actor()
 AND a.created_transaction=txid_current()
 AND public.hyprn_analysis_unprepared(a.study_id,a.analysis_command,a.run_id)) THEN
 RAISE EXCEPTION 'preparation recovery needs a current authorized audit' USING ERRCODE='23514';
 END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER analysis_preparation_reset BEFORE UPDATE ON execution_operations
 FOR EACH ROW EXECUTE FUNCTION hyprn_analysis_preparation_reset();
REVOKE ALL ON FUNCTION hyprn_analysis_preparation_reset() FROM PUBLIC;
