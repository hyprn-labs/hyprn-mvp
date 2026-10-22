# HYPRN engineering pattern map

> Retired 2026-10-18: `WorkflowNavigation` (superseded by NavigationRail) and `ClaimButton` with statement sets (statement panels are retired). Rows below that name them are historical.

Design catalogue for the Contour lane, 2026-10-15. This document defines presentation and interaction requirements; it does not declare a feature implemented or a scientific judgment established. [Contour](Contour.md) owns visual foundations, [Scientific states](Scientific-states.md) owns scientific meaning, and [domain language](../CONTEXT.md) owns entity names. The public contract and the owning record remain authoritative.

## Scope and reading key

The catalogue covers **58 families: 10 foundations, 27 controls/content components, 17 composites and 4 communication patterns**, followed by engineering-specific supplements. Each family has one disposition:

- **Present**: an existing shared component or behavior can carry the pattern. This includes work visible in the current Contour foundation; presence is not committed-tree qualification or human acceptance.
- **Adapt now**: a presentation change within existing records and actions, owned by C2/C3 after the orchestrator updates their task scope. It grants no new backend capability.
- **Future**: requires a named scientific, identity, document or assistant capability outside this lane.
- **Not applicable**: omit the domain meaning entirely; do not manufacture an engineering equivalent.

Names in the tables are HYPRN pattern names. Component references identify reuse points, not permission to edit another task's files. The reconciliation below names implemented shared components and remaining capability boundaries. Future designs are absent from production navigation until their public capability is available.

## Engineering lifecycle

The working area supports a sequence of questions, not a wizard that awards completion:

| Journey | What the engineer needs to see | Existing home and owner | Boundary / future prerequisite |
|---|---|---|---|
| Define the question and criteria | Question, scope, limits, intended cases; requirements with quantities, thresholds and units | Overview question and owning study/Modeling approach records; configuration criteria through `CriterionRecord` | The question does not automatically become executable criteria. A person or authorized agent authors the interpretation. |
| Compare models and cases | Methods, assumptions, model versions, input provenance, criterion differences and limits of comparison | Models, Calculations; `ComparisonView`, `ModelView` | Existing comparison aligns records, not scientific equivalence. A ranked alternative-selection system requires its own explicit decision model. |
| Calculate and explore | Explicit inputs, saved configuration, run action, results and unavailable reasons; estimated versus calculated values | Configurations, Runs; separately owned `AnswerExplorer`, `QuantityResult`, `ResponseCurve` | New sampling, uncertainty, optimization and solver behavior require their own contracts and numerical qualification. A UI interaction cannot supply them. |
| Assess claims and evidence | Full statement, scope, basis, qualifications, supporting and challenging material, source/run context | Assumptions, findings, study answers; `Assumptions`, `ApproachFindings`, `EvidenceRecordBody` | A statement's scope and basis cannot be inferred from layout, sentence proximity or chat text. |
| Record the decision | Answer to the question, alternatives considered, reasons, unresolved obligations and cited versions | Current answer presentation separates observations, interpretation, qualifications and still-to-answer items | A formal decision/review record, reviewer authority or approval workflow is Future. Do not label an existing answer as an approved decision. |

Navigation names remain Overview, Models and Calculations. The current Overview design direction is **question → generic exploration canvas → interpretation and still-to-answer items**. Methods remain with the canonical Model owner; this catalogue does not introduce a competing methods layout in Overview. Evidence remains reachable from its statements and existing direct links. The lifecycle describes how those homes work together; it adds no duplicate model graph, scheduler, completion percentage or validity score. The current view registry and editor guards continue to own movement between them. See [product workflow](../docs/product/overview.md), [Layouts](Layouts.md), [view registry](../ui/src/views/registry.ts) and [operation ownership](../docs/specs/architecture-and-contracts.md); the parent reconciles the newer Overview direction with legacy layout documentation in its owned work.

## Complete family catalogue

### Foundations — 10 families

