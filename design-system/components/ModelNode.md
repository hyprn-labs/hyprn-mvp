# ModelNode

A component in the graph view: its evaluation order, name, ports with their connection state, and the definition version it pins.

- **The consumer provides** `name`, `index` (evaluation order), `ports` (`{name, dir, state}`: `connected`, `free`, `output`, `unassigned`), `definition` ("Affine · v1"), `selected`, `status` and `onSelect`.
- **States.** Selected: 2px `accent` border and an `accent-soft` header. `status="incomplete"`: hatched body and "implementation missing", not runnable. `status="proposed"`: dashed `ai` border until the proposal is applied.
- Model connections are individual measured output-to-input routes, with rounded orthogonal lanes outside card interiors and dashed feedback. Every route has an exact accessible mapping, pointer target and Enter/Space selection. Hover/focus highlights both endpoints without changing selection. Fit includes complete routes. Shared-source junctions alone may receive dots; crossings never do. XDSM retains grouped exchanges; explorer routing retains its separate natural-height branch.
- QuantityDirection supplies teal inlet Input and rose outlet Output marks, split between both roles when connected. Neutral text retains direction and from/to meaning. Nodes and ports are keyboard buttons; selecting one updates the full-width reader below the diagram without scrolling it away.

## Component reading controls

Selecting a node opens its Component / Python / Quantities reader without an additional Read component action. Component-local description is an explicit instance annotation from the shown model snapshot, never inferred from topology or copied from a shared approach method. Edit component combines the name and this optional explanation in one dialog. Python has no component-metadata actions or source expansion toggle.
