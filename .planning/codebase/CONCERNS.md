---
last_mapped_commit: ab3d09af609fad34a28344b521757101ee8605f5
last_mapped_at: 2026-10-13
---
# Codebase Concerns

**Analysis Date:** 2026-10-13

Scope: whole repository (`application/`, `integration/`, `modeling/`, `deployment/`, `contracts/`, `ui/`, `upstream/`, `editions/`). This file covers what the code and fixtures show. `docs/specs/ui-target.md` §7 lists the UI debt, `.planning/STATE.md` lists open blockers, and the summaries of both here point back to them. The scientific invariants and execution rules in `AGENTS.md` are the yardstick for "risk".

Severity tags: **[High]** can break an invariant, hide a regression or block a release; **[Medium]** slows change or adds avoidable risk; **[Low]** hygiene.

---

## Tech Debt

**[High] Test-group registry is hand-maintained and many Python test modules are run by no group:**

- Issue: `deployment/checks.py` holds a literal `GROUPS` dict with 94 groups, plus about 20 overlapping hand-written frozensets (`AE_NATIVE_GROUPS`, `APPROACH_APP_GROUPS`, `UNITS_PYTEST_GROUPS`, `DOCKER_GROUPS`, `FIXTURE_GROUPS`, `GROUP_INTERPRETERS`, `UNITS_SELECTIONS`, `AE_SELECTIONS`, …). Targets are named as file paths, `file::test_name` node IDs or `-k` substrings (`'ae-generated': ['-k', 'test_generated_']`). A guard fails on an unregistered **browser** spec (`deployment/tests/test_repository_guard.py` `test_every_browser_spec_is_registered_in_a_group`). No such guard exists for Python tests.
- Python test modules that no group names (a basename search of `deployment/checks.py`): `application/tests/test_api.py`, `test_authorization.py`, `test_ownership.py`, `test_security_regressions.py`, `test_public_contract.py`, `test_run_api.py`, `test_configuration.py`, `test_history.py`, `test_scoped_evidence.py`, `test_ui_discovery.py`, `test_ui_static.py`; `contracts/tests/test_contract_boundaries.py`, `test_modeling_contract.py`, `test_native_program_contract.py`, `test_portability.py`, `test_ui_discovery_contract.py`; `integration/tests/test_configuration.py`, `test_execution.py`, `test_history_read.py`, `test_isolation.py`, `test_native_parser.py`, `test_profile_identity.py`; `deployment/tests/test_initialize_stores.py`, `test_term_scan.py`, `test_topology.py`; `modeling/tests/test_atomic_adapter.py`, `test_ui_discovery.py`. `.planning/STATE.md` mentions only three of these.
- Impact: `--group qualification` can pass while the authorization, ownership, CSRF/replay, public-contract alignment, attestation-refusal (`integration/tests/test_isolation.py`) and modeling-contract boundary tests never run. Some of these modules exist only so other tests can import their fixtures (`from test_api import api,...`), which makes it easy to miss that their own `test_*` functions are never collected.
- Fix approach: add a guard next to the browser-spec guard. It should enumerate `*/tests/test_*.py` and fail on any module that no group selects, with an explicit "fixture-only module" allowlist that has a reason per entry. Then either register each listed module in a must-pass group or move its shared fixtures into a non-`test_` helper module and delete it. Longer term, derive the class/need frozensets from per-group metadata (one record per group: targets, class, needs, interpreter, selection) instead of parallel sets.

**[High] Two 1 MB JSON schemas kept in sync by hand-copying:**

- Issue: `contracts/schemas/model.schema.json` and `contracts/schemas/execution.schema.json` each hold the same 538 `$defs` (about 1.06 MB each). Their own `$comment` says: "Edit shared $defs in model.schema.json, copy the complete $defs into execution.schema.json … No shared-schema generator exists." `upstream/whatsopt-patches/040-modeling-contract.patch` also carries a third, stale copy (`config/modeling.schema.json`, about 230 KB of the 292 KB patch). Build steps overwrite that copy (`deployment/modeling_runtime.py:411` copies `contracts/schemas/model.schema.json`), but it still ships in the patch.
- Impact: any edit is a manual copy, and a missed copy is caught only by the `contracts` group. Both schemas and all patches are in the attested execution inventory (`integration/src/hyprn_mvp_integration/launcher.py` `execution_source_hashes()`), so **every schema edit, including Documents-only definitions, invalidates the worker attestation** and forces a rebuild, a new pin and a fixture recapture (`.planning/STATE.md`: "a change to a modeling source needs a rebuild, a new pin and a fixture recapture").
- Fix approach: write a small stdlib generator that emits `execution.schema.json` from `model.schema.json`, with a `--check` mode wired into the `contracts` group. Drop the schema body from the 040 patch and copy it at build time, which already happens. Consider splitting the Documents `$defs` (119 `Document*` definitions) into their own schema file outside the attested set, so Phase 4 work does not re-attest the worker.

