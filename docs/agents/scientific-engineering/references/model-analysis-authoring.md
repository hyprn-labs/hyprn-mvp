# Model and analysis authoring

Read when creating or revising a model or analysis. Follow the connected client's
live schemas; page labels below describe the current UI, not additional API fields.
“Analysis details” in earlier guidance means the analysis's `description` and saved
settings. There is no separate Analysis details primitive.

## Put each explanation at its useful level

| UI location | Content and owner | Appropriate detail |
|---|---|---|
| Study brief | Question, criteria, global assumptions and limits | The decision and scope the work must address, including unanswered parts. |
| Models → Diagram → Component | Component name; `component_details[]` in model explanation content stores the instance description and limits | What this transformation represents, its local governing relation and applicability. Keep adopted conditions in scoped assumptions and cite their evidence. |
| Component → Python | Definition source and declared function interface | The actual implementation. Document non-obvious conventions and algorithm choices; do not hide scenario inputs or investigation settings in code. |
| Component → Quantities | Quantity definitions and units | Physical meaning, sign and reference conventions. Definitions do not assign configuration values or duplicate source code. |
| Models → Model explanation → What the model represents | `represents` | System boundary, intended use, fidelity and important exclusions. |
| Model explanation → Basis and reasoning | `basis` | Why the governing relations and simplifying assumptions suit that system and domain; consequential evidence and limitations. |
| Model explanation → Calculation logic | `calculation_logic` | End-to-end input-to-output sequence, connections, intermediate quantities and supported coupling/iteration. Explain what the actual assembled model computes. |
| Model explanation → Component explanations | `components[]` | Each component's role in this assembly: what it receives, what it supplies and why the connection matters. Add only useful context beyond the component's local explanation. |
| Experiments → Analyses → Description | Analysis `description` | Purpose of this investigation, what varies and stays fixed, why the selected conditions and checks answer the question, and why numerical error limits are adequate. |
| Analysis settings | Members, sampled `design`, `estimate_plan`, exact model/brief pins and criterion bindings | Reproducible configuration choices, ranges, sampling method/counts/seed and output error limits. The prose explains these choices; it is not a second settings table. |
| Results / Surrogate validation | Frozen runs and assessed estimate | Calculated values, execution failures, criterion outcomes, sample use and measured numerical agreement. |
| Study answer | Interpretation and conclusion with exact references | What the results imply for the question, under which conditions, and what remains uncertain. |

Scale prose to complexity: a one-component model may need only a short model-level
sequence and no additional component summary. Do not invent interactions to fill a
section. A multi-component model needs the connection logic, not a pasted list of
component descriptions. Equations, dimensional conventions and physical domain
limits belong with the model even when numerical; sampling budgets, surrogate error
limits and observed check results belong with the analysis.

Local component documentation (`component_details[]`) and assembly-role explanations
(`components[]`) are distinct. Legacy annotations are read only as the fallback when
no local documentation exists. Use `component_details` for new local descriptions
and limits; do not duplicate either in an annotation. Assumptions stay in scoped
model assumptions with their evidence. Read both back when both are relevant.
Resolve contradictory current prose at its owner within the requested revision.
Do not duplicate assumptions or claim that changing prose changes executable code.

## Create a model before planning its investigations

The New model dialog supplies a name and an empty model or an ordinary example.
This creates a draft scaffold, not a scientifically complete model. Example code
and values are not an endorsed engineering basis.

Give each quantity a readable human name; keep its Python identifier in `code_symbol`.
Do not use a code symbol as the display label when a clear engineering name exists.
Read the saved names back alongside meanings and units.

Author the component definitions, quantities, source, connections, scoped assumptions
and local explanations. Inspect source as text and use supported static validation.
Then explain the assembled model and save an exact model version. Model persistence
and explanation persistence are separate: save/read back the explanation for the
intended exact model version using the current explanation workflow. A saved draft
does not establish that an immutable version has its explanation.

For monetary quantities, first save the model explanation with each exact quantity,
catalogue expression, price year, economic basis and evidence. The catalogue determines
currency, scale and denominator; do not infer conversions or use dimensionless money.

