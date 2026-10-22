# Approved overview proposal — 2026-10-16

Implemented in `f354c6d`; final section-spacing correction in `2e86e61`.
User approved the HTML proposal, requested wider figures, generic behavior and
minimal checks. No new numerical capability, backend/API change or sampling run.

Delivered: exact saved conclusion before the explorer, case-grouped supporting
results in scientific context, expandable observations/qualifications, per-assertion
evidence actions, wider response plots beside readouts, independent plot axis,
Fit width and 100% controls, readable result-basis dialogs, and Input ranges /
Sampling / Assessment tabs retaining unsaved edits. Units are typographically
formatted without changing stored unit strings or conversions.

Verification:

- `combined-static` on `f354c6d`: 9 stages passed, zero failures, 6.90 s;
  archive `6f807e01-f778-492c-a430-f18db4f55611`.
- `exploration-answer-ui` on `f354c6d`: 1 passed, zero failures/skips, 13.89 s;
  archive `12db51b4-3d2c-48f5-a4f8-300eb68dff50`. Real product/browser/HTTP,
  auth and persistence with the existing synthetic retained-failure handoff;
  this check does not produce native calculations.
- `combined-static` on `2e86e61`: all 9 stages passed, zero failures, 7.12 s;
  archive `b67f5c3c-c58f-4adf-925e-16d6e67f7d66`. The browser-tested
  implementation differs only by the final CSS sibling spacing rule. Production
  build succeeds; existing bundle-size warning remains.
- Live CUA: moved Mach and heating-value sliders together; all 11 outputs
  became saved-surrogate estimates. Changed the plot axis to range while both
  inputs retained their values. Reset restored 11 calculated outputs. All
  three settings tabs opened; an unsaved range edit survived tab changes and
  was restored without saving. Supporting results retained eight exact case
  groups. Result-basis dialog was readable outside graph styling.
- Live sampling remains 122 completed / zero failed. Outbox count stayed 405
  before and after this verification; no sampling or original runs submitted.

Commands used the host environment script and `./hyprn-mvp dev check` entry
point. The final invocations set `HYPRN_MVP_TEST_SCRATCH_BYTES=17179869184` only
for the process after the default 10 GiB quota refused admission at 12.13 GB;
90 GiB was free. No other session's retained artifacts were removed. Runner
finalization released isolated fixture scopes and archived evidence.

Earlier failures: sandbox cache access required approved execution; initial
formatting changed a quoted source pattern checked by the UI contract scanner
and was removed; no product behavior failed. Visual inspection found a legacy
flow-root rule overriding the new grid spacing, fixed by sibling panel spacing.

The checked static UI was published to the existing demo at port 54821, live
scope `f7145c6a-9848-4541-8aa4-0acf069102fb`. Assets copied before index; prior
hashed assets and previous index retained. Services, worker image and saved
scientific records unchanged. UI identity is recorded in the host ready file.
Screenshots and rollback index are outside the repository in
`/private/tmp/hyprn-overview-implementation/`.

This is automated verification, not human acceptance or full qualification.
Native sampling/refinement suites were not rerun: computation code is unchanged;
existing native evidence remains applicable, with live prediction verification
above. Next action: user review of the approved layout in the running demo.

## Follow-up: compact controls and generic details

User requested smaller numeric boxes, removal of repeated explanation sentences,
clarification of point-only plots, and closer alignment with the mockup. Delivered
in `376915e` and `7437394`: compact input editors with full-width unit captions,
data-driven category-control styling, removed global helper prose, structured
result-basis facts, readable answer sections, sampling advanced settings and
range rationale disclosures, and assessment totals derived from saved records.
No fuel-specific condition or category label was added. The category name and
options are read from `design.request.category_dimensions`.

Plot inspection found repeated discrete coordinates (99/100/101 in this example),
near-constant outputs magnified by autoscaling, and a renderer gap where isolated
estimates had no marker. Markers now remain visible across gaps, exact duplicates
are drawn once, and near-constant axes have the documented minimum display span.
The renderer neither interpolates missing values nor changes predictions.

