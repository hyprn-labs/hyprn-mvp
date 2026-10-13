---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
# Codebase Structure

**Analysis Date:** 2026-10-13

## Directory Layout

```
<repo>/
├── AGENTS.md                    # The only agent instruction file (binding rules)
├── CONTEXT.md                   # Domain language: binding terms and words to avoid
├── README.md                    # Product summary, editions, target layout
├── .gitignore                   # Ignores stores, logs, venvs, node_modules, dist, credentials
├── .claude/skills/hyprn-mvp-ui/ # Project skill: UI and design-system rules (SKILL.md)
├── .planning/                   # Current roadmap, state, phase plans and checkpoints
├── application/                 # hyprn_mvp_app: API, auth, domain modules, store, dispatcher
│   ├── src/hyprn_mvp_app/       # Flat package, 20 modules
│   ├── tests/                   # pytest; boundary, golden identity, API, domain tests
│   ├── generate_contract.py     # Writes contracts/hyprn-mvp.openapi.yaml from routes
│   ├── audit_dependencies.py    # Dependency pin audit
│   ├── pyproject.toml, requirements.lock, dependency-pins.json, provenance.md
├── integration/                 # hyprn_mvp_integration: AiiDA, launcher, worker, results
│   ├── src/hyprn_mvp_integration/
│   ├── tests/                   # Native integration and worker tests, fixtures/
│   ├── pyproject.toml           # AiiDA entry points hyprn_mvp.scalar
│   ├── worker-requirements.lock, test-requirements.lock, document-parser.lock.json
│   └── provenance.md, document-parser-provenance.md
├── contracts/                   # Wire contracts (schemas govern over prose)
│   ├── schemas/                 # model.schema.json, execution.schema.json (authored)
│   ├── hyprn-mvp.openapi.yaml   # Public API /api/1 (GENERATED)
│   ├── modeling.openapi.yaml    # Private Modeling Backend Contract /modeling/1
│   ├── README.md, documents.md, investigation-foundation.md
│   └── tests/                   # Contract tests (schemas, portability, modeling contract)
├── modeling/                    # Independently authored helpers for the modeling service
│   ├── generate_unit_catalog.py, rehearsal.py, verify_rehearsal.py, provenance.md
│   └── tests/                   # Modeling contract tests against a disposable service
├── upstream/whatsopt-patches/   # Ordered AGPL patches 010..090 applied to pinned WhatsOpt
├── deployment/                  # Managers, Dockerfiles, pins, check runner, fixtures
│   ├── checks.py                # Fail-closed test-group runner
│   ├── local_paths.py           # The single path-policy module
│   ├── *_runtime.py, manage.py, initialize_stores.py, release_binding.py, native_environment.py
│   ├── *.Dockerfile, modeling-compose.yaml, modeling_policy.rb, pins.json
│   ├── tools/                   # backup_immutable.py, term_scan.py
│   └── tests/                   # Guards, fixtures (*_fixture.py), native journeys, live_fence.py
├── ui/                          # React 19 + Vite 8 + TypeScript browser client
│   ├── src/                     # Screens, controllers, projections, api.ts, contract.ts
│   │   └── design/              # Design layer: components, primitives, tokens.css (GENERATED)
│   ├── tests/                   # Playwright specs (*.spec.ts), support/, criterion-record.test.cjs
│   ├── public/                  # THIRD_PARTY_NOTICES.txt
│   ├── check_design_system.py, check_ui_contract.py, design_tokens.py, generate_types.py
│   ├── test_design_tooling.py, design_smoke.mjs, audit_dependencies.py
│   ├── control-map.json, design-baseline.json, dependency-audit.json
│   └── package.json, package-lock.json, tsconfig.json, vite.config.ts, playwright*.config.ts
├── design-system/               # Design authority: README, Layouts, Scientific-states, Naming,
│   │                            # Coherence, SOURCE.md, tokens.json
│   └── components/              # One note per design component (Button.md ... Tabs.md)
├── editions/
│   └── local/README.md          # Local edition scope; no code yet (hyprn_mvp_local planned)
└── docs/
    ├── adr/                     # MADR decisions 0001..0005 + README.md
    ├── specs/                   # architecture-and-contracts, requirements, ui-target, agents,
    │                            # documents, workspaces-identity-onboarding
    ├── agents/                  # tooling-spec.md, playbook.md
    ├── product/overview.md
    ├── legal/licensing.md
    └── research/workbench-market/
```

## Directory Purposes

**`application/src/hyprn_mvp_app/`:**

