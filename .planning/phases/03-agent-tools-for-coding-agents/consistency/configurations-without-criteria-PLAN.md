# M2 slice 3: configurations without criteria

Owner choices (2026-10-18): remove criteria from configurations everywhere, through new record format versions; retained formats stay readable.

## Outcome and acceptance

A new configuration, its preview, frozen record, execution bundle, worker result and run history carry no criteria; criteria are evaluated only through calculation bindings. Accepted when:

- New writes use the new versions below and are refused if they carry `criteria`.
- Every retained format (configuration revision 1–5, results 1–2, bundle ≤10, history ≤7) still reads exactly; golden, native-program and durable fixtures pass unchanged.
- The attested worker reads result protocol 2 and 3; native groups pass on a freshly built and attested worker.
- The configuration editor has no criteria section; run pages show execution only and point to calculations for criteria.
- Contract tests, the UI contract checker, `qualification` must-pass groups and the native groups listed below pass.

## New versions (new writes only)

| Family | Current | New | Change |
|---|---|---|---|
| Configuration request, candidate, revision | 4 | 6 | no `criteria` (5 stays the reserved Documents family) |
| Private modeling configuration (+ revision) | 3 | 5 | no `criteria` |
| Configuration preview, commit | 7, 5 | 8, 6 | wrap version 6 |
| Frozen configuration (+ Read) | 8 | 9 | wraps revision 6 |
| Results | `RetainedResults2`, protocol 2 | `RetainedResults3`, protocol 3 | no `criteria` |
| Execution bundle | 10 | 11 | file schemas name revision 6 and modeling revision 5; pins protocol 3 |
| Run history (+ Read), modified-run seed, result source | 7, 7, 2 | 8, 8, 3 | no criterion outcomes |
| Run status | `RunStatus1` | `RunStatus2` | no `criteria` facet |

## Decisions needed before batch A

1. **Approach binding.** ADR-0007 already says configurations no longer link an approach version. Proposed: revision 6 also drops `approach_binding`, so no new approach closure or approach run-context versions are made for a domain M5 deletes; approach findings cannot cite runs of new configurations. Recommended.
2. **Agent tools.** The read tools count and project `configuration.criteria`; they must tolerate its absence in the same change. That edits the agent tool catalogue, which waits for the agent-writes branch. Proposed: land batches A–C after that branch is merged (or with a one-line tolerance edit agreed with its owner).

## Batches (one integrated change; nothing lands until B passes)

- **A. Formats and application write path:** schema definitions and pinned body digests, execution schema regeneration, contract generation and UI types; `configuration.py`, `scientific_configuration.py`, `execution_bundle.py`, `history.py`, `modified_runs.py`, `result_bindings.py`, `store.py` (criterion evidence scope for new records), `approach_closure.py`; application tests.
- **B. Worker and modeling service:** `results.py` (protocol 3 without criteria; `evaluate_criteria` kept for retained protocol 2 reads and the calculation parity test), `worker.py`, `calculation.py`, `computational_export.py`; WhatsOpt patches 040/080 (`compatible_literal`) with AGPL notices and corresponding-source records; `launcher.py` source list; native program capture for protocol 3; native groups on a rebuilt, attested worker.
- **C. UI:** configuration editor and record without criteria, run outcomes without the criteria facet, change preview, evidence scope labels, exploration focus; control map and UI contract checker; browser groups.
- **D. Agent tools** (after the agent-writes merge): configuration and run projections, playbook text, golden projections.

## Verification

Focused groups per batch: contracts, locality-contracts, projection, bindings, api-a, modified, ae-configuration, units-configuration, units-bundle, findings-history, calculations-api; native (Docker): native-execution, bridge-history, units-worker, units-native, approach-worker, native-bindings, native-a/b, modeling-contract, units-model; browser: ui-navigation, foundry-nav, ui-reading, units-ui-configuration, ae-ui-*, approach-ui-*, calculations-ui. Then `qualification`.

## Estimate (guess)

Comparable to `790a09f` (one results bump, 54 files) but across three families: roughly 3–5 agent working sessions, plus native group wall time, which has not been measured on this host. The demonstration needs a rebuilt worker, attestation and modeling image before it can run new configurations.

## Version design (as decided 2026-10-18)

New writes accept only `ConfigurationRequest6`, and only for Model4 versions: model formats 2 and 3 require the approach closure that the new format drops. Older formats stay readable; new writes in them are refused.

| New definition | From | Difference |
|---|---|---|
| `ConfigurationRequest6` | Request4 | no `criteria`, no `approach_selection` |
| `ConfigurationCandidate6`, `ConfigurationRevision6` | Candidate4, Revision4 | no `criteria`, no `approach_binding` |
| `ConfigurationRequestRead6`, `ConfigurationCandidateRead6`, `ConfigurationRevisionRead6` | the unions | add version 6 |
| `ConfigurationCommit6` | Commit4 | wraps Request6 |
| `ModelingConfiguration5`, `ModelingConfigurationRevision5` | 3 | no `criteria` |
| `Compatibility2`, `Prepare2` | Compatibility, Prepare | admit modeling version 5 |
| `ConfigurationPreview8`, `ConfigurationPreviewRead8` | Preview7 | Candidate6, no `approach_closure` |
| `FrozenConfiguration9`, `FrozenConfigurationRead9` | 8 (Model4) | Revision6, no `approach_closure` |
| `RetainedResults3`, `RetainedResultsRead3` | 2 | no `criteria` |
| `PreparedModelArtifact4` (+ Read4, Response4) | 3 | result protocol 3 |
| `ExecutionVersions3`, `Capabilities3` | 2 | artifact 4, bundle 11 current |
| `ExecutionBundle11`, `ExecutionBundleRead11` | 10 From9 Model4 | input layout 11, protocol 3, Revision6 and modeling revision 5 files, no approach digests |
| `RunHistory8`, `RunHistoryRead8` | 7 Current Model4 | Revision6, RetainedResults3, bundle 11, no `assessment`, no `approach_closure` |
| `ModifiedRunSeed8`, `ModifiedRunSeedRead8` | 7 Model4 | Revision6/Request6, no approach closure |
| `ResultSource3`, `ResultSourcePage3` | 2 | `outcomes` carries execution only |

