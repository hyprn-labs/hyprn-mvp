# Factorization opportunities

**Analysis Date:** 2026-10-13
**Baseline:** Phase 1 tasks 1.1–1.9 verified, 1.10 (phase gate) next; Phases 2–4 planned (`phases/0[2-4]-*/0?-PLAN.md`).
**Sources:** the codegraph index (12,054 nodes, 38,372 edges, 286 files), direct reads, and the sibling documents in this folder (`ARCHITECTURE.md`, `CONCERNS.md`, `TESTING.md`).

## How to read this

Each item names a **seam** (where behaviour can change without editing callers), the **interface** that seam exposes, and what it buys in **depth** (more behaviour behind a smaller interface). Items are ordered by value over effort. "Covered" refers to the planned Phase 2–4 tasks.

Effort: **S** is under one task, **M** is about one task, **L** is several tasks or touches attested sources.

Invariant checks used in every item:
- **Attested sources:** does the change touch `ATTESTED_PROJECT_FILES` (`application/tests/test_module_boundaries.py:96`), and so force a worker re-attestation?
- **Golden corpus:** does it change canonical bytes or digests (`application/tests/fixtures/identity_golden.json`)?
- **Module-boundary test:** does it add or remove import edges?
- **ADR-0004:** does it move orchestration or authoritative state, and in which direction?

## Summary

| # | Title | Effort | Best timing | Covered by a plan? |
|---|---|---|---|---|
| 1 | Orphan guard for Python test modules | S | Now, with 1.10 | Partly (STATE names 3 modules; 4.4 covers Documents only) |
| 2 | Server-decided recovery on the receipt | M | Before 3.20 | No (3.20 adds a second client-side copy) |
| 3 | One browser-fixture harness | M | Before 4.4 | No (4.4 adds a seventh copy) |
| 4 | One run-row read and a light run-status read | S–M | Before 3.9, at the latest 3.32 | Partly (3.32 waits for a light read that no task delivers) |
| 5 | Declarative registry for every test group | M | Right after 4.4, or fold into 4.4 | Partly (4.4 covers Documents groups only) |
| 6 | Boundary test pins the whole layer table | S | With 3.1 | Partly (3.1 makes the scan subpackage-aware only) |
| 7 | Dynamic-loading allowlist keyed by function, not line | S | Now, or with 2.8 | No |
| 8 | API routes in per-owner routers | M | Decide before 3.4 and 4.1 | Partly (3.4 adds the first router, for agent routes) |
| 9 | Study-shell view registry | M–L | Before 3.6 and 4.13 | No (ui-target §7 names the seam) |
| 10 | Remaining hosts on the access-loss seam | S–M | With 4.23, before the Phase 5 security review | No |
| 11 | Contract schemas split by consumer | L | With 4.37 (re-attests anyway), or 2.8 | No |
| 12 | Version-family capabilities instead of version literals | L | With 4.34–4.37 (OQ-1 chain) | No |
| 13 | Outbox history projection made explicit and rebuildable | M | After the first release (or with 3.9) | No |
| 14 | Authorization by effect instead of boolean flags | M | After the first release | Declined for now by 3.1 |

---

## 1. Orphan guard for Python test modules

**Evidence**
- `deployment/checks.py:32` `GROUPS` lists 94 groups, each naming its target files by hand.
- 28 tracked Python test modules are named by no group. Examples:
  - `application/tests/test_authorization.py`, `test_ownership.py`, `test_security_regressions.py`, `test_public_contract.py`, `test_api.py`, `test_run_api.py`
  - `contracts/tests/test_contract_boundaries.py`, `test_modeling_contract.py`
  - `integration/tests/test_isolation.py`, `test_execution.py`, `test_history_read.py`
  - `modeling/tests/test_atomic_adapter.py`
- Some of these are imported as helper libraries by other tests, but none runs as a target.
- Browser specs already have this guard: `deployment/tests/test_repository_guard.py:905` (`test_every_browser_spec_is_registered_in_a_group`). Python modules have none.

**Problem:** `qualification` can pass while security and contract tests never run. The registry is hand-maintained, and nothing catches a module that drops out of it.

**Change:** add `python_test_modules()` beside `browser_specs()` (`deployment/checks.py:587`), plus a guard case: every tracked `test_*.py` is selected by exactly one group, or listed in a closed `HELPER_MODULES` set with a reason. For each orphan, decide whether to register it or remove it with a reason. This is the generalized form of the orphan check that 4.4 plans for Documents (`test_documents_registry_every_documents_test_has_one_group`).

