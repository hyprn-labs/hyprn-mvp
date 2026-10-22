# Project State

- **Display aliases (2026-10-20):** `7a66f44` adds self-service Display alias in
  Settings, backed by one profile API/identity owner. Sign-in names and actor IDs
  stay unchanged. New attribution and chat messages capture the human name;
  historical names are preserved. Model explanations now show the shared chip.
  Parent acceptance: access-control 11, agent-tools 335, assistant 123, boundaries
  165, contracts 127, static/build 9 and navigation browser 23 passed. Main owns
  coordinated live backend/UI publication; human acceptance remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/display-alias/CHECKPOINT.md).

- **Navigation affordances (2026-10-20):** `447f1c5` centralizes content navigation
  in OpenLink: named underlined links plus arrow, passive statuses plus separate
  arrow, back arrows on returns. Record details, citations and readers share the
  pattern; commands lose link underlines. Sidebar/tabs unchanged. Orchestrator
  acceptance at `81bcbf9`: static/build 9/9 and browser 22/22 passed, with declared
  API doubles. Implementation complete; main agent owns coordinated live publication,
  human acceptance remains separate. Unrelated edits preserved.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/navigation-affordances/CHECKPOINT.md).

- **Hosted staging Assistant/UI update (2026-10-22):** runtime `415a5555`, release
  `10a81dac`, schema 8, desired sequence 15, ongoing named-user staging access.
  Shared message formatting, isolated Home forms, question + opt-in autonomous
  creation, brief spacing and canvas height deployed. UI 28, agent tools 321,
  containment and 19 network probes pass. Chrome creation and joint predictions
  verified; existing study remains at 27 runs. Earlier fixed specific heat was
  explicitly requested in the launch instruction, not an Assistant error. New
  autonomous study has two completed comparison runs and joint sampling underway
  across load, flow and specific heat (all three saved ranges verified);
  its final answer is not yet verified. Remote `staging` published through the
  existing hook; no automatic deploy workflow is claimed. Next: complete that
  independent study check, cold-start profiling, automatic deployment, recovery
  qualification and second-user acceptance. Full release qualification remains open.
  [Current checkpoint](phases/06-hosted-staging/06-ASSISTANT-UI-CHECKPOINT.md).

- **Model/analysis skill coherence (2026-10-20):** `b7faa44` aligns installed /hyprn
  with live model readers and both analysis creation paths. Component-local reasoning,
  assembled-model explanation, investigation description and structured settings have
  explicit owners. Estimate targets precede launch; save/run and validation roles
  stay distinct. Browser inspection, skill validation and 18 reference links pass.
  Existing studies untouched. Next: use on future authoring; independent agent
  behavior evaluation remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/model-explanation-cleanup/CHECKPOINT.md).

- **Shared UI coherence (2026-10-20):** `cfd3acd` live, extending the answer
  reader pass to other pages/editors. Shared major-card type, title/help groups,
  contextual-panel controls and legacy form captions; custom dialogs reuse SectionHeader.
  Static/build 9/9, model browser 7/7 and evidence browser 13/13 pass. Live model,
  quantity/evidence editors and analysis settings reviewed without saving changes.
  Scientific data, numerical paths and version behavior unchanged; unrelated edits kept.
  Next: user review; full release qualification remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/ui-coherence/CHECKPOINT.md).

- **Automatic analysis lifecycle (2026-10-20):** `f96ae25` / `bd7f848` live.
  Estimation outputs and explicit limits are saved before one launch; missing calculations,
  fitting and validation then advance automatically. Saved settings remain read-only and
  changes require a new version. Exact run pins and recoverable launch receipts preserve
  reproducibility. API 71, contracts 127, browser 6, static/build 9/9, boundaries 165,
  owner client 18 and agent tools 326 pass. Live version 3 reused 33 existing calculations;
  both outputs passed eight independent validation points at unchanged limits. Joint-domain
  readiness and real predictions pass. Old records and answer pins unchanged.
  Next: user review; full release qualification and restricted delegated launch capability
  remain separate obligations.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-lifecycle/CHECKPOINT.md).

- **Analysis pagination and validation (2026-10-19/20):** `4f67735`, `006f3a6`,
  `650aef9` live. One member pagination loads relevant runs automatically; outputs lead
  compact linked rows. New sampled analysis/estimate formats use validation terminology;
  old records and numerical attestation remain intact. Surrogate limits are explicit,
  relative entry is percent, and blank differs from zero. API 67, contracts 127, agent
  tools 326, owner client 18, browser 6 and static/build 9/9 pass. Live points 21–33
  and retained surrogate metrics verified; no scientific writes or model runs.
  Next: user review; full release qualification remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-reader/CHECKPOINT.md).

- **Version actions and collection integration (2026-10-19):** `e6668d4` / `0c2deb8`
  unify saved readers and explicit Create new version across models, configurations
  and analyses. Design system session `agent-collection-loading` integrated as
  `2c4a29b`, preserving current dialogs and concurrent changes. Shared counts,
  load-more/retry and stale-response protection are live. Integrated static/build
  9/9, navigation 21/21, analyses 6/6 pass; model/configuration journeys 13/13 and
  7/7 passed before integration. Live paging reaches all 36 runs; saved sampling
  settings remain read-only. No scientific data or engine changes.
  Broader source-branch qualification failures remain open; next: user review and
  resolve those failures before release qualification.
  [Integration evidence](phases/03-agent-tools-for-coding-agents/collection-loading/checkpoints/3.L1.md).

