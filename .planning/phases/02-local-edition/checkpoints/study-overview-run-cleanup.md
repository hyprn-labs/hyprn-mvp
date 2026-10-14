# Study overview, evidence and run presentation

Authorization: user feedback following the Study details demonstration, within the focused
local demo delivery plan. Implementation commit: `8453b83`, based on `cdc6e08`.

## Delivered behavior

Overview has one About this study card. Its Study question reads the most recent saved
modeling approach through existing access checks. Draft questions and study descriptions
do not replace it.
Loading, unavailable, retry, absent-version and denied states retain their distinctions.
The card omits repeated approach scope. See more details and View modeling approach share
a wrapping action row with token spacing. The separate Edit study dialog preserves the
name and description writer, labels the latter Study list description, and explains where
the question is edited. Metadata attribution stays with that editor.

Limits use the compact evidence row composition used by assumptions. Evidence detail leads
with its title, original content and inert source references. Relationships use plain
language; conflicting evidence remains visible. Version and stored scope/resource metadata
remain inspectable in Record details, and downloads preserve the complete evidence record.

Run Results contains one complete output table, with Output, Value and Units columns. The
arbitrary first-four preview is removed. Missing outputs retain not computed and their
reason in the Value cell. Full precision remains available. Export model and data names the
existing portable model/diagram/quantities/source capability; Export computational record
still identifies the run archive with dependencies and scientific context. Run export help points to that run's
Model tab, avoiding a change to the current model.

No API, numerical model, runtime or stored scientific content changed. Formatting expansion
is limited to touched syntax nodes; no design or style baseline was amended.

## Executor verification

All group commands used `./hyprn-mvp dev check <group>` in the isolated worktree with the
existing development environment and scoped OS temporary fixtures.

- `style-ratchet`: 33 passed, 0 failed. After that pass, the final delta restores untouched
  RunPanel formatting and adjusts formatting-sensitive UI source guards. The root's
  integrated style run covers this final delta.
- `combined-static`: 6 commands passed, 0 failed: design checker (no FAIL), token check,
  UI contract wiring, criterion records, TypeScript and scoped production build.
- `ui-navigation`: 6 passed, 0 failed, 0 skipped, 0 flaky. The current UI talks to the isolated
  browser API double; this proves metadata edit guarding/navigation and renamed export
  controls, not the real installation or scientific workflow.
- `python3 ui/test_design_tooling.py`: 13 passed, 0 failed.
- `node ui/design_smoke.mjs`: all checks passed, 50 renders; scratch self-released.
- `git diff --check`: passed. Required commit hooks were executable; commit completed.

Final static/browser evidence: `hyprn-orchestration-verification-jjr_h8xt`; style evidence:
`hyprn-orchestration-verification-p2real7h`. Their archived scope metadata and reports keep
artifact identities and exact commands. Nine task-owned check scopes were archived and
released, zero remaining. The live demo's authoring store, services and author records were
not touched.

## Failures and corrections

Five style runs initially finished 32 passed / 1 failed because changed lines inherited
long-line debt. Range formatting exposed two test-selector syntax typos and a formatter
range-offset problem, corrected before verification. Untouched legacy test signatures were
restored; changed strings were wrapped. Evidence archives: `5nlnvr_6`, `emctpp49`, `ta18ffe1`,
`cvtl1ti4`, `5i4ivoag` (each has the `hyprn-orchestration-verification-` prefix).

One combined-static run passed its first two commands then failed source-wiring checks
because formatting changed literal source substrings. Restored untouched RunPanel wiring
and adjusted the Overview guards to the same formatted calls. The final six-command run
passed. No API behavior or security guard was relaxed.

## Integrated acceptance and live demo

Integrated UI commit `36d9967`; corrections `9026f91` (guard wrapping), `7ed69fa`
(zoom selectors), `05bb96b` (visible-copy assertions), and `ed27ba8` (visible evidence
attribution). The final application UI is `ed27ba8`. Later changes only record evidence
and clarify the matching design rule; no API or runtime behavior changes.

Each group used `./hyprn-mvp dev check <group>`:

| Group | Passed | Failed / skipped |
|---|---:|---:|
| naming | 9 | 0 / 0 |
| hygiene | 5 | 0 / 0 |
| guard | 116 | 0 / 0 |
| units-guards | 138 | 0 / 0 |
| style-ratchet | 33 | 0 / 0 |
| combined-static | 6 commands | 0 / 0 |
| ui-navigation | 6 | 0 / 0 |
| foundry-nav | 8 | 0 / 0 |
| ui-reading | 15 | 0 / 0 |
| approach-ui-reading | 16 | 0 / 0 |
| approach-ui-assumptions | 18 | 0 / 0 |
| agent-ui | 25 | 0 / 0 |
| ae-ui-model | 6 | 0 / 0 |
| ae-ui-evidence | 12 | 0 / 0 |
| units-ui-history | 14 | 0 / 0 |

The final evidence/attribution change reran style, static, agent-ui, ui-reading, both
approach groups and the three evidence/history groups on `ed27ba8`. Earlier navigation,
run-output and guard passes remain applicable: the later delta restores only the evidence
author label and corrects test selectors. All 120 browser tests in the union pass.
Design tooling and smoke evidence above remain applicable. Final term scan: 0;
`git diff --check`: pass.

Integrated failures were corrected, without changing baselines or weakening assertions:
style 32/33 identified one guard line; foundry-nav 7/8 found old metadata selectors;
ui-reading 13/15 included the closed editor's text instead of visible copy; agent-ui 23/25
found the removed author label. Restoring the label preserves the distinction between the
note's author and its cited source. One terminology scan finding in this checkpoint was
rewritten; the final scan has zero findings.

External archives are `hyprn-orchestration-verification-` plus `swnfk0hv`, `a6ljso68`,
`zmdp30wr`, `_ws6arma` and `pyph828h`. This checkpoint pins commits; reports retain exact
commands, timings, artifact identities, failures and releases. All 26 integrated scopes were archived and
released, zero remaining. The demo scope remains retained.

The production UI was rebuilt into the existing owned static directory without restarting
services. Runtime bytes and all 49 attested source paths remain unchanged. Actual browser
inspection verifies one About card, the full saved question, adjacent footer actions with
a 12px token gap, matching assumption/limit evidence rows, the exact source version, and
all eleven hydrogen-run outputs in three columns. Model download retains exact version
`420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`. Light-theme live captures and dark/200%-zoom
fixture checks are retained; reference-image comparison remains unavailable.

The computational-record preview is queued because the retained demo dispatcher omits
export processing. Request `6488355f-f5ca-4005-8aea-7ecb3b4aa0a9`, original command
`3923d30a-a01b-48e9-92de-fa116c58cfdf`, was not resubmitted. Archive completion/download
is unverified. Preserve and reconcile that request when the export loop is enabled.
No scientific authoring records or numerical results changed.

Live evidence is retained under the demo scope's `evidence/overview-run-cleanup` and
indexed by `file-identities.json`. Automated verification is not human acceptance.
Full qualification, the unregistered legacy export-test tag and broader served-suite
repair remain outside this presentation task; no phase or release completion is claimed.
