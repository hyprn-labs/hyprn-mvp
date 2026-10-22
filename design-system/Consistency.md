# Shared composition consistency

Current shared invariants, reconciled with the complete Contour layer. The table retains the original discrepancies and their single shared owner; scientific meanings are unchanged.

| Topic and observed discrepancy | Shared owner and correction | Acceptance |
|---|---|---|
| Compact evidence actions computed as 36px/14px despite `sm`; ordinary compact actions elsewhere computed as 28px/12px. Global minimum height and section-action font rules competed with Button. | Button recipes; remove global/screen recipe overrides. Explicit desk, sm, floor, link, icon and stacked compositions. | Same size has identical font, line height, padding, gap and minimum height in every context. Wrapped labels grow, touch minimum 48px. |
| Study assumption and limit structures had separate padding rules; empty evidence regions added a 12px grid gap. Evidence titles squeezed beside actions on narrow screens. | Assertion, AssertionList, EvidenceStack, ReadingSection and ReadingStack. Assumptions shared across approach/model/component/configuration; limits and all citation readers use the same rhythm. | 12px statement-to-evidence; 8px between sources; 16px each side of inter-assertion separator; 24px each side of section separator. No empty evidence gap. |
| Evidence in answer, method and configuration contexts had differing wrappers. | EvidenceStack and the compact evidence card: title above the action row. | Every source remains beside its assertion; long titles/actions wrap without overlap. Exact pins and challenged-source wording stay intact. |
| Form labels and dialog sections mixed global and dialog-specific margin/gap rules. | Shared native wrappers, form-stack/form-grid, DialogFrame/ActionDialog and common dialog CSS in Foundry. | One label/input gap, independent field spacing, visible validation and reachable close/submit actions. Exact-text source overlay remains a separately styled shared source surface. |
| Action rows and heading/action layouts had duplicate CSS definitions. | ActionGroup, SectionHeader and shared action-group styles. | Controls wrap with 8px gaps and consistent alignment; heading does not collide with actions. Page layout may choose placement only. |
| Table cell padding varied among runs, quantities and expanded answers; row headers inherited column-heading style. | DataTable default/dense cell rhythm and body-row-header typography. Column width, scrolling, numerical alignment and matrix layout remain page-specific. | Default cells pad 8px vertically; dense cells 4px. Values retain tabular numbers and separate units; unavailable remains explicit text. |
| Some panel bodies used 24px padding, others 16px through screen overrides. | Panel owns 16px default body padding. Lists own their row layout. | Matching panels share padding; no screen-level body padding overrides. |
| Status labels could be forced onto one line. | StatusTag allows wrapping while retaining mark and semantic colour. | Long status text remains within narrow cards without changing meaning. |
| Typography and line lengths | Assertion prose capped at 75ch; existing heading/type tokens retained. | Scientific paragraphs remain readable; identifiers and source bytes keep their own wrapping rules. |
| Disclosures, provenance/assistant marks, icon baselines, focus/hover/disabled, dark contrast, logo | Existing shared components remain authoritative; button icon sizing and touch rules clarified. No new visual language needed. | Existing meanings/colours retained; focus visible, disabled controls inert, supplied logo geometry and theme-aware ink; actual browser and component reference checks. |

## Authority and prevention

Screen CSS may position controls and choose column/scroll layouts. It must not
resize/restyle buttons, workspace/navigation/card/settings/claim/context/inspector/workflow internals or logo, or override table-cell
and panel-body padding. Use Button props and
shared compositions. No raw button/input/select/textarea outside `ui/src/design`.
`check_component_ownership.py` enforces these prohibitions without a baseline;
`test_design_tooling.py` tests the guard. Existing token and contract checks remain.

`ui/tests/DesignSpecimen.tsx` is the compact reference surface made from the actual
components, available only in the scoped browser fixture (`?specimen`). It covers every component export, with a separately tested number utility. The full state/consumer matrix lives in Contour.md. This complements real product/API journeys; it does not
replace them or constitute human acceptance.

No new feature, scientific state, data format or numerical capability is introduced.
Whole-release qualification, cross-platform visual qualification, independent review and product-owner acceptance remain separately recorded obligations. This pass
must report any discovered product-level regression before calling delivery complete.

Shared ClaimCard uses a 12px grid gap, zero external paragraph/heading margins and an 8px internal source gap; it does not stack inherited margins onto the grid. ReadingContents owns local method-section wayfinding. Inspector and detail-tab recipes live in Foundry; screen CSS retains workbench placement only. Tests reject descendants, BEM interiors and variant overrides without exemptions.
