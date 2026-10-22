# Shared version identity, analysis readers and contextual help — 2026-10-20

Delivered code: `95b37d0`, navigation fixture correction `08acd3e`, final shared
header alignment `d7a64b0`. This checkpoint and STATE update are documentation only.

The shared VersionSelect displays recorded ordinal numbers for briefs, answers and
analyses; models use complete unbranched ancestry, with a saved-identifier fallback
when that cannot establish an ordinal. IDs and exact pins are unchanged. RecordState
uses a neutral lock for immutable versions. Saved analysis settings are reader values
and tables, retaining the selected configuration source and explicit Create new version.
Shared checkbox captions stay inline. Circular HelpButton reuses the accessible modal
frame (named control, Escape, focus return), including model graph/XDSM, version choices,
sampling and surrogate error/validation explanations. Headers align labelled controls.

Analysis results have one pagination state at both ends, units in headers, aligned
numbers, a sticky point identity column, and grouped output/input column choices.
Execution is compact. Surrogate summaries separate training, method selection and
independent validation. Small positive error summaries use a bound with exact tooltip
values. No numerical logic, tolerance, saved record, API, sampling or surrogate changes.
The unstructured saved sampling rationale remains in Analysis record details rather
than being repeated as results-page commentary; no historical text was rewritten.

## Verification

Commands use `./hyprn-mvp dev check <group> --keep-scope` in the supplied locked
development environment. All scopes are isolated; retained evidence scopes are listed
below by UUID (under the configured scratch-checks root).

- `combined-static`: **9/9**, 6.93 s, final `d7a64b0` UI plus the pre-existing working
  tree delta described below. Scope `469297fc-5792-4648-a29f-0634506fe3cf`.
  Includes design ownership, tokens, public UI contract, design tooling/render checks,
  number/input tests, TypeScript and production build.
- `calculations-ui`: **6/6**, 77.99 s, `95b37d0` UI and final assertions; scope
  `496fd7e4-a3dc-45cb-be8c-0876995de1be`. Real HTTP/auth/store browser fixture,
  declared offline model/numerical services. Includes saved/new version settings,
  member pagination, retained outputs, checkbox geometry and help Escape/focus return.
- `ui-navigation`: **21/21**, 25.57 s, `08acd3e`; scope
  `3553bde5-6921-46b3-8cf5-126f3d199ade`. Current UI with explicit browser API double;
  does not qualify numerical execution. Includes history paging, exact version choice,
  stale/access-loss behavior and automatic member-run history loading.
- Final later delta is only two shared CSS declarations (header baseline alignment and
  help text decoration); static/build rerun and live inspection cover that delta.
- `git diff --check`: clean.

Earlier failed attempts are retained under `/private/tmp/hyprn-ui-coherence/`:
old units/pagination/disabled-field assertions (3 then 1 failures), an obsolete
navigation fixture expecting manual estimates/run pagination and missing the execution
read (1 failure), and a duplicate ReturnLink import (one type/build failure and two
refused fixture builds). Assertions were updated to exercise the intended behavior,
the fixture now models automatic run-history loading, and the duplicate import was
removed. No failing check is being represented as passing.

## Live delivery and boundaries

UI-only atomic publication on port 54821, guarded by current live index, runtime and
source fingerprints. Final build is the passing static scope above; deployment receipt
and previous index remain in the existing handover UI-delivery evidence location.
Backend runtime fingerprint unchanged. No worker restart, model run or scientific
write was requested. Live study `1174be5a-8527-4a51-83d9-aad3c8e4aeaa` still uses analysis
`70bed7e2-50ae-4ba9-8bc2-29e7a5f3aaff` and its original validated estimate.

Chrome review verified Version 3, 33/33 calculated, table pagination, Point 25's method
selection role, 24 training / 1 method selection / 8 validation, 2/2 outputs passed,
saved settings, and checkbox/help layout. In-app light/narrow Overview verified brief
Version 1 and answer Version 5. Screenshots are outside the repository in
`/private/tmp/hyprn-ui-coherence/`. Numerical behavior is preserved by unchanged paths;
no new numerical qualification is claimed. Human acceptance remains the user's review.

Pre-existing changes to RunPanel, the run header metric CSS, run-execution documentation,
ROADMAP and untracked research/proposals were preserved and not included in these commits.
The existing saved-state green style was superseded by the explicitly approved neutral
saved-record style. Live checks include the preserved RunPanel/CSS delta; source
fingerprints and the original working-tree patch are retained with external evidence.
No test scopes were manually deleted; the runner owns their retention/cleanup.
Full release qualification remains separate from this focused UI delivery.


## Follow-up: shared explanations and inert navigation — 2026-10-20

