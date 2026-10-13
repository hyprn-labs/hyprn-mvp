---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
# External Integrations

**Analysis Date:** 2026-10-13

HYPRN MVP calls no third-party SaaS API at runtime. Every integration is with a component that HYPRN MVP itself deploys:

- the private modeling service (patched WhatsOpt)
- AiiDA on the trusted host runner
- the restricted OpenMDAO worker
- the Docker daemon

Outbound network access exists only in developer-run audit tools, which fetch from the official package registries.

## APIs & External Services

**Private modeling service (WhatsOpt behind the Modeling Backend Contract):**

- Purpose: holds the editable model graph (definitions, instances, ports, connections, source), immutable model and definition versions, model-local assumptions, the unit catalog, portable model record export and import, and static OpenMDAO code generation (`prepare-execution`).
- Contract: `contracts/modeling.openapi.yaml`, OpenAPI 3.1.0, `info.version 1.3.0`, served at `/modeling/1`. `x-hyprn-mvp-protocol-matrix` lists envelope 1, contract versions 1.2 and 1.3, schema versions 1–3, bundle versions 2–6, artifact version 2 and program version 1. It defines 16 operations, including:
  - `/capabilities`, `/models`, `/models/{model_id}`
  - `/models/{model_id}/preview`, `/edits`, `/commits`, `/validate`, `/export`
  - `/revisions` and `/revisions/{revision_id}`
  - `/configuration-compatibility`, `/prepare-execution`
  - `/preparations/{preparation_id}/files/{file_id}`
  - `/imports`, `/commands/{command_id}`, `/unit-catalog`
- Client: `ModelingClient` in `application/src/hyprn_mvp_app/modeling.py`, which uses `httpx`. Durable model commands go through `Coordinator` in the same module. Every call:
  - validates the request against the named schema before sending, and the response after
  - caps the streamed response size: 32 MiB in general, the catalog size for `/unit-catalog`
  - maps any transport failure to `DomainError("backend_unavailable", 503, outcome="unknown")`
  - never forwards backend messages or paths to clients
- Auth: the `scopedBearer` scheme. `ModelingClient.call` builds an HS256 JWT-shaped token signed with a shared 256-bit service key. Its claims are `actor_id`, `study_id`, `resource_ids`, `permissions` (`read` or `read`+`write`), `expires_at` (60 s), `request_id`, `method`, `path` and `body_sha256`. The service rejects identity headers and checks the resource-to-study binding itself.
  - The key file comes from `HYPRN_MVP_MODEL_KEY_FILE`. Locally it is `<data root>/modeling/credentials/model.key`, mounted read-only at `/run/model.key`.
  - The Rails secret is `<data root>/modeling/credentials/rails.key`, mounted only into the modeling container.
- Server side: the patched WhatsOpt Rails app has a single route, `match '/modeling/1/*contract_path', to: 'modeling_contract#dispatch_contract'`, written by `deployment/modeling_policy.rb`. The adapter source lives in `upstream/whatsopt-patches/040-modeling-contract.patch` through `090-quantity-definitions.patch`.
- Native generation: the service invokes a fixed Ruby helper (`NativeProgram`) per request, with bounds of 20 s CPU, 28 s wall, 1 GiB and four slots (`modeling/provenance.md`).
- Rules:
  - Reach modeling only through `ModelingClient`.
  - Never expose native payloads in `/api/1`.
  - Never add a second editable graph.
  - Contract changes go into `contracts/modeling.openapi.yaml` together with a new ordered patch in `upstream/whatsopt-patches/`.

**Upstream source acquisition (build time only, off-cloud):**

- WhatsOpt `WhatsOpt/WhatsOpt` at commit `597f5abf…`, archive SHA-256 `4937188d…`, and WhatsOpt-CLI at commit `6e47df2d…`, archive SHA-256 `8b95f091…`. Both are recorded in `deployment/pins.json` `verified_sources`.
- The archive is read from the verified cache `<HYPRN_MVP_UPSTREAM_CACHE>/<sha256>/WhatsOpt.tar.gz`. The single resolver `upstream_archive()` in `deployment/modeling_runtime.py` fails closed on any mismatch. Image builds run with `--network=none --pull=false`.

