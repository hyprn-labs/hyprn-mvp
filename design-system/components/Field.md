# Field

An explicit scalar input with its unit, state and provenance: the building block of every configuration.

- **The consumer provides** `label` (the quantity symbol, rendered in monospace), an optional `meaning`, `value`, `unit` or `units` (compatible units only), `state`, `message`, `provenance`, and `onChange` / `onUnitChange`.
- **States.** `assigned`; `unassigned` (blank: advisory, placeholder "unassigned", never a default); `invalid` (alarm border and a message naming the problem and the fix); `readonly` (a saved configuration, shown on `surface-sunken`).
- **Zero is a value.** Pass `0` as assigned; when the user types it, say "0 is an explicit value and will be used as given." A blank value is never tagged as assigned or saved.
- **Units.** Offer only compatible units. When a conversion happens, the message shows it: `150 % → 1.5 (1) · factor 0.01`. An incompatible unit is `invalid` and the message names the declared unit and the compatible ones.
- **Compact.** Inside a labelled table, `compact` keeps the input's accessible label, the unassigned placeholder and the invalid state and message, but drops the repeated label and tag above the input. Zero is then explained once beneath the table, so rows keep an even height.
- Read-only fields keep exact values. The Configurations layout puts all inputs above the fold.
