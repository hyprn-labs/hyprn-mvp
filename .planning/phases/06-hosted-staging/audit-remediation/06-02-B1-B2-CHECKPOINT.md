# B1/B2 operational execution checkpoint

Status: implementation committed; integrated acceptance pending. This is not phase completion or deployment approval. B3 remains unimplemented by this executor.

## Commits and scope

- RED: `7e6cac34` — lifecycle-only transition must not write the retained document row.
- Implementation: `b7ae3d0b` — operational execution storage, privacy, discovery, migration and fixture compatibility.
- Follow-up fixture adapters and this checkpoint are in the immediately following scoped commit.

B2 was included with B1 because separating lifecycle state while leaving discovery, list reads or release drain counts on the previous source would produce stale state. Existing application ownership and single-writer transactions remain unchanged. No new dependency, service, scheduler or live-store mutation.

Owned source: `execution.py`, `history.py`, operational parts of `store.py`, migration `0010_operational_execution.sql`, and its registration in `migrations.py`. Owned tests: `test_hosted_domains.py` (excluding the later A authority test), `test_hosted_postgres.py`, `test_history.py`, `test_run_status.py`. Fixture adapters: `durable_fixture.py`, `findings_native_fixture.py`, `combined_fixture.py`, `test_native_journey.py`.

Concurrent A authority/context changes in Store, the later authority test, and migration registrations 0011/0012 were explicitly excluded from this commit. They remain owned by the parent/A executor.

## Storage and deployment identity

- New application-owned `execution_operations` table: exact run/study/actor/command identities; lifecycle and preparation state; status and retained result projection; database-maintained payload hash and lightweight summary.
- Existing outbox text and generated fingerprint remain unchanged during lifecycle transitions. Preparation stores its bundle once. Recording writes only the result projection and status. Original request/bundle/frozen-input guards remain in effect.
- Operational payloads permit only status/history, preventing an overlay from replacing frozen inputs or bundle content. PostgreSQL RLS follows current study authority; background credentials receive bounded identities only. Completed result projection remains immutable.
- Full authorized reads compose the two records through History. Compact rechecks authenticate both exact source hashes and preparation state. Lists/status read operational fields without joining the large source.
- Explicit PostgreSQL migration backfills operational rows without changing outbox bytes. Ordinary open refuses the previous schema; an older binary refuses the upgraded schema. SQLite uses its existing additive local initialization convention; historical source bytes are retained.
- Migration identity: `0010_operational_execution`.
- Migration SHA-256: `885c049144ded01b2862eae6c1239f54616c40fb6ac0d1f20a85de6cd464c48b`.
- Latest complete application schema identity will additionally include parent-owned 0011/0012; release must use the fully integrated migration ledger.
- Backup remains the complete application database, including both tables. Fixture snapshots retain exact original outbox payload files and hashes while reading current state from the new owner. Old fixture databases remain readable without mutation.

## Interfaces

`Submissions.submit(actor, sid, body, *, expected_runtime=None, admission_limit=None)` checks capacity under the existing single-writer transaction. An identical receipt replays even at capacity. Saturation raises `DomainError('limit_exceeded', 429)` before the receipt savepoint, leaving the stable command available for later admission.

`Store.command(..., admission=None)` invokes the admission callback after replay and before the savepoint; callbacks must not persist side effects.

`Store.background_jobs(category, identity=None, *, after=None, limit=None)` returns only `study_id`, `actor_id`, `work_id`. Pages are limited to 1–100 identities, ordered by work_id; retain the last work_id and wrap after an empty page for fair iteration. Existing default category limits and assistant resume ordering are preserved. Explicit cursor support is available for runs and analysis/estimate/sample/prediction receipts.

`execution_operations.state` is authoritative for new lifecycle changes. Parent owns dispatcher.pending_runs and accepted-analysis child scope integration. The hosted release drain function was updated in 0010 to use operational state and exclude preparation failures.

## Verification evidence

All checks used the pinned local entry point with the host's already configured development data/tools roots, isolated fixture stores, and `HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480`. No installation or staging data was used. Commands below omit host-specific path values intentionally.

