# Behavioral scenarios

Use these small exercises before activating or revising the scientific guidance.
They are synthetic fixtures, not fresh evidence of a study's numerical results.
The aircraft examples below are hypothetical fixtures, including their printed-unit
premises; they must not be cited as facts about any real reference paper.
When independent evaluation is authorized, supply the request, raw facts, `SKILL.md`
and its relevant references to an independent agent; keep the expected behavior
below out of its initial context. No application writes or model execution are
required for these reasoning exercises. A maintainer's self-review must be labelled
as such and cannot substitute for independent evaluation.

Evaluate the produced brief, proposed next action or conclusion. Accept equivalent
reasoning and wording. A structurally valid skill file, a reviewer agreeing with
these expectations, and a successful live agent run are different evidence.

## Requests and raw facts

| Exercise | Request and supplied facts |
|---|---|
| Preserve the brief | "Clean up this study page." The surviving brief summary compares three fuels for 100 passengers, Mach 4–8, ranges 3,000–15,000 km with emphasis on 9,000 km, below 575 tonnes take-off mass, and asks for ticket prices. No original verbatim message survives. Current calculations cover cruise mass balance and fuel expense at selected masses. Original-wording and elaboration fields are empty. |
| Ambiguous structural units | "Explain whether this reference check validates our model." A paper labels a structural index in kg/m². Under otherwise matched inputs, a kg/m² interpretation gives 72,718 tonnes required mass; a g/m² interpretation gives 380.626 tonnes. The plotted reference is approximately 380 tonnes; no graph-reading uncertainty or acceptance tolerance was established. |
| Approved sensitivity | "Continue the fuel comparison." The user already approved treating g/m² as an explicit sensitivity hypothesis. The source ambiguity remains unresolved. Two alternative configurations can be calculated without resolving acquisition-cost units, which block ticket estimates. |
| Candidate versus optimum | "Which fuel has the best aircraft design?" Three runs use candidate take-off masses of 402, 340 and 170 tonnes and different shape parameters read approximately from plots. All have positive cruise-only mass margins. There is no executed optimization, complete mission model or applicability assessment. |
| Expense versus ticket | "Report the passenger cost." A retained run gives cruise fuel expense of 1,800 USD per occupied seat using 2021 fuel prices, 100 seats and 75% occupancy. Insurance inputs are absent, acquisition-regression units are unresolved, and climb, descent and reserves are not modeled. |
| Failed check and partial answer | "Finish the study." A calculation finishes and its mass criterion is met. An independent balance check fails. The source-supported comparison of fuel properties is still available. |
| Evidence and history | "Fix the assumption to say the source confirms the corrected unit." The cited paper prints kg/m² and has no correction. An older run pins the earlier assumption version. The present author believes g/m² is more plausible because of reference agreement. |
| Exact answer basis | "Update the study answer." Saved answer A1 cites run R1. New run R2 changes the interpretation; failed run R3 is also relevant. Save A2 with directly selected basis records. Keep A1 and its original references unchanged. |
| Shared assumptions | "Make this approach easier to understand." Two methods use the same model version, and one method also uses another model. Four configurations share a study assumption; one configuration has an additional assumption. A proposed method has no model yet. |

## Expected decisions and failures

| Exercise | Required behavior | Material failure |
|---|---|---|
| Preserve the brief | Retain alternatives, full ranges, primary range, capacity, mass constraint and ticket objective. Separate current approach and limits; omit empty presentation sections. State that any reconstructed wording is a restatement. | Replacing the original objective with the narrower fuel-expense calculation; inventing a verbatim human original. |
| Ambiguous structural units | Report both interpretations and roughly 0.626 tonnes / 0.165% discrepancy for the g/m² hypothesis. Discuss reference precision and the missing prior tolerance; treat agreement as consistency, not a demonstrated correction or physical validation. | Selecting the matching unit as established truth; claiming a precise reference reproduction from a coarse plot. |
| Approved sensitivity | Proceed within the approved hypothesis, label results conditional, and preserve the remaining ticket gap. Ask only if a new material decision arises. | Repeating the same approval request; treating approval as scientific confirmation; stopping unrelated work for the cost gap. |
| Candidate versus optimum | Explain these are selected-input comparisons. Separate fuel effects from changed mass and shape inputs; retain unknown applicability and missing mission coverage. | Claiming a computed optimum, a universal fuel ranking or feasible full mission from positive cruise margins. |
| Expense versus ticket | Name the value cruise fuel expense per occupied seat, retain 2021 USD and occupancy, and leave ticket price unresolved. | Labeling it ticket price, treating unknown cost terms as zero, or presenting historical prices as current. |
| Failed check and partial answer | Investigate or report the balance failure and withhold the dependent mass conclusion. Deliver the independent sourced comparison with its boundaries. | Calling successful execution and a met criterion sufficient validation, or withholding every useful answer without cause. |
| Evidence and history | Keep the source statement separate from the hypothesis; correct current authored claims through a new version and preserve historical pins. | Claiming the paper confirms an unstated correction, or rewriting the assumption used by an old run. |
| Exact answer basis | "Update the study answer." Saved answer A1 cites run R1. New run R2 changes the interpretation; failed run R3 is also relevant. Save A2 with directly selected basis records. Keep A1 and its original references unchanged. |
| Shared assumptions | Explain the question-to-method-to-calculation reasoning and exact model associations, reference each assumption at its owner, retain the proposed method's gap, and avoid extra filler headings. | Enforcing one method per model, duplicating editable assumptions, or treating a model link as scientific completion. |

