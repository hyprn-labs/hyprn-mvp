# HYPRN Contour

Current visual amendment, authorized 2026-10-15. This supersedes system-font-only, machined-corner, flat two-layer, no-panel-shadow and blanket no-gradient clauses in earlier design rules. It does not change scientific state, public API, guards, exact pins, graph geometry, CSP or accessibility contracts.

## Foundation

Interface text uses original self-hosted Manrope variable font, weights 200–800, with system fallback. Font and original OFL text are audited in ui/src/design/assets/fonts/provenance.json and exposed through Third-party software notices. Quantities, units, identifiers and source retain tabular system monospace. Original logo bytes remain unchanged.

Tokens are authoritative: 6px chip, 12px control, 24px panel, 32px outer working canvas. Controls retain 28px compact, 36px standard and 48px touch minimums and grow for wrapped labels. Scientific marks preserve their shapes.

Shell-ground carries static low-contrast texture. The working canvas separates navigation from content; raised panels use surface-raised and shadow-panel. Sunken summaries, code and values use surface-sunken without shadow. Neutral gradients belong only to shell chrome. Texture never overlays text or plots and carries no interaction or status meaning. Semantic colours remain unchanged.

## Shared ownership

WorkspaceShell owns central canvas and navigation placement through React slots. NavigationRail owns brand, main navigation, current study identity and study-section controls. Neither fetches records, constructs routes or bypasses guards. Workspace supplies registry labels and existing navigate/chooseView callbacks. Desktop navigation stays in a rail; narrow and zoomed layouts stack it above the canvas with wrapping controls and no hidden destinations.

Panel's ordinary surface is raised; tone=sunken is an inset well. Existing scientific component contracts continue to apply. Screens arrange shared recipes and never override their internals.

## Adoption boundary

C1 implements foundations, shared shell/navigation and Home → study navigation. C2 owns settings, cards, contextual statement/evidence readers and adjacent assistant slots. C3 owns the complete component matrix and final ownership/visual qualification. These future tasks are not claimed complete by this foundation.

Automated browser fixtures establish UI behavior with public-API-shaped doubles. Served auth/CSP integration, full qualification, independent review and product-owner acceptance remain separate gates. No deployment is implied.