| # | HYPRN family | Disposition | Shared owner / concrete rule |
|---|---|---|---|
| 01 | Semantic tokens | Present | `tokens.json`, generated `tokens.css`, Foundry recipes. Component code consumes semantic roles; change shared values centrally. |
| 02 | Meaningful colour | Present | `StatusTag`, existing colour roles. Interaction, focus, provenance, assistant attribution and outcome colours keep distinct meanings in both themes. |
| 03 | Interface and scientific typography | Present | Contour interface font; `Readout`, `SourceSurface`, number formatting. Units, symbols, identities and source preserve the scientific monospace roles. No imported type scale. |
| 04 | Spacing and density | Present | Existing spacing/control tokens. Compact scientific tables remain legible; touch and wrapped controls grow rather than clipping. |
| 05 | Curvature hierarchy | Present | Contour radius tokens. Outer canvas, panels, controls and chips have related curvature; semantic status shapes are unchanged. |
| 06 | Elevation | Present | `Panel` and Foundry shadow tokens. Use depth for structural layers; read-only content gets no false clickable hover behavior. |
| 07 | Surface and texture | Present | Shell ground, working canvas, raised panels, sunken wells. Static neutral texture stays in chrome, away from text, numbers, plots and source. |
| 08 | Motion and reduced motion | Present | Shared motion recipes. Animate visibility changes without altering scientific geometry; reduced motion must work for CSS and behavioral transitions. |
| 09 | Action and status glyphs | Present | Independently authored `ActionIcon` and `StatusTag`. Name actions accessibly; no icon font or external glyph assets. |
| 10 | Product identity | Present | `BrandLogo`. Preserve supplied logo bytes and notices; do not create alternate marks from decorative patterns. |

### Controls and content — 27 families

| # | HYPRN family | Disposition | Existing reuse / adaptation or missing prerequisite |
|---|---|---|---|
| 11 | Action hierarchy | Present | `Button`, `ActionGroup`. One primary per action scope; quiet, secondary and destructive actions retain meanings and full labels. |
| 12 | Person and resource identity marks | Adapt now | Reuse `AttributionChip`; add only neutral resource marks backed by actual record kinds. Profile identity is available; team directory and organization membership are Future. No authority implied by an avatar. |
| 13 | Action chips, labels and counts | Adapt now | `SourceChip`, `StatusTag`, `Button`. Keep read-only labels visually distinct from actions. `ClaimButton` counts statements as specified below. |
| 14 | Outcome and attention markers | Present | `StatusTag`, `Ledger`, `RecordState`, `RunOutcomes`. Preserve HYPRN's actual facets; do not reduce them to three generic statuses or a severity ladder. |
| 15 | Statement and evidence attachment | Adapt now | `Assertion`, `AssertionList`, `EvidenceStack`, `EvidenceRecordBody`. `ClaimCard` composes these; sources remain attached to the statement they qualify. |
| 16 | Form fields and selectors | Present | `Field`, `TextInput`, `TextArea`, `Select`. Blank remains unassigned; preserve field errors, unit choices and exact entered values. |
| 17 | View tabs and set navigation | Present | `Tabs`, `DetailTabs`, registry navigation. Distinguish views of one record, entity destinations, filters and pagination; don't re-route by visual labels. |
| 18 | Short help and full-label reveal | Adapt now | Shared control help and accessible descriptions. Tooltip is supplementary; full statement/source content opens in a reader. Keep tooltips outside clipping surfaces and reachable on keyboard focus. |
| 19 | Resource list row | Adapt now | Study/model/configuration/run lists in `Workspace` and views. Clear primary destination with separate archive/restore or resource actions; never nest buttons inside a whole-row button. |
| 20 | Loading placeholders | Adapt now | `Progress` and section loading states. Reflect the expected content shape only; never use plausible numbers or finished claims as placeholders. Keep known partial content and label its scope. |
| 21 | Suggested assistant questions | Future | Requires connected assistant delivery, context binding and send lifecycle. Until then show no enabled suggestion that pretends to submit a message. Parent owns the assistant integration. |
| 22 | Resource action menu | Adapt now | Existing Model actions and shared button/dialog controls. Reuse one accessible menu recipe, support Escape/return focus, and expose only available actions. Destructive entries remain explicit. |
| 23 | Edit and confirmation dialog | Present | `DialogFrame`, `ActionDialog`. Preserve native modal behavior, safe initial focus, unsaved-edit guards and restoration to the invoking control. Closing a reader is neutral, not destructive. |
| 24 | Record cards | Adapt now | `Panel` plus shared reading/action compositions. A card may be a passive record, one destination, or a resource with distinct actions; its semantics must match. Full text is reachable without sacrificing zoom reflow. |
| 25 | Quantity summary card | Adapt now | `Readout`, `QuantityResult`. Include quantity meaning, units, exact context and source/run link; missing output has a reason. Do not cherry-pick arbitrary outputs from a run's complete output table. |
| 26 | Model/configuration comparison card | Adapt now | `ComparisonView` and canonical model/configuration readers. Show real compared identities and changed assumptions/inputs; no invented best-option rank or similarity percentage. |
| 27 | Collaborator card | Future | Workspace membership, invitations, reviewer permissions and attributed review API must exist first. An existing record attribution chip is not a collaboration directory. |
| 28 | Composition member card | Adapt now | `ModelNode`, `SelectionInspector`, `ModelMethodDetails`. Instance identity and pinned definition remain distinct; repeated definitions never collapse distinct instances. |
| 29 | Evidence catalogue card | Adapt now | `EvidenceIndex`, `EvidenceRecordBody`, `EvidencePicker`. Present existing evidence content and version, not a news feed. Uploaded-document previews require the separately owned document capability. |
| 30 | Limitation / unresolved concern card | Adapt now | Existing assumptions, limits and answer qualifications. Show the condition, consequence and recorded basis; do not infer a risk score or use warning colour for every assumption. |
| 31 | Financial exchange card | Not applicable | No investment/deal transaction entity in this lane. Computational records are not financial transactions; reusable comparison belongs in tables, not this domain metaphor. |
| 32 | Alternative source selection card | Future | Needs an explicit scientific comparison scope: same quantity, units, conditions, dates, method and retained source versions. Current evidence links can show disagreement; they do not choose which number is true. |
| 33 | Sourced / derived quantity pair | Adapt now | `Readout`, `QuantityResult`, provenance links. Label each basis and unit; computed derivation must link to the real run. Never average discordant sources just to fill a summary. |
| 34 | Scientific chart | Present | `ResponseCurve`, graph/XDSM renderers and existing chart rules. Preserve data geometry, units and unavailable gaps. Future uncertainty bands need real sample/method provenance, not illustrative distributions. |
| 35 | Sensitivity / applicability explanation | Future | Requires supported numerical method, declared applicability conditions, returned effects and validation. No generic fit ladder, inferred driver bars or confidence meter. |
| 36 | Multi-select, exclusive choice, immediate preference | Adapt now | `Checkbox`, `Select`, shared controls. Checkbox selects independently; one-of-set selection is exclusive; immediate theme preferences differ from saved scientific settings. Partial selection must not look like all selected. |
| 37 | File choice and transfer | Adapt now | `FilePicker` and existing model import flow. Preserve validation and recovery, visible file identity and permitted action. Rich document uploading/progress is Future until its service returns those states. |

