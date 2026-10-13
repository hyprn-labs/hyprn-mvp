# ModelNode

A component in the graph view: its evaluation order, name, ports with their connection state, and the definition version it pins.

- **The consumer provides** `name`, `index` (evaluation order), `ports` (`{name, dir, state}`: `connected`, `free`, `output`, `unassigned`), `definition` ("Affine · v1"), `selected`, `status` and `onSelect`.
- **States.** Selected: 2px `accent` border and an `accent-soft` header. `status="incomplete"`: hatched body and "implementation missing", not runnable. `status="proposed"`: dashed `ai` border until the proposal is applied.
- Connections between nodes are drawn by the page in `line-strong` (2px), labelled with the quantity symbol in monospace; feedback connections are dashed. Moving a node is a view preference and never creates a model version.
- Nodes are buttons in evaluation order, so the graph is keyboard-navigable (Tab, then Enter to select). Selecting a node fills the details panel with What it computes, Why and Assumptions.
