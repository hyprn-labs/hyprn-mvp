# Design system

The design system is the interface language of HYPRN MVP, a workspace where engineers build computational models, run them and decide what the results are worth. It is built for industrial engineering work: plant and process engineers, techno-economic analysts and the assistants that help them. The interface behaves like a well-made instrument. It stays quiet when things are normal, is precise about numbers and is explicit about where every value came from.

Read this file, [Layouts](Layouts.md) and [Scientific states](Scientific-states.md) before any UI work, then [Naming](Naming.md), [Coherence](Coherence.md) and the per-component notes in `components/`. The colour, type, spacing, radius, shadow and size values live in [`tokens.json`](tokens.json).

[Contour](Contour.md) is the current visual authority for typography, curvature, surfaces and shell composition; it supersedes conflicting legacy visual descriptions in Layouts and component notes. Scientific meaning, entity ownership and interaction contracts remain binding.

## Principles

1. **Grey is normal; colour asks for attention.** Following high-performance HMI practice (ISA-101), the resting interface is neutral grey and charcoal ink. Colour appears only to mean something: `accent` for what you can act on, `alarm` / `warning` / `advisory` for what needs attention, `ok` for a recorded success, `trace` for provenance, `ai` for assistant-originated content. Never colour a block to make it look nicer.
2. **One meaning per hue, everywhere.** A hue never changes job between screens. `trace` never marks a button; `accent` never marks a status; `ai` never appears on content a person typed or a run computed.
3. **Every state is redundant.** Status is shape + word + colour, never colour alone (alarm diamond, warning triangle, advisory square, ok circle, inert hollow circle). It has to survive colour-blindness, glare on a plant-floor screen and greyscale printing.
4. **Numbers are first-class.** Values are set in `readout` (the system monospace, tabular figures), units sit beside them in `ink-muted`, and missing values are words ("unassigned", "not computed"), never blanks or zeros.
5. **History is visibly frozen.** Whenever a past run or version is open, the `record` bar spans the workspace. Nothing else in the product uses that inverse band.
6. **Scientific meaning first.** Screens lead with human-readable context, quantities, claims and sources. Exact identities, hashes and serialized records are secondary, in Record details (see [Coherence](Coherence.md)).

## Content fundamentals

- Write in plain engineering language a reviewer would accept: "Run this configuration", "Save model version", "Not converged after 5 iterations". No marketing tone, no exclamation marks, no emoji.
- Address the user as "you" only in help text. Labels are sentence case: "Create modified run", not "Create Modified Run".
- Name things by what the engineer recognises (study, model, component, quantity, configuration, run, evidence, assumption), never by service, storage or database terms. Reader-facing text avoids implementation words such as "retained", "exact", "recorded", "attested", "frozen", "digest", "snapshot" or "worker"; saved states are versions, hashes are labelled "SHA-256", and exact identities belong in Record details. [Naming](Naming.md) lists the reader-facing names.
- Errors say what happened, where, and the next safe action: "Line 3 — “q” is not defined here. Available: x, z. Your edits are kept."
- Be explicit about blanks and zeros: "Blank values are missing; zero is an explicit value."
- Mark every claim's basis: computed (links to a run), sourced (links to a cited passage) or inferred (labelled "Inference"). The assistant never presents an inference as a fact.
- Identifiers and numbers: short IDs are display-only and labelled; SI units with a space (`12.5 kPa`); 24-hour ISO dates (`2026-10-09 14:20`); scientific notation as `1e−10` in `code`.

## Visual foundations

