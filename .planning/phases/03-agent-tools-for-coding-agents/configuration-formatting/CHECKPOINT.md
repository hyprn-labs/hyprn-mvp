# Configuration formatting correction — 2026-10-16

Implementation and integrated acceptance tree: `0e494ab`. Preserved the original table/provenance, criteria and bottom actions. Shared design recipe now uses normal-flow headers, wrapping title/actions, right-aligned numeric fields/headings and existing unit typography. Stored values/units and public contracts unchanged. No new dependencies.

## Evidence

| Exact command | Result |
| --- | --- |
| `./hyprn-mvp dev check combined-static --keep-scope` | 9 stages passed, 0 failed: design, ownership, tokens, UI contract, tooling, smoke, unit helpers, TypeScript and build |
| `./hyprn-mvp dev check foundry-nav` | 9 passed, 0 failed/skipped/flaky; draft/save/reopen, long-title back navigation, exact value preservation, both themes and genuine 200% zoom |
| `git diff --check` | exit 0 |

All commands used the pinned local entry point and scoped scratch stores. Exact environment/logs: external `/private/tmp/hyprn-configuration-fix/{static-committed,nav-committed}.log`. Runner evidence sessions: `5663f746-a8e7-45e8-b74a-74993efcda86` (static), `6a9944ad-adac-406a-bb5a-379ec8497234` (browser), under the external configuration-checks scratch root.

Initial browser run: 8 passed, 1 failed. The pre-existing 200% test chose the first Add evidence button behind the Input tools modal. Scoped the action to the named dialog; the committed rerun above passes. Initial static run also passed. No failures suppressed.

Live browser: existing saved configuration `3aca221a-5fff-434c-9f72-4c097452ed2d`, study `50e423fd-a709-4e21-9381-0b09022b4115`, port 54821. At 1440×1000: back bottom 149px/header top 181px; at 390×844: 477px/509px. Both have no page horizontal overflow. Back link clicked successfully and switched to the configuration list route (its data was still loading); exact saved detail was reopened and rendered. All 14 original input rows retained; numeric fields right aligned and density displayed as kg/m³. Automated fixture journey verifies list completion separately. No live scientific writes or executions. System appearance unchanged; temporary viewport reset.

Screenshots outside repository: `/private/tmp/hyprn-configuration-fix/configuration-desktop.png`, `configuration-narrow.png`. UI-only refresh preserved the backend and authoring store. Guarded static backup and asset manifest retained in the same folder; index SHA-256 `a501f5b199dd66a6ecf2fa1c864a22fddfd48639070785a39c44d4162aa2d15a`. Build is the static acceptance artifact for `0e494ab`.

Browser scratch scopes released by runner. Two static scopes deliberately retained by its bounded 24-hour policy for build/evidence recovery. Full release qualification was not run for this cosmetic change; existing broader qualification obligations remain. Browser evidence is not human visual acceptance. Next: user visual review of the preserved configuration layout.
