# Roadmap: HYPRN MVP — first local release

## Overview

The product already delivers the manual modeling workflow. This milestone turns it into a local edition any engineer can install on macOS or Linux (Windows through WSL2), gives desktop coding agents a governed tool surface onto one study, adds source documents, and ends with independent reviews and a first qualified local release. Phase 1 makes the repository consistent under the `hyprn-mvp` namespace with every must-pass group green. Phase 2 packages the local edition. Phases 3 and 4 add agent tools and documents and may run in parallel with Phase 2 where their files do not overlap. Phase 5 qualifies and releases.

## Phases

- [x] **Phase 1: Repository baseline** - One `hyprn-mvp` namespace, clean tree, every must-pass test group green through the renamed runner
- [ ] **Phase 2: Local edition** - Clone, `./hyprn-mvp setup`, `./hyprn-mvp start` on macOS and Linux from pinned sources, with attestation at setup and no hard-coded location
- [ ] **Phase 3: Agent tools for coding agents** - Attributed agent principal, agent-practices research, local MCP server, study folders, attributed authoring with the Agent activity page, configurations and runs, evaluation
- [ ] **Phase 4: Documents** - Collections and annotations on AiiDA, document API routes, library, reader, search and citations from evidence in the UI
- [ ] **Phase 5: Qualification and first local release** - Independent reviews, full qualification, fresh-account install, first install and product-owner UI acceptance

## Phase Details

### Phase 1: Repository baseline
**Goal**: The repository builds, tests and reads as one product named `hyprn-mvp`, and every must-pass test group passes on the development host.
**Depends on**: Nothing (first phase)
**Requirements**: OPS-02, OPS-04, ADOPT-01, ADOPT-03, UI-01, SEC-01
**Success Criteria** (what must be TRUE):
  1. Packages, contracts, CLI-facing names, environment variables, container labels, wire and record identifiers, fixtures, attested-source lists, WhatsOpt patches, design tokens, the UI wordmark and the UI skill all use the `hyprn-mvp` namespace; the structural naming guard passes.
  2. The configured term scans report zero matches on tracked file contents and paths.
  3. No tracked file contains an absolute user-home path, a private-key block or a token-format literal; detector tests build such inputs at run time.
  4. Code comments and test names state the invariant they protect; no comment or name cites a deployment or a work item.
  5. `python3 -B deployment/checks.py --group qualification` passes on the development host: every must-pass group green, none reported as environment absent.
**Plans**: 1 plan, 10 tasks (1.1–1.10), one task per fresh executor

Plans:
- [ ] 01-PLAN.md — Runner and gates (tracer), development locations, package and identifier rename, deployment identities, UI and design-system paths, WhatsOpt patches and modeling provenance, text sweep, durable fixtures, phase gate

### Phase 2: Local edition
**Goal**: Any engineer installs and runs HYPRN MVP on macOS or Linux (Windows through WSL2) with `git clone`, `./hyprn-mvp setup` and `./hyprn-mvp start`, from pinned sources, with attestation at setup and every location resolved without hard-coded paths.
**Depends on**: Phase 1
**Requirements**: OPS-04, IAM-01, OPS-02, ADOPT-01, ADOPT-03, SEC-01
**Success Criteria** (what must be TRUE):
  1. A fresh clone on a clean macOS host and a clean Linux host with only git and a Docker engine completes `./hyprn-mvp setup`, `start` and `test`; the smoke test reproduces the acyclic Sellar known answer.
  2. Every location resolves flag → `HYPRN_MVP_*` variable → installation configuration → per-OS default → ask; synced, symlinked and foreign folders are refused.
  3. Images, the native environment and the WhatsOpt source are built only from pinned, verified inputs; non-acquisition builds run without network.
  4. Setup snapshots the committed checkout and attests the worker; start refuses a changed checkout or a stale attestation and never rebuilds.
  5. `status`, `doctor`, `open`, `logs`, `stop` and `uninstall` behave as documented in `docs/operations/`, with no secret in output, arguments or logs.
**Plans**: 1 plan, 17 tasks (2.1–2.14 plus 2.8a–2.8c), one task per fresh executor

Plans:
- [ ] 02-PLAN.md — Entry point and pinned toolchain (tracer), installation configuration and path policy, installation-driven managers, native environment, reproducible images, checkout-mode release, CLI, OS adapters, lifecycle, uninstall, smoke and clean-room installs, operations docs

### Phase 3: Agent tools for coding agents
**Goal**: A desktop coding agent (Codex or Claude Code) works on one study through HYPRN MVP's local MCP tool server as an attributed agent acting for the Owner, writing directly within the Owner's authority, starting new studies the Owner owns, and never deleting saved records, archiving or restoring anything, or changing access (ADR-0003); every operation it triggers leaves one authoritative outcome (ADR-0004).
**Depends on**: Phase 1; the CLI parts (`./hyprn-mvp study new`, `./hyprn-mvp mcp relay`, token commands) depend on Phase 2 tasks 2.9–2.11
**Requirements**: AGENT-01, AGENT-05, AGENT-06, AGENT-07, AGENT-08, UI-04, RUN-07 (partial)
**Success Criteria** (what must be TRUE):
  1. Every agent-written record shows "{agent} for {user}"; effective authority is the intersection of delegation, the user's current access and the role ceiling.
  2. `./hyprn-mvp study new` creates a study folder from which both desktop clients list HYPRN MVP's tools and answer questions about the study; no token is written to any file, argument or log.
  3. Agent writes execute directly within the Owner's authority, attributed and journaled, including new studies owned by the Owner and removal of draft content under revision checks; no tool deletes a saved record, archives, restores or manages access, and agent sessions are refused on those routes; the Owner sees every agent action on the Agent activity page and can revoke the agent's access there.
  4. An agent saves configurations, submits runs within the run limits (a configuration that is not ready to run is refused with its reasons and no run created), reads results with outcome facets separate, and records an interim conclusion.
  5. Evaluation scenarios G2–G8 pass on both local clients (scripted where possible); G1 is recorded per client.
