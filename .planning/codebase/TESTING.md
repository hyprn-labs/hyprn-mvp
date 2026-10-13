---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
# Testing Patterns

**Analysis Date:** 2026-10-13

Every test runs through the fail-closed group runner `deployment/checks.py` inside a freshly allocated scratch scope. Do not run pytest, Playwright or unittest directly against a checkout: the runner chooses the reviewed interpreter, builds a clean environment, allocates the scope, disables plugin autoload and refuses empty, skipped or flaky results. Binding rules: `AGENTS.md` ("Running checks", "Locations and data"), `deployment/local_paths.py` (location variables), `.claude/skills/hyprn-mvp-ui/SKILL.md` (UI checks).

## Test Framework

**Runner:**

- Group runner: `deployment/checks.py` (stdlib only, 1007 lines). It launches each group as a scoped child process (`--<group>-child`) under a reviewed interpreter.
- pytest 9.1.1 (`application/pyproject.toml` `[project.optional-dependencies] test`) for application, integration, contract, modeling and native journey tests. Invoked by the runner as `pytest.main(['-q', '-p', 'no:cacheprovider', '--noconftest', '--basetemp=<scope>/tmp/pytest', ...targets], plugins=[Results()])` with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- stdlib `unittest` for repository guards: `deployment/tests/test_repository_guard.py`, `test_naming_guard.py`, `test_hygiene_guard.py`, `test_term_scan.py`, `test_findings_native_guards.py`, `test_units_fixture_guards.py`, and `ui/test_design_tooling.py`.
- Playwright 1.62.1 (`playwright/test`) for browser specs in `ui/tests/*.spec.ts`; Chromium only (`channel: 'chrome'`).
- `node:test` for `ui/tests/criterion-record.test.cjs` (server-side render of one design primitive).
- Script checks (exit code is the verdict): `ui/check_ui_contract.py`, `ui/check_design_system.py`, `ui/design_tokens.py --check`, `ui/design_smoke.mjs`.
- Config: `integration/pyproject.toml` `[tool.pytest.ini_options]` (`pythonpath = ["src"]`, `addopts = "-p no:cacheprovider"`, markers `quick`, `integration`, `isolation`); `application/pyproject.toml` (`testpaths = ["tests"]`); `ui/playwright.config.ts` (served installation); `ui/playwright.isolated.config.ts` (scoped served fixture). Isolated foundry groups generate their own Playwright config into the scope (`browser_config()` in `deployment/tests/foundry_ui_fixture.py`).

**Interpreters (from `deployment/local_paths.py`):**

- Native interpreter `HYPRN_MVP_NATIVE_PYTHON` (default `<data root>/dev/python-native/venv/bin/python`): native, guard and Documents-native groups. Exposed as `fixture.APPROVED_PYTHON`.
- Contract interpreter `HYPRN_MVP_CONTRACT_PYTHON` (default `<data root>/dev/python-contract/venv/bin/python`): application-only, contract, browser fixture groups. Exposed as `fixture.APPROVED_CONTRACT_PYTHON`. Per-group choice is the `GROUP_INTERPRETERS` map in `deployment/checks.py`; a child under the wrong interpreter refuses (`'Child must use the reviewed interpreter'`).

**Assertion Library:**

- pytest: bare `assert`, `pytest.raises(...)`, `pytest.mark.parametrize` (487 uses).
- unittest: `self.assertEqual`, `self.assertIn`, `self.subTest(...)`.
- Playwright: `expect(locator).toHaveText(...)`, `toBeVisible()`, `toHaveCount(...)`, role-based locators (`page.getByRole('button', { name: 'Export', exact: true })`).
- node:test: `require('node:assert/strict')` (`assert.match`, `assert.doesNotMatch`).

**Run Commands:**

```bash

# Every command needs HYPRN_MVP_DATA_ROOT=<development data root> (outside the repository, not synced)

python3 -B deployment/checks.py --list                    # every group: name, class, needs
python3 -B deployment/checks.py --list --class must-pass  # must-pass groups only
python3 -B deployment/checks.py --group <group>           # one group in a fresh scope
python3 -B deployment/checks.py --group qualification     # all must-pass groups in order; stops at first failure
python3 -B deployment/checks.py --group units-native --units-mixed-repair  # the one extra mixed-repair journey

# Design and UI checks (also run together by the combined-static group)

python3 ui/check_design_system.py          # no FAIL line (WARN lines are the recorded baseline)
python3 ui/design_tokens.py --check        # generated tokens current
python3 ui/check_ui_contract.py            # UI source wiring, public routes/types, control map
python3 ui/test_design_tooling.py          # unittest for the design tooling
node ui/design_smoke.mjs                   # render every design component once
node ui/node_modules/typescript/bin/tsc --noEmit -p ui/tsconfig.json
npm --prefix ui ci && npm --prefix ui run build
```

