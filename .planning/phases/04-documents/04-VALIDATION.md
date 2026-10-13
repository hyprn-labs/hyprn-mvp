---
phase: "04"
slug: "documents"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-13"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: `04-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest under the runner's scoped child (no conftest autoload, plugin autoload disabled), stdlib unittest guards, Playwright for browser groups |
| **Config file** | `deployment/checks.py` (the runner); after task 4.4 every group is one entry file `deployment/groups/<family>/<group>.json` loaded by `deployment/group_registry.py` (class `must-pass`/`opt-in`, needs `docker`/`browser`/`fixtures`/`installation`, interpreter, runner), the Documents modes and validators in `deployment/documents_groups.py`; after task 4.4a the scoped browser fixtures run on `deployment/tests/browser_harness.py`; `ui/playwright.isolated.config.ts`, `ui/playwright.documents.config.ts` |
| **Quick run command** | `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group <documents group>` |
| **Full suite command** | `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group qualification` |
| **Estimated runtime** | per group 1–10 min (native and browser groups); qualification above 60 min |

The runner fails a group when a target is missing, a selector matches no test, a test is skipped or expected to fail, or an environment need is absent. Measured groups must leave their measured artifacts outside the repository.

---

## Sampling Rate

- **After every task commit:** the task's own Documents groups, plus `documents-contracts` and `naming`; UI tasks add `combined-static`, `python3 ui/check_design_system.py` and `python3 ui/design_tokens.py --check`. Tasks that change shared infrastructure without changing behaviour (4.4, 4.4a, 4.22a, the capability moves of 4.37 and 4.38) also record the affected groups' counts before and after; the counts must match (new cases are listed separately). From 4.34 to 4.37b's verification (the stale-attestation window of the plan's "Blocked lane"; 4.34 starts after 4.4a, 4.22 and 4.22a), the groups on the binding list of checkpoints 4.34 and 4.36 are not sampled and no task whose verification names them runs.
- **After every wave:** every Documents group, plus `ae-evidence`, `locality-contracts` and `guard`.
- **Before phase verification:** `qualification` green; product-owner walk-through recorded separately from automated evidence.
- **Max feedback latency:** one group run (about 10 min).

---

## Per-Task Verification Map

Filled from `04-PLAN.md` (45 tasks; tasks 4.4a, 4.22a and 4.37b added and task 4.9 split into 4.9a and 4.9b). The command shown is each task's primary check; every task's full `<automated>` list, each with its `<fails_when>`, is in the plan. `CHECK g` = `python3 -B deployment/checks.py --group g` with the development variables exported. "File exists": ✅ the target exists before the task; ❌ the task creates it (W0 = Wave 0 infrastructure). Tasks blocked only by OQ-2 keep a numbered wave; tasks 4.31–4.39 show their position in the plan's "Blocked lane" (one lane task at a time, fixed order, explicit not-beside lists) and their open question.

