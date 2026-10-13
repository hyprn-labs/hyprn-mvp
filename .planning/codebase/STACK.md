---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
# Technology Stack

**Analysis Date:** 2026-10-13

## Languages

**Primary:**

- Python 3.12 (`requires-python = ">=3.12"`), used for:
  - the application `hyprn_mvp_app` (`application/src/hyprn_mvp_app/`, about 6,500 lines)
  - execution integration `hyprn_mvp_integration` (`integration/src/hyprn_mvp_integration/`, about 3,250 lines)
  - the deployment managers, the path policy and the test-group runner (`deployment/*.py`)
  - the modeling-service tooling (`modeling/*.py`)
  - the UI and design-system tooling (`ui/*.py`)
- TypeScript 5.9.3 (strict) with React 19 JSX, used for the browser UI (`ui/src/*.tsx`, `ui/src/design/`) and for the Playwright specs (`ui/tests/*.spec.ts`)

**Secondary:**

- Ruby 3.3.5 on Rails 8.1.3.1, used by the private modeling service (patched WhatsOpt) through `upstream/whatsopt-patches/*.patch` and the AGPL-3.0-only deployment adaptation in `deployment/modeling_policy.rb`. HYPRN MVP's own Ruby is limited to those patches and that policy file.
- JavaScript (ESM): `ui/design_smoke.mjs` (design smoke check) and `ui/tests/criterion-record.test.cjs`
- JSON Schema (Draft 2020-12), used for `contracts/schemas/model.schema.json` and `contracts/schemas/execution.schema.json`
- OpenAPI 3.1.0, used for `contracts/hyprn-mvp.openapi.yaml` (public API) and `contracts/modeling.openapi.yaml` (Modeling Backend Contract). Both files are JSON-compatible YAML.
- ERB templates (WhatsOpt-native, inside the modeling image) generate OpenMDAO Python source statically. Six templates are allowed by `deployment/modeling_policy.rb`.

## Runtime

**Environment:**

- **Application container:** `python:3.12.11-slim-bookworm`. The image ID is pinned as `BASE` in `deployment/application_runtime.py`, and the build is in `deployment/application.Dockerfile`. It runs `uvicorn hyprn_mvp_app.api:from_environment --factory` on port 8000 as user `10002:10002`.
- **Restricted worker:** CPython 3.12.15 with OpenMDAO 3.45.1. It is derived from the reviewed numerical engine image (`HYPRN_MVP_ENGINE_IMAGE`, pinned as `base_image` and `images.worker` in `deployment/pins.json`) by `deployment/worker.Dockerfile`, which installs no packages and runs as `65534:65534`.
- **Trusted host runner / executor:** CPython 3.12.11 with AiiDA 2.9.3. Its virtual environment is copied from reviewed installed distributions by `deployment/native_environment.py` and lives at `<HYPRN_MVP_DATA_ROOT>/dev/python-native/venv`. Its 89-distribution closure is recorded in `integration/provenance.md`.
- **Contract environment:** `<HYPRN_MVP_DATA_ROOT>/dev/python-contract/venv`. Use it for data-only contract generation and the application tests (`HYPRN_MVP_CONTRACT_PYTHON`).
- **Modeling service:** Ruby 3.3.5 base image `ruby@sha256:bceec758…` (`deployment/pins.json` `ruby_base_image`, `RUBY_IMAGE` in `deployment/modeling_runtime.py`) plus the Node binary as a native gem boot dependency. The service runs Rails in `RAILS_ENV=test` with SQLite as user `10001:10001`, built by `deployment/modeling.Dockerfile`.
- **Native authoring build (disposable):** Ruby image + Node 22 image + Bundler 2.7.1 + Yarn 4.14.1 via corepack, defined in `deployment/native.Dockerfile`.
- **Browser:** evergreen Chromium/Chrome. Playwright runs the `chromium` project with `channel: 'chrome'` (`ui/playwright.config.ts`), overridable through `HYPRN_MVP_CHROMIUM`.
- **Node.js** builds the UI. `package.json` declares no `engines` field and the repository has no `.nvmrc`. The modeling native build pins Node 22 (`deployment/pins.json` `runtime.node`).
- **Docker** is required for all native groups. The measured engine (Docker Engine 29.8.2) is recorded in `deployment/pins.json` `runtime`.

