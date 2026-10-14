# Delivery plan — restore the local fuel workflow through the cleaned API

## Current instruction — simplest working demo, 2026-10-14

The product owner explicitly rejected the preceding subset-heavy demo plan. The
current objective is to get the local application working with the cleaned API and
Codex authoring the whole engineering workflow in a loop from the fuel brief.
This section replaces that demo plan. The earlier A–D plan below is a record of
later product obligations, not the current execution queue or demo gate.

Use the existing public application API and ordinary local user authentication,
through a thin local client Codex can invoke. Reuse the existing deployment managers
and current runtime. Do not finish the dedicated agent platform to demonstrate
agentic use of the application. MCP is optional only if already usable and cheaper;
its completion is not a prerequisite. No new delegation/bootstrap system is needed.

For this owner-operated local demonstration, API actions use the authorized local
user session and appear under that user identity. Distinct delegated-agent identity,
attribution chips, agent-specific permissions and activity reporting are not demo
requirements. The helper handles normal login/session headers without printing
credentials; it neither disables server authentication nor changes the public API's
normal authorization. The local user authorizes the scientific workflow, not deletion
of existing records or changes to memberships. Application actions still go through
the public API, never through direct database/modeling-service access.

| Remaining delivery step | What to do | Done when |
|---|---|---|
| 1. Run the current app | Use existing deployment/runtime managers and the verified refactored code. Fix only actual startup or UI blockers. | The local UI and public API work against the real modeling/execution services. |
| 2. Give Codex an API client | Reuse a working client if available; otherwise add one thin local helper for login, API requests and receipt/status reads, plus concise workflow guidance. Use the existing user session across study creation and subsequent work. | Codex creates a study and immediately reads/edits it through the public API, without manual token renewal. |
| 3. Exercise the authoring/run loop | From the brief and legitimate source material, Codex records context/evidence/approach, creates and edits components/model, saves configurations, submits runs, reads errors/results and revises its work. Implement only missing API/client behavior encountered on this path. | Codex completes a genuine author-edit-run-inspect-revise loop using real execution; records are visible in the UI. |
| 4. Finish the fuel answer | Codex performs the fuel comparison and answers in chat with actual results, assumptions, sources and limitations. No preauthored model or seeded result substitutes for its work. | The engineering question has a defensible answer supported by retained runs, with any scientific uncertainty stated honestly. |
| 5. Rehearse and stop | Run focused checks for changed behavior and one complete Codex fuel rehearsal on the delivery tree; inspect the actual UI and fix blockers. | The brief-to-conclusion journey works locally without manual modeling or run submission. Record concise evidence and stop adding features. |

### Open Phase 2/3 tasks: deferred by default

No remaining original task is a prerequisite merely because of its number or plan
position. Reuse existing implementations; do not build every planned agent wrapper.

| Original tasks | Current disposition |
|---|---|
| 2.9–2.14 | Defer productized CLI/setup, OS adapters, store-initialization redesign/reset, uninstall/re-adoption, clean-room packaging and broad docs. Use existing managers and existing scoped test cleanup. Borrow only code needed to fix an observed startup/client blocker. |
| 3.11–3.23 | Defer notes/reports, MCP completion, evaluation infrastructure, delegated tokens/relay/kit, client matrices, new agent journaling/guards/policy work and activity UI. Existing API validation, authorization, revision checks and receipt recovery stay in use. |
| 3.24–3.26, 3.31–3.32 | Their scientific capabilities are essential, but their dedicated agent-tool implementations are deferred. Use existing public study/evidence/approach/model/configuration/run endpoints directly through the thin client; add only missing behavior required by the real workflow. |
| 3.27–3.30, 3.33–3.36 | Defer staged agent-platform reviews/enablements, standalone authoring evaluation, saved-conclusion tool, broad live matrix and phase closure. Replace their demo scheduling with the focused end-to-end rehearsal above; do not claim those original tasks passed. |

The already completed architecture/API refactor and 3.16-paths remain retained.
Preserve useful in-flight CLI/MCP work at a clean checkpoint; do not finish optional
work merely because it started and do not discard others' edits. The executing
orchestrator decides safe integration boundaries and keeps deferred work recoverable.

### Explicit demo exceptions and retained correctness

This instruction explicitly supersedes the old demo requirements for the installed
study kit, agent-only MCP access, new-study token binding, delegated attribution,
Agent activity UI, protocol/client-support decisions, writer-token capability reviews,
staged registry enablement and full current-host qualification. Those gates remain
for the later delegated-agent product/release; this demo does not mint or enable its
writer tokens. Historical accepted ADRs are not edited or claimed satisfied.

Retain the current restricted execution environment and its valid attestation,
scientific input/unit/provenance checks, immutable saved versions, actual computed
results and existing API command-receipt recovery. Never blindly repeat an uncertain
run launch. Do not spend this milestone redesigning these already working mechanisms.
No arbitrary physical defaults, host-side model execution or fabricated results.

Changed behavior receives focused tests through the established check entry point;
API changes retain contract tests and the UI contract checker. Run real native
execution and inspect actual UI persistence as part of the final journey. Full-suite
qualification, broad fault-injection/client matrices, multi-OS proof, new security
features and release audits move later. Existing failures that actually block or
invalidate the demonstrated journey still must be fixed. Use existing isolated test
scopes, preserve authoring records, and do not add an uninstall or cleanup framework.

Use the fuel reference to check the scientific answer; do not build a new G1 grading
framework or make every evaluation metric a prerequisite. If a source, unit ambiguity
or model limitation blocks a defensible answer, resolve or report it honestly; a
working interface alone is not evidence of a successful engineering study.

This is a local demonstration, not full Phase 2/3 completion, a supported delegated
agent release, a portability claim or permission to publish/deploy elsewhere.

## Earlier A–D amendment — retained full-product obligations

Status: approved priority change, executable planning amendment; no implementation or acceptance is claimed here.
Date: 2026-10-14. The October 15 demonstration is an aspiration, never an acceptance waiver.

