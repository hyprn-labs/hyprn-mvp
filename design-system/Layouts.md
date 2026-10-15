# Layouts

Page compositions for HYPRN MVP at the 1440 × 1000 reference viewport. Build them from the components in `ui/src/design`; every measurement below is a token from `tokens.json`. Each entity has one canonical home, and the same entity looks the same wherever it appears.

## The shell

WorkspaceShell composes persistent NavigationRail, central current canvas, Scientific context and independent Assistant slots. Home, Profile, current study identity and the five registry destinations remain real guarded actions. The supplied unchanged logo sits on its brand-ground plate. There is no second application bar duplicating navigation.

Study destinations are Overview, Models, Configurations, Runs and Cases. Navigation buttons use aria-current; tabs within one record use roving tab semantics. The current study/record heading belongs to its central owner. Agent activity remains a future page pending its actual route and API; no dormant destination is exposed.

The canvas uses radius-shell, canvas ground and shadow-shell. Raised panels use surface-raised/shadow-panel; sunken wells have no shadow. Context and assistant dock beside it where space permits and stack below at narrow widths/zoom. Each retains a visible title, Close and applicable Back control. Footer notices remain accessible. Only chrome carries the neutral gradient and static texture.

## Home

Centred column of `home-max` (1080px). Heading "Studies" with the primary "New study" action. A toolbar holds the "Find a study…" filter (`search-width`, 300px) and a segmented switch **Studies | Archived** with counts. Each study is a row: name as an `accent` link in `subheading`, its description in `ink-2` (at most `form-max` wide), then "Open study" and "Archive" (Archived rows offer "Restore"). Archiving asks for confirmation and says the study can be restored from Archived. Studies are archived and restored, never deleted. Creation and profile pages use a centred panel of `form-max` (720px); sign-in uses `login-max` (480px).

## Overview

1. The full saved question leads, with Study details and its existing Edit study action.
2. Generic answer exploration occupies the central working area; the integration owner supplies supported numerical behavior.
3. Interpretation and still-to-answer content follow, retaining the whole answer's basis and exact related run/configuration/case-answer links. A displayed estimate is not a calculation or a finding of validity.

Methods remain at their canonical Model owner. Cases have their own tab and exact approach-version/case identities; a case answer is a distinct saved record. There is no competing method map in Overview. This is the current target composition; the main integration owner records the explorer/served acceptance separately.

Study details separates question, approach, assumptions, limits and open questions. Empty optional read-only prose is omitted; editing retains its controls. Statements have direct View evidence actions and may additionally offer an explicitly scoped ClaimButton. Answer-wide basis never implies per-passage support.

## Models

