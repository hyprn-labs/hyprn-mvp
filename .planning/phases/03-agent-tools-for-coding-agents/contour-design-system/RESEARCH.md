# Grounded implementation research

Observed base: `fc650ab`, 2026-10-15. Discovery level 0 for React/CSS: existing components, generator, router and browser fixtures suffice; no new JS/Python library or package install. Asset integration uses the user-authorized local font inventory. These findings are source inspection, not successful execution evidence.

## Sources and responsibility map

| ID | Source / owner | Finding and implementation consequence |
|---|---|---|
| R-01 | `design-system/README.md`, `Layouts.md`, `Scientific-states.md`, `Naming.md`, `Coherence.md`, `Consistency.md`, `SOURCE.md`; `.claude/skills/hyprn-mvp-ui/SKILL.md` | Existing rules explicitly mandate system fonts, machined corners, two layers and no gradients. D-04 must amend those visual clauses while preserving semantics, ownership and CSP. Component notes remain authoritative; reconcile conflicts, do not leave contradictory instructions. |
| R-02 | `design-system/tokens.json`, `ui/design_tokens.py`, `ui/src/main.tsx` | JSON is the token authority. Entry loads generated tokens, Foundry and then screen CSS. Regenerate tokens; keep font declarations and depth/texture recipes inside design. Last-loaded screen CSS must not override new shared recipes. |
| R-03 | `ui/src/design/components.tsx`, `primitives.tsx`, `compositions.tsx`, `index.ts` | Existing export vocabulary includes Button, Field, Tabs, Panel, StatusTag, AttributionChip, Readout, Ledger, SourceChip, InferenceBlock, RecordBar/RecordState, ModelNode, DataTable, ActionIcon, CriterionRecord, native input wrappers, Disclosure, DialogFrame, SectionHeader, ActionDialog, DetailTabs, FilePicker, Progress, GraphCanvas, SourceSurface, BrandLogo, exploration controls and assertion/evidence/action compositions. Extend this ownership; do not clone screen-specific versions. |
| R-04 | `ui/src/Workspace.tsx:516`, `:680`, `:709`, `:930`; `ui/src/views/registry.ts` | Workspace owns session, guarded navigation and request generations. Home and Profile are real pages; Profile currently displays account name and Sign out. `studyTabs()`, `selectedTab()` and `breadcrumbOf()` are authoritative section adapters. Keep `navigate`, `chooseView`, `openLink` and guard order intact. A new shell takes content/action slots; it owns no record fetching. |
| R-05 | `ui/src/Workspace.tsx`, `ModelView.tsx`, `SelectionInspector.tsx`, `ConfigurationPanel.tsx`, `RunPanel.tsx`, `EvidenceView.tsx` | Adopt composites in real readers/editors. Preserve public event handlers and record pins. Model panel geometry is distinct from graph coordinate geometry: outer chrome may change; graph layout/projection and numerical logic do not. Agent activity is described by Layouts but absent from production source at this base; agent-ui tests exercise attribution chips. Preserve that separately owned implementation obligation rather than adding a fictional navigation destination. |
| R-06 | `ui/tests/study-navigation.spec.ts` | Current selectors include Main navigation, Profile, Open study, five study tabs, Study details and explicit model/version navigation. Tests already cover hidden-boundary preservation on keep/discard/save, late response invalidation/access loss, uncertain creation without duplicate writes and deep links/narrow shell. Extend these tests for the new shell and settings; do not replace them with CSS snapshots. |
| R-07 | `ui/tests/DesignSpecimen.tsx`, `screen-readability.spec.ts`, `foundry-zoom.spec.ts` | `?specimen` is isolated test-only. The genuine zoom test uses browser extension `chrome.tabs.setZoom(2)` with a persistent scoped profile and verifies actual viewport changes, focus and hit testing. Reuse it; CSS zoom or viewport resize is insufficient. Existing specimen has control sizes/variants, assertions/evidence and exploration recipes. Expand to every shared component and new composite. |
| R-08 | `ui/check_component_ownership.py`, `ui/test_design_tooling.py`, `ui/tests/design-colors.test.cjs` | Ownership currently rejects raw controls, screen-level control recipes and assertion/evidence/logo internals without a baseline. Extend to shell/card/settings/inspector/workflow internals with positive and negative tooling cases. Colour tests check 4.5 text contrast and 3.0 focus/control boundaries on both themes; include new depth grounds and browser composited backgrounds. |
| R-09 | `ui/vite.config.ts`, `ui/src/design/BrandLogo.tsx` | `/ui/` base and `assetsInlineLimit: 0` already preserve self-only CSP and hashed asset URLs. Bundle the font through a relative CSS URL into Vite assets; no data URI/CDN. Keep the logo source unchanged. |
| R-10 | `ui/src/ApproachAssumptions.tsx` (`Citations`, `ApproachAssumptions`, `QuestionClaim`, `StudyDetails`), `Assumptions.tsx` (`evidenceRows`), `ApproachFindings.tsx`, `EvidenceView.tsx` (`EvidenceRecordBody`) | Existing scientific statements and exact evidence readers supply the contextual claims experience. Add a presentation selection adapter, not another stored entity. Reuse exact evidence bodies and existing record-link callbacks; keep type/relationship/limits separate. Context selection must clear on study/access changes and ignore stale asynchronous reads. |
| R-11 | Latest user steering and parent-owned assistant lane | Persistent left navigation + central work area + details + adjacent assistant is required. Shared shell slots are the stable seam. This base does not supply an assistant backend; a truthful disabled/unavailable pane and integration contract are required until the separate owner connects it. External proposal chat is explicitly simulated, never production evidence. |

