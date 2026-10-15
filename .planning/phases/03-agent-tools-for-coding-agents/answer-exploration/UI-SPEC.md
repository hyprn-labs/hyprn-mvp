# Answer exploration — design-system contract

Binding alongside CONTEXT.md. Applies to the current study Overview and canonical graph; existing history/entity homes retain appropriate provenance/access controls. Read design-system/README.md, Layouts.md, Scientific-states.md, Naming.md, Coherence.md and relevant component recipes before implementation.

## Composition and content budget

1. `StudyQuestionBox`: preserve the complete actual question and scope, no duplicated subtitle/question.
2. `AnswerExplorer`: title Explore the answer; one selector per categorical dimension in its header; Sample settings aligned top-right; one graph; Open model at bottom-right within this box.
3. `AnswerInterpretation`: Interpretation and Still to answer. Show the saved scientific prose, essential conditions, qualifications and citation access without separate Observations/Sources/metadata inventories duplicating the same content. Keep genuinely distinct observations in prose. Do not discard persisted content merely to shorten the page.

No Curves against control, standalone Calculate, Reset inputs toolbar, View combination, Saved interpretation, full supporting-results list, reasoning/methods panel, permanent tutorial text or architecture labels on Overview. No chart-engine/model-version plumbing in the normal flow. Exceptions earn space only while actionable: missing range, outside assessed domain, failed point, unmet accuracy target, unsaved settings, denied access, ongoing preparation.

## Shared components owned by ui/src/design

| Primitive / recipe | Required behavior |
|---|---|
| QuantitySlider (new) | Label, value, unit, numeric entry and native range. Bounds/step from a declared input design. Pointer, keyboard arrows, Home/End; precision and focus preserved. Dragging does not pan the canvas. Numeric value beyond assessed domain remains explicit, with no silent clamp; range/domain edits live in Sample settings. All free inputs remain reachable; no top-K hiding. |
| QuantityResult (extend Readout/StatusTag) | Scalar + unit and compact Estimated / Calculated / Not computed state with shape and colour. Approximation mark for estimates. Accessible label includes value, units and state. Exact-record availability wins only for available outputs; never fill failed calculated outputs with an unlabeled estimate. |
| ResponseCurve (new shared SVG recipe) | Dashed estimated response, filled calculated points, hollow estimate cursor, axis label/unit and sufficient ticks; zero/criterion reference where meaningful. Point markers only for matching category/model/full fixed-input slice. Break unavailable intervals; no line through failures. Constant curves do not invent variation. Numeric accessibility summary; expanded view has explicit axes. |
| CategoricalSelection (compose Select/segmented control) | One control per qualitative dimension; valid joint combinations; accessible disabled-choice reason. Category-derived scalar values can be overridden explicitly. On category switch apply that category's assignments and retain only declared compatible noncategory selections; do not silently retain a fuel-property override for a different fuel. |
| SampleSettings (compose DialogFrame, Field, DataTable, Disclosure, Button) | Numerical ranges for all free inputs, categorical scope, max additional evaluations, wall/concurrency bounds, per-output absolute/relative target errors. Current-vector calculation is a second action **inside** this dialog. Advanced method settings collapsible; no mandatory tutorial. Preview budget split/reuse and elapsed counts; allow cancel/reconcile/resume through server state. Primary action is context-appropriate Prepare/Refine/Calculate, never competing primary buttons. |
| AnswerExplorationPanel / InterpretationPanel (shared composition) | Enforce heading/action/footer placement and copy budget. Screens supply data, not styling. No duplicated graph or ad hoc page-level status styles. |

Implement in `ui/src/design/components.tsx`, `primitives.tsx`, `graph.tsx`, `foundry.css`, `index.ts` or cohesive new modules exported by that index. Documentation recipes go in `design-system/components/`. Reuse existing tokens and formatting. If a token is actually missing, edit tokens.json and generate tokens.css; never hand-edit generated CSS. No raw screen controls, inline styles, external fonts/CDNs or unreviewed graph/chart dependency. Tiny curves can use the existing SVG approach; benchmark rendering before considering a chart library.

## Axis and graph behavior

There is one current full input vector. Focusing/changing an input sets active axis; keyboard and numeric edits do the same. The initial axis is declared by the study's design (fuel: Mach). Every visible output shows its response to that input while all other selected values remain fixed. Add no global axis selector. Mark active input with the existing focus/selection recipe and label the x-axis concisely. Upstream outputs can remain flat when the active input is downstream; this is correct.

Canonical `GraphView.project` and `GraphCanvas` still own topology/identity. Add an exploration rendering mode/slots for controls/curves without importing exploration business state into design primitives. Retain model editor, run and configuration graph behavior. Layout must accommodate every input with readable nodes, bounded canvas pan/zoom/scroll and progressive output expansion; no arbitrary four-input limit. Correlated/co-varied input bindings are explicit design assignments, never inferred by equal names.

## Traceability and interpretation without noise

Select a result/point to inspect its calculated run or surrogate basis and validation. Model-version pins, data IDs and detailed metrics stay in contextual details. Remove inventories, not provenance. Estimated criterion crossings are indications; only original-model runs provide calculated criterion evaluations. Unmet accuracy is a compact warning; never display an uncalibrated confidence band. Baseline-specific interpretation must say its essential conditions in prose or compact claim context. No saved-interpretation label and no automatic scientific conclusion updates on slider events.

`Open model` opens the exact selected model version; editing uses the existing explicit edit/copy-draft flow. It must not take the user to an unrelated current draft. Methods referencing several models retain their approach-version context on the Model page without creating a second editable approach or rewriting old answer links.

## Required UI acceptance

- Three boxes in order; all prohibited controls/text absent. Open model is inside exploration footer, not interpretation.
- Every free numerical fuel input has a usable slider/entry and correct unit. Category selector changes appropriate bindings. Connected inputs cannot be edited.
- Active slider determines labeled curves; no Curves against dropdown. All outputs update from the same selected vector and result generation.
- Calculated and estimated points are distinguishable in grayscale and screen-reader output. Unavailable stays unavailable; a selected calculated point does not relabel its surrounding curve.
- Settings includes adding the selected original-model point, ranges, budget, all-output tolerances and unmet-target behavior. No calculation action elsewhere on Overview.
- Day/Control room, keyboard-only, genuine 200% zoom, touch targets, long labels, many ports, loading/access-loss/error cases. Stale response cannot overwrite a newer category/input vector. Drag preserves focus and graph position.
- Update design specimens, smoke rendering and ownership checker fixtures so future screens must use these recipes. Automated evidence is separate from Guerric's acceptance.
