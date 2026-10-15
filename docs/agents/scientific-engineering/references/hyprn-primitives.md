# Operating on HYPRN primitives

Read before authoring or revising a study. This is a semantic operating guide, not
an alternative API specification. [CONTEXT.md](../../../../CONTEXT.md) defines terms;
[the public contract](../../../../contracts/hyprn-mvp.openapi.yaml) and the session's
exposed tool schemas define permitted operations. Keep wire names unchanged even
when the UI uses clearer terms such as quantity rather than port.

## Establish the surface

For a delegated client, start with `get_study_overview`, `get_capabilities` and
`get_playbook("workflow")`; load the area guidance when operating there. Inspect
pagination, truncation and missing-source warnings. Read the exact underlying
records for consequential claims rather than relying on a clipped overview.

A capability flag does not grant permission or add a tool to the session. The
current local registry is read-only; several write names in the playbook describe
planned capabilities. The owner-operated demonstration instead has an expressly
authorized [public API path](../../local-api-demo.md). Use that only in its authorized
context, not as a way around delegated restrictions. Verify current state on each
installation; never infer capability from the roadmap or this dated description.

Read the unit catalogue before declaring model quantities. For the authorized
owner HTTP client, discovery uses `GET /api/1/capabilities` and
`GET /api/1/studies/{study_id}/unit-catalog`. Use the current schema version that
supports quantity definitions when advertised; do not omit semantic definitions
merely because an older model format remains accepted. Unsupported units call for
an explicit limitation or justified reformulation, never a false unit label.

The owner client accepts `{"operation":"run_status","study_id":"<UUID>",
"run_ids":["<UUID>"]}` for a single lightweight status read of up to 20 distinct
runs. Use bounded batches and back off between unchanged observations. Read full
records when results or a failure need inspection. Keep returned envelopes intact:
a configuration's saved record is under `data.configuration`. Validate against the
public response schema rather than assuming all reads have identical nesting.

When a request is rejected unchanged, repair the indicated fields using the public
schema and discovery results. Do not recreate the study. Save command IDs before
mutations and returned identities immediately afterward; resolve uncertain outcomes
through the command receipt rather than repeating the mutation.

## Primitive map

| Primitive | Agent responsibility | Read-back acceptance |
|---|---|---|
| Study | Preserve the engineering question and requested outcomes; give it a useful name and description. | The scope of the question has not shrunk to match available computations. |
| Modeling approach | Explain the physical argument, current scope, methods, intended cases, assumptions and limits. Save a coherent version. | Implemented steps link the intended exact models/elements; proposed work is visibly incomplete. |
| Method step | Write purpose, suitability, actual calculation sequence, evidence and unmet requirements. | Explanation agrees with source and connections; shared context is not falsely presented as each component's own computation. |
| Component definition/version | Declare a cohesive transformation, scalar quantities and readable source. Separate physics from economic interpretation where their assumptions differ. | Source, declarations, units and domain restrictions agree. A saved version is exactly the reviewed implementation. |
| Component instance | Select a particular use of a definition and its local assumptions/connections. | Editing shared code updates only the intentionally selected instances; other uses keep their versions. |
| Quantity | State meaning, units, sign, reference condition, aggregation basis and input/output role. | Temperature vs temperature difference, absolute vs gauge pressure, power vs energy, and per-seat vs total are unambiguous. |
| Connection | Transfer the intended producer output to the intended consumer input. | Semantic meaning, reference state and units agree, not just scalar shape. No accidental duplicate free assignment. |
| Evidence version | Preserve a source/observation with locator and scope; distinguish the source from interpretation. | The exact referenced content warrants the particular assertion; contradictory evidence remains discoverable. |
| Assumption | Record an adopted condition at approach, model, component or configuration scope, with relevant evidence. | All affected cases inherit it, exceptions are explicit, and copies do not drift. |
| Case | State the situation's question and why examining it is informative. | Its “held fixed” and “varied” claims agree with its configurations, including derived geometry or loads. |
| Configuration | Pin the model and relevant approach/case; assign every free input with unit and provenance, numerical choices and criteria. Preview before committing. | Preview/read-back has the intended values and links; no silent defaults or source copied indiscriminately across inputs. |
| Criterion | Express an actual requirement on a computed output with units, threshold and justified tolerance. | Requirement, calculation check and applicability condition are distinguishable; a pass cannot imply all three. |
| Run | Submit once, resolve its authoritative outcome, inspect results and failures. | The run used the intended configuration; all required outputs have values or explicit reasons for absence. |
| Result-linked input | Use the supported binding to a specific run/output when it is scientifically transferable. | Conditions and meaning remain compatible; uncertainty/shared dependencies are not lost by copying a scalar. |
| Case/study answer | Save observations, interpretation, qualifications, open deliverables and exact basis. | The displayed answer uses the selected approach/case and intended source, run and case-answer versions. |

