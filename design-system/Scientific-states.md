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

Displayed numbers use up to three decimal places, with scientific notation below 0.001 or at and above 1e9; a nonzero quantity is never rounded to a displayed zero. Full-precision values stay available in a "Full-precision values" dialog and in exports; editing, thresholds and comparisons always use exact values.

## Run headline

A run's headline shows only the outcome facets the runtime actually computes: **Execution** and **Criteria**, each with its own `StatusTag`, never merged into one badge or a confidence score.

| Facet | ok | warning | alarm | advisory | inert | running |
|---|---|---|---|---|---|---|
| Execution | Completed | Finished · results unavailable; Needs review | Failed; Preparation failed | Results unavailable; Unknown | Queued; Ready to start | Starting; Running |
| Criteria | `M of M met` | — | `N of M not met` | `N of M not evaluated`; Not evaluated | None defined | — |

- "Recorded" describes storage only; it is never shown as a successful execution or a met criterion. A state the reader cannot confirm reads "Unknown" or "Status unavailable", never success.
- Several criteria get one count summary; each criterion's own outcome stays with the configuration the run used.
- Convergence, optimization termination, constraints and feasibility, sample completeness and applicability are recorded separately and stay separate in the stored run and its exports. They are not shown in the headline while the runtime produces only constant values for them, and they return to the headline when a numerical method computes them. A finished optimizer is then a termination fact; it does not mean a criterion is met. "Not applicable" (inert hollow circle) is a valid answer and is shown, not hidden.
- Per-output availability stays visible in the outputs table ("not computed").
- Execution completion never means a criterion is met or the result is scientifically valid.

## Ensembles

Show `k / s` meeting a criterion over evaluable samples only when `s > 0`, the unresolved count over generated `N`, and, if shown, the bounds `[k/N, (k + N − s)/N]` labelled "bounds over generated samples — not a confidence interval". Unavailable analyses (for example Sobol indices with dependent inputs) appear as an inert panel that names the reason.

## Basis of a claim

- **Computed**: a `Readout` or inline fact linking to the run that produced it.
- **Sourced**: a `SourceChip` opening the exact cited location.
- **Inferred**: the word "Inference" in `ai`, inside an `InferenceBlock` or inline; never styled like a computed value.

## Progress

Use measured counts ("1 of 2 components evaluated", "9 of 50 iterations") or an indeterminate track with the stage in words ("Queued — waiting for a worker"). No percentage or remaining time is invented. Cancellation shows "Cancellation requested" until the worker confirms it. An uncertain outcome is an explicit warning, never a running track.