**Invariants:** no attested source, no golden-corpus change. Registering a module may expose failures that already exist.

**Effort:** S for the guard. The orphan triage is variable.

**Timing:** now, with 1.10. The phase gate should not certify `qualification` while it silently skips the authorization tests. **Covered:** partly. `STATE.md` tracks 3 retained-record modules; 4.4 covers Documents only.

## 2. Server-decided recovery on the receipt

**Evidence**
- `ui/src/api.ts:188` (`mutate`), `:209` (`reconcile`) and `:227` (`retryOriginal`) encode the receipt-state table in the browser:
  - `committed` or `rejected` clears the command;
  - a run with a `run_id` clears it;
  - `pending_remote` on a model command makes it retry-ready;
  - a `resource_not_found` receipt makes a non-run command retry-ready.
- `PublicReceipt.state` has 9 values (`ui/src/contract.ts:565`).
- Phase 3 task 3.20 step 1 re-encodes the same table in Python, with different rules: `pending_remote` is re-checked three times at 2, 4 and 8 s; an absent receipt is retried once.

**Problem:** two clients repeat the same recovery logic differently. This is what ADR-0004 (Context; consequences 2 and 4) warns against. A third client, the command line, would need a third copy. The rule "never resend a command whose outcome is unknown" is enforced separately in each client.

**Change:** the owner decides. The receipt read (`GET …/commands/{command_id}?category=`, owned by `store.receipt`) returns a closed `recovery` field: `adopt` (with the result), `wait` (with `retry_after_s`), `resend_same_command`, `uncertain` or `refused`.
- The UI's `reconcile` and 3.20's `journal.reconcile` become thin readers of that field.
- Interface: one field on an existing route.
- Depth: the state table and the per-category exceptions (run never resent; scoped 404 for non-run categories) live once, in `store`.

**Invariants:**
- Additive public contract change: the contract tests and the UI contract checker must stay green.
- `store` is not attested, and canonical bytes are unchanged.
- ADR-0004 improves: coordination moves from clients to the owner.

**Effort:** M. **Timing:** before 3.20, or as 3.20's first step, so the agent journal never ships its own table. **Covered:** no.

## 3. One browser-fixture harness

**Evidence:** the same code is repeated across `deployment/tests/`:
- **Proxy handler** (6 copies): forwards `/api/1/*` through `TestClient` with header filtering, serves the static UI from `dist` with `is_relative_to` containment, and defines `respond`. Found in `ae_ui_fixture.py:105-172`, `approach_ui_fixture.py:48-146`, `units_ui_fixture.py:207-326`, `ui_fixture.py:58-72`, `combined_fixture.py:22-35,138` and `findings_native_fixture.py:758`.
- **Playwright staging** (5 copies): writes a config that does `import base from 'ui/playwright.isolated.config.ts'`, runs `node …/playwright/cli.js test --grep <tag> --reporter=json`, and parses `stats` from the report. Found in `ae_ui_fixture.py:347-350`, `approach_ui_fixture.py:324-350`, `units_ui_fixture.py:361-365`, `units_native_fixture.py:188-207` and `findings_native_fixture.py:1127-1130`.
- The fixture files total 5,746 lines.
- Phase 4 task 4.4 step 4 plans `documents_ui_fixture.start_isolated_api(scope)` "on the `ae_ui_fixture.run` pattern", which would be a seventh copy.

**Problem:** each copy has slightly different write allowlists, body caps (2 MiB in one, 262,144 bytes planned in another) and header rules. A containment or header fix has to be made six times.

**Change:** add `deployment/tests/browser_harness.py` (stdlib plus the existing `TestClient`):
- `serve(scope, app, *, dist, writable=predicate, controls={path: handler}, body_cap)` returns the server URL and a stop function;
- `run_playwright(scope, *, tag, config_base, evidence)` returns the parsed `stats`.

Each fixture keeps only its seed data, its `/fixture/*` controls and its write predicate. Interface: two functions. Depth: proxying, containment, staging, the reporter and evidence files live behind them.

**Invariants:**
- No attested source.
- The guard tests that pin fixture behaviour, such as the bounded write allowlists, must keep passing per group, with their counts recorded before and after.

**Effort:** M. **Timing:** before 4.4 (then 4.4 calls `serve` instead of copying), or as 4.4's first step. **Covered:** no.

