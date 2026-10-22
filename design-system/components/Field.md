# Field

An explicit scalar input with its unit, state and provenance: the building block of every configuration.

- **The consumer provides** `label` (the quantity symbol, rendered in monospace), an optional `meaning`, `value`, `unit` or `units` (compatible units only), `state`, `message`, `provenance`, and `onChange` / `onUnitChange`.
- **States.** `assigned`; `unassigned` (blank: advisory, placeholder "unassigned", never a default); `invalid` (alarm border and a message naming the problem and the fix); `readonly` (a saved configuration, shown on `surface-sunken`).
- **Zero is a value.** Pass `0` as assigned; when the user types it, say "0 is an explicit value and will be used as given." A blank value is never tagged as assigned or saved.
- **Units.** Offer only compatible units. When a conversion happens, the message shows it: `150 % → 1.5 (1) · factor 0.01`. An incompatible unit is `invalid` and the message names the declared unit and the compatible ones.
- **Compact.** Inside a labelled table, `compact` keeps the input's accessible label, the unassigned placeholder and the invalid state and message, but drops the repeated label and tag above the input. Zero is then explained once beneath the table, so rows keep an even height.
- Read-only fields keep exact values. Configuration tables retain their full input/provenance rows and scroll naturally. Numeric configuration fields align right in both editable and read-only states; saved fields retain their sunken surface.

Catalogue unit editors and their labels use shrinkable grid tracks. A native input’s
intrinsic width must not enlarge or overflow its table cell; the surrounding table
owns horizontal scrolling at narrow widths and browser zoom.

The shared label/input gap and field spacing come from Foundry. Errors are associated with aria-describedby and aria-invalid; disabled controls preserve visible reason text. Local appearance choices use SettingsSection/Select and never mutate scientific values. Wrapped labels and coarse-pointer control targets remain readable in both themes.

## Narrative form fields

Use `FormField` for ordinary labelled text controls in brief and analysis editors.
It owns the label/control spacing and appends a muted `(optional)` marker when
`optional` is true. Keep optional Description and Scope fields visible; optionality
is not a reason to put a field behind a Disclosure. Brief alternative descriptions
and reasons use this same treatment. Required labels have no optional marker.
Pass one control as the child and retain its stable accessible name. This wrapper
changes presentation only, never validation, defaults or persisted values.


### Editable mappings without repeated names

Use DataTable with **Output** and **Requirement** columns to map brief criteria
onto model outputs. Each output is a native Select. Show the quantity name alone
unless offered names collide; then include the component name to disambiguate.
Requirements include operator/direction, threshold when applicable, and units.
An unassigned row names the intended criterion in its selection prompt. Stable
accessible labels preserve criterion identity. Do not repeat the criterion name
above its selected output, or substitute a component-only summary for the output.
Presentation never changes the saved criterion, mapping or unit compatibility.

## Compact form cards

Use `Panel` with `hf-panel--compact` for short, related control groups. It keeps the
sunken surface and header divider, with space-3 header/body padding and inner gaps.
Its FormFields reset legacy label/control margins so spacing is applied once.
Use `hf-form-grid` with `--pair` for mode/value and `--triple` for short numeric
settings. Columns share available width, labels wrap, and controls align at the bottom.
Control sizes, accessible names, values and validation stay unchanged. Keep space-4
between cards; compactness comes from the interior, not loss of group separation.

### Editing dialogs

DialogFrame and ActionDialog share the compact rhythm in Foundry: space-4 shell
padding, space-3 between fields, and space-4 between sections/actions. Existing
form grids keep their columns; control heights and text-area minimums are unchanged.
Grid/flex labels remove legacy margins so the declared gap is applied once. Plain
stacked labels retain one field gap. Editable nested Panels use the compact card
padding while keeping their header divider and surface; repeated quantity groups
retain a divider and section gap. Do not add page-specific spacing overrides or
hide fields to achieve density. Reading content, validation, focus, save and cancel
behavior remain owned by their existing components.

Use `hf-form-readonly` on a disabled form group when inspecting saved settings.
Unlike unavailable editing actions, saved values retain normal text contrast on the
sunken surface. Select arrows are omitted; native disabled semantics still prevent
changes. Pair it with the shared saved-record state and an explicit revision action.

Read-only choice cards keep their selected treatment and normal contrast while
remaining disabled, so the saved choice explains the fields shown underneath.