Code commit `1565af2`. The follow-up supersedes version-selector help: major object
sections now own circular help, through typed SectionHelp topics and the shared
section-help catalogue. Brief, answer, exploration, model, explanation, quantities,
inputs/provenance, results, surrogate/settings, assumptions and evidence reuse it.
The agent workflow playbook explains the same domain distinctions through existing
get_playbook/MCP resource surfaces; generated documentation was refreshed.

ErrorAllowance renders saved absolute/relative limits with the explicit dimensional
reference in both the validation table and saved settings. Unknown units remain
unavailable. It does not evaluate pass/fail or modify limits. RecordNavigation keeps
point labels and execution statuses outside the arrow button; scientific table cells
use the shared middle alignment. No study-specific strings, data edits, API changes,
model execution, sampling or surrogate changes were introduced.

Final checks through `./hyprn-mvp dev check <group> --keep-scope`:

- `combined-static`: 9/9, 5.37 s, scope `1aed1f00-0d2e-47f0-a213-36968a6b46c7`.
  Includes render coverage for every help topic and generic allowance examples using
  Pa, W, dimensionless and missing units; TypeScript, build, design and UI contract.
- `calculations-ui`: 6/6, 59.20 s, scope `c5857745-324b-4f14-8350-b11606192aad`.
  Browser/public HTTP/store fixture; no numerical execution. Checks inert statuses,
  labelled arrows, vertical cell alignment, section help, focus return and saved settings.
- `agent-tools`: 326 passed, one pre-existing deprecation warning, 52.97 s;
  scope `b9e1a3f6-fe79-4d7d-8ff1-eb09381a386b`. Guidance and supported tool-surface tests
  passed before the UI-only renderer extraction; agent source was unchanged afterward.
- `git diff --check`: clean.

Earlier development checks also passed (static `21fd8f84-6e88-4c4a-98e5-7bfd192f6920`,
analysis browser `3f952fc9-010f-44ae-896b-dbcf8c3171a9`). They were repeated only after
shared renderer extraction and a saved-settings presentation change. The first sandboxed
launcher attempt could not access the existing uv cache; it ran no checks. Approved
normal-cache runs above completed. Logs: `/private/tmp/hyprn-section-help-*.log`.
Runner-owned evidence scopes retained; no manual store/scope deletion.

The checked UI was published atomically through the existing handover publisher;
receipt `/private/tmp/hyprn-final-exploration/ui-delivery/delivery.json` confirms runtime
unchanged. Live Chrome verified all 33 calculated points still recorded, two outputs
passing the original assessment, inert Completed labels, separate point/run arrows,
complete dimensional allowances, Results help and configuration provenance help.
Screenshots: `/private/tmp/hyprn-ui-coherence/live-section-results.png`,
`live-error-allowances.png`, `live-input-help.png`. Publication is UI-only; no backend
restart or redeployment is claimed for the updated packaged agent guidance.

Other session's RunPanel/CSS/run documentation/ROADMAP and research changes remain
unstaged and preserved. The live verification includes their current run-layout delta;
only this follow-up's help hunk and shared navigation/table CSS were committed.
Human acceptance and full release qualification remain separate.


## Follow-up: analysis density — 2026-10-20

`bf65563` is live. Shared TableControls owns one top-right Columns/range/Previous/Next
row. Removed duplicate bottom paging and the results-page input-domain disclosure;
its settings reader remains authoritative, and the now-unused anchor reads were removed.
The saved description is kept in settings and omitted from page identity metadata.
Saved sampling uses existing Panel/hf-flow/MetricGrid primitives for distinct Inputs,
Sampling settings and Surrogate settings. State, Create new version and Help share one
row. A single validation table contains assessment, largest error, allowance, independent
validation counts, method and RMSE for each output/group. Help explains the error metrics.
All rules are generic and recorded in design-system Coherence; no data or execution writes.

Verification (locked `./hyprn-mvp dev check <group> --keep-scope`):
- `combined-static`: 9/9, 4.86 s, scope `811b3321-ad49-42ad-b678-5b26278f38b9`;
  exact committed UI source tested before commit, no subsequent source changes.
- `calculations-ui`: 6/6, 65.15 s, on committed batch; scope
  `b6f3049a-4b47-4754-9a3e-d9a3ecf7e78f`. Covers single pagination, record reads,
  one validation table, saved range preservation and metric layout at 720/390px.
  Fixture uses real HTTP/API/store but no modeling/numerical execution.
- `git diff --check`: clean. No failed checks; existing dependency deprecation warning.

Guarded UI publication used the above passing build; runtime fingerprint unchanged.
Live Chrome confirmed the saved description still appears in settings, no description
in header, one pagination region, no duplicate input summary, readable saved counts,
and one two-output validation table with the original results. Screenshots outside repo:
`/private/tmp/hyprn-ui-coherence/live-analysis-settings-compact.png`,
`live-validation-single-table.png`, `live-analysis-single-pagination.png`.
Retained test scopes belong to the runner. Other session's dirty files remain preserved.
Human acceptance and full release qualification remain separate.