Runner exit codes: `0` passed, `1` failed, `2` refused (`Check refused: <reason>` on stderr: unknown group, missing target, missing need, wrong interpreter, unset location), `124` Documents child timeout.

No watch mode and no coverage command exist.

## Group Registry (`deployment/checks.py`)

**Registration:**

- `GROUPS` maps a kebab-case group name to a tuple of repo-relative targets (files or `file::test_name` nodes). Example:

```python
'units-history': ('application/tests/test_unit_history.py',),
'bindings': ('application/tests/test_result_bindings.py',
    'integration/tests/test_submission.py::test_fault_windows_never_blindly_redispatch', ...),
'ui-reading': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
               'ui/tests/screen-readability.spec.ts', 'ui/tests/evidence-workspace.spec.ts',
               'ui/tests/record-labels.spec.ts'),
```

- `DOCUMENTS_ROUTES` adds Documents groups with a `mode` (`native` or `application/contracts`), targets and a `selector` prefix; the runner parses targets with `ast` and selects `test_<group with underscores>_*` functions without importing them.
- Family sets decide routing, interpreter and environment: `AE_*`, `APPROACH_*`, `UNITS_*` (`_NATIVE_GROUPS`, `_APP_GROUPS`, `_BROWSER_GROUPS` with `@tag` selectors), `NATIVE_PYTEST_GROUPS`, `APPLICATION_PYTEST_GROUPS`, `MODELING_PYTEST_GROUPS`, `LOCALITY_PYTEST_GROUPS`, `RELEASE_PYTEST_GROUPS`, `FOUNDRY_BROWSER_GROUPS`, `SERVED_BROWSER_GROUPS`, `SERVED_INSTALLATION_GROUPS`, `UNITTEST_GUARD_MODULES`, `FINDINGS_NATIVE_GROUPS`. Selections by keyword live in `UNITS_SELECTIONS` / `AE_SELECTIONS` (`-k test_generated_`).
- Routing is closed: a group cannot name arbitrary modules, and `--group` only accepts registered names.

**Class and needs:**

- Class: `must-pass` (default) or `opt-in` (`OPT_IN_GROUPS` = `ui-served` and `ui-fidelity`).
- Needs: `docker` (`DOCKER_GROUPS`: native backend, modeling, findings-native), `browser` (`BROWSER_GROUPS`: Node plus `ui/node_modules/playwright/cli.js`), `fixtures` (`FIXTURE_GROUPS`: durable fixture root present), `installation` (`HYPRN_MVP_UI_BASE_URL` and `HYPRN_MVP_UI_PASSWORD_FILE`). An absent need refuses with `environment absent: <need>` before any scope is allocated.
- `qualification` runs `must_pass_groups()` sequentially: static groups first, then `fixtures`, then `docker`, then browser and combined needs.

**Group families (current registry):**

- Guards: `guard`, `naming`, `hygiene`, `units-guards`, `findings-native-guards` (unittest).
- Contracts and data-only: `contracts`, `ae-contracts`, `approach-contracts`, `units-contracts`, `documents-contracts`, `documents-citation-contracts`, `documents-parser-adoption`, `locality-contracts` (golden corpus, module boundaries, contract errors).
- Application (no native backend): `ae-*` app groups, `approach-closure`, `approach-service`, `approach-api`, `approach-configuration`, `units-api`, `units-resolution`, `units-configuration`, `units-bundle`, `projection`, `bindings`, `runtime-observation`, `api-a`, `api-c`, `modified`, `fuel-platform`, `findings-history`.
- Native (AiiDA backend in scope, docker): `native-a`, `native-b`, `native-bindings`, `archive-*`, `bridge-history`, `combined-security`, `combined-native`, `ae-execution`, `ae-history`, `ae-export`, `ae-native`, `approach-bundle`, `approach-worker`, `approach-history`, `approach-export`, `approach-native`, `units-history`, `units-launcher`, `units-worker`, `units-attestation`, `units-native`, `investigation-*`, `fuel-native-provenance`, `documents-native-*`, `documents-collection-protocol`.
- Modeling: `units-model`, `ae-model`, `modeling-isolation` (owned modeling deployment in the scope).
- Browser, isolated double: `foundry-nav`, `ported-isolated`, `ui-navigation`, `ui-reading`, opt-in `ui-fidelity`.
- Browser, scoped real application: `ui-a`, `ui-a-retained`, `ui-b`, `ui-c`, `ae-ui-*`, `approach-ui-*`, `units-ui-*`, `findings-native`, `findings-native-read`.
- Browser, served installation (opt-in): `ui-served`.
- Static bundle: `combined-static` (design checks, UI contract check, node:test, `tsc`, `vite build` into the scope).
- Release tooling: `deployment-hardening`.

**Pass criteria (fail closed):**