**Supported hosts:** macOS and Linux, with Windows through WSL2 (`README.md`, `editions/local/README.md`). Dependency pins target CPython 3.12 on macOS arm64 and Linux arm64 (`application/dependency-pins.json` `targets`).

**Package Manager:**

- Python: pip, used offline and hash-enforced (`pip install --no-index --find-links=/wheels --require-hashes -r requirements.lock`, see `deployment/application.Dockerfile`). No uv or Poetry is in the tree today. Phase 2 plans uv 0.12.24 and CPython 3.12.15 everywhere (`.planning/STATE.md`, `.planning/PROJECT.md`), but a root `pyproject.toml` or `uv.lock` does not exist yet.
- Node: npm with lockfile v3. Resolve with `npm install --package-lock-only --ignore-scripts` and install with `npm ci --ignore-scripts`. Lifecycle scripts never run (`ui/provenance.md`).
- Ruby: Bundler 2.7.1 with `BUNDLE_FROZEN=true`, used only inside the modeling images.
- Lockfiles present:
  - `application/requirements.lock`: 28 packages, every line carries `--hash=sha256:`
  - `integration/worker-requirements.lock`: 20 packages, the numerical worker closure
  - `integration/test-requirements.lock`: 5 packages (pytest 9.0.2 and its dependencies)
  - `integration/document-parser.lock.json`: the pypdf wheel adoption record
  - `ui/package-lock.json`: 52 `node_modules/` entries
  - `deployment/pins.json`: image digests, upstream commits and archive hashes, plus the verified artifacts of `wop`, `openmdao` and `aiida-core`

## Frameworks

**Core:**

- **FastAPI 0.143.0** (MIT): the public HTTP API at `/api/1`. Create the app with `create_app(store, auth, model)` in `application/src/hyprn_mvp_app/api.py`. Docs, ReDoc and the OpenAPI routes are disabled at runtime (`docs_url=None, redoc_url=None, openapi_url=None`).
- **Starlette 1.7.0** (BSD-3-Clause): `StaticFiles` subclass `WorkspaceFiles` serves the compiled UI at `/ui` with a strict CSP (`application/src/hyprn_mvp_app/ui.py`).
- **Pydantic 2.14.0** (MIT): request models in `api.py`. Closed domain schemas are validated separately with jsonschema.
- **Uvicorn 0.54.0** (BSD-3-Clause): the ASGI server, started with `--no-access-log`.
- **React 19.3.0 / React DOM 19.3.0** (MIT): the UI. It is mounted from `ui/src/main.tsx` and builds screens only from `ui/src/design` components.
- **OpenMDAO 3.45.1** (Apache-2.0): the numerical engine, run only inside the restricted worker (`integration/src/hyprn_mvp_integration/worker.py`). It also supplies the unit catalog (`modeling/generate_unit_catalog.py`, `openmdao.utils.units.unit_conversion`).
- **AiiDA core 2.9.3** (MIT): process lifecycle, provenance graph, artifacts and archives on the trusted host runner (`integration/src/hyprn_mvp_integration/calculation.py`, `computational_export.py`). The plugin entry points are registered in `integration/pyproject.toml`:
  - `aiida.calculations` → `hyprn_mvp.scalar = hyprn_mvp_integration.calculation:ScalarCalculation`
  - `aiida.parsers` → `hyprn_mvp.scalar = hyprn_mvp_integration.calculation:ScalarParser`
- **WhatsOpt** (AGPL-3.0, Rails) at upstream commit `597f5abf18d4a6335c2f3b9174ab16acdf1de4bd`: the private modeling service, reduced and patched (`modeling/provenance.md`).

**Testing:**

