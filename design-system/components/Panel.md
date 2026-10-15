# Panel

A quiet working surface with a line border, radius-md, optional header and space-4 body padding. [Contour](../Contour.md) owns current geometry and elevation.

- The consumer provides a sentence-case title, optional actions, accessible label and body.
- Ordinary panels use surface-raised and shadow-panel to separate them from canvas.
- tone="sunken" uses surface-sunken without shadow for read-only summaries, criteria and code.
- Group content with SectionHeader and hairlines; use explicit sunken wells instead of arbitrary raised nesting.
- Workbench chrome may change; graph coordinates and scientific data geometry do not.