- **Future model/analysis prose ownership (2026-10-19):** `129cbe9` / `ee28ae1`.
  Installed /hyprn skill and owner helper direct physical meaning/logic to model
  explanation and sampling/check plans/error targets to Analysis details. Packaged
  playbook and tool descriptions aligned (guidance version 0.1.1); no old records changed.
  Agent tools 326/326, owner client 18/18, skill validation pass. Repo style gate remains
  failing on pre-existing debt after the two new long literals were corrected.
  Backend rollout and independent behavioral evaluation remain release obligations.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/model-explanation-cleanup/CHECKPOINT.md).

- **Saved source choice (2026-10-19):** `3ef6b86` live. Both configuration-source
  cards remain visible and read-only, with the saved choice selected. Static/build
  9/9 and browser 6/6 pass; live visual review confirms the selection and fields.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Read-only analysis settings (2026-10-19):** `dd6cf7f` / `d90a6f7` live. Saved
  settings show the exact selected version with disabled, readable fields. Only the
  latest offers explicit Create new version; history stays read-only. Static/build 9/9
  and browser 6/6 pass; live cancel/reopen restores saved values. No data changed.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Single analysis settings action (2026-10-19):** `84fe033` live. Revision and
  sampling share one dialog, initialized from the saved design; values and point reuse
  preserved. Static/build 9/9, analysis browser 6/6 pass; live dialog verified.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Compact editing dialogs (2026-10-19):** `446b5b8` / `f04b6f5` live. Shared
  field/section rhythm and responsive quantity grid; fields and behavior unchanged.
  Static/build 9/9, quantity browser 13/13, evidence browser 13/13 pass. Live component
  and quantity editors inspected; no authoring mutations. Concurrent changes preserved.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Model explanation cleanup (2026-10-19):** `c834399` live in the integrated UI.
  Shared persistence wording corrected in `418ac11`: no primitive-name qualifiers;
  static/build 9/9 and model browser 7/7 passed, live draft/saved states verified.
  One heading and edit action, explicit draft/saved states, exact-version publication
  dialog and evidence reads. Shared design-system/agent guidance separates model reasoning
  from Analysis details; historical prose preserved. Static/build 9/9, model browser 7/7,
  integrated analysis browser 6/6 passed; real draft/saved/analysis readers verified.
  Next: user review. [Checkpoint](phases/03-agent-tools-for-coding-agents/model-explanation-cleanup/CHECKPOINT.md).

- **Compact sampling cards (2026-10-19):** `2cb4253` live. Shared compact Panel
  and form-grid recipes halve card height while keeping boundaries and full-size controls.
  Static/build 9/9 and sampling browser journeys 6/6 pass; live fixed/range layout verified.
  Sampling and surrogates unchanged. Next: user review.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Sampling settings card (2026-10-19):** `4c6335c` live. Shared sunken card groups
  method, training points, check points and seed; total-points field and summary removed.
  Static/build 9/9 and browser 6/6 pass. Live card verified at narrow width. No sampling,
  surrogate or data changes. Concurrent model-explanation work preserved separately.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Simplified analysis form (2026-10-19):** `ecea1a3` live; browser expectations
  corrected in `e665839` / `4512b77`. Removed criteria controls from creation/revision;
  saved mappings preserved. Sampling inputs use shared sunken Panel cards and standard
  header dividers/gaps. Static/build 9/9 and final browser 6/6 pass. Live narrow-screen
  cards inspected; runtime, saved records and scientific engines unchanged. Next: user review.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Input-first sampling (2026-10-19):** `a1c14bb` is live. New analysis → Generate
  samples reads independent inputs from the selected saved model, each fixed or ranged.
  No configuration prefill or separate justification; unchanged range provenance and
  eligible points/runs retained. Public configuration preview/save then existing sampling;
  numerical generation, surrogate assessment and publication contracts unchanged.
  Committed-tree static/build 9/9 and browser 6/6 pass; live narrow-screen form verified.
  Runtime and all demo records unchanged. Next: user review; release qualification separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Output / Requirement mapping (2026-10-19):** `093b075` / `e519476` live.
  Editable output/requirement table, exact bindings and unique-name suggestions preserved.
  Sampling proposal with optional prefill is superseded by the approved input-first form.

- **Consistent optional fields (2026-10-19):** `b6060fe` is live. Description is
  always visible and marked optional in analysis creation/revision; brief Scope and
  alternative descriptions/reasons use the same shared FormField. Static/build 9/9
  and analysis browser 5/5 pass. Brief browser 2/2 passes after stale test
  expectations and save timing were updated (`5466d12`, `b805003`). Live editors
  inspected without data changes. Scientific behavior unchanged. Next: user review.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Analysis preparation corrected (2026-10-19):** `8ddb61f` / `ab813f4` / `2318906`
  are live. One New analysis dialog offers Select configurations (one or more checkboxes)
  or Generate samples (ranges and total joint point count, with advanced settings).
  This supersedes the single/multiple branch. Shared compact checklist and retained entries;
  backend, data, sampling and accuracy checks unchanged. Static 9/9, browser 5/5 pass.
  Live two-path popup verified. Next: user review.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analysis-creation/CHECKPOINT.md).

