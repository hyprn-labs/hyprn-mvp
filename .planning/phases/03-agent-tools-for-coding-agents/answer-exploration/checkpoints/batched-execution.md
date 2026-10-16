# Bounded execution batches and completed slider preparation

Owner request: continue batching and worker-startup optimization toward six seconds per point, then finish remaining sampling securely. The owner warned of concurrent storage work. Implementation is isolated on `codex/batched-execution`; no storage-session files/index entries were changed. Integration and committed acceptance are recorded below when available.

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

The completed fuel evaluation has 150 new continuous-slice originals and 30 additional fits (five training points plus two disjoint checks per slice, reusing compatible originals). All 30 fits meet all 11 output targets without tolerance changes. Four further exact passenger endpoints complete methane/hydrogen's three-value integer interval. Integer passengers are never interpolated into fractional people. Earlier Mach fits and kerosene integer originals remain reused.

The demo runs from frozen `a3b2140` on `codex/sampling-runtime`, preserving runtime identity across the entire completed preparation. A storage-session edit invalidated attestation while one fit was pending: the old receipt was retained, exact numerical-request SHA was checked against every native exploration input, and zero matching native inputs permitted one deliberate fresh command after restoring the exact frozen source. Proof and old receipt identity remain in the external reconciliation manifest. No original points were repeated for that recovery.

Browser checks cover every continuous slider in kerosene, methane and hydrogen at calculated and estimated stops, with all 11 outputs. Final endpoint/last-fit verification and screenshot are recorded below. These are baseline one-input-at-a-time slices; combined-input interactions are not qualified. Automated evidence is not human acceptance.

Earlier recovery gaps remain: 212 historical native log/submission objects for 53 older runs were absent after the prior cleanup. Saved authoring and result records remain available; historical native export completeness is not claimed. See the existing all-input checkpoint. No historical records were rewritten.

## Remaining acceptance

Integrate with the storage branch, run focused committed native/public/contract/style checks, record timings and final browser evidence. Six-second full-run latency and multi-input joint surrogate qualification remain unachieved. No final release qualification or human acceptance is claimed.
