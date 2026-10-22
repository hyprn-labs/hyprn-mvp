-- Original outbox text and its fingerprint remain byte-for-byte intact. Only
-- explicit migration authority backfills this operational projection.
CREATE TABLE execution_operations (
 run_id TEXT PRIMARY KEY REFERENCES run_associations(run_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 actor_id TEXT NOT NULL,
 command_id TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('accepted_run','dispatching','recorded','uncertain')),
 preparation_state TEXT CHECK(preparation_state IN ('prepared','preparation_failed')),
 payload TEXT NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(payload::jsonb)='object'
   AND payload::jsonb - 'status' - 'history' = '{}'::jsonb),
 payload_sha256 TEXT GENERATED ALWAYS AS (hyprn_payload_sha256(payload)) STORED,
 read_summary JSONB GENERATED ALWAYS AS (hyprn_run_summary(payload)) STORED
);

CREATE FUNCTION hyprn_execution_projection(value TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
 SELECT ((CASE WHEN value::jsonb ? 'status' THEN jsonb_build_object('status',value::jsonb->'status')
          ELSE '{}'::jsonb END) ||
         (CASE WHEN value::jsonb ? 'history' THEN jsonb_build_object('history',value::jsonb->'history')
          ELSE '{}'::jsonb END))::text
$$;

INSERT INTO execution_operations(run_id,study_id,actor_id,command_id,state,preparation_state,payload)
 SELECT r.run_id,r.study_id,coalesce(o.payload::jsonb->>'actor',c.actor_id,''),r.command_id,
        o.state,o.payload::jsonb->>'preparation_state',hyprn_execution_projection(o.payload)
 FROM outbox o JOIN run_associations r USING(run_id)
 LEFT JOIN receipts c ON c.scope=r.study_id AND c.category='run' AND c.command_id=r.command_id;

ALTER TABLE execution_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_operations FORCE ROW LEVEL SECURITY;
CREATE POLICY execution_read ON execution_operations FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id,false));
CREATE POLICY execution_insert ON execution_operations FOR INSERT TO hyprn_request
 WITH CHECK(hyprn_member(study_id,true) AND EXISTS(SELECT 1 FROM run_associations r
 WHERE r.run_id=execution_operations.run_id AND r.study_id=execution_operations.study_id
 AND r.command_id=execution_operations.command_id));
CREATE POLICY execution_update ON execution_operations FOR UPDATE TO hyprn_request
 USING(hyprn_member(study_id,true)) WITH CHECK(hyprn_member(study_id,true));
CREATE POLICY execution_owner ON execution_operations TO hyprn_migration USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON execution_operations TO hyprn_request;

CREATE FUNCTION hyprn_execution_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN
 IF (NEW.run_id,NEW.study_id,NEW.actor_id,NEW.command_id) IS DISTINCT FROM
    (OLD.run_id,OLD.study_id,OLD.actor_id,OLD.command_id) THEN
  RAISE EXCEPTION 'execution identity is immutable' USING ERRCODE='23514';
 END IF;
 IF NEW.payload IS DISTINCT FROM OLD.payload AND OLD.payload::jsonb#>'{history,errors}'='[]'::jsonb
 AND OLD.payload::jsonb->'history' IS DISTINCT FROM NEW.payload::jsonb->'history' THEN
  RAISE EXCEPTION 'completed retained projection is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
 END $$;
CREATE TRIGGER execution_fixed BEFORE UPDATE ON execution_operations
 FOR EACH ROW EXECUTE FUNCTION hyprn_execution_fixed();
CREATE TRIGGER execution_no_delete BEFORE DELETE ON execution_operations
 FOR EACH ROW EXECUTE FUNCTION hyprn_reject_delete();

-- Acceptance and preparation write the source once. Legacy owner fixture/import
-- writes also maintain the projection atomically. Lifecycle writes use only the
-- operational table, so never detoast, hash or parse the retained bundle.
CREATE FUNCTION hyprn_execution_sync() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN
 INSERT INTO execution_operations(run_id,study_id,actor_id,command_id,state,preparation_state,payload)
 SELECT r.run_id,r.study_id,coalesce(NEW.payload::jsonb->>'actor',''),r.command_id,
        NEW.state,NEW.payload::jsonb->>'preparation_state',hyprn_execution_projection(NEW.payload)
 FROM run_associations r WHERE r.run_id=NEW.run_id
 ON CONFLICT(run_id) DO UPDATE SET
 state=CASE WHEN TG_OP='UPDATE' AND OLD.state=NEW.state THEN execution_operations.state ELSE excluded.state END,
 preparation_state=coalesce(excluded.preparation_state,execution_operations.preparation_state),
 payload=(execution_operations.payload::jsonb || excluded.payload::jsonb)::text;
 RETURN NEW;
 END $$;
CREATE TRIGGER execution_sync AFTER INSERT OR UPDATE OF payload,state ON outbox
 FOR EACH ROW EXECUTE FUNCTION hyprn_execution_sync();

CREATE INDEX execution_pending ON execution_operations(run_id)
 INCLUDE(study_id,actor_id,command_id,state)
 WHERE state IN ('accepted_run','dispatching')
 AND (preparation_state IS NULL OR preparation_state<>'preparation_failed');