**[Medium] Versioned wire-shape families multiply:**

- Issue: `model.schema.json` carries 7 variants each of `ExecutionBundle#Model#`, `FrozenConfiguration#Model#`, `ModifiedRunSeed#Model#` and `RunHistory#Model#`, plus 5 each of `ConfigurationRevision#`, `ConfigurationPreview#`, `ConfigurationCommit#` and `ConfigurationCandidate#`. `contracts/hyprn-mvp.openapi.yaml` is 1.4 MB for 44 paths (569 component schemas). `ui/src/contract.ts` (158 KB, generated by `ui/generate_types.py`) mirrors all of them.
- Files: `contracts/schemas/*.json`, `application/generate_contract.py`, `ui/src/contract.ts`, `application/src/hyprn_mvp_app/execution_bundle.py` (`RETAINED_PAIRINGS`)
- Impact: every reader of retained records has to handle every historical variant. Contract regeneration and review diffs are huge, and adding a variant touches schema, generator, pairing table, history readers and UI types together.
- Fix approach: keep the immutable variants (the rule is that existing shapes are never edited) but document a cut-off policy for which variants new writers may emit. Keep `RETAINED_PAIRINGS` as the single interpretation table, as the module-boundary test requires.

**[Medium] `generate_contract.py` patches the public contract by mutation:**

- Issue: `application/generate_contract.py` appends error codes with `schemas["Error"]["properties"]["error"]["properties"]["code"]["enum"] += [...]` and overrides `Study`, `Evidence` and others after importing the shared `$defs`.
- Impact: the public contract is the shared schema plus imperative edits. Its true shape is visible only after generation, and a renamed `$def` breaks the generator silently or loudly depending on the path.
- Fix approach: move public-only definitions into a declared overlay document that the generator merges, and validate that every overlay key targets an existing definition.

**[Medium] `create_app` is a 399-line, 29 KB closure holding all 49 routes:**

- Files: `application/src/hyprn_mvp_app/api.py:102` (`create_app`)
- Issue: middleware, every route handler, every service construction and error mapping sit in one function. `.planning/ROADMAP.md` already names `api.py` as a shared file that Phases 3 and 4 must edit serially.
- Impact: agent routes (Phase 3) and Documents routes (Phase 4) cannot land in parallel, and review diffs touch a single giant function.
- Fix approach: split into per-domain `APIRouter` modules (session, studies, models, evidence, configurations, runs, records, documents), each registered from `create_app`. Keep the middleware in `api.py` and update `application/tests/test_module_boundaries.py` to pin the new edges.

**[Medium] Test-only alias re-exports live in production modules:**

- Issue: the `application/tests/test_module_boundaries.py` docstring says "The temporary aliases in `store`/`modeling`/`execution`/`result_bindings`/`modified_runs` exist only for test imports". An example is `application/src/hyprn_mvp_app/modeling.py:17` `from .contracts import SCHEMA, VALIDATORS  # noqa: F401`.
- Impact: production modules expose names that the boundary rules forbid production code from using, and the guard has to police them.
- Fix approach: point the test imports at the owning modules (`hyprn_mvp_app.contracts`, `units`, …), then delete the aliases and their allowlist entries.

**[Medium] Two parallel worker-isolation implementations with divergent policies:**

- Files: `deployment/manage.py` (`POLICY` wall 15 s, its own `isolated`, `fingerprint`, `require_attestation`, `verify_isolation`) together with `deployment/launch_worker.py`; and `integration/src/hyprn_mvp_integration/launcher.py` (`POLICY` wall 20 s with `file_bytes`, `attest`, `isolated`).
- Issue: the release path launches through `deployment/native_environment.py` `launch_worker_text`, which uses `hyprn_mvp_integration.launcher`. `manage.py`/`launch_worker.py` appear only in live-fence lists (`deployment/tests/live_fence.py:121`) and in a fence test (`deployment/tests/test_repository_guard.py:1221`).
- Impact: two containment policies and two attestation formats. Someone hardening one can easily miss the other, and the canary in `launcher.attest` hard-codes `memory.max == 268435456` and `pids.max == 32` instead of reading from `POLICY`.
- Fix approach: confirm that `manage.py` and `launch_worker.py` are unused, then remove them, or fold them into `launcher.py`. Derive the canary's expected limits from `POLICY`.

**[Medium] Container run arguments are duplicated across production and fixtures:**

- Issue: hardened `docker run` argument lists (`--cap-drop ALL`, `--read-only`, tmpfs strings such as `/tmp:rw,noexec,nosuid,size=192m,mode=1777`) are written out separately in `deployment/initialize_stores.py`, `deployment/application_runtime.py`, `deployment/modeling_runtime.py`, `deployment/native_environment.py`, `deployment/manage.py`, `integration/src/hyprn_mvp_integration/launcher.py` and fixtures `deployment/tests/combined_fixture.py`, `findings_native_fixture.py`, `units_native_fixture.py`, `units_model_fixture.py`, `native_deployment_fixture.py`. `deployment/modeling_runtime.py:164` compares tmpfs strings for exact equality.
- Impact: fixtures can drift from the production container policy and still pass. Phase 2 image work has to edit about 10 places.
- Fix approach: one stdlib module in `deployment/` (and one in the attested launcher, which must not import deployment code) that returns the argument list per role. Fixtures call it instead of restating it.

