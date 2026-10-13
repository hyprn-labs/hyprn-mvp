---
phase: "03"
slug: "agent-tools-for-coding-agents"
# status lifecycle: draft (seeded by plan-phase) -> validated (set by validate-phase)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-13"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `03-RESEARCH.md` § Validation Architecture and revised for ADR-0003 (`docs/adr/0003-agent-write-rights-revised.md`, superseding ADR-0002: agent writes are direct, attributed and journaled, study creation (owned by the delegating user) and removal of draft content under revision checks included; deleting saved records, archive and restore, and access management are never available to agents; an agent's run submission that is not ready to run is refused by the execution owner; oversight is the Agent activity page) and ADR-0004 (`docs/adr/0004-operation-ownership.md`: every tool names its owners and stored outcome); revised again for the product owner's factorization schedule (D-19: per-owner API routers and a study-shell view registry as pure refactors, one run-row read with the light run-status read, server-decided recovery on command receipts, the whole layer table in the module-boundary test); task identifiers follow `03-PLAN.md` (tasks 3.1–3.36, the research task 3.2a and the factorization tasks 3.3a–3.3d).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (application, contracts, local edition); Playwright (UI); stdlib `unittest` in the runner guards — all already pinned, nothing installed |
| **Config file** | `application/pyproject.toml` (`testpaths = ["tests"]`); `ui/playwright.isolated.config.ts` for fixture-served specs |
| **Quick run command** | `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group <task group>` (after Phase 2: `./hyprn-mvp dev check <task group>`) |
| **Full suite command** | `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group qualification` |
| **Estimated runtime** | quick groups without Docker: about 60–180 s; `qualification`: tens of minutes |

---

## Sampling Rate

- **After every task commit:** the task's own group(s) plus `locality-contracts` and `contracts`; for UI tasks also `python3 ui/check_design_system.py`, `python3 ui/design_tokens.py --check`, `node ui/design_smoke.mjs`.
- **After every stage:** every Phase 3 group (`agent-tools`, `agent-tools-native`, `mcp`, `study-kit`, `agent-ui`, `agent-eval`) plus `qualification`.
- **Before `/gsd-verify-work`:** `qualification` green; live evaluation and human smoke records present per client; human acceptance recorded separately from automated evidence.
- **Pure refactors (3.3a, 3.3b):** the covering groups run at BASE and at HEAD with identical pass, fail, skip and flaky counts, both recorded in the checkpoint — for 3.3a every must-pass group whose targets build the application (the enumeration command of 3.3a) plus `contracts`, `combined-static`, `combined-security`, `ui-a`, `ui-a-retained`, `ui-b` and `ui-c`, and a byte comparison of the regenerated contract and UI types with the committed files; for 3.3b every must-pass browser group (`--list`) plus `units-native`, with `findings-native-preflight` first.
- **Contract editors (3.3c, 3.3d, 3.4, 3.12, 3.22):** `contracts`, `combined-static` and the contract freshness test after every commit; 3.3c and 3.3d also prove against BASE that no existing operation or schema changed beyond their additive members, and that no attested source changed (TG-2); 3.3c commits and verifies its run-row move (exact BASE counts) before it adds the run-status read; 3.3b's and 3.3d's unchanged-file checks read only their own commits, and 3.3d starts after 3.3b is verified.
- **Max feedback latency:** 180 s for the no-need groups.

---

## Groups to register in `deployment/checks.py`

