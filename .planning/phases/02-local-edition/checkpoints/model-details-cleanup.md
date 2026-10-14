# Model details, quantity filters and run exports

Date: 2026-10-14. Scoped demo follow-up under DELIVERY-PLAN.md; no phase closure.
Implementation: `d2f553db95e12307e7f2738c5c0dc42f07c2fc83` from `2c399e8`.

## Delivered behavior

- Remove the Components toggle, panel, presentation ordering state and related CSS;
  graph/XDSM selection, search, source access and the Details toggle remain.
- Remove the quantity Availability filter. Zero, unassigned values, missing outputs
  and their reasons remain distinct. Search/component/direction filters remain.
- Model details show the selected name once. The linked step's shared transformation
  is accurately labelled Method context; purpose/rationale appear under Why this
  method without repeated step/version lines or empty purpose/rationale placeholders.
  Exact approach/model pins remain in Method record and direct step navigation.
- Known-empty read-only assumption sections disappear; unreadable/older-format states
  and editable assumption controls remain. No source or scientific record is rewritten.
- Run exports are adjacent in one wrapping action group. Both export workflows,
  receipt recovery, authorization and frozen records are unchanged.

The reported escaped Purpose text is absent from the preserved demo input records:
step purpose, rationale and transformation are plain strings, not Document payloads.
The old UI added bold labels; the new UI renders authored strings as plain paragraphs,
without decoding entities, parsing Markdown or removing scientific syntax.

## Verification

Commands run on the implementation tree; final documentation delta is this checkpoint.

| Command | Result |
|---|---|
| `./hyprn-mvp dev check combined-static` | 6 commands pass, 0 fail |
| `./hyprn-mvp dev check style-ratchet` | 33 tests pass, 0 fail |
| `./hyprn-mvp dev check foundry-nav` | 8 tests pass, 0 fail/skip/flaky |
| `./hyprn-mvp dev check ui-reading` | 15 tests pass, 0 fail/skip/flaky |
| `./hyprn-mvp dev check ae-ui-configuration` | 14 tests pass, 0 fail/skip |
| `./hyprn-mvp dev check ui-c` | 11 tests pass, 0 fail/skip |
| `python3 ui/test_design_tooling.py` | 13 tests pass, 0 fail |
| `node ui/design_smoke.mjs` | all checks pass, 50 renders |
| `./hyprn-mvp dev check naming` | 9 tests pass, 0 fail |
| `./hyprn-mvp dev check hygiene` | 5 tests pass, 0 fail |
| `git diff --check` | pass |

The last two design checks use the UI skill's explicit commands. Static includes
current design tokens, UI contract wiring, TypeScript and an isolated clean Vite build.
Browser checks cover absent controls, retained unavailable-output reasons through
filtering, both exports' adjacency and real API export flow, themes and genuine 200%
zoom. Light/dark model screenshots were visually inspected. The scientific fixture
uses transport doubles and never executes candidate code. Live demo and human
acceptance remain the orchestrator's separate checks.

Failures corrected before the passing run:

1. Initial static run: 2 commands passed, UI wiring failed because formatting changed
   an unrelated RunPanel source-text assertion. Restored untouched markup; the export
   placement change is local. No contract expectation was weakened.
2. Next run: static passed; style had 32 passing tests and 1 failing test, identifying
   four changed-line length violations. Wrapped those lines without baseline edits.
3. The passing configuration fixture logged BrokenPipeError on canceled reads; all
   14 assertions passed. It did not alter the checked outcome.

## Evidence and cleanup

External evidence archives: `hyprn-orchestration-verification-_cxlpmwt` (first static
failure), `hyprn-orchestration-verification-8o0qsbsj` (style failure), and
`hyprn-orchestration-verification-5ikc3igu` (all six passing groups), plus
`hyprn-orchestration-verification-o6le74si` (checkpoint naming/hygiene). Their `results.json`,
per-scope result/source identities, browser reports, screenshots and `release.json`
retain exact commands, timings, artifact identities and cleanup. All 11 owned scopes
released; 0 remain. The standalone design-smoke scratch scope removed itself.

No live demo, authoring records, API schemas, backend state, dependencies, attested
runtime inputs or other worktrees were changed. Opt-in ui-fidelity was not invoked:
its required design-system/reference directory is absent. Full qualification and
release acceptance remain deferred. The orchestrator owns integration and its union
of acceptance groups, plus the separately edited approach-reading regression.
