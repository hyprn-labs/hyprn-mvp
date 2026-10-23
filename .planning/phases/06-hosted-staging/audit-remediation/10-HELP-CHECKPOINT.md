# Help center checkpoint — 2026-10-23

Implementation commit: `6e0b7a14`.

Delivered a shared read-only Help center from Home and the current study. Seven
interactive topics explain the workflow and its primitives, version behavior,
sampling roles and validation, exploration, evidence and Assistant recovery. The
four-step overview and concept cards use a token-owned Contour recipe with container
queries, named topic navigation, keyboard activation and heading focus. Existing
unsaved-edit guards and study context are preserved. No API mutation, study content,
model execution, sampling or accuracy behavior changed.

## Evidence

- `ui/node_modules/.bin/tsc --noEmit -p ui/tsconfig.json`: pass on integrated
  Help/progress tree. Initial attempt overlapped progress contract generation and
  reported missing `AssistantConversationRead5` in that unfinished lane; repeated
  only after generated contract was available, then passed. No Help type error.
- `python3 ui/check_design_system.py`: no new violations; existing six exports.ts
  baseline warnings only.
- `python3 ui/design_tokens.py --check`: fresh.
- `python3 ui/check_component_ownership.py`: zero violations.
- `node ui/design_smoke.mjs`: all checks pass, 120 renders. Existing React list-key
  warning in Button specimen remains; no failure. Log retained outside repository.
- `./hyprn-mvp dev check ui-navigation`: shared run performed by progress owner,
  **45 passed, 0 failed/skipped/flaky, 49.45 s**. Includes Help navigation, dirty
  editor protection, no writes, keyboard interaction and every topic at widths
  1440/720/390 in light/dark. This one integrated run covers both UI lanes.

Logs: `/private/tmp/hyprn-task10-help-smoke.log` and
`/private/tmp/hyprn-task10-progress-navigation.log`.
Archived browser evidence lives beneath check storage
`2fd36059-7743-4ee2-bc45-5bbcd9add945`, scope
`ef613131-2164-469f-bad5-1852d001fd04` (scoped runtime released by runner).
`nav/help-1440-dark.png` and `nav/help-390-light.png` inspected visually: hierarchy,
card separation and responsive reading are intact. Existing floating Assistant
launcher remains the shell’s common behavior on narrow screens.

This is isolated browser evidence with API doubles, not a live deployment claim or
human acceptance. Parent owns staging publication, real public smoke and integrated
release checks. No duplicate browser group is needed unless relevant source changes.