- Purpose: The one cohesive Python application (API, auth, domain, store, dispatcher, static UI mount).
- Contains: Flat modules only; relative imports are single-level (`from .store import Store`).
- Key files: `api.py` (all `/api/1` routes in `create_app`), `store.py` (SQLite schema + transactions), `contracts.py` (canonical bytes, schema validation, errors), `execution_bundle.py`, `execution.py`, `dispatcher.py`, `modeling.py`, `configuration.py`, `approach.py`, `history.py`.

**`application/tests/`:**

- Purpose: Application unit and API tests in fresh scratch stores.
- Contains: `test_<topic>.py`, `conftest.py`, `fixtures/identity_golden.json`.
- Key files: `test_module_boundaries.py` (import graph and ownership pins), `test_identity_golden.py` (canonical bytes and digests corpus), `test_contract_errors.py`, `test_public_contract.py`, `test_security_regressions.py`.

**`integration/src/hyprn_mvp_integration/`:**

- Purpose: Execution and document integration: AiiDA CalcJob/parser, launcher, worker, results, native archive and documents.
- Contains: `calculation.py`, `launcher.py`, `worker.py`, `results.py`, `computational_export.py`, `documents.py`, `native.py`.
- Key files: `launcher.py` (`execution_source_hashes()` reviewed literal, attestation, `isolated()`), `worker.py` (runs inside the worker image; `load_program`), `results.py` (`ASSESSMENT_VERSION = 'fixed-threshold-1'`).
- Note: `native.py` (declared-data source validation) is consumed only by `integration/tests/test_configuration.py`; `documents.py` is consumed only by `integration/tests/test_documents_native.py` until Phase 4 wires it.

**`integration/tests/`:**

- Purpose: Native integration, worker containment, retained reads, archives, documents.
- Key files: `execution_fixtures.py`, `native_origin_fixture.py`, `capture_native_programs.py`, `fixtures/native-programs.json.gz`, `fixtures/units-native-evidence.json`.

**`contracts/`:**

- Purpose: Machine-readable wire contracts and their tests.
- Key files: `schemas/model.schema.json` (`$defs` loaded by `hyprn_mvp_app.contracts`), `schemas/execution.schema.json`, `hyprn-mvp.openapi.yaml` (generated), `modeling.openapi.yaml`, `README.md` (wire-name ↔ domain-term table, API call sequence), `tests/documents_prior_definitions.json` (pinned prior definitions).

**`modeling/`:**

- Purpose: Independently authored helpers around the patched WhatsOpt modeling service (no service source here).
- Key files: `generate_unit_catalog.py` (engine-derived unit catalog), `rehearsal.py` (builds a test image like `deployment/modeling_runtime.py`), `verify_rehearsal.py`, `provenance.md` (ordered patch table and SHA-256s).

**`upstream/whatsopt-patches/`:**

- Purpose: The AGPL-scoped adapter: ordered patches applied with `--fuzz=0` at image build.
- Contains: `010-workspace-tests.patch` … `090-quantity-definitions.patch`. The contract adapter lives in `app/services/modeling_contract.rb` inside the patches.

**`deployment/`:**

- Purpose: Component managers, images, pins, release binding, test-group runner, deployment tests and fixtures.
- Key files: `checks.py`, `local_paths.py`, `application_runtime.py`, `modeling_runtime.py`, `execution_runtime.py`, `dispatch_runtime.py` (host executor), `manage.py` (isolation attestation), `launch_worker.py`, `initialize_stores.py`, `release_binding.py`, `native_environment.py`, `pins.json`, `application.Dockerfile`, `modeling.Dockerfile`, `worker.Dockerfile`, `native.Dockerfile`, `modeling-compose.yaml`, `modeling_policy.rb`.

**`deployment/tests/`:**

- Purpose: Guards (repository, naming, hygiene, term scan), deployment hardening, bridge, attestation, native journeys, and the fixtures browser/native groups depend on.
- Key files: `live_fence.py` (process-wide audit hook fencing live roots/ports/docker), `scoped_fixture.py` (scoped scratch folders `hyprn-mvp-test-<uuid>`), `durable_fixture.py` (pinned durable native fixture below `HYPRN_MVP_TEST_FIXTURES_ROOT`), `*_fixture.py` per group, `test_repository_guard.py`, `test_naming_guard.py`, `test_hygiene_guard.py`.

**`ui/src/`:**

