# Answer exploration

The canonical GraphCanvas accepts per-port content from an answer-bound exploration.
Model topology and identity still come from GraphView.project; the graph owns geometry.
`AnswerExplorationPanel` owns the qualitative choices, Sample settings and Open model.
Saved conclusions remain distinct from the selected interactive point.

## Response plot recipe — approved 2026-10-17

The response-plot treatment from the study-organization prototype is approved.
Only the separately approved [Calculations grouping](Calculations.md) and compact input controls below are adopted from the later hybrid prototype. Other proposed layouts are not approved.

An output has four vertical levels, with token spacing between them:

1. Output name.
2. Current value and units, with a noninteractive Calculated / Estimated basis label.
3. The response plot, using the full output tile width.
4. One right-aligned Result basis action.

Do not squeeze the plot beside a narrow column of title, value and buttons. Do not
wrap the plot in another card or require a disclosure to see it. Input and output
columns have equal natural height; input rows distribute that height. No internal
component scrolling. The existing diagram supports 25–250% zoom.

### Marks and axes

- Calculated samples: small solid `plot-calculated` circles. In light mode this is
  black; in dark mode it is light ink. Do not connect isolated calculated values
  to imply an evaluated continuous response.
- Estimated samples: small hollow `plot-estimated` circles, orange in both themes.
  Estimated segments use a thin dashed orange line. Gaps in available predictions
  break the line. Preserve isolated estimated points.
- Selection: a neutral outer halo around the point's original basis mark. The
  selected API result owns its value and basis; a nearby calculated sample or one
  at the same abscissa cannot relabel an estimated selection as calculated.
- Axes: quiet horizontal baseline, minimal numeric ticks, and a centered caption
  containing input name and units. Omit the redundant `X:` prefix. Output name and
  units stay visible immediately above the plot and in its accessible summary.
- Scale the vertical axis to the actual displayed response. Do not force zero into
  every plot. Mark zero when it falls inside the range. Preserve the existing
  near-constant display-span floor (0.01% of magnitude); it is not uncertainty or
  an accuracy guarantee. Numbers and criterion comparisons remain unrounded.
- The accessible SVG title retains the available values and output units. A curve
  with fewer than two available abscissae remains explicitly unavailable; a single
  point is not presented as a trend. No invented zero or curve fills a gap.

### Declared reference lines

`ResponseCurve.referenceLines` optionally accepts `{value, label}` entries already
expressed in the output's display units. A thin dashed `line-strong` reference has
an adjacent short label and value; its accessible name includes units. The range
includes the reference so it cannot disappear offscreen. Non-finite reference
values are not drawn; a reference alone cannot fabricate an output plot.

The caller must resolve a real criterion against the selected output and exact
context. Never infer a threshold from the brief, copy a prototype value or silently
convert units in the renderer. No status is computed by this presentation prop.
An estimated value on one side of a line does not become a recorded criterion
evaluation. Dense or coincident limits require a readable shared label, not an
unbounded label stack. Current answer integration does not supply reference lines;
the shared component and specimen support them for a future explicit binding.

## Input and prediction behavior

- QuantitySlider exposes every free scalar input as a native range plus numeric
  entry, in saved assignment units. Range and optional step are explicit design
  declarations. Missing ranges direct the user to Sample settings; blank and
  out-of-range numbers remain visible and never silently clamp.
- Plot against is independent of slider focus and value changes. One full selected
  vector owns all outputs. Curves vary only the chosen axis while retaining other
  coordinates, except declared linked-input bindings. Equal names never create a
  binding; connected inputs remain read-only.
- QualitativeChoice uses pressed-state buttons for at most four declared values,
  a labelled selector for longer lists, and disables unsupported combinations.
  A choice pins its configuration and model version. Only declared compatible
  common keys carry across a switch; category-owned values reset. Category labels
  are not interpolated.
- Slider stops, plots and result labels share basis colours and shapes. Unavailable
  stops use a neutral square. Preserve joint-coverage gaps: never substitute a
  result from another fixed-input slice or silently extrapolate.
- QuantityResult shows Calculated, Estimated (with approximation mark), Not computed
  with its reason, or Updating while the current request is pending. An expired
  prediction process renews from the saved surrogate without rerunning sampling.
  A result for an older selection cannot appear as current.
- Sample settings owns declared input ranges, sampling budget, error targets and
  preparation controls. Selecting a prepared point performs no original-model
  calculation or training. Preparation progress uses actual counts or an
  indeterminate stage; sample counts are not elapsed-time percentages.

The visual recipe is study-independent. No fuel names, heat-load defaults,
criterion values or study-specific card arrangements belong in the shared layer.

## Compact input control — approved 2026-10-17

Keep the input label on the left and a compact editable value/unit box on the
right. The native range sits below, followed by small prepared-point marks and
minimum/maximum labels. Long names and units wrap; numerical entry remains
editable without precision loss. Use the existing calculated/estimated/unavailable
marks and tokens in both themes. Blank, off-step and out-of-range diagnostics
remain visible. This changes presentation only: prepared values, vector selection,
linked inputs, plot-axis selection, prediction renewal and sampling are unchanged.

## Compact answer view — approved 2026-10-17, corrected

`ExplorationFocus` shows every independent input on the left, a central Model / Expand model
control with directional arrows, and selected outcomes in one right column. Both
columns share top/bottom bounds and distribute their rows evenly; rows do not imply
one-to-one physical dependencies. Matching panel surfaces, spacing and headings
make the two sides coherent. All controls remain visible without internal scrolling.
On narrow screens the complete sections stack in reading order.

Explicit linked-input groups share one control; names never imply links. Never hide
an independent input because an older display selection omitted it or it lacks a
prepared range. Preserve unavailable controls/diagnostics honestly. There is no
Fixed inputs section. Only connected inputs and intermediate outputs are hidden.
Expand model reveals the full graph; Collapse model restores the compact
view without changing selections, plot axis, predictions or numerical pins.

Select outcomes saves answer/configuration-bound presentation through the public API.
Authors can promote intermediate outputs. Without saved choices, use criterion and
unconnected outputs (all outputs for a closed cycle). Display changes never sample,
train, change bounds or reset inputs. Historical input selections may select a linked
group representative, but never exclude independent controls.

The action below each output is Why; it opens the existing calculation/assessment
record without choosing the plot axis. Calculated, Estimated and unavailable status
remain explicit beside the value. Units appear once beside each input value; slider
endpoints contain only numbers.

Select outcomes sits immediately left of Sample settings in the panel heading.
Qualitative dimensions are data-driven, individually enclosed fields with an inline
label and their supported modalities. Multiple fields wrap as peers; long modality
lists use a select. Plot against is a compact, bounded-width control aligned with
these fields, not a full-width row. Duplicate input names get component qualifiers;
unique names do not. No study-specific labels or arrangements belong in the UI.