### Workspace and contextual composites — 17 families

| # | HYPRN family | Disposition | Existing reuse / adaptation or missing prerequisite |
|---|---|---|---|
| 38 | Location and resource action header | Adapt now | `SectionHeader`, `ActionGroup`, `Workspace`. Keep the real breadcrumb/current record legible; actions wrap at zoom. Avoid duplicate titles, navigation or record controls. |
| 39 | Persistent application navigation | Present | `NavigationRail`, `WorkspaceShell`, `studyTabs`, existing guarded callbacks. Current study context, Home and Profile remain real destinations. Collapse/stack must preserve every destination and its accessible label. |
| 40 | In-page contents navigation | Adapt now | Shared navigation for an actually long reader, using existing sections/anchors. This is optional within the central canvas; it must not duplicate the study navigation or invent a second Modeling approach map. |
| 41 | Contextual assistant pane | Adapt now | `AssistantPane` slot adjacent to the work area. Show actual connection/capability state. Connected chat, tool dispatch, streaming and history are Future/separately owned; unconnected UI has no enabled send action. |
| 42 | Contextual record panel | Adapt now | Compose shared `Panel`, reader content and navigation controls; `ContextualPanel`. Own presentation and an ephemeral back stack only. The screen owns guarded navigation and exact record reads. |
| 43 | Composite decision score panel | Not applicable | No overall scientific validity, authority, readiness-to-decide or engineering fit score. Show independent criteria, execution, limitations and explicitly supported numerical facets. |
| 44 | Current study context panel | Adapt now | Existing Study details / Overview content. Question, rationale, scope and limits retain their owner; don't offer an action that silently duplicates the current study. |
| 45 | Related resource panel | Adapt now | Canonical model/configuration/run readers and `WorkspaceLink`. Caption why this record was opened using the actual relationship; current names never overwrite historical content. |
| 46 | Person and review context panel | Future | Requires identity/membership and attributed scientific review records. Preserve current attribution only; a person's role or avatar never proves expertise or independence. |
| 47 | Alternative method appraisal panel | Future | A comparative argument requires scoped assumptions, supporting/challenging evidence and an authored assessment of the same engineering question. Current record diffs alone do not provide it. |
| 48 | Limitation / objection reader | Adapt now | Existing assumptions, qualifications and open deliverables in full. Keep all recorded evidence visible, including conflicting or unavailable sources, with no auto-generated risk ranking. |
| 49 | Deal-event detail panel | Not applicable | Do not reinterpret business-deal terms as run outcomes. Use the existing saved-run/configuration reader for computational history. |
| 50 | Equity ownership panel | Not applicable | Scientific authorship, workspace access and computational dependencies are separate concepts. None should use equity/holding proportions. Future workspace access uses its own permission contract. |
| 51 | Method step reader | Adapt now | Existing method content, canonical model view. Methods stay with the Model owner, not a new Overview method layout. Preserve purpose, basis, calculation logic and source; scope any statement count to the displayed step and its version. |
| 52 | Conflicting evidence / uncertainty reader | Future | Requires comparable evidence conditions and supported uncertainty outputs. Current sources may be inspected side by side without statistical pooling; a disagreement range is not a confidence interval. |
| 53 | Question and criteria context | Adapt now | Study question plus configuration-owned `CriterionRecord`. Keep original intent and its formal interpretation distinct. Missing criteria offer the existing authoring route; no automatic criterion derivation. |
| 54 | Claims and evidence reader | Adapt now | `ClaimButton` / `ClaimCard` / contextual reader over existing assumptions and answer records. Exact scope, count semantics and source/back behavior are specified below. |

