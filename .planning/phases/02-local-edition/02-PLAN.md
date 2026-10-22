---
phase: 02-local-edition
plan: 01
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - hyprn-mvp
  - .python-version
  - pyproject.toml
  - uv.lock
  - THIRD_PARTY_NOTICES.md
  - README.md
  - deployment/
  - integration/src/hyprn_mvp_integration/installation.py
  - integration/src/hyprn_mvp_integration/launcher.py
  - modeling/rehearsal.py
  - editions/local/
  - docs/operations/
  - docs/legal/licensing.md
  - contracts/schemas/
  - contracts/tests/
  - contracts/README.md
  - contracts/documents.md
  - application/src/hyprn_mvp_app/contracts.py
  - application/src/hyprn_mvp_app/units.py
  - application/src/hyprn_mvp_app/execution_bundle.py
  - application/src/hyprn_mvp_app/modeling.py
  - application/generate_execution_schema.py
  - application/generate_contract.py
  - application/tests/test_module_boundaries.py
  - application/tests/
  - integration/tests/
  - modeling/tests/
autonomous: false
requirements: [OPS-04, IAM-01, OPS-02, ADOPT-01, ADOPT-03, SEC-01]
user_setup:
  - service: docker
    why: "Every HYPRN MVP component runs in containers"
    dashboard_config:
      - task: "Install Docker Desktop (macOS, Windows with WSL2) or Docker Engine (Linux) and give the engine at least 6 GiB of memory"
        location: "Docker documentation for the host operating system"
must_haves:
  truths:
    - "A fresh clone on a clean macOS host and a clean Linux host completes ./hyprn-mvp setup, start and test, and the smoke test reproduces the acyclic Sellar known answer"
    - "Every location resolves flag, then HYPRN_MVP_* variable, then installation configuration, then the per-OS default from one path-policy module, then a question to the user"
    - "Synced, symlinked, foreign and Windows-mounted folders are refused as data roots and checkouts"
    - "uv, CPython, Python packages, gems, npm packages, base images and the WhatsOpt archive are verified against pins before use; non-acquisition builds run without network"
    - "Setup snapshots the committed checkout and attests the worker; start refuses a changed checkout or a stale attestation and never rebuilds"
    - "No secret appears in configuration, output, process arguments or logs"
    - "The dynamic-loading allowlist of the attested modules is keyed by (path, enclosing function, callee, count): edits elsewhere in an attested file leave it unchanged, while any new, removed or moved dynamic call still fails the boundary test"
    - "The attested launch path validates only against the generated contracts/schemas/execution.schema.json, which equals the transitive closure of the definitions the attested modules name; Documents-only definitions and the x-hyprn-mvp-documents-contract registry live in the non-attested contracts/schemas/documents.schema.json; no two schema files are kept in sync by hand"
    - "Records and prepared artifacts captured before the schema split, including the schema identities they record, stay admissible and are read without substituting current content; the golden identity corpus, every definition body and the regenerated public contract are byte-unchanged"
  artifacts:
    - path: hyprn-mvp
      provides: "POSIX sh entry point: pinned uv bootstrap, then the local edition CLI"
    - path: deployment/config.schema.json
      provides: "Closed installation configuration schema, version 1"
    - path: integration/src/hyprn_mvp_integration/installation.py
      provides: "Stdlib-only installation configuration loader (in the attested set)"
    - path: editions/local/src/hyprn_mvp_local/paths.py
      provides: "The single path-policy module with per-OS defaults and refusals"
    - path: deployment/release.py
      provides: "Checkout-mode release snapshot, manifest and binding"
    - path: deployment/locks/
      provides: "tools.json, upstream.json, whatsopt-gems.json, native-host lock"
    - path: docs/operations/
      provides: "Install, CLI, troubleshooting, uninstall, development, dependency audit"
    - path: contracts/schemas/documents.schema.json
      provides: "Documents-only definitions and the x-hyprn-mvp-documents-contract registry; in the application image inventory, in no execution or modeling inventory (not attested)"
    - path: contracts/schemas/execution.schema.json
      provides: "Generated: the transitive $ref closure of the reviewed launch-path definition roots; the only contract schema the attested launch path reads (attested)"
    - path: application/generate_execution_schema.py
      provides: "Execution-schema generator with --check (not on the launch path)"
  key_links:
    - from: hyprn-mvp
      to: deployment/locks/tools.json
      via: "uv download verified by per-platform SHA-256 before execution"
    - from: editions/local/src/hyprn_mvp_local/setup.py
      to: deployment/release.py
      via: "snapshot, build, attest, activate"
    - from: editions/local/src/hyprn_mvp_local/start.py
      to: "integration/src/hyprn_mvp_integration/launcher.py attestation"
      via: "start refuses unless the attestation matches the active snapshot's execution source set"
    - from: application/src/hyprn_mvp_app/contracts.py
      to: contracts/schemas/execution.schema.json
      via: "validator(name) resolves every launch-path root from the attested generated file only; every other definition from the authored files"
    - from: integration/src/hyprn_mvp_integration/launcher.py
      to: contracts/schemas/execution.schema.json
      via: "execution source inventory (the list approved at checkpoint 2.8a; documents.schema.json never in it)"
---

# Phase 2: Local edition — plan

<objective>
Any engineer installs and runs HYPRN MVP on macOS or Linux (Windows through WSL2) with `git clone`, `./hyprn-mvp setup` and `./hyprn-mvp start`, with only git and a Docker engine on the host. Everything else is acquired from pins and verified; every location is resolved without hard-coded paths; setup snapshots the committed checkout, builds from it and attests the worker; start never rebuilds.

Purpose: the product becomes installable and testable on a clean machine, which the agent tools (Phase 3), documents (Phase 4) and the release (Phase 5) build on.
Output: the `./hyprn-mvp` entry point and `hyprn_mvp_local` CLI, the installation configuration and path policy, reproducible images, the checkout-mode release (with the two factorization changes its single re-attestation carries: a function-keyed dynamic-loading allowlist and the contract schemas split by consumer), OS adapters, the smoke and clean-room tests, and `docs/operations/`.
</objective>

## How this plan is executed

**Pending-work amendment (2026-10-14):** read
[DELIVERY-PLAN.md](../../DELIVERY-PLAN.md) before dispatch. Its A–D waves, named
slices and explicit dependency replacements govern pending work; unchanged task
actions, invariants and acceptance remain binding. The waves below retain the
original phase structure. Completed checkpoints are unchanged; an original task
closes only after all its slices pass. Broader portability/docs complete in E.

- One numbered task per fresh executor context. Each task stages explicit paths, ends with atomic commits and a checkpoint `phases/02-local-edition/checkpoints/<task>.md` in the planning directory (commits; exact commands with counts and every failure; lock, image and attestation identities; scratch scopes released; remaining risks), and is verified by the orchestrating session before a dependent task starts.
- Tests use scratch installations only: configuration and data root inside `<scratch root>/hyprn-mvp-test-<uuid>`, a random free port, a scratch credential store. No task touches a user installation.
- From task 2.1 on, `./hyprn-mvp dev check <group>` runs a test group (it wraps `deployment/checks.py` in the locked environment).
- Phase 1 must be complete. Phase 3 and 4 tasks may run beside this plan when their files are disjoint (see `ROADMAP.md` and "Cross-phase coordination" below).

### Waves

| Wave | Tasks |
|---|---|
| 1 | 2.1 (tracer): **done**, verified on its branch; merges right after the Phase 1 gate closes |
| 2 | 2.1a → 2.2 → 2.3 → 2.4 (2.1a opens with a blocking audit checkpoint and may run beside Phase 3 tasks: its files are disjoint from theirs except `deployment/checks.py`) |
| 3 | 2.5 ∥ 2.6 ∥ 2.7 (disjoint files) |
| 4 | 2.8a (decision, blocking) → 2.8b → 2.8c → 2.8 → 2.9 → 2.10 → 2.11 → 2.12 |
| 5 | 2.13 → 2.14 |

Task 2.8a computes its facts on the tree that 2.5–2.7 leave and runs before 2.8b; no attested file changes until its answer is recorded. 2.8b is test-only; from 2.8c's first attested edit the development attestation is stale until 2.8 re-attests once (re-attestation window below).

### Cross-phase coordination

- **2.8 before Documents schema edits.** After 2.8c, the Documents-only definitions and the `x-hyprn-mvp-documents-contract` registry live in `contracts/schemas/documents.schema.json` (not attested), and `contracts/schemas/execution.schema.json` is generated; 2.8 closes the chain with the single re-attestation and stays the task Phase 4 depends on. Phase 4 tasks that add or change Documents schema definitions or the registry (4.32 and 4.34, and any other task the Phase 4 plan names; 4.31 changes wording in `contracts/documents.md` only) depend on 2.8 and edit `documents.schema.json`. A change to `model.schema.json` (where the shared citation vocabulary stays under option a) regenerates the execution schema and makes the attestation stale; it is re-attested once by the task that closes the chain (4.37 for the Phase 4 document-bearing chain), and the re-attestation-window rule applies from the first such edit (4.34) until the window closes with the producer re-pin and fixture recapture of 4.37b. 4.37 (worker admission with re-attestation) depends on 2.8 and re-attests on top of the set 2.8 leaves; 4.19 already depends on 2.8 for the release binding. A registry reader that merges before 2.8c (for example the `DOCUMENT_LIMITS` check of Phase 4 task 4.1) is moved to `contracts` by 2.8c in the same commit.
- **Attested set.** Phase 3's TG-2 gate ("attested sources unchanged") names the attested set as 2.8c leaves it and 2.8 attests it, the list recorded in checkpoint 2.8a; a Phase 3 task that merges before 2.8c uses the current list.
- **Re-attestation window.** From the first edit that makes the development attestation stale until the task that re-attests (2.8c's first attested edit until 2.8; in Phase 4, 4.34's first `model.schema.json` edit until 4.37 re-attests and 4.37b re-pins and recaptures; Phase 4 keeps the binding list of affected groups measured in checkpoints 4.34 and 4.36), no other task runs native, durable-fixture or attestation groups against the shared development fixtures; a branch that predates the re-attesting task's merge rebases before running them.
- **Shared files, edited by one task at a time across Phases 2–4:** `application/tests/test_module_boundaries.py` (Phase 2: 2.3, 2.8b, 2.8c; Phase 3: 3.3a, 3.3c, 3.4; Phase 4: 4.1, 4.20, 4.25, 4.37); `contracts/schemas/*.json` (2.8c, then the Phase 4 schema tasks); `contracts/hyprn-mvp.openapi.yaml` with `ui/src/contract.ts` and `application/generate_contract.py` (2.8c regenerates the two generated files byte-identical without committing them and edits the generator only to read definitions through `contracts`); `deployment/checks.py` with `deployment/tests/test_repository_guard.py` (2.1a, 2.2, 2.5, 2.6, 2.8c, 2.8 and 2.9–2.14 register groups or targets and 2.4 edits the guard; after Phase 4 task 4.4 lands, a Phase 2 task registers a group by adding an entry file under `deployment/groups/<family>/`, recommended family `local`, and edits `checks.py` only for runner changes; before 4.4 lands, groups are registered in `checks.py` as planned and 4.4 migrates every group present when it runs); `application/src/hyprn_mvp_app/store.py`; `application/src/hyprn_mvp_app/api.py` (composition only after Phase 3 task 3.3a; a route goes into its owner's `routes/<owner>.py`).

## Target design

### Locations

Every location resolves in this order: command-line flag → `HYPRN_MVP_*` environment variable → installation configuration → per-OS default from `editions/local/src/hyprn_mvp_local/paths.py` → otherwise setup asks the user and records the confirmed answer. In non-interactive mode an unresolved location exits 2 with `location_unresolved`; a coding agent running setup asks the user instead of choosing a path.

| Location | Flag | Variable | Configuration field | macOS default | Linux and WSL2 default |
|---|---|---|---|---|---|
| Installation configuration | `--config` | `HYPRN_MVP_CONFIG` | — | `~/.config/hyprn-mvp/installation.json` | `${XDG_CONFIG_HOME:-~/.config}/hyprn-mvp/installation.json` |
| Data root | `--data-dir` | `HYPRN_MVP_DATA_ROOT` | `data_root` | `~/Library/Application Support/hyprn-mvp` | `${XDG_DATA_HOME:-~/.local/share}/hyprn-mvp` |
| Tool cache (uv, CPython) | — | `HYPRN_MVP_TOOLS_DIR` | — | `~/Library/Caches/hyprn-mvp/tools` | `${XDG_CACHE_HOME:-~/.cache}/hyprn-mvp/tools` |
| Logs | — | — | — | `<data root>/logs` | `<data root>/logs` |

The `./hyprn-mvp` shell entry point is the only other place that computes the tool-cache default (it runs before Python exists); a test asserts it equals the path-policy module.

Refused as a data root or checkout: any folder under a synced location (macOS `~/Library/CloudStorage`, `~/Library/Mobile Documents`, and `~/Desktop` or `~/Documents` because they may be synced; Dropbox, OneDrive and Google Drive folders on every OS); a path with a symlink component; a folder not owned by the user; a non-empty folder without this installation's identity; on WSL2, a Windows-mounted drive (`/mnt/<letter>/…`).

### Installation configuration (version 1)

Closed JSON schema `deployment/config.schema.json`; unknown fields and duplicate keys are refused. File 0600 in a 0700 folder, owned by the user, no symlink in any component. Fields: `schema`, `edition` (`local`), `installation_id` (uuid4, fixed at first setup), `owner_username`, `host_home`, `data_root`, `ports.app`, `origin` (`http://127.0.0.1:<port>`), `docker.endpoint` and `docker.engine` (discovered at setup), `release.mode` (`checkout` or `frozen`), `release.require_review`, `release.immutable`, `agent.enabled` (default true), `agent.token_ttl_hours` (default 8), `upstream.cache` (inside the data root). Never in the configuration: secrets, worker policy or limits, image ids. The loader `integration/src/hyprn_mvp_integration/installation.py` is stdlib only and belongs to the attested execution source set.

### Data root layout

    <data root>/                      0700
      identity.json                   installation id, edition, store identities, AiiDA profile and repository identities
      credentials/                    0700: owner password (0600), modeling and service keys
      application/  modeling/         component stores
      execution/                      AiiDA profile and repository, venv-<lock16>/, runtime and attestation records, launch-worker, locks/, licenses/, executor state
      releases/<release-id>/          checkout-mode snapshots (source/, manifest.json); active.json pointer
      cache/upstream/whatsopt/<sha256>/WhatsOpt.tar.gz   0400, verified at fetch and at every read
      logs/                           setup and executor logs, without secrets

Ordinary start never creates stores. Initialization runs only on a blank root or on a root carrying this installation's own partial-setup marker (resumed or refused, never overwritten). A root with another identity, foreign files or symlinks is refused. Each store records its schema version (the application store inside the store, and every store's version in `identity.json` beside its identity); `start` compares them with the release's expected versions and refuses on a mismatch (D-12).

