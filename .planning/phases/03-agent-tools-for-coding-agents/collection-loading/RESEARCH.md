# Collection loading research

Inspected source: `4c6335cc7fa0fad7d6975904341836dc34e08093`, isolated branch `codex/collection-loading`. No new libraries. Existing React state, public API fences, Foundry primitives and closed browser groups suffice.

## Findings and adoption inventory

| Consumer | Current behavior | Required disposition |
|---|---|---|
| `CollectionToolbar` in design/workspace.tsx | Arbitrary ReactNode summary; no loading/coverage contract | Add typed collection status/summary and shared paging/status rendering; retain toolbar for genuinely non-collection contextual text |
| `ConfigurationList.tsx` | String cursor, saved-version noun, retry restarts at first page | Configuration-version count; initial vs append states; retry same cursor; keep reference-mark mutations separate |
| `CalculationsPanel.tsx` CalculationList | Number cursor, unqualified count; append failure deletes rows | Shared summary/actions; preserve rows/cursor on transient append error; zero-valued cursor must not mean first page |
| Same file CalculationRecord runs | Number cursor, “loaded” copy; retry starts over | Shared run collection, independent from run-submission errors |
| Same file analysis version selector | `calculationVersions` first page only, discards next_cursor | Expose additional pages with shared version-history state and retry; keep selected exact version available |
| `RunPanel.tsx` | Visible count divided by received count; first page 20 appears complete | Distinguish filtered matches from coverage; shared append retry and initial failure; retain model/version/session fences |
| `CalculationDesign.tsx` EstimatesPanel | Discards calculationEstimates.next_cursor; count may include fitting record | Page estimates; de-duplicate fitting record by estimate ID; separate fit/poll errors from collection errors and never alter scientific lifecycle |
| `EvidencePanel.tsx` / `EvidencePicker.tsx` | Ad hoc counts and generic paging; refresh is offered after any read failure | Shared summaries/local filter scope and failed-page retry; keep evidence attach/create errors independent |
| `ResultPicker.tsx` | Local filter, generic Load more, no collection count | Shared result coverage; reset/fence scope and actor; preserve exact chosen scalar and unit semantics |
| `EvidenceView.tsx` / `Assumptions.tsx` version dialogs | Paged families, mixed loading/inspection errors | Shared version-page state; retry exact failed read; do not replace an inspection failure with pagination retry. EvidenceView currently applies callback writes before checking generation: fence writes too |
| `Workspace.tsx` Home | api.studies/archivedStudies call api.list, which drains all pages; filter count says loaded | Complete collection only after full success; shared matching/empty wording; existing tab totals are legitimate after success |
| Model revisions; StudyBrief/StudyAnswer version lists | Model API list and controllers already collect all pages | Keep exhaustive strategy; no false partial summary or extra pager. VersionSelect's empty option is only valid after successful exhaustion; validate owners' loading/error gates |
| `EvidenceIndex.tsx` | Counts known owner groups, not records, and preserves unknown owners | Keep scientific/owner-read progress separate; existing known denominator is valid |
| Analysis member configurations, sampled design points, criterion rows | Complete arrays belonging to exact saved record | No pagination treatment or scientific count rewrite |

## Shared contract

Create `ui/src/design/collections.tsx` with typed presentation state and deterministic summary. Distinguish initial loading/error, ready partial/complete, appending, append error, refreshing and refresh error. Completeness must not be representable before first successful read; filtered counts cannot manufacture totals. Use explicit singular/plural labels, including analysis/analyses and evidence records. Cursor storage and public API reads remain in application consumers, not the design layer.

Examples: incomplete first page “20 runs shown · More available”; exhausted “36 configuration versions”; filtered partial “3 matches in 20 runs shown · More available”; filtered complete “3 matches in 36 runs”. No-match partial “No matches in the runs shown. Load more runs or clear the filters.” No-match complete “No runs match these filters.” Initial failure “Runs could not be loaded.” Append failure “More runs could not be loaded. The runs already shown are kept.” Buttons: “Load more runs”, busy “Loading more runs…”, failed append “Retry loading more runs”, initial failure “Retry loading runs”. Scope such as “For this model version” is a separate stable field, never part of count math. Use standard neutral Foundry text and Button recipes, not scientific warning/success statuses for ordinary pagination.

Refresh preserves rows while busy, then replaces them only on success. Failure leaves old coverage visible with a clear refresh failure; retry repeats refresh. Access denial overrides row retention and clears rows, cursor, selection and late writes.

## Verification approach

`ui-navigation` and `ui-reading` run actual built React UI against explicit HTTP fixtures, no live stores or Docker. Extend their existing files so runner registration need not change. Cover initial pending/error/retry, 20+later rows and cursor exhaustion, page-two failure and same-cursor retry, partial local no-match, late prior-scope responses, zero-valued numeric cursors, de-duplication and exact pin retention. Test evidence/results and analysis versions/estimates as well as runs/configurations/analyses. Screenshots in both themes at 1440 and narrow width remain outside repo. `foundry-nav` covers genuine browser zoom. These checks establish UI behavior under controlled API responses, not backend or human acceptance.

## Source coverage audit

| Source | Item | Coverage |
|---|---|---|
| GOAL | User-directed collection consistency extension in Phase 3 | 03-01, task 3.L1 |
| GOAL | Original Phase 3 MCP/agent outcomes | Existing phase plans; outside this scoped UI correction |
| REQ | UI-01, UI-03 from docs/specs/requirements.md | 03-01, task 3.L1; no claim to completing their unrelated obligations |
| REQ | Phase 3 AGENT-01/05/06/07/08, UI-04, RUN-07 | Existing phase work, outside this correction |
| CONTEXT | D-01 through D-05 | 03-01, task 3.L1 |
| RESEARCH | Every inventory disposition, state/copy rules and race/retry acceptance above | 03-01, task 3.L1 |

No source item within the scoped correction is omitted. No package installation is planned.
