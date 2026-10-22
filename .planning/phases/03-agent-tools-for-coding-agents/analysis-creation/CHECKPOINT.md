# Unified analysis creation

Implementation: `3f62777`, 2026-10-19.

One New analysis action opens one shared ActionDialog. Single configuration selects one saved
record; Multiple configurations either selects at least two existing records or generates
sample points. The name, optional description and each branch's selections survive mode
switches. Sampling settings and criterion bindings remain explicit, behind disclosures.
Shared choice-card and form-section recipes own spacing, wrapping and selected appearance.

The existing creation/version APIs, exact membership, sampling method/counts/seed, polling,
reference values, units and estimate checks are preserved. Mode switching is disabled during
submission/sampling. No backend, worker, stored scientific data or surrogate change.

Initial focused evidence: combined-static 9/9 (4.10 s); calculations-ui 5/5 (31.22 s),
including real browser/API single creation, multiple creation, revision, reference marks,
sample generation, estimate assessment, state retention and narrow light/dark layouts.
The sample/fit transport in that test is a data-only fixture, not numerical qualification.
The only subsequent UI delta is the minimum-selection/count hint, verified below.

Live inspection: one collection button; single and generated-sample branches readable;
no submission was made to the user's study. Existing 2 analyses and scientific basis retained.
Screenshot stored outside the repository. Only checked UI assets are deployed; the scientific
runtime and live authoring stores are unchanged. Unrelated roadmap/proposals untouched.

No failures in this task's initial checks. Human visual acceptance and full release
qualification are separate. Test scopes released by runner except retained static build
used to deliver the assets. No installation or dependencies added.

Final committed-tree build/design checks: `./hyprn-mvp dev check combined-static --keep-scope`
9/9 passed (3.90 s), `/private/tmp/hyprn-analysis-dialog-static-delivery.log`.
Assets delivered from scope `71ac9a68-e6d0-4e50-a210-066bbe861c62`, with publisher's
source fingerprints and scientific runtime hash verified. Live screenshot:
`/private/tmp/hyprn-analysis-dialog/new-analysis.png`.

Final `./hyprn-mvp dev check calculations-ui`: 5 passed, 0 failed/skipped (30.58 s),
`/private/tmp/hyprn-analysis-dialog-browser-delivery.log`, exact implementation `3f62777`.

## Corrected choice of preparation (supersedes single/multiple navigation)

User correction delivered in `8ddb61f`, compact checklist `ab813f4`, test locator
`2318906`. New analysis now offers Select configurations (one or more checkboxes)
or Generate samples. There is no single/multiple branch or source dropdown.
Generation exposes input ranges and a total joint sample count; method, seed,
training/check split and optional step columns remain advanced. Changing total
preserves check count and changes training count; the split remains visible.
No change to backend validation, accuracy checks, runtime, stored records or surrogate.

Final focused checks through the locked entry point:
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 4.30 s;
  `/private/tmp/hyprn-analysis-paths-static-final.log`.
- `./hyprn-mvp dev check calculations-ui`: 5/5, 30.46 s;
  `/private/tmp/hyprn-analysis-paths-browser-final.log`.
- Initial browser attempt: 4/5, one raw first-checkbox locator hit a hidden advanced
  control before configurations loaded. Corrected to the named configuration.
  Other paths including joint sample submission passed; no production workaround.

Checked UI deployed from retained scope `39105978-b08a-497c-b37c-4cf4be0dd0c1`;
source fingerprints and unchanged runtime hash verified. Live two-path dialog and
25-point total / 17 training / 8 checks inspected; no live data created.
Screenshot `/private/tmp/hyprn-analysis-dialog/choose-or-sample.png`.
The browser sample transport remains a fixture; native numerical qualification
was not repeated for this UI-only change. Human visual review remains separate.


## Visible optional fields (2026-10-19)

Implementation `b6060fe`: shared `FormField` owns label, optional marker and spacing.
Description is visible in both analysis creation paths and both revision editors.
The brief uses the same treatment for Scope, alternative descriptions and reasons.
No backend, stored content, numerical, sampling or accuracy changes.
Test-only follow-up `5466d12` replaces stale lifecycle prose expectations with
actual selected draft/version checks; the removed prose was unrelated to this change.

- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 4.51 s,
  `/private/tmp/hyprn-optional-static-delivery.log`, implementation `b6060fe`.
- `./hyprn-mvp dev check calculations-ui`: 5/5 passed, 31.31 s,
  `/private/tmp/hyprn-optional-analyses.log`, same implementation.
- Initial `brief-ui`: 1/2 passed; failed on the previously removed draft explanation,
  after optional-field checks and saving passed. Evidence retained in check session
  `a5970f67-d779-4f3b-9197-76d316e4496e`.
- Second brief attempt: 1/2 passed; removing the obsolete text wait exposed an
  immediate API read before save completion. `b805003` waits for the selected saved
  version before reading its record. No production change or weakened assertion.
- Final `./hyprn-mvp dev check brief-ui`: 2/2 passed, 11.65 s, exact `b805003`;
  `/private/tmp/hyprn-optional-brief-delivery.log`. Final delta from the checked UI
  implementation is test-only; analysis/static evidence remains applicable.

Delivered checked assets from scope `a43ddccc-3774-423b-8b90-36441a385442`;
publisher confirmed unchanged source fingerprints and scientific runtime hash.
Live analysis dialog and brief optional labels inspected without saving any records.
Screenshots `/private/tmp/hyprn-analysis-dialog/optional-description.png` and
`/private/tmp/hyprn-analysis-dialog/brief-optional.png`.
Browser fixture stores released; static build scope retained for delivery evidence.
Earlier development static pass (9/9, `08cebdf7-a3be-474b-a6f9-3099dcae91c1`)
was superseded by the final committed-tree build. No broad numerical/release
qualification repeated for this presentation change; human acceptance remains separate.


## Explicit fields and criterion suggestions (2026-10-19)

Implementation `b256eef`, test correction `a4775c9`. New analysis uses Name,
Description, configuration choice. No editable analysis fields use disclosures:
criteria, sampling method/counts/seed and optional input steps are visible.
Criterion suggestions require a unique normalized quantity-name/exact-unit match;
units alone, duplicate names and mismatched/unresolved units never select an output.
Explicit changes and clears survive switching modes. Saved revisions retain their
exact brief and existing bindings; no saved data is changed by opening an editor.
Generic shared FormField/section/choice components own presentation.

- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 5.70 s,
  `/private/tmp/hyprn-explicit-analysis-static.log`, exact implementation `b256eef`.
  Includes independent matching regressions for ambiguity, wrong units and names.
- Initial `calculations-ui`: 5/6 passed, 47.87 s. New journey passed matching,
  clearing, switching and saving, then incorrectly expected only one criterion row;
  the saved table correctly retains unmatched criteria. Test now checks all rows
  and explicitly checks the unmatched state. No production change needed.
- Final `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 36.02 s, exact
  `a4775c9`, `/private/tmp/hyprn-explicit-analysis-browser-final.log`. Delta from
  static-checked implementation is the test-only expected unmatched row.

Checked build scope `04f2227c-0f06-425d-84ed-a33b02dee092` delivered with source
fingerprints and unchanged scientific runtime verified. Live coolant criteria both
preselect their matching outputs; mode switching retains selection and sampling
fields are visible. No new live records/runs or samples created. Screenshots:
`/private/tmp/hyprn-analysis-dialog/explicit-fields.png` and `automatic-criteria.png`.
Browser scopes released by runner, static scope retained for build evidence.
This does not qualify the numerical runtime or substitute for human visual acceptance.


## Compact editable criterion mapping (2026-10-19)

Implementation `aa69805`. Criterion labels show name plus requirement/units once.
The shared Select supports a short closed summary; matching output names show
`From <component>` while native choices and accessibility keep full output names.
Differently named selections retain full labels, and forced-colors mode uses the
native label. Matching rules, saved bindings and numerical behavior are unchanged.

Exact implementation checks (no failures):
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 4.48 s;
  `/private/tmp/hyprn-mapping-static.log`. Includes native option/summary rendering.
- `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 35.96 s;
  `/private/tmp/hyprn-mapping-browser.log`. Covers short matching label, full label
  on a differently named selection, manual clear, switching, saving and revision.