## Authority and execution contract

This amends the pending work in [Phase 2](phases/02-local-edition/02-PLAN.md) and
[Phase 3](phases/03-agent-tools-for-coding-agents/03-PLAN.md), preserving their task IDs,
completed commits, checkpoints, scientific invariants and security requirements.
Read this amendment before either original plan. Where this document changes a dependency,
slice or acceptance boundary it governs; otherwise the original task's files, actions,
read-first references, checks and done definition apply in full.

Closely related tasks or slices may share a fresh executor context under the cadence
amendment below. A slice checkpoint is
`phases/<original-phase>/checkpoints/<task>-<slice>.md`; the original `<task>.md` closes
only when every slice and every original acceptance item is verified. Never rewrite a
historical checkpoint to make a partial task appear complete. Every checkpoint records
explicit-path commits, exact commands and pass/fail/skip counts, all failures, source and
artifact identities, released scratch scopes and remaining risks. The orchestrator reruns
acceptance on the committed tree before dispatching dependants; it alone updates status.

### Execution cadence amendment approved 2026-10-14

This approval supersedes the earlier one-task-per-context and duplicate broad executor/orchestrator
acceptance rules for remaining A–D work. Batch 2–4 related tasks with explicit file ownership,
separate atomic commits and task-to-evidence mapping. Never cross an unresolved human decision,
capability enablement review or stale-attestation boundary. Run specific prerequisite checks
before dependent steps within a batch; dispatch no outside dependant before integrated acceptance.

Executors run focused behavior checks and useful cheap guards. Every API change still passes
contract tests and the UI contract checker. After integration, the orchestrator reviews the diff
and runs the union of all required acceptance groups once on the exact committed tree; a group
may satisfy several tasks. Preserve every special assertion, comparison, required no-cache build,
artifact/attestation check and visual review. Rerun affected groups after relevant source, test,
fixture, dependency, configuration or runtime changes, conflict resolution, failure or concern.
Never reuse pre-integration evidence for a changed tree.

Checkpoint/status-only commits need document, whitespace and term checks, not repeated application
acceptance, when behavioral inputs are unchanged. Record the tested implementation commit and exact
documentation delta; generated instructions/playbooks and executable examples are behavioral inputs.
Keep compact task checkpoints or one shared evidence table with commits, commands/counts, identities,
every failure, cleanup and remaining risks. No new reporting or result-cache framework is required.

Parallelize disjoint work and lightweight checks where resources permit; name one shared-wiring
owner and serialize fixed-scratch/native users. Keep competing heavy work out of qualification.
Reuse verified development caches while retaining all required clean builds. Current-host final
qualification, scientific/security invariants, native numerical execution, safe cleanup, both-client
live UI evidence and human gates are unchanged. E/F remain deferred, not removed. Continue in-flight
2.6 without restarting successful builds/checks; apply this cadence at the next safe boundary.

All `CHECK` references in the original plans now mean `./hyprn-mvp dev check`.

### Parallel scheduling amendment approved 2026-10-14

Use two implementation lanes by default after verified prerequisites; a third is only for
independent lightweight work with spare resources. Preserve the exclusive ordered
2.8c → 3.16-paths → 2.8 attestation window and its tested source tree. Do not interrupt
valid in-flight baseline work or mix unrelated implementation into that tree.

The following administrative edges supersede the wave table's serialization:

| Earlier ordering | Approved replacement |
|---|---|
| Wave 4: 2.10-host → 3.12 because runner/guard registration overlaps | Their disjoint implementation/test files may overlap once their real prerequisites pass; one integrator owns runner/guard registration and verifies it before dependants proceed. |
| Waves 5–6: all local lifecycle work before MCP/evaluation implementation | Local-installation and MCP implementation may overlap where shared registration is the only remaining constraint. Keep genuine interface/store/fixture dependencies; explicitly serialize 2.11's store-creation test migration and any intersecting files. |
| Wave 10: 3.23 waits for the whole 3.22 ∥ 3.24-evidence wave | Start 3.23 once 3.22's actual activity API/contracts are integrated and verified and all other original prerequisites hold. 3.27-evidence still waits for both verified UI and evidence-write results. |

Use the existing approved overlaps (2.9/3.11, 3.20/3.21, 3.22/3.24-evidence,
3.24-remaining/3.25/3.26, 3.32/3.33) from verified dependencies without unnecessary
whole-wave barriers. Keep one editor for each shared contract/type generator, API composition,
store/schema, UI shell and CLI documentation surface. The orchestrator owns current state
and integration of `deployment/checks.py` and `deployment/tests/test_repository_guard.py`
when parallel workers need them; workers provide exact registration changes without editing
those shared files concurrently. If genuine dependencies make overlap unhelpful, keep the
existing order; do not introduce compatibility layers for scheduling.

Budget CPU, Docker, browser, database and port use as well as files. Native/fixed-scratch
work stays serialized; qualification freezes its tree and excludes competing heavy work.
Focused executor checks, integrated acceptance, exact artifact comparisons, clean builds,
real public-boundary/live-client evidence, cleanup and human capability gates remain intact.
No new planning cycle, orchestration framework, publication or capability approval is implied.

No direct invocation of `deployment/checks.py`, second deployment harness, alternate agent
stack, new dependency, native payload exposed to a client or direct scientific-store access.
The existing operator mint command remains the credential administration seam; scientific
actions from the CLI, agent tools and UI all use the public API.

## Outcomes and acceptance

