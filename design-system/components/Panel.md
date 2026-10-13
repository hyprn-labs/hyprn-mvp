# Panel

The one container: a `surface` with a `line` border, `radius-md`, an optional header row and `space-4` padding.

- **The consumer provides** `title` (a `subheading`, sentence case), optional `actions` (quiet buttons such as "View all runs", right-aligned), an accessible label and the body.
- `tone="sunken"` makes a well for criteria, read-only summaries and code inside another panel, never a third raised layer.
- Panels have no shadow and never nest inside each other; group content inside a panel with hairlines and `subheading`s (`SectionHeader`).
- In the model workbench the components list, canvas and details are panels separated by `space-3`.
