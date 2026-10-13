---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
<!-- refreshed: 2026-10-13 -->

# Architecture

**Analysis Date:** 2026-10-13

Binding sources for everything below: `AGENTS.md`, `CONTEXT.md` (domain language), `docs/specs/architecture-and-contracts.md` (§3 component ownership, §3.1 unified operations, §6 API rules, §7 module ownership, §8 persistence) and `docs/adr/0004-operation-ownership.md`. If code and those documents disagree, the spec governs and the drift below is a finding, not a precedent.

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Clients (interchangeable, thin)                      │
├────────────────────────┬─────────────────────────┬───────────────────────────┤
│  Browser UI (React 19) │  Agent tool surface     │  Local CLI                │
│  `ui/src/`             │  (planned, Phase 3:     │  (planned, Phase 2:       │
│  `ui/src/api.ts`       │  agent_tools/runtime/   │  `editions/local/`,       │
│                        │  surface in app)        │  `hyprn_mvp_local`)       │
└───────────┬────────────┴────────────┬────────────┴─────────────┬─────────────┘
            │  same-origin fetch, session cookie, Origin + X-CSRF-Token
            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  HYPRN MVP application  `application/src/hyprn_mvp_app/`  (one container)    │
│  api.py (FastAPI /api/1) → domain modules → store.py (SQLite, sole writer)   │
│  ui.py serves compiled UI at /ui                                             │
├──────────────────────────────┬───────────────────────────────────────────────┤
│  modeling.py ModelingClient  │  dispatcher.py (trusted, NOT an endpoint)     │
│  signed scoped envelope      │  stdio bridge, started by host executor       │
└──────────────┬───────────────┴───────────────────────┬───────────────────────┘
               │ HTTP /modeling/1 (private net)        │ framed JSON over stdio
               ▼                                       ▼
┌──────────────────────────────┐   ┌───────────────────────────────────────────┐
│ Private modeling service     │   │ Trusted host executor                     │
│ patched WhatsOpt (Rails)     │   │ `deployment/dispatch_runtime.py`          │
│ `upstream/whatsopt-patches/` │   │ + `hyprn_mvp_integration.calculation`     │
│ `deployment/modeling*`       │   │ AiiDA profile (sole writer), CalcJob      │
│ own SQLite store             │   │ `integration/src/hyprn_mvp_integration/`  │
└──────────────────────────────┘   └───────────────────┬───────────────────────┘
                                                       │ launcher.isolated()
                                                       ▼  docker run, no network
                                   ┌───────────────────────────────────────────┐
                                   │ Restricted worker (OpenMDAO 3.45.1)       │
                                   │ `integration/.../worker.py`, `results.py` │
                                   │ image: `deployment/worker.Dockerfile`     │
                                   └───────────────────────────────────────────┘