- **Analyses within Experiments (2026-10-19):** implementation `a95527b`, browser fixture
  `29372c6` / `9b4fa93`. Experiments retains global Analyses/Configurations/Runs for the selected model
  version. Analysis is now the domain/API/agent term; retained calculation_* keys preserve
  stored pins. Publication rejects mixed versions of the same analysis or model. Demo answer
  `6520275a-8ea7-4513-a57a-8210df71ddb4` uses separate operating-point and sampled analyses;
  all 36 configurations/runs and the surrogate are unchanged. Live joint sliders verified.
  Focused checks pass: answer API 29, contracts 127, agent tools 326, owner client 18,
  answer browser 2, analyses browser 4, static/build 9/9.
  Next: user review; broader release qualification remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/analyses/CHECKPOINT.md).

- **Reading refinement (2026-10-19):** delivered `89e0b15`: heading-free study navigation,
  48 px execution strip, consistent inset records, output-only comparisons and structured
  Answer basis. /hyprn and playbook now require clear causal uncertainties and concrete
  next analysis; all study prose stays in backend records. Static 9/9, agent tools 326,
  answer browser 2 pass; live layout/prose verified. New answer
  `af62b860-2d8e-4ea9-82ee-674554b5b155`, all 36 runs and numerical pins unchanged.
  Next: user review; broader release qualification remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/reading-refinement/CHECKPOINT.md).

- **Concise answers and Experiments (2026-10-19):** delivered `08b423f`. Experiments groups
  calculations/configurations/runs without another stored primitive. Answer content 2 and
  agent tools use Interpretation, Uncertainties and Next analysis; historical qualifications
  remain intact. One comparison table, full-width brief prose, hidden technical metadata and
  genuine execution status/duration are live. API 24, units/execution 94, agent tools 326,
  contracts 127, browser 2 and final static/build 9/9 pass. Live joint estimates verified;
  all 36 original runs unchanged. Current answer `ebde4145-cb51-4f27-9322-486c717a2737`.
  Next: human visual review; broader qualification and legacy-suite migration remain separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/answer-cleanup/CHECKPOINT.md).

- **Shared layout rhythm (2026-10-19):** delivered `ffa1b3e` through `2571af7`: common
  collection/record gaps, panel insets, narrative reading rhythm, separate option entries,
  responsive headers and model search clearance. Screen overrides now fail the ownership
  guard. Static/build 9/9 and navigation/spacing/200% zoom 12/12 pass; live Overview, Models,
  Configurations and Runs reviewed. Numerical/runtime/data unchanged. Broader reading suite
  has nine obsolete-domain expectations to migrate; no full qualification claim.
  Next: human visual review; UI test maintainers own legacy-suite migration.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/layout-rhythm/CHECKPOINT.md).

- **Earlier execution presentation (superseded by concise-answer cleanup above):** delivered `4e8ccad`, fixture correction `6e0e7d4`.
  Current configurations omit criteria; Runs uses shared collection cards; Execution presents
  recorded status/operation/wall duration/time limit, with files and diagnostics secondary.
  Answer legend omits no-result when displayed values are available. Committed static 9/9 and
  browser 11/11 pass; live demo readback verified. Numerical/runtime/data unchanged.
  Future solver/optimization metrics documented, not fabricated or implemented. Next: human
  demo review; broader release qualification remains separate.
  [Checkpoint](phases/03-agent-tools-for-coding-agents/execution-presentation/CHECKPOINT.md).

- **Current work (2026-10-19):** joint boundary sampling, independent assessment publication
  gate and `/hyprn` preparation-before-publication are implemented in `f064690`; stable slider
  coordinates in `e93f3fb`. API/native/static checks pass. New coolant study
  `1174be5a-8527-4a51-83d9-aad3c8e4aeaa` replaces the old active demo with recovery retained.
  All 36 original evaluations recorded; eight assessment checks and a fresh joint verification
  pass at unchanged tolerances. Answer `026ac8e2-724f-4aec-9a76-8fd338216ae4` is published.
  23 API interaction checks create no model runs; warm full-curve median 1.382 s. Final slider
  UI is deployed; browser multi-slider, independent axis and calculated-point readback pass.
  Next: human demo review. High-dimensional coverage exceeds the bounded sampler
  capacity and is explicitly refused; no universal continuous error guarantee is claimed.
  [Current checkpoint](phases/03-agent-tools-for-coding-agents/joint-preparation/CHECKPOINT.md).

- **Previous demo (superseded 2026-10-19):** the calculation-based answer explorer and active
  approach retirement are implemented on `codex/resume-domain-integration`. The rebuilt live
  demonstration has 99 recorded native runs, three assessed groups, and answer version 2 pinned
  to its estimate. Joint predictions, exact originals and unavailable boundaries are verified;
  no prediction repeats sampling. The final design-system UI is published. Original authoring
  stores are recoverable under the configured development data root; unrelated work is preserved.
  **Next:** human demo review. Multi-calculation comparison, historical reader removal and the
  inherited wider qualification debt remain separate; M3/M5 and release qualification are not
  declared complete. [Delivery checkpoint](phases/03-agent-tools-for-coding-agents/consistency/RETIREMENT-CHECKPOINT.md).


- Compact exploration corrected: all independent inputs remain visible, explicit linked groups share a control, matching input/outcome panels surround an expandable Model node, and calculation links say How calculated / How estimated. Shared design-system checks and live multi-input predictions pass. [Correction checkpoint](phases/03-agent-tools-for-coding-agents/focused-exploration/SYMMETRY.md). Earlier input-hiding behavior is superseded; numerical coverage gaps remain separate.

