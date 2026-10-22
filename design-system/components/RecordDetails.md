# RecordDetails

One metadata action for every record, including embedded readers and scientific-context dialogs.

**Position:** a dedicated left-aligned metadata row immediately below the owning record's title, before prose, tabs, graphs or tables. Show its saved/draft state and attribution in that row when available. Never place record details among export/edit/run actions, in an overflow menu, beneath long content, or inside a collapsed interpretation section. An embedded record uses its own title and row; a parent action never substitutes for the child's identity.

**Trigger:** the shared `RecordDetails` component renders a small `OpenLink` with the underlined label **Record details** followed by the shared inclined arrow. Its accessible name is **{Record type} record details**. Use sentence case, the standard small-button focus/hover/touch recipe and token spacing. Status remains noninteractive; details is a separate action. The row wraps naturally and stays in document flow at narrow widths and 200% zoom.

**Dialog:** title **{Record type} record**; saved models retain the precise title **Model version record**. Use the shared dialog with Escape, labelled Close, Done and focus return. Identity/value pairs use `hf-record-details`, long identifiers wrap, and serialized content scrolls locally. Keep exact values, pins, attribution and historical bytes; do not substitute current records. No redundant explanatory sentence is required.

Supported types: Model, Configuration, Run, Approach, Method, Study brief, Study answer, Evidence, Prediction. The metadata slot accepts status/attribution; scientific outcome controls remain separate. If no record exists, omit its action. Prediction details belong at the start of the result-basis reader, below its title. Compact evidence references expose details inside the full evidence reader, directly below its title.

Enforcement: screen code uses `RecordDetails`, never bespoke record-detail `ActionDialog` or `summary` triggers. The component-ownership check rejects those alternatives and screen CSS overrides. Browser acceptance checks placement, accessible naming, exact content and focus restoration on representative page and embedded records. This rule supersedes earlier placement descriptions in Layouts, Scientific-states and Naming.

## Record identity and order (owner amendment)

Immediately below the owning title: **Record details first at the left**, then any
noninteractive storage state and attribution. Canonical IDs belong inside the details dialog,
never beside its trigger. Version selectors may distinguish immutable choices by ID. Keep exact
pins unchanged in API data and exports. Omit repeated version prose, identifier-based headings
and IDs in ordinary reference links.

Page heading action groups stay top-aligned and occupy at most half the desktop header, wrapping their own controls. Below the shared narrow breakpoint, actions use the full row. Loading run readers use the same RecordDetails identity row; attribution alone never creates an empty paragraph.

Model explanation uses this same row, including its exact explanation/model identities
and authorship. Its storage state names Explanation explicitly so it cannot be confused
with the executable model's state. Unsaved text is not labelled Saved draft.
