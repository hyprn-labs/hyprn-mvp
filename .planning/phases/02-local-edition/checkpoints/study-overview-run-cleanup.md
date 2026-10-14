# Study overview, evidence and run presentation

Authorization: user feedback following the Study details demonstration, within the focused
local demo delivery plan. Implementation commit: `8453b83`, based on `cdc6e08`.

## Delivered behavior

Overview has one About this study card. Its Study question comes from the latest saved
approach through the existing fenced read, never from the draft or study-list description.
Loading, unavailable, retry, absent-version and denied states retain their distinctions.
The card omits repeated approach scope. See more details and View modeling approach share
a wrapping action row with token spacing. The separate Edit study dialog preserves the
name and description writer, labels the latter Study list description, and explains where
the question is edited. Metadata attribution stays with that editor.

Limits use the compact evidence row composition used by assumptions. Evidence detail leads
with its title, original content and inert source references. Relationships use plain
language; conflicting evidence remains visible. Version and stored scope/resource metadata
remain inspectable in Record details, and downloads preserve the complete evidence record.

Run Results contains one complete output table, with Output, Value and Units columns. The
arbitrary first-four preview is removed. Missing outputs retain not computed and their
reason in the Value cell. Full precision remains available. Export model and data names the
existing portable model/diagram/quantities/source capability; Export computational record
still identifies the complete computational archive. Run export help points to that run's
Model tab, avoiding a change to the current model.

No API, numerical model, runtime or stored scientific content changed. Formatting expansion
is limited to touched syntax nodes; no design or style baseline was amended.

## Executor verification

All group commands used `./hyprn-mvp dev check <group>` in the isolated worktree with the
existing development environment and scoped OS temporary fixtures.

- `style-ratchet`: 33 passed, 0 failed. After that pass, the final delta restores untouched
  RunPanel formatting and adjusts formatting-sensitive UI source guards. The root's
  integrated style run covers this final delta.
- `combined-static`: 6 commands passed, 0 failed: design checker (no FAIL), token check,
  UI contract wiring, criterion records, TypeScript and scoped production build.
- `ui-navigation`: 6 passed, 0 failed, 0 skipped, 0 flaky. The current UI talks to the isolated
  browser API double; this proves metadata edit guarding/navigation and renamed export
  controls, not the real installation or scientific workflow.
- `python3 ui/test_design_tooling.py`: 13 passed, 0 failed.
- `node ui/design_smoke.mjs`: all checks passed, 50 renders; scratch self-released.
- `git diff --check`: passed. Required commit hooks were executable; commit completed.

Final static/browser evidence: `hyprn-orchestration-verification-jjr_h8xt`; style evidence:
`hyprn-orchestration-verification-p2real7h`. Their archived scope metadata and reports keep
artifact identities and exact commands. Nine task-owned check scopes were archived and
released, zero remaining. The live demo's authoring store, services and author records were
not touched.

## Failures and corrections

Five style runs initially finished 32 passed / 1 failed because changed lines inherited
long-line debt. Range formatting exposed two test-selector syntax typos and a formatter
range-offset problem, corrected before verification. Untouched legacy test signatures were
restored; changed strings were wrapped. Evidence archives: `5nlnvr_6`, `emctpp49`, `ta18ffe1`,
`cvtl1ti4`, `5i4ivoag` (each has the `hyprn-orchestration-verification-` prefix).

One combined-static run passed its first two commands then failed source-wiring checks
because formatting changed literal source substrings. Restored untouched RunPanel wiring
and adjusted the Overview guards to the same formatted calls. The final six-command run
passed. No API behavior or security guard was relaxed.

## Remaining integration

Root owns the committed-tree union: style/static, ui-reading, ui-navigation, foundry-nav,
approach-ui-reading, approach-ui-assumptions, agent-ui, ae-ui-model, ae-ui-evidence and
units-ui-history. The executor stopped after the agreed focused navigation check to avoid
duplicating the complete union. Root also owns rebuilding the live UI and checking the real
saved question, evidence, all eleven outputs, both themes and narrow/zoom behavior.
Reference-image comparison is unavailable; automated browser checks and screenshots are
not human acceptance. No phase qualification, release, deployment or product-owner
acceptance is claimed here.