Build scope `b0f40bd1-b1eb-4d88-ac4a-93fae5b5ab50` delivered with source
fingerprints and unchanged runtime verified. Live closed summaries inspected visually;
expanded native control retains full labels in accessibility state. Screenshot
`/private/tmp/hyprn-analysis-dialog/compact-mapping.png`. No live records changed.
Browser scope released; static scope retained for delivery evidence. Human visual
acceptance and broad numerical/release qualification remain separate.


## Output / Requirement presentation (2026-10-19)

Implementation `093b075`, accessible table name `e519476` supersedes the component-only
closed selector. Shared DataTable shows editable Output and Requirement columns.
Quantity names appear alone unless another offered output shares the name, in which
case component context disambiguates. Unselected prompts retain the intended criterion.
Removed the unused short-summary Select extension; native selection and exact saved
bindings remain unchanged. Sampling controls and data were not changed in this pass.

- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 4.81 s;
  `/private/tmp/hyprn-output-requirement-static.log`. Completed after `e519476`.
- Initial browser check: 5/6 passed. The fixture copied source before the table-name
  follow-up, so its unnamed table could not satisfy the new named-table assertion.
  Retained error context confirms the named region and unnamed table; live/final
  build has both names. Rerunning the affected browser group on final source.
- Final `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 36.31 s,
  exact `e519476`; `/private/tmp/hyprn-output-requirement-browser-final.log`.

Checked UI delivered from scope `f6ca90a9-6a74-406c-806e-21b16c3edcb8`; fingerprints
and unchanged runtime verified. Live narrow-screen table inspected and editable
selections verified. Screenshot `/private/tmp/hyprn-analysis-dialog/output-requirement.png`.
No live authoring data changed. Static scope retained; browser scopes released.
Human visual acceptance and numerical/release qualification remain separate.

Sampling explanation: reference supplies untouched inputs and exact model pins;
17/8 are UI defaults for joint training/check counts, not accuracy evidence.
Generated points copy the baseline name, explaining repeated names. Generation
creates configurations; running, fitting and assessment remain separate operations.
User questioning reference-first UX suggests a future input-first editor with fixed
values/ranges and optional configuration prefill; no implementation authorized yet.


## Input-first sampling — 2026-10-19

User explicitly requests inputs with fixed values or ranges, no configuration prefill,
existing range provenance reused, and no separate justification. This supersedes the
optional-prefill proposal above. First outcome: New analysis → Generate samples reads the
selected exact model, shows only independent inputs and saves/dispatches declared values.

Implementation uses public model read and configuration preview/commit, followed by the
unchanged sampling command. New fields are blank; revising a sampled analysis restores its
own declaration. Unchanged ranges reuse recorded rationale; changed/new ones record a
manual user declaration without borrowing evidence. Existing anchors are reused when fixed
inputs are unchanged, preserving eligible points/runs and their training/check partitions.
A changed fixed context saves a fresh anchor; saved contexts, input result bindings and
assumptions are retained. Unknown configuration acknowledgements use the existing recovery
flow and a retained command ID. Multi-group edits are explicitly refused by this single-group
editor rather than dropping groups. Backend schemas, numerical execution, fits/checks and
answer publication remain unchanged. No new dependencies or private store access in clients.

Focused evidence so far:
- Initial calculations-ui: 5/6; successful generation reached a test selector matching nine
  headings (analysis plus member cards). Corrected the test to select heading level 2.
- calculations-ui: 6/6, 39.58 s; `/private/tmp/hyprn-input-sampling-browser-final.log`.
  Real API/auth/store/configuration writes; data-only modeling/design/fit transports.
  Verifies explicit fixed value, new generation, adding points retaining eight runs,
  estimate refusal with missing recorded outputs, both themes, and form state retention.
- Initial combined-static: 7 checks passed, type check failed on an optional result-binding
  union. Narrowed the typed property; local tsc passed. Final static/build pending.
- Local sampling declaration tests: initially 5/5; added exact run-result binding retention.
  Registered in combined-static; final committed-tree run pending.
- Final delta after browser: count validation matches existing public limits (3–64 training,
  2–64 checks, 32-bit seed, corners plus interior), result-binding type narrowing.

Next: committed-tree static/build and browser checks, live UI delivery and visual inspection.
Full release qualification and human acceptance remain separate. Unrelated ROADMAP and
research files preserved. Scratch browser scopes released by check runner.


### Delivered input-first form

Implementation commit `a1c14bb`; later delta is this evidence/state update only.
- `./hyprn-mvp dev check combined-static --keep-scope`: **9/9 passed**, 4.82 s;
  `/private/tmp/hyprn-input-first-static-final.log`. Includes six sampling declaration
  tests (explicit zeros/missing values, independent inputs, exact provenance, changed
  bounds/fixed context, unresolved units/unsafe values, exact run-result references),
  design ownership/tokens, UI contracts, TypeScript and production build.
- `./hyprn-mvp dev check calculations-ui`: **6/6 passed**, 37.10 s;
  `/private/tmp/hyprn-input-first-browser-final.log`. Corrected selector and full sampled
  revision journey pass on the committed tree. Browser scope released; archived evidence:
  `scratch-checks/.hyprn-checks/b98f5df1-e73f-4ad7-b606-a2c3e2c1b054` under development root.
- Built scope `031eaa09-4a70-4867-bd29-5e60c3a2ee94` retained and published through the
  fingerprint-checked UI delivery helper. Runtime unchanged; seven assets published.
- Live selected model read correctly supplies four independent inputs, all initially blank.
  Changing Heat load to Range shows min/max/optional step while the other inputs remain
  fixed fields. No reference selector or separate justification. Narrow-screen screenshot:
  `/private/tmp/hyprn-analysis-dialog/input-first-live.png`. No live data mutations.

Both-theme browser screenshots retained; human acceptance remains the user's review.
This UI/API preparation journey does not requalify numerical accuracy or worker containment;
those unchanged layers retain their existing evidence. No numerical tolerances relaxed.
Other-session ROADMAP and untracked research/spec files remain untouched.


## Simplified analysis form and separated input cards — 2026-10-19

User requests removing the criteria section completely from the form and improving input
separation through the design system. Removed the editable criteria section from creation
and revision. Existing saved bindings are copied exactly on revision; new hand-picked
analyses retain the existing unique name/unit matching behavior. No domain/API retirement.
Sampling input groups now use the shared sunken Panel, header divider and hf-form-stack;
no new study-specific styling or values. Model labels and unit declarations remain the source.

Local TypeScript passed; committed-tree combined-static and calculations-ui acceptance pending.
Focused browser expectations now verify absence of controls and saved mapping retention.
The calculations fixture uses matching output names to exercise automatic evaluation while
its separate unmatched-criterion journey verifies no mapping is invented.
Next: checks, publish the verified build, inspect live narrow-screen cards. Scientific execution,
sampling, surrogate assessment and saved authoring data are unchanged.


Initial committed acceptance: static/build 9/9 pass (4.53 s); browser 5/6. The zoom/reader
journey still expected Not evaluated despite the fixture now having unique matching output
names. Updated that expectation to actual Met/Measured; unmatched behavior remains covered
by the separate criterion preservation journey. No production source change after `ecea1a3`.
Live shared card layout and removed criteria section inspected; data/runtime unchanged.
Browser rerun pending for this test-only correction.


### Delivered simplified form

Production `ecea1a3`; test-only corrections `e665839` / `4512b77`.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 4.53 s;
  `/private/tmp/hyprn-input-cards-static.log`. Built scope
  `85b7f466-7563-48ec-8461-ae215a2a8eb3`, retained for delivery; no later UI source changes.
- `./hyprn-mvp dev check calculations-ui`: final 6/6 passed, 38.85 s;
  `/private/tmp/hyprn-input-cards-browser-final.log`. Browser scope released, archived under
  `scratch-checks/.hyprn-checks/b3db0789-18bb-4d01-a379-fc2ce5ec6fc0`.
- Verified source/runtime fingerprints, published seven UI assets. Live creation dialog
  contains no criterion controls; input cards visibly separated at narrow width. Screenshot
  `/private/tmp/hyprn-analysis-dialog/input-cards-live.png`. No live records changed.
- Browser light/dark media variants run, but profile Light overrides media: screenshot
  evidence establishes Light layout, not separate Dark visual acceptance. Token checks pass.

No numerical engines/accuracy checks changed or rerun. Shared components carry existing
scientific states and token colors. Human visual acceptance and release qualification remain
separate. This evidence/state-only commit does not invalidate the tested implementation.


## Sampling settings card — 2026-10-19

User requests the same darker card for method, training/check counts and seed, and deletion
of Total sample points. Uses the existing sunken Panel and FormField recipes; removes the
editable total and duplicate summary. Separate training/check states, defaults, validation
and submitted values remain unchanged. Browser journey enters training count directly.
No API, data, sampling engine or surrogate change. Next: committed static/browser checks,
publish and inspect the live card. Unrelated session files preserved.


### Sampling settings delivered

Implementation `4c6335c`.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 7.19 s;
  `/private/tmp/hyprn-sampling-settings-static.log`; retained scope
  `1af8d2be-6b64-4036-b680-4d9116019d45` supplied the build.
- `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 44.62 s;
  `/private/tmp/hyprn-sampling-settings-browser.log`; browser scope released.
