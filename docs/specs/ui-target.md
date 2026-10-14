# UI target

Status: current specification. This document says what the HYPRN MVP user interface is, what it must guarantee, how it is organised today, and where it is going. It is the single UI specification. The visual language, tokens, component notes, page layouts, scientific-state wording and names live in the design-system package (`design-system/` at the repository root: `README.md`, `Layouts.md`, `Coherence.md`, `Scientific-states.md`, `Naming.md`, `components/`). This document references them and does not repeat them: it is the authority for where information lives, and `design-system/Naming.md` is the authority for the words.

Related specifications: architecture and contracts (`docs/specs/architecture-and-contracts.md`), agents (`docs/specs/agents.md`), workspaces and identity (`docs/specs/workspaces-identity-onboarding.md`), documents (`docs/specs/documents.md`). Requirements: UI-01 to UI-05; related HUM-02, HUM-06, CRIT-01, OPS-01, AGENT-06 (`docs/specs/requirements.md`).

A plain-language wording pass is in progress, so the labels quoted below are the current wording, not a frozen list.

## 1. What the UI is for

HYPRN MVP is a workspace where engineers state a study question, build computational models, configure and run them, and judge what the results are worth with cited evidence. The UI is the human client of the HYPRN MVP API. Assistants (a provider-hosted managed agent in the cloud edition, local coding agents through MCP in the local edition) are a second client of the same API; they never get a privileged route. Their writes are attributed and shown to the person they act for in the HYPRN MVP UI, and they never delete saved records, archive or restore anything, or manage access (ADR-0003, `docs/adr/0003-agent-write-rights-revised.md`).

Binding constraints on the UI:

- **Independently implemented.** The UI is HYPRN MVP's own React application. It is built from behavioural targets and public contracts only. No modeling-service UI code, markup or product screens are copied, embedded or proxied. The browser calls only the HYPRN MVP API; it never talks to the modeling service, the execution layer or a provider directly.
- **One API for everyone.** Every screen action maps to a public HYPRN MVP API operation with the same authorization, validation, idempotent command receipts and audit as any other client. Capability checks decide which actions are offered; an action that is not supported is either absent or disabled with its real reason.
- **No browser-side scientific state.** Local drafts, filters, layouts and caches are disposable presentation state scoped to the signed-in actor and the exact resource. Nothing scientific is persisted only in the browser.
- **Built from the design system.** Screens use only the shared components in `ui/src/design`. Colours, sizes and spacing come only from generated tokens. No inline styles, external fonts, external URLs or icon fonts. The design-system checker must report no new violations.

## 2. UI principles

### 2.1 One canonical home per entity

Every piece of information has exactly one editable home. Everywhere else shows the same shared read-only component, or a link to that home. It is never rendered a second way.

| Entity | Editable home | Read-only reuse |
|---|---|---|
| Study name and description | Overview › About this study › Edit | Home row; breadcrumb |
| Study archive state | Home row (Archive / Restore) | Home Archived view |
| Study question, context, approach assumptions, limits | Modeling approach (edit mode) › Study details | Study question box and Study details dialog on Overview and the approach page; retained approach reader in configurations and runs |
| Method steps | Modeling approach › Methods | Retained approach reader; "Why" in the model view |
| Cases | Modeling approach › Cases and their answers (one expandable row per case) | Run header "Case: … · View case"; configuration "View case in approach" |
| Model composition, components, connections, source | Models › model draft | Canonical model view, read-only, in model versions, Run › Model, configuration "View model version", approach "Open model version" |
| Quantities (ports) | Models › model view › Edit ports | Quantities table below the canvas; run and configuration contexts add Value and Provenance |
| Model and component assumptions | Model view Details (nothing selected for the model; component selected for the component) | Evidence page; Run › Evidence |
| Configuration (context, inputs and provenance, criteria, configuration assumptions, approach and case link) | Configurations › draft editor | Saved configuration, Run › Configuration, approach case cards |
| Run outcomes and outputs | Computed and immutable; no editable home | Run › Results; Overview recent runs; case cards; result picker |
| Evidence sources | Evidence page › Sources | "View evidence" wherever cited |
| Exact identities, digests, serialized records | The record's own Record details dialog | Nowhere inline |