**Colour — Charcoal (approved Option B).** Interaction uses charcoal on light surfaces and light neutral ink on dark surfaces. Blue is reserved for visible keyboard focus, separate from selection. Quiet action links are underlined; primary and secondary controls retain their button boundaries. Build every screen on `canvas` with `surface` panels and `line` hairlines. Text is `ink` (values, titles), `ink-2` (body) or `ink-muted` (metadata and units). Use `accent` only for interaction: the single primary button per view, links, the active tab and selection (`accent-soft` fill + `accent` border). Status colours follow alarm priority: `alarm` (priority 1: failed, violated, invalid), `warning` (priority 2: not converged, partial, stale, needs review), `advisory` (priority 3: unassigned, not evaluated), then `ok` for recorded success and `inert` for not applicable. Never show a live "normal" state in green. A banner uses the `*-soft` ground with the matching text token. Text on a filled `accent`, `ai` or `alarm` button uses `on-accent`, `on-ai` or `on-alarm`, never literal white. Two themes exist: Day (light) and Control room (dark); every screen works in both.

**Type.** Audited self-hosted Manrope (200–800) with system fallback supplies interface text and dense table labels. System monospace with tabular figures remains mandatory for quantities, units, identifiers and source. See [Contour](Contour.md). One title per page; uppercase only for label and table-head roles.

**Space and density.** 4px base: `space-1` to `space-12`. Panels pad `space-4`; workbench panels sit `space-3` apart; sections separate by `space-6`. Pages use the `page-gutter` (28px) on desktop and narrower gutters on small screens. Controls are `control-desk` (36px) by default and switch to `control-floor` (48px) on touch or shared displays. Tables use `row` (36px) or `row-dense` (28px) for variable and sample tables. Button sizes are complete recipes in [Button](components/Button.md); their height grows for wrapped labels. The XDSM view uses a `space-12` matrix pitch.

**Shape.** Contour uses radius-xs for chips, radius-sm for proportional controls, radius-md for working panels and radius-shell for the central canvas. Shared shadows distinguish floating and raised surfaces; sunken wells remain shadowless. Status shapes remain unchanged.

**Surfaces.** Neutral shell-ground frames the canvas; raised panels use surface-raised and shadow-panel. Sunken values/code wells use surface-sunken without elevation. Static texture and restrained neutral gradients belong only to shell chrome, never over scientific text or data.

**Focus and states.** Every focusable element shows a 2px `focus` outline offset 2px; elements that clip outlines use `focus-ring`. The inverse record bar uses `focus-on-record`, a contrasting blue in both themes. Hover changes `accent` to `accent-hover`; disabled is 45% opacity with the reason stated nearby. Selected = `accent-soft` fill + 2px `accent` edge.

**Assistant content.** Proposals sit in an `InferenceBlock`: a dashed `ai` border, an `ai-soft` header, the word "Proposal" and its status. The assistant's mark is a solid `ai` square with an iris glyph. Neutral shell-chrome gradients follow Contour; assistant and scientific semantic colours retain their dedicated meanings.

**Motion.** Only for state change: 120ms ease-out for hover and selection, 200ms for panels opening. The running indicator is the only loop. Respect `prefers-reduced-motion`.

**Charts.** Faint `line` grid, data in `accent`, thresholds and tolerances as dashed `ink-2` lines labelled in words, violations as `alarm` marks with a shape. Log axes say so. Mock or illustrative histories carry the "Illustrative data" tag.

## Iconography and wordmark

Icons are small inline SVGs drawn independently for HYPRN MVP on a 24-unit grid (`ActionIcon`: close, back, add, import, export, chevrons, search) and passed to components as React nodes. No icon font or icon library is loaded. Icons always sit beside a word, except icon buttons, which carry an `aria-label`. Status marks are drawn shapes from the `StatusTag` component, not icons. The components' built-in glyphs (lock, return arrow, document, iris mark, basis glyphs) are inline SVGs too.

The approved stacked HYPRN logo is `ui/src/design/assets/brand/hyprn-stacked-color-on-light.png`, supplied by the product owner and used unchanged by the shared `BrandLogo` component without a duplicate text name. Screens import the component from the design entry point. Vite owns the hashed, base-aware asset URL; the source asset is never duplicated under public. Asset inlining is disabled for the self-only CSP. `brand-ink` and `brand-signal` document the asset colours; its orange signal also informs the dedicated estimated-result palette described in Scientific-states.md. Use `brand-ground` for a small light plate in both themes, independent of button `on-accent`. Do not recolour, redraw or introduce another lockup.