- pytest groups: `status == 0`, passed > 0, no failed, no skipped (`pytest_qualification_passed` in `deployment/checks.py`). Native imports (`aiida`, `openmdao`, `openturns`) in `sys.modules` fail any group not in `NATIVE_BACKEND_GROUPS`; only `aiida` is allowed there.
- unittest groups: `result.testsRun > 0 and result.wasSuccessful() and not result.skipped` (`successful()`); `findings-native-guards` must run exactly 17 tests.
- Browser groups: Playwright JSON report with `expected > 0` and zero `unexpected`, `skipped`, `flaky`; the set of reported spec files must equal the group's registered specs (`report_passed` in `deployment/tests/foundry_ui_fixture.py`). Runs use `--forbid-only`, `--retries=0`, `workers: 1`.
- Documents groups: every target file reports passes, none failed or skipped; `documents-collection-protocol` must also leave measured evidence files (`documents_collection_evidence`).
- Fixed `file::test` nodes are parsed with `ast` before setup; a `skip`/`skipif`/`xfail` decorator or module `pytestmark` refuses the group (`'Required test skipped: ...'`).

**Adding a test to a group:**

1. Put the test in the component's `tests/` folder and name it after the invariant.
2. Add the file (or `file::test`) to `GROUPS` and the right family set; set `GROUP_INTERPRETERS` for application-only groups.
3. Update `deployment/tests/test_repository_guard.py`: its registry tests assert exact group sets (`test_approach_groups_fail_closed_before_allocation`, `test_ae_registry_has_exact_reviewed_groups_and_interpreters`, `test_every_group_has_a_class_and_known_needs`, `test_every_browser_spec_is_registered_in_a_group`).
4. For a browser spec, register it in a group (or `FIXTURE_BROWSER_SPECS`), give titles the group's `@tag`, and map any named control in `ui/control-map.json`.
5. Record the exact command with pass and fail counts in the task checkpoint (see `.planning/phases/01-repository-baseline/checkpoints/1.9.md`).

## Test File Organization

**Location:**

- Separate `tests/` folder per component, never co-located with source:
  - `application/tests/` (pytest, 45+ modules; `conftest.py` sets import roots and `LOOPBACK_ORIGIN`).
  - `integration/tests/` (pytest; `conftest.py` prepends `integration/src`, `application/src`, repo root).
  - `contracts/tests/` (pytest; data-only schema tests plus the live modeling-contract client).
  - `modeling/tests/` (pytest against the modeling service / native generator).
  - `deployment/tests/` (fixtures, guards, native journeys, release hardening).
  - `ui/tests/` (Playwright specs, `foundry-fixtures.ts`, `support/browser.ts`, `support/served.ts`, `evidence.ts`, `criterion-record.test.cjs`).
  - `ui/test_design_tooling.py` (unittest beside the tools it tests).
- The runner passes `--noconftest`; conftest files apply only to ad-hoc runs. The runner inserts `application/src`, `application/tests`, `contracts/tests`, `integration/src`, `integration/tests` into `sys.path` itself.

**Naming:**

- Python: `test_<capability>.py`; fixture/capability modules `<capability>_fixture.py`, `<capability>_native_fixture.py`, `<capability>_ui_fixture.py`, `execution_fixtures.py`, `native_origin_fixture.py`.
- Browser: `<feature>.spec.ts`; title prefix `@<group-tag>` when a group selects by tag.

**Structure:**

```
application/tests/
├── conftest.py                       # import roots, LOOPBACK_ORIGIN
├── fixtures/identity_golden.json     # golden identity corpus (pinned by sha256)
├── test_api.py                       # shared `api` fixture and helpers (study, model_revision, post)
└── test_<capability>.py
integration/tests/
├── fixtures/native-programs.json.gz  # frozen prepared programs (README.md explains capture)
├── fixtures/units-native-evidence.json
├── execution_fixtures.py             # contract fixtures, scoped_evidence_root()
├── capture_native_programs.py        # capture tool for the frozen programs
└── test_<capability>.py
contracts/tests/
├── documents_prior_definitions.json  # released definition digests
├── test_modeling_contract.py         # live Client + shared builders (creation, candidate, source)
└── test_<contract>.py
deployment/tests/
├── scoped_fixture.py                 # scope allocation, clean env, native backend, worker attestation
├── live_fence.py                     # audit-hook fence installed by every deployment test module
├── durable_fixture.py                # durable native fixture resolver and capture tool
├── *_fixture.py / *_ui_fixture.py    # group fixtures (native journeys, browser servers)
└── test_*.py                         # guards, native journeys, hardening
ui/tests/
├── foundry-fixtures.ts               # isolated in-browser API double + static server
├── support/{browser,served}.ts       # Chromium resolution, served-installation variables
├── evidence.ts                       # evidence root helper
└── *.spec.ts, criterion-record.test.cjs
```

**Test modules as helper libraries:** several test modules export fixtures and builders imported by other tests across roots. Keep their helper names stable:

