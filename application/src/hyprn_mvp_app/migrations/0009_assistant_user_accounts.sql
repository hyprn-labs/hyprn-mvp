-- Accounting survives archiving and membership changes. The first human to start
-- a study conversation owns its cumulative provider spend, including subagents.
-- Only the existing background accounting authority can see these identifiers.
CREATE FUNCTION hyprn_assistant_user_accounts() RETURNS TABLE(
 study_id TEXT,conversation_id TEXT,provider_id TEXT,provision TEXT,
 reserved_cents INTEGER,active_turn TEXT,state TEXT,actor_id TEXT)
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT c.study_id,c.conversation_id,c.provider_id,c.provision,
 c.reserved_cents,c.active_turn,c.state,
 (SELECT t.actor_id FROM public.assistant_turns t WHERE t.study_id=c.study_id
  ORDER BY t.created_at,t.turn_id LIMIT 1)
 FROM public.assistant_conversations c $$;
REVOKE ALL ON FUNCTION hyprn_assistant_user_accounts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_assistant_user_accounts() TO hyprn_assistant_background;
