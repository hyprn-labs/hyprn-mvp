-- Accepted finite analyses retain only their frozen command authority after a
-- reasoning credential expires. Ordinary hyprn_member is deliberately unchanged.
CREATE TABLE analysis_execution_children(
 study_id TEXT NOT NULL REFERENCES studies(study_id), analysis_command TEXT NOT NULL,
 child_category TEXT NOT NULL CHECK(child_category IN ('run','calculation_estimate')),
 child_command TEXT NOT NULL, run_id TEXT,
 PRIMARY KEY(study_id,child_category,child_command), UNIQUE(run_id)
);
ALTER TABLE analysis_execution_children ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_execution_children FORCE ROW LEVEL SECURITY;
CREATE POLICY analysis_children_owner ON analysis_execution_children TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE TRIGGER analysis_children_fixed BEFORE UPDATE ON analysis_execution_children
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
CREATE TRIGGER analysis_children_no_delete BEFORE DELETE ON analysis_execution_children
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
GRANT SELECT,INSERT ON analysis_execution_children TO hyprn_request;

-- Identity-only owner discovery; no request role can discover another actor's jobs.
CREATE FUNCTION hyprn_analysis_child_job(kind TEXT, identity TEXT)
RETURNS TABLE(study_id TEXT,analysis_command TEXT,actor_id TEXT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF session_user<>'hyprn_dispatcher_background' THEN
  RAISE EXCEPTION 'dispatcher purpose required' USING ERRCODE='42501';
 END IF;
 RETURN QUERY SELECT c.study_id,c.analysis_command,r.actor_id
 FROM public.analysis_execution_children c JOIN public.receipts r
 ON r.scope=c.study_id AND r.category='analysis_execution' AND r.command_id=c.analysis_command
 WHERE c.child_category=kind AND (CASE WHEN kind='run' THEN c.run_id ELSE c.child_command END)=identity;
END $$;

CREATE FUNCTION hyprn_analysis_receipt(sid TEXT) RETURNS JSONB
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT to_jsonb(r) FROM public.receipts r
 WHERE r.scope=sid AND sid=current_setting('hyprn.analysis_study',true)
 AND r.category='analysis_execution' AND r.command_id=current_setting('hyprn.analysis_command',true)
 AND r.actor_id=public.hyprn_actor() AND r.request::jsonb#>>'{authority,actor_id}'=r.actor_id
$$;
CREATE FUNCTION hyprn_analysis_active(sid TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM (SELECT public.hyprn_analysis_receipt(sid) AS r) x
 WHERE r IS NOT NULL
 AND (r->>'state'='pending_remote' OR current_setting('hyprn.analysis_child',true)='true')
 AND EXISTS(SELECT 1 FROM public.memberships m WHERE m.study_id=sid
 AND m.actor_id=public.hyprn_human() AND m.role IN ('owner','writer'))
 AND (public.hyprn_human()=public.hyprn_actor() OR EXISTS(
 SELECT 1 FROM public.agent_delegations d
 WHERE d.delegation_id=(r->>'request')::jsonb#>>'{authority,delegation_id}'
 AND d.agent_actor_id=public.hyprn_actor() AND d.study_id=sid
 AND d.revoked_at IS NULL AND d.role_ceiling='writer' AND d.allowed_effects::jsonb ? 'submit')))
$$;
CREATE FUNCTION hyprn_analysis_command(sid TEXT,kind TEXT,command TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT public.hyprn_analysis_active(sid)
 AND (public.hyprn_analysis_receipt(sid)->>'state')='pending_remote'
 AND coalesce(current_setting('hyprn.analysis_child',true),'false')<>'true'
 AND CASE WHEN kind='run' THEN
 ((public.hyprn_analysis_receipt(sid)->>'request')::jsonb->'run_commands') ? command
 WHEN kind='calculation_estimate' THEN
 (public.hyprn_analysis_receipt(sid)->>'request')::jsonb->>'estimate_command'=command
 AND (public.hyprn_analysis_receipt(sid)->>'request')::jsonb->'estimate_plan'<>'null'::jsonb
 ELSE false END
$$;
CREATE FUNCTION hyprn_analysis_child(sid TEXT,kind TEXT,command TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT public.hyprn_analysis_receipt(sid) IS NOT NULL AND EXISTS(
 SELECT 1 FROM public.analysis_execution_children c WHERE c.study_id=sid
 AND c.analysis_command=current_setting('hyprn.analysis_command',true)
 AND c.child_category=kind AND c.child_command=command)
$$;
CREATE FUNCTION hyprn_analysis_run(rid TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.run_associations r WHERE r.run_id=rid AND
 (public.hyprn_analysis_child(r.study_id,'run',r.command_id)
 OR (public.hyprn_analysis_command(r.study_id,'run',r.command_id) AND
 (public.hyprn_analysis_receipt(r.study_id)->>'request')::jsonb#>>ARRAY['run_commands',r.command_id]
 =r.configuration_revision_id)))
$$;

CREATE POLICY analysis_receipt_read ON receipts FOR SELECT TO hyprn_request USING(
 (category='analysis_execution' AND command_id=current_setting('hyprn.analysis_command',true)
 AND hyprn_analysis_receipt(scope) IS NOT NULL)
 OR (category IN ('run','calculation_estimate') AND hyprn_analysis_active(scope))
 OR hyprn_analysis_child(scope,category,command_id));
CREATE POLICY analysis_receipt_insert ON receipts FOR INSERT TO hyprn_request WITH CHECK(
 actor_id=hyprn_actor() AND hyprn_analysis_command(scope,category,command_id));
CREATE POLICY analysis_receipt_update ON receipts FOR UPDATE TO hyprn_request USING(
 (category='analysis_execution' AND command_id=current_setting('hyprn.analysis_command',true)
 AND hyprn_analysis_receipt(scope) IS NOT NULL) OR hyprn_analysis_child(scope,category,command_id))
 WITH CHECK((category='analysis_execution' AND command_id=current_setting('hyprn.analysis_command',true)
 AND hyprn_analysis_receipt(scope) IS NOT NULL) OR hyprn_analysis_child(scope,category,command_id));
CREATE POLICY analysis_children_read ON analysis_execution_children FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id) OR hyprn_analysis_child(study_id,child_category,child_command));
CREATE POLICY analysis_children_insert ON analysis_execution_children FOR INSERT TO hyprn_request
 WITH CHECK(analysis_command=current_setting('hyprn.analysis_command',true)
 AND hyprn_analysis_command(study_id,child_category,child_command)
 AND ((child_category='run' AND EXISTS(SELECT 1 FROM run_associations r WHERE r.run_id=analysis_execution_children.run_id
 AND r.study_id=analysis_execution_children.study_id AND r.command_id=child_command))
 OR (child_category='calculation_estimate' AND run_id IS NULL)));
CREATE POLICY analysis_runs_read ON run_associations FOR SELECT TO hyprn_request
 USING(hyprn_analysis_active(study_id) OR hyprn_analysis_child(study_id,'run',command_id));
CREATE POLICY analysis_runs_insert ON run_associations FOR INSERT TO hyprn_request WITH CHECK(
 hyprn_analysis_command(study_id,'run',command_id) AND
 (hyprn_analysis_receipt(study_id)->>'request')::jsonb#>>ARRAY['run_commands',command_id]=configuration_revision_id);
CREATE POLICY analysis_runs_update ON run_associations FOR UPDATE TO hyprn_request
 USING(hyprn_analysis_child(study_id,'run',command_id))
 WITH CHECK(hyprn_analysis_child(study_id,'run',command_id));
CREATE POLICY analysis_outbox_read ON outbox FOR SELECT TO hyprn_request USING(hyprn_analysis_run(run_id));
CREATE POLICY analysis_outbox_insert ON outbox FOR INSERT TO hyprn_request WITH CHECK(hyprn_analysis_run(run_id));
CREATE POLICY analysis_outbox_update ON outbox FOR UPDATE TO hyprn_request
 USING(hyprn_analysis_run(run_id)) WITH CHECK(hyprn_analysis_run(run_id));
CREATE POLICY analysis_execution_read ON execution_operations FOR SELECT TO hyprn_request
 USING(hyprn_analysis_active(study_id) OR hyprn_analysis_run(run_id));
CREATE POLICY analysis_execution_insert ON execution_operations FOR INSERT TO hyprn_request
 WITH CHECK(actor_id=hyprn_actor() AND hyprn_analysis_run(run_id));
CREATE POLICY analysis_execution_update ON execution_operations FOR UPDATE TO hyprn_request
 USING(hyprn_analysis_run(run_id)) WITH CHECK(hyprn_analysis_run(run_id));
CREATE POLICY analysis_delegation_read ON agent_delegations FOR SELECT TO hyprn_request
 USING(agent_actor_id=hyprn_actor() AND delegation_id=
 (hyprn_analysis_receipt(study_id)->>'request')::jsonb#>>'{authority,delegation_id}');
CREATE POLICY analysis_membership_read ON memberships FOR SELECT TO hyprn_request
 USING(actor_id=hyprn_human() AND hyprn_analysis_receipt(study_id) IS NOT NULL);
CREATE POLICY analysis_attribution_read ON agent_attribution FOR SELECT TO hyprn_request
 USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_attribution_insert ON agent_attribution FOR INSERT TO hyprn_request
 WITH CHECK(agent_actor_id=hyprn_actor() AND delegator_actor_id=hyprn_human()
 AND hyprn_analysis_command(study_id,command_category,command_id));

-- Only immutable dependencies can be read through finite authority; there is no
-- scoped write policy for authoring tables, membership, sessions or credentials.
-- Preparation may read exact upstream configurations linked from a pinned member.
-- Scoped reads retain current study membership; writes still name only frozen commands.
CREATE POLICY analysis_configurations_read ON configurations FOR SELECT TO hyprn_request
 USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_versions_read ON calculation_versions FOR SELECT TO hyprn_request
 USING(hyprn_analysis_active(study_id) AND calculation_version_id=
 (hyprn_analysis_receipt(study_id)->>'request')::jsonb->>'calculation_version_id');
CREATE POLICY analysis_dependency_read ON studies FOR SELECT TO hyprn_request USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_dependency_read ON model_associations FOR SELECT TO hyprn_request USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_dependency_read ON evidence FOR SELECT TO hyprn_request USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_dependency_read ON study_brief_versions FOR SELECT TO hyprn_request USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_dependency_read ON calculations FOR SELECT TO hyprn_request USING(hyprn_analysis_active(study_id));
CREATE POLICY analysis_dependency_read ON reference_marks FOR SELECT TO hyprn_request USING(hyprn_analysis_active(study_id));
REVOKE ALL ON FUNCTION hyprn_analysis_child_job(TEXT,TEXT),hyprn_analysis_receipt(TEXT),
 hyprn_analysis_active(TEXT),hyprn_analysis_command(TEXT,TEXT,TEXT),hyprn_analysis_child(TEXT,TEXT,TEXT),
 hyprn_analysis_run(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_analysis_child_job(TEXT,TEXT) TO hyprn_dispatcher_background;
GRANT EXECUTE ON FUNCTION hyprn_analysis_receipt(TEXT),hyprn_analysis_active(TEXT),
 hyprn_analysis_command(TEXT,TEXT,TEXT),hyprn_analysis_child(TEXT,TEXT,TEXT),hyprn_analysis_run(TEXT)
 TO hyprn_request;

CREATE FUNCTION hyprn_analysis_request_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.category='analysis_execution' AND NEW.request IS DISTINCT FROM OLD.request THEN
 RAISE EXCEPTION 'accepted finite authority never changes' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER analysis_request_fixed BEFORE UPDATE ON receipts
 FOR EACH ROW EXECUTE FUNCTION hyprn_analysis_request_fixed();
REVOKE ALL ON FUNCTION hyprn_analysis_request_fixed() FROM PUBLIC;

CREATE FUNCTION hyprn_analysis_reused(sid TEXT,parent TEXT,command TEXT,rid TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT 1 FROM public.receipts r JOIN public.execution_operations x ON x.run_id=rid
 WHERE r.scope=sid AND r.category='analysis_execution' AND r.command_id=parent
 AND r.actor_id=public.hyprn_actor() AND r.state='pending_remote'
 AND r.request::jsonb#>>ARRAY['reused_runs',command]=rid
 AND x.actor_id=r.actor_id AND x.study_id=sid AND x.command_id=command)
$$;
CREATE POLICY analysis_children_reused ON analysis_execution_children FOR INSERT TO hyprn_request
 WITH CHECK(child_category='run' AND hyprn_member(study_id,true)
 AND hyprn_analysis_reused(study_id,analysis_command,child_command,run_id));
REVOKE ALL ON FUNCTION hyprn_analysis_reused(TEXT,TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_analysis_reused(TEXT,TEXT,TEXT,TEXT) TO hyprn_request;
