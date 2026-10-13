---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
# Coding Conventions

**Analysis Date:** 2026-10-13

Binding sources for every convention below: `AGENTS.md` (repository rules), `CONTEXT.md` (domain language), `docs/specs/architecture-and-contracts.md` (ownership and guarantees), `application/README.md` (module ownership table), `design-system/README.md` and `.claude/skills/hyprn-mvp-ui/SKILL.md` (UI rules). Several conventions are enforced by tests; the enforcing file is named next to each rule.

## Naming Patterns

**Files:**

- Python packages are `hyprn_mvp_*` only: `application/src/hyprn_mvp_app/`, `integration/src/hyprn_mvp_integration/`, future `editions/local/src/hyprn_mvp_local/`. Enforced by `deployment/tests/test_naming_guard.py` (`test_packages_use_the_product_namespace`).
- Python modules are short lowercase snake_case nouns named after the capability they own: `store.py`, `history.py`, `result_bindings.py`, `modified_runs.py`, `execution_bundle.py`, `approach_closure.py`.
- Test modules are `test_<capability>.py` (`application/tests/test_unit_history.py`). Fixture modules are `<capability>_fixture.py`, `<capability>_native_fixture.py`, `<capability>_ui_fixture.py` (`deployment/tests/units_native_fixture.py`, `deployment/tests/approach_ui_fixture.py`).
- React components are `PascalCase.tsx` (`ui/src/RunPanel.tsx`, `ui/src/ConfigurationPanel.tsx`); non-component helpers are `camelCase.ts` (`ui/src/recordViews.ts`, `ui/src/accessLoss.ts`, `ui/src/criterionLabels.ts`).
- Playwright specs are `kebab-case.spec.ts` (`ui/tests/model-configuration-run.spec.ts`); the one node:test file is `ui/tests/criterion-record.test.cjs`.
- Contract files are exactly `contracts/hyprn-mvp.openapi.yaml` and `contracts/modeling.openapi.yaml` (naming guard `contracts` check).
- No file, group, test function or browser tag carries a work-item reference (phase numbers, task/wave numbers, `C4`, `P4-S6`, `01-09` style codes). Enforced by the `WORK_ITEM` regex in `deployment/tests/test_naming_guard.py`.

**Functions:**

- snake_case, short, often a bare noun for pure helpers: `canonical`, `digest`, `uid`, `raw_hash`, `data_json`, `validate` (`application/src/hyprn_mvp_app/contracts.py`).
- Module-private helpers take a leading underscore: `_violations`, `_execution_schema` (`contracts.py`), `_interpreter` (`deployment/tests/scoped_fixture.py`).
- Test functions state the invariant as a sentence: `test_missing_and_unknown_fields_are_reported_per_field_not_at_root` (`application/tests/test_contract_errors.py`), `test_canonical_bytes_and_digest_unchanged` (`application/tests/test_identity_golden.py`). Never name a test after a work item.
- Documents groups select tests by prefix: a test in a Documents group is named `test_<group with underscores>_*` (for example `test_documents_native_atomicity_*`). See `documents_targets()` in `deployment/checks.py`.
- Browser test titles start with their group tag: `test('@approach-controller keeps precise validation fields ...')` in `ui/tests/approach.spec.ts`. The runner selects with `--grep @<tag>`.
- TypeScript functions and React hooks are camelCase (`runPending`, `useAccessLoss`); React components are PascalCase (`RunPanel`, `EvidenceIndex`).

**Variables:**

