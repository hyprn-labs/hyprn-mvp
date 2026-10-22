-- A study keeps one HYPRN conversation while provider definitions advance only
-- between human turns. Every provider generation remains billable and inspectable.
CREATE TABLE assistant_provider_sessions (
 study_id TEXT NOT NULL REFERENCES studies(study_id), generation INTEGER NOT NULL,
 session_key TEXT NOT NULL UNIQUE, binding TEXT, billing_actor TEXT NOT NULL REFERENCES users(actor_id),
 initial_turn_id TEXT NOT NULL, handoff TEXT NOT NULL, provider_id TEXT UNIQUE,
 provision TEXT NOT NULL CHECK(provision IN ('new','intended','accepted')),
 created_at DOUBLE PRECISION NOT NULL, PRIMARY KEY(study_id,generation),
 CHECK(generation>0), CHECK((provision='accepted')=(provider_id IS NOT NULL))
);
INSERT INTO assistant_provider_sessions
 SELECT c.study_id,1,c.conversation_id,NULL,t.actor_id,t.turn_id,'',c.provider_id,c.provision,c.created_at
 FROM assistant_conversations c CROSS JOIN LATERAL (
 SELECT actor_id,turn_id FROM assistant_turns WHERE study_id=c.study_id
 ORDER BY created_at,turn_id LIMIT 1) t
 WHERE c.provision<>'new';

ALTER TABLE assistant_provider_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_provider_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY provider_sessions_read ON assistant_provider_sessions FOR SELECT TO hyprn_request
 USING(hyprn_member(study_id,false));
CREATE POLICY provider_sessions_insert ON assistant_provider_sessions FOR INSERT TO hyprn_request
 WITH CHECK(hyprn_member(study_id,false) AND billing_actor=(
 SELECT t.actor_id FROM assistant_turns t WHERE t.study_id=assistant_provider_sessions.study_id
 ORDER BY t.created_at,t.turn_id LIMIT 1) AND EXISTS(
 SELECT 1 FROM assistant_turns t WHERE t.study_id=assistant_provider_sessions.study_id
 AND t.turn_id=initial_turn_id));
CREATE POLICY provider_sessions_update ON assistant_provider_sessions FOR UPDATE TO hyprn_request
 USING(hyprn_member(study_id,false)) WITH CHECK(hyprn_member(study_id,false));
CREATE POLICY provider_sessions_owner ON assistant_provider_sessions TO hyprn_migration
 USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON assistant_provider_sessions TO hyprn_request;

CREATE FUNCTION hyprn_provider_session_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'provider session accounting is retained' USING ERRCODE='23514';
 END IF;
 IF (OLD.study_id,OLD.generation,OLD.session_key,OLD.binding,OLD.billing_actor,
     OLD.initial_turn_id,OLD.handoff,OLD.created_at) IS DISTINCT FROM
    (NEW.study_id,NEW.generation,NEW.session_key,NEW.binding,NEW.billing_actor,
     NEW.initial_turn_id,NEW.handoff,NEW.created_at) OR NOT (
    (OLD.provision='new' AND NEW.provision='intended' AND NEW.provider_id IS NULL) OR
    (OLD.provision='intended' AND NEW.provision='accepted' AND NEW.provider_id IS NOT NULL)) THEN
  RAISE EXCEPTION 'provider session identity is fixed' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER provider_session_fixed BEFORE UPDATE OR DELETE ON assistant_provider_sessions
 FOR EACH ROW EXECUTE FUNCTION hyprn_provider_session_fixed();
REVOKE ALL ON FUNCTION hyprn_provider_session_fixed() FROM PUBLIC;

CREATE OR REPLACE FUNCTION hyprn_assistant_user_accounts() RETURNS TABLE(
 study_id TEXT,conversation_id TEXT,provider_id TEXT,provision TEXT,
 reserved_cents INTEGER,active_turn TEXT,state TEXT,actor_id TEXT)
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT p.study_id,p.session_key,p.provider_id,p.provision,
 c.reserved_cents,c.active_turn,c.state,p.billing_actor
 FROM public.assistant_provider_sessions p
 JOIN public.assistant_conversations c ON c.study_id=p.study_id
 UNION ALL
 SELECT c.study_id,c.conversation_id,c.provider_id,c.provision,
 c.reserved_cents,c.active_turn,c.state,
 (SELECT t.actor_id FROM public.assistant_turns t WHERE t.study_id=c.study_id
 ORDER BY t.created_at,t.turn_id LIMIT 1)
 FROM public.assistant_conversations c WHERE NOT EXISTS (
 SELECT 1 FROM public.assistant_provider_sessions p WHERE p.study_id=c.study_id AND
 (p.provider_id=c.provider_id OR (c.provider_id IS NULL AND p.provision<>'accepted')))
$$;
REVOKE ALL ON FUNCTION hyprn_assistant_user_accounts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_assistant_user_accounts() TO hyprn_assistant_background;
