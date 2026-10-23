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

Final product checks, deployment identities and public read-only verification:
pending. Existing full-qualification gaps are retained in 11-PARENT-CHECKPOINT.md.
