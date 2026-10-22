-- Rechecks must compare every retained byte without repeatedly reading large
-- artifact payloads. PostgreSQL maintains this fingerprint on every payload write;
-- request/background roles cannot assign a stale or forged value to it.
DO $$ BEGIN
 IF current_setting('server_encoding') <> 'UTF8' THEN
  RAISE EXCEPTION 'Retained fingerprints require UTF8 storage';
 END IF;
END $$;

-- Fixed UTF8 input/output makes this byte conversion independent of client
-- encoding and session settings. Schema ownership remains migration-only.
CREATE FUNCTION hyprn_payload_sha256(value TEXT) RETURNS TEXT
LANGUAGE SQL IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
 SELECT encode(sha256(convert_to(value, 'UTF8')), 'hex')
$$;

ALTER TABLE outbox ADD COLUMN payload_sha256 TEXT
 GENERATED ALWAYS AS (hyprn_payload_sha256(payload)) STORED;
