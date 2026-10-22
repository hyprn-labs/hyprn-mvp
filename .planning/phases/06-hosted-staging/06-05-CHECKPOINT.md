# 06-05 — hosted application lifecycle prerequisite

This is a committed prerequisite batch, **not completion of 06-05**. The native
owner adapter and installed Linux artifact remain required by
`06-05-NATIVE-PLAN.md`. Aggregate lifecycle activation and admission opening are
closed. No cloud resource, live store, real provider credential or scientific
execution was used here. Parent acceptance is separate.

## Delivery

- RED: `a833e46b019e6266ff3052b0a0e2382d4d2a6609`.
- Source: `eba461804e4ded2f01ce314a06b6d778598878ab`.
- Ledger base: `113bf6225a083d494dddbe3cc80b53670bc1e780`.
- Base-to-source range: three commits, including parent documentation `2ec798c`.
- Explicit owned paths only; no tracked deletion. Unrelated source, design,
  research, planning files and index entries were preserved. Parent owns current
  STATE/ROADMAP and acceptance. No platform repository edits.
- Platform consumer: `72d533ed55c539e5be91750390366afe9c766c8f`; exact schema,
  fixtures and renderer hashes are in `deployment/cloud_release.schema.json`.

| Source artifact | SHA-256 |
|---|---|
| migration 0004 | `0862f9f66018f67755a215f8b0ccb025800ec4f3cecee2ab3ea64e0e200f6009` |
| cloud requirements lock | `baa1a492a6ce3c2138b59459a38db18261c487efb25049c2f3eba7404d5dfca9` |
| application Dockerfile | `56de0a33a152d50628dcceda1b1dd6f76665ebf2ecfad7af6cb2229bd602fcf2` |
| platform consumer pin | `97e49e0ae2efbe32788045afb9e7c07e82aa17c77fb452a135816ca4b3cc744b` |
| uv lock | `c88933d2a1c8c2826a9cd745875ac16908d8ccc3616eba88100bb8102172cfa6` |

## Implemented boundary

The cloud factory composes `AccessIngress(innerAPI, HostedAuth, AccessVerifier)`.
The embedded Assistant keeps the trusted inner API; admission middleware wraps
that API too. Explicit verified database TLS, credential files, artifact paths,
persisted installation/store identity and database process leases are required.
The cloud image target contains the cloud adapter, built UI, contracts and the
existing managed Assistant definition code. The local image target is preserved.
Cloud dependency hashes reuse the reviewed lock; no dependency was substituted.

Migration 0004 persists immutable installation/store identity. Explicit empty
initialization inserts identity in the same migration transaction. Request
credentials cannot insert, modify or delete it. Migration checks live application
and dispatcher leases. A closed SECURITY DEFINER function returns aggregate
pending/uncertain counts, including uncertain durable receipts and outbox rows,
without domain payloads. Request leases cover the complete ASGI response. Tests
exercise real PostgreSQL initialization, identity rejection, migration conflict,
accepted/uncertain receipt counts and request quiescence. Ordinary cloud modeling
startup refuses a missing store; local initialization behavior remains unchanged.

The dispatcher opens PostgreSQL with scoped background credentials and discovers
pending runs through the existing closed queue function. Both processing loops
check its process lease. Actual cloud-native launch integration remains unproven
until the native continuation; no new scheduler or privileged application socket
was introduced.

Assistant startup checks the complete released 56-tool definition, exact agent
version and environment readback before starting delivery. Its bounded provider
inventory includes archived sessions. Retained and carried sessions must be
classified, distinct and idle/terminated. Explicit reviewed untracked prior usage
is supported; missing history never becomes zero. Provider behavior in these
tests is synthetic read-only data, not evidence of live provider qualification.

## Host control and invocation handoff

Use the invocation published by the pinned platform contract:

`python -B deployment/cloud_lifecycle.py OP --binding FILE --operation-id UUID --timeout N`

`N` is an integer from 1 to 3600. Admission additionally requires `--surface
browser|scientific --state open|closed`; those flags are rejected elsewhere.
Binding schema is `hyprn-product-binding/v1`, with exact fields `schema`,
`platform_root`, `workload`, `release`, `runtime`, `desired`, `payload_inventory`,
`control_root`. Optional `migration_secret_file` is accepted only for initialize
and migrate. Paths are trusted absolute host inputs, not API input. Duplicate
keys, unsupported fields and nonfinite values fail. The supplied platform
renderer is verified before import; it is not vendored.

Results retain the platform's seven fields and exit meanings. The real CLI test
exercises invalid input and the closed response; it does **not** prove valid
aggregate host operations. Fixed app database image operations and modeling
commands are present but whole initialize/migrate/start/stop/inspect/check require
the missing native owner. No invented `status: success` native receipt is accepted.
Admission opening, qualification, backup and restore remain unavailable. Drain
can inspect app work but cannot claim aggregate native quiescence. Timeout or
uncertain state returns recovery required. Private operation intent/result files
prevent an identical operation ID from blindly replaying an interrupted action;
platform remains the deployment/reconciliation authority.

The reviewed control root must equal the renderer's readonly control mount
source. Root owns the directory; it must be traversable by application UID 10002
(for example 0755). Shared nonsecret controls are 0644 with explicit fchmod, even
under umask 077; operation receipts and lock are private 0600. A real amd64
container test creates root-owned controls, permanently drops to UID/GID 10002,
reads admission and verifies that writes fail. Host record reads reject symlinks,
wrong ownership, group/world write access, duplicates and oversized documents.

Control document shapes:

- `runtime-identity.json`: exact `installation_id`, `release_sha256`,
  `config_sha256` (the latter is the pinned renderer output digest).
