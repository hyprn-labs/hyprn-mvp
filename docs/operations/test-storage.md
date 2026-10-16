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
