---
phase: 03-agent-tools-for-coding-agents
plan: model-flow
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [UI-01, UI-02, UI-03]
files_modified:
  - design-system/README.md
  - design-system/Layouts.md
  - design-system/Scientific-states.md
  - design-system/Naming.md
  - design-system/Contour.md
  - design-system/components/ModelNode.md
  - design-system/components/DataTable.md
  - design-system/tokens.json
  - ui/src/design/tokens.css
  - ui/src/design/components.tsx
  - ui/src/design/graph.tsx
  - ui/src/design/graphRouting.ts
  - ui/src/design/foundry.css
  - ui/src/design/index.ts
  - ui/src/GraphView.tsx
  - ui/src/ModelView.tsx
  - ui/src/SelectionInspector.tsx
  - ui/src/ModelMethodDetails.tsx
  - ui/src/ModelEditor.tsx
  - ui/src/VariablesTable.tsx
  - ui/src/views/model.tsx
  - ui/src/styles.css
  - ui/tests/DesignSpecimen.tsx
  - ui/tests/design-colors.test.cjs
  - ui/tests/foundry-fixtures.ts
  - ui/tests/screen-readability.spec.ts
  - ui/tests/model-configuration-run.spec.ts
  - ui/tests/unit-model-reading.spec.ts
  - ui/tests/evidence-workspace.spec.ts
  - ui/tests/record-labels.spec.ts
  - ui/tests/study-navigation.spec.ts
  - ui/tests/foundry-zoom.spec.ts
  - ui/control-map.json
  - .planning/phases/03-agent-tools-for-coding-agents/model-flow/1-CHECKPOINT.md
must_haves:
  truths:
    - Each model connection is individually readable from its actual output row to its actual input row, selectable by pointer and keyboard, and included by Fit model.
    - Inputs and outputs retain their direction in graph and table; connected quantities use both dedicated quantity colours and a textual relationship, independently of selection or scientific status.
    - Diagram uses the available width; model explanations and selected-component reading have separate scopes, and opening prose or Python never stretches a side panel alongside the graph.
    - Tabs preserve authoring drafts, guards, verified source and exact historical context; XDSM and all canonical model readers remain usable.
    - Quantity rows have a coherent surface and directly open the existing quantity editor in a mutable draft; optional missing definitions do not create a blanket notice.
  artifacts:
    - path: design-system/Layouts.md
      provides: Authoritative model and component reading composition
    - path: design-system/tokens.json
      provides: Dedicated quantity direction tokens for both themes
    - path: ui/src/design/graphRouting.ts
      provides: Deterministic model-only measured-endpoint routing
    - path: ui/tests/screen-readability.spec.ts
      provides: Route geometry, scope, surface and interaction regressions
  key_links:
    - from: ui/src/design/graph.tsx
      to: ui/src/GraphView.tsx
      via: Exact connection and endpoint identities, without changing model data
    - from: ui/src/ModelView.tsx
      to: ui/src/ModelMethodDetails.tsx
      via: Existing method links and approach-owned editing
    - from: ui/src/VariablesTable.tsx
      to: ui/src/ModelEditor.tsx
      via: Guarded owner selection and an explicit quantity-edit request
---

<objective>
Deliver the user-approved next model UI: readable connection arrows and consistent quantity colours, separate whole-model explanation and component reading, and a clean quantities table with discoverable definition editing. Update the authoritative design system before adopting its recipes. Target the existing local demonstration, then stop after focused committed-tree checks and the parent's browser verification of the requested live model. This is one cohesive numbered execution batch under DELIVERY-PLAN's cadence amendment, not completion of Phase 3 or release qualification.
</objective>

<context>
@AGENTS.md
@.planning/DELIVERY-PLAN.md
@.planning/phases/03-agent-tools-for-coding-agents/model-workspace/PLAN.md
@.planning/phases/03-agent-tools-for-coding-agents/model-workspace/1-CHECKPOINT.md
@.claude/skills/hyprn-mvp-ui/SKILL.md
@design-system/README.md
@design-system/Layouts.md
@design-system/Scientific-states.md
@design-system/SOURCE.md
@design-system/Contour.md
@design-system/Naming.md
@design-system/Coherence.md
@design-system/components/ModelNode.md
@design-system/components/DataTable.md
@design-system/components/ContextualPanel.md
@ui/src/modelMethods.ts
@ui/src/GraphView.tsx
@ui/src/design/graph.tsx
@ui/src/ModelView.tsx
@ui/src/SelectionInspector.tsx
@ui/src/ModelMethodDetails.tsx
@ui/src/ModelEditor.tsx
@ui/src/VariablesTable.tsx
@ui/src/views/model.tsx
</context>

