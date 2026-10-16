# Answer exploration

The canonical GraphCanvas accepts per-port content from an answer-bound exploration.
Model topology and identity still come from GraphView.project; the graph owns geometry.

`AnswerExplorationPanel` owns the category header, top-right Sample settings and
bottom-right Open model action. `InterpretationPanel` follows it with saved prose
and qualifications. Overview has no method or supporting-result inventory; Inspect
answer basis opens the whole answer's actual pins in Scientific context.

Exploration uses the canonical node's two bounded port columns: all free input
controls remain reachable in the left column while output values stay in the right.
Each column scrolls independently; native keyboard focus reveals its control. The
first output response is expanded, and every other output can expand its response.
The graph's zoom and scroll remain local; component and port identities never change.
This recipe is identical for every model and contains no study-specific layout.

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
  The selected marker uses the selected API result even between curve samples.
  Axes show quantity names, units and numeric ticks; zero is marked only within the
  displayed range. The accessible summary retains numeric values.
- Sample settings owns input-design saving, range/step declarations, budget and error
  targets, preview/prepare and sampling progress/cancel/reconcile/resume. Original-model
  calculation remains in that dialog. Selecting
  a point performs no calculation or training. Result details expose exact provenance.
  Explicit completed/total counts use Progress; warming remains indeterminate.
  A sample count never represents an overall elapsed-time percentage.

Existing one-axis prepared results are eligible only on their original complete
fixed-input slice. A changed second input invalidates those estimates, even if focus
returns to the old axis. Unavailable joint predictions remain Not computed until
the separate assessed-surrogate capability supplies them.
