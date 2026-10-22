# Operating on HYPRN primitives

Read before authoring or revising a study. This is a semantic operating guide, not
an alternative API specification. The offered tool schemas and canonical playbook
define the permitted operations. Keep wire names unchanged even
when the UI uses clearer terms such as quantity rather than port.

## Establish the surface

For a delegated client, start with `get_study_overview`, `get_capabilities` and
`get_playbook("workflow")`; load the area guidance when operating there. Inspect
pagination, truncation and missing-source warnings. Read the exact underlying
records for consequential claims rather than relying on a clipped overview.

A capability flag does not grant permission or add a tool to the session. Inspect the
actual exposed catalogue, stage and delegated effects. Never infer capability from
roadmap prose. Read the unit catalogue returned by `get_capabilities` before
model authoring. Use the tool schemas that support quantity definitions; unsupported
units require a limitation or justified reformulation, never a false unit label.
For money, catalogue metadata determines currency, scale and denominator. Save
price year, economic basis and evidence for the exact model quantities in the model
explanation before configurations or analysis. Units do not imply FX or inflation.

Use `get_run_status` or `wait_for_runs` for standalone runs; use
`get_analysis_execution` for launched analyses. Read full results when a value or
failure needs inspection. Keep returned identities and receipt states intact.

When a request is rejected unchanged, repair the indicated fields using the public
schema and discovery results. Do not recreate the study. Save command IDs before
mutations and returned identities immediately afterward; resolve uncertain outcomes
through the command receipt rather than repeating the mutation.

## Primitive map

| Primitive | Agent responsibility | Read-back acceptance |
|---|---|---|
| Study | Preserve the engineering question and requested outcomes; give it a useful name and description. | The scope of the question has not shrunk to match available computations. |
| Study brief | Preserve question, scope, alternatives, criteria, global assumptions and limits. Save an exact version. | Each requested deliverable remains identifiable; no narrower model silently replaces the brief. |
| Model explanation | Explain system purpose, physical basis and connected calculation logic against an exact model version. Component summaries explain their role in this assembly rather than repeating local annotations. | Prose agrees with source and connections; evidence is attached to the claim it supports. Physical assumptions and equations stay here; sampling settings, accuracy targets and observed checks belong to the analysis. |
| Component definition/version | Declare a cohesive transformation, scalar quantities and readable source. Separate physics from economic interpretation where their assumptions differ. | Source, declarations, units and domain restrictions agree. A saved version is exactly the reviewed implementation. |
| Component instance | Select a particular use of a definition and its local assumptions/connections. | Editing shared code updates only the intentionally selected instances; other uses keep their versions. |
| Quantity | State meaning, units, sign, reference condition, aggregation basis and input/output role. | Temperature vs temperature difference, absolute vs gauge pressure, power vs energy, and per-seat vs total are unambiguous. |
| Connection | Transfer the intended producer output to the intended consumer input. | Semantic meaning, reference state and units agree, not just scalar shape. No accidental duplicate free assignment. |
| Evidence version | Preserve a source/observation with locator and scope; distinguish the source from interpretation. | The exact referenced content warrants the particular assertion; contradictory evidence remains discoverable. |
| Assumption | Record an adopted condition at brief, model, component or configuration scope, with relevant evidence. | All affected calculations inherit it, exceptions are explicit, and copies do not drift. |
| Configuration | Pin the model; assign every free input with unit and provenance and explicit numerical choices. Preview before committing. | Preview/read-back has the intended values and links; no silent defaults or source copied indiscriminately across inputs. |
| Analysis | Group configurations of one exact model version and bind brief criteria to outputs. Use `description` for investigation/check rationale, the structured design for sampling settings, and `estimate_plan` for estimation intent and output error limits before launch. Launch calculates missing points and validates requested estimates automatically; use a new version for changed settings. | Description agrees with settings without duplicating their inventory. Numerical checks stay out of model calculation logic. Criteria use the pinned brief; measured results stay in run/estimate records and never replace an answer citation silently. |
| Estimate | Fit and assess against explicit output tolerances and disjoint check points. | Save the exact sampled calculation and original-run identities; failed assessments stay unavailable. |
| Criterion | Express an actual requirement on a computed output with units, threshold and justified tolerance. | Requirement, calculation check and applicability condition are distinguishable; a pass cannot imply all three. |
| Run | Submit once, resolve its authoritative outcome, inspect results and failures. | The run used the intended configuration; all required outputs have values or explicit reasons for absence. |
| Result-linked input | Use the supported binding to a specific run/output when it is scientifically transferable. | Conditions and meaning remain compatible; uncertainty/shared dependencies are not lost by copying a scalar. |
| Study answer | Save comparison cells, interpretation with limits, uncertainties, next analysis and cited basis. | The displayed answer pins its brief and analysis versions, cited runs and evidence, and any assessed estimate. |