<tasks>
<task type="tracer" tdd="true">
  <name>1. Read a model's connections, explanation and component quantities through one coherent design-system composition</name>
  <files>All files in files_modified; touch ui/src/design/index.ts and ui/control-map.json only when a new shared export or changed named control requires them. Test fixture/assertion changes remain limited to the listed existing suites. No backend, dependency, check-runner, ROADMAP or STATE edits.</files>
  <behavior>
    - A real-shaped three-component/30-port fixture displays five separate connections with exact endpoint anchors; branch, merge, bypass, feedback, unequal heights and long labels have finite stable geometry. Paths avoid unrelated card interiors and labels, and only genuine shared-source junctions receive dots.
    - Hover/focus highlights one complete connection and its two endpoint rows. Enter/Space and pointer selection persist the exact connection identity; fitting, resizing and graph projection changes preserve it. Selection/focus styling remains distinguishable from input/output semantics.
    - Dedicated input/output and combined connected marks render consistently in graph and table in Day and Control room, at narrow width and genuine 200% zoom. Accessible names retain input/output and relationship meaning without reliance on colour.
    - Diagram and Model explanation are distinct main views. Component Explanation, Python and Quantities occupy a full-width reading area below the graph, with no right-hand reader. Shared method prose appears only in model scope; a single-component method appears only with its actual owner.
    - Changing reading tabs preserves unsaved source, quantities and explanation drafts. Cross-owner/version navigation retains the existing dirty guards; historical readers do not fetch or show current source or approach content in place of their pins.
    - A row's Edit quantity details action selects its exact owner and opens/focuses its saved quantity's optional definition field. The isolated real HTTP units-ui-reading fixture proves edit/preview/save persistence across reload, including blank as optional absence. Cancel and stale/dirty paths remain guarded; saved versions expose no mutation action.
    - Table corners, row headings, cells and selected rows have coherent surfaces without white seams; empty and mixed-definition tables, explicit zero, unavailable values and units retain their meaning. Explorer portContent layout and interactions remain intact.
  </behavior>
  <action>
    Begin with failing assertions in the existing isolated browser suites for one complete path: select an individual connection, read its model explanation, open the selected component's Python/Quantities tabs and invoke the exact row's existing quantity editor. Then expand the same production path with the geometry and lifecycle cases below. Existing runner output is sufficient RED evidence; do not add a reporting adapter. One owner is necessary because routing, canonical selection, reader tabs and editor portals share the same files and lifecycle. Commit reviewable explicit-path changes within this batch.

    First amend the design system. Layouts replaces the previous graph-plus-Details prescription with a full-width Diagram / Model explanation primary switch and a component reader below the diagram using Explanation / Python / Quantities. Retain Graph / XDSM as diagram projections. Naming records these labels and Edit quantity details. ModelNode documents individually routed connections and direction/connection markers. DataTable documents one clipped surface, row-heading parity and full selected-row background. README and Scientific-states establish dedicated quantity-input teal and quantity-output rose roles in both themes; these describe direction, not health, success, provenance, inference or selection. Connected uses both hues in a split mark while retaining an inlet/outlet shape and Input/Output words. Use neutral text, accent selection and blue keyboard focus. Add required values to tokens.json and regenerate tokens.css with the existing generator. Record shared recipe/export adoption in Contour; preserve explorer calculated/estimated semantics and existing export palette. No hard-coded screen colours, inline styles, remote assets or dependency installs.

    Implement deterministic model-only routing in graphRouting.ts, consumed by GraphCanvas after measured node rectangles and port centres are available. Flatten each projection group into its actual links for model rendering; preserve the grouped projection for XDSM and existing consumers. Start each route at the specific source output and finish at the specific target input, never at a group's first ports. Allocate stable ordered orthogonal lanes using exact connection identities. Reserve space outside card rectangles for backward/feedback and bypass routes; round corners without entering obstacle clearance. Feedback remains dashed. Branches may share a trunk only when their source reference is identical; draw a dot only at a true shared-source junction, never at a crossing. Include complete route extents in Fit model. Render labels only where necessary to disambiguate a route, on reserved clear segments, with full mapping available in the accessible name/selected connection reader. Do not manufacture repeated truncated labels on top of nodes.

    Use visible endpoint marks, clear receiving arrowheads and readable strokes through the supported model zoom range. Adjust hit targets so nearby links remain individually reachable rather than letting a broad invisible path steal every neighbour's pointer. Pointer hover and keyboard focus identify the route and both endpoint rows; click/Enter/Space persist exact connection selection. Use current Selection contracts and traceRelationships; do not make hover rewrite persistent selection. Where the old inspector assumes a group, keep multi-link inspection available for XDSM while showing only the exact selected connection mapping in the diagram. Keep the separate portContent branch's routing, natural heights, plots, sliders and numerical colour roles unchanged. Shared changes still require its existing browser coverage.

    Move layout and semantic rendering into shared Foundry recipes and components. ModelNode and the table use one shared direction/connection marker contract; if a new exported component is introduced, add it to DesignSpecimen, the existing smoke render and Contour's inventory before acceptance (coordinate adding ui/design_smoke.mjs to ownership if needed). Maintain direction on connected quantities, e.g. Input with from-component relationship or Output with to-component relationship. Body prose and quantities stay neutral. Add the new role/background pairs to design-colors.test.cjs and inspect actual rendered samples in both themes: text must meet 4.5:1 and nontext direction marks 3:1. Do not reuse or recolour warning/success/scientific-basis tokens for these roles.

    Restructure ModelView so the diagram spans available width and the reader follows it in normal document flow. Remove the Details toggle/sidebar and the short narrative's ReadingContents duplication. Retain graph controls, search reveal, footer, explicit pan, ordinary document scrolling, Fit model, compact selection information and XDSM. A component heading owns the Explanation / Python / Quantities tabs; show one full-width quantities table at its existing canonical owner, scoped to selection, with its All components escape and keyboard sorting/filtering. Jump to Quantities activates the correct pane before focusing its heading. Connection selection shows its exact mappings without inventing a component owner. Model assumptions and model authoring actions remain reachable even when no component is selected. Long prose and expanded source never change the graph viewport height or create a narrow growing side column.

    Separate authored scope using existing MethodLink.instanceIds and exact approach/model pins. Multi-component methods belong in Model explanation, once each, with their real title, linked components, complete authored prose, evidence/assumptions and Method record. Single-component methods belong in that component's Explanation. Model explanation may link to those components for their local reasoning, but must not duplicate their prose. If no component-specific explanation exists, offer a concise link to the shared model explanation and retain its source/assumptions; do not repeat the shared text under each component or fabricate a purpose. Any topology summary is explicitly a structural list of current inputs, outputs and connections, not invented scientific rationale. Reuse ModelMethodDetails and the existing ApproachController for explanation edits. Existing modelling-approach navigation, guards, draft/saved states and immutable pins stay intact.

    Preserve editor identity while switching either tab level. ModelEditor and its authoring state must remain mounted; hidden panels must be inaccessible but must not discard their portals, local buffers or guard registration. Extend its host/render contracts only as needed to place explanation and Python in their correct readers. Source remains text, checked against the existing exact source hashes; source editing/import/preview never executes candidate code. Keep current save/discard/conflict behavior, instance-sharing controls, assumptions and authoring menus. ModelMethodDetails continues to edit existing approach records and requires explicit save. Do not create a second explanation store or silently publish an approach version.

    Repair the quantities table through shared DataTable/Foundry ownership: one surface and boundary with correctly clipped outer corners, consistent th/td background, full selected-row treatment, and a named local horizontal-scroll region when necessary. Remove the blanket absent-definition notice; preserve nonempty definitions and honest per-row absence in a mixed table. Keep redundant Component cells omitted in a single-component scope and retain an explicit owner action. Add a direct Edit quantity details action only where current draft authoring is supported. Send an explicit identity-bearing request through ModelView to the mounted ModelEditor; after guarded selection is accepted and the definition has loaded, open the existing quantity dialog and focus that exact port's optional definition field. Do not rely on array indices surviving a change of owner, bypass Workspace selection guards, or create a second metadata editor. Save uses existing component/definition edits, validation, public API commands and recovery. Cancel restores the correct invoking row/action. Existing unsaved new quantities still require their normal save before a definition can be attached.

    Update meaningful browser assertions for the new composition, not broad locators that accept either old or new behavior. Include five individual paths in the large model fixture; representative branch/merge/bypass/feedback fixtures; label/card and path/card geometry; exact route endpoints; distinct hit/focus targets; stable routing after selection; fit after resize; model versus component method scope; dirty source across tabs; saved-version controls; table edit persistence and surfaces. Cover empty/single-node models, long labels, scrolling, both themes, 390px width and genuine 200% zoom. Keep source tamper/unavailable tests, existing unit/schema readers, run/configuration/approach canonical reuse and explorer layout checks effective. Do not run a mutating served suite against the user's live installation.

    You are not alone in the checkout. Preserve unrelated ROADMAP/research edits, existing staging and all other contributors' changes. Run browser/build groups serially; parent owns live browser inspection and deployment refresh. Record exact commits, commands/counts, every failure, evidence identities and released or intentionally retained scopes in 1-CHECKPOINT.md. The known style gate has 61 unrelated findings; fix new owned-path findings without rebasing the baseline or formatting unrelated code. Do not call the whole repository green if those remain.
  </action>
  <verify>
    <automated>./hyprn-mvp dev check combined-static</automated>
    <automated>./hyprn-mvp dev check ui-reading</automated>
    <automated>./hyprn-mvp dev check foundry-nav</automated>
    <automated>./hyprn-mvp dev check units-ui-reading</automated>
    <automated>./hyprn-mvp dev check ui-navigation</automated>
    <automated>./hyprn-mvp dev check style-ratchet</automated>
    <human-check>Parent verifies the committed build's loaded assets in the requested live model, then inspects all five arrows, exact endpoint highlighting, Fit model, model/component explanation scopes, Python, table surfaces and row edit discovery without saving live scientific changes. Capture 1440 by 1000 in both themes, 1920 by 878 and 390 by 844; preserve the isolated genuine 200% zoom evidence. Save screenshots outside the repository and distinguish automated browser inspection from product-owner acceptance.</human-check>
  </verify>
  <done>The complete user journey and listed regressions pass on the committed UI; parent confirms the refreshed live page and asset identity. Design docs, generated tokens and shared recipes agree. Any unrelated style failure, unrun qualification and human-acceptance boundary are stated explicitly. No backend/API contract or live scientific records changed.</done>
