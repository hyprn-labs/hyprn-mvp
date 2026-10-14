# Names and identities in the interface

How the interface names domain records. This file is the single source for reader-facing names. Domain meanings follow the glossary in `CONTEXT.md`. These are presentation rules only: wire names, stored data and exported record formats never change because of them.

| Concept | Primary presentation | Exact identity and context |
|---|---|---|
| Study, current model, configuration | Authored name in interface type, unchanged | Full ID in Record details; a short ID only where needed to tell records apart |
| Component instance | Its name in the graph, search, lists and the details panel | An instance is one use of a definition version. Duplicate names remain distinct; identity is never inferred from text |
| Component definition | Definition name in the component-version editor | Definition version ID in monospace, explicitly labelled; updating one instance never silently updates its peers |
| Quantity | Case-sensitive code symbol in monospace, with its descriptive name alongside when different | The port ID identifies the quantity inside the exact instance and version; neither replaces the symbol for the reader |
| Model version | "Model version <short ID>" with the "Read-only model version" record bar | Saved model versions keep no model name, so the heading never borrows the mutable draft name or invents numbered versions |
| Mutable model | Authored name plus "Draft · saved" or "Unsaved local edits" | Unsaved local changes differ from the saved draft; neither is a saved model version |
| Configuration | Authored name plus "Saved · read-only"; model version as secondary context | Configuration version, model version and run are separate identities |
| Run | Name from the configuration version it ran, plus the short run ID | Full run ID in the record bar and Record details. A run never borrows today's configuration, model or evidence name; a missing name falls back to "Run" and the short ID |
| Assumption | The statement, with its attached evidence | One concept everywhere; the interface has no "notes", "component notes", "definition notes" or "configuration notes" |
| Evidence | Its content and title first | Evidence version ID, typed scope and references in Record details; a missing scope reads "No scope." there and is never inferred |

## Typography of names

Human-readable text uses interface type; symbols, IDs, hashes and numerical readouts use monospace. Table body styles never uppercase names. Technical IDs are secondary, labelled and copyable; abbreviated IDs are display-only, never request identities. Historical content always comes from the stored record, never from current names.

## Model version selector

The selector lists `<short ID> (draft)` for the draft and `<short ID> (read-only)` for each saved version, without repeating the model name. If the current draft's token has not been read yet, the draft entry says `Current (draft)` rather than borrowing an old token. Secondary model actions live in the labelled "Model actions" menu in the model header.

## Configurations and their versions

Lists distinguish a configuration from its saved versions ("Configuration version", "Version <short ID> · read-only", "N saved versions", "All saved versions"), and every version stays inspectable. Counts group versions by configuration identity, never by name. History never shows the current head's name in place of the name a version had.

## Outcomes

Execution and criteria summaries are separate. "Recorded" describes storage and never means a successful execution or a met criterion; "Execution recorded" is only the run submission state. Criteria summaries always read `N of M not met`, `N of M not evaluated` or `M of M met`; the outcome of each criterion stays with the configuration version the run used. Overview reads the details of at most the five runs it displays; a missing or failed read says the status is unavailable and never implies success. Outcome words follow `Scientific-states.md` exactly and are never merged.

## Plain-language rules

1. **Say what the reader can see or do.** Implementation words do not appear in reader text: "retained", "exact", "recorded" (as an adjective for stored content), "attested", "frozen", "digest", "snapshot" for a saved version, "worker", "public API", and "package" outside a method package. Use the plain word ("saved", "this run's", "full precision", "SHA-256", "calculation environment", "record export") or drop the qualifier.
2. **Domain names are kept.** The dialog titles "Run record", "Configuration record", "Model version record", "Approach record", "Evidence record" and "Earlier work record", and the action "Record details", name records and stay.
3. **Version, not revision, for saved states.** A saved, immutable state is a version (model version, configuration version, approach version, evidence version). Revision names only the edit-concurrency marker ("Review current revision", "Refresh study revision", "Model draft revision"). Wire fields such as `configuration_revision_id` keep their names.
4. **Record format, not version, for a stored shape.** A record the application cannot read "uses a record format this application cannot display". Older formats without a field say so ("Model versions saved in this older format have no assumptions.").
5. **Empty authored fields.** An editable item says "No … yet" ("No description yet."). A saved, read-only version says "No …" ("No description.", "No study question", "No definition"). Method and case prose fields say "… not described" ("Inputs not described", not "No inputs"), so an empty field never reads as a scientific claim.
6. **Unavailable is never substituted.** "This run's model version can't be shown. The current model is not shown in its place." The same pattern applies to the configuration.
7. **Identities.** Hashes are labelled "SHA-256" everywhere, never "digest" or "SHA256". Full IDs stay in Record details.

Any change to a reader-facing name is made in this file together with the interface change.

## Reader-facing names

