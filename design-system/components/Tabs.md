# Tabs

Switches between sibling views: underline tabs for page sections, a segmented control for views of the same thing.

- **Underline** (default): record views such as the run tabs (Results, Model, Configuration). The selected tab is `accent` with a 3px rule. With `navigation`, controls act as page navigation; WorkflowNavigation supplies Overview, Models, Configurations, Runs and Cases with aria-current.
- **Segmented** (`variant="segmented"`): view switches over one object, such as the model views **Graph · XDSM** or the Home list **Studies · Archived**.
- **The consumer provides** `items` (`id`, `label`, optional `count`, optional tab and panel IDs), the selected `value`, `onChange`, and an accessible `label`. Keep labels to one or two words. Wire the tab panels with `aria-controls` in the page.
- Keyboard: Left/Right move between tabs, Home/End jump to the ends.
- Never use tabs for steps in a process; use a sequence of sections instead.

Labels wrap inside the owner; no negative outer margin or clipped hidden label. View tabs use one roving tab stop and Left/Right/Home/End; navigation destinations remain independently tabbable. DetailTabs is a compatibility export with a specimen, not the current continuous model inspector.
