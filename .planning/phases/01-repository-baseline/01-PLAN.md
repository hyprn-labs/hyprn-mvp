---
phase: 01-repository-baseline
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - deployment/
  - application/
  - integration/
  - contracts/
  - modeling/
  - upstream/whatsopt-patches/
  - ui/
  - .claude/skills/hyprn-mvp-ui/SKILL.md
  - AGENTS.md
autonomous: true
requirements: [OPS-02, OPS-04, ADOPT-01, ADOPT-03, UI-01, SEC-01]
must_haves:
  truths:
    - "Every package, contract, CLI-facing name, environment variable, container label, wire and record identifier, fixture, attested-source list, WhatsOpt patch, design token file and UI wordmark uses the hyprn-mvp namespace"
    - "The configured term scans report zero matches on tracked file contents and paths"
    - "No tracked file contains an absolute user-home path, a private-key block or a token-format literal"
    - "Comments, docstrings and test names state the invariant they protect"
    - "The attested execution source set and every pinned digest match the renamed sources; the two-sided coverage test passes"
    - "python3 -B deployment/checks.py --group qualification passes on the development host"
  artifacts:
    - path: deployment/checks.py
      provides: "Test-group runner with group classes, environment needs, --list and the qualification aggregate"
    - path: deployment/tools/term_scan.py
      provides: "Configurable term scan over tracked contents and paths"
    - path: deployment/tests/test_naming_guard.py
      provides: "Structural hyprn-mvp namespace guard (group naming)"
    - path: deployment/tests/test_hygiene_guard.py
      provides: "Home-path, key-block and token-format guard (group hygiene)"
    - path: application/src/hyprn_mvp_app/
      provides: "Application package"
    - path: integration/src/hyprn_mvp_integration/
      provides: "Execution and document integration package"
    - path: contracts/hyprn-mvp.openapi.yaml
      provides: "Public API contract"
    - path: .claude/skills/hyprn-mvp-ui/SKILL.md
      provides: "UI rules for agents working on ui/"
  key_links:
    - from: integration/src/hyprn_mvp_integration/launcher.py
      to: "execution source set pins"
      via: "execution_source_hashes() and the two-sided transitive-coverage test"
    - from: ui/design_tokens.py
      to: design-system/tokens.json
      via: "token generation into ui/src/design/tokens.css"
    - from: deployment/checks.py
      to: "every must-pass group"
      via: "qualification aggregate"
---

# Phase 1: Repository baseline — plan

<objective>
Make the repository build, test and read as one product named `hyprn-mvp`. Every package, contract, identifier, label, fixture, patch, design-token path and wordmark uses the `hyprn-mvp` namespace; every location comes from a flag, a `HYPRN_MVP_*` variable or a neutral default; comments and test names state the invariants they protect; and every must-pass test group passes through the renamed runner on the development host.

Purpose: every later phase (local edition, agent tools, documents, release) builds on names, gates and green groups that no longer need repair.
Output: the renamed tree, the runner `deployment/checks.py` with a `qualification` aggregate, the term scan, the naming and hygiene guards, the UI skill, and ten task checkpoints.
</objective>

## How this plan is executed

- One numbered task per fresh executor context, in the wave order below. A task starts only after the orchestrating session has verified the previous task's checkpoint.
- Each task stages explicit paths only and ends with atomic commits plus a checkpoint file `phases/01-repository-baseline/checkpoints/<task>.md` in the planning directory: commits; exact commands with pass and fail counts and every failure; attested-source digest and image ids built; scratch scopes created and released; remaining risks.
- The orchestrating session reruns the task's acceptance commands on the committed tree, compares the commits' files with the task's Files list, and only then dispatches the next task.
- Evidence (logs, reports, screenshots) stays outside the repository under `HYPRN_MVP_EVIDENCE_ROOT`. Tests run only in scoped scratch stores.
- A failure owned by a later task is allowed only when it is listed in a guard's `PENDING` table with the owning task; every `PENDING` table is empty after task 1.10.

### Development environment

The values are specific to the development host and never committed. Until task 1.2 the runner resolves its interpreters below the development data root as it does today; from task 1.2 on, these variables apply:

    export HYPRN_MVP_DATA_ROOT=<development data root, outside the repository and outside synced folders>
    export HYPRN_MVP_NATIVE_PYTHON=<native development interpreter>
    export HYPRN_MVP_CONTRACT_PYTHON=<contract development interpreter>
    export HYPRN_MVP_TEST_FIXTURES_ROOT=<durable test fixture folder>
    export HYPRN_MVP_UPSTREAM_CACHE=<verified WhatsOpt archive cache>
    export HYPRN_MVP_ENGINE_IMAGE=<numerical engine base image id>
    export HYPRN_MVP_MODELING_SOURCE_IMAGE=<WhatsOpt source base image id>
    export HYPRN_MVP_TERM_SCAN_FILES=<term pattern files, path-separator list>

`CHECK <group>` below means `python3 -B deployment/checks.py --group <group>` with these variables exported (before task 1.1 lands: `python3 -B deployment/phase02_checks.py --group <group>`). Phase 2 replaces the interpreters and base images with pinned, reproducible builds and wraps the runner as `./hyprn-mvp dev check`.

### Waves

| Wave | Tasks | Why |
|---|---|---|
| 1 | 1.1 (tracer) | Runner and gates every later task reports against |
| 2 | 1.2 ∥ 1.3 | Disjoint files: deployment side versus browser and API tests |
| 3 | 1.4 | Python packages and contracts; everything else depends on the new import roots |
| 4 | 1.5 ∥ 1.6 | Disjoint files: deployment identities versus UI and design system |
| 5 | 1.7 | Needs the renamed modeling runtime (1.5) and packages (1.4) |
| 6 | 1.8 → 1.9 → 1.10 | Sweep, fixtures, gate; each reads the whole tree |