| Bucket | Outcome | Evidence required before calling it achieved |
|---|---|---|
| A | Clear application ownership and installation boundary | Existing router, view, run-read, receipt-recovery and import-layer refactors remain verified; 2.6 finishes; PD-2.4 is answered; 2.8b/2.8c/2.8 preserve history, close the attestation window and bind the installed committed source. Architecture §7 and its boundary test agree. |
| B | One consistent public API for every client | Generated contract and UI types are current; shared authorization, scoped errors, receipts and owner-decided recovery are used by UI, CLI and MCP; tools name owners and stored outcomes; contract, API, boundary and UI-contract groups pass after the new activity route. No wholesale API rename is implied. |
| C | Both local clients make a visible, persisted scientific write | On fresh scratch installations on the demonstration host, Codex and Claude Code each create one evidence note in an existing study. The UI reads the saved evidence version, displays the correct attribution and Agent activity link, and preserves it after restart. Restricted token authority, reconciliation, conflicts, guards, revocation, injection and local-boundary evidence pass. |
| D | Model → configurations → real runs → results → saved conclusion | Both clients perform full G2: 110 kPa met and 121 kPa violated against 120 kPa, with explicit units/provenance and exact pins; failure outputs remain unavailable. The UI opens the retained runs and saved “Study conclusion” evidence version with attribution/activity. Full authoring/control review and live G2/G3/G4/G5/G6/G7/G8 obligations pass; G1 is recorded. |
| E | Portable, documented local edition | Complete all remaining real OS adapter proofs, macOS/Linux clean-room installs, cold/warm timings, host/client parity and broad operating/development documentation; close original Phase 2/3 task records only against their full criteria. |
| F | Documents and qualified first release | Execute Phase 4, then plan and execute Phase 5: independent code/security/UI reviews, final qualification, fresh-account install, first installation and separate product-owner UI acceptance. |

Freshness promise for C and D: use the existing Refresh action or navigate/reopen the
record/page. Automatic live synchronization is not claimed. The browser must retrieve the
persisted version and attribution after this action; a transcript, seeded UI double or agent
claim is not evidence of persistence. Human evaluation and automated evidence stay separate.

## Complete original-task disposition

“Retained” means already verified, not to be repeated as implementation. “Full” preserves
the original task unchanged except the dependency replacements below. The two plans contain
18 and 41 original task IDs respectively; slice names do not change those counts.

| Original ID | Bucket | Disposition |
|---|---|---|
| 2.1 | A | Retained: entry point and pinned toolchain. |
| 2.1a | A | Retained: formatting/lint ratchet and its approved dependency audit. |
| 2.2 | A | Retained: path policy and configuration. |
| 2.3 | A | Retained: installation-driven execution. |
| 2.4 | A | Retained: installation-driven managers and follow-up. |
| 2.5 | A | Retained: native environment. |
| 2.6 | A | Finish in flight, full; sole pin/fixture owner until accepted. |
| 2.7 | A | Retained; combined-tree verification after 2.6 still required. |
| 2.8a | A | Full blocking PD-2.4 decision, no implied approval. |
| 2.8b | A | Full function-keyed dynamic-loading test. |
| 2.8c | A/B | Full approved schema split and preserved pre-split history sample. |
| 2.8 | A/B | Full snapshot/binding and closure of the attestation window. |
| 2.9 | C prerequisite | Full CLI foundation and all platform refusal tables. |
| 2.10 | C prerequisite/E | `host`: all adapter implementation and current-host proof; `platforms`: remaining real host proofs. |
| 2.11 | C prerequisite | Full lifecycle, explicit store creation/schema refusal/reset safeguards. |
| 2.12 | C prerequisite | Full uninstall/re-adoption, including safe confirmed purge. |
| 2.13 | C prerequisite/E | `smoke`: real local smoke and owner API client; `clean-room`: both clean hosts and timings. |
| 2.14 | C prerequisite/E | `runtime-docs`: CLI/refusal/operator prerequisites; `guides`: remaining install/developer/portability guide acceptance. |
| 3.1 | A/B | Retained: principal and authorization intersection. |
| 3.2a | A/B | Retained: practices research, no new external research required. |
| 3.2 | A/B | Retained: recorded product decisions, including fixed session tool lists. |
| 3.3 | A/B | Retained: aligned specification. |
| 3.3a | A/B | Retained: per-owner API routers. |
| 3.3b | A | Retained: view registry and model controller. |
| 3.3c | A/B/D | Retained: one run-row read and light status. |
| 3.3d | A/B | Retained: server-decided receipt recovery. |
| 3.4 | A/B/C | Retained: administration, attribution read and layer table. |
| 3.5 | C | Retained: design-system attribution component. |
| 3.6 | C | Retained: attribution integration and browser group. |
| 3.7 | C/D | Retained: attribution on record views. |
| 3.8 | B/C | Retained registry/API client; named C/D slices extend its composition safely. |
| 3.9 | B/C/D | Retained read projections and secret fuzz. |
| 3.10 | C/D | Retained runtime core; queue-limit ambiguity stays open for D review. |
| 3.11 | C | Full outside-study notes/reports, before final store initialization wiring. |
| 3.12 | B/C | Full MCP server, composed registry shared with API policy. |
| 3.13 | C/D | Full scripted read eval, G2 fixture and live runbook. |
| 3.14 | C | Full token commands; current-host prerequisites substituted below. |
| 3.15 | C | Full relay and port-owner refusal. |
| 3.16 | A/C | `paths` inside A's attestation window; `kit` is the remaining full task. |
| 3.17 | C/E | `host`: both clients on demonstration host; `platforms`: remaining host matrix. |
| 3.18 | C | Protocol/kit decision from both current-host probes; broad platform claim remains pending. |
| 3.19 | C/E | `host`: verified client identities/facts; `platforms`: remaining facts and any resulting fixes. |
| 3.20 | B/C | Full reconciliation, error mapping, back-maps and attribution outcome wiring. |
| 3.21 | C | Full guards; no blocked text or secret reaches scientific records. |
| 3.22 | B/C | Full route classification/refusals, draft-rule tests and human-only activity read. |
| 3.23 | C | Full Agent activity page, including Revoke access and accessibility checks. |
| 3.24 | C/D | `evidence`: add_evidence only; `remaining`: create study, study-context/revise evidence and gated reviews. |
| 3.25 | D | Full approach tools and revision-checked draft removal. |
| 3.26 | D | Full model tools, automatic rebind and native proof. |
| 3.27 | C/D | `evidence`: restricted write/control review build; `full`: every original broader scenario. |
| 3.28 | C/D | `evidence`: limited writer decision; `full`: original full-authoring review and run-cap decision. |
| 3.29 | C/D | `evidence`: restricted production enablement; `full`: original broad writer enablement. |
| 3.30 | C/D | `evidence`: both-client visible-write/safety proof; `authoring`: original full authoring evaluation on current host; closes when both slices pass. |
| 3.31 | D | Full configuration tools, explicit sources and conflict behavior. |
| 3.32 | D | Full owner-side readiness admission, bounded waits and uncertain-launch refusal; fix stale cache wording. |
| 3.33 | D | Full deterministic saved conclusion; evidence version is authoritative. |
| 3.34 | D | Full runs enablement, scripted/native G2 and G3/G6. |
| 3.35 | D | `host`: original complete live workflow on both current-host clients; closes when its original per-client criteria pass. |
| 3.36 | D/E/F | `delivery-status`: truthful evidence notes after D; final original task/status closure after E and required phase gate; AGENT-01 remains partial until F. |

