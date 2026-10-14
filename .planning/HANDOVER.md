# Handover — orchestration of Phases 2–4

Read this file first, then `AGENTS.md`, `.planning/STATE.md` (decisions and "Session Continuity") and `.planning/ROADMAP.md`. Each phase plan and its checkpoints are under `.planning/phases/`.

## Delivery priority approved by the product owner (2026-10-14)

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
  - Phase 2: 2.1, 2.1a, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8a, 2.8b, 2.8c.
  - Phase 3: 3.1, 3.2, 3.2a, 3.3, 3.3a, 3.3b, 3.3c, 3.3d, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10.
  - The 3.16-paths slice is verified; full 3.16 remains partial.
  - Each task has a checkpoint.
- Combined-tree results are linked from STATE "Current Position". Every listed completed group is green; pending native groups are explicit.

## In flight

| Task | State | Next step |
|---|---|---|
| 2.8c (consumer schema split) | Integrated and verified through `fde9937`; all 30 required groups pass. | Pending current-image/native checks remain assigned to 2.8. |
| 3.16-paths | Integrated and verified in the same batch. | Study kit and the remainder of original 3.16 stay pending. |
| 2.8 (release snapshot and re-attestation) | Next, with the schema/path prerequisite verified. | Close the combined window with final committed snapshots, rebuild/pins/capture and all deferred current-image/native checks. |

Tasks 2.6 and 2.7 are merged and verified. PD-2.4 option a and its exact packet are approved; checkpoint 2.8a is complete.
Task 2.8b is merged at `577e30d` and verified: all seven integrated groups pass,
including locality-contracts 139; all seven scopes released. Follow DELIVERY-PLAN.md
waves: 2.8c → 3.16-paths → 2.8, keeping the
study-folder configuration change inside the same re-attestation window. Continue
with C's local lifecycle/credential/smoke prerequisites and MCP/write/UI slices.
The amendment owns the detailed ordering and every dependency replacement.
The after-split `public-api` run also waits for 2.8's current-source producer;
its 70-test baseline is recorded by 2.8c. This follows the existing stale-image
restriction and retains every public API assertion and identity check.

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
