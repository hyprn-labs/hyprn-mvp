# Phase 4: Documents - Pattern Map

**Mapped:** 2026-10-13
**Files analyzed:** 52 new or modified files (steps 1–13; steps 14–18 are deferred by PD-4.1 and not mapped), plus the files of the product owner's factorization schedule (D-18), mapped in "Factorization analogs"
**Analogs found:** 47 / 52 (5 have only a partial analog or none; see "No Analog Found")

## Naming rule for this map

Phase 1 renamed or moved these locations; analogs and plans name the final path:

| Today (cite as analog) | Final (name in plans) |
|---|---|
| `application/src/hyprn_mvp_app/…` | `application/src/hyprn_mvp_app/…` |
| `integration/src/hyprn_mvp_integration/…` | `integration/src/hyprn_mvp_integration/…` |
| `contracts/hyprn-mvp.openapi.yaml` | `contracts/hyprn-mvp.openapi.yaml` |
| `ui/check_ui_contract.py` | `ui/check_ui_contract.py` + `ui/control-map.json` (task 1.6) |
| `deployment/approach_polish_release.py`, `migrate_runtime.py` | `deployment/release.py` (Phase 2 2.8), `deployment/modeling_runtime.py` (1.5) |
| `contracts/tests/test_documents_planning_gates.py` | `contracts/tests/test_document_parser_adoption.py` + `integration/document-parser.lock.json` (1.8) |
| Session cookie `hyprn_mvp_session`; env `HYPRN_MVP_*` | `hyprn_mvp_session`; `HYPRN_MVP_*` |
| Native namespace `'hyprn_mvp_documents'` | whatever 1.4 lands (research assumes `hyprn_mvp_documents`; read it from the adapter constant, never retype it) |
| Dockerfiles `deployment/*.Dockerfile` | `deployment/images/*.Dockerfile` (Phase 2 2.7 convention) |

Every analog below was confirmed git-tracked (`git ls-files`). No gitignored mirror path is cited.

---

## File Classification