## Dependency replacements — exhaustive exceptions

| Original edge or rule | Replacement and retained obligation |
|---|---|
| 3.16 steps 1–2 wait for 2.9–2.14 | Extract `3.16-paths` after 2.8c and before 2.8. It needs completed 2.2; only the later kit needs CLI/install prerequisites. |
| Re-attestation window ends after 2.8c alone | 2.8 closes changes from both 2.8c and 3.16-paths, with all original pending native groups, pins and captures; no execution against stale attestation. |
| 2.8c lists public-api among its immediate checks | Apply its existing current-source-image prerequisite to this group too: preserve the 70-test pre-edit baseline, then run public-api after 2.8 rebuilds and pins the producer. Its test_api fixture uses owned_modeling → setup → reviewed_image, which refuses the old producer after schema edits. No assertion or image-identity check is removed; 2.8c records this acceptance as pending. |
| 2.11 requires completed 2.10 | `2.10-host` provides every adapter interface and current-host round trip; other real OS proofs remain E. No unqualified OS is claimed. |
| 3.14/3.15/3.16 need full 2.14 | Require verified `2.14-runtime-docs` and `./hyprn-mvp dev check docs`; broad guide completion remains E. |
| 3.16 needs full 2.13 | Require `2.13-smoke`, including the owner API client, and completed 2.12. Clean-room transportability is E. |
| 3.17/3.30/3.35 need full 2.13 | Their current-host slices require 2.11, 2.12 and 2.13-smoke; every live stage still uses fresh setup of its exact committed tree, then safe purge. |
| 3.18 waits for all hosts of 3.17 | Require both clients passing `3.17-host`; decide only that host's protocol/kit support. Linux/WSL2 claims and facts stay unverified until E. |
| 3.19 or 3.29 needs full 2.14 | Require 2.14-runtime-docs; each CLI change updates the command/refusal catalogue and passes docs. |
| 3.27/3.28/3.29/3.30 require all authoring tools | Only their named evidence slices may precede 3.24-remaining/3.25/3.26. Full counterparts keep their original dependencies and full acceptance. |
| Full writer issuance follows a single 3.28 | C review authorizes only C's exact tool/effect set. D review explicitly authorizes the expanded set before 3.29-full; C approval cannot satisfy it. |
| 3.31/3.34/3.36 depend on original full stages | Keep 3.31 after 3.29-full; 3.34 after passed 3.30-authoring, 3.32 and 3.33; delivery status after 3.35-host, final status only with remaining evidence. |

All other task, native fixture, contract-generation, human-review and scientific dependencies
remain in force. Full Phase 2 is not claimed unnecessary: its real operational subset is on
the critical path. The schema split remains in A because bypassing it would require a new
approved architecture choice and duplicate re-attestation work; option C at 2.8a still returns
the affected plans for revision before execution continues.

## Topological execution waves and ownership

Each arrow means verification before the next task. Tasks separated by `∥` may run together
only after the orchestrator confirms disjoint exact file manifests and non-overlapping checks.
Numbers are delivery waves, not replacements for original task IDs.

| Wave | Tasks | Ownership / serialization |
|---|---|---|
| 0 | Finish 2.6 | Exclusive modeling images, producer pin, captured fixtures and fixed scratch groups. |
| 1 | 2.8a → 2.8b | Product decision, then boundary test only. |
| 2 | 2.8c → 3.16-paths → 2.8 | Exclusive attested schema/source/manager/pin lane; no shared-fixture native work until closure. |
| 3 | 2.9 ∥ 3.11 | Local CLI files versus runtime notes/schema/catalogue; predeclare runner registrations for 2.9 alone. |
| 4 | 2.10-host → 3.12 | Adapter and MCP group registrations share the runner/guard; serialize those owners. |
| 5 | 2.11 → 2.12 → 2.13-smoke → 2.14-runtime-docs | Local lifecycle/store initialization/cleanup/smoke/docs; serial shared CLI and runner ownership. |
| 6 | 3.13 → 3.14 → 3.15 → 3.16-kit | Shared runner, CLI and cli.md serialized; each registers its missing test group before use. |
| 7 | 3.17-host → 3.18 → 3.19-host | Human client facts, product decision, then identity/spec/kit application. |
| 8 | 3.20 ∥ 3.21 | Journal/errors/back-maps/attribution versus guards/notes; no shared file. |
| 9 | 3.22 ∥ 3.24-evidence | Activity route/contracts versus evidence handler/catalogue composition/tests. |
| 10 | 3.23 → 3.27-evidence → 3.28-evidence | UI owns shell/registry/api.ts/styles and browser runner; then evaluation; then human review. |
| 11 | 3.29-evidence → 3.30-evidence | Existing mint/token path and registry; fresh install and both-client proof: C checkpoint. |
| 12 | 3.24-remaining ∥ 3.25 ∥ 3.26 | Distinct catalogue/test files; 3.26 alone owns native group registration. Production catalogue remains C's. |
| 13 | 3.27-full → 3.28-full → 3.29-full | Shared eval fixtures, full human review and reviewed catalogue/token expansion. |
| 14 | 3.30-authoring ∥ 3.31 | Human authoring evidence versus configuration handler/native tests; serialize heavy native runs and freeze each evidence commit. |
| 15 | 3.32 ∥ 3.33 | Runs/execution/API composition versus conclusion/tooling prose; 3.32's cache wording edit follows 3.33 if same spec is held. |
| 16 | 3.34 → 3.35-host → 3.36-delivery-status | Registry/eval expansion, fresh full workflow on both clients, truthful status: D checkpoint. |
| 17 | E: remaining platform, clean-room, documentation and probe slices | Finish 2.10/2.13/2.14/3.17/3.19; then original 3.36 and Phase 2/3 gates. |
| 18 | F: Phase 4 → Phase 5 | Documents first; qualified release afterwards, per original plans. |