### Communication — 4 families

| # | HYPRN family | Disposition | Existing reuse / concrete rule |
|---|---|---|---|
| 55 | Optional explanatory disclosure | Present | `Disclosure`. Put background explanation inside; prerequisites, blocking errors and unavailable reasons remain outside and visible. |
| 56 | Scoped error and recovery | Adapt now | Existing field/section/API errors composed with shared status and actions. Preserve unaffected content and drafts. Name the affected record and a safe action; unknown command outcomes require reconciliation, never automatic replay. |
| 57 | Loading, running and cancellation | Present | `Progress`, stored run outcomes and existing command state. Show measured counts or a named indeterminate stage; no invented ETA. Cancellation is requested until confirmed. |
| 58 | Empty, absent, unavailable and partial | Adapt now | Shared reading states, `StatusTag`, evidence-index coverage. Distinguish no saved content, filter no-match, access loss, failed read and uncomputed output. A zero count requires a complete known set. |

## Claims, cards and compact count controls

“Claim” is a reading concept in this catalogue, not a new persisted entity. A card must retain its actual domain name: Assumption, Observation, Interpretation or the relevant answer heading. An assumption remains an assumption even if it has several supporting sources. Existing answer records own observations, interpretation, qualifications, remaining deliverables and answer-level basis. [Assumptions implementation](../ui/src/Assumptions.tsx), [answer reader](../ui/src/ApproachFindings.tsx), [evidence reader](../ui/src/EvidenceView.tsx) and the [public contract](../contracts/hyprn-mvp.openapi.yaml) establish the current boundaries.

### Compact ClaimButton

`ClaimButton` is a shared presentation control, composed from `Button` with a count. It is not an evidence badge or a source-authority indicator.

| Situation | Required behavior |
|---|---|
| Passage scope | Place one compact action beside/below the passage when an explicit association identifies its actual statement set. Accessible name includes count and passage purpose. The reader caption states that these statements are cited in this passage. |
| Section scope | Place the action with the section heading; count the distinct statements belonging to that section's explicit owner/version and currently specified scope. Opening selects that exact set. |
| Statement identity | Use the existing owner's stable item identity plus its version/context. Two statements with identical words under different owners are not interchangeable. Repeated references to the same identity in one set count once. Never deduplicate by text. |
| Count meaning | Count statement records/items, not attached sources, runs, source references, paragraphs, support links or rendered cards. Adding evidence changes the source list, not the statement count. |
| Known empty set | Show plain “No linked statements” where explanation is needed, or omit the optional count action. Preserve the existing omission of zero-count links; no dead enabled button. |
| Unknown or partial set | Show an explicit loading/unavailable/partial explanation. Do not display zero or silently turn “loaded items” into a total. Filters state whether they cover loaded items or the full set. |
| Several groups | Each group names its owner and has its own count. A total is a union of actual identities, not a sum that double-counts shared statements. A single group needs a heading, not a lone tab. |
| Answer-wide basis only | Offer a clearly named answer-basis action. Do not split narrative into allegedly supported claims or count evidence as claims. Full passage-scoped associations remain unavailable until an authoritative association is supplied. |

A compact count supplements the existing direct evidence action beside every assertion. It must not replace “View evidence” with an obligatory aggregate dialog. This preserves [Coherence](Coherence.md) rule 3: evidence still opens directly; the new count enumerates statements. No extra mandatory click is added to an existing source-reading journey.

### ClaimCard

The shared `ClaimCard` composes `Assertion`, `EvidenceStack`, reading sections and existing record actions. It is a full reader, not a selectable truth rating. Keep these parts together:

