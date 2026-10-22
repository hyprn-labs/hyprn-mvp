# Handover

Read this section first, then `AGENTS.md`, `CONTEXT.md`, ADR-0007 to ADR-0010 in `docs/adr/`, and `.planning/phases/03-agent-tools-for-coding-agents/consistency/` (`DECISIONS.md` for the owner's decisions and batch sequence, `CHECKPOINT.md` for verified evidence). Machine-specific notes (development environment, demonstration server, helper scripts) are kept outside the repository, in the `handover/` folder of the development data root (`HYPRN_MVP_DATA_ROOT`).

## Current state (2026-10-18)

Branch `feat/local-edition-continued`. The product is moving from the modeling approach to a decision-framing domain (ADR-0007 to ADR-0010): a study owns a versioned brief (question, alternatives, criteria in priority order, assumptions, limits, open questions); calculations are versioned sets of configuration versions for one model version with criterion bindings; one study answer records the comparison and recommendation. Development studies may be discarded when the new domain lands (owner authorization); the product still never deletes studies.

Batch sequence (DECISIONS.md): B1, B2, B3 and M1 are done; **M2 (calculations) is in progress: slices 1 (backend) and 2 (Calculations area, with reference marks) are done; slice 3 (remove criteria from configurations) is next**, then M3 (study answer), M4 (model explanations), M5 (remove the approach, reset the development store, re-create the fuel demonstration).

### M1, study brief: done and committed

`cd98f77` record and public API, `897f647` objective order as first ranking rule, `efc8ccb` formatting, `061c78e` agent tools (`get_study_brief`, `list_study_brief_versions`, `update_study_brief`, `save_study_brief_version`), `a84a627` Overview reader and editor, `81dc10b` checkpoint. Evidence is in the consistency `CHECKPOINT.md` ("Study brief (M1)").

### Page width through the design system: done and committed

`ba1ccb8`: `ContentColumn` owns page width (reading, form, login, full) and section spacing; screen CSS no longer sets widths and the component ownership check enforces it. The 200% zoom overflow on Home came from screen rules that set an inline `auto` margin on a column child (a flex child with auto inline margins shrinks to its content width); screen rules on column children now set block margins only. Nine UI groups green on that tree (see the consistency `CHECKPOINT.md`).

### M2 plan (slices 1 and 2 done; slices 3 to 5 next)

Slices, each ending green and committed:

1. **Calculation record and reference mark (backend): done**, see the consistency `CHECKPOINT.md` ("Calculations (M2, slice 1)") and the owner's evaluation decisions in `DECISIONS.md`. Design as built:
   - **Calculation versions.** Immutable records with number and predecessor. Each holds `name`, `description`, `model_id`, `model_revision_id` and `configuration_revision_ids` (at least one, all for that model version). The design is `hand_picked` for now; `sampled` comes in slice 4.
   - **Criterion bindings** pin one saved brief version: items are `criterion_id` plus the output `PortRef` of the model version.
   - **Unit rule.** A binding is refused unless the output's declared unit equals the criterion's unit text exactly (dimensionless is the empty unit). Conversion stays with the native worker; it is never implicit.
   - **Run listing** is derived from the member configurations; runs are never rewritten.
   - **Evaluation per run.** Constraints read met, not met or unresolved with a reason. Unbound criteria are unresolved ("criterion not bound"). Objectives report the measured value with its unit, or unresolved. Comparison follows `integration/src/hyprn_mvp_integration/results.py` (tolerance only for `eq`).
   - **As built, beyond the proposal:** evaluation words `met`, `not_met`, `measured`, `unresolved` with a reason; the application's own comparison is pinned to the worker's by a parity test; runs are evaluated only from integrity-checked retained records, 20 per page (`?limit`, `?after`); a calculation keeps its model across versions; bindings need `brief_version_id`, which is null only with no bindings; `GET /studies/{sid}/calculations/{calculation_id}` reads one calculation with its latest version. Receipt categories `calculation_create`, `calculation_version`, `reference_mark`.
   - **Reference marks** are a mutable mark per configuration version, set and cleared by POST commands. Never a DELETE route: every DELETE is human-only under ADR-0003.
   - **Routes:**
     - `GET`/`POST /studies/{sid}/calculations`
     - `POST /studies/{sid}/calculations/{calculation_id}/versions` with `expected_version_id`
     - `GET /studies/{sid}/calculations/{calculation_id}/versions`
     - `GET /studies/{sid}/calculation-versions/{id}` and `GET .../runs`
     - `GET`/`POST /studies/{sid}/reference-marks`
   - **Pattern to follow:** `application/src/hyprn_mvp_app/brief.py`, `routes/brief.py` and `application/tests/test_brief_api.py` (module-local JSON Schema definitions, command receipts, compare-and-swap, immutability triggers, contract generation and a must-pass group).
2. **Done** (`ef048a8`, see the consistency `CHECKPOINT.md`). **Calculations area UI** (lists calculations first; each calculation shows its configurations, runs, bindings and outcomes), with browser tests. Follow the `brief-ui` pattern: the group is registered with `APPROACH_BROWSER_SPECS` in `deployment/checks.py`, and the real-application fixture `deployment/tests/approach_ui_fixture.py` needs new write routes in its allowlist.
3. Remove criteria from configurations (contract, execution evaluation, UI, exploration).
4. Move sampling designs and estimates onto calculation versions.
5. Calculation agent tools, after the agent-writes work below lands, since both edit the agent tool catalogue.

### Work elsewhere

- **Agent writes**: a separate session, in its own worktree and branch, is opening every non-human-only API write to agent tools, with attribution. Owner decision: ADR-0003 human-only operations (deleting saved records, archive and restore, access management, backup and import) stay human-only; no new ADR. Its branch must be merged by the owner's decision; check its state before M2 slice 5.
- **Agent attribution browser group**: `agent-ui` has 11 of 25 tests failing since the B3 page-header batch. The tests look up chips under retired header classes (`.study-heading`, `.model-header .model-context`). A fix was proposed as its own task, not started.

### Open owner questions

- Remove the study title from Model and Run pages, given that the sidebar names the study?
- Graph port labels: code symbols or quantity names?
- Move the Assistant launcher into the navigation rail?
- Until M5, Overview shows the approach's "About this study" question beside the brief.

### Working rules and lessons from this batch

**Commits and checks**

- Run checks only through `./hyprn-mvp dev check <group>`.
- Stage explicit paths only. Commits in this repository carry no Co-Authored-By trailer.
- Never name a machine, account, e-mail address or another company in the repository.
- Never edit an accepted ADR; supersede it with a new one.
- The style ratchet (`style-ratchet`) already fails on many files changed since its base. New files must still be formatted (ruff for Python, prettier for TypeScript).

**Accessible names in forms**

- A textarea inside its label adds its text to the label's name, and a select adds its chosen option. Give each one an explicit `aria-label`.

**Unsaved-changes guards**

- A guard's `save` must report success when there is nothing to save, including an editor that was never opened. Otherwise the save sequence stops before later editors.
- A read in flight is not unsaved work; only a write in flight is.

**In-browser API doubles**

- `ui/tests/foundry-fixtures.ts` and `ui/tests/study-navigation.spec.ts` record unknown requests. Every new GET a page makes needs a declared answer there.

---

## History (superseded)

### Orchestration of Phases 2–4

Read this file first, then `AGENTS.md`, `.planning/STATE.md` (decisions and "Session Continuity") and `.planning/ROADMAP.md`. Each phase plan and its checkpoints are under `.planning/phases/`.

## Current priority: working fuel demo

The latest instruction at the top of [DELIVERY-PLAN.md](DELIVERY-PLAN.md) supersedes
the A–D demo queue below. Run the existing refactored application and real services;
use normal authorized local user authentication with a thin public API client. Codex
must create a study and author, run, inspect and revise the fuel workflow in the same
session, then answer from retained results visible in the UI. No prebuilt model or
seeded result counts. Stop adding features after one successful end-to-end rehearsal.

The in-flight local CLI/adapters and MCP/notes batches are stopping at recoverable
worktree checkpoints. Preserve their code and evidence; do not merge or finish them
merely because they started. All open numbered tasks are deferred completion
obligations. Existing authentication, scientific validation, restricted execution,
attestation, immutable records and receipt recovery remain. Focused changed-behavior
checks and required API/UI contract checks apply; full qualification, delegated-agent
reviews, other clients/hosts, installation productization and release audits are later.

The follow-up is delivered: cleaned Study/Model/Run presentation, continuous
approach reader, persistent case/study answer API and runtime scientific guidance.
The focused reader test passes 17/17; answer/API/static groups pass. The refreshed
demo has eight current successful cases (all 11 outputs each), eight case answers
and a study synthesis, authored through the public API and inspected in the real UI.
Every selected mass is below 575 tonnes and expense uses 100 occupied seats. The
original engineering question remains intact; aircraft optimization, complete-mission
feasibility and ticket price are explicitly unresolved. The latest UI refinement makes Overview the saved approach, with section boxes and visible case filtering; model details share the method explanation and edit its draft. Port-metadata paste is removed. See [overview-refinement.md](phases/03-agent-tools-for-coding-agents/checkpoints/overview-refinement.md). Stop adding features and await product feedback. Exact current identities are in the integration checkpoint.

The latest cleanup (`e5e98cd`) reads question → study answer → methods, with cases
in their own tab replacing Evidence. Evidence stays beside assertions; Edit study is
one editor; model quantities/actions, configurations and run tabs are simplified.
Focused browser 19, style 33, agent-tools 270 and static/build checks pass. See
[interface-cleanup.md](phases/03-agent-tools-for-coding-agents/checkpoints/interface-cleanup.md).
The refreshed runtime guidance requires citations to support the actual input value
and scenario. Existing scientific records were not re-authored in this UI batch.

Latest user instruction: old studies and runs are disposable. Historical preservation,
backups and broad compatibility verification are not prerequisites for this demo.
The prior queued computational export completed after export processing was enabled.
The current calculation → saved answer → visible UI journey is verified; defer
full qualification and nonessential work. See STATE and the continuous integration
checkpoint for current evidence. The standalone scientific skill is repository-owned;
its core guidance is now loaded by the runtime and nine independent scenarios passed.

## Earlier delivery priority — superseded for the current demo (2026-10-14)

Read [DELIVERY-PLAN.md](DELIVERY-PLAN.md) before dispatching pending Phase 2/3
work. It supersedes the earlier whole-Phase-2-plus-Phase-3 demo target with
value buckets A–D first: clear application ownership, a consistent public API,
a narrow visible agent write, then the complete engineering workflow.

C is an earlier useful stop: both Codex and Claude Code save an evidence note
in an existing study; the UI shows the persisted version, attribution and Agent
activity, including access revocation. Refresh/navigation is the freshness promise.
D adds model authoring, configurations, real runs, results and a saved conclusion;
then freeze features and rehearse the pressure-loss example on the exact committed
tree. The October 15 demo is a target, never a waiver of verification.

E retains the broader installation, adapter/probe, clean-room and documentation
proofs. F retains Documents and the qualified release. All original task IDs,
completed checkpoints, invariants, current-host safety checks and human decision
gates remain. Named slices close separately; original tasks close only when all
original acceptance is satisfied. Do not repeat the full live scenario suite per
OS: its original matrix is scenario by client; platform connection probes are E.

The approved execution-cadence amendment in DELIVERY-PLAN.md permits 2–4 related tasks per
fresh executor, focused development checks and one union of required acceptance groups after
integration on the exact committed tree. Keep separate commits and task/evidence mapping;
never batch across a human decision, capability review or stale-attestation boundary.
Documentation-only status/checkpoint changes do not repeat application checks when behavioral
inputs are unchanged. Relevant changes or failures require affected reruns. All final gates,
required no-cache builds, exact artifact checks and both-client live evidence remain mandatory.

The approved parallel scheduling amendment in DELIVERY-PLAN.md uses two implementation lanes
after the exclusive schema/study-path/re-attestation window. It removes runner-only ordering
between local installation and MCP work with one shared-wiring integrator, and allows 3.23
after verified 3.22 while 3.24-evidence finishes. Genuine interface/store dependencies,
2.11's overlapping test migration, native-resource serialization and human gates remain.

## Where the work is

- Work branch: `feat/local-edition-continued`, branched from `main`, with no upstream. The next pull request to `main` comes from it. Push or open a pull request only when the product owner asks.
- Ignore the remote branch `agent/codd/mvp-resume`; never merge it.
- Merged and verified on the work branch:
  - Phase 1: complete.
  - Phase 2: 2.1, 2.1a, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8a, 2.8b, 2.8c, 2.8.
  - Phase 3: 3.1, 3.2, 3.2a, 3.3, 3.3a, 3.3b, 3.3c, 3.3d, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10.
  - The 3.16-paths slice is verified; full 3.16 remains partial.
  - Each task has a checkpoint.
- Combined-tree results are linked from STATE "Current Position". Every listed completed group is green; pending native groups are explicit.

## Deferred batches from the earlier queue

| Task | State | Next step |
|---|---|---|
| 2.9 + 2.10-host | Ready from verified 2.8. | CLI/prerequisite/status journey and all adapter implementations, with current-host proof. Other-host proofs remain E. |
| 3.11 + 3.12 | Ready from verified foundations and the closed attestation window. | Runtime-owned notes/reports and the composed MCP surface; preserve the read-only capability gate. |
| 3.16-paths | Integrated and verified. | Study kit and the remainder of original 3.16 stay pending. |

Task 2.8 is integrated through `d4467eb` and verified. Its initial 23-group union,
affected docstring checks, full native journey and durable-reader checks all pass.
Every native/current-image check deferred by 2.8c is complete, including public-api 70
and the added historical-export case. The final runtime keeps all 49 reviewed paths
and one unreplaced attestation. The new durable fixture is `native-20261014T143925Z`;
all preceding fixtures and the exact pre-split capture remain preserved. See checkpoint
2.8 for source/artifact identities, test counts, exact later deltas and cleanup.

Continue in two fresh worktree contexts from the verified integration commit. The
orchestrator owns runner/guard registration for both lanes. Keep 2.11's overlapping
store/test migration serialized and reserve native resources explicitly. The delivery
amendment owns the detailed ordering and every dependency replacement.

The next human checkpoint is the 3.17-host live probe on both clients, followed by
the 3.18 decision. Product-owner gates at 3.28-evidence and 3.28-full and later
both-client checkpoints remain mandatory. The queue-limit ambiguity is decided
for D. Phase 4 is deferred until A–D and E are complete.

## Decisions waiting for the product owner

- 3.28: read literally, the queue cap of 10 waiting or running runs makes the 20-runs-per-call cap unreachable. Should the queue rule count only the runs waiting before the call?
- Old unpinned durable-fixture folders in the development data root: keep or remove.

## Facts a new orchestrator needs

- Every check runs through `./hyprn-mvp dev check <group>` (see `AGENTS.md`, "Running checks"). The phase gate is `./hyprn-mvp dev check qualification --jobs 3` on a fixed commit. Hold heavy work (native groups, browser groups, image builds) while the gate runs.
- Per-batch verification by the orchestrator, after merging (one union of all required groups):
  - review the commits: explicit paths, and the files match the task's list;
  - run `naming`, `hygiene`, `guard`, `units-guards` and `style-ratchet`;
  - run the task's fast contract and application groups, and the term scan;
  - preserve all task-specific native/browser acceptance and special assertions.
- Modeling images are not reproducible. Any change to a modeling source needs:
  - a rebuild;
  - a new `modeling_producer` pin in `deployment/pins.json`;
  - a recapture of `integration/tests/fixtures/native-programs.json.gz`.
  The durable native fixture is pinned in `deployment/tests/durable_fixture.py`; recapture it with its `capture` command. The durable-fixture groups and `units-native` need `HYPRN_MVP_SCRATCH_ROOT` set to the scratch folder inside the data root. Only one task at a time may use that folder.
- `./hyprn-mvp` runs with umask 077. Build contexts need explicit file modes.
- `style-ratchet` (ruff 0.16.10, prettier 3.9.10, line-level baseline `deployment/style_baseline.json`) fails on long lines in any file a task touches.
- `native-environment` downloads its packages, so it needs network.
- Build backend: flit_core 4.1.0, pinned in `deployment/locks/build-backend.json`.
- Executors run one task, or a batch of 2–4, each in its own worktree. They never edit `STATE.md` or `ROADMAP.md`; the orchestrator records each merge there.
- Development variables are listed in `AGENTS.md`. Their values are specific to the development host, are confirmed with the product owner, and never go into the repository.

## Small open items

- Regenerate `ui/dependency-audit.json` for the prettier addition.
- An earlier worktree `units-native` run reported `unsafe_export`; final task 2.6 acceptance passed from both its worktree and the primary checkout.
- Section 5.4 of `docs/agents/tooling-spec.md` mentions a run-read cache that no tool has; fix it in 3.32.
- Agent runtime client names (`claude-code`, `codex-mcp-client`) are unconfirmed until the client-facts probe (3.17/3.19).
