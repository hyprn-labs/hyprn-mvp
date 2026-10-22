# NavigationRail

The application sidebar follows the owner-selected reference navigation structure,
with HYPRN destinations and tokens. The shared component owns every row, icon,
spacing, active state, collapse behavior and footer. It uses independently authored
SVG icons and the supplied HYPRN logo; no external assets or application code.

Order: compact brand and Collapse menu; Home; current study card; Overview;
**Workflows** (Models, Calculations); **Library** (Evidence, Documents); flexible
space; Help, Settings; the signed-in account and Sign out. Home has the same brand,
return and footer structure without study-specific destinations. The account name
is the signed-in identity, shown but not a destination: Settings is the one way to the account and appearance page, whose title is Settings.

The desktop rail uses navigation-width (224px), or navigation-collapsed-width
(64px) when collapsed. It fills the available viewport height, with its footer at
the bottom and internal scrolling when required. At small phone widths an expanded
rail stacks above the canvas. A collapsed rail retains icons, tooltips, accessible
names and current-page semantics. Collapse is a local presentation preference;
it never changes routes, guards, model selection or pending commands.

All routes, including placeholders, pass through the existing unsaved-work guard.
Documents and Help are real navigable destinations with a shared
`FeatureUnavailable` surface stating “This functionality is not implemented yet.”
They have no pretend data, upload control, counts or fabricated backend behavior.
The Evidence library remains functional. Counts are omitted until an authoritative
complete count is available. Placeholder links can be reloaded and preserve study
context. This explicitly supersedes the earlier ban on visible unimplemented
destinations in WorkflowNavigation; user authorization is dated 2026-10-17.

Home always opens Studies, including from Settings and Help. On Studies, Home is
a noninteractive current-location marker, not a redundant button. Home uses a
house icon; Overview uses a four-pane dashboard icon. Visible labels, tooltips,
accessible names and destinations stay identical in expanded and collapsed modes.
There is no hidden return-to-study meaning attached to Home.

The menu toggle uses the shared PanelToggle chevron, pointing left while expanded (collapse action), right while collapsed (expand action). Direction describes the action, not a static decoration.