## Decisions applied

- **D-01** `hyprn-mvp` is the only product namespace: Python packages `hyprn_mvp_app`, `hyprn_mvp_integration`; contract `contracts/hyprn-mvp.openapi.yaml`; environment prefix `HYPRN_MVP_`, including the variables the code already reads for the data root, the container socket, Chromium and the UI build output (`HYPRN_MVP_DATA_ROOT`, `HYPRN_MVP_DOCKER_SOCKET`, `HYPRN_MVP_CHROMIUM`, `HYPRN_MVP_UI_OUT`), each renamed by the task that owns the reading file; container labels `org.hyprn-mvp.*`; container, network and image names `hyprn-mvp-*`; command-line entry `./hyprn-mvp` (Phase 2); UI skill folder `.claude/skills/hyprn-mvp-ui/`; wordmark "HYPRN MVP"; design system name "HYPRN MVP Foundry" in `design-system/tokens.json`.
- **D-02** No compatibility readers for records, fixtures or identifiers outside the `hyprn-mvp` namespace. Format identifiers keep their version numbers inside the new namespace. Development run data is discardable.
- **D-03** The runner is `deployment/checks.py`; each group has a class (`must-pass` or `opt-in`) and environment needs (`docker`, `browser`, `fixtures`); a group whose need is absent fails with `environment absent: <need>`.
- **D-04** Locations resolve flag → `HYPRN_MVP_*` variable → neutral default below `HYPRN_MVP_DATA_ROOT` → refusal with a message naming the variable. No operating-system folder layout is written into code in this phase (Phase 2 adds the installation configuration and the single path-policy module).
- **D-05** Provenance and licence allowlists in `computational_export.py` may be narrowed, never widened: entries that admit upstream archive bytes stay; entries for repository files whose bytes the rename changes are recomputed for the new bytes; entries that admitted only support-file bytes of records outside the `hyprn-mvp` namespace are removed; nothing is added for any other path.
- **D-06** Term pattern files are supplied by the development environment and never committed; no tracked file contains a literal that a guard searches for.
- **D-07** Retired groups: those whose targets pin identities of one particular installation (activation and handoff pins, release selection over a fixed commit list) and duplicate aggregates. They are replaced by one `qualification` aggregate of all must-pass groups.

## Tasks

### Task 1.1 (tracer) — Runner rename, group registry and scan gates

<task type="tracer" id="1.1">

<name>Task 1.1 (tracer) — Runner rename, group registry and scan gates</name>

<files>

- rename `deployment/phase02_checks.py` → `deployment/checks.py`;
- rename `deployment/tests/phase02_fixture.py` → `scoped_fixture.py`, `phase02_fixture_launcher.py` → `scoped_fixture_launcher.py`, every `deployment/tests/phase02_<area>_fixture.py` → `<area>_fixture.py`;
- rename `deployment/tests/test_phase02_guard.py` → `test_repository_guard.py`, `test_phase02_journey.py` → `test_native_journey.py`, `test_phase02_units.py` → `test_units_native.py`, `test_phase02_approach.py` → `test_approach_native.py`, `test_phase02_bridge.py` → `test_bridge.py`;
- rename `ui/playwright.phase02.config.ts` → `ui/playwright.isolated.config.ts`;
- delete `deployment/tests/test_activation.py`, `test_approach_activation.py`, `test_assumptions_evidence_activation.py`, `test_phase02_handoff.py`; split `deployment/tests/test_units_activation.py` into `deployment/tests/test_attestation.py` (attestation cases only);
- create `deployment/tools/term_scan.py`, `deployment/tests/test_term_scan.py`, `deployment/tests/test_naming_guard.py`, `deployment/tests/test_hygiene_guard.py`;
- every file that references a renamed module (`git grep -n phase02`), including the scoped-test environment variable, which becomes `HYPRN_MVP_TEST_SCOPE_ROOT`.

</files>

<action>

- **Goal:** the renamed runner runs one group end to end and the gates that every later task reports against exist: `CHECK contracts` passes with the same count as before, and `CHECK naming` reports the current violation inventory, each entry owned by a later task.