**Package registries (developer audit tools only):**

- PyPI (`pypi.org/pypi/<name>/<version>/json`, `files.pythonhosted.org`): `application/audit_dependencies.py` inspects downloaded wheels as ZIP data and compares them with registry metadata. Records go to `application/dependency-pins.json`.
- npm registry: `ui/audit_dependencies.py` verifies the locked tarballs (SHA-512 integrity, licence, repository) before `npm ci --ignore-scripts`. Records go to `ui/dependency-audit.json`.
- Use these tools before any new or changed dependency. Record the official source, exact version, hash and licence, and admit only permissive licences (`docs/legal/licensing.md` §5).

**Agent providers (specified, not implemented):**

- Local: the Codex or Claude Code desktop app over MCP, through the loopback `/mcp` endpoint (server name `hyprn-mvp`) and a stdio relay (`editions/local/README.md`, `docs/specs/agents.md` §4.1).
- Cloud: Claude Managed Agents or the OpenAI Agents API through a custom-tool bridge, with remote MCP as a fallback.
- Kill switch: `HYPRN_MVP_AGENT_ENABLED`.
- Status: none of this exists in `application/src` or `editions/` yet (no MCP or agent code). AGENT-01 in `docs/specs/requirements.md` covers it.

## Data Storage

**Databases:**

- **Application store (SQLite):**
  - Connection: `HYPRN_MVP_APP_STORE`. Locally the file is `<data root>/application/application/application.sqlite`, mounted at `/store` in the container.
  - Client: stdlib `sqlite3` in `application/src/hyprn_mvp_app/store.py` (`Store.connection(write=...)`, explicit transactions, `foreign_keys=ON`, 15 s busy timeout).
  - Tables: `users`, `sessions`, `studies`, `memberships`, `model_associations`, `evidence`, `evidence_families`, `configuration_families`, `configurations`, `receipts`, `run_associations`, `outbox`, `execution_observation`, `computational_record_requests`, `approach_drafts`, `approach_versions`, `study_archive`. They are created with `CREATE TABLE IF NOT EXISTS` in `store.py`.
  - Single writer: the application container. The host dispatcher writes through `docker exec` into the same container process space (`application/src/hyprn_mvp_app/dispatcher.py`).
- **Modeling store (SQLite, owned by WhatsOpt):** `/store/model.sqlite3` (primary) and `/store/scratch.sqlite3` (scratch) inside the modeling container. The bind source is `${HYPRN_MVP_MODELING_ROOT}/modeling`. The configuration is written into `config/database.yml` by `deployment/modeling_policy.rb`. Only the modeling service touches it.
- **Execution store (AiiDA `core.sqlite_dos` profile):**
  - Location: `<data root>/execution` (`launcher.configured_root()` in `integration/src/hyprn_mvp_integration/launcher.py`). The profile is initialized without a broker or daemon (`broker_backend=None`) by `deployment/native_environment.py`.
  - Contents: process nodes, retained bundles, results, artifacts and document original bytes (`integration/src/hyprn_mvp_integration/documents.py`, namespace `hyprn_mvp_documents`).
  - Single writer: the trusted host executor (`deployment/dispatch_runtime.py`).
  - Scoped tests use the same backend in `hyprn-mvp-test-<uuid>` folders and refuse any other backend (`deployment/tests/scoped_fixture.py`).
- **Planned:** PostgreSQL with row-level security for multi-organisation operation (`docs/specs/workspaces-identity-onboarding.md`, open item O7). It is not in code.

**File Storage:**