## Follow-up: readable tables and trailing creation actions — 2026-10-20

Code `1aa0049`. Shared DataTable column presentations and size tokens reserve readable
labels/formulas; textual columns align left, numerical columns right, every cell
vertically centered. Custom configuration/run value cells use the same numeric class.
Validation now orders Output, Method, Points, Max. error, RMSE, Allowed error, Result;
compact allowances retain both dimensional operands with full accessible wording.
Section help owns definitions. Labelled sample-use metrics replace compressed prose.
Results group identity/use before principal outputs, then run navigation and optional
inputs. Saved description appears once in a labelled panel above Results, sourced
from the same immutable field as settings. CollectionStatus/Toolbar and PageHeader
keep creation actions right-aligned, including narrow headers. The HYPRN source
skill (also the installed hard-linked file) now distinguishes descriptive authoring
from deterministic structured facts/layout. No study data, validation thresholds,
execution, sampling, surrogate, API or exact pins changed.

Verification on the committed tree, preserving the previously documented unrelated
working-tree delta:
- `./hyprn-mvp dev check combined-static --keep-scope`: **9/9**, 5.81 s;
  scope `7596f075-cffd-4d0e-a26c-c3de94e0d8d4`.
- `./hyprn-mvp dev check calculations-ui --keep-scope`: **6/6**, 57.16 s;
  scope `504133e3-6686-4dd9-84e8-f62591f063e7`. Real HTTP/API/store fixture,
  declared offline numerical/modeling services. Adds description readback, header/body
  alignment, logical validation ordering and trailing New analysis at 1440/720/390 px;
  existing version, failure, paging and saved-settings journeys remain covered.
- Skill-creator `quick_validate.py docs/agents/scientific-engineering`: valid.
- `git diff --check`: clean.
Earlier static 9/9 (`ce7f5c84-d45e-47eb-895c-9e344f4e5ed3`) and browser 6/6
(`fc055aec-870b-4259-9ac7-d644e44fe0ca`) predate the collection action selector fix.
Live inspection caught the wrong CSS action-container selector; it was corrected,
covered with geometry assertions and the focused groups rerun. No failed check run.

UI-only atomic delivery uses the final static build above, with runtime fingerprint
unchanged and rollback index/receipt in the existing ui-delivery evidence folder.
Chrome live checks confirm both New configuration and New analysis end exactly at
their collection's right edge, the description panel, readable validation rows and
unchanged real errors/counts. Screenshot:
`/private/tmp/hyprn-ui-coherence/live-validation-readable-final.png`.
Test scopes retained by the runner for evidence; no manual store cleanup or model runs.
Human acceptance and full release qualification remain separate. Other-session
RunPanel/header-metric and run documentation changes remain unstaged and preserved.


## Answer reader coherence — 2026-10-20

Delivered commits `babd63d`, `ffc3a57`, `b7b735c`, `808330d`, `03ee8b1`.
Saved brief details are compact; saved brief/answer readers expose Read-only and
explicit successor/continue-draft actions. Comparison groups alternatives, separates
requirements from outputs, and uses shared source arrows. Shared validation renders
identical saved facts in analysis and Why. Exploration has coordinate-based Load point,
fixed/ranged domain, compact controls, per-value origin symbols and exact-unit criterion
lines only when brief and analysis pins match. Idle display rounding does not change
input values. No execution, sampling, surrogate fitting, thresholds or API change.
Updated source/installed hard-linked `/hyprn` writing guidance, preserving saved prose.

Verification (isolated stores; existing unrelated working-tree delta preserved):
- `./hyprn-mvp dev check combined-static --keep-scope`: final **9/9**, 4.31 s,
  scope `020dc8ca-f398-4495-86b6-e2595842d9aa`, source `808330d`.
  Later `03ee8b1` changes only a browser test locator. Earlier successful static
  scopes `4dc08564-0f0b-4322-bdea-edfac4b9f1db` and
  `74356f68-67ff-4b43-bdf9-2c8a3e7979ad` preceded final CSS widths/alignment.
- `./hyprn-mvp dev check brief-ui --keep-scope`: **2/2**, 12.78 s,
  scope `c8b3e23d-00a5-4f86-a8bf-4675ceeb6c81`; brief code unchanged afterwards.
- `./hyprn-mvp dev check study-answer-ui --keep-scope`: **2/2**, 14.87 s,
  scope `8d910271-9c63-4b4c-a3d1-9ac8f23598fa`; final delta is shared CSS only.
- `./hyprn-mvp dev check calculations-ui --keep-scope`: **6/6**, 49.08 s,
  scope `f8287971-9a94-4893-be07-80e362a95d67`, final committed tree.
