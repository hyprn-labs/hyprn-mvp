---
phase: 06-hosted-staging
plan: 03B
subsystem: deployment
tags: [managed-agents, provisioning, reconciliation]
requires: []
provides:
  - Release-derived offline managed assistant plans and exact-hash apply
  - Durable creation reconciliation and exact provider binding readback
affects: [hosted-staging, platform-runtime]
tech-stack:
  added: []
  patterns: [content-addressed definitions, private durable creation intent]
key-files:
  created: [deployment/managed_assistant.py, deployment/tests/test_managed_assistant.py]
  modified: [deployment/checks.py, docs/agents/embedded-assistant.md]
key-decisions:
  - Reuse the existing audited Claude HTTP adapter; no new CLI or SDK dependency.
  - Changed definitions create distinct agents and never alter or delete existing resources.
  - Keep session history, shared allowance and scientific execution in their existing owners.
requirements-completed: []
actuals:
  tokens: 9393.5
  tasks: 1
  commits: 2
commits: 2
plan_head_before: b14df29fe2eff6f8dc05b3052f30abcbe9e401fd
plan_head_after: 1e0c10a67d6a394a88791d2494fef7aaff03dd4b
duration: 6min from RED commit to code completion; initial research excluded
completed: 2026-10-20
status: complete
---

# Phase 06 Plan 03B: Managed assistant setup Summary

Deterministic Claude agent/environment plans now derive 56 custom tools and scientific
guidance from the release registry/playbook, with exact-hash approval and durable safe
reconciliation through the existing HTTP adapter.

The offline plan records explicit Sonnet model settings, inline subagents, disabled
advisor/workflows/MCP/skills, and no network or added packages. Apply records intent before
creation, pins and rereads the returned agent version, verifies environment restrictions,
and exports the existing Settings binding names plus a platform configuration digest.
Uncertain absence blocks further creation. Repetition reuses verified resources; changed
definitions create a separate agent. No scientific execution or session/budget mutations
were added.

## Tasks and commits

- `6d492a2` — test-first offline command acceptance, plan and registered test group.
- `1e0c10a` — setup command, 16 tests and concrete review/apply/reconcile instructions.

## Verification

`./hyprn-mvp dev check hosted-assistant-setup`: 16 passed, 0 failed, 0 skipped, exit 0.
The last source change is represented by `1e0c10a`. The real offline module invocation also
created the review artifact without a key or provider call. Exact hashes, commands,
failures, scope cleanup and remaining obligations are in
[06-03B-CHECKPOINT.md](06-03B-CHECKPOINT.md).

## TDD Gate Compliance

RED: the target command test failed on its intentional `result == 0` assertion.
The registered unittest report passed the machine evidence classifier with
`RED_EVIDENCE_OK`; semantic inspection found no collection or fixture fault.
GREEN: all 16 isolated command/HTTP-adapter cases pass. No behavioral refactor was needed;
the pinned formatter was applied before final verification.

## Deviations from Plan

- The new test group uses the existing isolated unittest lane so the actual RED report is
  supported by the required evidence classifier. No runner framework was added.
- Official API documentation requires package-registry access when a package request is
  specified. Create therefore omits that request, and readback explicitly requires all
  package lists to be empty. No permission was weakened.
- Raw RED output contained local machine paths and was rejected by the existing commit
  hook. It remains external; portable evidence is recorded in the checkpoint.
- Global state/roadmap updates are handed to the orchestrator, which owns concurrent edits
  to those files. This independent task does not claim the hosted phase complete.

## Remaining qualification

Live provisioning, provider enforcement, account/model eligibility, hosted end-to-end
acceptance, final qualification and human review remain unverified. They were explicitly
outside this code-only task. The review artifact is ready for later approval; no provider
mutation, session creation, secret transfer or spend occurred.

## Self-Check: PASSED

Owned implementation/tests/docs and checkpoint exist. Both task commits are ancestors of
HEAD. The measured two-commit range excludes this later documentation record.