- Record/control consistency delivered in `55bc055` / `5179806`: direct evidence, canonical metadata, right-stacked study actions, inset dropdown arrows and reversible shared panel chevrons. Integrated UI deployed with compact Overview preserved; live desktop/narrow and both themes verified. Static 9/9 and navigation 18/18 pass; integrated reading 32/33 has a new exploration-specimen coverage gap, broader legacy suite migration remains open. [Checkpoint](phases/03-agent-tools-for-coding-agents/record-polish/CHECKPOINT.md). Next: human visual acceptance; exploration/design-specimen maintainer to cover new exports, UI/release maintainers to qualify legacy suites.

- Compact answer exploration delivered: authored independent controls and outcomes, expandable full calculation graph, inspectable fixed inputs and persistent generic display choices. API 64/64, contracts 127/127, static/build 9/9 and live simultaneous-input predictions verified; same 120 originals and surrogate identity retained. [Checkpoint](phases/03-agent-tools-for-coding-agents/focused-exploration/CHECKPOINT.md). Next: human visual acceptance; existing boundary sampling gaps remain separate.

- Theme-aware owner branding, Settings return to the originating study, full-width saved Python and shared control alignment delivered in `72539a7`. Integrated static 9/9 and browser 49/49 pass; UI deployed and verified in the real app in both themes. Original assets/provenance retained in the design asset folder. [Checkpoint](phases/03-agent-tools-for-coding-agents/brand-controls/CHECKPOINT.md). Next: human visual acceptance; full release qualification remains separate.

- Grouped sidebar delivered in `73390d1` / `69aaac4`: shared collapse, study card, Workflows/Library and bottom account controls; Documents/Help explicitly unimplemented. Final static 9/9 and navigation 14/14 pass; deployed UI and verified the real app, including a short 703px desktop. [Checkpoint](phases/03-agent-tools-for-coding-agents/sidebar/CHECKPOINT.md). Next: human visual acceptance; underlying Documents/Help features remain separate.

- Case retirement is implemented in the current API/storage/worker/UI and `/hyprn`; model names come from the backend in both views and appearance is Light/Dark. The live demo has a new case-free store with authored-record recovery, current attestation and eight output-equivalent baseline runs. Joint exploration rebuilt: 120/120 originals and all 33 assessed outputs meet unchanged error targets. All 14 UI controls are enabled and interior simultaneous-input estimates work; default-baseline boundary coverage remains incomplete and needs axis/boundary support before claiming full restoration. Human acceptance and that sampling follow-up remain next. [Checkpoint](phases/03-agent-tools-for-coding-agents/primitives-cleanup/CHECKPOINT.md). Historical entries below describe superseded primitives; current policy is ADR 0006. Other session navigation/details/branding work remains independent.

- Calculation listing performance delivered in `c33a4a4`, cold-read and design-system follow-up in `2c175e8`: bounded pages, metadata summaries, request-local reuse of identical validated subrecords, labeled Model / Model version selectors and padded list actions. Matched fresh-web first 20-run read improved from 2.899 to 1.276 s; quiet repeated reads 0.428–0.496 s. 62 admission tests, 12 navigation cases and 9 static/build stages pass; real joint predictions preserved (11/11 estimated and reset calculated). [Latest checkpoint](phases/03-agent-tools-for-coding-agents/calculation-performance/COLD-READ.md), [initial pagination evidence](phases/03-agent-tools-for-coding-agents/calculation-performance/CHECKPOINT.md). Next: human acceptance; host memory contention and broader API/release obligations remain separate. No unrelated session processes stopped.

- Calculations navigation and compact sliders delivered in `d1f1a9e` / `b65c9ac`: Overview, Models, Calculations; shared saved-version context filters configurations/runs and preserves exact links. Real two-input prediction returns 11/11 estimates; static 9/9 and navigation 11/11 pass. UI-only live refresh includes concurrent evidence work. [Checkpoint](phases/03-agent-tools-for-coding-agents/calculations-navigation/CHECKPOINT.md). Next: human visual acceptance; initial listing timeout superseded by the calculation-performance checkpoint above; full release qualification deferred.

- Evidence validation is now deployed and six live evidence families have source-checked excerpt/location/explanation versions; all eight old records and sampled run history remain identical. Independent assistant/details behavior and shared header wrapping delivered in `535c6df` / `d0a76f4`. Final static 9/9, evidence 13/13 and navigation 12/12 pass; live light/dark/narrow and both-panel/solo/full-width/resize behavior verified. [Deployment checkpoint](phases/03-agent-tools-for-coding-agents/evidence-panel/DEPLOYMENT-CHECKPOINT.md). Frozen records retain historical evidence pins. Next: human visual acceptance; chat remains disconnected, authenticated extraction and full release qualification remain separate. Earlier reader/baseline evidence is retained in READER-CHECKPOINT.md. Shared details dock `d49c486` now enforces equal statement/evidence/supporting-results dimensions, including dialog-hosted readers; static 9/9, navigation 13/13 and evidence 13/13 pass on the isolated delivery snapshot. [Dock checkpoint](phases/03-agent-tools-for-coding-agents/evidence-panel/DETAILS-DOCK-CHECKPOINT.md) records the concurrent-checkout isolation and live verification.

- Run/page consistency delivered in `827fb67` and `eb0fec4`: shared top-aligned headers and wrapping actions, restored case-card padding/action placement, aligned values/unit typography and secondary success diagnostics. Original layouts retained. Final `1f575b2` acceptance: 85 browser cases and 9 static/build stages pass; live run/cases light/dark/narrow and model/approach headers verified. [Checkpoint](phases/03-agent-tools-for-coding-agents/page-consistency/CHECKPOINT.md). Next: human visual acceptance; release qualification and observed slow record reads remain separate.