## 4. One run-row read and a light run-status read

**Evidence**
- The `run_associations r JOIN outbox o USING(run_id)` statement is written 6 times: `application/src/hyprn_mvp_app/execution.py:93,128,135,183` and `history.py:258,281`.
- `History.run_row` (`history.py:274`) already exists, authorizes, and returns the row with its receipt. `execution` imports `history` but does not use it for these reads.
- `approach.py:470` and `result_bindings.py:92,105` query `run_associations` directly.
- Phase 3 task 3.32 step 3 keeps "the cached last full read per run until the API advertises a light run-status read", but no task delivers that read.

**Problem:**
- Ownership of the run row is spread across four modules.
- The planned agent tool would hold a client-side cache of execution status, which is close to the parallel representation that ADR-0004 consequence 5 forbids.
- `History.list` (`history.py:246`) already projects the public state cheaply, using `json_extract` without loading payloads.

**Change:**
- Route every run-row read through `History.run_row` (or one `run_row(db, sid, run_id)` owned by `store`, which owns run associations by §7) with a column selector.
- Expose `GET S/runs?fields=status` (or `S/runs/{id}/status`) built from the same projection, so `get_run_status` and `wait_for_runs` read the owner instead of caching.

**Invariants:**
- No attested source.
- No import-edge change (`execution → history` already exists).
- ADR-0004 improves.

**Effort:** S for the reads, M with the route. **Timing:** before 3.9, which introduces the run read tools; at the latest within 3.32, which edits `execution.py` and `api.py`. **Covered:** partly.

## 5. Declarative registry for every test group

**Evidence**
- `deployment/checks.py` (1,007 lines) classifies its 94 groups through about 20 hand-kept sets that must agree: `GROUP_INTERPRETERS` (:474), `AE_*`, `APPROACH_*`, `UNITS_*`, `NATIVE_PYTEST_GROUPS` (:542), `APPLICATION_PYTEST_GROUPS`, `CHILD_GROUPS` (:556), `OPT_IN_GROUPS`, `DOCKER_GROUPS` (:572), `BROWSER_GROUPS` (:576), `FIXTURE_GROUPS` (:581), `FIXTURE_BROWSER_SPECS`, among others.
- Dispatch is written twice: once in `run_group` (:828) and once in `child` (:934).
- `findings_guards_passed` hard-codes `testsRun == 17` (:904).
- Tasks that edit `checks.py`: 2.1, 3.1, 3.6, 3.12, 3.13, 3.14, 3.15, 3.23, 3.26, 4.1 and 4.4. The roadmap serializes all of them.

**Problem:** adding a group means editing three to five sets and two dispatch tables in a shared file. A group that is missing from one set fails late or runs under the wrong interpreter. The file is a serialization bottleneck across three phases.

**Change:** generalize 4.4's Documents design to every group: one entry per group (`deployment/groups/<family>/<group>.json`, or one Python table) with `targets`, `runner` (closed set: `pytest`, `unittest-guard`, `browser-isolated`, `browser-served`, `fixture`, `static`), `interpreter`, `class` and `needs`. The current sets are derived from the entries, `run_group` and `child` dispatch on `runner`, and `--list` is generated.
- Interface: one entry per group.
- Depth: the environment checks, interpreter choice, scoping and evidence recording all live in the runner.
- Phase 2's `./hyprn-mvp dev check` wraps it unchanged.

**Invariants:**
- No attested source.
- `--list` before and after must be identical, as 4.4 already requires for Documents.
- The guard cases that read the sets move to the loader.

**Effort:** M. **Timing:** fold into 4.4, or do it right after 4.4 and before the Phase 3 group additions (3.1 `agent-tools`, 3.6 `agent-ui`). **Covered:** partly (4.4, Documents only).

## 6. Boundary test pins the whole layer table

**Evidence**
- `application/tests/test_module_boundaries.py` pins selected directions only: the pure seam, the attested closure, `history` against its consumers, `approach` never reaching `configuration`, the alias ban and the private allowlist.
- The code has six edges that `docs/specs/architecture-and-contracts.md` §7 does not draw:
  - `modeling → store` (`modeling.py:14`);
  - `store → readiness`, imported inside functions (`store.py:214,233`);
  - `configuration → {modeling, readiness, scientific_configuration}` (`configuration.py:11,249-250`);
  - `execution → readiness` (`execution.py:30,102`);
  - `modified_runs → readiness` (`modified_runs.py:7`);
  - `dispatcher → computational_export` (`dispatcher.py:22`).
