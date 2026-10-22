# Complete PostgreSQL domains — implementation checkpoint

Date: 2026-10-20. Task 06-02. Local PostgreSQL implementation only; no hosted
deployment, Cloud SQL acceptance, native execution attestation or human acceptance
is claimed. The orchestrator owns committed-tree acceptance and state advancement.

## Delivery identity

- RED commit: `aa53449` (complete schema and public composition required).
- Implementation and final focused tested source: `4c40f0862c114c84382d3494316de5a7573c0e6b`.
- Migration `0002_domains.sql` SHA-256:
  `dac772da6e29dedb1361cb399db5b5fdb8aaf0c08444f5c111f6cd7a6155a70f`.
- Baseline: `2f9c629`; integrated prerequisite evidence: [06-core-ACCEPTANCE.md](06-core-ACCEPTANCE.md).
- Scope follows [IMPLEMENTATION-AMENDMENT.md](IMPLEMENTATION-AMENDMENT.md) and ADR0014:
  embedded Assistant, fresh database initialization, no transfer or external MCP.

## Implemented behavior

All local scientific schema owners have explicit PostgreSQL equivalents. Startup
verifies the complete migration ledger and never initializes schema. Explicit
initialization applies a recognized checksummed prefix atomically; mismatched,
partial or unrecognized databases fail closed. An intentionally aborted migration
leaves no partial tables. No runtime query rewriting or new dependency was added.

Study-bearing tables use forced row policies, including indirect Assistant,
delegation, journal, outbox and export records. Policies intersect current human
membership with current agent delegation. Exact saved payload text, accepted run
inputs, command identity, immutable versions and journal transitions are protected
by database triggers. Composite foreign keys preserve study lineage. Fixed stored
ordering replaces implicit SQLite row ordering where public pagination needs it.

Real HTTP tests cover concurrent duplicate brief commands, one-winner revision
races, immutable saved reads after application restart, successful calculation
lists/reference marks and foreign IDs across every registered study GET route.
Raw-role tests exercise the complete domain table inventory and missing, foreign,
reader, revoked and inherited authority. Existing numerical prediction and embedded
Assistant owners run through actual persisted PostgreSQL work with controlled
numerical/provider adapters. These adapters prove persistence and authority, not
hosted scientific execution or a live provider connection.

## Process and credential interface for 06-03 / 06-05

Construct `Store.postgres(request, authentication, background=..., artifact_root=...)`.
Each credential is `PostgreSQLCredentials`. TLS verification remains enabled by
default; the lifecycle adapter supplies resolved host, database, role, secret and
optional CA/certificate name. `artifact_root` is an explicitly resolved application
artifact directory shared by the app and trusted dispatcher. It must satisfy the
existing location guard; no repository, cloud-synced or invented production path.
Missing artifact configuration is refused when assembling computational records.

| Process | Login / secret alias | Purpose |
|---|---|---|
| Application | `hyprn_request` + `hyprn_auth` + `hyprn_assistant_background` / `db-assistant-background` | HTTP actor transactions, narrow identity lookup/bootstrap, Assistant discovery/account metadata |
| Trusted app-side dispatcher | `hyprn_request` + `hyprn_dispatcher_background` / `db-dispatcher-background` | Discover work identities, ordinary actor-scoped domain work, publish bounded execution observation |
| Native execution consumer | none | Existing fixed stdio bridge; no application/provider/database secret |
| Migration job | `hyprn_migration` only | Explicit schema initialization/upgrade; never application process authority |

The Store constructor currently takes the authentication credential argument for
both compositions; the dispatcher never opens that connection. The lifecycle
adapter can pass its request credential as the unused authentication argument;
the dispatcher must not receive the authentication secret solely to construct a
Store. Production entrypoints and environment variable names remain 06-05-owned.

Background logins must exist before migration. They have no direct table access,
owner privileges, request/auth memberships or membership in each other. Construction
rejects those grants. The request login likewise cannot inherit background/auth or
owner authority. Functions use qualified objects and fixed `pg_catalog,public`
search paths; PUBLIC EXECUTE is revoked.

Exact SQL interface:

```sql
hyprn_background_jobs(category TEXT, identity TEXT DEFAULT NULL)
  RETURNS TABLE(study_id TEXT, actor_id TEXT, work_id TEXT)
hyprn_assistant_accounts()
  RETURNS TABLE(study_id TEXT, conversation_id TEXT, provider_id TEXT,
    provision TEXT, reserved_cents INTEGER, active_turn TEXT, state TEXT)
hyprn_publish_observation(status TEXT, reason TEXT,
  observed DOUBLE PRECISION, runtime TEXT) RETURNS VOID
```

- Assistant login may discover only `assistant` work and call `hyprn_assistant_accounts`.
  Account metadata supports existing shared provider allowance accounting; no
  conversation messages or tool payloads are returned.
- Dispatcher login may discover only `analysis_execution`, `calculation_sample`,
  `calculation_estimate`, `calculation_prediction`, `run` and `export` work, and may
  publish an execution observation. Discovery returns identities only.
- Discovery does not grant row authority. Each owner enters `background_actor`
  using the returned actor, then uses the ordinary request login. Membership and
  delegation are rechecked by RLS on every statement; the context is restored even
  after failure. No missing-actor global bypass exists.
- `Store.authentication_connection(write=True)` is an explicit transaction option
  for 06-03's narrowly granted identity/session function. This task grants no
  general authentication table writes. Auth bootstrap remains separate and must
  revoke PUBLIC EXECUTE, fix its search path and refuse arbitrary actor escalation.