- **pytest 9.1.1** for application tests (`application/pyproject.toml` `[project.optional-dependencies] test`, `testpaths = ["tests"]`)
- **pytest 9.0.2** for integration tests (`integration/test-requirements.lock`). Markers are `quick`, `integration` and `isolation` (`integration/pyproject.toml`), and `addopts = "-p no:cacheprovider"`.
- **unittest (stdlib)** in parts of `deployment/tests/` and in the runner `deployment/checks.py`
- **Playwright 1.62.1** (Apache-2.0) for browser specs. The served-installation config is `ui/playwright.config.ts` and the scoped-fixture config is `ui/playwright.isolated.config.ts`.
- The test-group runner is `deployment/checks.py` (stdlib only, fail-closed, `--list`, `--group <name>`, `--group qualification`). `AGENTS.md` still names `deployment/phase02_checks.py`, but the file in the tree is `deployment/checks.py`.

**Build/Dev:**

- **Vite 8.3.4** (MIT): `ui/vite.config.ts` sets `base: '/ui/'`, turns sourcemaps off and reads the output folder from `HYPRN_MVP_UI_OUT` (default `dist`). Rolldown, oxc and Lightning CSS (MPL-2.0, build only) come in transitively.
- **TypeScript 5.9.3**: `ui/tsconfig.json` sets `target ES2022`, `moduleResolution Bundler`, `jsx react-jsx`, `strict`, `noEmit`. The build script is `tsc --noEmit && vite build`.
- **setuptools** (`>=61`) is the build backend for `integration/pyproject.toml`.
- **Docker / Docker Compose**: every image build uses `docker build --network=none --pull=false`. The modeling deployment recipe is `deployment/modeling-compose.yaml`.
- **Code generators in the repository:**
  - `application/generate_contract.py` regenerates `contracts/hyprn-mvp.openapi.yaml` from the live routes and domain schemas
  - `ui/generate_types.py` generates TypeScript declarations from the public schema into `ui/src/contract.ts`
  - `ui/design_tokens.py` generates `ui/src/design/tokens.css` from `design-system/tokens.json` (`--check` verifies it). Never hand-edit the output.
  - `modeling/generate_unit_catalog.py` builds the unit catalog that is embedded in patch `080`
- **Design-system checks:** `ui/check_design_system.py`, `ui/test_design_tooling.py`, `ui/design_smoke.mjs`. The UI contract checker is `ui/check_ui_contract.py` and its control map is `ui/control-map.json`.

## Key Dependencies

**Critical (application, `application/requirements.lock`):**

- `fastapi==0.143.0`, `starlette==1.7.0`, `pydantic==2.14.0` / `pydantic_core==2.50.0`, `uvicorn==0.54.0`: HTTP surface
- `httpx==0.28.1`: the only outbound HTTP client, used by `ModelingClient` in `application/src/hyprn_mvp_app/modeling.py` with `trust_env=False`, `follow_redirects=False` and a 20 s timeout
- `jsonschema==4.26.0` (`Draft202012Validator`, `FormatChecker`): closed-schema validation in `application/src/hyprn_mvp_app/contracts.py`
- `rfc8785==0.1.4`: RFC 8785 canonical JSON for every digest and identity (`contracts.canonical`, `contracts.digest`)
- Transitive packages that need attention: `certifi==2026.7.22` (MPL-2.0, unmodified) and `opentelemetry-api==1.45.1` (present only as an upstream dependency; no exporter is configured)

**Critical (worker, `integration/worker-requirements.lock`):**

- `openmdao==3.45.1`, `numpy==2.5.3`, `scipy==1.18.1`, `networkx==3.7`, `openmdao_extensions==1.6.3`
- `wop==2.6.1` (WhatsOpt CLI, Apache-2.0) and `xdsmjs==2.1.0` are present in the numerical image lock. HYPRN MVP clients never use `wop` (`docs/legal/licensing.md`).

**Critical (host runner):**

- `aiida-core==2.9.3`. The wheel hash is verified first, then every copied file is checked against its `RECORD` SHA-256 (`deployment/native_environment.py`). `.planning/STATE.md` records paramiko 3.x arriving transitively; only the local transport is used.

**Adopted, not yet installed:**