- **Steps:**
  1. Before any change, run `CHECK contracts` and `CHECK guard` with the current runner and record their pass counts.
  2. Rename with `git mv` and update every reference. The child entry flags (`--<group>-child`) follow the group names.
  3. Group registry: give every group `class` and `needs`. Add `--list [--class must-pass]`, printing group, class and needs. An absent need fails the group. Add the aggregate `qualification`: every must-pass group, sequentially, stopping at the first failure.
  4. Retire per D-07: `ae-activation`, `approach-activation`, `units-activation`, `handoff`, `polish-release`, `checkpoint-a`, `checkpoint-b`, `checkpoint-c`, `combined`, `ae-ui`, `approach-ui`. Before deleting a module, show with `git grep` and an AST import scan that no remaining group imports it. `units-attestation` targets `deployment/tests/test_attestation.py`.
  5. Register `ui/tests/simple-navigation.spec.ts` as group `ui-navigation` (must-pass, browser).
  6. Documents groups: rename each group that selects tests after the capability its tests cover (for example `documents-contracts`, `documents-native-originals`, `documents-collection-protocol`, `documents-parser-adoption`), rename the selected test functions and browser tags to match, and delete registered routes that select no test. Replace the guard case that cross-checked the routes against a planning document by a check against the runner's own table: every Documents group has existing targets and selects at least one test.
  7. `term_scan.py` (stdlib only): pattern files from repeatable `--patterns FILE` or `HYPRN_MVP_TERM_SCAN_FILES`; `#` comments and blank lines ignored; patterns joined as case-insensitive extended regular expressions; scans the contents of tracked text files and the tracked paths (`git ls-files -z`); prints `path:count` per file and a total; prints matched text only with `--show`; exit 0 clean, 1 on any match, 2 when no pattern file is configured or readable. `test_term_scan.py` uses synthetic pattern files in a scratch folder.
  8. `naming` group (must-pass, no needs), structural assertions: every top-level package under `application/src`, `integration/src` and `editions/*/src` is `hyprn_mvp_*`; every environment variable read by product code and tests is `HYPRN_MVP_*` or in a closed list of standard variables (`HOME`, `PATH`, `TMPDIR`, `DOCKER_HOST`, `XDG_*`, `PLAYWRIGHT_*`, `CI`, `LANG`, `LC_*`); Docker label keys start with `org.hyprn-mvp.`; container, network and image names built by managers start with `hyprn-mvp-`; the contract files are `contracts/hyprn-mvp.openapi.yaml` and `contracts/modeling.openapi.yaml`; every OpenAPI extension key starts with `x-hyprn-mvp-`; no file, group, test function or browser tag name carries a numbered work-item reference.
  9. `hygiene` group (must-pass, no needs): no absolute user-home path in macOS, Linux or Windows form; no private-key block header; no token-format literal (common cloud, source-hosting, chat and model-provider token prefixes, and `hyprn_mvp_mcp_`); no tracked `.env`, key, certificate, keychain or SQLite file. Both guards assemble their search strings at run time, so they never contain what they search for.
  10. Each guard holds a `PENDING` table: `path → owning task` for every current violation.

- **Risks:** a deleted module still imported by a must-pass group (AST import evidence before deletion; any failure routes back to this task); renamed child entry flags breaking a subprocess group (run every renamed group once and record the result).

</action>

<verify>
<automated>

- `python3 -B deployment/checks.py --list` lists every group with class and needs; `git grep -n phase02` returns nothing.
- `CHECK contracts` passes with the count recorded in step 1; `CHECK guard` passes, and its count differs from step 1 only by the cases listed in the checkpoint (added or retired).
- `CHECK naming`, `CHECK hygiene` and `CHECK ui-navigation` pass (the guards with their `PENDING` tables).
- `python3 -B -m pytest -q deployment/tests/test_term_scan.py` passes; with `HYPRN_MVP_TERM_SCAN_FILES` unset, `python3 -B deployment/tools/term_scan.py` exits 2.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.1.md` is verified by the orchestrating session.</done>

</task>

### Task 1.2 — Development locations: neutral layout and per-location variables

<task type="auto" id="1.2">

<name>Task 1.2 — Development locations: neutral layout and per-location variables</name>

<files>

`deployment/local_paths.py`; `deployment/tests/scoped_fixture.py`, `scoped_fixture_launcher.py`, `live_fence.py`, `test_repository_guard.py`; `deployment/tests/c4_fixture.py` → `deployment/tests/durable_fixture.py` (and its importers); `deployment/tools/backup_immutable.py`; `deployment/manage.py`; location constants only in `deployment/application_runtime.py`, `execution_runtime.py`, `dispatch_runtime.py`, `native_environment.py`, `migrate_runtime.py`, `approach_polish_release.py`; `deployment/fresh_workspace.py` → `deployment/initialize_stores.py` with `deployment/tests/test_fresh_workspace.py` → `test_initialize_stores.py`; the data-root read in the integration package's `launcher.py` (the package is renamed in 1.4).

</files>

<action>

- **Goal:** the deployment managers, fixtures and tools take every location from a flag, a `HYPRN_MVP_*` variable or a neutral default below `HYPRN_MVP_DATA_ROOT`; no code names one installation's folders, ports, interpreters or images.

- **Depends on:** 1.1.

- **Steps:**
  1. Neutral layout below `HYPRN_MVP_DATA_ROOT`: `application/`, `modeling/`, `execution/` (development installation stores), `releases/`, `fixtures/`, `cache/upstream/whatsopt/`, `evidence/`, `dev/python-native/`, `dev/python-contract/`. Each location also has its own variable: `HYPRN_MVP_NATIVE_PYTHON`, `HYPRN_MVP_CONTRACT_PYTHON`, `HYPRN_MVP_TEST_FIXTURES_ROOT`, `HYPRN_MVP_UPSTREAM_CACHE`, `HYPRN_MVP_EVIDENCE_ROOT`, `HYPRN_MVP_SCRATCH_ROOT` (default: the operating system's temporary folder, resolved to its real path), `HYPRN_MVP_LIVE_ROOTS` (path-separator list of folders tests must never touch), `HYPRN_MVP_ENGINE_IMAGE`, `HYPRN_MVP_MODELING_SOURCE_IMAGE`, `HYPRN_MVP_PORT` (development application port; refused when unset), plus `HYPRN_MVP_DOCKER_SOCKET`, `HYPRN_MVP_CHROMIUM` and `HYPRN_MVP_UI_OUT`. Every read of the data-root, container-socket, Chromium and UI-output variables in this task's files, including the integration package's `launcher.py`, uses these `HYPRN_MVP_` names. Document each in the module docstring. Remove resolver functions that no remaining caller uses.
  2. Scoped test folders become `<scratch root>/hyprn-mvp-test-<uuid>`; container and network names in scopes become `hyprn-mvp-test-<scope8>-<role>`.
  3. The test-safety fence denies writes, mounts and container operations inside the development data root's stores, every `HYPRN_MVP_LIVE_ROOTS` entry and any user installation configuration file; it lists only entry points present in the repository; it acts on containers and networks only when they carry the scope's label.
  4. `manage.py` keeps `isolated` and `require_attestation` (imported by `deployment/launch_worker.py`). Remove each subcommand whose inputs are not in the repository, and each recipe or pin file used only by those subcommands; record the reference evidence.
  5. Replace every remaining literal port, interpreter path, container socket path, base image id and scratch prefix in deployment code with the resolvers above.
  6. Rename `fresh_workspace.py` to `initialize_stores.py`: "workspace" is reserved for the cloud edition's user-owned workspaces (`CONTEXT.md`).

- **Risks:** a weaker fence (its tests must refuse at least every case they refused before, with the live roots configured); unset interpreters (every native group refuses with a message naming the variable).

</action>

<verify>
<automated>

`CHECK guard`, `CHECK deployment-hardening`, `CHECK units-guards`, `CHECK units-staging` and `CHECK hygiene` pass; the fence tests show that a write, mount or container operation inside each configured live root is refused; `term_scan.py` reports no match in the files of this task other than entries the `naming` guard's `PENDING` table assigns to 1.4 or 1.5.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.2.md` is verified by the orchestrating session.</done>