## Verification evidence

Every command below used `source /private/tmp/hyprn-collection-env.sh` followed by
`./hyprn-mvp dev check <group>` in pinned environments. Logs stay outside the repo.

| Group | Result | Log |
|---|---|---|
| hosted-postgres | 24 passed, 0 failed, 1 warning, 38.51 s | `/private/tmp/hyprn-06-02-hosted-delivery.log` |
| access-control | 11 passed, 0 failed, 3.94 s | `/private/tmp/hyprn-06-02-access-control.log` |
| public-api | 83 passed, 0 failed, 13 existing warnings, 90.89 s | `/private/tmp/hyprn-06-02-public-api.log` |
| agent-tools | 321 passed, 0 failed, 1 warning, 44.45 s | `/private/tmp/hyprn-06-02-agent-tools.log` |
| contracts | 127 passed, 0 failed, 2 warnings, 8.76 s | `/private/tmp/hyprn-06-02-contracts.log` |
| locality-contracts | 165 passed, 0 failed, 1 warning, 11.73 s | `/private/tmp/hyprn-06-02-locality-final.log` |
| combined-static | 9 checks passed, 0 failed, 6.16 s | `/private/tmp/hyprn-06-02-static.log` |

Failures and corrections (all retained, no failure reported as a pass):

| Run | Observed failure | Resolution |
|---|---|---|
| initial sandbox | exit 5 before tests, pinned host cache inaccessible | Same authorized check with host cache/Docker access |
| RED | 2 expected failures, 10 passed, 10.84 s | Complete-schema behavior implemented; see [06-02-RED.md](06-02-RED.md) |
| green1 | locked native environment changed concurrently with audited JWT dependency | Waited for owning executor's provision; no reset/delete |
| domains | 15 setup errors; privilege scan queried unqualified information-schema relation | Schema-qualified public table privilege scan |
| domains2 | 3 failed, 12 passed, 12.33 s | Canonical UUID actors, explicit agent-enabled fixture, rollback outside expected exception scope |
| domains3 | 1 failed, 14 passed, 15.22 s | Normalize SQLSTATE 23 integrity errors from trigger errors |
| domains5 | 1 failed, 18 passed, 44.43 s | Explicit NoModeling fixture instead of absent adapter in Assistant readiness |
| locality-contracts | 2 failed, 163 passed, 14.55 s | Update exact SQL allowlist and permitted database dependency edges |
| expired-red | 1 failed, 23 passed, 37.92 s; fixture itself refused expired grant | Create then revoke a valid delegation before exercising raw SQL |
| revoked-red | 1 failure, 23 passed, 38.94 s; raw INSERT was accepted | Creation policy review tightened live writer+record requirements; this negative fixture was later found to share another live grant, so it is not standalone revocation proof |
| create-red | 3 failed, 21 passed, 52.39 s | Permit only creation-transaction attribution for the human-owned new study; give real PostgreSQL Assistant recovery a bounded 20 s wait instead of SQLite fixture's 3 s; negative fixture still shared a live grant |
| hosted-complete | 1 failed, 23 passed, 40.84 s | Diagnose the negative fixture's remaining authority before changing policy again |
| create-diagnostic | 1 failed, 23 passed, 39.28 s; explicit query confirmed another live delegation | Seed a unique actor for the denial test; preserve legitimate live-grant behavior |

Intermediate green hosted runs: 12/12 (11.89 s), 16/16 (26.43 s), 19/19
(44.12 s), 23/23 (40.78 s). Final focused evidence supersedes them. Existing warnings
are Starlette HTTP client deprecation and previously unregistered pytest quick marks.
All seven final group invocations exited 0. Source was committed without edits after
the final focused run. The exact later delta from the local regression runs was
PostgreSQL migration policy/index SQL and focused hosted tests; the module-boundary
allowlist correction was verified by the final locality-contracts run. Summary,
checkpoint and normalized plan references are the subsequent documentation delta.

Delegated study creation retains the established Store contract: the new study
belongs to the delegating human. The creating agent gains neither a membership nor
ongoing read authority to it. The focused test checks both sides of this boundary.

## Isolation, cleanup and remaining acceptance

The fixture uses the pinned official PostgreSQL 17.6 image
`postgres@sha256:45cd22f8d32e189d245403954882f88e7a8714301fda80dab6da90f1265b25a3`,
random loopback port, ownership label and tmpfs data directory. Teardown checks the
label before removing its container. The abort-upgrade test's extra database is
inside that disposable container. Artifact/lock fixtures use pytest scratch scopes.
All recorded runner exits include check-storage release; no live installation,
authoring data, cloud resource, production entrypoint or attestation was modified.
Post-check `docker ps --filter label=ai.hyprn.fixture.postgres --format '{{.Names}}'`
returned no remaining fixture containers. Final hosted evidence scope:
`hyprn-mvp-test-779ebf35-bbb3-42a1-bf7f-cd5b159cc395`; check-storage scope:
`de1e5728-ec6d-4060-bd54-194d61c4ae5d`.

The orchestrator must rerun the required acceptance groups on the committed batch.
Full qualification, Cloud SQL/TLS target verification, Cloudflare session binding,
hosted process assembly and target-native attestation remain later task obligations.
Global STATE/ROADMAP files were intentionally left to the orchestrator.
