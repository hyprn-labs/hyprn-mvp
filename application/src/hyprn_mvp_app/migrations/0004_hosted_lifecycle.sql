-- Installation identity is immutable; maintenance sees counts, never domain rows.
CREATE TABLE hyprn_installation_identity (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 installation_id TEXT NOT NULL,
 store_id TEXT NOT NULL
);
CREATE FUNCTION hyprn_immutable_installation() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public AS $$
 BEGIN RAISE EXCEPTION 'installation identity is immutable' USING ERRCODE='42501'; END $$;
CREATE TRIGGER hyprn_installation_immutable BEFORE UPDATE OR DELETE
 ON hyprn_installation_identity FOR EACH ROW EXECUTE FUNCTION hyprn_immutable_installation();
GRANT SELECT ON hyprn_installation_identity TO hyprn_request;
CREATE FUNCTION hyprn_lifecycle_counts() RETURNS TABLE(pending BIGINT, uncertain BIGINT)
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT
 (SELECT count(*) FROM public.outbox WHERE state IN ('accepted_run','dispatching','uncertain')) +
 (SELECT count(*) FROM public.computational_record_requests WHERE state IN ('queued','building')) +
 (SELECT count(*) FROM public.receipts WHERE state IN ('pending_remote','uncertain')) +
 (SELECT count(*) FROM public.assistant_conversations WHERE active_turn IS NOT NULL),
 (SELECT count(*) FROM public.outbox WHERE state IN ('dispatching','uncertain')) +
 (SELECT count(*) FROM public.receipts WHERE state='uncertain') +
 (SELECT count(*) FROM public.assistant_conversations WHERE active_turn IS NOT NULL AND state='blocked')
 $$;
REVOKE ALL ON FUNCTION hyprn_lifecycle_counts() FROM PUBLIC;
REVOKE ALL ON FUNCTION hyprn_immutable_installation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_lifecycle_counts() TO hyprn_request;