| Concept | Reader-facing name | Not in reader text |
|---|---|---|
| Method package | "package", the only use of the word | "model package", "inspection package", "package" for exports |
| Model and data export | "Export model and data" opens the portable model, diagram, quantities CSV and source downloads | an unqualified "Export" action |
| Portable model record (model import and export) | "Download portable model record", "Portable model record file", "Choose a HYPRN MVP portable model record (.json)." | "model package" |
| Computational record export | Dialog "Export computational record"; actions "Create record export", "Download record export"; section "Computational record export"; "Record export SHA-256", "Record export size (bytes)", "Record export size limit"; "No record export was created." / "No record export was downloaded." | "Inspection package", "Create package", "Download package", an unqualified "export" for this archive |
| Comparison (model version, configuration version or current draft) | "Compare", "Read comparison target", region "Comparison", "Right side identity", "Uses the loaded model; unsaved edits are excluded." | "snapshot" |
| Criterion evaluation | "Criterion evaluator", "criterion evaluation" ("Display rounding never changes criterion evaluation or exported data.") | "assessment" for a threshold check. "Assessment" stays for the scientific interpretation ("No study answer has been assessed.") |
| Run status ledger (accessible name) | "Run status" | "Scientific outcomes" |
| Run outputs | "Outputs"; table "Output values"; dialog and action "Full-precision values"; "Values at full precision."; tooltip "Full precision: …" | "Recorded outputs", "Exact values", "Exact recorded values" |
| Run files | "Run files" (table "Run files table"); "This run file is unavailable."; "Read-only run file"; "Execution diagnostics" | "Retained files", "retained artifact" |
| Run history intro | "Newest first. Failed and incomplete runs stay listed." | "Recorded calculations, newest first." with a second "every attempt" note |
| Run record bar | "Run record · Read-only" | "Read-only run record" with a line about retained inputs |
| Modified-run availability | "Create modified run"; "Checking whether this run can be modified…"; "Available once the run has finished." | "Checking retained configuration…", "A complete retained terminal run is required." |
| Run case link | "View case" | "View case context" |
| Evidence used by a run in an older format | "Evidence used by this run" | "Supporting evidence" |
| Configuration context evidence | "Context evidence" | "Supporting evidence" |
| Earlier work (the approach's prior basis) | "Earlier work" everywhere: the ⋯ menu, the section, "Add earlier work", "View earlier work", "Earlier work record", "Earlier record" | "Prior scientific basis", "prior basis" |
| Study limits prose | Shown under "Limits" alongside structured limits, without a format label | "Earlier limits text", "Recorded limitations (legacy text)" |
| Approach version label in Study details | "Current approach draft", "Saved approach vN", "Current saved approach vN" | "Retained with approach vN" |
| Approach link of a configuration | "Linked modeling approach"; "No modeling approach is linked." | "Recorded modeling approach", "No modeling approach was recorded." |
| Evidence library intro | "Sources and observations used in this study." | "Saved notes and references" |
| Evidence index partial state | "N of M groups loaded." … "Groups that could not be loaded are left out; they are not shown as having no assumptions." | "owners loaded" |
| Quantities CSV | "Quantities CSV" | "Variables CSV" |
| Unit with an empty stored spelling | "Dimensionless" as a label or choice; "dimensionless" in a unit column beside a value (an empty unit means dimensionless) | a blank |
| Calculation environment | "The isolated calculation environment needs verification." | "Worker isolation" |
| Study description | Editable study: "No description yet."; saved configuration: "No description." | "Add a description of what you want to investigate." as an empty state |
| Study question details | "See more details" | "Question in detail", "Study conditions & limits" |
| Overview lists | "View all runs", "View all configurations" (specific, so two buttons on one page have distinct names) | a bare "View all" |
| Study archive | "Archive" (row action), "Archive study" (dialog), "Archived" (Home view and tag), "Restore" (row action in Archived). Archiving hides a study from Home for everyone and deletes nothing | "Delete", "Unarchive" |
| Model version (canonical view) | "Model version <short ID>"; record bar "Read-only model version"; "Open model version" and "View model version" open it | "Exact model version", "Source and ports are retained for this version.", "Inspect recorded model" |
| Canvas footer | "1 component · 1 connection", "N components · M connections" (singular and plural) | a fixed plural |
| Agent activity (the study's page of what assistants did for the signed-in user) | "Agent activity" for the study-heading entry, the page heading and the breadcrumb (`/ <Study> / Agent activity`); it is not a study tab | "Journal", "Agent log", "Audit log", "Proposals" |
| Agents with current access to the study | Panel "Agent access" | "Tokens", "Delegations" |
| Ending an agent's access | Action "Revoke access" (accessible name "Revoke access for {agent}"); dialog "Revoke access for {agent}?" | "Delete token", "Stop agent", "Cancel runs" (revoking is not run cancellation) |
| Outcome of an agent's call | "Completed", "In progress", "Outcome uncertain", "Refused", "Failed". "Completed" is the stored outcome of the call only, never a run's execution or criteria | "Succeeded", "Approved", "Confirmed", "Error" for a refusal |
| Agent activity views | "Changes", "All calls" (group label "Activity view") | "Writes", "Reads", "Log" |
| Who acted through an assistant | "{agent} for {user}", with the hidden prefix "Assistant: " (`AttributionChip`); Record details rows "Saved by", "Submitted by", "Changed by"; a review an assistant recorded adds "Recorded by an assistant" | "{user} via {agent}", "Confirmed by", "Approved by", a combined name parsed from text |
| Record details of one agent call | Dialog "Agent action record" (trigger "Record details") | "Journal entry", "Audit record" |
| Records an agent call created or changed | "Open study", "View study description", "View evidence", "Open model", "Open model version <short ID>", "View modeling approach", "View approach vN", "View configuration", "Open run <short run ID>" | a bare "Open" or "View", "Go to record" |

## Fixed labels

- Study tabs: Overview, Models, Configurations, Runs, Evidence.
- Run tabs: Results, Model, Configuration, Evidence.
- Model views: Graph, XDSM.
- Footer link: "Third-party software notices".

Study details uses "Current approach" for the approach scope and omits empty optional prose sections in read-only views. Assumption role fields, citation relationship codes and evidence version IDs stay out of this brief; proposed conditions remain labelled "Proposed condition", conflicting evidence stays visibly labelled "Conflicting evidence", and citation relationships and version IDs remain available when opening the evidence. Authorship claims are labelled as supplied and unverified.

The model inspector labels a linked step's shared transformation "Method context" and its purpose/rationale "Why this method". Exact approach and model pins remain in "Method record"; a component-level computation description is never inferred from a shared step.