For the current pages and creation paths, read
[Model and analysis authoring](model-analysis-authoring.md). The reader now labels
the analysis prose **Description** and opens settings through **Analysis settings**.
This map creates no new product entities. Verification rationale belongs in the
analysis; its numerical cases use ordinary configurations/runs. External benchmark
observations belong in evidence; quantitative validation comparisons can be explicit
model outputs. Interpretation belongs in the answer. If a structured field is absent,
use the appropriate existing prose field without claiming the missing feature exists.

## Building a useful model

Choose component boundaries for coherent physics, independent checks and reuse—not
one component for every arithmetic operator, nor one opaque block for the entire
study. Include quantities that expose balances and assumptions. A mass margin can
be inspected; an unexplained “feasible = 1” cannot establish feasibility.

- Follow the current scalar contract: finite real numbers, explicit units and no
  arrays, boolean quantities or implicit broadcasting. A field model or time series
  does not become a scalar study by hiding an unsupported solver in Python.
- Keep scenario choices, material properties, empirical coefficients and uncertain
  calibration parameters explicit wherever they are free inputs. Mathematical
  identities and exact unit-definition factors may be literal constants when their
  role is documented. Physical constants need an identified convention/source;
  do not quietly make an input invariant because it is convenient to hard-code.
- Read source as text. Saving, importing and static validation do not execute it.
  Use only the accepted numerical modes, imports and execution environment. No
  private WhatsOpt/AiiDA access, external execution or installation of a solver to
  bypass the advertised contract.
- Check dimensions term by term, not just at connections. State unit conventions
  for empirical coefficients, offsets, normalized inputs and logarithm arguments.
  A dimensional logarithm or a formula calibrated in tonnes but fed kilograms can
  survive a syntactically valid API call.
- In a valid domain, return the meaningful physical output and signed residual or
  margin, including a negative margin. For undefined physics or numerical failure,
  do not manufacture a finite output or use zero as a sentinel. Let the supported
  failure path report the problem; qualify downstream conclusions accordingly.
- Do not silently clamp a quantity to hide an invalid domain. Document any physical
  saturation law and its applicability; distinguish it from numerical clipping.

## A coherent record sequence

This sequence follows actual dependencies; it is not a demand for redundant saves.

1. Inspect current records and revisions; settle the next bounded scientific question.
2. Retain source evidence and scoped assumptions. Draft the reasoning and comparison conditions before
   implementation, allowing unresolved/proposed work.
3. Author or revise definitions and the model; inspect declarations, source and
   connections, perform supported static validation, and save the exact model version.
4. Save the model explanation for that exact version; preserve proposed work separately
   from what the source actually calculates. Save the brief version before binding criteria.
5. Preview and save configurations with all free values, provenance and numerical settings.
   Put the configurations in an analysis version and bind brief criteria to its outputs.
6. Launch the saved analysis through `launch_analysis` and monitor
   `get_analysis_execution`; standalone verification uses the offered run tools. Wait on
   existing operation identities; an uncertain receipt requires lookup/reconciliation,
   never an automatic second submission. A readiness failure is not a run.
7. Read the complete results needed for the question and verification. Plan a further
   calculation only when it resolves an identified error, sensitivity or coverage gap.
8. Before publishing interactive results, prepare joint boundary samples and independently
   assessed surrogates following [Joint answer exploration](joint-exploration.md). Call
   `prepare_answer_exploration` for all shown outcomes and require readiness. Verify
   complete-vector predictions; reopening uses automatic renewal, never model reruns.
9. Save the study answer with its exact brief, calculations, runs and passing estimate.
   Read it back; inspect the public UI when requested or relevant and accessible. An API-only
   request does not require browser inspection. Keep an incomplete exploration in draft;
   a noninteractive answer may explicitly leave its exploration basis unassigned.


A changed coefficient generally needs a new configuration; changed equations need
a new model version and corresponding configurations. A changed explanation may
need a new brief or explanation version and deliberately revised answers, not new numerical runs. Inspect
the API's compatibility/pinning requirements: do not claim a run belongs to a newer
brief merely because its numbers are reusable. Explain a reused older result's
role and preserve its original context.

