-- Session creation serializes identities separately from the application writer.
-- 68272602 remains the live writer fence; keeping it here blocks every sign-in.
CREATE OR REPLACE FUNCTION hyprn_external_session(provider TEXT, person TEXT, token TEXT, csrf TEXT, contact TEXT)
RETURNS TABLE(actor_id TEXT, expires_at DOUBLE PRECISION)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE actor TEXT; expiry DOUBLE PRECISION;
BEGIN
 IF provider IS NULL OR person IS NULL OR length(provider) NOT BETWEEN 1 AND 2048
 OR length(person) NOT BETWEEN 1 AND 1024 OR token !~ '^[0-9a-f]{64}$'
 OR csrf !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid identity session'; END IF;
 PERFORM pg_advisory_xact_lock(68272605);
 SELECT e.actor_id INTO actor FROM public.external_identities e WHERE e.issuer=provider AND e.subject=person;
 IF actor IS NULL THEN
  actor := gen_random_uuid()::text;
  INSERT INTO public.users(actor_id,username,display_alias) VALUES(actor,actor,coalesce(contact,'Member'));
  INSERT INTO public.external_identities VALUES(provider,person,actor);
 END IF;
 expiry := extract(epoch FROM clock_timestamp())+28800;
 INSERT INTO public.sessions VALUES(token,actor,csrf,expiry);
 RETURN QUERY SELECT actor,expiry;
END $$;
REVOKE ALL ON FUNCTION hyprn_external_session(TEXT,TEXT,TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_external_session(TEXT,TEXT,TEXT,TEXT,TEXT) TO hyprn_auth;
