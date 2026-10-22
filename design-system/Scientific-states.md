# Scientific states

How HYPRN MVP words and marks results. These rules carry the product's scientific guarantees into the interface; a screen that breaks one is wrong even if it looks right.

## Values

| Situation | Show | Never |
|---|---|---|
| Input has no value | "unassigned" in `ink-muted` + advisory `StatusTag` | an empty box, a default number |
| Input is zero | `0` in `readout`, plus "0 is an explicit value" when edited | treat it as missing |
| Output not produced | "not computed" in `ink-muted` | `0`, `—` without a word, a blank cell |
| Converted unit | entered value, factor and received value: `150 % → 1.5 (1)` | silent conversion |
| Incompatible unit | alarm on the field, the declared unit and the compatible list | auto-correct |

Displayed numbers use up to three decimal places, with scientific notation below 0.001 or at and above 1e9; a nonzero quantity is never rounded to a displayed zero. Full-precision values stay available in numeric tooltips and exports, without a separate precision dialog; editing, thresholds and comparisons always use exact values.

## Run execution

A run records what executed, not whether the study's design should be accepted. Its
**Execution** panel uses `MetricGrid`: Status and measured Duration.
Only present recorded facts; absent timing is not zero. Duration is launcher wall time,
including startup and stopping, not OpenMDAO model/solver time.

Status uses the shared `executionStatus` and a `StatusTag`: Completed, Failed, Timed out,
Queued, Ready to start, Starting, Running, Needs review or Results unavailable as supported
by the record. Unknown states never become success. A saved/recorded request is not success.
Failure explanations remain visible. Routine logs, source maps and artifacts stay in the
computational record export, not a duplicate Execution details projection.

Study criteria are defined in the brief, bound/evaluated in calculations and interpreted in
the answer (ADR-0010). Current configurations and run headlines have no Criteria section or
“evaluated elsewhere” placeholder. Old recorded criteria, where historical readers still
exist, remain explicitly labelled and never substituted from the current brief.

For future coupled solves, separately project solver identity, convergence, iteration count,
absolute/relative residuals and declared tolerances. For optimization, separately project
driver termination, iterations, model/derivative evaluations and their measured time; final
objectives/constraints belong beside their engineering meaning. Do not show empty future
metrics or interpret driver success as feasibility. OpenMDAO owns numerical statistics;
AiiDA and the launcher own lifecycle/resource facts. Neither establishes physical validity.

Per-output availability stays visible in the outputs table ("not computed" with a reason).
Unavailable is never zero, and execution completion never means a study criterion is met.

## Calculation runs

Each run in a calculation shows one cell per study criterion, each its own `StatusTag` beside its value or reason, never merged into a score.

| Criterion kind | ok | alarm | inert | advisory |
|---|---|---|---|---|
| Constraint | Met · value with units | Not met · value with units | — | Not evaluated · reason |
| Objective | — | — | Measured · value with units | Not evaluated · reason |

An unbound criterion reads "Not evaluated · Criterion not bound"; a missing value reads "not computed". Measured is a value, not a ranking.

## Ensembles

Show `k / s` meeting a criterion over evaluable samples only when `s > 0`, the unresolved count over generated `N`, and, if shown, the bounds `[k/N, (k + N − s)/N]` labelled "bounds over generated samples — not a confidence interval". Unavailable analyses (for example Sobol indices with dependent inputs) appear as an inert panel that names the reason.

## Basis of a claim

- **Computed**: a `Readout` or inline fact linking to the run that produced it.
- **Sourced**: a `SourceChip` opening the exact cited location.
- **Inferred**: the word "Inference" in `ai`, inside an `InferenceBlock` or inline; never styled like a computed value.

## Progress

Quantity direction is independent of scientific state: teal `quantity-input` inlet and rose `quantity-output` outlet, always with Input or Output. A connected quantity uses both hues and an explicit from/to relationship. Blank, zero, unavailable and criterion meanings remain unchanged. Selection uses accent and keyboard focus uses blue, never the direction colours.

Use measured counts ("1 of 2 components evaluated", "9 of 50 iterations") or an indeterminate track with the stage in words ("Queued — waiting for a worker"). No percentage or remaining time is invented. Cancellation shows "Cancellation requested" until the worker confirms it. An uncertain outcome is an explicit warning, never a running track.

## Record persistence