- Another session changed ModelView and shared RecordState/PageHeader/RecordDetails during
  preflight. Preserved those compatible changes; all UI source timestamps preceded the
  first static acceptance command, none changed during its checks/build. Refreshed delivery
  fingerprint and published the passing integrated build. No unrelated edits staged.
  Subsequent ModelExplanation edits remain owned by that session and were not republished.
- Live UI shows the four requested controls in the shared sunken card, no total count;
  `/private/tmp/hyprn-analysis-dialog/sampling-settings-live.png`. Runtime and records unchanged.
No numerical requalification or human acceptance claimed. Evidence/state-only delta follows.


## Compact sampling cards — 2026-10-19

Shared compact Panel recipe removes duplicate label margins and reduces inset padding;
fixed mode/value share a row, range bounds/step and sampling counts/seed use numeric grids.
Card separation, control size, labels, handlers and sampling payloads remain unchanged.
Next: committed static/browser checks and live inspection. Concurrent run-summary and
model-explanation edits are preserved and excluded from this change's staging.

### Compact cards delivered

Implementation `2cb4253`, integrated with model-explanation `c834399`.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 4.69 s;
  `/private/tmp/hyprn-compact-sampling-static.log`, retained build scope
  `b5004bf9-1be7-4991-9f48-ea4564ada8f1`.
