# Navigation affordances

Authorized 2026-10-20 in the visualization/design conversation. One cohesive UI
batch on the existing local checkout; no numerical, persistence or public API change.
The user approved the rule and explicitly excludes sidebar navigation and tabs.

## Task 1 — consistent opening controls

Outcome: every content link opening a destination or dedicated reader has a visible
shared inclined arrow, including Record details. Named links use one focus/click
target for underlined label + arrow. Passive facts/statuses remain noninteractive
beside a separately named arrow. Return links use the shared back arrow.

Commands (save, calculate, retry, delete, sorting) are buttons without link
underlining or an opening arrow. Disclosures retain chevrons. Sidebar and tabs
retain existing appearance/behavior. Opening editors and confirmation dialogs is
an action, not a read-navigation link. External/new-tab semantics remain explicit.

Ownership: ui/src/design shared components and recipes; relevant consumer call
sites only; design-system README/Coherence/Layouts and affected component docs;
existing component ownership tooling, smoke specimens and focused browser tests.
No new dependencies. Reuse the existing open-record SVG. Preserve existing
navigation handlers, dirty guards, exact record identities, scientific statuses,
disabled behavior, focus restoration and responsive touch targets.

Research complete: existing RecordNavigation already separates passive facts and
inclined arrow; RecordDetails still has a document icon; quiet/link Button variants
currently conflate commands and navigation. ReturnLink lacks an arrow. Shared
SourceChip and EvidenceButton also open readers. Do not infer semantics from label
text or decorate every quiet button using CSS.

Implementation: give opening behavior one typed shared primitive/semantic contract;
compose record navigation, metadata and source-reader controls with it; audit and
migrate content navigation across all consumers. Document exact exemptions.

Verification: run through ./hyprn-mvp dev check using the configured development
environment; combined-static includes design/token checks, smoke, ownership,
contracts and production build. Exercise representative real browser flows for
record details, content navigation, passive status arrows, returns, command
controls, keyboard/focus, both themes and narrow layout. Use existing browser
group(s) or a scoped added navigation test integrated into that runner.
Preserve unrelated failures as explicit limits; do not claim whole release.

Concurrency: other agent owns assistant backend/UI work. Preserve its edits and
index; no blanket formatter or staging. Stage only owned clean files or precise
hunks; inspect staged diff before atomic commit. Evidence goes outside source.

Checkpoint: record source commit, exact checks and outcomes including failures,
browser evidence, cleanup, remaining unverified claims and delivery state.
Orchestrator verifies checkpoint and reruns batch acceptance on committed source.

## Plan check

The approved examples map to shared primitives, with command/disclosure/sidebar/tab
exceptions explicit. Migration plus real browser checks prevents a docs-only result.
No source or record mutation is necessary for visual verification. Fully reversible.
