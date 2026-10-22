# Analysis reader

Approved 2026-10-19. This supersedes the analysis-record layout in Calculations.md;
creation, immutable versions, selection/sampling and scientific checks are unchanged.

An analysis is one purposeful investigation of one model version. Its record leads
with a PageHeader: name, RecordDetails and saved state, optional description, one
version selector, Analysis settings. Do not repeat version IDs, brief pins or a
second Analysis details heading. Exact pins remain in RecordDetails.

The two main panels are **Results** and, for sampled analyses, **Surrogate**.
No separate configuration-card inventory, criterion-binding table or Design panel.
The global Configurations and Runs collections retain their independent purpose.

Results connects each member configuration with its explicit displayed run and
outputs in one DataTable. Generated samples use Point N and Training/Validation roles;
never reuse the preparation anchor's name as every sample's identity. Authored
configuration names remain. Input and output labels include component names only
when needed to disambiguate quantities. Requirements accompany output headers;
unbound criteria stay visibly unresolved. Column selection includes all independent
inputs and outputs. Fixed inputs remain inspectable in columns and the input-domain
reader. Domain rationale remains authored data, never study-specific UI prose.

Use ten member rows per page and bounded reads of those records. The shared
comparison-table recipe keeps horizontal overflow local at narrow widths. Each
cell uses hf-result-cell: token-based compact spacing between values, status and
actions. Actions use shared Buttons; no screen-level padding or alignment rules.

Each row links to its configuration and displayed run. Multiple loaded runs have an
explicit selector; changing it changes displayed values and the run link together.
Never silently replace the selected run with a later one. Shared executionStatus
reads actual backend lifecycle/result facts; recording is not execution success.
Failures, unresolved evaluations and unavailable values remain explicit.

The results table has one member pagination control. It automatically exhausts the
filtered runs of its visible members with bounded concurrency; it never asks the user
to load run pages separately. Output columns precede execution, surrogate role and
optional input columns. Point/configuration names and execution statuses remain passive facts.
`RecordNavigation` places a separately named inclined-arrow control beside each,
opening the exact configuration or selected run.
No stacked Open configuration / Open run buttons. Training/Validation is a separate
role column, not a substitute for execution state or calculated result basis.

Surrogate shows training/validation record counts, per-output assessment, largest independent
validation error and the saved combined absolute/relative error target. Never call all
referenced records fitting data. Method and independent-validation metrics are secondary
under Disclosure. Groups retain separate assessment rows; one group's outcome never
substitutes for another's. Passing checks is agreement with the model, not physical
validity. Failed or partially usable surrogates remain visible. Build surrogate uses the
existing explicit operation and unchanged error targets; viewing the page never fits.

Read-only Analysis settings, explicit Create new version and exact saved pins remain
as specified in Calculations.md and PageHeader.md. All prose, quantities, names, ranges,
values and scientific outcomes come from public study/model/configuration/run/estimate
records. No special case for the demonstration study is permitted.

The surrogate panel explains its purpose: fast estimates between calculated points.
Build and validate asks for output-specific absolute limits (output units) and relative
limits (percent); both are explicit, and blank is never converted to zero. The API
still uses a relative fraction, with a deliberate percent conversion at this UI boundary.
Method selection uses the first held-out point; independent validation uses the remainder.


## Analysis execution (2026-10-20)

Analysis settings owns estimation intent, chosen outputs and explicit absolute/percent
error fields in the same compact sunken Panel recipe as sampling. Saved fields are disabled;
Create new version is the only path to changing them. A saved analysis has one Launch analysis
action, then measured calculation progress, Fitting and validating surrogate, or its final
Completed/Failed/Needs review state. Do not expose a manual fit action on the result reader.
The surrogate panel reads immutable metrics and per-output failures. Refreshing/polling a
status never submits a run or fit. Historical versions retain their results and offer the
existing explicit version action to adopt the new lifecycle.
