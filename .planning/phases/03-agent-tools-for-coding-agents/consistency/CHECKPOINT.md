# Consistency checkpoint: decisions and retired surfaces

Owner decisions and their authority are in [DECISIONS.md](DECISIONS.md). This checkpoint covers the decision records and contract wording, and the removal of retired surfaces.

## Commits

- `afb35e6` Record the study brief, study answer and calculation decisions (ADR-0007 to ADR-0009, ADR index including 0006, glossary, decisions, specification notes).
- `57275ee` Remove case wording and the unaccepted case_id parameter from the contract (generator, regenerated OpenAPI, checker comment). The usage route already rejected `case_id` with 400.
- `39295da` Remove retired navigation, statement and dashboard surfaces (WorkflowNavigation, ClaimButton and statement sets, the unused recent-runs dashboard, the retained-run assumption projection, the source-only dialog, the run-history link that opened Home).

## Checks

All through `./hyprn-mvp dev check <group>` with a dedicated scratch root and the demo port declared in `HYPRN_MVP_LIVE_PORTS`.

| Group | Result | Tree |
|---|---|---|
| contracts | 127 passed | after `57275ee` changes |
| approach-contracts | 152 passed | same |
| approach-api | 25 passed | same |
| answers-api | 25 passed | same |
| exploration-contracts | 31 passed | same |
| guard | 117 passed | same |
| hygiene | passed | same |
| naming | 1 failure, not from this work: five tracked file names under `contour-design-system/` (`03-01-PLAN.md`, `03-01-SUMMARY.md`, `checkpoints/3.C1.md` to `3.C3.md`, committed in `951b856`) carry work-item numbers | same |
| combined-static | 9/9 stages | working tree that became `39295da` |
| ui-navigation | 18/18 | same |
| ui-reading | 33/33 after removing the statement-set assertions of the deleted ClaimButton | same |
| units-ui-reading | 13/13 | same |
| ae-ui-evidence | 13/13 | same |
| foundry-nav | 10/11; the failing 200% zoom test failed identically before this work | same |
| term scan | 4 findings, identical to before | committed tree |

The first guard run failed only because `HYPRN_MVP_LIVE_PORTS` was unset in the shell (empty live-port list); it passed once the development host's live ports were declared.

## Deferred, with reason

- Comparison removal waits for the browser-suite session's branch, because it deletes tests in `ui/tests/unit-history.spec.ts`, which that session is migrating.
- Help keeps its study view: placeholder destinations preserve study context by the 2026-10-17 authorization.
- The Settings page title ("Profile") moves to the wording contract batch.
- The opt-in fidelity suite still names the deleted dashboard; it cannot run without reference images and is retired with the approach suites.

## Remaining risks

The migration batches (study brief, calculations, study answer, model explanations, approach removal and development-store reset) are planned, not started. No live demo record changed in this work.

## Page contract (B3)

Commits: `000ff78` one page header, return and version vocabulary; `cfcbd2a` focus returns to a visible control after nested editors close (with the migrated model authoring, model assumption and isolated history suites); `b215158` page-header commands share one row with the version choice.

- PageHeader, ReturnLink and VersionSelect are the shared recipes on Studies, Models, a model, Evidence, Settings, configurations, run history and runs; collection rows use ResourceCard. The account area shows the signed-in identity; Settings is the one way to the Settings page.
- `ui/check_component_ownership.py` rejects local heading, return and row classes, "Back to" or arrow returns and hand-built version labels; screen CSS may not style the new header classes.
- Product fixes found while migrating tests: the quantities dialog returned focus to a hidden button; a refused component save focused a source editor hidden in another tab; cancelling an evidence version change lost focus when its panel had closed.

Final run on the committed tree (`./hyprn-mvp dev check <group>`, dedicated scratch root):