</task>
</tasks>

<threat_model>
| ID | Boundary / category | Severity | Disposition and mitigation |
|---|---|---|---|
| T-03-MF-01 | API prose/source to rendered UI / tampering | high | Mitigate: existing text rendering, exact verified source reader, no HTML injection or candidate execution. |
| T-03-MF-02 | Reading tabs/row action to authoring owner / tampering | high | Mitigate: persistent editor identity, explicit port reference, guarded selection, existing public API validation and command recovery; saved versions cannot invoke edits. |
| T-03-MF-03 | Model method scope to scientific interpretation / information integrity | medium | Mitigate: exact method associations, shared/local separation, retained pin disclosures and no invented explanations. |
| T-03-MF-04 | Shared graph to numerical explorer / tampering | medium | Mitigate: preserve separate portContent branch and existing explorer browser regression. |
| T-03-MF-05 | Browser tests to live data / tampering | high | Mitigate: mutation tests use existing isolated fixtures; parent live check is read-only. |
| T-03-SC | Package supply chain / tampering | high | Accept for this scope: no installation or dependency changes. |
</threat_model>

<verification>
combined-static owns design/token/ownership/UI-contract/tooling/smoke/TypeScript/build checks. ui-reading covers route geometry, shared specimens, model reading and explorer cards; foundry-nav covers authoring and real browser zoom; units-ui-reading preserves source/schema/units and canonical historical model reading; ui-navigation preserves owner/version navigation. Parent runs the union once on the committed integrated tree under the delivery cadence amendment. If shared changes alter explorer behavior beyond the existing measured-layout branch, also run ./hyprn-mvp dev check exploration-answer-ui. Retain style-ratchet diagnostics, including unrelated failures. Full qualification remains deferred by DELIVERY-PLAN. API-shaped fixture evidence is not real service persistence; live read-only verification establishes the actual visual delivery only.
</verification>