- Skill-creator quick validation: valid. `git diff --check`: clean.

Failures recorded: initial sandbox cache access refused (rerun with authorized cache
access); first answer browser failed on retired criterion-picker locator
(`3ec29bf0-3e86-443e-8c34-b317f72cb150`), next failed because its old fixture criteria
names were ambiguous (`67bb5a8a-ea5b-4ab4-a6ed-096af58405ba`). Updated fixture to
unambiguous output names, without weakening automatic binding. Initial analysis
browser failed on the renamed saved-brief action
(`2dcf43d8-478c-41b9-bf5b-74b77a03c182`); corrected its locator. Live read-only
snapshot login initially refused missing Origin; retried with the required origin.

Live Chrome verified version 5, compact brief, requirement comparison and arrows,
Why metrics, all four domain inputs, loading exact point 4 (9.524 K, 0.6 kW), and
three independent slider moves giving real estimates. Complete public run-list
snapshots before/after contain identical 36 records. No model reruns or scientific
writes. UI-only atomic publication uses final static scope, runtime fingerprint
unchanged; rollback index/receipt in existing ui-delivery folder. Screenshots and
snapshots: `/private/tmp/hyprn-ui-coherence/answer-exploration-final.png`,
`answer-why.png`, `runs-before.json`, `runs-after.json`.
Test scopes retained by runner for evidence, no processes left by this task.
No human acceptance or full release qualification claimed. Other-session RunPanel,
header-metric, run docs, roadmap and research edits remain untouched/uncommitted.


## Heading, help and action semantics correction — 2026-10-20

`eabfe05` implements shared title/help groups in SectionHeader, Panel, PageHeader
and ActionDialog. Major card titles use 20/28 heading tokens; internal sections
use 16/24. Help sits beside its owning title rather than among actions or floating
in dialog contents. Migrated analysis settings, sampling, estimate limits, results,
quantities and result/domain dialogs. Conclusion owns a sunken Panel with a distinct
recommendation classification/evidence-or-alternative row from the saved outcome.
View model restores the canonical read-only ModelView popup, mounted on first open;
its selection is independent from numerical exploration. Explicit View actions use
buttons, citations remain text links, passive table facts/statuses keep detail arrows.
Grouped comparison tables draw whole-alternative boundaries across spanning cells.

Checks:
- `./hyprn-mvp dev check combined-static --keep-scope`: **9/9**, 4.35 s,
  `deb9eb6e-6be9-4b68-9a10-637d44439ef3` on `eabfe05`. Earlier intermediate
  static 9/9: `610330e8-88d7-4825-af76-4962fa170fee`.
- `./hyprn-mvp dev check study-answer-ui --keep-scope`: **2/2**, 14.83 s,
  `eb73295a-5885-4944-872c-9c8ec20cbce9` on `3ad9785`. Covers live geometry
  (help/title centers and gap), title hierarchy, model popup, recommendation and
  saved-history behavior. First run `842dd267-af61-47ba-a0b7-e3717dfe95f7`
  had 1/2 pass: old assertion expected the former combined recommendation sentence.
  `3ad9785` updates only that test to assert classification and evidence separately.
- `git diff --check`: clean. No numerical or API changes; no full qualification claimed.

UI-only publication from final static scope; runtime fingerprint unchanged. Live Chrome
verified major headings, conclusion card, both alternative boundaries, View model reader,
Why help in header, View analysis navigation and Analysis settings help. Existing estimates
and saved analysis remain readable. Screenshots outside repo:
`/private/tmp/hyprn-ui-coherence/answer-hierarchy-final.png` and `answer-groups-final.png`.
No scientific writes or model runs. Scopes retained as runner evidence; no test processes
left. Unrelated working-tree edits preserved. Human acceptance remains pending.


## Follow-up: remaining readers and editors — 2026-10-20

UI commits `062bb61`, `8e8251d`, final CSS/test commit `cfd3acd`; evidence test
selector correction `2bc6fbb`. Shared SectionHeader now owns custom editor titles
(quantity, assumption, evidence, input preview, modified configuration/model-binding
review, result picker, exports and confirmations). Existing aria-labelledby IDs,
handlers and commands remain. Help uses the existing domain topics beside the title.
ContextualPanel separates title/help from commands. Raised panel titles and direct
panel-body headings use the major type role; inset/compact sections retain their
smaller role. Legacy form checkbox captions share the same spacing as newer forms.
Input preview buttons use ActionGroup. No API, data or numerical changes.

Review covered Home, Settings, Models/component/quantity/assumption editors,
Experiments, configurations, runs, Evidence and new analysis settings. Existing
CTA buttons and record links were retained; no arrows replaced explicit tasks.
Live quantity editor, evidence help nested over its editor, and analysis settings
were opened and closed without saving. Screenshots:
`/private/tmp/hyprn-ui-coherence/quantity-header-final.png` and
`/private/tmp/hyprn-ui-coherence/evidence-editor-final.png`.

