-- Incremental Assistant reads retain immutable events and project public messages.
-- Apply only under the existing migration authority with writers fenced.
-- Retained payload/event identity/position are untouched; only derived fields change.
ALTER TABLE assistant_conversations ADD COLUMN provider_cursor TEXT;
ALTER TABLE assistant_events ADD COLUMN event_type TEXT NOT NULL DEFAULT '';
ALTER TABLE assistant_events ADD COLUMN processed_at TEXT;
ALTER TABLE assistant_events ADD COLUMN reference_id TEXT;
ALTER TABLE assistant_events DISABLE TRIGGER immutable_record;
UPDATE assistant_events SET
 event_type=COALESCE(payload::jsonb->>'type',''),
 processed_at=COALESCE(payload::jsonb->>'created_at',payload::jsonb->>'processed_at'),
 reference_id=CASE
  WHEN payload::jsonb->>'type'='user.custom_tool_result' THEN payload::jsonb->>'custom_tool_use_id'
  WHEN payload::jsonb->>'type' IN ('hyprn.turn_started','hyprn.turn_resumed') THEN
   COALESCE(payload::jsonb->>'turn_id',substring(event_id FROM 14))
  WHEN payload::jsonb->>'type'='user.message' THEN
   (SELECT substring(item->>'text' FROM 26) FROM jsonb_array_elements(payload::jsonb->'content') item
    WHERE item->>'type'='text' AND item->>'text' LIKE 'HYPRN request reference: %' LIMIT 1)
  ELSE NULL END;
ALTER TABLE assistant_events ENABLE TRIGGER immutable_record;
CREATE INDEX assistant_events_study_position ON assistant_events(study_id,position);
CREATE INDEX assistant_events_study_type_position ON assistant_events(study_id,event_type,position);
CREATE INDEX assistant_events_study_reference ON assistant_events(study_id,reference_id,event_type);
UPDATE assistant_conversations c SET provider_cursor=(
 SELECT max(e.processed_at) FROM assistant_events e WHERE e.study_id=c.study_id);

CREATE TABLE assistant_public_messages (
 position BIGSERIAL PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(study_id),
 message_id TEXT NOT NULL UNIQUE,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),
 text TEXT NOT NULL,
 actor_id TEXT,
 author_display_name TEXT,
 created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX assistant_public_messages_study_position ON assistant_public_messages(study_id,position);

-- Use public application identities derived deterministically from scoped events.
-- New code uses the same SHA-256 first-128-bits UUID representation.
INSERT INTO assistant_public_messages(study_id,message_id,role,text,actor_id,author_display_name,created_at)
SELECT study_id,message_id,role,text,actor_id,author_display_name,created_at FROM (
 SELECT t.study_id,t.turn_id AS message_id,'user'::text AS role,t.text,t.actor_id,
 COALESCE(t.author_display_name,u.username,'Former member') AS author_display_name,t.created_at
 FROM assistant_turns t LEFT JOIN users u ON u.actor_id=t.actor_id
 UNION ALL
 SELECT e.study_id,
 (substring(encode(sha256(convert_to(e.study_id || ':' || e.event_id,'UTF8')),'hex') FROM 1 FOR 32)::uuid)::text,
 'assistant',left(p.text,65536),NULL,NULL,(e.payload::jsonb->>'_received_at')::double precision
 FROM assistant_events e CROSS JOIN LATERAL (
 SELECT string_agg(item->>'text',E'\n' ORDER BY ordinal) AS text
 FROM jsonb_array_elements(e.payload::jsonb->'content') WITH ORDINALITY AS content(item,ordinal)
 WHERE item->>'type'='text' AND jsonb_typeof(item->'text')='string'
 ) p
 WHERE e.event_type='agent.message' AND COALESCE(e.payload::jsonb->>'session_thread_id','')=''
 AND p.text IS NOT NULL AND p.text<>''
) messages ORDER BY created_at,message_id;

ALTER TABLE assistant_public_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_public_messages FORCE ROW LEVEL SECURITY;
CREATE POLICY assistant_public_messages_read ON assistant_public_messages FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id,false));
CREATE POLICY assistant_public_messages_insert ON assistant_public_messages FOR INSERT TO hyprn_request
 WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY assistant_public_messages_owner ON assistant_public_messages TO hyprn_migration
 USING(true) WITH CHECK(true);
GRANT SELECT,INSERT ON assistant_public_messages TO hyprn_request;
GRANT USAGE,SELECT ON SEQUENCE assistant_public_messages_position_seq TO hyprn_request;
CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON assistant_public_messages
 FOR EACH ROW EXECUTE FUNCTION immutable_evidence_update_fn();
