-- Disposable results of full retained admission. Original outbox bytes remain
-- authoritative; readers recheck their database-owned fingerprint and receipt.
CREATE TABLE retained_read_cache (
 run_id TEXT PRIMARY KEY REFERENCES run_associations(run_id),
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 reader_sha256 TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(octet_length(payload)<=1048576),
 payload_sha256 TEXT NOT NULL
);
ALTER TABLE retained_read_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE retained_read_cache FORCE ROW LEVEL SECURITY;
CREATE POLICY retained_cache_owner ON retained_read_cache TO hyprn_migration
 USING(true) WITH CHECK(true);
CREATE POLICY retained_cache_scope ON retained_read_cache TO hyprn_request
 USING(hyprn_member(study_id))
 WITH CHECK(hyprn_member(study_id) AND EXISTS(
 SELECT 1 FROM run_associations r WHERE r.run_id=retained_read_cache.run_id
 AND r.study_id=retained_read_cache.study_id));
GRANT SELECT,INSERT,UPDATE ON retained_read_cache TO hyprn_request;
