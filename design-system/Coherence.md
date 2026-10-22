# Coherent scientific records and actions

Shared rules for how records and their actions are composed across screens. They apply to every page alongside [Layouts](Layouts.md) and the component notes.

1. **Show scientific meaning first.** Lead with human-readable context, quantities, claims and sources. Raw kind, schema or scope-version fields are not ordinary product content. Exact identities and serialized records live in secondary Record details.
2. **One canonical home per entity.** Each record type has one home and one presentation, reused wherever it appears: the same model view in Models, in a run, from a configuration and from the modeling approach; the same configuration composition for drafts, saved versions and the configuration a run used.
3. **One evidence action per supported item.** Use **View evidence (n)** to open all attached evidence in the shared details panel. Titles, notes, references, relationships and editable citation actions appear there together. Count distinct evidence versions, retain unavailable attachments and exact pins, and never imply passage-specific support from an answer-wide basis.
4. **Make structured requirements look structured.** Criteria use the shared numbered `CriterionRecord`: quantity, comparison in words, threshold, units and applicable tolerances. Evidence is supporting content, never more prominent than the quantity it supports. Assessed outcomes come only from a run's stored results; criteria are not optimizer constraints.
5. **Keep composition stable across lifecycle states.** Configuration content is always Context, Inputs, Criteria, Assumptions. Drafts use dedicated edit actions; saved configurations and the configuration kept with a run use the same read-only structure with their stored data.
6. **Put actions beside their resource.** Run actions stay in the run heading across all run tabs. Every record uses the shared [RecordDetails](components/RecordDetails.md) metadata row immediately below its own title, separate from edit/export/run action groups. Dialog titles name the resource ("Run record", "Configuration record"). No duplicate actions at the bottom of a page and no ambiguous nested disclosures.
7. **Inheritance is a starting point, not a second comparison screen.** A modified run starts from one editable copy of its configuration's recorded context. Saving creates a separate immutable configuration version. The study and the source run are never rewritten, and inherited text is never replaced with today's study context.
8. **One assumption concept.** An assumption is a statement with its attached evidence, owned by the approach, model, component or configuration it qualifies. There are no separate notes in the interface.
9. **Protect the engineer's editing flow.** Keep local changes through stale responses and uncertain command outcomes. Discard restores the draft's inherited baseline. Populated fields keep stable accessible names. Dialog focus restoration never steals focus from the next control. Support keyboard use, long content, both themes and genuine 200% zoom.

Use the shared components and tokens only. No scientific state persists only in the browser, no record has two authorities, no historical context is inferred, and no unavailable output is shown as zero. A stored format the editor cannot change states that editing limitation. A successful execution does not by itself establish scientific validity.

## Collection coverage

[Collections](components/Collections.md) owns typed collection counts, completeness, filtering, loading, paging and retry. Received rows never imply an unknown total.

## Version identity and saved readers

`VersionSelect` owns visible version labels on every page. Use the recorded version
number; never format a UUID as a version number or number a paginated/reordered list.
For models, a complete unbranched parent chain may establish the ordinal. Missing,
cyclic or branching ancestry retains `Saved · <identifier>` with the full ID available
in record details. The exact ID remains the selected value and pin in every case.
An externally labelled selector opts out of its own visible caption to avoid nesting labels.
Read-only is a neutral lock, stated once beside the record. Green means a successful
outcome, not persistence. Saved settings use `SavedField` or tables, with the selected
source choice visible; editing begins explicitly with Create new version.

Checkbox/radio captions stay beside their controls in all shared form layouts. Table
column pickers group Outputs before Inputs. Result tables place units in headers,
align numbers and preserve the point column during horizontal scroll. Use one
`TableControls` row above the table, aligned right: Columns, visible range, Previous
and Next. Do not repeat pagination or the range beneath the table. Announce loading
once per table.

Surrogate validation separates training, method-selection and independent-validation
roles. Error limits and pass/fail come from recorded assessments. Small positive error
summaries may show `< 0.001` in the stated unit with the exact value in a tooltip;
never round a nonzero scientific quantity to zero or alter its stored value.

## Context help

Use `HelpButton` for optional explanations beside the relevant heading or labelled
control. Its circular question-mark trigger uses the shared token sizes, a named
accessible dialog, Escape dismissal and focus return. Use the same component in
models, analyses and settings. Keep explanations short and generic; live values,
errors and required instructions stay visible. Do not put help buttons inside a
field label or rely on a hover tooltip as the only explanation.

