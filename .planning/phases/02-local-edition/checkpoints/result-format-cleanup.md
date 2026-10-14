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

## Integration correction checkpoint

Follow-up to ee27a18: real HTTP old/current run-basis tests exercise preview, draft/save,
version read and receipt read. The legacy case verifies nested public source/view hashes
and unchanged SQLite bytes; the current case verifies Context2/Closure4 with no obsolete
fields. This exposed Receipt3 still pointing to the old command-result union; corrected
with additive CommandResult3/Read3 and preserved every old definition. The manual public
configuration-preview union now includes Preview7; API and UI state types include it.
Resolver.frozen accepts the additive Read8 union. Portable/native exports select results
from the exact bundle protocol. Missing current results retain history7 rather than being
mislabelled with the older input family's history version.

Readability fixes are limited to changed statements; a whole-function Prettier expansion
was narrowed using a dry-run patch after preserving exact full files/diffs externally and
proving canonical formatter output unchanged. Automatic approval first rejected reconstruction
as potential loss of others' changes; ownership/content proof and a scoped patch resolved it.
A second automatic rejection misread Read8/Read2 as replacements; exact oneOf definitions
proved legacy formats remained included, and the counted call-site edit then succeeded.
No requested work remains blocked by either review.

Passed latest focused runs:
- contracts127 and approach-api25 (r5hlmia8; 8.7/20.6s), including the real old/current receipt journey.
- units-bundle121 (kedrkd10; 91.8s): six prior input layouts with prepared3/protocol2,
  strict cross-protocol refusal and Context2→Closure4→Frozen8→Bundle10/input9.
- combined-static all6, style-ratchet33, guard116, units-guards138 (1wnihf1u;
  4.1/11.3/4.0/4.6s).
- approach-closure67 and approach-history39 (c9jyyep3; 4.9/313.7s).
- API-a finished successfully in kedrkd10; exact count and repeated bridge-history result
  are appended in final verification. No source changes are planned during root native lane.

Additional failures: expanded units119/1 used dependencies with legacy config1; corrected.
Next expanded units120/1 omitted the required linked implementation in its new fixture;
corrected and121 passed. New HTTP approach24/1 exposed the actual receipt bug above;
corrected and25 passed. Static3gnbctgi TSC needed separate discriminant branches, then
wdtihtho static passed; style32/1 found changed long lines, corrected. r5hlmia8 static
failed the exact textual UI exemption after whitespace formatting; checker now normalizes
whitespace while keeping exact tokens/count and static passes. Root owns actual current
native fixture rebuild/execution; current native test assertions now require preparation3,
result2, history7 and bundle10 with explicit input layout. Seed4 for unchanged layout6
is deliberately preserved. No standalone unit-native browser spec numeric change was needed.

Fifteen completed evidence roots archived/released: bau6hpc4, tnp6flcd, x93brx9y,
g0iin9q_, nsh8z9a3, 19baflf6, 8rxy3vkq, 540gon7q, nwiw56sf, 3gnbctgi,
wdtihtho, ro50agg1, c9jyyep3, 575yjlak, 1_1i4ujj: 27 scopes, zero remaining.
Active/final sequences are released after completion; no native/live scope touched.

Corrected final model schema SHA-256: 7dbe1a233a1f852a7187f442cc784840826f56112b3e4e862bdfe0e9f6a30bc2.
Execution schema is unchanged by this Documents-only receipt fix. Root explicitly
accepted rebuilding producer and recapturing after this correction; earlier rebuilt
image/capture is intermediate evidence only. Exact old538 definitions remain unchanged.


## Unissued input-layout refusal

Final read-only dispatch audit found standalone schema9 remnants in runtime admission;
9 is an input layout tag of bundle10, never an issued bundle. Removed those entries in
submission, launcher, independent worker, retained reader and native export admission.
Added schema9 refusal to existing old-version worker/native preflight tests and retained
reader negatives. This does not change producer/model schema inputs. Root was notified
before changing runtime sources and will attest only the final integrated tree.
Guard116 and units-guards138 pass (mv0n8_26; 5.0/6.0s); style follows in the same log.
API-a121 passed (kedrkd10,164s), including current bundle with missing results keeping
history7. Final committed agent-tools270 passed (81te2q_8,43.9s). Bridge-history and
archive-service/readiness/locality checks remain running; no current native execution
has been claimed by this lane.

## Final executor verification and handoff

