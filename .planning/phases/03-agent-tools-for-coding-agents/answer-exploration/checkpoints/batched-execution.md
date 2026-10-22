# Bounded execution batches and completed slider preparation

Owner request: continue batching and worker-startup optimization toward six seconds per point, then finish remaining sampling securely. The owner warned of concurrent storage work. Implementation is isolated on `codex/batched-execution`; no storage-session files/index entries were changed. Integrated implementation and committed acceptance are recorded below.

## Implementation

- A private bridge batch contains at most two independent run requests. Application claims, immutable bundles, execution budgets, native processes, restricted worker containers and results remain separate. AiiDA owns both processes in one runner; no candidate interpreter or writable filesystem is reused.
- Every claim is retained before dispatch. Current membership is rechecked after preparing the group. Lost/mismatched replies become uncertain and reconcile by each original request, without automatic redispatch. No public schema change. Sampling's existing explicit concurrency-one budget remains binding; independent queued runs can be batched.
- Pure successful schema validation is reused for exact ordinary JSON snapshots in a process-local LRU (16 MiB, 256 entries, maximum 1 MiB per entry). Encoding checks still run; failed validation, authority, semantic checks, hashes and runtime admission are never cached. Validator identity is retained. Validation uses the same decoded snapshot as the key.
- Trusted installed libraries and worker support modules are precompiled into hash-checked bytecode during the immutable image build, without network or importing candidate code. Fresh runtime attestation is required. No dependencies added.

## Development evidence and failures

All commands use `./hyprn-mvp dev check <group>` under the configured pinned environment. External logs are in the owner-authorized `hyprn-all-sliders` scratch folder.

- `locality-contracts`: red repeated-schema-walk regression (1 failed, 162 passed), then 164 passed after snapshot/type and bounded-cache checks.
- `bridge-history`: 139 passed, including lost replies, response identity/order mismatch, revoked access and reconciliation without duplicate launch. Repeated after dispatch formatting: 139 passed.
- `native-execution`: initial fixture failure (3 failed, 82 passed, 29 errors) because the previously cleaned durable dependency inventory was absent. Restored only 280 hash-verified lock/licence files and its reviewed selection from the retained inventory. Rerun: 113 passed, one stale history-test expectation (schema 2 versus current schema 10). That test now compares the exact retained native manifest rather than a hard-coded historical version.
- Native two-point batch passed with distinct restricted-worker identities and exact expected outputs. First public-batch group combined two incompatible fixture initializers in one store; duplicate native computer registration failed before the public journey. Separated the public journey into its own group; `execution-batch` then passed through real public POST/GET and the production stdio dispatcher (outputs 6 and 35).
- Style initially caught changed long lines, then the newly extended test's formatting; corrected. Final status is recorded with committed acceptance.
- The first cold public batch took 74.23 seconds for two points on a contended host. This is not a speedup claim or a six-second result. Warm and sequential comparison follows below.

## Sampling and reader verification

The completed fuel evaluation has 150 new continuous-slice originals and 30 additional fits (five training points plus two disjoint checks per slice, reusing compatible originals). All 30 fits meet all 11 output targets without tolerance changes. All three categories already had the three admissible passenger values among retained originals. A disabled slider during deferred overlay loading was initially mistaken for absent methane/hydrogen endpoints; four additional exact verification runs were unnecessarily authored before diagnosing that loading delay. They are retained, not deleted or presented as new coverage. Integer passengers are never interpolated into fractional people. Earlier Mach fits and kerosene integer originals remain reused.

The demo runs from frozen `a3b2140` on `codex/sampling-runtime`, preserving runtime identity across the entire completed preparation. A storage-session edit invalidated attestation while one fit was pending: the old receipt was retained, exact numerical-request SHA was checked against every native exploration input, and zero matching native inputs permitted one deliberate fresh command after restoring the exact frozen source. Proof and old receipt identity remain in the external reconciliation manifest. No original points were repeated for that recovery.

Final browser audit verifies all 42 category/input controls: all 39 continuous controls have at least five calculated stops and assessed estimates, each returning all 11 outputs; each integer control has three calculated stops and no fractional estimates. External evidence: `final-slider-audit.json` and `completed-sliders.png`. Optional retained-history overlays can still take tens of seconds to load; this is separate from preparation and remains a reader-performance follow-up. These are baseline one-input-at-a-time slices; combined-input interactions are not qualified. Automated evidence is not human acceptance.

Earlier recovery gaps remain: 212 historical native log/submission objects for 53 older runs were absent after the prior cleanup. Saved authoring and result records remain available; historical native export completeness is not claimed. See the existing all-input checkpoint. No historical records were rewritten.

## Integration boundary

Rebased implementation onto storage commits `640cd15` / `0a6a901` without conflicts; integrated implementation is `f628aa0`. Committed native/public/contract/style acceptance is recorded below. Development style check passed all 33 tests. A contended development comparison (before integration) measured 51.87 s cold batch, 49.72 s warm batch and 46.00 s sequential for the same two cases; do not claim a batch speedup from those measurements. Six-second full-run latency and multi-input joint surrogate qualification remain unachieved. No final release qualification or human acceptance is claimed.


