# Answer exploration

The canonical GraphCanvas accepts per-port content from an answer-bound exploration.
Model topology and identity still come from GraphView.project; the graph owns geometry.

- QuantitySlider selects an existing prepared query point, with keyboard and numeric
  entry. An unprepared value remains explicit and is never clamped or interpolated.
- QuantityResult shows Estimated (approximation mark), Calculated, or Not computed
  with the shared status shape and wording. Missing results never become zero.
- ResponseCurve draws dashed estimated segments, leaving gaps for unavailable values,
  and separate filled calculated markers. A hollow cursor identifies an estimate.
  Axes show quantity names and units; the accessible summary retains numeric values.
- Sample settings owns preparation selection and original-model calculation. Selecting
  a point performs no calculation or training. Result details expose exact provenance.

The first tracer supports one declared axis and already prepared query points. Other
free inputs remain visible as fixed values. This is an explicit temporary limitation;
the all-input joint surrogate and categorical controls belong to subsequent tasks.
