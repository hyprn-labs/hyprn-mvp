# Simplified analysis reader — 2026-10-19

User approved a generic connected Results table and Surrogate section, preserving
sampling, assessment and saved-version behavior. Product `5399eb2`, authenticated
browser-test follow-up `a27177f`, narrow-table recipes `f29850c` / `4a36b2e`.

- One header/description/version/settings owner. Exact identities in RecordDetails.
- One member row connects explicit inputs, selectable execution, outputs and requirements.
  Unexecuted members remain; partial run-list coverage never implies Not run. Ten member
  rows per page, four concurrent detail reads maximum. Point names derive from saved
  sample order; scientific quantities and all prose remain public record data.
- All independent inputs and outputs are available via Columns. Input domain includes
  each saved group's fixed values and ranges. No copied reference name on every point.
- Surrogate training/check record counts are separate, targets remain saved absolute +
  relative tolerances, independent metrics are per output/group. Native checks and fit
  operations unchanged; no model execution or fitting during reading.
- Shared DataTable/comparison overflow, compact hf-result-cell, RecordDetails and existing
  version/settings recipes. Concurrent run/design/planning changes preserved unstaged.

## Verification

All commands through pinned `./hyprn-mvp dev check` with isolated stores.

- `combined-static --keep-scope`: final **9/9**, exit 0, 5.03 s, product `4a36b2e`;
  `/private/tmp/hyprn-analysis-simplified-static-cell.log`.
  Build scope `ff09d0ba-6102-43e6-9f68-909d3679b23b` retained for delivery.
- `calculations-ui`: final **6/6**, no skips, exit 0, 41.06 s;
  `/private/tmp/hyprn-analysis-simplified-browser-verified.log`.
  Test revision `a27177f`; product source `5399eb2`. Later delta `f29850c` only adds
  the existing comparison-table class to two surrogate tables; `4a36b2e` prevents
  splitting a status word in shared result cells. Final build/design
  checks and real narrow-screen review verify that delta without repeating journeys.
  Includes real browser/controller/HTTP/API/auth/receipts/store, preserved saved-version
  selection/revision, explicit choice of two executions and differing scientific results,
  sampled preparation/point reuse and rejected incomplete surrogate assessment.
  Fixture has no modeling service/numerical execution; it does not qualify numerical accuracy.
  Check storage `0dea2563-cfe5-4f84-a076-d23992465b10`, browser scope
  `19cb2ec3-f8ec-47fc-bc96-cb763a82489c` released by runner.

Intermediate failures and fixes:
- First static run stopped at TypeScript: wrapper identity access, missing toolbar summary,
  removed designWord helper and missing Analysis RecordDetails kind. Corrected; next 9/9.
- First browser 4/6: two overly short output-label expectations missed component disambiguation.
  Corrected expectations (duplicate quantity names still display their component).
- Second browser 5/6: new direct write test omitted CSRF authentication. Corrected to use
  the authenticated public analysis run-request boundary. No product auth relaxation.
- Final visual review found fragmented surrogate table names at narrow width; `f29850c`
  applies the shared horizontally scrolling comparison recipe.
- Earlier static scopes retained: `8a2a6116-6ef3-4a15-9a7b-4fa46a20d6ad` (failed),
  `5f45c6b6-6d60-4833-ad1c-a894487e903c`, `663ac960-ef8e-45e5-a039-51b638169202`,
  `5bb3bf2b-948b-44ea-bb12-c0586cc21238`.
  Earlier browser scopes released automatically; logs retained under /private/tmp.

## Live delivery and limits

Published seven UI assets with matched source/live fingerprints and a recoverable
previous index; runtime unchanged. Live study/analysis records and numerical artifacts
unchanged. Real demo inspected: calculated values/criterion outcomes, fixed 10 K input,
page navigation and partial-run state, saved disabled settings with explicit Create new
version, and 24 training / 9 reserved checks / 8 independent assessments per output.
No live runs, fits, sampling or authoring writes were made.
Screenshots: `/private/tmp/hyprn-analysis-dialog/simplified-analysis-live.png` and
`/private/tmp/hyprn-analysis-dialog/simplified-surrogate-live.png`.

This is scoped UI verification and local demo delivery, not release qualification or
human acceptance. Existing wider qualification obligations remain in STATE.md.
Next: user review of the simplified page.

## Unified pagination and numerical validation — 2026-10-19/20