Final `./hyprn-mvp dev check combined-static` on `7437394`: 9 stages passed,
zero failures, 10.07 s; archived check `c18dc39c-d3b5-44c6-916d-b56e28bde08f`.
Includes marker-gap, repeated-coordinate and near-constant-axis render regressions.
The earlier pass on `376915e` is `244f76a5-9a79-4c3a-9a6f-065cc62a8f05`.
Both used the same invocation-only 16 GiB scratch allowance. A build caught the
new summary reading target_met from the output instead of its metrics; corrected
before the final commit/check. Existing bundle-size warning remains.

Live CUA verified settings/assessment layout, 122 completed points, 3/3 groups,
33/33 targets, compact inputs without wrapped unit words, and 11 real estimated
outputs after two joint input changes. Baseline restored afterwards. No sampling
or original calculation requested. Static UI republished to the same live scope;
ready file identifies `7437394`. Screenshots: `refined-live.png` and
`assessment-refined.png` in the existing external evidence directory. Saved
scientific prose is preserved; the mockup's shortened illustrative text is not
substituted for the saved answer. Automated review only; next action is user review.

## Follow-up: answer authoring and editor consistency

Implementation: `d974602`, `f775c1f`, `31f80bd`, `866f160`, `7d222b1`.
The installed `/hyprn` symlink resolves to the repository skill, now with explicit
conclusion/comparison/limits field guidance and a domain-neutral behavioral
scenario. This is an instruction improvement, not evidence of a newly completed
scientific study. Existing saved answers and all exact pins are preserved.

The interpretation disclosure now has a full card header/divider and spaced
observations. Result marks share the zoom toolbar's right side; slider stop and
selected markers are smaller without shrinking the range input hit area. Quantity
row editing says Edit quantity and uses a structured, scrollable dialog with fixed
footer. Component has only its name/explanation editor; bulk quantity management
remains in Component actions. The reported assumption-editor substitution was not
reproduced: live UI opened exactly Component name and Component explanation.
Assistant opens a right-hand drawer with an unavailable message and disabled
composer/Send; no conversation transport is added.

Qualitative-input proposal remains a proposal: generic named choices from declared
category dimensions, compact segmented controls for short lists and a selector for
long lists, selecting only supported saved combinations. Never interpolate category
labels or silently carry category-owned values into a different choice. Current
category rendering remains data-driven; there is no fuel-name branch.

Verification: initial build caught an incorrect TextArea import; corrected before
commit. Skill creator quick_validate.py passed. Initial combined-static passed all
9 stages. ui-navigation passed 9/9 in 14.10 s (archive
`b0d416dc-1669-4c12-83a7-2924a2abfcf7`). ui-reading initially passed 26/31:
four obsolete statement-entry labels, and one real coarse-pointer output-title
size regression. Updated the tests to current per-assertion entry points; rerun
passed 30/31, isolated the compact output-title rule overriding touch minimums,
and corrected that rule in `7d222b1`. Failure archives:
`89e70f75-1c49-41bc-a70a-a09fe1b7b101` and
`9d0a08b9-8c1f-4c7a-9cb3-e9e50ab11c59`.

Live CUA inspection verified toolbar alignment, interpretation expansion, selected
quantity fields, separate component editing and disabled assistant controls. No
scientific records were edited and no sampling campaign was launched. Screenshots
`assistant-refined.png` and `quantity-refined.png` are in the existing external
evidence directory. Final checks and deployment identity are recorded below.

Final committed tree `7d222b1`: `./hyprn-mvp dev check combined-static`
passed 9/9 stages, 8.79 s, archive `8b4f09c6-1c33-4c15-a96e-2826d339fd7f`;
`./hyprn-mvp dev check ui-reading` passed 31/31, zero failures/skips/flakes,
39.08 s, archive `2f89f6a8-e0da-4766-99f3-f1169b502667`. Commands sourced
`/private/tmp/hyprn-orchestration-env.sh` and used the existing invocation-only
16 GiB scratch allowance. Runner archived evidence and released scoped fixtures.
Navigation evidence above remains applicable: later changes only corrected helper
copy, slider geometry, statement test entry points and output touch sizing.
`npm --prefix ui run build` passed; existing bundle-size advisory remains.