- `pypdf==6.20.0` (BSD-3-Clause), no extras and no dependency resolution. It is the planned document text extraction parser. See `integration/document-parser.lock.json` and `integration/document-parser-provenance.md`.

**Infrastructure:**

- Stdlib `sqlite3` is the application store (`application/src/hyprn_mvp_app/store.py`). It connects with `timeout=15`, `isolation_level=None` (explicit transactions) and `PRAGMA foreign_keys=ON`.
- Stdlib `hashlib.scrypt` hashes passwords (`application/src/hyprn_mvp_app/auth.py`: `n=2**17, r=8, p=1`).
- Stdlib `hmac`/`hashlib` sign the HS256 JWT-shaped service tokens (`ModelingClient.call`).
- Stdlib `subprocess` drives the Docker CLI (`integration/src/hyprn_mvp_integration/launcher.py`, `deployment/*_runtime.py`). No Docker SDK is used.

**Planned (specs only, not in code):**

- OpenTURNS (uncertainty, `docs/specs/requirements.md` UQ-01)
- Keycloak 26+ (identity, `docs/specs/workspaces-identity-onboarding.md`)
- PostgreSQL with row-level security (cloud application store)
- OpenFGA (later authorization)
- Tiptap, Yjs, React Flow, XDSMjs, dockview, assistant-ui (`docs/legal/licensing.md` §5)
- the MCP tool server and agent bridge (`docs/agents/tooling-spec.md`, `docs/specs/agents.md`)

## Configuration

**Environment:**

- Every location resolves in this order: CLI flag → `HYPRN_MVP_*` environment variable → installation configuration (not present yet) → neutral default below `HYPRN_MVP_DATA_ROOT` → refusal with `LocationUnset`. The single policy module is `deployment/local_paths.py` (stdlib only, no import side effects). Never hard-code a path. Add new locations there.
- Application runtime variables are read in `application/src/hyprn_mvp_app/api.py` `from_environment()`:
  - `HYPRN_MVP_APP_STORE`: path of the application SQLite store (in the container: `/store/application.sqlite`)
  - `HYPRN_MVP_ORIGIN`: exact public origin. Only `https://…` or `http://127.0.0.1:<port>` is accepted.
  - `HYPRN_MVP_MODEL_URL`: base URL of the private modeling service (`http://hyprn-mvp-modeling:3000/modeling/1` locally)
  - `HYPRN_MVP_MODEL_KEY_FILE`: file holding the modeling-service credential (in the container: `/run/model.key`). A key shorter than 32 bytes is refused.
- Development and deployment variables (`deployment/local_paths.py`):
  - `HYPRN_MVP_DATA_ROOT` is required by every default. It must be absolute, outside the repository and outside synced folders. `deployment/manage.py` refuses cloud-synced roots.
  - Overrides for the development interpreters, dependency inventory, fixtures and upstream cache: `HYPRN_MVP_NATIVE_PYTHON`, `HYPRN_MVP_NATIVE_INVENTORY`, `HYPRN_MVP_CONTRACT_PYTHON`, `HYPRN_MVP_TEST_FIXTURES_ROOT`, `HYPRN_MVP_UPSTREAM_CACHE`, `HYPRN_MVP_EVIDENCE_ROOT`
  - `HYPRN_MVP_SCRATCH_ROOT`, the scoped test-folder parent (default: the OS temporary folder, resolved)
  - Test-safety fences: `HYPRN_MVP_LIVE_ROOTS`, `HYPRN_MVP_LIVE_PORTS`, `HYPRN_MVP_LIVE_NAMES`
  - `HYPRN_MVP_PORT`, the development application port. It has no default.
  - `HYPRN_MVP_DOCKER_SOCKET` (default `DOCKER_HOST` or the active Docker context) and `HYPRN_MVP_CHROMIUM`
  - Base image IDs: `HYPRN_MVP_ENGINE_IMAGE` and `HYPRN_MVP_MODELING_SOURCE_IMAGE` (`sha256:<64 hex>`). Each must equal its pin in `deployment/pins.json`.
  - UI variables: `HYPRN_MVP_UI_OUT`, `HYPRN_MVP_UI_BASE_URL`, `HYPRN_MVP_UI_PASSWORD_FILE`, `HYPRN_MVP_UI_EVIDENCE_ROOT`, `HYPRN_MVP_FOUNDRY_SNAPSHOTS`
  - Scoped-fixture variables: `HYPRN_MVP_TEST_SCOPE_ROOT`, `HYPRN_MVP_TEST_SCOPE_PROFILE`, `HYPRN_MVP_TEST_SCOPE_URL`