- `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 46.70 s;
  `/private/tmp/hyprn-compact-sampling-browser.log`; fixture scope released.
- Source/live fingerprints matched when publishing seven UI assets. Concurrent uncommitted
  inline MetricGrid styling was included in that passing build but not staged here; its
  owner subsequently requested a different run layout and is handling that independently.
- At 358px card width, settings height fell 477→215px (55%), fixed input 273→139px
  (49%). Live fixed/range fields remain readable, separated and keyboard accessible.
  Screenshots `/private/tmp/hyprn-analysis-dialog/compact-sampling-live.png` and
  `/private/tmp/hyprn-analysis-dialog/compact-range-live.png`. No study data changed.
Sampling handlers, payloads, engine, accuracy checks and surrogate behavior unchanged.
No new numerical qualification or human acceptance claimed. Next: user review.


## Shared compact editing dialogs — 2026-10-19

Apply compact rhythm through DialogFrame/ActionDialog CSS: space-4 shell/sections,
space-3 field gaps, single label/control spacing, compact editable nested panels and
separated quantity groups. No form handlers, fields, APIs or scientific values changed.
Concurrent run/status and configuration-reference changes preserved unstaged.
Next: focused static and quantity/evidence browser checks; live editor review and delivery.

### Shared compact dialogs verification

Implementation `446b5b8`, quantity refinement `f04b6f5`. Integrated run-header guard
alignment `f670798`/`a16a29e` follows concurrent RunPanel changes, without staging them.
- Initial static pass stopped at a stale `label="Execution"` guard (3 checks passed,
  UI-contract check failed). Guard now asserts shared status and output-header components.
- Static/build 9/9 passed in `/private/tmp/hyprn-compact-dialogs-static-final.log`
  (5.10 s) and `/private/tmp/hyprn-compact-dialogs-integrated.log` (4.58 s).
  Concurrent reference-spacing delivery changed the live index. Publication refused;
  automatic approval review also rejected recapturing/publishing that prior build.
  Used the safer requested path: rebuilt reconciled current source, preserving `2937125`.
- Final static/build 9/9 passed, 4.38 s, `/private/tmp/hyprn-compact-dialogs-delivery.log`;
  final retained build `97b0fc5d-4c81-43e5-ae52-27f245e7449c` published seven UI assets
  with matching source/live fingerprints and unchanged runtime.
- Initial quantity browser 13/13 (29.57 s), evidence browser 13/13 (25.56 s), logs
  `/private/tmp/hyprn-compact-dialogs-quantities.log` and
  `/private/tmp/hyprn-compact-dialogs-evidence.log`. Both test scopes released.
- Live component/quantity editors inspected without changing authoring data. Quantity
  dialog at 392px width shrank from 742px to 588px and all fields/actions fit visibly.
  `/private/tmp/hyprn-analysis-dialog/compact-quantity-live.png`.
- Final quantity-only CSS refinement removes nested unit label margins/line break spacing
  and lets name/symbol share available width with auto-fit fallback. Final quantity
  browser rerun 13/13 passed (22.99 s),
  `/private/tmp/hyprn-compact-dialogs-quantity-final.log`; scope released. Evidence
  unaffected by this three-line quantity-scoped delta. Human acceptance remains separate.
No handlers, sampling behavior, numerical engines or accuracy checks changed.


## Unified analysis settings — 2026-10-19

One Analysis settings action reuses the creation dialog for revisions. Defaults to the
saved design and initializes its name/description; both existing-configuration and
sampling editors keep their original save paths, bindings and point reuse. A new
version resets dialog state by exact version key. Browser journey verifies one trigger,
mode switching, restored ranges and point reuse. Concurrent run/layout edits preserved.
Next: focused static/browser checks and live dialog verification.

### Unified settings delivered

Implementation `84fe033`.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 passed, 6.87 s;
  `/private/tmp/hyprn-analysis-settings-static.log`; retained build scope
  `8e9bb162-d877-4685-8f61-951d1f34fd29`.
- `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 49.78 s;
  `/private/tmp/hyprn-analysis-settings-browser.log`; scope released. Tests cover
  both revision paths, exactly one header action, saved sampling defaults, mode switching
  and existing point/run reuse. Numerical execution remains represented by fixture doubles.