- Local filesystem only, under `HYPRN_MVP_DATA_ROOT`. Never inside the repository or a cloud-synced folder; managers refuse synced paths (`deployment/manage.py` `independent_root()`).
- Computational record exports are AiiDA `ArchiveFormatSqlZip` archives produced by `integration/src/hyprn_mvp_integration/computational_export.py` and downloaded through `GET /api/1/studies/{study_id}/computational-records/{request_id}/download`.
- Run artifacts are served through `GET /api/1/studies/{study_id}/runs/{run_id}/artifacts/{artifact_id}`.
- Backups: `deployment/tools/backup_immutable.py` copies the stopped stores with the SQLite backup API from `mode=ro&immutable=1` sources. It never copies credentials or AiiDA profile bytes.

**Caching:**

- None. Modeling `config.cache_store = :null_store`. API responses carry `Cache-Control: no-store`.

## Authentication & Identity

**Auth Provider:**

- Custom local authentication in `application/src/hyprn_mvp_app/auth.py`:
  - Single owner user (`owner`) with a scrypt password hash (`scrypt$<salt>$<hex>`, `n=2**17`). Passwords are 16–1024 characters, and there is no default password.
  - First setup writes a random password once to `<data root>/application/credentials/owner.password` (mode 0600, `deployment/application_runtime.py`). It is never printed or logged.
  - Recovery is a local command only: `python -m hyprn_mvp_app.auth recover --store <store>`, run inside the container. It revokes all sessions. No HTTP route exists for it.
  - Login lockout: five failures lock the account for 60 s and return `rate_limited` 429. The comparison is constant-time against a dummy hash when the user is unknown.
  - Sessions are opaque `secrets.token_urlsafe(32)` tokens. Only their SHA-256 is stored, together with the CSRF hash. They expire after 8 hours.
  - Cookie `hyprn_mvp_session` is HttpOnly, `SameSite=strict`, Secure over HTTPS and scoped to `path=/api/1` (`api.py` `login`).
  - Every mutation needs the exact `Origin` and an `X-CSRF-Token` header. Every request's `netloc` must equal the configured origin (the `boundaries` middleware in `application/src/hyprn_mvp_app/api.py`).
- Authorization: study-scoped membership checks in `store.py` and the domain modules. Every read, export and receipt replay authorizes the actor, the study and the resource.
- Service-to-service: the HS256 scoped bearer token for the modeling service (see above). The worker gets no credentials.
- Planned: Keycloak 26+ (Organizations, enterprise SSO brokering, Keycloakify-themed login) and OpenFGA later (`docs/specs/workspaces-identity-onboarding.md`). Neither is in code.

## Monitoring & Observability

**Error Tracking:**

- None. `opentelemetry-api` is installed only as a transitive dependency, with no exporter (`application/provenance.md`).

**Logs:**

- Uvicorn runs with `--no-access-log`. Unexpected exceptions become a typed `internal_error` 500 envelope with `outcome="unknown"` (`api.py` `unexpected_error`).
- The dispatcher and readiness modules print store-contention and stall messages to stderr (`application/src/hyprn_mvp_app/dispatcher.py`, `readiness.py`).
- The modeling Rails logger writes to stdout (`deployment/modeling_policy.rb`).
- Readiness is published by `ObservationPublisher` (`application/src/hyprn_mvp_app/readiness.py`) into the `execution_observation` table and surfaced through `GET /api/1/studies/{study_id}/execution-readiness`.
- Test and browser evidence goes under `HYPRN_MVP_EVIDENCE_ROOT` (default `<data root>/evidence`), never in the repository.

## CI/CD & Deployment

**Hosting:**