- `application/tests/test_api.py` → `api`, `study`, `model_revision`, `post`, `uid`, `candidate` (used by `test_public_contract.py`, `test_run_api.py`, `test_configuration.py`, `test_scoped_evidence.py`, `test_security_regressions.py`, `test_ui_static.py`, `test_ui_discovery.py`).
- `contracts/tests/test_modeling_contract.py` → `Client`, `creation`, `candidate`, `source`, `digest`, `canonical`, `numerical`, `validate` (used by `contracts/tests/test_contract_boundaries.py`, `test_portability.py`, `modeling/tests/*`, `deployment/tests/test_modeling_isolation.py`, `deployment/tests/units_model_fixture.py`). Its sha256 is pinned in `contracts/tests/test_unit_declaration_contracts.py`.
- `application/tests/test_reuse_api.py` → records used by `deployment/tests/ui_fixture.py`.

## Test Structure

**pytest suite organization (application):**

```python
@pytest.fixture
def api(tmp_path):
    store=Store(tmp_path/"app.sqlite")
    auth=Auth(store,ORIGIN);actor=auth.provision("owner","correct horse battery staple")
    transport=FaultTransport()
    model=ModelingClient("http://modeling:3000/modeling/1",
        b"synthetic-model-credential",transport=transport)
    app=create_app(store,auth,model)
    client=TestClient(app,base_url=ORIGIN)
    session=client.post("/api/1/session",json={"username":"owner","password":"correct horse battery staple"},headers={"Origin":ORIGIN})
    assert session.status_code==200,session.text
    client.headers.update({"Origin":ORIGIN,"X-CSRF-Token":session.json()["data"]["csrf_token"]})
    return client,store,auth,model,transport,actor
```

(`application/tests/test_api.py`). Every API test gets a fresh SQLite store under pytest `tmp_path` (which the runner places at `<scope>/tmp/pytest`) and the in-process `TestClient` on `LOOPBACK_ORIGIN = 'http://127.0.0.1:19999'` (nothing listens there).

**unittest guard organization:**

```python
class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_live_cloud_relative_and_traversal_roots_refused(self):
        ...
```

(`deployment/tests/test_repository_guard.py`). Guard classes group by concern: `RegistryGuardTests`, `DocumentsGuardTests`, `LocationResolutionTests`, `LiveFenceTests`, `DurableFixtureGuardTests`, `BrowserSpecRegistryTests`.

**Playwright organization (isolated double):**

```typescript
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture);
test.beforeEach(async ({ page }) => { await guardOrigin(page); });
test.afterAll(stopFixture);
test('model quantities inspect their component; tables, XDSM and portability stay concise', async ({ page }) => {
  const state = await harness(page); referenceModel(state);
  await login(page, `#v=1&study=${sid}&model=${mid}&view=model`);
  ...
  expect(state.writes).toEqual([]); expect(state.unknown).toEqual([]);
});
```

(`ui/tests/model-configuration-run.spec.ts`). The `test.skip` guard makes a missing build a skip, which the runner counts as a failure, so the group never passes silently.

**Patterns:**

- Setup: build state through the public API or the real store, never by writing rows directly (except deliberate tamper/corruption tests).
- Teardown: pytest `tmp_path` and the scope folder; unittest `self.addCleanup(shutil.rmtree, self.scratch, True)` or `tempfile.TemporaryDirectory` in `setUp`/`tearDown` (`deployment/tests/test_term_scan.py`, `ui/test_design_tooling.py`).
- Assertions check exact envelopes and identities: `assert (error.code, error.status, error.outcome) == ('invalid_request', 400, 'unchanged')`.
- Assert absence of side effects explicitly: `assert len(transport.calls)==before` after a refused command; `expect(state.writes).toEqual([])` in read-only browser tests.
- Assert restart behaviour by building a second app on the same store: `restarted=TestClient(create_app(Store(store.path),auth,model),base_url=ORIGIN)`.

## Scoped Scratch Stores (`deployment/tests/scoped_fixture.py`)

**Layout:** `<scratch root>/hyprn-mvp-test-<run uuid>/` with `scope.json` (marker), `home/`, `tmp/`, `aiida/`, `native/`, `artifacts/`, `evidence/`, all mode `0700`. Scratch root is `HYPRN_MVP_SCRATCH_ROOT` (default: the OS temporary folder, resolved). The prefix is `local_paths.SCOPE_PREFIX`.

**API to use:**

- `new_scope(*, url=None)` → `Scope(root, run_uuid, profile, profile_uuid, store_uuid, backend='core.sqlite_dos', interpreter, url)` with three distinct fresh UUIDs.
- `allocate_scope(scope)`: validates every field before the first write, refuses an existing root, creates the folders and writes the marker with `open('x')`.
- `validate_scope(scope)`: canonical absolute path, no symlink anywhere on the path, root under the scratch root, UUID identity, reviewed interpreter, isolated loopback URL only, no default or foreign AiiDA profile, repository identity matches the marker.
- `scoped_path(scope, relative)`: the only way to build a path inside a scope; refuses absolute paths, `..`, backslashes, symlinks and escapes.
- `clean_environment(scope)`: the exact child environment (`PATH`, `HOME=<scope>/home`, `TMPDIR=<scope>/tmp`, `AIIDA_PATH=<scope>/aiida`, `HYPRN_MVP_TEST_SCOPE_ROOT`, `HYPRN_MVP_TEST_SCOPE_PROFILE`, optional `HYPRN_MVP_TEST_SCOPE_URL`, plus pass-through location variables). No ambient credential reaches a child.
- `guarded(scope, callback, *, env=None)`: runs the callback only if the environment equals `clean_environment(scope)` exactly.
- `scope_from_environment()`: in a child, reload and validate the scope named by `HYPRN_MVP_TEST_SCOPE_ROOT`; call it before any import, build or write. `scope_at(path)` resolves the scope owning a path from inside a running test.
- `create_native_fixture(scope)`: one fresh AiiDA test profile (`test_profile=True`) and `core.sqlite_dos` storage in `<scope>/native`; pins the actual repository UUID into the marker before any node is stored.
- `prepare_worker_fixture(scope, backend)`, `change_worker_fixture_identity(scope)`, `build_derived_image(...)`: build and attest the restricted worker in the scope; derived images are labelled `org.hyprn-mvp.test-scope=<run uuid>` and tagged `hyprn-mvp-<role>:<digest16>`.
- `launcher_command(scope)`: runs `deployment/tests/scoped_fixture_launcher.py` with `env -i` and the clean environment, bound to this tree (never a checkout named by an interpreter `.pth`).

**Rules:**

- Tests never touch a user installation, live store, live port or development store. A browser URL must be `http://127.0.0.1:<port>` with port ≥ 1024 and not in `HYPRN_MVP_LIVE_PORTS` (`validate_url`).
- Docker resources created by a fixture carry the scope label and scope-derived names (`hyprn-mvp-test-<scope8>-modeling`, `-private`); remove them when the run ends. A retained fixture capture refuses a producer scope with containers left.
- Evidence (logs, reports, screenshots, `tests.json`, `result.json` with source sha256 of every target) stays in `<scope>/evidence/`, never in the repository. Record released scopes in the task checkpoint.
- Native integration evidence goes through `scoped_evidence_root()` / `require_scoped_runtime()` (`integration/tests/execution_fixtures.py`); outside a scope they raise instead of guessing.

