---
phase: 06-hosted-staging
plan: 05-native
status: incomplete
subsystem: cloud-execution
tags: [native, aiida, cloud, linux, attestation]
requires: [06-05-application-prerequisite, platform-231bad2]
provides: [explicit-cloud-execution-projection, native-owner-source, shared-dispatch-bridge, explicit-native-rebind, installed-native-calculation-and-restart]
affects: [hosted-artifact, platform-host-startup]
tech-stack:
  added: []
  patterns: [execution-only-projection, protected-observed-uuid-receipt]
key-files:
  created: [deployment/cloud_native.py, deployment/dispatch_bridge.py]
  modified: [deployment/cloud_lifecycle.py, deployment/native_environment.py, deployment/execution_runtime.py]
key-decisions:
  - Keep native configuration separate from local installation configuration.
  - Bind attestation to the stable execution projection, excluding mutable admission.
  - Pin generated native UUIDs in protected host receipts rather than inventing them from logical store IDs.
plan_head_before: 65e5411b447545bf9107e760894a4a684bcf9378
plan_head_after: 68418b13ea70eef08e8303f30113032c4e5e2244
commits: 29
completed: null
---

# Phase 6 Plan 5 Native: Installed calculation slice summary

Cloud execution has a closed configuration seam, actual native UUID observations,
shared private dispatcher transport, explicit Linux build targets and protected
release rebind for stopped owners. Exact installed Linux extraction,
initialization, real containment attestation, calculation and restart now pass on
rebuilt source `18d872a`. The real restricted worker produced available outputs
49.0 and 7.0; fresh-process reads preserved the exact record and duplicate launch
was refused. Full PostgreSQL dispatch, saved scientific workflows, release
replacement and coherent backup/restore remain unverified; this plan is incomplete.

Detailed commands, pass/fail counts, prior failures, identities, scope cleanup and
remaining gates are in [the checkpoint](06-05-NATIVE-CHECKPOINT.md). The measured
29-commit range includes concurrent parent build/dependency and checkpoint
commits; this executor's source commits are `bd8cee4` (RED), `44b87a0`
(implementation), `55b6429` (explicit target fixes and safe worker export), and
`784bbf9` (explicit native release rebind). The latter passes 12 native-owner,
six configuration and 165 locality tests. Its real scoped AiiDA records are
preserved; positive root authorization and exact image/inventory checks still
need installed Linux proof.

The installed fixture and honest failure record are committed in `a31439e`.
`fa8272c` makes only authenticated working-copy input files read-only and their
directories worker-traversable; ten configuration tests pass, including real
restrictive modes, symlink/hardlink refusal and unchanged private ancestors.
`18d872a` requires real bash/ps/tail/whoami before cloud execution mutation or
admission; fifteen native-owner tests pass. The fixture reuses an existing
reviewed Linux image for host utilities and changes no worker restrictions.
The exact archive/image identities, every installed failure and released scope
are recorded in the checkpoint. No failed calculation is presented as success.

The parent accepted the rebuilt installed fixture: one test passed in 107.771 s,
exit 0. This executor reviewed the existing evidence and exact-label cleanup without
rerunning it. Archive SHA-256 is
`76f4946d5b10a573f666ab915e1623b1a91e7f16dc285dbc0a3444f512fcfbe5`;
the exact worker image is `sha256:2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`.
The checkpoint records the original attestation hash and the fixture collector's
documented trailing-newline normalization. Binding remains explicitly
`isolated-native-bundle`, not full hosted release qualification.

## TDD Gate Compliance

The fresh launcher process accepted an ambient development root under cloud
selection. The intended target assertion and two related assertions failed with
three tests discovered. The classifier returned `RED_EVIDENCE_OK`. Semantic
inspection confirmed the missing cloud boundary caused the failures. The final
selector group passes six tests; real native-store and local regression evidence
is recorded separately in the checkpoint.

## Deviations from Plan

- [Rule 2] Native wheel packaging now includes exact owned PostgreSQL migration
  SQL. Real Linux preparation exposed the earlier Python-only assumption.
- [Rule 1] Explicit Linux target participates in engine cache identity and Docker
  builds, preventing reuse of a different architecture for cloud packaging.
- [Rule 2] Native execution uses a stable execution-only digest to avoid an
  attestation/admission digest cycle. Full host/application identity remains bound
  independently to the full platform preview.
- [Rule 1] Real installed Linux execution exposed AiiDA private input-directory
  modes. Only authenticated execution-copy permissions are normalized, preserving
  saved bytes, worker UID, read-only mounts and private stores.
- [Rule 2] Missing host ps caused AiiDA to retrieve unfinished output. Explicit
  owner host-utility preflight now refuses before initialization/execution.

## Deferred Issues

Full installed artifact qualification, installed cross-release replacement,
PostgreSQL-to-worker execution, saved scientific workflows and coherent backup/restore
remain mandatory. No requirement or
phase completion is recorded. Parent owns global planning state and separate
Linux packaging evidence.

## Self-Check: PASSED

All listed executor source commits and new source files exist. No tracked deletion was
introduced. Parent installed evidence and exact-label resource cleanup were reviewed.
This confirms the native slice, not the open full delivery gates.
