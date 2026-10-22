---
phase: 03-agent-tools-for-coding-agents
plan: continuous-answers
status: complete
subsystem: application
tags: [scientific-answers, immutable-history, public-api]
requires: [saved-approach-versions, study-authorization, command-receipts]
provides: [persistent-case-answers, persistent-study-synthesis, exact-answer-history]
affects: [continuous-approach-ui, scientific-authoring-guidance]
tech-stack:
  added: []
  patterns: [owner-transaction, immutable-versions, expected-revision, command-replay]
key-files:
  created:
    - application/src/hyprn_mvp_app/answers.py
    - application/src/hyprn_mvp_app/routes/answers.py
    - application/tests/test_answers_api.py
  modified:
    - application/src/hyprn_mvp_app/api.py
    - application/generate_contract.py
    - contracts/hyprn-mvp.openapi.yaml
    - ui/src/api.ts
    - ui/src/contract.ts
key-decisions:
  - Answer schemas and storage remain application-owned and outside execution inputs.
  - Exact approach/case targets have immutable versions and explicit current heads.
  - Qualified synthesis may cite incomplete or failed work without implicit conclusions.
duration: 15 min
completed: 2026-10-14
actuals:
  tokens: 20399
  tasks: 1
  commits: 2
plan_head_before: e0ed5bae8b4e68132509aad37674a42ae196208f
plan_head_after: b7d94f2e051157c89a7950227dd97d466c1f86ff
---

# Phase 3: Persistent scientific answers summary

Application-owned case answers and study synthesis now preserve exact approach, case,
configuration, run, evidence and case-answer references through immutable versions and
ordinary public API authorization.

Implementation: `47e0322`. Failed retained-run regression: `b7d94f2`.
The [executor checkpoint](checkpoints/continuous-answers.md) records the complete contract,
commands, counts, failures, artifact identities, cleanup and remaining integration work.

Final automated evidence: answers API 25, module/identity contracts 155, domain contracts
127, runner guards 116 and style 33 passed; combined-static passed all six commands.
No skipped tests. No new dependencies, live-study edits, execution-source changes or
delegated writer enablement.

## Deviations from plan

The first reference implementation directly read run associations; the boundary test
correctly rejected it. The final implementation reads through the existing History owner
inside the same transaction. Other corrections were a test-fixture field mismatch and
line wrapping. The checkpoint records all failures.

## Scope and remaining obligations

This completes the authorized persistence slice, not Phase 3. UI integration, isolated
served rehearsal and human acceptance remain with the orchestrator. Shared STATE, ROADMAP
and handover records remain under the orchestrator's exclusive ownership.

## Self-Check: PASSED

Owner/routes/tests/generated artifacts exist; both task commits are reachable; no blocking
stub remains. All 13 task scratch stores were released, retaining external evidence.