Consequences that the UI must keep:

- A configuration shows only what the configuration adds. It links to its model's assumptions in one line instead of repeating them, and never shows study conditions or limits.
- A run shows its own record. Study-level context is reached through "View modeling approach" or "View case", not repeated on the run.
- Full identities appear once, in Record details. Lists may show a short display ID to distinguish rows; short IDs are never request identities.

### 2.2 Read-only views reuse the canonical component

A read-only view is the canonical component in read-only mode, fed by the exact retained version, never a parallel rendering. The model view, the assumption list, the evidence index, the configuration record, the run-outcome tags and the Study details dialog are each one component used everywhere they appear. Historical views carry the record bar across the study screen and hide authoring actions; they read the retained snapshot, so they keep working when the modeling service is unavailable, and they never substitute today's model, configuration or evidence for what was recorded.

### 2.3 No duplicated information

The same fact is not shown twice on one screen or in competing forms across screens. When two surfaces need the same information, one becomes a link to the other. Removal of a duplicate never removes stored data: it changes presentation only. Fields that the UI does not show (for example `notes` wire fields, constant run facets, numerical mode) stay in records, Record details and exports byte for byte.

### 2.4 Plain language

Reader-facing text says what the user can see or do, in engineering language a reviewer would accept. Storage and integrity vocabulary ("retained", "exact", "recorded", "attested") belongs only in Record details and file or integrity diagnostics. Empty states are short and literal ("No assumptions", "No description yet"). Errors say what happened, where, and the next safe action, and say that the user's edits are kept when they are. Content rules: `design-system/README.md` (content fundamentals) and `design-system/Naming.md`.

### 2.5 Scientific states are never merged

- Each run outcome is its own status tag (shape, word and colour). Outcomes are never combined into one "success".
- The run headline shows only outcomes that the frameworks actually compute today: **Execution** and **Criteria**. Convergence, termination, constraints or feasibility, sample completeness and applicability are recorded as constants by today's scalar runs, so they are not shown. They remain recorded and exported, remain separate in the data, and return to the headline through the same shared outcome component as soon as a framework computes a non-constant value (coupled solves, optimization, uncertainty).
- Per-output availability stays visible in the outputs and quantities tables ("not computed", with its reason). A missing value is a word, never a blank or a zero. Zero is an explicit value. An unassigned input says "unassigned".
- Execution completing does not mean a criterion is met, and a criterion met does not answer the study question. Criteria are fixed-threshold checks on outputs.
- Every claim shows its basis: computed (links to the run), sourced (opens the cited evidence) or inferred (marked as inference and styled as assistant content).

Exact wording, tag mapping and ensemble rules: `design-system/Scientific-states.md`.

### 2.6 One Assumption concept

An **Assumption** is a statement plus attached evidence links (relationship, title, version, optional locator). It is one concept with one shared list component for every owner: modeling approach, model, component and configuration. The list is editable at its owner and read-only elsewhere. Empty state: "No assumptions", with "Add assumption" where editable. The owner name is not repeated under the heading. The Evidence page lists every current assumption with its evidence, grouped by owner, each with a link to its owner. There are no notes in the UI: component notes, definition notes and configuration notes are neither shown nor authored, and their stored values are passed back unchanged by commands. A limit is not an assumption; limits live in Study details. Input provenance is not an assumption; it stays with the input.

### 2.7 Accessibility, zoom and themes

- Every action has a keyboard path, including every graph and canvas action (selection, filtering, connecting), with a table equivalent for anything shown only graphically. Focus is always visible and dialogs restore focus.
- Genuine 200 % browser zoom and narrow widths stay usable: no horizontal page scroll, primary actions reachable, wide tables and code scroll inside their own region, the canvas keeps a bounded height.
- Light and dark themes are both first-class; status never relies on colour alone.
- Reduced motion is respected.
- Reference viewport 1440 × 1000; validated also at 1024 px width and at 200 % zoom, in both themes. Long names, many quantities, partial results and empty collections stay readable.