- Published seven assets with source/live fingerprints matched; runtime unchanged.
  Live sampled analysis opens Analysis settings with its saved name, description,
  ranges/fixed values, seed and counts. No live data or runs changed. Screenshot
  `/private/tmp/hyprn-analysis-dialog/analysis-settings-live.png`.
No sampling algorithm, accuracy check or backend change. Human acceptance remains separate.


## Saved analysis settings are read-only — 2026-10-19

Settings now read the selected version, not the latest version implicitly. Saved fields
are disabled and submission actions omitted; submit handlers also refuse read-only mode.
An explicit Create new version action on the latest version enables the existing revision
paths and shows New version · unsaved. Older versions offer inspection only. Closing and
reopening an idle revision restores saved values; active sampling stays mounted.
Tests cover initial disabled fields, no submit action, explicit revision, exact historical
membership, sampling reuse and preserved bindings. Next: focused checks and live review.

### Read-only settings delivered

Implementation `dd6cf7f`; shared readability refinement `d90a6f7`.
- `./hyprn-mvp dev check calculations-ui`: 6/6 passed, 53.47 s;
  `/private/tmp/hyprn-readonly-analysis-browser.log`; scope released. Verifies disabled
  saved fields, no save/generate action, explicit new version, original historical
  membership, preserved bindings and sample/run reuse. No numerical qualification.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 before and after the
  presentation-only refinement; final 4.45 s, `/private/tmp/hyprn-readonly-analysis-final.log`.
  Final retained build scope `1ec9f8f5-750a-4d3f-aab2-eddc7fd7cd59` published seven assets
  with matched source/live fingerprints and unchanged runtime.