## Font asset audit

The parent-supplied local proposal's `fonts/provenance.json` records official source bytes. Copy only the authorized Manrope asset and its licence; rehash before use. Repository provenance retains source URLs and legal attribution, but product design prose contains no outside inspiration brand.

| Asset | Official source | Exact revision | SHA-256 | Licence |
|---|---|---|---|---|
| `manrope.ttf` | `https://raw.githubusercontent.com/google/fonts/1d0e46c7933245c8180fe83e47917961c913bbdb/ofl/manrope/Manrope%5Bwght%5D.ttf` | `1d0e46c7933245c8180fe83e47917961c913bbdb` | `3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6` | SIL Open Font License 1.1 |
| `OFL.txt` | same official revision, `ofl/manrope/OFL.txt` | same | `58172e0c0fac2cda8a37b348164bb55e44b0e69051e557e92b1d3f6910141f7b` | SIL Open Font License 1.1 |

No npm/pip/cargo install is planned. Existing locked dependencies remain unchanged. The original licence and copyright text must accompany the bundled font and the existing third-party notices route must expose its notice. A missing/mismatched asset stops font import; do not substitute an unaudited download.

## Grounded check inventory

`./hyprn-mvp dev check --list` was attempted and exited 5 because sandbox access to the existing uv cache was refused. The following names and targets were read directly from `deployment/checks.py`; execution remains unverified. Executor uses the configured development environment, never another interpreter or a live store.

| Group | Relevant coverage |
|---|---|
| `combined-static` | Design-system scanner, ownership guard, generated tokens, UI contract map, tooling tests, component smoke, criterion/colour/exploration-input tests, TypeScript and Vite production build in a scope. |
| `ui-navigation` | `study-navigation.spec.ts`: real React shell over scoped in-browser public API double. |
| `foundry-nav` | `model-configuration-run.spec.ts` and genuine `foundry-zoom.spec.ts`. |
| `ui-reading` | Readability, evidence workspace and record labels. Known older assertions may predate current product; reconcile only against authoritative scientific semantics, preserving coverage. |
| `ported-isolated` | Command recovery and historical record races; guard behavior must survive shell migration. |
| `agent-ui` | Agent attribution browser behavior; it does not establish an implemented Agent activity page. |
| `exploration-ui` | Existing exploration integration regression; coordinate with numerical owner and shared heavy resources. |
| `guard`, `style-ratchet` | Repository ownership/integrity and required formatting checks. |
| `ui-served` | Existing served-installation journeys require a separately created isolated test installation, explicit fixture URL and credentials. Never point them at a user/demo installation. |
| `qualification` | Full must-pass release gate, separate scoped groups; preserve the obligation on the exact final integration tree. |
| `ui-fidelity` | Opt-in reference-image comparison; currently refuses absent `design-system/reference`. It cannot be silently marked passed or replaced by automation claimed as human acceptance. |

Shared browser fixture groups do not prove the installed application's actual auth/network/CSP path. Retain a served-test installation smoke after integration. The parent owns its setup and heavy-resource window. Screenshots, traces and reports remain outside Git; checkpoints link identities, counts and cleanup.

## Dependencies and integration seams

Sequence 3.C1 → 3.C2 → 3.C3 because tokens, Foundry, Workspace and specimen overlap. The parent is concurrently evolving `AnswerExplorer.tsx`, exploration design controls, tests and numerical code: keep those source files outside this lane's mutation set; inspect merged UI and preserve consumer compatibility. If shared selector or registry shape changes, stop only the conflicting edit and reconcile with the owner. No graph rebuild context exists: graphify reports disabled. History digest identifies exact immutable answer pins and public result reuse as current invariants; this lane preserves them.
