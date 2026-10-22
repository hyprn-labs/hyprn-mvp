# Grouped application sidebar — 2026-10-17

User requested the open reference application's left navigation structure adapted
to HYPRN, including honest destinations for unimplemented features. Implemented
in `73390d1`; short-window and collapsed-card corrections in `69aaac4`.

The shared NavigationRail owns brand/collapse, All studies, current study card,
Overview, Workflows (Models/Calculations), Library (Evidence/Documents), bottom
Help/Settings/account and Sign out. Documents and Help render FeatureUnavailable.
All navigation keeps the existing unsaved-work guards; collapse persists locally.
No dependencies, backend changes or authoring mutations. The design-system
NavigationRail contract explicitly replaces the old prohibition on placeholders.

## Verification

All checks used the pinned local entry point in an isolated snapshot; the 15 owned
paths were verified byte-for-byte against `69aaac4` before final qualification.

- `./hyprn-mvp dev check combined-static`: 9/9 stages passed, 0 failed, including
  design/ownership/token/contract guards, tooling, node tests, TypeScript and build.
  Final committed scope: `25c488ec-9372-4325-8d42-a8725fe82164`.
- `./hyprn-mvp dev check ui-navigation`: 14 passed, 0 failed/skipped/flaky.
  Final scope: `804bfc9a-3170-4ba2-9d68-b8b943640817`. Covers protected unsaved
  edits, placeholder deep links after sign-in, persisted collapse, real evidence
  navigation, one Sign out action, light/dark at 1440/720/390, no horizontal
  overflow, a 703px-high desktop and compact collapsed study cards.
- Real local browser: Documents and Help placeholders, collapse/expand, Models,
  Calculations, Settings/Profile, All studies and reopening a study verified.
  No saved study/model/evidence/configuration/run was modified.

## Isolation and failures

Concurrent primitive/appearance changes remain unstaged and out of this delivery.
Initial navigation check: 9 passed/5 failed because copied concurrent tests expected
new model/theme behavior and because the reload assertion omitted sign-in. Rebuilt
baseline tests with only this task's delta; next run 13 passed/1 failed, confirming
the missing sign-in. Corrected the public login journey; subsequent runs 14/14.
An initial snapshot transformation missed the parenthesized overview branch;
corrected it before final verification so placeholders avoid modeling reads.
Visual review found short-window overflow and inherited mobile flex-basis stretching
the collapsed study card. Fixed both and added observable geometry assertions.

The first index write required sandbox escalation; the next attempt added four
paths before refusing a new file without --add. Reconciled the exact index and
finished staging safely. A commit hook rejected private reference names in two
design documents; replaced them with portable descriptions and committed. No hook
was bypassed and no concurrent content was staged or reverted.

Evidence, source hashes, screenshots and recovery index are outside the repository
under the task's temporary navigation folder and scoped check evidence store.
Ephemeral browser/check scopes were released by the runner; retained static build
scopes and the isolated source remain for delivery/recovery. Live UI delivery also
retains the prior, unrelated export-scope spacing delta (space-5 to space-6), as did
the previous live baseline. It is not included in these commits.

Human visual acceptance and complete product release qualification remain separate.
Documents/Help backend functionality remains unimplemented. Integration and release
of concurrent primitive/appearance changes belongs to that work's owner.

## Final live delivery

`combined-static --keep-scope`: 9/9 stages passed on the live delivery snapshot,
scope `ce0f3f1d-5b83-48b8-ab25-b36905fcde8c`. UI-only deployment used source,
index and runtime hash guards plus an index backup; runtime descriptor unchanged.
At the real 1512 × 703 viewport the final rail content and client height both
measure 653px: no internal overflow. Documents deep-link reopening after login
and final collapse/expand were verified again. Screenshots: `sidebar-live.png`
and `sidebar-collapsed-live.png` in the temporary navigation evidence folder.