## Source coverage

| Source | Item | Coverage |
|---|---|---|
| GOAL | Current local demonstration and user-approved model-flow redesign | Task 1 end-to-end path and parent live verification |
| REQ | UI-01 shared design/public API; UI-02 canonical model; UI-03 accessible themes/zoom/honest states | Task 1 shared recipes, existing API editors and named check groups |
| RESEARCH | Current groups anchor all links to first ports; portal editor owns local drafts; method links carry actual component scope; table wrapper overrides clipping | Task 1 measured individual routing, mounted editor, scope split and shared table repair |
| CONTEXT | Individual rounded arrows, teal input/rose output/dual connected marks, full-width views, scoped explanations, table cleanup and direct definition editing | Task 1, all accepted proposal items retained |
| CONTEXT | Scientific values, immutable exact pins, source verification, CSP, no new backend/store/dependency and isolated mutations | Task 1 retained invariants and threat mitigations |

Discovery is Level 0: existing React, SVG, public API and design-system patterns; no external library choice. The parent's explicit one-task request and current delivery cadence govern this cohesive shared-file batch. Existing wider Phase 3, release and human-acceptance obligations stay with their current owners.

<output>
Create .planning/phases/03-agent-tools-for-coding-agents/model-flow/1-CHECKPOINT.md. Parent owns integration/live-browser evidence and current-state reconciliation. Do not update ROADMAP or declare phase closure.
</output>

