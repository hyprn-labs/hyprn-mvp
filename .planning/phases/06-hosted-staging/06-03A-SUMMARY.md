---
phase: 06-hosted-staging
plan: 03A
status: complete
subsystem: cloud-identity-verification
tags: [cloudflare, jwt, cryptography, security]
requires: [ADR-0014, IMPLEMENTATION-AMENDMENT]
provides: [bounded-RS256-assertion-verifier, hosted-assertions-check]
affects: [06-03, 06-05]
tech-stack:
  added: [PyJWT-2.15.1]
  patterns: [immutable-external-identity, shared-key-refresh-budget]
key-files:
  created:
    - editions/cloud/src/hyprn_mvp_cloud/access.py
    - editions/cloud/src/hyprn_mvp_cloud/__init__.py
    - editions/cloud/pyproject.toml
    - editions/cloud/provenance.md
    - application/tests/test_hosted_assertions.py
  modified: [pyproject.toml, uv.lock, deployment/checks.py]
key-decisions:
  - Cloud edition returns verified issuer and subject only; application owns session authority.
  - One process shares a bounded key cache and refresh cooldown, including refresh failures.
  - Reuse audited native cryptography and httpx; defer hosted release closure to 06-05.
commits: 2
plan_head_before: aa53449d5ffa9c8e112ec6b8bbe6058f8ea9080b
plan_head_after: 06a43f6272826ff5a1776502897d8dc2f97d2068
completed: 2026-10-20
duration: not measured; exact check timings in checkpoint
requirements-completed: []
---

# Phase 6 Plan 03A: Cloud assertion verification Summary

RS256 Cloudflare assertions now produce immutable issuer/subject identities through
an audited PyJWT adapter with bounded key refresh and fail-closed expiry handling.

## Delivered

The isolated adapter and 71 signed-fixture tests cover signature and claim validation,
key rotation, malformed keys, expired caches during outages, concurrent calls,
unknown-key abuse, transport failures, redirects and size limits. A focused
`hosted-assertions` must-pass group runs through the local edition's locked native
environment. No hosted application entry point or session integration was added.

## Tests-first evidence

- RED `daf4875`: 44 passed, 10 failed, 0 skipped; the valid signed assertion executed
  and failed the planned non-null identity assertion against the fail-closed interface.
- GREEN `06a43f6`: 71 passed, 0 failed, 0 skipped on the exact committed source;
  0.33 seconds pytest, 0.594 seconds scoped child. No subsequent source delta.
- REFACTOR: formatting included before final GREEN verification; no extra commit needed.

Exact commands, every intermediate outcome, source/artifact identities and scratch
cleanup are in [06-03A-CHECKPOINT.md](06-03A-CHECKPOINT.md).
The orchestrator independently accepted the committed group with 71 passing tests;
a separate public-key read confirmed the configured issuer's JWKS schema matches
the strict adapter checks, without retaining key material.

## Deviations from Plan

None. The runner's first invocation refused the incompletely registered group;
dispatch registration was completed before test execution. Existing domain-port
edits and global planning state were preserved. The orchestrator owns their updates.

## Remaining obligations

Full 06-03 actor/session/API integration, trusted delegated API handling and the
two-user browser journey remain open. Final cloud release packaging/provenance
closure belongs to 06-05. These local cryptographic/transport tests establish no
live Cloudflare configuration, deployment or human acceptance. See the checkpoint
for the per-operation timeout versus wall-clock budget limitation.

No known stubs prevent this bounded adapter outcome. No new trust surface beyond
the planned fixed HTTPS signing-key source was introduced.

## Self-Check: PASSED

Adapter, tests, provenance and checkpoint exist. Both task commits are ancestors
of HEAD; all owned source paths are committed. Global state updates remain with
the orchestrator as explicitly delegated.