**[Medium] Strict-JSON and finite-scalar checks are re-implemented at each boundary:**

- Issue: separate strict parsers (duplicate keys, `parse_constant` refusal, depth bounds) exist in `application/src/hyprn_mvp_app/api.py:129-144`, `application/src/hyprn_mvp_app/contracts.py:68-80` (`data_json`), `application/src/hyprn_mvp_app/dispatcher.py:70` and `integration/src/hyprn_mvp_integration/results.py:75-95` (`_bounded_json`), with different depth and collection limits. About 15 inline `type(v) in (int,float) and math.isfinite(v)` predicates are spread over `execution_bundle.py:630`, `approach_closure.py:328-390`, `dispatcher.py:102`, `calculation.py:243`, `results.py:28/188`, `worker.py:83/1180`, `readiness.py:39` and others.
- Impact: the invariant "non-finite numbers, booleans posing as numbers and unsafe integers are rejected at every boundary" depends on each copy being right. The inline predicates do not bound unsafe integers (|x| > 2^53−1), and `math.isfinite(10**400)` raises `OverflowError`, not `False`. `readiness.py:37` documents that trap, but most call sites do not guard against it. Rejection then depends on which exception the caller happens to catch.
- Fix approach: one pure `finite_scalar(value)` predicate (exact type check, safe-integer bound, overflow-safe) in `application/src/hyprn_mvp_app/contracts.py`, plus one `strict_json(raw, *, depth, collections, size)`. The attested worker can keep its own copy, because it must not import more application code, but a shared test vector should pin that copy to the same behaviour.

**[Medium] SQLite schema evolves through `CREATE … IF NOT EXISTS` plus ad-hoc `ALTER`:**

- Files: `application/src/hyprn_mvp_app/store.py:14-178` (`SCHEMA`), `store.py:189-197` (the `runtime_json` column migration)
- Issue: there is no schema version table and no migration ledger. Each additive change is an inline `PRAGMA table_info` check.
- Impact: Phase 3 (agent principal, journal, tokens) and Phase 4 (document chain, upload spool in the application store) both add tables or columns. Without a version, a store cannot say which migrations it has seen, and a partial migration cannot be detected.
- Fix approach: add a `schema_migrations` table with ordered, idempotent, append-only steps run inside `BEGIN IMMEDIATE`. Refuse to open a store whose version is newer than the code.

**[Low] Very dense code style hampers review:**

- Issue: 441 semicolon-joined statements in `application/src` plus `integration/src` (154 in `integration/src/hyprn_mvp_integration/worker.py`, 61 in `application/src/hyprn_mvp_app/computational_export.py`). Lines run up to 2,849 characters (`ui/src/contract.ts`; `ui/src/Workspace.tsx` max 2,192, 62 lines over 200; `ui/src/ConfigurationPanel.tsx` 76 lines over 200). Line counts badly understate size: `ui/src/Workspace.tsx` is 450 lines but 65 KB.
- Impact: diffs are hard to read, `git blame` is coarse, and executors misjudge module size from `wc -l`.
- Fix approach: no Python formatter, linter or type checker is configured (no ruff, mypy, flake8 or pyproject tool sections), and there is no ESLint or Prettier for `ui/`. Adopting a formatter is a provenance-reviewed dependency decision (see `docs/legal/licensing.md`). Until then, measure module size in bytes and keep new code to one statement per line.

**[Low] Stale documentation and comments:**

- `AGENTS.md` "Running checks" still says "Until Phase 1 task 1.2 lands, use the data-root variable name…", although task 1.2 has landed.
- `ui/check_design_system.py` docstring says it is "Not wired into the build, the tests or the served runtime", but `deployment/checks.py:847-854` runs it in `combined-static`.
- `integration/src/hyprn_mvp_integration/worker.py:1191` ends with "Active origin proof belongs to12-3." This is a work-item reference, which `AGENTS.md` forbids. It is in an attested source, so the fix waits for a re-attesting change (`.planning/STATE.md` pending todo).
- `application/tests/fixtures/identity_golden.json` `purpose` field cites a work-item code ("14-B1"). The golden corpus is "never regenerate", so record the correction as an accepted exception.

---

## Known Bugs

**Failing or not-yet-qualified groups (from `.planning/STATE.md`):**

- Symptoms: the Phase 1 gate (task 1.10) has not run yet. `ui-served` (opt-in, 15 browser specs) has only been wiring-checked, and `ui-fidelity` is waiting for reference images (`deployment/checks.py:837` refuses without `design-system/reference`).
- Files: `deployment/checks.py`, `ui/playwright.config.ts`
- Trigger: `python3 -B deployment/checks.py --group qualification` on a host without the base images or fixture root.
- Workaround: none. Host prerequisites are listed under Blockers in `.planning/STATE.md`.