Verification through `./hyprn-mvp dev check <group> --keep-scope`:
- Final `combined-static`: 9/9, 4.57 s, scope
  `ae6849a4-28b9-4bae-af46-415f51470211` on `cfd3acd` plus preserved unrelated
  RunPanel/header-metric working tree changes. Includes tokens, design ownership,
  UI contracts, tooling/render, input helpers, type checking and production build.
- `ae-ui-model`: 7/7, 20.73 s, scope
  `24631213-0a66-4ad0-9800-7fd9496b57f2` on the editor-header batch. Later changes
  only add evidence-reader help, major panel type, legacy checkbox gap and test selectors;
  final static checks and live quantity review cover that presentation delta.
- Final `ae-ui-evidence`: 13/13, 19.80 s, scope
  `ee62e0a7-6e55-490f-8b62-45a1b76d5253` on `cfd3acd`. Real HTTP/auth/store browser
  journey; no native scientific execution. Includes immutable evidence history,
  editing/dirty Escape, access loss, attachment/recovery, responsive details and assistant.
- Earlier evidence runs: 10/13 (`1426426e-8f43-4b1a-abb4-19b6b8924f19`) then 11/13
  (`e076c23c-c604-4791-97d8-acf16beb6980`). Stale generic Load more/Load more versions
  selectors and assumptions that no status/only one alert existed were corrected to
  the current collection controls and specific access-loss notice. No product behavior
  was changed to satisfy these assertions. First attempt also logged a disconnected
  browser request BrokenPipe in the fixture.
- Earlier static passes `7c88b498-a6d9-4fd3-bd5d-162604364fdf` and
  `86c16432-119b-4a5f-bc9d-08657790190d` were superseded by the final build after
  the additional reader and checkbox presentation changes. `git diff --check` clean.

Final UI-only publication uses the passing final static scope, with source/live-index
and runtime fingerprint guards. Existing publisher retained previous index and delivery
receipt; runtime unchanged. No model runs or authoring writes requested. Browser left
on Overview. Other-session dirty files and commits preserved. Runner owns scoped
scratch retention; no live stores or unrelated processes cleaned up. Human acceptance
and full release qualification remain separate from these focused automated checks.

## Follow-up: shared dialog completion footer — 2026-10-20

Code `73abe91`; final footer spacing `40d778d`. `DialogActions` contributes to its
nearest `DialogFrame` footer, grouping completion and cancellation at bottom right.
Applied to analysis/sampling, model/component/quantity, explanation publication,
evidence/attachment, assumption, configuration previews, imports/exports and unsaved
change confirmations. Inline page editors and per-row actions retain their behavior.
Native submit buttons retain explicit form association; hidden modes contribute no
footer action; inherited fieldset disabling is preserved explicitly. The stable portal
target mounts in the same commit, preserving initial safe-action focus. Coherence and
component inventory document the recipe. No API, scientific data or numerical changes.

Checks: `./hyprn-mvp dev check <group> --keep-scope`, locked environment, isolated scopes:
- `combined-static` 9/9, 4.27 s, final `40d778d`, scope
  `b9ca33f6-f19c-452b-a5f9-30dc2323972f`. Includes required design, tokens, ownership,
  UI contract, rendering, type and production build checks.
- `ae-ui-model` 7/7, 19.99 s, `73abe91`, scope
  `5f83bbb6-78f1-4f9c-8c82-cfe8b202532e`.
- `ae-ui-evidence` 13/13, 23.32 s, `73abe91`, scope
  `4bc883c1-ec0d-434f-b6f7-62323f77b050`.
- `calculations-ui` 6/6, 57.29 s, `73abe91`, scope
  `621d5708-7f35-4afb-8334-259cb6478f79`. Added assertions for one visible save action
  across input modes, footer form ownership, and same-row Save/Cancel at narrow width.
- Browser groups exercise public HTTP/UI/auth/store paths with declared modeling doubles;
  they perform no native model execution. The later `40d778d` delta is only one shared
  CSS margin rule for inset dialogs, verified by final static build and live screenshot.
- Earlier model check: 6/7, scope `5e3e92c5-e030-401b-b3b2-24c60ca39cd1`; initial
  deferred footer mounting prevented Keep assumption receiving focus. Fixed in the
  shared frame; original focus assertion unchanged and now passes.
- Earlier evidence 13/13 (`e805b4cd-4dc3-40b4-a343-37a5eae9b410`, 20.44 s; fixture logged
  a disconnected browser request BrokenPipe), analysis 6/6
  (`9b07fd2b-261b-4afc-9583-2c210a048e4c`, 50.30 s), and static 9/9
  (`cf72ccfe-78e3-459a-b181-d818cacd01a8`, 4.48 s) were superseded after that focus fix.
  Static `79b6bea3-60b2-4aae-ade4-0aa97d7ffddd` passed 9/9 before final spacing.