- `admission.json`: schema `hyprn-admission/v1`, those three identities,
  boolean `browser` and `scientific`, integer epoch `expires_at`; maximum future
  validity 300 seconds. Missing, stale or mismatched controls close admission.
- `assistant-plan.json`: exact existing `managed_assistant.definition` output;
  explicit 1 MiB bound admits the full definition. Other controls stay 64 KiB.
- `assistant-continuity.json`: schema `hyprn-assistant-continuity/v1`, those three
  identities, `configuration_sha256`, integer `prior_cents` and `total_cents`,
  `carried_sessions` mapping provider IDs to cents, integer `untracked_cents`,
  and a reviewed `review_sha256`. Carried plus reviewed untracked equals prior.
  No deployment-specific identities or spend values are committed.

## Commands and results

All checks used `source /private/tmp/hyprn-collection-env.sh` followed by the
registered `./hyprn-mvp dev check GROUP` command. Final focused checks ran on the
owned source committed as above; the last control-mount identity guard was added
after the final focused run and is included in the required parent acceptance.
Release-container ran against the committed snapshot itself.

| Group | Passed | Failed | Skipped | Test seconds | Group seconds |
|---|---:|---:|---:|---:|---:|
| hosted-lifecycle | 18 | 0 | 0 | 8.501 | 9.282 |
| release | 28 | 0 | 0 | 2.95 | 3.263 |
| deployment-hardening | 76 | 0 | 0 | 0.86 | 1.114 |
| locality-contracts | 165 | 0 | 0 | 10.53 | 10.841 |
| release-container | 1 | 0 | 0 | 19.50 | 19.779 |
| hosted-artifact | 0 | 1 | 0 | 0.000 | 0.054 |

The last row is an intentional unresolved publication gate, **not a pass**:
built payload/documents were absent. Even valid payload hashes cannot yet pass
the installed-artifact rehearsal until its native continuation implements that
test. Source-only qualification never stands in for these bytes.

The existing local-target container passed original-byte verification and
changed/missing/extra-byte refusals. Image
`sha256:8357fac4ed5473e4d71fecff9f602c0e7e43f330d09376ab827cac85d09425b8`
is **linux/arm64, local edition**, tagged by build inputs `d0d93b31c3f4fe0c`.
It is not the requested cloud amd64 artifact. Hosted amd64 image, native bundle,
release descriptor, detached evidence and installed qualification do not yet exist.

## Failures and corrections

1. Initial hosted-lifecycle used the native interpreter and could not import
   Starlette (one import error); runner corrected to the locked application
   interpreter. RED then failed the missing factory assertion (one failure),
   repeated once to retain evidence. The RED classifier returned
   `RED_EVIDENCE_OK`; evidence lives outside source. The first RED commit attempt
   was rejected by the term hook for a machine path in evidence metadata; that
   metadata was moved out of the repository before successful explicit commit.
2. An initial read-only Docker probe was denied by the sandbox. Authorized
   escalated verification used scoped fixtures; no cloud permissions were used.
3. Intermediate hosted-lifecycle green runs: 10 tests/3.235 seconds and
   13 tests/7.471 seconds. Expanding Assistant/Linux cases produced 13 passes,
   three failures and one error/9.428 seconds: synthetic environment readback
   omitted the provider's explicit empty package list; the Linux fixture used
   the index name instead of the cached reviewed amd64 digest. Corrected fixture
   data/pin produced 17 passes/9.111 seconds, then the final 18 above.
4. Locality first returned 163 passes/two failures/11.38 seconds because the
   new modules were absent from the layer table. Updating that table produced
   164 passes/one failure/11.21 seconds, identifying the matching architecture
   table obligation. Aligning both produced the final 165 passes. A pre-existing
   Starlette TestClient deprecation warning remains; no dependency upgrade.
5. Parent review found uncertain receipts missing from drain aggregates. The
   final migration and test cover accepted-to-uncertain transitions. Parent also
   identified restrictive-umask control readability, now verified on Linux.
6. Hosted-artifact's one failure remains: no built payload and no installed
   native-owner rehearsal. No unavailable capability was replaced with a mock.

## Cleanup and remaining work

Parent independently accepted source `eba4618`: hosted-lifecycle 18/8.351s,
hosted-postgres 24/42.897s, release 28/3.011s, deployment-hardening 76/1.177s,
locality-contracts 165/11.999s, release-container 1/5.139s. All 312 tests passed;
no additional source correction was required. Parent logs are
`/private/tmp/hyprn-06-05-parent-GROUP.log`; documentation record `0a6eb58` adds
acceptance and the continuation plan without changing tested source. This also
covers the final control-mount guard absent from the earlier development run.

Final hosted-lifecycle scope `9d5f86dc-bdfb-4375-85ff-ad72654c4a23`, locality scope
`a4858462-742c-48ab-a852-7a848182d419`, and release-container scope
`c6585f23-4200-4ca2-8938-d7cdf369b23f` were released by the runner. Read-only Docker
inventory confirmed no PostgreSQL fixture containers and no release-scope
containers remain. The reusable built local image remains cached. Live ports,
live stores and user authoring records were not touched.

Parent acceptance above covers the required groups and hosted-postgres.
The fresh executor in `06-05-NATIVE-PLAN.md` owns cloud native configuration,
attested import closure, real native owner receipts, actual owner lifecycle,
Linux amd64 build/bundle, complete installed-artifact rehearsal and exact release
assembly. Parent owns platform operations, coherent backup/restore, provider
preactivation refresh, allowance concurrency and eventual activation approval.
No HS requirement or 06-05 completion is recorded by this checkpoint.

## Self-check

Both task commits exist; source paths are committed; no tracked deletions or
unrelated staged files were introduced. Checkpoint and incomplete summary retain
the unresolved aggregate/native/artifact gates.
