# Component heading and assistant preview follow-up — 2026-10-16

Implementation: `412d1e5`. Isolated verification tree: that commit. Parent comparison: `d8cd7dd`. No scientific records, public APIs, dependencies, guards or source buffers changed.

The Component tab now owns one name heading, with both edit actions on the same SectionHeader row; narrow layouts wrap the actions together. Saved versions use the same heading without edits. WorkspaceShell uses the user-approved preview’s labeled Assistant button with chat-outline icon, rounded rectangle, accent/on-accent and floating shadow. Existing design tokens were sufficient; the shared recipe and design documentation changed together.

## Automated evidence

All groups ran through `./hyprn-mvp dev check <group>` with the pinned tool cache, locked existing UI dependencies and scoped test storage. Exact commands and reports are retained externally under `/private/tmp/hyprn-component-header-evidence`.

| Command | Implementation result | Parent comparison |
|---|---|---|
| `./hyprn-mvp dev check combined-static --keep-scope` | 9 stages pass, 0 fail; design, ownership, token generation, UI contract, tooling, smoke, unit helpers, TypeScript and build | Not needed |
| `./hyprn-mvp dev check ui-navigation` | 9 pass, 0 fail/skip/flaky; visible launcher label, navigation persistence, narrow bounds, Escape/focus, disconnected state | Not needed |
| `./hyprn-mvp dev check ui-reading` | 26 pass, 5 fail, 0 skip/flaky; model header alignment and source preservation pass | Same 26 pass / 5 fail |
| `./hyprn-mvp dev check foundry-nav` | 7 pass, 1 fail, 0 skip/flaky | Same 7 pass / 1 fail |

The six pre-existing failures are: statement-set opener label, limit-context opener label, late/denied context-source opener labels (two cases), a coarse-pointer specimen button below 48px, and the 200% test attempting an underlying Add evidence action while Study details is modal. They reproduce without this change. They remain owned by the broader UI qualification follow-up; these groups are not reported green and full zoom qualification is not established.

Initial isolated runs refused (exit 2) because the new checkout had no browser dependency directory. Reusing the existing locked node_modules installation resolved that prerequisite; no dependency was installed. An earlier working-tree static run also passed but is superseded by the committed isolated result.

## Live browser evidence

The user’s model on port 54821 was checked in Chrome at 1440×1000 in light/dark and 390×844. The preview button was inspected directly. Component title and both actions share the same centerline on desktop, wrap without horizontal scrolling on narrow width, and preserve the name/explanation editor. Saved version reading has one name heading and no edits. The labeled Assistant button opens/closes the independent side panel; its narrow bounds remain within the viewport. No record writes; original draft, System appearance and viewport restored, Saved draft visible and no unsaved changes.

Screenshots: external `preview-reference.png`, `model-light.png`, `model-dark.png`, `model-narrow.png`. Browser artifacts and tests are evidence, not human acceptance.

A concurrent overview build changed the live UI after baseline. The guarded refresh refused before copying any assets. The newer build already included the requested controls and was preserved. `live-assets.json` records exact observed JS/CSS hashes and index SHA-256 `4d510f5b414910f7d609c0dccf30e03a529f8510aed4bba68bcf230dd03c07c8`; no unproven source-commit attribution is made for it. No backend restart or store change.

Browser test scopes were released by the runner. Two deliberately retained static build scopes remain under the runner’s 24-hour retention policy. The temporary verification worktree is archived after the comparisons. Evidence stays outside the repository. No push or publication. Human visual acceptance and full release qualification remain open.