`deployment/checks.py`, `deployment/tests/test_repository_guard.py`, generated OpenAPI/types,
`application/generate_contract.py`, `store.py`, each route module, the UI shell and
`docs/operations/cli.md` have one editor at a time. Register new groups in the existing runner;
after Phase 4 task 4.4 only its designated entry files own group declarations. All native and
durable-fixture users serialize on the fixed scratch scope, regardless of file disjointness.
Hold image builds and other heavy work during qualification. Original large tasks remain
their approved executor units; this amendment does not hide extra tasks inside parallel lanes.

## Executable slice definitions

Paths below are repository-relative. Prefixes in braces denote the explicitly listed files,
not permission to edit a whole directory. All unchanged original task checks remain binding.
New group registrations fail on a missing target/environment or zero selected tests.

### 3.16-paths — put the study-folder configuration inside A's attestation window

- Needs: 2.8a approved, 2.8b and 2.8c verified. Files: `deployment/config.schema.json`, `integration/src/hyprn_mvp_integration/installation.py`, `editions/local/src/hyprn_mvp_local/paths.py`, `deployment/tests/test_installation_config.py`, `editions/local/tests/test_paths.py`.
- Action: implement exactly 3.16 steps 1–2 (D-08, PD-3.2); `studies_root` is absent on the current tree, and the loader rejects unknown fields. Add the optional absolute path without changing worker policy. Preserve location precedence/refusals and test missing field compatibility. Record source hashes and the existing two-sided inventory, keeping all attested inventory paths; 2.8 owns final pins/rebuild/capture. No unrelated loader refactor.
- Verify: `./hyprn-mvp dev check installation-config`; `./hyprn-mvp dev check portability`; `./hyprn-mvp dev check locality-contracts`. Native/attestation checks are pending for 2.8, explicitly recorded, never reported passed here.
- Done: configuration and path tests pass; 2.8 consumes this slice's digest changes, re-attests the combined tree and passes both-sided coverage before A closes. 3.16 remains partial until its kit slice.

### 2.10-host / 2.10-platforms — one adapter implementation, separate proof hosts

- Files/actions: original 2.10 in full. Implement all OS branches and refusal tables now; current-host real scratch credential round trip plus fake-process arguments/clipboard/browser cases. No file credential fallback (D-10, PD-2.2; Phase 3 PD-3.4).
- Verify host: `./hyprn-mvp dev check local-adapters`; `./hyprn-mvp dev check local-cli`. Register local-adapters in `deployment/checks.py` and its guard as part of this slice if not yet present; a non-host real-OS proof is listed pending, not silently skipped by this group.
- Done host: secret-free arguments/output, real host adapter evidence and unavailable-store refusal pass. In E, run `./hyprn-mvp dev check local-adapters` with a scratch Secret Service on Linux and retain original macOS/WSL2 acceptance; close 2.10 only when the complete original matrix is recorded.

### 2.13-smoke / 2.13-clean-room — separate real computation from portable installation

- Needs smoke: full 2.11 and 2.12. Files: `editions/local/src/hyprn_mvp_local/smoke.py`, `editions/local/smoke/sellar.json`; add `editions/local/src/hyprn_mvp_local/owner_api.py` for the owner API client shared by smoke and 3.16, with `editions/local/tests/test_owner_api.py`; CLI wiring stays in the original local CLI owner lane.
- Action: implement the original smoke sequence and both Sellar answers in full, using setup/start, the public API, real worker execution and the original negative cross-site check. The reusable owner client keeps credentials in memory and uses the session/Origin/CSRF protocol and owner-decided receipt recovery. Never reconstruct a result or resend an uncertain run.
- Verify: `./hyprn-mvp test`; `./hyprn-mvp dev check local-lifecycle`; `./hyprn-mvp dev check local-uninstall`; `./hyprn-mvp dev check local-cli` (register the owner-client target there). Purge on success and failure through installation identity checks; record cleanup failures and preserve their scope for investigation.
- Done smoke: both exact numerical assertions, unchanged real-installation configuration/container states, and no resource labelled with this scratch installation remain. The client exists for 3.16. In E, original `deployment/tests/test_clean_room.py` and `./hyprn-mvp dev check clean-room` prove no-cache fresh installs on macOS and Linux with cold/warm timings; no original clean-room assertion is omitted.

### 2.14-runtime-docs / 2.14-guides — a narrow operational prerequisite