## Live-Runtime Fence (`deployment/tests/live_fence.py`)

Every `deployment/tests/test_*.py` must import the fence right after its docstring and declare a policy (enforced by `test_fenced_deployment_modules_are_declared` in `deployment/tests/test_repository_guard.py`):

```python

# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.

import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')           # pytest module

# setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')   # unittest module

```

- `unit` policy: no docker, docker sockets or non-probe signals. Use it for any module that needs no container (`test_deployment_hardening.py`, `test_bridge.py`, all guards).
- `baseline` policy: docker allowed except against live names/paths; for native journeys (`test_native_journey.py`, `test_units_native.py`, `test_approach_native.py`, `test_attestation.py`, `test_modeling_isolation.py`, ...).
- The fence is a process-wide audit hook; a trip raises `LiveRuntimeAccess` and fails the test even if product code catches it.

## Mocking

**Framework:** No general mocking library in product tests. Use hand-written, declared test doubles and pytest `monkeypatch` (48 modules). `unittest.mock` (`Mock`, `patch`) appears only in deployment guard tests (`test_repository_guard.py`, `test_attestation.py`, `test_findings_native_guards.py`, `test_units_fixture_guards.py`).

**Patterns:**

```python
class FaultTransport:
    def __init__(self):self.fail_before=False;self.fail_after=False;self.calls=[];self.tamper=False
    def __call__(self,method,path,body,headers):
        self.calls.append((method,path))
        if self.fail_before:raise OSError("synthetic unavailable")
        status,result=raw_request(method,path,body,headers)
        if self.fail_after and method=="POST":
            self.fail_after=False
            raise OSError("response lost after durable remote commit")
        ...
```

(`application/tests/test_api.py`: wraps the real private-contract request; injected through `ModelingClient(..., transport=transport)`.)

```python
class Crash(BaseException): pass

class NativeDouble:
    def require_attestation(self):return True
    def launch(self,bundle,request):
        self.launches+=1
        if self.mode=='before_node':raise Crash('before durable node')
        ...
```

(`integration/tests/test_submission.py`: fault windows around durable dispatch; `Crash` subclasses `BaseException` so product `except Exception` cannot swallow it.)

```python

# The bundle id is a fresh identifier at assembly; pin it to the captured value.

monkeypatch.setitem(assemble_bundle.__globals__, 'uid', lambda: inputs['bundle_id'])
```

(`application/tests/test_identity_golden.py`.)

Browser doubles intercept every API call with `page.route('**/api/1/**', ...)` inside `harness(page)` (`ui/tests/foundry-fixtures.ts`) and record `state.writes` and `state.unknown`; `guardOrigin(page)` aborts any request to another origin.