| Group | Result |
|---|---|
| combined-static | 9/9 stages |
| contracts | 127 passed |
| ui-navigation | 18/18 |
| ui-reading | 33/33 |
| units-ui-reading | 13/13 |
| ae-ui-evidence | 13/13 |
| foundry-nav | 11/11 (the 200% zoom test that failed before this work now passes) |
| ported-isolated | 17/17 |
| units-ui-authoring | 13/13 (was 5/13) |
| ae-ui-model | 6/6 (was 4/6) |
| term scan | 4 findings, unchanged |

The CSS-only follow-up `b215158` was rechecked with combined-static, foundry-nav, ui-reading and ui-navigation. The committed UI was published to the local demo as a static refresh with the runtime unchanged, and a before/after atlas of the record and collection pages was captured with no writes.

Tests rewritten rather than migrated: the editor-guard test now protects one write for a pending component edit, because the quantity metadata paste control no longer renders; the run-history race test now protects one in-flight list read applied once, because a second overlapping read cannot be started from the history screen.

Remaining risks and obligations:
- The quantity metadata paste code is still present but unreachable from the interface; deleting it needs the owner's OK.
- The overlapping-response guard in the run-history list is no longer exercised by a browser test.
- Number and unit display rules (decimal separator, repeated "Dimensionless", rounded slider bounds, currency units) move to M3 with the exploration rebuild; "Dimensionless" must stay explicit under the units invariant.
- Still open on pages that survive: the sidebar sits lower on long pages, the floating Assistant button covers content, the model graph shows raw port names, and the study title is absent on Model and Run pages.
- Not run in this batch: the configuration, run-history, exploration and approach browser groups, which the migration batches rewrite or delete.

## Study brief (M1)

Commits: `cd98f77` brief record and public API; `897f647` objective order as the first ranking rule; `efc8ccb` formatting; `061c78e` agent tools that read and change the brief; `a84a627` Overview brief reader and editor.

Final runs (`./hyprn-mvp dev check <group>`, dedicated scratch root):

| Group | Result |
|---|---|
| brief-api | 19 passed |
| agent-tools | 281 passed |
| contracts | 127 passed |
| guard, hygiene | OK |
| brief-ui | 2/2, twice in a row on the final tree |
| ui-navigation | 18/18 |
| ui-reading | 33/33 |
| foundry-nav | 11/11 |
| ported-isolated | 17/17 |
| approach-ui-reading | 18/18 |
| units-ui-reading | 13/13 |
| ae-ui-evidence | 13/13 |
| combined-static | passed |
| agent-ui | 14/25: the same 11 failures on the committed tree before M1 (attribution chips looked up under page-header classes replaced in B3); none added |
| term scan | 4 findings, unchanged |

Product faults found by the browser runs and fixed before commit: a brief read in flight counted as unsaved work in the navigation guard; a never-opened brief refused the guard's save and stopped the save sequence before evidence.

Remaining risks and obligations:
- Local agent sessions are still offered read tools only (`LOCAL_STAGE = 'read_only'`, read-only local delegations); agent writes and their attribution are the separate agent-writes session.
- Overview still shows the approach's "About this study" question beside the brief until the approach is removed (M5).
- The running demonstration predates the brief routes; its application must be restarted before the new UI is published to it.
- The 11 agent-ui failures above are open.
- The style ratchet fails on many files changed since its base, mostly earlier work; files added in M1 are formatted.

## Page width (B3 follow-up)

Commit `ba1ccb8`. Fixes before commit: the specimen inventory gained a `ContentColumn` specimen; the approach Overview test locates the reading column instead of the retired `.approach-overview` wrapper; Home overflowed at 200% zoom because screen rules gave column children an inline `auto` margin, which shrinks a flex child to its content width; screen rules on column children now set block margins only.

| Group | Result |
|---|---|
| design checks | no FAIL; tokens fresh; tooling tests OK |
| ui-reading | 33/33 |
| foundry-nav | 11/11 |
| approach-ui-reading | 18/18 |
| combined-static | passed |
| brief-ui | 2/2 |
| ui-navigation | 18/18 |
| ported-isolated | 17/17 |
| units-ui-reading | 13/13 |
| ae-ui-evidence | 13/13 |
| term scan | 4 findings, unchanged |