1. **Statement and meaning.** Full text with line breaks, domain kind and actual authored/agent attribution where available. No truncation in the contextual reader. A compact card may summarize only when opening it reveals the complete saved text.
2. **Scope and limits.** The owning study, approach/model/configuration/answer version, component, and the conditions or qualifications actually recorded. Show a missing scope explicitly; never infer one from the current page.
3. **Basis.** Display each recorded support, challenge or context relationship in words. Include all evidence versions and associated run/configuration links; keep source relationships local to the statement. An unlabeled answer-wide basis remains answer-wide, not silently classified as supporting every sentence.
4. **Scientific result.** When the statement cites a run, show its recorded quantity, units, availability reason and exact version context through the canonical reader. Execution and criteria remain separate from the statement's scientific interpretation.
5. **Record details.** Full identities, timestamps, hashes and immutable relationship context stay accessible through existing secondary record actions. The human-readable title leads; hashes do not become card headings.

Unknown relationships say “Relationship not recorded” or remain in an accurately named basis list. Missing links stay visible with an unavailable reason. Never fabricate a support/challenge relationship, a quotation, an exact passage locator, an author, a review status or a confidence tier. Neither source count, age, publisher identity nor repeated agreement yields “verified”.

### Source snippet and back stack

Selecting a source from the contextual reader pushes its existing evidence view into the **same contextual panel**. The source reader shows exact retained evidence text and references. A quoted passage is allowed only when the exact source text and locator are actually available; a free-text citation or evidence note is not proof of an authenticated source excerpt. If only evidence content is retained, label it as evidence content and offer its real references. State that a source passage is unavailable rather than constructing one.

Before pushing, keep the invoking control, owning record/version, active group, selected statement, source relationship, filters and scroll offset in ephemeral view state. Back restores that state and keyboard focus. Closing restores the original canvas trigger/selection. Opening another source replaces the active source view through the same navigation owner; it does not create nested floating readers. A separate permitted source destination is labelled as such and still preserves a way back. Do not introduce external links or remote fetches merely because a source reference contains a URL.

The contextual reader is read-only. Draft authoring stays at the existing record owner and passes its normal unsaved-change guard. A version/session/study change invalidates pending reads; access loss clears protected content, source snippets and back-stack data. Historical views continue reading their stored evidence, with no “latest source” substitution.

## Workspace composition, assistant and settings

Use four coordinated regions: persistent left navigation, central working canvas, one contextual reader, and a separately controlled assistant pane. “Canvas” means the current study/model/configuration/run reading or editing surface; only the existing model view owns model topology. A page-contents list is an optional subordinate navigation aid inside that work area, not a fourth global navigation system.

The shell receives real registry destinations, existing guarded callbacks and reader/assistant slots. It owns sizing, collapse and focus presentation; it does not fetch scientific records or hold authoritative state. The central area must retain a useful width when a reader opens. At narrow widths and genuine 200% zoom, provide one reachable stacked or drawer presentation with a visible close/back path. Do not squeeze four columns into the viewport or hide scientific values behind a permanently overlaid chat composer.

The contextual panel has a stable title, explicit scope caption, a scrollable body and Back/Close controls. It can show a claim set, single claim, evidence content, question/criteria or an existing record. Opening a new context preserves the canvas selection until intentional navigation changes it. Escape affects the top active layer only; a modal drawer traps focus while open and restores it on close, whereas a docked nonmodal panel must not trap the entire application. Hidden panes are not keyboard destinations. Full text stays available after title truncation.

The adjacent assistant names the current study and the specific selected record/version or states that no context is attached. It must not silently retarget a drafted question when selection changes. The current lane provides a truthful disconnected/unavailable state and slot contract; actual sends, cancellation, error recovery, tool activity and transcript retention belong to the assistant owner. A proposed conversational response remains separate from a saved scientific answer. User messages, assistant interpretation, tool activity and saved run results are visibly distinct. No local simulated conversation appears as authoritative history.

Settings use the existing Profile account/sign-out capability and local theme preference. A local theme is a presentation preference; it never changes units, source values, execution settings or scientific records. Workspace selection, invitations, roles, organization settings and provider configuration are Future and are not decorative disabled menu items. “Workspace” may describe the screen composition, but does not imply that a multi-user Workspace backend is delivered.

## Engineering supplements and exceptions