- Files: `docs/operations/cli.md`, `docs/operations/troubleshooting.md`, `docs/operations/install.md`, `deployment/tools/check_docs.py`; registration in `deployment/checks.py` and its guard is serialized. The remaining original 2.14 files belong to guides.
- Action: document every implemented command/flag/refusal, setup/start/stop/reset and safe uninstall/purge, credential availability, scratch configuration and source-change/stale-attestation recovery. Mark host qualification truthfully. Implement the original command/help and refusal-code equality check across the complete current CLI, not an allowlist that hides undocumented commands.
- Verify: `./hyprn-mvp dev check docs`; `./hyprn-mvp dev check local-cli`.
- Done runtime-docs: 3.14–3.16 and later CLI edits have a working drift gate and accurate operator instructions. E completes README, per-OS install/uninstall/developer guides, link checks and every remaining original 2.14 criterion; runtime-docs alone never closes 2.14.

### 3.17-host / 3.19-host / 3.16-kit — finish the real read path before writes

- 3.16-kit runs every remaining original 3.16 step/check using 3.16-paths and the owner client from smoke; no late attested loader edit is permitted without a newly recorded re-attestation window. Verify `./hyprn-mvp dev check study-kit`; `./hyprn-mvp dev check docs`; `./hyprn-mvp dev check installation-config`; `./hyprn-mvp dev check portability`.
- 3.17-host uses the original checklist on both installed desktop clients on the demonstration host, with a fresh scratch setup and full read-only G2 fixture. Files: its named checkpoint only; transcripts outside the repository. Neither a scripted MCP client nor one desktop client substitutes for the other.
- 3.18 keeps its blocking protocol/kit decision; an incompatible client returns to planning. It cannot remove either client from C or D. 3.19-host changes only the original 3.19 files, maps measured clientInfo names and marks unprobed platforms pending rather than “Verified”.
- Verify automated support: `./hyprn-mvp dev check mcp`; `./hyprn-mvp dev check study-kit`; `./hyprn-mvp dev check agent-eval`; `./hyprn-mvp dev check agent-tools`; `./hyprn-mvp dev check docs`. Human done: both-client probe rows with exact versions, kit/protocol decision, G2 read answers, secret scan and released scratch installation. E completes the original other-host matrix and associated spec facts.

### 3.24-evidence — the one production write path, using existing owners

- Needs: 3.18, 3.20 and 3.21. Files: `application/src/hyprn_mvp_app/agent_tools/catalogue/evidence.py`, `application/src/hyprn_mvp_app/agent_tools/catalogue/__init__.py`, `application/tests/agent/test_agent_study_evidence_tools.py`, `application/tests/agent/test_agent_write_policy_registry.py`.
- Action: implement original add_evidence with its complete closed input, guards, pointer back-map, scope checks, journal-before-call, receipt reconciliation and evidence_version attribution (D-01/D-02/D-04/D-13/D-18). Preview only where the evidence API supports it; reuse 3.20 rather than inventing an evidence preview API. Preserve original read tools.
- Composition: keep a catalogue of implemented ToolSpecs for injected test registries, but the production `TOOLS` tuple contains only the existing 20 reads, the two outside-study tools and add_evidence. Use a closed reviewed name set in this existing composition module; no stored profile, new effect or parallel permission system. API policy and Runtime receive the same production registry. Stage filtering alone is insufficient: current `Registry.api_operations` does not filter by stage.
- Verify: `./hyprn-mvp dev check agent-tools`; `./hyprn-mvp dev check contracts`; `./hyprn-mvp dev check locality-contracts`. Test actual real-middleware evidence creation, read-only refusal, wrong-study 404, malformed inputs, guarded text, lost reply adopted once, duplicate call id once, and an additive revision race with bounded retry and no changed human record. Synthetic overwrite tests from 3.20/3.22 still prove stale writes never retry.
- Done: evidence creation is production-quality and testable end to end under scratch-only writer delegations; installation minting remains read-only until 3.28-evidence/3.29-evidence. 3.24-remaining in D performs every original study/context/revise-evidence/review-gate action and acceptance, in test registries until its separate review.

### 3.27-evidence — prepare the complete restricted-write safety review

- Needs: 3.22, 3.23, 3.24-evidence. Files: original 3.27 files plus `application/tests/agent_eval/test_scripted_evidence.py`; reuse its real-application review fixture, not a second serving harness.
- Action: seed a study as the Owner, then invoke add_evidence through composed MCP. Verify owner receipt/version, journal, attribution and human activity reads agree; replay/lost reply yields one version. Include guard block/warning, bounded error handling, uncertain recovery, current authority loss, CLI/UI revocation, kill switch, API budget exhaustion and human-only route classification. Exercise conflict preservation with the existing test-only revision tool; keep product writes restricted.
- Run G4/G8 structural checks against the exact C registry, including explicit absence/refusal of study creation, evidence revision, model/approach writes, configuration and submission routes. G5 stays active. Scope G2 to read questions plus the evidence write; keep full G2/native computation acceptance in D. No claims that the full G2 authoring scenario passed.
- Verify: `./hyprn-mvp dev check agent-eval`; `./hyprn-mvp dev check agent-tools`; `./hyprn-mvp dev check agent-ui`; `./hyprn-mvp dev check mcp`. Fixture smoke refuses non-scratch roots and releases its scope. Run limits remain tested as implemented in 3.10; contradictory “20 accepted while capped at 10 queued” acceptance is reserved for the explicit D decision, never weakened silently.
- Done: the product owner has a concrete visible evidence write, its refusals, attribution/activity and revocation to review. Original all-tool scripted authoring, draft removal, study creation and run-cap scenarios remain owned by 3.27-full in D.

### 3.28-evidence / 3.29-evidence — review first, enable exactly the reviewed write

