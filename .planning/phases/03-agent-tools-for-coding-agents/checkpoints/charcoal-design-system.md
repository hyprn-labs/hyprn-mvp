# Charcoal design system and canonical brand asset

User-approved Option B, conveyed by the design assessment chat on 2026-10-15.
Target: existing local demo. Acceptance: shared neutral interaction roles in both
actual application themes, distinct blue keyboard focus, preserved scientific
status/provenance/assistant roles, unchanged logo and usable pages at 200% browser
zoom. No scientific record, API, numerical capability or worker changes.

## Delivered

Approved Charcoal colours live in tokens.json and generated tokens.css. Quiet
link-style actions are underlined; tabs and buttons retain their boundaries.
Source syntax has its own neutral roles instead of warning/success/action colours.
The inverse record bar has a contrasting blue focus token. The light control border
was darkened slightly to meet 3:1 on the new sunken ground (previously 2.94:1).

BrandLogo owns one imported asset under ui/src/design/assets/brand, the accessible
name and theme-independent light plate. The public duplicate is removed. Vite owns
the base-aware hashed URL; explicit no-inline import works with the self-only CSP.
Original PNG SHA-256 remains
`3ec5f72242e291ff570315ea60ae7b669ce20e8dea20d62d7a712e3d74b9ac43`.
No dependency added. Export diagrams retain their centralized fixed print palette.
Design rules and provenance describe these ownership decisions.

## Verification

All checks run through the scoped local-edition entry point. Final committed-tree
results are recorded below. Development evidence is retained outside the repository
in the hyprn-charcoal folder and identified scratch scopes.

- combined-static: all eight stages pass, including design/token/contract checks,
  design-tooling tests, shared-component render smoke, contrast/render tests,
  TypeScript and production build (scope 9822a26f-3195-42b0-803c-04c8b3a6976d).
- approach-ui-demo: 3 passed, no skipped, including both themes on Overview, Models,
  Configurations, Runs and Cases at browser zoom 2.0 and 720 CSS-pixel width
  (scope 8a2103f9-d60c-47ae-9547-66999c71cd3e). No horizontal page overflow;
  source asset loads, record states remain visible and keyboard focus is blue.
  Subsequent editor-specific syntax/hover checks are included in final verification.
- Corrected development failures: control-border contrast (2.94:1); a test looked
  for highlighted keywords in the plain saved-source reader (highlighting belongs
  to the editable source surface); a hover assertion read before the CSS transition
  completed; changed-line/new-file formatting violations.

The browser uses real product HTTP/API/auth/store boundaries with a declared private
modeling fixture and retained failed-run fixture; it does not execute numerical code.
Screenshots were visually inspected. Automated checks are not human acceptance or
full release qualification. Older reading-suite reconciliation and external-release
legal/source-offer review remain with the maintainer, as recorded in demo-polish.md.
Unrelated ROADMAP changes are preserved. No push or publication.

Next stopping point: checked static build served by the existing demo, evidence
archived and completed test scopes released; then user visual review.

## Committed delivery

Implementation `0f6328f` passed the focused committed-tree checks:

- `./hyprn-mvp dev check combined-static`: eight stages pass, 4.36s,
  scope `6470b3c8-cae6-499d-81ca-eec598415877`.
- `./hyprn-mvp dev check style-ratchet`: 33 passed, 0 failures, 9.29s,
  scope `3f4fc0a3-ce65-4451-b7c8-b78c4adec05e`.
- `./hyprn-mvp dev check approach-ui-demo`: 3 passed, 0 failures/skipped, 34.65s,
  scope `cdcdce67-5d55-41fd-8eab-bdd17bc56aa5`. This includes actual editor
  keyword weight/colour, string/number colours and primary-hover transition in
  both themes, plus genuine browser zoom across all five study views.

The checked static build is served by the existing demo. Live browser sign-in and
study display verified the hashed same-origin logo, loaded image, fixed light ground
and Charcoal token; screenshots are saved externally. No service restart or study
mutation. `ui-manifest.json` in the external hyprn-charcoal folder identifies build
files and commit. All twelve identified completed scopes were identity-checked,
evidence archived and scratch stores removed; `cleanup.json` records the results.
The live demo remains available. This last checkpoint delta is documentation only.