**UI wording and access-loss defects (from `docs/specs/ui-target.md` §7):**

- Symptoms: "1 connections" in the canvas footer; leftover non-plain labels ("Recorded outputs", "Exact values", "Definition not recorded", …); availability reason "Unavailable: Unknown"; a denied saved configuration shows its message twice.
- Files: `ui/src/GraphView.tsx`, `ui/src/ModelView.tsx`, `ui/src/ConfigurationPanel.tsx`, `ui/src/RunAvailability.tsx`, `ui/src/accessLoss.ts`
- Trigger: open the views named in §7.
- Workaround: none. Fix them during the plain-language pass and the access-loss residual work.

**Mixed-repair qualification hard-codes a test count:**

- Files: `deployment/checks.py:763` (`results.passed == 5` when `mixed=True`)
- Symptoms: adding or removing a test in the mixed-repair selection fails qualification without explaining why.
- Fix: derive the expected count from `UNITS_MIXED_REPAIR_TARGETS` or the collected items.

---

## Security Considerations

**[High] Security regression tests are not in any qualification group:**

- Risk: `application/tests/test_authorization.py` (no default owner, scrypt, lockout), `test_ownership.py`, `test_security_regressions.py` (revoked model/configuration replay never reaches the backend), `test_public_contract.py`, `integration/tests/test_isolation.py` (missing, failed or changed fingerprint cannot authorize candidate code) and `contracts/tests/test_contract_boundaries.py` (duplicate body, depth and size refusals) never run under `deployment/checks.py`.
- Current mitigation: none in the runner.
- Recommendations: register these modules in a must-pass group before the Phase 5 ASVS L1 review (requirement SEC-01). This is the same fix as the registry concern under Tech Debt.

**[Medium] Login runs scrypt inside the application store's write lock:**

- Files: `application/src/hyprn_mvp_app/auth.py:39-60` (`login`), `application/src/hyprn_mvp_app/store.py:199-210` (`BEGIN IMMEDIATE`, `timeout=15`)
- Risk: each login attempt runs `hashlib.scrypt(n=2**17, r=8, maxmem=256 MiB)`, about 128 MiB and a noticeable CPU cost, while holding the SQLite RESERVED lock. A burst of unauthenticated login requests serializes every write in the API and the dispatcher, which share the store, and can push other writers past the 15 s busy timeout. The dispatcher then logs "store busy" and backs off (`application/src/hyprn_mvp_app/dispatcher.py:40-48`). The per-user lockout (5 failures, then 60 s) does not apply to unknown usernames.
- Current mitigation: loopback-only listening, a Host and Origin check in the middleware (`api.py:114-121`), per-user lockout.
- Recommendations: read the user row, compute scrypt outside any transaction, then open a short write transaction to record the outcome. Add a global concurrent-login bound.

**[Medium] Authorization is enforced at about 60 scattered call sites:**

- Files: `application/src/hyprn_mvp_app/store.py:243` (`authorize`), called from `store.py` (17), `modeling.py` (10), `approach.py` (8), `configuration.py` (6), `execution.py` (6), `api.py` (5), `readiness.py` (4), `history.py` (2), `result_bindings.py` (1), `computational_export.py` (1)
- Risk: Phase 3 adds an agent principal whose authority is the intersection of delegation, current access and a role ceiling (AGENT-05, ADR-0003). Every one of these sites must learn the new rules, and missing one grants an agent the owner's full rights on that path. IAM-03 (`can(principal, action, resource)`) is still `planned` in `docs/specs/requirements.md`.
- Current mitigation: the role check (`owner`/`writer`/`reader`) and receipts scoped per study.
- Recommendations: introduce the single `can()` wrapper before any agent write lands (Phase 3 task 3.1 is the natural place). Add a test that enumerates every route and asserts that it passes through `can()`.

**[Medium] Single-owner authentication model:**

- Files: `application/src/hyprn_mvp_app/auth.py:22-29` (`provision` refuses once any user exists), `auth.py:31-37` (`recover` updates every user row)
- Risk: Reviewer roles (ADR-0005), workspace invitations and agent tokens have no identity substrate yet. Expired sessions are never purged from `sessions`.
- Recommendations: plan the principal table (human or agent) and token storage as part of the Phase 3 tracer. Purge expired sessions on login.

**[Medium] Cloud-sync and symlink refusal is duplicated and inconsistent:**