Owner requested one results pagination, compact row navigation, prominent outputs,
validation terminology in UI/backend and a comprehensible surrogate workflow.
Product `4f67735`; final reading/style corrections `006f3a6`, `650aef9`.

- One ten-member page loads all runs of those members automatically, four bounded
  readers at most. The public optional configuration_revision_id filter validates
  membership before reading. Multiple executions retain an explicit selector.
- Outputs precede execution, surrogate role and selected inputs. Configuration names
  and execution status are link Buttons. Shared comparison-table links preserve short
  names while long authored labels can wrap. Loading is distinct from missing output.
- New sampled analysis format 3 and estimate format 2 name validation_count/validation.
  Predecessor records/digests remain unchanged. Frozen worker protocol vocabulary is
  adapted explicitly; numerical algorithms, partitions and error thresholds are unchanged.
  New public reader unions, UI types, owner tool guidance and /hyprn references agree.
- Surrogate reader explains estimates between calculated points. Build and validate
  takes explicit absolute limits and relative percent (converted explicitly to API
  fraction); blanks are rejected. It names use of the latest recorded run per point.
  Method-selection points remain excluded from independent validation metrics.

Verification through ./hyprn-mvp dev check (isolated stores):

| Group | Result | Log |
|---|---|---|
| calculations-api | 67 passed; 38.60 s | /private/tmp/hyprn-analysis-pagination-api.log |
| contracts | 127 passed; 8.67 s | /private/tmp/hyprn-analysis-pagination-contracts.log |
| agent-tools | 326 passed; 57.69 s | /private/tmp/hyprn-analysis-pagination-agents.log |
| local-api-client | 18 passed; 9.26 s | /private/tmp/hyprn-analysis-pagination-owner-client.log |
| calculations-ui | 6 passed; 42.82 s | /private/tmp/hyprn-analysis-pagination-ui-verified.log |
| combined-static --keep-scope | 9/9; 4.88 s | /private/tmp/hyprn-analysis-pagination-static-links.log |

Browser verification covers saved settings/revision, role-preserving sample extension,
member pagination, explicit run selection, incomplete surrogate refusal, required
error limits and percent-to-fraction preservation. API tests also prove old-format
readback is identical after a new-format extension, new estimate roles, filtered run
pagination and nonmember refusal. Browser/API transports do not establish numerical
accuracy; the attested numerical engine was not changed or requalified.

Earlier browser attempts each passed 5/6 and exposed obsolete test assertions: Check
instead of Validation, then No runs yet instead of each row's Not run. Corrected; no
product guarantee weakened. Initial TypeScript successor-union errors corrected before
checks. Final post-browser delta only fixes Loading wording, latest-run help text and
shared table link wrapping; static checks and real browser review verify that delta.
The first wrapping selector covered th only; real DOM uses td for point cells, so
650aef9 covers both. No repeated numerical work for these presentation changes.

Delivery: seven UI assets published atomically with source/live fingerprints and a
recoverable previous index. Final retained build scope:
cb7f5e1a-04b6-4bc2-8087-b8d277ef2ffc. Earlier static scopes d4967185,
83267853 and c5a7193c retained under the runner's bounded scratch policy. API/browser/
agent scopes released by their runner; logs and check-storage evidence retained.

The public demo showed one study, 36 stored runs and no active sampling, fitting or
run operations before restarting its own web/dispatch processes. First restart refused
because a warm surrogate was a second child; narrowed selection to the exact dispatch
child. Test environment values then correctly refused the live scratch root/port;
restarted with the verified demo scope and its own port excluded from the other-live
installation denylist. Bridge shutdown closed its warm surrogate normally. Current
web and dispatcher are running, numerical attestation current; runtime.json unchanged.
No authoring records were changed, and no model run or fit was submitted on the demo.

Live review reaches points 21–33 with real calculated outputs without Load more runs.
Existing surrogate retains 24 training and 9 validation records, 8 independent assessment
points per output, and prior error metrics. Narrow and wider views confirm compact point
links, visible leading outputs and the clarified dialog. Screenshots:
/private/tmp/hyprn-analysis-pagination/results-live.png and
/private/tmp/hyprn-analysis-pagination/surrogate-dialog-live.png.

Other session's six tracked design/run/planning edits and untracked research documents
remain untouched and unstaged. This is scoped verification/local demo delivery, not full
release qualification or human acceptance. Next: user review; existing release obligations
remain open in STATE.md.