## Integrated committed acceptance and live delivery

Implementation `f628aa0` is fast-forwarded into `feat/local-edition-continued`; storage commits `640cd15` / `0a6a901` are preserved. The later checkpoint/state update changes evidence text only. All commands below used the new supervisor with explicit scratch root `hyprn-batching-acceptance`.

| Check | Result | Scope / retained supervisor record |
| --- | --- | --- |
| `./hyprn-mvp dev check native-execution` | 114 passed, 223.64 s | `cc57f07e-5ecb-4468-8718-dfb193215d60` / `70afbd73-2c77-4b2d-a699-967e6800fdff` |
| `./hyprn-mvp dev check execution-batch --keep-scope` | 1 real public journey passed (six originals), 110.50 s | `d10a7f3c-4f90-42bc-8e4a-e596badac15b` / `ea8e0514-ada9-4ec3-8179-3c6266ef0651` |
| `./hyprn-mvp dev check locality-contracts` | 164 passed, 12.61 s | `0051b179-5fa7-47cc-b829-60d3b1e022dc` / `3dd77eb4-78c8-445a-a4b8-206c115b7c04` |
| `./hyprn-mvp dev check bridge-history` | 139 passed, 75.74 s | `21b17ef3-a917-40d9-87ab-bdc401f20e49` / `ed4af821-42a0-499f-9e02-0dd017b31636` |
| `./hyprn-mvp dev check style-ratchet` | 32 passed, 1 failed | `b4a19e16-d466-49fb-9a9f-69bb86817399` / `4bfd52ef-ac4d-499b-a7f3-6c591c51cf57` |

The last failure is 31 inherited storage-change findings: long lines in storage-added portions of `deployment/checks.py`, `scoped_fixture.py`, `test_attestation.py`, local CLI, and new `check_build_cache.py`, `check_storage.py`, `test_check_storage.py`, `test_check_storage_native.py`; the four new files also fail formatter checks. No finding refers to this batch's implementation. A temporary full-diagnostic test-message edit exposed all findings through a second style run (same failure; supervisor `056843e9-b71e-49e5-b296-0714f8c967e2`) and was then removed. The storage implementation was not reformatted. Owner: storage workstream; integrated style acceptance remains outstanding, not waived.

Uncontended same-input public comparison: two cold batched runs 28.160 s, two warm batched runs 26.847 s, two sequential runs 33.031 s. Batch elapsed is 18.7% lower than sequential; amortized throughput is 13.424 s/point. Both batched points become available at the group boundary, so this is not 13.424 s individual latency. Different models/authoring boundaries make direct comparison with the earlier roughly 31 s fuel-authoring cycle inappropriate. Six-second end-to-end latency remains unachieved. Worker bytecode compilation is included in the implementation, but its isolated causal speedup was not separately measured.

Supervisor cleanup succeeded for each integrated group. Only the explicitly retained public-batch timing scope remains under its 24-hour retention policy. Earlier unmanaged development scopes were not broadly deleted; none of the live/resumed studies was adopted by cleanup.

After all sampling ended, the live demo's 400 recorded outbox rows and absence of pending originals were checked. The three exact owned service processes were stopped, SQLite was backed up, and runtime/proof/wrappers were retained in external `before-batch-runtime`. An initial upgrade command lacked the demo's configured scratch-root variable and refused at scope validation; the app remained stopped and no candidate code ran. Restoring the explicit existing root allowed source selection, worker build and fresh containment attestation to pass. The same URL and stores now run the integrated immutable source checkout. Historical fitted samples retain their earlier exact runtime identities and are not re-fitted against the new runtime.

Public live verification submitted exactly two fresh commands for retained fuel configurations, then read the resulting records. Runs `6b83c453-eed1-418c-a6fc-6878817940c2` and `750e652e-438f-4db9-8056-1240914af9d9` reproduce all 11 outputs, criteria, execution outcome, exact model/configuration and evaluator pins. New histories have no integrity errors. Submission-to-recorded elapsed was 43.961 s for the pair; this does not establish that both were coalesced into one batch. The first comparison incorrectly compared the whole result envelope, whose run ID and bundle digest necessarily change; a read-only reconciliation compared the scientific fields and exact pins without any resubmission. Evidence: `live-batch-equivalence.json`, `live-batch-reconciled.log`, fresh containment proof and ready record in external scratch.

Live answer: `http://127.0.0.1:54821/ui/#v=1&view=overview&study=50e423fd-a709-4e21-9381-0b09022b4115`. Remaining: storage-owned style cleanup, delayed optional original overlays, six-second performance target, and separate joint-input surrogate qualification. The explicit sampling concurrency-one budget is unchanged. This is a completed performance increment and completed single-input sampling coverage, not a qualified release.
