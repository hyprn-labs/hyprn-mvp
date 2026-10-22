# Reference badge spacing — 2026-10-19

Implementation 2937125: ConfigurationList uses the existing shared hf-record-metadata
row and a separate input-count span. The space-2 gap owns badge/text clearance and
wrapping; StatusTag guidance documents this composition. Browser checks measure actual
clearance at 1440, 720 and 390 widths, with explicit light/dark themes, and retain
mark/unmark persistence and unchanged configuration-data assertions.

Delivery snapshot: committed base 446b5b8 plus ConfigurationList, StatusTag guidance and
calculations.spec.ts from this change. These UI/test files match implementation 2937125.
The snapshot excludes concurrent unfinished run-summary/state-color changes. Concurrent
StatusTag record-state guidance was included in the same commit; its implementation
belongs to the other UI session. No runtime or scientific records changed.

Verification through ./hyprn-mvp dev check:
- combined-static --keep-scope: 9/9 passed, 6.08 s; build scope
  abbcc30a-ca33-4e6d-997a-513b4b1d29e0.
- calculations-ui: 6/6 passed, no failures/skips, 46.34 s; scope
  78fc8c04-007d-44f5-8e13-2507e18d2b05 released by the runner.
- Earlier integrated-working-tree browser: 6/6 passed, 42.16 s.
- Earlier static attempts: default tool cache permission/incomplete Python failures;
  verified development cache resolved startup. Integrated static then stopped at an
  unrelated in-progress RunPanel contract assertion; stable snapshot passed all checks.

Logs, inspected desktop-light/narrow-dark screenshots, recovery index and delivery
fingerprints are outside the repo under /private/tmp/hyprn-reference-spacing*.
Seven verified UI assets published to the existing local app; source/live-index/runtime
fingerprints checked and runtime unchanged. Retained static scope supplies build evidence.
Browser fixtures use actual API/auth/stores and data-only scientific records; no numerical
execution or full release qualification claimed. Human visual acceptance remains separate.
