---
phase: 01-repository-baseline
plan: 01
status: gate-open
gate_commit: a66a1f3
---

# Phase 1 Plan 01: Repository baseline — summary

One product namespace (`hyprn-mvp`) across packages, contracts, identifiers, labels, fixtures, patches, design tokens and wordmark; a fail-closed runner with group classes and environment needs; term scan, naming and hygiene guards without exemption lists; every tracked test module registered in a must-pass group or retired with a reason. The phase gate passed 102 of the 103 groups it ran; **`findings-native` is under investigation, and the gate completes when it and `findings-native-read` pass.**

Tasks: 1.1–1.9 and the added 1.11 verified and merged; 1.10 (this gate) done except the open item. Per-task detail is in `checkpoints/1.1.md` … `1.11.md`; this summary points to them rather than repeating them.

## Groups, counts and timings

Gate run on `a66a1f3` with the sequential runner of that commit (`python3 -B deployment/checks.py --group qualification`, development variables exported, `HYPRN_MVP_SCRATCH_ROOT` set to the dedicated scratch folder inside the data root). The full per-group table with test counts and seconds is in `checkpoints/1.10.md`.

| Class | Groups run | Passed | Minutes |
|---|---|---|---|
| Static, contract and application | 41 | 41 | 11.6 |
| Native (Docker, AiiDA) | 38 | 38 | 100.4 |
| Browser (Node, Playwright) | 21 | 21 | 15.6 |
| Durable fixtures | 3 of 4 | 2 (`findings-native` failed; `findings-native-read` not reached) | 9.5 |
| **Total** | **103 of 104** | **102** | **137.2** |

Longest groups: `units-native` 766 s, `combined-native` 480 s, `ae-export` 451 s, `approach-ui-history` 412 s, `archive-service` 364 s, `approach-native` 334 s, `native-execution` 307 s, `approach-worker` 285 s. No group reported an absent environment. The term scan reports 0; `naming` and `hygiene` pass with no `PENDING` table.

After the gate commit: task 2.1 moved every check to `./hyprn-mvp dev check <group>` in the locked environments and added `local-edition` (105 must-pass groups now), and the gate gained a bounded parallel pool (`--jobs`, default 3; `--jobs 1` sequential) with serialized lanes for groups that share an ordering dependency or a fixed resource. A 29-group fast subset took 88.8 s with three jobs against 185.9 s sequentially; the full gate has not yet run in parallel.

## Digests changed

The attested execution source set (`launcher.execution_source_hashes()`) went from 35 entries (26 literal + 9 patches) to 34 (25 + 9): `deployment/migration-pins.json` left the set and the repository (1.5). The two-sided launch-path closure test passes throughout. Changes by task (old → new SHA-256 in each checkpoint):

| Task | What changed |
|---|---|
| 1.2 | `launcher.py` (data-root and scope-root reads) |
| 1.4 | Package rename: 12 attested digests (both package `__init__.py` files, `execution_bundle.py`, `calculation.py`, `computational_export.py`, `launcher.py`, `results.py`, `worker.py`, both contract schemas, `execution_runtime.py`, the then modeling manager); four application sources moved with unchanged bytes. Golden identity corpus revised namespace-only (corpus `efeaa418…` → `d389d1f1…`, every changed digest mapped back to the captured bytes). Generated contract and `ui/src/contract.ts` regenerated. Contract-test definition and file pins recomputed namespace-only |
| 1.5 | 8 entries: `execution_runtime.py`, modeling manager and compose recipe (renamed), `pins.json`, `worker.Dockerfile`, `launcher.py`, `modeling/rehearsal.py`; `migration-pins.json` removed |
| 1.6 | `ui/dependency-audit.json` lock identity (root name only); `ui/src/design/tokens.css` header regenerated |
| 1.7 | 20 attested digests (both schemas, modeling Dockerfile and policy, modeling runtime, `pins.json`, `computational_export.py`, `results.py`, `worker.py`, `modeling/provenance.md`, `rehearsal.py`, the nine WhatsOpt patches); modeling producer image rebuilt and pinned (`sha256:96c5a85a…`); `ProgramEntrypoint`, `ExecutionVersions` and two whole-file contract-test pins |
| 1.8 | None (attested sources left as they were; the comment rewrites they need are deferred to the Phase 2 re-attestation) |
| 1.9 | None in attested sources; durable native fixture manifest pinned (`eb4f0159…`); Documents prior definitions pinned individually (403 entries) |
| 1.11 | `contracts/tests/test_native_program_contract.py` re-pinned as it stands (product owner); reversing its two audited repairs gives back the original hash |