</task>

### Task 1.3 — Browser and API test locations

<task type="auto" id="1.3">

<name>Task 1.3 — Browser and API test locations</name>

<files>

`ui/playwright.config.ts`, `ui/playwright.isolated.config.ts`, `ui/vite.config.ts`, `ui/tests/support/browser.ts`, `ui/tests/evidence.ts`, the `ui/tests/*.spec.ts` files with fixed origins, ports, password locations or `HOME`/`PATH` literals (find them with the term scan and `git grep -nE "127\.0\.0\.1:[0-9]+|HOME|PATH" ui/tests`); `application/tests/conftest.py`, `test_api.py`, `test_authorization.py`, `test_contract_errors.py`, `test_history.py`; `integration/tests/graph_selection.cjs`.

</files>

<action>

- **Goal:** browser and API tests carry no fixed origin, port, password location, home folder or browser cache path.

- **Depends on:** 1.1. Parallel with 1.2.

- **Steps:**
  1. One loopback test origin is defined in `application/tests/conftest.py` and imported by every API test that needs it.
  2. Specs that need a served installation read `HYPRN_MVP_UI_BASE_URL` and the owner credential from `HYPRN_MVP_UI_PASSWORD_FILE`; their groups are opt-in until Phase 2 provides scratch installations.
  3. Chromium resolves through Playwright or `HYPRN_MVP_CHROMIUM`; `ui/vite.config.ts` builds into `ui/dist` unless `HYPRN_MVP_UI_OUT` is set; both Playwright configurations, `ui/tests/support/paths.ts` and `integration/tests/graph_selection.cjs` read the data root from `HYPRN_MVP_DATA_ROOT`.
  4. `ui/tests/prototype-fidelity.spec.ts` reads reference images from `design-system/reference/`; it belongs to the opt-in group `ui-fidelity`, which fails with "reference absent" when the folder is missing (the images are produced from the running local edition in Phase 5).
  5. Specs whose assertions target screen compositions that no longer exist are updated to the current composition, or removed with the reason recorded in the checkpoint. Spec files named after work streams (for example `ui/tests/migration-journey.spec.ts`) are renamed after the behaviour they test.

- **Risks:** a spec silently dropped from every group (the guard lists unregistered specs; each is registered or removed with a reason).

</action>

<verify>
<automated>

`CHECK api-a`, `CHECK api-c`, `CHECK combined-security`, `CHECK foundry-nav`, `CHECK ported-isolated`, `CHECK ui-b` and `CHECK ui-navigation` pass; `npm --prefix ui run build` writes `ui/dist`; with `HYPRN_MVP_UI_OUT` set it writes there; `CHECK hygiene` passes with this task's `PENDING` entries removed.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.3.md` is verified by the orchestrating session.</done>

</task>

### Task 1.4 — Python packages, contract and wire identifiers

<task type="auto" id="1.4">

<name>Task 1.4 — Python packages, contract and wire identifiers</name>

<files>

`application/src/**` (package directory → `hyprn_mvp_app`), `application/pyproject.toml`, `application/generate_contract.py`, `application/audit_dependencies.py`, `application/dependency-pins.json`, `application/tests/**`; `integration/src/**` (→ `hyprn_mvp_integration`), `integration/pyproject.toml`, `integration/tests/**` (except `integration/tests/fixtures/native-programs.json.gz`, regenerated in 1.7); `contracts/**` (OpenAPI file → `contracts/hyprn-mvp.openapi.yaml`); `modeling/tests/**` and import lines in `modeling/*.py`; `ui/generate_types.py` (input path) and the generated `ui/src/contract.ts`; in `deployment/`, package path strings and import lines only.

</files>

<action>

- **Goal:** the application and integration packages, their distributions, the public contract and every wire and record identifier use the `hyprn-mvp` namespace, with the attested execution source set recomputed.

- **Depends on:** 1.2, 1.3.

