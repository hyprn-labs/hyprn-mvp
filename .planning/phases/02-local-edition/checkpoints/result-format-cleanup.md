# Current result contract cleanup — implementation checkpoint

User authorized removal of obsolete HYPRN-owned aggregate run facets from current backend/API, preserving upstream-native fields privately and immutable records. Parent owns final producer/worker builds, attestation and live demo refresh.

## Implementation boundary

Prepared artifact3 pins result protocol2; bundle10 explicitly tags the existing input layout (2/3/4/5/6/8, or 9 for closure4). Result2 and history7 keep execution, every output, criteria and artifacts; they omit convergence, optimization, completeness and applicability. Inventory equality, finite scalars, assignment, producer completion and unavailable/null/reason checks remain mandatory. Historical artifact/result/bundle schemas are strict and unchanged. The original 12 retained family pairs remain; current result/history pairing is explicit and tested independently.

Prior current-run contexts use Context2 and Closure4, frozen configuration8 and modified seed7. Public historical projections remove obsolete fields recursively and identify canonical source/view JSON with record_view. Existing digest fields retain exact source meaning. Exact artifact and computational archive bytes remain historical records. New writes use exact internal originals, not public projections.

Agent implementation/checkpoint cherry-picked as a1faba5/f23bae5. No live stores, workers, containers, authoring records or existing captures modified. The current protocol1 capture is copied byte-for-byte to native-programs-protocol1.json.gz for explicit historical admission; current native tests require the actual new producer capture and fail until rebuilt/recaptured.

## Verification at this checkpoint

All commands below use ./hyprn-mvp dev check GROUP in isolated scopes via /private/tmp/hyprn-orchestration-verify.py, after sourcing reviewed host environment and unsetting dedicated native scratch. This checkpoint freezes modeling build inputs; it is not final qualification or a working current native demo claim.

- contracts: 126 passed, 0 failed (nwiw56sf, 10.4s). All 430 original authored definitions compare exactly equal; additions only.
- agent-tools: 270 passed, 0 failed; units-bundle: 114 passed, 0 failed; bindings: 69 passed, 0 failed; modified: 59 passed, 0 failed (19baflf6; 54.1/107.3/93.8/225.9s).
- bridge-history: 117 passed, 0 failed including seven current-protocol parser scalar guards (8rxy3vkq, 228.9s); units-guards and guard passed in the same sequence (9.2/5.6s).
- Latest expanded units-bundle: 119 passed, 1 failed (nwiw56sf, 88.3s): new layout2 test accidentally supplied dependencies to config1. Test helper corrected; rerun pending. Other five current layout cases passed.
- Latest combined-static failed TSC on ConfigurationApproach closure4 dispatch; minimal branch widening applied. Rerun plus style-ratchet in progress (3gnbctgi).
- New stored-native result/protocol matching guard was added after bridge-history; repeat required. HTTP current-context lifecycle test pending. API-a repeat pending after earlier 118/2 obsolete public expectations were fixed. No native execution/build attempted.

Earlier failures retained: bau6hpc4 contracts122/4 stale schema assertions; tnp6flcd125/1 stale seed name; nsh8z9a3 contracts126/0 then agent260/10 fixture page shape and intentional malformed fuzz adapter; both fixed and agent270/0. 540gon7q119/7 followed removal of unused intermediate schemas before Read10 reference updated; resolved then contracts126/0. 3_94tth3 static environment absent; pinned offline npm install succeeded (29 packages, 0 vulnerabilities). x93brx9y and 8rxy3vkq static TSC exposed old type/dispatch assumptions; latest rerun pending. Incorrect generator path/native interpreter and one non-escalated write were refused; corrected generation used the existing pinned contract interpreter. No success inferred from those attempts.

Evidence roots are the named hyprn-orchestration-verification-* folders under the host temporary root. All scopes are isolated; release/archive ledger will be appended after checks finish. No scope in the live demo/durable native area was used or released.

## Producer build input freeze and next steps

- 050 patch SHA-256: 051e1068e637487850e33490b3ce8a02b062255a7e85cbbe03a3503241f151a0
- 090 patch SHA-256: 18cd7538f928d5fa5ca662d9b486fe11873214336a5595e8348535e93af0243e
- model.schema.json SHA-256: 0d1b16260113c89b481d86a1b9072e9472b66f477ed3050ba7f88a847d2b9537
- exact preserved protocol1 capture SHA-256: 958c151bdbfaabb93f09a4ff110c408bdc74ec0c23c9c4fc466d539f840a55dd

Root: follow checkpoint2.8 build recipe with modeling_runtime.build(root,evidence,no_cache=True,source_no_cache=False) only when unchanged source image remains verified; verify provenance, pin new modeling_producer image; recapture current 13 programs using updated capture_native_programs.py (requires prepared3/protocol2), preserving pre-split and protocol1 captures. Commit current capture and producer pin before worker rebuild/attestation. Current worker and attested schema/runtime sources changed, so no earlier attestation authorizes them. Root owns isolated native tests and exact final source attestation, then guarded live refresh. Required remaining groups depend on final integrated changes: projection, units-worker, approach-worker, units-launcher, archive/native, native-execution/bindings, units-attestation/native; root coordinates full qualification after this integration. Never use the live demo scratch for tests or cleanup.
