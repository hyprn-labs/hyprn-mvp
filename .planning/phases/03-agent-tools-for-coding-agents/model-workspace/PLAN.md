---
phase: 03-agent-tools-for-coding-agents
plan: model-workspace
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [UI-01, UI-02, UI-03]
files_modified:
  - deployment/tests/test_style_ratchet.py
  - design-system/Layouts.md
  - ui/src/design/graph.tsx
  - ui/src/design/foundry.css
  - ui/src/design/components.tsx
  - ui/src/ModelView.tsx
  - ui/src/VariablesTable.tsx
  - ui/src/Workspace.tsx
  - ui/tests/evidence-workspace.spec.ts
  - ui/tests/study-navigation.spec.ts
  - ui/src/SelectionInspector.tsx
  - ui/src/ModelEditor.tsx
  - ui/src/views/model.tsx
  - ui/src/styles.css
  - ui/tests/screen-readability.spec.ts
  - ui/tests/foundry-zoom.spec.ts
  - ui/tests/unit-model-reading.spec.ts
  - ui/tests/model-configuration-run.spec.ts
  - ui/tests/record-labels.spec.ts
  - .planning/phases/03-agent-tools-for-coding-agents/model-workspace/1-CHECKPOINT.md
must_haves:
  truths:
    - Opening the current three-component model shows a useful graph; Fit model places all nodes and routed connections inside the visible viewport.
    - Component titles and quantity symbols remain complete and readable, and ordinary wheel scrolling predictably reaches Quantities.
    - Selection, search reveal, keyboard focus, grouped connections and XDSM preserve exact identities.
    - Details explains the selected component and any shared method without repeated identity and boxed prose; source, evidence, editing and record details remain reachable.
    - Draft and saved version controls explain editability and publication without presenting an opaque draft ID as the main label.
    - Shared answer-exploration graph content and existing authoring guards remain functional.
  artifacts:
    - path: ui/src/design/graph.tsx
      provides: Measured graph bounds, fitting and predictable viewport interactions
    - path: ui/tests/screen-readability.spec.ts
      provides: Browser geometry and interaction regression coverage
  key_links:
    - from: ui/src/ModelView.tsx
      to: ui/src/design/graph.tsx
      via: GraphView projection, selected identities and reveal targets
    - from: ui/src/views/model.tsx
      to: existing modelVersions.saveVersion and guarded navigation
      via: Existing public API authoring lifecycle
---

<objective>
Repair the model inspection journey requested by the user: first graph sizing, actual fitting, readable labels and scrolling, then Details and version controls. Target the current local demonstration and the existing canonical ModelView; stop after the committed UI passes focused checks and the parent verifies the refreshed live page. This is one cohesive numbered executor task under the current DELIVERY-PLAN cadence amendment, not closure of Phase 3 or full release qualification.
</objective>

<context>
@AGENTS.md
@.planning/DELIVERY-PLAN.md
@.claude/skills/hyprn-mvp-ui/SKILL.md
@design-system/README.md
@design-system/Layouts.md
@design-system/Scientific-states.md
@design-system/Contour.md
@design-system/Naming.md
@design-system/Coherence.md
@design-system/components/ModelNode.md
@design-system/components/ContextualPanel.md
@ui/src/design/graph.tsx
@ui/src/GraphView.tsx
@ui/src/ModelView.tsx
@ui/src/SelectionInspector.tsx
@ui/src/ModelEditor.tsx
@ui/src/views/model.tsx
@ui/src/ModelMethodDetails.tsx
@ui/tests/screen-readability.spec.ts
@ui/tests/foundry-fixtures.ts
</context>