- None of them creates a cycle today.
- The private-access allowlist is healthy (3 framework or same-module entries, `:550`).

**Problem:** "acyclic, function-local imports included" is a rule in prose. The test would not catch a new cycle through an unpinned edge. `store → readiness` points from the transaction owner up to an observation module.

**Change:**
- Add one `LAYERS` table in the test, a copy of the §7 diagram, and assert that the observed import graph, including function-local imports, is a subgraph of it.
- Update §7 for the six edges, or move `runtime_identity` and `valid_observation_time` to their owner, so that `store` no longer imports `readiness`. That follows the §7 rule "move pure functions to their owner".
- Interface: one table.

**Invariants:**
- No attested source.
- Moving `runtime_identity` touches `store`, `execution`, `modified_runs` and `configuration` only.

**Effort:** S. **Timing:** with 3.1, which already rewrites the boundary scan to be subpackage-aware and adds the agent package rows. **Covered:** partly.

## 7. Dynamic-loading allowlist keyed by function, not line

**Evidence:** `DYNAMIC_ALLOWLIST` (`application/tests/test_module_boundaries.py:116`) pins `(path, line, callee)` in two places:
- `worker.py` lines 1010, 1013 and 1014;
- `calculation.py` lines 66 and 129.

**Problem:** any edit above those lines in an attested file fails the test, even though no dynamic call was added. Two planned edits will trip it: the pending comment rewrite in attested sources (`STATE.md`, Phase 2 release snapshot) and 4.37 (worker admission). Each forces a reviewed allowlist edit.

**Change:** key entries as `(path, enclosing function, callee, count)`, for example `('worker.py', 'load_program', 'exec_module', 1)`. The test still fails on any new call site or a moved seam.

**Invariants:** test-only, with no attested source and no golden-corpus change.

**Effort:** S. **Timing:** now, or with 2.8, before the first re-attesting edit. **Covered:** no.

## 8. API routes in per-owner routers

**Evidence**
- `application/src/hyprn_mvp_app/api.py` (512 lines, 34 KB) defines all 49 routes inside `create_app` (:102), plus the middleware.
- Tasks that edit `api.py`: 3.1, 3.4, 3.12, 3.22, 3.32, 4.1, 4.9a, 4.9b, 4.20, 4.25 and 4.32. All are serialized as a shared file.
- 4.1 adds six Documents routes to `api.py`; the Documents registry holds 47 routes in total.
- 3.4 introduces the first `APIRouter` (`agent_runtime/routes.router`), included inside `create_app` so the contract generator sees it.

**Problem:** one module is both the HTTP edge and the route table for every domain, which makes it the most contended file of Phases 3 and 4.

**Change:** keep `api.py` as the edge (middleware, auth dependency, envelope, `create_app` composition). Each domain owner exposes a `router(deps)`: Documents from 4.1, agents from 3.4, and the existing domains moved one at a time later.
- Interface: `router(deps) -> APIRouter`.
- The generated `contracts/hyprn-mvp.openapi.yaml` must stay byte-identical for moved routes; the contract tests prove it.

**Invariants:**
- No attested source.
- Adds the edges `api → <owner>.routes`, which stay acyclic.
- ADR-0004 is neutral: the routes stay on one API.

**Effort:** M to move the existing routes; S to decide "new domains get routers". **Timing:** decide before 3.4 and 4.1; move the existing routes after the first release. **Covered:** partly (3.4).

## 9. Study-shell view registry

**Evidence**
- `ui/src/Workspace.tsx` is one function component (`:48`, 449 lines, 65 KB) with 53 `useState`, 25 imports and 84 callees (codegraph).
- It has 55 `view === '…'` branches over 6 views (`workspaceModel.ts:70`).
- It handles routing, guards, archive and dirty dialogs, and the model-version save orchestration (`:427`).
- Peers are also large: `ConfigurationPanel.tsx` (58 KB, 29 `useState`), `ModelEditor.tsx` (40 KB, 35 `useState`) and `RunPanel.tsx` (38 KB).
- Tasks that edit `Workspace.tsx`: 3.6, 3.23, 4.13, 4.26 and 4.29. Each adds a view or a placement.
- `docs/specs/ui-target.md` §7 ("Structure") names the shell as the seam. Architecture §7 asks for "navigation and composition while domain controllers own their workflow state behind one editor-guard interface". The guard interface already exists (`useGuardSlot`, `GuardEntry`).

