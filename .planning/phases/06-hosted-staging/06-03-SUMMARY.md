---
phase: 06-hosted-staging
plan: "03"
subsystem: auth
tags: [postgresql, cloudflare-access, sessions, browser]
status: complete
completed: 2026-10-20
duration: 21min
requires:
  - phase: 06-02
    provides: PostgreSQL Store and isolated roles
  - phase: 06-03A
    provides: Audited Access assertion verifier
provides:
  - Durable issuer/subject actors and secure hosted sessions
  - Assertion-bound external ingress with trusted inner delegated API
  - Hosted browser bootstrap, logout and private-cache clearing
  - Real HTTPS/PostgreSQL browser acceptance fixtures
affects: [06-05, 06-07]
tech-stack:
  added: []
  patterns: [narrow authentication SQL functions, trusted identity context]
key-files:
  created:
    - application/src/hyprn_mvp_app/external_identity.py
    - application/src/hyprn_mvp_app/migrations/0003_external_identity.sql
    - editions/cloud/src/hyprn_mvp_cloud/asgi.py
    - deployment/tests/hosted_ui_fixture.py
    - ui/tests/hosted-identity.spec.ts
  modified:
    - application/src/hyprn_mvp_app/routes/session.py
    - contracts/hyprn-mvp.openapi.yaml
    - ui/src/api.ts
    - ui/src/Workspace.tsx
key-decisions:
  - Identity is solely issuer/subject; bounded verified contact is display metadata.
  - Expose only assertion-bound ingress; embedded delegated clients retain the inner API object.
  - Reuse audited JWT dependencies in the application contract check environment.
requirements-addressed: [HS-02, HS-03, HS-08]
requirements-completed: []
actuals:
  tokens: 18299
  tasks: 1
  commits: 4
plan_head_before: ea64cb7a7f517c7447329140d92288cb183db982
plan_head_after: 1c5a4d25d66a4995d97aa591d58a1916aeddbe17
---

# Phase 06 Plan 03: Hosted identity and session integration

Verified Access assertions now open durable PostgreSQL-backed private browser
workspaces, with per-request cookie identity binding and private-state clearing.

The implementation task is complete. Hosted requirements remain open for live
deployment and human acceptance; this summary does not mark the phase complete.

## Delivery

- `28e4267`: tests-first missing-bootstrap boundary.
- `1c5a4d2`: cohesive identity/session/UI implementation and acceptance fixtures.

The measured four-commit range includes the parent's independent documentation
commits `5471feb` and `a5de6ef`. Actual tokens are ceil(diff characters / 4) for
owned changed files, not a runtime token count. Global planning state remains
parent-owned and was not edited or staged.

## Verification

Development checks passed: hosted identity 90, hosted UI 3, PostgreSQL 24,
contracts 127, access control 11, locality 165, public API 83 and local browser
navigation 25. Nine combined static checks passed, including a scoped clean UI
build. Exact commands, times, failures, hashes, scopes and cleanup are in
[06-03-CHECKPOINT.md](06-03-CHECKPOINT.md). Parent committed acceptance remains
pending against `1c5a4d2` for the six plan-required groups.

## Deviations from plan

- The approved implementation amendment removes external MCP/ChatGPT scope and
  supplies the corrected configured staging hostname. Embedded Assistant access
  stays available through trusted in-process composition.
- [Rule 2] Added mode discovery, canonical ingress errors and redirect-aware
  private-cache clearing because these are required for a safe browser journey.
- [Rule 3] Registered hosted integration checks in the application contract
  environment, reusing the existing audited JWT closure. The native environment
  lacks the HTTP application's dependencies.
- [Rule 3] Updated local browser fixtures for explicit mode discovery and waited
  for observable conversation readiness before the existing keyboard assertion.
  Assistant source remained unchanged.
- Initial RED was a missing interface failure; no machine RED classification was
  run. Strict TDD gate compliance is not claimed. This limitation was reported.

## Remaining work

No capability-blocking stub remains in this task. The lifecycle owner must apply
0003 and compose the configured ingress around the inner application. Deployment,
actual Cloudflare email/admission, provider execution, recovery rehearsal and
human browser acceptance remain later plan responsibilities. Synthetic assertions
and redirect fixtures cannot establish those live outcomes.

## Self-Check: PASSED

Owned artifacts exist; task commits are ancestors of delivery; explicit-path
staging left unrelated edits intact; no tracked deletions or secret artifacts
were introduced. Fixture containers and servers stopped; retained screenshot
scopes use the normal 24-hour runner expiry.