**Plans**: 1 plan, 41 tasks (3.1–3.36 plus 3.2a and 3.3a–3.3d), one task per fresh executor

Plans:
- [ ] 03-PLAN.md — Agent principal and attribution (tracer), agent-practices research, read-only tools and local MCP server, study folders and relay, client-facts probe, authoring with the Agent activity page, configurations and runs, evaluation

### Phase 4: Documents
**Goal**: Within a study an engineer uploads source documents, organizes exact versions in collections, reads and searches extracted text, annotates passages and cites them from evidence, and reopens an old run with its exact cited source.
**Depends on**: Phase 1; the parser image follows Phase 2 task 2.7 (image conventions)
**Requirements**: DOC-01, HUM-06, RUN-02
**Success Criteria** (what must be TRUE):
  1. Two collections share one original without copying bytes; stale edits change nothing; a deleted collection is terminal and replay-safe.
  2. An upload becomes a published version whose exact bytes download after restart; every recovery state is visible in the library.
  3. A search hit opens the exact passage in the text-first reader, with honest coverage.
  4. A citation from evidence freezes the exact version, locator and server-verified quotation; later edits, re-extraction or a modeling outage never change what an old run shows.
  5. Every document screen passes keyboard, light/dark and genuine 200 % zoom checks and uses only design-system components.
**Plans**: 1 plan, 45 tasks (4.1–4.41, 4.9a/4.9b, 4.4a, 4.22a, 4.37b), one task per fresh executor

Plans:
- [ ] 04-PLAN.md — Upload tracer, test-group registry and isolated API, design-system additions, native collections and annotations, bridge and read loop, library, collections and annotations API and UI, parser image and containment, extraction, search, reader, citations and evidence version 4, configuration chain and frozen history, zoom sweep, acceptance

### Phase 5: Qualification and first local release
**Goal**: The local edition is independently reviewed, fully qualified on macOS and Linux, installed by the product owner on a fresh macOS account and then as the first installation on the product owner's machine, with the UI accepted by the product owner.
**Depends on**: Phases 2, 3 and 4
**Requirements**: SEC-01, OPS-04, UI-02, UI-03, ACPT-01
**Success Criteria** (what must be TRUE):
  1. Independent code, security (ASVS L1) and UI reviews are recorded with no open high finding.
  2. The qualification run passes on the final commit: every must-pass group, `./hyprn-mvp test`, clean-room installs on macOS and Linux, the full browser suite.
  3. The product owner completes the install, smoke, study-folder and agent-connection checklist on a fresh macOS user account.
  4. The first installation on the product owner's machine reports ready; the handoff records its URL, data root, release and attestation.
  5. The product owner's acceptance of the UI is recorded separately from automated evidence.
Release gate action: remove `documents` from the advertised unavailable capabilities once Phase 4 acceptance is recorded.
**Plans**: TBD (plan-phase from `phases/05-qualification-and-first-local-release/05-CONTEXT.md`)

## Parallel work

- Phase 3 backend work (agent principal, registry, MCP server, tools) touches `application/` and `contracts/`; Phase 4 touches `integration/`, `application/`, `contracts/` and `ui/`; Phase 2 touches `deployment/` and `editions/local/`. Phases 3 and 4 may run beside Phase 2 task by task when file sets are disjoint.
- Shared files (`contracts/hyprn-mvp.openapi.yaml`, `application/src/hyprn_mvp_app/api.py`, the UI study shell, `deployment/checks.py`) are edited by one task at a time; the orchestrating session serializes those tasks.

## Later (not in this milestone)

- Coordinated backup, restore drill and an update path for installed editions (OPS-03).
- Architecture decision records for decisions already captured in `docs/specs/`.
- Documents lifecycle and portability: deletion fences, portable export and import, restore, lifecycle UI (rest of DOC-01).
- Cloud edition and the platform repository; cloud agent bridge; workspaces and identity.
- Product gaps agents depend on (typed provenance, conclusion record, status channel, infeasible outcome, sweeps).
- Coupled solves and derivatives, then a first optimization family; uncertainty with OpenTURNS; method packages and scientific reviews.

## Progress

| Phase | Plans Complete | Status | Completed |
|---|---|---|---|
| 1. Repository baseline | 1/1 | Complete (tasks 1.1–1.11) | 2026-10-14 |
| 2. Local edition | 0/1 | Planned | - |
| 3. Agent tools for coding agents | 0/1 | Planned | - |
| 4. Documents | 0/1 | Planned | - |
| 5. Qualification and first local release | 0/? | Context ready | - |