| Command / run | Outcome |
|---|---|
| `./hyprn-mvp dev check hosted-postgres`, initial attempt | No tests: sandbox refused existing tool-cache access. Escalated isolated check was then authorized. |
| Same command, default cache allowance | No tests: existing shared build cache exceeded 10 GiB; preserved shared layers and used explicit 20 GiB allowance. |
| Same command, RED | 39 passed, 1 planned assertion failure: state-only update changed PostgreSQL xmin while payload and digest stayed equal. |
| Same command, RED reporter attempts | Two further runs, each 39 passed/1 same intentional failure. Runner stripped PYTEST_ADDOPTS; temporary reporter configuration was removed. Genuine JUnit report classified `RED_EVIDENCE_OK`. No synthetic report was used. |
| Same command, first GREEN | 2 collection errors from concurrent monetary-tool registry bounds; no storage tests ran. Parent corrected the registry. |
| Same command, second GREEN | 35 passed, 9 failed. Corrected recursive null stripping in the operational projection, a missing budgeted native-double method, fixture ordering, and assistant discovery ordering. |
| Same command, third GREEN | 41 passed, 3 failed solely because concurrent assistant code required the not-yet-registered `assistant_public_messages` table. B tests passed, including public HTTP acceptance/preparation/restart/recorded values, source bytes/digest/xmin preservation, explicit upgrade and old-binary refusal, quota/replay, privacy and indexed discovery. |
| `./hyprn-mvp dev check api-a` | 121 passed, 4 failed: generated contract drift from concurrent schema work; two corruption fixtures still looked for retained history in outbox; one detector assumed the prior SQL alias. Fixtures/detector updated without weakening their assertions. Parent regenerated the contract. |
| `./hyprn-mvp dev check hosted-postgres`, A integrated run | 43 passed, 2 failed, exit 1 (40.38 s). The explicit-upgrade fixture retained its own read transaction, blocking a later migration with SQLSTATE 55P03; now commits the read before migration. The queue fixture tried to change committed receipts back to pending, correctly refused by immutability; now inserts the intended three pending receipts directly. Migration compatibility, exact-byte assertions and query-plan assertions remain intact. Final rerun belongs to integrated acceptance. |

Raw logs: `/private/tmp/hyprn-operational-red.log`, `hyprn-operational-red-junit.log`, `hyprn-operational-green.log`, `hyprn-operational-green2.log`, `hyprn-operational-green3.log`, `hyprn-operational-local.log`. Actual RED classification record: `06-02-B1-RED.json` beside this checkpoint. PostgreSQL fixtures use random ownership labels and teardown in finally; completed check output reported scope cleanup without failure.

Latest integrated log: `/private/tmp/hyprn-a1-hosted.log`. This run also passed the accepted-authority expiry/revocation/privacy test. The two fixture repairs and final combined/native journey read adapters have not been rerun separately; parent requested one integrated rerun after changes stabilize.

Measured PostgreSQL queue plan: 2,000 retained rows with a small active subset; `Index Only Scan` on `execution_pending`, 2 rows returned, 2 heap fetches, 2 shared buffer hits, no shared reads/writes; observed execution time about 0.306 ms in one scoped run. Returned pages contain at most two identities in the test and serialize below 1,024 bytes. The immutable-row regression uses a source document over 2 MiB and proves zero writes to that row by unchanged xmin, bytes and hash.

## Required integrated follow-up

Parent must run hosted-postgres and api-a on the committed integrated tree after A/C migration registration and authority integration. Later changes after the 41-pass run include stronger operational-key constraints, explicit checks of actor-admission and receipt-discovery index plans, multi-actor cursor reachability, no-outbox lightweight joins, release drain counts, and fixture adapters. Their final integrated results are not claimed here.

Run `bindings` for crash/reconciliation and result-binding coverage, the required contract/UI checks, and full qualification before release. Native execution in the new hosted lifecycle regression is a controlled double; this test proves public API/database lifecycle and retained results, not worker attestation or real numerical execution. Native/backup fixture adapters need the corresponding integrated acceptance groups.

Do not call B1/B2 qualified or mark 06-02 complete until these checks pass. B3 timeout causality and execution phase timing still need a fresh executor. Final schema identity, recovery release, backup and deployment are parent-owned release obligations.

## Self-check

Created migration and RED evidence exist; RED and implementation commits are ancestors of HEAD. No tracked files were deleted. No source placeholders were introduced. Unrelated working-tree and index changes were preserved.
