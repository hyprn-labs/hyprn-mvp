# Analyses

The current analysis record layout is specified in [Analysis reader](AnalysisResults.md).
It supersedes the separate Design, Configurations, Criterion bindings and Runs panels below.

Approved 2026-10-17; calculations added 2026-10-18 (ADR-0009, ADR-0010). The study rail
contains Overview, Models and Experiments. Experiments opens on its Analyses tab, followed
by the Configurations and Runs readers; URLs and exact record links remain valid. The study answer links directly to configurations and recorded runs; there is no Case primitive.

Models and Experiments share the ModelVersionSelect vocabulary and Select recipe.
Models includes Current draft; Experiments includes saved versions only. A model
selector scopes the version list. Switching Experiments tabs retains model and
version; changing either selection goes through the existing unsaved-change guard.
The selected saved pin is encoded in list URLs and restored after sign-in/reload.

Entering Experiments from a saved model preserves its pin. Entering from a draft
uses that model's latest saved version, visibly selected. With no saved version,
show “Save a model version to prepare calculations” and View model; New configuration
is disabled. Creating a configuration in this section uses the selected saved
version and never implicitly saves the current draft.

Configuration lists filter by model ID and model-version ID. Run lists join each
run's configuration-version ID to those exact configurations. Names and ordering
never determine membership. Opening a configuration or run selects its own pin;
returning to Models opens that saved version. A mutable model-service failure may
show versions from retained configurations with an explicit unavailable-list notice.
A failed version lookup never silently substitutes another pin.

Lists load on demand. Configurations reads a bounded page of summary metadata;
full inputs, evidence and model bytes load only when a configuration is opened.
Runs requests only the selected model/version, newest first, with an explicit Load
more control. Filters explicitly search received records. Overview and hidden run panels do not
fetch run history. A model/version switch resets list pagination; study access loss
clears retained list rows and fences late responses. No list read computes outputs.

The scope controls carry visible Model and Model version labels above their shared
Select surfaces. CalculationNavigation owns wrapping and the gap below the tab bar.
Do not repeat the active Configurations tab as a content heading. CollectionToolbar
places the shared collection count and New configuration action inside the list panel, with
shared padding and spacing; commands never sit against the tabs' separator.

## Analyses tab

The tab lists the calculations whose latest version uses the selected model version, each as
a ResourceCard (name; version, configuration count and bound criteria) with Open calculation.
**New analysis** is the only collection creation action. Its ActionDialog uses the shared
choice-card recipe for **Select configurations** and **Generate samples**. Selection
uses a bounded shared checklist for one or more saved configurations. Generation starts with the selected saved model’s independent inputs: each has a
Fixed value / Range select and explicit value or minimum/maximum/optional step fields.
New inputs start blank; there is no configuration selector or prefill. Training and check counts
apply across the joint input space. These are preparation choices,
not new domain types. Names, descriptions and selections survive switching and cancellation.

Name is followed immediately by the visible optional Description field, then the
configuration preparation choice. Editable fields use FormField and hf-form-section;
no form fields are hidden behind disclosures. Analysis creation/revision contains no
criteria-mapping section. Criteria stay in the brief and saved analysis readers. Existing
bindings are preserved on revision; new hand-picked analyses retain the existing unique
name/exact-unit matching rule, leaving ambiguous matches unbound.
Generated samples show input values/ranges and optional steps. A separate sunken Panel
labelled Sampling settings contains the method, training points, check points and seed,
using the same header divider and FormField spacing as input cards. No total-points field
or repeated count summary is shown. Revising a sampled analysis restores its own
inputs and ranges, retaining exact range provenance when unchanged. Changed/new ranges
record the explicit user declaration without inheriting unrelated evidence. No separate
justification field is presented. Each input uses a shared sunken Panel with a quantity/unit header, separated from its
controls by the standard header divider. The surrounding hf-form-stack supplies the gap
between cards; FormField supplies label spacing. No study-specific CSS. Duplicate
quantity names include their component to remain distinguishable. Preparation saves explicit
inputs through the public configuration API; it never runs the model. Training and check counts are edited independently. No Cartesian product or per-input
count is implied, and backend assessment requirements remain binding.
Submission preserves the existing API and polling lifecycle; mode switching is disabled while
an operation is pending. Completion closes the one dialog and opens the saved analysis.
Use shared hf-form-section/hf-form-stack spacing and hf-choice-grid/hf-choice-card controls;
selected cards have a border and aria-pressed as well as the neutral selected background.

