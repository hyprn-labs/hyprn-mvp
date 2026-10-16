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

For two or more independent controls, plan joint sampling by default. One-input
slices cannot supply results after other inputs change. For one independent input,
prepare its assessed curve; for a discrete interval with fewer than five admissible
values, calculate all admissible values instead of fabricating continuous steps.
A study with no variable numerical inputs has no slider-preparation obligation.
Respect an explicit user request to omit exploration.

Set output-specific numerical error targets before fitting. Budget baseline/axis
support, joint training and disjoint checks together; five points per slider is
not enough to train an arbitrary multivariable surrogate. Provide at least five
successful original points spanning each displayed baseline slice, including the
baseline and endpoints, unless the discrete exception applies. Include joint
interior and decision-relevant simultaneous boundary conditions. Preserve the
platform's returned training/check partition; checks used for method selection
are not independent assessment points. Reserve additional joint verification
points before examining their original-model outputs.

Preview incremental original evaluations and wall budget. Reuse the authorized
budget; do not ask the user to prepare samples manually. If a useful joint design
exceeds that budget, state the missing coverage and its cost before expanding it.
Do not silently narrow the brief or promise all combinations from a sparse sample.

## Execute through the public primitives

Use `list_tools` and `describe_tool` first. The owner-session tool names below are
available in the current client; a restricted installation may expose less.

1. After saving the case answers and study answer, read `get_exploration_basis`
   for the intended configuration mappings. Save the declared domain with
   `save_exploration_design`, pinned to that answer version. If later scientific
   findings require a revised answer, recheck the exploration's answer/model pins.
2. Inspect `list_exploration_samples`, `list_prepared_explorations` and
   `list_exploration_surrogates`. Reuse compatible originals by full-vector numerical
   equality, exact units, model/source and numerical/runtime identities. A reused
   coordinate is not a newly executed point; `4` and `4.0` are the same coordinate.
   Never relabel a held-out check as training to improve apparent agreement.
3. Use `preview_exploration_samples`, then `sample_exploration` for missing joint
   and support originals. For seeded designs, evaluate the exact coordinates the
   platform returns, not a hand-picked substitute grid. Follow the operation with
   `get_exploration_samples`; use lightweight `run_status` for individual run groups.
   Read full histories only for needed results or diagnostics. Persist command and
   operation IDs and reconcile uncertain submissions instead of resubmitting.
4. Use `adopt_exploration_point` where supported to add compatible existing originals
   to the retained basis. Check its returned operation ID and counts: duplicate
   adoption may return the existing operation. Preserve the training/check roles.
   For baseline slices needing explicit equal-value linked controls, use the live
   slice format supporting `varying_targets` through `submit_exploration`; its
   `sample_outputs` retain original run links. Such slices supplement joint coverage.
5. Call `build_exploration_surrogate` on the completed sampling operation and saved
   design. Poll `get_exploration_surrogate` to terminal state. Inspect every category
   and output's method, independent check count, error target, observed error and
   reason. A terminal or partly assessed version is not proof that all outputs are
   ready. Adopt or calculate only missing informative points, then create a new
   immutable fit where checks or coverage fail. Never weaken targets for display.
6. Call `predict_exploration` on that exact version with complete selected vectors
   and an independently selected curve axis. Current HYPRN automatically loads or
   renews its prediction process from the saved artifact; manual warming is not a
   delivery requirement. This does not sample or refit. `warm_exploration_surrogate`
   remains an optional optimization for an installation that exposes it, not a
   substitute for proving the ordinary prediction path works.

No sampling, fitting or original execution belongs in the slider interaction path.
Keep saved original-execution and surrogate-computation runtime identities distinct.
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
