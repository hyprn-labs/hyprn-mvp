# Persistent case answers and study synthesis — executor checkpoint

Scope: approved continuous-approach follow-up; application/API slice only. Automated
verification is complete for this slice. UI integration, isolated served rehearsal and
human acceptance remain with the orchestrator; this is not Phase 3 completion.

## Commits and boundaries

- `47e03222c1eb58ccb4b036e5fe8bb6a025632380`: immutable application-owned answer
  versions, per-target heads, same-transaction reference checks/CAS/receipts, three public
  routes, generated schemas/types, client methods and 24 focused HTTP tests.
- `b7d94f2e051157c89a7950227dd97d466c1f86ff`: one additional failed-retained-run HTTP
  regression; final answer suite contains 25 tests.
- Base: `e0ed5bae8b4e68132509aad37674a42ae196208f`.

No modeling, execution schema, worker, launcher, runtime pin or historical record format
changed. No live installation or study was written. No delegated writer capability was
enabled. All tests used newly scoped synthetic stores and the required check entry point.

## Saved contract

`POST /api/1/studies/{study_id}/answers` saves a new immutable
`ScientificAnswer1`; command format `ScientificAnswerSave1` carries `command_id`,
`expected_revision` (null first, current answer-version ID thereafter), exact
`approach_version_id`, `case_id` (null for study synthesis), observations,
interpretation, qualifications, open_deliverables, and an explicit basis of configuration,
run, evidence and case-answer version IDs. Every field is required and closed.

`GET /api/1/studies/{study_id}/approach/versions/{version_id}/answers` returns explicit
head records for that exact approach version. Empty means unassessed.
`GET /api/1/studies/{study_id}/answers/{answer_version_id}` returns exact history.
Clients expose `answers`, `answer`, and `saveAnswer`.

One target family exists per study/approach-version/case. A synthesis can cite case answers
only from its exact approach version; these links never follow later heads. Many same-study
configurations/runs may support an answer, including comparison bases from other cases.
Pending or failed runs and incomplete deliverables do not prevent an explicitly qualified
authored answer. Execution and criterion outcomes never create an answer.

## Persistence and recovery

The application composition registers two new tables and immutable-version triggers through
the existing Store connection, using idempotent DDL. Existing rows are not migrated,
reinterpreted or seeded. The Store command transaction reauthorizes, checks the exact saved
approach and case, checks supporting references, compares the expected head, and writes
version/head/receipt together. Run references use History.run_row in that transaction.

The existing command receipt category is `answer_save`. A replay returns its original saved
result even after a later revision. A different payload with the same command is refused.
A stale head is refused. Missing/foreign references are refused without a partial answer.
Receipt recovery uses the existing owner policy: adopt committed result; resend the exact
command only when the authorized owner reports that recovery.

## Commands and results

All commands below ran as `./hyprn-mvp dev check <group>`, with the established development
environment and the generic scratch-root override unset. No alternative test interpreter
or direct runner invocation was used.

| Group | Final result | Evidence scope ID |
|---|---:|---|
| `answers-api` | 25 passed, 0 failed, 0 skipped | `11df18a9-8d67-4438-9d9a-d8ef35ad3a76` |
| `locality-contracts` | 155 passed, 0 failed, 0 skipped | `a52dd5c1-2aec-4b0b-b498-ac9c533e06e3` |
| `contracts` | 127 passed, 0 failed, 0 skipped | `1a9222e5-9aa7-409e-97a4-2692ffacfde4` |
| `combined-static` | 6 commands passed, 0 failed | `4ad92127-95e2-4207-ba0f-fd414d066619` |
| `guard` | 116 passed, 0 failed, 0 skipped | `c37c9a30-7ba3-4304-8cff-b9f06b491d48` |
| `style-ratchet` | 33 passed, 0 failed, 0 skipped | `f1d7cad8-6ee3-4868-b632-f397a3e2b68c` |

