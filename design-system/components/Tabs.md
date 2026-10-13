# Tabs

Switches between sibling views: underline tabs for page sections, a segmented control for views of the same thing.

- **Underline** (default): the study sections (Overview, Models, Configurations, Runs, Evidence) and the run tabs (Results, Model, Configuration, Evidence). The selected tab is `accent` with a 3px rule. With `navigation`, tabs act as page navigation.
- **Segmented** (`variant="segmented"`): view switches over one object, such as the model views **Graph · XDSM** or the Home list **Studies · Archived**.
- **The consumer provides** `items` (`id`, `label`, optional `count`, optional tab and panel IDs), the selected `value`, `onChange`, and an accessible `label`. Keep labels to one or two words. Wire the tab panels with `aria-controls` in the page.
- Keyboard: Left/Right move between tabs, Home/End jump to the ends.
- Never use tabs for steps in a process; use a sequence of sections instead.
