---
phase: 06-hosted-staging
plan: 05-owner-schemas
subsystem: deployment
status: complete
scope: stopped-owner-schema-prerequisite-only
tags: [cloud, sqlite, postgresql, aiida, compatibility]
requires: [06-05-native, 08-02-reconcile]
provides: [real-all-owner-schema-observation, same-schema-compatibility]
affects: [06-05, platform-08-02]
tech-stack:
  added: []
  patterns: [stopped-read-only-owner-probes]
key-files:
  created: [deployment/cloud_owner_schemas.py, deployment/tests/test_cloud_owner_schemas.py]
  modified: [deployment/cloud_lifecycle.py, deployment/checks.py, deployment/tests/test_hosted_lifecycle.py]
key-decisions:
  - Inspect exact owner ledgers under both pinned releases without invented integer versions.
  - Require stopped writers and refuse pending SQLite journals before immutable reads.
  - Preserve ordinary receipt hashes and retain explicit active binding for incoming probes.
commits: 1
plan_head_before: 326f77e34ced908582db32eae9332e4e3d7a3635
plan_head_after: 63af9f041a321c175387eea1ef79643b631c9e45
completed: 2026-10-21
duration: not-captured
actuals:
  tokens: 8471
  tasks: 1
  commits: 1
---

# Phase 6 Plan 5: Stopped owner schemas

Real PostgreSQL, modeling SQLite and AiiDA schema observations enable conservative
same-schema replacement after stopped-writer proof. Product commit `63af9f0` and
platform commit `68d04d3` implement this prerequisite; neither full phase is complete.

See [the scoped checkpoint](06-05-OWNER-SCHEMAS-CHECKPOINT.md) for exact commands,
failures, artifact identities, cleanup and remaining parent-owned integration.
Final checks: owner schemas 9/9, PostgreSQL lifecycle 21/21, committed platform
reconcile 41/41. No skipped tests or known stubs in this scope.

## Deviations from Plan

Approved narrowing: compatibility now follows drain/stop because immutable SQLite
inspection is unsafe against live WAL writers. Startup reports its pre-start
schema observation; live public behavior remains separately qualified. Explicit
modeling owner identity is initialized for new stores; unbound legacy markers
refuse. The adjacent native receipt bug now accepts both upstream UUID encodings
without rewriting identifiers. These correctness adjustments are detailed in
the checkpoint, including every intermediate failure.

## Threat Flags

| Flag | File | Description |
|---|---|---|
| threat_flag: file-access | deployment/cloud_owner_schemas.py | New fixed reads of native owner SQLite and repository identities; protected active binding, stopped writers, read-only mounts and journal refusal constrain the boundary. |

## Self-Check: PASSED

Source files and both cross-repository implementation commits exist. Product
STATE and overall phase progress remain with the parent to avoid concurrent edits
or falsely advancing incomplete integration.