- Local edition containers, all managed with the Docker CLI from Python:
  - `hyprn-mvp-application`:
    - Managed by `deployment/application_runtime.py`.
    - Container settings: user `10002:10002`, read-only root, `--cap-drop=ALL`, `no-new-privileges`, 512 MiB, 1 CPU, 64 pids, tmpfs `/tmp`.
    - Ports and networks: published only on `127.0.0.1:<HYPRN_MVP_PORT>`, on the `hyprn-mvp-public` network and connected to `hyprn-mvp-private`.
  - `hyprn-mvp-modeling`: defined in `deployment/modeling-compose.yaml` and managed by `deployment/modeling_runtime.py`. It runs as user `10001:10001` with a read-only root, 768 MiB, 1 CPU and 128 pids, only on the internal `hyprn-mvp-private` network.
  - Restricted worker:
    - Launched per run by `integration/src/hyprn_mvp_integration/launcher.py` with `docker run --network none --read-only --cap-drop ALL --security-opt no-new-privileges`.
    - Limits: 256 MiB, 0.5 CPU, 32 pids, 20 s wall time, 64 KiB output, user `65534:65534`.
    - Prerequisite: the containment attestation (`containment.json`) from `deployment/manage.py verify-isolation`.
  - Host executor: `deployment/dispatch_runtime.py`. It owns the AiiDA profile and the launch authority, and it talks to the application only through a framed stdio bridge (`docker exec -i hyprn-mvp-application python -B -m hyprn_mvp_app.dispatcher`, 64 MiB max message).
- Releases: `deployment/release_binding.py` verifies retained release manifests below `<data root>/releases` and binds manager processes to the exact release tree.
- Cloud: not in this repository. The separate platform repository holds infrastructure.

**CI Pipeline:**

- None detected (no `.github/`, no CI configuration). Run checks locally with `HYPRN_MVP_DATA_ROOT=<data root> python3 -B deployment/checks.py --group <group>`, or `--group qualification` for every must-pass group.

## Environment Configuration

**Required env vars (application runtime):**

- `HYPRN_MVP_APP_STORE`
- `HYPRN_MVP_ORIGIN`
- `HYPRN_MVP_MODEL_URL`
- `HYPRN_MVP_MODEL_KEY_FILE`

**Required env vars (development / managers):**

- `HYPRN_MVP_DATA_ROOT` (always)
- `HYPRN_MVP_PORT` (application manager)
- `HYPRN_MVP_ENGINE_IMAGE` and `HYPRN_MVP_MODELING_SOURCE_IMAGE` (image builds, which must match `deployment/pins.json`)
- `HYPRN_MVP_MODELING_IMAGE` and `HYPRN_MVP_MODELING_ROOT` (compose recipe)
- `HYPRN_MVP_UI_BASE_URL` and `HYPRN_MVP_UI_PASSWORD_FILE` (opt-in served browser groups)
- `HYPRN_MVP_NATIVE_PYTHON` (isolated Playwright config)
- The full list and defaults are in `deployment/local_paths.py`.

**Secrets location:**

- Credentials are files below the data root, never environment values:
  - `<data root>/modeling/credentials/model.key` (shared service key, read-only mount into both the application and modeling containers)
  - `<data root>/modeling/credentials/rails.key` (modeling container only)
  - `<data root>/application/credentials/owner.password` (one-time handover, mode 0600)
- `.gitignore` excludes `credentials/`, `.env` and `.env.*`. The repository has no `.env` file.
- The worker containment check asserts that no `AWS_*`, `OPENAI_*` or `AIIDA_*` variables and no Docker socket reach the worker (`launcher.py`).

## Webhooks & Callbacks

**Incoming:**

- None. The only listener is the public HYPRN MVP API at `/api/1` (`contracts/hyprn-mvp.openapi.yaml`, OpenAPI 3.1.0, version 1.0.0, 53 operations) plus static `/ui`.
- Long-running work (runs, computational record exports) returns 202 with a receipt or operation resource that clients poll (`/api/1/studies/{study_id}/commands/{command_id}`, `/runs/{run_id}`, `/computational-records/{request_id}`).

**Outgoing:**

- None to external parties.
- Internal outbound calls:
  - application → modeling service over HTTP on the private network
  - host executor → Docker daemon over the local socket (`HYPRN_MVP_DOCKER_SOCKET`)
  - `deployment/application_runtime.py` → its own loopback health probe (`http://127.0.0.1:<port>/api/1/studies`, with the proxy handler disabled)

---

*Integration audit: 2026-10-13*
