# Shared details dock — 2026-10-17

Implemented in `d49c486`. User requested the same shape and dimensions for all
contextual details. `DetailsDock` owns tokenized width and viewport height;
`DetailsLayer` retains Back state without an auto-height wrapper. Statements,
evidence and custom supporting-result readers share this dock. Native-dialog
readers use the same geometry inside their existing modal boundary. Embedded
model inspectors retain the workbench layout. CSS ownership guards cover both
new primitives; the component contract and Layouts document the rule.

## Verification and delivery

Run through `./hyprn-mvp dev check` using the pinned local toolchain:

- `combined-static --keep-scope`: 9/9 stages passed, including design guards,
  token generation, UI contract, 17 tooling tests, 15 node tests, TypeScript and
  production build. Scope `387ec14e-4a6b-4182-8a3e-d4653eb3ab8d`.
- `ui-navigation`: 13 passed, 0 failed/skipped; includes equal statement/evidence
  dimensions at 1440 and 720, native-dialog ownership, Back, Escape and focus.
  Post-commit acceptance: 13 passed, 0 failed/skipped, scope
  `0b6432da-0192-464f-b1f1-e86720a0cc3a`.
- `ae-ui-evidence`: 13 passed, 0 failed/skipped; actual local HTTP application
  fixture, evidence saving/history and independent assistant behavior. Scope
  `721db394-2848-4d01-862f-09b6f223250c`.
- Real app `http://127.0.0.1:54821/ui/`: Statement, Evidence and Supporting results
  each measured 360 × 968 px with 24 px rounding at 1440 × 1000. Dialog-hosted
  Statement and Evidence measured the same, at y=16. Back and Escape restored
  the invoking control without closing Study details. Assistant expansion/hide
  retained and restored the full-height Supporting results reader.

UI assets deployed with source/index/runtime hash guards and an index backup.
The backend and runtime descriptor were unchanged. Screenshots, deployment
manifest, source identity and recovery index are outside the repository under
`/private/tmp/hyprn-details-panel/`; final screenshots include statement-live.png,
evidence-live.png, dialog-live.png and results-live.png. Browser fixture screenshots
cover light/dark and 1440/720 widths. This is automated verification, not human
acceptance or complete product qualification.

## Isolation, failures and remaining obligations

Other work changed the shared checkout during checking. Initial combined-static
failed on two unrelated missing Association.name types; initial ui-navigation
had 11 passes and 2 failures for concurrent theme/model-name changes (the new
geometry regression passed). No unrelated source was reverted or staged.

Delivery was isolated from parent `7f4493a` plus `d49c486`'s exact changes and the
pre-existing, unstaged export-scope spacing correction (space-5 → space-6), which
was already present in the live UI baseline. The snapshot's owned files were
verified byte-for-byte against the commit with only that recorded delta. Its
static and browser suites passed. An initial archive extraction attempt failed
because system Python lacks tarfile's filter argument; checked local Git archive
member paths and retried successfully. No live side effect occurred on failure.

Ephemeral browser scopes were released by the runner; evidence was retained in
its `.hyprn-checks` store. The isolated source snapshot and successful static-build
scope are retained for delivery provenance/recovery. Integration of concurrent
primitive/appearance work and its qualification belongs to that work's owner.
No evidence records, saved versions, runs or user authoring data changed here.
