# Prepare joint answer exploration

Read for every new numerical study, and when revising its model, answer basis or
input ranges. This is part of `/hyprn` delivery, not a follow-up the user must
request. Use the exposed public tools and their live schemas. Guidance does not
enable unavailable tools or expand execution authority.

## Define the domain before spending the budget

Inventory every free input and output from the saved answer basis. For each
category, map its exact configuration and model versions, units, ranges, steps,
baseline and linked-input bindings. Use brief or applicable evidence ranges first.
Otherwise choose a scientifically defensible local interval, recorded as an
agent-selected exploration assumption with its rationale. It is not an uncertainty
distribution or a validated operating envelope. Do not infer integer steps or
physical bounds from a symbol alone. Keep discrete categories separate; link
inputs only when the model requires that relationship, not to reduce sampling.

Reconcile the dimension inventory with every requested scenario before sampling.
An input that changes between scenarios must be represented in joint coverage,
or in separate groups when the alternatives are discrete. A constant requirement
remains fixed. Do not turn a changing parameter into a fixed input merely to save
sampling effort. If coverage is incomplete, report the gap before publication;
verify the actual saved dimensions against the brief, not only the baseline.

For two or more independent controls, plan joint sampling by default. One-input
slices cannot supply results after other inputs change. For one independent input,
prepare its assessed curve; for a discrete interval with fewer than five admissible
values, calculate all admissible values instead of fabricating continuous steps.
A study with no variable numerical inputs has no slider-preparation obligation.
Respect an explicit user request to omit exploration.

Set output-specific numerical error targets before fitting. Record their rationale
and the sampling/check rationale in the analysis `description` (shown as Description), with
exact counts/partitions in its design and exact output targets in its saved `estimate_plan`.
Model calculation logic stays focused on the model's input-to-output computation;
do not store exploration settings there or repeat the settings inventory in prose.
See [Model and analysis authoring](model-analysis-authoring.md) for the creation
paths and the distinction between saving and launching. Budget baseline/axis
support, joint training and disjoint checks together; five points per slider is
not enough to train an arbitrary multivariable surrogate. Include enough joint training to resolve the response and its boundaries. Five points
per independent axis do not establish multidimensional support. Report the actual
calculated coordinates; do not require or fabricate baseline slice points when the
joint design does not contain them. Preserve the
platform's returned training/validation partition; validation points used for method selection
are not independent assessment points. Reserve additional joint verification
points before examining their original-model outputs.

Preview incremental original evaluations and wall budget. Reuse the authorized
budget; do not ask the user to prepare samples manually. If a useful joint design
exceeds that budget, state the missing coverage and its cost before expanding it.
Do not silently narrow the brief or promise all combinations from a sparse sample.

## Execute through the public primitives

Read the offered tool schemas and the canonical playbook section
`configuration_and_runs`. The same scientific lifecycle applies on local and managed
surfaces; a restricted catalogue never grants permission to bypass the public boundary.

1. Save explicit configurations with units and provenance for each discrete group.
   Derive ranges from the brief, applicable evidence or a labelled engineering assumption.
   Keep independent variables independent; do not interpolate category codes.
2. Call `create_sampled_analysis` with `boundary_latin_hypercube`, an explicit seed,
   disjoint validation and output-specific tolerances. Count every group against the
   advertised capacity: currently 128 training plus validation points in total, at most
   64 of each per group. Training must accommodate all 2^d corners plus interior points.
   Reserve unused capacity for added training and fresh independent validation. If the
   required dimension count cannot fit, explain the capability gap instead of hiding
   variables, weakening targets or silently narrowing the domain.
3. Poll `get_sampling_status`, retain the saved analysis version and call
   `launch_analysis`. Monitor `get_analysis_execution`; the application reuses pinned
   runs, admits missing points and fits the immutable plan without an open agent session.
   Do not manually submit member points or run a separate fit. A changed plan needs a
   new analysis version. Resolve uncertain operations before any deliberate retry.
4. Inspect `get_surrogate` for every output and group. Method-selection points choose
   the approximation; validation points independently assess its selected method.
   After a failure, diagnose and refine without relaxing accuracy. Once validation
   outcomes influence refinement, reserve fresh validation before claiming independence.
5. Require `prepare_answer_exploration` ready for all displayed outputs, then copy its
   exact `exploration_basis` into the answer draft. A ready surrogate alone is not proof
   of full joint support or physical validity. Keep incomplete outcomes interim.
6. Use `get_answer_exploration` and `predict_answer` with complete independent input
   vectors and a separately chosen plot axis. Verify every group, save the answer and
   read it back. Predictions load the saved artifact automatically, without sampling,
   refitting or original-model execution.

No sampling, fitting or original execution belongs in the slider interaction path.
Surrogates evaluate new selections cheaply; precomputing the exponential Cartesian product
of slider stops is not required. Full box coverage is a geometric support guarantee, not a
proof of accuracy at every continuous coordinate. Keep numerical agreement and physical
validity separate. Keep saved original-execution and surrogate-computation runtime identities distinct.
A runtime mismatch requires diagnosis, not silently changing a saved artifact's pin.

## Verify the journey before handoff

Check the ordinary public prediction path, not only build status or a baseline:

- In every category, exercise every independent control and declared linked group.
  Query representative simultaneous changes, including an all-controls-changed
  interior vector and decision-relevant simultaneous boundaries. Hold the other
  selections fixed while changing the plot axis; the full selected vector governs
  both values and curves. Check every displayed output, not only the headline one.
- Compare estimates at a fresh predeclared joint point in each category with a new
  original-model run, within the predeclared targets. Do not feed that point back
  into the same fit and still call it an independent check. Failed checks block the
  affected ready claim and require diagnosis/refinement.
- Assess actual coverage, not just each input's min/max. The current joint predictor
  restricts estimates to retained convex support. Individual endpoint coverage does
  not cover arbitrary combinations of endpoints. When a promised interaction has
  no result, enrich its support and reassess within budget. Do not stitch independent
  curves, extrapolate, label an old result as current or substitute zero.
- Reopen the study and query the saved surrogate without a manual warm call. Verify
  cold/expired renewal if the authorized test surface permits it; do not kill live
  services merely to test a study. Without a safe cold test, report that limitation
  rather than claiming expiry was exercised. When UI inspection is available, check
  that loading resolves to current results, with no preparation action required.
- Confirm interaction-only checks create no new original runs, sampling operations
  or surrogate versions. Use returned identities and public readback. A transient
  load is distinct from a genuine unsupported region or failed numerical check.

Do not finish with “open Sample settings to prepare the study.” Deliver the saved
answer and prepared joint exploration, identifying the domain and any remaining
unavailable combinations/outputs. If authority, capacity, failure or budget prevents
completion, keep the usable scientific answer but explicitly mark exploration as
incomplete; do not advertise “all sliders ready.” Do not claim every continuous
combination is covered from a finite handful of successful queries.

These checks establish numerical agreement with the original model within tested
conditions. They do not establish physical validity, feasibility, convergence or
correctness of the engineering interpretation. Range assumptions and source limits
remain visible beside the claims they qualify.

## Choose study outcomes

Save `exploration_basis.shown_outputs` on the study answer with the exact calculation
version and optional assessed estimate. Select quantities that answer the brief;
a relevant intermediate output can be a headline outcome. The application shows all
independent inputs and keeps computational intermediates in the expandable model.
Preserve explicit linked-input groups; do not infer links from names. Read back the
saved answer. The reader's Select outcomes control changes only the current view;
persistent scientific answer changes require a new saved answer version.
Do not hide a consequential limitation or failed requested outcome to make the
compact view appear successful.