- 3.28-evidence is a blocking human decision using the original review fixture, with one recorded `Review:` answer and the exact approved tool names, effects, commit and evidence locations. It covers the full C control set above and the original oversight requirements; it grants no model, approach, study-context, evidence-revision, study-creation or run capability. Listed changes return to their owners before approval is effective.
- 3.29-evidence files: original 3.29 files plus `application/src/hyprn_mvp_app/agent_runtime/tokens.py` (propagate read_only through the real mint path), `docs/agents/tooling-spec.md` and `docs/agents/evaluation.md` (exact intermediate availability/counts).
- Action: use the existing delegation fields: eligible Owner/writer gets only read, record, outside_study; reader and explicit --read-only keep read/outside_study. No draft or submit effect. Existing tokens remain as minted. Production registry stays the reviewed C tuple; `LOCAL_STAGE=authoring`, `REGISTRY_VERSION=0.1.1`, a documented evidence-only slice. Semver remains the existing three-integer format; no new stage enum.
- Verify: `./hyprn-mvp dev check agent-tools`; `./hyprn-mvp dev check mcp`; `./hyprn-mvp dev check study-kit`; `./hyprn-mvp dev check docs`. Assert exactly 23 tools for C writer and 22 for read-only, names as well as counts; all definitions stable within a session, no list-changed notifications, registry/tool-definition/playbook hashes recorded. Test direct API refusal for every unexposed write using the actual production registry, not only tools/list.
- Done: a fresh setup of the reviewed commit can mint only C authority; the exact installed release and new sessions carry the new list. No running installation is upgraded in place, no existing token silently gains authority. D's separate full review/enablement remains mandatory.

### 3.30-evidence — both desktop clients, real persistence and UI observation

- Needs: 3.29-evidence and all C prerequisites. Files: named checkpoint only; original external evidence locations and runbook apply. A human starts each live client session.
- Action: fresh scratch setup/start and Owner-created study/folder; each client reads context and adds one bounded evidence note requested by the evaluator. In the browser use Refresh/navigation, open its exact saved evidence version, inspect “{client} for {user}”, and follow the Agent activity record link. Stop/start and reopen the same version. Run live G4, G5, G7 and G8 on both clients with C's actual tool list; include a lost-response/reconciliation exercise and record the synthetic conflict proof separately from live observations.
- Verify support: `./hyprn-mvp dev check agent-eval`; `./hyprn-mvp dev check agent-ui`; `./hyprn-mvp dev check mcp`; `./hyprn-mvp dev check local-lifecycle`; `./hyprn-mvp dev check local-uninstall`. Compare note/version/receipt/action identities and hashes, not merely matching text.
- Done: two successful live write records with persisted UI proof, all C safety scenarios passing and scratch resources released. A single failed client blocks C. Full G2 model authoring and broader-tool safety scenarios remain 3.30-authoring in D. No additional per-OS live-scenario matrix is introduced.

### D expansion — preserve the full original authoring and run contract

- 3.24-remaining, 3.25 and 3.26 implement every remaining original handler/test. Their ToolSpecs join the test catalogue only; production composition stays C until 3.29-full. 3.27-full executes every original scenario and fixture acceptance, in addition to the C regressions.
- 3.28-full is the original full human review, explicitly including study creation, draft removal, mutable conflicts and full limits. Resolve the existing queue ambiguity here, before claiming 20 accepted per call: record whether the 10 limit counts only pre-call queued work or remains a total waiting/running bound, then amend the conflicting 3.27/3.32 expectations and tooling text consistently. No decision is inferred from the delivery priority.
- 3.29-full uses original files/actions, the real tokens.py propagation and production catalogue composition. Enable exactly the 33 authoring tools at registry 0.2.0, with original writer effects, after review. No run-stage ToolSpec contributes an API allowlist operation yet. Fresh setup/new sessions apply the release; read-only delegations stay read-only.
- 3.30-authoring performs the entire original both-client live authoring/G4/G5/G7/G8 evaluation on the current host. Then 3.31, 3.32 and 3.33 run unchanged, with their complete native/contract/readiness/reconciliation checks. In 3.32 also edit `docs/agents/tooling-spec.md` §5.4 to remove the stale run-read cache promise and describe the existing owner light read and bounded polling.
- 3.34 adds exactly the five run-stage tools to production (38 total) at registry 0.3.0; the same production registry supplies MCP and API policy. Run every original scripted and native G2/G3/G5/G6/G4/G8 check. Preserve backend-owned refusal before creating a run, one preparation command, null-with-reason outputs and immutable source/configuration pins.
- Verify: `./hyprn-mvp dev check agent-tools`; `./hyprn-mvp dev check agent-tools-native`; `./hyprn-mvp dev check agent-eval`; `./hyprn-mvp dev check mcp`; `./hyprn-mvp dev check study-kit`; `./hyprn-mvp dev check docs`; plus every original task-specific group (3.32 includes api-a, bindings, approach-bundle, locality-contracts).
- Done expansion: all original task acceptance holds on the committed tree, including exact exposed name sets, production API refusal of unexposed tools and an unchanged attested execution set. No broader writer implementation is counted as enabled before its review.

### 3.35-host / 3.36-delivery-status — full workflow proof, bounded claims

- 3.35-host executes the original full live checklist on both clients: G2/G3/G4/G6/G8 pass, G1 recorded; preserve prior passed G5/G7 and repeat affected safety cases after any tool/playbook change. Fresh setup/start per D-15; real worker runs, no seeded outputs. Add browser observation of model/configuration versions, retained results and saved conclusion, Refresh/navigation, attribution/activity links and restart persistence. Both numerical cases and the downstream-failure variant are required.
- Files: original 3.35 checkpoint/evidence destinations; `3.36-delivery-status` owns original 3.36 documentation files only. Record delivery-host scope, exact commit/release/attestation/registry/tool/playbook identities, per-client parity and every unmet E/F item. Before D acceptance run `./hyprn-mvp test` and `./hyprn-mvp dev check qualification --jobs 3` on the exact tree; the current-host qualification includes all registered must-pass groups and has no environmental skips.
- Done: D's full user workflow and current-host controls are proven. Original 3.17/3.19 stay partial where platform-probe acceptance remains; 3.30/3.35 close against their original per-client criteria, without an added per-OS scenario matrix. Original 3.36 and Phase 2/3 summaries wait for E/full phase gates. AGENT-01/AGENT-07/AGENT-08 and RUN-07 retain their original partial-status rules; OPS-04 waits for Phase 5. No milestone/release completion is claimed.