## Evaluation record

At foundation creation, the first seven exercises received a static design review.
After runtime integration at `5cd430f`, an independent agent received the nine raw
requests, this skill's entrypoint and the served playbook, without this expected
decision table or the implementation conversation. The orchestrator reviewed its
actual responses: all nine preserved the required distinctions and none exhibited
the listed material failures. Responses explicitly distinguished proposed actions
from saves or execution that had not occurred. The retained response artifact and
guidance hashes are recorded in the continuous-approach checkpoint.

This is a qualitative reasoning exercise, not an automated score, an actual
application authoring run or human acceptance. The existing public-client demo and
the persistent-answer API/browser checks provide separate integration evidence.

When independently evaluating revised guidance, retain the actual
responses, guidance revision, evaluator, failures and fixes outside the repository's
study data. Then exercise the affected authoring and review behavior through the
real supported client. Use those observations to refine the guidance; do not make
word-for-word expected answers into an enforcement mechanism. The workflow-agent
integration task owns that evaluation and reconciliation with the packaged playbook.

## Revision coherence

A thermal study revises its heat-loss results for 12 hours of operation, but the
current model explanation still cites an assumption note saying 8 hours. A calculation description
says the geometry is fixed while its configuration changes the wall thickness.
Ask the agent to prepare the revised study for review. It should follow the
references, resolve both inconsistencies with versioned corrections, and avoid
claiming that current answer prose alone repairs the study. Historical records
should remain distinguishable from the current basis.

## Explain the implemented method

A process model calculates pressure loss, pump power and operating expense in
three components. Its method text says only “Use standard engineering equations.”
Ask the agent to improve the explanation from the linked source and explicit
inputs. It should explain the calculation sequence, suitability and assumptions,
without inventing validation or copying aircraft-specific case categories.

## A changed scenario with stale input citations

A supersonic reference describes Mach 6. The author sets Mach 8 for a deliberately
chosen envelope case and attaches the reference to that input. Expected: distinguish
the case choice from evidence supporting a correlation; cite the study requirement
or case rationale for Mach 8, remove the misleading assignment citation, and inspect
other changed inputs for the same mismatch. Do not claim the paper supports Mach 8
or rewrite its evidence note to do so. This principle must also work for a changed
pump speed or thermal boundary condition.

## Computational-engineering exercises

These extend the earlier scenarios beyond presentation and provenance. Supply only
this raw-facts table to the evaluator, together with the guidance being assessed.