**What to Mock:**

- The private modeling transport (`ModelingClient` transport callable), the native launcher/record reader (`NativeDouble`), the API in isolated browser groups, docker/HTTP/signals in release-tooling tests (`deployment/tests/test_deployment_hardening.py`: "docker, HTTP, signals and the live runtime are faked or refused").
- Fresh identifiers or time only where a golden value must be reproduced.

**What NOT to Mock:**

- Canonical JSON, digests, schema validation, the SQLite store and receipts: use the real ones on a fresh store.
- Native proof: "test doubles never stand in for native proof" (`integration/tests/test_submission.py` docstring). Numerical results, generated programs and attestations come only from native groups.
- Never synthesize generated classes or rebind generated identifiers (`integration/tests/fixtures/README.md`).
- Isolated browser evidence is not acceptance of the real API; served/scoped groups and human acceptance are recorded separately.

## Fixtures and Factories

**Builders:** module-level helpers return plain dicts built through public operations:

```python
def study(api):
    return post(api[0],"/studies",dict(command_id=uid(),name="Study"),201)["data"]

def model_revision(api):
    c=api[0];s=study(api);sid=s["study_id"]
    m=post(c,f"/studies/{sid}/models",dict(command_id=uid(),expected_revision=s["revision"],name="Independent app model",template="empty"),201)["data"]
    ...
```

(`application/tests/test_api.py`.) Contract builders `creation()`, `candidate(model, study)`, `source(...)` live in `contracts/tests/test_modeling_contract.py`; legacy schema-1 data comes from `legacy_fixture()` in `integration/tests/execution_fixtures.py`.

**Golden identity corpus (`application/tests/fixtures/identity_golden.json`):**

- Pins canonical bytes and digests of canonical values, canonicalization refusals, evidence snapshots, receipts, bundle manifests and executable digests.
- The test pins the corpus bytes (`CORPUS_SHA256`) and its capture commit; blobs are base64 with sha256 keys, some resolved from `integration/tests/fixtures/native-programs.json.gz`.
- A mismatch means an existing record identity would change: fix the code, never the corpus. Regenerating it requires an explicit reviewed change of the pin.

**Frozen native programs (`integration/tests/fixtures/native-programs.json.gz`):** exact prepared artifacts captured with `integration/tests/capture_native_programs.py` from the pinned modeling producer image (`deployment/pins.json`). Data only; never extracted or imported. Negative cases are derived in tests, not stored.

**Durable native fixture (`deployment/tests/durable_fixture.py`):**

- Lives below `HYPRN_MVP_TEST_FIXTURES_ROOT` (default `<data root>/fixtures`), never in the repository. Pinned by `NATIVE_FIXTURE` (folder name) and `NATIVE_MANIFEST_SHA256`.
- Every file read is size- and sha256-checked; unlisted entries fail; absence or mismatch raises `FixtureUnavailable` with the reason, no fallback.
- `native_scope()` materializes a disposable working copy at the producer's original scope root (requires the same `HYPRN_MVP_SCRATCH_ROOT`).
- Capture a new one from a fully passing `units-native` producer scope: `python3 -B deployment/tests/durable_fixture.py capture --scope <producer scope root>`; then pin the new manifest digest. Never modify an existing fixture.
- Groups reading it: `findings-native-preflight`, `findings-native`, `findings-native-read`, `approach-ui-history` (`FIXTURE_GROUPS`).

**Other pinned data:** `contracts/tests/documents_prior_definitions.json` (released definition digests), `ui/tests/foundry-fixtures.ts` `unitCatalog` (identical to the catalog in `application/tests/test_unit_guidance_api.py`).

## Contract Tests

- Data-only schema tests (`contracts/tests/test_reuse_contract.py`, `test_assumptions_evidence_contracts.py`, `test_approach_contracts.py`, `test_unit_declaration_contracts.py`, `test_documents_contract.py`) validate wire examples with `jsonschema.Draft202012Validator` against `contracts/schemas/model.schema.json` and `execution.schema.json`; no model service, native store or candidate import. Heavy use of `@pytest.mark.parametrize` over accepted and refused shapes.
- Live modeling-contract tests (`contracts/tests/test_modeling_contract.py`, `test_contract_boundaries.py`, `test_portability.py`) talk to a modeling service through `Client`; import tests read `HYPRN_MVP_MODEL_IMPORT_URL` and `HYPRN_MVP_MODEL_IMPORT_KEY_FILE`.
- Public API contract: `application/tests/test_public_contract.py` asserts the set of actual routes equals the documented paths, that every operation documents 400/401/403/404/409/413/422/503, and validates representative responses against `contracts/hyprn-mvp.openapi.yaml`. The document is regenerated from code by `application/generate_contract.py`; generated UI types by `ui/generate_types.py`.
- `application/tests/test_contract_errors.py`: field-level diagnostics and the unchanged envelope.
- `application/tests/test_module_boundaries.py`: import directions, owner tables, attested-source coverage of the launch path.
- Every API change keeps contract tests and the UI contract checker green (`AGENTS.md`).

