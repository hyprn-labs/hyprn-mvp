# 06-03 — hosted identity and private browser workspace

Implementation complete; parent committed acceptance and live hosted acceptance
remain separate. No cloud resources, real credentials, email login, scientific
execution, provider requests or user stores were used by this task.

## Delivery and ownership

- RED commit: `28e4267` (`test(06-03): require hosted identity session bootstrap`).
- Delivery: `1c5a4d25d66a4995d97aa591d58a1916aeddbe17`.
- Base ledger: `ea64cb7a7f517c7447329140d92288cb183db982`.
- The measured base-to-delivery range contains four commits: two task commits
  and concurrent parent documentation commits `5471feb` and `a5de6ef`.
- Explicit owned paths only; no tracked deletion, unrelated staging, platform
  edit, global STATE/ROADMAP update or changes to scientific execution.

Final SHA-256 identities:

| Artifact | SHA-256 |
|---|---|
| `uv.lock` | `c88933d2a1c8c2826a9cd745875ac16908d8ccc3616eba88100bb8102172cfa6` |
| migration `0003_external_identity.sql` | `e6e6bcdc34b6be8fbd829b048841f088e60644158fb05cb7605cd6d094ae8d2b` |
| `editions/cloud/src/hyprn_mvp_cloud/access.py` | `116af71a316bd0dcf0e34ece77ec7579f6f7a64d6abed03ef5fe364c9dde8472` |
| public OpenAPI | `eb01761e29d9df65d8ea570bd7bb44eb908a67ced5135a946ceede647909a061` |

## Implementation

`HostedAuth` requires PostgreSQL and an explicit HTTPS origin. Migration 0003
creates issuer/subject identity linkage and narrow authentication-role functions
for atomic first sign-in, session ending and coordinated credential revocation.
The runtime authentication role cannot directly create/link actors or edit the
mapping. Identity linkage never depends on email. Optional verified email is
bounded display/contact metadata; absent email uses a friendly editable alias.
No password credential is generated, and local provisioning/recovery/login are
unavailable in hosted mode.

`AccessIngress` verifies the assertion on every external HTTP request and binds
any browser cookie to that assertion's actor. Duplicate/missing assertions,
invalid signatures/claims and mismatched or delegated cookies are denied with
canonical private-cache-safe errors and cookie deletion. Trusted in-process
delegated clients retain the inner API object. No bypass header exists.

Public mode discovery and explicit external bootstrap preserve exact-origin
checking; subsequent mutations require the existing CSRF token. The UI chooses
hosted sign-in/retry or local password login from mode discovery. Hosted identity
loss, redirects, switching and logout clear private state, recovery and pending
navigation. Responses from an older session cannot clear a newer one. Logout
also navigates to the configured site's Cloudflare logout path.

The browser fixture uses the compiled UI, real HTTPS, real application routes
and isolated PostgreSQL with two independent browser actors. Only assertion/JWKS
and Cloudflare redirect responses are synthetic. It covers private study creation,
cross-actor isolation, cookie mismatch, retry, access loss and logout, keyboard,
light/dark themes, narrow layout and genuine browser 200% zoom.

## Commands and results

Each command below was preceded by
`source /private/tmp/hyprn-collection-env.sh`. All checks used the registered
`./hyprn-mvp dev check GROUP` entry point with scoped stores. No checks skipped.
These are development verification results, captured before committing the same
owned source. Parent acceptance will rerun the six required groups on delivery
`1c5a4d2`; that independent committed run is not claimed here.