- Files: `application/src/hyprn_mvp_app/store.py:183` (refuses only a `CloudStorage` path part; exempts the literal `Path("/tmp")`), `application/src/hyprn_mvp_app/computational_export.py:85` (`CloudStorage`, `Google Drive`, `GoogleDrive`), `integration/src/hyprn_mvp_integration/launcher.py:202` (`/tmp` exemption)
- Risk: synced folders on Linux or WSL2 (Dropbox, OneDrive, Nextcloud) and macOS iCloud Drive (`Mobile Documents`) are not refused. Absolute-path literals in product code go against the "no absolute path in code" rule. The single path-policy module (`deployment/local_paths.py`) has no sync detection.
- Recommendations: Phase 2 task 2.2 should put one `refuse_synced(path)` in the path-policy module and in an attested-safe copy for the launcher. Replace the `/tmp` literal with the platform's real temporary folder from `tempfile.gettempdir()`.

**[Low] The request handler writes a private Starlette attribute:**

- Files: `application/src/hyprn_mvp_app/api.py:146` (`request._body=bytes(raw)`)
- Risk: a FastAPI or Starlette upgrade can silently change how the cached body is read, so validated bytes and handler bytes could differ.
- Recommendations: pin a test asserting that handlers receive exactly the validated bytes, or re-inject the body through a custom `Request` subclass or ASGI receive wrapper.

**[Low] Bind-mount source is interpolated into a CSV `--mount` string:**

- Files: `integration/src/hyprn_mvp_integration/launcher.py:272` (`f'type=bind,source={input_dir},target=/input,readonly'`)
- Risk: a runtime root containing `,` would change the mount options. Roots come from validated configuration, so exposure is low.
- Recommendations: refuse `,` and `=` in `input_dir` before building the argument.

**[Low] `.gitignore` does not cover the application store filename:**

- Files: `.gitignore` ignores `*.sqlite3` but not `*.sqlite`, and the store is `application.sqlite` (`application/tests/test_authorization.py`, `deployment/tests/test_bridge.py`).
- Current mitigation: `deployment/tests/test_hygiene_guard.py` fails on a tracked `.sqlite` or `.db` file.
- Recommendations: add `*.sqlite` and `*.sqlite-*` to `.gitignore`.

**Access-loss residuals (from `docs/specs/ui-target.md` §7):**

- Risk: evidence hosts (`ui/src/EvidenceView.tsx`, `EvidencePicker.tsx`, `EvidenceIndex.tsx`, `Assumptions.tsx`, `ModelEditor.tsx`, `UnitEditor.tsx`) use their own denial classification rather than the shared seam in `ui/src/accessLoss.ts`. Study-shell lists are not cleared on a confirmed loss of access.
- Recommendations: an independent security recheck before SEC-01 records these as mitigated (`docs/specs/requirements.md` SEC-01 is `partial`).

---

## Performance Bottlenecks

**SQLite in rollback-journal mode with a new connection per operation:**

- Problem: the API (FastAPI threadpool) and the dispatcher process write the same `application.sqlite`. Writers serialize under `BEGIN IMMEDIATE`, and readers block a committing writer.
- Files: `application/src/hyprn_mvp_app/store.py:199-210`, `application/src/hyprn_mvp_app/dispatcher.py:24-48` (lock backoff up to 30 s), `application/src/hyprn_mvp_app/readiness.py:75,123`
- Cause: no `journal_mode=WAL`. The comment in `application/tests/test_configuration.py:18` notes that WAL was avoided for host and container reasons. A connection is opened per call.
- Improvement path: inside the single container that owns the store, evaluate WAL with `synchronous=NORMAL`. Keep scrypt and other slow work out of write transactions.

**Computational record export is built in memory under tight limits:**

- Problem: exports are assembled in `io.BytesIO` (`application/src/hyprn_mvp_app/computational_export.py:619-623`) with `LIMITS` `expanded_bytes=32 MiB`, `selected_runs=16`. `.planning/STATE.md` records that a two-run export only fit under 32 MiB after schema copies were replaced by schema identities.
- Files: `application/src/hyprn_mvp_app/computational_export.py:26-28`, `integration/src/hyprn_mvp_integration/computational_export.py`
- Cause: each run retains large frozen artifacts (generated code, inventories, notices).
- Improvement path: share retained blobs across runs by content digest (some deduplication already exists), stream to a spool file, and measure bytes per run against the 16-run limit.

**Browser fetch fan-out for study-wide views:**

- Problem: the Evidence page aggregates owner reads in the browser (`docs/specs/ui-target.md` §7). List endpoints (`store.list_studies`, configuration and run lists) have no last-activity data or server aggregation.
- Files: `ui/src/EvidenceIndex.tsx`, `ui/src/OverviewRecords.tsx`, `application/src/hyprn_mvp_app/store.py:280-310`
- Improvement path: a server-side assumptions and evidence read for large studies, as §7 proposes.

---

## Fragile Areas

**The attested execution inventory couples unrelated edits to re-attestation:**