<tasks>
<task type="tracer" tdd="true">
  <name>1. Make the canonical model readable and navigable from graph to component details</name>
  <files>design-system/Layouts.md, ui/src/design/graph.tsx, ui/src/design/foundry.css, ui/src/design/components.tsx, ui/src/ModelView.tsx, ui/src/SelectionInspector.tsx, ui/src/ModelEditor.tsx, ui/src/views/model.tsx, ui/src/styles.css, ui/tests/screen-readability.spec.ts, ui/tests/model-configuration-run.spec.ts, ui/tests/record-labels.spec.ts, .planning/phases/03-agent-tools-for-coding-agents/model-workspace/1-CHECKPOINT.md</files>
  <behavior>
    - A three-component model with unequal port counts and long names fits its complete node/connection bounds at desktop widths, including 1920 by 878; Fit model still works after pan, zoom, Details toggle and viewport resize.
    - Empty and single-component models have finite geometry and honest empty content. A dense model remains navigable through zoom, focus and search reveal without clipped labels or inaccessible ports.
    - Ordinary wheel input over the model moves the document toward Quantities without nested graph/main-panel scrolling; explicit pan and keyboard actions move the graph. Narrow layout and genuine 200% browser zoom retain controls without horizontal page overflow.
    - Selected component, quantity and connection identities survive fitting and Graph/XDSM changes. Search reveal brings the target into view and transfers keyboard focus to it; the footer reflects actual selection.
    - Draft and saved-version labels remain distinguishable; changing version uses existing guards and saving uses the existing command lifecycle. Source/explanation editing, cancellation and dirty-navigation protections remain intact.
    - Answer explorer GraphCanvas portContent retains natural-height cards, readable plots/sliders, zoom and correct connecting paths.
  </behavior>
  <action>
    Start with failing browser assertions in the existing isolated screen-readability harness. Model the reported three-component, many-port case using public-API-shaped records; include empty and single-node cases and retain existing distant search-reveal coverage. Assert actual bounding boxes, document/viewport scrolling and focus, not source strings or mere element presence. Existing connected-views.spec.ts is a served-installation suite with stale control expectations; do not run it against the user's live store or expand this repair into rewriting that suite.

    First update only the Models section of design-system/Layouts.md to record the user's authorized visual amendment: prioritize working graph area, measured Fit model, full labels, predictable document scrolling and quieter Details/version controls. Preserve canonical model ownership, exact identities, scientific state wording and source verification. The user's request supersedes the old fixed-height, UUID-first and repeated action ordering prescriptions for this repair.

    Implement graph geometry in the shared GraphCanvas and ModelNode recipes. Replace hard-coded two-column/global-max-port spacing with layout that uses available width and actual per-node dimensions, choosing a readable compact arrangement for three components. Measure wrapped headings and port rows so node bounds and connection anchors agree; include routed curves/labels in fitting bounds. Fit model computes a finite viewport-to-content scale and centered translation with padding, resets obsolete scroll offsets and is a visibly labelled action. Auto-fit initial model content and respond to container changes without continuously overriding intentional user pan/zoom. Keep explicit zoom and Focus selection, use actual selected bounds, and make search reveal reliable after any transform. Handle zero-sized/hidden containers, missing measurements and empty projections without NaN or oscillating resize updates. Use SVG attributes for geometry and existing token-driven classes; retain CSP compatibility.

    Render complete component names and symbols with wrapping and suitable width instead of ellipsis. Fit alone is insufficient if the real three-component/30-port model becomes illegible: use the recovered workspace width, compact token-based row spacing and a three-node left-to-right arrangement where it fits, then verify label readability in the actual browser. Keep arrow direction, grouped-link selection and access to individual endpoint mappings; selection cannot imply all quantity rows are individually chosen. Do not alter the model graph or scientific content to improve its presentation. Preserve the separate portContent branch's natural measured heights and interactive plots/sliders; model canvas changes must not impose fixed-height or clipped explorer cards.

    Expand useful model width and reduce redundant vertical chrome through the existing workbench/shared recipes. Scope model layout changes so other pages are unaffected unless an intentional shared improvement is covered by their tests. Remove competing overflow containers around the graph; use ordinary document scrolling for reaching Quantities, a single intentional graph pan surface, and a visible Quantities shortcut that scrolls/focuses its existing section. Keep its wide data in its existing named local scroll region. On narrow screens stack Details after the graph with all controls reachable. Update footer guidance to match current selection.

    Simplify Details in SelectionInspector, the ModelEditor authoring slot and Foundry styling: one component heading, compact actions associated with that component, one clearly scoped shared-method notice, flowing Purpose/Basis and reasoning/Calculation logic content, and a Python function disclosure followed by Method record. Keep complete authored prose, evidence, assumptions, all existing edit actions, source hash checks, focus restoration and exact method-version context. Reduce repeated borders, nested cards and navigation chrome without removing the useful section jump behavior for long content. ModelMethodDetails behavior is reused; change its callers/layout only unless a concrete required behavior cannot otherwise be preserved.

    Follow-up browser findings: keep the three-component graph and footer within the initial 1920 by 878 document viewport through compact navigation and controls; prefer three desktop columns from 720px canvas width for readable fit at 1440. Wrap creation buttons as whole controls on narrow screens. In Quantities, omit repeated Component cells for a single-component scope while retaining an owner action; omit Definition only when all visible definitions are absent, using one honest notice for nonempty results. Keep mixed definitions, empty results and scientific value states.

    Make version controls read Current draft and human-readable saved-version labels derived from existing record fields; retain exact option values, distinguish saved versions reliably and keep complete identities in Model record details. Retain the shared Saved draft / Unsaved changes / Saved version read-only states. Place a concise explanation by Save model version that this creates a saved read-only version; do not imply an automatic publication, alter current dirty/save guards or fabricate version dates/numbers. Preserve configuration creation and all model actions, and show editing/publication controls only in their existing valid lifecycle context. Adjust affected tests for the intentional labels while keeping behavioral assertions.

    You are not alone in this checkout. Touch only owned paths, preserve unrelated edits and staged entries, install no packages and make no API/backend changes. Run focused checks through the local entry point serially to avoid contested browser/build resources. Commit explicit paths atomically. Write the checkpoint with tested commit, exact commands and counts, every failure, evidence/scratch identities and cleanup, plus any unverified items; parent owns live refresh and browser acceptance.
  </action>
  <verify>
    <automated>./hyprn-mvp dev check combined-static</automated>
    <automated>./hyprn-mvp dev check ui-reading</automated>
    <automated>./hyprn-mvp dev check foundry-nav</automated>
    <automated>./hyprn-mvp dev check style-ratchet</automated>
    <human-check>Parent refreshes the requested live model page through the existing local deployment mechanism, confirms loaded asset identity, and inspects Fit model, full labels, pan/zoom, page scrolling to Quantities, selection/search/Details, draft and saved-version reading at 1920 by 878 and 1440 by 1000 in both themes plus narrow and genuine 200% browser zoom. Save screenshots outside the repository. Existing live authoring records are read only during browser verification; mutation regression belongs to scoped fixtures. Record this as automated browser inspection, separately from product-owner acceptance.</human-check>
  </verify>
  <done>Focused checks pass on the committed UI; all listed visible behaviors are demonstrated in isolated browser tests; the parent has refreshed and verified the actual model page and reported the remaining qualification/human-acceptance boundaries. No scientific records or backend contracts changed.</done>