Configuration and analysis creation require the intended saved model version.
Check the selected version; never choose “latest” simply to enable creation.
An already saved explanation cannot be overwritten. Preserve historical content;
do not create replacement model versions solely to clean up earlier prose.

## Create an analysis with a declared plan

Start from the selected saved model in Experiments → Analyses → New analysis.
Give the investigation a useful name and a concise description. Although Description
is optional in the UI, supply the rationale needed to understand a nontrivial choice.
Do not report planned checks as completed.

Choose the creation path deliberately:

- **Select configurations:** choose the exact saved configurations relevant to this
  investigation. Check all free inputs, provenance and model compatibility. This is
  a hand-picked comparison, not a sampled domain or an interpolation guarantee.
- **Generate samples:** declare every independent free input as a fixed value or a
  range with units, bounds and an optional justified step. Connected inputs are
  supplied by the graph. New creation leaves values blank; neither zero nor an
  unrelated configuration is a default. The UI prepares its reference configuration
  and generated members on save. For agent tools, follow the live sample schema and
  supply the required exact reference configuration; do not invent a direct-values
  tool shape from the UI.

Justify fixed values and ranges from the brief, evidence or an explicit exploration
assumption. The UI's generated “user-declared” provenance records an entry, not a
scientific source. Use available configuration provenance/evidence fields and explain
the range rationale in the analysis; do not imply that a typed value was measured.
A preparation anchor is not necessarily the nominal operating point.

For sampling, select the method, training count, validation pool count and seed
before evaluation. UI defaults are numerical suggestions, not scientific choices.
Use [Joint answer exploration](joint-exploration.md) for boundary coverage, budgets
and publication requirements. Keep requested validation-pool size distinct from
the independent validation count: the first held-out point selects the method and
the rest independently assess it. For example, a pool of 16 is 1 selection plus
15 independent validation points, not an unexplained missing result. Read
`get_surrogate.sample_roles` and the per-output assessed/unavailable metrics.

When estimates are needed, enable **Estimate between calculated points** and select
the outputs and both error limits at creation. Save these in `estimate_plan` before
launching; do not wait for observed errors to choose tolerances. Absolute limits use
the output unit; the UI relative entry is percent, while the API stores a fraction
(0.2% is 0.002). Blank differs from explicit zero. The allowance is absolute limit
plus relative fraction times the magnitude of the calculated output. Distinguish
this numerical allowance from a physical requirement, solver tolerance or measurement
uncertainty. Explain its decision relevance in Description.

Calculation-only investigations use no estimate plan. The current hand-picked
creation UI has no estimate controls; do not promise interpolation from that path.
The analysis pins a brief and may suggest criterion bindings automatically. Inspect
the saved bindings by physical meaning, unit and intended output; a suggested match
is not a scientific review. Before launching, bind every criterion this investigation
is intended to assess, including an exploration analysis used in the answer. Do not
require unrelated criteria on investigations with another purpose. Keep a missing or
unsuitable binding explicit; do not discover it only during answer publication.

## Saving, launching and reading are different steps

**Save analysis** stores a version (and, for sampling, generates configurations).
It does not establish successful model runs or a validated surrogate. Reconcile a
pending, failed or uncertain sampling operation before continuing or retrying.

Launch the saved version once through the supported lifecycle. It reuses pinned
compatible runs, calculates missing points, and, when an estimate plan exists,
builds and validates the estimate automatically. Follow the returned operation;
do not separately fit a managed analysis or relaunch it to replace a failure.
Use the current public capability/schema discovery if this lifecycle is unavailable.

The reader separates Description, Results and Surrogate validation; **Analysis
settings** opens the saved inputs, sampling settings and error limits read-only.
**Create new version** is the path for revised settings, within the same analysis
identity when it replaces/refines that investigation. A separate investigation
needs its own identity. Do not rewrite existing studies for presentation cleanup.

Before handoff, read back the model/explanation pins, configuration membership,
description, structured plan and criterion bindings. After execution, check run
states, every requested output, actual sample partition and each error assessment.
An estimate passing its checks is numerical agreement with that model, not evidence
that the model is physically valid. Publish only the exact prepared basis required
by the answer workflow; keep unresolved parts explicit.
