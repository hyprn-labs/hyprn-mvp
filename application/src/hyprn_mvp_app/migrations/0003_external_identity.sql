-- Only trusted authentication code chooses the verified issuer/subject. It cannot
-- select an existing actor or attach an identity to another person's account.
CREATE TABLE external_identities(
 issuer TEXT NOT NULL, subject TEXT NOT NULL, actor_id TEXT UNIQUE NOT NULL REFERENCES users(actor_id),
 PRIMARY KEY(issuer,subject), CHECK(length(issuer) BETWEEN 1 AND 2048),
 CHECK(length(subject) BETWEEN 1 AND 1024)
);
REVOKE ALL ON external_identities FROM PUBLIC;
GRANT SELECT ON external_identities TO hyprn_auth;
CREATE POLICY sessions_owner ON sessions TO hyprn_migration USING(true) WITH CHECK(true);

CREATE FUNCTION hyprn_external_session(provider TEXT, person TEXT, token TEXT, csrf TEXT, contact TEXT)
RETURNS TABLE(actor_id TEXT, expires_at DOUBLE PRECISION)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE actor TEXT; expiry DOUBLE PRECISION;
BEGIN
 IF provider IS NULL OR person IS NULL OR length(provider) NOT BETWEEN 1 AND 2048
 OR length(person) NOT BETWEEN 1 AND 1024 OR token !~ '^[0-9a-f]{64}$'
 OR csrf !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid identity session'; END IF;
 PERFORM pg_advisory_xact_lock(68272602);
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

-- Coordinated operator revocation is explicit. Cloudflare must end admission too.
-- No identity link or scientific authoring record is deleted.
CREATE FUNCTION hyprn_invalidate_external(provider TEXT, person TEXT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 DELETE FROM public.sessions WHERE actor_id IN
 (SELECT e.actor_id FROM public.external_identities e WHERE e.issuer=provider AND e.subject=person);
 UPDATE public.agent_delegations SET revoked_at=extract(epoch FROM clock_timestamp()),
 revoked_reason='external_identity_revoked' WHERE revoked_at IS NULL AND delegator_actor_id IN
 (SELECT e.actor_id FROM public.external_identities e WHERE e.issuer=provider AND e.subject=person);
END $$;
REVOKE ALL ON FUNCTION hyprn_invalidate_external(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_invalidate_external(TEXT,TEXT) TO hyprn_auth;

CREATE FUNCTION hyprn_end_external_session(token TEXT) RETURNS VOID
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 DELETE FROM public.sessions WHERE token_hash=token
$$;
REVOKE ALL ON FUNCTION hyprn_end_external_session(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION hyprn_end_external_session(TEXT) TO hyprn_auth;