- Record details standardized in `99a5b8f`: shared document-icon control and metadata row directly below each owning title, across page and embedded readers. Ownership checks prevent ad-hoc replacements. Final integration: 83 browser cases and all 9 static/build stages pass; live desktop/dark/narrow and model/method/approach/case/answer/evidence reading verified. [Checkpoint](phases/03-agent-tools-for-coding-agents/record-details/CHECKPOINT.md). Next: human visual acceptance; full release qualification remains separate.

- Configuration formatting correction delivered in `0e494ab`: original layout retained; back-link overlap removed, title/actions aligned and numeric/unit formatting shared through the design system. Committed static 9/9 and browser 9/9 pass, including genuine 200% zoom. Live saved configuration checked at desktop/narrow widths; guarded UI-only refresh, no scientific writes. [Checkpoint](phases/03-agent-tools-for-coding-agents/configuration-formatting/CHECKPOINT.md). Next: user visual acceptance; the rejected configuration mockup is not a delivery target.

- `/hyprn` now prepares joint exploration by default for new numerical studies, before handoff: justified ranges, reused originals, joint samples/support, assessed surrogates, fresh joint checks and all-category/output prediction readback. Manual-warm guidance removed. Installed skill points directly to the updated source. See [skill checkpoint](phases/03-agent-tools-for-coding-agents/answer-exploration/checkpoints/joint-skill.md); structural validation passed, new independent study trial not performed in this documentation change.

- Automatic prediction renewal delivered in `f076a56` and live runtime `55eb0cd`: cold/expired prediction processes reload the saved surrogate automatically, with running “Updating…” states. Real browser recovery restored all 11 outputs; original/sampling/build/manual-warm counts are unchanged. 63 API tests, real restricted-worker expiry test and all 9 committed static/build stages pass. See [renewal checkpoint](phases/03-agent-tools-for-coding-agents/answer-exploration/checkpoints/prediction-renewal.md).

- Model flow redesign and minimalist follow-up delivered in `100d7ee`, `7566a59`, `d78c5d7` and `1b1663c`: individual arrows and shared direction colors, model/component reading separation, selected-quantity dialogs, combined component title/explanation, aligned header and persistent assistant launcher. Final isolated verification at `c5e5b5d`: 61 browser cases and all 9 static/build stages pass; style retains 61 unrelated findings. The live model includes these changes and was checked in both themes and at narrow width; a concurrent UI refresh was preserved, with exact asset hashes recorded rather than attributed to this commit. Appearance and viewport restored, no scientific writes. See [model flow checkpoint](phases/03-agent-tools-for-coding-agents/model-flow/1-CHECKPOINT.md). Next: human visual acceptance; assistant chat remains disconnected and full qualification remains deferred.
- Component heading/assistant follow-up: `412d1e5` removes the duplicate heading, aligns name/edit actions and adopts the approved preview’s labeled chat button. Live light/dark/narrow and saved-version checks pass. Static 9/9 and navigation 9/9; reading 26/31 and Foundry 7/8 have the same six failures on parent `d8cd7dd`, retained for broader UI qualification. See [follow-up checkpoint](phases/03-agent-tools-for-coding-agents/model-flow/3-CHECKPOINT.md). Human visual acceptance remains next.

- Joint exploration prepared in `7b0f062` / `7615f52`: 122 distinct existing points reused, generic bounded Kriging fitting, 33/33 retained output assessments and 33/33 fresh independent comparisons pass. Public full-vector queries take 0.086–0.167 s; live multi-slider results verified. Convex coverage remains bounded; automatic prediction renewal is now delivered in `f076a56`. See [joint preparation checkpoint](phases/03-agent-tools-for-coding-agents/answer-exploration/checkpoints/joint-preparation.md). This supersedes the earlier joint-preparation obligation below, not full-domain or physical qualification. Concurrent UI deployment preserved.

- Independent answer controls delivered in `5d5292c`: sliders retain other inputs, Plot against is separate, columns are visually separated and output basis/axis/actions have distinct spacing. Unsupported combinations remain selectable with honest no-result states and one shared notice. /hyprn guidance matches. All 9 static/build stages and 23 reading tests pass on the committed tree; real demo interaction and narrow-layout verification pass. See [independent controls checkpoint](phases/03-agent-tools-for-coding-agents/answer-exploration/checkpoints/independent-controls.md). Existing joint-coverage/predictor availability remains a scientific preparation obligation; no new calculations were launched.

- Answer component layout delivered in `e759698`: 25% zoom, visible curves, measured equal-height columns, aligned discrete controls and shared black/orange calculated/estimated palette. Nine static/build stages and 23 browser tests pass on the committed tree; desktop/narrow live verification passes. Static demo UI refreshed without restarting the attested backend. See [component layout checkpoint](phases/03-agent-tools-for-coding-agents/answer-exploration/checkpoints/component-layout.md). Next: human visual review; performance and historical-overlay obligations below remain.