- **Target identifiers** (names the documentation already uses):

  | Kind | Target |
  |---|---|
  | Python packages / distributions | `hyprn_mvp_app` / `hyprn-mvp-app`; `hyprn_mvp_integration` / `hyprn-mvp-integration` |
  | Owner recovery entry | `python -m hyprn_mvp_app.auth recover` |
  | AiiDA calculation entry point | `hyprn_mvp.scalar` |
  | Generated program protocol | `hyprn_mvp.openmdao.program/1` |
  | Text extractor identity | `hyprn-mvp-utf8/1` |
  | Worker result marker | `HYPRN_MVP_RESULT_V1` |
  | Record kinds and archive roles | `hyprn-mvp-…` (for example `hyprn-mvp-computational-record`) |
  | OpenAPI extensions | `x-hyprn-mvp-invariants`, `x-hyprn-mvp-file-schemas` |
  | Session cookie | `hyprn_mvp_session` |
  | Application environment | `HYPRN_MVP_APP_STORE`, `HYPRN_MVP_ORIGIN`, `HYPRN_MVP_MODEL_URL`, `HYPRN_MVP_MODEL_KEY_FILE` |

- **Steps:**
  1. `git mv` the package directories and the contract file; update imports, entry points, distribution names and generators.
  2. Apply the identifier table. Readers accept only the new identifiers (D-02).
  3. Regenerate the OpenAPI components, the TypeScript types and the golden identity corpus from the renamed code. The checkpoint lists every changed golden file with a one-line reason and a word-diff summary showing that canonical bodies differ only in namespace strings.
  4. Recompute the attested execution source set (`launcher.execution_source_hashes()` file list and pinned digests) and keep the two-sided transitive-coverage test green.

- **Risks:** a large mechanical diff hiding a semantic change (word-diff review; goldens change only in namespace strings); an attested-set mismatch (two-sided coverage test).

</action>

<verify>
<automated>