- Live inspection confirmed read-only fields, explicit new-version transition and Cancel
  restoring the original saved name after a temporary unsaved edit. No authoring record,
  run or sample was written. Screenshot
  `/private/tmp/hyprn-analysis-dialog/readonly-analysis-settings-live.png`.
- Final refinement only adds a shared class/colors and hides select chevrons while
  controls remain disabled. Browser behavior evidence remains applicable; final visual
  review checks legibility. Human acceptance remains separate.

### Saved source choice remains visible (2026-10-19)

Implementation `3ef6b86`: both configuration-source cards remain visible in saved
Analysis settings, with the persisted mode selected. Native disabled controls and
shared read-only card styling preserve inspection without allowing changes.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 5.54 s;
  `/private/tmp/hyprn-visible-choice-static.log`; retained build scope
  `f8c8ea16-b498-4802-bedc-7f0a1a02f530`.
- `./hyprn-mvp dev check calculations-ui`: 6/6, 45.28 s, no skips/failures;
  `/private/tmp/hyprn-visible-choice-browser.log`; scope
  `23149299-7e51-4c13-ac2f-50b267b9263d` released. Tests cover both saved
  source selections, disabled controls and existing explicit revision paths.
- Published seven UI assets with matched source/live fingerprints and no runtime
  change. Live saved sampled settings show selected Generate samples followed by
  sampling inputs. Screenshot: `/private/tmp/hyprn-analysis-dialog/readonly-analysis-choice-live.png`.
- No authoring data, sampling, surrogate or execution behavior changed. Concurrent
  run/design edits preserved. Automated verification is not human acceptance.

### Consistent saved-version authoring (2026-10-19)

Product `e6668d4`; test migration `0c2deb8`. Models, configurations and analyses use
CreateVersionAction. Saved model explanation has no editor, even when absent. Models
expose revision only on the unique latest saved leaf and preserve the existing draft;
configuration copies preserve exact values/model pins, and saving creates a new identity.
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 7.70 s;
  `/private/tmp/hyprn-version-consistency-0.log`. Build scope
  `7e16d422-6c88-4e7c-9e7f-13eaf2e4c47c` published with matching fingerprints.
- `./hyprn-mvp dev check units-ui-reading`: final 13/13, 42.47 s;
  `/private/tmp/hyprn-version-consistency-1-final.log`. Initial 11/14: two obsolete
  approach-page journeys and one new test compared request IDs. Replaced retired
  approach checks with version-action keyboard/reflow coverage; compare record data.
- `./hyprn-mvp dev check units-ui-configuration`: final 7/7, 24.86 s;
  `/private/tmp/hyprn-version-consistency-2-final.log`. Initial 6/7 expected a removed
  criteria placeholder; now verifies its absence. Original configuration remains equal
  after a successor saves different input values.
- `./hyprn-mvp dev check calculations-ui`: 6/6, 40.36 s;
  `/private/tmp/hyprn-version-consistency-3.log`. All browser scopes released.
- Live models/configurations/analyses share explicit revision action; opening model
  draft then returning to its saved version works. No live authoring mutations or
  model runs. Screenshots `/private/tmp/hyprn-analysis-dialog/model-version-action-live.png`
  and `configuration-version-action-live.png`. Native numerical qualification unchanged;
  automated checks do not constitute human acceptance.