### Checkout mode

- `setup` snapshots the committed `HEAD` with `git archive`, restricted to product paths (`application`, `contracts`, `deployment`, `editions`, `integration`, `modeling`, `ui`, `upstream`), into `<data root>/releases/<edition>-<sha12>-<tree16>/source`, and writes a manifest `hyprn_mvp.release/1` (source commit, tree digest, per-file SHA-256, edition, image identities, optional review record). Uncommitted changes are listed as a warning and never installed.
- Images, the native environment and the launch-worker wrapper are built from the snapshot; the worker is attested against the snapshot's execution source set; `active.json` is replaced atomically.
- `start` binds every manager to the active snapshot: manifest and tree verification, foreign `sys.path` entries removed, a module-origin record, and a launch-worker wrapper that must equal this release's wrapper. `start` never rebuilds or re-attests; when the checkout's `HEAD` differs from the active release it refuses with `source_changed` and names the installed commit.
- `release.mode = frozen` keeps optional governance: the snapshot must carry a recorded independent review, and `release.immutable` makes the snapshot read-only (see D-09). Both are off by default.

### Acquisition

| Artifact | Source and verification |
|---|---|
| uv | Official release archive, version 0.12.24 (latest stable when adopted); version and per-platform SHA-256 (darwin arm64 and x86_64, linux x86_64 and aarch64) in `deployment/locks/tools.json`; downloaded over HTTPS by `./hyprn-mvp`, verified before extraction, cached in the tool cache |
| CPython | uv-managed CPython 3.12.15 (python-build-standalone build named by uv's download metadata), pinned in `.python-version` and the lock; downloaded only from the python-build-standalone GitHub releases (`UV_PYTHON_INSTALL_MIRROR`) |
| Python packages | `uv` lock with hashes; installs use `--require-hashes`; versions stay at the reviewed sets, raised only where CPython 3.12.15 requires it or a published security fix applies, each change re-audited |
| Native host environment | `deployment/locks/native-host.txt` with hashes, installed into `<data root>/execution/venv-<lock16>`; `hyprn-mvp-app` and `hyprn-mvp-integration` wheels built from the snapshot and installed without dependencies |
| Base images | Python, Ruby and Node images pinned by digest (index digest and resolved platform digest recorded) |
| WhatsOpt source | Archive of commit `597f5abf18d4a6335c2f3b9174ab16acdf1de4bd` fetched at setup from the pinned URL in `deployment/locks/upstream.json`, verified against SHA-256 `4937188df6ea12daa8a2b00767005e3649d2974ab6e634409f7756043ef0b360` and size 2,078,870 bytes |
| Ruby gems | `deployment/locks/whatsopt-gems.json` (name, version, platform, SHA-256); every cached gem verified after `bundle install` |
| Node packages | `yarn install --immutable` and `npm ci` against committed lockfiles |

Network is allowed only in acquisition stages. Every other build runs with `--network none`. Rebuilt artifacts are proven equivalent to the Phase 1 reference images at file level; image ids are new identities.

### CLI contract

Global: `--config PATH` (or `HYPRN_MVP_CONFIG`), `--json`, `--non-interactive`. JSON envelope `{operation_id, operation, installation_id, status, reason_code, observed, evidence_refs}`. Exit codes: 0 success or no-op, 2 invalid input or identity, 3 incompatible release or schema, 4 admission conflict (for example an active run), 5 failed verification or dependency, 6 operator recovery required. No secret ever appears in output, process arguments or logs.

| Command | Contract |
|---|---|
| `setup [--reset-data [--yes]]` | Prerequisites → first-run questions with defaults → initialize if blank → acquire → snapshot → build → native environment → initialize stores (generated owner password, at least 24 URL-safe characters, written 0600 and passed on standard input) → build worker and attest → activate release. On an existing installation with the same release: verified no-op. With a different release: refuses with `update_unavailable` (D-08). `--reset-data` (D-12): after an explicit confirmation (typing the installation id when interactive; `--yes` is required with `--non-interactive`), stops the installation, discards the data root's stores (application, modeling, AiiDA profile and repository) and initializes fresh ones with a new generated owner password; refuses with exit 4 while a launch is active or uncertain; configuration, images and release are kept |
| `start` | Verify configuration, identities, store schema versions, active release, image labels, attestation, port owner; start modeling, application (bound to `127.0.0.1:<port>`) and executor; liveness and a cross-site request negative check (expects 403); print the URL only. Never creates a store or alters a schema |
| `stop` | Stop the executor without force-killing an active launch (bounded wait 120 s; exit 4 with active and uncertain counts on timeout), then application and modeling. Data untouched |
| `status` | Read-only: release, attestation, components, executor, URL, data root, disk |
| `open` | Copy the owner password to the clipboard and clear it after 90 s if unchanged; open the URL. Never prints the password; without a clipboard it prints the URL and the password file's location |
| `logs [app\|modeling\|executor] [--follow] [--since]` | Read logs |
| `doctor` | Read-only prerequisites, configuration, identity, images, attestation, executor, containers, credential-store availability; resources without this installation's label are listed as foreign and never acted on |
| `test` | Smoke test on a throwaway installation; never touches the real one |
| `uninstall [--purge --confirm <installation_id>]` | Stop; remove this installation's labelled containers, networks and images, native environments, credential-store items and configuration file; keep the data root. `--purge` deletes the data root only after the exact installation id is confirmed |
| `version` | Tool, Python, lock, edition and release identities |
| `dev check <group>` | Developer passthrough to the test-group runner |

`study new`, `mcp relay` and `mcp token …` are added in Phase 3.

## Decisions and defaults applied

- **D-01** Supported hosts: macOS (arm64, x86_64) and Linux (x86_64, aarch64) natively; Windows through WSL2, treated as Linux. Native Windows is not supported in this phase.
- **D-02** Qualified engines: Docker Desktop (macOS, Windows with WSL2) and Docker Engine (Linux). Other engines are accepted; `doctor` reports them as unqualified.
- **D-03** Per-OS defaults live only in the path-policy module (and the tool-cache default in the shell entry point, tested equal).
- **D-04** The topology keeps the per-component managers (modeling compose, application container, host executor); no unified product compose file in this phase.
- **D-05a** The dependency audit in `2.1-dependency-audit.md` (this folder) is approved: task 2.1 copies it to `docs/operations/dependency-audit.md`, applies its single package change and its accepted residuals, and may download without a further checkpoint. Any version or package beyond that record is a new blocking checkpoint.
- **D-05b** Setup refuses macOS on Intel (x86_64) with an explanation; supported hosts are macOS on Apple silicon, Linux x86_64 and aarch64 (glibc), and Windows through WSL2.
- **D-05** CPython is 3.12.15 everywhere (host environments and images), installed by uv 0.12.24; adopt the newest stable releases available at the time of the audit, without an age delay. Package versions follow the reviewed sets; a version moves only when CPython 3.12.15 requires it or a published security fix applies, and each move is re-audited. The numerical engine (OpenMDAO 3.45.1) and AiiDA stay at their reviewed versions.
- **D-06** Default port 18470, changeable at setup; the owner's sign-in name defaults to the operating-system account's short name.
- **D-07** Tests and smoke runs use throwaway installations; `doctor` and `status` are read-only.
- **D-08** No backup, restore or update command in this phase. `uninstall` is the only lifecycle command beyond setup, start and stop. `setup` refuses a different release on an existing installation (`update_unavailable`); re-adopting a kept data root after `uninstall` is allowed only for the same release.
- **D-09** Frozen-release immutability uses the macOS user-immutable flag where available and read-only permissions plus manifest verification on every bind elsewhere; no elevated privileges are ever requested.
- **D-10** The credential-store adapter calls the operating system's own tools with secrets on standard input (`/usr/bin/security -i` on macOS, `secret-tool` on Linux); no new Python dependency.
- **D-11** Factorization schedule for this phase (product owner, 2026-10-13; `.planning/codebase/FACTORIZATION.md`): item 7 (dynamic-loading allowlist keyed by enclosing function instead of line) and item 11 (contract schemas split by consumer) fold into task 2.8b (item 7, test-only, before any attested edit) and task 2.8c (item 11), and the single re-attestation happens in task 2.8, whose release snapshot re-attests anyway: one deliberate re-attestation, the golden identity corpus unchanged, historical prepared artifacts readable. Item 11 changes the attested inventory, so its exact shape is shown to the product owner at the blocking checkpoint 2.8a (PD-2.4) before any attested file changes.
- **D-12** Store schema changes before the pilot-retention boundary (product owner, 2026-10-13): no migration code. Each store records its schema version; ordinary open never creates a store and never alters a schema (the ad-hoc `ALTER TABLE` and the creation on open are removed in task 2.11); a version mismatch makes `start` refuse with a message naming the reset command; `./hyprn-mvp setup --reset-data` is the only way to a fresh store, after an explicit confirmation, and never runs automatically. Full retention, backup and migration rules begin only when the pilot-retention boundary is declared (architecture §8).
- **D-13** Formatting and readability (product owner, 2026-10-13): Python is formatted and linted with ruff and TypeScript with prettier, installed only after the blocking audit checkpoint of task 2.1a; a ratchet baselines existing violations and refuses new ones. Pinned execution sources (the attested set) are reformatted only in task 2.8c, which is followed by the single re-attestation of task 2.8; hash-pinned test files are never reformatted.

## Open product decisions (recommended defaults)

- **PD-2.1 OPS-04 status.** Default: OPS-04 stays `planned` until Phase 5 qualifies the local edition (clean-room installs on macOS and Linux and the fresh-account run); then it becomes `delivered`.
- **PD-2.2 Linux or WSL2 host without a credential store** (no Secret Service, for example a headless server). Default: the adapter reports "unavailable"; anything that needs to store a token refuses with an explanation of how to enable a Secret Service provider, and never falls back to a file. Alternative: a 0600 file under the data root's `credentials/`, accepted only if the product prefers headless convenience over the "never in files" rule of the agent specification.
- **PD-2.3 Upstream archive no longer matches its pin.** Default: setup stops (fail closed). Recommended remedy, adopted only after review: keep a verified copy of the archive in the repository under `upstream/whatsopt/` with the same SHA-256 pin, which also makes the corresponding source available with every clone.
- **PD-2.4 Exact contract-schema split** (FACTORIZATION item 11, D-11; answered at checkpoint 2.8a). Default (option a of task 2.8a): the Documents-only definitions (108 today) and the registry move to `contracts/schemas/documents.schema.json`; the `Document*` definitions that evidence-4 records reference (11 today) stay in `model.schema.json`, which stays closed under `$ref` and remains the modeling service's schema; `execution.schema.json` is generated as the closure of a reviewed root list; the execution inventory keeps its path list (contents change), `ATTESTED_PROJECT_FILES` is unchanged, and `documents.schema.json` joins only the application image inventory; prepared artifacts keep recording the same two schema paths, and earlier artifacts keep their recorded identities and stay admissible.

## Deferred work

- **Outbox history projection made explicit and rebuildable** (FACTORIZATION item 13): after the first release.
- **Authorization by effect instead of boolean flags** (FACTORIZATION item 14): after the first release.
- **Domain SQL moved into the store module** (code review follow-up, product owner, 2026-10-13): planned with the cloud edition, whose PostgreSQL row-level security needs one place that owns every statement; not in this plan, and the local edition keeps its current split meanwhile.
- Factorization items planned elsewhere, not in this plan: item 1 in Phase 1 task 1.11; in Phase 3, item 2 (task 3.3d), item 4 (3.3c), item 6 (folded into 3.4), item 8 (3.3a) and item 9 (3.3b); in Phase 4, items 3 and 5 (folded into 4.4), item 10 (task 4.22a, before 4.23) and item 12 (Phase 4 tasks 4.37–4.38). This plan carries items 7 and 11 (tasks 2.8b and 2.8c, gated by 2.8a; re-attested once in 2.8).

## Tasks

### Task 2.1 (tracer) — `./hyprn-mvp` entry point, pinned toolchain and locked environments

<task type="tracer" id="2.1">

<name>Task 2.1 (tracer) — `./hyprn-mvp` entry point, pinned toolchain and locked environments</name>

<files>

create `hyprn-mvp` (POSIX sh, executable), `deployment/locks/tools.json`, `.python-version`, `pyproject.toml` (uv workspace: `application`, `integration`, `editions/local`), `uv.lock`, `editions/local/pyproject.toml`, `editions/local/src/hyprn_mvp_local/{__init__,__main__,cli}.py` (`version`, `dev check`), `editions/local/tests/test_shim.py`, `docs/operations/dependency-audit.md`; modify `deployment/checks.py` and `deployment/tests/scoped_fixture.py` (interpreters come from the locked environments instead of `HYPRN_MVP_NATIVE_PYTHON` and `HYPRN_MVP_CONTRACT_PYTHON`).

</files>

<action>

- **Goal:** from a fresh clone, `./hyprn-mvp dev check contracts` downloads and verifies uv, provisions the pinned CPython and locked environment, and runs the group: the thinnest path from the entry point through the toolchain to the test suite.

- **Steps:**
  1. Record in `dependency-audit.md`: uv's official release, version, per-platform archive SHA-256 from the release's checksum files, licence (MIT or Apache-2.0); the uv-managed CPython 3.12.15 build, its bundled libraries and their licences (the Linux builds statically link Berkeley DB under the Sleepycat licence: record it as an open item in `docs/legal/licensing.md`; HYPRN MVP does not redistribute the interpreter). **Blocking human checkpoint:** the product owner confirms this record before the first download. Any package or version absent from the reviewed locks is another blocking checkpoint, never auto-approved.
  2. `hyprn-mvp` (`set -eu`): refuse a synced checkout; find uv in the tool cache or download it with `curl --proto =https --tlsv1.2 -fsSL` to a temporary file; verify with `shasum -a 256` or `sha256sum`; refuse on mismatch; then run `python -I -B -m hyprn_mvp_local "$@"` in the locked environment. Never use a system Python.
  3. Lock exactly the versions of `application/requirements.lock`, `integration/test-requirements.lock` and the distribution sets of the Phase 1 development interpreters (read with `importlib.metadata`, read-only). If one resolution cannot satisfy both sets, use two locked projects (contract and native).
  4. The runner keeps its exact-interpreter guard, now against the locked environments.

- **Risks:** version conflicts between the two sets (two locked projects); network needed for the first download (documented prerequisite).

</action>

<verify>
<automated>

`./hyprn-mvp version` prints uv, Python and lock digests; `./hyprn-mvp dev check contracts`, `locality-contracts`, `projection`, `api-a`, `combined-security` and `units-guards` reach the Phase 1 counts; `test_shim.py` passes (tampered checksum refused, synced checkout refused, no system Python executed, tool-cache default equal to the path-policy value once 2.2 lands); the lock's versions equal the reviewed sets (diff recorded).

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.1.md` is verified by the orchestrating session.</done>

</task>

### Task 2.1a — Formatter, linter and readability ratchet

<task type="auto" id="2.1a">

<name>Task 2.1a — Formatter, linter and readability ratchet</name>

<files>

modify `docs/operations/dependency-audit.md` (the ruff and prettier records), `pyproject.toml` (ruff configuration), `uv.lock`, `deployment/locks/tools.json` (only if the tool pins live there), `ui/package.json` and `ui/package-lock.json` (prettier, development dependency); create `ui/.prettierrc.json`, `deployment/style_ratchet.py`, `deployment/style_baseline.json`, `deployment/tests/test_style_ratchet.py` (group `style-ratchet`); modify `deployment/checks.py` (register `style-ratchet` as a must-pass group).

</files>

<action>

- **Goal:** one formatter and one linter per language, and a ratchet that lets existing code stay as it is while refusing new unreadable code: long lines, statements chained with `;` in Python, and new or changed files that are not formatted.

- **Depends on:** 2.1 (the locked environments and `./hyprn-mvp dev check`). Ordered before 2.2 so that every later task writes into the ratchet; the product owner's answer to the audit checkpoint can be given while Phase 3 tasks run.

- **Steps:**
  1. Record in `dependency-audit.md`, for ruff (Python) and prettier (TypeScript): official source, exact version, the SHA-256 of each artifact the install resolves (ruff's per-platform wheels; prettier's npm tarball integrity), licence (both expected permissive; confirmed from the release, never assumed), and what each tool does not do (neither executes project code). **Blocking human checkpoint:** the product owner confirms the record, and the line-length limit (recommended default 100 characters) before anything is installed. A version or package beyond that record is another blocking checkpoint.
  2. After the checkpoint: add ruff to the locked development environment and prettier to `ui/` (exact versions, hashes in the lock files); configuration only in `pyproject.toml` and `ui/.prettierrc.json`, with the confirmed limit; no editor-specific or absolute paths.
  3. `style_ratchet.py` (standard library; runs ruff and prettier through the locked environments): for Python, the violation counts per file of the line-length rule and of the semicolon-chaining rules (`E501`, `E702`, `E703`); for TypeScript and Python, `--check` formatting. `style_baseline.json` records, per file, the counts of the existing violations and the base commit. The check fails when a file's count rises, when a file absent from the baseline has any violation, and when a file added or modified since the base commit is not formatted; a file that only shrinks its violations passes and `--update` may lower (never raise) the baseline.
  4. Exclusions, read from their owners and never copied by hand: the pinned execution sources (the attested set, read from `ATTESTED_PROJECT_FILES` in `application/tests/test_module_boundaries.py` and the `execution_source_hashes()` literal) until task 2.8c reformats them and removes this exclusion; test files whose bytes are pinned by hash (read from the pin tables of the contract tests, for example `test_unit_declaration_contracts.py`); generated files whose bytes are asserted elsewhere (`contracts/hyprn-mvp.openapi.yaml`, `ui/src/contract.ts`, `ui/src/design/tokens.css`, `contracts/schemas/execution.schema.json`) and captured fixtures.
  5. Register `style-ratchet` in `deployment/checks.py` (or its entry file under `deployment/groups/` once Phase 4 task 4.4 has landed) as a must-pass group: a missing tool, baseline or base commit fails it, never skips.
  6. Reformat nothing else in this task: no existing file changes except the configuration files above.

- **Risks:** formatting churn reaching pinned or generated files (exclusions read from their owners, plus a test that every exclusion exists); a baseline that hides new violations (counts only ever fall, `--update` refuses a rise); tool downloads before the checkpoint (none).

</action>

<verify>

<automated>

`./hyprn-mvp dev check style-ratchet` passes on the committed tree with its tests: a seeded new Python line over the limit fails; a seeded `a = 1; b = 2` fails; a new unformatted TypeScript file and a new unformatted Python file fail; a file with its baselined violations unchanged passes; a baselined file with one more violation fails; an excluded pinned execution source and an excluded hash-pinned test file pass unformatted; the exclusion lists equal what `ATTESTED_PROJECT_FILES` and the pin tables name.

</automated>
<fails_when>any seeded case does not fail (or any passing case fails), an exclusion is a hand-copied list, or the group is skipped or missing from `deployment/checks.py`</fails_when>
<automated>

`git diff --name-only "$BASE"..HEAD`, with `BASE` the commit this task started from.

</automated>
<fails_when>it prints any path other than the files listed above: this task reformatted or changed existing code</fails_when>
<automated>

`grep -nE 'ruff|prettier' docs/operations/dependency-audit.md` shows, for each, an official source, an exact version, a hash and a licence, and checkpoint `phases/02-local-edition/checkpoints/2.1a.md` records the product owner's confirmation before the first install.

</automated>
<fails_when>a record lacks one of the four fields, or a tool was installed before the confirmation is recorded</fails_when>

</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.1a.md` is verified by the orchestrating session.</done>

</task>

### Task 2.2 — Installation configuration and path policy

<task type="auto" id="2.2">

<name>Task 2.2 — Installation configuration and path policy</name>

<files>

create `deployment/config.schema.json`, `integration/src/hyprn_mvp_integration/installation.py`, `editions/local/src/hyprn_mvp_local/paths.py`, `deployment/tests/test_installation_config.py` (group `installation-config`), `editions/local/tests/test_paths.py`, `deployment/tests/test_portability_guard.py` (group `portability`); modify `deployment/local_paths.py` (installation configuration becomes resolution step three), `application/src/hyprn_mvp_app/store.py` (the location check of `Store.__init__` only), `application/tests/test_store_location.py` (added to the `api-a` group).

</files>

<action>

- **Goal:** one validated configuration and one path-policy module decide every location, with per-OS defaults and refusals.

- **Steps:**
  1. Schema and loader per "Installation configuration". The loader takes an explicit path and refuses symlinks, group or other access, a foreign owner, unknown fields, duplicate keys, an edition mismatch, relative paths and a data root in a synced or Windows-mounted folder.
  2. Path policy per "Locations", with operating-system detection (macOS, Linux, WSL2 by its kernel release or `WSL_DISTRO_NAME`). Tests run each OS's table with a temporary `HOME` and injected platform values.
  3. `portability` guard: no operating-system folder layout outside the path-policy module and the shell entry point; no absolute user-home path in tracked code (prefixes assembled at run time).
  4. Application store location: `Store.__init__` replaces its hard-coded temporary-folder exemption and its check for the macOS "CloudStorage" folder with the path policy's one refusal function (synced folder on every operating system, symlinked path or parent, Windows-mounted drive), so the loader and the store apply the same rule. The application never imports the local edition package: if the path policy lives there, the composition root injects the function into `Store`; the checkpoint records the placement, and `test_module_boundaries.py` is edited only if an edge is added. Tests that use scoped scratch stores keep working through the scratch root's own approval (`hyprn-mvp-test-<uuid>`), not through a temporary-folder exemption.

- **Risks:** misdetected synced folders (conservative refusal with a message naming the rule); scratch stores in a temporary folder refused once the exemption is gone (the scoped-root approval covers them).

</action>

<verify>
<automated>

`./hyprn-mvp dev check installation-config` (unknown field, duplicate key, symlinked data root, 0644 configuration, foreign owner, each synced location, Windows-mounted drive, edition mismatch), `./hyprn-mvp dev check portability` and the path tests pass.

</automated>
<automated>

`./hyprn-mvp dev check api-a` including `test_store_location.py`: `Store` refuses a path under each operating system's synced-folder table (injected platform values) and a symlinked path or parent, accepts a scoped scratch root, and `git grep -nE 'CloudStorage|"/tmp"' -- application/src/hyprn_mvp_app/store.py` prints nothing.

</automated>
<fails_when>`Store` accepts a synced location that the loader refuses (or the reverse), or the grep prints a line: a second, hard-coded location rule remains</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.2.md` is verified by the orchestrating session.</done>

</task>

### Task 2.3 — Execution side from the installation

<task type="auto" id="2.3">

<name>Task 2.3 — Execution side from the installation</name>

<files>

`integration/src/hyprn_mvp_integration/launcher.py` (root and owner from the installation; the home-denial containment probe uses `host_home`; `runtime.json` records a digest of the execution-relevant fields: data root, AiiDA profile, Docker endpoint), `deployment/execution_runtime.py`, `deployment/dispatch_runtime.py`, `deployment/native_environment.py` (roots and profile name only), the attested-set pins and their coverage tests.

</files>

<action>

- **Goal:** the launcher, executor, dispatch and native managers take roots and identities from the installation; attestation covers the configuration that matters for containment.

- **Steps:** add `installation.py` to the execution source set with its pins; the worker policy stays in source and cannot be configured; existing scoped fixture roots keep working through the test constructor that accepts only `hyprn-mvp-test-<uuid>` roots.

- **Risks:** an attested-set change without coverage (two-sided test); weakening the containment probe (its home-denial case runs with a scratch `host_home`).

</action>

<verify>
<automated>

`./hyprn-mvp dev check units-launcher`, `units-worker`, `units-attestation`, `approach-bundle`, `guard` and `portability` pass; the two-sided coverage test passes with `installation.py` in the set.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.3.md` is verified by the orchestrating session.</done>

</task>

### Task 2.4 — Modeling and application managers from the installation

<task type="auto" id="2.4">

<name>Task 2.4 — Modeling and application managers from the installation</name>

<files>

`deployment/modeling_runtime.py` (roots, upstream cache, Docker endpoint, container, network and label names from the installation; the upstream resolver stays fail-closed), `deployment/application_runtime.py` (root, port, names, provisioning username), `modeling/rehearsal.py` (reads the archive through the upstream resolver), `deployment/tests/live_fence.py` (adds the user installation's data root and configuration), `deployment/tests/test_repository_guard.py`, `deployment/tests/test_deployment_hardening.py`.

</files>

<action>

- **Goal:** the modeling and application managers are fully installation-driven, code that served only one fixed installation is gone, and `units-native` passes end to end including the per-run computational record export.

- **Steps:** remove activation, recovery-record and fixed-root code paths that no installation-driven path uses, with their tests (reference evidence in the checkpoint); keep `stage_native_inputs` and the upstream resolver's semantics.

- **Risks:** removing code a test still needs (failures route back to this task).

</action>

<verify>
<automated>

`./hyprn-mvp dev check units-native` (all steps, including the export), `fuel-native-provenance`, `findings-native-read`, `approach-ui-history`, `guard`, `deployment-hardening` and `portability` pass; `git diff "$BASE"..HEAD -- integration/src/hyprn_mvp_integration/computational_export.py` is empty, with `BASE` the commit this task started from.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.4.md` is verified by the orchestrating session.</done>

</task>

### Task 2.5 — Native host environment from pinned packages

<task type="auto" id="2.5">

<name>Task 2.5 — Native host environment from pinned packages</name>

<files>

`deployment/native_environment.py` (`prepare`, `extend`, `initialize` with profile `hyprn-mvp-local-<id8>`), `deployment/locks/native-host.txt`, `deployment/tests/test_native_environment.py` (group `native-environment`).

</files>

<action>

- **Goal:** the host-side AiiDA environment is created from hashed pins, with real entry points.

- **Depends on:** 2.4. Parallel with 2.6 and 2.7.

- **Steps:** `prepare(installation, release)` keeps the populated-root refusal, resolves the pinned CPython, creates `execution/venv-<lock16>` with `--require-hashes`, builds non-editable `hyprn-mvp-app` and `hyprn-mvp-integration` wheels from the snapshot with a pinned, hashed build backend, installs them without dependencies, writes the installed inventory and `licenses/native/`.

- **Risks:** wheel build reproducibility (pinned backend, offline build); dependency drift (exact lock).

</action>

<verify>
<automated>

`./hyprn-mvp dev check native-environment`: scratch prepare; a second prepare refused; inventory equal to the reviewed set; `AUDITED_LICENSES` metadata bytes equal; no path of the checkout inside the environment; no `.pth` file; a `core.sqlite_dos` profile initialised in scratch; the `hyprn_mvp.scalar` entry point loads. `./hyprn-mvp dev check units-attestation` passes.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.5.md` is verified by the orchestrating session.</done>

</task>

### Task 2.6 — WhatsOpt acquisition, source and modeling images, notices

<task type="auto" id="2.6">

<name>Task 2.6 — WhatsOpt acquisition, source and modeling images, notices</name>

<files>

create `deployment/locks/upstream.json`, `deployment/locks/whatsopt-gems.json`, `deployment/images/whatsopt-source.Dockerfile` (from `deployment/native.Dockerfile`), `THIRD_PARTY_NOTICES.md`, `deployment/tests/test_upstream_acquisition.py` (group `upstream`); modify `deployment/modeling_runtime.py` (`acquire_upstream`: fetch → verify → 0400 cache; source image built from the verified archive; recorded build identity instead of a fixed image id), `deployment/modeling.Dockerfile`, `docs/legal/licensing.md` (local-edition corresponding source).

</files>

<action>

- **Goal:** the modeling service is built from the verified upstream archive and verified gems on any host, with its licence obligations recorded.

- **Depends on:** 2.4. Parallel with 2.5 and 2.7.

- **Steps:**
  1. Fetch the pinned archive into scratch and compare its SHA-256 and size with the pin. If they differ, stop and apply PD-2.3 only after review.
  2. Derive the gem lock by hashing the cached `.gem` files of `HYPRN_MVP_MODELING_SOURCE_IMAGE` in a throwaway `--rm --network none` container, and cross-check each SHA-256 with the checksums published by rubygems.org; any gem without a published match is a blocking human checkpoint.
  3. The source image verifies every cached gem after `bundle install` and fails on mismatch; `yarn install --immutable` relies on the lockfile checksums; Ruby and Node bases are digest-pinned.
  4. Equivalence: build the modeling image with `--no-cache` and compare `/native` and `/usr/local/bundle` file hashes with the Phase 1 reference modeling image; only documented differences are allowed.
  5. `docs/legal/licensing.md` states for the local edition: WhatsOpt is AGPL-3.0; the corresponding source is the upstream archive (by commit and hash), `upstream/whatsopt-patches/` and the build recipes and pins, all in the repository or fetched by pin and shipped in the modeling image's corresponding-source directory; legal review remains pending (L1, L4). `THIRD_PARTY_NOTICES.md` lists the shipped components and points there.

- **Risks:** upstream bytes changed (PD-2.3); gem source drift (lock and checksums); long builds.

</action>

<verify>
<automated>

`./hyprn-mvp dev check upstream` (wrong hash, wrong size, symlinked cache, group-readable file, network failure → fail closed; a valid cached file reused without network); `./hyprn-mvp dev check units-native` and `native-a` pass with the rebuilt images; the equivalence report shows no unexplained difference.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.6.md` is verified by the orchestrating session.</done>

</task>

### Task 2.7 — Engine, worker and application images from pinned sources

<task type="auto" id="2.7">

<name>Task 2.7 — Engine, worker and application images from pinned sources</name>

<files>

create `deployment/images/engine.Dockerfile`; modify `deployment/execution_runtime.py` (build engine, then worker; recorded build identity instead of a fixed image id), `deployment/application.Dockerfile` (multi-stage: digest-pinned Node stage runs `npm ci` and `npm run build`; digest-pinned Python stage installs `application/requirements.lock` with `--require-hashes`), `deployment/application_runtime.py` (no host wheels or host UI build), `deployment/pins.json` (base digests, build-input digests); fold the wheel-caching step of `deployment/initialize_stores.py` into the image build.

</files>

<action>

- **Goal:** the numerical engine, worker and application images build from digest-pinned bases and hashed locks, with no host-built artifacts.

- **Depends on:** 2.4. Parallel with 2.5 and 2.6.

- **Steps:** record each base's index digest and resolved platform digest for arm64 and amd64; equivalence: engine `site-packages` RECORD hashes equal those of `HYPRN_MVP_ENGINE_IMAGE`; UI assets built in the image equal a host `npm run build` of the same tree.

- **Risks:** base digest drift in multi-architecture indexes (both digests recorded); package registry availability.

</action>

<verify>
<automated>

`./hyprn-mvp dev check units-worker`, `units-attestation`, `approach-worker`, `investigation-worker`, `api-a` and `ui-a` pass (the browser served from the image-built UI); a `--no-cache` build of all three images succeeds; no fixed image id remains except as recorded reference identities.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.7.md` is verified by the orchestrating session.</done>

</task>

### Task 2.8a — Decision: contract-schema split before the attested change (PD-2.4)

<task type="checkpoint:decision" id="2.8a" gate="blocking">

<name>Task 2.8a — Decision: contract-schema split before the attested change (PD-2.4)</name>

<reversibility rating="costly">The split changes the attested execution schema and the schema identities every newly prepared artifact records; undoing it needs another re-attestation, and artifacts carrying either identity stay in stores and must keep being read.</reversibility>

<decision>The exact split task 2.8c implements (D-11, FACTORIZATION item 11): which definitions move to `contracts/schemas/documents.schema.json`, the reviewed root list and generated closure of `contracts/schemas/execution.schema.json`, the attested inventory and modeling image inputs after the change, and the schema-identity compatibility rule for prepared artifacts.</decision>

<context>

Verified on the planning baseline; step 1 recomputes every number on the tree 2.5–2.7 leave.

- `contracts/schemas/model.schema.json` (1,060,581 bytes) and `execution.schema.json` (1,060,585 bytes) hold the same 538 `$defs` and differ only in `$id`; 119 definitions are `Document*`; both carry the registry `x-hyprn-mvp-documents-contract` (`version`, `definitions` naming 118 definitions, `routes`, `bridge`, `runtime_invariants`, `limits`, the operation and extraction transitions, `collection_protocol`, the scientific allocations, `extraction_reconciliation`, `operation_commit_authorities`). Their `$comment` asks for a hand copy of `$defs`, and about a dozen assertions across the contract, application and modeling tests check that the two files agree.
- The attested modules validate through two entries of `contracts`: `validate_execution` (one caller, `execution_bundle.validate_bundle_shape`, definition `ExecutionBundleRead8`, read from `execution.schema.json`) and `validate` (model file, a validator per definition built at import), reached from `execution_bundle.closed`, `approach_closure`, `scientific_configuration` (names computed from a version), `units` (which also reads `SCHEMA['$defs']['UnitDeclaration1']` at import) and `calculation`. The worker validates no JSON schema (standard-library checks), so what "worker admission names" is the launch-path admission in these attested modules. A first count, taking every matching version for the computed names: 43 root names and a `$ref` closure of 167 definitions (about 0.37 MB), 9 of them `Document*`, reached through `EvidenceSnapshot4` and `EvidenceRecord4` → `DocumentCitation1`.
- 11 `Document*` definitions are referenced by non-Documents definitions (`EvidenceCreate4`, `EvidenceRevise4`, `EvidenceRecord4`, `EvidenceSnapshot4`, `EvidenceCitationPreviewRequest4`, `EvidenceCitationPreview4`); the other 108 reference only each other and `Error`. In file order, Documents definitions are interleaved with the evidence-4 and configuration-5 definitions.
- Both schema paths are in `launcher.execution_source_hashes()` (a 25-entry reviewed literal, 34 entries with the patches; task 2.3 adds `installation.py`), whose native part mirrors `modeling_runtime.source_hashes()`. The modeling image reads a byte copy of `model.schema.json` as `config/modeling.schema.json`, which is in every prepared artifact's patched inventory and so in its `adapter_digest`. The application image inventory (`application_runtime.hashes()`) globs `contracts/schemas/`.
- Prepared artifacts record `provenance/support/schema-identities.json` (`schema_version` "1"; path, SHA-256 and size of each `SCHEMA_IDENTITY_SOURCES` entry, today both schema files). No reader compares those rows with current files: `execution_bundle.validate_provenance` and the worker's provenance check verify recorded rows against the artifact's own bytes and its generator identity. Only `test_artifacts_record_schema_identities_instead_of_schema_copies` compares the captured fixture with current files. The golden identity corpus holds older bundles that carry schema copies under `provenance/support/`.
- `application/generate_contract.py` copies every `$defs` entry, in file order, into `contracts/hyprn-mvp.openapi.yaml` (and through `ui/generate_types.py` into `ui/src/contract.ts`), so the Documents definitions are part of the public contract.
- Task 2.8's release work edits `deployment/execution_runtime.py` and `deployment/modeling_runtime.py` (execution-inventory files and modeling image inputs), so the split (task 2.8c) rides 2.8's single worker re-attestation and modeling rebuild instead of adding one.
- Variant for option a, listed for the answer and not recommended: drop `model.schema.json` from the execution inventory because the launch path no longer reads it. That inventory deliberately mirrors the modeling image inputs (the producer of every executed program); narrowing it is a security-scope change for the Phase 5 review, not part of this refactor.

</context>

<options>
<option id="option-a"><name>Move the Documents-only definitions; keep the shared citation vocabulary in the model schema (recommended)</name><pros>`documents.schema.json` takes the 108 Documents-only definitions and the registry; `model.schema.json` keeps every other definition (including the 11 `Document*` definitions that evidence-4 records reference), stays closed under `$ref` and remains the self-contained schema the modeling service reads; definition bodies keep their local `#/$defs/` references and stay byte-identical; Documents-only changes (most of Phase 4) no longer re-attest the worker or rebuild the modeling image; the execution inventory keeps its path list</pros><cons>The 11 shared citation definitions stay on the attested and modeling path, so changing them still re-attests (as it must, because attested records reference them); "Documents definitions in one file" has that exception</cons></option>
<option id="option-b"><name>Move all 119 `Document*` definitions</name><pros>No exception to "Documents definitions in one file"</pros><cons>`model.schema.json` is no longer closed under `$ref`, so the staged modeling schema must become a second generated file that includes Documents definitions; `documents.schema.json` then stays a modeling image input and Documents-only changes still rebuild the modeling image</cons></option>
<option id="option-c"><name>Do item 7 only (2.8b), drop 2.8c and move the split to Phase 4 task 4.37's re-attesting window</name><pros>Phase 2 carries no schema change</pros><cons>Phase 4 tasks 4.32 and 4.34 keep editing both hand-synced files and each re-attests; this plan's schema must_haves and the Phase 3 and Phase 4 plans must be changed back</cons></option>
</options>

<read_first>

- `.planning/codebase/FACTORIZATION.md` item 11; `contracts/README.md`; `contracts/documents.md` (first paragraph, "Exact scientific pairings")
- `application/src/hyprn_mvp_app/contracts.py`, `units.py`, `execution_bundle.py` (`closed`, `validate_bundle_shape`, `validate_provenance`), `approach_closure.py`, `scientific_configuration.py`; `integration/src/hyprn_mvp_integration/launcher.py` (`execution_source_hashes`), `calculation.py`
- `deployment/modeling_runtime.py` (`source_hashes`, `SCHEMA_IDENTITY_SOURCES`, `schema_identities`, `stage_native_inputs`), `deployment/application_runtime.py` (`hashes`); `application/generate_contract.py`
- `application/tests/test_module_boundaries.py` (`ATTESTED_PROJECT_FILES`, the attested-closure tests, `FAIL_CLOSED_PROBE`); `integration/tests/test_fuel_native_provenance.py`; `integration/tests/fixtures/README.md`

</read_first>

<action>

- **Goal:** before any attested file changes, the product owner sees the exact split, computed on the current tree, and approves it (D-11, PD-2.4).
- **Depends on:** 2.5, 2.6, 2.7 (the facts are computed on the tree they leave). Runs before 2.8b and 2.8c.
- **Steps:**
  1. Read-only (no repository file changes; a scratch script outside the repository is allowed). Write into the checkpoint `phases/02-local-edition/checkpoints/2.8a.md`, in full (names, not only counts):
     a. the root list: every definition name an attested module passes to `validate`, `closed` or `validate_execution` or reads from the schema, with computed names enumerated per version and each call site named;
     b. the generated closure: names, count and byte size, and the `Document*` definitions it contains;
     c. for each option, the move list (definitions and registry), what stays and why;
     d. for each option, the inventories before and after: the `execution_source_hashes()` literal and total, `ATTESTED_PROJECT_FILES`, `modeling_runtime.source_hashes()`, `SCHEMA_IDENTITY_SOURCES` and the schema entries of `application_runtime.hashes()`;
     e. the compatibility rule: which identities a newly prepared artifact records; that earlier artifacts keep theirs and stay admissible (no reader compares recorded identities with current files, re-derives or rewrites them); which pre-split captured artifact is preserved byte for byte as the historical sample and the repository size it adds; and, if the recorded set of schema paths changes, the new record `schema_version` and that readers accept every earlier one;
     f. the cost: one worker re-attestation and one modeling rebuild, producer re-pin and fixture recapture, all already forced by 2.8's release work.
  2. Present options a (recommended), b and c with these facts.
  3. The orchestrating session records the answer as one line starting `PD-2.4 answer:` (option, any change to the listed split, who answered, when), followed by the approved lists that 2.8c implements.

</action>

<acceptance_criteria>

- The checkpoint holds exactly one `PD-2.4 answer:` line and the approved root list, closure, move list, inventories before and after, and compatibility rule written out in full.
- No repository file outside the planning directory changed.

</acceptance_criteria>

<verify>
<automated>grep -c "^PD-2.4 answer:" .planning/phases/02-local-edition/checkpoints/2.8a.md</automated>
<fails_when>prints 0, or more than 1: no single recorded answer</fails_when>
<automated>git status --porcelain -- application contracts deployment editions integration modeling ui upstream</automated>
<fails_when>prints any path: the decision step changed a repository file</fails_when>
</verify>

<resume-signal>The product owner answers "a", "b" or "c", with any change to the listed split; the orchestrating session records it as the `PD-2.4 answer:` line.</resume-signal>

<done>The decision is recorded, and the checkpoint `phases/02-local-edition/checkpoints/2.8a.md` names the answer, who gave it and when, and holds the full approved lists that task 2.8c implements.</done>

</task>

### Task 2.8b — Dynamic-loading allowlist keyed by function

<task type="auto" id="2.8b">

<name>Task 2.8b — Dynamic-loading allowlist keyed by function</name>

<read_first>

- `.planning/codebase/FACTORIZATION.md` item 7
- `application/tests/test_module_boundaries.py` (`DYNAMIC_ALLOWLIST`, `dynamic_loading`, `test_attested_modules_load_no_code_dynamically_outside_the_reviewed_allowlist`, `test_dynamic_loading_scanner_detects_every_banned_form`)
- `integration/src/hyprn_mvp_integration/calculation.py` (`ScalarCalculation.define.validate_inputs`, `ScalarParser.parse`), `integration/src/hyprn_mvp_integration/worker.py` (`load_program`)

</read_first>

<files>

`application/tests/test_module_boundaries.py` only. Test-only: no attested file, schema or inventory changes.

</files>

<action>

- **Goal:** the boundary test pins each reviewed dynamic-loading seam of the attested modules by `(path, enclosing function, callee, count)` instead of by line, so edits elsewhere in an attested file leave it unchanged while any new, removed or moved dynamic call still fails it (D-11, FACTORIZATION item 7).

- **Depends on:** 2.3 (the previous editor of `test_module_boundaries.py`). Runs in wave 4 after 2.8a (it does not need the answer) and lands before 2.8c, the first task that edits attested files.

- **Steps:**
  1. Record the current `DYNAMIC_ALLOWLIST` entries and the `locality-contracts` pass count.
  2. `dynamic_loading(path)` reports each construct with its qualified enclosing function (`<module>` at module level, `Class.method`, `outer.inner`); the attested-modules test compares entries `(path, enclosing function, callee, count)` with `DYNAMIC_ALLOWLIST`, exactly both ways (unreviewed and stale entries reported).
  3. Replace the line-number cross-checks with function-scoped ones: each allowlisted `__import__` takes the literal `'hashlib'`; `load_program` holds the single `spec_from_file_location('_hyprn_mvp_frozen_entry', …)` call and the `module_from_spec` and `exec_module` calls on that spec.
  4. Add keyed-scanner cases on scratch sources: lines inserted above an allowlisted call leave the entries unchanged; a second call in the same function changes its count; the call moved to another function changes its key; a module-level call is keyed `<module>`. Test names state the invariant (line drift outside a reviewed seam keeps the allowlist; a new or moved dynamic call fails it).
  5. Expected entries on the current tree: `calculation.py` `ScalarCalculation.define.validate_inputs` `__import__` 1; `calculation.py` `ScalarParser.parse` `__import__` 1; `worker.py` `load_program` `spec_from_file_location` 1, `module_from_spec` 1 and `exec_module` 1. The comment above the allowlist states the invariant, not the change.

- **Risks:** the keyed scanner missing a construct the line-keyed one caught (every existing banned-form case stays and passes); nested functions and methods qualified inconsistently (cases for both).

</action>

<acceptance_criteria>

- The task's commits change only `application/tests/test_module_boundaries.py`.
- `DYNAMIC_ALLOWLIST` holds exactly the function-keyed entries the checkpoint lists beside the old line-keyed ones; the line-drift case passes the scan; the second-call and moved-seam cases fail it; every existing banned-form case is still detected.

</acceptance_criteria>

<verify>
<automated>`./hyprn-mvp dev check locality-contracts`</automated>
<fails_when>the group fails, or its pass count differs from the count recorded in step 1 by anything other than the added scanner cases</fails_when>
<automated>`git diff --name-only "$BASE"..HEAD`, with `BASE` the commit this task started from</automated>
<fails_when>prints any path other than `application/tests/test_module_boundaries.py`</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.8b.md` records the old and new allowlist entries side by side and the `locality-contracts` counts before and after; it is verified by the orchestrating session.</done>

</task>

### Task 2.8c — Contract schemas split by consumer

<task type="auto" id="2.8c">

<name>Task 2.8c — Contract schemas split by consumer</name>

<precondition>Checkpoint `phases/02-local-edition/checkpoints/2.8a.md` holds the `PD-2.4 answer:` line and the approved lists, and checkpoint 2.8b is verified.</precondition>

<read_first>

- `phases/02-local-edition/checkpoints/2.8a.md` (PD-2.4 answer and approved lists); `.planning/codebase/FACTORIZATION.md` item 11; `phases/01-repository-baseline/checkpoints/1.8.md` ("Left unchanged and listed for review": the wording for comments in attested sources)
- `application/src/hyprn_mvp_app/contracts.py`, `units.py`, `execution_bundle.py`, `approach_closure.py`, `scientific_configuration.py`, `modeling.py` (aliases); `application/generate_contract.py`, `ui/generate_types.py`
- `application/tests/test_module_boundaries.py` (`ATTESTED_PROJECT_FILES`, the attested-closure and inventory-count tests, `FAIL_CLOSED_PROBE`, `MOVED`)
- `contracts/README.md`, `contracts/documents.md`, the `$comment` and registry of `contracts/schemas/*.json`, `contracts/tests/` (the mirror assertions and the file pins in `test_unit_declaration_contracts.py`), `contracts/tests/documents_prior_definitions.json`
- `integration/src/hyprn_mvp_integration/launcher.py` (`execution_source_hashes`), `integration/src/hyprn_mvp_integration/computational_export.py` (`sensitive`), `integration/src/hyprn_mvp_integration/worker.py` (`verify_unit_catalog`); `deployment/modeling_runtime.py` (`source_hashes`, `SCHEMA_IDENTITY_SOURCES`, `schema_identities`, `stage_native_inputs`), `deployment/application_runtime.py` (`hashes`)
- `integration/tests/test_fuel_native_provenance.py`, `integration/tests/execution_fixtures.py`, `integration/tests/fixtures/README.md`, `integration/tests/test_documents_native.py`, `application/tests/test_identity_golden.py`, `deployment/tests/test_attestation.py`

</read_first>

<files>

- create `contracts/schemas/documents.schema.json`, `application/generate_execution_schema.py`, `contracts/tests/definition_body_digests.json` (pre-split record), `contracts/tests/test_schema_sources.py` (added to the `contracts` group), `application/tests/test_retained_schema_identities.py` (added to the `units-bundle` group);
- modify `contracts/schemas/model.schema.json`, `contracts/schemas/execution.schema.json` (generated), `contracts/README.md`, `contracts/documents.md`, `contracts/tests/` (mirror assertions, reads through `contracts`, the file pins in `test_unit_declaration_contracts.py` where a pinned file changes, the purpose text of `documents_prior_definitions.json`);
- the attested `application/src/hyprn_mvp_app/contracts.py`, `units.py`, `execution_bundle.py` (comments only) and `integration/src/hyprn_mvp_integration/launcher.py` (inventory per PD-2.4, comment); the rest of the attested set (worker, calculation, results and every other file of `ATTESTED_PROJECT_FILES` and the `execution_source_hashes()` literal) for review-code comments and the format-only commits of step 12; the `style-ratchet` configuration (the attested-set exclusion removed);
- `application/src/hyprn_mvp_app/modeling.py` (the `SCHEMA` and `VALIDATORS` re-export removed), `application/generate_contract.py`, `application/tests/test_approach_closure.py` and `application/tests/test_fuel_platform.py` (read definitions through `contracts`), `application/tests/test_module_boundaries.py` (alias rows, root coverage, launch-path schema probe, inventory counts);
- `deployment/modeling_runtime.py` (`SCHEMA_IDENTITY_SOURCES`, `source_hashes`, the staged modeling schema, per PD-2.4), `deployment/tests/test_attestation.py`, `deployment/tests/test_deployment_hardening.py`, `deployment/tests/test_modeling_isolation.py`;
- `integration/tests/test_fuel_native_provenance.py`, `integration/tests/test_documents_native.py`, the other schema readers under `application/tests/`, `integration/tests/` and `modeling/tests/` (read path only), the preserved pre-split sample under `integration/tests/fixtures/` (as approved at 2.8a);
- `deployment/checks.py` (the `contracts` and `units-bundle` group targets; their entry files under `deployment/groups/` once Phase 4 task 4.4 has landed); `modeling/provenance.md` (attested; only if the recorded schema set changes).

</files>

<action>

- **Goal:** each contract definition is authored once; the attested launch path reads only a generated execution schema that is exactly the closure of what the attested modules name; Documents-only definitions and the registry leave the attested and modeling path; no schema file is kept in sync by hand (D-11, PD-2.4 as answered, FACTORIZATION item 11).

- **Depends on:** 2.8a (answer recorded) and 2.8b.

- **Attestation:** this task rebuilds and re-attests nothing. Its first edit to an attested file or inventory schema makes the development attestation stale, and from then until task 2.8 re-attests, the re-attestation window of "Cross-phase coordination" applies. Groups that need the attested worker, a modeling image built from the current sources or the recaptured native fixture (`units-attestation`, `units-launcher`, `units-worker`, `units-model`, `ae-model`, `approach-bundle`, `approach-worker`, `bridge-history`, `modeling-isolation`, `fuel-native-provenance`, `units-native`, `native-a`) are not run here: step 1 records their counts before the first edit, and task 2.8 runs them after its re-attestation and recapture. `fuel-native-provenance` is among them because `test_artifacts_record_schema_identities_instead_of_schema_copies` compares the captured fixture's recorded identities with the current schema bytes until 2.8 recaptures. The checkpoint lists the pending groups.

- **Steps:**
  1. Before any edit, record: the canonical-body digest of every definition (name → SHA-256 of its canonical JSON) in `contracts/tests/definition_body_digests.json`, committed before the split; the SHA-256 of `application/tests/fixtures/identity_golden.json`, `contracts/hyprn-mvp.openapi.yaml`, `ui/src/contract.ts` and the captured native fixtures; the inventories of 2.8a step 1d; the pass counts of every group in this task's verify list and of the groups pending for 2.8. The verify list is complete when every module found by `git grep -l 'contracts/schemas' -- '*/tests/*' 'ui/*.py'` belongs to one of its groups or to a pending group. `documents-native-atomicity` and `documents-native-originals` (Docker groups that read Documents definitions) run in this task only if they need neither the attested worker nor the modeling image; if either fails for that reason, it goes on the pending-for-2.8 list with the failure recorded, and any other failure is a failure of this task.
  2. Create `documents.schema.json` (`$id` `https://hyprn-mvp.local/contracts/documents.schema.json`) with exactly the approved moved definitions and the `x-hyprn-mvp-documents-contract` registry, and remove them from `model.schema.json`; definition bodies byte-unchanged; each `$comment` says which file is authored and that the execution schema is generated and never edited by hand.
  3. `contracts` (attested) no longer reads `model.schema.json` at import. The module-level `SCHEMA` and `VALIDATORS` are removed, together with the `modeling.py` re-export and its `MOVED` alias rows in `test_module_boundaries.py`; their importers (`application/generate_contract.py`, `application/tests/test_approach_closure.py`, `application/tests/test_fuel_platform.py`) use `contracts.definitions()` (the authored definitions in source order, loaded on first call) and `contracts.validator(name)`. `validator(name)` returns the compiled validator for any definition wherever it is authored: a name in the reviewed literal of launch-path roots resolves only from `execution.schema.json`, every other definition from the authored files (one definition namespace, names disjoint), loaded on first use. `validate` and `validate_execution` keep their signatures and behaviour. `units` computes its physical-unit set from `contracts.definition('UnitDeclaration1')`, a root read from the attested `execution.schema.json`, so importing `units` opens no other schema file. These two changes are what make the launch-path `open` probe of step 5 hold. Every other reader of definitions or of the registry (the contract tests, `integration/tests/test_documents_native.py` and any Documents code already merged) goes through `contracts`.
  4. `application/generate_execution_schema.py` (standard library and `contracts`; `--check` exits 1 on any difference) writes the closure of the root list, definitions in source order, `$id` kept; regenerate `execution.schema.json`.
  5. `contracts/tests/test_schema_sources.py`: the committed execution schema equals the closure byte for byte; authored names are disjoint and every `#/$defs/` reference resolves; `model.schema.json` is closed under references (option a); every registry definition resolves through `contracts.validator`; `test_definition_bodies_equal_the_pre_split_digests` compares every definition body with `definition_body_digests.json` (none changed, lost or added). In `test_module_boundaries.py`: every definition name an attested module passes to `validate`, `closed` or `validate_execution` or reads through `contracts.definition` is a root (literal names directly, computed names through a reviewed enumeration, wrapper parameters through their call sites; a name the scan cannot resolve fails); a fresh-interpreter probe with an `open` audit hook imports `launcher`, `calculation`, `results` and `units` and compiles the validator of every root, and the only `contracts/schemas/` file it opens is `execution.schema.json`.
  6. The model/execution hand sync disappears: each test assertion that the two files or their `$defs` are equal is replaced by the generated-equals-closure test, and a test reading a definition from `execution.schema.json` outside the closure reads it through `contracts`; the checkpoint lists each replaced assertion beside its replacement. `contracts/tests/test_assumptions_evidence_contracts.py` (whole-file pin) and `contracts/tests/test_approach_contracts.py` (prefix and definition pins) are pinned in `test_unit_declaration_contracts.py`: a change to either updates its pin in the same commit, with the reason.
  7. Public contract: `application/generate_contract.py` takes the definitions from `contracts.definitions()` in the current order; regenerating `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts` reproduces the committed files byte for byte (neither file is committed by this task).
  8. Inventories equal the lists approved at 2.8a: the `execution_source_hashes()` literal, `ATTESTED_PROJECT_FILES`, the inventory-count assertions and the fail-closed probe in `test_module_boundaries.py`, `modeling_runtime.source_hashes()`, `SCHEMA_IDENTITY_SOURCES` and the staged modeling schema, and the inventory tests in `deployment/tests/test_attestation.py` (run by `units-attestation` in task 2.8), `test_deployment_hardening.py` and `test_modeling_isolation.py` (run by `modeling-isolation` in task 2.8); a test asserts that `documents.schema.json` is in the application image inventory and in no execution or modeling inventory.
  9. Historical prepared artifacts: preserve the pre-split captured artifacts byte for byte as approved at 2.8a (SHA-256 recorded in the checkpoint). Add `test_artifact_prepared_with_earlier_schema_identities_stays_admissible` in the new module `application/tests/test_retained_schema_identities.py`, added to the `units-bundle` group (application interpreter, no Docker, no attested worker; it reads only the preserved capture, never the recaptured fixture), so it runs in this task. On the preserved pre-split artifact: (i) the recorded `provenance/support/schema-identities.json` names the pre-split identities (literal SHA-256 and sizes taken from the checkpoint), and they differ from the current `modeling_runtime.schema_identities()`; (ii) the application admission (`execution_bundle.validate_preparation`, which runs `validate_provenance`), the retained-bundle admission (`validate_retained_bundle` on a bundle assembled from it) and the worker's provenance check (`verify_unit_catalog` in `integration/src/hyprn_mvp_integration/worker.py`, standard library only, called in a fresh subprocess as the boundary tests already do, so `hyprn_mvp_integration.worker` and `launcher` are never imported into the shared `units-bundle` pytest process) accept it; the existing assertion of `test_exact_frozen5_bundle6_private3_retains_originals` in `application/tests/test_unit_execution_admission.py` that the worker and launcher are not imported stays unchanged; (iii) afterwards the artifact bytes, its recorded identity file and its `generator_identity` digests are unchanged, so no reader re-derives or substitutes current schema content. The export content check needs the native interpreter (`integration/src/hyprn_mvp_integration/computational_export.py` imports AiiDA), so `test_historical_artifact_passes_the_export_content_check` (`sensitive` in that module accepts every provenance file of the preserved artifact) goes into `integration/tests/test_fuel_native_provenance.py` and runs with that group in task 2.8. `test_artifacts_record_schema_identities_instead_of_schema_copies` keeps asserting that a newly prepared artifact records the current identities; it holds again after 2.8's recapture.
  10. Documentation: `contracts/README.md` (which file is authored, which is generated and how to regenerate and check it, which is attested); `contracts/documents.md` (the sentence about identical Documents definitions in both files); `modeling/provenance.md` only if the recorded schema set changes.
  11. In the same commit series, rewrite the comments in attested sources that still cite review codes, with the wording of checkpoint 1.8 (`contracts.py`, `execution_bundle.py`, `units.py`, `launcher.py`, and every other attested source that cites one): the pending item STATE assigns to the re-attesting release work.
  12. Formatting of the pinned execution sources (D-13): as the last commits of the series, after every other attested edit of this task, run the formatter of task 2.1a over exactly the attested set (`ATTESTED_PROJECT_FILES` and the `execution_source_hashes()` literal as approved at 2.8a), one format-only commit per component, no other change in those commits; the development attestation is already stale (see "Attestation"), and 2.8 re-pins and re-attests the formatted bytes in its single step. Remove the attested-set exclusion from the `style-ratchet` configuration in the same commit as the first reformat, so the ratchet covers these files from then on; hash-pinned test files stay excluded. Record in the checkpoint, per file, the formatter's AST-equivalence result (the module's parsed syntax tree before and after, ignoring comments and docstring line wrapping) and the attested-source SHA-256 before and after.
  13. No WhatsOpt patch changes (AGPL scope): the schema copy inside `040-modeling-contract.patch` stays, and the build keeps overwriting it with the staged file.

- **Risks:** the launch path silently depending on a non-attested schema (root-coverage scan and the `open` audit probe); a definition body or the public contract drifting during the move (digest map, byte-identical regeneration); the merge order of the interleaved Documents definitions (source order kept); pinned contract test files (pin updated in the same commit); historical artifacts refused or re-identified (step 9); Documents code merged before this task still reading the registry from `model.schema.json` (moved to `contracts` in the same commit); groups left unverified until 2.8 (listed with their pre-edit counts); a formatter change inside a string literal or a test that pins attested source bytes (the AST comparison and the pin updates in the same commits).

</action>

<acceptance_criteria>

- `application/generate_execution_schema.py --check` exits 0; the root-coverage scan and the launch-path `open` probe pass; the authored files hold exactly the approved definitions; no test asserts that two schema files are equal; `contracts` reads no schema file at import.
- Every definition body equals its pre-split canonical digest; `application/tests/fixtures/identity_golden.json` is unchanged; regenerated `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts` are byte-identical to the committed files.
- The inventories equal the lists approved at 2.8a; `documents.schema.json` is in the application image inventory and in no execution or modeling inventory.
- `test_artifact_prepared_with_earlier_schema_identities_stays_admissible` passes in `units-bundle` on the preserved pre-split artifact.
- Every attested source is formatted by the task 2.1a formatter in format-only commits; each file's syntax tree is unchanged by them; `style-ratchet` passes with no attested-set exclusion.
- No rebuild, re-pin, recapture or re-attestation happens in this task; the checkpoint lists the groups pending for 2.8 (including `fuel-native-provenance` and any Documents native group moved there under step 1) with their pre-edit counts.

</acceptance_criteria>

<verify>
<automated>`python3 -B application/generate_execution_schema.py --check`</automated>
<fails_when>exits non-zero: the committed execution schema is not the closure of the root list</fails_when>
<automated>`./hyprn-mvp dev check contracts`, `locality-contracts`, `documents-contracts`, `documents-citation-contracts`, `approach-contracts`, `ae-contracts`, `units-contracts`, `ae-generated`, `ae-public`, `projection`, `units-bundle`, `units-guards`, `units-staging`, `approach-closure`, `fuel-platform`, `deployment-hardening`, `guard`, `combined-static`, `documents-native-atomicity` and `documents-native-originals` (under the step-1 rule), plus the groups task 1.11 registers for `contracts/tests/test_modeling_contract.py`, `test_native_program_contract.py`, `test_ui_discovery_contract.py`, `test_contract_boundaries.py`, `application/tests/test_public_contract.py`, `test_scoped_evidence.py`, `test_ui_discovery.py` and `modeling/tests/test_ui_discovery.py` (named from the 1.11 checkpoint), each with counts before and after</automated>
<fails_when>any group fails, except a Documents native group that fails only because it needs the attested worker or the modeling image (then it is on the pending-for-2.8 list with that failure recorded); a count changes without a listed added, replaced or removed test; `test_artifact_prepared_with_earlier_schema_identities_stays_admissible` is not among the passed `units-bundle` cases; a module found by the step-1 `git grep` belongs to no listed or pending group</fails_when>
<automated>`application/generate_contract.py --output <scratch>/openapi.yaml` and `ui/generate_types.py --input <scratch>/openapi.yaml --output <scratch>/contract.ts`, each compared with `cmp` against `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts`; `python3 ui/check_ui_contract.py`</automated>
<fails_when>`cmp` reports a difference or the checker fails: the split changed the public contract</fails_when>
<automated>`git diff --exit-code "$BASE"..HEAD -- application/tests/fixtures/identity_golden.json contracts/tests/definition_body_digests.json`, with `BASE` the commit before the split (the digest record is committed first); `./hyprn-mvp dev check contracts`, which runs `test_definition_bodies_equal_the_pre_split_digests`</automated>
<fails_when>either file changed after the split started, or `test_definition_bodies_equal_the_pre_split_digests` is not among the passed `contracts` cases: a definition body changed, appeared or disappeared</fails_when>
<automated>`git diff --name-only "$BASE"..HEAD -- deployment/pins.json integration/tests/fixtures/native-programs.json.gz`</automated>
<fails_when>prints a path: this task re-pinned or recaptured, which belongs to the single rebuild in task 2.8</fails_when>
<automated>for each attested file, compare the syntax tree (`ast.dump` without attributes) of the version before the first format-only commit with the committed version; `./hyprn-mvp dev check style-ratchet`; `git log --format=%s "$BASE"..HEAD -- <attested files>` for the format-only commits</automated>
<fails_when>any tree differs (the formatter changed behaviour), `style-ratchet` still excludes an attested file, or a format-only commit touches anything beyond whitespace, line wrapping, quoting and trailing commas</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.8c.md` records the split as implemented against the 2.8a lists, the definition-body digest map, the replaced mirror assertions, the inventories before and after, the group counts before and after, the groups pending for 2.8 with their pre-edit counts and the SHA-256 of the preserved pre-split sample; it is verified by the orchestrating session.</done>

</task>

### Task 2.8 — Release snapshot and checkout-mode binding

<task type="auto" id="2.8">

<name>Task 2.8 — Release snapshot and checkout-mode binding</name>

<precondition>Checkpoint `phases/02-local-edition/checkpoints/2.8c.md` is verified; the development attestation is stale from 2.8c until this task re-attests.</precondition>

<read_first>

- `phases/02-local-edition/checkpoints/2.8a.md` (approved inventories) and `2.8c.md` (groups pending for this task with their pre-edit counts, the preserved pre-split sample)
- `deployment/release_binding.py` and its importers (`deployment/application_runtime.py`, `dispatch_runtime.py`, `execution_runtime.py`, `modeling_runtime.py`, `native_environment.py`, `deployment/tests/scoped_fixture_launcher.py`, `deployment/tests/test_deployment_hardening.py`); `deployment/checks.py`
- `integration/src/hyprn_mvp_integration/launcher.py` (`execution_source_hashes`, `fingerprint`, `require_attestation`); `deployment/tests/test_attestation.py`; `deployment/pins.json` (`modeling_producer`); `integration/tests/capture_native_programs.py`, `integration/tests/fixtures/README.md`

</read_first>

<files>

`deployment/release_binding.py` → `deployment/release.py`, `deployment/tests/test_release.py` (group `release`), importers in the managers (including the execution-inventory files `deployment/execution_runtime.py` and `deployment/modeling_runtime.py`) and `deployment/checks.py`, the launch-worker wrapper text and pattern; after the single rebuild, `deployment/pins.json` (producer pin) and the native fixtures recaptured under the STATE rule for a modeling-source change, never overwriting the pre-split sample 2.8c preserved.

</files>

<action>

- **Goal:** installs run exactly the committed snapshot they were attested for; this task also closes the re-attestation window that 2.8c opened, with the single rebuild and re-attestation of D-11.

- **Depends on:** 2.5, 2.6, 2.7 and 2.8c.

- **Steps:**
  1. Implement "Checkout mode"; the dispatch container's source inventory check compares hashes read inside the image with the manifest; port every binding test, then add: a dirty tree is warned about and its changes not installed; a modified snapshot file makes bind refuse; another release's launch-worker is refused; a module imported from the checkout instead of the snapshot is refused; `require_review` without a review record is refused.
  2. Re-attestation, once, after the last attested edit: rebuild the worker and modeling images from the committed tree through the reviewed manager rebuild for the development fixture roots; attest once; apply the STATE rule for a modeling-source change (new `modeling_producer` pin, fixture recapture) without touching the preserved pre-split sample; record the attested inventory before (the one attested before 2.8c) and after (path → SHA-256), and the image and attestation identities.
  3. Run the groups 2.8c left pending and compare each count with its pre-edit count.

- **Risks:** this is the security-critical start path (reviewed specifically in Phase 5); losing the wrapper-equality protection (its test is ported unchanged); the stale-attestation window closes only here ("Cross-phase coordination"); a recapture overwriting the historical sample (its SHA-256 compared with 2.8c's record).

</action>

<acceptance_criteria>

- Every ported release-binding assertion is listed beside its original, none dropped, and the five new refusal cases pass.
- The worker is re-attested exactly once in this task; the attested inventory equals the list approved at 2.8a and is recorded before and after.
- Every group 2.8c left pending passes; each count equals its pre-edit count or the change is explained by a listed added, replaced or removed test.
- The preserved pre-split sample is byte-unchanged.

</acceptance_criteria>

<verify>
<automated>`./hyprn-mvp dev check release`, `deployment-hardening`, `guard`, `units-attestation` and `native-environment`</automated>
<fails_when>any group fails, or the checkpoint lacks a ported assertion beside its original</fails_when>
<automated>After the single rebuild, re-attestation and recapture: `./hyprn-mvp dev check units-attestation`, `units-launcher`, `units-worker`, `units-model`, `ae-model`, `approach-bundle`, `approach-worker`, `bridge-history`, `modeling-isolation`, `fuel-native-provenance`, `units-native` and `native-a`, and any Documents native group 2.8c moved to its pending list</automated>
<fails_when>any group fails; `test_artifacts_record_schema_identities_instead_of_schema_copies` or `test_historical_artifact_passes_the_export_content_check` is not among the passed `fuel-native-provenance` cases; a count differs from 2.8c's pre-edit count without a listed added, replaced or removed test; the attested inventory differs from the list approved at 2.8a; more than one re-attestation is recorded; the preserved pre-split sample's SHA-256 differs from 2.8c's record</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.8.md` records every ported release assertion beside its original, the attested inventory before and after with the single re-attestation's image and attestation identities, the new producer pin, and the pending groups' counts before and after; it is verified by the orchestrating session.</done>

</task>

### Task 2.9 — CLI foundation: output, prerequisites, wizard, doctor, status

<task type="auto" id="2.9">

<name>Task 2.9 — CLI foundation: output, prerequisites, wizard, doctor, status</name>

<files>

`editions/local/src/hyprn_mvp_local/{cli,output,prereqs,wizard,doctor,status}.py`, `editions/local/tests/{test_wizard,test_doctor,test_output,test_prereqs}.py` (group `local-cli`).

</files>

<action>

- **Goal:** the CLI has one output envelope and exit-code scheme, checks prerequisites per OS, asks the first-run questions with safe defaults, and reports state read-only through `doctor` and `status`.

- **Steps:** global behaviour, JSON envelope and exit codes; prerequisites per OS (architecture; git; Docker CLI and reachable engine and its kind; engine memory at least 6 GiB, warning below 8; free disk at least 20 GiB, warning below 30; port free; checkout not synced; on Linux, daemon access without `sudo`); the first-run wizard (data folder, port, owner name) with non-interactive flags `--data-dir`, `--port`, `--owner`, `--yes`; atomic configuration write (0600 in 0700); read-only `doctor` and `status`.

- **Risks:** engine detection differences (Docker context endpoint plus `docker info`; unknown engines reported as unqualified).

</action>

<verify>
<automated>

`./hyprn-mvp dev check local-cli` (table-driven refusals with a temporary `HOME`, envelope, exit codes); `./hyprn-mvp status --json` without a configuration exits 2 with `reason_code=not_installed`; `./hyprn-mvp doctor --json` on the development host exits 0 or 5 with reasons and lists unlabelled resources that look like HYPRN MVP resources as foreign.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.9.md` is verified by the orchestrating session.</done>

</task>

### Task 2.10 — OS adapters: credential store, clipboard, browser

<task type="auto" id="2.10">

<name>Task 2.10 — OS adapters: credential store, clipboard, browser</name>

<files>

`editions/local/src/hyprn_mvp_local/{credentials,clipboard,browser}.py`, `editions/local/tests/{test_credentials,test_clipboard,test_browser}.py` (group `local-adapters`), `editions/local/src/hyprn_mvp_local/doctor.py` (availability lines).

</files>

<action>

- **Goal:** secrets, the clipboard and the browser are reached through one adapter each per OS, with secrets only on standard input and a safe fallback where a facility is missing.

- **Steps:**
  1. Credential store per D-10: `store`, `read`, `delete`, `list` for items keyed by service `hyprn-mvp` and account `<installation_id>:<name>`; secrets only on standard input; macOS through `/usr/bin/security -i`, with a scratch keychain for tests (`HYPRN_MVP_KEYCHAIN`); Linux and WSL2 through `secret-tool` when a Secret Service is reachable; otherwise "unavailable" per PD-2.2.
  2. Clipboard: `pbcopy` (macOS), `wl-copy` or `xclip` (Linux), `clip.exe` (WSL2); clear after 90 s only if the content is unchanged; no clipboard → plain fallback that never prints the secret.
  3. Browser opener: `open` (macOS), `xdg-open` (Linux), `wslview` (WSL2); fallback prints the URL.

- **Risks:** credential-store prompts on macOS (item access limited to the system tool; recorded); headless Linux (PD-2.2).

</action>

<verify>
<automated>

`./hyprn-mvp dev check local-adapters`: recorded process arguments never contain a secret; round trip in a scratch keychain on macOS and in a scratch Secret Service session on Linux; "unavailable" path refuses with its explanation; `doctor` reports each adapter.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.10.md` is verified by the orchestrating session.</done>

</task>

### Task 2.11 — `setup`, `start`, `stop`, `open`, `logs`

<task type="auto" id="2.11">

<name>Task 2.11 — `setup`, `start`, `stop`, `open`, `logs`</name>

<files>

`editions/local/src/hyprn_mvp_local/{setup,lifecycle,start,stop,open_ui,logs}.py`, installation-aware entry functions in the deployment managers, `deployment/tests/test_local_lifecycle.py` (group `local-lifecycle`, Docker, scratch); for the store rule of D-12: `application/src/hyprn_mvp_app/store.py` (explicit creating constructor, recorded schema version, ordinary open refusals; the `executescript` on open and the `ALTER TABLE` migration removed), `deployment/initialize_stores.py` (the one place that creates stores and records their versions), `deployment/tests/scoped_fixture.py` (a single helper through which tests create scratch stores), `application/tests/test_store_schema_version.py` (added to the `api-a` group), and the test modules that construct a `Store` (a mechanical switch to the creating helper, listed by `git grep -l 'Store(' -- '*/tests/*'`).

</files>

<action>

- **Goal:** an engineer goes from a fresh clone to a running, attested installation with `setup` and `start`, opens it with `open`, reads logs and stops it without losing data.

- **Steps:** implement the CLI contract rows. Store initialization reuses the managers: modeling setup, application provisioning with `owner_username` and the generated password on standard input, AiiDA profile. `start` refusal codes: `source_changed`, `attestation_stale`, `foreign_port_owner`, `identity_mismatch`, `store_missing`, `store_schema_mismatch` (exit 3). After start, the cross-site request negative check must return 403.
  Store rule (D-12, this task because `setup` and `start` are where stores are initialized and opened): (1) `Store` gains an explicit creating constructor used only by store initialization and the test helper; the ordinary constructor opens an existing store, never creates the file, never runs DDL and never alters a table; (2) the application store records its schema version (`PRAGMA user_version`, set at creation) and `identity.json` records every store's version beside its identity; (3) opening a missing store refuses with `store_missing`, and a recorded version different from the release's expected version refuses with `store_schema_mismatch` and a message that names `./hyprn-mvp setup --reset-data` and says the stored data is not migrated; `status` and `doctor` report each version read-only; (4) `setup --reset-data` follows the CLI contract row: confirmation first (the installation id typed interactively, or `--yes` with `--non-interactive`; neither given → exit 2 and nothing touched), refusal while a launch is active or uncertain, an exact-id and identity-marker check before anything is discarded (foreign roots refused), then fresh stores and a new generated owner password; (5) no migration code is written: the removed `ALTER TABLE` is not replaced; (6) tables owned by other modules (the Phase 3 agent runtime tables) are created only by store initialization, from the DDL the composition root passes to the creating constructor, and count toward the recorded version; `create_app` and ordinary open run no DDL.

- **Risks:** engine memory pressure (doctor check); long first builds (content-tagged images reused); the switch of the many test modules to the creating helper (mechanical, one commit, counts compared before and after); a reset discarding the wrong root (identity marker plus confirmation; foreign roots refused).

</action>

<verify>
<automated>

`./hyprn-mvp dev check local-lifecycle` on a scratch installation: setup → `status` ready → start → `GET /ui/` 200; sign-in with the generated password read from the scratch credentials → negative check 403; create a sentinel study → stop → start → sentinel present and store identities unchanged; a committed change to an attested source in a scratch clone → `start` exits 2 with `source_changed`; teardown leaves nothing labelled with the scratch installation id.

</automated>
<automated>

`./hyprn-mvp dev check api-a` (with `test_store_schema_version.py`) and `local-lifecycle` on a scratch installation: opening a path with no store raises and leaves no file; a store with a changed recorded version makes `start` exit 3 with `store_schema_mismatch`, the message names `setup --reset-data`, and the store bytes are unchanged afterwards; `setup --reset-data` with no confirmation exits 2 and leaves every store untouched, with `--yes --non-interactive` it discards and recreates the stores (the sentinel study is gone, the version matches, `start` succeeds); `git grep -n 'ALTER TABLE' -- application/src/hyprn_mvp_app/store.py` prints nothing and `executescript` appears only in the creating constructor.

</automated>
<fails_when>an ordinary open creates a file or alters a schema, a mismatch starts anyway or its message does not name the reset command, a reset runs without confirmation, or a mismatching store is altered by the refusal</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.11.md` is verified by the orchestrating session.</done>

</task>

### Task 2.12 — `uninstall` and re-adoption

<task type="auto" id="2.12">

<name>Task 2.12 — `uninstall` and re-adoption</name>

<files>

`editions/local/src/hyprn_mvp_local/uninstall.py`, `editions/local/src/hyprn_mvp_local/setup.py` (re-adoption), `deployment/tests/test_local_uninstall.py` (group `local-uninstall`).

</files>

<action>

- **Goal:** an installation can be removed while keeping its data, re-adopted for the same release, or purged only with an exact confirmation.

- **Steps:** implement the `uninstall` row and D-08 re-adoption.

- **Risks:** deleting the wrong folder (identity marker plus exact id; foreign roots refused).

</action>

<verify>
<automated>

`./hyprn-mvp dev check local-uninstall`: uninstall keeps the data root; a second setup with the same release re-adopts with the same installation id and sentinel; a different release is refused with `update_unavailable`; `--purge` without the exact id is refused; a foreign or unmarked root is refused; after `--purge`, no labelled resource, configuration or credential item remains.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.12.md` is verified by the orchestrating session.</done>

</task>

### Task 2.13 — Smoke test and clean-room installs

<task type="auto" id="2.13">

<name>Task 2.13 — Smoke test and clean-room installs</name>

<files>

`editions/local/src/hyprn_mvp_local/smoke.py`, `editions/local/smoke/sellar.json`, `deployment/tests/test_clean_room.py` (opt-in group `clean-room`).

</files>

<action>

- **Goal:** one command proves an installation computes a known answer end to end, and a clean-room harness proves a fresh clone installs on macOS and on Linux with nothing borrowed from the host.

- **Smoke (`./hyprn-mvp test`):** a throwaway installation (own configuration, data root, scratch credential store, free port; images reused by content tag): setup → start → as the generated owner: create a study; author Disc1 `y1 = z1**2 + z2 + x - 0.2*y2_in` and Disc2 `y2 = y1**0.5 + z1 + z2` with `y1` connected from Disc1, all quantities dimensionless, `y2_in` an explicit configuration input (the model is acyclic because coupled solves are not available yet); commit the model version; configuration A `x=1`, `z1=5`, `z2=2`, `y2_in=12`, manual provenance "Sellar and Batill (1996) canonical test point"; submit and wait at most 5 minutes; assert execution completed, `y1 = 25.6` and `y2 = 12.059644256269407` (relative tolerance 1e-12); configuration B `y2_in = 12.058488150612`, assert `y1 = 25.588302369878` and `y2 = 12.058488150624` (relative 1e-9); negative cross-site check; stop; `uninstall --purge --confirm <id>`; assert nothing labelled remains and the real installation's configuration hash and container states are unchanged.

- **Clean room (`./hyprn-mvp dev check clean-room`):** `git clone` of `HEAD` into scratch; `HOME`, `UV_CACHE_DIR`, `HYPRN_MVP_TOOLS_DIR`, `HYPRN_MVP_CONFIG` and the scratch credential store inside scratch, so uv and CPython download fresh; image builds with `--no-cache`; `./hyprn-mvp setup --non-interactive …` → `start` → `test` → `uninstall --purge`; assert that no resolved path in configuration, release or runtime records points outside the scratch tree; record cold-setup and warm-start timings. Run on macOS and on a Linux host (VM or machine with Docker Engine).

- **Risks:** long cold builds (30–45 minutes; run in this task and in Phase 5 only); build-cache sharing (`--no-cache` plus the portability guard).

</action>

<verify>
<automated>

`./hyprn-mvp test` exits 0 on the development host; `./hyprn-mvp dev check clean-room` exits 0 on macOS and on Linux, with both timings recorded.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.13.md` is verified by the orchestrating session.</done>

</task>

### Task 2.14 — Operations documentation and README

<task type="auto" id="2.14">

<name>Task 2.14 — Operations documentation and README</name>

<files>

`docs/operations/{install,cli,troubleshooting,uninstall,development}.md` (with `dependency-audit.md` from 2.1), `README.md` (quick start), `deployment/tools/check_docs.py` (group `docs`).

</files>

<action>

- **Goal:** a new user and a new developer can install, operate, troubleshoot and remove HYPRN MVP from `docs/operations/` alone, and the docs cannot drift from the CLI.

- **Steps:** document prerequisites per OS, the location chain and defaults, first-run questions, every CLI command, refusal codes and their remedies, uninstall and purge, developer setup (`./hyprn-mvp dev check`, scratch roots, test environment variables).

- **Risks:** documentation drifting from behaviour (the `docs` group compares commands and refusal codes with the CLI on every run).

</action>

<verify>
<automated>

`./hyprn-mvp dev check docs`: relative links resolve; every command in `docs/operations/cli.md` appears in `./hyprn-mvp --help` and the reverse; every refusal code emitted by the CLI is documented.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/02-local-edition/checkpoints/2.14.md` is verified by the orchestrating session.</done>

</task>

<threat_model>

## Trust boundaries

| Boundary | Description |
|---|---|
| Internet → setup | uv, CPython, Python packages, gems, npm packages, base images and the WhatsOpt archive enter the installation |
| Owner CLI → local API | The CLI acts as the owner over loopback with the owner's password and the cross-site request token |
| Checkout → installed snapshot | Developer edits must not reach execution without setup and attestation |
| Host executor → worker | Candidate code runs only in the attested restricted container |
| Installation → other containers on the host | Lifecycle commands act only on this installation's labelled resources |

## STRIDE threat register

| Threat ID | Category | Component | Severity | Disposition | Mitigation plan |
|---|---|---|---|---|---|
| T-2-01 | Tampering | Supply chain (uv, CPython, packages, gems, npm, bases, WhatsOpt archive) | high | mitigate | SHA pins in `tools.json` and `upstream.json`, `--require-hashes`, gem lock checked after install, lockfile integrity, digest-pinned bases, fail-closed acquisition, `--network none` outside acquisition (2.1, 2.6, 2.7) |
| T-2-SC | Tampering | New tool or package installs | high | mitigate | Dependency audit record; blocking human checkpoint for uv, CPython and any package absent from the reviewed locks; never auto-approved (2.1, 2.6) |
| T-2-02 | Tampering | Uncommitted or modified checkout code executed | high | mitigate | `git archive` snapshot of committed `HEAD`; manifest verification on bind; start refuses a changed checkout; wrapper equality (2.8, 2.11) |
| T-2-03 | Elevation of privilege | Worker containment regression through configuration or paths | critical | mitigate | Policy only in source; execution-config digest in `runtime.json`; home-denial probe on `host_home`; attestation at setup; two-sided coverage (2.3, 2.11) |
| T-2-04 | Information disclosure | Stores in a synced or shared folder | medium | mitigate | Path-policy refusals for data roots and checkouts (2.1, 2.2) |
| T-2-05 | Information disclosure | Owner password or stored secrets in output, arguments or logs | high | mitigate | Password generated and passed on standard input, 0600 file, clipboard cleared after 90 s; credential store through standard input only; argument-recording tests (2.10, 2.11) |
| T-2-06 | Information disclosure | Owner password read by a same-user process | medium | accept | Local mode is not a security boundary against the logged-in user; documented residual risk |
| T-2-07 | Denial of service / Tampering | Lifecycle commands acting on resources of another installation | high | mitigate | Label-scoped operations; unlabelled resources only listed; no prune commands (2.9, 2.11, 2.12) |
| T-2-08 | Tampering | `uninstall --purge` deleting the wrong data | high | mitigate | Exact installation-id confirmation; identity marker required; foreign roots refused (2.12) |
| T-2-09 | Elevation of privilege | Modeling service gaining a launcher, socket or foreign store | high | mitigate | Mount and compose assertions kept; isolation test (2.4) |
| T-2-10 | Spoofing | Another local process holding the configured port | medium | mitigate | `start` refuses a port not owned by this installation's container (2.11) |
| T-2-11 | Denial of service | Smoke and clean-room runs exhausting disk | medium | mitigate | Disk checks in `doctor`; throwaway installations purged; content-tagged image reuse (2.13) |
| T-2-12 | Tampering / Elevation of privilege | Attested launch path validating against a non-attested schema after the split | high | mitigate | Reviewed root list in `contracts`; generated execution schema equal to the closure (`--check` and a test); root-coverage scan of the attested modules; launch-path `open` audit probe; inventories approved at 2.8a and asserted both ways (2.8a, 2.8c, 2.8) |
| T-2-13 | Tampering | Historical prepared artifacts or records refused, or read with current schema content substituted, after the split | high | mitigate | No reader compares recorded schema identities with current files; admission test on the preserved pre-split artifact; golden identity corpus and every definition body unchanged; byte-identical public contract regeneration (2.8c, 2.8) |
| T-2-14 | Tampering | Dynamic code loading added to an attested module unnoticed | high | mitigate | Allowlist keyed by (path, enclosing function, callee, count), exact both ways; scanner cases for a second call and a moved seam (2.8b) |

</threat_model>

<verification>
- `./hyprn-mvp test` exits 0; `./hyprn-mvp dev check clean-room` exits 0 on macOS and on Linux.
- `./hyprn-mvp dev check qualification` (now including `installation-config`, `portability`, `native-environment`, `upstream`, `release`, `local-cli`, `local-adapters`, `local-lifecycle`, `local-uninstall`, `docs`) exits 0.
- `python3 -B deployment/tools/term_scan.py` exits 0.
- `python3 -B application/generate_execution_schema.py --check` exits 0, and regenerating `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts` reproduces the committed files byte for byte.
</verification>

<success_criteria>
- All five Phase 2 success criteria in `ROADMAP.md` are true.
- Seventeen checkpoints exist (2.1–2.14, the decision checkpoint 2.8a, and 2.8b and 2.8c), each verified before the next dependent task started; the blocking supply-chain checkpoints and the PD-2.4 answer are recorded with the product owner's confirmation.
</success_criteria>

<output>
After task 2.14, write `phases/02-local-edition/02-SUMMARY.md` in the planning directory: identities of locks and images, the attested inventory before task 2.8c and after task 2.8's re-attestation, clean-room timings per OS, refusal codes, and the status of PD-2.1 to PD-2.4.
</output>