- Python constants are UPPER_SNAKE at module top: `MAX_DIAGNOSTICS`, `TEXT_LIMIT` (`contracts.py`), `REPO`, `GROUPS`, `DOCKER_GROUPS` (`deployment/checks.py`), `CORPUS_SHA256` (`application/tests/test_identity_golden.py`).
- `REPO = Path(__file__).resolve().parents[N]` is the standard way to reach the repository root from any file; never write an absolute path.
- Environment variables are `HYPRN_MVP_*` or a closed list of standard/tool variables (`HOME`, `PATH`, `TMPDIR`, `AIIDA_PATH`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD`, `PYTHONDONTWRITEBYTECODE`, ...). Enforced by `deployment/tests/test_naming_guard.py` (`test_environment_variables_use_the_product_prefix_or_a_closed_standard_list`). Declare each location variable name once as a constant in `deployment/local_paths.py` (`DATA_ROOT = 'HYPRN_MVP_DATA_ROOT'`).
- TypeScript: camelCase locals; short ids in test doubles are typed UUID constants (`sid`, `mid`, `version` in `ui/tests/foundry-fixtures.ts`).

**Types:**

- Domain service classes are PascalCase plural nouns owning one capability: `Configurations`, `Approaches`, `Submissions`, `ResultBindings`, `ModifiedRuns`, `History`, `Coordinator`, `ModelingClient`, `Store`, `Auth` (wired in `create_app` in `application/src/hyprn_mvp_app/api.py`).
- Exceptions end in `Error` or name the refusal: `DomainError`, `ContractError` (`contracts.py`), `FixtureUnavailable` (`deployment/tests/durable_fixture.py`), `LiveRuntimeAccess` (`deployment/tests/live_fence.py`), `LocationUnset` (`deployment/local_paths.py`).
- Wire schema and request-model versions are suffixed numbers, never edited in place: `NewModel3`, `EvidenceV2`, `ConfigurationCommitV2` (Pydantic, `api.py`); `ConfigurationRequest3`, `ModifiedRunSeedRead6`, `ExecutionBundle4`, `RunHistory2` (schemas). Add a new numbered definition for a change; keep old ones readable.
- Pydantic request models inherit a closed base: `class Closed(BaseModel): model_config=ConfigDict(extra="forbid",strict=True)` (`api.py`). Every request body is closed and strict.
- Frozen dataclasses for identity records: `@dataclass(frozen=True) class Scope` (`deployment/tests/scoped_fixture.py`).
- TypeScript unions for closed states: `export type Tone = 'alarm' | 'warning' | 'advisory' | 'ok' | 'inert' | 'running';` (`ui/src/design/components.tsx`), `export type ReadFailure = 'stale' | 'access-lost' | 'transient' | 'error';` (`ui/src/api.ts`).

**Product-wide names (enforced by `deployment/tests/test_naming_guard.py`):**

- Container label keys start with `org.hyprn-mvp.` (`org.hyprn-mvp.test-scope=<run uuid>`).
- Container, network, image and project names start with `hyprn-mvp-` (`hyprn-mvp-test-<scope8>-modeling` in `deployment/tests/units_native_fixture.py`).
- OpenAPI extension keys start with `x-hyprn-mvp-`.

**Domain words (binding, `CONTEXT.md`):**

- Use the glossary term and never its _Avoid_ words in UI text, API descriptions, docs or new identifiers: "Configuration" not case/setup/scenario; "Run" not job/calculation; "Version" not revision/snapshot (a "Revision" is the changing marker of an editable item); "Criterion evaluation" not assessment/check result; "Execution bundle" not package; "Modeling approach" not workflow/pipeline; "Assumption" not note.
- "Package" means only a method package. Legacy wire names (`ModelPackageN`, the `package` request field, `model_package_manifest`) stay as documented in `contracts/README.md`; `application/tests/test_module_boundaries.py` guards the wording in the public API document.

## Code Style

**Formatting:**

- No formatter or linter is configured (no ruff, flake8, black, mypy, ESLint, Prettier or Biome config in the repository). Formatting is by convention only.
- Two Python styles coexist:
  - Dense style (no spaces around `=` or after `,`, `;`-joined statements, one-line `def`/`if` bodies) in `application/src/hyprn_mvp_app/api.py`, the lower half of `contracts.py`, `integration/src/hyprn_mvp_integration/launcher.py`, `application/tests/test_api.py`, `contracts/tests/test_contract_boundaries.py`, parts of `deployment/tests/scoped_fixture.py`.
  - PEP 8-like style (4-space indent, spaces around operators, lines up to ~120 columns, blank lines between top-level defs) in `deployment/checks.py`, `deployment/local_paths.py`, `deployment/tests/durable_fixture.py`, `application/tests/test_identity_golden.py`, `application/tests/test_contract_errors.py`, `ui/check_design_system.py`.
- Rule: when editing a file, match that file's existing style. Write new files in the PEP 8-like style. Never reformat a file you are not otherwise changing (`AGENTS.md`: "Never stage, stash, revert or reformat another task's files").
- Quotes: single quotes dominate in `deployment/` and newer tests; double quotes in `api.py` and `test_api.py`. Follow the file.
- TypeScript: 2-space indentation, single quotes, semicolons, long single-line expressions are common in `ui/src/api.ts` and specs. `ui/tsconfig.json` sets `"strict": true`, `"target": "ES2022"`, `"module": "ESNext"`, `"moduleResolution": "Bundler"`, `"jsx": "react-jsx"`, `"noEmit": true`.
- CSS: `ui/src/styles.css` is minified-style (many rules per line); `ui/src/design/foundry.css` holds design-layer classes. Use only `var(--…)` tokens for colour, size, spacing, radius and type.

**Linting (enforced checks that act as linters):**

- `python3 ui/check_design_system.py`: no new hex/rgb/hsl colours, px literals other than `1px`/`2px`, inline styles (`style=`, `setAttribute('style')`, `cssText`) or font declarations in `ui/src/**` outside `ui/src/design/**`. Existing violations live in `ui/design-baseline.json` (currently only `src/exports.ts` colours); WARN lines are the baseline, FAIL lines block.
- `python3 ui/design_tokens.py --check`: `ui/src/design/tokens.css` matches `design-system/tokens.json`.
- `node ui/node_modules/typescript/bin/tsc --noEmit -p ui/tsconfig.json`: type check.
- `deployment/tests/test_naming_guard.py`, `deployment/tests/test_hygiene_guard.py`: names, environment variables, home paths, private keys, token literals, tracked secret files. Both assemble every searched literal from fragments at run time so the guard file never contains what it searches for. Copy that technique for any new detector.
- `application/tests/test_module_boundaries.py`: import directions, owners, attested-source coverage.

**Language versions:**

- Python `>=3.12` (`application/pyproject.toml`, `integration/pyproject.toml`). Use `str | None`, `Path.is_relative_to`, `str.removeprefix`, `functools.cache`.
- `from __future__ import annotations` appears in `contracts.py` and `scoped_fixture.py`; optional elsewhere.
- Node tooling is ESM (`"type": "module"` in `ui/package.json`); `.mjs` for scripts, `.cjs` only for `ui/tests/criterion-record.test.cjs`.

## Import Organization

**Order (Python):**

1. Standard library (`import json`, `from pathlib import Path`).
2. Third-party (`import rfc8785`, `from jsonschema import Draft202012Validator`, `from fastapi import FastAPI`).
3. Local: relative imports inside a package (`from .contracts import DomainError, canonical, uid` in `api.py`); absolute package imports in tests (`from hyprn_mvp_app.store import Store`).

Ordering within groups is loose (not sorted). Tests that need extra roots insert them into `sys.path` before local imports and mark the following imports `# noqa: E402`:

```python
sys.path.insert(0, str(REPO / 'deployment'))
import release_binding as release  # noqa: E402
```

**Import ownership rules (enforced by `application/tests/test_module_boundaries.py`):**

- Import each name from its owner, never through a temporary forwarding alias. The `MOVED` table lists aliases that exist only for test imports: for example `canonical`, `digest`, `uid`, `DomainError` are owned by `hyprn_mvp_app.contracts`, not `hyprn_mvp_app.store`. Production code must write `from .contracts import canonical`, not `from .store import canonical`.
- `hyprn_mvp_integration` (launcher, calculation, results, computational_export) may import only the pure application modules `hyprn_mvp_app.contracts`, `units`, `scientific_configuration`, `approach_closure`, `execution_bundle`.
- The application import graph is acyclic, function-local imports included; `approach` never imports `configuration`; `history` is depended on by `result_bindings` and `modified_runs`, never the reverse.
- `contracts.py` may import only stdlib, `rfc8785` and `jsonschema`.
- Native packages (`aiida`, `openmdao`, `openturns`) are imported only inside functions that need them (see `create_native_fixture` in `deployment/tests/scoped_fixture.py`), so data-only modules stay importable without them. The runner fails any non-native group that ends with a native module in `sys.modules`.
- Stdlib-only modules (no third-party import at all): `deployment/checks.py`, `deployment/local_paths.py`, `deployment/tests/scoped_fixture.py`, `deployment/tests/durable_fixture.py`, `deployment/tools/term_scan.py`, `ui/check_design_system.py`, `ui/check_ui_contract.py`, `ui/design_tokens.py`, `ui/generate_types.py`, and the integration launcher.

**Order (TypeScript):**

- Value imports and `import type` imports mixed at the top; use `import type` for contract types: `import type { HistoryArtifact, ProgramSourceMapEntry } from './contract';`.
- Import screen building blocks only from the design barrel: `import { Button, Panel, Tabs, ... } from './design';`.
- Import the API client only from `./api`: `import { HyprnMvpApi, accessLostText, message } from './api';`.

**Path Aliases:**

- None. Use relative imports (`./design`, `./api`, `../src/contract` from tests).

## Error Handling

**Public error envelope (application):**

- Raise `DomainError(code, status=409, *, current_revision=None, fields=None, outcome="unchanged")` from `application/src/hyprn_mvp_app/contracts.py` for every client-visible failure. `DomainError.data()` is persisted in command receipts and replayed with `DomainError(**data)`; never change its shape.
- Schema failures are `ContractError(schema, code, status, fields=..., outcome=...)`, a `DomainError` subclass. Validate through `validate(name, value, *, remote=False)`:

```python
fields=_violations(lambda:VALIDATORS[name],value)
if fields:
    if remote:raise ContractError(name,"backend_unavailable",503,outcome="unknown")
    raise ContractError(name,"invalid_request",400,fields=fields)
return value
```

- Field diagnostics carry a JSON-pointer `path`, `code` `invalid` and a controlled message; at most `MAX_DIAGNOSTICS = 20`. Never echo the submitted value in a message (`application/tests/test_contract_errors.py` asserts a `SECRET` value never appears).
- A remote (modeling backend) payload failure is always `backend_unavailable` 503 with outcome `unknown` and no diagnostics, so backend details never reach clients.
- `create_app` in `api.py` maps every exception to the envelope: `DomainError` → its own status; `RequestValidationError` → `invalid_request` 400 with diagnostics; `HTTPException` → `resource_not_found`; any other `Exception` → `internal_error` 500 with outcome `unknown`.
- Outcome vocabulary is `unchanged`, `unknown`, `pending`; an uncertain outcome is reconciled by lookup, never re-dispatched.
- Use `raise ... from None` when the cause would leak input, `from error` when the cause is useful: `except (UnicodeError,RecursionError) as error:raise ValueError('Invalid bounded JSON') from error`.

**Scientific values:**

- Reject non-finite numbers, duplicate JSON keys and unsafe integers at the boundary (`data_json` and `canonical` in `contracts.py`). Never substitute a default for a missing input; an unavailable output is `null` with a reason.

**Tooling and fixtures (fail closed):**

- Raise `ValueError` with a refusal sentence (`raise ValueError('Unique scoped off-cloud root required')`). Validate every caller-controlled field before the first write (`allocate_scope` in `deployment/tests/scoped_fixture.py`).
- CLI entry points catch `(ValueError, OSError, TypeError)`, print `Check refused: <reason>` to stderr and exit 2 (`main()` in `deployment/checks.py`).
- Refusal messages name the variable, never its value: `local_paths` raises `LocationUnset` naming `HYPRN_MVP_DATA_ROOT`; `guarded()` says `'Unscoped environment or ambient credential rejected'` and never includes environment values.
- `LiveRuntimeAccess` (`deployment/tests/live_fence.py`) deliberately does not subclass `OSError` so product error handling cannot absorb it.

**UI:**

- API failures surface as `ApiError` carrying the contract `detail` (`ui/src/api.ts`). Convert to reader text with `message(error)`: `stale_revision` → "This model changed. Your edits are preserved; ...", `backend_unavailable` → "Modeling is unavailable. Your edits are preserved. ...", outcome `unknown`/`pending` → "Command outcome is uncertain. Check the original command before making more changes."
- Access denial is classified once by `accessDenied(error)` / `accessDeniedCodes`; reuse it instead of checking codes in screens.
- Error text says what happened, where, and the next safe action (`design-system/README.md`, Content fundamentals).

## Logging

**Framework:** None. No `logging` module is used in product code.

**Patterns:**

- Operational messages go to stderr with a role prefix and `flush=True`: `print(f'dispatcher: store busy ({error}); attempt {attempt}, retrying in {delay:g} s',file=sys.stderr,flush=True)` (`application/src/hyprn_mvp_app/dispatcher.py`, `readiness.py`).
- Machine-readable protocol lines are a fixed marker plus compact JSON on stdout: `print('\nHYPRN_MVP_RESULT_V1 ' + json.dumps(result, allow_nan=False, separators=(',', ':')), flush=True)` (`integration/src/hyprn_mvp_integration/worker.py`).
- Always serialize with `allow_nan=False` where output is parsed downstream.
- Test tooling records evidence as files inside the scope, not logs: `evidence/stdout.log`, `evidence/stderr.log`, `evidence/tests.json`, `evidence/result.json`, and prints one JSON summary line (`{"evidence": ..., "exit": ...}`) at the end (`run_group` in `deployment/checks.py`).
- Never log credentials, environment values or submitted input.

## Comments

**When to Comment:**

- Every module starts with a docstring saying what it owns, what it must not own or import, and the invariant it keeps. Example (`application/src/hyprn_mvp_app/contracts.py`): "Owns: canonical JSON bytes and digests ... It must not own or import SQLite, HTTP transport, authentication ...".
- Test module docstrings state the guarantee under test: `"""Golden identity corpus: existing canonical bytes and digests never change. ... fix the code, never the corpus."""`.
- Comments and test names state the invariant they protect, not the work item that introduced them (`AGENTS.md`). Write `# The bundle id is a fresh identifier at assembly; pin it to the captured value.`, not "added for task X".
- Explain refusals and boundaries inline where a reader could otherwise relax them: `# Explicit plugins only: installed native pytest entry points must not load.` (`deployment/checks.py`).

**Known deviations to avoid copying:**

- `deployment/tests/test_native_journey.py` keeps `"""Fresh Addition A checkpoint ..."""`, a `# P2 live-runtime fence` comment and `test_addition_a`/`test_addition_b` names.
- `application/src/hyprn_mvp_app/contracts.py` docstring cites `14-B1`/`14-B2` work items.
- `ui/tests/model-configuration-run.spec.ts` has `// Criteria render as numbered records since 261010-kpx-03`.

**Docstrings / TSDoc:**

- Python: short docstrings on public functions and classes, reST double backticks for code names (``DomainError``), no parameter tables. Example: `"""Validate ``value`` against the model-contract definition ``name``; return it unchanged."""`.
- TypeScript: `/** ... */` on exported types and helpers with non-obvious semantics (`ReadFence`, `ReadFailure`, `accessDeniedCodes` in `ui/src/api.ts`; `servedBaseUrl` in `ui/tests/support/served.ts`). Design-layer files open with a block comment stating the implementation rules (`ui/src/design/components.tsx`).

## Function Design

**Size:** Prefer small pure functions placed in the owning module ("move pure functions to their owner instead of creating service objects", `docs/specs/architecture-and-contracts.md`). Large files exist (`integration/src/hyprn_mvp_integration/worker.py` 1233 lines, `application/src/hyprn_mvp_app/store.py` 751 lines); do not add new capabilities to them when an owner module fits better.

**Parameters:**

- Use keyword-only arguments for options and flags: `def validate(name,value,*,remote=False)`, `def targets_for(group, *, repo=REPO, units_mixed_repair=False)`, `def new_scope(*, url=None)`.
- Inject dependencies through constructors: `create_app(store, auth, model)`; `ModelingClient(url, credential, transport=transport)` accepts a transport callable so tests can substitute one.
- Pass explicit locations; never compute a default path inside product code. Locations resolve through `deployment/local_paths.py`: flag → `HYPRN_MVP_*` variable → installation configuration → neutral default below `HYPRN_MVP_DATA_ROOT` → refuse with a message naming the variable.

**Return Values:**

- Validators return the value unchanged on success and raise on failure (`validate`, `validate_scope`, `no_symlinks`, `root_path`).
- API handlers return the envelope `{schema_version: "1", request_id, data, ...}` through the local `response()` helper in `create_app`.
- Status-returning CLIs return an int exit code from `main()` and call `sys.exit(main())`.

## Module Design

**Exports:**

- Python: no `__all__`; package `__init__.py` files are one line. Ownership is documented in `application/README.md` (Module ownership table) and pinned by `application/tests/test_module_boundaries.py`.
- One owner per capability: `store` owns transactions, receipts and exact evidence reads; `execution_bundle` owns the single `RETAINED_PAIRINGS` table; `units` owns `port_units`; `history` owns retained-run reading. Do not repeat these elsewhere.

**Barrel Files:**

- `ui/src/design/index.ts` is the only barrel: it re-exports components and types and imports no CSS. `ui/src/main.tsx` imports `./design/tokens.css`, `./design/foundry.css`, then `./styles.css` once.
- `ui/src/api.ts` re-exports all contract types (`export type * from './contract';`) so screens import types from `./api` or `./contract`.

**Generated files (never hand-edit):**

- `ui/src/contract.ts`: from `contracts/hyprn-mvp.openapi.yaml` by `python3 ui/generate_types.py`.
- `ui/src/design/tokens.css`: from `design-system/tokens.json` by `python3 ui/design_tokens.py`.
- `contracts/hyprn-mvp.openapi.yaml`: exported from the actual routes by `application/generate_contract.py` (run through `scoped_fixture.contract_generator_command`). The file content is JSON despite the `.yaml` suffix; readers use `json.loads`.

## UI Conventions

- Build screens only from `ui/src/design` exports; never write a second rendering of an existing component.
- All client actions go through `HyprnMvpApi` in `ui/src/api.ts`; no `fetch` in screens. Retained-run views must not resolve live content (`ui/check_ui_contract.py` asserts `RunEvidence` and `retainedRunAssumptions` contain no `api.`, `fetch(`, `useEffect(`).
- CSS classes: design layer uses the `hf-` BEM prefix (`hf-criterion__number`, `hf-field__tag`, `hf-th--num`); screen classes are kebab-case (`connected-workbench`, `page-heading`).
- Status is shape + word + colour (`StatusTag`); blank reads "unassigned", a missing output reads "not computed", zero is an explicit `0`. Execution and Criteria facets keep separate tags.
- Labels are sentence case ("Create modified run"); no exclamation marks or emoji; reader-facing text avoids implementation words ("retained", "digest", "snapshot", "worker"), see `design-system/Naming.md`.
- Icons are inline SVG React nodes; icon-only buttons carry `aria-label`.
- No inline styles, external fonts, external URLs or CDNs (served CSP is `default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'`).

## Dependencies

- Pin exact versions: `fastapi==0.143.0`, `pydantic==2.14.0` (`application/pyproject.toml`); `"react": "19.3.0"`, `"playwright": "1.62.1"` (`ui/package.json`). Lock files: `application/requirements.lock`, `integration/worker-requirements.lock`, `integration/test-requirements.lock`, `ui/package-lock.json`.
- Before adding a dependency record source, exact version, hash and licence in the component's `provenance.md` (`application/provenance.md`, `integration/provenance.md`, `ui/provenance.md`, `modeling/provenance.md`); only permissive licences.

## Commits

- Conventional-commit subjects with a scope and an invariant sentence: `test(fixtures): pin the native fixture captured from the producer run on the committed tree`, `docs(contracts): record the accepted in-place widening of two early read definitions`, `refactor: comments, docstrings and test names state the invariant they protect`.
- Stage explicit paths only (never `git add -A` / `git add .`); never stage `ui/node_modules`, `ui/dist` or evidence. Repository commits carry no trailer (recorded in `.planning/phases/01-repository-baseline/checkpoints/1.9.md`).
- Product content only: no host paths, user names, machine names or account names in tracked files (`deployment/tests/test_hygiene_guard.py` rejects user-home paths).

---

*Convention analysis: 2026-10-13*