**Problem:** every new view (Agent activity, Documents library, reader, cited source) edits the same component and its link parser. The shell also performs a multi-call save (save guards → read model → commit → read revisions) that belongs in a model controller, as `ApproachController` already shows.

**Change:** add a closed view registry: `{name, parseLink, render(ctx), guard?, available(capabilities)}` for each view in its own module. The shell iterates the registry for tabs, routing and guards. The model-version save moves to a `ModelController` beside `ApproachController`. Interface: one registry entry per view.

**Invariants:**
- No attested source.
- The UI contract checker and design-system checks stay green.
- Browser groups must keep their counts, and the existing specs pin the screen composition.

**Effort:** M for the registry and the three existing views; L to include the controller extraction. **Timing:** before 3.6 or 4.13, whichever runs first. Otherwise Phases 3 and 4 add five more branches. **Covered:** no.

## 10. Remaining hosts on the access-loss seam

**Evidence**
- `ui/src/accessLoss.ts` (`useAccessLoss`) is used by 10 hosts.
- `docs/specs/ui-target.md` §7 lists these hosts as still using their own denial classification:
  - Evidence view, picker and library;
  - the assumption list;
  - the model editor and unit editor;
  - the study-shell lists, which are cleared on sign-out but not on confirmed access loss;
  - several configuration-editor reads.
- `EvidenceView.tsx` and `Workspace.tsx` classify denials locally.

**Problem:** two classifications of the same access-loss event exist, and a denied saved configuration shows its message twice. Phase 3 adds agent access-ended states on top of this.

**Change:** move the listed hosts to `useAccessLoss` and the shared `accessDenied`. Remove the local classification. Interface: the existing hook.

**Invariants:** no attested source. The browser groups covering access loss must keep their counts.

**Effort:** S–M. **Timing:** with 4.23, which edits the Evidence editor and View evidence, and before the Phase 5 independent security recheck. **Covered:** no.

## 11. Contract schemas split by consumer

**Evidence**
- `contracts/schemas/model.schema.json` (1,060,581 bytes) and `execution.schema.json` (1,060,585 bytes) differ only in `$id`.
- Each holds 538 `$defs`, 119 of them `Document*`, plus the `x-hyprn-mvp-documents-contract` registry.
- Both are inputs of the attested execution inventory (`integration/src/hyprn_mvp_integration/launcher.py:134-135`) and of the modeling image (`deployment/modeling_runtime.py:373,411`).
- They are kept identical by hand.
- Phase 4 tasks 4.32 and 4.34 edit both.

**Problem:**
- Every Documents-only definition change re-attests the worker and forces an image rebuild, a re-pin and a fixture recapture (`STATE.md`).
- Two hand-synced copies can drift.
- The worker trusts definitions it never uses.

**Change:** keep one authored source.
- Generate the execution schema as the transitive closure of the definitions that `contracts.validate_execution` and the worker admission name.
- Move Documents definitions and the registry to a non-attested `documents.schema.json`, loaded by `contracts.validator(name)`.
- A test asserts that the generated file equals the closure.
- Interface: `contracts.validator(name)`. Depth: callers never learn which file holds a definition.

**Invariants:**
- One deliberate re-attestation; the attested files list changes.
- The golden corpus is unchanged if canonical bytes of records are unchanged. Prepared artifacts record schema identities, so the change is a new artifact identity, which historical reads must keep accepting.
- Raise for review before acting.

**Effort:** L. **Timing:** inside the re-attesting window of 4.37, or with the 2.8 release snapshot; never on its own. **Covered:** no.

## 12. Version-family capabilities instead of version literals

**Evidence**
- About 117 literal schema-version comparisons across 14 modules: `worker.py` 38, `execution_bundle.py` 19, `results.py` 10, `approach_closure.py` 8, `configuration.py` 7, `computational_export.py` 7, `execution.py` 5, `modified_runs.py` 5, and others.
- `RETAINED_PAIRINGS` (`execution_bundle.py:63`) already centralizes the valid pairings.
- `stored_family(...).carries_dependencies` (`history.py:75`) and `uses_polish_envelope` (`execution_bundle.py:174`) show a capability pattern that is only partly adopted.
- Phase 4 OQ-1 (tasks 4.34–4.38) adds a document-bearing chain across the application, the modeling service and the worker.