An analysis record is one exact version: PageHeader with Return to all calculations, the
calculation VersionSelect and New version; then three titled panels. Configurations lists the
member versions with Open configuration and a Reference tag where marked. Criterion bindings
is a DataTable of criterion, requirement and output, with an advisory "Not bound" tag. Runs is
a DataTable with one column per brief criterion: Met (ok), Not met (alarm), Measured (inert)
with the value and its units, or Not evaluated (advisory) with its reason. An unbound
criterion is never met; a missing value reads "not computed". Runs load 20 at a time.

## Reference marks

Configuration rows carry Mark as reference / Clear reference mark beside Open configuration,
and an inert Reference tag while marked. A mark labels a baseline for its model; setting or
clearing it never changes or pins the configuration.

## Runs and execution (2026-10-19)

The Runs collection uses the same ResourceCard/CollectionToolbar recipe as Analyses and
Configurations. Its card status is submission metadata; only the opened run's verified
execution record establishes completion. Shared collection filters wrap without changing
card/action alignment. No duplicate Run history heading beneath the active Runs tab.

An opened run separates Execution facts from Results, Model and Configuration. `MetricGrid`
shows known status, operation, measured wall duration and time limit without a criteria
placeholder. `Execution details` keeps files/source mapping available for diagnosis. See
Scientific states for the separation of execution, future solver convergence, optimization
termination and study criteria.

OpenMDAO reference: [DriverResult](https://openmdao.org/newdocs/versions/latest/_srcdocs/packages/core/driver.html)
records runtime, iteration/model/derivative evaluation counts and driver termination;
[solver recording](https://openmdao.org/newdocs/versions/latest/features/recording/solver_recording.html)
records solver errors and residuals. These inform the future recording contract, not fields
invented by the current UI. No numerical runtime or saved result format changes in this pass.

The enclosing workspace is named **Experiments**; Analyses remains its first tab, beside
Configurations and Runs. Model/version controls scope all three.


An analysis references configurations and runs; it does not own them exclusively.
The top-level Configurations and Runs tabs always retain their selected model/version
scope, including records not referenced by an analysis. Opening an analysis shows
its members only. New analysis starts a complementary investigation; Revise analysis
saves a successor for the same purpose. The answer editor warns about conflicting
versions of one analysis/model; publication validates them in the backend.

## Single settings entry

An open analysis has one **Analysis settings** action. Reuse the creation dialog's
Name, optional Description and configuration-source choices, initially showing the
saved design (selected configurations or generated samples). Both paths remain
editable within that dialog; switching paths preserves their entered values. Existing
version pins, saved bindings, sampling reuse and save/operation boundaries stay intact.
Do not place separate revision and sampling actions in the record header.

Saved Analysis settings are read-only and display the exact selected version, never
substituting the latest version. The shared saved-record badge makes that state explicit.
Only the latest version offers **Create new version**, which enables a separate unsaved
revision in the same dialog. Saving retains the original version and exact command pins.
Historical versions remain inspectable without revision controls. Closing an idle revision
and reopening restores the saved settings; an in-flight sampling operation remains visible.

## Collection coverage

Analyses, configuration versions, runs, analysis version history and estimates use [Collections](Collections.md). Model-version scope is a separate context line. Exact saved member counts and scientific fit/run state remain independent from pagination.