- Modeling compose variables (`deployment/modeling-compose.yaml`): `HYPRN_MVP_MODELING_IMAGE` (required, from `identity.json`) and `HYPRN_MVP_MODELING_ROOT`
- Worker image environment (`deployment/worker.Dockerfile`): `OPENMDAO_REPORTS=0`, `OPENBLAS_NUM_THREADS=1`, `PYTHONDONTWRITEBYTECODE=1`
- Store layout below the data root: `application/`, `modeling/`, `execution/`, `releases/`, `fixtures/`, `cache/upstream/whatsopt`, `evidence/`, `dev/python-native/`, `dev/python-contract/`. It is documented in the docstring of `deployment/local_paths.py`.
- `.gitignore` excludes `*.sqlite3`, `*.log`, `*.local.*`, `.env`, `.env.*`, `credentials/`, `ui/node_modules/` and `ui/dist/`. The repository has no `.env` file.

**Build:**

- `deployment/application.Dockerfile`: offline, hash-enforced wheel install. It copies `application/`, `contracts/` and the built UI (`ui-dist` → `/app/ui`).
- `deployment/worker.Dockerfile`: adds only `worker.py`, `results.py` and `__init__.py` to the engine image and labels them with their SHA-256.
- `deployment/modeling.Dockerfile`: replays patches 010–040 and applies the `native`, `discovery`, `assumptions` and `units` patches with `--fuzz=0`. It then runs `modeling_policy.rb --install` and copies the result onto the pinned Ruby base without a network fetch.
- `deployment/native.Dockerfile`: the disposable native authoring build from verified upstream source.
- `deployment/pins.json`: every image digest, the upstream WhatsOpt and WhatsOpt-CLI commits and archive hashes, verified artifacts, the measured runtime, and `worker_lock_sha256`/`native_patch_sha256`. Its `status` is `"measured-experiment-adoption-pending"`.
- `ui/vite.config.ts`, `ui/tsconfig.json`, `ui/package.json`
- `application/pyproject.toml`, `integration/pyproject.toml`. Each component has its own project file; the repository has no root workspace.

## Platform Requirements

**Development:**

- Python 3.12 on the host for `deployment/checks.py` and the managers (stdlib only)
- Docker Engine with a reachable socket for the native, modeling, worker and application groups
- Node with npm for the UI build (`npm --prefix ui ci && npm --prefix ui run build`)
- Playwright with Chrome/Chromium for the browser groups
- `HYPRN_MVP_DATA_ROOT` set to a local, non-synced, owner-only (0700) directory
- The development interpreters under `<data root>/dev/python-native/venv` and `<data root>/dev/python-contract/venv`, plus the verified upstream WhatsOpt archive in `<data root>/cache/upstream/whatsopt/<sha256>/WhatsOpt.tar.gz`

**Production:**

- The local edition is the first target: one machine, the `./hyprn-mvp` CLI (`hyprn_mvp_local`, specified in `editions/local/README.md`; no code is in the tree yet). Its layout:
  - application container bound to `127.0.0.1:<HYPRN_MVP_PORT>`
  - modeling container on the internal network `hyprn-mvp-private`
  - host executor (`deployment/dispatch_runtime.py`) bridged to the application through `docker exec -i … python -m hyprn_mvp_app.dispatcher`
  - ephemeral `--network none` workers
- The cloud edition (`editions/cloud/`) does not exist yet. Its infrastructure belongs in the separate platform repository. The cloud target is PostgreSQL, Keycloak and an edge proxy (`docs/specs/workspaces-identity-onboarding.md`).

---

*Stack analysis: 2026-10-13*