- Initial sandboxed check could not open the pinned uv cache; rerun with approved
  cache/scratch access. Initial CSS index patch was malformed; corrected and included
  before final verification. No source changes or other-task index entries were lost.

Final build published to the existing 54821 demo via fingerprint-guarded UI publisher;
backend runtime unchanged, prior index and delivery receipt retained. Live Chrome
checked both analysis modes, cancellation and evidence footer; no records saved.
Screenshots: `/private/tmp/hyprn-ui-coherence/analysis-footer-final.png` and
`/private/tmp/hyprn-ui-coherence/evidence-footer-final.png`. Browser returned to Overview.
Unrelated RunPanel/header-metric, planning and research changes preserved. Runner owns
scratch retention; no unrelated processes or stores stopped. Human acceptance and full
release qualification remain separate from this focused presentation delivery.

## Follow-up: action order, primary emphasis and spacing — 2026-10-20

Code `69e9811`. DialogActions now has an explicit primary slot. The shared frame
renders secondary actions before primary actions in DOM and visual order, independent
of editor mounting/mode changes. Primary buttons receive the filled Button recipe;
destructive confirmations retain danger styling. Existing handlers, refs, form IDs,
disabled states and cancellation behavior are preserved. All existing committing
footer actions migrated; no label-based role inference or CSS-only ordering.

Shared CSS gives tab content space-4 separation and labelled controls one label-gap,
removing stacked gap/margin spacing. Live model reader gap changed from 0 to 16 px;
model version and both Experiments selectors measure 6 px caption/control gaps.
Live assumption and both new-analysis modes show Cancel before highlighted Apply/Save.
No forms saved or model runs launched; browser returned to Overview. Screenshots:
`/private/tmp/hyprn-ui-coherence/model-tab-spacing.png` and `ordered-popup-actions.png`.

Verification: `./hyprn-mvp dev check <group> --keep-scope` in locked isolated fixtures:
- combined-static 9/9, 8.07 s, scope `33e45c33-3378-4911-b9d3-f33a12c85ce6`, exact
  final source tree immediately before the code commit (no later source delta).
- ae-ui-model 7/7, 39.27 s, `094a4a04-a1ba-4cbe-a0d0-c9a3dc0266e5`.
- ae-ui-evidence 13/13, 30.24 s, `af13b100-d5d3-47fa-8966-05abb66fff96`.
  Fixture logged one disconnected-request BrokenPipe; all assertions passed.
- calculations-ui 6/6, 61.01 s, `d6417f24-58ca-404e-8600-148a153f3c3c`.
Browser groups ran on `69e9811`. New assertions check footer DOM order, primary styling,
left/right geometry and mode transitions; existing checks cover focus, validation,
save/cancel and immutable records. No native numerical execution claimed.

UI published from that static build with live/source fingerprint guards; backend runtime
unchanged. Prior index and delivery receipt retained. Unrelated working-tree changes
preserved; runner owns scratch retention. Human acceptance/full release qualification
remain separate. This checkpoint is the only post-verification delta.

## Responsive editor completion pass — 2026-10-20

Implementation: `c92ede9`. Shared FormActions now puts inline-editor cancellation
before the highlighted primary action (new study, brief, answer, explanation),
matching DialogActions. Quantity Name/Symbol uses two full-width columns and stacks
at narrow widths. Shared field grids reflow, nested first labels do not double body
padding, empty collection toolbars reserve no spacing, and discard prompts separate
text from buttons. No API, stored study, numerical, version or action-handler changes.
Unrelated RunPanel/header-metric and hosted-staging edits remain unstaged/preserved.

Checks ran through `./hyprn-mvp dev check <group> --keep-scope`, serialized browser
resources. Scope IDs below resolve under the configured scratch-checks root:

| Group | Passed | Seconds | Scope |
|---|---:|---:|---|
| combined-static | 9/9 | 4.55 | 80e8064d-a813-48bd-9570-c38823ff0abc |
| ae-ui-model | 8/8 | 25.12 | 8438a7d7-328b-46cd-a7a5-d51b05cbb34c |
| ae-ui-evidence | 13/13 | 21.99 | 8eec8b03-bd74-4c65-a57d-e2825362794e |
| calculations-ui | 6/6 | 52.44 | c659dc53-430c-4395-9261-f471f3a6be03 |
| brief-ui | 2/2 | 12.01 | 3ddbe257-2155-431b-bfa5-ab3dcd5107ea |
| study-answer-ui | 2/2 | 14.89 | f6fd467f-ed18-4224-bfe3-89bb59793179 |

