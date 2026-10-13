# Readout

A number with its unit and the basis it rests on: the way key results are shown on a run's Results.

- **The consumer provides** `label`, `value`, `unit`, `basis` (`computed`, `measured`, `sourced`, `inferred`) and `source` (the run or cited location).
- A `null` or empty value renders "not computed" in words. Never pass `0` for a missing output.
- `inferred` readouts show their basis line in `ai`; use them only inside or next to an `InferenceBlock`.
- Large readouts (`readout-lg`) are for at most four key outputs per view; use `size="sm"` inline and in summaries.
- Numbers display with up to three decimal places, in scientific notation below 0.001 or at and above 1e9, and a nonzero value is never shown as zero. Full precision stays in the "Full-precision values" dialog (and a "Full precision: …" tooltip) and in untouched exports; input editing, authored code, thresholds and comparisons stay exact. Labels wrap without uppercasing quantity names, and units wrap below values when needed.
