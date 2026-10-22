# PostgreSQL private-study tracer — implementation handoff

Date: 2026-10-20. Status: committed as `2f9c629` together with external-agent
retirement; integrated core acceptance passed. **Not accepted as hosted staging.**
See [integrated acceptance](06-core-ACCEPTANCE.md). The orchestrator owns state
advancement and subsequent full-domain acceptance.

## Implemented boundary

- Audited pg8000 1.31.5 and its five-package permissive closure (including pg8000)
  before installation; synchronized application/root pins, wheel inventory and lock.
- Explicit PostgreSQL Store constructor and core schema profile. Only the existing
  study API routes are composed in this profile; no cloud entry point, agent
  authoring or scientific execution is claimed.
- Request role has default-deny row policies and verified actor context propagated
  across the actual asynchronous HTTP / synchronous route boundary. An in-process
  delegated API request can establish its own authenticated request scope without
  inheriting the caller's actor.
- Separate read-only authentication role; no request access to credential tables.
  Request role cannot own tables, inherit their owner, bypass RLS or create roles.
- Explicit checksummed transactional initialization and compatibility validation.
  Ordinary startup never migrates; unrecognized nonempty databases are refused.
- TLS defaults to verified certificate/hostname checks, with optional trusted CA
  file and distinct private connection address / certificate DNS server name.
- Local SQLite construction/behavior retained.
- Store's retired MCP token table, revocation writes and surface values removed
  in coordination with the retirement executor.

The initial creator is visible only within the creation transaction before its
membership exists. `created_transaction` is a transaction ID, not an enduring
authorization grant. Using PostgreSQL `xmin` here failed because Store uses a
savepoint (subtransaction IDs differ); the explicit immutable marker fixes this.
The request role cannot update either creation identity column.

## Owned paths for the parent commit

```
pyproject.toml
uv.lock
application/pyproject.toml
application/requirements.lock
application/dependency-pins.json
application/provenance.md
application/src/hyprn_mvp_app/database.py
application/src/hyprn_mvp_app/migrations.py
application/src/hyprn_mvp_app/migrations/0001_core.sql
application/src/hyprn_mvp_app/store.py
application/src/hyprn_mvp_app/api.py
application/tests/test_hosted_postgres.py
deployment/tests/hosted_fixture.py
deployment/checks.py
application/tests/test_module_boundaries.py
docs/specs/architecture-and-contracts.md
```

`auth.py` has the single shared `Auth.authenticate` connection change; the
retirement executor owns the whole file in the combined commit.

## Verification

All group commands used the existing nonsecret development environment sourced
from `/private/tmp/hyprn-collection-env.sh`, then the pinned local entry point.

| Command | Result |
|---|---|
| `./hyprn-mvp dev check hosted-postgres` final | 10 passed, 6.10 s |
| `./hyprn-mvp dev check access-control` | 11 passed, 3.83 s |
| `./hyprn-mvp dev check public-api` | 83 passed, 13 existing warnings, 92.91 s |
| `./hyprn-mvp dev check locality-contracts` final | 165 passed, 1 existing warning, 10.98 s |
| Locked Ruff format/check on four new Python files | Passed |
| `git diff --check` on owned tracked paths | Passed |

Retirement executor reports `agent-tools` 321 passed and `contracts` 127 passed;
refer to its checkpoint for exact artifacts rather than treating those as reruns
performed by this executor.

Final PostgreSQL evidence:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-0124b3ba-635f-4504-972f-84fdadc2cb07/evidence`.
Access-control:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-05b5c0b5-fdc0-4d25-919a-24ed70dfb980/evidence`.
Public API:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-78fb2206-2273-4159-9df7-368ad7d3ffab/evidence`.
Locality:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-2b2776c2-cb02-4d71-a081-358076e44610/evidence`.

Failures retained:

1. First PostgreSQL run: 4 passed / 1 failed, test expected an `items` wrapper
   although the existing public listing envelope contains a list directly.
2. Strengthened creation/revocation policy run: 4 passed / 1 failed; then expanded
   diagnostic run 6 passed / 2 failed. PostgreSQL savepoint `xmin` mismatch denied
   initial membership insertion. Explicit creation transaction marker fixed it.
3. Next run: 8 passed; final repeat justified by added CA/server-name connection
   support and formatting: 8 passed.
4. Parent review removed the database-to-migrations import cycle by moving
   compatibility verification to Store composition and added real migration-role
   and BYPASSRLS-role inheritance refusal tests: 10 passed.
5. Locality checks first found the two new layers were not registered:
   163 passed / 2 failed. The first table patch placed the API edge in the routes
   row: 162 passed / 3 failed. The edge was moved to the correct API row; the
   acyclic check itself was never weakened. Final locality result: 165 passed.
6. Final Ruff check caught one new 101-character privilege expression. Extracted
   the unchanged boolean expression to a local variable; final Ruff check passes.
   This is the only source delta after the final group checks; parent integrated
   acceptance remains required on the committed tranche.

The plan prescribed TDD, but implementation preceded the new tests; these failure
runs are **not** claimed as valid test-first RED evidence. This process deviation
is recorded for the orchestrator, not concealed as a completed TDD gate.

## Identities and cleanup

- Core SQL SHA-256:
  `2f60897e1f42baa890fb559c2da02098266bc8e6934d7a636bf1e91955d9910c`.
- uv.lock SHA-256:
  `4f7293b5dfdd96fdb169248e77798266c9d75c051482f85e15cbb9fb258b9064`.
- Fixture image: official PostgreSQL 17.6-bookworm Linux amd64
  `sha256:45cd22f8d32e189d245403954882f88e7a8714301fda80dab6da90f1265b25a3`.
  This older, isolated test-only pin does not select the production Cloud SQL
  minor release.
- Each fixture generated a UUID container name and ownership label; ephemeral
  loopback port and tmpfs database; no named or host-mounted data volume. Generated
  fixture password passed on stdin. Teardown inspected the ownership label.
- Final `docker ps -a --filter label=ai.hyprn.fixture.postgres` returned no rows.
- Wheel audit files remain only under `/private/tmp/hyprn-pg-audit`; no credentials,
  live stores or runtime artifacts were placed in the repository.
- No existing application data deleted, no cloud resources changed.

## Remaining required work

Task 06-02 must port every domain owner, immutable schema, indirect RLS and agent
write path before replacing the core composition. Current sharing/agent domain
semantics are not claimed by this tracer.

Background dispatcher, Assistant recovery and prediction processes need explicit
narrow service authority to discover their queues, followed by current
actor/delegation-scoped operations. Giving missing-scope requests global access
or treating every background connection as migration authority is forbidden.

Task 06-03's external identity bootstrap must create internal actors and sessions
through a narrowly privileged function/authority. The current `hyprn_auth` role
is read-only credential lookup; do not silently grant general users/session writes
or load migration credentials into application request handling.

The first implementation opens a fresh connection per operation and serializes
write transactions to retain local receipt behavior; there is no pool or replica
scaling claim. Subsequent work must retain per-operation scope when introducing
pooling/concurrency. Custom-CA TLS and Cloud SQL hostname behavior require actual
target acceptance; plain loopback fixture TLS is explicitly disabled.

No Cloudflare login, full application PostgreSQL startup, scientific host
attestation, live Assistant or deployment acceptance has been performed here.
