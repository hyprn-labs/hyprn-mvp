# Bounded background work, readiness and finite-plan fairness

Status: implemented and committed with focused verification below. Bridge-history
has five legacy storage-fixture failures delegated to the parent for integration;
its one stale readiness test double was corrected. No staging mutation or deployment
has occurred. Native throughput and browser acceptance remain parent obligations.

## Implemented behavior

- Local pending-run discovery reads the indexed operational table; hosted discovery
  already uses the narrowly scoped indexed background function. Retained outbox bundles
  are not parsed for queue selection.
- Idle background polling backs off from 50 ms to 1 s; interactive prediction polling
  backs off to 250 ms. Activity resets the delay. Existing owner stop events interrupt
  waits. This is polling, not a new scheduler or durable notification service.
- The dispatcher retains its analysis owner and cursor. Each page shares actor queue
  capacity between pending plans, rotating the first admitted plan on subsequent passes.
  Same-actor analyses share ten available slots as five each. Unchanged analysis progress
  does not rewrite its receipt. Standalone run limits and finite-authority checks remain.
- A fixed, read-only native observation lane permits actual attestation while primary
  work is active. It accepts only require_attestation and bundle_runtime; all queues are
  bounded to one message. Execution still re-attests at launch. Readiness additionally
  requires a finite application stage or declared native operation deadline; it does not
  renew readiness solely from a timer. A late reply cannot publish ready after owner stop; the shutdown fence is set before
  joining threads. The polling-evidence destination is checked for symlinks before
  native rebind writes any file.
- PostgreSQL rollback failure cannot mask the original statement/commit exception.
  Native timeouts retain a sanitized timeout category across the private bridge. Native
  operation logs contain operation, duration_ms and outcome, without inputs or identities.

## Native polling finding and correction

Pinned AiiDA core.local has DEFAULT_MINIMUM_JOB_POLL_INTERVAL = 0.1 s, and Computer
uses the transport default when unset. Therefore lack of explicit 0.2 s does NOT prove
there was a 10 s floor or explain the observed approximately 24 s lifecycle. Do not
claim a measured speedup from this setting.

Reproducible initialization and authorized native rebind cap a slower configured
interval at 0.2 s while preserving faster existing/default intervals (including 0.1 s).
Rebind checks exact native identity and quiescence, records the previous value in its
pending recovery journal, and writes previous/current settings into operational evidence.
Scientific nodes, configurations and run results are unchanged. A new release still
requires attestation; no live profile was edited by this work.

## Verification so far

All groups use the pinned `./hyprn-mvp dev check <group>` entry point and scoped stores.

- RED runtime-observation: 3 failed, 61 passed, 17.78 s. Regressions demonstrate the
  missing idle backoff, retained outbox queue scan and masked transaction timeout.
- RED calculations-api: 1 failed, 78 passed, 59.43 s. Two same-actor plans received
  [10, 0] queue slots instead of [5, 5].
- First GREEN runtime-observation: 65 passed, 18.06 s (before shutdown race test).
- First GREEN calculations-api: 79 passed, 55.47 s (before 126-member restart test
  and unchanged-receipt suppression).
- Subsequent runtime-observation: 65 passed, 1 failed, 19.77 s. The old restart test
  reused the stopped publisher; corrected to construct a new owner, as real restart
  does. The new late-publication race test passed.
- One default-sandbox invocation stopped at the pinned uv cache permission boundary
  before tests; retried with authorized cache access.
- bridge-history stopped before tests because the existing shared build cache exceeded
  its default 10 GiB budget; no images were deleted. Next run uses the already reviewed
  scoped 20 GiB budget.
- A later calculations-api invocation stopped before tests when the shared Docker
  inventory changed during a concurrent native build. Final checks are serialized after
  that build; no product assertion failed in this invocation.

Deterministic polling schedule acceptance bounds: at most 65 background polls per idle
minute (formerly 3,000), at most 242 prediction polls (formerly 6,000); wake bounds 1 s
and 250 ms respectively. These are loop scheduling measurements, not an end-to-end
staging latency or database CPU claim. Actual native and hosted measurements remain.

## Final serialized verification

Environment for each command: `HYPRN_MVP_DATA_ROOT` and `HYPRN_MVP_TOOLS_DIR`
resolved to the existing private development roots; `HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480`.
No shared images were removed. Logs are private scratch artifacts.

- `./hyprn-mvp dev check runtime-observation`: **67 passed**, 19.17 s;
  `/private/tmp/hyprn-a2-verified.log`, exit 0, runner cleanup exit 0.
- `./hyprn-mvp dev check calculations-api`: **81 passed, 1 failed**, 57.52 s;
  `/private/tmp/hyprn-a3-verified.log`. New cross-actor fixture mistakenly called the
  one-user local bootstrap twice. Corrected to the existing scoped multi-user seed
  convention; actual public login, authorization, queue and isolation assertions remain.
  The 126-point owner-restart test passed.
- Final `./hyprn-mvp dev check calculations-api`: **82 passed**, 57.55 s;
  `/private/tmp/hyprn-a3-verified-final.log`, exit 0, runner cleanup exit 0.
- `./hyprn-mvp dev check hosted-native-owner`: **21 passed**, 14.91 s;
  `/private/tmp/hyprn-a2-owner-verified.log`, exit 0, runner cleanup exit 0.
  Tests use real isolated AiiDA profiles and prove retained scientific nodes unchanged,
  slower polling capped, faster polling preserved and unsafe evidence destinations refused.
- `./hyprn-mvp dev check bridge-history`: **135 passed, 6 failed**, 44.21 s;
  `/private/tmp/hyprn-a2-bridge-verified.log`, runner cleanup exit 0.
  New private bridge concurrency and sanitized timeout assertions passed. One old
  dispatcher test double lacked the already-required `ready()` method; corrected in
  8ff7f7ef. Five remaining failures in test_history_reuse.py still write/read retired
  outbox payloads: three missing inline history keys and two preparation failures before
  source-disappearance injection. Parent owns migration and integrated rerun; not waived.
- `git diff --check` and syntax parsing passed all 12 owned source/test files.

## Commits and evidence identity

- `7f00298d`: native initialization/rebind polling consistency and owner tests.
- `8ff7f7ef`: indexed queue selection, adaptive waits, independent bounded observation,
  shutdown/stall fencing, rollback cause preservation, native timing and bridge tests.
- `26665d11`: finite-plan fairness, unchanged-receipt suppression, >60-point restart
  and cross-study/actor public-boundary tests.

Checks ran on the shared integration tree containing concurrent monetary and C3 work;
these commits contain only this lane's explicit paths/hunks. Parent monetary readiness
hunks remain untouched and uncommitted by this lane. No runtime source changed after
passing runtime-observation and hosted-native-owner. The bridge test-double correction
is the only later bridge-related delta and awaits integrated bridge rerun.
All runners returned scoped cleanup reports; no owned test process remains. Existing
shared Docker/cache resources and other sessions were preserved. Rebuilding this changed
native runtime invalidates its previous execution attestation: deployment must re-attest.

## Final evidence to add

- Parent integrated bridge-history rerun after the legacy storage-fixture migration.
- Parent integrated agent-tools and units-api acceptance required by the plans.
- Parent restricted-worker finite analysis, cancellation/revocation, validated exploration
  without reruns, before/after staging latency, and deployed release identity.