## Task 2 — Minimal model reading and precise editing

User-authorized follow-up in the same cohesive executor context. Own ModelEditor, ModelView, SelectionInspector, ModelMethodDetails if needed, SourceEditor, VariablesTable, views/model and styles.css; model-specific Layouts/Naming/DataTable/ModelNode rules; related existing model browser tests; narrow named-control checks and existing fixture adjustments only. Parent independently owns global assistant/context design files, foundry.css, design/index.ts and its tests. Preserve all unrelated changes.

Acceptance: a row's Edit quantity details opens only that saved quantity; general management stays on Component. Component / Python / Quantities retains dirty buffers and guards. Component shows the name, optional model-local explanation and existing owner-scoped method prose; one Edit component dialog edits name and explanation through the existing preview/public edit pipeline. Public set_annotation on the instance stores explanation in the model snapshot (architecture-and-contracts.md's model-local description semantics), with saved versions reading their exact annotation. No browser-local authored store or new API/backend/dependency. Shared approach prose and method pins remain independent. Python omits metadata actions and source expansion. Remove Jump to Quantities, Read component, scoped-table Inspect component, redundant missing-explanation navigation and the header save-version sentence. Align title/actions responsively.

Focused RED assertions cover selected-quantity isolation, combined component name/explanation persistence and removed controls. Existing real HTTP units fixture proves save/reload and saved annotation reads; API doubles remain explicitly identified. Focused checks use the pinned entrypoint and isolated scratch root; parent coordinates browser/build resources and runs the final committed union/live verification. Evidence root: `/private/tmp/hyprn-model-minimal-evidence`; scratch root: `/private/tmp/hyprn-model-minimal`. Record every failure, commit and remaining acceptance boundary in the existing checkpoint. This is not phase closure.

## Approved execution scope additions

Existing `ui/design_smoke.mjs` and `ui/check_ui_contract.py` assertions were updated for the shared direction mark and named scroll owner. `deployment/tests/units_ui_fixture.py` gained the already-supported schema-4 quantity definitions in its explicit private transport double so real HTTP save/reload could be exercised. No production backend, dependency or runner changed. Live visual review refined safe adjacent routes and removed nested model-reader framing. Exact deviations and verification are retained in `1-CHECKPOINT.md`.

## Task 3 — Component heading and preview assistant launcher

Owner: current session. User-authorized small follow-up: replace the redundant Component heading with one component-name SectionHeader and aligned edit actions; adopt the approved preview’s visible Assistant label and chat icon in the persistent shared launcher. Reuse existing tokens and preserve guards, stored records and navigation. Own ModelEditor, SelectionInspector, the obsolete title rule in styles.css, WorkspaceShell, only assistant rules in foundry.css, related design notes and two existing browser assertions. Preserve concurrent overview work. Acceptance: combined-static, ui-reading, ui-navigation and foundry-nav on the committed tree; live model verification in both themes and narrow viewport. No scientific mutation or backend change.
