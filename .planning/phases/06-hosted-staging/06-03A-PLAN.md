# Cloud identity verification adapter — independent prerequisite

Status: planned. This is the bounded cryptographic part of 06-03, not the
PostgreSQL session bootstrap or a working hosted sign-in.

The owner authorized implementation and the shortest path to working staging.
The verified-assertion adapter has no dependency on the domain-schema port.
Implementing and testing it in parallel with 06-02 changes administrative
ordering only. Full 06-03 integration still requires accepted 06-02.

## Outcome and boundary

The cloud edition verifies Cloudflare Access assertions against explicitly
configured issuer, audience and HTTPS key source. A valid assertion produces
an immutable issuer/subject identity; invalid, missing or expired assertions
produce no authority. Nothing in an unverified claim or request header selects
the issuer, audience or signing-key endpoint.

Own only:

- `editions/cloud/pyproject.toml`, `editions/cloud/provenance.md` and
  `editions/cloud/src/hyprn_mvp_cloud/{__init__,access}.py`
- `application/tests/test_hosted_assertions.py`
- The narrow dependency/locked-environment and check-group registration needed
  by this adapter, coordinated with the domain-port executor.
- This plan's checkpoint and summary.

Do not change the app API, auth, migrations, domain owners, UI, deployment
contract or live Cloudflare configuration. Do not provide a premature cloud
entry point. The later ASGI integration must retain the internal delegated API
path without a spoofable network bypass header.

## Implementation and checks

1. Audit the official source, exact release, hashes and permissive licence of
   a maintained JWT verifier before installation. Reuse already audited
   dependencies where appropriate; do not implement JWT cryptography manually.
2. Add signed-fixture tests before implementation: exact issuer/audience,
   approved algorithm, signature, expiry, not-before and issued-at handling,
   nonempty subject, missing assertion and unknown key.
3. Bound token and JWKS sizes, network timeouts, cached key lifetime and refresh
   frequency. Disable redirects and ambient proxy credentials for the fixed
   trusted key endpoint. Expired cached keys must not grant indefinite access
   during an outage. Do not log tokens, cookies or claim payloads.
4. Exercise key rotation, malformed JWKS, unavailable keys, concurrent calls
   and a hostile unknown-key stream through the real verifier and signed tokens.
   Tests must never contact the real Cloudflare account.
5. Register a focused `hosted-assertions` group through the local edition runner.
   Record exact results, package hashes and remaining integration in the
   checkpoint. Commit explicit owned paths; orchestrator verifies the committed
   group before full 06-03 consumes the adapter.

No Cloudflare login, actor/session mapping, private browser journey or live
email delivery is established by these tests.
