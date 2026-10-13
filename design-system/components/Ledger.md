# Ledger

The scientific status of a run, one facet per question, never collapsed into a single badge or confidence score.

- **The consumer provides** `facets`: `{label, value, tone, detail}`, and an accessible `label` ("Run status" for the run headline).
- **Run headline.** Today the run headline passes two facets, **Execution** and **Criteria** (see [Scientific states](../Scientific-states.md)). Other facets (convergence, termination, constraints, sample completeness, applicability) are added only when the runtime computes them; when added, "Not applicable" is a real answer shown with the `inert` tone, not hidden, and a finished optimizer is a termination fact, separate from Criteria.
- A single criterion's Met, Not met or Not evaluated is the primary badge. Several criteria get one count summary (`N of M not met`, `N of M not evaluated`, `M of M met`), with each criterion's outcome in the configuration the run used.
- Put the ledger first on a run's Results, above the outputs. Facet cells sit in a responsive grid (minimum width `panel-outline`) that wraps on narrow screens. Detailed diagnostics live with the run's files, not in a second ledger.
- Lists (Overview recent runs, run history, result pickers) use the compact inline form of the same two facets.