### 2.8 Honest states

| Situation | Required behaviour |
|---|---|
| Loading a selection | Show the requested identity loading; never old content under a new name |
| Unsaved local edits | Persistent dirty marker; Save / Discard / Keep editing on any navigation that would lose them |
| Stale revision on save | Keep the local proposal, fetch the current revision, show a reviewable conflict; no blind overwrite |
| Invalid batch | Field, row or element diagnostics; no partial success; all proposed changes kept |
| Static validation passed | Name what was checked; never imply the model ran or is scientifically valid |
| Capability unsupported vs service unavailable | Two different messages; recorded history stays readable during an outage |
| Submission outcome uncertain | Show the original command and reconcile it; never send a new command automatically |
| Partial or failed run | Keep the available values and their reasons; criteria that lack usable outputs are unresolved |
| Missing recorded artifact | Name the missing item; never fall back to current data |
| Confirmed access loss or sign-out | Clear displayed protected content for that study; keep unsaved local work where safe; never leak cached data across users |
| Partial aggregate read (for example the Evidence page) | Say how many owners loaded; never say "No assumptions" when a read failed |

## 3. Screen map as built

The application is a single-page React client with hash deep links that name explicit resource IDs and versions. Opening a link to an unavailable resource shows that state; it never opens the latest resource instead.

### 3.1 Shell

| Element | Responsibility |
|---|---|
| Sign in | Username and password; returns to the requested deep link |
| App bar | "HYPRN MVP" wordmark, breadcrumb Home / study / section, account entry (Profile: account name, Sign out) |
| Study header and tabs | Study name shown once; tabs Overview · Models · Configurations · Runs · Evidence. The modeling approach opens from Overview and keeps Overview selected |
| Editor guard | One ordered guard list covers every editor (approach, model, configuration, evidence, units). Leaving with unsaved changes asks Save / Discard / Keep editing |
| Access-loss seam | One client-side session seam fences study reads by actor, session and access epoch. A confirmed denial or sign-out clears the protected view; transient failures keep content and offer retry |
| Footer | One link: "Third-party software notices" |

### 3.2 Home

- Lists studies with a find filter over loaded rows, and **New study** (name required, description optional).
- **Studies | Archived** switch. A study row has **Open study** and a quiet **Archive** button. Archive asks for confirmation and states that the study disappears from Home for everyone, nothing is deleted, and it can be restored from Archived. The Archived view shows the same rows with an "Archived" tag, Open study and **Restore**.
- Archive is study-wide presentation state. It is not deletion and not access control: reads and commands keep their current authorization. Studies are never deleted.

### 3.3 Overview

- **Study question box** at the top, read from the latest saved approach version only (a draft is never study context). **See more details** at its bottom-right opens the **Study details** dialog: Study question (agreed question, original wording, elaboration, each with attribution) · Study context (scope, open questions) · Assumptions (approach-owned, with evidence) · Limits (with evidence; limits apply to the whole study).
- **About this study**: Edit, description, and one action, **View modeling approach**.
- **Recent runs**: run name and short ID with Execution and Criteria tags. **Recent configurations**: name and revision. Full identities are only in Record details.

### 3.4 Modeling approach

- Header: back to Overview, version select, Edit approach / save draft / save approach version, overflow with Record details and Earlier work. The same study question box and Study details dialog as Overview; in edit mode Study details is where approach assumptions and limits are added and edited.
- One continuous page follows the full saved engineering question: **Reasoning and methods**, **Cases and their answers**, then **Answer to the study question**. Section links move focus and scroll without replacing the workspace route. There are no chapter tabs or separate method map.
- Methods expand in place to show purpose, basis and reasoning, calculation, dependencies and unresolved work. Proposed and partially linked methods remain explicit. Model selection handles several exact versions; **Open model version** opens the canonical read-only model view with the relevant components and quantities highlighted. Assumption and evidence references use their canonical owners alongside the explanation.
- Cases expand to show the question and purpose, every associated saved configuration and run, and the case answer where explicitly assessed. No configuration disappears merely because a run exists, and no run is selected implicitly as latest. Outputs keep units and missing-value reasons; full precision, execution and criterion checks are supporting run details.
- Usage review keeps case filtering, refresh, bounded reads, pagination and failures explicit. The final study synthesis follows the cases. Empty scientific assessments say they have not been assessed; successful execution, met criteria and evidence titles never supply an answer. Study limits remain in **Study details**.

