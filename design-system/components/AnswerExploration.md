# Answer exploration

The canonical GraphCanvas accepts per-port content from an answer-bound exploration.
Model topology and identity still come from GraphView.project; the graph owns geometry.

- QuantitySlider exposes every free scalar input as a native range plus numeric
  entry, in its saved assignment units. Range and optional step are explicit design
  declarations. Missing ranges disable the range and direct the user to Sample
  settings; blank and out-of-range numbers remain visible and never clamp.
- Focus or a change selects the curve axis. One full selected vector owns all
  outputs. Declared covary groups propagate selections by port identity; connected
  inputs remain read-only. Equal names never imply a binding.
- Category dimensions each have a selector; unsupported joint tuples are disabled
  with a reason. A tuple pins its configuration and model version. Only declared
  compatible common keys carry across a switch; category overrides reset.
- QuantityResult shows Estimated (approximation mark), Calculated, or Not computed
  with the shared status shape and wording. Missing results never become zero.
- ResponseCurve draws dashed estimated segments, leaving gaps for unavailable values,
  and separate filled calculated markers. A hollow cursor identifies an estimate.
  Axes show quantity names and units; the accessible summary retains numeric values.
- Sample settings owns input-design saving, range/step declarations, budget and error
  targets, preview/prepare and sampling progress/cancel/reconcile/resume. Original-model
  calculation remains in that dialog. Selecting
  a point performs no calculation or training. Result details expose exact provenance.

Existing one-axis prepared results are eligible only on their original complete
fixed-input slice. A changed second input invalidates those estimates, even if focus
returns to the old axis. Unavailable joint predictions remain Not computed until
the separate assessed-surrogate capability supplies them.
