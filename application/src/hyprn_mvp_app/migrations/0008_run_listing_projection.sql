-- Lists need lifecycle fields, not repeated parsing of full execution archives.
-- This stored projection is maintained by PostgreSQL on every original write;
-- clients cannot assign stale values. It does not establish scientific validity.
CREATE FUNCTION hyprn_run_summary(value TEXT) RETURNS JSONB
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
DECLARE
 document JSONB;
 artifacts JSONB;
BEGIN
 document := value::jsonb;
 SELECT coalesce(jsonb_agg(artifact ORDER BY position), '[]'::jsonb)
 INTO artifacts
 FROM jsonb_array_elements(
  CASE WHEN jsonb_typeof(document#>'{history,artifacts}')='array'
   THEN document#>'{history,artifacts}' ELSE '[]'::jsonb END
 ) WITH ORDINALITY AS entries(artifact,position)
 WHERE artifact->>'path'='result.json';
 RETURN jsonb_build_object(
  'preparation_state', document->'preparation_state',
  'status', document->'status',
  'history', jsonb_build_object('results', document#>'{history,results}',
                               'artifacts', artifacts)
 );
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
 -- Preserve corrupt originals for the full diagnostic reader, never invent results.
 RETURN '{}'::jsonb;
END
$$;

ALTER TABLE outbox ADD COLUMN read_summary JSONB
 GENERATED ALWAYS AS (hyprn_run_summary(payload)) STORED;
