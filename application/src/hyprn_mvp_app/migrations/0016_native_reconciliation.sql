-- Public resume authorizes a reconciliation, never supplies a native absence proof.
CREATE TABLE analysis_reconciliation_intents(
 study_id TEXT NOT NULL REFERENCES studies(study_id), command_id TEXT NOT NULL,
 analysis_command TEXT NOT NULL, actor_id TEXT NOT NULL, runs TEXT NOT NULL,
 previous_result TEXT NOT NULL, PRIMARY KEY(study_id,command_id)
);
CREATE TABLE analysis_reconciliation_results(
 study_id TEXT NOT NULL, command_id TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK(outcome IN ('not_started','unproven')), proof TEXT NOT NULL,
 created_transaction BIGINT NOT NULL DEFAULT txid_current(),
 PRIMARY KEY(study_id,command_id),
 FOREIGN KEY(study_id,command_id) REFERENCES analysis_reconciliation_intents(study_id,command_id)
);
ALTER TABLE analysis_reconciliation_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_reconciliation_intents FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_reconciliation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_reconciliation_results FORCE ROW LEVEL SECURITY;
CREATE POLICY reconciliation_intent_owner ON analysis_reconciliation_intents TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE POLICY reconciliation_result_owner ON analysis_reconciliation_results TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE POLICY reconciliation_intent_read ON analysis_reconciliation_intents FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id));
CREATE POLICY reconciliation_result_read ON analysis_reconciliation_results FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id));
CREATE POLICY reconciliation_intent_insert ON analysis_reconciliation_intents FOR INSERT TO hyprn_request
 WITH CHECK(actor_id=hyprn_actor() AND hyprn_member(study_id,true)
 AND hyprn_analysis_authorized(study_id,analysis_command)
 AND jsonb_array_length(runs::jsonb)>0
 AND EXISTS(SELECT 1 FROM receipts a WHERE a.scope=study_id AND a.category='analysis_execution'
 AND a.command_id=analysis_command AND a.state='pending_remote'
 AND a.result::jsonb->>'state'='needs_review' AND a.result::jsonb=previous_result::jsonb)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(runs::jsonb) item
 WHERE NOT EXISTS(SELECT 1 FROM analysis_execution_children c JOIN execution_operations x
 ON x.run_id=c.run_id JOIN outbox o ON o.run_id=x.run_id
 JOIN run_associations r ON r.run_id=x.run_id
 WHERE c.study_id=analysis_reconciliation_intents.study_id
 AND c.analysis_command=analysis_reconciliation_intents.analysis_command
 AND c.child_category='run' AND c.run_id=item->>'run_id'
 AND c.child_command=item->>'command_id' AND x.state='uncertain'
 AND r.store_uuid IS NULL AND r.process_uuid IS NULL
 AND o.payload_sha256=item->>'source_sha256'
 AND o.payload::jsonb->'request'=item->'request'
 AND o.payload::jsonb#>'{bundle,manifest,runtime}'=item->'runtime')));
CREATE POLICY reconciliation_result_insert ON analysis_reconciliation_results FOR INSERT TO hyprn_request
 WITH CHECK(session_user='hyprn_dispatcher_background' AND created_transaction=txid_current()
 AND EXISTS(SELECT 1 FROM analysis_reconciliation_intents i
 WHERE i.study_id=analysis_reconciliation_results.study_id
 AND i.command_id=analysis_reconciliation_results.command_id
 AND hyprn_analysis_authorized(i.study_id,i.analysis_command)));
GRANT SELECT,INSERT ON analysis_reconciliation_intents,analysis_reconciliation_results TO hyprn_request;
CREATE TRIGGER reconciliation_intent_fixed BEFORE UPDATE OR DELETE ON analysis_reconciliation_intents
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();
CREATE TRIGGER reconciliation_result_fixed BEFORE UPDATE OR DELETE ON analysis_reconciliation_results
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();

-- No client or periodic reconciliation can turn an uncertain launch into fresh work.
-- Only an audited native-owner proof in this transaction releases the original bundle.
CREATE FUNCTION hyprn_native_reconciliation_reset() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
 IF OLD.state IN ('uncertain','dispatching') AND NEW.state='accepted_run' THEN
 IF session_user<>'hyprn_dispatcher_background' OR OLD.state<>'uncertain'
 OR NEW.preparation_state<>'prepared' OR NEW.payload IS DISTINCT FROM OLD.payload
 OR NOT EXISTS(SELECT 1 FROM analysis_reconciliation_results a
 JOIN analysis_reconciliation_intents i USING(study_id,command_id)
 CROSS JOIN LATERAL jsonb_array_elements(a.proof::jsonb) p
 JOIN outbox o ON o.run_id=p->>'run_id'
 WHERE a.study_id=OLD.study_id AND a.outcome='not_started'
 AND a.created_transaction=txid_current()
 AND public.hyprn_analysis_authorized(i.study_id,i.analysis_command)
 AND p->>'run_id'=OLD.run_id AND p->>'command_id'=OLD.command_id
 AND p->>'source_sha256'=o.payload_sha256
 AND p->'request'=o.payload::jsonb->'request'
 AND p#>'{native,request}'=p->'request'
 AND p#>>'{native,outcome}'='not_started') THEN
 RAISE EXCEPTION 'uncertain execution requires an explicit native-owner proof' USING ERRCODE='23514';
 END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER native_reconciliation_reset BEFORE UPDATE ON execution_operations
 FOR EACH ROW EXECUTE FUNCTION hyprn_native_reconciliation_reset();
REVOKE ALL ON FUNCTION hyprn_native_reconciliation_reset() FROM PUBLIC;

-- The native owner's credential can publish only this bounded reconciliation result.
-- It cannot select an arbitrary actor, edit source bytes or release an unlinked run.
CREATE FUNCTION hyprn_reconcile_native(sid TEXT,cmd TEXT,outcome TEXT,proof_text TEXT)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE intent public.analysis_reconciliation_intents;
 parent public.receipts; item JSONB; released BOOLEAN;
BEGIN
 IF session_user<>'hyprn_dispatcher_background' THEN
 RAISE EXCEPTION 'native dispatcher required' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(68272601);
 SELECT * INTO STRICT intent FROM public.analysis_reconciliation_intents
 WHERE study_id=sid AND command_id=cmd;
 SELECT * INTO STRICT parent FROM public.receipts WHERE scope=sid
 AND category='analysis_execution' AND command_id=intent.analysis_command;
 PERFORM set_config('hyprn.actor_id',parent.actor_id,true);
 IF parent.state<>'pending_remote' OR NOT public.hyprn_analysis_authorized(sid,parent.command_id) THEN
 RAISE EXCEPTION 'analysis authority unavailable' USING ERRCODE='42501'; END IF;
 IF EXISTS(SELECT 1 FROM public.analysis_reconciliation_results WHERE study_id=sid AND command_id=cmd) THEN
 RETURN false; END IF;
 released := outcome='not_started' AND jsonb_typeof(proof_text::jsonb)='array'
 AND jsonb_array_length(proof_text::jsonb)=jsonb_array_length(intent.runs::jsonb)
 AND jsonb_array_length(proof_text::jsonb)>0;
 FOR item IN SELECT value FROM jsonb_array_elements(proof_text::jsonb) LOOP
 IF NOT (intent.runs::jsonb @> jsonb_build_array(item - 'native'))
 OR item#>>'{native,outcome}' IS DISTINCT FROM 'not_started'
 OR item#>'{native,request}' IS DISTINCT FROM item->'request'
 OR NOT EXISTS(SELECT 1 FROM public.execution_operations x JOIN public.outbox o USING(run_id)
 JOIN public.analysis_execution_children c ON c.run_id=x.run_id
 JOIN public.run_associations r ON r.run_id=x.run_id
 WHERE x.run_id=item->>'run_id' AND x.command_id=item->>'command_id' AND x.state='uncertain'
 AND r.store_uuid IS NULL AND r.process_uuid IS NULL
 AND c.study_id=sid AND c.analysis_command=intent.analysis_command AND c.child_category='run'
 AND o.payload_sha256=item->>'source_sha256'
 AND o.payload::jsonb->'request'=item->'request'
 AND o.payload::jsonb#>'{bundle,manifest,runtime}'=item->'runtime') THEN released := false; END IF;
 END LOOP;
 IF (SELECT count(DISTINCT value->>'run_id') FROM jsonb_array_elements(proof_text::jsonb))
 <>jsonb_array_length(intent.runs::jsonb) THEN released := false; END IF;
 INSERT INTO public.analysis_reconciliation_results(study_id,command_id,outcome,proof)
 VALUES(sid,cmd,CASE WHEN released THEN 'not_started' ELSE 'unproven' END,proof_text);
 IF released THEN
 FOR item IN SELECT value FROM jsonb_array_elements(intent.runs::jsonb) LOOP
 UPDATE public.execution_operations SET state='accepted_run',preparation_state='prepared'
 WHERE run_id=item->>'run_id';
 UPDATE public.receipts SET state='prepared',result=(result::jsonb || '{"state":"prepared"}'::jsonb)::text
 WHERE scope=sid AND category='run' AND command_id=item->>'command_id';
 END LOOP;
 END IF;
 RETURN released;
END $$;
REVOKE ALL ON FUNCTION hyprn_reconcile_native(TEXT,TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_reconcile_native(TEXT,TEXT,TEXT,TEXT) TO hyprn_dispatcher_background;
