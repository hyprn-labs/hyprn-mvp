# Scientific depth and stopping rules

Use this reference when selecting checks, interpreting numerical results or deciding
whether to answer. These are engineering judgments supported by evidence, not new
API status fields or a universal certification checklist. The practices and their
primary sources are identified in [primary-sources.md](primary-sources.md).

## Match depth to the intended claim

| Intended claim | Minimum defensible basis | What remains outside the claim |
|---|---|---|
| Explain a mechanism or screen candidates | Relevant physical argument, explicit assumptions, dimensional and implementation checks, informative baseline and failure cases, influential omissions identified | Predictive accuracy and complete feasibility unless separately established |
| Compare alternatives | Above, plus a controlled comparison, uncertainty in differences/rankings and investigation of influential interactions | Universal ranking outside the evaluated domain |
| Predict performance or size a design | Above, plus evidence of adequacy in the intended domain, numerical error controlled at the required resolution, validation against applicable independent observations, uncertainty and constraint margins | Unvalidated regimes and unmodeled system requirements |
| Claim an optimum | A supported optimization actually executed, explicit objective/design variables/bounds/constraints, verified evaluations and evidence for the stated degree of optimality | Global optimality from a local solver or a finite sample |
| Support a consequential commitment | Evidence commensurate with consequences, relevant standards and acceptance criteria, unresolved hazards and model limitations addressed, appropriate accountable human review | Certification, release or human approval by the agent alone |

An unvalidated model may support a conditional prediction or exploratory comparison;
label that dependence explicitly. Do not present it as a validated prediction.
These rows are cumulative reasoning needs, not a mandatory number of runs. A simple
closed-form balance may need fewer calculations than a poorly characterized empirical
model. More simulations do not compensate for missing physics or evidence.

Record the intended resolution before selecting fidelity: which difference matters,
which constraint is close, and what error could alter the decision? If no defensible
tolerance exists, explain that uncertainty rather than choosing a convenient one.

## Verify the calculation at the relevant layers

**Formulation and dimensions.** Check the system boundary, conservation laws, sign
conventions, absolute versus gauge values, bases and denominators. Distinguish energy
from power, mass from weight, and per installed seat from per occupied seat. Empirical
coefficients carry the units and normalization of their fitted relation. Logarithms,
fractional powers and correlations need valid arguments and domains. A unit label in
the API cannot establish that the equation is dimensionally correct.

**Implementation.** Choose tests capable of finding plausible errors: independently
derived simple solutions, analytic limits, balances, symmetry or invariance where
applicable, and physically justified monotonic trends. Check intermediate quantities
so compensating errors cannot hide in one final match. Predict the expected behavior
and its tolerance first. A second implementation is useful only to the extent its
derivation and failure modes are independent; shared equations or data are not
independent physical validation. Never run candidate component code in the agent
shell: verification calculations use the supported restricted execution path.

**Solution.** For an algebraic model, inspect conditioning, cancellation, domain
boundaries and rounding near constraints. For an available iterative solver, inspect
convergence and the quantities of interest under justified tighter numerical settings.
A small residual alone does not bound output error in an ill-conditioned problem.
If a supported method discretizes space or time, examine refinement behavior and
whether error estimation assumptions hold; a small change between two grids is not
automatically a reliable error bound. Do not demand mesh studies for a scalar
closed-form calculation or imply that HYPRN currently offers a field solver.

Use numerical tolerances that resolve the engineering decision. Keep them separate
from physical acceptance thresholds. Do not loosen a tolerance after failure just to
pass a check. If revision is justified, record why and what it changes.

A valid negative margin is a useful physical result. An undefined expression,
unsupported regime or unconverged computation is not a feasible/infeasible result:
retain its failure or unavailable-value reason. Never clip, extrapolate or substitute
zero silently. A failed check blocks dependent numerical conclusions, while independent
source-based findings may still be reported.

## Validate the representation, not just the implementation

Identify the target system, observable, operating range and accuracy required for
the intended use. Find relevant measurements with known conditions, provenance and
uncertainty. Compare like quantities under matched boundary conditions; document
remaining differences. Treat simulation-to-simulation agreement as comparison, not
experimental validation. A publication's authority does not establish applicability
to a new geometry, scale, material or regime.

Separate parameter calibration from validation. Data used to select a coefficient,
unit interpretation or model variant cannot independently validate that choice.
Use independent conditions or withheld data where available, and acknowledge small
or biased validation sets. One matched point does not validate an entire envelope.
Examine systematic discrepancy as well as average agreement; do not tune away a
structural model error without revisiting the physical assumptions.