| Group | Class | Needs | Content |
|---|---|---|---|
| `agent-tools` | must-pass | — | principal and authorization intersection (agent study creation owned by the delegating user, pre-study receipt read without widening), route allowlist with the closed human-only classification and its coverage test against the contract and `contracts/documents.md`, registry and schema rules, the registry-level absence of tools that delete saved records, archive, restore or manage access on every surface and stage, gated review tools absent until their gates are advertised, tool ownership rows (`owners`, `outcome`) per tool, OpenAPI parity, projections on recorded fixtures, caps and run admission, the owner-side refusal of unready agent submissions, `untrusted_content`, secret fuzz, content guards, error back-maps, playbook equality, instructions limits, journal and attribution rebuild, write policy and the draft rule, per-route refusals and the Agent activity read |
| `agent-tools-native` | must-pass | docker | model, configuration and run tools against the native fixtures |
| `mcp` | must-pass | — | scripted MCP client against the in-process `/mcp`; relay against a scratch loopback server with a fake credential adapter and a stub container endpoint |
| `study-kit` | must-pass | — | kit generation, no token in any file, TOML and JSON read-back, deny rules, location refusals |
| `agent-ui` | must-pass | browser | Agent activity page and attribution chip on a fixture app |
| `agent-eval` | must-pass | — | scripted G2, G3 and G5 and the structural parts of G4 and G8 in their ADR-0003 framing (injected content causes no write, study creation, archive, deletion or submission; tools that delete saved records, archive, restore or manage access absent and their routes refused whatever the client's approval settings), the end-to-end study creation and draft-rule scenarios, plus the control scenarios (limits, kill switch, revocation, journal, attribution, activity read), with no model, on every commit |
| (live evaluation) | — | — | not a runner group: a recorded runbook (`docs/agents/evaluation.md`) for live G1–G8 per desktop client, started manually (costs money) |

Targets added to an existing group: `api-a` gains `application/tests/test_run_status.py` (3.3c) and `application/tests/test_receipt_recovery.py` (3.3d). Once Phase 4 task 4.4 has landed, the Phase 3 groups are entry files under `deployment/groups/agent/` and the `api-a` targets go into its entry file; before that they are registered in `deployment/checks.py`.

---

## Per-Task Verification Map

| Task ID | Stage | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3.1 | 1 | AGENT-05, AGENT-06 | spoofing, elevation (T-3-04, T-3-10, T-3-11) | token on `/api/1` → 401; read-only agent session POST/PATCH/DELETE → 403; other study → 404; intersection re-checked per call; at store level an agent's study creation gives the Owner membership to the delegating user, none to the agent, keeps the agent as receipt actor and leaves the delegation unchanged (new study → 404 for the agent); pre-study replay and receipt read never authorize the agent on the new study; other pre-study commands refused | unit, integration | `checks.py --group agent-tools` | ❌ W0 | ⬜ pending |
| 3.2a | 1 | AGENT-01, AGENT-08 | — (no rights change: ADR-0003 and ADR-0004 are constraints, not designs to redo) | `03-PRACTICES.md` exists with every listed topic covered (Linear Agent practices, MCP specification and client support, MCP era for OQ-3, vendor guidance, cloud bridge implications); each source cited with URL and access date; every decision (a)–(e) with rationale and status and its check against ADR-0003 and ADR-0004; each spec-changing or conflicting decision listed as an open question OQ-8x; the approval-by-context option only under "Options not adopted" | research record | grep-able checks of task 3.2a (section headings, `- [S<n>] … — https://… — accessed YYYY-MM-DD` lines, `### D-P<n> (<letter>)` with `Rationale:` and `Status:` lines, `\| OQ-8<x> \|` rows equal to the open-question statuses) | n/a | ⬜ pending |
| 3.2–3.3 | 1 | — | — | product-owner decisions recorded (OQ-1, 2, 4, 5, 6, 7 and every OQ-8 practice question); specs aligned with them and with the binding practice decisions, each `D-P` decision accounted for; no retired write-review text reintroduced | decision checkpoint, docs | recorded decision lines (grep in the checkpoint, OQ-8 answers equal to the questions of `03-PRACTICES.md`); `D-P` accounting in checkpoint 3.3; added-line scan of the specs | n/a | ⬜ pending |
| 3.3a | 1 | — (D-19) | elevation (T-3-34) | routes move into per-owner route modules with no behaviour change: regenerated contract and UI types byte-identical to the committed files; every group that builds the application keeps its BASE counts; `api.py` defines no route and stays the only importer of `agent_policy`; route modules reach only the edge helpers, `contracts` and their owners | refactor evidence, static boundary | byte comparison of the `generate_contract.py` and `generate_types.py` output; the enumerated groups at BASE and HEAD; `--group locality-contracts` | ✅ existing tests | ⬜ pending |
| 3.3b | 1 | — (D-19) | — | study views become registry entries and the model-version save moves to `ModelController`; every must-pass browser group and `units-native` keep their BASE counts; no spec, control map, API client, contract type or design file changes; no import cycle between the link model and the registry | refactor evidence, browser | every must-pass browser group (`--list`), `--group units-native`, design checks, `--group combined-static` | ✅ existing specs | ⬜ pending |
| 3.3c | 1 | RUN-07 (partial), VER-04 | information disclosure, DoS, parallel state (T-3-33, T-3-30) | one run-row read in `history` (one-owner statement test); the light status of 1 to 20 runs equals the full run read's fields, unavailable never zero, process times null with `not_projected`, no payload loaded (statement trace), scoped 404 without a partial answer, p95 under 1 s for 20 runs; every existing contract operation and schema unchanged; no attested source changed | integration, static boundary | `--group api-a`, `--group locality-contracts`, `--group bindings`, `--group approach-api`, `--group approach-history`, `--group contracts` | ❌ W0 (`application/tests/test_run_status.py`) | ⬜ pending |
| 3.3d | 1 | VER-03, VER-04 | tampering, repudiation (T-3-32) | every receipt read carries the owner's `recovery`; the table holds for every category and state, and a run never yields `resend_same_command`; a missing receipt's 404 carries `recovery` only for a reader who may see the scope, through a dedicated `ReceiptError` schema referenced only by the two receipt operations (`Error` and every other operation's responses unchanged); the UI's `reconcile` and `retryOriginal` keep no receipt-state, error-code or category rule; existing receipt members unchanged; no attested source changed | integration, browser | `--group api-a`, `--group ported-isolated`, every must-pass browser group, `--group contracts` | ❌ W0 (`application/tests/test_receipt_recovery.py`) | ⬜ pending |
| 3.4 (layer table) | 1 | — (D-19) | elevation (T-3-17) | `LAYERS` equals the "Allowed imports" table of architecture §7; the observed import graph, function-local imports included, is a subgraph of it; the table is acyclic; a test-only extra edge fails the check; the attested file list is unchanged | static boundary | `--group locality-contracts` | ✅ `application/tests/test_module_boundaries.py` | ⬜ pending |
| 3.4 | 1 | AGENT-05, AGENT-07, UI-04 | repudiation, elevation (T-3-21, T-3-27) | receipts and records carry the agent actor; `study` attribution entries cross-checked against the pre-study receipt, readable by members of the new study (study read and Home read); Owner-only token routes; revoke ends the token's delegation and takes effect on the next call | integration | `--group agent-tools`, `--group contracts` | ❌ W0 | ⬜ pending |
| 3.5–3.7 | 1 | AGENT-05, UI-04 | repudiation | "{agent} for {user}" shown on every agent-written record, on Home and in the heading of a study an agent created, and nothing on human records; no confirmer | browser + design checks | `--group agent-ui`, design checks | ❌ W0 | ⬜ pending |
| 3.8–3.11 | 2 | AGENT-01, AGENT-06, AGENT-07 | information disclosure, DoS, elevation, repudiation (T-3-06, T-3-09, T-3-15, T-3-16, T-3-28, T-3-30, T-3-31) | parity, caps, run admission, kill switch, journal with digests only, secret fuzz; no tool that deletes a saved record, archives, restores or manages access on any surface, stage or scope; the human-only classification refuses its routes for every effect set, the annotation DELETE only working material; gated tools absent until their gate is advertised; every `ToolSpec` declares owners and outcome and matches its "Tool ownership (ADR-0004)" row; `get_run_status` reads the light run-status read once per call and keeps no status cache | unit, integration | `--group agent-tools` | ❌ W0 | ⬜ pending |
| 3.12 | 2 | AGENT-01 | CSRF, DNS rebinding | any `Origin` → 403, foreign `Host` → 403, cookie on `/mcp` → 401, body > 256 KB refused | integration | `--group mcp` | ❌ W0 | ⬜ pending |
| 3.13 | 2 | AGENT-08 | — | scripted G2, G5 | integration | `--group agent-eval` | ❌ W0 | ⬜ pending |
| 3.14–3.16 | 2 | AGENT-01 | token leakage, port squatting | no token in files, arguments or logs; relay refuses an unowned port | integration | `--group study-kit`, `--group mcp` | ❌ W0 | ⬜ pending |
| 3.17–3.19 | 2 | AGENT-01, AGENT-08 | — | client facts and human smoke per client, confirming or correcting the documented client support of `03-PRACTICES.md`; protocol-era decision informed by its "MCP era for OQ-3" | human-verify + decision | recorded checkpoint lines | manual | ⬜ pending |
| 3.20–3.21 | 3 | AGENT-05, AGENT-06 | duplicates, injected text, parallel state (T-3-09, T-3-23, T-3-30) | duplicates return the stored outcome; lost responses reconciled through the owner's receipt by following its `recovery` value alone (pre-study `study_create` included), `uncertain` and runs never resent; the attribution index equals its rebuild from receipts and the journal; guards block before preview or save; warnings and records written to the journal | integration | `--group agent-tools` | ❌ W0 | ⬜ pending |
| 3.22 | 3 | AGENT-06, AGENT-07, UI-04 | elevation, information disclosure (T-3-06, T-3-08, T-3-26, T-3-28) | agent session 403 on every human-only route of the contract (never vacuous); the classification covers every human-only route of `contracts/documents.md` and its route registry, and only the annotation DELETE is working material; draft rule at the route level (removal with the last-read revision; stale → `conflict`, no effect, no retry; saved versions never deletable); refused, failed and uncertain calls journaled with a reason (`human_only` included); activity read human-only, own delegations only, no secrets, `create_study` rows linking the new study | integration | `--group agent-tools`, `--group contracts` | ❌ W0 | ⬜ pending |
| 3.23 | 3 | UI-04 | spoofing, elevation (T-3-27) | Agent activity page; Revoke access only for the Owner, behind a confirmation dialog, one request with the cross-site request token | browser + design checks | `--group agent-ui`, design checks | ❌ W0 | ⬜ pending |
| 3.24–3.26 | 3 | AGENT-01, AGENT-06 | overwrite of a human edit, prompt injection, widened reach (T-3-12, T-3-07, T-3-11, T-3-31) | writes execute directly with the agent as receipt actor and journal records; `create_study`: Owner membership to the delegating user, none to the agent, the creating token gets 404 on the new study, a lost response reconciled through the pre-study receipt with no second study, the result names the renew command, the activity read links the study; `record_scientific_review` and `request_scientific_review` absent with the product capabilities, and with a test capability `record_scientific_review` labelled agent-recorded and absent for reader-ceiling delegations; draft rule per tool (`update_approach_draft` `remove_step` and `remove_case`, `edit_model` `remove_component` with the last-read revision; stale → `conflict`, no retry); a concurrent human edit yields `conflict`, is kept and never retried; guard blocks never reach the API; each `ToolSpec` equals its ownership row | integration | `--group agent-tools`, `--group agent-tools-native` | ❌ W0 | ⬜ pending |
| 3.27–3.30 | 3 | AGENT-06, AGENT-07, AGENT-08 | T-3-06, T-3-07, T-3-11, T-3-14, T-3-25 | scripted structural G4 (injected requests to create studies included) and G8 (human-only routes refused, `create_study` only for writer delegations), end-to-end study creation and draft rule, and the control scenarios; product-owner review of agent write and control behaviour (study creation, draft deletion and the human-only classification included) before writer tokens; live G2, G4, G5, G7, G8 | scripted + decision + live | `--group agent-eval` + live runbook | ❌ W0 | ⬜ pending |
| 3.31–3.36 | 4 | AGENT-01, AGENT-06, AGENT-08 | duplicate, unbounded or unready runs, overwrite, parallel state (T-3-09, T-3-12, T-3-29, T-3-30) | `wait_for_runs` reads the light run-status read, never faster than 15 s per run, keeps no status cache, `stalled` not resubmitted; run caps per call, actor and session; nothing submitted while readiness is not `ready`; the execution owner refuses an agent's submission that is not ready to run (readiness, unresolved units, unresolved reference, preparation refused) with reasons and no run association, outbox row or receipt, human submissions unchanged; new configuration and conclusion versions need the last-read revision; each `ToolSpec` equals its ownership row; scripted G3 (human edit kept), G6; live G1, G3, G6 | integration, live | `--group agent-tools`, `--group agent-tools-native`, `--group bindings`, `--group agent-eval` + live runbook | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Recorded modeling responses (or a test modeling-client transport) for the no-need groups
- [ ] Scripted MCP client helper (`application/tests/mcp/mcp_client.py`)
- [ ] Golden projection fixtures; secret-seeded fixtures assembled at run time (the hygiene guard refuses tracked token-shaped literals)
- [ ] Text-inventory fixture for the content guards (blocked items assembled at run time)
- [ ] Fake credential-store adapter and stub container endpoint for relay tests
- [ ] `deployment/tests/agent_ui_fixture.py` serving the fixture app
- [ ] G2 pressure-loss fixture (met, violated and downstream-failure variants)
- [ ] Runner registrations for the groups above, and the `api-a` targets `application/tests/test_run_status.py` (3.3c) and `application/tests/test_receipt_recovery.py` (3.3d)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Both desktop clients list the HYPRN MVP tools from a study folder and answer a read-only G2 question | AGENT-01 | needs the real desktop clients | after a fresh `./hyprn-mvp setup` on a scratch installation, `./hyprn-mvp study new`, open the folder in each client, record the tool list and answer per client |
| Client and protocol facts (tooling spec §11.7 items 5–8) | AGENT-01 | client behaviour is not documented | record initialize parameters, protocol version, prompts/resources support, relay sandbox reachability, timeout handling per client |
| Live G1–G8 per client and the parity table | AGENT-08 | costs money; started manually | run the live scenarios per the evaluation runbook; record results per client |
| Product owner's review of agent write and control behaviour before writer tokens | AGENT-06, AGENT-07 | human decision gate (ADR-0003 "Confirmation") | on the scratch review fixture of task 3.27, review the Agent activity page (outcomes, reasons, warnings, record links), attribution chips (on Home and in the heading of a study the agent created included), study creation (the Owner owns the new study; the agent reaches it only after a renewed token), removal of draft content with the last-read revision and the conflict on a stale one, the human-only route classification and its refusals (deleting saved records, archive, restore, access management), the run and API-call limits, the kill switch, Revoke access and access-ended handling; record the decision at checkpoint 3.28 |
| Product-owner UI acceptance | UI-04 | automated browser evidence is never human acceptance | recorded separately in Phase 5 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180 s for the no-need groups
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