No failures/skips. First four groups cover the final committed source. Brief/answer
journeys preceded only the final empty-toolbar/discard-prompt CSS and test additions;
their handlers and FormActions source are identical. Earlier development model,
analysis and static passes were repeated only after these layout changes.
Browser fixtures exercise real HTTP/auth/store/controller flows with declared model
transport doubles, not native scientific execution. Final popup checks cover light
and dark at 1440/720/390px, geometry, no horizontal overflow and action order.
Screenshot review includes quantity/component editors and analysis/discard dialogs.

Reviewed live Home/New study, Settings, Models and quantity/component popups, Evidence,
Experiments/configurations, saved configuration, run reader and Overview in Chrome.
Published the final static scope using the existing guarded publisher; source/live
identity checks passed, runtime unchanged, previous index retained by that helper.
Live New study confirmed Cancel then primary Create study. Closed review editors
without saving and restored Dark/Overview. Evidence screenshots remain outside repo
in scoped evidence and `/private/tmp/hyprn-ui-coherence/`.

Test services released by the group runner; scoped artifacts retained for evidence.
Automated and agent visual checks are not human acceptance. Full release qualification
is not claimed for this presentation-only pass.

## 2026-10-20 — transfer dialogs, collection summaries and default appearance

Implemented in `0213c6d`, `faa4b2d`, `f8db825`, `e4ac05e`.
Shared TransferSection separates reusable model records from current-view downloads;
explicit Import model / Export model / Refresh model names, footer import stages,
concise computational export review with context/limits disclosure. Existing file
formats, exact pins, import compatibility checks, export review/creation/download,
command recovery and worker behavior unchanged. Package remains reserved for future
method packages. ResourceCard facts and CollectionStatus enforce compact summaries;
model scope appears once, collection count/actions share a wrapping row. Assumption
help uses the compact nested-heading gap. Settings and initial render share Dark
as default, while preserving an explicitly saved Light choice.

Verification (entry point `./hyprn-mvp dev check <group> --keep-scope`, sourced
existing host environment; scope names below are under the development scratch-checks):

- Final combined-static: 9/9, 4.54 s, scope `b601c41b-ecaa-4b9c-963f-0c415c23cebb`.
  Exact delivered UI source; design guards, tokens, ownership, contracts, smoke,
  existing pure tests, TypeScript and production build pass.
- ui-c: 11/11, 125.86 s, scope `698aab0f-6f1d-424a-8040-d495562e59c3`.
  Real HTTP/Auth/Store with verified native archive transport double; archive review,
  verified binary download, denials, limits, command recovery and 200% keyboard flow.
  First attempt `1adf08ec-7588-4f6e-a48f-041dc5a9accd`: 10 pass, 1 failure because
  keyboard wrap expected Details first; now Contents and limits precedes it. Updated
  traversal expectation and reran. Later deltas are layout-only collection direction,
  separation between transfer groups and the import file-format caption; no handlers.
- foundry-nav: 7 pass, 6 fail, 66.75 s, scope `1dd4af74-b619-44b2-989b-e59ba8c59a22`.
  Model/CSV export and new theme preference + narrow transfer checks passed.
  Remaining assertions outside this batch: navigation button Analyses (now Experiments),
  all configuration input top edges (22 px difference), Analysis running (now Run running),
  removed Execution summary and Execution regions, and run-header left-alignment at
  narrow width (actions intentionally right-aligned). No baseline rerun; these are
  recorded unresolved suite failures, not claimed as a green navigation suite.
  Run header belongs to another session and was not reverted or staged here.

Other static builds were repeated only after live review found missing transfer-group
spacing and an inherited column direction on the collection toolbar. No broad repeat.
Guarded UI publisher delivered final static scope, verified source/live/runtime identities,
retained previous index and left runtime/data unchanged. Live Chrome verified model actions,
export/import dialogs, analysis/configuration lists, selected-version identity and toolbar
geometry. Final screenshots: `/private/tmp/hyprn-ui-coherence/model-transfer-final.png`
and `compact-collection-cards.png`. No live authoring writes or model executions.
Browser fixtures/services released by runners; evidence scopes retained. Agent visual checks
are not human acceptance; full release qualification is not claimed. Broader navigation
assertion reconciliation remains with the UI acceptance suite, outside this transfer pass.
Unrelated hosted planning, run-header and scientific-state edits remain unstaged/preserved.

## 2026-10-20 — versioned documentation, recoverable deletion and export cleanup

Implementation: `a98a163`. User explicitly approved recoverable Trash/Restore and a
versioned Limits field. Model explanation content 2 adds model limits and per-instance
component descriptions/limits, retaining immutable format-1 readers. Exact model pins,
draft CAS, duplicate/foreign component rejection and downgrade refusal preserve ownership.
Assumptions retain their existing model-owned evidence records. Shared model/component
editors show name, description, assumptions, limits; brief editors use the same section
order and footer hierarchy. Documentation drafts are published using the existing
Save for model version action, not silently substituted into historical readers.
The two owners are not falsely presented as an atomic write: a partial save reports
which documentation remains unsaved. Agent tools and the installed /hyprn source were
updated for the new fields, their ownership and exact-version publication.