| Group | Passed | Failed | Skipped | Seconds | Console file under `/private/tmp/` |
|---|---:|---:|---:|---:|---|
| `hosted-identity` | 90 | 0 | 0 | 15.07 pytest | `hyprn-hosted-identity-contract.log` |
| `hosted-ui --keep-scope` | 3 | 0 | 0 | 28.775 child | `hyprn-hosted-ui-redirect.log` |
| `hosted-postgres` | 24 | 0 | 0 | 39.60 pytest | `hyprn-hosted-pg.log` |
| `contracts` | 127 | 0 | 0 | 9.13 pytest | `hyprn-hosted-contracts.log` |
| `access-control` | 11 | 0 | 0 | 4.54 pytest | `hyprn-hosted-access.log` |
| `combined-static` | 9 checks | 0 | 0 | 6.526 | `hyprn-hosted-static-delivery.log` |
| `locality-contracts` | 165 | 0 | 0 | 14.68 pytest | `hyprn-hosted-locality-final.log` |
| `public-api` | 83 | 0 | 0 | 144.56 pytest | `hyprn-hosted-public.log` |
| `ui-navigation` | 25 | 0 | 0 | 23.821 child | `hyprn-hosted-local-ui-ready.log` |

All final exits are zero. Existing warnings: PostgreSQL 1, contracts 2, locality 1,
public API 13. Combined static includes design-system, component ownership,
generated tokens, UI contract, design tooling/smoke, frontend unit tests,
TypeScript and a clean scoped Vite build. `git diff --check` passed.

The final backend identity run includes all 76 verifier cases (71 inherited plus
five display-contact cases); the verifier was not otherwise rewritten. Later UI
changes were checked by the final three-case browser run and nine static checks.
The only delta after that browser/static run was the local keyboard fixture's
readiness assertion, verified by the final 25-case navigation run.

## Failures and corrections

1. Initial sandbox launch could not access the pinned external tool cache (exit
   5, no tests). Authorized escalated runner execution resolved this.
2. RED: 1 failed, 71 passed, absent bootstrap interface. This establishes a
   missing capability only. No machine RED classifier was run; strict TDD gate
   compliance is not claimed. Parent was informed.
3. First integration run: 1 failed, 71 passed in 17.21s. A missing PostgreSQL
   driver in the native environment was masked as fixture readiness. ImportError
   now propagates. A temporary native dependency-closure attempt was rejected
   by the launcher (exit 5, no tests); after closure correction the missing
   application server caused 6 setup errors with 72 passes in 5.11s. The final
   solution uses the existing application contract environment and adds only the
   previously audited JWT/cryptography closure there. Native closure is unchanged.
4. Hosted logout returned 500: 1 failed, 77 passed in 12.86s. PostgreSQL DELETE
   visibility under the request role required an inappropriate credential read.
   Fixed with the narrow auth-role session-ending function, preserving RLS.
5. Hosted browser fixture initially failed import (exit 1, no tests); moved its
   application import after the scoped application path registration.
6. Locality: 1 failed, 164 passed in 13.09s; the architecture layer table lacked
   the new provider-independent identity module. Documentation and boundary
   allowlists were aligned, then 165 passed.
7. Local navigation initially lacked a mode-discovery fixture response. After
   repeated known fixture failures its owned Playwright child was interrupted:
   22 failed, 3 skipped, 291.39s. Adding explicit local mode fixed the mocks.
8. Two subsequent local navigation runs returned 24 passed, 1 failed (31.265s
   and 32.26s). The Assistant Enter test raced its initial conversation read.
   Waiting for the observable Send button readiness before Enter produced
   25 passed. No Assistant source or behavior changed; no unsupported baseline
   defect claim is made.
9. Inspection corrected the contact bound to the public profile's 128-character
   maximum, standardized ingress errors, and fenced hosted redirects/stale
   responses. These were covered by the final relevant runs above.

No package download failed and no unreviewed dependency was substituted.
Context7 was unavailable; pinned Starlette implementation and official
PostgreSQL security-definer documentation supplied the version-specific behavior.

## Evidence and cleanup

Final identity scope: `fbc3a50e-edb6-4d61-80e4-f43a6b4c3276`; wrapper
`c560ddde-b153-475a-91b8-068213a95357`. Final hosted browser scope:
`6152deb0-c89f-4805-8348-50512646034f`; wrapper
`574c4c88-861d-491d-b083-8b47acdd087c`. Browser signing fixture key ID:
`fixture-e569b2cf9aa145bfb023d3c333581ca0`. Unit verifier key IDs are `current`
and `rotated`; their ephemeral RSA keys are regenerated, never persisted. HTTP
identity-test fixture UUID key IDs are ephemeral and were not separately logged.

