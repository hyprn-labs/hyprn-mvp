# Retained native read performance

Task 1 of `07-PERFORMANCE-UX-PLAN.md`; parent owns integration and deployment.

## Change and preserved boundaries

`NativeExecution.read_record` now validates its already selected exact process
and request once, reads its retained bundle once, and then validates its stored
result. `retained_bundle` no longer calls `inspect`, which previously repeated
the full bundle traversal before returning the same bytes.

The host-only repository adapter reads through the pinned AiiDA 2.9.3 public
`NodeRepository.get_object` and storage backend `iter_object_streams` APIs. It
batches unique object keys, checks every returned identity and size, requires
complete inventory, and closes the generator on success or failure. Multiple
logical paths sharing a key retain separate size obligations. All paths, file
counts and expanded sizes are admitted before bulk reads. Unknown versions and
wrong request pins still fail through the original reader before object access.

The original `results.retained_bundle` validator runs unchanged on request-local
buffered bytes: every manifest, hash, schema, exact pin and scientific invariant
remains checked. No cache survives a call; subsequent corrupt bytes are refused.
The worker's `results.py`, `worker.py`, `exploration.py` and `surrogate.py` are
unchanged. The new host module is included in the exact attested source inventory;
the native installation must be rebuilt and re-attested, without changing the
numerical image or invalidating saved surrogate runtime pins.

## Verification so far

- Initial entry-point attempt was refused by the sandbox before testing.
- First authorized attempt was refused by the build-cache budget (14.09 GB of
  shared/active layers versus the default 10 GiB); no test ran. Subsequent runs
  use an explicit 20 GiB cache ceiling and preserve other sessions' images.
- Red `./hyprn-mvp dev check bridge-history`: **141 passed, 8 failed**, 82.86 s.
  The direct regression observed **two** manifest/full-file traversals rather
  than one. Seven tests failed because the new bulk adapter did not exist yet.
  Log: `/private/tmp/hyprn-native-read-red.log`.
- A sibling locality check correctly refused the newly introduced, then unlisted
  host module, then caught four old inventory counts. The three inventories and
  all exact counts are now updated; parent owns the integrated locality check.
- Green `./hyprn-mvp dev check bridge-history`: **157 passed**, 74.35 s;
  scoped runner exit 0, 76.318 s, storage cleanup exit 0. Log:
  `/private/tmp/hyprn-native-read-green.log`.
- First `./hyprn-mvp dev check units-launcher`: **2 passed, 62 setup errors**,
  0.32 s. The existing imported `catalog` fixture acquired a `current_catalog`
  dependency but its consumer did not import that fixture. Added that fixture
  import only; no production unit-catalog behavior changed. Initial log:
  `/private/tmp/hyprn-native-read-units-launcher.log`.
- Corrected `units-launcher`: **60 passed, 4 failed**, 23.04 s; scoped runner
  exit 1, 25.017 s, storage cleanup completed. All four failures are the portable
  archive test's retired fixture importing the removed application `approach`
  module. That fixture also targets retired approach/outbox tables. No affected
  launcher/parser/retained-reader test failed. This group is **not passing**;
  no test was skipped or weakened. Fixture migration remains parent-owned.
  Log: `/private/tmp/hyprn-native-read-units-launcher-green.log` (the filename
  records the intended rerun, not a successful outcome).
- `git diff --check` passed. `results.py` has no diff.

## Controlled repository benchmark

Within the passing bridge-history group, the same 480 files were read first with
the previous per-path public AiiDA reader, then through the bulk reader. Both
loose and packed object storage were exercised; byte equality was asserted. SQL
counts use SQLAlchemy's execution event, not inferred call counts. These are
local transport measurements, excluding schema validation, process lookup and
remote database latency; they are not an end-to-end staging speed claim.

| Storage | Previous SQL executions | Bulk SQL executions | Previous seconds | Bulk seconds |
|---|---:|---:|---:|---:|
| Loose | 1,920 | 2 | 0.847861 | 0.019094 |
| Packed | 1,919 | 2 | 0.847664 | 0.003584 |

Parent will run `native-execution` once on the integrated committed tree,
including the real retained-failure read assertion that only one bulk traversal
occurs while outputs, artifacts and process count remain unchanged. Public
staging before/after measurements and live sampling are parent's remaining work.
`units-attestation` also covers the updated exact source inventory; this remains
an integrated acceptance obligation. No live records or staging services were
changed by this task.