- Purpose: Browser client.
- Contains: Screen/panel components (`PascalCase.tsx`), domain controllers (`ApproachController.tsx`), shell model (`workspaceModel.ts`), typed record projections (`recordViews.ts`, `recordLabels.ts`, `unitLabels.ts`, `criterionLabels.ts`, `quantityDefinitions.ts`), transport (`api.ts`), generated types (`contract.ts`), styles (`styles.css`).
- Key files: `main.tsx` (entry), `Workspace.tsx` (study shell), `api.ts` (`HyprnMvpApi`, the only `/api/1` transport), `contract.ts` (generated).

**`ui/src/design/`:**

- Purpose: The only building blocks for screens.
- Key files: `index.ts` (barrel; re-exports components only, no CSS), `components.tsx`, `primitives.tsx`, `graph.tsx`, `source.tsx`, `numbers.ts`, `foundry.css`, `tokens.css` (generated from `design-system/tokens.json`).

**`ui/tests/`:**

- Purpose: Playwright browser specs and a Node unit test.
- Contains: `<kebab-topic>.spec.ts`, `support/browser.ts`, `support/served.ts`, `foundry-fixtures.ts` (in-browser API double), `evidence.ts`, `criterion-record.test.cjs`.

**`design-system/`:**

- Purpose: Visual and wording authority for the UI.
- Key files: `README.md`, `Layouts.md`, `Scientific-states.md`, `Naming.md`, `Coherence.md`, `SOURCE.md`, `tokens.json`, `components/*.md`.

**`editions/local/`:**

- Purpose: Local edition adapters and packaging (CLI `./hyprn-mvp`, prerequisite checks, OS credential store/clipboard adapters, study-folder kit, stdio MCP relay, smoke test).
- Contains: `README.md` only. `hyprn_mvp_local` does not exist yet (Phase 2).

**`docs/`:**

- Purpose: Specifications, decisions, agent rules, legal and product docs.
- Key files: `docs/specs/architecture-and-contracts.md`, `docs/specs/requirements.md`, `docs/specs/ui-target.md`, `docs/adr/0004-operation-ownership.md`, `docs/agents/tooling-spec.md`, `docs/legal/licensing.md`.

## Key File Locations

**Entry Points:**

- `application/src/hyprn_mvp_app/api.py`: `from_environment()` uvicorn factory; `create_app(store, auth, model)`.
- `application/src/hyprn_mvp_app/dispatcher.py`: `python -m hyprn_mvp_app.dispatcher` (only via host executor).
- `application/src/hyprn_mvp_app/auth.py`: `python -m hyprn_mvp_app.auth recover --store <application store>`.
- `deployment/dispatch_runtime.py`: host executor (`--start/--stop/--status/--serve`).
- `integration/src/hyprn_mvp_integration/worker.py`: `python -m hyprn_mvp_integration.worker` inside the worker image.
- `integration/src/hyprn_mvp_integration/launcher.py`: `main()` and attestation.
- `ui/src/main.tsx`: browser entry.
- `deployment/checks.py`: test-group runner.

**Configuration:**

- `deployment/local_paths.py`: every location and `HYPRN_MVP_*` variable (data root layout: `application/`, `modeling/`, `execution/`, `releases/`, `fixtures/`, `cache/upstream/whatsopt`, `evidence/`, `dev/python-native/`, `dev/python-contract/`).
- `deployment/pins.json`: image, base image, upstream commit, worker lock and source pins.
- `application/pyproject.toml`, `application/requirements.lock`, `application/dependency-pins.json`.
- `integration/pyproject.toml`, `integration/worker-requirements.lock`.
- `ui/package.json`, `ui/package-lock.json`, `ui/tsconfig.json`, `ui/vite.config.ts`, `ui/playwright.config.ts`, `ui/playwright.isolated.config.ts`.
- `ui/control-map.json`: named UI controls → spec and test title (checked by `ui/check_ui_contract.py`).
- `design-system/tokens.json`: token source.
- `.planning/config.json`: planning workflow settings.

**Core Logic:**

- `application/src/hyprn_mvp_app/execution_bundle.py`: bundle assembly/admission, `RETAINED_PAIRINGS`.
- `application/src/hyprn_mvp_app/configuration.py`: configuration preview/commit.
- `application/src/hyprn_mvp_app/approach.py`, `approach_closure.py`: Modeling approach.
- `application/src/hyprn_mvp_app/history.py`: retained-run reads.
- `application/src/hyprn_mvp_app/modeling.py`: modeling coordination and transport.
- `integration/src/hyprn_mvp_integration/calculation.py`: AiiDA side.
- `integration/src/hyprn_mvp_integration/worker.py`: numerical execution.

