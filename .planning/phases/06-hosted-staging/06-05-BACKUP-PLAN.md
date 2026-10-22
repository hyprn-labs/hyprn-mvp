# 06-05 owner-files backup prerequisite

Status: bounded file-owner foundation; coherent hosted backup remains incomplete.
This scoped implementation is part of task 5 in `06-05-PLAN.md`. The parent
orchestrator confirmed the reduced scope after inspecting PostgreSQL RLS backup
authority on 2026-10-21. No cloud resource or live-store action is authorized here.

## First outcome and acceptance

A stopped-owner snapshot can restore the exact native UUIDs, retained scientific
bytes, both modeling SQLite databases, and application artifact files into empty
original paths. A real AiiDA database with packed and loose objects is used in the
native pinned interpreter. Missing objects, unsettled processes, conflicting locks,
changed bytes, unsafe paths and nonempty destinations fail closed. Restoring old
containment evidence never makes it active, including on interruption.

The snapshot declares `coherent_backup: false` and
`application_database: not_included`. This is the next stopping point. It is not
the complete 06-05 outcome or release qualification.

## Owned batch

- `deployment/cloud_backup.py`: one fixed owner-file layout adapter and native
  hold context, manifest-last inventory, validation and empty same-path restore.
- `deployment/tests/test_hosted_backup.py`: real native/SQLite roundtrip and
  failure cases, without Docker or a cloud dependency.
- `deployment/checks.py`: only the `hosted-backup` guard registration and target.
- This plan and `06-05-BACKUP-CHECKPOINT.md`.

No changes to lifecycle invocation, platform contracts, app migrations, source
pins or source inventories are included. Other agents retain those files.

## Interface and guarantees

`native_hold(execution_root, profile_name, timeout=...)` holds the actual
`executor.lock` and AiiDA `ProfileAccessManager.lock()` across the caller's whole
context. The future trusted host can keep this hold across its PostgreSQL backup
receipt and file snapshot. It must already hold the outer deployment fence,
close admission, settle accepted work and stop app/modeling/native writers.

`snapshot_files(hold, destination, roots=..., identity=..., owner=...)` takes
exactly execution/modeling/artifact roots and expected installation, logical
store, release/configuration and native-owner identities. The manifest is
published last after SQLite integrity/foreign-key checks, native schema and UUID
checks, referenced-object completeness and disk-objectstore validation. Native
DB and packed-object index both use `sqlite3.Connection.backup`, as do both
modeling databases. No live SQLite DB bytes or WAL files are copied raw.

`restore_files(snapshot, roots=..., identity=..., owner=..., timeout=...)`
verifies every manifest path and byte before destination writes, requires empty
original paths, retains source ownership/modes and native UUIDs, and writes old
containment evidence only at its historical digest path. Partial failures retain
their files and cannot be retried into the nonempty destination automatically.

The adapter runs in one dedicated process under the pinned native interpreter;
AiiDA configuration is process-global. It imports only audited native libraries,
never candidate component source. AiiDA 2.9.3 and disk-objectstore 1.5.0 are already
locked dependencies. Their generic backup helper is not used because it performs
maintenance and requires an additional external utility.

## Verification and remaining owners

Acceptance: `./hyprn-mvp dev check hosted-backup` under the existing scoped runner.
Parent reruns the group on the committed integrated tree before dependent work.

Platform/parent still owns the authoritative PostgreSQL backup/restore choice,
cloud/IAM review, closed-admission and stopped-writer orchestration, isolated
restore authorization, protected snapshot transport/receipts, root-to-service UID
checks on Linux, and an actual full-store recovery drill. The modeling snapshot
test proves SQLite WAL and byte preservation, not a running WhatsOpt restore.
These are required before advertising a coherent backup or enabling lifecycle
backup/restore. Existing lifecycle operations continue refusing that completion.