### Section help and record navigation

Major object sections use `SectionHeader help`, `PageHeader help`, or `SectionHelp`
in a Panel's help slot. Topics and copy live in `ui/src/design/section-help.json`:
brief, answer, exploration, model/explanation/quantities, inputs and provenance,
analysis results/settings, sampling, surrogate limits/validation, run outputs,
assumptions and evidence. Reuse these meanings in embedded and standalone readers.
Keep help outside disabled fieldsets so saved records remain explainable. Do not add
help to version selectors, repeated rows or individual status badges. New major
object sections require a topic; every topic explains the section's purpose and
any distinction needed to interpret it, without copying a study's content.

`RecordNavigation` separates a plain identity or inert status from a named inclined
arrow button. Status never navigates. The arrow has a descriptive accessible name,
keyboard focus and the destination in its tooltip. Data-table cells align vertically
at the middle; prose-specific tables can retain their documented top alignment.

### Opening destinations and readers

Use `OpenLink` for content navigation to a page or a dedicated reader (panel or
dialog). A named link has an underlined label and the shared inclined arrow, always
visible and forming one click/focus target. `RecordDetails` and evidence/source
readers use this same contract. `RecordNavigation` composes a passive fact or status
with an arrow-only `OpenLink`; the fact itself is never interactive. Arrow-only
controls require a descriptive accessible name. Returns use `ReturnLink`, with the
shared back arrow and the named destination.

The inclined arrow means “open”, not “new tab”. Preserve native anchor semantics
for URLs; disclose a new window explicitly when one is requested. Commands (save,
calculate, retry, delete, sorting), editor/confirmation triggers and dismissals use
buttons without link underlining or opening arrows. In-place disclosures use
chevrons. Sidebar navigation, tabs, graph selection, reading contents anchors and
context-help triggers retain their established dedicated patterns.

Render error allowances with `ErrorAllowance`, supplying the saved absolute and relative
limits, unit and explicit reference. It must include its operands: `absolute [unit] + percentage ×
|calculated output|`. A bare sum of a dimensional amount and a percentage is forbidden.
The percentage multiplies a magnitude, so the result has output units. This display
must not change stored tolerances, validation gates or precision.

Agents receive the domain distinctions through `get_playbook("workflow")` and
`hyprn-mvp://playbook/workflow`; the packaged playbook stays the agent authority.

### Analysis reader density

The saved analysis description has a labelled Description panel below identity and above
Results, and the same field in Analysis settings; never put it in the metadata row.
Input ranges and fixed values have one reader there; Results does not repeat it.
Saved sampling uses sunken Panels for Inputs, Sampling settings and Surrogate settings,
with `hf-flow` body spacing and `MetricGrid` for counts and seed. Help shares the state
and version-action row. Labels and values stay paired when a narrow dialog wraps.

Surrogate validation has one row per output (and per group where applicable), containing
assessment, largest absolute error, allowed error, independent validation counts, fitted
method and RMSE. One table owns those facts; no second output table in a disclosure.
Aggregate training/selection/validation counts remain a summary above it. All descriptions,
ranges, counts, methods and numerical results come from saved public records.


### Table reading order and alignment

DataTable owns semantic alignment on every page: text and units left, numerical
values right, and column headings aligned with their values. All cells align
vertically in the middle, including missing results and navigation arrows. Custom
rows use `num`/`missing` on numeric cells just as declarative `numeric` columns do.
Child layouts inherit that alignment rather than spreading a value across the cell.

Use shared column presentations: `label` reserves a readable identity width and
wraps at words; `compact` keeps short categories and statuses intact; `formula`
reserves room for each dimensional term. Numeric values and units stay together.
Tables scroll within their own region when needed; never compress them into word
fragments to fit a narrow screen. Explanations belong in the section's help, not
repeated cells or long headers. Failure reasons must remain visible.

Validation order is output, method, independent point count, maximum error, RMSE,
allowed error and result. Compact ErrorAllowance deliberately separates its two
terms onto two lines, with the reference named and explained in help. Sample-use
counts use labelled MetricGrid entries, never an undifferentiated sentence. Results
put point identity and sample use together, followed by outputs and assessment,
then run navigation and optional input detail; priority outputs remain near the left.