- Active delivery: all-input answer exploration and bounded execution performance. All 150 additional continuous originals, 30 fits (11/11 error targets each), and all 42 category/input browser controls are verified; integer controls use their three valid calculated values. Baseline single-input slices are complete; joint-input coverage is not qualified. Bounded two-run dispatch, exact-snapshot validation reuse and trusted bytecode startup preparation are integrated with the storage work in `f628aa0`. The live demo is upgraded and freshly attested; two fuel verification runs reproduce all outputs and exact model/configuration pins. Same-input public benchmark: 26.847 s per warm two-point batch versus 33.031 s sequential (13.424 s/point throughput, not individual latency). Six seconds remains unmet. See [batching and completion checkpoint](phases/03-agent-tools-for-coding-agents/answer-exploration/checkpoints/batched-execution.md) for 418 passing focused tests, browser evidence, exact records and failures. Integrated style remains blocked by 31 storage-owned formatting findings; preserve that session's files. Optional historical overlays still load slowly. Earlier native-history recovery gaps remain recorded. User removed 3.V6 final qualification/Guerric stage; no release or human-acceptance claim. Unrelated ROADMAP/research work remains untouched.


- Current demo design: approved Charcoal tokens, distinct blue keyboard focus,
  shared neutral syntax roles and canonical unchanged logo owned by BrandLogo.
  See [Charcoal checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/charcoal-design-system.md)
  and [demo polish checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/demo-polish.md).
  The consistency pass is delivered in `a10e986`: complete button recipes, shared
  assertion/evidence spacing, form/dialog rhythm and ownership enforcement.
  Final checks: 9 static/build stages, 33 style tests, 5 browser journeys; live
  study details verified after refresh. See the
  [consistency checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/design-system-consistency.md).
  Next: human demo review. Older reading-suite reconciliation and
  external-release legal/source-offer review remain explicit obligations.
  No scientific records changed.

## Project Reference

See [PROJECT.md](PROJECT.md), [ROADMAP.md](ROADMAP.md) and [HANDOVER.md](HANDOVER.md).

**Core value:** An engineer can reach a defensible feasibility answer whose every number is reproducible and traceable, without shell or database steps, on their own machine.
**Current focus:** Deliver the current local demo: cleaned continuous reader, fresh real calculation and persistent scientific answers. The user authorized deleting old data and explicitly stopped historical-preservation ceremony; the DELIVERY-PLAN amendment removes those checks from this batch. API/static checks, native workers and attestation checks pass. The focused current-page browser check passes and the demo is refreshed; all eight current cases and their study synthesis are saved and visibly verified. Full mission/cost closure and release qualification stay separate.

## Current Position