Shared design changes: sunken reading sections, field hints, label/value typography,
Cancel/Save placement and nested-dialog dismissal. Export model remains only on Models;
Source files and Export scope disclosures are removed (Python source remains in the
portable model record). Computational export keeps the reviewed digest, recovery and
verified download flow with clearer actions and optional technical details. Home uses
Delete → Move to Trash and Restore via the unchanged archive API; no permanent deletion.
Brief details are compact and right-aligned; Conclusion leads with Recommendation then
Evidence and reasoning. No demo-specific content was introduced into application code.

Checks through `./hyprn-mvp dev check <group> --keep-scope`, existing host environment:

| Group | Pass | Seconds | Scoped evidence suffix |
|---|---:|---:|---|
| explanations-api | 12 | 10.85 | 13d8ee09-47fd-4352-8a77-646c19019cba |
| agent-tools | 327 | 53.04 | 4d039468-c142-4f6a-8704-ac2e15765791 |
| contracts | 127 | 8.86 | 0a160f46-e950-4c88-bde5-de96fcf56fcc |
| ae-ui-model | 9 | 28.80 | c1ed4c40-d255-452e-81ab-56b4ceb541ef |
| ui-c | 11 | 126.89 | 7b053984-82cd-4daf-8cda-c0e4a62bb420 |
| combined-static | 9 checks | 4.77 | c78df637-ea41-402c-8582-76b332c0cb3b |
| brief-ui | 2 | 12.72 | fe365b1b-27fb-4e98-b13e-13224f1954f3 |
| study-answer-ui | 2 | 16.15 | 24589ea6-b37a-438f-a1a6-91a67342acf3 |

Scopes are under the development scratch-checks root. The final static scope contains
the delivered production build, TypeScript and all design/ownership/contract checks.
Backend and agent source did not change after their passing runs. Model/export browser
checks cover final production source; brief/answer checks ran after the implementation
commit. The later test-only answer delta checks the evidence in its new section.
Skill quick_validate passed. No repeat of already-green numerical qualification.
Browser fixtures exercise real public HTTP/auth/store/controller paths, with declared
model/archive transport doubles; they do not establish native numerical qualification.

Development failures and their resolution:
- Static scopes 598af512-28db-494e-b3b8-6881db11bc87 and
  971f48ba-13a4-483d-b27a-678a7e3fe38b found old label expectations in the contract guard;
  updated to the intended Trash/export controls. Subsequent static checks passed.
- Model scope 220ad1ed-658a-4c12-955b-99230b7a972a: 4 pass / 5 fail. Nested Escape
  bubbled into the parent editor; fixed at ActionDialog's event boundary. Updated
  duplicate-reader selectors, description heading expectations, and authenticated
  request use in the new test. Scope c58556b0-5c9b-4b36-863b-5c32afa01c6e: 7 pass /
  2 fail (parent Model actions dialog still open; text selector included hidden reader).
  Corrected the browser journey/selectors; final model group passes all nine.
- Export scope 23870fce-ecf9-4810-babf-c661e1fcc3ba: 9 pass / 2 fail, both stale
  wording/focus-order expectations after the new disclosures. Updated assertions;
  final export group verifies all eleven including stale inventory recovery.
- Answer scope c56d8c69-21e2-4273-acdc-c4bb88494258: 1 pass / 1 fail: evidence basis
  moved out of Recommendation as requested. Assert it in Evidence and reasoning;
  final group passes both.

Publication: guarded publisher captured source/live/runtime fingerprints, backed up
previous index and deployed final static scope. Restarted only the verified demo web
process to serve format 2. First restart attempt refused the check-only scratch root;
second refused the protected demo port after stopping the old owned web process.
Relaunched with the demo's exact root and port exception scoped to this command,
retaining other installations' protected ports. Web ready confirmed at 54821; numerical
workers/runtime configuration unchanged. No authoring records modified or model runs.
Live Chrome verified unified component editor, Cancel, Home Trash confirmation/Cancel,
and recommendation/evidence. Screenshot: `/private/tmp/hyprn-ui-coherence/component-documentation-final.png`.
A later optional See details inspection lost its browser connection; prior live review
and fixture checks are complete. No live Trash/Restore mutation was performed; the
underlying archive/restore implementation and authorization were unchanged.

Test runners released fixture services; evidence scopes retained. Unrelated hosted
planning, run-header, scientific-state and analysis-design edits remain unstaged.
Automated/agent visual checks are not human acceptance or full release qualification.
The earlier foundry-nav suite failures documented above remain outside this batch.