| Task | Wave | Requirement | Threat ref | Automated command | File exists | Status |
|---|---|---|---|---|---|---|
| 4.1 (tracer) | 1 (after Phase 3 3.3a) | DOC-01 | T-4-01, T-4-04, T-4-05, T-4-09, T-4-15, T-4-16 | `CHECK documents-upload-api` (incl. every Documents route served from `routes/documents.py`) | ❌ `application/tests/test_documents_upload_api.py` | ⬜ pending |
| 4.2 (decision OQ-2) | 1 | DOC-01 | T-4-SC | `grep -c "D-14 (OQ-2)" .planning/phases/04-documents/04-CONTEXT.md` | ✅ | ⬜ pending |
| 4.3 (decision OQ-1) | 1 | RUN-02, HUM-06 | T-4-13 | `grep -c "D-13 (OQ-1)" .planning/phases/04-documents/04-CONTEXT.md` | ✅ | ⬜ pending |
| 4.4 | 2 | DOC-01 | T-4-23 | `CHECK documents-registry`; `CHECK guard`; `--list` diff (only `documents-registry` added); every group's counts before and after (`qualification`) | ❌ W0 `deployment/group_registry.py`, `deployment/groups/<family>/*.json`, `deployment/documents_groups.py`, `deployment/tests/test_documents_registry.py` | ⬜ pending |
| 4.4a | 3 | DOC-01 | T-4-23 | `CHECK documents-isolated-api`; `CHECK guard`; `CHECK findings-native-guards` (exactly 17); the migrated browser and native-journey groups' counts before and after | ❌ W0 `deployment/tests/browser_harness.py`, `ui/tests/documents-isolated-api.spec.ts` | ⬜ pending |
| 4.5 | 2 | DOC-01 | T-4-06 | `CHECK combined-static`; `python3 ui/check_design_system.py` | ✅ | ⬜ pending |
| 4.6 | 2 (OQ-2) | DOC-01 | T-4-08 | `CHECK documents-parser-adoption` | ✅ (Phase 1 task 1.8) | ⬜ pending |
| 4.7 | 3 | DOC-01 | T-4-09, T-4-18 | `CHECK documents-collections` | ❌ W0 `integration/tests/test_documents_collections.py` | ⬜ pending |
| 4.8 | 3 | DOC-01 | T-4-10 | `CHECK documents-bridge`; `CHECK documents-read-loop` | ❌ `application/tests/test_documents_bridge.py`, `integration/tests/test_documents_read_loop.py` | ⬜ pending |
| 4.9a | 3 | DOC-01 | T-4-02, T-4-05 | `CHECK documents-library-api` | ❌ `application/tests/test_documents_library_api.py` | ⬜ pending |
| 4.9b | 4 (after Phase 3 3.3d) | DOC-01 | T-4-01, T-4-02, T-4-03, T-4-04, T-4-09, T-4-14, T-4-15, T-4-22 | `CHECK documents-access`; `CHECK documents-upload-api` (incl. the server-decided recovery rows) | ❌ `application/tests/test_documents_access.py` | ⬜ pending |
| 4.10 | 3 | DOC-01, HUM-06 | T-4-06 | `node ui/design_smoke.mjs` | ✅ | ⬜ pending |
| 4.11 (human check) | 4 (OQ-2) | DOC-01 | T-4-SC | `CHECK documents-parser-adoption` | ✅ | ⬜ pending |
| 4.12 | 4 | DOC-01 | T-4-09, T-4-18 | `CHECK documents-annotations` | ❌ `integration/tests/test_documents_annotations.py` | ⬜ pending |
| 4.13 | 5 (after Phase 3 3.3b) | DOC-01 | T-4-05, T-4-06, T-4-22 | `CHECK documents-library-ui` | ❌ `ui/tests/documents-library.spec.ts` | ⬜ pending |
| 4.14 | 5 | DOC-01 | T-4-01, T-4-09 | `CHECK documents-collections-api` | ❌ `application/tests/test_documents_collections_api.py` | ⬜ pending |
| 4.15 | 4 (OQ-2) | DOC-01 | T-4-07, T-4-08 | `CHECK documents-parser-image` | ❌ `integration/tests/test_documents_parser_image.py` | ⬜ pending |
| 4.16 | 6 | DOC-01 | T-4-06 | `CHECK documents-collections-ui` | ❌ `ui/tests/documents-collections.spec.ts` | ⬜ pending |
| 4.17 | 6 | DOC-01 | T-4-01, T-4-09 | `CHECK documents-annotations-api` | ❌ `application/tests/test_documents_annotations_api.py` | ⬜ pending |
| 4.18 | 5 (OQ-2) | DOC-01 | T-4-07, T-4-17 | `CHECK documents-parser-containment` | ❌ W0 `integration/tests/test_documents_parser_containment.py`, `integration/tests/document_fixtures.py` | ⬜ pending |
| 4.19 | 5 | DOC-01 | T-4-10 | `CHECK documents-supervision` | ❌ `deployment/tests/test_documents_supervision.py` | ⬜ pending |
| 4.20 | 7 | HUM-06, DOC-01 | T-4-11, T-4-12, T-4-16 | `CHECK documents-citations`; `CHECK documents-evidence-v4` | ❌ `application/tests/test_documents_citations.py`, `test_documents_evidence_v4.py` | ⬜ pending |
| 4.21 | 7 (OQ-2) | DOC-01 | T-4-07, T-4-09, T-4-17 | `CHECK documents-extraction` | ❌ `integration/tests/test_documents_extraction.py` | ⬜ pending |
| 4.22 | 8 | HUM-06, DOC-01 | T-4-13 | `CHECK documents-usage` | ❌ `application/tests/test_documents_usage.py` | ⬜ pending |
| 4.22a | 7 (after 4.16 and Phase 3 3.3b) | DOC-01 | T-4-21 | the access-loss groups (`ae-ui-evidence`, `ae-ui-model`, `ae-ui-configuration`, `units-ui-authoring`, `units-ui-configuration`, `approach-ui-controller`, `approach-ui-reading`, `approach-ui-configuration`, `approach-ui-history`, `ui-c`, `ui-reading`) with their before counts plus the new cases; `CHECK combined-static` | ✅ `ui/tests/assumptions-evidence.spec.ts`, `ui/tests/unit-authoring.spec.ts` (new cases) | ⬜ pending |
| 4.23 | 9 | HUM-06 | T-4-06 | `CHECK documents-evidence-ui`; `ae-ui-evidence`, `ae-ui-model`, `ae-ui-configuration` with the counts of checkpoint 4.22a | ❌ `ui/tests/documents-evidence.spec.ts` | ⬜ pending |
| 4.24 | 9 (OQ-2) | DOC-01 | T-4-01, T-4-07 | `CHECK documents-extraction-api` | ❌ `application/tests/test_documents_extraction_api.py` | ⬜ pending |
| 4.25 | 10 (OQ-2) | DOC-01 | T-4-02 | `CHECK documents-search`; `CHECK documents-extraction-provenance` | ❌ `application/tests/test_documents_search.py`, `integration/tests/test_documents_extraction_provenance.py` | ⬜ pending |
| 4.26 | 11 (OQ-2) | DOC-01 | T-4-06 | `CHECK documents-reader-ui` | ❌ `ui/tests/documents-reader.spec.ts` | ⬜ pending |
| 4.27 | 11 (OQ-2) | HUM-06 | T-4-12 | `CHECK documents-citation-spans` | ❌ `application/tests/test_documents_citation_spans.py` | ⬜ pending |
| 4.28 | 12 (OQ-2) | DOC-01 | T-4-06 | `CHECK documents-annotations-ui` | ❌ `ui/tests/documents-annotations.spec.ts` | ⬜ pending |
| 4.29 | 13 (OQ-2) | HUM-06, DOC-01 | T-4-06, T-4-12 | `CHECK documents-cite-ui` | ❌ `ui/tests/documents-cite.spec.ts` | ⬜ pending |
| 4.30 | 10+ (OQ-2) | DOC-01 | T-4-07, T-4-10 | `CHECK documents-served` (opt-in) | ❌ `deployment/tests/test_documents_served.py` | ⬜ pending |
| 4.31 | lane 2 (OQ-3) | DOC-01 | T-4-09 | `CHECK documents-collections-api` | ✅ (extends 4.7, 4.14, 4.16 tests) | ⬜ pending |
| 4.32 | lane 3 (OQ-5; after Phase 2 2.8) | DOC-01 | T-4-01 | `CHECK documents-upload-recovery`; attested inventory unchanged | ❌ `application/tests/test_documents_upload_recovery.py` | ⬜ pending |
| 4.33 | lane 4 (OQ-4) | DOC-01 | T-4-01 | `CHECK documents-archived-study` | ❌ `application/tests/test_documents_archived_study.py` | ⬜ pending |
| 4.34 | lane 1 (OQ-1; after Phase 2 2.8) | RUN-02 | T-4-13 | `CHECK documents-chain-contracts`; attested inventory and generated execution schema unchanged | ✅ `contracts/tests/test_documents_contract.py` (new selector) | ⬜ pending |
| 4.35 | lane 5 (OQ-1) | RUN-02, HUM-06 | T-4-13 | `CHECK documents-configuration-chain` (explicit version checks for the new versions, listed for 4.37) | ❌ `application/tests/test_documents_configuration_chain.py` | ⬜ pending |
| 4.36 | outside the lane (OQ-1) | RUN-02 | T-4-13 | `CHECK documents-modeling-private`; the post-modeling window candidates measured (`units-worker`, `units-native`, `fuel-native-provenance`, `ae-model`, `units-model`) and every failing group added to the binding window list | ❌ `modeling/tests/test_documents_private_projection.py` | ⬜ pending |
| 4.37 | outside the lane (OQ-1) | RUN-02 | T-4-13, T-4-24 | `CHECK locality-contracts` (capability property tests, golden corpus); `CHECK documents-bundle-admission`; `CHECK units-attestation` (one re-attestation); configuration, history, export and bundle groups' counts before and after the capability move (one verify pair per group) | ❌ `integration/tests/test_documents_bundle_admission.py` | ⬜ pending |
| 4.37b | outside the lane (OQ-1) | RUN-02 | T-4-13 | `CHECK findings-native-read`; every group on the binding window list passes again (window closed) | ✅ (recaptures pinned fixtures; no new test file) | ⬜ pending |
| 4.38 | lane 6 (OQ-1) | RUN-02 | T-4-13, T-4-24 | `CHECK documents-frozen-history`; history and seed groups' counts before and after the capability move | ❌ `application/tests/test_documents_frozen_history.py` | ⬜ pending |
| 4.39 | lane 7 (OQ-1) | HUM-06, RUN-02 | T-4-06 | `CHECK documents-history-ui` | ❌ `ui/tests/documents-history.spec.ts` | ⬜ pending |
| 4.40 | 14 (after 4.29, 4.31, 4.32, 4.33 and 4.39, each verified or recorded out of this phase) | DOC-01 | T-4-06 | `CHECK documents-ui-zoom` | ❌ `ui/tests/documents-zoom.spec.ts` | ⬜ pending |
| 4.41 (acceptance) | 15 | DOC-01, HUM-06, RUN-02 | all | `CHECK qualification`; `CHECK documents-served` | ✅ | ⬜ pending |