Collection creation actions are trailing actions: right-aligned after read/retry
controls in CollectionStatus and CollectionToolbar, and on the right in PageHeader
even when it wraps. Screens do not reposition New actions individually.

### Answer readers

- Keep the study question visible and put the rest of the saved brief behind See details.
- Saved brief and answer versions use the shared read-only state. Offer an explicit
  successor or Continue draft action; never display a disabled save action on a saved record.
- Comparisons group each alternative and separate output, value, requirement, result and
  source. Show the actual pinned criterion condition. Passive table facts may use RecordNavigation; source citations and explicit View/Open controls use labelled `OpenLink` targets.
- SurrogateValidation owns the same validation facts in analyses and result explanations.
  Keep one shared legend and a per-value origin symbol, without repeated origin words.
- Exploration domain includes fixed and varied independent inputs. Load point identifies
  calculated combinations by coordinates. Display rounding never changes stored values.
- Plot requirement lines require explicit output bindings from the pinned brief and
  analysis, with identical units. Never infer a binding from similar names.
- Major answer sections use shared contextual help. Study-specific reasoning belongs
  to authored records; presentation never adds domain claims.

### Heading and action roles

- Every major card title uses the heading type role (20/28); sections inside it use
  subheading (16/24), and subordinate labels use body type. Shared heading groups
  align help immediately beside the title, independently of version selectors/actions.
- Dialog help belongs in ActionDialog's heading, never floating above its contents.
  Panel help uses its dedicated help slot; actions retain the trailing side.
- Custom DialogFrame editors use SectionHeader at level 2, preserving any heading
  ID used by aria-labelledby. Reuse the relevant section-help topic for quantity,
  assumption, evidence and configuration editors; simple confirmations need no help.
  Header groups and contextual panels keep title/help together and commands separate.
  A SectionHeader directly owning a panel body uses the major-card type role even
  when its semantic level is h3. Nested sections retain the smaller type role.
- Dialog action rows use ActionGroup or the shared actions recipe so buttons wrap
  with a consistent gap. Keep their existing labels, order and action semantics.
- Controls name explicit tasks. Save is a command button; View model and View analysis
  are opening links. View model opens
  the saved model reader in a dialog, with an optional Open model page action.
- Text links include the shared opening arrow (citations, Record details). Use RecordNavigation only
  to add a separate detail arrow beside passive facts such as point names or statuses.
  An arrow never replaces the label of a named link or marks an ordinary command.
- The conclusion owns a panel. Its recommendation row keeps classification, selected
  alternative or evidential limitation distinct from the authored finding. These come
  only from the saved outcome, never from inferred criterion success.
- Grouped comparison tables use one tbody per alternative, spanning identity/source
  cells and a full-width boundary between alternatives. Inner output separators must
  not appear to continue across alternative boundaries.

## Dialog completion actions

Use `DialogActions` for Save, Apply, preview/commit and Cancel/Done actions. The
nearest `DialogFrame` owns one footer at the bottom right, outside the scrolling
content. Nested editors contribute to that footer; nested dialogs own a separate
footer. Row actions and intermediate selections remain beside their content.
Keep actions together with shared spacing and wrapping, never split a save button
into the form and its cancel button into the footer.

Portalled submit buttons explicitly identify their form with `form={formId}`.
Preserve disabled conditions previously inherited from a fieldset. Editors retained
inside hidden mode panels must set `active` on their `DialogActions`; only the
selected mode contributes actions. This composition changes no save, cancellation,
validation, read-only or draft-recovery semantics.


### Modal action order and control rhythm

`DialogActions` declares the committing button in its `primary` slot; Cancel, Done,
Keep editing and other secondary actions remain children. `DialogFrame` renders the
secondary slot first and the primary slot last, in both visual and keyboard order,
regardless of nested editor mounting or mode changes. The primary slot applies the
shared filled primary Button recipe; destructive confirmations retain danger styling.
Never infer the action role from its label or use CSS order to disagree with Tab order.

Stacked labels and controls use `label-gap` exactly once. `VersionSelect`, `FormField`
and the model/version scope selectors share this rhythm, without additional input
margins. Visible tab content starts `space-4` below its separator; retained hidden
panels remain mounted and hidden, without contributing spacing.

### Responsive editing surfaces