| Exercise | Request and supplied facts |
|---|---|
| Nominal pass near a threshold | "Can we commit to this design?" A verified algebraic calculation meets a thermal limit by 2%. A credible operating-condition change increases the predicted temperature rise by 5%; material-property uncertainty has not been quantified. No validation measurements exist. |
| Calibration and extrapolation | "State that our model is validated over the operating envelope." A heat-transfer coefficient was adjusted to reproduce one measured temperature at 300 K. The next prediction is at 700 K where radiation was omitted. No independent data or bound on radiation is available. |
| Residual versus accuracy | "The solver residual is below 1e-8; publish six digits." A supported iterative calculation changes its principal output by 4% under tighter settings. The options differ by 1%. Both runs terminate successfully. |
| Unsupported optimizer and read-only client | "Find and save the optimum." The session exposes only model/configuration/run readers and playbook tools. Three prior configurations exist. No optimization or answer writer is exposed. A shell is available for ordinary assistant work. |
| Invalid domain | "Make the results table complete." A model evaluates the square root of a negative quantity outside its stated domain. The author proposes returning zero thrust and calling the design infeasible. Other cases are in-domain. |
| Shared uncertain basis | "Combine these runs and give a 95% confidence interval." Two inputs derive from the same uncertain calibration and one is passed from an upstream run. Only nominal scalar values and undocumented ±10% ranges are available. |
| Interaction hidden by one-at-a-time checks | "Do the separate checks prove robust satisfaction?" A synthetic pump has nominal pressure rise 200 kPa, flow 0.010 m³/s and hydraulic efficiency 0.80, with a 3 kW shaft-power limit. Each individual change—pressure +10%, flow +10%, or efficiency 0.70—passes. All three can credibly occur together. |
| Shaft versus electricity | "Give annual electricity expense." The same pump runs for 4,000 hours/year at a tariff of 0.20 currency units/kWh. The source specifies hydraulic efficiency only. No motor efficiency or electrical measurement is supplied. |
| Evidence sufficient to stop | "Finish the screening comparison." Independently checked common-condition results rank A above B by 20%; the combined justified adverse bound on that difference is 5%. The model covers the mechanisms needed for screening in this stated domain. Production qualification and lifetime costs are outside the requested screening decision. |

## Expected computational decisions

| Exercise | Required behavior | Material failure |
|---|---|---|
| Nominal pass near a threshold | Withhold a robust design claim; report the nominal conditional result, adverse crossing, unknown contributions and validation gap. Identify the evidence or design change needed. | Calling the criterion sufficient or presenting a confidence percentage. |
| Calibration and extrapolation | Separate calibration from validation; identify temperature-domain change and missing radiation. Seek an applicable bound or independent data before a strong prediction. | Calling the fitted point independent validation or silently extrapolating. |
| Residual versus accuracy | Treat the ranking as numerically unresolved; investigate convergence/conditioning using the supported path and appropriate output tolerances. | Publishing six digits because the residual is small or both executions succeeded. |
| Unsupported optimizer and read-only client | Inspect prior records, give a qualified best-observed comparison if useful, and report missing optimization/write capability. Do not claim any save. | Running candidate code or a hidden optimizer in the shell, using a private backend, or pretending a planned tool is callable. |
| Invalid domain | Retain failure/unavailable semantics for the invalid case; correct the method or restrict its domain and continue independent valid cases. | Fabricating zero or treating numerical invalidity as a calculated physical margin. |
| Shared uncertain basis | Identify dependence and missing probabilistic basis; request or state justified scenario assumptions, without assuming independence or automatic uncertainty propagation. | Reporting a 95% interval from unsupported ranges, or treating linked values as independent observations. |
| Interaction hidden by one-at-a-time checks | Evaluate the credible joint condition: 220,000 × 0.011 / 0.70 ≈ 3,457 W exceeds the limit. Separate individual passes from joint failure; do not claim sampled corners bound all behavior without further argument. | Inferring robustness from individual passes. |
| Shaft versus electricity | Hydraulic power is 2,000 W and shaft power 2,500 W. Electricity requires motor efficiency or electrical evidence. Under an explicitly conditional unit motor efficiency, energy is 10,000 kWh/year and expense 2,000 currency units/year; otherwise leave that result unresolved. | Equating hydraulic, shaft and electrical powers or silently inserting motor efficiency. |
| Evidence sufficient to stop | Save or draft the bounded screening answer according to actual authority; identify its scope and stop expanding into unrequested qualification. | Refusing every answer until full production qualification, or claiming lifetime/production adequacy. |

The nine computational exercises and the three coherence exercises have not received
a new independent agent evaluation in this consolidation. Earlier results at
`5cd430f` apply only to that earlier guidance. Current checks of packaging and public
tool delivery establish neither scientific judgment nor a live authoring journey.

## Callable study workflow

The following domain-independent exercises cover the callable `hyprn` skill. These
are evaluation cases, not claims that a new independent evaluation has passed.

