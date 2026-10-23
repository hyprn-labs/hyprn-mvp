# Database contention and user allowance recovery

Target: staging. Acceptance: database contention does not kill the dispatcher;
analysis saves retain all integrity checks with short write-lock occupancy; failed
chat refresh does not claim live progress; an explicit user allowance override
preserves cumulative spending. No study repair, Assistant message or resume.

Diagnosis: dispatcher exited on a raw TLS read timeout while obtaining the global
PostgreSQL writer lock. Safety admission then closed staging. The account also
reached its default allowance. The exact long-running blocker was not retained;
analysis save validation is a confirmed long critical section, not a proven trace
of that particular lock holder.

Changes: normalize transport errors without transaction replay; bound server lock
waits before socket deadlines; preserve dispatcher reconciliation/backoff and
host-owned shutdown; validate immutable analysis members before the writer lock
and bulk-recheck exact bytes under it; show unconfirmed connection state; scoped
operator user limits (USD cents), default unchanged, spending never reset.

Pre-fix reproduction: runtime-observation, 2 failed / 67 passed (raw TimeoutError
and OSError escaped). Initial fixes exposed startup-loop stop-event initialization,
reference-mark lookup, and an outdated timeout assertion; corrected. Platform
fixture pins regenerated; nested JSON error normalization corrected. No failures
are counted as passes. Platform contract: 28 passed, commit 2776a09.

Verified implementation commits: f4975cf6, ac46df2e, 7628acb0; delivery source
b1412959f96de1b1ac7d2a202f961d66ba3d5f0f (same committed tree). Platform 2776a09.
Each product command used `./hyprn-mvp dev check <group>` with isolated fixtures:
runtime-observation 70, calculations-api 105, assistant-bridge 219, agent-tools
331, hosted-postgres 59, contracts 127, ui-navigation 49, hosted-lifecycle 21,
hosted-cloud-build 9 passed. Design-system checker, generated tokens and TypeScript
checks passed. PostgreSQL regression exercised real lock contention, bounded refusal
and a successful subsequent write; no replay. Browser regression exercised lost
refresh, preserved draft and recovery without sending. Explicit Resume after an
allowance increase rechecks budget and sends the original request once; startup
keeps blocked turns paused. An isolated corruption fixture initially hit its
immutable trigger; corrected only the disposable fixture setup and reran 105 tests.

Release a6e016116db2c852155eec72face12cac9689c22c38a8e688fb6d28740744d9c.
Preparation 1cb5af248b075489013dbd0c7a1125f0f6f552ad4e1177800c99c8ab677574d5.
Deployment evidence: `/private/tmp/hyprn-database-recovery-final-release/` and
`/private/tmp/hyprn-database-recovery-final-deploy/packet-1/application-evidence/`.
Published/staged, prior runtime stopped after zero-active-work checks. One paused
Assistant and one uncertain analysis retained. No migration; schema 16 unchanged.
Coherent PostgreSQL and owner-file backup completed. Fresh containment/startup and
19 network observations passed, with zero study executions/provider messages from
the network check. Signed-in Chrome displayed the original brief and paused
Assistant with explicit Resume. Read-only counts remained 128 configurations,
5 analysis versions, 20 recorded runs and no answer. Exact conversation/turn IDs
and pause reason retained. Account read: USD49 cumulative ceiling, USD20.03 spent,
USD28.97 remaining, no reset. No Assistant message, Resume or Stop was submitted.
Three runtime containers are running and ongoing named-user staging access promoted.

Promotion initially collided with the periodic health check before any promotion
receipt was written. Read-only reconciliation confirmed the absence of promotion;
the continuation waited for both activating/active service states to finish, then
normal promotion succeeded. Both attempts retained in deployment evidence. This
operator race is separate from the fixed application database failure.

Public screenshot: `/private/tmp/hyprn-database-recovery-final-release/assistant-recovered.png`.
Tests released their isolated fixtures. Immutable build/release/backup evidence is
retained for recovery; unrelated files and other sessions were untouched. No new
study workload was submitted: completion after the owner's explicit Resume and
full qualification/human acceptance remain unverified. Existing full-qualification gaps are retained in 11-PARENT-CHECKPOINT.md.

Operational follow-up (not a study runtime measurement): the stopped-owner snapshot
copied more than 68,000 files / 1.2 GB before completion; many small retained execution
license files amplify deployment I/O. Preserve the backup guarantee; evaluate file
deduplication/snapshot efficiency separately rather than skipping recovery protection.