Use `FormActions` for inline editor completion and `DialogActions` for modal
completion. Both render secondary/cancel actions before the highlighted primary
commit action in reading and keyboard order, aligned to the trailing edge. Keep
handlers, form ownership and disabled state explicit; presentation does not infer
an action from its label. Wrap action groups without clipping controls.

A dialog body owns its edge padding. A nested form/fieldset's first label must not
add another top margin. Quantity Name/Symbol fields fill two equal columns on wide
screens and one column on narrow screens; full-width definitions do not create
phantom empty columns. Shared pair/triple form grids wrap by available width, with
readable control widths and token gaps. Verify light and dark surfaces at desktop,
720px and 390px; keep long tables locally scrollable and footer actions reachable.

Empty collection toolbars reserve no row or margin. Discard prompts keep their
message on a separate row from spaced Keep editing / Discard actions.

## Import, export and appearance

- Name transfers by their object: **Import model**, **Export model**, **Export computational
  record**. **Refresh model** rereads the current model; it is not a transfer. Keep refresh in
  secondary model actions, including the existing unsaved-changes guard.
- Offer export only with a selected object. Use `TransferSection` to group each purpose with
  one short scope statement and its download buttons. **Reusable model** downloads a portable
  model record; **Current view** offers diagram formats and quantities CSV. Keep exact scope
  and individual source downloads in disclosures. Unsaved edits are excluded from these reads.
- Model import selects a portable model record, previews compatibility/collisions, then imports
  explicitly. The primary step is in the shared footer with Close/Back to its left. Review must
  never execute source. A collision/unsupported record must not say it is ready to import.
- A computational record is an inspection archive, not an importable model or backup. Show
  included computations and blockers up front, context/limits and technical IDs on demand.
  Preserve review, creation and verified download as separate actions.
- Evidence/retained-file downloads remain beside their own record. Do not add empty import or
  export controls to unrelated objects. Reserve **method package** for the future procedure,
  evidence, model assets and checks; current transfers are not labelled packages.
- Dark is the shared default when no valid appearance preference is saved, including sign-in
  and denied storage. An explicit Light choice remains honoured. Settings and initial render
  resolve this through the same function, not separate defaults.
- Nested (h4) help sits beside its heading with the compact heading gap. It is never positioned
  beside the opposite-edge Add/Edit action or on its own line.

## Documentation editors and transfers

- At study, model and component scope, group descriptive content first, scoped
  Assumptions second and Limits third. Use sunken `ReadingSection` containers in
  editors and readers; domain-specific sections follow. Never invent empty claims
  or infer a limit from prose. New component description/limits use explanation
  format 2; existing assumptions retain their owner and evidence.
- `ActionDialog` owns the common completion footer. Cancel is on the left of the
  highlighted save action; Escape and the close icon follow the same local cancel
  handler. A controller decides which local fields to discard. Saved versions stay
  read-only and exact-version reads never substitute the latest explanation.
- Dialog titles use heading type, field labels strong body type, input values
  regular body type. Optional guidance uses `FieldHint` (small, muted, connected
  with `aria-describedby`); failures remain full-size alerts. Do not shrink all
  explanatory paragraphs or turn field contents bold with their label.
- Model export belongs only to Models: a portable model record, or the current
  diagram/quantity view. Individual Python files are already included in the record;
  do not expose a second Source files section or an Export scope inventory.
- Run export uses **Export computational record**, then **Check contents**,
  **Create export**, **Download ZIP**. Required dependency and byte-safety review
  stays real. Keep technical inventory under disclosures, with blockers visible.
  Do not call the inspection archive a method package or promise re-execution.
- Home **Delete** moves a study to **Trash**, after a confirmation naming the study
  and recoverability. Restore uses the existing archive-state owner; do not erase
  authoring records, pretend the records are inaccessible, or offer these actions
  to the agent.
- Conclusion leads with the structured Recommendation, followed by one Evidence
  and reasoning block. A no-recommendation basis remains visible, connected to
  the authored reason. The UI never manufactures scientific justification.

### Evidence reading

The Evidence library and every contextual reader use the same Source → Source excerpt
(with page/location) → Explanation composition in EvidenceReading. Library cards are
already open evidence. Never put View evidence inside them. Brief and answer claims
retain their direct evidence action; assumptions stay at their owner. Record details
is discreet metadata below the owning evidence title. See [Evidence](components/Evidence.md).
