# Criteria

Criteria are structured scientific requirements on computed outputs, distinct from optimizer constraints and applicability conditions.

`CriterionRecord` renders the same compact numbered record for a draft summary, a saved configuration and the configuration a run used. It owns presentation only: consumers resolve names from the exact model version and supply the comparison wording and any saved criterion evaluation (`evaluation` prop). The component does no fetching, comparison, unit conversion or evaluation.

- **Hierarchy.** "Criterion 1" and, when supplied, its stored outcome; target component and quantity; the comparison in words followed by threshold and units. Equality adds absolute and relative tolerances. Optional evidence uses direct "View evidence" actions. A single border separates the record from surrounding content; no nested cards or repeated field labels.
- **Draft.** Summarises the current local values; a null threshold or tolerance reads "unassigned" and a null target reads "Choose output". A dedicated "Edit" action sits in the Criteria section header. Editing keeps exact numbers; the summary never changes them.
- **Saved.** No outcome is shown unless the caller supplies one: no success colour and no invented "Not evaluated" merely because a configuration exists.
- **Evaluated.** The `StatusTag` keeps shape + word + colour. The caller supplies the stored outcome and reason independently of execution completion. The actual value is optional: an explicit null reads "not computed", zero reads `0`, and an omitted value creates no empty row. An outcome is never inferred from formatted numbers.
- **Precision.** Display uses the shared `formatNumber` helper (three decimals, scientific notation for small nonzero values). A "Full-precision values" dialog shows the untouched threshold, tolerances and any supplied actual value. Relative tolerance has no physical unit; absolute tolerance uses the criterion units; blank units are dimensionless.
- **Evidence.** Pass the shared evidence references as the evidence slot; no separate attachment dialog or request.
- **Layout.** Token spacing and intrinsic wrapping in both themes and at narrow or zoomed widths. Heading with status, and comparison with value, wrap together; evidence text never forces fixed row heights. Each record is an article labelled by its numbered heading. Dialogs have scoped names, standard focus restoration and keyboard dismissal.
