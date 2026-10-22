# 06-05 owner-files backup checkpoint — 2026-10-21

Implementation: `661c8b858da9474b57078400a414933265541c0b`.
Scope and remaining prerequisites: [06-05-BACKUP-PLAN.md](06-05-BACKUP-PLAN.md).
This checkpoint is documentation only; no behavior changed after the final run.

## Result

The bounded owner-file snapshot/restore foundation is implemented and its focused
checks pass. Both native locks remain held across the caller's context, including
after `snapshot_files` returns. The immutable snapshot inventory binds exact
release/configuration/store/native identities and every retained file's hash,
size, UID, GID and mode. SQLite backup APIs snapshot both native databases and
both modeling databases. AiiDA and disk-objectstore validate native schema,
UUIDs, retained entities, terminated processes, object hashes and referenced
object completeness. Restore requires empty original paths and retains old
containment evidence only under its historical digest name, even on interruption.

Every receipt explicitly reports an incomplete store set:
`coherent_backup: false`, `application_database: not_included`.
No lifecycle or platform operation now claims complete backup/restore. There was
no cloud operation, dependency installation, image build, Docker test, migration,
candidate execution, human acceptance or release qualification in this batch.

## Commands and evidence

All test executions used the registered entry point:

```sh
source /private/tmp/hyprn-collection-env.sh
HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184 ./hyprn-mvp dev check hosted-backup --keep-scope
```

The override is the existing build-cache byte allowance, not a memory allowance.
The runner selected pinned `native-c88933d2a1c8c282`; the adapter checked AiiDA
2.9.3 and disk-objectstore 1.5.0. No alternative interpreter ran the tests.

| Run / scratch-scope UUID | Result | Reason for subsequent run |
|---|---|---|
| Initial sandbox invocation, no test scope | exit 5, tests not collected | Read-only sandbox could not open the pinned uv cache; the same scoped command succeeded through approved escalation |
| `a4d5aed3-4b89-4261-a47d-42e4c06118ad` | 6 tests, 0 failures, 6 errors, 0 skipped; exit 1; 2.11 s | Synthetic AiiDA config omitted its format version, triggering an inappropriate legacy fixture migration; fixture corrected to actual current format |
| `3a8e7a58-d592-447f-893e-dc4e13de5946` | 6 passed, 0 failures/errors/skipped; exit 0; 2.97 s | Added referenced-object completeness and interruption checks; moved old attestation directly to historical path |
| `62f0856e-159e-4517-8333-0932265eb99f` | 9 passed, 0 failures/errors/skipped; exit 0; 3.10 s | Added native lock ownership preservation, copied-byte recheck and file/directory durability |
| `37eb2373-ffc0-4d8f-b391-1fb2d65eea1f` | **9 passed, 0 failures/errors/skipped; exit 0; 3.01 s** | Final implementation tree committed unchanged |

Final evidence is the runner's `evidence/tests.json` under scoped scratch UUID
`37eb2373-ffc0-4d8f-b391-1fb2d65eea1f`; its check-storage record UUID is
`d5a0017b-3965-466b-ba77-79034ce0454f`. `--keep-scope` retains evidence under the
runner's 24-hour policy. All nested test databases, snapshots and restore trees
were removed by the scoped fixtures; the final scope's `tmp` directory was
confirmed empty. No container or process remains from the checks.

Final byte identities:

| File | SHA-256 |
|---|---|
| `deployment/cloud_backup.py` | `da50b88d32136269aad68961b0cbc546700011c23424c235b7d737601ed60d32` |
| `deployment/tests/test_hosted_backup.py` | `6b5237f8d9079d0c3a7fdd71f80f12e1e721a07db3d6d1f015d7d2f81421e9ff` |
| `deployment/checks.py` | `69427caabfa5f3950c19dd3c5a8f713f35ac31c7aa11643f1793c58a10797d81` |

`git diff --cached --check` passed before the explicit-path implementation commit.
Unrelated edits and index entries were preserved.

## Handoff and limits

Parent must rerun `hosted-backup` on the committed integrated tree before using
this prerequisite. Automated evidence proves owner-file behavior in isolated
native/SQLite stores on this development host. It does not prove Linux UID
handoff, a running WhatsOpt restore, stopped application/modeling writers,
effective platform fencing, full PostgreSQL RLS data coverage, cloud backup
completion, transport authenticity, or a coherent full-store restore.

Parent/platform owns the PostgreSQL authority decision and the eventual lifecycle
wrapper. The ordinary migration role cannot grant itself `BYPASSRLS`; this batch
does not introduce such a grant or pretend a privileged local PostgreSQL fixture
would establish a supported Cloud SQL operation. The host must bind a real
authoritative PostgreSQL receipt while maintaining the same stopped-writer hold,
then verify an isolated complete restore before complete-backup success is valid.
Admission remains closed until separate current qualification; VM state and live
cloud settings are unchanged by this work.
