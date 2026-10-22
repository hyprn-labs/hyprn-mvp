# Stopped owner schema inspection checkpoint — 2026-10-21

Scoped prerequisite delivered. Product 06-05 and platform 08-02 remain incomplete;
this is neither whole-host Linux acceptance nor staging activation authority.
Parent owns STATE, bootstrap, backup integration and full installed acceptance.

## Revisions and behavior

- Product `63af9f041a321c175387eea1ef79643b631c9e45`: five explicit paths, cloud
  lifecycle, new `deployment/cloud_owner_schemas.py`, registered
  `hosted-owner-schemas` group and its tests, PostgreSQL lifecycle regression.
- Platform `68d04d3cede0de81793820b00269329991a335b5`: `host/reconcile.py` and
  `tests/platform/test_reconcile.py` only.

`inspect` returns three `hyprn-owner-schema/v1` observations, each binding owner,
installation and exact store ID. Application inspection verifies its real
PostgreSQL identity and exact source checksummed migration ledger with the
request role. Modeling inspection checks its explicit initialized ownership
marker and reads both primary and scratch SQLite ledgers against the pinned
image's migration files and schema-load baseline, including hashes of those
sources. Scratch has no migration directory entries; its schema-load version
comes from the actual upstream schema declaration, never a fabricated integer.
Native inspection reads its actual SQLite Alembic version and compares the
candidate pinned AiiDA backend head; it verifies retained profile, repository,
computer and code UUIDs against the real profile, database and object repository.
It does not instantiate AiiDA's writing/touching backend or migrator.

An incoming pinned product may use `inspect --compatibility-active-binding` only
with an exact protected active binding, matching installation/stores/mounts,
active control identity and native owner projection. Ordinary operations keep
their existing exact active identity check. Ordinary operation receipt hashes
are unchanged; explicit compatibility receipts additionally bind the active
binding digest and native owner. No scientific Python or Rails startup runs in
inspection. The modeling subprocess has no network, writable store or secrets.

**Coherent `inspect` and `check` require stopped writers.** `check` also requires
the current native attestation. These commands are not live readiness probes.
The active product proves stopped writers before incoming inspection. Nonempty
SQLite WAL or rollback journals refuse; probes never checkpoint, delete or
ignore pending journal bytes. Under that stopped boundary, immutable read-only
SQLite avoids creating sidecars. `qualify` and `start` observe all owner schemas
while stopped; start returns that prior observation after successful startup.
The platform compares qualify/start observations without inspecting a running
immutable database. Running public API/scientific behavior is a separate
parent-owned acceptance boundary.

Compatibility runs after successful admission closure, drain and stop, before
backup/migrate. Both pinned releases must independently accept and return
identical exact owner observations. Integer release declarations must remain
unchanged as a separate restriction; no migration count, hash or string is
converted into those declared versions. Incompatibility leaves admission closed,
the previous installed identity retained and stores unchanged. Unknown or
schema-changing replacements remain refused pending an explicit migration plan.

Fresh cloud initialization writes installation/store identity into the modeling
`initialized` marker. Existing empty markers are unbound and refused, never
silently adopted. The existing lifecycle native receipt check now accepts
upstream's dashed and compact UUID encodings while preserving their bytes;
malformed values and non-string types remain refused.

## Exact checks and failures

Every product command used this setup, then the registered entry point:

```sh
source /private/tmp/hyprn-collection-env.sh
export HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184
./hyprn-mvp dev check hosted-owner-schemas
./hyprn-mvp dev check hosted-lifecycle
```

The final source tree was committed without further source/test changes as
`63af9f0`. Parent independently repeated committed acceptance before its next
dependent batch; its results are recorded below. Platform committed acceptance
was also run by this executor.

