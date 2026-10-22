# Shared record details — 2026-10-17

Implementation: `99a5b8f`. Specimen/attribution test integration: `8b78a5b`; current-owner approach assertion: `08a8908`. Final static and reader acceptance: `7ab81d2` (only later changes were tests and design/checkpoint documentation). Concurrent `7ab81d2` also included this turn's Layouts reconciliation alongside the other owner's assistant documentation; no history rewritten or unrelated changes reverted.

One shared RecordDetails component now supplies the document icon, compact quiet Record details button, type-specific accessible name, standard dialog and metadata-row spacing. It sits immediately below its owning title, before content. Model and approach controls moved out of overflow menus; configuration/run controls out of command groups; method/case/answer/evidence/prediction controls out of content footers. Embedded configuration readers use the same row. Exact record contents, identities, attribution and historical data remain unchanged.

The authoritative recipe is design-system/components/RecordDetails.md, reconciled with README, Naming, Scientific-states, Coherence and Layouts. The ownership check rejects ad-hoc record-details ActionDialog/summary controls and screen-level metadata styling. Existing token and button/dialog recipes are reused; no dependency or API change.

## Integrated acceptance

All commands ran through the pinned `./hyprn-mvp dev check` entry point in isolated scratch stores. External logs are in `/private/tmp/hyprn-record-details-fix`; runner session IDs below resolve under the external configuration-checks scratch root's `.hyprn-checks` directory.

| Command | Result | Log / runner session |
| --- | --- | --- |
| `./hyprn-mvp dev check combined-static` | 9 stages passed, 0 failed | static-final.log / 80d76cd2-616a-4d9e-a439-d98c5f5f534d |
| `./hyprn-mvp dev check foundry-nav` | 10 passed, 0 failed/skipped/flaky | foundry-nav-committed.log / 191a825c-e725-40f1-b0e9-f106fce0152f |
| `./hyprn-mvp dev check agent-ui` | 25 passed, 0 failed/skipped/flaky | agent-ui-final.log / f62ae51f-cede-48a9-9144-d0212851bbc4 |
| `./hyprn-mvp dev check ui-reading` | 31 passed, 0 failed/skipped/flaky | reading-serial.log / e0ce508d-7d5d-48f9-bfac-4db94b2215a5 |
| `./hyprn-mvp dev check approach-ui-reading` | 17 passed, 0 failed/skipped | approach-reading-final.log / 2817a9b8-6575-4989-b951-8e932c94ee54 |
| `git diff --check` | exit 0 | final documentation delta only |

83 browser cases pass. Foundry and attribution include genuine 200% zoom and both themes. Approach reading exercises actual browser/HTTP/auth/receipt/store behavior in a scoped fixture; other browser groups declare API doubles. These do not qualify numerical execution or a release.

Failures retained: initial static contract check expected the old inline Model record label; updated to require the shared component plus exact model identity/digest. Initial reading: 30/31, missing RecordDetails specimen; added it. Initial attribution: 20/25, obsolete overflow-menu and configuration-header selectors; migrated selectors without weakening exact-attribution assertions. Initial approach reading: 16/17, existing context assertion targeted the Overview question rather than Current approach inside Study details; moved the same exact-text assertion to its existing owner. Second reading: 30/31, browser setup exceeded 45s before the criterion test began; rerunning without concurrent browser suites passed all 31. No skipped tests or suppressed failures.

## Live UI

User's installation on port 54821, study `50e423fd-a709-4e21-9381-0b09022b4115`. Original configuration `3aca221a-5fff-434c-9f72-4c097452ed2d` inspected at 1440×1000 light/dark and 390×844; no page horizontal overflow, metadata below title, original table retained. Dialog open/close and focus return checked. Evidence reader, saved study answer, case, case answer, saved model, method and approach controls opened through the UI and retained their distinct identities. Automated run/embedded-configuration tests cover the same placement and exact contents. Prediction metadata uses the same shared reader; its numerical behavior was not changed or separately exercised live.

Screenshots outside repository: configuration-light.png, configuration-dark.png, configuration-narrow.png, evidence-light.png, answer-light.png, case-light.png, model-light.png, approach-light.png, under the external log folder above. System appearance and normal viewport restored; original configuration left open. No live authoring writes or executions.

UI-only refresh: checked build of `99a5b8f`, guarded target identity and original index hash, backup and file manifest in the same external folder. Served index SHA-256 `6590e749123e6f42e06bf443b97382c2e943c6b9c2d89b5f0690c2d22b43bb49`. Backend and authoring store preserved. Later commits contain no product-source changes.

Browser scopes released by the runner. Deliberately retained static build scopes remain under its bounded 24-hour policy for recovery; final static scope was released. Full release qualification and human visual acceptance remain open. Next: user visual acceptance of the common metadata placement. No push/publication.
