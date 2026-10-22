# DataTable

Tabular records (quantities, inputs, samples, evaluations, outputs, files) with numbers right-aligned in monospace and units in their own column.

- **The consumer provides** `columns` (`key`, `label`, `numeric`, `unit`, `missingText`), `rows`, an optional `selected` row index, `dense` and a `caption` for screen readers.
- A numeric cell with no value renders "not computed" (or the column's `missingText`, for example "unassigned") in words.
- Body text uses the `table` style; headers are uppercase `table-head` on `surface-sunken`. Use `dense` (`row-dense`, 28px) for quantities and samples; the default `row` is 36px. Quantity symbols and names keep their exact case; only headers use label styling.
- Wide tables scroll inside their own box; the page never scrolls sideways. Selection is `accent-soft` with an `accent` edge on the first cell.
- Shared cells align at the top for multiline content and errors. The quantities owner may align its read-only rows to the middle; that placement does not alter shared cell padding.
- Right alignment is for numerical value columns only.
- Numeric headings use `hf-th--num` to align with their values. Read-only units use
  `displayUnit` typography (m**2 → m², kg/m**3 → kg/m³), including output tables and
  criterion records. Stored units, editable spellings and exported bytes stay exact.
- Read-only displayed input values use the same up-to-three-decimal formatter as results, with full precision on hover and in Record details. Editable configuration values and saved or exported numbers stay exact.
- File tables keep filename case, wrap long paths and scroll locally on narrow screens; hashes stay in Details.

Default cells use space-2 (8px) vertical padding; dense cells use space-1 (4px). Pass regionLabel for a named keyboard-scrollable wide table. Headers retain their role, while body row headings preserve authored case. Selected, empty and unavailable rows are covered separately in the specimen.

One clipped surface owns the outer boundary and corners. Body row headings and data cells share the same ground; selection fills the entire row, including its heading. QuantityDirection uses the same direction and connected marks as ModelNode. Optional definitions are omitted when all are absent; mixed tables say No definition per absent row. Mutable saved quantity rows offer Edit quantity details through the existing guarded component editor. No blanket absence notice is shown.

## Model quantity row editing

Edit quantity details opens only the selected saved quantity's fields through the existing guarded editor and preview flow. It does not show other rows or add-quantity controls. Component-wide quantity management remains a distinct component action. Keep Show all quantities as the scope escape; omit a second Inspect component action for an already-scoped table.

Table buttons, navigation actions and status badges keep their complete label on one line. Narrow
containers scroll the table horizontally rather than splitting action text.