- Execution budgets and agent tools, 2026-10-15: `b782241` delivers per-run 1–3600 second budgets (300 default), retained timeout diagnostics, named owner-session API tools and `/hyprn` guidance. Tools own model request formats while exact scientific version pins remain explicit. Focused API/client/contract/native/UI checks pass, including a real >20-second run, intentional timeout, export and restart. The refreshed attested demo contains verified coolant study `cba1e324-06b9-4e7f-b716-37ac6ea2fba4`: four successful computations, three case answers and synthesis; nominal 9.52 K meets the rise limit, simultaneous adverse 15.79 K does not. API authoring-to-readback took 6m05s. See [execution-tools checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/execution-tools.md). Next: human demo review; delegated writer enablement and full release qualification remain separate.
- API diagnostics and engineering units, 2026-10-15: implementation `a17a406` adds precise nested field errors and 20 ordinary physical unit spellings (48 total). The approved additive schema exception is recorded beside the contract rules. The rebuilt modeling producer and final worker are attested; a committed-tree public author–run–read journey verifies five conversions and restart persistence. Four existing demo study approaches/run lists are preserved. See [delivery checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/engineering-units-errors.md) for exact checks, corrections and release limits.
- Callable study workflow, 2026-10-15: `hyprn` is installed and discovered by Codex from its repository-owned source. Commit `baabd60` adds a brief-to-answer launch sequence and the owner client's lightweight batch-status shortcut. Client checks 10 and style checks 33 pass; a read of 20 retained runs matches their configuration pins. See [callable skill checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/hyprn-callable-skill.md). Full new-study behavioral evaluation remains a follow-up; this earlier skill batch changed no numerical runtime or live scientific records. Diagnostics and units are delivered in the later checkpoint above.
- Phase 1 is recorded complete. Its original gate passed 102/103 groups on `a66a1f3`; the remaining findings chain passed later on the continuation branch. That history is not a claim of full qualification on today's tree.
- Phase 2 completed: 2.1, 2.1a, 2.2–2.8 and 2.8a–2.8c. Phase 3 completed: 3.1, 3.2, 3.2a, 3.3, 3.3a–3.3d and 3.4–3.10. Checkpoints retain exact commands, failures, counts, artifact identities and cleanup. Full 3.16 remains partial; its paths slice is verified.
- Task 2.8 closes the combined schema/study-path/release attestation window. The current modeling producer and native captures are verified; the final runtime retains exactly 49 reviewed source paths and one unreplaced attestation. See [checkpoint 2.8](phases/02-local-edition/checkpoints/2.8.md).
- Latest integrated acceptance: all 23 initial groups pass at `b5a7b62`; the docstring-only correction passes affected release checks at `a5ef4eb`; the final native journey passes 14 tests plus its existing one deselection, with seven runs, four archive pairs and three browser checks. The two-constant durable pin at `d4467eb` passes guards 17 and preflight 1, preserving seven processes and 5,675 original files; final style 33 and term scan 0. All 29 allocated orchestrator scopes and the fresh materialized copy are released; the referenced worker image and immutable captures are retained.
- Every current-image/native group deferred by 2.8c now passes, including public-api 70, ae-model 26 and fuel-native-provenance 16 (one added historical-export case). The earlier 30-group schema/path acceptance remains recorded in [2.8c](phases/02-local-edition/checkpoints/2.8c.md#integrated-orchestrator-verification) and [3.16-paths](phases/03-agent-tools-for-coding-agents/checkpoints/3.16-paths.md); unchanged checks are not repeated.
- Current demo: the public-API author–run–inspect–revise loop is working with the cleaned UI, current producer and attested worker. Eight explicit cases use 100 occupied seats. Persistent case answers cite exact configurations and real runs; the study synthesis separates conditional cruise comparison from unresolved complete-mission feasibility and ticket pricing. See [DEMO-REHEARSAL.md](DEMO-REHEARSAL.md) and the [current integration checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/continuous-approach-integration.md).
- Latest interface cleanup (`e5e98cd`) puts the study answer below the question, moves cases into their own workspace tab, places compact evidence links beside assertions, consolidates Edit study, improves method hierarchy, and simplifies configuration/run views. Model actions use quantities consistently. Focused checks pass: browser 19, style 33, agent tools 270, all six static stages. See [interface-cleanup.md](phases/03-agent-tools-for-coding-agents/checkpoints/interface-cleanup.md). Runtime guidance requires citations to support the actual value, units and scenario; existing scientific content has not received a new coherence correction. The repository skill is not installed globally.
- Scientific skill consolidated at `1388d2e`: primitive operations, verification versus validation, decision-relevant uncertainty, claim depth and stopping rules, supported capability boundaries and a worked pump example. Essential rules are packaged in the existing playbook; agent-tools 270 and style 33 pass. See [scientific guidance checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/scientific-guidance-consolidation.md). Expanded behavioral scenarios await independent evaluation; no new live authoring or scientific record correction is claimed.
- Timed scientific authoring trial, 2026-10-15: new study `a04b7ddc-0cd3-46d4-94f7-b4fed043b02a`, “Fuel choice across hypersonic cruise conditions,” uses two newly authored models, 23 real runs, four case answers and one saved synthesis. Elapsed 35m40s (11m05s to first submission, 21m37s through final checked result, 2m58s for answers/read-back/final browser attempt), reusing the running installation and existing source material. Analytic and arithmetic checks pass; 13/15 nominal mass screens pass, while physical validation, complete-mission feasibility and tickets remain unresolved. Public API read-back confirms all answers. Approach and a negative-margin run were visually checked; the browser session expired before the final answer view. External `hyprn-timed-fuel-study/timer.json`, transcript and study-state records retain identities, timing and corrected authoring refusals. This is a real authoring trial by the maintaining agent, not independent skill evaluation. No application source or earlier study records changed.
- Optional 2.9/2.10-host and 3.11/3.12 work is preserved in isolated branches at deferred checkpoints and remains unmerged. The previous A–D queue is not the active demo queue; future product scope follows the roadmap decisions.

## Decisions and Authority

- [DELIVERY-PLAN.md](DELIVERY-PLAN.md) governs task slices, dependency replacements, batches and parallel scheduling. Use focused executor checks, one integrated union of required acceptance, and complete final gates. Two independent implementation lanes follow the exclusive attestation window; one integrator owns shared runner/guard registration. Preserve real dependencies and serialize contested resources.
- PD-2.4 option a and its exact packet are approved: move 108 Documents-only definitions and registry; retain 11 shared citation definitions, 37 launch roots, their 140-definition closure and all 49 attested inputs. Preserve the exact pre-split capture and historical identities. [Checkpoint 2.8a](phases/02-local-edition/checkpoints/2.8a.md) is authoritative.
- Build backend: approved flit_core 4.1.0. Task 2.7's three approved packaging transformations must preserve runtime-file bytes, dependencies and entry points; only enumerated metadata differences are accepted. No setuptools licence exception. The exact proposal hashes, transformations and equivalence evidence are retained in [checkpoint 2.7](phases/02-local-edition/checkpoints/2.7.md) and its dependency audit.
- Namespace and historical identity: `hyprn-mvp` is the product namespace; no compatibility readers for records outside it. Prepared artifacts record schema identities instead of copies. The golden corpus retains its captured blobs; historical reads never substitute current content.
- Modeling producer builds are not bit-reproducible. A changed modeling source requires a rebuild, a new `modeling_producer` pin and native fixture recapture. [Checkpoint 2.8](phases/02-local-edition/checkpoints/2.8.md) records the current images, 49-file inventory and durable fixture `native-20261014T143925Z`; [2.6](phases/02-local-edition/checkpoints/2.6.md) retains the preceding identities. Preserve historical captures and unpinned old fixture folders.
- Store rule D-12: before the pilot-retention boundary, ordinary open/start never creates or migrates stores. Task 2.11 adds explicit creation, schema-version refusals and confirmed identity-checked `setup --reset-data`; no automatic reset or migration. After the retention boundary, the full retention, backup and migration rules apply.
- Authority and ownership follow ADR-0003, ADR-0004 and ADR-0005. Agents cannot delete saved records, archive/restore or manage access; working material stays revision-checked. Reviewer delegations may record labelled scientific reviews. One operation has one authoritative outcome; the UI follows server-decided receipt recovery. Method-package release remains human-only.
- Phase 3 decisions and practices are in [checkpoint 3.2](phases/03-agent-tools-for-coding-agents/checkpoints/3.2.md) and [03-PRACTICES.md](phases/03-agent-tools-for-coding-agents/03-PRACTICES.md): runtime-owned progress notes, packaged playbook sections, explicit revisions, interactive-only token display, CLI token administration and WSL2-local clients. OQ-3 is decided after both-client evidence at 3.17/3.18.
- No credential-file fallback when a credential store is unavailable. Study folders resolve flags/environment/configuration/defaults through the common path policy. OPS-04 stays planned until qualification; VER-03 semantics are reused by clients.
- The approved formatter ratchet uses ruff 0.16.10 and prettier 3.9.10, line limit 100 and single quotes. Task 2.8c formatted the attested sources in separate syntax-equivalent commits and removed their exclusion; hash-pinned tests stay excluded. A history rewrite that removes the baseline requires regeneration.
- Toolchain and licensing decisions are retained in [the Phase 2 dependency audit](phases/02-local-edition/2.1-dependency-audit.md) and `docs/legal/licensing.md`: pinned uv/CPython, only audited package changes, and recorded residuals. The later approved Flit decision supersedes the earlier setuptools choice.
- Supported hosts: Apple-silicon macOS, Linux x86_64/aarch64 with glibc, and Windows through WSL2. Intel macOS is refused until a reviewed dependency build exists. Current-host evidence does not qualify the other hosts.
- Phase 4 decisions, capability slices, parser re-audit, document-bearing version chain and one-owner operation rules remain in [04-CONTEXT.md](phases/04-documents/04-CONTEXT.md) and its plan. Documents stays unavailable until its release gate. Lifecycle/portability follow-ups and cloud work remain deferred.
- [FACTORIZATION.md](codebase/FACTORIZATION.md) and the original phase plans retain later module-boundary, browser-fixture, group-registry, access-loss and version-family work. Earlier completed refactors are evidence, not pending dependencies.

## Remaining Obligations

| Owner / checkpoint | Obligation |
|---|---|
| 2.9 / 2.10-host and 3.11 / 3.12 | Deferred worktree checkpoints; preserve code, existing evidence and unverified items. No further completion or integration is a demo prerequisite. |
| 2.11 | Explicit store creation and versions; no DDL on ordinary open. Serialize the mechanical migration of test store constructors with agent work. |
| 3.17-host / 3.18 | Human probe on both installed clients, exact client names/versions and protocol/kit decision. Neither scripted tests nor one client substitutes for both. |
| 3.28-evidence / 3.28-full | Human capability reviews; for D resolve whether the queue cap counts only runs waiting before a call, since the current 10 waiting/running cap makes 20-per-call unreachable. |
| 3.32 | Remove the unsupported run-read cache claim from tooling-spec §5.4; finish the planned run-status work. |
| Next UI dependency task | Regenerate `ui/dependency-audit.json` for prettier. |
| Documents / final qualification | Make the parser lock's real-wheel verification runnable through the scoped entry point; it currently depends on a wheel variable not passed by the runner. |
| E / Phase 5 | Real served-installation browser evidence, remaining OS/clean-room proofs, final gate and genuine human acceptance. `ui-fidelity` still needs reference images. |
| Demo integrator | Old demo studies/runs may be discarded; do not spend time on historical preservation for this batch. |
| Later evidence-label fix | Run-scoped evidence expects a synthetic root instance absent from the production model. Preserve frozen identities; the demonstrated conclusion uses study scope with exact run references. |
| Demo export integration | Export processing is enabled; the existing queued computational-record request completed. No duplicate was submitted. |
| Later performance work | `get_study_overview` reads whole owner lists; large-study scaling remains unqualified. |
| Workflow-agent integration | The user-scope `hyprn` skill is installed and discoverable. Independently evaluate the revised guidance and expanded scenarios, then exercise a new study through the supported authoring client. Earlier nine-scenario evidence applies only to its earlier revision. Diagnostics and reviewed units are delivered by the engineering-units checkpoint; execution observability remains a separate follow-up. |

## Verification Constraints and Known Limits

- Every check uses `./hyprn-mvp dev check`; missing environments fail. Qualification freezes its tree and excludes competing heavy work. Durable-fixture groups and units-native share one dedicated scratch lane.
- A findings continuation consumes its working copy; rebuild that copy through preflight before repeating. Never alter immutable authoring records to make a test pass.
- Test stores are scoped; live roots, ports and names are protected by the development environment. No host-specific value belongs in repository content.
- API test modules retain their synthetic loopback origins when browser fixtures shadow conftest imports.
- The old unregistered-test, obsolete fixture-path, namespace and worker-read-permission issues have completed owners; their checkpoints retain failures and fixes. They are not current blockers. Any recurrence needs fresh evidence.
- Automated acceptance, human acceptance and deployment status remain separate. Neither Phase 2 nor Phase 3 is complete, and the current tree is not a qualified release.

## Session Continuity

Work branch: `feat/local-edition-continued`, no upstream. No push or pull request is authorized.

Current demo batch delivered. Eight current real runs returned all 11 outputs, with 100 occupied seats and every selected mass strictly below 575 tonnes. Eight case answers and one study answer are persisted through the public API and visible in the continuous reader. The original engineering question is intact; full mission and ticket-price conclusions remain unresolved. The actual UI verifies question/answer/methods in Overview, a separate Cases tab, shared editable model details and exact configuration/run links. Numerical results and answer records were unchanged by the UI refinement or the scientific-guidance consolidation. The repository skill and packaged playbook now include computational-engineering depth and primitive operations; focused tool/style checks pass. Expanded guidance needs independent behavioral evaluation and a real authoring trial before claiming demonstrated scientific judgment. Existing demo content still needs its separately scoped coherence correction. Old data is disposable and historical-preservation checks are not a prerequisite. Full release qualification, other clients/hosts and delegated writer-token enablement remain deferred; no push or publication is authorized.