The browser scope is retained for 24 hours under the runner's normal storage
budget at `/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-6152deb0-c89f-4805-8348-50512646034f`.
It contains the compiled bundle, JSON results and screenshots, no TLS PEM files
or signed credentials. HTTPS thread stopped and PostgreSQL container removed.
Docker readback found no `ai.hyprn.fixture.postgres` containers remaining.
PostgreSQL image remains the reviewed fixture image
`postgres@sha256:45cd22f8d32e189d245403954882f88e7a8714301fda80dab6da90f1265b25a3`.

Screenshot SHA-256 identities (under that scope's evidence/browser tree):

- `hosted-light.png`: `2f90974e0772f7458fd42896a51b610dac64386dff43af3f19855a1fe9d81734`
- `hosted-dark.png`: `1c42f7939154669402d6786b99b2333e53da2988b18a6b23646180e7d9301b62`
- `zoom-light.png`: `2b28081b653f087288b107eb378e4ee2711c4055b4e5dfedadcff4d58d309ae1`
- `zoom-dark.png`: `992a1e8d3e7d99e5b8fd7db8857ad435441e82f76b96695809574e98080c7142`

Light and zoomed dark screenshots were visually inspected. Automated browser
evidence is not human acceptance. One retained failed local navigation diagnostic
scope `6f69ec73-e682-49d3-9a3b-57a0bc91083b` also expires normally; it contains
synthetic data. Other ordinary scopes were released, including final navigation
scope `5a1d6651-0796-4e9d-ba2e-db39fb0915a7` (absence checked).
Isolated test stores were used; live installations and user stores were preserved.

## Lifecycle handoff and remaining acceptance

Apply migration 0003 using the migration owner before starting the application.
Compose `Store.postgres(...)`, `HostedAuth(store, configured_https_origin)` and
the existing inner `create_app(...)`; mount WorkspaceFiles on the inner app,
then expose only `AccessIngress(inner, auth, AccessVerifier(issuer, browser_audience))`
to external HTTP. Trusted embedded Assistant code keeps the inner API object.
The wrapper registers verifier shutdown cleanup. No external MCP audience or
network bypass is supported. The accepted staging hostname is a configuration
value, `https://staging.hyprn.ai`, never derived from forwarded headers.

Coordinated admission revocation calls trusted `auth.invalidate(issuer, subject)`
and ends Cloudflare admission; no new administrative HTTP endpoint exists.
This task does not deploy an entry point or prove real Access email delivery,
live policy, GCP runtime, provider execution, recovery rehearsal or release
qualification. These remain with 06-05/06-07 and the parent. The parent owns
global planning state and the six-group committed acceptance rerun.

## Self-check

PASS: owned source exists, both task commits are ancestors of delivery, generated
contracts passed, no tracked deletions and the index was empty after commit.

## Parent committed acceptance — 2026-10-20

Parent ran the six required groups once on delivery source1c5a4d2, with only
checkpoint/summary documentation b9d8230 added. Each invocation used
`source /private/tmp/hyprn-collection-env.sh` then
`./hyprn-mvp dev check GROUP`. All exited0, no failures or skips:

| Group | Result | Child seconds |
|---|---:|---:|
| hosted-identity | 90 passed | 12.111 |
| hosted-ui | 3 passed | 24.261 |
| hosted-postgres | 24 passed | 46.623 |
| contracts | 127 passed | 9.792 |
| combined-static | 9 checks passed | 7.821 |
| access-control | 11 passed | 4.177 |

Total255 tests plus9 combined checks. Private logs are
`/private/tmp/hyprn-06-03-parent-GROUP.log`, with the runner evidence scope/exit
records. Browser fixture key `fixture-aafcd083c93a4c819bfb03848943e4ff`;
HTTPS server stopped and PostgreSQL fixture removed. Parent reviewed ingress,
identity binding and narrow migration-role functions; no additional issue found.
This accepts the committed integration prerequisite, not live email delivery,
production deployment, scientific execution or human acceptance.