**Testing:**

- `application/tests/test_module_boundaries.py`: import graph, attestation scope, ownership pins.
- `deployment/checks.py` `GROUPS`: maps each group to its targets; classes `must-pass`/`opt-in`; needs `docker`/`browser`/`fixtures`/`installation`.
- `deployment/tests/live_fence.py`, `deployment/tests/scoped_fixture.py`, `deployment/tests/durable_fixture.py`.

## Naming Conventions

**Files:**

- Python modules: `snake_case.py`, one owner per module (`result_bindings.py`, `scientific_configuration.py`).
- Python tests: `test_<topic>.py`; group-specific fixtures in deployment: `<topic>_fixture.py` (`units_native_fixture.py`, `approach_ui_fixture.py`).
- Deployment managers: `<component>_runtime.py` (`application_runtime.py`, `modeling_runtime.py`, `execution_runtime.py`, `dispatch_runtime.py`).
- Dockerfiles: `<component>.Dockerfile`.
- React components and screens: `PascalCase.tsx` (`ConfigurationPanel.tsx`, `RunPanel.tsx`); non-component modules: `camelCase.ts` (`workspaceModel.ts`, `recordViews.ts`); `runStatus.tsx` is a camelCase helper with JSX.
- Browser specs: `kebab-case.spec.ts` (`unit-authoring.spec.ts`).
- WhatsOpt patches: `NNN-kebab-name.patch`, numbered in steps of 10, applied in order.
- ADRs: `NNNN-kebab-title.md` in `docs/adr/`.
- Design component notes: `PascalCase.md` in `design-system/components/`.
- Top-level docs: `UPPERCASE.md` (`AGENTS.md`, `CONTEXT.md`, `README.md`); design-system docs: `PascalCase.md`.

**Directories:**

- Python packages: `hyprn_mvp_*` under `<area>/src/` (`application/src/hyprn_mvp_app`, `integration/src/hyprn_mvp_integration`, planned `editions/local/src/hyprn_mvp_local`). `deployment/tests/test_naming_guard.py` enforces the prefix for `application/src`, `integration/src` and `editions/*/src`.
- Technical identifiers use `hyprn-mvp` (containers `hyprn-mvp-application`, `hyprn-mvp-modeling`, network `hyprn-mvp-private`, label `org.hyprn-mvp.owner`); environment variables use `HYPRN_MVP_*`.
- No durable name encodes a phase, architecture style or person (spec §9).

**Wire names:**

- Keep legacy persisted names exactly (`ModelPackageN`, `model_revision_id`, `assessment`); map them to domain terms through `contracts/README.md`. New shapes get a new numeric suffix (`ExecutionBundle9`, `Model5`).

## Where to Add New Code

**New API route:**

- Primary code: add the handler inside `create_app` in `application/src/hyprn_mvp_app/api.py`, with a closed Pydantic body model (`class X(Closed)`), and delegate to the owning domain module. No business logic in the handler.
- Contract: regenerate `contracts/hyprn-mvp.openapi.yaml` with `application/generate_contract.py`, then `ui/src/contract.ts` with `python3 ui/generate_types.py`.
- Tests: `application/tests/test_<topic>.py`; keep `contracts/tests` and `python3 ui/check_ui_contract.py` green.

**New domain capability / module:**

- Implementation: a new flat module `application/src/hyprn_mvp_app/<owner>.py` with one narrow public interface; transactions go through `Store.connection(write=True)` / `Store.command(...)`.
- Keep the import graph acyclic; place pure functions in their owner; pure modules (`contracts`, `units`, `scientific_configuration`, `approach_closure`, `execution_bundle`) never import `store`, HTTP or engines.
- Update the module table in `application/README.md` and `docs/specs/architecture-and-contracts.md` §7. Add a pin to `application/tests/test_module_boundaries.py` only against a concrete regression.
- New tables: append `CREATE TABLE IF NOT EXISTS` to `SCHEMA` in `application/src/hyprn_mvp_app/store.py`; immutable records get BEFORE UPDATE/DELETE triggers like `immutable_configuration_update`.

**Agent tools (Phase 3):**

- Implementation: planned modules `agent_tools`, `agent_runtime`, `agent_surface` in `application/src/hyprn_mvp_app/`; tools see only `contracts` and an injected API client (spec §7, `docs/agents/tooling-spec.md`).

**Local edition code (Phase 2):**

- Implementation: `editions/local/src/hyprn_mvp_local/` (CLI, OS adapters, MCP relay); path policy stays single-sourced.

