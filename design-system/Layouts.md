# Layouts

Page compositions for HYPRN MVP at the 1440 × 1000 reference viewport. Build them from the components in `ui/src/design`; every measurement below is a token from `tokens.json`. Each entity has one canonical home, and the same entity looks the same wherever it appears.

## Current ownership (ADR-0007–0010)

Overview contains the Study brief and saved Study answer, with answer exploration directly
beneath its outcome. There is no modeling approach page or duplicated method inventory.
Model explanation is an application-owned, versioned record on Models, pinned to the exact
model it explains. Analyses group configurations, runs, sampled designs and assessed
estimates. The figure pins an analysis version and optional assessed estimate: controls
change only the selected vector; plot axis selection is independent. It never samples or
fits while sliding. Use the shared scientific-state components for original, estimated,
updating and unavailable values. Why links each number to its recorded basis.

The following compositions apply with these owners; references below to the old approach
layout are superseded by this ownership rule.

## The shell

WorkspaceShell composes persistent NavigationRail, central current canvas, Scientific context and independent Assistant slots. Home, Profile, current study identity and the three study destinations remain real guarded actions. The shared logo retains supplied geometry on a transparent, theme-aware ground. There is no second application bar duplicating navigation.

Study destinations are Overview, Models and Experiments. The approved [Analyses grouping](components/Calculations.md) places Analyses, Configurations and Runs tabs beneath a saved model/version selector; the area opens on Analyses. Navigation buttons use aria-current; tabs within one record use roving tab semantics. The current study/record heading belongs to its central owner. Agent activity remains a future page pending its actual route and API; no dormant destination is exposed.

The canvas uses radius-shell, canvas ground and shadow-shell. Raised panels use surface-raised/shadow-panel; sunken wells have no shadow. Scientific context docks beside it where space permits and stacks below at narrow widths/zoom. The assistant opens from its persistent lower-right labeled launcher into a reserved right column that compresses the canvas; closing restores its width. At narrow widths, the assistant stacks above the canvas without overlaying it. Both retain a visible title, Close and applicable Back control. Footer notices remain accessible. Only chrome carries the neutral gradient and static texture.

## Home

Centred [ContentColumn](components/ContentColumn.md) of `home-max` (1080px). Heading "Studies" with the primary "New study" action. A toolbar holds the "Find a study…" filter (`search-width`, 300px) and a segmented switch **Active | Trash** with counts. Each study is a row: name as an `accent` link in `subheading`, its description in `ink-2` (at most `form-max` wide), with "Open" and "Delete" stacked at the right (Trash rows offer "Restore"). Delete study asks for confirmation with the primary action "Move to Trash" and explains that every record is retained and can be restored. Trash uses the recoverable archive state; no permanent deletion is exposed. Creation and profile pages use a centred panel of `form-max` (720px); sign-in uses `login-max` (480px).

## Overview

Overview is one [ContentColumn](components/ContentColumn.md) of `home-max`: the study brief leads, then the saved conclusion, exploration and the remaining sections, each spanning the column with `space-4` between them.

For a saved study answer, the current composition is Study question, Saved
conclusion, Explore the answer, then expandable Interpretation & qualifications. Preserve complete saved
prose and qualifications. Methods are reached from Models and remain editable at
their existing approach owner; an answer's Open model carries both exact model and
approach versions. This supersedes the earlier Overview method/inventory placement
below; retained approach readers keep their own full review composition.

1. The full saved question leads, with Study details and its existing Edit study action.
2. Saved conclusion displays the complete authored interpretation (or observations when interpretation is empty), its saved version, and Supporting results. Supporting results opens the scientific-context panel with direct configuration and run actions. Slider changes never rewrite this conclusion.
3. Generic answer exploration occupies the central working area. The default shows every independent input on the left, a central expandable Model control and selected outcomes stacked on the right. Both quantity columns share their top/bottom bounds without implying input/output pairs. Expand model reveals connected and intermediate quantities. Select outcomes saves display settings independently of numerical preparation. Inputs and output readouts remain separate from wider response plots. The plot-axis selector is independent of slider selection. Calculated and estimated points retain their distinct marks and shared palette.
4. Expandable interpretation and qualifications retain observations, limits, unanswered deliverables with answer record details in the title metadata row above the saved conclusion. Sample settings separates Input ranges, Sampling and Assessment without discarding unsaved edits. Proposed requests remain distinct from recorded sampling and assessment. A displayed estimate is not a calculation or a finding of validity.

