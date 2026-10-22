# Bounded storage for developer checks

`./hyprn-mvp dev check <group>` supervises each group in its own process group.
New scopes allocated through `scoped_fixture.allocate_scope` register with that
supervisor, including allocations in child test processes. On success, failure,
interruption or quota refusal, the supervisor stops its processes, removes Docker
containers with that exact test/worker ownership label, releases scope-owned
networks/images, and removes the registered disposable directories.

Existing stores, resumed experiments, durable fixtures, source repositories,
installation stores and other applications are never adopted for deletion. Legacy
scratch scopes count toward admission limits but require explicit cleanup. An
abandoned managed session is recovered on the next check only when neither its
supervisor nor its recorded child is alive. Identity changes or symlink substitution
refuse deletion and report incomplete cleanup.

## Budgets

These are developer storage settings, not scientific inputs. Values are positive
integer byte counts supplied in the invoking environment:

| Variable | Default | Enforcement |
| --- | ---: | --- |
| `HYPRN_MVP_TEST_SCRATCH_BYTES` | 10 GiB | All test scopes under the selected scratch root; admission, approximately once per second, and completion |
| `HYPRN_MVP_TEST_MIN_FREE_BYTES` | 5 GiB | Stop the owned check if free space on the scratch filesystem drops below this reserve |
| `HYPRN_MVP_TEST_EVIDENCE_BYTES` | 512 MiB | Retired check diagnostics; evict oldest completed records to meet the budget |
| `HYPRN_MVP_TEST_BUILD_CACHE_BYTES` | 10 GiB | Project-attributed Docker build-cache records, checked before and after Docker groups |

Monitoring is a portable software limit, not a filesystem quota: a fast writer can
overshoot between polls. Docker pruning may take time. A cloud operator requiring
hard limits must also put disposable jobs/builds on a quota-limited filesystem.
Image layers, dependencies and durable authored records are not governed by the
scratch budget; cache pruning preserves shared/in-use layers and fails visibly if
it cannot reach the requested budget. This is not a whole-laptop storage cap.

Every completed check keeps a small record below
`<scratch root>/.hyprn-checks/<session UUID>`. Evidence is capped at 4 MiB per session
and 1 MiB per file (the final bytes of a larger log); this diagnostic copy is not a
complete scientific archive. Records expire after 24 hours or earlier under budget
pressure. The final `check_storage` output identifies the result location; earlier
printed scope paths describe the now-released test scope.

Use `--keep-scope` with one group for a diagnostic or fixture-capture session that
must retain its full disposable scope. Its processes and containers still stop.
Retention lasts at most 24 hours, is collected on subsequent checks, and counts
against the scratch budget. A budget refusal overrides retention. `qualification`
does not accept this flag: keep only the individual group being investigated.
Explicit resume paths are never newly registered, so they remain untouched.

Location policy is unchanged: configure `HYPRN_MVP_SCRATCH_ROOT` explicitly when a
separate development disk/root is desired; otherwise the OS temporary directory
is used. Tests never silently move to an invented host location. Old unmanaged
scopes may make a new check refuse admission; choose an empty scratch root or
review those legacy scopes rather than deleting an unknown installation.

## Reuse without sharing writable scientific state

Worker images are keyed by exact engine, recipe and source hashes. Derived test
images are keyed by their base image, recipe, context-file hashes and modes. Random test
UUIDs no longer change image identity. Cached input labels and base layers are
verified before reuse. Changed inputs require a different image.

Runtime roots, stores, container labels, execution ownership, source inventories
and attestation remain scope-specific. Reuse never accepts a stale attestation or
executes candidate code during preparation. Build-cache collection follows only
project-attributed records and dependency ancestry; it does not globally prune
unrelated Docker resources. A successful prune exit is followed by measurement.

## Verification and operating practice

- `./hyprn-mvp dev check check-storage` exercises repeated success/failure,
  cancellation, retention, recovery, unsafe paths and budget refusal.
- `./hyprn-mvp dev check check-storage-native` exercises real Docker reuse,
  independent attestation and exact container ownership cleanup.
- Run focused groups while changing code and the required integrated acceptance
  once on the delivery tree. Repeating an unchanged test adds no new evidence.
- On a serving VM, deploy qualified images by digest; keep developer qualification
  and build caches on a separate builder. Scientific record retention remains a
  separate application/platform policy. These test-cleanup changes do not garbage
  collect production studies or implement cloud infrastructure.

## Demo backups and ad-hoc experiments

Explicitly enroll **disposable developer folders** with the public CLI. This does
not enroll application installations or scan the home folder. The policy path
resolves from `--config`, then `HYPRN_MVP_EXPERIMENT_STORAGE_CONFIG`, then
`experiment-storage.json` below the configured development data root. No host
path is embedded in the repository.

```sh
./hyprn-mvp dev storage enroll --root "$DEMO_FOLDER" --root "$EXPERIMENT_FOLDER"
./hyprn-mvp dev storage status
./hyprn-mvp dev storage collect
./hyprn-mvp dev storage run --root "$EXPERIMENT_FOLDER" -- your-experiment-command
```

Folders must already exist. Enrollment persists across invocations; enroll each
new ad-hoc folder, or use `run --root` to enroll it and execute its command. Every
subsequent `dev check` automatically collects the configured folders before
admission. `storage run` collects before and after its command. There is no
background daemon: cleanup happens at these command boundaries, including after
an experiment returns a failure. Use `collect` in an existing host maintenance
schedule if cleanup while idle is required.

The default aggregate budget is **40 GiB**, with **5 GiB free space** reserved on
each enrolled filesystem. Change these with `enroll --budget-bytes N
--reserve-bytes N --root "$EXPERIMENT_FOLDER"`. All enrolled bytes, including
protected files, count. Budget pressure refuses new managed work and reports
which folders remain; it never deletes recent data or stops running experiments.
An experiment that crosses the budget reports a failing wrapper exit on completion.
These are admission/completion limits, not quotas on arbitrary external writers.

An entire folder is protected until all its files are older than **24 hours**,
using modification, change and available creation times. Host process arguments,
open files and Docker bind mounts protect active folders. Failed activity
inspection refuses collection. Trees are rechecked before removal; cooperating
writers should use `storage run` and keep their working directory or files inside
the enrolled experiment. External processes can race observation; use filesystem
quotas for a strict cloud capacity limit.

Only recognized disposable data formats (SQLite/databases and sidecars, logs,
tabular/array data and rendered media) are removed. Repositories,
source subtrees, links, hard links, archives and unknown formats remain. A `package.json`
file is preserved without protecting gigabytes of sibling databases. Empty folder
scaffolding remains, so enrolled locations remain usable. Source and scientific
execution/attestation rules are unchanged. Enrollment is an explicit declaration
that expired data in that folder is disposable; do not enroll durable study stores.