| Capability | Current / future mapping | Required scientific exception |
|---|---|---|
| Quantities table, filter and list coverage | Present: `DataTable`, `VariablesTable`, configuration/run tables | Keep units, provenance and unavailable reasons with values. Name filtering scope; page counts and selection counts describe actual sets. No hidden defaults or blank numeric cells. |
| Source/code reader and model structure | Present: `SourceSurface`, `ModelView`, `GraphCanvas`, XDSM | Source is text until authorized contained execution. A decorative curve must not change graph coordinates, port alignment or edge meaning. Diagram exports keep their own approved palette. |
| Numerical inputs and units | Present: `Field`, `UnitEditor`, provenance editors | Only finite real scalars; reject booleans/nonfinite/unsafe values. Unit transformations are explicit and inspectable. Empty differs from zero; physical defaults are never inferred from a visual control. |
| Method fidelity and applicability | Current recorded assumptions/limits; richer checks Future | State approximation, intended regime and limits where recorded. A higher-fidelity model is not automatically better for every question. Do not rank fidelity without an authored criterion and evidence. |
| Criteria and feasibility | Present: `CriterionRecord`, stored run outcomes | An output can meet a criterion under an inapplicable model. A met criterion, completed run or saved record does not establish feasibility, validity or approval. |
| Exploration and estimation | Present in the separately owned exploration feature | Preserve estimated/calculated distinction and returned coverage. A response curve is not permission to interpolate beyond its declared method or recompute in the browser. |
| Uncertainty and confidence | Future method-specific quantitative uncertainty | State method, distribution assumptions, dependence, coverage and sample count. Measurement uncertainty, numerical error, model discrepancy and confidence in an interpretation differ. A range across publications is not a probability interval. |
| Evidence conditions and disagreement | Current evidence/assumption links; structured comparison Future | Keep material, scale, operating regime, boundary conditions, units, method and date when available. Contradictory sources remain visible. No silent pooling or source-authority rank. |
| Exact pins and history | Present throughout model/configuration/run/evidence readers | Reopening an old run uses the model, inputs, source and evidence it used. New names, newer versions and agent summaries never replace history. |
| Recorded decision and review | Existing scientific answers; formal decision/review Future | Preserve author, purpose, exact subjects, limitations and unresolved objections. A reviewer role is not scientific endorsement; agent-recorded reviews must remain attributed. |
| Collaboration and reusable methods | Future workspace/identity and method-package contracts | Access management is separate from scientific approval. A method package application does not approve its applicability to a new study. |

## Interaction acceptance matrix

These are acceptance requirements for implementation, not a report of checks already passed.

| Journey / failure case | Observable result |
|---|---|
| Read a passage with two explicit statements and several shared sources | Count is two; both full statements appear; sources are attached to their real statement; no source count is substituted. |
| Open a section, change its group, read a source, then Back | Original group, statement, filters, scroll and focus return; canvas selection remains unchanged. |
| Read an answer whose basis is only answer-wide | UI names the answer-wide basis and does not claim exact per-sentence support or quote a missing source passage. |
| Open existing direct View evidence | Existing evidence opens with no newly mandatory claims-list step. |
| Missing evidence version, partial group load, denied access | Unavailability/partial scope is explicit; count is never falsely zero; denied content and stale responses do not remain visible. |
| Open a historical run after its draft/model/evidence changes | Record bar/read-only state and the historical content remain; no current content substitution. |
| Unassigned input, explicit zero, unavailable output | Three distinct presentations, with units and reasons preserved. |
| Open reader beside unconnected assistant | Reader works; assistant says unavailable/not connected; no fake sending or tool activity occurs. |
| Narrow layout, keyboard, both themes, genuine 200% zoom | All destinations, source text and Back/Close remain reachable; no horizontal page scrolling or hidden focused pane. |
| Long labels and source text with reduced motion | Reflow preserves readability and numerical geometry; no animation is required to understand state. |
| Saved-run navigation from an edited draft | The established guard resolves unsaved work before navigation; a new shell cannot bypass it. |

Run project checks through the local entry point. The existing `combined-static`, `ui-navigation`, `ui-reading`, `foundry-nav` and `ported-isolated` groups are relevant to shared UI changes; public-API served journeys and full qualification remain separate required evidence under the plan. Browser doubles do not establish live authorization, contained execution, scientific correctness or genuine human design acceptance. Record the tested commit, exact outcomes and remaining limitations in the owning task checkpoint.

## Final shared-owner reconciliation

The original 58 dispositions remain **19 Present, 28 Adapt now, 7 Future, 4 Not applicable**. “Adapt now” is the original scope classification, not a claim that a backend capability was added. The rows below identify the actual presentation implementation and its boundary. Compatibility-only SourceChip, Readout, InferenceBlock and DetailTabs are fully inventoried in [Contour](Contour.md); they are not falsely cited as production consumers. Current quantities/evidence instead use their real QuantityResult, Field, table and EvidenceRecordBody owners.

Evidence entries name registered groups and assertions to consult; actual commands, tested commits, failures and remaining gates live in [C3 checkpoint](../.planning/phases/03-agent-tools-for-coding-agents/contour-design-system/checkpoints/3.C3.md). The complete export specimen complements actual record journeys and is not scientific validation. Existing comparison-specific acceptance and main-owned exploration/served gates are not newly claimed by this lane.