## Fixtures regenerated or replaced

| Fixture | Fate (task) |
|---|---|
| Golden identity corpus (`application/tests/fixtures/identity_golden.json`) | Namespace revision with proof per bundle (1.4) |
| Native program capture (13 cases) | Recaptured from authored format-1 inputs through the private contract; 252 blobs, file `5d685d99…` (1.7) |
| Durable native fixture (`findings-native-preflight`, `findings-native`, `findings-native-read`) | Regenerated from a passing `units-native` producer run with the tracked capture tool; manifest `eb4f0159…` pinned (1.9) |
| `findings-native-guards` fixture | Replaced by a synthetic fixture built in the group's own scope (1.9) |
| `approach-ui-history` fixture | Re-pointed to the regenerated fixture's application store; the salvaged application fixture and its resolver are retired (1.9) |
| Browser specs bound to one installation | Eight removed, one served case removed; served specs kept as opt-in `ui-served` (1.3) |

The superseded fixture folders below the fixtures root were neither modified nor deleted; deleting them is the product owner's decision.

## Assertions not kept (accepted by the product owner)

- Projection legacy cross-check: the WhatsOpt `040` patch schema is the baseline instead of a historical commit outside this repository (1.9).
- Interpreter registry: `runtime-observation` asserts its own entry instead of a one-entry registry (1.9).
- Physical group delete probes: the three cases of the refuted hypothesis now assert the hazard; logical deletion is covered by `documents-collection-protocol` (1.9).
- Findings guards prove their refusal logic against a synthetic identity; the real identity is exercised by the three continuation groups (1.9).
- Durable resolver: "no native AiiDA scope" went with the salvaged kind; malformed or foreign manifests are refused (1.9).
- Retained schema-1 byte-identity comparison in `test_native_program.py` is not kept; reaching a profile outside the scope is refused instead (1.8).
- Not selected: `test_history_read.py::test_actual_schema1_remains_data_only_and_byte_identical` (needs a historical record no scope holds; covered by `bridge-history`) and two real-preparation cases of `test_scoped_evidence.py` (covered by `public-api`) (1.11).
- Retired module: `integration/tests/test_configuration.py` (in-process OpenMDAO, refused by every group; revisit if its validator gets a caller) (1.11).

## Recorded exceptions

- `contracts/README.md`: two read definitions (`ModelPackage`, `ExecutionVersions`) were widened in place before any release; the widened bodies are accepted and every prior definition is now pinned individually (1.9).
- The test-safety fence admits the dedicated scratch folder below the data root only when it overlaps no store, evidence folder, read-only location or live root (1.9, mitigation T-1-04).
- Attested-source comments that still cite review codes are rewritten only in the Phase 2 step that re-attests anyway (1.8).
- The parser lock's real-wheel check runs only directly with pytest when a local wheel is named; the scoped runner does not pass that variable.

## Task 1.11 (added)

26 of 27 unregistered test modules now run in must-pass groups (new groups `access-control`, `public-api`, `public-discovery`, `modeling-contract`, `native-execution`); a guard requires every tracked test module to be a group target or retired with a reason. No product defect was found: every failure was test or harness drift. `qualification` grew by about 12 minutes.

## Open

- **`findings-native`: under investigation; the gate completes when it and `findings-native-read` pass.** The failure is reproducible: the continuation's fixture teardown refuses an immutable read of the private model copy because a nonempty WAL remains.
- The first full parallel gate (`--jobs 3`) should be compared with the sequential timings; only `documents-collection-protocol` was made exclusive for its runner time bound.
