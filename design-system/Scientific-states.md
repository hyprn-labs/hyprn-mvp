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

## Run headline

A run's headline shows only the outcome facets the runtime actually computes: **Execution** and **Criteria**, each with its own `StatusTag`, never merged into one badge or a confidence score.

| Facet | ok | warning | alarm | advisory | inert | running |
|---|---|---|---|---|---|---|
| Execution | Completed | Finished · results unavailable; Needs review | Failed; Preparation failed | Results unavailable; Unknown | Queued; Ready to start | Starting; Running |
| Criteria | `M of M met` | — | `N of M not met` | `N of M not evaluated`; Not evaluated | None defined | — |

- "Recorded" describes storage only; it is never shown as a successful execution or a met criterion. A state the reader cannot confirm reads "Unknown" or "Status unavailable", never success.
- Several criteria get one count summary; each criterion's own outcome stays with the configuration the run used.
- Current explicit scalar results record execution, every output with its availability and reason, and criterion outcomes. They omit aggregate convergence, optimization, completeness and applicability fields. Output inventory validation remains strict; unavailable is never zero. Exact frozen historical artifacts retain their original fields, while public read views omit those fields and identify both source and view with canonical JSON hashes. Any future numerical method must define computed facets separately: termination or a met criterion does not establish validity.
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

## Record persistence

Use the noninteractive `RecordState` beside or below the entity title. It describes storage/editability, never scientific success. `New draft`, `Saved draft`, and `Saved version · read-only` use the neutral ring and inert colour; `Unsaved changes` uses the warning triangle and warning colour. Run history uses `Saved run · read-only` with the shared record lock; execution and criteria retain their separate scientific tags.

Record metadata uses compact quiet buttons at the owning card: `Model record details`, `Configuration record details`, `Run record details`, `Case record details`, `Case answer record details`, `Study answer record details`, `Approach record details`, and `Evidence record details`. `Method record` follows the Python function. A case is identified by both its case ID and approach version; an answer is a different versioned record. Do not repeat parent record controls inside child prose.