- Files: `integration/src/hyprn_mvp_integration/launcher.py:110-135` (`execution_source_hashes()`, a reviewed literal list), `application/tests/test_module_boundaries.py` (pins that the list equals the launch path's import closure)
- Why fragile: the list includes `deployment/pins.json`, both 1 MB schemas, every `upstream/whatsopt-patches/*.patch`, `deployment/modeling_runtime.py` and the application modules `contracts.py`, `units.py`, `approach_closure.py`, `execution_bundle.py` and `scientific_configuration.py`. A docstring or schema edit in any of them makes the attestation stale, so execution is refused until rebuild and re-attestation. A modeling-source change also needs a new `modeling_producer` pin and a recapture of `integration/tests/fixtures/native-programs.json.gz`, because builds are not bit-reproducible.
- Safe modification: batch edits to attested files into one change that rebuilds, re-pins and recaptures. Never edit attested comments on their own (`.planning/STATE.md` pending todo).
- Test coverage: the module-boundary test pins the inventory. `deployment/tests/test_attestation.py` (group `units-attestation`) covers refusal.

**Guard `PENDING` tables and stale-key rules:**

- Files: `deployment/tests/test_naming_guard.py:76`, `deployment/tests/test_hygiene_guard.py:54`, `deployment/tests/test_repository_guard.py:28`
- Why fragile: a stale `PENDING` key fails the guard, so any rename of a listed file must update the table in the same commit. All three are empty today. Keep them empty: re-adding an entry means accepting debt with a named owner.
- Safe modification: run the `guard`, `naming` and `hygiene` groups after any rename or move.

**Durable native fixtures and the once-per-working-copy continuation:**

- Files: `deployment/tests/findings_native_fixture.py` (74 KB), `deployment/tests/durable_fixture.py`, `deployment/tests/documents_native_fixture.py`, `deployment/tests/units_native_fixture.py`, `deployment/tests/scoped_fixture.py`, `integration/tests/capture_native_programs.py`
- Why fragile: `findings-native` consumes its continuation once per working copy, so a rerun needs a fresh working copy (preflight) or a new capture. The fixture root and base images (`HYPRN_MVP_ENGINE_IMAGE`, `HYPRN_MVP_MODELING_SOURCE_IMAGE`) exist only on a prepared development host. `deployment/pins.json` `runtime` records one development host's OS and Docker Desktop versions, and `status` is `measured-experiment-adoption-pending`.
- Safe modification: change fixtures only through the tracked capture tools. Never hand-edit the pinned manifests.
- Test coverage: `findings-native-guards`, `units-staging` and the `units-guards` fixture guards.

**Golden identity corpus:**

- Files: `application/tests/fixtures/identity_golden.json` (1.8 MB, "Never regenerate"), `application/tests/test_identity_golden.py`
- Why fragile: canonical bytes and digests are frozen from an earlier commit. Any change to `contracts.canonical`/`digest` or to `rfc8785` behaviour breaks every recorded identity. Namespace revisions have to be proven blob by blob.
- Safe modification: never change canonicalization. Changes to identity-bearing records need a new versioned shape.

**Two read definitions widened in place:**

- Files: `contracts/README.md:59` (recorded exception: `ModelPackage` admits `ModelPackage4`; `ExecutionVersions` admits further bundles), `contracts/tests/documents_prior_definitions.json`
- Why fragile: this exception to "existing shapes are never edited" is held in check only by per-definition pins. A further in-place widening would break the immutability of historical reads.
- Safe modification: always add a new versioned definition.

**Unit blank versus none in the worker:**

- Files: `integration/src/hyprn_mvp_integration/worker.py:1182` (`old, new = value['units'] or None, binding['units'] or None`)
- Why fragile: an empty units string and an absent unit are merged into one value. `docs/specs/ui-target.md` §7 still has an open decision on "Dimensionless" versus a marked blank. If that decision makes blank mean something different from dimensionless, the worker conversion will silently treat them alike.
- Safe modification: settle the blank-unit decision first, then make the worker distinguish the two cases explicitly, in a change that re-attests.

**Worker reads `[0]` of native arrays and relies on an upstream shape check:**

- Files: `integration/src/hyprn_mvp_integration/worker.py:966,1203` (`float(inputs[key][0])`, `float(problem.get_val(...)[0])`), `integration/src/hyprn_mvp_integration/native.py:72` (`shape != '1'` refused)
- Why fragile: scalar-only behaviour is enforced at generation time, not where values are read. Supporting non-scalar ports later would turn this into silent reduction to the first element, which is implicit broadcasting the invariants forbid.
- Safe modification: assert `size == 1` where values are read when the worker is next re-attested.

**UI study shell and hash routing:**

- Files: `ui/src/Workspace.tsx` (65 KB, 41 `useState`, hash routing at lines 369-370), `ui/src/ConfigurationPanel.tsx` (59 KB), `ui/src/ModelEditor.tsx` (41 KB), `ui/src/RunPanel.tsx` (38 KB)
- Why fragile: routing, guards and dialogs live in one component with no router (`docs/specs/ui-target.md` §7). Phase 4 document screens and the Phase 3 Agent activity page both need to attach here.
- Safe modification: extract the workbench layout component at this seam before adding new screens. Edit the study shell one task at a time (`.planning/ROADMAP.md` "Parallel work").

**Monolithic browser specs selected by tag:**

- Files: `ui/tests/approach.spec.ts` (370 KB, run by six `approach-ui-*` groups), `ui/tests/assumptions-evidence.spec.ts` (163 KB, three `ae-ui-*` groups), `ui/control-map.json` (maps control IDs to test-title substrings)
- Why fragile: renaming a test title breaks `ui/check_ui_contract.py`, and one spec file serves several groups. 12 `waitForTimeout`/`setTimeout` uses in `approach.spec.ts` raise flake risk. `docs/specs/ui-target.md` §7 notes that some specs still target earlier screen compositions.
- Safe modification: keep tags and titles stable, and split specs per group when touching them.

**Cross-test-module imports and the conftest shadowing:**

- Files: 88 `from test_<x> import …` lines across `*/tests/*.py` (top sources `test_api`, `test_approach_closure`, `test_submission`, `test_result_dependencies`); `application/tests/conftest.py`; `integration/tests/conftest.py`; the runner uses `--noconftest` (`deployment/checks.py:803`)
- Why fragile: test modules double as fixture libraries. `.planning/STATE.md` notes that `integration/tests/conftest.py` shadows `application/tests/conftest.py` on some import paths.
- Safe modification: move shared fixtures into named helper modules (the pattern `integration/tests/execution_fixtures.py` already uses).

---

## Scaling Limits

**Worker containment budget:**

- Current capacity: `integration/src/hyprn_mvp_integration/launcher.py:45-46` `POLICY`: 256 MiB memory, 0.5 CPU, 32 PIDs, 20 s wall, 64 KiB output, 1 MiB per file, 16 MiB scratch.
- Limit: any model needing more time, memory or output fails with `wall_limit` or `output_limit`. Coupled solves (SCI-01) and OpenTURNS ensembles (UQ-01..04) will exceed these limits.
- Scaling path: make the limits part of the attested policy per run class, recorded in the run, never silently raised.

**Request and record bounds:**

- Current capacity: request body 2 MiB, depth 32 (`application/src/hyprn_mvp_app/api.py:125,135`); export 16 selected runs and 32 MiB expanded (`computational_export.py:26-28`); session 8 h (`auth.py:52`).
- Limit: large imported model packages and multi-run exports hit 413.
- Scaling path: streaming uploads (Phase 4 already plans an upload spool) and spooled exports.

**Single local owner and single SQLite store:**

- Current capacity: one provisioned user (`auth.py:26`) and one SQLite file per installation.
- Limit: Reviewer roles, workspaces and the cloud edition (IAM-04, IAM-05) need PostgreSQL with row-level security (`docs/specs/requirements.md`).
- Scaling path: keep store access behind `Store` and the planned `can()` so the cloud adapter can replace it.

**Host coverage:**

- Current capacity: only the development host has qualified pins (`deployment/pins.json` `runtime`). macOS on Intel is refused (`.planning/STATE.md`). `deployment/local_paths.py:account_home` uses `pwd`, which is POSIX only (fine on WSL2, not on native Windows).
- Scaling path: Phase 2 clean-room installs on Linux x86_64 and aarch64.

---

## Dependencies at Risk

**WhatsOpt (AGPL), carried as a 9-patch stack:**

- Risk: about 500 KB of patches against pinned commit `whatsopt_commit` in `deployment/pins.json` (`upstream/whatsopt-patches/010…090`). `040-modeling-contract.patch` alone is 292 KB, including the stale schema copy. Rebasing on upstream is costly. The licence open items L1-L4 in `docs/legal/licensing.md` block commercial cloud distribution.
- Impact: modeling-service changes need a patch edit, an image rebuild, a new producer pin and a fixture recapture.
- Migration plan: L3 (a permissive replacement backend behind the Modeling Backend Contract, `contracts/modeling.openapi.yaml`). Keep the contract the only coupling.

**`rfc8785==0.1.4` (pre-1.0) carries every identity digest:**

- Risk: `application/src/hyprn_mvp_app/contracts.py:36-55` builds all digests through it, with a workaround for integer-looking floats over 2^53.
- Impact: any behaviour change breaks `identity_golden.json` and every stored digest.
- Migration plan: pin exactly (already done in `application/pyproject.toml`). Treat any upgrade as an identity-breaking change gated by the golden corpus.

**Pending re-audits and accepted residuals (from `.planning/STATE.md`):**

- pypdf 6.20.0 → 6.20.1 must be re-audited in Phase 4. `expat 2.8.5` in the CPython build and a low `paramiko` 3.x advisory (pinned by AiiDA) are accepted residuals. The Linux CPython builds statically link Berkeley DB (Sleepycat), to be recorded as licensing open item L6 by Phase 2 task 2.1.
- `pip` is to be removed from the worker image at its next rebuild.

**FastAPI and Starlette internals:**

- Risk: `request._body` (see Security). `fastapi==0.143.0` and `pydantic==2.14.0` are pinned in `application/pyproject.toml`.
- Migration plan: add a regression test before any upgrade.

---

## Missing Critical Features

**Local edition entry point:**

- Problem: `editions/local/` contains only `README.md`. There is no `./hyprn-mvp` script and no `hyprn_mvp_local` package, and per-OS defaults are not yet in `deployment/local_paths.py`.
- Blocks: OPS-04 and the whole of Phase 2, Phase 5 qualification, and the Phase 3 CLI parts (`study new`, `mcp relay`, token commands).

**Agent principal, MCP server and journal:**

- Problem: no agent identity, token store, action journal or Agent activity page (AGENT-01, 05-08, UI-04).
- Blocks: Phase 3. The scattered authorization sites (see Security) must be unified first.

**Documents capability:**

- Problem: `documents` is advertised as unavailable (`application/src/hyprn_mvp_app/api.py:206`). The schemas hold 119 `Document*` definitions and `integration/src/hyprn_mvp_integration/documents.py` exists, but there are no public routes. `deployment/documents_groups.py` is planned for Phase 4 task 4.4.
- Blocks: DOC-01, citations from evidence, and the first release (the Phase 5 release gate removes `documents` from the unavailable list).

**Single authorization function (IAM-03), schema migration ledger, backup and restore (OPS-03 partial):**

- Blocks: safe agent writes, Phase 3 and 4 store additions, and recovery of a damaged installation.

**Scientific product gaps (planned in `docs/specs/requirements.md`):**

- Typed input provenance (HUM-07), the conclusion record (HUM-10), an infeasible outcome distinct from execution failure (RUN-05), sweeps (RUN-06), light run status (RUN-07), coupled solves and derivatives (SCI-01/02), uncertainty (UQ-01..04).

**No continuous integration:**

- Problem: no CI configuration is tracked. Every check runs by hand on the development host through `deployment/checks.py`.
- Blocks: independent verification of the "every API change keeps the contract tests green" rule.

**UI affordances (from `docs/specs/ui-target.md` §7):**

- No "Archived" marker inside an archived study, no archive metadata in the public read, no role field (so Archive cannot be hidden for reviewers), no authored-equations field, no attribution chip, no last-activity data on Home rows.

---

## Test Coverage Gaps

**Unregistered Python test modules:**

- What's not tested: authorization, ownership, security regressions, public-contract and route alignment, attestation refusal, modeling-contract boundaries, portability, history read, store initialization, topology, term scan (the full list is under Tech Debt).
- Files: see the first Tech Debt item.
- Risk: security and contract regressions pass qualification.
- Priority: High

**Served-installation browser suite never run for real:**

- What's not tested: 15 specs in the opt-in `ui-served` group (`deployment/checks.py:153-157`: `authoring-dirty`, `authoring-evidence-records`, `batch-authoring`, `configuration-evidence`, `connected-views`, `model-revision-journey`, `overview`, `overview-states`, `paste-guard`, `run-history`, `served-read-only-inspection`, `source-editor`, `source-import-races`, `submission-scope`, `variables`).
- Files: `ui/tests/*.spec.ts`, `ui/playwright.config.ts`, `ui/tests/support/served.ts`
- Risk: regressions in authoring, paste guards and import races go unseen until Phase 2 provides a scratch installation.
- Priority: High (before Phase 5)

**Visual fidelity:**

- What's not tested: `ui-fidelity` waits for the Phase 5 reference images (`design-system/reference` is absent).
- Priority: Medium

**Parser real-wheel check:**

- What's not tested: `contracts/tests/test_document_parser_adoption.py:248` is `skipif` without `HYPRN_MVP_PARSER_WHEEL`, and the scoped runner does not pass that variable.
- Risk: the parser lock is checked only against metadata.
- Priority: Medium (Phase 4)

**Static analysis:**

- What's not tested: there is no type checking of the Python packages and no lint for Python or TypeScript. `tsc --noEmit` (`ui/package.json` `build`) is the only static check besides the design and contract checkers (`ui/check_design_system.py`, `ui/design_tokens.py --check`, `ui/check_ui_contract.py`).
- Risk: unused imports, shadowed names and unreachable code in dense modules such as `integration/src/hyprn_mvp_integration/worker.py` go unnoticed.
- Priority: Medium

**Finite-scalar edge cases at every boundary:**

- What's not tested: no shared test vector feeds booleans, `2**53`, `10**400`, `-0.0`, `1e400` (which parses to `inf`) and `NaN` to every boundary parser and predicate listed under Tech Debt.
- Risk: one boundary accepts what another refuses, breaking the "rejected at every boundary" invariant.
- Priority: High

**Design baseline residue:**

- What's not tested: `ui/design-baseline.json` still allows 6 hard-coded colours in `ui/src/exports.ts` (`#17212b`, `#718096`, `#fff`, used in the exported SVG diagram).
- Risk: exported diagrams ignore theme tokens.
- Priority: Low

---

*Concerns audit: 2026-10-13*