When observations are absent, use physical bounds, established limiting cases and
applicable prior evidence to support a narrower claim. State the remaining predictive
gap and the observation that would close it. Do not invent measurement uncertainty
from plotting resolution or treat a rounded graph value as an exact target.

## Assess uncertainty in the decision

Identify potentially material contributions before propagating numbers:

- Input measurement, property, geometry and operating-condition uncertainty.
- Calibration and empirical-correlation uncertainty, including applicability limits.
- Numerical approximation and solver error.
- Omitted mechanisms, system boundaries and alternative plausible formulations.
- Future scenario choices, such as utilization or price, which may have no defensible
  probability distribution.

Distinguish variability from lack of knowledge where it affects the decision. Record
the basis of ranges, distributions and correlations. A guessed range is a scenario
assumption, not a measured confidence interval. Do not assign independent distributions
to quantities sharing calibration, environmental conditions or an upstream run.
Result-linked inputs preserve exact values; they do not automatically propagate
uncertainty or covariance.

Use a supported method proportional to the problem. Local perturbations can identify
important inputs; they do not establish global behavior. Test interactions when the
physics or decision suggests them. Deterministic bounds or alternative assumptions
may be more honest than probabilities. Endpoint or corner samples are not proven
worst cases without monotonicity or other bounding arguments. Nonlinear responses,
regime transitions and coupled constraints can require interior cases or a revised
model. Do not introduce hidden randomness or an unsupported uncertainty engine.

Evaluate uncertainty in the **difference** when comparing options. Shared input errors
may partly cancel or reinforce, depending on sensitivities; do not assume either.
Separate comparisons under common conditions from separately sized designs. If mass,
geometry and operating conditions all change, the result does not isolate the effect
of a fuel, material or technology alone.

Compare a constraint margin with the plausible adverse change and numerical error.
For example, a nominal 2% positive margin with a credible 5% adverse shift does not
establish robust satisfaction. Do not combine overlapping uncertainty contributions
as independent errors. If a material contribution is unquantified, say so; a narrow
interval for known inputs is not a bound on total model error. Report precision
appropriate to the evidence and distinguish bounds, scenario envelopes, standard
uncertainties and coverage intervals. Never invent a confidence percentage.

## Make optimization claims only at the achieved level

Check capability and authorization first. Specify the objective, design variables,
units, bounds, constraints and treatment of failed evaluations. Verify scaling and,
where used, derivatives. Inspect convergence, active constraints and sensitivity to
initial conditions when relevant. Re-evaluate the selected candidate with the same
verified model and explicit settings; examine constraint margins under uncertainty.

A local solution is not a proven global optimum. A boundary solution can expose an
arbitrary bound or missing physics. The best sampled configuration is only best among
the evaluated configurations. If optimization is unsupported, provide that conditional
comparison and leave the optimization deliverable open. Never hide an optimizer
inside a component or claim that a published design was optimized by this study.

## Stop, refine or narrow the answer

| Finding | Next action |
|---|---|
| Implementation, balance or unit check fails | Correct the cause and re-run affected computations before using them; retain the failed check and its consequence. |
| Numerical error could reverse the decision | Refine the supported numerical method or narrow the claim; do not report unresolved digits as certainty. |
| Ranking changes under credible assumptions | Report the conditional ranking and decisive assumptions; select the next discriminating case or evidence request. |
| Important physics or validation evidence is absent | Bound its effect if defensible; otherwise leave the stronger deliverable open and name the missing evidence. |
| Supported evidence resolves the intended decision | Record the answer and stop expanding the study unless further work changes its use or required resolution. |
| Platform capability or authority is missing | Explain the concrete limitation, continue independent work, and request only the missing capability or decision when needed. |

In HYPRN, put the check rationale and adequacy argument in the method; explicit
verification or sensitivity inputs belong to configurations; executions
and computed comparisons belong to runs; independent sources belong to evidence.
Record comparison cells, interpretation with limitations, uncertainties and next
analysis in the study answer with exact calculation, run and evidence references. Use existing fields, not a second quality database.

Before saving the final answer, account for each requested deliverable and identify
the exact basis, applicable domain, relevant checks, uncertainty and remaining gap.
Read back saved records. An attractive summary, a successful API response and a met
criterion do not independently establish scientific acceptability.

