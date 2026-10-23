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
  no test was skipped or weakened. Parent subsequently assigned fixture migration
  to this lane; the completed repair is recorded below.
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

## Required fixture repairs and final checks

- Production commit: `07cacb56`. Fixture migration: `d8dd2ad0`, corrected by
  `467dfed6`. The current portable-archive fixture seeds the same historical
  authoring bytes and uses the actual submission preparation, dispatch and
  recording owners with a synthetic native boundary. It does not execute
  candidate code or weaken archive, exact-model or quantity assertions.
- First migrated-fixture run: **60 passed, 4 failed**, 42.73 s. Direct terminal
  payload writes used an obsolete shape; the current database CHECK correctly
  refused them. Replaced those writes with `Submissions.dispatch`, preserving
  the current single-writer boundary. Log:
  `/private/tmp/hyprn-native-read-units-launcher-current.log`.
- Final `./hyprn-mvp dev check units-launcher` on `467dfed6`: **64 passed**,
  24.36 s; runner 26.274 s and cleanup exit 0. One upstream event-loop
  deprecation warning. Log:
  `/private/tmp/hyprn-native-read-units-launcher-final.log`.
- Parent's integrated `units-attestation` reported **57 failed, 26 passed**.
  Its stale fixture inventory omitted the already-attested `cloud_native.py`
  and `dispatch_bridge.py`, cascading into absent-file failures when testing
  copied source trees. Added both fixture entries and corrected exact inventory
  size from 53 to 56; no production attestation or containment rule changed.
  Initial log: `/private/tmp/hyprn-performance-ux-release/units-attestation.log`.
- Parent reports integrated **native-execution 114 passed**, **locality-contracts
  166 passed**, **contracts 127 passed**, **hosted setup 27 passed**. Parent
  checkpoint owns exact commands, logs and source identity for those runs.
- Final `./hyprn-mvp dev check units-attestation` on `467dfed6`: **85 passed**,
  112.17 s; runner 114.986 s and scoped cleanup exit 0. The two additional
  source-drift cases account for the increase from 83 to 85 tests. Log:
  `/private/tmp/hyprn-native-read-units-attestation-final.log`.

All checks above use the pinned `./hyprn-mvp` entry point with the existing
external development data/tools roots, a 20 GiB test build-cache ceiling and
live port fences 54821, 54458, 54932. No live-store or service mutation occurred.
The only delta after tested source commit `467dfed6` in this lane is this
checkpoint. Parent retains staging release, before/after public measurements
and signed-in Assistant/slider verification; those are not established by the
local transport benchmark.
