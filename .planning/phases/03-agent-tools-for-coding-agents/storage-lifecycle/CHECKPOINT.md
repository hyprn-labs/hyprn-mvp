# Developer storage lifecycle checkpoint

Implementation: `640cd15` — one maintenance batch. No application API, scientific
data contract, production store, global instruction or unrelated worktree changed.

## Delivered behavior

The public local-edition check command supervises new disposable scopes, stops its
process group, reconciles exactly owned Docker resources, and removes test stores
on completion, failure or interruption. Scope identity/inode/live-root checks
protect existing stores; abandoned registered sessions are recovered on a later
invocation. Scratch, free-space reserve, diagnostics and project build-cache budgets
are enforced. Explicit full-scope retention expires after 24 hours.

Workers reuse exact engine/recipe/source inputs. Derived images also account for
context bytes and permissions. Runtime ownership and attestation remain independent
per scope. Deliberately mutated images are disposable. See
`docs/operations/test-storage.md` for settings and operating boundaries.

## Committed-tree acceptance

All checks use the pinned toolchain through `./hyprn-mvp dev check`. The host's
reviewed development data/tool roots were supplied via their documented variables;
verification used dedicated external scratch roots and `HYPRN_MVP_LIVE_PORTS=65123`.

| Command suffix | Result |
| --- | --- |
| `check-storage` | 16 passed; real subprocess/filesystem cleanup, failure, interruption, quotas, retention, recovery and foreign-data preservation |
| `local-edition` | 44 passed, 459 subtests passed |
| `units-attestation` | 80 passed; containment, exact identities and forced unreadable-worker refusal |
| `check-storage-native` (three consecutive runs) | 2 passed each; independent attestation, byte/mode invalidation, exact container and multi-tag disposable image cleanup |
| `qualification --jobs 1` | 3 groups passed; `units-staging` failed; 124 not started |

Qualification passed `findings-native-guards` (17 tests), `units-guards` (139 tests)
and `units-contracts`. It stopped at
`test_units_staging_generator_pinned_catalog_and_factors` (1 failed, 4 passed,
22 deselected): the host lacks the previously pinned Docker image
`sha256:a2c45218391208dafdc9d62735f075d6a6cb7d547d25dca469272d298ddb17c1`.
No substitute identity or relaxed attestation was introduced to make it pass.
Full product qualification and human acceptance are therefore unverified.

## Repeat measurements on the committed implementation

Three consecutive public CLI runs used `HYPRN_MVP_TEST_EVIDENCE_BYTES=65536` to
exercise retention pressure. The measurement harness captured actual allocated
scratch bytes, Docker IDs and attributed Buildx cache bytes after every exit.

| Run | Remaining scopes / allocated bytes | Reusable image count | Attributed cache bytes | Diagnostic bytes |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0 / 0 | 12 | 6,094,153,604 | 0 |
| 2 | 0 / 0 | 12 | 6,094,153,604 | 0 |
| 3 | 0 / 0 | 12 | 6,094,153,604 | 0 |

The reusable image-ID set was identical in every run, with SHA-256
`7610609d7ad6e7ef49476740633d2e5d6b0d7220dc4f3e3bdb4886b4990d52b6`.
The native test also verifies exact owned-container removal while preserving an
unrelated sentinel container, then releases its sentinel. Diagnostics exceeding
the deliberately small test budget were retired; external verification logs remain.
Another worktree was active: global Docker image counts changed 138 → 139 → 139,
so global counts were not misattributed to these runs. The relevant image set,
scratch allocation and measured cache did not grow across these three runs.

## Development failures resolved

- New tests initially failed repository coverage because they were untracked;
  explicit staging fixed the registry check. A removed upstream archive was restored
  through the existing acquisition function and verified against its existing pin.
- Guard environment: an empty live-port list broke an existing `max()` assertion;
  port 8000 collided with an existing source-text timeout scan. The isolated reserved
  sentinel 65123 passed all 139 guards.
- Lifecycle test iteration: 9 failures/3 passes/9 teardown errors exposed an overly
  restrictive test fence for owned subprocess signals; the established baseline
  fence permits only owned children. Three subsequent failures were test discovery
  treating the new collection lock as a session directory; directory filtering fixed
  them. Final 16 lifecycle tests pass.
- Attestation initially reported 79 passed/1 failed: cache reuse bypassed the test's
  deliberate unreadable-file fault. That test now forces the fault build against the
  reviewed engine and restores shared image tags and scoped records afterwards.
  The corrected development run passed all 80 tests.

## Scope, evidence and remaining obligations

The first real budget enforcement reduced attributed build cache from
16,211,012,617 to 4,154,420,509 bytes. Subsequent verification can legitimately warm
additional cache within its 10 GiB budget. No global Docker prune was performed.

Runtime logs and measurement JSON remain outside the repository in the dedicated
`hyprn-storage-verification` directory. Completed managed scopes are released;
bounded diagnostic copies are disposable, not scientific archives. Existing legacy
scopes and authored stores are never adopted by this collector.

Software polling can overshoot between checks. Retained image revisions and durable
dependencies are outside the scratch/cache budgets; this is not a whole-host hard
quota. Cloud hard quotas, production retention and separate builder deployment
remain platform-owner responsibilities. The development environment owner must
restore the missing reviewed fixture before full release qualification can pass.