The run status read keeps `RunStatus1`; a run of a version-6 configuration reports `criteria` as an empty list (no configuration criteria exist).

## Progress (branch `feat/configurations-without-criteria`, worktree `.claude/worktrees/configurations-without-criteria`)

Owner decision 2026-10-18: requests 2–4 are refused now, not at M5; tests that write them migrate to version 6 in this slice.

Done (WIP commits, not yet green as a whole):
- Schemas: the 30 definitions above plus `CapabilitiesResponse3`, `CapabilitiesRead3`, `CapabilitiesResponseRead3`; execution schema regenerated; public contract and UI types regenerated (public configuration request, commit and preview are version 6 / preview 8).
- Application: preview, commit and exploration points write only version 6; projection 6 → private 5; bundle 11 assembly and admission; frozen 9; history 8 (no evaluator identity); results 3 outcome check; run status reports `criteria: []` for results 3; result sources 3; modified-run seeds 8; capabilities read 3; preparation 4 only with configuration 6. Boundary review tables updated (locality-contracts 162 passed).
- Modeling service: `100-configurations-without-criteria.patch` (adapter only; staged in the adapter chain, recorded in `modeling/provenance.md`).
- Worker: bundle 11, protocol 3 results without criteria, preparation 4; launcher and export admit bundle 11; the parser records no evaluator identity for protocol 3.

Done since (2026-10-19):
- Patch 100 exercised in the producer image (re-pinned); protocol-3 native program fixture captured from 13 Model4 cases (`integration/tests/fixtures/native-programs-protocol3.json.gz`).
- Configuration owner writes version 6 only; the legacy write paths (requests 1–4, approach pin) are deleted and `configuration` no longer imports `approach`.
- Configuration 6 runs resolve and recheck their result-linked inputs and seed modified runs; discovery advertises `configuration/6` and `execution_bundle/11` only when the service supports criteria-free configurations, and reads modeling capabilities 3.
- Tests that wrote configurations migrated to version 6 on the captured Model4 cases; the approach configuration-writing tests and the `approach-ui-configuration` group are retired (owner decision).
- UI: configuration 6 records read their context; model edits use format 4 where the service advertises it, so a model built in the editor can be configured; a refused earlier-run seed explains itself first.

Verified (2026-10-19, branch head after the native migration): every must-pass group passes except the pre-existing failures below. Native groups ran on scoped, freshly built and attested workers; browser groups on the current UI. Production gaps found by the native runs and fixed here: computational records admit results 3; derived configuration formats 4 and 6 report their runtime comparison; model-scoped evidence reads format 4 models. The units mixed-repair check mode is retired with its approach-selected journey.

Pre-existing failures (same on `feat/local-edition-continued` or caused by this host):
- `naming` (numbered planning file names), `style-ratchet` (files changed since its base);
- `units-staging` (pinned worker image absent from this host's Docker store);
- durable-fixture groups (`findings-native*`, `approach-ui-history`): the pinned fixture folder has no manifest;
- `archive-diagnostics`, `archive-native`: native licence metadata missing from the tool cache; `native-environment` wheel build in the scratch scope;
- retired `cases` field: `approach-ui-method`, `approach-ui-demo`, `approach-ui-assumptions`, `approach-ui-controller` (2), `exploration-answer-ui`, `agent-ui`, `units-ui-history`, `investigation-native`, `exploration-native`, `execution-batch`, and the `units-native` browser stage (also an outdated "Edit ports" step);
- artifact 2 expected where the adapter prepares artifact 3 since patch 050: `modeling-contract` (2), `modeling-isolation` (1), `ae-model` (1);
- `modeling/provenance.md` records an outdated hash for patch 080. Correcting it changes the modeling image's reviewed sources, so it needs a producer rebuild, re-pin and protocol-3 recapture together.

Remaining:
1. Batch D (agent tools tolerate configuration 6) after the owner merges the agent-writes branch; then land this branch.
2. The demonstration needs the rebuilt worker, attestation and producer image before it runs new configurations.

## Review findings carried by this slice (2026-10-18)

Fixed: criteria are read through a version gate (`configuration_criteria`; version 6 has none, earlier versions must carry the field); run status reports criteria of results 3 as null with reason `evaluated_in_calculations`; one private-version map (`scientific_configuration.PRIVATE_VERSIONS`); patch 100 checks requests against `Compatibility2`/`Prepare2` and advertises current execution versions 3–4 / 10–11; the new public read unions are flat, so the public views stay acyclic. units-model 32 passed (patch 100 exercised in the real adapter).

Known debt, not fixed here: version interpretation is spread across hand-written tuples in the worker, results, calculation, history, configuration and modified-run modules (architecture §6.2 asks for few named points). Consolidating them into the owner tables is a separate change.