This map creates no new product entities. Verification plans belong in method
reasoning; their numerical cases use ordinary configurations/runs. External benchmark
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
2. Retain source evidence and scoped assumptions. Draft the method/cases before
   implementation, allowing unresolved/proposed work.
3. Author or revise definitions and the model; inspect declarations, source and
   connections, perform supported static validation, and save the exact model version.
4. Link implemented methods to that version; save the coherent approach version with
   the intended cases. The approach references models; models do not execute an approach.
5. Preview configurations that pin those versions and assign inputs, provenance,
   numerical settings and criteria. Review warnings and conversion provenance, then
   commit and read back the returned versions.
6. Submit the intended configurations within the current execution limits. Wait on
   existing run identities; an uncertain receipt requires lookup/reconciliation,
   never an automatic second submission. A readiness failure is not a run.
7. Read the complete results needed for the question and verification. Plan a further
   case only when it resolves an identified error, sensitivity or coverage gap.
8. Save case answers, then the study answer selecting their exact versions. Read them
   back; inspect the public UI when requested or relevant and accessible. An API-only
   request does not require browser inspection.

A changed coefficient generally needs a new configuration; changed equations need
a new model version and corresponding configurations. A changed explanation may
need an approach version and re-associated answers, not new numerical runs. Inspect
the API's compatibility/pinning requirements: do not claim a run belongs to a newer
approach merely because its numbers are reusable. Explain a reused older result's
role and preserve its original context.

The answer API currently has `observations`, `interpretation`, `qualifications`,
`open_deliverables` and a `basis` containing configuration, run, evidence and
case-answer version IDs. A case answer uses its case ID; a study answer has no
case ID. Use the current schema and expected-revision mechanism rather than copying
this description as a payload. If the exposed client has no answer writer, report
the unsaved answer plainly; do not create a misleading evidence note instead.

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
0.80, 4,000 operating hours/year and an assumed tariff of 0.20 currency units/kWh.

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
  and expense 2,000 currency units/year; declare the currency and price year when
  applying the example to a real study. Currency remains outside dimensional checking
  if the installation does not support it.
- **Challenge cases:** if flow and pressure may each rise 10% and pump efficiency
  fall to 0.70, the combined corner is about 3,457 W. That corner has physical meaning
  only if the simultaneous conditions are credible for the pump/system interaction.
  Separate perturbations do not prove a bound over arbitrary interactions.
- **Answer:** nominal power meets the criterion, but the stated joint corner does
  not. These equations alone do not establish pump availability, cavitation margin,
  off-design efficiency, motor sizing or full lifecycle cost. The next useful evidence
  is a pump/system operating curve and applicable efficiencies, not dozens of runs
  of unchanged algebra. Save the case answers and select their versions in the synthesis.

This illustrates an acceptable screening answer that rejects a stronger sizing claim.
The same primitive sequence applies to thermal, structural, process and aircraft
studies; the required physics and evidence change.

## Owner-session tools and execution budgets

Use the named tools documented in [the local client](../../local-api-demo.md).
`describe_tool` supplies the public body schema; `create_model`, `preview_model`
and `edit_model` choose request formats without changing saved scientific versions.
Do not extrapolate a request format from `model/4` in capabilities. Consult
`model_formats` for operation-specific formats if a direct API operation is needed.

Use `submit_run` with an explicit `execution_budget.wall_seconds`, then `run_status`
for lightweight polling and `get_run` for results or diagnosis. The default is 300
seconds and the supported range is 1–3600 seconds, discoverable in capabilities.
The native process retains the budget. Read `execution_diagnostic` even when
`history.results` is null. `read_artifact` returns checked bytes separately from API
envelopes. Preserve command IDs before calls and returned IDs after each step;
resume from those records rather than restarting authoring after a local exception.