## Common verification and retained human gates

Every implementation slice retains the original TG-1 dependency and TG-2 attested-source checks
against its own commits (with only the documented A-window exception), then the orchestrator
runs `./hyprn-mvp dev check naming`, `hygiene`, `guard`, `units-guards`, `style-ratchet`,
`locality-contracts` and `contracts` as separate invocations, plus its affected application
groups and `python3 -B deployment/tools/term_scan.py`. A failed/skipped/missing target fails
acceptance; no count may fall without an itemized reason. APIs also require api-a and
combined-static; UI work keeps every original design/build/browser check, including
`python3 ui/check_design_system.py`, `python3 ui/design_tokens.py --check`,
`python3 ui/check_ui_contract.py`, `python3 ui/test_design_tooling.py`,
`node ui/design_smoke.mjs` and `npm --prefix ui run build`.

Unchanged full tasks use their original verification blocks, including 2.8c's full before/after
definition and contract byte checks and 2.8's full pending native-group list. Groups not yet
registered (release, local-cli, local-adapters, local-lifecycle, local-uninstall, docs, mcp,
study-kit, agent-eval, agent-tools-native, clean-room) are created by their owning original
task/slice before invocation, using its exact named targets and needs. New group wiring owns
the runner/guard pair explicitly; absent tools or required hosts never become passing evidence.

Retain PD-2.4; existing dependency/licence checkpoints for anything outside reviewed pins;
3.18 protocol/kit support; 3.28-evidence and 3.28-full; the queue-limit decision; both-client
human smoke/live checkpoints; and Phase 5's separate human installation/UI acceptance.
No new confirmation is needed to write this amendment or carry out already authorized fixes.
These are execution gates on concrete reviewed artifacts, not permission to reduce scope.

## Deferred inventory and source coverage

| Source / obligation | Owner and coverage |
|---|---|
| GOAL: Phase 2 clean installation on supported hosts | A/C establish the actual installation path; E completes 2.10-platforms, 2.13-clean-room and 2.14-guides; F qualifies it. |
| GOAL: Phase 3 all tool effects and both-client study workflow | C proves the narrow evidence loop; D completes 3.24–3.35 in full on the host; E completes original platform parity; original IDs above account for every task. |
| REQ: OPS-04, IAM-01, OPS-02, ADOPT-01, ADOPT-03, SEC-01 | Original Phase 2 coverage retained across A/C/E/F; no installed-edition or security claim moves earlier without its evidence. |
| REQ: AGENT-01, AGENT-05, AGENT-06, AGENT-07, AGENT-08, UI-04, RUN-07 | Original Phase 3 coverage retained across B/C/D/E/F; partial statuses follow 3.36, not the demonstration date. |
| CONTEXT Phase 2 D-01–D-13, PD-2.1–PD-2.4 | All original tasks retained; D-05b overrides Intel-Mac support; D-11/PD-2.4 keep the schema decision; D-12 keeps explicit creation, mismatch refusal and confirmed reset; no authoring data deleted for convenience. |
| CONTEXT Phase 3 D-01–D-19, PD-3.1–PD-3.9 | Same API/authority, attribution, token/relay, fixed list, guards, limits, receipts and immutable history. D-03/D-15/D-16 are applied at C and D separately; D-14 remains the interim evidence conclusion. Original deferred ideas remain excluded. |
| RESEARCH / PRACTICES / PATTERNS | Retain no-new-package stack, ASGI client, outer MCP dispatcher, credential-store relay, closed projections, fixture layers and all security mitigations. Current decisions supersede historical proposal/confirmation and direct-run-cache passages. D-P6 counts gain a measured intermediate 23-tool slice; D-P9 fixed session lists and D-P10 client deferral remain. |
| UI-SPEC | Original attribution/activity composition, outcomes, reasons, access loss, revocation, keyboard/themes/zoom and human acceptance retained in 3.22/3.23; Refresh/navigation is the promised freshness. |
| Broader host/client proof | E owns 2.10-platforms, 2.13-clean-room and 3.17-platforms/3.19-platforms connection probes, using the same implementation. Original 3.30/3.35 require scenario-by-client evidence and close in D; repeating all scenarios on every OS is not required. Failures return to the original owning task. |
| Broader docs and final records | E owns 2.14-guides and original 3.36 completion/Phase 2–3 summaries; F owns final requirement/release qualification. |
| Documents | F owns every original Phase 4 task and acceptance; nothing is erased or advertised as delivered early. Its schema/native dependencies on completed 2.8 remain. |
| Release | F owns all original Phase 5 criteria, full browser suite, independent ASVS L1/security/UI/code review, no open high finding, clean-room/fresh-account/first installation and product-owner acceptance. |
| Already deferred beyond this milestone | Cloud/bridge, document agent tools, typed conclusion/provenance/status/infeasibility/sweeps, cancellation, import/export tools and separate token panel retain their original ownership/scope; no new acceptance is invented. |

Threat registers T-2-* and T-3-* remain binding with their existing severities/dispositions.
In particular C retains T-3-01–10, 12–18, 20–28, 30 and 32 through the original security
tasks and restricted-registry refusal tests; D retains all remaining run/study/review-gate
mitigations. The new exposure risk is mitigated by one production catalogue shared by
listing, invocation and API policy, exact named-tool tests, explicit C/D reviews and fresh
installed releases. No new store, execution authority or credential transport is introduced.

Companion edits before dispatch: link this amendment prominently from both plans, ROADMAP,
STATE and HANDOVER; replace their contradictory next-task/whole-phase-before-demo wording;
correct Phase 2's count to 18 while preserving original IDs. During execution, the slice
owners update tooling-spec availability/counts, evaluation matrices and docs with evidence;
the orchestrator records the scoped gates and remaining slices without broad phase claims.