**Source syntax.** `syntax-keyword` is neutral ink with body-strong weight; `syntax-string` and `syntax-number` use secondary ink. Comments use muted ink. Syntax is neither a warning, successful result nor interactive element. All source readers/editors share these roles.

**Export palette.** Standalone SVG/PNG/HTML diagrams retain their existing fixed print palette in the single export renderer (`ui/src/exports.ts`). It provides a stable white-ground document independent of application theme. This change does not recolour old or new exported diagrams. Any future export palette revision must be centralized and separately verified.

## Implementation

The complete export, consumer, recipe and state inventory is maintained in [Contour](Contour.md). Workspace composites live in workspace.tsx; reading compositions in compositions.tsx; numerical presentation in exploration.tsx. The implementation is the typed React port in `ui/src/design`: `components.tsx` (AttributionChip, Panel, Tabs, Button, Field, DataTable, ModelNode, StatusTag, Ledger, Readout, SourceChip, InferenceBlock, RecordBar), `primitives.tsx` (ActionIcon, CriterionRecord, TextInput, TextArea, Select, Checkbox, Disclosure, DialogFrame, SectionHeader, ActionDialog, DetailTabs, FilePicker, Progress), `graph.tsx` (GraphCanvas), `source.tsx` (SourceSurface), `numbers.ts` (`formatNumber`), `foundry.css` and the generated `tokens.css`. `ui/src/main.tsx` imports `tokens.css`, then `foundry.css`, then the screen styles once. Compose screens only from these exports; never introduce a colour, size or radius that is not a token.

Implementation rules:

- No inline style attributes; component styling lives in `foundry.css` classes.
- `Field` never tags a blank value as assigned or saved: `null` or `''` shows the advisory "unassigned" tag (unless invalid) and a blank read-only value reads "unassigned" in `ink-muted`. `0` stays an assigned, explicit value.
- `Tabs` support Left/Right/Home/End keys, so unselected tabs stay reachable with the roving tab index.
- `Readout` small size also shrinks its "not computed" words.
- Type sizes use the `--type-*` tokens. A few fixed component measurements with no token (for example the graph node width, panel header height, status mark size and tab label size) live in `foundry.css` only.

## Tokens and checks

`tokens.json` is the single source of the token values. `python3 ui/design_tokens.py` generates `ui/src/design/tokens.css` from it; never hand-edit `tokens.css`, and `python3 ui/design_tokens.py --check` fails when it is stale.

[Consistency](Consistency.md) records the shared ownership inventory and acceptance criteria. [Assertions](components/Assertion.md) defines scientific statement/evidence rhythm. `check_component_ownership.py` rejects raw controls, old class aliases and screen-level overrides of button recipes or assertion/evidence/logo internals, without a baseline.

`python3 ui/check_design_system.py` keeps screen code on the tokens. It scans `ui/src/**/*.{ts,tsx,css}` except `ui/src/design/**` for colour literals (hex, `rgb()`/`hsl()` and, in CSS, the white/black keywords), CSS px literals, inline styles (`style=`, `setAttribute('style')`, `cssText`) and font declarations (`font-family`, `font` shorthand, `fontFamily`), and must report no new violations.

- Violations already recorded in `ui/design-baseline.json` print one `WARN` line per file. A key (file, rule, normalised snippet) whose count exceeds its baseline prints `FAIL path:line:rule:snippet` and exits 1; moving lines never fails. A dropped count prints a `NOTE` that the baseline can be tightened. `--update-baseline` rewrites the baseline; use it only when the baseline may legitimately change.
- Exempt: `1px` and `2px` hairline and focus widths, px values inside `@media` and `@container` preludes, the `font` shorthand set to `inherit`, `initial`, `unset` or `revert`, and everything under `ui/src/design`.

`node ui/design_smoke.mjs` renders every component once as a smoke check, and `python3 ui/test_design_tooling.py` tests the tooling. These are developer checks; they are not part of `npm run build` or the served runtime.