## Write for the answer reader


The reader must understand the answer without this conversation. Author the saved
fields for distinct purposes, using connected sentences rather than compressed
technical noun lists:

- **Outcome:** choose the structured recommendation first. In `outcome.reason`, write
  one connected evidence-and-reasoning paragraph: decisive result, conditions and the
  limitation that determines the recommendation. If evidence is insufficient or
  contested, explain what is missing or conflicting and why it prevents a choice.
  Do not repeat UI labels, IDs or a bare status as the explanation. Do not invent a
  winner when several alternatives pass or evidence is insufficient.
- **Comparison:** cite relevant original runs and outputs with their criterion
  evaluations. Explain the selection when many runs are available (for example,
  a reference condition and the smallest margin). A sampling set or surrogate is
  supporting numerical evidence, not an extra physical outcome in the table.
- **Justifications:** explain why a cited record supports, challenges or limits a
  claim. This can concern governing physics, numerical checks, physical validation,
  evidence quality or surrogate accuracy; it is not just a list of records. State
  which question the check answers and what it does not establish. Distinguish
  agreement with the original calculation from agreement with the physical system.
- **Interpretation:** connect the comparison to its engineering meaning and scope
  in a few short paragraphs. Preserve material limitations here; do not repeat
  the table or paste a calculation inventory.
- **Uncertainties:** name what is unknown in a complete sentence. Give a justified
  range when available, then explain the causal link to a result, margin or choice:
  what could change, in which direction, and whether that effect was evaluated.
  Distinguish an illustrative operating range from measured uncertainty. If no
  bound is known, say what evidence is missing; do not invent a confidence interval.
- **Next analysis:** name the next concrete calculation, measurement or source check,
  the conditions to examine, and the observable to compare. In the resolves field,
  explain what decision this would enable or what uncertainty it would reduce.
  Explain unfamiliar terms on first use. Avoid prescriptions such as “validate
  robustness” or “assess operating point” without saying what to calculate or measure.

All study-specific names, descriptions, reasoning and scientific claims must be
saved through public authoring operations in their owning records. Never change
application code, rendering conditions or fixtures to make one study read better.
The application's layout must work for unrelated studies using the same primitives.
If a needed distinction cannot be expressed, report that gap rather than inventing
hidden data or a special-purpose screen.

Give each analysis a short description stating the question it investigates, the
conditions varied or held fixed, and what its results can establish. This description
is reused by the saved reader and settings; do not put counts, IDs, button instructions
or compressed metadata summaries into it. Counts, methods, errors and validation
outcomes must come from structured platform records, not claims in prose. Keep
training, method selection and independent validation distinct. Do not rewrite
immutable records merely to improve their presentation; use an explicit successor
when the scientific description needs revision. Table ordering, alignment, creation
actions and contextual help belong to shared platform primitives, not study-specific
content or agent-generated HTML.

Lead the conclusion with the engineering finding and its conditions. Keep the
recommendation classification distinct: a useful screening result need not qualify
a design. Let structured comparison cells carry values and requirements; use
interpretation to explain causes and consequences rather than reciting the table.
Give each basis entry a distinct evidential role. Do not repeat validation counts,
methods or accuracy claims in prose when the platform already displays their saved
records. Explain an uncertainty as what is unknown, how it could change the answer,
and what evidence would resolve it; make the next analysis address that gap.

Use plain paragraphs and simple bullet lines; these fields do not render Markdown
tables or emphasis. Keep units, conditions and useful precision, and link the full
records instead of repeating IDs. Read the fields together before saving: each
sentence should add a finding, its reason, a meaningful limit or a next action.
Improve wording without rerunning unchanged calculations or changing their pins.

Before finishing, read back the saved records and check the public reader journey
through the requested surface; a browser is not required for an API-only task.
Follow the evidence links and check agreement of values, units, denominators,
scenario descriptions, controlled comparisons and claim strength. Revise stale
references and affected answers together. Keep old records identifiable rather than
silently replacing their basis. Use concise explanatory prose, appropriate precision,
and selected comparisons; link full result tables instead of copying every output.
A reviewer should understand the answer without the conversation or internal IDs.

Report the supported answer, its scope and uncertainty, the unresolved deliverables,
and what was actually saved/run. Stop when the evidence meets the stated use and
further work is unlikely to change the decision at the required resolution, or when
a named gap prevents a stronger answer. Do not invent a numerical confidence score.