Every task has at least one automated command; no three consecutive tasks lack one. Measured groups (`documents-collections`, `documents-annotations`, `documents-read-loop`, `documents-parser-containment`) also fail when their validator rejects the measured artifacts.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `deployment/checks.py` → `deployment/group_registry.py` and `deployment/groups/<family>/*.json` (task 4.4): every test group registered by one entry file with a closed schema (`runner`, `interpreter`, `class`, `needs`, `targets`); the hand-kept sets derived; `--list` and every group's counts unchanged. `deployment/documents_groups.py` (task 4.4): a `browser-native` mode (native interpreter; `docker` and `browser` needs); per-group measured-artifact validators (`collection_protocol` 4.4, `read_loop_timeline` 4.8, `parser_canaries` 4.18). Documents groups re-run under their registered interpreter from task 4.1.
- [ ] `deployment/tests/browser_harness.py` (task 4.4a): one `serve` and one `run_playwright` for every scoped browser fixture, each fixture keeping its write predicate, cap and controls.
- [ ] `deployment/tests/documents_ui_fixture.py` (task 4.4a): an isolated real API on the harness (real store and auth, scratch AiiDA, in-process writer and read loop, modeling double, fixture controls).
- [ ] `deployment/tests/documents_native_fixture.py` (task 4.7): probes against the production `NativeDocuments` methods.
- [ ] `integration/tests/document_fixtures.py` (task 4.18, extended by 4.21): run-time generated fixtures (PDF: text, encrypted, image-only, malformed, over 500 pages, cyclic tree, decompression bomb, oversized page; UTF-8 edge cases). Nothing binary committed.
- [ ] `application/tests/test_module_boundaries.py`: new modules and their allowed imports, in the task that adds each module (4.1, 4.20, 4.25); the capability property tests in 4.37.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Product-owner walk-through: upload and reopen an original; two collections; search, read, annotate; create and attach a citation; change source, annotation and extraction, reopen an old run (also with the modeling service down); a failed extraction | DOC-01, HUM-06, RUN-02 | Human acceptance is never automated evidence | Recorded in the phase acceptance checkpoint, separate from automated evidence |
| Genuine 200 % zoom, light and dark, keyboard review of every Documents screen | DOC-01 | Screenshots are automated evidence; the visual judgement is human | Screenshots under `HYPRN_MVP_UI_EVIDENCE_ROOT`, reviewed by the product owner |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (planned in `04-PLAN.md`)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (planned)
- [x] Wave 0 covers all MISSING references (planned in tasks 4.4, 4.4a, 4.7, 4.18)
- [x] No watch-mode flags
- [ ] Feedback latency within one group run (the parser image build in 4.15 and the served journey in 4.30 may exceed it; measured in their checkpoints)
- [ ] `nyquist_compliant: true` set in frontmatter (stays false until the Wave 0 items above are delivered and validate-phase confirms them)

**Approval:** pending