**New wire shape:**

- Implementation: add a new versioned `$defs` entry in `contracts/schemas/model.schema.json` or `contracts/schemas/execution.schema.json`; never edit an existing definition (prior definitions are pinned by contract tests).
- If it is a historical record combination, extend `RETAINED_PAIRINGS` in `application/src/hyprn_mvp_app/execution_bundle.py` only.

**Execution-side code:**

- Implementation: `integration/src/hyprn_mvp_integration/`. If the module joins the launch-path closure, update the reviewed literal in `launcher.execution_source_hashes()` and `ATTESTED_PROJECT_FILES` in `application/tests/test_module_boundaries.py`; the worker image copies only `worker.py`, `results.py`, `__init__.py` (`deployment/worker.Dockerfile`).

**Modeling service change:**

- Implementation: a new ordered patch `upstream/whatsopt-patches/NNN-<name>.patch` (AGPL notice), registered in `modeling/provenance.md`, `deployment/modeling.Dockerfile` / `deployment/modeling_runtime.py`, and the private contract `contracts/modeling.openapi.yaml`.

**UI screen or panel:**

- Implementation: `ui/src/<PascalCase>.tsx`, built only from `ui/src/design` exports; data only through `HyprnMvpApi` in `ui/src/api.ts`; version branching only in projections (`ui/src/recordViews.ts`).
- New design component: `ui/src/design/components.tsx` or `primitives.tsx`, exported from `ui/src/design/index.ts`, documented in `design-system/components/<Name>.md`.
- Tokens: edit `design-system/tokens.json`, regenerate `ui/src/design/tokens.css` with `python3 ui/design_tokens.py`.
- Tests: `ui/tests/<kebab-topic>.spec.ts`; register the control in `ui/control-map.json`.

**New test group:**

- Register targets in `GROUPS` in `deployment/checks.py` and add the group to the matching class/need sets (`DOCKER_GROUPS`, `BROWSER_GROUPS`, `FIXTURE_GROUPS`, `OPT_IN_GROUPS`). Deployment test modules start with the `live_fence` prelude.

**Utilities:**

- Shared canonical/digest/ID/error helpers: `application/src/hyprn_mvp_app/contracts.py`.
- Unit helpers: `application/src/hyprn_mvp_app/units.py`.
- Location resolution: `deployment/local_paths.py`.
- UI number formatting: `ui/src/design/numbers.ts`.

**Decisions:**

- New ADR `docs/adr/NNNN-<title>.md` (MADR); an accepted record is superseded by a new one, never edited.

## Special Directories

**`.planning/`:**

- Purpose: `PROJECT.md`, `ROADMAP.md`, `STATE.md`, `config.json`, `phases/<NN-name>/` plans and checkpoints, `codebase/` maps.
- Generated: No (authored by planning workflows).
- Committed: Yes (`.planning/research/.cache/` ignored).

**`.claude/skills/`:**

- Purpose: Project skill `hyprn-mvp-ui`.
- Generated: No. Committed: Yes. (`.claude/worktrees/` and `.claude/settings.local.json` are ignored.)

**`contracts/hyprn-mvp.openapi.yaml`:**

- Purpose: Public API contract.
- Generated: Yes (`application/generate_contract.py`). Committed: Yes. Never hand-edit.

**`ui/src/contract.ts`:**

- Purpose: TypeScript types for the public API.
- Generated: Yes (`ui/generate_types.py`). Committed: Yes. Never hand-edit.

**`ui/src/design/tokens.css`:**

- Purpose: CSS custom properties.
- Generated: Yes (`ui/design_tokens.py` from `design-system/tokens.json`). Committed: Yes. Never hand-edit.

**`ui/node_modules/`, `ui/dist/`, `ui/test-results/`, `ui/playwright-report/`:**

- Generated: Yes. Committed: No.

**`integration/tests/fixtures/`, `application/tests/fixtures/`:**

- Purpose: Pinned test fixtures (`native-programs.json.gz`, `units-native-evidence.json`, `identity_golden.json`).
- Generated: Captured by tracked tools (`integration/tests/capture_native_programs.py`). Committed: Yes.

**Development data root (outside the repository):**

- Purpose: Stores, releases, durable fixtures, upstream cache, evidence, development interpreters (layout in `deployment/local_paths.py`).
- Generated: Yes. Committed: Never; the repository must not hold stores, logs, scratch, evidence or credentials (`.gitignore` blocks `*.sqlite3`, `*.log`, `.env*`, `credentials/`).

---

*Structure analysis: 2026-10-13*
