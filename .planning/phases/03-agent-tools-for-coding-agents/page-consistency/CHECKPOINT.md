# Run and page formatting — 2026-10-17

Implementation: `827fb67`; live narrow-screen correction: `eb0fec4`; independent
case-reader fixture: `1f575b2`. Final acceptance below ran on `1f575b2`. Later delta
is checkpoint/state documentation only.

Existing page layouts retained. The design-owned page-heading recipe aligns titles
and commands at the top, then stacks all nested action groups left on narrow
screens. SectionHeader owns section title/action alignment. Case cards retain
ResourceCard padding, typography and separate action slots, with gaps between cards.
Ownership guards reject page-heading and case-card overrides in screen CSS.

Run identity and attribution share the metadata row, with identity retained even
when history is unavailable. Empty status messages and empty-results filler are
omitted. Successful worker details/time move into the existing diagnostics disclosure;
failed, incomplete and uncertain states stay visible. Run/case output headers and
values align right, and shared read-only unit typography includes criterion records.
No API, dependency, calculation, authoring-data or execution changes.

## Integrated acceptance

All commands use the pinned local entry point and isolated test stores. Logs below
are in `/private/tmp/hyprn-page-consistency`; runner IDs resolve beneath the external
configuration-checks scratch root's `.hyprn-checks` folder.

| Command | Result | Log / runner session |
| --- | --- | --- |
| `./hyprn-mvp dev check combined-static` | 9 stages passed, 0 failed | static-final-committed.log / 8372b08e-b80f-4a4d-b302-570da6278a9b |
| `./hyprn-mvp dev check foundry-nav` | 11 passed, 0 failed/skipped/flaky | foundry-nav-final.log / 5dabc2d7-586c-4a6e-a952-a7728ce5b343 |
| `./hyprn-mvp dev check ui-reading` | 31 passed, 0 failed/skipped/flaky | ui-reading.log / 8b1bc030-37b3-4eb4-b3bb-f94118d15179 |
| `./hyprn-mvp dev check approach-ui-reading` | 18 passed, 0 failed/skipped | approach-reading-final.log / 6a336f87-cacd-42c0-967d-4d32faa4c5b0 |
| `./hyprn-mvp dev check agent-ui` | 25 passed, 0 failed/skipped/flaky | agent-ui.log / 613f300b-aa11-4f26-b44f-ca4aed9dace3 |

85 browser cases pass. Includes genuine 200% zoom, both themes, long titles, exact
record identity/focus return, output zero/unavailable distinctions, scientific
attribution and original configuration controls. Approach reading uses actual
HTTP/auth/receipts/store; other browser groups declare API doubles. These checks
are UI acceptance evidence, not numerical or release qualification.

Failures retained: initial static unit-render loader lacked the newly imported
unit formatter; loaded the real module and reran successfully. Initial new case
browser test used a model fixture unavailable in the reading suite (17/18 passed);
it now creates a case through the public editor (18/18 pass). Live narrow check
caught nested export buttons still right aligned; shared CSS and a geometry
assertion corrected this before final acceptance. A live read-only DOM inspection
used an unsupported checkVisibility method; repeated with visible bounding boxes.
One live run-heading wait expired during the slow retained-record read; the actual
record subsequently loaded and was verified. No checks suppressed or weakened.

## Live browser

Verified installation: port 54821, instance f7145c6a-9848-4541-8aa4-0acf069102fb,
study 50e423fd-a709-4e21-9381-0b09022b4115. Saved run
0191b88f-bba5-429b-bda1-810985b05ded retains configuration
845e4fba-cfb0-4eed-bf78-c772a8f42d54 and model version
420b8ed0-dbc6-465b-968b-3e1ca7dc0df6.

Run and Cases checked at 1440×1000 in light/dark and 390×844; no horizontal page
overflow. Narrow run command buttons all start at x=33, matching the title, while
record dialog Escape returns focus. Run output units show m²; underlying exact
metadata remains available. Models and approach headers inspected live; approach
also checked narrow. Overview, case detail and profile reviewed in this pass.
The run Configuration tab retains its original read-only inputs/provenance layout;
the existing diagnostics disclosure shows the preserved worker message and elapsed time.
Screenshots under the external log folder: run-light.png, run-dark.png,
run-narrow.png, run-narrow-dark.png, cases-light.png, cases-dark.png,
cases-narrow-dark.png, models-light.png, approach-light.png, approach-narrow.png.

Guarded UI-only refresh with backup and file hashes: ui-manifest.json, served index
SHA-256 f2c821036a1458f5e53bec873cf88b86ae794ced52caf19a0c354dc8c8a1d787.
Served product source is eb0fec4; 1f575b2 changes only its browser fixture. Backend
and live authoring store were preserved, with no live scientific writes or executions.
Appearance restored to System, viewport override reset and reviewed run left open. Browser scopes released by the runner; retained
static-build scopes remain under the runner's bounded retention policy for recovery.
Unrelated ROADMAP/research/assistant proposal work is excluded. No push/publication.

Next: human visual acceptance. Full release qualification remains separate; slow
live run/supporting-record reads observed but performance was not changed here.