```

Contracts that bind the edges: `contracts/hyprn-mvp.openapi.yaml` (public, generated), `contracts/modeling.openapi.yaml` (private Modeling Backend Contract), `contracts/schemas/model.schema.json` and `contracts/schemas/execution.schema.json` (authored JSON Schema 2020-12).

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Public API | HTTP surface `/api/1`, request bounds, origin/CSRF middleware, error envelope, route → domain module delegation | `application/src/hyprn_mvp_app/api.py` |
| Store | SQLite transactions, command receipts, studies, memberships, archive state, exact evidence reads/snapshots, run associations, outbox | `application/src/hyprn_mvp_app/store.py` |
| Contracts core | Canonical JSON (RFC 8785), digests, IDs, strict JSON, schema validation, `DomainError`/`ContractError` | `application/src/hyprn_mvp_app/contracts.py` |
| Units | Unit labels, active ports, resolved units, single port-units rule `port_units` | `application/src/hyprn_mvp_app/units.py` |
| Model coordination | `ModelingClient` (signed private transport), `Coordinator` (durable model commands, portable record checks), pure `checked_model` | `application/src/hyprn_mvp_app/modeling.py` |
| Modeling approach | Approach drafts, versions, preview, restore, `saved_version` | `application/src/hyprn_mvp_app/approach.py` |
| Approach closure | Reference-only validation of an exact approach closure | `application/src/hyprn_mvp_app/approach_closure.py` |
| Configurations | Preview → candidate digest → commit with write-time rechecks | `application/src/hyprn_mvp_app/configuration.py` |
| Scientific snapshot | Literal scientific projection of a configuration | `application/src/hyprn_mvp_app/scientific_configuration.py` |
| Execution bundle | Bundle assembly, admission, re-admission, version predicates, `RETAINED_PAIRINGS` table | `application/src/hyprn_mvp_app/execution_bundle.py` |
| Submissions | Run receipt + outbox, static preparation, dispatch, record adoption | `application/src/hyprn_mvp_app/execution.py` |
| Dispatcher | Serialized dispatch loop, `NativeBridge` stdio client, export iterations | `application/src/hyprn_mvp_app/dispatcher.py` |
| History | Authorized retained-run reads, outcome completeness, read integrity | `application/src/hyprn_mvp_app/history.py` |
| Result-linked inputs | Result sources for result-linked inputs (via `history`) | `application/src/hyprn_mvp_app/result_bindings.py` |
| Modified runs | Modified-run seeds (via `history`) | `application/src/hyprn_mvp_app/modified_runs.py` |
| Computational record export | Export requests, preview, archive inspection and publication | `application/src/hyprn_mvp_app/computational_export.py` |
| Readiness | Executor observation publication, runtime identity/comparison, execution readiness | `application/src/hyprn_mvp_app/readiness.py` |
| Auth | Local users, scrypt hashes, sessions, CSRF, recovery CLI | `application/src/hyprn_mvp_app/auth.py` |
| Static UI mount | Same-origin compiled assets with CSP | `application/src/hyprn_mvp_app/ui.py` |
| AiiDA integration | `ScalarCalculation` CalcJob, `ScalarParser`, `NativeExecution` (host side of the bridge) | `integration/src/hyprn_mvp_integration/calculation.py` |
| Launcher | Attestation, attested source set, bounded `docker run` of the worker | `integration/src/hyprn_mvp_integration/launcher.py` |
| Worker | Re-admits frozen bundle, loads generated Group, runs OpenMDAO, writes results | `integration/src/hyprn_mvp_integration/worker.py` |
| Result protocol | Data-only result protocol, fixed-threshold criterion evaluation (`ASSESSMENT_VERSION`) | `integration/src/hyprn_mvp_integration/results.py` |
| Native archive | AiiDA archive creation for computational record exports | `integration/src/hyprn_mvp_integration/computational_export.py` |
| Native documents | Original-bytes storage on AiiDA (Phase 4; only tests consume it today) | `integration/src/hyprn_mvp_integration/documents.py` |
| Modeling service | Editable graph, versions, static OpenMDAO generation, prepared artifacts | `upstream/whatsopt-patches/*.patch`, `deployment/modeling_policy.rb`, `deployment/modeling.Dockerfile` |
| UI shell | Study shell, navigation, editor guards, composition of domain panels | `ui/src/Workspace.tsx`, `ui/src/workspaceModel.ts` |
| UI API client | The only transport to `/api/1` | `ui/src/api.ts` (`HyprnMvpApi`) |
| UI design layer | Token-driven components; the only allowed building blocks | `ui/src/design/index.ts` |
| Check runner | Fail-closed test-group runner | `deployment/checks.py` |
| Path policy | Single resolver of every local location | `deployment/local_paths.py` |

## Pattern Overview

**Overall:** Modular monolith with explicit single-owner modules, plus two separately deployed, contract-bound units (private modeling service, restricted worker) and an out-of-process trusted executor. Cross-store work uses intent-persisting receipts and an outbox, never distributed transactions (spec §6.6, ADR-0004).

**Key Characteristics:**

- One public API (`/api/1`) for every client; no client gets native modeling payloads or routes (spec §6.1).
- Each store has exactly one writer: application store → application; modeling store → modeling service; AiiDA profile/repository → execution integration on the host executor (spec §8).
- Central invariant (ADR-0004): every operation produces one authoritative, stored outcome that any client can read back without repeating the operation. The platform owns what happened; clients only compose.
- Flat Python packages with an acyclic import graph, function-local imports included. Relative imports deeper than one level are refused by the boundary test.
- Immutable records: SQLite triggers forbid UPDATE/DELETE on `evidence`, `configurations`, `approach_versions`, `study_archive` (`application/src/hyprn_mvp_app/store.py` SCHEMA).
- Versioned record formats as closed alternatives (`Model4`, `ExecutionBundle8`, `ConfigurationRevision4`); existing shapes are never edited; historical readers are data-only.
- Candidate model code is imported only inside the attested restricted worker.

## Layers

**Clients:**

- Purpose: Presentation and interaction state only.
- Location: `ui/src/` (browser). Agent tools (`agent_tools`, `agent_runtime`, `agent_surface`) and the local CLI (`hyprn_mvp_local`) are specified but not present yet.
- Contains: React components, controllers, typed record projections, generated contract types.
- Depends on: `/api/1` only, through `ui/src/api.ts`.
- Used by: People (and, later, agents over MCP).

**API edge:**

- Purpose: Routing, authentication, request bounds, error envelope.
- Location: `application/src/hyprn_mvp_app/api.py`, `application/src/hyprn_mvp_app/auth.py`, `application/src/hyprn_mvp_app/ui.py`.
- Contains: `create_app(store, auth, model)`, closed Pydantic request models (`extra="forbid", strict=True`), `from_environment()` factory.
- Depends on: every domain module.
- Used by: uvicorn (`deployment/application.Dockerfile` CMD), `application/generate_contract.py` (calls `create_app(None, None, None).openapi()`).

**Domain modules:**

- Purpose: Business resources and operation lifecycles (domain state per ADR-0004).
- Location: `application/src/hyprn_mvp_app/{approach,configuration,execution,history,result_bindings,modified_runs,computational_export,modeling,readiness}.py`.
- Contains: Classes constructed once per app (`Coordinator`, `Configurations`, `Approaches`, `Submissions`, `History`, `ResultBindings`, `ModifiedRuns`, `ComputationalRecords`).
- Depends on: pure modules, `store`.
- Used by: `api`, `dispatcher`.

**Pure (data-only) modules:**

- Purpose: Canonical bytes, schemas, units, snapshots, bundle admission; shared with the execution side and bound into the attestation.
- Location: `application/src/hyprn_mvp_app/{contracts,units,scientific_configuration,approach_closure,execution_bundle}.py`.
- Depends on: standard library, `jsonschema`, `rfc8785`; never on `store`, HTTP clients, AiiDA or OpenMDAO (pinned by `test_pure_contract_and_unit_imports_do_not_load_storage_clients_or_runtime`).
- Used by: domain modules and `hyprn_mvp_integration`.

**Persistence:**

- Purpose: Transactions and authorization reads.
- Location: `application/src/hyprn_mvp_app/store.py` (`Store.connection(write=True)` = `BEGIN IMMEDIATE`; `Store.command(...)` = idempotent receipt-scoped command).
- Depends on: `contracts` (top-level), `readiness` (function-local).

**Execution integration (host side):**

- Purpose: AiiDA process lifecycle, retained artifacts, launching the worker.
- Location: `integration/src/hyprn_mvp_integration/` (`calculation.py`, `launcher.py`, `computational_export.py`, `documents.py`), driven by `deployment/dispatch_runtime.py`.
- Depends on: `aiida-core==2.9.3`, pure application modules only.

**Restricted worker:**

- Purpose: Run the exact frozen generated program.
- Location: `integration/src/hyprn_mvp_integration/worker.py`, `integration/src/hyprn_mvp_integration/results.py` (copied alone into the image by `deployment/worker.Dockerfile`).
- Depends on: `results` and the standard library only (spec §7: `worker → results only`).

## Application module graph

Spec target (`docs/specs/architecture-and-contracts.md` §7):

```text
contracts ← units ← {scientific_configuration, approach_closure} ← execution_bundle
  ← {history ← {result_bindings, modified_runs}, execution, configuration, approach, computational_export} ← api
modeling → {units, contracts};  store → contracts
integration → {contracts, units, scientific_configuration, approach_closure, execution_bundle} only
worker → results only (standard library otherwise)
```

Actual edges in the tree (static and function-local imports, derived from the sources on the analysis date; the graph is acyclic):

| Module | Imports (project modules) |
|---|---|
| `contracts`, `ui`, `__init__` | none |
| `units`, `scientific_configuration`, `readiness` | `contracts` |
| `store` | `contracts`; `readiness` (function-local, lines ~214 and ~233) |
| `approach_closure` | `contracts`, `units` |
| `execution_bundle` | `approach_closure`, `contracts`, `scientific_configuration`, `units` |
| `history` | `contracts`, `execution_bundle`, `units` |
| `auth` | `contracts`, `store` |
| `modeling` | `contracts`, `units`, `store` (for `ForeignEvidence`) |
| `result_bindings` | `contracts`, `execution_bundle`, `history`, `units` |
| `modified_runs` | `contracts`, `history`, `readiness` |
| `approach` | `approach_closure`, `contracts`, `execution_bundle`, `history`, `store` |
| `execution` | `contracts`, `execution_bundle`, `history`, `result_bindings`, `scientific_configuration`, `readiness` (function-local) |
| `computational_export` | `approach_closure`, `contracts`, `execution_bundle`, `history`, `modified_runs`, `result_bindings` |
| `configuration` | `approach`, `contracts`, `execution_bundle`, `history`, `modeling`, `modified_runs`, `result_bindings`, `store`, `units`, `scientific_configuration` and `readiness` (function-local) |
| `api` | `approach`, `auth`, `computational_export`, `configuration`, `contracts`, `execution`, `history`, `modeling`, `modified_runs`, `readiness`, `result_bindings`, `store`, `ui` (function-local) |
| `dispatcher` | `computational_export`, `contracts`, `execution`, `execution_bundle`, `modeling`, `readiness`, `store` |
| `hyprn_mvp_integration.launcher`, `.results` | `hyprn_mvp_app.contracts`, `hyprn_mvp_app.execution_bundle` |
| `hyprn_mvp_integration.computational_export` | `hyprn_mvp_app.contracts`, `hyprn_mvp_app.execution_bundle`, `.results` |
| `hyprn_mvp_integration.calculation` | `hyprn_mvp_app.contracts`, `hyprn_mvp_app.execution_bundle`, `.launcher`, `.computational_export`, `.results` |
| `hyprn_mvp_integration.worker` | `.results` |
| `hyprn_mvp_integration.native`, `.documents` | none |

Edges present in code but not drawn in the §7 diagram: `modeling → store`, `store → readiness`, `configuration → {modeling, readiness, scientific_configuration}`, `execution → readiness`, `modified_runs → readiness`, `dispatcher → computational_export`. None creates a cycle. Treat the table above as the current graph and the §7 diagram as the direction rule.

### What the module-boundary test pins

`application/tests/test_module_boundaries.py` (run in check group `locality-contracts` with `application/tests/test_identity_golden.py` and `application/tests/test_contract_errors.py`):

- Pure imports load nothing heavy: importing `contracts` + `units` loads no `httpx`, `sqlite3`, `fastapi`, `starlette`, `aiida`, `openmdao`, `store`, `modeling`, `execution` or `hyprn_mvp_integration`.
- Integration seam: everything reachable from `launcher`, `calculation`, `results`, `computational_export` stays inside `PURE = {hyprn_mvp_app, contracts, units, scientific_configuration, approach_closure, execution_bundle}`.
- Attestation scope: `ATTESTED_PROJECT_FILES` equals the static import closure of `launcher`, `calculation`, `results`, `worker`, and equals the reviewed literal list in `launcher.execution_source_hashes()` (`integration/src/hyprn_mvp_integration/launcher.py:101`).
- Dynamic loading in attested modules is banned except `DYNAMIC_ALLOWLIST` entries pinned by file and line (`calculation.py` 66 and 129; `worker.py` 1010, 1013, 1014).
- Temporary forwarding aliases (`MOVED` table) in `store`, `modeling`, `execution`, `result_bindings`, `modified_runs` are never imported by production code (`ALLOWED = set()`).
- `history` never reaches `result_bindings` or `modified_runs`; those two never reach each other.
- `approach` never reaches `configuration`; `configuration → approach` is a top-level import.
- Only `store` validates `EvidenceRecordRead` or selects evidence rows; the two other raw statements are listed in `EVIDENCE_WITNESSES`.
- Only `store` reads `model_associations`, except the reviewed `ASSOCIATION_STATEMENTS`.
- Cross-object private attribute access in the app equals `PRIVATE_ALLOWLIST` exactly.
- `RETAINED_PAIRINGS` (twelve historic tuples) lives only in `execution_bundle`; `port_units` lives only in `units`.
- Public API wording: "package" only for method packages.

The test pins specific directions; it does not assert global acyclicity of the whole package. Keep the graph acyclic by construction (see Anti-Patterns).

## Data Flow

### Primary Request Path (any UI read or command)

1. UI calls a method of `HyprnMvpApi`, which calls `fetch('/api/1' + path, {credentials: 'same-origin', headers: {'X-CSRF-Token': csrf}})` (`ui/src/api.ts:169`).
2. Middleware `boundaries` assigns `request_id`, checks host and exact `Origin`, CSRF on mutations, and body bounds (`application/src/hyprn_mvp_app/api.py:114`).
3. Closed Pydantic body model validates shape; handler calls `valid_id(...)` for every UUID (`api.py:77`).
4. Handler delegates to the owning domain object created in `create_app` (`api.py:102-112`).
5. Domain object authorizes actor/study/resource via `Store.authorize` inside a `Store.connection()` (`store.py:243`), runs a single local transaction; mutations go through `Store.command(actor, study, category, command_id, payload, operation)` (`store.py:372`) for idempotent replay.
6. Response is `{schema_version, request_id, ...data}`; failures are `DomainError` → `error_response` (`api.py:97`) with closed `code`, `fields`, `outcome`.

### Model command (cross-store, modeling service owns the graph)

1. `POST /studies/{id}/models/{mid}/edits` → `Coordinator.execute` (`application/src/hyprn_mvp_app/modeling.py:270`) reserves a pending receipt with the exact remote operation, payload and command ID in the application store.
2. `ModelingClient.call` (`modeling.py:26`) signs an HS256 envelope `{actor_id, study_id, resource_ids, permissions, expires_at, request_id, method, path, body_sha256}` and posts to `/modeling/1/...`.
3. The modeling service (patched WhatsOpt, `app/services/modeling_contract.rb` from `upstream/whatsopt-patches/040..090`) applies the batch atomically against `expected_revision` and records its own receipt.
4. `Coordinator.reconcile` (`modeling.py:292`) adopts the authoritative remote receipt; a lost reply is resolved by lookup, never by resending.

### Configuration preview and commit

1. `POST /configurations/preview` → `Configurations.preview` (`application/src/hyprn_mvp_app/configuration.py:172`): resolves evidence snapshots via `store`, fetches the exact committed model version, verifies digests and source hashes, calls the pure compatibility operation; allocates nothing.
2. `POST /configurations` with `expected_preview_digest` = candidate digest → `Configurations.commit` (`configuration.py:201`): re-resolves everything, freezes configuration, model snapshot, context and evidence in one transaction with study-revision compare-and-set.

### Run submission → execution → recording

1. `POST /studies/{id}/runs` (`api.py:481`) → `Submissions.submit` (`application/src/hyprn_mvp_app/execution.py:70`): one transaction inserts `run_associations`, an `outbox` row in state `accepted_run`, and the run receipt. Returns 202 with `receipt_url`. The API process never dispatches (`Submissions(store, None, None)` at `api.py:107`).
2. Host executor `deployment/dispatch_runtime.py --serve` holds the AiiDA profile and `executor.lock`, constructs `NativeExecution.from_environment()` (`integration/src/hyprn_mvp_integration/calculation.py:151`), and spawns `docker exec -i hyprn-mvp-application python -B -m hyprn_mvp_app.dispatcher --with-exports`, serving its stdio through `bridge_child` (`dispatch_runtime.py:43`).
3. `dispatcher.main` (`application/src/hyprn_mvp_app/dispatcher.py:174`) loops: refreshes the execution observation, selects `outbox` rows in `accepted_run`/`dispatching`, calls `Submissions.dispatch` (`execution.py:173`).
4. Dispatch prepares statically through the modeling service (`StaticPreparation`, `execution.py:23`), assembles the execution bundle (`execution_bundle.assemble_bundle`), claims the run, then crosses the bridge with `NativeBridge.launch` (`dispatcher.py:163`). Bridge verbs are a closed set: `require_attestation`, `bundle_runtime`, `launch`, `matches`, `inspect`, `read_record`, `resolve_results`, `archive_record` (`BRIDGE_ARITIES`, `dispatcher.py:50`).
5. Host side `NativeExecution.launch` (`calculation.py:312`) submits AiiDA `ScalarCalculation` (`calculation.py:25`); AiiDA retains bundle and artifacts before launch.
6. The CalcJob runs `launcher.isolated` (`integration/src/hyprn_mvp_integration/launcher.py:259`) after `require_attestation`: `docker run` of the worker image with `-m hyprn_mvp_integration.worker /input <digest> ...`, no network, non-root, read-only, bounded.
7. `worker.execute` (`integration/src/hyprn_mvp_integration/worker.py:1114`) re-admits the bundle bytes, `load_program` (`worker.py:1006`) loads the generated Group through the fixed entrypoint, runs OpenMDAO, writes `results.json` with separate outcome facets; `results.evaluate_criteria` gives criterion evaluations.
8. `ScalarParser` (`calculation.py:116`) parses bounded output. The dispatcher reads the retained record back (`NativeBridge.read_record`) and `Submissions._record` (`execution.py:133`) stores the native association, the history projection and state `recorded`. Uncertain launches become `uncertain` and are never redispatched.

### Historical read

1. `GET /studies/{id}/runs/{run_id}` (`api.py:485`) → `Submissions.read` + `History.read` (`application/src/hyprn_mvp_app/history.py:243`) from application-store rows only; `retained_read_integrity` reports partial/corrupt artifacts.
2. Never consults the current model, configuration or evidence; works with the modeling service offline.

### Computational record export

1. `POST /computational-record-previews` → `POST /computational-records` (202) → `ComputationalRecords` (`application/src/hyprn_mvp_app/computational_export.py:362`) stores the request.
2. The dispatcher's export iteration (`export_once`, `dispatcher.py:171`) calls `NativeBridge.archive_record`; host side uses `integration/src/hyprn_mvp_integration/computational_export.py` (AiiDA archive). The app verifies and publishes; `GET .../download` serves the archive.

**State Management:**

- Domain state: application SQLite store (`store.py` SCHEMA tables `users`, `sessions`, `studies`, `memberships`, `model_associations`, `evidence`, `evidence_families`, `configuration_families`, `configurations`, `receipts`, `run_associations`, `outbox`, `execution_observation`, `computational_record_requests`, `approach_drafts`, `approach_versions`, `study_archive`). Rollback-journal mode, no WAL; keep reads short.
- Execution state: AiiDA (processes, bundles, results, artifacts) and the modeling store (models, versions). The app keeps only associations, receipts and a status projection.
- Interaction state: browser only (unsaved buffers, selection, editor guards in `ui/src/workspaceModel.ts`).

## Key Abstractions

**Command receipt:**

- Purpose: Idempotency and recovery for every mutation; states `absent`, `rejected`, `committed`, `pending_remote`, `accepted_run`, `dispatching`, `recorded`, `uncertain` (spec §6.6).
- Examples: `Store.command`, `Store.command_receipt`, `Store.replay` (`application/src/hyprn_mvp_app/store.py:335-398`); `GET /studies/{id}/commands/{command_id}` (`api.py:458`).
- Pattern: Persist intent locally, invoke remote with the same command ID, adopt the remote receipt.

**Preview → digest → commit:**

- Purpose: Dry run without persistent effect, then commit bound to the previewed candidate.
- Examples: `Configurations.preview/commit`, `Approaches.preview` (`application/src/hyprn_mvp_app/approach.py:340`), model `/preview` + `/edits`.

**Execution bundle:**

- Purpose: Frozen self-contained input of one run; admitted by the app, re-admitted by launcher and worker.
- Examples: `application/src/hyprn_mvp_app/execution_bundle.py`, `launcher.verify_execution_bundle` (`launcher.py:216`), `worker.read_inputs` (`worker.py:862`).

**Retained pairing table:**

- Purpose: The single closed table of readable historical record-format combinations.
- Examples: `RETAINED_PAIRINGS`, `bundle_family` in `execution_bundle.py`; unknown → `unsupported_record_version`.

**Signed scoped modeling envelope:**

- Purpose: Private service authentication bound to method, path, body hash, short expiry.
- Examples: `ModelingClient.call` (`application/src/hyprn_mvp_app/modeling.py:26`).

**Attestation:**

- Purpose: Execution is refused unless target, image, launcher, policy and attested source set match.
- Examples: `launcher.execution_source_hashes`, `launcher.attest`, `launcher.require_attestation` (`launcher.py:101-176`, `312`); built by `deployment/execution_runtime.py`, `deployment/manage.py verify-isolation`.

**Typed record projections (UI):**

- Purpose: Presentation never branches on wire versions directly.
- Examples: `ui/src/recordViews.ts`, `ui/src/recordLabels.ts`, `ui/src/unitLabels.ts`, `ui/src/criterionLabels.ts`.

## Entry Points

**Application HTTP server:**

- Location: `application/src/hyprn_mvp_app/api.py` `from_environment()` (factory).
- Triggers: `python -m uvicorn hyprn_mvp_app.api:from_environment --factory` (`deployment/application.Dockerfile`).
- Responsibilities: Builds `Store`, `Auth`, `ModelingClient` from `HYPRN_MVP_APP_STORE`, `HYPRN_MVP_ORIGIN`, `HYPRN_MVP_MODEL_URL`, `HYPRN_MVP_MODEL_KEY_FILE`; mounts the UI at `/ui`.

**Dispatcher (app side of the bridge):**

- Location: `application/src/hyprn_mvp_app/dispatcher.py` `main()`.
- Triggers: `docker exec` from the host executor only; modes `--with-exports`, `--once`, `--run-id`, `--hydrate`, `--exports-only`, `--prepare-only`, `--fault`.
- Responsibilities: Serialized dispatch, observation publication, export iterations.

**Host executor:**

- Location: `deployment/dispatch_runtime.py` (`--start/--stop/--status/--serve`).
- Triggers: Deployment manager; binds to a retained release via `release_binding.entrypoint` before any project import.
- Responsibilities: Owns AiiDA, flock, bridge.

**Auth recovery CLI:**

- Location: `application/src/hyprn_mvp_app/auth.py` `main()`; `python -m hyprn_mvp_app.auth recover --store <application store>`.

**Worker:**

- Location: `integration/src/hyprn_mvp_integration/worker.py` `main()` (`worker.py:1225`), run as `-m hyprn_mvp_integration.worker` inside the worker container.

**AiiDA plugins:**

- Location: `integration/pyproject.toml` entry points `hyprn_mvp.scalar` → `calculation:ScalarCalculation` / `calculation:ScalarParser`.

**UI:**

- Location: `ui/src/main.tsx` renders `<Workspace />` from `ui/src/Workspace.tsx`; built by Vite with `base: '/ui/'` (`ui/vite.config.ts`).

**Deployment managers (development, stdlib):**

- `deployment/application_runtime.py`, `deployment/modeling_runtime.py`, `deployment/execution_runtime.py`, `deployment/manage.py`, `deployment/initialize_stores.py`, `deployment/native_environment.py`, `deployment/release_binding.py`, `deployment/launch_worker.py`.

**Contract and type generation:**

- `application/generate_contract.py` → `contracts/hyprn-mvp.openapi.yaml`; `ui/generate_types.py` → `ui/src/contract.ts`; `ui/design_tokens.py` → `ui/src/design/tokens.css`.

**Check runner:**

- `deployment/checks.py` (`--list`, `--group <group>`, `--group qualification`). `AGENTS.md` still names `deployment/phase02_checks.py`; that file no longer exists.

## Architectural Constraints

- **Threading:** API is a synchronous FastAPI app (handlers are plain `def`, run in the threadpool); every request opens its own short SQLite connection (`Store.connection`, 15 s busy timeout). Dispatch is single-process and serialized (one dispatcher, host `executor.lock`). Launcher uses a `ThreadPoolExecutor` only to drain container output.
- **Global state:** `contracts.SCHEMA`/`VALIDATORS` loaded at import from `contracts/schemas/model.schema.json` via `Path(__file__).resolve().parents[3]` (requires the repository layout, reproduced in the container as `/app/application` + `/app/contracts`); `units.UNIT_CATALOG_DIGEST`; `deployment/local_paths.py` resolves roots at import in each manager (`ROOT = local_paths.execution_root(required=False)`); `release_binding.ACTIVE`.
- **Circular imports:** None today. The former `history ↔ result_bindings ↔ modified_runs` and `approach ↔ configuration` cycles are broken and pinned.
- **Attested closure:** Any change to a file in `launcher.execution_source_hashes()` (app pure modules, integration modules, `deployment/worker.Dockerfile`, `deployment/pins.json`, modeling deployment inputs, schemas, patches) invalidates the attestation; execution is refused until rebuilt and re-attested.
- **No code execution outside the worker:** `integration/src/hyprn_mvp_integration/native.py` parses with `ast`, never imports; modeling service generation is static.
- **Store location:** `Store.__init__` refuses symlinked parents and any path containing `CloudStorage` (`store.py:180`).
- **Fixed container path:** `from_environment()` mounts the UI from `/app/ui` (container-internal path set by `deployment/application.Dockerfile`).
- **Edition selection:** By installation configuration `edition` field only; editions hold adapters and packaging, never scientific/API behavior (spec §9).

## Anti-Patterns

### Client-side orchestration of shared state

**What happens:** A client chains several writes (or keeps an outbox/rollback) so stores stay consistent only if it finishes.
**Why it's wrong:** Violates ADR-0004 consequence 2; a stopped client leaves state no server owner can recover.
**Do this instead:** Put coordination in a server owner with a receipt or operation resource, as `Submissions.submit` + outbox does (`application/src/hyprn_mvp_app/execution.py:70`). UI recovers by reading the receipt (`GET .../commands/{command_id}`), never by resending.

### Recomputing a result for display

**What happens:** A view re-runs or re-resolves live content to show an earlier result.
**Why it's wrong:** The displayed number can differ from the recorded one (ADR-0004 consequence 3).
**Do this instead:** Read the stored resource. `ui/check_ui_contract.py` asserts `RunEvidence` in `ui/src/RunPanel.tsx` and `retainedRunAssumptions` in `ui/src/EvidenceIndex.tsx` call no `api.`/`fetch(`/`useEffect(`.

### Importing through a forwarding alias or another module's private helper

**What happens:** Production code imports `canonical` from `store` or calls `store._study`.
**Why it's wrong:** Blurs ownership; fails `test_production_code_never_imports_temporary_aliases` and the private-access allowlist tests.
**Do this instead:** Import from the owner (`from .contracts import canonical`); use public in-transaction reads `Store.study_row`, `Store.command_receipt`, `Store.model_association`.

### Adding a reverse or sideways edge between domain modules

**What happens:** `history` imports `result_bindings`, `approach` imports `configuration`, or a pure module imports `store`.
**Why it's wrong:** Recreates broken cycles; drags persistence into the attested closure.
**Do this instead:** Move the pure function to its owner (spec §7: "move pure functions to their owner instead of creating service objects"); keep pure modules dependency-light.

### Second representation of engine state

**What happens:** New app tables mirror model graphs or AiiDA lifecycle.
**Why it's wrong:** Parallel state drifts (ADR-0004 consequence 5); spec forbids a second editable graph or scheduler.
**Do this instead:** Store references, associations, receipts, and rebuildable projections only (e.g. `run_associations.process_uuid`, `execution_observation`).

### Hard-coded locations

**What happens:** A new script embeds a host path or a default folder.
**Why it's wrong:** Breaks the location rule and `deployment/tests/test_hygiene_guard.py`.
**Do this instead:** Resolve through `deployment/local_paths.py` (flag → `HYPRN_MVP_*` → installation config → neutral default below `HYPRN_MVP_DATA_ROOT` → refuse with `LocationUnset`).

## Error Handling

**Strategy:** Fail closed with a closed error vocabulary; never imply rollback or success on uncertainty.

**Patterns:**

- Raise `DomainError(code, status, current_revision=..., fields=..., outcome=...)` (`application/src/hyprn_mvp_app/contracts.py:83`); schema failures raise `ContractError` with field diagnostics (max `MAX_DIAGNOSTICS = 20`).
- Messages never contain stack traces, SQL, paths or secrets; remote modeling errors are re-validated and re-raised with local messages (`modeling.py:56-60`).
- Transport failure to the modeling service → `backend_unavailable` 503 with `outcome="unknown"`.
- Unknown record formats → `unsupported_record_version`; corrupt retained records → `corrupt_retained_record` / partial diagnostics; unavailable outputs are `null` with a reason, never zero.
- Dispatcher treats SQLite lock contention as transient with capped backoff (`dispatcher.py:38-49`) and publishes `unavailable` after `STALL_ITERATIONS`.

## Cross-Cutting Concerns

**Logging:** Minimal; dispatcher writes diagnostics to stderr (stdout is the bridge). Uvicorn runs with `--no-access-log`. Development evidence goes below `HYPRN_MVP_EVIDENCE_ROOT`, never into the repository.
**Validation:** Closed Pydantic models at the HTTP edge; JSON Schema 2020-12 (`contracts.validate`) for domain shapes; independent re-admission at launcher and worker.
**Authentication:** Local users with scrypt hashes, HttpOnly SameSite=strict session cookie, exact Origin, `X-CSRF-Token` on mutations (`application/src/hyprn_mvp_app/auth.py`); every read and write authorizes actor/study/resource via `Store.authorize`. Agent principals and delegations are planned (spec §4.6, ADR-0003).

---

*Architecture analysis: 2026-10-13*