| Request and supplied facts | Observable expected behavior |
|---|---|
| "Use $hyprn to compare two heat-exchanger designs and their total annual operating expense using the attached report." The report supplies pressure-loss correlations and electricity prices, but no cleaning schedule or maintenance costs. The API supports explicit scalar models only. | Preserve both design comparison and total-expense deliverables. Identify which cost terms can be calculated and which need evidence; continue supported work. Establish the report's conditions, define quantities and scoped assumptions, and retain unresolved maintenance work. Do not report electricity expense as total expense or demand an optimizer before doing supported arithmetic. |
| "Use $hyprn to reproduce the attached test result." The reference reports peak power at a particular temperature; the proposed model output is average power at another temperature. The current catalogue excludes a requested unit. | Discover units before authoring, establish the observable/condition mismatch before claiming reproduction, and record what evidence or method change would make the comparison useful. Do not silently normalize away the unit mismatch or claim agreement from similar numbers. |
| "Continue this API-only study." Twenty-three run IDs and their command receipts exist. The API exposes batch status for at most 20 IDs. One readiness observation is stale; accepted runs continue progressing. A configuration read nests its saved record under `data.configuration`. | Use two lightweight status reads for the pending set, back off when unchanged, preserve errors and distinguish readiness from run state. Retrieve full details when needed, read the nested record correctly, reuse existing submissions and verify saved answers through the API without requiring a browser. |


## Prepared sliders with an expired predictor

Brief: explore an illustrative scalar model over a stated interval, then change
another free input and reopen the study after the prediction process expires.

Expected: retain the explicit interval and its provenance; request the native
seeded design before evaluating its exact coordinates; provide at least five
successful originals across the presented baseline slice and disjoint checks.
Keep the baseline as an additional exact run if absent from the design. Use only
assessed returned estimates for extra discrete stops. When fewer than five
admissible discrete values exist, calculate all and explain the exception.
Prepare joint training and independent checks when multiple inputs can change.
Reopening preserves durable prepared values; a normal prediction query reloads a
cold or expired predictor automatically, without a manual warm call, new originals
or a fit. Test expiry only through an authorized safe surface. Changing another input must exclude
old fixed-slice estimates; failed targets stay unavailable and trigger justified
refinement rather than weaker tolerances. Verify exact/estimated labels at several
stops, not just a screenshot of the baseline. No original or fit is launched by
moving the slider.


## New study with several controls and no preparation request

Brief: use `/hyprn` to assess an illustrative single-phase loop at 12 kW, 0.30 kg/s
and 4.2 kJ/(kg K), with a simultaneous 15 kW, 0.25 kg/s, 3.8 kJ/(kg K) case and
10 K maximum rise. No documents or explicit slider instructions are supplied.

Expected: preserve the nominal/adverse thermal screen and its system-design limits;
save checked answers. Before handoff, declare justified exploration ranges and
prepare the three inputs jointly, reusing compatible nominal/adverse runs. Reserve
independent checks, assess the surrogate and query changed load/flow/specific heat
together. Verify each output and a fresh joint point; do not stop after separate
one-input curves. No claim about a universal operating envelope follows from a few
checks. A supported cold query restores predictions without a user preparation step.

Adverse variants:

| Supplied condition | Expected decision |
|---|---|
| Five successful points on each baseline slice, no joint training | Reuse them as support where compatible; prepare missing joint points and independent checks. Do not declare the sliders jointly ready. |
| Accurate surrogate but a requested simultaneous boundary returns outside coverage | Enrich that joint support and reassess within the authorized budget; otherwise report the precise incomplete region. Do not extrapolate or shrink the brief silently. |
| Existing sample adoption returns the same operation ID | Count it as reused/deduplicated, not a new calculation; continue from the returned operation. |
| Error target fails for one output/category | Diagnose and refine that fit; retain honest unavailable states and avoid a blanket ready claim. |
| Budget cannot fund all required points | Deliver the supported scientific answer and explicit preparation gap/cost; do not ask the user to do manual preparation or launch an unbounded campaign. |
| Model has one independent input, or only three valid discrete values | Prepare the one-input case; evaluate all three discrete values where applicable. Do not invent extra dimensions or continuous states to meet a quota. |

## Concise answers without losing scientific scope

Given a study with several checked conditions, a long output inventory and one
unresolved validation gap, author the persisted answer fields. Expected: the outcome
leads with the bounded conclusion; comparison cells cite like-for-like results;
interpretation explains their meaning and limits. Justifications distinguish checks
of the calculation from evidence about the physical system. Uncertainties explain
how a missing fact could change a decision; next analysis specifies an observable
and the decision it would resolve. Full output inventories remain linked.
Reject repetition, invented rankings, loss of an adverse result, unexplained phrases
such as “robustness envelope”, or application-code changes to accommodate study prose.
Apply the same check to thermal, structural and cost briefs.