| New/Modified File (final path) | Role | Data Flow | Closest Analog (today's path) | Match Quality |
|---|---|---|---|---|
| **Step 1** | | | | |
| `integration/src/hyprn_mvp_integration/documents.py` (modify: collections, annotations, read verbs, generalized reconcile) | service (native adapter) | CRUD, single-writer transaction | `integration/src/hyprn_mvp_integration/documents.py` (`store_original`/`reconcile`) + `deployment/tests/documents_native_fixture.py` `CollectionProtocolProbe` | exact (port of qualified probe) |
| `integration/tests/test_documents_collections.py` (new) | test (native) | CRUD + kill/replay | `integration/tests/test_documents_collection_protocol.py` | exact |
| `integration/tests/test_documents_annotations.py` (new) | test (native) | CRUD + CAS | `integration/tests/test_documents_native.py` (`docs26_*` tests) | exact |
| `deployment/tests/documents_native_fixture.py` (modify: production-adapter probes) | test fixture | subprocess kill / fresh-process inspect | same file, `AtomicityProbe`/`CollectionProtocolProbe` `_child`, `kill_at`, `inspect_fresh` | exact |
| `deployment/checks.py` (modify, every step) | config (group registry) | batch | same file `DOCUMENTS_ROUTES`, `DOCUMENTS_MEASURED_GROUP`, `DOCKER_GROUPS`, `BROWSER_GROUPS` | exact |
| **Step 2** | | | | |
| `application/src/hyprn_mvp_app/document_bridge.py` (new) | service (bridge, app side) | event-driven (stdio frames), read mailbox | `application/src/hyprn_mvp_app/dispatcher.py` | exact |
| `application/src/hyprn_mvp_app/dispatcher.py` (modify: drain document write queue) | service (serve loop) | batch / queue drain | same file `export_once` + main loop | exact |
| `deployment/document_reads_runtime.py` (new) or a mode of `deployment/dispatch_runtime.py` | service (host read process) | event-driven (stdio), supervised | `deployment/dispatch_runtime.py` `bridge_child`, `native_call`, `main` | exact |
| `deployment/dispatch_runtime.py` (modify: start/supervise read loop) | service (host executor) | process supervision | same file lines 236–270 | exact |
| `application/src/hyprn_mvp_app/store.py` (modify: `document_operations`, `document_read_requests`, upload/spool lease tables) | model (store schema) | CRUD | same file `computational_record_requests` + `outbox` tables | exact |
| `application/tests/test_documents_bridge.py` (new; group `documents-bridge`) | test (contract/unit) | request-response | `deployment/tests/test_bridge.py` | exact |
| `integration/tests/test_documents_read_loop.py` (new; measured) | test (native, measured) | timeline measurement | `test_documents_collection_protocol.py` + `checks.documents_collection_evidence` | role-match |
| **Step 3** | | | | |
| `application/src/hyprn_mvp_app/documents.py` (new: families, versions, associations, operations, upload protocol, spool) | service | CRUD + file-I/O (spool) | `application/src/hyprn_mvp_app/computational_export.py` `ComputationalRecords` | exact (queue + artifact file + status + download) |
| `application/src/hyprn_mvp_app/api.py` (modify: routes, chunk-route exemption, capabilities) | controller | request-response | same file (computational-record routes, middleware, capabilities) | exact |
| `application/generate_contract.py` (modify) → `contracts/hyprn-mvp.openapi.yaml` (regenerate) | config (contract generator) | transform | same file lines 195–205, 243–261 | exact |
| `ui/src/contract.ts` (regenerate via `ui/generate_types.py`) | config (generated types) | transform | existing generated file (never hand-edit) | exact |
| `application/tests/test_module_boundaries.py` (modify) | test (architecture) | static analysis | same file `test_retained_run_owner_never_depends_on_its_consumers`, `EVIDENCE_WITNESSES` | exact |
| `application/tests/test_documents_api.py` (new; selectors `test_documents_upload_api_*`, `test_documents_library_api_*`, `test_documents_access_*`) | test (API integration) | request-response | `application/tests/test_computational_api.py` + `test_evidence_revisions.py` `env` fixture | exact |
| **Step 4** | | | | |
| `design-system/Layouts.md`, `Naming.md`, `components/Tabs.md`, `docs/specs/ui-target.md` §3.1 (modify; A1, A2) | config (design docs) | — | same files (study-tab lines) | exact |
| `design-system/components/Progress.md` + `ui/src/design/primitives.tsx` `Progress` (modify; A3 measured variant) | component | presentation | `primitives.tsx` `Progress` lines 41–44 | exact |
| `design-system/components/Notice.md` (new) + `Notice` in `ui/src/design` (new; A4) | component | presentation | `StatusTag` (`components.tsx` 334–341) + `.evidence-recovery` banner CSS (`foundry.css` 189) | role-match |
| `ui/src/design/index.ts` (modify: exports) | config (barrel) | — | same file | exact |
| `ui/design_smoke.mjs` (modify) | test (render smoke) | — | same file `check(...)`/`render(...)` lines 36–50, 152–161 | exact |
| `ui/src/documents.css` (new, imported once from `main.tsx`) or `ui/src/styles.css` (A7) | config (screen CSS) | — | `foundry.css` `.overview-grid` + `@media` rules lines 214–215 | exact |
| `ui/src/DocumentsLibrary.tsx`, `ui/src/DocumentUpload.tsx` (new) | component (screen) | request-response + polling | `ui/src/ComputationalExportDialog.tsx` (enqueue/poll/download) + `Workspace.tsx` `study-row` list | role-match |
| `ui/src/views/registry.ts` (modify: the Documents entry before Evidence) and `ui/src/views/documents.tsx` (new: the Documents library view module) | component (view module) | routing + presentation | the registry and view modules of Phase 3 task 3.3b (see "Study-shell view registry"); today's tab list and view slot in `ui/src/Workspace.tsx` lines 417 and 441, which the registry replaces | exact (after 3.3b) |
| `ui/src/workspaceModel.ts` (modify: `WorkspaceView`, link fields) | utility | transform | same file lines 70, 82–91 | exact |
| `ui/src/api.ts` (modify: document methods, raw chunk PUT, verified download) | service (client) | request-response | same file `mutate`, `request`, `downloadComputationalRecord`, `artifact` | exact |
| `deployment/tests/documents_ui_fixture.py` (modify: `start_isolated_api`) | test fixture | HTTP serve | `deployment/tests/ae_ui_fixture.py` `run` | exact |
| `ui/tests/documents-library.spec.ts` (new, `@documents-library-ui`) | test (browser) | — | `ui/tests/assumptions-evidence.spec.ts` (tags, `capture`) + `ui/tests/foundry-zoom.spec.ts` | exact |
| `ui/control-map.json` / `ui/check_ui_contract.py` (modify) | config (contract checker) | static | `ui/check_ui_contract.py` `routes` + `control_tests` | exact |
| **Step 5** | | | | |
| `ui/src/DocumentCollections.tsx` (new) | component (screen) | CRUD | Collections panel = `Panel` + quiet `Button aria-pressed` (`foundry.css` line 34); dialogs = `DialogFrame`/`ActionDialog` | role-match |
| `ui/tests/documents-collections.spec.ts` (new) | test (browser) | — | `assumptions-evidence.spec.ts` | exact |
| **Step 6** | | | | |
| `deployment/images/parser.Dockerfile` (new) | config (image) | build | `deployment/worker.Dockerfile` + `deployment/application.Dockerfile` (`--require-hashes`) | exact |
| Parser image manager (new, e.g. `deployment/parser_image.py` or a function in the Phase 2 image manager) | service (build manager) | file-I/O + build | `deployment/execution_runtime.py` `build_worker` + `deployment/migrate_runtime.py` `upstream_archive` | exact |
| `integration/src/hyprn_mvp_integration/document_parser.py` (new; runs inside the image) | utility (in-image entry) | transform | `integration/src/hyprn_mvp_integration/worker.py` (copied into image by Dockerfile) | role-match |
| `integration/src/hyprn_mvp_integration/document_parser_launch.py` (new) | service (launcher + canaries) | process isolation | `integration/src/hyprn_mvp_integration/launcher.py` `isolated`, `attest`, `require_attestation`, `POLICY` | exact |
| Parser policy file (new, tracked, next to worker policy) | config | — | `launcher.py` `POLICY` dict (lines 45–46) — moved to a reviewed file per D-07 | role-match |
| `integration/tests/test_documents_parser.py` (new; `documents-parser-image`, `documents-parser-containment`) | test (docker) | measured canaries | `integration/tests/test_isolation.py` | exact |
| `deployment/pins.json`, `docs/legal/licensing.md` (modify) | config | — | same files | exact |
| **Step 7** | | | | |
| `integration/src/hyprn_mvp_integration/document_extraction.py` (new: `@calcfunction`, manifest, text folder) | service (native process) | batch / transform | `integration/src/hyprn_mvp_integration/calculation.py` (`FolderData` retention, `matches` before launch, CREATE-link reads) | partial (no calcfunction exists) |
| `integration/tests/test_documents_extraction.py` (new) | test (native + docker) | — | `test_documents_native.py` (boundary injection, fresh-process reconcile) | role-match |
| **Step 8** | | | | |
| `application/src/hyprn_mvp_app/document_search.py` (new) | service | CRUD (projection) + query | `store.list_evidence` cursor binding (store.py 589–675) | role-match |
| `application/tests/test_documents_search.py` (new) | test | — | `test_evidence_revisions.py` | role-match |
| **Step 9** | | | | |
| `TextReader` in `ui/src/design` + `design-system/components/TextReader.md` (new; A5) | component | presentation | none (see No Analog); placement like `ui/src/design/source.tsx` | none |
| `ui/src/DocumentReader.tsx` (new) | component (screen) | request-response | `EvidenceView.tsx` (read with abort + generation fence) | role-match |
| `ui/tests/documents-reader.spec.ts` (new) | test (browser) | — | `assumptions-evidence.spec.ts` | exact |
| **Step 10** | | | | |
| `application/src/hyprn_mvp_app/document_citations.py` (new) | service | transform + validation | `store.exact_evidence` / `evidence_snapshot` (store.py 37–67) — single-owner pure functions | role-match |
| `application/src/hyprn_mvp_app/store.py` (modify: EvidenceCreate4/Revise4, source reservations) | model | CRUD | same file `add_evidence`/`revise_evidence` (678–718) | exact |
| `application/src/hyprn_mvp_app/api.py` evidence routes (modify: admit 4; annotation, preview, usage routes) | controller | request-response | same file lines 376–400; usage route like approach `/versions/{version_id}/usage` (api.py 302) | exact |
| `CitationRecord` in `ui/src/design` + `design-system/components/CitationRecord.md` (new; A6) | component | presentation | `CriterionRecord` (`primitives.tsx` 86–113) + `SourceChip` | exact (presentation-only record) |
| **Step 11** (blocked by research Open Question 1) | | | | |
| `configuration.py`, `scientific_configuration.py`, `execution_bundle.py`, `approach.py`, `approach_closure.py`, `history.py`, `modified_runs.py`, `result_bindings.py`, `modeling.py`; integration `results.py`, `calculation.py`, `worker.py`, `launcher.py`; `contracts/modeling.openapi.yaml`; `upstream/whatsopt-patches/100-…patch` | model / service (versioned chain) | transform | `execution_bundle.py` `uses_polish_envelope`/`frozen_version` (174–182), `RETAINED_PAIRINGS`; `upstream/whatsopt-patches/090-quantity-definitions.patch` | exact (prior chain increments) |
| **Step 12** | | | | |
| `application/src/hyprn_mvp_app/history.py` (modify), `ui/src/RunPanel.tsx` (modify) | service / component | read-only historical | `History.read` / `retained_read_integrity` (history.py 174, 345); `RunEvidence` no-live-fetch guard (`check_ui_contract.py` 32–35) | exact |
| **Step 13** | | | | |
| `ui/src/EvidenceView.tsx` (Citations section in `EvidenceRecordBody`), `EvidencePanel.tsx`, `EvidencePicker.tsx`, `EvidenceIndex.tsx`, `Assumptions.tsx`, `ConfigurationPanel.tsx`, `ApproachAssumptions.tsx`, `RunPanel.tsx`, `recordViews.ts` | component | presentation + request-response | `EvidenceView.tsx` lines 12–55 (`Source references` section at 45) | exact |
| `ui/tests/documents-evidence.spec.ts`, `documents-zoom.spec.ts` (new) | test (browser) | — | `foundry-zoom.spec.ts` | exact |
| **Factorization (D-18)** | | | | |
| `application/src/hyprn_mvp_app/routes/documents.py` (new, 4.1; every later Documents route task) | controller (router) | request-response | the per-owner routers of Phase 3 task 3.3a; `agent_runtime/routes.py` (3.4); today's route bodies in `api.py` | exact (after 3.3a) |
| `deployment/group_registry.py`, `deployment/groups/<family>/<group>.json` (new, 4.4) | config (group registry) | batch | `deployment/checks.py` `DOCUMENTS_ROUTES` (an entry table with mode, targets, selector) and the family sets | exact |
| `deployment/tests/browser_harness.py` (new, 4.4a) | test fixture (HTTP serve, Playwright run) | request-response | the proxy handler and Playwright staging copies in `ae_ui_fixture.py`, `approach_ui_fixture.py`, `units_ui_fixture.py`, `ui_fixture.py`, `combined_fixture.py`, `findings_native_fixture.py`, `units_native_fixture.py` | exact (one copy becomes the harness) |
| `ui/src/views/documents.tsx`, `documentReader.tsx`, `citedSource.tsx` (new, 4.13, 4.26, 4.29) | component (view module) | presentation + routing | the view modules and `ui/src/views/registry.ts` of Phase 3 task 3.3b; `useGuardSlot` (`workspaceModel.ts`) | exact (after 3.3b) |
| Access-loss hosts (4.22a) | component | session seam | `ui/src/accessLoss.ts`, `api.readFailed`; `EvidenceIndex.tsx`, `RecordedConfiguration.tsx` | exact |
| `application/src/hyprn_mvp_app/execution_bundle.py` capability table (4.37) | model (version families) | transform | `BundleFamily` and `bundle_family` in the same file; `history.stored_family` | exact (extension) |

---

## Pattern Assignments

### `integration/src/hyprn_mvp_integration/documents.py` (service, single-writer CRUD) — step 1

**Analog A (adapter conventions):** `integration/src/hyprn_mvp_integration/documents.py`

**Module contract and lazy AiiDA import** (lines 1–21, 127–129): no `aiida` import at module load; every native call imports inside the method.
```python
MAX_ORIGINAL = 10 * 1024 * 1024
CHUNK = 256 * 1024
NAMESPACE = 'hyprn_mvp_documents'
...
def _nodes(self, cls, filters):
    from aiida import orm
    return orm.QueryBuilder(backend=self.backend).append(cls, filters=filters).limit(2).all(flat=True)
```

**Closed-shape validators** (lines 30–47): reuse `_exact`, `_uuid`, `_hash`, `_integer` for every new verb input. Never add a parallel validator.

**Identity binding** (lines 80–87): every verb starts with `self._identity(identity)` (store UUID re-check, study scope, `payload_sha256`).

**Witness-first transaction** (lines 199–229) — the template for `collection_*` and `annotation_*`:
```python
identity, payload = json.loads(json.dumps([identity, payload], allow_nan=False))
self._command(identity, payload)
with self.backend.transaction():
    prior = self.reconcile(identity)
    if prior is not None:
        return prior
    ...                                    # mutate
    self._original(association)            # exact readback precedes witness/commit
    witness = self._witness(metadata)
    orm.Dict(dict=witness, backend=self.backend).store()
return witness
```

**Reconcile semantics** (lines 176–197): zero witnesses → `None` (absence is not a fencing proof); several → `'uncertain'`; changed digest → conflict. Generalize this function across categories (`upload`, `collection`, `annotation`, `extraction`) by keeping the unfiltered command lookup (comment at lines 180–181) and branching on `witness['category']`.

**Bounded reads** (lines 231–258): `descriptor`, `stream`, `read` verify the full original before yielding bytes; `read` returns `disposition='attachment', cache_control='no-store', content_type_options='nosniff'`. The read-loop `original` verb wraps `read()`.

**Analog B (collection protocol to port):** `deployment/tests/documents_native_fixture.py` `CollectionProtocolProbe`

**Prior lookup before active filter or CAS** (lines 326–347):
```python
prior = self.receipts(command)
if len(prior) > 1: raise ValueError('multiple witnesses: uncertain')
if not prior: return None
witness = prior[0]
if witness['payload_digest'] != digest(command): raise ValueError('command digest conflict')
```

**Fail-closed state validation** (lines 402–433): lifecycle in `('active','deleted')`, int revision, UUID collection id, terminal marker `{command_id, payload_digest}` that points to exactly one matching delete witness. Port as product code.

**Active filter before bounded pagination** (lines 435–441):
```python
filters = {'extras.hyprn_mvp_documents.lifecycle': 'active', **{...scope fields...}}
return orm.QueryBuilder(backend=self.backend).append(orm.Group, filters=filters,
    project='uuid').order_by({orm.Group: {'id': 'asc'}}).limit(100).all(flat=True)
```

**Logical terminal delete** (lines 443–482): `group.remove_nodes(list(group.nodes))`, then extras `lifecycle='deleted'`, `revision+1`, `deletion` marker, then witness, all in one `backend.transaction()`. Never `Group` delete or `clear()`.

**Required changes when porting** (from research Pitfall 6): create at `revision=1` (probe uses `revision=-1 → 0`, line 372/367); output shapes validated against `DocumentCollection1` (`revision ≥ 1`, `lifecycle: "active"`). Keep `boundary(name)` fault hooks only in the test probe; product code takes an injectable `fault` callable like `NativeExecution.fault` (`calculation.py` `self.fault('before_node')`, line 335).

**Do not:** add `documents.py` to `ATTESTED_PROJECT_FILES` or import it from `launcher`, `calculation`, `results`, `worker` (`application/tests/test_module_boundaries.py` lines 87–96, 282–289).

---

### `integration/tests/test_documents_collections.py`, `test_documents_annotations.py` (native tests) — step 1

**Analog:** `integration/tests/test_documents_collection_protocol.py`, `integration/tests/test_documents_native.py`

**Probe acquisition through the runner globals** (collection protocol lines 6–9):
```python
def probe():
    import checks
    from documents_native_fixture import CollectionProtocolProbe
    return CollectionProtocolProbe(checks.PROJECTION_SCOPE, checks.NATIVE_BACKEND)
```

**Production-adapter case builder** (`test_documents_native.py` lines 139–151, `docs26_case`): builds `NativeDocuments(checks.NATIVE_BACKEND, study_id=scope.run_uuid, native_store_id=scope.store_uuid)` plus a closed payload and `payload_digest`. Copy for collection and annotation commands.

**Boundary failure + lost reply** (`test_documents_native.py` lines 179–212): monkeypatch `orm.Dict.store` / `backend.transaction` to fail at `before_*`, `after_*`, `after_commit`; assert `reconcile()` result and node counts.

**SIGKILL + fresh-process replay** (collection protocol lines 42–60): `p.kill_at(command, boundary)` → `returncode == -9`, `reply_received is False` → `inspect_fresh` equals before (or committed state with exactly one receipt).

**Naming rule:** functions must start with `test_documents_collections_` / `test_documents_annotations_` (selector derived from the group name, `checks.py` lines 202, 215–218). No `skip`/`xfail` anywhere (lines 219–224 refuse them). Every measured case calls `p.record(label, dict(before=..., ...))` (fixture lines 63–67) so the measured validator finds artifacts.

---

### `deployment/tests/documents_native_fixture.py` (fixture, modify) — step 1

**Analog:** same file.

- Entry `start(*, group)` (lines 19–28) checks `DOCUMENTS_ROUTES[group]['mode'] == 'native'`; a new native-backed browser mode must be admitted here or in the UI fixture, not by loosening this check.
- Fresh-process helpers `_child` (484–491), `inspect_fresh`/`replay_fresh` (493–513), `kill_at` (515–536): reuse them, pointing the child at production `NativeDocuments` methods instead of the probe's own `mutate` (research Wave 0 gap).
- Evidence path: `guard.scoped_path(self.scope, 'evidence/atomicity-' + label + '.json')` with `open('x')` (lines 63–67) — never overwrite.

---

### `deployment/checks.py` (registry, modify in nearly every task — serialize)

**After task 4.4 (D-18):** no task edits `checks.py` to register a group; a group is one entry file under `deployment/groups/<family>/` (see "Group registry for every group" below). The analogs in this section describe today's file, which 4.4 converts.

**Analog:** same file.

**Route registration** (lines 162–187):
```python
DOCUMENTS_ROUTES = {
    'documents-collection-protocol': {'mode': 'native',
        'targets': ('integration/tests/test_documents_collection_protocol.py',),
        'selector': 'test_documents_collection_protocol_'},
    ...
}
GROUPS.update({group: route['targets'] for group, route in DOCUMENTS_ROUTES.items()})
DOCUMENTS_MEASURED_GROUP = 'documents-collection-protocol'
```

**Interpreter by mode** (190–194) and **needs derived from mode** (566–573):
```python
DOCKER_GROUPS = (... | {g for g, route in DOCUMENTS_ROUTES.items() if route['mode'] == 'native'})
BROWSER_GROUPS = (... | {g for g, route in DOCUMENTS_ROUTES.items() if route['mode'] == 'browser'})
```
Add a `'browser-native'` mode (native interpreter; both `docker` and `browser` needs) by extending these two comprehensions and `documents_interpreter`, `documents_capabilities` (231–245) and `documents_child` (295–338). Do not reuse `'browser'`: it selects `APPROVED_CONTRACT_PYTHON` (research Pitfall 8).

**Measured-artifact validator** (260–292) and its hook (366–371):
```python
if status == 0 and group == DOCUMENTS_MEASURED_GROUP:
    try:
        documents_collection_evidence(scope)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        status = 1
```
Generalize to a `DOCUMENTS_MEASURED = {group: validator}` mapping; add validators for `documents-read-loop` (timeline: block start, every read start/end, release; each read ends before release and within the bound) and `documents-parser-containment` (every canary case present and passed).

**Result acceptance** (248–257, 374–378): a child exit without `tests.json` reporting `passed is True`, `tests > 0`, `skipped == 0` is a failure. Keep.

**Browser targets** (208–213): a `.ts` target must contain the literal `@<group>` tag.

---

### `application/src/hyprn_mvp_app/document_bridge.py` (bridge, app side) — step 2

**Analog:** `application/src/hyprn_mvp_app/dispatcher.py`

**Imports / module header** (lines 1–22): docstring states it is not a public endpoint; stdlib + `.store`, `.contracts`; no FastAPI.

**Closed verb table + refusal before I/O** (lines 50–51, 75–80):
```python
BRIDGE_ARITIES={'require_attestation':0,'bundle_runtime':0,'launch':2,
                'matches':1,'inspect':1,'read_record':2,'resolve_results':1,'archive_record':1}
def bridge_request(method,values,*,read_only=False,exports_only=False):
    if (not isinstance(method,str) or method not in BRIDGE_ARITIES or ...
            or (read_only and method!='read_record') ...):
        raise ValueError('Unexpected bridge operation')
```
For documents, the verb tables come from the registry `x-documents-contract.bridge.read` (7 verbs) and `.write` (15 verbs, only the in-scope ones admitted), and every frame is validated with `closed('DocumentBridgeRead1'|'DocumentBridgeWrite1', frame)` before it is written (pattern: `closed('ArchiveRecordRequest1', values[0])`, line 82).

**Frame codec** (lines 24, 55–73): reuse `MAX_MESSAGE`, `bridge_encode`, `bridge_decode` (duplicate-key and non-finite refusal). Do not write a second codec.

**Client** (lines 149–160): `NativeBridge.call` writes one line to stdout, reads one bounded line from stdin, accepts only `{'data': ...}`; anything else raises. A missing reply is `ConnectionError` → operation stays `uncertain`, never retried.

**Owner-exit detection** (line 251): `if select.select([sys.stdin],[],[],1)[0]:return` — the read-mailbox loop must exit when the host closes stdin.

**Lock contention** (lines 25–48): reuse `wait_out_lock` / `lock_backoff` for store-busy errors.

---

### `application/src/hyprn_mvp_app/dispatcher.py` (modify: drain document writes) — step 2

**Analog:** same file, export queue.

```python
def export_once(store,request_id=None):
    return records_for_store(store).process_one(NativeBridge(exports_only=True).archive_record,request_id=request_id)
...
while True:
    try:
        if args.with_exports:export_once(store)
        observation.refresh()
```
(lines 171–172, 228–231). Add one `documents_once(store)` call in the same serve iteration. The serve loop is the single writer; a document write waits while `launch` blocks it, which the UI reports as "Saving waits for a running calculation to finish." Note lines 235–238: export work continues while attestation is not ready — document writes should follow the same rule (they never need the attested worker).

---

### `deployment/document_reads_runtime.py` (host read process) and `deployment/dispatch_runtime.py` (modify) — step 2

**Analog:** `deployment/dispatch_runtime.py`

**Fixed host dispatch** (lines 26–40): one `if method==...` per verb, nothing generic.

**Owned stdio child** (lines 43–67):
```python
child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,env=env,cwd=cwd)
try:
    on_ready()
    while True:
        raw=child.stdout.readline(MAX_MESSAGE+1)
        if not raw:break
        ...
        except (OSError,RuntimeError,ValueError,TimeoutError):response=dict(error='native_unavailable')
        child.stdin.write(bridge_encode(response));child.stdin.flush()
finally:
    child.stdin.close();child.stdout.close()
    if child.poll() is None:
        child.terminate();child.wait(timeout=10)
```

**Exclusive lock** (lines 236–238): the read process takes its **own** lock file (not `executor.lock`) with `O_CREAT|O_RDWR|O_NOFOLLOW, 0o600` and `flock(LOCK_EX|LOCK_NB)`.

**App-side command** (lines 256–261): `['docker','exec','-i',application_runtime.NAME,'python','-B','-m','hyprn_mvp_app.dispatcher', ...]` → for reads `-m hyprn_mvp_app.document_bridge --reads`.

**Conflict note:** `dispatch_runtime.py` is edited by Phase 2 tasks 2.3 and 2.8 (it imports `approach_polish_release as release_binding`, line 20). Put the read-loop core in the new file; keep the `dispatch_runtime.py` hook a small separate task after 2.8.

---

### `application/src/hyprn_mvp_app/store.py` (additive tables) — steps 2, 3, 8, 10

**Analog:** same file.

**Additive schema** (lines 69–177; queue table 132–141):
```sql
CREATE TABLE IF NOT EXISTS computational_record_requests(
 request_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id),
 actor_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('preview','create')),
 command_id TEXT NOT NULL, payload_digest TEXT NOT NULL, ...
 state TEXT NOT NULL CHECK(state IN ('queued','building','reviewable','ready','failed')),
 generation INTEGER NOT NULL, payload_json TEXT NOT NULL, error_json TEXT, ...
 UNIQUE(study_id,kind,command_id)
);
```
Model `document_operations.state` as a `CHECK(state IN (...))` over the registry's `operation_transitions` states, with `generation` for claim fencing.

**Immutability triggers** (lines 142–149, 162–165, 175–176): add `BEFORE UPDATE/DELETE … RAISE(ABORT, …)` for document versions, citations and any frozen descriptor rows.

**Migration of existing tables** (lines 191–196): `PRAGMA table_info` + `ALTER TABLE … ADD COLUMN` inside `connection(write=True)`.

**Transactions** (lines 198–210): `isolation_level=None`, `BEGIN IMMEDIATE` only for writes.

**Commands and receipts** (lines 361–397):
```python
def command(self,actor,study,category,command,payload,operation,*,owner=False,receipt_state="committed",request=None):
    with self.connection(write=True) as db:
        if study:self.authorize(db,actor,study,write=True,owner=owner)
        ...
        old=self.command_receipt(db,scope,category,command)
        if old: ... raise DomainError("command_payload_conflict") ... return old["result"]
        db.execute("SAVEPOINT domain_write")
```
Use `Store.command` with new categories (for example `document_upload`, `document_collection`, `document_annotation`, `document_extraction`). Use `Store.cas(current, expected)` (399–400) for every `expected_revision`.

**Authorization first** (lines 243–247): `self.authorize(db, actor, study, write=...)` before any association lookup; a missing membership is `resource_not_found` 404 (non-disclosing).

---

### `application/src/hyprn_mvp_app/documents.py` (service: uploads, library, operations) — step 3

**Analog:** `application/src/hyprn_mvp_app/computational_export.py` `ComputationalRecords`

**Authorized row read** (lines 367–371):
```python
def _row(self,db,actor,sid,rid):
    self.store.authorize(db,actor,sid)
    row=db.execute('SELECT * FROM computational_record_requests WHERE study_id=? AND request_id=?',(sid,rid)).fetchone()
    if row is None:raise DomainError('resource_not_found',404)
```
Unknown and foreign IDs both fall through to the same 404 (D-02).

**Public projection validated on the way out** (lines 373–382): `return validate('RecordRequestRead', value)` → `validate('DocumentOperation1' | 'DocumentUploadStatus1' | ..., value)`.

**Enqueue with replay, quota and receipt** (lines 447–468): `store.replay` first; quota counted inside `apply(db)` (`pending[0]>=32 ...` → per-study 4 incomplete uploads and 100 MiB staged); `store.command(actor, sid, category, command_id, payload, apply)`.

**Owned file I/O** (lines 497–516): server-derived path under a checked root, `O_NOFOLLOW`, `S_ISREG`, bounded read, hash check. Same for spool chunk files (`O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600`, lines 665–666) and atomic publish with `os.replace` + directory `fsync` (671–674).

**Download re-authorizes after I/O** (lines 518–525): status → read → status again.

**Queue processing with generation fence** (lines 635–691): claim under flock, `state='building', generation+1`, every later `UPDATE … WHERE … AND generation=?` checks `rowcount==1`; exceptions persist only a safe error (`safe_export_error`, never a native message or path).

**Limits** (lines 26–27 `LIMITS = dict(...)`): define `DOCUMENT_LIMITS` once and add a test asserting it equals `x-documents-contract.limits` from `contracts/schemas/model.schema.json` (D-07: code and contract cannot drift).

**Spool location:** beneath the application `/store` bind mount (`deployment/application_runtime.py` line 85 `expected={"/store":...}`); not `/tmp` (16 MiB tmpfs, line 255).

---

### `application/src/hyprn_mvp_app/api.py` (controller, modify) — steps 3, 5, 7, 8, 10

**After Phase 3 task 3.3a (D-18):** Documents routes go in `routes/documents.py` (see "Per-owner routers" below); `api.py` keeps the middleware (including the chunk-route exemption), the auth dependency, the envelope and the `create_app` composition. The route shapes below are copied into the router, not into `api.py`.

**Analog:** same file.

**Service wiring in `create_app`** (lines 102–111): construct `Documents(store)` beside `records=records_for_store(store) if store is not None else None` — `create_app(None, None, None)` must still work for `generate_contract.py` (line 12 there).

**Middleware** (lines 113–153). The chunk route is the **only** exemption from:
```python
if len(raw)>2*1024*1024:raise DomainError("limit_exceeded",413)
if raw:
    if request.headers.get("content-type","").split(";")[0]!="application/json":
        raise DomainError("invalid_request",400,fields=[issue((),"Content-Type must be application/json.")])
```
Keep the host, origin, session and CSRF checks (lines 117–121) for the chunk PUT. Use a route-exact regex (research "Code Examples"), a 262,144-byte streaming cap, `application/octet-stream` only, and skip JSON parsing only for that match. Note the session cookie name on line 121 becomes `hyprn_mvp_session` after 1.4.

**Route shape** (lines 439–457) — copy for document routes:
```python
@app.post('/api/1/studies/{study_id}/computational-records',status_code=202)
def create_record(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
    if request.query_params:raise DomainError('invalid_request',400)
    return response(request,records.enqueue_create(who,valid_id(study_id),body),202)
```
**Download response** (lines 451–457): `Response(content=raw, media_type=..., headers={'Content-Disposition': 'attachment; filename="..."', 'X-Content-SHA256': ...})`. For originals, the filename must be RFC 6266/5987-encoded from the stored display name, never raw; the middleware already adds `no-store`, `nosniff`, `no-referrer` (line 152).

**Receipts** (lines 458–476): add document categories to `GET /studies/{sid}/commands/{command_id}?category=…` following the `computational_record_*` branch (re-authorize, keep the original result immutable).

**Capabilities** (lines 194–206): `"documents"` stays in `unavailable` until the PD-4.8 gate; slice IDs (research Open Question 5) are appended conditionally exactly like `(["model/3"] if units else [])`.

**Evidence routes** (lines 376–400): today `validate("EvidenceCreate",body)` and `validate("EvidenceRevise3",body)`. Step 10 admits EvidenceCreate4/Revise4 **in addition** (Phase 3 agent tools depend on 1–3).

---

### `application/generate_contract.py` → `contracts/hyprn-mvp.openapi.yaml` (contract generator) — every API task

**Analog:** same file.

- Shared `$defs` flow in unchanged (line 20: `schemas.update(rewrite(SCHEMA["$defs"]))`); Document definitions are already there.
- Per-route response/request mapping is an `elif` chain (lines 195–205 for computational records). Add document branches; unknown paths raise `ValueError(path)` (line 240), so a route without a mapping fails generation.
- Error statuses and CSRF/Origin headers are added uniformly (lines 243, 258–261). The chunk PUT must also get `Origin` + `X-CSRF-Token` (extend the `method in {"post","patch","delete"}` set to include `"put"`), and a `requestBody` of `application/octet-stream`.
- Binary download response pattern (lines 248–255).
- Output default (line 302) becomes `contracts/hyprn-mvp.openapi.yaml` after 1.4. Regenerate, then run `ui/generate_types.py`; never hand-edit either output.

---

### `application/tests/test_module_boundaries.py` (modify) — steps 2, 3, 8, 10

**Analog:** same file.

**Reachability pins** (lines 462–470):
```python
owner, sources, seeds = 'hyprn_mvp_app.history', 'hyprn_mvp_app.result_bindings', 'hyprn_mvp_app.modified_runs'
assert not reachable([owner]) & {sources, seeds}, sorted(reachable([owner]) & {sources, seeds})
```
Add: `documents` → only `contracts`, `store`; `document_citations`/`document_search` → `contracts`, `store`, `documents`; none of them reachable from `execution_bundle` or any attested root.

**Single evidence-read owner** (lines 478–481, 518–533): `EVIDENCE_WITNESSES` and `test_exact_evidence_reading_has_one_owner` fail on any new `FROM evidence` statement or `'EvidenceRecordRead'` literal outside `store.py`. `document_citations.py` must read evidence through `Store.evidence_record` (store.py 730–741), or the task updates `EVIDENCE_WITNESSES` with a reviewed reason.

**Private-access allowlist** (`PRIVATE_ALLOWLIST`, line 549): a new `request._body`-style access in the chunk route must be added there with its reason.

---

### `application/tests/test_documents_api.py` (API integration tests) — step 3

**Analog:** `application/tests/test_computational_api.py` (lines 1–25) and `application/tests/test_evidence_revisions.py` (lines 20–26).

```python
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

@pytest.fixture
def env(tmp_path):
    assert guard.no_symlinks(tmp_path).is_relative_to(SCOPE.root)
    store = Store(tmp_path / 'evidence.sqlite')
```
HTTP through `TestClient(create_app(store, Auth(store, ORIGIN), model), base_url=ORIGIN)` with a loopback `ORIGIN` constant (`test_computational_api.py` lines 17–25). Restart = construct a new `Store` + `create_app` on the same file. Foreign-study cases: second study, same IDs, assert identical 404 body shape.

---

### `application/tests/test_documents_bridge.py` (bridge policy) — step 2

**Analog:** `deployment/tests/test_bridge.py`

**Refusal before any I/O** (lines 30–35):
```python
def test_invalid_bridge_calls_fail_before_io_or_native(method,args,monkeypatch,capsys):
    with pytest.raises(ValueError): dispatcher.NativeBridge().call(method,*args)
    assert capsys.readouterr().out == ''
    with pytest.raises(ValueError): dispatch_runtime.native_call(Native(),method,args)
```
**Mode isolation** (lines 38–41): read mode refuses every write and scientific method on both ends. **In-process wire** (lines 44–60): `wire(monkeypatch, native, read_only=...)` exercises real app and host codecs without a subprocess. Name tests `test_documents_bridge_*`. If it imports `dispatch_runtime` (a deployment module), register it as a native-mode group; otherwise `application/contracts`.

---

### Design-system additions A1–A7 — step 4 (A5 step 9, A6 step 13)

**Doc analog:** `design-system/components/SourceChip.md`, `FilePicker.md`, `Progress.md` — one short paragraph or bullet list stating consumer-provided props, states, accessibility and the "never" rules. `Progress.md` today is one paragraph; A3 appends a "Measured" paragraph.

**Study-tab text to change in the same task (A1/A2):** `design-system/Layouts.md` line 9, `design-system/Naming.md` line 82, `design-system/components/Tabs.md` line 5, and `docs/specs/ui-target.md` §3.1.

**Component analog — Progress (A3):** `ui/src/design/primitives.tsx` lines 41–44:
```tsx
/** Indeterminate progress only. No percentage is inferred from execution stages. */
export function Progress({ label, message }: { label: string; message?: string }) {
  return <section className="hf-progress"><p role="status">{label}</p><progress aria-label={label} />{message && <p className="hf-progress__message">{message}</p>}</section>;
}
```
Extend with optional `value`/`max`/`valueText`; fail closed to this exact indeterminate markup. CSS already exists (`foundry.css` 286–289); add `.hf-progress__value` with tokens only.

**Component analog — Notice (A4):** `StatusTag` (`components.tsx` 334–341, shape + word + colour via `Mark`), tone classes `.hf-tag--alarm … --running` (`foundry.css` 75–80), and the existing banner rule `.evidence-recovery{padding:var(--space-4);background:var(--warning-soft);border:1px solid var(--warning);border-radius:var(--radius-sm)…}` (`foundry.css` 189). Generalize that rule into `.hf-notice--<tone>`; use the existing `Tone` type (`components.tsx` 27).

**Component analog — CitationRecord (A6):** `CriterionRecord` (`primitives.tsx` 86–113): typed props, `useId` heading, `<article aria-labelledby>`, presentation only ("callers … supply saved …"), nested `ActionDialog` for detail. Embed `SourceChip` (`components.tsx` 441–464) for title + locator + authority.

**Barrel:** add every export to `ui/src/design/index.ts` (lines 7–52); screens import only from `./design`.

**Smoke:** `ui/design_smoke.mjs` — add `render(name, h(F.X, props))` + `check(name, condition, html)` cases (pattern lines 152–161), and extend the `expected` export list (line 53).

**Layout CSS (A7):** analog `foundry.css` lines 214–215:
```css
@media(max-width:1050px){.overview-grid{grid-template-columns:minmax(0,1fr)}...}
@media(max-width:600px){...}
```
Grid tracks `var(--panel-outline)` / `var(--panel-inspector)`, gaps `var(--space-3)`. Px values only inside `@media` preludes (the checker exempts them).

**Gates per task:** `python3 ui/check_design_system.py` (no FAIL), `python3 ui/design_tokens.py --check`, `python3 ui/test_design_tooling.py`, `node ui/design_smoke.mjs`.

---

### `ui/src/Workspace.tsx` and `ui/src/workspaceModel.ts` (shell) — step 4

**Analog:** same files.

Tab list (Workspace.tsx line 417):
```tsx
items={(['overview', 'model', 'configurations', 'runs', 'evidence'] as const).map(id => ({ id, label: id === 'model' ? 'Models' : id[0].toUpperCase() + id.slice(1) }))}
```
Insert `'documents'` before `'evidence'`, **only when the library slice is advertised** (D-08). View slot pattern (line 441): `<div hidden={view !== 'evidence'}>{view === 'evidence' && <EvidencePanel key={study.study_id} … />}</div>`.

`workspaceModel.ts`: `WorkspaceView` union (line 70), `WorkspaceLink` fields (line 82), `views` allowlist (line 83) and `parseWorkspaceLink` (85–) — add `'documents'` and explicit `document`/`version`/`extraction`/locator fields; an unknown view throws `'This workspace view is unavailable.'` (line 90).

**After Phase 3 task 3.3b (D-18):** each Documents screen is a view module under `ui/src/views/` registered in `ui/src/views/registry.ts` (see "Study-shell view registry" below); the tab list, link parsing and guard placement above are what the registry replaces, and `Workspace.tsx` is edited only for view-independent shell behaviour.

Shared with the Phase 3 Agent activity page (the `activity` view module of task 3.23): one task at a time on `ui/src/views/registry.ts`, `Workspace.tsx` and `workspaceModel.ts`.

---

### `ui/src/api.ts` (client) — steps 3–5, 7–10

**Analog:** same file.

- JSON reads: `request<T>(path, body?, method, signal)` (lines 165–179): 30 s timeout, actor-change guard, 401 → `closeSession()`.
- Commands: `mutate<T>(path, body, category, study, method, signal)` (lines 187–199) keeps `pending` for uncertain outcomes; reuse with document categories.
- Verified binary download: `downloadComputationalRecord` (lines 314–339) — expected size bound, streamed size check, SHA-256 compare, actor re-check; copy for `downloadOriginal`.
- **New:** the chunk PUT cannot use `request` (it sets JSON `Content-Type`, line 169). Write one `putChunk` method: `fetch(url, { method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/octet-stream', 'X-CSRF-Token': this.csrf, <sha256 header> }, body: bytes })`, with the same timeout, actor and 401 handling as `request`.

---

### `ui/src/DocumentsLibrary.tsx`, `DocumentUpload.tsx`, `DocumentCollections.tsx`, `DocumentReader.tsx` (screens) — steps 4, 5, 9

**Analogs:**
- List rows: `Workspace.tsx` home list (line 411): `<Panel className="study-list" bodyClassName="catalogue-body" label="Studies">{visibleStudies.map(s => <article className="study-row" …><div><h2>…</h2></div><div className="actions">…</div></article>)}</Panel>` and empty state `<p className="empty-state">…</p>`. UI-SPEC S1 asks for `<ul>` of `<article>` rows (no table).
- Loading: `<p role="status" aria-busy="true"><StatusTag tone="running">Loading studies…</StatusTag></p>` (same region).
- Enqueue → poll → download: `ui/src/ComputationalExportDialog.tsx` (checked strings in `check_ui_contract.py` line 17: `previewComputationalRecord`, `computationalRecord`, `downloadComputationalRecord`, `clearTimeout(timer)`).
- Abortable reads with a generation fence: `EvidenceView.tsx` lines 13–23 (`request.current?.abort(); const controller = new AbortController(); … const token = ++generation.current;` and `evidenceAccessLost` → clear content, line 7, 21).
- Dirty guard: join the existing ordered guard (`useGuardSlot`, `workspaceModel.ts` line 57; `Workspace.tsx` dirty dialog at the end of the file).

---

### `deployment/tests/documents_ui_fixture.py` (`start_isolated_api`) — step 4

**Task 4.4a (D-18):** built on `browser_harness.serve` and `run_playwright` (see "Browser-fixture harness" below), never as another copy of the handler; the points below are what the harness and the Documents fixture's own arguments carry.

**Analog:** `deployment/tests/ae_ui_fixture.py` `run` (lines 95–183)

- Scope and interpreter guard first (lines 96–101), then `sys.path` inserts (102–103).
- `ThreadingHTTPServer(('127.0.0.1', 0), Handler)` on an ephemeral port (174–180); write `scope.json`, replace `os.environ` with `guard.clean_environment(scope)`.
- `/api/1/*` proxied into `TestClient(app)` (148–164); add `do_PUT` (the AE handler has only GET/POST, lines 107–108) and raise the 2 MiB `Content-Length` guard only for the chunk route.
- Static UI from `dist` with a path-containment check (165–169).
- Test-only controls under `/fixture/*` (113–147) — use the same shape for "block the writer", "stop the read loop", "stop the modeling double".
- In-process writer and read loop: `scoped_fixture.run_export_dispatcher` (scoped_fixture.py 345–369) shows how to run the real app CLI with the guarded native backend and forbid unrelated constructors (`dispatcher.ModelingClient=forbidden`).
- The function **must be named `start_isolated_api`** at module top level (`checks.documents_capabilities`, lines 236–245).

---

### `ui/tests/documents-*.spec.ts` (browser) — steps 4, 5, 9, 13

**Analog:** `ui/tests/assumptions-evidence.spec.ts`, `ui/tests/foundry-zoom.spec.ts`

**Tag in the title** (assumptions-evidence line 290): `test('@ae-evidence titled evidence shows …', async ({page}) => {…})` → `test('@documents-library-ui …')`.

**Light/dark capture** (line 9):
```ts
async function capture(page: Page, name: string) { for (const colorScheme of ['light','dark'] as const) { await page.emulateMedia({colorScheme}); await page.screenshot({path:`${process.env.HYPRN_MVP_UI_EVIDENCE_ROOT}/opk-${name}-${colorScheme}.png`,animations:'disabled'}); } }
```
(`HYPRN_MVP_UI_EVIDENCE_ROOT` after 1.6.)

**Genuine 200 % zoom** (`foundry-zoom.spec.ts` lines 9–24, 57–63, 70–87): Chromium extension + `chrome.tabs.setZoom(tab.id, 2)` at a native 1440 × 1000 window, `page.viewportSize()` must be `null`; per control: focus visible (2px outline), inside 720 × 500, unobstructed hit test, and
```ts
const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
expect(layout.scroll, name).toBeLessThanOrEqual(layout.width + 1);
```
Loop `for (const theme of ['light', 'dark'] as const)` (line 89).

---

### `ui/control-map.json` / `ui/check_ui_contract.py` (contract checker) — every UI and API task

**Analog:** `ui/check_ui_contract.py`

**Route ↔ type binding** (lines 44–57):
```python
routes={
    '/studies/{study_id}/computational-records':('post','RecordRequest'),
    '/studies/{study_id}/computational-records/{request_id}':('get','RecordRequest'),
}
for path,(method,kind) in routes.items():
    operation=spec['paths'][path][method]
    success=operation['responses']['202' if method=='post' else '200']
    assert kind in json.dumps(success),(path,kind)
    assert kind in (ROOT/'src/contract.ts').read_text()
```
**Control ↔ named browser test** (lines 140–145): every control id maps to a test title string that must exist in the spec file. After 1.6 these move into `ui/control-map.json`; register each Documents control and route in the task that adds it.

**History never fetches live** (lines 32–35): the run evidence region is scanned for forbidden strings (`'api.'`, `'fetch('`, `'useEffect('`). Apply the same guard to the cited-source history view (S7) and run citations (step 12).

---

### Parser image (step 6): `deployment/images/parser.Dockerfile`, parser image manager, `document_parser.py`, `document_parser_launch.py`

**Dockerfile analog:** `deployment/worker.Dockerfile` (whole file) and `deployment/application.Dockerfile` line 4:
```dockerfile
ARG ENGINE_IMAGE
FROM ${ENGINE_IMAGE}
ARG WORKER_SHA256
LABEL org.hyprn-mvp.worker_sha256=${WORKER_SHA256}
USER 0:0
COPY worker.py /opt/hyprn_mvp_integration/worker.py
ENV PYTHONPATH=/opt PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
WORKDIR /output
```
```dockerfile
RUN python -m pip install --no-index --find-links=/wheels --require-hashes -r /requirements.lock && rm -rf /wheels
```
Parser: base = Phase 2's digest-pinned CPython 3.12 base from `deployment/pins.json`; install `--no-deps --no-index --require-hashes --only-binary=:all:`; re-hash the wheel inside the build; label the parser source SHA-256; non-root user.

**Build manager analog:** `deployment/execution_runtime.py` `build_worker` (lines 24–68): verify base identity against `pins.json` and the lock SHA-256 before building (37–42); copy exact inputs into a `tempfile.TemporaryDirectory(dir=root)` context (44–46); `docker build --network=none --pull=false --label … --build-arg …` (49–50); keep the build log as evidence (51–53); re-check source hashes after the build (57–58); write a runtime record (59–67).

**Wheel acquisition/cache analog:** `deployment/migrate_runtime.py` `upstream_archive` (lines 537–558):
```python
info = os.lstat(path)
if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
        or info.st_mode & 0o077 or info.st_mode & 0o222):
    raise ValueError('Upstream archive is not an owner-private read-only file: ' + str(path))
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
...
if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
    raise ValueError('Upstream archive identity mismatch')
```
Cache location resolves through `deployment/local_paths.py` (add a `HYPRN_MVP_PARSER_CACHE` variable or a `cache/parser` layout constant beside `UPSTREAM = 'cache/upstream/whatsopt'`, line 113, and document it in the module docstring, lines 14–60). No literal paths in code.

**Launcher analog:** `integration/src/hyprn_mvp_integration/launcher.py`
- Policy (lines 45–46): `POLICY=dict(memory='256m',cpus='0.5',pids='32',wall_seconds=20,output_bytes=65536,scratch_bytes=16777216,user='65534:65534',file_bytes=1048576)` → parser values (1 CPU, 512 MiB, 64 PIDs, 64 MiB scratch, 30 s) come from a **tracked reviewed policy file** hashed into the fingerprint (D-07), not literals.
- `isolated()` (lines 259–304): `docker run --name <unique> --label <owner> --network none --user … --read-only --cap-drop ALL --security-opt no-new-privileges --memory … --memory-swap … --cpus … --pids-limit … --log-driver none --tmpfs … --mount type=bind,…,readonly`; external wall clock and output cap with `selectors`; `docker kill` then `docker rm -f` in `finally`. Add reaping of labelled parser containers at writer start (research Pitfall 9).
- `fingerprint()` / `require_attestation()` (lines 149–175): evidence `passed` and an exact fingerprint match, else `RuntimeError('Failed or stale containment attestation')`. Extraction start refuses without current parser evidence (D-05).
- `attest()` (lines 312–353): synthetic canaries only (non-root, socket, home, secrets incl. `AIIDA_`, write denied, network denied, cgroup memory/pids/cpu values, OOM, wall, output, file bound, PIDs); writes `evidence/containment.json`, archives the previous file by hash.

**In-image entry analog:** `worker.py` is copied into the image and run as `python -m …` (launcher line 275). `document_parser.py` follows the same "copied in, stdlib + pypdf only, no project imports beyond itself" rule.

**Test analog:** `integration/tests/test_isolation.py` (line 6: missing/failed/changed fingerprint cannot authorize; line 21: real canaries).

---

### `integration/src/hyprn_mvp_integration/document_extraction.py` (calcfunction) — step 7

**Partial analog:** `integration/src/hyprn_mvp_integration/calculation.py` (attested — copy patterns, **never import it** from a document module, and never import a document module from it).
- Retain material as `orm.FolderData` with `put_object_from_filelike` (lines 332–334) → text folder per page.
- Look up before launch: `if self.matches(request): raise RuntimeError('Existing native request cannot be launched again')` (319–320) → one active extraction per installation; an interrupted attempt is never resumed.
- Verify provenance by CREATE links (lines 197–205): `node.base.links.get_outgoing(link_type=LinkType.CREATE, link_label_filter='results').one().node` → the provenance group verifies `manifest` and `text` outputs and the `original` input link.
- Fault hooks `self.fault('before_node')` etc. (335–350) for kill tests.

---

### `application/src/hyprn_mvp_app/document_search.py` (projection + search) — step 8

**Analog:** `Store.list_evidence` (store.py 593–675).
- Strict query allowlist: unknown or repeated keys → `invalid_request` 400 (lines 599–601).
- Cursor binds actor, study, view and filter digest plus a high-water mark (lines 644–656):
```python
binding=dict(cursor_version='1',study_id=sid,actor_id=actor,view=view,family_id=family_id,filter_digest=digest(values))
...
if (not isinstance(token,dict) or set(token)!=set(binding)|{'high_water','last_rowid'} or
    any(token[k]!=v for k,v in binding.items()) or self._evidence_cursor(token)!=cursor ...):raise ValueError()
```
For documents add the query, the projection revision and (research Open Question 8) an HMAC over the canonical token (`hmac` stdlib, key stored once in an application-store row).
- Bounded SQL page with `LIMIT ?+1` and `next_cursor` (lines 669–675).

---

### `application/src/hyprn_mvp_app/document_citations.py` and evidence v4 — step 10

**Analog:** `store.py` lines 19–67 and 678–718.
- One owner for exact reads and snapshot shape (`exact_evidence`, `evidence_snapshot`); citations get the same treatment: one pure `freeze_citation(...)` producing `DocumentCitation1`, used by evidence, configuration and history.
- `add_evidence` (678–697): authorize → `validate(...)` → `replay` → resolve context outside the write → `apply(db)` rechecks inside the write → `self.command(...)`. Evidence v4 adds: resolve each citation through the read loop (fragment verb) **before** `apply`, recheck source reservations **inside** `apply` (commit barrier).
- `revise_evidence` (699–718): `self.cas(old['evidence_version_id'], expected)` on the family head.
- Validate with `validate('EvidenceRecord4', result)` before insert (pattern line 692/713).

**Usage route ("Used by"):** copy the approach usage route shape (`api.py` line 302 `/approach/versions/{version_id}/usage`, generator mapping `generate_contract.py` lines 140–150 with `limit`/`cursor` parameters).

---

### Step 11 chain files (blocked by research Open Question 1)

**Analog:** `application/src/hyprn_mvp_app/execution_bundle.py` lines 174–182:
```python
def uses_polish_envelope(model,closure):
    return model['schema_version']=='4' or closure is not None and closure['schema_version']=='3'
def frozen_version(model,closure):
    return '7' if uses_polish_envelope(model,closure) else '5' if uses_units_envelope(model,closure) else '4'
```
Each new document-bearing version is one more branch, plus one more tuple in `RETAINED_PAIRINGS` (pinned by `test_module_boundaries.py` `test_retained_pairings_are_exactly_the_twelve_historic_tuples_with_one_owner`, line 648) and golden digests unchanged for older versions. Modeling side: a new patch after `upstream/whatsopt-patches/090-quantity-definitions.patch` (AGPL scope). Attested files change → re-attestation (research Pitfall 7).

---

### Step 12 and 13 UI changes (`EvidenceView.tsx`, `RunPanel.tsx`, evidence editors)

**Analog:** `ui/src/EvidenceView.tsx` `EvidenceRecordBody` (lines 12–55).
- Insert the "Citations" section between content and "Source references" (line 45: `{inspected.source_refs.length > 0 && <><SectionHeader title="Source references" />…}`), rendering `CitationRecord` from stored descriptors only.
- "Retained callers never fetch" (comment line 11; `library` prop optional): the cited-source view and run evidence pass no `library` and do no live lookup; enforced by the checker guard (`check_ui_contract.py` lines 32–35).
- Record details dialog pattern (lines 47–49): `<dl className="hf-record-details"><dt>…</dt><dd><code>…</code></dd>` → "Citation record" fields (UI-SPEC "Record details dialogs").

---

## Factorization analogs (product owner's schedule, D-18)

Line numbers are those of the planning commit; re-check them when the task starts (Phase 2 task 2.1 adds a few lines to `deployment/checks.py`).

### Per-owner routers — `application/src/hyprn_mvp_app/routes/documents.py` (4.1; later Documents route tasks)

**Analog:** the routers Phase 3 task 3.3a creates (`routes/<owner>.py`, each `router(deps) -> APIRouter`) and its edge-helper module; the first router of the codebase, `agent_runtime/routes.router` (Phase 3 task 3.4). Today's route bodies are in `api.py` `create_app` (line 121; middleware line 132; capabilities line 227; approach usage line 340; model assumption evidence line 382; evidence lines 414–437; receipts line 496).

- `router(deps)` receives the services `create_app` builds (`store`, `auth`, the `Documents` service, the bridge) and returns an `APIRouter`; `create_app` includes it at the composition point that keeps the existing route registration order, so the generated contract for existing routes stays byte-identical.
- Helpers the routes share (`valid_id`, `response`, the actor dependency, `page`) come from 3.3a's edge-helper module, never from `api.py` (`api` imports `routes.documents`; the reverse would be a cycle).
- `application/tests/test_module_boundaries.py` gets the `routes.documents` row in the same task (imports: the edge-helper module, `contracts`, `store`, `documents`, `document_bridge`, later `document_citations` and `document_search`; imported only by `api`).
- The chunk-route body exemption is edge middleware and stays in `api.py` (route-exact pattern).

### Study-shell view registry — `ui/src/views/documents.tsx`, `documentReader.tsx`, `citedSource.tsx` (4.13, 4.26, 4.29)

**Analog:** the closed registry Phase 3 task 3.3b creates (`ui/src/views/registry.ts`; entries `{name, parseLink, render(ctx), guard?, available(capabilities)}`, one module per view) and the `activity` view module of task 3.23. Today's equivalents: the tab list and view slots of `ui/src/Workspace.tsx` (lines 417, 441), `WorkspaceView`, `views` and `parseWorkspaceLink` in `ui/src/workspaceModel.ts` (lines 70, 83, 85), the ordered editor guard `useGuardSlot` / `GuardEntry` (`workspaceModel.ts` line 57), and the controller pattern of `ApproachController.tsx` (and the `ModelController` 3.3b adds).

- `available(capabilities)` reads `document_slices`; a view whose slice is absent shows no tab and no control (D-08).
- `parseLink` owns the view's link fields (document, version, extraction, locator, collection, cited-source origin) and throws the same "This workspace view is unavailable." / "incomplete" errors as today's parser.
- `guard` joins the shell's ordered guard (an active upload transfer in the library view).

### Group registry for every group — `deployment/group_registry.py`, `deployment/groups/<family>/<group>.json` (4.4)

**Analog:** `deployment/checks.py`: `DOCUMENTS_ROUTES` (line 168: a per-group table with `mode`, `targets`, `selector`) is the entry shape to generalize; the hand-kept sets it replaces are `GROUP_INTERPRETERS` (line 477), `AE_BROWSER_GROUPS` and the `AE_*` sets (480–491), `APPROACH_*` (493–505), `UNITS_*` with `UNITS_SELECTIONS` (509–528), `RELEASE_PYTEST_GROUPS`, `FOUNDRY_BROWSER_GROUPS`, `LOCALITY_PYTEST_GROUPS`, `NATIVE_PYTEST_GROUPS`, `APPLICATION_PYTEST_GROUPS`, `MODELING_PYTEST_GROUPS` (532–555), `CHILD_GROUPS` (559), `AGENT_PYTEST_GROUPS` and `AGENT_DIRECTORY_TARGETS` with `directory_target` (566–580), `OPT_IN_GROUPS`, `DOCKER_GROUPS`, `BROWSER_GROUPS`, `FIXTURE_GROUPS`, `FIXTURE_BROWSER_SPECS` (605–619). Ordering and listing: `must_pass_groups` (675) and `list_groups` (682) follow `GROUPS` insertion order, so entries carry an explicit rank. Dispatch by name today: `run_group` (863), `findings_guards_passed` (938, exactly 17 tests), `child` (969), `contracts_child` (the guard-first step of `approach-contracts`, the `units-guards` suite).

- Keep every exported name and value (`GROUPS`, `DOCUMENTS_ROUTES`, the family sets): fixtures (`from checks import AE_BROWSER_GROUPS`, `DOCUMENTS_ROUTES`, `documents_targets`) and guard tests import them.
- Closed schema, fail loading on any unknown key; the orphan guards (browser specs, `test_*.py` modules from Phase 1 task 1.11, Documents tests) read targets through the loader.
- Proof of no behaviour change: `--list` before and after, and every group's counts before and after.

### Browser-fixture harness — `deployment/tests/browser_harness.py` (4.4a)

**Analog (proxy handler, the copies to merge):** `ae_ui_fixture.py` `run` (handler lines 105–172, server line 174), `approach_ui_fixture.py` (handler 48–146, server 148), `units_ui_fixture.py` (`guarded_request` and handler 207–327, server 328), `ui_fixture.py` (handler 33–74, server 76), `combined_fixture.py` (`write_http_response` 22–33; `web` handler 131–139, server 141; its modeling-contract double at 169–177 is not a browser proxy and stays), `findings_native_fixture.py` (handler 747–760, server 763).
**Analog (Playwright staging and run, the copies to merge):** `ae_ui_fixture.py` 347–356, `approach_ui_fixture.py` 324–350, `units_ui_fixture.py` 361–370, `units_native_fixture.py` 188–211, `findings_native_fixture.py` 1127–1135 (with `durable_write`), `ui_fixture.py` 206–210.

- What is common and moves: `/api/1/*` through `TestClient` with hop-by-hop and length headers dropped; static `dist` with `is_relative_to` containment and regular files only; `respond`; disconnect tolerance (`write_http_response`); the staging configuration that imports `ui/playwright.isolated.config.ts`; `node …/playwright/cli.js test --grep <tag> --reporter=json`; parsing `stats`.
- What stays per fixture (arguments): the write predicate (for example the AE `writable` expression), the body cap (2 MiB in the AE, approach and units fixtures; none in the others today, passed explicitly), the `/fixture/*` controls, seed data, and file-writing rules (`durable_write`).
- Not merged: `foundry_ui_fixture.py` (an in-browser API double with its own generated configuration and snapshot policy).
- Guard tests that patch `ThreadingHTTPServer` in a fixture module (`test_ae_browser_fixture_guards_before_server_or_application`) patch it in `browser_harness` instead.

### Access-loss seam — residual hosts (4.22a)

**Analog:** `ui/src/accessLoss.ts` (`useAccessLoss`); `ui/src/api.ts` `accessDenied` (line 21), `onSessionChange` (108), `accessLost` (120), `fence` (121), `confirmAccess` (131), `readFailed` (152); hosts already on the seam: `EvidenceIndex.tsx` (line 147), `RecordedConfiguration.tsx` (19), `ApproachFindings.tsx` (184), `executionReadiness.ts` (10). The local classification to remove: `evidenceAccessLost` (`EvidenceView.tsx` line 7, which also treats `resource_not_found` as access loss) and its callers (`EvidencePanel.tsx` 41 and 126, `EvidencePicker.tsx` 33 and 47, `Assumptions.tsx` 114, `ModelEditor.tsx` 52, `UnitEditor.tsx` 19, `ConfigurationPanel.tsx` 127 and 155). Study-shell lists cleared only on sign-out today: `Workspace.tsx` `clearSession` (line 137).

### Version-family capabilities — `execution_bundle.py` (4.37) and its consumers (4.37, 4.38)

The attested table is added only inside the re-attesting task 4.37; 4.35 admits its new configuration and approach versions with explicit checks, which 4.37 replaces.

**Analog:** `application/src/hyprn_mvp_app/execution_bundle.py`: the "Version interpretation points" comment (lines 52–62), `RETAINED_PAIRINGS` (63), `BundleFamily` with the capability properties `carries_dependencies` and `carries_approach` (76–95), `bundle_family` (110), `uses_typed_units`, `uses_polish_envelope`, `uses_units_envelope`, `frozen_version` (166–182); `history.stored_family` (line 53). Tests: `application/tests/test_module_boundaries.py` `HISTORIC_PAIRINGS` and `HISTORIC_FAMILIES` (664–682), `test_bundle_family_is_derived_from_the_single_table` (694), `test_unlisted_bundle_versions_are_explicitly_unsupported` (705), `FAMILY_LITERALS` and `PRODUCER_MAPS` (714–722), `test_application_holds_no_second_retained_pairing_table` (736); golden corpus `application/tests/test_identity_golden.py`.

- Literal comparisons by module (planning commit): `configuration.py` about 24, `computational_export.py` about 10, `execution.py` 5, `modified_runs.py` 5, `history.py` 4; producers and admission sets stay explicit.
- The worker and `results.py` keep their own tables (trust boundary).

## Shared Patterns

### Study-scoped authorization before any lookup
**Source:** `application/src/hyprn_mvp_app/store.py` lines 243–247; used in `computational_export.py` line 368.
**Apply to:** every document route, operation drain, read-mailbox delivery, cursor page and download.
```python
def authorize(self, db, actor, study, write=False, owner=False):
    row=db.execute("SELECT role FROM memberships WHERE study_id=? AND actor_id=?",(study,actor)).fetchone()
    if row is None: raise DomainError("resource_not_found",404)
    if owner and row["role"]!="owner" or write and row["role"]=="reader":
        raise DomainError("forbidden",403)
```

### Command identity, replay and CAS
**Source:** `store.py` `replay`/`command`/`cas` (lines 361–400).
**Apply to:** upload begin/complete, collection create/update/members/delete, annotation create/revise/delete, extraction start, evidence v4. An `uncertain` outcome is never re-sent; recovery reads the receipt and then the native witness.

### Error envelope and IDs
**Source:** `api.py` `valid_id` (77–81), `error_response` (97–100), `response` (167–168); `contracts.py` `DomainError` and `validate(name, value, *, remote=False)` (lines 120–131).
**Apply to:** all API code. Validate public shapes with `validate('<Document$def>', value)`; use `remote=True` for values read back from native (fail as `backend_unavailable` 503, never echo native text).

### Closed bridge frames
**Source:** `dispatcher.py` `bridge_encode`/`bridge_decode`/`bridge_request` (55–116); `dispatch_runtime.py` `bridge_child` (43–67).
**Apply to:** document writes (executor loop) and reads (read loop). One codec, one byte bound, refusal before I/O.

### Single-writer queue with generation fence
**Source:** `computational_export.py` `process_one` (635–691) under an owned flock.
**Apply to:** `document_operations` drain and the one-active-extraction rule.

### Owner-private file I/O
**Source:** `computational_export.py` `_path`/`_read_artifact` (497–516) and atomic publish (661–674); `migrate_runtime.py` `upstream_archive` (537–558).
**Apply to:** upload spool, parser wheel cache, parser scratch, evidence files.

### Locations
**Source:** `deployment/local_paths.py` (resolution order docstring lines 1–60; `located()`, `require()`).
**Apply to:** spool root, parser cache, parser scratch, read-loop lock, evidence. No literal path in code (AGENTS.md).

### Measured evidence and runner registration
**Source:** `deployment/checks.py` 162–187, 260–292, 341–399; fixture `record()` (documents_native_fixture.py 63–67).
**Apply to:** every new Documents group; measured groups get a validator.

### Design-system only UI
**Source:** `ui/src/design/index.ts`; tokens via `design-system/tokens.json` → `ui/src/design/tokens.css` (generated).
**Apply to:** every screen. Status is `StatusTag`/`Notice` (shape + word + colour); provenance is `SourceChip`/`trace` only; no inline styles; text from uploads rendered only as React text nodes.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `TextReader` in `ui/src/design` (A5) | component | presentation + selection mapping | No read-only text surface exists. `SourceSurface` (`ui/src/design/source.tsx`) is a code-editor overlay over a textarea and must not be reused as the reader. Use UI-SPEC A5 and research Pattern 4 (UTF-16 → codepoint conversion on the server). |
| `integration/src/hyprn_mvp_integration/document_extraction.py` | service | batch | No `@calcfunction` exists in the tree; only a `CalcJob` (`calculation.py`). Partial patterns listed above; verify the multi-output dict return on aiida-core 2.9.3 in the first extraction task (research assumption A5). |
| `integration/src/hyprn_mvp_integration/document_parser.py` | utility (in-image) | transform | No PDF or text parser exists. Only the "copied into the image, run as a fixed command" convention (worker.py) applies; behaviour comes from `docs/specs/documents.md` §7 and `integration/document-parser-provenance.md`. |
| Read-loop timeline validator (in `deployment/checks.py`) | config | measurement | No existing measured-latency validator; the collection evidence validator is the structural template only. |
| Signed cursor key row (in `store.py`) | model | crypto | No server signing key exists (approach "signed" values are content digests). Research Open Question 8. |

---

## Metadata

**Analog search scope:** `application/src/hyprn_mvp_app/`, `application/tests/`, `application/generate_contract.py`, `integration/src/hyprn_mvp_integration/`, `integration/tests/`, `contracts/`, `deployment/` (managers, Dockerfiles, `tests/`), `ui/src/`, `ui/src/design/`, `ui/tests/`, `ui/*.py`, `ui/design_smoke.mjs`, `design-system/`, `upstream/whatsopt-patches/`.
**Files scanned:** 48 read or grepped (of 392 tracked files).
**Pattern extraction date:** 2026-10-13. Re-check line numbers after Phase 1 tasks 1.4–1.8 land (renames shift no logic but may shift lines).