Combined-static covers design-system checks, generated tokens, UI contract checker, criterion
record tests, TypeScript and Vite build. Contract and boundary results cover the implementation
tree preceding `47e0322`; the only later production delta splits two SQL string literals into
identical concatenated strings. The architecture paragraph moved into its owner section.
`b7d94f2` changes only the regression test; its answer and style checks are the final runs above.

HTTP coverage includes create/read/revise, persistent reopen, exact old reads, concurrent
replay, payload conflict, stale revision, normal reader/writer/nonmember authorization,
unauthenticated and delegated-session refusal, missing cases and exact approach versions,
missing/foreign basis IDs, multiple configurations/runs, pinned case-answer versions in
synthesis, strict content/query validation and immutable database rows. The failed-run test
first reads a retained failure through the public run API with unavailable null outputs,
then saves an explicit interpretation and verifies the retained history bytes are unchanged.

## Failures and their resolution

1. Initial answers-api: 21 passed, 1 failed. Foreign evidence fixture used unsupported
   title/text fields in a legacy evidence command. Corrected it to the existing owner shape.
2. Initial locality-contracts: 154 passed, 1 failed. Direct run-association lookup violated
   History ownership. Replaced it with History.run_row; no History source change.
3. Initial style-ratchet: 32 passed, 1 failed. Two new SQL literals exceeded the line limit.
   Split the literals without changing SQL; final style checks pass.
4. Initial guard: 115 passed, 1 failed. The newly registered test was still untracked.
   Explicitly staged the task files; the unchanged registry guard then passed all 116.
5. Initial scratch cleanup encountered a read-only fixture directory. Made only directories
   within the positively identified task scratch scopes writable, then removed temporary
   stores and homes. No symlink target or durable fixture store was followed.

Existing warnings: Starlette's HTTP test-client deprecation, and two existing unknown
schema-marker warnings in contract tests. No dependency was added or changed.

## Artifact identities and cleanup

- Answer owner SHA-256: `c71b644fc621c096c5e33cff6af1399876a54a89d7a43acd50126cbdc9de1535`.
- Generated OpenAPI SHA-256: `340318aa4095b68b81f96a34a5ef9aa17ea40e047b971d1a130c86a6965a52d4`.
- Generated TypeScript SHA-256: `e57f6e382f9e6cdf1486feb3f7e6132122ab82854a888052264e6e1110f60e30`.

Released temporary stores/homes/native/aiida folders from all 13 task-owned scopes.
Evidence logs, scope descriptors and generated artifacts remain outside the repository.
No listener, browser, container or native process was started by this executor.

Released scope IDs: `2592a3cc-fc07-44fa-9fd8-2b6a8842e270`, `8eb34b3a-edbf-4c31-bf6b-38d4a9503791`, `34c185bf-4556-4836-8353-d1bd70c0b781`, `60e0b5aa-add9-4b88-8f2f-0898f738aced`, `a52dd5c1-2aec-4b0b-b498-ac9c533e06e3`, `1a9222e5-9aa7-409e-97a4-2692ffacfde4`, `4ad92127-95e2-4207-ba0f-fd414d066619`, `3b23a888-d480-441e-b56b-59c05141d4db`, `69539702-a5ae-449b-a92a-e0d383c2a25e`, `7c07eaab-3b46-411c-a092-9d83d46c05f2`, `c37c9a30-7ba3-4304-8cff-b9f06b491d48`, `11df18a9-8d67-4438-9d9a-d8ef35ad3a76`, `f1d7cad8-6ee3-4868-b632-f397a3e2b68c`.

## Remaining risks and next action

The tests prove application persistence and public HTTP semantics with synthetic retained
fixtures. They do not establish a newly executed scientific result, browser acceptance,
human acceptance, full qualification or deployment. The UI executor integrates the typed
read methods; the orchestrator checks the integrated tree and rehearses on an isolated study.
Existing live evidence is not automatically treated as an authoritative answer.

## Self-check: PASSED

Both implementation commits are ancestors of the checked branch; owner, routes, focused
tests and generated artifacts exist. Whitespace checks pass. No placeholder answer,
mock scientific prose or value was seeded into application storage.
