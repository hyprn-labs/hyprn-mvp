# Experiment retention checkpoint

Implemented in `942eca8`, tightened archive/source-backup preservation in
`d2cb099`. Tested delivery tree: `d2cb099`. This checkpoint is the only later
owned change. Unrelated roadmap and research work remained untouched.

## Delivered journey

Public `dev storage enroll/status/collect/run` commands manage explicit disposable
experiment roots. `dev check` collects the configured roots before admission;
`storage run` collects before/after its command and preserves its failure code.
Default aggregate admission/completion budget: 40 GiB; free reserve: 5 GiB.
Whole roots updated within 24 hours or observed active remain protected. Only
recognized data files expire; code, repositories, links, opaque archives and
unknown formats remain. Scientific execution and attestation are unchanged.

The host policy now enrolls four previously identified demo/ad-hoc folders. A
real public `collect` and subsequent normal `dev check` both reported 7,011,840,000
allocated bytes, all recent, zero removed, admitted within budget. Configuration
and raw logs live outside the repository; no host-specific path is portable code.

## Verification

All group commands used `./hyprn-mvp dev check`, the existing pinned tool/data
roots, a dedicated external scratch root and `HYPRN_MVP_LIVE_PORTS=65123`.
On the final implementation commit:

- `check-storage`: 31 passed. Three simulated expiry cycles each remove a
  131,072-byte backup and return to the same source-only allocation baseline.
  Recent/active roots survive budget pressure. Changed roots, symlinks, hard links,
  source trees, repositories and failed activity inspection are preserved/refused.
  Public CLI dispatch refuses a command before launch when over budget and retains
  exit 7 from a failed command.
- `local-edition`: 44 passed, 459 subtests passed.
- `units-guards`: 139 passed.
- Real CLI `storage enroll` followed by `storage run -- /bin/sh ...` in an isolated
  folder successfully created a backup and retained its 4,096 allocated bytes as
  recent. No production store was used by tests.
- After enabling the host policy, `dev check check-storage` was repeated to verify
  the changed configuration wiring: automatic collection reported all four roots
  preserved, then 31 tests passed and the owned test scope was released.
- `git diff --check`: passed.

The first sandboxed test launch could not write the existing pinned uv cache;
rerunning with authorized host access succeeded. Earlier implementation runs also
passed (27 storage tests before the additional CLI/source guards; 44 local tests).
There were no test assertion failures in this batch. Test supervisor scopes were
released; compact external logs remain in the experiment-storage verification
folder. No Docker rebuild was needed for this filesystem/CLI change.

## Limits and next action

This is command-boundary maintenance, not a daemon or a hard filesystem quota.
It does not kill already-running experiments, throttle arbitrary external writers,
or silently enroll future unknown folders. New folders should use `storage run
--root` or explicit enrollment. Expiry tests advance the collector clock in an
isolated store; they do not claim a real 24-hour wall-clock soak. External writers
can race process/file observation. Unknown formats and empty scaffolding remain
and count toward the budget. A cloud hard capacity cap remains a platform-owner
filesystem quota responsibility.

Full release qualification was not repeated for this maintenance batch. The
previous storage-lifecycle checkpoint records the missing pinned staging-image
blocker; restoring and qualifying that dependency remains the environment owner's
release obligation. Human product acceptance is separate and unverified.
