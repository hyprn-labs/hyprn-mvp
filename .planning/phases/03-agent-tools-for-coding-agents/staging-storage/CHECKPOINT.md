# Staging retention cleanup and acceptance

Delivery commits: `bf8dd325`, `7b1acee2`, `0981cf10`. Final tested implementation:
`0981cf10`. Only this checkpoint follows it in the owned change set. Unrelated
hosted plans, design-system work, ADRs and research were preserved.

## Actual cleanup

The enabled host policy discovers immediate staging children by source/payload
manifest under the explicitly enrolled temporary parent. No new build or cloud
publication was performed. No running workload was stopped, and no image was removed.

- 41 expired staging folders: 26,961,850,368 allocated bytes of recognized generated
  OCI/native archives removed (25.11 GiB). Source trees, source.tar, evidence,
  manifests, corresponding-source and unknown files remain.
- 30 exact commit-labelled, unreferenced build volumes: read-only content inspection
  measured 13,923,766,272 bytes removed (12.97 GiB). Creation/content age, all container
  references, associated root age and process activity were checked. Recent or
  unassociated volumes remain.
- Exact-recipe-attributed, unshared cache IDs were pruned with `until=24h`;
  Docker reported 297.6 MB reclaimed (about 0.28 GiB). Shared, recent, unrelated and
  dependency-retained records remain; this was not a global prune.
- Total directly attributed deletions: approximately 38.35 GiB.
- Recorded free space: 8.4017 -> 50.6116 GiB, a 42.2099 GiB net increase. Concurrent
  host work and filesystem reclamation account for the difference; the full net
  increase is not claimed as directly measured deletions.
- Docker.raw allocated storage: 51.9450 -> 38.8336 GiB.
- Twenty recent experiment roots retained. Final status: zero eligible expired
  archive bytes, zero eligible volumes, admission true. Remaining measured staging
  roots: 22,317,305,856 bytes; owned volumes: 4,188,221,440 bytes; attributed cache:
  13,627,612,668 bytes.

Raw action reports, policy snapshot, before/after measurements and logs remain in
`/private/tmp/hyprn-staging-retention-audit/` on this host. The policy is outside the
repository; no host path or machine-specific image ID entered portable source.

## Workflow behavior

Staging CLI commands collect before and after snapshot, application build and
payload assembly, including failed commands. Developer checks also collect.
Manifest discovery enrolls future folders below configured parents automatically;
new staging output parents are enrolled by the current command entry point.
Cleanup diagnostics go to stderr so existing machine-readable build JSON remains
valid. Nested scoped test children cannot implicitly discover host retention policies.

Defaults: 40 GiB generated staging trees, 20 GiB owned build volumes, 20 GiB
attributed cache, 5 GiB free reserve. The initial 10 GiB staging cache proposal
refused admission after expanded attribution measured 12.69 GiB retained cache;
20 GiB accommodates observed dependencies without deleting recent/shared records.
The pre-existing check-specific cache budget is unchanged. Limits refuse new work;
they never stop running workloads or override the 24-hour/source protections.

## Committed-tree verification

All groups ran through `./hyprn-mvp dev check` using the pinned existing tools and
an isolated external scratch root. Host staging policy discovery was disabled in
these group launch environments; real host cleanup/status was exercised separately.

- `check-storage`: 44 passed. Repeated expiry cycles return exports to baseline;
  source and source archives survive. Recent/active roots, linked exports, nested
  repositories, changed/foreign activity, exact volume identity, recent volume
  contents, cache age filters, automatic discovery, budget refusal and scoped-child
  isolation are covered.
- `hosted-cloud-build`: 9 passed. The real snapshot command runs retention on both
  sides and still verifies exact source identity. Existing payload checks pass.
- `units-guards`: 135 passed.
- `local-edition`: 43 passed, 482 subtests passed, 1 failed. The remaining failure is
  `LockTests.test_the_groups_are_the_reviewed_sets`: contract environment and
  application lock sets differ. Both lock files are unchanged from the parent of
  this task's first implementation commit; this pre-existing consistency problem
  remains a release qualification obligation.
- Public `dev storage staging-collect` completed filesystem/volume cleanup. The
  cache pass returned status 2 for the initial undersized cache budget; the final
  configured-policy `staging-status` returned 0/admitted after the budget correction.
- `git diff --check` passed. Managed verification scopes were released.

Earlier local-edition verification exposed a second failure: nested CLI argument
checks discovered the host policy and reached Docker. Scoped automatic policy
lookup is now disabled unless an explicit policy override is supplied. The new
regression test and final CLI argument checks pass. No assertion failures remain
in the retention/build/safety groups. Full product qualification was not run after
this known lock-consistency failure; human acceptance is separate and unverified.

## Remaining scope

There is no idle daemon or hard filesystem quota. Older copied scripts/internal
Python calls bypassing the current command entry point need explicit collection.
Unknown formats, source snapshots, unrelated Docker state and younger/running work
are intentionally retained. Read-only observations cannot eliminate races with
uncooperative external writers; Docker itself refuses referenced-volume deletion.
Cloud hard quotas and the lock consistency repair remain separate owner work.
