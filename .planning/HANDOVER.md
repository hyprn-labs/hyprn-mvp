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

## Where the work is

- Work branch: `feat/local-edition-continued`, branched from `main`, with no upstream. The next pull request to `main` comes from it. Push or open a pull request only when the product owner asks.
- Ignore the remote branch `agent/codd/mvp-resume`; never merge it.
- Merged and verified on the work branch:
  - Phase 1: complete.
  - Phase 2: 2.1, 2.1a, 2.2, 2.3, 2.4, 2.5, 2.7.
  - Phase 3: 3.1, 3.2, 3.2a, 3.3, 3.3a, 3.3b, 3.3c, 3.3d, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10.
  - Each task has a checkpoint.
- Combined-tree results are in STATE "Stopped at". Every listed group is green.

## In flight

| Task | State | Next step |
|---|---|---|
| 2.6 (WhatsOpt acquisition, source and modeling images, notices) | Independent implementation `5c58720` and incomplete checkpoint `5ec1de4` on `agent-modeling-image-build`. | Rebase onto verified 2.7 (`77f47a9` plus its verification record), retain both runner changes, finish combined inventory, producer pin and fixture capture. No-cache runtime equivalence and 25 upstream tests passed before integration; final units-native, native-a and strict inventory checks remain. 2.6 alone owns pins and uses the fixed scratch folder groups. |
| 2.7 (engine, worker and application images) | Complete through `77f47a9`; checkpoint verified. | Eleven merged-tree groups pass, including attestation and image-built UI. Approved Flit transformations preserve runtime equivalence. Combined 2.6 sources require fresh native verification. |

After 2.6 is merged and verified: prepare the concrete PD-2.4 decision at 2.8a.
Then follow DELIVERY-PLAN.md waves: 2.8b → 2.8c → 3.16-paths → 2.8, keeping the
study-folder configuration change inside the same re-attestation window. Continue
with C's local lifecycle/credential/smoke prerequisites and MCP/write/UI slices.
The amendment owns the detailed ordering and every dependency replacement.

Product-owner gates remain at PD-2.4, 3.18, 3.28-evidence and 3.28-full; live
both-client checkpoints remain mandatory. The queue-limit ambiguity is decided
for D. Phase 4 is deferred until A–D and E are complete.

## Decisions waiting for the product owner

- PD-2.4: contract schema split, before 2.8a.
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
- `units-native` failed with `unsafe_export` once, when run from a worktree folder. It passes from the primary checkout.
- Section 5.4 of `docs/agents/tooling-spec.md` mentions a run-read cache that no tool has; fix it in 3.32.
- Agent runtime client names (`claude-code`, `codex-mcp-client`) are unconfirmed until the client-facts probe (3.17/3.19).