The study answer contains its pinned brief, alternative mappings, comparison cells,
justifications, interpretation, outcome, decisive uncertainties, next analysis and
optional exploration basis. Comparison cells cite an analysis version and run;
the application derives their criterion evaluations from checked results. There is
no case-answer record. Read the exposed schema and expected-revision mechanism.
If the client has no answer writer, report the unsaved answer plainly; do not create
a misleading evidence note instead.

## Input provenance and evidence placement

For each consequential assignment, distinguish its actual authority:

| Origin | What to record | What not to imply |
|---|---|---|
| Brief/design choice | Requirement or case rationale; why this value samples it. | A nearby published reference specified the same choice. |
| Measurement/property | Source, locator, material/conditions, units and relevant uncertainty. | A value at another temperature/composition is directly transferable. |
| Fitted coefficient | Fit data/domain and convention; keep calibration separate from validation. | Calibration accuracy proves predictive accuracy. |
| Judgment/hypothesis | Scientific reason, plausible range and consequence if wrong. | Approval is independent supporting evidence. |
| Numerical choice | Purpose and accuracy/stability check. | A solver tolerance is a physical requirement or measurement uncertainty. |
| Prior result | Exact run/output and supported binding; source and receiving conditions. | Re-typing its value preserves the dependency. |

Use the origin categories the actual client accepts. An authorized owner-API input
may use a provenance statement and evidence-version IDs; delegated writer guidance
may describe a typed source. Do not invent fields to make one surface resemble another.
General context evidence does not support an arbitrary assignment. Evidence for the
standard atmosphere belongs with the method/assumption that uses it; attach it to an
input only if it warrants that input. Recheck citations after changing values.

Before comparing with a supplied reference result, record the target observable,
system boundary, conditions, units/normalization, source locator and precision in
the method's existing reasoning or evidence. Mark values as stated, graph-read,
derived or adopted. If these differ from the authored calculation, explain which
comparison remains meaningful; do not present a contextual ratio as validation.
Use the same check for any reference document, dataset or previous study.

## Worked pattern: pump energy screening

Synthetic arithmetic example, not a measured benchmark or saved HYPRN study.
Question: can a pump meet a duty within a 3 kW shaft-power limit, and what is the
annual electricity expense? Select pressure rise 200 kPa, flow 0.010 m³/s, efficiency
0.80, 4,000 operating hours/year and an illustrative 2026 tariff of
0.20 USD/(kW*h). The tariff is an explicit assumption, not a market observation.

- **Method/model:** a pump-duty component computes hydraulic power `Δp Q` and shaft
  power `Δp Q / η`; an operating-energy component uses shaft power, duration and
  tariff. Connect shaft power. Define the pressure locations and efficiency basis;
  motor losses require another explicit efficiency if the tariff is for electrical
  input rather than shaft energy. Without it, label the expense estimate conditional
  on motor efficiency of one, or leave electrical expense unresolved.
- **Baseline/configuration:** assignments are explicit design choices or supplied
  data, not invented measurements. Set a shaft-power criterion of at most 3,000 W.
  The hand-calculated verification target is 2,000 W hydraulic and 2,500 W shaft
  power. At an explicitly assumed unit motor efficiency, energy is 10,000 kWh/year
  and the conditional annual expense is 2,000 USD on that assumed 2026 basis.
  Save the tariff and expense conventions against their exact model quantities. If its monetary unit is not admitted, leave
  expense unavailable rather than disguising money as dimensionless.
- **Challenge cases:** if flow and pressure may each rise 10% and pump efficiency
  fall to 0.70, the combined corner is about 3,457 W. That corner has physical meaning
  only if the simultaneous conditions are credible for the pump/system interaction.
  Separate perturbations do not prove a bound over arbitrary interactions.
- **Answer:** nominal power meets the criterion, but the stated joint corner does
  not. These equations alone do not establish pump availability, cavitation margin,
  off-design efficiency, motor sizing or full lifecycle cost. The next useful evidence
  is a pump/system operating curve and applicable efficiencies, not dozens of runs
  of unchanged algebra. Cite the nominal and joint-corner runs in the study answer.

This illustrates an acceptable screening answer that rejects a stronger sizing claim.
The same primitive sequence applies to thermal, structural, process and aircraft
studies; the required physics and evidence change.

## Execution budgets

Use the exposed submission schema and `get_capabilities` for execution limits.
The run's wall budget includes startup and differs from the HTTP request timeout.
Inspect terminal execution state and failure reason even when results are absent.
An ambiguous submission requires receipt reconciliation, never an automatic retry.
Saved analysis launch owns missing-run admission and the frozen surrogate plan;
standalone run tools remain appropriate for separate verification calculations.