Use the noninteractive `RecordState` beside or below the entity title. It describes storage/editability, never scientific success. `New draft` uses the advisory square; `Saved draft` is neutral; saved versions use a neutral lock and `Read-only`; `Unsaved changes` uses the warning triangle and warning colour. Run history uses `Saved run · read-only` with the shared record lock; execution and calculation-level criteria retain their separate scientific tags.

Record metadata uses the shared [RecordDetails](components/RecordDetails.md) row immediately below its owning title, alongside storage state when available. All types share the visible Record details label, with a type-specific accessible name. Never place it in page action groups, overflow menus, after prose, or beneath Python. An answer pins its brief version and directly cites calculation versions, runs and evidence; its exploration pins the exact calculation and optional assessed estimate. Parent controls never substitute for child records.

## Answer exploration (owner-approved visual amendment, 2026-10-16)

Calculated samples use solid circles in neutral black ink (`plot-calculated`, light ink in dark mode). Estimated samples use orange outlined marks and dashed curves (`plot-estimated`). Apply this same pair to slider stops, selected points, curves and result basis labels; keep words and shapes so colour is never the only distinction. This narrow use supersedes the former logo-only orange restriction. Neither basis implies validity.

Component cards show inputs on the left and outputs with visible response plots on the right. Columns share their natural height; input rows divide it evenly. All content stays visible without an internal scrollbar. When input minimum sizes need more room, the card grows rather than clipping controls. The graph supports 25–250% zoom, including on narrow screens.

Sliders preserve all other selected inputs, except explicit linked-input bindings. Plot against chooses the response axis independently and never changes the selected vector. Curves hold all other selected coordinates fixed (linked axes vary together; their relationships are listed in Input ranges). Prepared coordinates remain selectable outside the available joint coverage: neutral square stops mean no available result for this combination, never a calculated or estimated result from a different slice. Result values, their noninteractive basis labels, plots, axis captions and the result-basis action have distinct vertical spacing.

While a prediction request is pending, unavailable values show the running “Updating…” state instead of “Not computed”; they never display an old selection as a current result. The shared status announces “Updating predictions…”. Expired prediction processes reload the saved surrogate automatically without sampling. Once the request finishes, genuine coverage gaps and errors remain explicit.

Response plots retain isolated estimated points and deduplicate identical calculated coordinates. Discrete inputs remain point samples; no line is invented between calculated values. Near-constant responses use a minimum display span of 0.01% of their magnitude, with explicit axis labels; raw values remain unchanged. This is an axis presentation rule, not an error tolerance or a claim of physical constancy.


## Response plot refinement (approved 2026-10-17)

The [response plot recipe](components/AnswerExploration.md) adopts full-width plots
below the output title/readout, quiet axes, a redundant selection halo and explicit
reference-line styling. Selection never overrides Calculated / Estimated basis.
Declared criterion lines remain separate from criterion evaluation; no threshold is
invented and estimates never acquire a recorded run outcome through presentation.
This approval covers graphs only. The prototype's navigation remains a proposal.

The compact answer view foregrounds saved study inputs/outcomes. Intermediate and
connected quantities remain available through Expand model; the full model
workspace retains every quantity. Hiding a quantity is presentation only, never
removal from a calculation, physical constancy, or a change to its result basis.

The calculation explorer's **Inputs** selector distinguishes an explicit **Sample centre**
(the mean of the retained training vectors, snapped to declared steps and linked mappings)
from **Calculated point** selections. The centre is only a starting selection: the native
predictor still decides coverage and output eligibility. It is never labelled calculated.
Reset inputs restores the reference configuration's exact assignments. No saved record changes.


### Prepared joint exploration

Publishing an answer with interactive exploration requires full joint domain support and
passing independent assessments for every displayed output in every group. Preparation
errors name the missing coverage or failed output check and preserve the draft. A saved
surrogate's general completion state is not an all-output readiness claim. Calculated and
estimated retain their existing shapes and colours; readiness never implies physical validity.
Changing a slider evaluates the saved surrogate, with the existing brief updating state.
A fixed requirement remains visibly assigned and cannot masquerade as a sampled slider.
Historical answers may retain incomplete exploration and their original unavailable reasons.

The answer-explorer legend shows “no result” only when a displayed output or curve point
has no value. Loading is “Updating”, not “no result”. Failed execution, unsupported bounds
and missing outputs remain representable; preparing joint coverage does not erase them.

RecordState uses the same labels for every versioned primitive, including embedded
explanations: New draft, Saved draft, Unsaved changes, and Read-only.
Never insert the primitive type into a persistence label; its owning title supplies
that context. Each record shows its own state independently of its parent.
Publication never implies physical validation.
