---
phase: 03-agent-tools-for-coding-agents
plan: navigation-affordances
status: complete
subsystem: ui-design
tags: [navigation, accessibility, design-system]
requires: [shared-record-navigation, shared-dialogs]
provides: [typed-open-link, consistent-reader-arrows]
affects: [content-navigation, record-readers]
tech-stack:
  added: []
  patterns: [typed-reader-controls, passive-status-with-separate-navigation]
key-files:
  created: [ui/src/design/navigation.tsx, ui/src/design/icons.tsx]
  modified: [design-system/Coherence.md, ui/src/design/primitives.tsx, ui/src/design/records.tsx, ui/tests/study-navigation.spec.ts]
key-decisions:
  - Named opening links use one underlined label-and-arrow target.
  - Passive facts keep a separate arrow-only target.
  - Commands, sidebar navigation and tabs preserve their distinct semantics.
completed: 2026-10-20
plan_head_before: 222a02163b3cb7ff6b0aa68f7850c0602012d66b
plan_head_after: 3af1780befe7957f1f74fbb431fc58db7c055ebe
commits: 2
---

# Navigation affordances summary

Typed reader links now provide one shared visible arrow across record details,
sources, content references, collections and returns, while statuses remain passive.

Task 1 implementation: `447f1c5`. The measured ledger interval includes the concurrent
main-agent commit `3af1780`; only the former belongs to this task.

See [CHECKPOINT.md](CHECKPOINT.md) for exact scope, checks, failures, retained evidence,
cleanup, ownership and integration obligations. Final static passed 9/9 stages.
Navigation browser checks passed 21/22, with the one Assistant assertion owned and
subsequently updated by the main agent. No live deployment or human acceptance claim.

## Deviations

Existing source-structure tests and explicit module-loader bindings were updated for
the new shared module. Two stale browser assertions were reconciled on orchestrator
instruction; the unrelated Assistant assertion was preserved for its owner.

## Self-Check: PASSED

Implementation commit and new modules exist; no unrelated hunks or file deletions
were included. Parent owns integrated acceptance and the shared state update.