</task>
</tasks>

<threat_model>
| Boundary | Protection |
|---|---|
| API record text to browser | Keep React text rendering and verified source reader; do not introduce HTML injection or candidate execution. |
| Draft/version navigation to public API | Preserve existing authorization, dirty guards, command receipts and exact IDs. |
| Shared graph to answer explorer | Isolated explorer regression protects controls, values and unavailable states. |
| Test runner to live installation | Existing scoped fixtures only; no served mutation suite pointed at the user's page. |
| Package supply chain | No dependency install is part of this task. |
</threat_model>

<verification>
combined-static owns design, ownership, tokens, contract wiring, tooling, smoke, TypeScript and scoped build checks. ui-reading covers the changed reader, new graph cases and existing exploration geometry; foundry-nav covers authoring/version lifecycle and zoom. style-ratchet protects source conventions. If changes affect unit/source interpretation or explorer scientific behavior, or focused failures reveal such a concern, additionally run ./hyprn-mvp dev check units-ui-reading and ./hyprn-mvp dev check exploration-answer-ui respectively; otherwise record them as not run for this UI repair. Browser fixtures use API-shaped doubles and do not prove real service integration; parent live read-only verification closes that visual delivery boundary. Full release qualification is deferred by the current DELIVERY-PLAN amendment.
</verification>

## Source coverage

| Source | Scope item | Coverage |
|---|---|---|
| GOAL | Current DELIVERY-PLAN local UI demonstration; user-requested model repair | Task 1 and parent live browser check |
| REQ | UI-01 public API/design-system ownership; UI-02 canonical model; UI-03 keyboard, themes, zoom and honest state | Task 1; static and browser checks |
| RESEARCH | Inspected graph uses global maxPorts rows, fit resets to 100%, wrapped content bounds differ; nested overflow and repeated Details chrome | Task 1 geometry, scroll and reader changes |
| CONTEXT | User priority: graph sizing, fit, full labels, scrolling, then Details/version controls | Task 1 implementation order |
| CONTEXT | Existing scientific, exact-pin, source-verification, CSP and scratch isolation guarantees | Task 1 retained behavior and verification |

Discovery: Level 0, existing React/design-system/public API patterns, no external integration or dependency. Original Phase 3 agent-platform requirements remain under their existing owners; this local UI repair does not claim their delivery.

Execution scope amendment: truthful quantity selection required the existing VariablesTable row state and Workspace.select owner guard; their narrow fixes and affected version-label assertions in evidence-workspace/study-navigation are included. The style-ratchet test now prints its complete failure diff (maxDiff=None) so unrelated violations can be distinguished without changing its baseline. The existing check runner's unmodified Playwright JSON and assertion output are the RED evidence for this visual task; no reporting adapter or runner change is required.

<output>
Create .planning/phases/03-agent-tools-for-coding-agents/model-workspace/1-CHECKPOINT.md. Parent records integration/browser evidence alongside it; do not update ROADMAP or STATE from this task.
</output>
