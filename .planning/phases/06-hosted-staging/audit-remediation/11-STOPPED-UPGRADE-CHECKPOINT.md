# Preserve unresolved work during a stopped upgrade

## Implementation

A fully stopped installation may contain unresolved execution records. They are
not themselves active writers. Migration now proves closed admission, stopped
native/app/modeling/dispatcher owners and detached workers, and no active request
lease or Assistant turn. The read-only `stopped-work` database owner operation
uses the already scoped migration credential, exposes counts only and requires no
schema change. Pending/uncertain rows and payloads are never updated or retried.
Running owners still follow the normal drain path; unknown ownership fails closed.
Only migration permits previous-release images of stopped known services. Backup
and ordinary inspection retain exact-image checks.

Platform commit `155ae61` accepts an explicit successful inspect receipt as the
schema observation alongside the existing stop receipt. Existing drain receipts
remain supported. Inspect is never relabelled drain. Native process termination,
continuous deployment/product/executor/AiiDA holds, repeated stopped-writer/worker
checks and coherent SQL/files verification remain strict.

## Verification

Commands use the existing reviewed data/tools roots and explicit sibling platform
root; all stores and containers belong to scoped fixtures.

- `./hyprn-mvp dev check hosted-lifecycle`: 21 passed, 0 failed (10.798 s tests).
  Private log `/private/tmp/hyprn-stopped-upgrade-lifecycle-final.log`.
- `./hyprn-mvp dev check platform-backup-set`: 19 passed, 0 failed (10.867 s tests).
  Private log `/private/tmp/hyprn-stopped-upgrade-backup-final.log`.
- Earlier lifecycle run: 3 errors (fixture live-name fence, fixture foreign-study
  insertion authority, accumulated fence teardown). The real one-off container
  test now explicitly doubles worker inventory and the fixture administrator
  creates foreign data; production counts remain migration-role read-only.
- Earlier backup attempt failed before test collection when the existing global
  storage inventory raced a concurrently removed fixture container. Groups were
  then serialized, with explicit HYPRN_PLATFORM_ROOT. No fence was relaxed.
- Final later deltas are line wrapping and this evidence document only.
- Scoped runners exited 0 and released their fixtures. No live operation or study
  write occurred. The parent owns reviewed recovery/deployment and public checks.

## Integration

The existing normal platform reconciler still performs ordinary drain. For this
explicit stopped-owner recovery, close admission, verify no active provider turn,
stop the old release, collect its successful inspect receipt, then pass only
`inspect_operation_id` (not a drain ID) to the updated `backup_set.create` helper.
Retain the coherent backup before new migration. The incoming migration has its
own independent stopped/remote-activity checks. Do not manufacture a successful
drain receipt, alter uncertainty, retry a model or send an Assistant message.
