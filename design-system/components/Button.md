# Button

One component and one complete recipe per size, independent of page or variant.
Primary appears at most once per view for its main action. Use the typed API; old
`primary`, `quiet` and `link` class aliases are not supported.

| Size | Minimum height | Type / line | Horizontal / vertical padding | Icon | Icon-label gap |
|---|---|---|---|---|---|
| desk (default) | 36px | 14px / 20px, 600 | 16px / 4px | 18px | 8px |
| sm | 28px | 12px / 16px, 600 | 12px / 4px | 16px | 4px |
| floor | 48px | 14px / 20px, 600 | 24px / 12px | 18px | 8px |

Height is a minimum, never a clipping box. Labels wrap and the control grows.
On coarse pointers all button sizes have a 48px minimum; typography retains the
chosen size. Icon-only controls are square at the size's minimum, with 4px padding
and a meaningful aria-label. Icons remain decorative.

Variants do not change geometry: secondary (default), primary, quiet, danger and
ai. Quiet commands are not underlined. Content navigation uses `OpenLink`: an
underlined label and visible inclined arrow in one sized keyboard/touch target.
The arrow-only presentation requires an accessible name. `ReturnLink` uses the
back arrow. See [Coherence](../Coherence.md) for reader/action distinctions and exemptions.
Use `align="start"` for left-aligned labels and `stacked` for matrix/card actions
with several lines. Do not introduce page CSS to simulate a new size.

Compact evidence, record and dense-row actions use sm. Ordinary form and page
commands use desk. Floor is for explicit shared/touch displays. Primary/secondary
pairings within one action group use the same size. `ActionDialog` passes its size
to its trigger; dialog completion and close controls use desk.

- Disabled: inert with 45% opacity, no hover change; explain unavailability nearby.
- Focus: blue 2px outline, 2px offset; the inverse record bar uses focus-on-record.
- Pressed: accent-soft ground and accent border; colour is not the sole indicator.
- Danger: only inside a confirmation naming the affected resource.
- AI: only for applying an assistant proposal. Brand orange never marks controls.
- The workspace assistant launcher uses the floor recipe with radius-sm, accent /
  on-accent and shadow-float. A chat-outline icon accompanies the visible Assistant
  label, matching the approved design preview without its preview-only badge. It has
  an Open/Close assistant accessible label and tooltip, independent of page actions.
- Use ActionGroup for aligned, wrapping actions with an 8px gap. SectionHeader
  composes headings/actions; page layout can position the group, not resize buttons.

The source toolbar uses compact controls. Model header order remains version
select, Save model version, Create configuration, Model actions. Candidate source
import and destructive confirmations retain their existing safeguards.

Contour uses radius-sm (12px). Shell, card, settings, inspector, evidence and dialog contexts do not alter a size recipe. Full labels and semantic names survive wrapping, both themes and 200% zoom. Reduced motion removes transition animation.

Expandable controls obey the same vertical centering contract. Native selects
reserve room for the text line plus equal block padding inside their control
height. Disclosure summaries use a flex row with centered text and a decorative
chevron, retain native keyboard/open semantics, and grow when text wraps. Button
boxes align to the middle of adjacent inline content. Screens never compensate
with text offsets, padding overrides or line-height hacks.

Native Select uses one shared shell with a decorative, noninteractive chevron inset by space-3 and space-8 + space-2 reserved at the text end. It preserves native options and keyboard semantics, including unit selectors. Disclosure arrows have shared inline padding. Never rely on platform arrow placement against the border. PanelToggle is shared by navigation, assistant and details: left sidebar collapse points left and expand right; right-side reader expand points left and restore right.
