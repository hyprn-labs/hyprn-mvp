# Layouts

Page compositions for HYPRN MVP at the 1440 × 1000 reference viewport. Build them from the components in `ui/src/design`; every measurement below is a token from `tokens.json`. Each entity has one canonical home, and the same entity looks the same wherever it appears.

## The shell

- **App bar**: `appbar-height` (66px) tall, `surface`, `line` bottom edge, `page-gutter` (28px) side padding. Left: the supplied HYPRN logo, with no duplicate text wordmark, then the main navigation: a "Home" link and, inside a study, the breadcrumb `/ <Study> / <Section>` (study name in `ink-muted`, truncated with an ellipsis; current section in `ink`). Right: the "Profile" button. Nothing else lives here.
- **Study header**: one `title` with the study name. The current section is named once, by the selected study tab; there is no subtitle repeating it. At the right end of the same row, a `quiet` "Agent activity" button, always shown inside a study and without a count, opens the study's Agent activity page. The header is omitted inside an open model and an open run, which carry their own headings.
- **Study tabs** (`Tabs`, underline variant): Overview, Models, Configurations, Runs, Cases. They sit under the header, full width, with a `line` rule beneath and `space-6` below.
- **Content** on `canvas`, maximum width `page-max` (1600px), `page-gutter` side padding.
- **Footer**: a "Third-party software notices" link in `small`, `ink-muted`.

## Home

Centred column of `home-max` (1080px). Heading "Studies" with the primary "New study" action. A toolbar holds the "Find a study…" filter (`search-width`, 300px) and a segmented switch **Studies | Archived** with counts. Each study is a row: name as an `accent` link in `subheading`, its description in `ink-2` (at most `form-max` wide), then "Open study" and "Archive" (Archived rows offer "Restore"). Archiving asks for confirmation and says the study can be restored from Archived. Studies are archived and restored, never deleted. Creation and profile pages use a centred panel of `form-max` (720px); sign-in uses `login-max` (480px).

## Overview

1. **About this study** contains the saved study question and **See more details**. Its Study details dialog has one **Edit study** action for the name, list description, question, approach, assumptions, limits and open questions. Fields and assertion editors have distinct spacing.
2. **Answer to the study question** follows immediately, then **Reasoning and methods**. The answer's supporting results lead with each case answer title and an aligned row of **View configuration**, **View run**, **View case answer** actions; identities remain in record details.
3. **Cases** is a study tab. Its list has a case filter and an Open case action per row; selecting a case opens its detail with an All cases back action. Exact approach-version and case identities remain in the URL; configurations own their associated runs. Each answer separates its scientific explanation from supporting results and sources. A referenced case answer opens in a dialog.
4. Expanded methods give the purpose a full-width lead, with separate shaded sections for basis/reasoning and calculation in plain words, followed by Python source. The sections stack on narrow screens. **View model details** stays at the bottom-right of the full method.

Study details keeps the question separate from the current approach and limits. Empty optional prose, assumptions and limits are omitted in read-only views; editing retains the controls needed to add them. Every assertion has its own compact evidence title and **View evidence** action; shared sources are not grouped away from the assertions. Version and relationship details belong inside the evidence view.

## Models

