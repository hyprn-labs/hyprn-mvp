---
phase: 06-hosted-staging
plan: "05"
status: incomplete
subsystem: hosted-runtime
tags: [postgresql, lifecycle, admission, assistant, release]
requires:
  - phase: "06-03"
    provides: Hosted identity and private browser workspace
  - phase: platform-contract-v1
    provides: Reviewed descriptor, runtime renderer and lifecycle invocation
provides:
  - Cloud application composition and explicit database lifecycle prerequisite
  - Host-owned admission and Assistant startup continuity checks
  - Pinned artifact validation and explicit incomplete publication gate
affects: [06-05-native, platform-host]
tech-stack:
  added: []
  patterns: [immutable-store-identity, explicit-migrations, separate-host-controls]
key-files:
  created:
    - application/src/hyprn_mvp_app/hosted_lifecycle.py
    - application/src/hyprn_mvp_app/hosted_runtime.py
    - deployment/cloud_lifecycle.py
    - deployment/cloud_release.py
    - deployment/tests/test_hosted_artifact.py
  modified:
    - editions/cloud/src/hyprn_mvp_cloud/asgi.py
    - deployment/application.Dockerfile
    - deployment/checks.py
key-decisions:
  - Consume the separately supplied pinned platform renderer without vendoring it.
  - Keep aggregate activation closed until native owner evidence is real.
  - Require reviewed prior-use continuity without inferring zero.
requirements-completed: []
actuals:
  tokens: 21934
  tasks: 0
  commits: 3
plan_head_before: 113bf6225a083d494dddbe3cc80b53670bc1e780
plan_head_after: eba461804e4ded2f01ce314a06b6d778598878ab
duration: 25min-from-red-commit-to-source-verification
updated: 2026-10-20
---

# Phase 06 Plan 05: application lifecycle prerequisite

The hosted application now composes verified ingress with its trusted inner API,
requires immutable PostgreSQL installation identity, and enforces host admission
and exact Assistant startup readback/usage continuity. This is a prerequisite
batch. **06-05 remains incomplete.**

Source `eba4618` follows RED `a833e46`. The measured three-commit range includes
one concurrent parent documentation commit. Actual token estimate is realized
owned diff characters divided by four; no full planned task is claimed complete.

Exact commands, counts, failures, source hashes, runtime document shapes and
cleanup are in [06-05-CHECKPOINT.md](06-05-CHECKPOINT.md). Focused results: hosted
lifecycle 18, release 28, hardening 76, locality 165, and committed local container
1 passing test. Hosted-artifact fails one missing-input test and remains blocked.
The passing local image is arm64; it is not a cloud amd64 release.

Parent acceptance on exact source `eba4618` passed 312 tests across all six
required/regression groups, including hosted-postgres. Parent documentation
record `0a6eb58` retains this acceptance and the native continuation plan.

## Deviations and remaining obligations

The parent authorized migration 0004 and supporting runtime, dispatcher, runner,
Docker context and architecture-boundary changes needed for the approved hosted
identity/drain behavior. Existing local behavior remains covered by release
regressions. No new dependency selection or platform source change occurred.

Discovery showed that the native owner still consumes local installation
configuration. The parent separated substantive cloud native integration into a
fresh executor continuation, `06-05-NATIVE-PLAN.md`, while retaining all original
acceptance obligations. A source-only payload or boolean native receipt is not
accepted as a successful installation.

## Known Stubs

| File | Incomplete capability | Owner |
|---|---|---|
| deployment/cloud_lifecycle.py | Verified native-owner integration and full aggregate lifecycle; admission opening, qualification, backup and restore remain refused | Native continuation and platform host |
| deployment/tests/test_hosted_artifact.py | Actual fresh Linux installation/replacement/API/UI/private-data rehearsal after payload hashing | Native continuation |
| deployment/cloud_release.py | Immutable hosted release build/assembly and actual amd64 payload remain to be produced | Native continuation |

These are blockers, not successful operations. The runner registers hosted-artifact
as opt-in because source qualification cannot supply its inputs; publication must
require it after the actual build. Parent acceptance includes hosted-postgres
because this batch changes persisted schema. Global STATE/ROADMAP and requirement
completion remain parent-owned; this executor does not advance them.

## Self-Check: PASSED

Source files and both task commits exist. No tracked files were deleted. Owned
source is clean and unrelated edits remain intact. The checkpoint distinguishes
local automated evidence, missing cloud artifacts, live deployment and human
acceptance.
