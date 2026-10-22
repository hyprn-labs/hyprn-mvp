---
phase: 06-hosted-staging
plan: "02"
status: complete
subsystem: database
tags: [postgresql, row-security, scientific-records, assistant, background-authority]
requires:
  - phase: 06-01
    provides: Explicit PostgreSQL core, audited driver, migration discipline and request authority
provides:
  - Complete scientific, Assistant and journal PostgreSQL schema with forced row policies
  - Immutable saved records and accepted execution inputs
  - Separate purpose-limited Assistant and dispatcher discovery authority
  - Explicit schema upgrade and process composition interfaces
affects: [06-03, 06-05, 06-07]
tech-stack:
  added: []
  patterns: [checksummed explicit migrations, actor-scoped background work, forced row policies]
key-files:
  created:
    - application/src/hyprn_mvp_app/migrations/0002_domains.sql
    - application/tests/test_hosted_domains.py
  modified:
    - application/src/hyprn_mvp_app/database.py
    - application/src/hyprn_mvp_app/store.py
    - application/src/hyprn_mvp_app/migrations.py
    - application/src/hyprn_mvp_app/assistant/conversation.py
    - application/src/hyprn_mvp_app/execution.py
    - deployment/tests/hosted_fixture.py
key-decisions:
  - "Background discovery uses separate EXECUTE-only Assistant and dispatcher credentials, then ordinary request-role actor transactions."
  - "Hosted startup verifies the complete schema; only an explicit migration job applies a recognized checksummed prefix."
  - "Authentication bootstrap stays separate for 06-03; no general authentication writes are granted."
  - "Application artifact storage is an explicit composition parameter; production paths and entrypoints remain 06-05-owned."
  - "Delegated study creation preserves human ownership without granting the creating agent new study access."
duration: 30min
completed: 2026-10-20
actuals:
  tokens: 31961
  tasks: 1
  commits: 8
plan_head_before: aefa20d523d2a38f3a4801f69b0adb2bfc2be847
plan_head_after: 4c40f0862c114c84382d3494316de5a7573c0e6b
---

# Phase 06 Plan 02: Complete PostgreSQL domains

Scientific records, Assistant recovery and agent journals now use the complete
PostgreSQL schema with current membership/delegation policies and immutable saved
history. Separate background logins discover only work identities or provider
account metadata; domain work still runs under ordinary actor-scoped row policies.

This completes the local implementation task. Orchestrator acceptance on the
committed batch, hosted deployment, Cloud SQL qualification, target execution
attestation and human acceptance remain distinct obligations.

## Task commits

| Task | Commit | Result |
|---|---|---|
| Require complete hosted scientific composition | `aa53449` | Behavioral RED: 2 expected failures, 10 passed |
| Preserve private scientific domains and background authority | `4c40f08` | Complete schema, owner adaptations and focused/regression verification |

The measured ledger interval contains eight commits: these two owned commits and
six concurrent orchestrator/06-03 commits. No concurrent task's paths were staged.
The token actual is `ceil(127841/4)` over the two owned commit diffs, not a model
usage figure. This summary/checkpoint commit is additional documentation.

## Verification

- Hosted PostgreSQL: **24 passed**, 0 failed, 38.51 seconds.
- Access control: **11 passed**; public API: **83 passed**; agent tools: **321 passed**.
- Contracts: **127 passed**; locality contracts: **165 passed**.
- Combined static: **9 checks passed**, including public UI contract/type/build checks.
- `git diff --check` passed; no tracked files deleted; no fixture PostgreSQL containers remain.

All invocations used the pinned local edition check entrypoint. Full commands,
warnings, every failed intermediate run, source/checksum identities and scratch
cleanup are in [06-02-CHECKPOINT.md](06-02-CHECKPOINT.md). Required committed-tree
acceptance belongs to the orchestrator; no additional qualification claim is made.

## TDD gate compliance

The full-composition/table-inventory tests were committed before implementation;
the expected failures and original output are recorded in [06-02-RED.md](06-02-RED.md).
Additional behavior tests cover concurrent duplicate/revision commands, complete
raw-role table visibility, immutable bytes, background purpose restrictions,
Assistant recovery through the delegated API, persisted prediction processing,
atomic migration rollback and delegated creation. Intermediate fixture errors were
diagnosed and retained in the checkpoint; they are not counted as behavioral RED.
The final denial test uses a unique actor to exclude another test's live grant.

## Deviations from plan

1. **Approved scope clarification:** Embedded Assistant persistence and recovery
   replace the retired external MCP consumer, following the implementation amendment
   and ADR0014. No cloud resources or production entrypoints were changed.
2. **Rule 2 — authority boundary:** Added two purpose-limited background logins and
   explicit artifact-root configuration because global unscoped discovery would
   defeat request row policies. Parent approved both roles and secret aliases.
3. **Rule 2 — preserved domain semantics:** Added scoped creation-transaction
   attribution for supported delegated study creation, keeping ownership with the
   human and denying ongoing agent access. Tightened raw creation to live
   writer/record delegation authority.
4. **Rule 1 — portability:** Explicit SQL parameter/numeric casts, conflict syntax,
   stable ordering columns and driver error normalization preserve existing local
   semantics without global SQL rewriting. Exact dependency allowlists were updated
   only for the database error boundary; the import graph remains acyclic.
5. **Orchestrator ownership:** Global STATE, ROADMAP and requirement status were
   intentionally not edited. The parent owns advancement after integrated acceptance.

## Security boundary and handoff

The new SQL helper functions are a trust boundary. All security-definer functions
pin `pg_catalog,public`, qualify accessed objects and revoke PUBLIC EXECUTE.
Runtime roles cannot own schema, inherit elevated authority or directly read through
the background credential. Migration authority never enters the application.

`Store.postgres` and exact SQL signatures, credential consumers, background
categories and 06-03/06-05 obligations are documented in the checkpoint. The native
execution consumer remains unchanged and receives no application/provider secret.

## Remaining obligations

- Orchestrator: committed-tree acceptance for this task.
- 06-03: narrow identity/session bootstrap and verified assertion integration.
- 06-05: process-specific credential/path assembly and hosted entrypoints.
- 06-07: actual Cloud SQL/TLS, containment/attestation, full qualification and human acceptance.

No implementation stub prevents the local task's stated goal. Controlled provider
and numerical adapters in focused tests do not establish live provider or hosted
execution behavior.

## Self-check: PASSED

Both task commits exist in current ancestry. The complete SQL migration, hosted
domain tests, checkpoint and summary exist. The final tested source is `4c40f08`;
later task-owned changes are this summary, checkpoint and normalized plan references.