## UI Contract Checker (`ui/check_ui_contract.py`)

- Stdlib source guard: asserts required strings in UI sources (`checks['src/RunPanel.tsx'] = [...]`), forbids live reads inside retained views, checks public routes and types in `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts`.
- `ui/control-map.json` maps each named control (`"approach-01"`) to a spec file and a test title fragment; a missing spec or title fails the check.
- It is a wiring guard, never behavioural proof; behaviour is proven only by the browser groups.
- When adding a UI control or wiring: add the source string check and a control-map entry pointing at the spec test that proves it.

## Design-System Checks

- `ui/check_design_system.py`: baseline-aware style guard (see CONVENTIONS.md). Change `ui/design-baseline.json` with `--update-baseline` only for lines your change moved, and say so in the commit.
- `ui/design_tokens.py --check`: generated `tokens.css` is current.
- `ui/test_design_tooling.py`: unittest of the generator and guard in `tempfile.TemporaryDirectory(prefix='hyprn-mvp-design-tokens-')`.
- `ui/design_smoke.mjs`: Vite SSR build of `src/design/index.ts` into a temp folder (or `HYPRN_MVP_UI_EVIDENCE_ROOT`, which must be outside the repository), renders each component, prints `PASS`/`FAIL` lines.
- `ui/tests/criterion-record.test.cjs`: transpiles `ui/src/design/primitives.tsx` with TypeScript and asserts scientific-state wording (zero shown as `0`, null as "unassigned", no invented assessment).

## Browser Tests (Playwright)

**Three modes:**

1. Isolated in-browser double (`foundry-nav`, `ported-isolated`, `ui-navigation`, `ui-reading`, `ui-fidelity`): `deployment/tests/foundry_ui_fixture.py` builds the current `ui/` into `<scope>/artifacts/nav-dist` (`HYPRN_MVP_NAV_BUILD`), writes a Playwright config into the scope and runs the group's fixed specs; `ui/tests/foundry-fixtures.ts` serves the build on an ephemeral loopback port and answers every API call. No application, modeling or native process is started.
2. Scoped real application (`ui-a`, `ui-b`, `ui-c`, `ae-ui-*`, `approach-ui-*`, `units-ui-*`): `deployment/tests/ui_fixture.py`, `ae_ui_fixture.py`, `approach_ui_fixture.py`, `units_ui_fixture.py` serve the actual Workspace, API, Auth and Store on a scope-bound loopback socket with fresh SQLite; the private modeling transport is a declared double. `ui/playwright.isolated.config.ts` re-validates the scope with `deployment/checks.py --validate-browser` before discovery.
3. Served installation (`ui-served`, opt-in): `ui/playwright.config.ts` talks to `HYPRN_MVP_UI_BASE_URL` with the owner password from `HYPRN_MVP_UI_PASSWORD_FILE` (`ui/tests/support/served.ts`). The runner refuses the development installation's port, live ports and password files inside stores or live roots. Only an installation created for testing may serve it.

**Settings (all modes):** `workers: 1`, `retries: 0`, `forbidOnly`, `timeout: 45000`, `expect.timeout: 8000`, `actionTimeout: 8000`, viewport `1440 × 1000`, `trace: 'off'` (no credentials in traces), `screenshot: 'only-on-failure'`, Chromium `channel: 'chrome'` (or `HYPRN_MVP_CHROMIUM`, resolved by `ui/tests/support/browser.ts`). Output and snapshots go to `<scope>/evidence/browser` and `<scope>/evidence/snapshots`.

**Screen evidence:** capture both themes with `page.emulateMedia({ colorScheme })` for `'light'` and `'dark'` into `process.env.HYPRN_MVP_UI_EVIDENCE_ROOT`. Automated browser evidence is never human acceptance; record product-owner acceptance separately.

**Locators:** prefer roles and exact accessible names (`getByRole('tab', { name: 'XDSM', exact: true })`); use design-layer classes (`.hf-criterion__number`) or data attributes (`[data-variable]`) for structure checks.

## Coverage

**Requirements:** None enforced. No coverage tool is configured.

Coverage is expressed structurally instead:

- Every browser spec must be registered in a group (`test_every_browser_spec_is_registered_in_a_group`).
- Every named UI control maps to a spec test (`ui/control-map.json`).
- The attested source set must equal the launch-path import closure (`application/tests/test_module_boundaries.py`).
- `PENDING` tables in guard modules (`test_repository_guard.py`, `test_naming_guard.py`, `test_hygiene_guard.py`) list known failures owned by a later task; a stale entry fails the guard. All are currently empty.