Runtime/schema source remains frozen at da90a08. Final bridge-history passed119,
failed0 (23xemlbl,279.3s), including standalone9 refusal. Final style-ratchet33,
guard116 and units-guards138 passed (mv0n8_26). Final sequence81te2q_8 passed
agent-tools270 (43.9s), archive-service44 (679.6s), runtime-observation58 (26.6s)
and locality-contracts155 (12.1s), with zero failures or skips. These results
complement the focused contract/API/current-receipt checks above; they do not
establish current native producer execution or final qualification.

Release ledgers now cover21 evidence roots and45 isolated scopes, all archived
and released, zero remaining. Additional completed roots after the first27 scopes:
r5hlmia8,1wnihf1u,mv0n8_26,kedrkd10,23xemlbl,81te2q_8. The earlier3_94tth3
environment refusal allocated no scope. No live or durable-native scope was used.

Root confirmed the boundary: current local production remains enforced by its exact
pinned producer; this batch does not broaden arbitrary private-backend policy.
Strict historical readers retain old protocol bytes and digests, while public
historical views remove obsolete aggregate fields and expose explicit source/view
identities. Downloads retain exact historical artifacts. This decision requires
no additional producer/schema changes.

Root review found one further current native fixture assertion: the shared
ApproachJourney.execute helper still expected history3 when executing a new run of
a legacy string-unit model. It now requires history7/results2, and the units-native
comment describes that current execution accurately. This final fixture-only delta
changes no attested source or producer input; root owns its native journey verification.
Old captured-history admission tests remain unchanged.

Archive-service wall time prompted a read-only performance inquiry. Retained
units-launcher baselines were77.8s and77.4s; root's current integrated run passed
at148.4s. No retained archive-service timing was found for comparison. A pure
schema timing probe used a nonexistent old PreparedModelArtifactRead2 definition
and failed before measuring; no runtime or store was touched and no performance
conclusion is claimed. Root explicitly deferred optimization unless the real
browser/native journey exposes material latency. Source freeze remains intact.

Root owns the final rebuilt producer image/pin and current13-program recapture,
worker rebuild/attestation, integrated native checks and guarded demo refresh.
The earlier producer build before the receipt correction is intermediate evidence.
The exact protocol1 and pre-split captures remain retained. No live deployment,
human acceptance or complete phase/release qualification is claimed by this lane.

## Native retained-input regression correction

Root's integrated units-worker run at57679bc failed5 and passed162 in wpe0feod.
All five failures (affine rejection, kelvin alias, direct mapping, HTTP/restart and
original-template reference) reached the same independent retained_bundle field
guard. Current bundle10/input2 carries preparation3 with entrypoint, executable
digest and result protocol; the guard incorrectly tested outer bundle2 instead of
resolved input layout2. Commit1f98c91 corrects that one condition without relaxing
the exact field set, protocol pairing, byte inventories or digests.

Existing registered retained-reader success and corruption cases now also cover
an inert bundle10/input2 fixture. It is data-only and never executed; the current
native capture remains exact and unchanged. bridge-history passed128/0
(w9q7l0s5,224.6s). Style initially passed32/failed1 for two new helper formatting
lines; only formatting changed, then style-ratchet passed33/0
(ib5jgekz,9.6s). All three additional scopes archived/released, zero remaining;
the executor's cumulative ledger now covers48 scopes. No native resources used.

No producer input, schema, pin or captured program changed. results.py is an
attested runtime source, so root must include1f98c91 in worker rebuild/attestation
and rerun the failed native group. Root received the implementation commit before
this checkpoint. Full native success remains unverified by this executor.

## Current demo configuration capability correction

The refreshed demo producer returned200 for capabilities, but Configurations still
used the old CapabilitiesResponse/Capabilities schemas. A read-only authenticated
capability probe against the current scoped service found11 old-schema violations
(preparation3/bundle10 and retained version inventory) and zero violations against
CapabilitiesRead2. Model reads already used the current read union. No authoring
record was changed during diagnosis; the scoped credential was not printed.

Commit5c19b90 switches the two configuration capability reads to the existing
CapabilitiesResponseRead2/CapabilitiesRead2 aliases. Existing HTTP configuration
preview/save regression now covers the current producer capability matrix and
rejects unknown preparation99 with503 and zero allocated configurations/outbox.
approach-configuration passed61/0 (gfulo8f2,14.5s); style-ratchet passed33/0 (8.9s).
Both scopes archived/released, zero remaining; cumulative executor ledger50 scopes.

This changes application configuration code only, no schema, producer input,
capture, worker or attested source. Root owns app refresh and real demo retry;
this lane did not restart the demo or save any live configuration. The focused
HTTP tests use an explicit private-service transport, not native numerical proof.
