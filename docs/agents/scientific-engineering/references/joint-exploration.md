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
not enough to train an arbitrary multivariable surrogate. Provide at least five
successful original points spanning each displayed baseline slice, including the
baseline and endpoints, unless the discrete exception applies. Include joint
interior and decision-relevant simultaneous boundary conditions. Preserve the
platform's returned training/validation partition; validation points used for method selection
are not independent assessment points. Reserve additional joint verification
points before examining their original-model outputs.

Preview incremental original evaluations and wall budget. Reuse the authorized
budget; do not ask the user to prepare samples manually. If a useful joint design
exceeds that budget, state the missing coverage and its cost before expanding it.
Do not silently narrow the brief or promise all combinations from a sparse sample.

## Execute through the public primitives

Use `list_tools` and `describe_tool` first. The owner-session tool names below are
available in the current client; a restricted installation may expose less.

1. Save and mark explicit reference configurations of one exact model version. Declare
   each group's independent dimensions, units, ranges, steps, and any required co-variation.
   Discrete alternatives use separate groups with their own reference configuration;
   never interpolate between category labels or infer shared meanings from names.
2. Inspect existing calculations and sample operations. Reuse compatible saved configuration
   runs by exact identity; do not relabel training data as held-out validation points. Choose `boundary_latin_hypercube` for published exploration. It includes every joint
   corner in training and fills the remaining training budget with seeded interior points.
   Validation points remain separate. Interior-only Latin hypercube sampling is available for investigation
   but does not establish full slider coverage. Neither method guarantees five calculated
   points on every baseline slice; report actual coordinates without inventing them.
   For d independent dimensions, reserve more than 2^d training points (up to 64 per group)
   and validation points within the 128-point total limit. Count linked coordinates once.
   If the domain exceeds capacity, report the required count and capability gap. Do not
   hide inputs, link unrelated variables, silently narrow ranges or promise full coverage.
3. Use `sample_analysis` with explicit `estimate_plan.tolerances`, then `get_analysis_samples`. The completed operation creates
   an immutable analysis version containing generated configurations and disjoint
   training/validation partitions. Do not hand-pick substitute coordinates. Reconcile an
   uncertain operation before trying again.
   New requests use `validation_count`; new saved points use `partition: validation`.
   Historical `check_count`/`check` records remain immutable. Training and validation
   describe use, not numerical basis: model runs provide calculated values for both.
4. Use `launch_analysis` with body `{}`, then `get_analysis_execution`. The launch pins
   and reuses existing member runs, calculates missing points and automatically builds the
   surrogate from the saved plan. It continues without an open client. Repeating launch
   returns the same operation, never a replacement run. Resolve uncertain runs explicitly.
5. Require execution `complete`, then inspect `get_analysis_estimate` using its pinned
   estimate id. All requested outputs must pass; inspect each group's metrics and failures.
   Do not call standalone fit for a managed analysis. Change ranges, counts or targets only
   in a new analysis version, reusing compatible points. Never relax accuracy merely to
   display a curve. Historical versions remain readable; create a version with an explicit
   estimate plan to use this lifecycle.
6. Read `get_analysis_exploration`, then `predict_analysis` on that exact estimate
   with the complete selected input vector and an independently selected plot axis.
   Cold predictions reload the assessed artifact automatically without fitting or sampling.
   Exercise every group before publication to warm the interaction path and measure latency.
   The figure starts at a labelled sample centre when training points are available; this is
   an exploration selection, not a calculated result or a coverage guarantee. Reset restores
   reference inputs, and calculated-point selection restores an exact original input vector.
7. Call `check_analysis_preparation` with the estimate and all `shown_outputs`.
   Require `ready: true`: every group's training corners cover the declared box, every shown
   output passed its independent assessment, and calculated samples have available outputs.
   A failed check is a preparation failure, even if the estimate's broad state says ready.
   Refine training within budget, then rebuild and recheck. Keep tolerances unchanged;
   reserve new independent checks when earlier check results inform refinement. Do not use
   validation data to fit or select a model and still count it as independent assessment.
8. Save the answer's `exploration_basis` with the exact analysis version, estimate and
   bound output criteria, then read it back. Do not silently use an estimate belonging to
   another version. Alternative comparisons cite exact calculations and original runs.

These names refer to the owner-session thin tools. On a delegated surface, inspect the
exposed catalogue first; absent operations remain a stated capability gap, never permission
to bypass the public tool boundary.

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