CREATE INDEX execution_actor_pending ON execution_operations(actor_id,state)
 WHERE state IN ('accepted_run','dispatching','uncertain')
 AND (preparation_state IS NULL OR preparation_state<>'preparation_failed');
CREATE INDEX receipts_background_pending ON receipts(category,command_id)
 INCLUDE(scope,actor_id) WHERE state='pending_remote';

-- Keep the two-argument function for existing owners; the paged variant lets
-- callers retain a work_id cursor and wrap after exhaustion without starvation.
CREATE FUNCTION hyprn_background_jobs_page(category TEXT, identity TEXT, after_id TEXT, page_size INTEGER)
 RETURNS TABLE(study_id TEXT,actor_id TEXT,work_id TEXT) LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$
 BEGIN
 IF page_size<1 OR page_size>100 THEN RAISE EXCEPTION 'bounded page required'; END IF;
 IF category='run' AND session_user='hyprn_dispatcher_background' THEN
  RETURN QUERY SELECT o.study_id,o.actor_id,o.run_id FROM public.execution_operations o
  WHERE o.state IN ('accepted_run','dispatching')
  AND (o.preparation_state IS NULL OR o.preparation_state<>'preparation_failed')
  AND (identity IS NULL OR o.run_id=identity) AND (after_id IS NULL OR o.run_id>after_id)
  ORDER BY o.run_id LIMIT page_size;
 ELSIF category IN ('analysis_execution','calculation_sample','calculation_estimate','calculation_prediction')
 AND session_user='hyprn_dispatcher_background' THEN
  RETURN QUERY SELECT r.scope,r.actor_id,r.command_id FROM public.receipts r
  WHERE r.category=hyprn_background_jobs_page.category AND r.state='pending_remote'
  AND (identity IS NULL OR r.command_id=identity) AND (after_id IS NULL OR r.command_id>after_id)
  ORDER BY r.command_id LIMIT page_size;
 ELSIF category='assistant' AND session_user='hyprn_assistant_background' THEN
  RETURN QUERY SELECT c.study_id,t.actor_id,c.study_id FROM public.assistant_conversations c
  JOIN public.assistant_turns t ON t.turn_id=c.active_turn
  WHERE (identity IS NULL OR c.study_id=identity) AND (after_id IS NULL OR c.study_id>after_id)
  ORDER BY c.study_id LIMIT page_size;
 ELSIF category='export' AND session_user='hyprn_dispatcher_background' THEN
  RETURN QUERY SELECT r.study_id,r.actor_id,r.request_id FROM public.computational_record_requests r
  WHERE r.state IN ('queued','building') AND (identity IS NULL OR r.request_id=identity)
  AND (after_id IS NULL OR r.request_id>after_id) ORDER BY r.request_id LIMIT page_size;
 ELSE RAISE EXCEPTION 'background purpose not permitted' USING ERRCODE='42501';
 END IF;
 END $$;
CREATE OR REPLACE FUNCTION hyprn_background_jobs(category TEXT, identity TEXT DEFAULT NULL)
 RETURNS TABLE(study_id TEXT,actor_id TEXT,work_id TEXT) LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$
 BEGIN
 IF category='assistant' AND session_user='hyprn_assistant_background' THEN
  RETURN QUERY SELECT c.study_id,t.actor_id,c.study_id FROM public.assistant_conversations c
  JOIN public.assistant_turns t ON t.turn_id=c.active_turn
  WHERE identity IS NULL OR c.study_id=identity ORDER BY (t.delivery='new'),t.created_at LIMIT 100;
 ELSE
  RETURN QUERY SELECT * FROM public.hyprn_background_jobs_page(category,identity,NULL,
   CASE WHEN category='run' THEN 100 ELSE 1 END);
 END IF;
 END
$$;
REVOKE ALL ON FUNCTION hyprn_execution_projection(TEXT),hyprn_execution_fixed(),hyprn_execution_sync(),
 hyprn_background_jobs_page(TEXT,TEXT,TEXT,INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_execution_projection(TEXT) TO hyprn_request;
GRANT EXECUTE ON FUNCTION hyprn_background_jobs_page(TEXT,TEXT,TEXT,INTEGER)
 TO hyprn_dispatcher_background,hyprn_assistant_background;

CREATE OR REPLACE FUNCTION hyprn_lifecycle_counts() RETURNS TABLE(pending BIGINT, uncertain BIGINT)
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT
 (SELECT count(*) FROM public.execution_operations
  WHERE state IN ('accepted_run','dispatching','uncertain')
  AND (preparation_state IS NULL OR preparation_state<>'preparation_failed')) +
 (SELECT count(*) FROM public.computational_record_requests WHERE state IN ('queued','building')) +
 (SELECT count(*) FROM public.receipts WHERE state IN ('pending_remote','uncertain')) +
 (SELECT count(*) FROM public.assistant_conversations WHERE active_turn IS NOT NULL),
 (SELECT count(*) FROM public.execution_operations WHERE state IN ('dispatching','uncertain')) +
 (SELECT count(*) FROM public.receipts WHERE state='uncertain') +
 (SELECT count(*) FROM public.assistant_conversations WHERE active_turn IS NOT NULL AND state='blocked')
$$;