### 3.5 Models and the canonical model view

- Models list with **New model** (empty or from a starting model) and Open model.
- Model page: back to all models, name and version select (draft or read-only version), **Save model version**, Create configuration, overflow (rename, reload, import and compare, Record details for versions). A "Units incomplete" disclosure lists quantities whose unit is still unspecified; such drafts can be saved, but execution stays blocked until units are resolved.
- **Canonical model view** (one component, reused everywhere a model is shown):
  - Toolbar: **Graph | XDSM** toggle, clear selection, show or hide Components and Details. Authoring actions (add component, connect ports, overflow) appear only in the current draft.
  - Canvas with a Details panel beside it, and the **Quantities** table below at full width in its own scroll region.
  - Details, nothing selected: the model's summary and its **Assumptions**, plus a count of component assumptions.
  - Details, component selected: **What it computes** (each linked method step's transformation text, then **View source**, a read-only text view that is never run; in a draft, Edit source), **Why** (every linked method step with its purpose and rationale and a link back to that step in the modeling approach), and the component's **Assumptions**. Method steps are linked by exact implementation references, never by name.
  - Quantities table: Quantity (symbol and name) · Component · Direction (with "from …", "to …", "set in configuration" or "model result" folded in) · Definition · Unit, plus Value and Provenance in configuration and run contexts. Filters for text, component, direction and availability. Selecting a component in the graph, XDSM or table scopes and highlights its rows.
  - Edit ports and component edits open as dialogs. There is no ports table in Details, no incoming or outgoing lists and no notes.

### 3.6 Configurations

- List with New configuration; each row names the configuration, its revision and model version.
- Saved configuration: header with name, revision and model version, read-only tag, Record details, **Copy configuration to draft**. Then, in this fixed order, which is the same for drafts, saved configurations and runs:
  1. **Context**: description, a strip naming the linked approach version and case with View modeling approach and View case in approach, and supporting evidence.
  2. **Inputs**: value, unit and provenance per free input; connected inputs are shown, not assigned.
  3. **Criteria**: numbered criterion records (quantity, comparison in words, threshold and unit, tolerances, evidence).
  4. **Assumptions**: the configuration's own, then one line "Model assumptions: N in Model version … · View model assumptions".
  - Then **Run this configuration** with its readiness reason, and **View model version** (the canonical model view of that exact version with the configuration's values).
- Draft editor: the same order with dedicated edit actions, input tools (including **Use a run result** for result-linked inputs), criteria editing, Add assumption, the approach and case picker, and Save configuration.

### 3.7 Runs

- History: newest first; failed and incomplete runs stay listed. Opening a run replaces the list.
- Run detail: record bar "Run record · Read-only" with Back to run history; heading with the configuration name and one context line (short run ID, case, View case); actions **Record details** (run ID, configuration revision, model version, start time, criterion evaluator, digests, dependencies), **Export**, **Create modified run**, and Refresh status while pending.
- Tabs **Results · Model · Configuration · Evidence**:
  - Results: Execution and Criteria tags; a failed run's execution diagnostic; outputs as readouts and a table, with full-precision values on request and "not computed" for missing outputs.
  - Model: the canonical model view, read-only, with this run's values.
  - Configuration: the shared configuration record, with per-criterion outcomes.
  - Evidence: the shared evidence index built only from the versions recorded with the run, then input provenance, criterion evidence, files and execution diagnostics.

### 3.8 Evidence

- **Assumptions**: every current assumption grouped by owner (latest saved approach version, each model's current draft, the latest revision of each configuration), each with its evidence rows and a link to its owner. Nothing is added here; adding happens at the owner. Reads are bounded and show partial and denied states explicitly.
- **Sources**: the evidence library with filter, **New evidence**, new versions of existing records, and View evidence (all versions, record details, download).

### 3.9 Shared dialogs

Study details; View evidence; attach evidence (choose existing or create, with a relationship such as supports, challenges or context); Record details; change preview (before and after, including current-revision differences on conflict); compare snapshots and portable model record; computational record export; result picker; unit editor; source view and editor; the unsaved-changes guard; run availability with its reason.

## 4. Target evolution: the workbench

Status: **proposed, not decided.** What follows is the recommended target (rationale in section 6 and in `docs/research/workbench-market/00-recommendation.md`), with the parts that are already decided marked as such. Order: the local edition ships first with the current screens; the workbench comes with the cloud edition.

### 4.1 Shape

```text
Home ── workspaces ── studies ── settings
          │
          └─ study workbench
               ┌ study header and section tabs ─────────────────────────────┐
               │ [structure / lists]  [main area: screen or canvas]  [Details│
               │                                                     or     │
               │                                                  Assistant]│
               │ [bottom: quantities table, outputs, activity]              │
               └────────────────────────────────────────────────────────────┘
```

### 4.2 Home, workspaces and settings

- **Cloud edition:** Home lists the workspaces the user can access and their studies; a workspace holds studies (and later documents and collaboration). Settings covers account and session, members and invitations of a workspace, assistant access (provider session, spend, local tool tokens), capability and readiness, display preferences and third-party notices. The access model (who owns a workspace, who can be invited, roles) is defined in `docs/specs/workspaces-identity-onboarding.md`; the UI shows it and never decides it.
- **Local edition:** one implicit workspace. Home stays the study list described in 3.2. Recommended default: do not show a workspace level until there is more than one.
- Study archive and restore stay on Home in both editions (decided).
- The shell is built on the current React and FastAPI stack, not on a forked workspace product (recommended; no permissive workspace application exists that would not duplicate HYPRN MVP's API, authorization or records).

### 4.3 Study workbench with docked panels

- The existing study screens become panels hosted by one HYPRN MVP layout component. Screens never import the docking library directly, so it stays replaceable. Recommended engine: dockview core (MIT), pinned; FlexLayout (MIT) as fallback; plain resizable panels for fixed shells such as Home and Settings.
- The default layout reproduces today's tabs, so nothing is lost for a user who never rearranges. Docking adds side-by-side work (for example a run's Model next to its Results, or the quantities table under any canvas).
- Panel layout is a per-user, per-study presentation preference stored outside scientific records. Arranging panels never changes model topology, solver order or any record.
- Below the narrow-width breakpoint and at 200 % zoom the workbench falls back to stacked tabs. Keyboard docking is required; if the chosen engine only offers it in a paid tier, HYPRN MVP builds it.
- The editor guard, access-loss seam and canonical components carry over unchanged: one panel never shows a second editable copy of something another panel is editing.

### 4.4 Assistant panel and agent activity

Decided (`docs/specs/agents.md`, ADR-0003, ADR-0004): the cloud assistant is a provider-hosted managed agent; HYPRN MVP owns a provider-neutral tool registry that calls the HYPRN MVP API as an agent principal acting for a user; the study is fixed by the session, never a tool argument; agent writes execute directly within the delegating user's authority, attributed and journaled, study creation and agent-labelled reviews included; agents may change or delete draft material under revision checks but never delete saved records, archive or restore anything, or manage access; provider or client approval prompts never widen what an agent can do. Agent proposals and confirmation cards are retired. The panel shows outcomes the platform recorded; it never reconstructs or repeats an operation to display it (one authoritative outcome per operation).

UI requirements:

- **Panel.** Docks on the right and replaces Details by default; both can be pinned on wide screens. It shows an explicit context chip (study and, where relevant, the selected model version, component, configuration or run) that the user can inspect and remove. Switching the main view never silently retargets a pending instruction; a conversation about a run stays tied to that run.
- **Agent activity.** The panel lists what the agent did, newest first, read from the action journal: typed operations, affected resources with links to the records they created or changed, outcomes (completed, failed, refused, uncertain), guard warnings and budget, not hidden reasoning. It is the same list as the local Agent activity page.
- **Concurrent edits.** An agent write never overwrites a dirty editor or a newer revision: overwrites need the agent's last-read revision, so the user's unsaved and saved work wins, and the agent's conflicting call fails with a conflict that the agent must resolve.
- **Drafts.** Agent edits to drafts are visible and restorable in the normal draft views; they are not hidden in the conversation.
- **Attribution.** Records written through an agent show an attribution chip "{assistant name} for {user}". The chip appears on studies an agent created, study context changes, evidence versions, model versions, approach drafts and versions, configurations, runs and working annotations; a scientific review recorded by an agent also carries the label "Recorded by an assistant".
- **Control.** **Stop** interrupts the assistant and is a separate control from scientific run cancellation. Assistant-originated text uses the assistant colour and the inference marking; computed and sourced facts keep their own basis.
- **Shared primitives.** Tool results render with the same HYPRN MVP components as the screens (resource chips, run outcome tags, change previews, evidence rows). There is no chat-only representation of a resource.
- Recommended libraries: assistant-ui unstyled primitives (MIT), wrapped once inside the design-system components and styled with design tokens; AG-UI events (MIT) over HYPRN MVP's own authenticated same-origin event stream. Rejected: closed or restrictively licensed chat frontends.

Local edition (decided in `docs/specs/agents.md`): there is no in-app conversation; the conversation stays in the desktop coding client, which reaches HYPRN MVP only through the local MCP tool server. The UI adds a study-scoped, read-only **Agent activity** page, a study view reached from a quiet entry in the study heading row (it is not a sixth tab): recent agent actions from the action journal, newest first, each with the agent attribution, the tool's plain-language operation, its outcome and links to the records it created or changed, plus the agents' current access to the study with an entry point to stop an agent by revoking its access. Tool tokens are listed and revoked through the CLI and the owner-session API, and revoked from the Agent activity page; minting is a CLI operation, and a token is shown once, printed only on request with `--show-token`. A separate token-management panel is deferred. Deleting saved records, archive, restore and access management stay human UI actions; a study an agent created appears on Home with its attribution chip.

### 4.5 Canvas wired to typed modeling commands

- Decided: the canvas is a view, never a second editable model graph. Every structural edit (add, connect, disconnect, remove, rename, edit ports or source) dispatches the same typed, revision-checked edit command through the HYPRN MVP API that the manual editors and the agent's model-editing tool use. The canvas holds no model state that outlives the API snapshot it was drawn from; a rejected or stale command leaves the canvas showing the server's state plus the user's preserved proposal.
- Drag-to-connect is a convenience over the same command with a keyboard equivalent. Node positions are a presentation preference; they never change solver or execution order. Feedback loops stay visibly loops.
- Recommended engines: xyflow (React Flow, MIT) with dagre (MIT) layout for the Graph projection and for study canvases (linked records, evidence, run lineage); XDSMjs (Apache-2.0) for the XDSM projection. Today's Graph and XDSM views are HYPRN MVP's own rendering and stay until a replacement passes the same interaction and accessibility checks.
- Viewers the numerical frameworks already produce (model structure diagrams, reports, case views) are generated in the restricted worker, kept as run artifacts and shown through the HYPRN MVP API in a sandboxed frame, instead of being rebuilt (recommended).

### 4.6 Authored documents

Source documents (uploaded files: versions, collections, reading, annotation, citation, extraction) are covered by `docs/specs/documents.md`, including their UI (Documents tab before Evidence, library, reader, citing). Authored in-app reports use a Tiptap-based editor later; live co-editing only for the multi-user cloud. A finished or cited text is frozen into an evidence version, so the editor never becomes a second source of truth (proposed).

### 4.7 Later capability views

These appear only when the backend computes and records the matching data; disabled mock controls are not shipped. Each reuses the same shell, tables and outcome component.

- Coupled solves and derivatives: solver scopes on the graph, convergence and residual history, derivative matrices with units and independent checks. Convergence and termination return to the run headline here.
- Optimization: configuration-level roles (design variables, objectives, constraints), termination separate from feasibility separate from criteria.
- Uncertainty: input distributions and dependence, sample tables with stable sample IDs and failure classes, honest ensemble bounds; sample completeness and applicability return here.
- Comparison and history: model, configuration and run comparison over exact snapshots; revision timelines with only API-returned metadata; restoring creates a new draft.
- Graph interactions still to reach full engineering parity: upstream and downstream highlighting with reset, multi-select batch actions with preview, a connection form with searchable valid endpoints and unit diagnostics, nested groups with breadcrumbs.

Plots must name their dataset, units and inclusion filters, offer a table and raw export, and never manufacture sequences from final values.

## 5. Decided, provisional and proposed

| Item | Status |
|---|---|
| Independently implemented UI over the public API only; no copied modeling-service UI | Decided (architecture) |
| Design system binding; system font stacks, inline SVG icons, "HYPRN MVP" wordmark, shell measurements 66 / 28 / 190 / 350 px | Decided |
| One canonical home per entity; read-only views reuse the canonical component; no duplicated information | Decided |
| Run headline Execution + Criteria only; other facets hidden until computed, never merged | Decided |
| One Assumption concept; no notes in the UI; Evidence page lists current assumptions grouped by owner | Decided |
| Canonical model view: Graph \| XDSM on top, quantities table below, component "what it computes and why" | Decided |
| Study-wide archive and restore from Home; studies never deleted | Decided |
| Overview About card with only View modeling approach; See more details → Study details; study conditions and limits only on the approach page | Decided |
| Section name shown once; footer "Third-party software notices" | Decided |
| Plain-language wording | Decided principle; wording pass in progress; `design-system/Naming.md` is the authority |
| Question box on both Overview and the approach page; quiet Archive button; stacked What / Why / Assumptions details; "Connected to" folded into Direction; per-criterion outcomes in the run's Configuration tab; no separate Record details in Run › Configuration; identical assumptions not grouped on the Evidence page; "What it computes" from the step's transformation text | Implemented as defaults; **acceptance pending** |
| Agent writes direct and attributed, never deletion of saved records, archive, restore or access management (ADR-0003); attribution chip; local Agent activity page | Decided (`docs/specs/agents.md`); not built |
| Home with workspaces, settings, members | Proposed; access model owned by `docs/specs/workspaces-identity-onboarding.md` |
| Docked study workbench (dockview core wrapped) | Proposed |
| Assistant panel on assistant-ui + AG-UI | Proposed |
| Canvas on xyflow + dagre, XDSM on XDSMjs | Proposed (the "canvas is a view over typed commands" rule is decided) |
| Tiptap authored documents, Yjs co-editing | Proposed, only when needed |

## 6. Rationale for the workbench recommendation

No permissively licensed open-source platform provides an engineering workbench that fits without duplicating what HYPRN MVP already owns. Notebook platforms run arbitrary user code and would bypass the attested worker; workflow and multidisciplinary-analysis frameworks duplicate the execution and numerical layers HYPRN MVP already uses; model-graph tools would introduce a second editable model graph; IDE shells impose a file-and-code workflow; and the workspace applications worth forking are under copyleft, source-available or paid licences. The fastest route is a thin HYPRN MVP shell on the current stack, a few permissive engines for the hard generic parts (docking, canvas, chat primitives, rich text, identity), and surfacing what the numerical and provenance frameworks already produce. Every new dependency needs a provenance and licence review before install; permissive licences only; libraries with recent licence drift (paid tiers appearing in previously free packages) are pinned and wrapped.

Licensing note that constrains the UI indirectly: the modeling service is a patched copy of an AGPL-licensed application. Legal review is pending before any commercial cloud launch, and a permissive replacement behind the Modeling Backend Contract is being scoped in parallel (`docs/legal/licensing.md`). The UI must therefore depend only on the HYPRN MVP API and the contract's public shapes, so that a backend swap changes no screen.

## 7. Known UI debt

**Acceptance.** The current screen composition (canonical model view, assumption simplification, run outcomes, Study details, case cards, Evidence index, Home archive) is implemented and passes automated checks. Human acceptance of the implemented result is pending, and any of the defaults in section 5 may be revised.

**Wording.** The plain-language pass is in progress. Known leftovers: "Recorded outputs", "Exact values", the "Scientific outcomes" accessible name, "Source and ports are retained for this version", "Definition not recorded", "Recorded limitations (legacy text)", the comparison dialog's "Exact …" labels, the canvas footer "1 connections", "View all runs/configurations", and `design-system/Naming.md` entries for Archive and Restore. The blank unit label ("Dimensionless" versus a marked blank) and the availability reason "Unavailable: Unknown" need a decision.

**Access-loss residuals.** Evidence hosts (evidence view, evidence picker, evidence library, assumption list, model editor, unit editor) still use their own denial classification instead of the shared session seam. Study-shell lists (Overview records, configuration and evidence lists, the comparison scope) are cleared on sign-out but not on a confirmed loss of access to the open study. Some configuration-editor reads (assumption evidence, unit preview, saved copies) are not on the seam, and a denied saved configuration shows the message twice. An independent security recheck of the access-loss fixes is recommended before they are recorded as mitigated.

**Structure.** The study shell is one large component holding routing, guards and dialogs; it is the natural seam for the workbench layout component. Navigation is hash-based with versioned links; there is no router. The Evidence page aggregates owner reads in the browser; a server-side assumptions read may be needed for large studies. Repeated identical assumptions across many configurations show one row each; the cause belongs to inherited-assumption work, not to the page.

**Missing affordances.** No "Archived" marker inside an opened archived study; no archive metadata (who, when) in the public read; Archive is not hidden for reviewers because the public read has no role field. No authored equations field for "What it computes". No attribution chip, Agent activity page or token revocation in the UI yet. Home rows carry no last-activity information because the API does not provide it.

**Deferred agent items.** Not built with the Agent activity page: the separate token-management panel (tokens are listed through the CLI and revoked from the page, the CLI or the owner-session API), the in-app list of platform-issue reports for the Owner and its export, and an in-app list and export of agent progress notes. The reports and notes are stored by the agent runtime and listed for the operator until these views exist.

**Tests.** Some browser test specs still target earlier screen compositions and need updating; some isolated fixture groups carry known failures that are compared against a baseline. Checks that pin built asset hashes need updating at each release.

## 8. Open questions (with recommended defaults)

1. **Screen defaults** (section 5, provisional row). Recommended: keep all of them as implemented.
2. **Workspace level in the local edition.** Recommended: hide it while there is a single implicit workspace.
3. **Docking.** Adopt dockview core behind a HYPRN MVP layout component, or keep fixed section tabs for the first cloud release? Recommended: keep tabs as the default layout and add docking after the licence review, with a keyboard path built in-house if needed.
4. **Assistant panel placement.** Recommended: right dock replacing Details, both pinnable on wide screens; agent activity also listed on the study-level "Agent activity" page in both editions, so what an agent did is never only inside a scrolled conversation.
5. **Equations in the model view.** Recommended: keep the method step's transformation text plus View source; add an authored equations field only as a typed domain change.
6. **Evidence page grouping of identical assumptions.** Recommended: no grouping; fix repetition at its source.
7. **Opened archived study.** Recommended: a quiet "Archived" tag in the study header with Restore beside it for users who may restore.
8. **Framework viewers.** Recommended: show worker-generated model diagrams and reports as run artifacts in a sandboxed frame, after the artifact read path supports it.

## 9. Out of scope

- Copying, embedding or proxying any modeling-service UI, or letting the browser call private services.
- A second editable model graph in the canvas, the assistant or browser storage.
- Chat-only resource representations, provider-hosted chat frontends, or treating provider approvals as HYPRN MVP authority.
- Agent controls that delete saved records, archive, restore or manage access.
- Showing outcome facets that no framework computes; mock controls for unsupported numerical methods.
- Deleting studies from the UI; deleting or rewriting recorded runs to continue authoring.
- Notebook or arbitrary-code surfaces inside the product.