`CHECK contracts`, `locality-contracts`, `projection`, `bindings`, `units-contracts`, `units-public-types`, `approach-contracts`, `approach-closure`, `ae-contracts`, `ae-generated`, `ae-public` and every application group (`api-a`, `api-c`, `runtime-observation`, `modified`, `combined-security`, `approach-api`, `approach-service`, `approach-configuration`, `findings-history`, `fuel-platform`, `investigation-evidence`, `investigation-diagnostics`, `archive-service`, `archive-accounting`, `archive-diagnostics`, `units-api`, `units-resolution`, `units-configuration`, `ae-evidence`, `ae-authoring`, `ae-configuration`) pass, except failures already listed for 1.9; `term_scan.py` reports no match under `application/`, `integration/src/`, `contracts/` and `modeling/tests/`; native groups are listed in `PENDING` for 1.5 and 1.7.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.4.md` is verified by the orchestrating session.</done>

</task>

### Task 1.5 — Deployment identities, images and pins

<task type="auto" id="1.5">

<name>Task 1.5 — Deployment identities, images and pins</name>

<files>

`deployment/migrate_runtime.py` → `deployment/modeling_runtime.py`; `deployment/migration-compose.yaml` → `deployment/modeling-compose.yaml`; `deployment/approach_polish_release.py` → `deployment/release_binding.py`; `deployment/migration-pins.json` (entries still consumed by code move into `deployment/pins.json`, inventories naming files that are not in the repository are dropped, the file is removed); `deployment/pins.json`, `deployment/authoring-pins.json`; `deployment/*.Dockerfile`; `deployment/application_runtime.py`, `execution_runtime.py`, `dispatch_runtime.py`, `native_environment.py`, `launch_worker.py`, `initialize_stores.py`, `modeling_policy.rb`; `deployment/tools/backup_immutable.py`; `deployment/tests/**` expectations; importers of the renamed modules.

</files>

<action>

- **Goal:** managers, Dockerfiles, compose files, labels, pins and the attested-source list use `hyprn-mvp` names; native groups that do not need the modeling patches pass with base images from `HYPRN_MVP_ENGINE_IMAGE` and `HYPRN_MVP_MODELING_SOURCE_IMAGE`.

- **Depends on:** 1.4. Parallel with 1.6.

- **Steps:**
  1. Labels become `org.hyprn-mvp.<key>`; containers and networks `hyprn-mvp-<role>`; test scopes `hyprn-mvp-test-<scope8>-<role>`; image tags `hyprn-mvp-<role>:<build-input-digest16>`.
  2. The worker image copies `hyprn_mvp_integration`; the application image runs `hyprn_mvp_app.api:from_environment`.
  3. Recompute pinned digests and the attested-source list for the renamed deployment files; record each change (path, old digest, new digest).
  4. Remove code paths whose only purpose was to act on one particular installation and that no remaining test reaches; show the reference evidence.
  5. The release-binding path set (`RELEASE_BINDING_PATHS` in `deployment/release_binding.py`) and the hardening tests name only files present in the repository; a hardening case that reads a script absent from the repository is removed or rewritten against files that exist.

- **Risks:** a renamed label that a cleanup step no longer matches, leaving containers behind (post-run listing above); an attested-set change without coverage (two-sided test).

</action>

<verify>
<automated>

`CHECK units-staging`, `units-launcher`, `units-worker`, `units-attestation`, `units-bundle`, `units-history`, `approach-bundle`, `approach-worker`, `approach-history`, `investigation-worker`, `native-bindings`, `ae-execution`, `ae-history`, `deployment-hardening` and `guard` pass, except native groups that need the modeling image (listed in `PENDING` for 1.7) and failures listed for 1.9; `term_scan.py` reports no match under `deployment/` outside 1.7 and 1.9 entries; after the run, `docker ps -a --filter label=org.hyprn-mvp.test-scope` is empty.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.5.md` is verified by the orchestrating session.</done>

</task>

### Task 1.6 — UI names and design-system paths

<task type="auto" id="1.6">

<name>Task 1.6 — UI names and design-system paths</name>

<files>

`ui/design_tokens.py`, `ui/design_smoke.mjs`, `ui/test_design_tooling.py`, `ui/check_design_system.py`, `ui/design-baseline.json`; `ui/src/design/index.ts`, `components.tsx`, `foundry.css`, `tokens.css` (generated); `ui/src/**` (API client and names); `ui/tests/**`; `ui/package.json` and `ui/package-lock.json` (package name only); `ui/check_phase02_contract.py` → `ui/check_ui_contract.py` with a new `ui/control-map.json`; `ui/README.md`, `ui/provenance.md` where they name tooling paths; `.claude/skills/hyprn-mvp-ui/SKILL.md` (new).

</files>

<action>

- **Goal:** the UI uses `hyprn-mvp` names, the design tooling reads `design-system/`, the UI contract checker no longer reads a missing file, and the UI rules exist as a skill.

- **Depends on:** 1.4. Parallel with 1.5.

- **Steps:**
  1. Token tooling reads `design-system/tokens.json`; regenerate `tokens.css` (system name "HYPRN MVP Foundry"); comments that cited planning documents now cite `design-system/` files.
  2. Remove the stale seven-column `.hf-ledger` rule from `foundry.css`.
  3. Rename the API client and identifiers (for example `hyprnMvpApi`), browser variables (`HYPRN_MVP_UI_EVIDENCE_ROOT`, `HYPRN_MVP_NAV_BUILD`) and the wordmark ("HYPRN MVP").
  4. The UI contract checker reads its named control-to-spec mappings from `ui/control-map.json` (tracked) and fails on any control without an existing spec test; it no longer reads a coverage document.
  5. Write `.claude/skills/hyprn-mvp-ui/SKILL.md`: when to load it (`ui/src`, `ui/tests`, styles, tokens, design system); read order (`design-system/README.md`, `Layouts.md`, `Scientific-states.md`, `SOURCE.md`, component notes); rules (components only from `ui/src/design`; tokens only; never hand-edit `tokens.css`; content security policy `default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'`, so no inline styles, external fonts, icon fonts, URLs or CDNs; icons as inline SVG with `aria-label` on icon-only buttons; status as shape + word + colour; "unassigned", "not computed", explicit zero; separate outcome facets); checks (`check_design_system.py`, `design_tokens.py --check`, `tsc --noEmit`, build); definition of done for screen work (one screen per step, 1440 × 1000 screenshots in light and dark compared with the design-system reference images, evidence outside the repository, DOM tests are not fidelity, product-owner acceptance recorded separately); explicit-path commits.
  6. No dependency version changes: `npm --prefix ui ls --all` is identical before and after, apart from the root package name.

- **Risks:** generated types drifting from the contract (regenerate, never hand-edit); a baseline update hiding a new violation (`--update-baseline` only for lines this task moved, listed in the checkpoint).

</action>

<verify>
<automated>

`python3 ui/design_tokens.py --check`; `python3 ui/check_design_system.py` prints no FAIL line; `python3 ui/test_design_tooling.py`; `node ui/design_smoke.mjs`; `npm --prefix ui ci && npm --prefix ui run build`; `CHECK combined-static`, `ui-a`, `ui-a-retained`, `ui-b`, `ui-c`, `foundry-nav`, `ported-isolated`, `ui-navigation`, every `approach-ui-*` (except `approach-ui-history`, owned by 1.9), every `ae-ui-*` and every `units-ui-*` group pass; `term_scan.py` reports no match under `ui/` and `.claude/`.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.6.md` is verified by the orchestrating session.</done>

</task>

### Task 1.7 — WhatsOpt patches and modeling provenance identity

<task type="auto" id="1.7">

<name>Task 1.7 — WhatsOpt patches and modeling provenance identity</name>

<files>

`upstream/whatsopt-patches/*.patch`; `deployment/modeling.Dockerfile`, `deployment/modeling_policy.rb`, `deployment/modeling_runtime.py` (patch digests), `deployment/pins.json` (`native_patch_sha256`); `modeling/provenance.md`, `modeling/rehearsal.py`, `modeling/verify_rehearsal.py`; `integration/src/hyprn_mvp_integration/computational_export.py` (allowlists, per D-05); `integration/tests/test_fuel_native_provenance.py`; `integration/tests/fixtures/native-programs.json.gz` (regenerated with `integration/tests/capture_native_programs.py`).

</files>

<action>

- **Goal:** the ordered WhatsOpt patches, the modeling image's corresponding-source directory and the modeling provenance record use `hyprn-mvp` names; the modeling image builds from the patched upstream; every native group passes, including the per-run computational record export.

- **Depends on:** 1.5.

- **Steps:**
  1. Rename product identifiers inside the patches (adapter and contract names, environment names, file references). Keep every AGPL-3.0-only notice. The patches still apply in order with `patch --batch --fuzz=0`.
  2. The corresponding-source directory in the modeling image becomes `/usr/share/hyprn-mvp-modeling-source/`; `modeling/rehearsal.py` reads the data root from `HYPRN_MVP_DATA_ROOT`.
  3. Recompute patch digests in `modeling/provenance.md`, `deployment/modeling_runtime.py` and `deployment/pins.json`; rebuild the modeling image from `HYPRN_MVP_MODELING_SOURCE_IMAGE`.
  4. Regenerate the native-programs fixture from the rebuilt modeling image.
  5. Apply D-05 to `AUDITED_PROVENANCE`, `AUDITED_PROVENANCE_REVISIONS` and `AUDITED_LICENSES`; list every entry change (path, old digest, new digest or removal, reason). `test_fuel_native_provenance.py` asserts that the current support sources pass `sensitive()` without any allowance and that the allowlists equal the new closed inventory.

- **Risks:** a patch that no longer applies with zero fuzz (rebuild fails closed; fix the patch, never the fuzz level); widening an allowlist by mistake (closed-inventory test).

</action>

<verify>
<automated>

the modeling image builds; `CHECK units-model`, `ae-model`, `units-native` (all steps, including the per-run export), `approach-native`, `approach-export`, `investigation-native`, `ae-native`, `ae-export`, `archive-native`, `archive-bridge`, `bridge-history`, `native-a`, `native-b`, `combined-native` and `fuel-native-provenance` pass; `deployment/tests/test_modeling_isolation.py` passes (the modeling service has no launcher, socket or foreign store); `term_scan.py` reports no match under `upstream/` and `modeling/`.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.7.md` is verified by the orchestrating session.</done>

</task>

### Task 1.8 — Text sweep, detector inputs and the parser adoption record

<task type="auto" id="1.8">

<name>Task 1.8 — Text sweep, detector inputs and the parser adoption record</name>

<files>

every file the term scan or the `naming` guard still flags for comments, docstrings, names or messages; `application/tests/test_computational_records.py`, `integration/tests/test_computational_archive.py`, `integration/tests/test_investigation_diagnostics.py`; `contracts/tests/test_documents_planning_gates.py` → `contracts/tests/test_document_parser_adoption.py`; new `integration/document-parser.lock.json`; `integration/document-parser-provenance.md` (points to the lock).

</files>

<action>

- **Goal:** comments, docstrings, test names and assertion messages state the invariant they protect; detector tests build their sensitive-looking inputs at run time; the document parser adoption test checks a tracked record.

- **Depends on:** 1.7.

- **Steps:**
  1. Rewrite each comment or name that cites a deployment, a work item or a review finding so that it states the protected invariant (for example "the launch-worker wrapper must equal this release's wrapper").
  2. The three detector tests (private-key block, Linux home path, Windows account path) assemble their inputs from fragments at run time and still assert that the detectors refuse or redact them.
  3. `integration/document-parser.lock.json` records the adopted parser wheel: name `pypdf`, version 6.20.0, wheel filename, size, SHA-256 `f003fc2014814d264fe7dd3f9d435c158e23e1a85a2233f87a0a2d6d21c914ad`, index host, licence, no extras. The adoption test checks the lock against the provenance document's identity table. Checks that need the wheel bytes run only when `HYPRN_MVP_PARSER_WHEEL` names a local copy, and run unconditionally in the parser image build (Phase 4).

- **Risks:** a rewritten comment losing the reason a guard exists (each rewrite states the invariant, reviewed in the checkpoint sample).

</action>

<verify>
<automated>

`CHECK hygiene` passes with an empty `PENDING` table; `CHECK documents-parser-adoption`, `combined-static` and `contracts` pass; the three detector tests pass; `term_scan.py` reports matches only in files listed for 1.9.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.8.md` is verified by the orchestrating session.</done>

</task>

### Task 1.9 — Durable fixtures and remaining failures

<task type="auto" id="1.9">

<name>Task 1.9 — Durable fixtures and remaining failures</name>

<files>

`deployment/tests/durable_fixture.py`, `deployment/tests/findings_native_fixture.py`, `deployment/tests/test_findings_native.py`, `deployment/tests/test_findings_native_guards.py`, `deployment/tests/approach_ui_fixture.py`, `ui/tests/findings-native.spec.ts`, `ui/tests/approach.spec.ts` (history cases), fixture manifests and pins; the source and test files of the repaired cases.

</files>

<action>

- **Goal:** the durable-fixture groups run on fixtures whose records use the `hyprn-mvp` namespace, and every remaining failing case in a must-pass group is repaired.

- **Depends on:** 1.8.

- **Steps:**
  1. For each durable-fixture group (`findings-native-guards`, `findings-native-preflight`, `findings-native`, `findings-native-read`, `approach-ui-history`), either regenerate the fixture with its builder from authored inputs under the renamed code (new folder below `HYPRN_MVP_TEST_FIXTURES_ROOT`, manifest digest re-pinned), or replace it with a fixture the test builds in its own scratch scope with the same assertions. Record which, and why. No reader for other identifiers is added (D-02).
  2. Re-run `runtime-observation`, `units-resolution` and `approach-worker`; repair any failing case with RED/GREEN evidence in the checkpoint.

- **Risks:** a fixture that cannot be regenerated without data that no longer exists (replace it with a self-built fixture covering the same assertions; list any assertion that cannot be kept, for review).

</action>

<verify>
<automated>

the five durable-fixture groups (or their replacements, registered under the same names) pass; `CHECK runtime-observation`, `units-resolution` and `approach-worker` pass; `term_scan.py` reports zero matches on the tree.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.9.md` is verified by the orchestrating session.</done>

</task>

### Task 1.10 — Phase gate

<task type="auto" id="1.10">

<name>Task 1.10 — Phase gate</name>

<files>

`deployment/tests/test_naming_guard.py`, `deployment/tests/test_hygiene_guard.py` (remove the empty `PENDING` tables), `AGENTS.md` ("Running checks": runner `deployment/checks.py`, the development variables of this plan).

</files>

<action>

- **Goal:** prove the baseline and hand over a clean starting point.

- **Depends on:** 1.9.

- **Steps:**
  1. Run `CHECK qualification` on the development host and record each group's counts.
  2. Run `python3 -B deployment/tools/term_scan.py` over the whole tree.
  3. Confirm that every identifier the documentation names exists in code: `hyprn_mvp_app.auth recover`, `HYPRN_MVP_APP_STORE`, `HYPRN_MVP_ORIGIN`, `HYPRN_MVP_MODEL_URL`, `HYPRN_MVP_MODEL_KEY_FILE`, `HYPRN_MVP_UI_EVIDENCE_ROOT`, `hyprn_mvp.scalar`, `hyprn-mvp-utf8/1`, `hyprn_mvp.openmdao.program/1`, `/usr/share/hyprn-mvp-modeling-source/` (identifiers delivered by later phases, `HYPRN_MVP_STUDIES_DIR`, `HYPRN_MVP_MCP_TOKEN` and `hyprn-mvp://playbook/<section>`, are listed as such).
  4. Update `AGENTS.md` "Running checks".

- **Risks:** a long qualification run (native groups take minutes each; run sequentially and record timings).

</action>

<verify>
<automated>

`CHECK qualification` exits 0 with no group reported as environment absent; `term_scan.py` exits 0; `CHECK naming` and `CHECK hygiene` pass without `PENDING` tables; `git ls-files` lists no scratch, evidence, store or log file; each identifier in step 3 is found by `git grep -n`.

</automated>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/01-repository-baseline/checkpoints/1.10.md` is verified by the orchestrating session.</done>

</task>

## Must-pass groups after Phase 1

| Class | Groups |
|---|---|
| Static and contract | `naming`, `hygiene`, `guard`, `combined-static`, `contracts`, `locality-contracts`, `projection`, `bindings`, `units-guards`, `units-contracts`, `units-public-types`, `approach-contracts`, `approach-closure`, `ae-contracts`, `ae-generated`, `ae-public`, Documents contract groups |
| Application | `api-a`, `api-c`, `runtime-observation`, `modified`, `combined-security`, `approach-api`, `approach-service`, `approach-configuration`, `findings-history`, `fuel-platform`, `investigation-evidence`, `investigation-diagnostics`, `archive-service`, `archive-accounting`, `archive-diagnostics`, `units-api`, `units-resolution`, `units-configuration`, `ae-evidence`, `ae-authoring`, `ae-configuration`, `ae-model` |
| Native (Docker, AiiDA) | `units-staging`, `units-model`, `units-bundle`, `units-history`, `units-launcher`, `units-worker`, `units-attestation`, `units-native`, `approach-bundle`, `approach-worker`, `approach-history`, `approach-export`, `approach-native`, `investigation-native`, `investigation-worker`, `fuel-native-provenance`, `ae-execution`, `ae-history`, `ae-export`, `ae-native`, `archive-native`, `archive-bridge`, `bridge-history`, `native-a`, `native-b`, `native-bindings`, `combined-native`, `deployment-hardening`, Documents native groups |
| Durable fixtures | `findings-native-guards`, `findings-native-preflight`, `findings-native`, `findings-native-read`, `approach-ui-history` |
| Browser (Node and Playwright) | `ui-a`, `ui-a-retained`, `ui-b`, `ui-c`, `ui-navigation`, `foundry-nav`, `ported-isolated`, `approach-ui-controller`, `approach-ui-reading`, `approach-ui-method`, `approach-ui-assumptions`, `approach-ui-configuration`, `ae-ui-evidence`, `ae-ui-model`, `ae-ui-configuration`, `units-ui-authoring`, `units-ui-configuration`, `units-ui-reading`, `units-ui-history` |
| Opt-in | `ui-fidelity` (reference images from Phase 5), served-installation specs (scratch installations from Phase 2) |

<threat_model>

## Trust boundaries

| Boundary | Description |
|---|---|
| Repository → attested worker | Renamed execution sources must match the attested set exactly |
| Retained records → export | Allowlists decide which bytes a computational record export may carry |
| Tests → development host | Scoped tests must never touch live stores or foreign containers |
| Repository → readers | Tracked content must carry no secrets or personal paths |

## STRIDE threat register

| Threat ID | Category | Component | Severity | Disposition | Mitigation plan |
|---|---|---|---|---|---|
| T-1-01 | Tampering | Attested execution source set (`launcher.execution_source_hashes()`) | high | mitigate | Recompute with the rename; two-sided transitive-coverage test; every digest change listed in the checkpoint (1.4, 1.5) |
| T-1-02 | Elevation of privilege | Provenance and licence allowlists in `computational_export.py` | high | mitigate | Narrow-only rule D-05; closed-inventory test in `test_fuel_native_provenance.py` (1.7) |
| T-1-03 | Information disclosure | Tracked files | high | mitigate | `hygiene` guard and term scan; detector inputs built at run time (1.1, 1.8, 1.10) |
| T-1-04 | Tampering | Test-safety fence | high | mitigate | Fence covers the data-root stores and `HYPRN_MVP_LIVE_ROOTS`; label-scoped container operations; fence tests (1.2) |
| T-1-05 | Repudiation | Regenerated goldens and fixtures | medium | mitigate | Word-diff review showing namespace-only changes; regeneration recorded per file (1.4, 1.9) |
| T-1-06 | Denial of service | Leftover test containers after label rename | low | mitigate | Post-run listing by the scope label must be empty (1.5) |

</threat_model>

<verification>
- `python3 -B deployment/checks.py --group qualification` exits 0 on the development host.
- `python3 -B deployment/tools/term_scan.py` exits 0 with the configured pattern files.
- `python3 -B deployment/checks.py --group naming` and `--group hygiene` pass with no `PENDING` table.
- `python3 ui/check_design_system.py` prints no FAIL line; `python3 ui/design_tokens.py --check` passes.
</verification>

<success_criteria>
- All five Phase 1 success criteria in `ROADMAP.md` are true.
- Ten checkpoints exist, each verified by the orchestrating session before the next task started.
</success_criteria>

<output>
After task 1.10, write `phases/01-repository-baseline/01-SUMMARY.md` in the planning directory: groups and counts, timings, digests changed, fixtures regenerated or replaced, and any assertion that could not be kept.
</output>
