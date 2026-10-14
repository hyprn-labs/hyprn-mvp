# Handover — orchestration of Phases 2–4

Read this file first, then `AGENTS.md`, `.planning/STATE.md` (decisions and "Session Continuity") and `.planning/ROADMAP.md`. Each phase plan and its checkpoints are under `.planning/phases/`.

## Demo target approved by the product owner (2026-10-14)

For the 2026-10-15 demo, prioritize completion of Phase 2 and Phase 3 through the
live full-workflow checkpoint 3.35 and status recording 3.36. Then freeze feature
work and rehearse on the exact demo machine and committed tree. Defer Phase 4
Documents and the broader Phase 5 release process until after the demo; the
first-release roadmap and its qualification requirements remain in force.

The target is a working local installation connected to the user's local Codex
and Claude Code clients: study folder, tool discovery, model authoring, explicit
configurations, real run submission, result inspection, and a saved conclusion,
with attribution and Agent activity visible in the UI. Rehearse the planned
pressure-loss example (110 kPa met and 121 kPa violated against a 120 kPa limit)
on each claimed client. Record live human evaluation separately from automation.

Keep all task dependencies, acceptance checks and decision gates, including
PD-2.4 and the client and write-control checkpoints. The date is a target, not
evidence of completion. If the full workflow is unfinished, 3.19 (read-only
client connection) and 3.30 (authoring) are fallback demo checkpoints, with their
scope stated explicitly; neither satisfies the full workflow target.

## Where the work is

- Work branch: `feat/local-edition-continued`, branched from `main`, with no upstream. The next pull request to `main` comes from it. Push or open a pull request only when the product owner asks.
- Ignore the remote branch `agent/codd/mvp-resume`; never merge it.
- Merged and verified on the work branch:
  - Phase 1: complete.
  - Phase 2: 2.1, 2.1a, 2.2, 2.3, 2.4, 2.5.
  - Phase 3: 3.1, 3.2, 3.2a, 3.3, 3.3a, 3.3b, 3.3c, 3.3d, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10.
  - Each task has a checkpoint.
- Combined-tree results are in STATE "Stopped at". Every listed group is green.

## In flight

| Task | State | Next step |
|---|---|---|
| 2.6 (WhatsOpt acquisition, source and modeling images, notices) | Independent implementation `5c58720` and incomplete checkpoint `5ec1de4` on `agent-modeling-image-build`. | No-cache runtime equivalence passed; 25 upstream tests pass. Final combined inventory, producer pin and fixture capture wait for verified 2.7; two strict inventory-count failures remain. 2.6 alone uses the fixed scratch folder groups. |
| 2.7 (engine, worker and application images) | In progress on `agent-runtime-image-build`, from `3d2d813`. | Owns `deployment/pins.json` until merged and verified; 2.6 then rebases before its final pin and fixture work. |

After 2.6 and 2.7: task 2.8a needs the product owner's decision PD-2.4 on the contract schema split. Its default is recorded in STATE. Then come 2.8b, 2.8c, 2.8, and 2.9–2.14. Task 2.11 covers the store schema version, refusal on mismatch and `setup --reset-data`, with no migrations.

Phase 3 after 3.7: 3.12 (`/mcp` server), then the plan's waves. Checkpoints 3.17, 3.18 and 3.28 need the product owner. Phase 4 follows `04-PLAN.md`.

## Decisions waiting for the product owner

- PD-2.4: contract schema split, before 2.8a.
- 3.28: read literally, the queue cap of 10 waiting or running runs makes the 20-runs-per-call cap unreachable. Should the queue rule count only the runs waiting before the call?
- Old unpinned durable-fixture folders in the development data root: keep or remove.

## Facts a new orchestrator needs

- Every check runs through `./hyprn-mvp dev check <group>` (see `AGENTS.md`, "Running checks"). The phase gate is `./hyprn-mvp dev check qualification --jobs 3` on a fixed commit. Hold heavy work (native groups, browser groups, image builds) while the gate runs.
- Per-task verification by the orchestrator, after merging:
  - review the commits: explicit paths, and the files match the task's list;
  - run `naming`, `hygiene`, `guard`, `units-guards` and `style-ratchet`;
  - run the task's fast contract and application groups, and the term scan;
  - spot-check one long native or browser group that is relevant to the task.
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