## Calculations (M2, slice 1)

Commit `dcfaffb`: calculation versions, criterion bindings, run evaluation and reference marks in the store and the public API (`calculations.py`, `routes/calculations.py`, `test_calculations_api.py`, contract and UI types regenerated, additive only). Owner decisions on evaluation are in `DECISIONS.md`.

Final runs on `dcfaffb` (`./hyprn-mvp dev check <group>`, dedicated scratch root):

| Group | Result |
|---|---|
| calculations-api | 25 passed |
| brief-api | 19 passed |
| contracts | 127 passed |
| approach-contracts | 152 passed, guard OK |
| guard, hygiene | OK |
| combined-static | passed |
| agent-tools | 281 passed (run before the last ownership change, which touches no agent tool) |
| locality-contracts | 10 failed, 154 passed: the same 10 failures on `ba1ccb8` (versioned approach error messages); none added |
| term scan | 4 findings, unchanged |

Found and fixed before commit: model-association and run-association reads had been written in the calculation module; the module-boundary guards require them in `store` and `history`, so the module now uses `Store.model_association` and `history.calculation_runs`.

Remaining risks and obligations:
- The runs read evaluates each run from its integrity-checked record, so a page of 20 costs 20 retained reads; acceptable for hand-picked sets, to be measured when sampled calculations arrive (slice 4).
- Configuration criteria still exist until slice 3; run records keep their own `violated` outcomes beside the new evaluation.
- No UI or agent tool yet (slices 2 and 5); the running demonstration predates these routes and needs a restart before the UI uses them.
- The 10 locality-contracts failures were resolved afterwards (below).

## locality-contracts repair

The 10 failures had three causes: the brief (M1) and calculations modules were missing from the module-boundary layer table, route owners and the architecture's allowed-imports table (4 tests; `1645043`); the approach error test still sent the retired `cases` field (3 tests; `1645043`); three identity-golden bundles were captured with `cases` before `5713d58` retired it (3 tests; retired by owner decision, see `DECISIONS.md`).

| Group | Result |
|---|---|
| locality-contracts | 162 passed (was 10 failed, 154 passed) |
| guard, hygiene, approach-contracts | OK, 152 passed |
| brief-api, calculations-api | 19, 25 passed |
| agent-tools | 281 passed |

## Calculations area (M2, slice 2)

Commit `ef048a8`. Owner choices (2026-10-18): Calculations is the area's first tab; this slice reads, creates and versions calculations; reference marks are included.

| Group | Result |
|---|---|
| calculations-ui (new; real application, modeling service declared offline) | 3/3 |
| ui-navigation | 18/18 (three tests now open the Configurations tab after entering the area) |
| foundry-nav | 11/11 |
| ui-reading | 33/33 |
| approach-ui-reading | 18/18 |
| ported-isolated | 17/17 |
| units-ui-reading | 13/13 |
| ae-ui-evidence | 13/13 |
| brief-ui | 2/2 |
| ui-a | 9/9 |
| combined-static | passed |
| calculations-api, guard, locality-contracts | 25 passed, OK, 162 passed |
| design checks | no FAIL; tooling tests OK |
| term scan | 4 findings, unchanged |

Found and fixed before commit: the editor dialog loaded configurations, a frozen model and the brief while still closed, so every list read them (`ActionDialog` gained `onOpen`); the bindings panel and its table shared one landmark name; seeded configurations shared one identity across studies.

Remaining risks and obligations:
- Screenshots (light, dark, 720 px) were reviewed by the agent only; owner acceptance of the screens is not recorded.
- The list shows calculations whose latest version uses the selected model version; older versions on another model version are reachable only by link.
- No unsaved-changes guard: the editor is a modal dialog, and Cancel discards it.
- The running demonstration predates these routes and must be restarted and republished before it shows them.
- Agent tools for calculations wait for the agent-writes branch (slice 5).