**Problem:** each new record version is threaded through every `if version in (…)` site by hand. Missing one site is a silent acceptance or refusal bug on a historical read.

**Change:** extend the family object in `execution_bundle` so each entry declares capabilities (`carries_dependencies`, `typed_units`, `polish_envelope`, `approach_closure`, `document_citations`). Application modules ask for capabilities rather than versions.
- Interface: `family(record).has(capability)`.
- The worker keeps its own independent table on purpose (see "Not recommended").

**Invariants:**
- `execution_bundle` is attested, so this is a re-attestation.
- Historical reads must accept exactly the same records: a golden-corpus run before and after, and a property test that the capability table reproduces `RETAINED_PAIRINGS`.

**Effort:** L. **Timing:** with 4.35/4.37, which re-attest and add a chain anyway. **Covered:** no.

## 13. Outbox history projection made explicit and rebuildable

**Evidence**
- `execution.py:142-158` stores `payload['history']` (a projection of the AiiDA retained record, from `history.projection`, `history.py:65`) and `payload['status']` (`process_state`, `exit_status`) inside `outbox.payload`, next to the command intent and the base64 bundle files.
- History reads serve from it (`history.py:258,281`).
- No test asserts that a rebuild from AiiDA equals the stored projection.

**Problem:** ADR-0004 consequence 5 and its plan check require every projection to be rebuildable, non-authoritative and tested ("a rebuild equals the incremental state"). Today the projection is mixed into the command row, so its boundary is implicit.

**Change:**
- Name the projection: give `history.rebuild(run_id)` a read of the retained record.
- Add one test per retained family that the rebuild equals the stored projection.
- Optionally, separate the column from the command intent.

**Invariants:**
- No attested source.
- A column split would be a store migration; development data is discardable, but authoring records must be kept.

**Effort:** M. **Timing:** after the first release, or with 3.9 if the agent read tools rely on the projection. **Covered:** no.

## 14. Authorization by effect instead of boolean flags

**Evidence**
- `Store.authorize(db, actor, study, write=False, owner=False)` (`store.py:243`) has 49 callers across 10 modules (codegraph).
- Phase 3 task 3.1 keeps the signature ("Pattern 1") and maps `write=True` to "any of `draft`, `record`, `submit`". Route-level policy then lives in `agent_policy.route_allowed`, and the human-only classification arrives in 3.22.

**Problem:** call sites do not state which effect they need, so the effect check for agents lives in route strings, not at the owner. ADR-0003's draft/record/submit distinction can only be enforced at path granularity.

**Change:** `authorize(db, actor, study, effect=Effect.READ | DRAFT | RECORD | SUBMIT | OWNER)` at each call site. Route policy becomes a cross-check rather than the only check. Interface: one enum.

**Invariants:**
- No attested source.
- Touches 10 modules, including the human authorization matrix, so `api-a`, `api-c` and `combined-security` counts must be recorded before and after.

**Effort:** M. **Timing:** after the first release. 3.1 deliberately chose a stable signature to keep the agent tracer small. **Covered:** declined for now.

---

## Not recommended (checked and kept as is)

- **Worker re-verification duplicates application admission.** `integration/src/hyprn_mvp_integration/worker.py` has its own `ApproachClosure` (:347) and verification functions alongside `approach_closure.py` and `execution_bundle.py`. This is the trust boundary: §7 says "worker → results only (standard library otherwise)". Sharing code would widen the attested closure and remove independence.
- **A repository class per table in `store`.** §7 forbids it ("no repository-per-table, plugin framework or universal resolver"). Items 4 and 6 move reads to existing owners instead.
- **The two `computational_export.py` modules.** The application one owns requests and publication; the integration one owns AiiDA archive policy. They share no functions beyond `__init__` and `safe_path`, so there is no duplication.
- **Private cross-module access.** Only 3 allowlisted framework or same-module cases remain (`test_module_boundaries.py:550`). Nothing to factor.

## Notes for the phase gate

- `AGENTS.md` still names `deployment/phase02_checks.py`; the runner is `deployment/checks.py`. Task 1.10 step 4 covers this.
- `integration/src/hyprn_mvp_integration/native.py` and `documents.py` have no production caller yet (`ARCHITECTURE.md`); Phase 4 adopts `documents.py`.

---

*Factorization analysis: 2026-10-13*