Static demo at port 54821 now serves source `7d222b1`, recorded in its host ready
file. Prior asset hashes are retained for recovery. Browser viewport override was
reset and the final demo tab retained. Final screenshot: `assistant-final.png`.
No worker/runtime/API change, native recalculation or full qualification was
performed. Automated checks are not human acceptance. Next action: user review;
qualitative-choice presentation awaits selection of the proposed generic design.


## Generic choices and assistant dock — 2026-10-17

Implementation `2d392b7`; option assertion correction `321ddac`. QualitativeChoice
uses declared category dimensions and allowed combinations: up to four choices
as pressed-state buttons, longer lists as a labelled selector. The existing
category-selection, exact-configuration and surrogate handlers are preserved.
Assistant occupies a reserved column, leaving the canvas mounted; narrow screens
stack it above the canvas. Unavailable message and disabled composer remain.

Inspected the signed-in external Chrome reference: assistant compressed the main
content by 376px; collapse restored it. Further read-only navigation covered
workspace selection, overview, Target table/filter menu, Assess explanations,
Validate report and claims drawer, Documents and Settings. No workflows, messages
or uploads were submitted. Broader UX recommendations remain proposals.

Checks via the locked entry point, with the existing orchestration environment
and invocation-only 16 GiB scratch allowance:
- combined-static: 9/9, archive `93491e3a-cdd8-42df-8671-54b9258f1f33`.
- ui-navigation: 9/9, 19.70s, archive `5ca10a26-b5a1-41e0-b1a5-af780ac59070`.
- ui-reading: initial 30/31; Playwright toBeDisabled did not recognize the native
  option despite its disabled attribute. Corrected to assert its DOM disabled
  property. Rerun 30/31 because concurrently integrated RecordDetails lacked its
  specimen. That lane supplied specimen commit `8b78a5b`; final 31/31, no skips
  or flakes, 61.12s, scope `8887de7b-e389-4364-8ae1-a14b70b706ae`.
- npm --prefix ui run build: passed (existing bundle-size advisory).
A sandbox cache-access refusal was resolved by running the same pinned check with
filesystem approval. Tests use isolated API doubles, not native calculations.

Live CUA: all three data-driven choices loaded. Two prepared input sliders gave
11 estimated outputs; switching category preserved both common inputs and reset
category-owned values. Out-of-range input retained the explicit unavailable
reason. Reset restored the baseline. Outbox count stayed 405: no new native
sampling launched. On the refreshed demo, assistant changed canvas width from
1156px to 740px and collapse restored 1156px. Screenshot:
`/private/tmp/hyprn-overview-implementation/choices-docked.png`. Viewport override
reset; temporary sign-in reference tab closed; original Chrome reference restored.
The concurrent record-details lane deployed its integrated build during review;
its delivery identity is not overwritten here. No runtime, API or scientific
record changes. Full native suite and final qualification were not run.


## Approved graph recipe — 2026-10-17

Source `0b2026f` updates the shared response plot and design-system contract only.
Plots occupy the full output width below the title/readout; the basis action is
below the plot. Thin dashed estimates, quiet axes, an outer selection halo and
optional declared reference lines are generic. Selected API basis is authoritative
even when a calculated sample has the same x coordinate. No sampling, surrogate,
API, navigation or record-ownership change. The optional reference-line renderer
is exercised by specimens; application criterion binding is not implemented.

Combined-static passed 9/9 stages in 6.46s (archive
`e4443da7-c465-4be1-8d6c-69f732fe4034`). ui-reading passed 31/31, no failures,
skips or flakes, 32.73s (scope `5916c7ed-5770-4c6f-b995-26713a7f6486`).
Both ran through ./hyprn-mvp dev check with the existing orchestration environment
and invocation-only 16 GiB scratch allowance. Browser coverage checks full-width
plots, vertical order, unequal input/output rows, no internal scroll, 25–100% zoom,
390/1440 widths, both themes, and declared-reference geometry. Build passed with
the existing bundle-size advisory. No native execution rerun or live deployment
was performed. The user requested first-principles navigation planning after
rejecting the prototype's hierarchy as confusing; broader navigation remains
unapproved. Next action: review a simpler answer-led hierarchy before UI changes.