The Models tab lists models ("New model" as the primary action, one row per model with "Open model"). An open model shows one canonical model view, used everywhere a model appears (Models draft and versions, a run's Model tab, a configuration's model version, the modeling approach's linked model version):

1. A back link "← All models", then the heading: the model name for the draft, or "Model version <short ID>" for a saved version. Below it one state tag: "Saved draft", "Unsaved changes" or "Saved version · read-only".
2. Right-aligned on the same row, in this order: the version select (`<short ID> (draft)` or `<short ID> (read-only)`), the primary "Save model version" (draft only), "Create configuration", and the labelled "Model actions" menu (rename, reload, import, export).
3. A toolbar row: the view switch (`Tabs`, segmented: **Graph | XDSM**) on the left; on the right "Clear selection" (when something is selected) and the "Show/Hide Details" toggle.
4. The workbench: `[canvas, fluid] [details panel-inspector (350px)]`, `space-3` gaps, every panel `radius-md`. Its height is fixed on desktop so the details never move off-screen.
5. The canvas panel has its own toolbar (search "Search this model…" on the left; component and connection authoring actions on the right for a draft), a dotted `canvas` ground with `ModelNode`s, and a footer line: "N components · M connections" (singular for one) on the left, "Select a component to inspect its source and method" on the right.
6. Component details use the canonical **Purpose**, **Basis and reasoning**, **Calculation logic**, and **Python function** presentation. Empty prose is omitted; a method shared by several components is labelled as shared. Python source is checked against the exact model's hashes and shown as text. Only the current model panel offers explanation/source editing and assumption authoring. Explanation edits use the existing approach draft, with an explicit save; saved approach versions stay unchanged until a new approach version is published. **Method record**, after the Python function, keeps exact pins. There is no return-to-method link in the model inspector. Draft actions **Edit component** and **Edit quantities** sit above the component title; **Edit explanation** precedes the narrative with its own spacing; additional shared-code recipients appear only when sharing exists. There is no port-metadata paste control, ports table, incoming/outgoing list or notes section.
7. Below the workbench, full width: the **quantities table** (each quantity's symbol, meaning, units and, in a configuration or run context, its value), linked to the selection. Filters cover search, component and direction; unavailable values keep their reasons in the table.

## Configurations

1. The configurations list with "New configuration"; a new configuration starts by choosing a model, whose current draft is saved as the model version for that configuration.
2. An open configuration: a back link "← All configurations", its name, a state tag below the title ("Saved version · read-only" or the shared draft state) with a separate "Configuration record details" action, and the model version as secondary context. Saved versions are listed as "Configuration version" entries ("N saved versions").
3. One composition, in this order, for a draft, a saved configuration and the configuration kept with a run: **Inputs and provenance, Criteria, Assumptions**. Empty assumptions and zero-count links are omitted.
   - Study/configuration context stays in record details; draft description and general-context source editing are in **Input tools**. Sources that support inputs and criteria appear beside those assertions.
   - **Inputs**: a table (Quantity · Value (`Field`, compact) · Units · Provenance). Every input is visible without scrolling at 1440 × 1000; no graph or diagram comes before the inputs. One line beneath the table explains that blank values are missing and zero is an explicit value.
   - **Criteria**: numbered `CriterionRecord`s; a draft has a dedicated "Edit" action in the section header.
   - **Assumptions**: statements with their attached evidence.
4. The primary "Run this configuration", with the reason stated beside it when it is unavailable ("Save the configuration before running.").
5. A modified run starts from one editable copy of its configuration's recorded context; there is no side-by-side comparison of earlier and current study context.

## Runs

A single `Panel` list, newest first: one row per run (name from its configuration plus short run ID as a link, model version and configuration as `small` metadata, Execution and Criteria tags at the right); no list-order commentary. Opening a run replaces the list; history and detail are never side by side.

The run detail shows the "Saved run · read-only" record bar and a heading with the run's actions grouped together (the side-by-side "Export model and data" and "Export computational record" group, Record details, "Create modified run"), shared by all its tabs, and the run tabs **Results · Model · Configuration**:

- **Results** leads with the run headline (the "Run status" `Ledger` with Execution and Criteria; see [Scientific states](Scientific-states.md)), then the complete "Outputs" table. Each output appears once; no arbitrary subset is promoted. The table has Output, Value and Units columns. An unavailable value reads "not computed" with its reason in the Value cell.
- **Model** shows the model version the run used, in the canonical model view, read-only.
- **Configuration** shows the configuration the run used in the shared Inputs and provenance, Criteria, Assumptions order, read-only, with its own "Record details" beside its read-only tag.
- **Run files and diagnostics** is a disclosure beneath Results. Evidence is shown beside the model or configuration assertion it supports; there is no run Evidence tab.

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

Below 1150px the page gutters narrow and the model heading wraps. Below 1050px the workbench stacks (canvas, then details) and each part scrolls inside its own box. Below 600px rows, filters and action groups wrap to a single column and the unchanged logo retains its shared component size. Tables scroll inside their own box; the page never scrolls sideways. The primary action and header actions stay reachable without horizontal scrolling at genuine 200% zoom in both themes. Controls switch to `control-floor` on touch devices.


## Continuous method reading

The Model inspector preserves Purpose, Basis and reasoning, Calculation logic and Python function. ReadingContents appears only when multiple existing sections can be visited. Its buttons focus the actual heading; Python function opens the existing disclosure before moving focus. It never changes a route, graph or scientific record. Shared method references remain explicit and methods never collapse distinct component instances.

## Contour workspace amendment

The current shell has four independent regions: persistent NavigationRail, current central canvas, Scientific context and Assistant. Context and assistant dock beside the canvas where space permits and stack at narrow widths. Their headers, Close and source Back controls remain reachable. Overview follows question → generic exploration → interpretation/still-to-answer. Method content belongs to the canonical Model owner; the earlier Overview expandable-method arrangement is superseded.
