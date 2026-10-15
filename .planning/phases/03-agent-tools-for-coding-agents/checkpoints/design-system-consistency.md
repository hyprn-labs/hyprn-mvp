# Design-system consistency pass — 2026-10-15

## Scope and implementation

User authorized completion, commit and refresh of the existing local demo.
[Discrepancy inventory](../../../../design-system/Consistency.md) records observed
problems, shared ownership, corrections and acceptance. The live Study details
inspection found compact actions overridden to desktop geometry, unequal assumption
and limit rhythm, and empty source wrappers adding space.

Shared Button now owns complete size/variant/icon recipes and touch targets.
Assertion, EvidenceStack, ReadingSection and ActionGroup own their composition.
Consumers use these owners; panel/table padding, dialog/form rhythm and wrapping
are consolidated. Charcoal, source relationships, exact identities and edit guards
remain. Assumption choices use the existing version-aware record readers.
A real-component specimen and a no-baseline ownership guard prevent recurrence.
No dependency, API, persisted format, numerical runtime or live study data changed.

## Focused verification

Commands use the pinned local-edition entry point and isolated test stores:

- `./hyprn-mvp dev check combined-static`: 9 stages pass, including design/token
  checks, ownership guard, UI contract guard, tooling tests, TypeScript and build.
- `./hyprn-mvp dev check style-ratchet`: 33 tests pass before the final commit.
- `./hyprn-mvp dev check approach-ui-demo`: 5 tests pass. Covers actual
  product/HTTP/API authoring and reads, evidence counts 0/1/2, validation/focus and
  cancellation, exact case navigation, five views at genuine browser 200% zoom,
  light/dark, 360px layout, wrapped labels and 48px coarse-pointer targets.
- Screenshots inspected: desktop light and narrow dark assertions, with readable
  source titles, consistent intervals and reachable dialog controls.

The browser fixture uses a declared private modeling transport and synthetic failed
run handoff; it does not prove numerical execution. The live verification is read-only.
Committed-tree results and live artifact identity are recorded below after delivery.

## Corrected failures

- Initial static checks: obsolete assumption CSS-name assertion and a ReactNode/
  boolean class expression; corrected the composition guard and boolean conversion.
- Formatting: changed long lines and new-file formatting; corrected without changing
  source text semantics. A `style` command typo was refused; used `style-ratchet`.
- Zoom fixture: adding assertions after the historical-run fixture failed reference
  resolution. Use a separate valid authored study for the assertion zoom journey;
  preserve the historical fixture for its original exact-case checks.
- Final consolidation exposed remaining panel padding, a malformed media-rule suffix
  during CSS cleanup, and legacy direct assumption reads caught after formatting.
  Removed the override, fixed CSS, and used existing recordViews helpers.

## Limits and remaining obligations

This is a local demo UI delivery, not full release qualification or human acceptance.
Other host/browser qualification and stale older reading-suite expectations remain
with their existing owners. No push or publication. Unrelated ROADMAP changes are
preserved. Test artifacts remain outside the repository; cleanup and delivery follow.