**Python test modules not listed as a direct target of any group** (some are helper libraries imported by registered tests; none runs through `qualification` on its own): `application/tests/test_api.py`, `test_authorization.py`, `test_configuration.py`, `test_history.py`, `test_ownership.py`, `test_public_contract.py`, `test_run_api.py`, `test_scoped_evidence.py`, `test_security_regressions.py`, `test_ui_discovery.py`, `test_ui_static.py`; `integration/tests/test_configuration.py`, `test_execution.py`, `test_history_read.py`, `test_isolation.py`, `test_native_parser.py`, `test_profile_identity.py`; `contracts/tests/test_contract_boundaries.py`, `test_modeling_contract.py`, `test_native_program_contract.py`, `test_portability.py`, `test_ui_discovery_contract.py`; `modeling/tests/test_atomic_adapter.py`, `test_ui_discovery.py`; `deployment/tests/test_initialize_stores.py`, `test_term_scan.py`, `test_topology.py`. To make one count, register it in `GROUPS`.

## Test Types

**Unit / application tests:**

- `application/tests/*`: real `Store` on `tmp_path`, in-process FastAPI `TestClient`, injected modeling transport. No network, no native imports.
- Marked `quick` in `integration/tests/test_execution.py` for pure boundary and submission tests.

**Contract tests:** `contracts/tests/*` (see above).

**Integration (native) tests:**

- `integration/tests/*` marked `integration` / `isolation`; run in native groups with one fresh AiiDA backend per scope (`create_native_fixture`) and an attested worker (`prepare_worker_fixture`). Docker required.

**Native journeys (end to end, Docker):**

- `deployment/tests/test_native_journey.py`, `test_units_native.py`, `test_approach_native.py`, `test_assumptions_evidence_journey.py`, `test_investigation_native.py`, `test_findings_native.py`, `test_modeling_isolation.py`, `test_attestation.py`, driven by `*_native_fixture.py` journeys that start an owned modeling service on an internal scope network, the application, and the attested worker. They read scope globals from the runner: `from checks import PROJECTION_SCOPE, NATIVE_BACKEND`.

**E2E browser tests:** Playwright (see above).

**Guards:** unittest repository, naming, hygiene, term-scan, fixture and registry guards; detectors are tested against synthetic violations assembled at run time (`test_detectors_flag_synthetic_violations`).

## Common Patterns

**Concurrency and races:**

```python
from concurrent.futures import ThreadPoolExecutor

# integration/tests/test_submission.py: same command concurrently, restart, payload conflict

```

```typescript
export function latch() { let release!: () => void; const promise = new Promise<void>(resolve => { release = resolve; }); return { promise, release }; }
// ui/tests/foundry-fixtures.ts: hold a response (state.delayStudy) to test late responses across study or actor changes
```

**Async browser testing:**

```typescript
const downloading = page.waitForEvent('download');
await page.getByRole('button', { name: 'Quantities CSV', exact: true }).click();
const download = await downloading;
```

**Error testing:**

```python
def rejected(name, value, **kw):
    with pytest.raises(DomainError) as caught:
        validate(name, value, **kw)
    return caught.value

def test_remote_payload_failure_keeps_backend_unavailable_without_details():
    error = rejected('Diagnostic', dict(path=SECRET), remote=True)
    assert (error.code, error.status, error.outcome, error.fields) == ('backend_unavailable', 503, 'unknown', [])
```

(`application/tests/test_contract_errors.py`.) For HTTP: `post(c, path, body, 409)` asserts the status and returns the JSON; refusals also assert no side effect.

**Tamper and fail-closed testing:** mutate a marker, manifest or stored byte inside the scope, assert the refusal, then restore (`test_isolated_runtime_root_refusals` in `deployment/tests/test_native_journey.py` rewrites `scope.json` in `try/finally`).

**Parametrized refusals:**

```python
@pytest.mark.parametrize('path',['.aiida/other.json','../.aiida/calcinfo.json','a//b','a'*513, ...])
def test_native_repository_inventory_rejects_other_hidden_or_unsafe_paths(path):
    with pytest.raises(ValidationError):
        validate('RepositoryInventory',dict(node_uuid=uid(1),path=path,size=1,sha256=SHA))
```

(`contracts/tests/test_reuse_contract.py`.)

**Skips:** never skip a registered test; a skip fails the group. The only conditional skip in Python is `@pytest.mark.skipif(not os.environ.get(WHEEL_VARIABLE), ...)` on `test_supplied_parser_wheel_matches_lock` in `contracts/tests/test_document_parser_adoption.py`; it is outside the `test_documents_parser_adoption_*` selector, so the `documents-parser-adoption` group never collects it.

**Checkpoint evidence:** each task's checkpoint records the exact `deployment/checks.py --group` commands with pass/fail counts, every failure (RED) and the repair (GREEN on the committed tree), source and artifact identities, and released scratch scopes (example: `.planning/phases/01-repository-baseline/checkpoints/1.9.md`).

---

*Testing analysis: 2026-10-13*