Qualitative dimensions use shared choice buttons for up to four declared values and a labelled select for longer lists. Labels, values and supported combinations come from study data; selecting a choice uses the existing exact configuration and surrogate path. Unsupported combinations are disabled, and no interpolation between category labels is implied.

Methods remain at their canonical Model owner. Study answers cite configurations, runs and evidence directly. There is no competing method map in Overview. This is the current target composition; the main integration owner records the explorer/served acceptance separately.

Study details separates question, approach, assumptions, limits and open questions. Empty optional read-only prose is omitted; editing retains its controls. Statements have direct View evidence actions. Answer-wide basis never implies per-passage support.

## Models

The Models tab lists models ("New model" as the primary action, one row per model with "Open model"). An open model shows one canonical model view, used everywhere a model appears (Models draft and versions, a run's Model tab, a configuration's model version, the modeling approach's linked model version):

1. A back link "Return to all models", then the heading: the backend-provided model name for both draft and saved versions. Below it one state tag: "Saved draft", "Unsaved changes" or "Read-only".
2. Version controls say **Current draft** or **Saved version · ID <short ID>**. Exact option identities remain unchanged and complete IDs stay in Model record details. Draft-only **Save model version** explains that it creates a read-only version; **Create configuration** and **Model actions** retain their lifecycle guards. Do not invent dates or ordinals absent from the version record.
3. The main switch is **Diagram | Model explanation**. Diagram retains **Graph | XDSM** and Clear selection. There is no Details toggle or side reader.
4. The graph spans the available width in a bounded viewport. The selected component reader follows it in document flow, with **Component | Python | Quantities**. Tabs hide panels without unmounting authoring state. Selection never scrolls the graph away; the reader tabs provide direct navigation.
5. The canvas has search and draft authoring actions, a dotted ground, complete wrapping component names and quantity symbols, and compact readable port rows. **Fit model** fits measured nodes and routed connections with padding. Initial layout fits automatically; deliberate zoom/pan is preserved until Fit model is requested. Drag the background or use arrow keys to pan; ordinary wheel input scrolls the document. The footer shows counts and the actual selection. Three-component models use the available width for a readable arrangement rather than reducing a tall two-row graph to tiny text.
6. Model explanation shows each multi-component method once, with its title, the shared record-details metadata row, linked components and authored prose. A single-component method belongs only in its owner's Explanation. Shared prose is never repeated there; link to Model explanation instead. Empty prose is omitted. Python has its own full-width pane, checked against the exact model's hashes. Existing approach editing requires explicit save. Model assumptions and authoring remain reachable without component selection. Editor identity and dirty guards survive both tab levels.
7. Quantities has one full-width table at its canonical owner. Filters cover search, component and direction with All components as the escape. **Edit quantity** selects the exact owner through its guard, then opens the existing quantity editor at the saved port's optional definition. Optional absence creates no blanket notice. Saved versions expose no mutation action.

## Configurations

1. The configurations list with "New configuration"; a new configuration starts by choosing a model, whose current draft is saved as the model version for that configuration.
2. An open configuration: a back link "Return to all configurations", its name, a state tag below the title ("Read-only" or the shared draft state) with a separate "Configuration record details" action, and the model version as secondary context. Saved versions are listed as "Configuration version" entries ("N saved versions").
3. One composition, in this order, for a draft, a saved configuration and the configuration kept with a run: **Inputs and provenance, Assumptions**. Empty assumptions and zero-count links are omitted.
   - Study/configuration context stays in record details; draft description and general-context source editing are in **Input tools**. Sources that support inputs appear beside those assertions.
   - **Inputs**: a table (Quantity · Value (`Field`, compact) · Units · Provenance). Every input is visible without scrolling at 1440 × 1000; no graph or diagram comes before the inputs. One line beneath the table explains that blank values are missing and zero is an explicit value.
   - Study criteria belong to the brief and calculations; omit a configuration Criteria section.
   - **Assumptions**: statements with their attached evidence.
4. The primary "Run this configuration", with the reason stated beside it when it is unavailable ("Save the configuration before running.").
5. A modified run starts from one editable copy of its configuration's recorded context; there is no side-by-side comparison of earlier and current study context.

## Runs

A `Panel` with `CollectionToolbar` count/refresh and shared collection filters, then one
`ResourceCard` per run: configuration-based name and short run ID, submission state and
author attribution, Open run. This is the same card/action recipe as calculations and
configurations. Submission metadata never claims numerical success. No duplicated list title.

Opening a run replaces the list. The saved-run bar and title/actions remain above one
**Execution** panel using the shared `MetricGrid` (see Scientific states). Failure reasons
remain visible; **Execution details** opens secondary diagnostics, source mapping and files.
Then **Results · Model · Configuration** select the content:

- **Results** shows the complete Outputs table: Output, Value and Units. No repeated execution
  ledger or criteria. Missing values read “not computed” with the recorded reason.
- **Model** shows the saved model version the run used, read-only.
- **Configuration** shows its saved inputs/provenance and assumptions, read-only.

Run content stays readable from stored records even when the modeling service is unavailable.

## Evidence

Evidence titles and **View evidence** actions use the same compact presentation beside each assertion. The source library remains available to authoring and existing direct links, but is not a study tab.

## Agent activity — future capability

The following layout is a retained target, not a delivered navigation destination. It requires the attributed activity/access API and page owner; the Contour lane does not expose it.

A study page, read-only apart from "Revoke access", reached from the "Agent activity" button in the study header. It is not a sixth study tab: the five study tabs stay, none is current on this page, and the breadcrumb reads `/ <Study> / Agent activity`. Leaving an editor for it goes through the editor guard. Top to bottom, inside the content column:

1. `SectionHeader` (level 2) "Agent activity", with a `quiet` "Refresh" on the right.
2. A `body` intro in `ink-2` saying what assistants did for you in this study, newest first, each marked with who acted, and that they never delete saved work, archive or restore anything, or change who has access.
3. Assistant status notices, when any apply ("Assistant access off", "Access ended"), `space-4` apart: an `advisory-soft` ground with an `advisory` border, an `advisory` `StatusTag` first, then the text and, for ended access, the renew command in `code` with "Copy command".
4. `Panel` "Agent access": one row per agent with current access, a `line` hairline between rows. Line 1 is the `AttributionChip` with, for the study Owner only, a `secondary` "Revoke access" at the right end (absent, not disabled, for anyone else). Line 2 in `small`, `ink-muted`: the access expiry and this session's usage, or "No open session.". Revoking asks for confirmation in a dialog titled "Revoke access for {agent}?" with `danger` "Revoke access" and `secondary` "Cancel" (initial focus).
5. `Panel` "Activity", `space-6` below the access panel: the segmented `Tabs` **Changes | All calls**, then a list of agent calls, newest first, a `line` hairline between rows, `space-3` vertical padding. Each row: the operation in `body-strong` with the outcome `StatusTag` at the right end; a `small` metadata line starting with the `AttributionChip`, then the start time and "Record details" (dialog "Agent action record"); a reason line for refused, failed, uncertain and in-progress calls; one "Warning" tag and text per warning; `quiet` record links to the records the call created or changed. "Changes" leaves out completed reads and says how many; "All calls" lists them. "Show more activity" ends the list while more exist.

The page reads what was stored and never repeats an agent's call. An agent call's "Completed" is never a run's Execution or Criteria; runs keep their own tags on their own pages. Every row, link group, tag, chip and command wraps; at genuine 200% zoom and below 600px rows and action groups stack to one column without horizontal page scrolling.

## Historical views

Opening a saved model version, or the model or configuration used by a run, shows the `RecordBar` directly under the study tabs across the full content width. Editors become read-only and primary actions are removed, not disabled.

## Narrow screens and 200% zoom

Below 1150px the page gutters narrow and the model heading wraps. Below 1050px the workbench stacks (canvas, then details) and each part scrolls inside its own box. Below 600px rows, filters and action groups wrap to a single column and the shared logo retains its shared component size. Tables scroll inside their own box; the page never scrolls sideways. The primary action and header actions stay reachable without horizontal scrolling at genuine 200% zoom in both themes. Controls switch to `control-floor` on touch devices.


## Continuous method reading

Model readers preserve Purpose, Basis and reasoning and Analysis logic without a duplicate contents strip. Python is a separate component pane. Shared method references remain explicit and methods never collapse distinct component instances.

### Minimal model controls

The canonical model title and model actions share one responsive header row; model navigation has its own row. Do not add a sentence explaining Save model version beside the named control. Component reading uses Component / Python / Quantities. The Component pane contains the name, its optional instance-owned explanation and existing linked method content, with one Edit component dialog for name and explanation. This description belongs to the model snapshot, not to an approach method or a browser-local store. Shared approach prose remains in Model explanation. Saved readers use their exact snapshot annotation and expose no mutation control.

Python contains source editing and source-file import, without component/quantity actions or an Expand source toggle. Quantity management remains reachable from Component actions. A table row opens only that saved quantity in the existing guarded editor; adding/removing quantities remains in the all-quantity management dialog. Omit Jump to Quantities, Read component, the redundant scoped-table Inspect component action, and the no-component-explanation cross-link when the primary Model explanation tab already provides navigation.

## Contour workspace amendment

The current shell has four independent regions: persistent NavigationRail, current central canvas, Scientific context and Assistant. Scientific context docks beside the canvas where space permits and stacks at narrow widths. The independent assistant uses the global lower-right labelled Assistant button and a reserved right column that compresses the canvas; closing restores its width. At narrow widths the assistant stacks above the canvas. Contour owns this visual recipe. Headers, Hide assistant and source Back controls remain reachable. Assistant full-width mode preserves the hidden canvas/details state and restores it on exit; see [AssistantPane](components/AssistantPane.md). Overview follows question → saved conclusion → generic exploration → expandable interpretation/qualifications. Method content belongs to the canonical Model owner; the earlier Overview expandable-method arrangement is superseded.

The Component tab uses the selected component name as its only heading, with Edit component and Edit quantities in the same SectionHeader row. Actions wrap together below long names on narrow screens. Do not repeat a generic Component heading inside the tab. Saved versions keep the same name heading without edit actions.

## Configuration alignment correction (2026-10-16)

Preserve the existing configuration composition: study heading and back navigation, configuration name/state/model with its existing header actions, the complete Inputs and provenance table, Assumptions, then Run and View model version. The rejected configuration mockup is not a design target: do not group inputs, collapse provenance, replace saved field surfaces or move Run into the header.

Configuration headers stay in normal document flow above their existing Panel; never position them absolutely or reserve a fixed-height spacer. The shared configuration-heading recipe aligns the title and action group at the top, permits long names to wrap, and stacks left-aligned actions below the title at narrow widths. Back navigation must remain unobstructed with long titles and at 200% zoom. Saved and draft configuration headers share this recipe.

Numeric fields and their column heading align right. Keep saved values in the existing read-only Field surface, with exact precision in its tooltip; formatting never changes stored values. Read-only units use the shared displayUnit typography (kg/m**3 → kg/m³), while unit choices, stored spellings and dimensionless declarations remain unchanged.

## Record metadata position

Every record type uses [RecordDetails](components/RecordDetails.md): one underlined label-and-arrow opening control in a wrapping metadata row immediately below its owning title, alongside storage state when available. This applies to page headings, embedded records and full evidence/prediction readers. Keep record metadata out of export/edit action groups, overflow menus and content footers.

## Shared header and record formatting

Every record and collection page uses the shared [PageHeader](components/PageHeader.md):
return and related links in normal flow above, then the title with its record details
and state, and on the right the version choice followed by commands. Title and
commands start on the same row; long titles wrap within their column; commands never
align to the middle of the title-plus-metadata block. At narrow widths commands wrap
below, left aligned. Returns use ReturnLink and read "Return to <destination>". Screens
must not build their own heading, return or row recipes; the component check rejects
them.

Keep existing page compositions. ResourceCard actions use its `actions` slot;
cards retain shared padding and a visible gap between adjacent cards. Section
titles use SectionHeader, never an action-only alignment container.

Run results show the Execution facts above the Results / Model / Configuration tabs,
separated by `space-6`. Status and elapsed wall time stay in Execution. Original execution artifacts remain in
computational exports; no duplicate Execution details projection is shown. Criteria belong to the brief and
calculation evaluations. Failure, timeout, incomplete and uncertain states stay visible.

Evidence actions use one View evidence (n) per item and open the shared details slot. Source content never opens in an evidence popup. Existing page compositions remain unchanged.

All global contextual details use the shared `DetailsDock` / `ContextualPanel` recipe, including Statement details, evidence and Supporting results. Reader type never changes the dock dimensions; see [ContextualPanel](components/ContextualPanel.md).

## Grouped application sidebar (2026-10-17)

Use the shared [NavigationRail](components/NavigationRail.md) on every signed-in
page: brand/collapse, Home, study card, Overview, Workflows, Library, then
Help/Settings/account at the bottom. Documents and Help explicitly state that the
functionality is not implemented yet. Every destination retains the existing
navigation guards; the evidence library is a first-class Library destination.

## Minimal record and study-card amendment

Record details is first in the row directly below a record title, storage state to its right. Canonical identities remain inside Record details; cross-references omit version IDs outside choice controls and technical record details. Statements open evidence directly without an intermediate statement panel.

Study cards retain title and description at left. Their ResourceCard actions slot uses the stacked recipe at right: bordered Open, then bordered Archive (Restore for archived studies), equal width, space-2 gap and vertical centering within the card. Narrow cards wrap the complete action stack below content without overlap; screens do not position individual buttons.


Alternatives comparison uses the shared `hf-table--comparison` recipe: separate alternative,
calculation link, output, numeric value, criterion and evaluation columns; an optional reason
column is present only when authored. Values keep numeric alignment and units together.
At narrow widths the table scrolls locally instead of breaking ordinary words into fragments.
Analysis mappings without a cited comparison row remain accessible as supporting
calculations; the exploration basis is labelled from the answer's actual pin.

## Model explanation reader

Keep the Models tab and panel. The panel has one PageHeader titled Model explanation;
no second panel title or generic Explanation heading. Record details, explanation state
and attribution appear below it, with one Edit action at the right. The selected Models
version determines the reader: draft explanation for Draft, immutable explanation for
that exact saved model. Omit empty optional prose/component/evidence sections.

Model explanation owns physical meaning, governing equations, assumptions, applicability
and component reasoning. Sampling design, accuracy targets and numerical assessment
belong in Analysis details. Editor guidance and agent authoring rules enforce this boundary;
never classify or remove stored prose by keywords. Exact historical records remain readable.

Save draft edits the explanation draft. Save for model version appears in the editor and
opens a dialog with the exact target and an explicit save action; no permanent selector or
already-saved notice in the reader. An explained version has no replacement action.

Version numbers come from recorded metadata or complete unbranched model ancestry, never list order. If unavailable, show `Saved · <identifier>`; keep full identities in record details. VersionSelect owns its visible label unless the surrounding field already labels it.

## Compact workspace controls

Settings opens in a shared dialog over the current workspace, preserving its route,
selected versions and unsaved editors. Group Account and Appearance in inset sections;
stage changes until Save, with Cancel first and the primary Save last. Prevent dismissal
while saving. Direct profile URLs remain supported.

Home counts appear once in the collection heading. Preserve loading, filtered-count,
partial-list and error states. Short resource cards use horizontal actions beside their
content, wrapping without clipping on narrow screens; empty body slots add no height.

Exploration controls belong to their columns: Load point above Inputs, Plot against and
Select outcomes above Outputs. Input ranges is the section-wide settings action. On narrow
screens retain that ownership when stacking columns. Controls retain their existing effects.

Editor field legends use the shared subheading hierarchy; field labels, values and hints
remain distinct. Visible unit labels are concise, while accessible labels retain the specific
quantity identity. Persistence bars use neutral tonal surfaces, separate from scientific status.


## Shell and editor rhythm

The desktop canvas has the same viewport minimum height as the Assistant dock;
content may extend it. Narrow layouts stack the dock and canvas without forced
empty viewport height. Fieldset legends use the same field-to-control spacing
inside nested reading sections as at the root of an editor.

Compact answer exploration contains varying input controls and outcomes only.
Inputs fixed in the saved analysis remain visible in Input ranges and the model;
they do not become sliders or captions below the controls. The renderer uses the
saved dimensions, never quantity names, to make this distinction.
