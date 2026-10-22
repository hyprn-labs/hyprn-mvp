---
phase: 03-agent-tools-for-coding-agents
plan: "01-collection-loading"
status: partial
subsystem: ui-design-system
tags: [collections, pagination, design-system, recovery]
requires: [contour-design-system, public-api-pagination]
provides: [typed-collection-status, shared-paged-read-lifecycle]
affects: [experiments, evidence, home]
tech-stack:
  added: []
  patterns: [typed-coverage-projection, scoped-cursor-retry]
key-files:
  created:
    - design-system/components/Collections.md
    - ui/src/design/collections.tsx
    - ui/src/useCollectionRead.ts
  modified:
    - ui/src/RunPanel.tsx
    - ui/src/CalculationsPanel.tsx
    - ui/src/EvidencePanel.tsx
    - ui/tests/study-navigation.spec.ts
    - ui/tests/evidence-workspace.spec.ts
key-decisions:
  - Cursor exhaustion alone establishes complete collection coverage.
  - Keep application read lifecycle outside the design-system rendering layer.
  - Preserve inherited qualification failures instead of weakening gates.
completed: 2026-10-19
duration: "Per-group timings retained in checkpoint evidence"
actuals:
  tokens: 81267
  tasks: 1
  commits: 1
plan_head_before: 61833800fff2062addd1af32c83fa270667a9833
plan_head_after: fe54a75140808765e391fe2d7eef1b933954de33
---

# Phase 3 Plan 1: Collection loading summary

Typed collection coverage and recovery now govern all current paged readers,
including previously omitted analysis-version and estimate pages.

Implementation commit: `fe54a75`. See [checkpoint](checkpoints/3.L1.md) for complete
commands, counts, identities, failures, ownership, evidence and cleanup.

## Outcome

Initial loading/failure cannot claim zero records. Partial counts say “shown · More
available”; exhaustive counts omit transport wording. Filters state their received
scope. Failed page retries retain prior rows and use the exact cursor. Refresh,
scope changes and access loss preserve the correct authority and recovery intent.

Configuration versions, analyses, analysis runs/versions/estimates, run history,
evidence/result pickers and history readers use CollectionStatus and the shared
application hook. Home projects exhaustive API-list results. CSS ownership,
source-contract and rendered smoke checks enforce the shared boundary.

## Verification and deferred issues

Static 9/9 and navigation 21/21 passed. Reading 26/37 passed, including all four
new feature journeys; 11 failures remain from 12 reproduced on unchanged base.
Style 32/33 passed with 1024 final diagnostics, versus 1128 on unchanged base. Foundry
8/12 passed; the full 200% journey is blocked by an old navigation expectation.
No tests were skipped. Required groups remain honestly failing where noted.

Parent replay finished: static 9/9, navigation 21/21, reading 26/37, Foundry 8/12
and style 32/33 (1024 diagnostics). All new reading journeys passed; all 11 reading
failures match the unchanged base. Foundry failures remain unresolved without a
base comparison. Human acceptance, full qualification and integration remain open.
This summary is partial, not a full qualification or phase-completion claim.
The checkpoint records the dedicated assumption replacement and delayed mutation
scope-test gaps. No production stubs or new security endpoints were introduced.

## Deviations from plan

- Parent-approved application helper and three ownership/checker files keep the
  lifecycle cohesive without a generic framework.
- Removed task TDD attribute under explicit amendment; retained actual RED evidence.
- Same-HEAD agent branch satisfies executor commit guard.
- Reconciled owned navigation fixtures with current brief/evidence UX; unrelated
  historical reading/zoom failures remain deferred.
- Formatting is limited to owned paths. No new dependency, API change, deployment,
  main checkout edit or main-agent interruption occurred.
- Global planning state remains untouched under the scoped workflow amendment.

## Self-Check: PASSED

All created product files and checkpoint exist; fe54a75 is an ancestor of HEAD.
All source changes are committed. Acceptance limitations are explicit.