The Models tab lists models ("New model" as the primary action, one row per model with "Open model"). An open model shows one canonical model view, used everywhere a model appears (Models draft and versions, a run's Model tab, a configuration's model version, the modeling approach's linked model version):

1. A back link "← All models", then the heading: the model name for the draft, or "Model version <short ID>" for a saved version. Below it one state tag: "Saved draft", "Unsaved changes" or "Saved version · read-only".
2. Right-aligned on the same row, in this order: the version select (`<short ID> (draft)` or `<short ID> (read-only)`), the primary "Save model version" (draft only), "Create configuration", and the labelled "Model actions" menu (rename, reload, import, export).
3. A toolbar row: the view switch (`Tabs`, segmented: **Graph | XDSM**) on the left; on the right "Clear selection" (when something is selected) and the "Show/Hide Details" toggle.
4. The workbench: `[canvas, fluid] [details panel-inspector (350px)]`, `space-3` gaps, every panel `radius-md`. Its height is fixed on desktop so the details never move off-screen.
5. The canvas panel has its own toolbar (search "Search this model…" on the left; component and connection authoring actions on the right for a draft), a dotted `canvas` ground with `ModelNode`s, and a footer line: "N components · M connections" (singular for one) on the left, "Select a component to inspect its source and method" on the right.
6. Component details and the Overview method use the same **Purpose**, **Basis and reasoning**, **Calculation logic**, and **Python function** presentation. Empty prose is omitted; a method shared by several components is labelled as shared. Python source is checked against the exact model's hashes and shown as text. Only the current model panel offers explanation/source editing and assumption authoring. Explanation edits use the existing approach draft, with an explicit save; saved overview versions stay unchanged until a new approach version is published. **Method record**, after the Python function, keeps exact pins. There is no return-to-method link in the model inspector. Draft actions **Edit component** and **Edit quantities** sit above the component title; **Edit explanation** precedes the narrative with its own spacing; additional shared-code recipients appear only when sharing exists. There is no port-metadata paste control, ports table, incoming/outgoing list or notes section.
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

A single `Panel` list, newest first: one row per run (name from its configuration plus short run ID as a link, model version and configuration as `small` metadata, Execution and Criteria tags at the right); no list-order commentary Opening a run replaces the list; history and detail are never side by side.

The run detail shows the "Run record · Read-only" record bar and a heading with the run's actions grouped together (the side-by-side "Export model and data" and "Export computational record" group, Record details, "Create modified run"), shared by all its tabs, and the run tabs **Results · Model · Configuration**:

- **Results** leads with the run headline (the "Run status" `Ledger` with Execution and Criteria; see [Scientific states](Scientific-states.md)), then the complete "Outputs" table. Each output appears once; no arbitrary subset is promoted. The table has Output, Value and Units columns. An unavailable value reads "not computed" with its reason in the Value cell.
- **Model** shows the model version the run used, in the canonical model view, read-only.
- **Configuration** shows the configuration the run used in the shared Inputs and provenance, Criteria, Assumptions order, read-only, with its own "Record details" beside its read-only tag.
- **Run files and diagnostics** is a disclosure beneath Results. Evidence is shown beside the model or configuration assertion it supports; there is no run Evidence tab.

Run content stays readable from stored records even when the modeling service is unavailable.

## Evidence

Evidence titles and **View evidence** actions use the same compact presentation beside each assertion. The source library remains available to authoring and existing direct links, but is not a study tab.

## Agent activity

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

Below 1150px the page gutters narrow and the model heading wraps. Below 1050px the workbench stacks (canvas, then details) and each part scrolls inside its own box. Below 600px rows, filters and action groups wrap to a single column and the wordmark shrinks to `subheading` size. Tables scroll inside their own box; the page never scrolls sideways. The primary action and header actions stay reachable without horizontal scrolling at genuine 200% zoom in both themes. Controls switch to `control-floor` on touch devices.


## Continuous modeling approach

Preserve the entire saved question and its line breaks. Follow it with the study answer and expandable method rows. Cases have their own study tab. Hairlines and token spacing
separate rows; avoid a second method map, chapter tabs or an assumptions tab.

Each method shows its purpose and implementation state before expansion. Expanded
content explains the calculation and basis, dependencies and remaining work; linked
model versions open the canonical view from **View model details** at the bottom-right
of the full expanded method, after its evidence and assumptions. Each case keeps all configuration and run
links, with no implicit latest-run selection. Scientific interpretations require an
explicit persisted basis. Execution and criteria stay in supporting details; exports preserve full numerical precision. Limits and assumption editing remain at their existing owners.