| Family | Working shared owner | Actual consumer / capability owner | Supported states and scope | Evidence / remaining obligation |
|---|---|---|---|---|
| 01 | tokens / Foundry | All screens | both themes; fresh generated CSS | combined-static |
| 02 | StatusTag / Ledger | RunPanel | shape+word; criteria separate from execution | ui-reading; design-colors |
| 03 | Manrope / monospace | Workspace; SourceEditor; VariablesTable | loaded local font; exact source; small nonzero | ui-reading; combined-static |
| 04 | Button / Field / DataTable | ConfigurationPanel | compact/default/touch; full labels | ui-reading; foundry-nav |
| 05 | radius tokens / Panel | Workspace; ModelView | shell/panel/control/chip hierarchy | ui-navigation; ui-reading |
| 06 | Panel raised/sunken | Workspace; configuration readers | passive surfaces; no false click state | ui-navigation; ui-reading |
| 07 | WorkspaceShell / NavigationRail | Workspace | static shell-only texture; gradient; both themes | ui-reading rendered contrast |
| 08 | Foundry motion | Buttons; running markers | reduced motion; no necessary animation | ui-reading; foundry-nav |
| 09 | ActionIcon / StatusTag | Workspace; ActionDialog | decorative glyph; accessible names; unchanged status shapes | combined-static; ui-reading |
| 10 | BrandLogo | Workspace; NavigationRail | supplied geometry; same-origin wordmark; theme-aware ink | combined-static; ui-navigation |
| 11 | Button / ActionGroup | All actions | same size across contexts; disabled; keyboard | ui-reading |
| 12 | AttributionChip / RecordState | Workspace attribution; resource metadata | actual agent/user; neutral saved-resource state; full names | agent-ui; ui-reading |
| 13 | ClaimButton / StatusTag | StatementActions; RunPanel | ID-scoped count; partial singular; unknown has no zero | ui-reading; evidence-workspace |
| 14 | Ledger / StatusTag / RecordState | runStatus; configuration/model headings | independent facets; storage is neutral | ui-reading; foundry-nav |
| 15 | ClaimCard / Assertion / EvidenceStack | ContextDetails; Assumptions | full statement, conditions, actual relationships | ui-reading |
| 16 | Field / native wrappers | ConfigurationPanel; UnitEditor | unassigned/zero/invalid/readonly; compatible units | ui-reading; foundry-nav |
| 17 | Tabs / WorkflowNavigation | ModelView; RunPanel; NavigationRail | roving views; current destinations; no label routing | ui-reading; ui-navigation |
| 18 | Field message / named controls / exact readers | configuration errors; EvidenceRecordBody; source editor | visible help; full labels wrap; native title supplements exact values | ui-reading; foundry-nav |
| 19 | ResourceCard / Panel / list actions | Home; supporting results; canonical model/config/run lists | separate resource actions; filter empty; no nested whole-row button | ui-navigation; foundry-nav |
| 20 | Progress / explicit section status | RunPanel; ComputationalExportDialog; ContextDetails | indeterminate stage; partial source content; no plausible placeholders | ui-reading; ported-isolated |
| 21 | Future | Assistant integration owner | requires real connection, context binding and send lifecycle; absent from navigation | capability boundary |
| 22 | ActionDialog / DialogFrame / Button | Model actions | real actions only; Escape; return focus; explicit destructive confirmation | foundry-nav; ported-isolated |
| 23 | DialogFrame / ActionDialog | Workspace; record readers; ModelEditor | native modality; dirty guard; return focus | foundry-nav; ui-reading; ported-isolated |
| 24 | ResourceCard / Panel | Home; supporting results; canonical records | passive body and separate actions; full text; long labels | ui-navigation; ui-reading |
| 25 | QuantityResult / Field / DataTable | AnswerExplorer; full RunPanel output table | calculated/estimated/unavailable; units; no arbitrary promoted subset | ui-reading specimen; exploration-ui remains main-owned |
| 26 | Panel / DataTable / Disclosure | ComparisonView | actual identities; changed inputs/source; no ranking | foundry-nav model/config paths; comparison-specific acceptance remains existing comparison owner |
| 27 | Future | Identity/membership owner | requires membership, invitation, reviewer permission and attributed review API | capability boundary |
| 28 | ModelNode / ContextualPanel | GraphCanvas; SelectionInspector | instance vs definition identity; selected/incomplete; exact method/source | ui-reading; foundry-nav |
| 29 | EvidenceStack / ActionDialog / Panel | EvidenceIndex; EvidenceRecordBody; EvidencePicker | exact content/version; unavailable; no invented document preview | ui-reading; foundry-nav |
| 30 | ClaimCard / Assertion | ApproachAssumptions; ContextDetails; answer qualifications | full condition/limit; neutral assumption; retained basis | ui-reading modal limits |
| 31 | Not applicable | No financial exchange entity | omit business transaction metaphor | scope exclusion |
| 32 | Future | Scientific comparison owner | requires same quantity/units/conditions/date/method and retained versions | capability boundary |
| 33 | QuantityResult / Field provenance / evidence reader | AnswerExplorer; ConfigurationPanel | basis and units explicit; entered vs calculated; no source averaging | ui-reading; exploration-ui remains main-owned |
| 34 | ResponseCurve / GraphCanvas | AnswerExplorer; ModelView | gaps; real coordinates; unchanged graph/export palette | ui-reading; foundry-nav; exploration-ui main-owned |
| 35 | Future | Numerical method owner | requires declared method/applicability/effects and validation | capability boundary |
| 36 | Checkbox / Select / SettingsSection | ApproachReferences; Profile appearance | independent vs exclusive; theme-only local preference | ui-navigation; ui-reading |
| 37 | FilePicker / ActionDialog | ModelEditor import; ComparisonView | visible file name; empty/selected/disabled; guarded validation | ui-reading; ported-isolated |
| 38 | SectionHeader / ActionGroup | Workspace; canonical model/run headings | real location; wrapping actions; one resource owner | ui-navigation; foundry-nav |
| 39 | NavigationRail / WorkspaceShell | Workspace | all five study destinations; guards; narrow stack | ui-navigation; foundry-nav |
| 40 | ReadingContents | SelectionInspector.MethodExplanation | only existing reader sections; opens source disclosure before focus; local scroll | ui-reading method reader |
| 41 | AssistantPane | ContextDetails | truthfully disconnected; no send/history; independent close | ui-reading; ui-navigation |
| 42 | ContextualPanel / application ContextDetails | scientific context; SelectionInspector | exact source push/back; focus restoration; stale/access clearing | ui-reading |
| 43 | Not applicable | No composite validity/authority score | independent facets only | scope exclusion |
| 44 | Panel / Assertion / ClaimCard | Study details; Overview; ContextDetails | full question/scope/limits; unchanged authoring owner | ui-reading; ui-navigation |
| 45 | Button / ActionDialog / shared record readers | WorkspaceLink; ApproachFindings; run/configuration readers | actual relation and exact historical target; guards | ui-reading; foundry-nav; ported-isolated |
| 46 | Future | Identity/review owner | requires membership and attributed scientific review records | capability boundary |
| 47 | Future | Authored assessment owner | requires scoped comparative argument over same question and assumptions/evidence | capability boundary |
| 48 | ClaimCard / Assertion / ContextualPanel | Assumptions; answer qualification and limit readers | complete objection; challenging/missing evidence; no risk score | ui-reading; evidence-workspace |
| 49 | Not applicable | No deal-event entity | saved-run reader keeps its computational meaning | scope exclusion |
| 50 | Not applicable | No equity ownership entity | authorship/access/dependencies remain distinct | scope exclusion |
| 51 | ReadingContents / ContextualPanel / ResourceCard | SelectionInspector method; ApproachFindings supporting results | purpose/basis/calculation/source; exact configuration/version; no second Overview map | ui-reading; foundry-nav |
| 52 | Future | Uncertainty/comparison owner | requires comparable evidence conditions and supported numerical uncertainty | capability boundary |
| 53 | CriterionRecord / Panel | Study question; ConfigurationRecord; answer reader | intent separate from explicit criterion; missing values actionable | ui-reading; foundry-nav |
| 54 | ClaimButton / ClaimCard / ContextDetails | assumptions, limits and answer-wide basis | distinct statement IDs; full set; direct evidence; back; unavailable passage honest | ui-reading; evidence-workspace |
| 55 | Disclosure | RunPanel; SelectionInspector; ComparisonView | optional prose only; blocking failure stays visible | foundry-nav; ui-reading |
| 56 | Field message / StatusTag / ActionDialog | configuration editors; run errors; existing controllers | safe action; preserve draft; reconcile uncertain command without replay | ported-isolated; ui-reading |
| 57 | Progress / Ledger | RunPanel; ComputationalExportDialog | named stage; actual outcome; cancellation not fabricated | ui-reading; ported-isolated |
| 58 | ClaimButton / EvidenceStack / Field / QuantityResult | ContextDetails; evidence index; configuration/run readers | empty/unknown/partial/access-loss/not-computed distinct; complete set needed for zero | ui-reading; ui-navigation |

No family is reclassified to conceal unfinished work. Future families remain absent from production navigation. Parent/main owns the Overview generic exploration integration and served API verification; release owner retains full qualification and product owner retains design acceptance. The connected assistant, document snippets, comparative review and uncertainty services remain separate capabilities, not catalogue decorations.