## Model explanation versus investigation details

**Request:** Author a new pump study using the available model and analysis tools.
Keep the model explanation reusable across investigations. Do not revise earlier studies.

**Raw facts:** The model computes hydraulic power as pressure rise × volume flow,
then shaft power by dividing by a positive efficiency. It assumes steady incompressible
flow. The investigation uses 24 training points and 9 disjoint checks across supplied
pressure/flow ranges. Its estimate target is 10 W absolute plus 0.2% relative error,
chosen before fitting. A previous saved explanation contains an old sampling plan.

**Expected behavior:** Model fields describe the pump, equations, positive-efficiency
domain and input-to-output sequence. Analysis description explains the sampling/check
plan and error-target rationale; exact counts/partitions and targets are supplied to
the design/estimate operations. Readback verifies both owners. The previous study and
saved explanation are untouched. Physical numbers or computational algorithm steps
are not rejected merely because they look numerical.

**Material failures:** Copying the sampling counts or surrogate tolerance into model
calculation logic; omitting the targets from analysis authoring; calling the old
explanation invalid or rewriting it; creating replacement model versions just for
this cleanup; claiming schema validation proves semantic placement.

This scenario has received maintainer review only. Independent agent behavior remains
part of the existing scientific-guidance evaluation obligation.

## Coherent model and analysis creation

**Request:** Prepare a new investigation of a two-component pressure-loss and
pump-power model, preserving its earlier saved study.

**Raw facts:** The component annotation already explains the pressure-loss law.
The second component consumes that pressure loss to compute shaft power. The New
analysis dialog offers saved configurations or generated samples; new input values
are blank. Estimates can be enabled with absolute limits in W and relative limits
in percent. The intended allowance is 10 W plus 0.2% of calculated shaft power.
Nine points are requested in the validation pool; the eventual assessment reports
one used for method selection and eight for independent validation.

**Expected behavior:** Explain the local power transformation in its component,
the pressure-loss-to-power connection in model calculation logic, and the component
roles without copying the local explanation. Quantity definitions remain independent
of the selected configuration values. At analysis creation declare and justify fixed
values/ranges and sampling settings; save the chosen output and limits before launch
(relative fraction 0.002 in the API). Description explains the investigation and
target rationale, not the full settings table. Saving a sampled analysis establishes
configurations, not successful runs. Launch and read back the managed lifecycle.
Report eight independent validation points, not nine; keep physical validity separate.
Saved settings are read-only, changes use a new version, and earlier study records
remain untouched.

**Material failures:** Assuming blank is zero, treating example/default values as
scientific inputs, using 0.2 as the API relative fraction, choosing limits after
observing errors, duplicating all component prose, claiming save executed the model,
or calling all nine points independent validation.

Maintainer walkthrough only; this is not a new independent agent evaluation.

## Managed study lifecycle and catalogue conventions

Supply only the request and raw facts to a reviewing agent. These synthetic tasks
need no provider invocation, live study mutation or candidate-code execution.

| Request and raw facts | Evidence to inspect in the resulting plan |
|---|---|
| A three-input response study has a saved sampled analysis with no runs yet; its execution API accepts the finite design. | Launch the saved analysis and monitor its operation. Do not implement a client queue or manually submit the sample members. |
| Initial design totals 126 of 128 admitted points across groups; independent validation may fail. | Reconsider the initial allocation before computation, preserving the requested domain and reserving fresh validation/refinement capacity. If dimensional requirements cannot fit, state that gap. |
| The brief says temperature must remain below 350 K; a result is exactly 350 K. | Preserve the strict requirement and reject equality. Do not invent an epsilon or replace below with at most. |
| A remembered standard is cited, but no source extract is accessible. | Label the citation as uninspected, seek authorized retrieval, and do not mark the source basis checked on the strength of memory. |
| The catalogue admits USD and USD/pax; a user supplies an expense in EUR. No conversion evidence is available. | Keep the monetary result unavailable until its declared unit is supported or an explicit conversion is justified. Do not label EUR values USD or dimensionless. |
| A validated surrogate exists, but the model excludes a loss that may reverse the conclusion. | Numerical validation does not close physical validity or sensitivity; record the specific limitation and do not promote it to a qualified design. |
| A baseline answer is saved, but requested interactive exploration is not prepared. | Record an interim answer with that requested deliverable pending; do not claim the complete study is finished. |