| Run | Result |
|---|---|
| Initial schema group, sandbox | Exit 5 before tests: pinned uv cache access denied; scoped escalation succeeded, no approval-review rejection. |
| Schema group first real run | 7 tests: 3 pass, 2 failures, 2 errors, 8.290 s. Native UUID normalization was too strict; native environment lacks pg8000; cached modeling producer source identity was stale. |
| Schema group after environment/fixture correction | 6 tests: 4 pass, 2 failures, 319.403 s. Real Rails fixture required its ephemeral rails.key; upstream SQLite UUID columns held dashed strings. |
| Schema group next run | 7 tests: 6 pass, 1 failure, 108.469 s. Read-only WAL-mode modeling database tried opening missing SQLite sidecars. |
| Approved stopped-writer sequencing/immutable fix | 7 pass, 0 fail/error/skip, 23.854 s. |
| Added real native WAL and modeling journal preservation regressions | 8 pass, 0 fail/error/skip, 25.079 s. |
| Final schema group including lifecycle UUID validation | **9 pass, 0 fail/error/skip, 23.068 s**, exit 0. |
| PostgreSQL/lifecycle before final source delta | 21 pass, 0 fail/error/skip, 26.563 s. |
| Final PostgreSQL/lifecycle | **21 pass, 0 fail/error/skip, 16.547 s**, exit 0. |
| Platform focused discovery | 39 then 41 pass, 0 fail/error/skip, after implementation and sequencing change respectively. |
| `tests/platform/run.sh reconcile` at `68d04d3` | **41 pass, 0 fail/error/skip, 0.753 s**, exit 0. |
| Parent committed `hosted-owner-schemas` at `63af9f0` | **9 pass, 0 fail/error/skip, 22.848 s**; `/private/tmp/hyprn-owner-schemas-parent.log`. |
| Parent committed `hosted-lifecycle` at `63af9f0` | **21 pass, 0 fail/error/skip, 17.421 s**; `/private/tmp/hyprn-owner-lifecycle-parent.log`. |
| Parent committed `tests/platform/run.sh reconcile` at `68d04d3` | **41 pass, 0 fail/error/skip, 1.321 s**; `/private/tmp/hyprn-owner-reconcile-parent.log`. |

The environment error was corrected by moving the PostgreSQL regression into
the already registered application-interpreter lifecycle group, not by adding
a dependency. The modeling test builds and validates the reviewed image from
locked sources in its scope, avoiding the stale cached producer. AiiDA fixture
creation warnings describe disposable fixture setup, not probe mutation.

Diagnostic-only failures: one whitespace cleanup command ran from the platform
cwd, failed with FileNotFoundError and changed nothing; it was corrected in the
product cwd. A sandbox process listing was denied and a scoped escalated listing
succeeded. A broad temporary-directory listing encountered unrelated macOS
permission refusals; no protected directory was accessed. No check was skipped.

## Evidence and identities

Final schema evidence is retained under the external check session
`cc365d54-714e-42ed-8958-3573162af756`, scope
`69ee7707-f59f-491a-8852-ddc7943ba9a4`. Final lifecycle evidence is session
`cb06c13b-c1aa-4cdf-ac15-7b2a48ba9a34`, scope
`b4464040-fb7d-4f7f-8f2b-5f7d6d8ab7af`. Both live in the configured temporary
root's `.hyprn-checks/` evidence directory, outside this repository.

The real schema tests use pinned native CPython/AiiDA on this macOS arm64 host,
a reviewed Linux arm64 modeling image, and an isolated pinned PostgreSQL 17.6
Linux amd64 container. They do not qualify a packaged Linux amd64 full host.

- Modeling image: `sha256:897205a13e4a95d9025ab574f4002db4878a436dc20c890c2b292208038898ea`.
- Modeling source image: `sha256:7295ed39c0673a53692e952ee46ec8d9817b56d12db37ccd2541ee25124d29de`.
- Modeling build identity JSON SHA-256: `02604f888ca6b0e96d7c654de0c1726ac34138fcd38c8ed03fa535cec8de1752`.
- Product lifecycle SHA-256: `7607605874ace69b62325445921bdf7a5667d055fdba3b00ace2a0b25e2f6d3a`.
- Product schema probe SHA-256: `624b52b4d5cefa965bb45cc0b07f2da8df131e3e983c8beae45c3c898b67a32c`.
- Product schema tests SHA-256: `1578d548b4956d0e74896eed021ba50de92aaced516f849cda9575fac82a0b10`.
- Platform reconcile SHA-256: `ea572911a5d20185fb0f4aed7b83cff3f49f8bfdfcad0054d5d70340831c7a7e`.
- Platform reconcile tests SHA-256: `4045123382b9cd404957effe0e9ae0386f52ccd682df4f291c78ff0611b93845`.

TemporaryDirectory fixtures and test-store scopes were released; each modeling
volume and PostgreSQL container was ownership-checked and removed, including on
failures. Build images remain content-identified cache artifacts. No live store,
cloud API, provider, IAM, backup creation, VM start or admission opening was used.
No tracked files were deleted; unrelated changes and index entries were preserved.

## Remaining obligations

Parent completed independent committed acceptance and owns a newly built native
release bundle containing this source. No launcher import-closure source changed.
Whole Linux host initialization, same-schema second activation preserving actual
private records, effective containment, real backup/recovery and running public
boundary qualification remain required. Schema-ledger/source compatibility is
not a general integrity audit of every database table or every historical object.
Existing unbound modeling markers and unfinished journals require explicit
operator reconciliation; no migration/adoption tool was added here.

## Self-Check: PASSED

Both implementation commits exist on their respective branches. Both new product
source/test files exist. Final focused checks passed; full phase completion and
human/deployment acceptance are deliberately not asserted.
