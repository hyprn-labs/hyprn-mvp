# Grouped evidence details

User-authorized UI batch, retaining existing layouts. Implementation: `17ec020440807fe04c06b6361b986dcb92dc3c9e`; final test-only
adaptation: `e0138be8497942ab19abc31863c32bebcd5285bc`.

One `View evidence (n)` action per supported item opens the shared details panel.
Count distinct attached versions, including unavailable links. Source titles,
saved notes, references, relationships, citation locations and editing controls
live together in the panel. Conflict indicators remain beside claims. The shared
panel preserves parent readers, native editor modality and return focus; Escape
from a portalled record dialog closes only that dialog. Ownership guards reject
ad-hoc evidence dialogs/buttons. No API, scientific records or source pins changed.

The current evidence contract supplies authored notes/reference strings and
optional citation locators, not authenticated passage excerpts. The reader labels
these as Evidence note and preserves their exact text; it never invents quotations.
Document passage retrieval remains separate product work, not delivered here.

## Verification

All commands use `./hyprn-mvp dev check <group>` in isolated scoped stores.
Logs, browser reports and screenshots: `/private/tmp/hyprn-evidence-panel`.
Each log's `check_storage` points to retained reports after runner-scope cleanup.

| Source | Group | Result | Log |
|---|---|---|---|
| 17ec020 | static | all 9 stages pass | committed-static.log |
| 17ec020 | ae-ui-evidence | 12/12 pass | committed-ae-ui-evidence.log |
| e0138be isolated copy | ui-reading | 32/32 pass | delivery-ui-reading.log |
| e0138be isolated copy | agent-ui | 25/25 pass | delivery-agent-ui.log |
| e0138be isolated copy | ae-ui-configuration | 3/14 pass, 11 fail | delivery-ae-ui-configuration.log |
| unchanged baseline 2cdfe55 | ae-ui-configuration | same 11 failing names | ae-ui-configuration-baseline.log |
| development tree | approach-ui-reading | 18/18 pass | approach-ui-reading.log |
| development tree | approach-ui-assumptions | 18/19 pass, 1 fail | approach-ui-assumptions-3.log |
| development tree and baseline 2cdfe55 | approach-ui-method | both 9/19 pass, same 10 failures | approach-ui-method.log; approach-ui-method-baseline.log |

The e0138be delta only updates evidence-index browser selectors; production source,
static inputs and the passing ae-ui-evidence tests are unchanged from 17ec020.
Two source archives isolate final verification from concurrent navigation edits.
No dependency installation or changes to the other task's files were made.

The 11 configuration and 10 method failures reproduce on the unchanged baseline:
old Context/Run Evidence/quantity controls, bundled model-link and heading
expectations. The remaining assumptions failure expects the removed saved-
configuration “View modeling approach” action. These groups are not claimed green;
reconciliation belongs to the broader UI/navigation qualification work.

Intermediate failures and corrections:
- static-2: missing StatusTag import; corrected, subsequent static runs pass.
- ui-reading: 27/31 initially; migrated popup/parent-reader selectors, rerun 32/32.
- ae-ui-evidence: 6/12 then 10/12; provided production ContextWorkspace in fixture,
  updated dialog selectors and version-content updates, corrected a real portalled
  Escape propagation bug; final 12/12. No weakened scientific checks.
- approach-ui-assumptions: 12/19 then 15/19 then 18/19; migrated reader selectors,
  retained claim conflict badges and semantic EvidenceStack regions.
- initial ae-ui-configuration: 1/14; adapted the two additional evidence-related
  expectations; final failed-name set exactly matches baseline, no added failures.
- committed-ui-reading in the shared checkout was invalidated by concurrent
  navigation edits (20/32); isolated e0138be run supersedes it (32/32).
- Python 3.9 refused the archive extractor's newer filter parameter before
  extraction; safe member-path validation and compatible extraction succeeded.
- First Git write hit sandbox index permissions; authorized explicit-path commit
  succeeded with escalation. No automatic approval rejection.

Fixtures verify actual public HTTP/API/auth/store evidence journeys without
executing candidate code. UI-only fixtures verify grouping, deduplication,
unavailable links, exact snapshots/downloads, relationships, attribution,
no writes, navigation cleanup and focus. Native execution is outside this UI batch.

An additional exact-delivery `foundry-nav` run initially passed 10/11: the
run-header test measured a 68px title/action offset immediately after resizing.
Its failure screenshot shows the final header aligned; unchanged baseline passes
11/11. The unchanged delivery repeat passes 11/11 (`delivery-foundry-nav-2.log`),
including genuine 200% zoom. This is an intermittent geometry measurement; no
source or test was changed to obtain the passing repeat.

## Live browser

Local app `http://127.0.0.1:54821`, scope `f7145c6a-9848-4541-8aa4-0acf069102fb`.
Guarded UI-only refreshes preserve a backup, verify the prior index hash and switch
index atomically; no backend restart, candidate execution or scientific writes.
A duplicate backup name was refused before any copy; a distinct name resolved it.
Configuration evidence shows two saved source records with one action. Method
rationale uses the same panel. Light/dark, narrow layout, exact metadata and nested
Escape checked. Final live UI comes from 17ec020; `ui-manifest.json` records every asset hash and
backup. Index SHA256:
`cc8304609d4565635dc9d720cfc1faf1542004d097a1ac73d87790558c381f1c`.
`configuration-final.png` shows the final two-source reader; additional light,
dark, narrow and method captures are in the same evidence folder. Appearance
restored to System and browser viewport reset. No scientific authoring writes.

Human visual acceptance and full release qualification remain separate and unclaimed.

## Cleanup and remaining work

Runner-managed scopes were released automatically with retained reports. Three
kept static scopes and both isolated source copies were explicitly released after
verification; exact paths are in external `cleanup.json`. Live assets, screenshots,
UI recovery backups and reports remain available. Concurrent navigation/research
edits and unrelated index entries were preserved. This checkpoint and STATE entry
are the only post-verification delta. Human visual acceptance, source-passage
retrieval and full release qualification remain separate, unclaimed work.
