# Phase 3: Agent tools for coding agents - Pattern Map

> Superseded in part by ADR-0002 (docs/adr/0002-agent-write-rights.md): proposals, confirmation classes, the proposals page and envelope grants are retired; sections on them are historical. 03-CONTEXT.md and 03-PLAN.md govern.

**Mapped:** 2026-10-13
**Files analyzed:** 74 new or modified files (grouped below by stage and module)
**Analogs found:** 61 / 74 (the rest have no codebase precedent; see "No Analog Found")

## How to read paths in this document

Phase 1 task 1.4 renames the packages and the contract. Every entry gives the **analog as it exists today** and the **final path the plan uses**. Line numbers refer to today's files; re-locate them with `grep` after task 1.4 lands (the code moves, the patterns do not).

| Today (analog path, line numbers valid now) | Final path used in plans |
|---|---|
| (pre-rename identifiers) | see the note below this table |
| `editions/local/` (README only) | `editions/local/src/hyprn_mvp_local/` (Phase 2 tasks 2.1, 2.2, 2.9-2.13 create `cli.py`, `paths.py`, `output.py`, `credentials.py`, `setup.py`, `smoke.py`) |

Until Phase 1 task 1.4 lands, the tree still carries the pre-rename package, integration-package, contract, session-cookie, environment-variable, container-label and capability identifiers. This document writes only the final names (`application/src/hyprn_mvp_app/`, `integration/src/hyprn_mvp_integration/`, `contracts/hyprn-mvp.openapi.yaml`, cookie `hyprn_mvp_session`, `HYPRN_MVP_*` variables, labels `org.hyprn-mvp.*`); before task 1.4, locate a file by its basename and a symbol by its name (task 1.4's identifier table gives the exact pairs).

All analog paths below were checked with `git ls-files` (tracked source, no mirrors).

## File Classification

### Stage 1 - Agent principal and attribution (tasks 3.1-3.3)

| New/Modified file (final path) | Role | Data flow | Closest analog (today) | Match |
|---|---|---|---|---|
| `application/src/hyprn_mvp_app/auth.py` (modify) | service (credentials) | request-response | itself: `auth.py` `login`/`authenticate`/`authorize_mutation`/`recover` | exact |
| `application/src/hyprn_mvp_app/store.py` (modify: agent DDL, `authorize`, listing, pre-study refusal) | model / store | CRUD | itself: `store.py` `SCHEMA`, `authorize`, `list_studies`, `study_listing`, `command` | exact |
| `application/src/hyprn_mvp_app/api.py` (modify: middleware rules, router mount, outer dispatcher, capabilities) | controller / composition root | request-response | itself: `boundaries` middleware, `actor` dependency, `from_environment`; `ui.py` `mount_workspace` | exact |
| `application/src/hyprn_mvp_app/agent_runtime/__init__.py`, `schema.py` | model (own tables) | CRUD | `store.py` `SCHEMA` + `Store.__init__` additive migration | role-match |
| `application/src/hyprn_mvp_app/agent_runtime/delegations.py`, `tokens.py` | service | CRUD | `auth.py` token minting/hashing + `store.py` `set_membership` | role-match |
| `application/src/hyprn_mvp_app/agent_runtime/attribution.py` | service (index) | CRUD + read | `store.py` `study_archive` table + `set_study_archived` | role-match |
| `application/src/hyprn_mvp_app/agent_runtime/routes.py` | route (APIRouter) | request-response | `api.py` archive routes, `Closed` models, `page()` | role-match (no `APIRouter` exists yet) |
| `application/src/hyprn_mvp_app/agent_runtime/__main__.py` | utility (operator CLI, no HTTP route) | batch | `auth.py` `main()` | exact |
| `application/generate_contract.py` (modify) | config / generator | transform | itself: archive route block and `X-CSRF-Token` parameter loop | exact |
| `contracts/hyprn-mvp.openapi.yaml`, `ui/src/contract.ts` (regenerated) | config (generated) | transform | `application/generate_contract.py`, `ui/generate_types.py` | exact |
| `application/tests/test_agent_principal.py` | test | request-response | `application/tests/test_study_archive.py`, `test_authorization.py` | exact |
| `application/tests/test_agent_runtime_admin.py` | test | CRUD | `application/tests/test_study_archive.py` | exact |
| `application/tests/test_module_boundaries.py` (modify) | test (architecture) | static analysis | itself | exact |
| `deployment/checks.py` (modify: register groups) | config (runner) | batch | itself: `locality-contracts`, `foundry-nav`, `ui-reading` registrations | exact |
| `deployment/tests/test_repository_guard.py` (modify: closed-group guards) | test | static | itself: `LocalityContractsGuardTests`, browser-spec registry test | exact |
| `design-system/components/AttributionChip.md` (new) | doc (component) | - | `design-system/components/StatusTag.md`, `SourceChip.md` | exact |
| `design-system/components/InferenceBlock.md`, `design-system/Naming.md`, `design-system/Layouts.md` (modify) | doc | - | themselves | exact |
| `ui/src/design/components.tsx`, `ui/src/design/index.ts`, `ui/src/design/foundry.css` (modify: `AttributionChip`, `InferenceBlock` statuses and props) | component | render | `StatusTag`, `SourceChip`, `InferenceBlock` in `components.tsx`; `.hf-tag`, `.hf-infer` in `foundry.css` | exact |
| `ui/design_smoke.mjs` (modify) | test (component smoke) | render | itself: StatusTag and InferenceBlock checks | exact |
| record views: `ui/src/Workspace.tsx`, `ui/src/EvidenceView.tsx`, `ui/src/RunPanel.tsx`, `ui/src/RecordedConfiguration.tsx`, `ui/src/OverviewRecords.tsx`, `ui/src/ApproachPanel.tsx` (modify: chip placements) | component (screen) | render | `Workspace.tsx` model heading row with `StatusTag`; `OverviewRecords.tsx` rows | exact |
| `ui/src/api.ts` (modify: attribution read) | service (client) | request-response | `api.ts` read arrow members (`approach`, `approachVersion`) | exact |
| `deployment/tests/agent_ui_fixture.py` | test fixture (runner child) | batch | `deployment/tests/foundry_ui_fixture.py` | exact |
| `ui/tests/agent-fixtures.ts` (in-browser API double) | test fixture | request-response (mocked) | `ui/tests/foundry-fixtures.ts` | exact |
| `ui/tests/agent-attribution.spec.ts` | test (browser) | render | `ui/tests/record-labels.spec.ts` | exact |

### Stage 2 - Read-only tools and the local MCP server (tasks 3.4-3.10)

| New/Modified file (final path) | Role | Data flow | Closest analog (today) | Match |
|---|---|---|---|---|
| `agent_tools/__init__.py`, `spec.py`, `registry.py` | service (catalogue) | transform | `application/generate_contract.py` `OPERATION_NOTES` (operation descriptions); `contracts.py` `validate` | partial |
| `agent_tools/api_client.py` | service (in-process client) | request-response | `application/tests/test_study_archive.py` `login()` (TestClient with Origin + CSRF); `ui/src/api.ts` `request()`; `modeling.py` `ModelingClient(transport=...)` seam | role-match |
| `agent_tools/catalogue/*.py` (orient, study, approach, model, evidence, configuration, runs, conclusion, housekeeping) | service (tool handlers) | request-response | `ui/src/api.ts` route list (same `/api/1` paths); `ui/src/EvidenceIndex.tsx` read orchestration | partial |
| `agent_tools/projections.py` | utility | transform | `api.py` `page()` (cursor + limit) and `request_diagnostics` (never echo input) | partial |
| `agent_tools/two_phase.py` | utility | request-response | `ui/src/ChangePreview.tsx` preview-then-apply; `api.py` `ConfigurationCommitV2.expected_preview_digest` | role-match |
| `agent_tools/playbook.py` + generated `docs/agents/playbook.md` | config + generated doc | transform | `ui/design_tokens.py` `--check` staleness pattern | role-match |
| `agent_tools/instructions.py` | config | - | none | no analog |
| `agent_runtime/runtime.py`, `sessions.py`, `journal.py`, `limits.py`, `notes.py` | service | event-driven (per call) + CRUD | `store.py` `command()` (receipt-first, digest of payload, SAVEPOINT) | role-match |
| `agent_surface/__init__.py`, `jsonrpc.py` | utility (strict parser) | transform | `api.py` middleware strict-JSON block | exact (for strict JSON) |
| `agent_surface/mcp_server.py` | controller (raw ASGI) | request-response | `api.py` `boundaries` middleware + `error_response`; `ui.py` Starlette subclass | role-match |
| `application/tests/mcp_client.py`, `test_mcp_server.py` | test | request-response | `test_study_archive.py` TestClient fixtures | role-match |
| `application/tests/test_agent_registry.py`, `test_agent_api_client.py`, `test_agent_read_tools.py`, `test_agent_secret_fuzz.py`, `test_agent_runtime.py`, `application/tests/fixtures/agent/*.json` | test | mixed | `test_computational_api.py` (generated-contract parity), `test_study_archive.py` (synthetic users), `test_api.py` `FaultTransport` | role-match |
| `editions/local/src/hyprn_mvp_local/study.py`, `study_kit.py` | service (CLI command, file writer) | file-I/O | `store.py` `Store.__init__` (off-cloud, symlink, 0700/0600, `O_NOFOLLOW`); `deployment/local_paths.py` `absolute`/`located` | role-match |
| `editions/local/src/hyprn_mvp_local/mcp_tokens.py` | service (CLI command) | request-response | `auth.py` `main()`; `deployment/application_runtime.py` `main()` | role-match |
| `editions/local/src/hyprn_mvp_local/mcp_relay.py` | utility (stdio relay) | streaming | `deployment/application_runtime.py` `inspect`/`guard`/`check` (label + port binding guard) | partial |
| `editions/local/src/hyprn_mvp_local/cli.py`, `paths.py`, `deployment/config.schema.json`, `docs/operations/cli.md` (Phase 2 files, modify) | config / route (CLI) | request-response | Phase 2 plan modules (do not exist yet) | defer to Phase 2 output |
| `editions/local/tests/test_study_kit.py`, `test_mcp_tokens.py`, `test_mcp_relay.py` | test | file-I/O, streaming | `deployment/tests/test_deployment_hardening.py` `refuse_effects`; `test_attestation.py` subprocess monkeypatch | role-match |
| `application/tests/test_agent_eval_scripted.py`, `agent_eval_fixtures.py` | test | batch | `test_study_archive.py` env fixture + `deployment/tests/units_ui_fixture.py` fake `Models` | partial |
| `docs/specs/agents.md`, `docs/agents/tooling-spec.md` (modify) | doc | - | themselves | exact |

### Stage 3 - Local authoring with UI confirmation (tasks 3.11-3.18)

| New/Modified file (final path) | Role | Data flow | Closest analog (today) | Match |
|---|---|---|---|---|
| `agent_runtime/proposals.py` | service | CRUD + event-driven | `store.py` `command()` + `receipt()`/`replay()`; `computational_record_requests` table (state machine with CHECK) | role-match |
| `agent_runtime/journal.py` (reconciliation) | service | request-response | `api.py` `receipt` route (`GET /studies/{id}/commands/{command_id}?category=`) | exact |
| `agent_runtime/routes.py` (confirm, withdraw, list proposals) | route | request-response | `api.py` archive routes; middleware CSRF rule | role-match |
| `agent_tools/guards.py`, `backmaps.py` | utility | transform | `contracts.py` `issue`/`pointer`/`diagnostics`; `api.py` `request_diagnostics` | role-match |
| `agent_tools/catalogue/study.py`, `evidence.py`, `approach.py`, `model.py` (write tools) | service | request-response | `ui/src/api.ts` `mutate()` + approach mutation members | role-match |
| `ui/src/AssistantProposals.tsx` (new page) | component (screen) | request-response | `ui/src/OverviewRecords.tsx` (read state machine), `ui/src/EvidenceIndex.tsx` (guarded read + access loss) | role-match |
| `ui/src/ChangePreview.tsx` (extract `ModelChangeTable`) | component | render | itself `differences` + `DifferenceTable` (lines 16-59) | exact |
| `ui/src/ApproachPanel.tsx` (extract `ApproachChanges`) | component | render | itself line 141 | exact |
| `ui/src/workspaceModel.ts` (view `proposals`, `proposal` key) | utility (link model) | transform | itself `WorkspaceView`, `parseWorkspaceLink`, `workspaceHash` | exact |
| `ui/src/Workspace.tsx` (entry button, view branch, breadcrumb) | component (shell) | render | itself: study heading line 416, approach view branch line 423, breadcrumb line 397 | exact |
| `ui/src/styles.css` (notice classes) | config (styles) | - | existing banner classes in `styles.css` | exact |
| `ui/tests/agent-proposals.spec.ts` | test (browser) | request-response (mocked) | `ui/tests/record-labels.spec.ts`, `ui/tests/foundry-zoom.spec.ts` (genuine 200 % zoom) | exact |
| `application/tests/test_agent_proposals.py`, `test_agent_guards.py`, `test_agent_reconciliation.py` | test | mixed | `test_study_archive.py`, `test_api.py` (`FaultTransport` lost response) | role-match |

### Stage 4 - Configurations, runs and results (tasks 3.19-3.22)

| New/Modified file (final path) | Role | Data flow | Closest analog (today) | Match |
|---|---|---|---|---|
| `agent_tools/catalogue/configuration.py` | service | request-response | `api.py` `ConfigurationCommitV2` + `generate_contract.py` `OPERATION_NOTES` for preview/commit | role-match |
| `agent_tools/catalogue/runs.py` (`submit_runs`, `wait_for_runs`) | service | polling | `ui/src/OverviewRecords.tsx` `RecentRunOutcome` (bounded polling, terminal states) | role-match |
| `agent_tools/catalogue/conclusion.py` | service | transform | `store.py` `revise_evidence` (new version of a family) | partial |
| `application/tests/test_agent_config_run_tools.py` (Docker-need group) | test | request-response | `application/tests/test_api.py` native fixture | exact |

---

## Pattern Assignments

### `application/src/hyprn_mvp_app/auth.py` (service, request-response) - modify

**Analog:** itself, `application/src/hyprn_mvp_app/auth.py` (99 lines).

**Token mint + hash** (lines 11, 55-60) - copy for agent API sessions and tool tokens (`secrets.token_urlsafe(32)` is 256 bits; prefix the tool token with `hyprn_mvp_mcp_` at mint time):
```python
def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()
...
token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
expires=time.time()+8*60*60
db.execute("INSERT INTO sessions VALUES(?,?,?,?)",
           (token_hash(token),row["actor_id"],token_hash(csrf),expires))
```

**Authenticate** (lines 64-70) - extend to consult the human `sessions` table and the new agent session table, returning `kind`, `delegation_id`, `read_only` in the dict:
```python
def authenticate(self,token):
    if not token or len(token)>256:raise DomainError("unauthenticated",401)
    with self.store.connection() as db:
        row=db.execute("SELECT actor_id,csrf_hash,expires_at FROM sessions WHERE token_hash=? AND expires_at>?",
                       (token_hash(token),time.time())).fetchone()
        if row is None:raise DomainError("unauthenticated",401)
        return dict(row)
```

**Constant-time CSRF compare** (lines 75-80): `hmac.compare_digest(session["csrf_hash"],token_hash(csrf))` - reuse for tool-token verification (compare hashes, never raw tokens).

**Recovery** (lines 32-38) - Pitfall 8: add revocation of agent sessions, tool tokens and pending proposals inside the same `connection(write=True)` block:
```python
def recover(self,password):
    # Local administrative operation only; deliberately has no HTTP route.
    ...
        db.execute("DELETE FROM sessions")
```
Note: `auth.py` imports `.store` (line 9). `agent_runtime` may import `auth` (D-10), never the reverse; keep agent-session verification functions in `auth.py` operating on tables declared in `store.py` SCHEMA or have `agent_runtime.schema` register its DDL through a store hook (see `schema.py` below) so `auth` does not import `agent_runtime`.

---

### `application/src/hyprn_mvp_app/store.py` (model, CRUD) - modify

**Analog:** itself, `application/src/hyprn_mvp_app/store.py`.

**DDL style** (lines 69-177): one `SCHEMA` string, `CREATE TABLE IF NOT EXISTS`, CHECK constraints, append-only via triggers:
```sql
CREATE TABLE IF NOT EXISTS study_archive(
 study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
 archived INTEGER NOT NULL CHECK(archived IN (0,1)),
 command_id TEXT NOT NULL, actor_id TEXT NOT NULL, changed_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS study_archive_no_delete BEFORE DELETE ON study_archive
 BEGIN SELECT RAISE(ABORT,'study archive state is never deleted'); END;
```
Copy the trigger form for `agent_actions` (append-only journal: abort UPDATE of intended fields and every DELETE). Do **not** reference `users(actor_id)` from agent tables (Pitfall 2: `sessions` line 75 does).

**Additive migration** (lines 189-196): tables are created by `executescript(SCHEMA)`; columns added later use `PRAGMA table_info` + `ALTER TABLE` in a write connection. New agent tables need no migration step (CREATE IF NOT EXISTS is additive); the migration test pattern is `test_study_archive.py` lines 289-323.

**`authorize`** (lines 243-247) - the intersection lands here, signature unchanged (Pattern 1 in RESEARCH.md):
```python
def authorize(self, db, actor, study, write=False, owner=False):
    row=db.execute("SELECT role FROM memberships WHERE study_id=? AND actor_id=?",(study,actor)).fetchone()
    if row is None: raise DomainError("resource_not_found",404)
    if owner and row["role"]!="owner" or write and row["role"]=="reader":
        raise DomainError("forbidden",403)
```

**Listing for agent actors** (lines 280-283 `list_studies`, 303-309 `study_listing`): both join `memberships` on `actor_id`; resolve an agent actor to exactly its delegated study. `api.py` capabilities (lines 196-199) probes `studies[0]` - must keep working for agents.

**Pre-study command refusal** (lines 372-375, 402-408): `command()` only authorizes `if study:`; add an agent-actor refusal (403) when `study is None` before the receipt lookup:
```python
def command(self,actor,study,category,command,payload,operation,*,owner=False,receipt_state="committed",request=None):
    error=None
    with self.connection(write=True) as db:
        if study:self.authorize(db,actor,study,write=True,owner=owner)
```

**Receipts carry the actor** (lines 392-395): `INSERT INTO receipts VALUES(scope,category,command,actor,...)` - nothing to change; the agent actor id flows through `who`.

**One owner for membership SQL:** the boundary test pins single owners of raw statements (see `test_module_boundaries.py` lines 503-519 `test_exact_evidence_reading_has_one_owner`). Add the same kind of test: `FROM memberships` appears only in `store.py`.

---

### `application/src/hyprn_mvp_app/api.py` (composition root, request-response) - modify (shared with Phase 4; one task at a time)

**Analog:** itself, `application/src/hyprn_mvp_app/api.py`.

**Closed request bodies** (lines 26-36) - every agent route body (confirm, withdraw, revoke) is a `Closed` pydantic model, never a schema in `contracts/schemas/model.schema.json` (attested):
```python
class Closed(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
class StudyArchiveCommand(Closed):
    command_id:str=Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
```

**Browser middleware** (lines 113-153) - where the agent rules go: bearer tool token on `/api/1` -> 401 (before line 117's Host check returns), read-only agent session refuses mutations (403), agent route allowlist (method + route template):
```python
@app.middleware("http")
async def boundaries(request,call_next):
    request.state.request_id=uid()
    try:
        if request.url.netloc!=auth.origin.split("://",1)[-1]:raise DomainError("forbidden",403)
        if request.method in {"POST","PATCH","DELETE","PUT"}:
            auth.authorize_origin(request.headers.get("origin"))
            if request.url.path!="/api/1/session" or request.method!="POST":
                auth.authorize_mutation(request.cookies.get("hyprn_mvp_session"),request.headers.get("origin"),request.headers.get("x-csrf-token"))
        ...
    except DomainError as exc:response=error_response(request,exc)
    response.headers.update({"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"})
```
The route template for the allowlist is available after routing only; either match `request.url.path` against compiled templates from the registry's `api_operations`, or enforce in a dependency. Keep the 2 MiB bound (line 125) unchanged for `/api/1`.

**Actor dependency** (lines 164-166):
```python
def actor(request:Request):
    return auth.authenticate(request.cookies.get("hyprn_mvp_session"))["actor_id"]
Actor=Annotated[str,Depends(actor)]
```
A confirm route needs a dependency that additionally refuses agent actors (`HumanActor`).

**Error envelope** (lines 97-100) - every new route and `/mcp` HTTP-level refusal reuses `error_response` shape.

**Capabilities** (lines 194-207): `unavailable` ends with `"cancellation","assistance"]` - drop `assistance` when the registry is active and advertise the registry version (Pitfall 15).

**Router mount / outer dispatcher** - no `include_router` exists today; the nearest mounting pattern is `ui.py` `mount_workspace(app, directory)` called from `from_environment` (lines 502-512):
```python
def from_environment():
    store=Store(os.environ["HYPRN_MVP_APP_STORE"])
    origin=os.environ["HYPRN_MVP_ORIGIN"]
    ...
    app=create_app(store,auth,model)
    from .ui import mount_workspace
    mount_workspace(app,Path('/app/ui'))
    return app
```
- `app.include_router(agent_routes(...))` goes **inside `create_app`** so `generate_contract.py` (`create_app(None,None,None).openapi()`) sees the agent routes; it must tolerate `store is None` the way line 111 does (`records_for_store(store) if store is not None else None`).
- The `/mcp` outer dispatcher wraps the result in `from_environment` only (never in `create_app`), so `/mcp` is absent from OpenAPI and unreachable from the in-process client (ND-8).

---

### `application/src/hyprn_mvp_app/agent_runtime/schema.py` (model, CRUD)

**Analog:** `store.py` `SCHEMA` (lines 69-177) and `Store.__init__` (lines 179-196); state-machine table `computational_record_requests` (lines 132-141):
```sql
state TEXT NOT NULL CHECK(state IN ('queued','building','reviewable','ready','failed')),
generation INTEGER NOT NULL, payload_json TEXT NOT NULL, error_json TEXT,
UNIQUE(study_id,kind,command_id)
```
Copy the CHECK-enum form for `agent_proposals.state` (the ten lifecycle words in `03-UI-SPEC.md`) and `agent_delegations` (revoked_at, expires_at). The connection helper is `Store.connection(write=True)` (lines 198-210: `BEGIN IMMEDIATE`, commit, rollback). Tables are created through the one `Store` (single writer); decide in task 3.1 whether the DDL string lives in `store.py` or in `agent_runtime/schema.py` with `Store.__init__` executing a registered list (avoid `store` importing `agent_runtime`).

---

### `application/src/hyprn_mvp_app/agent_runtime/__main__.py` (operator CLI, no HTTP route)

**Analog:** `auth.py` `main()` (lines 86-99):
```python
def main():
    parser=argparse.ArgumentParser(description="Local owner provisioning/recovery; never prints passwords")
    parser.add_argument("action",choices=["provision","recover"])
    parser.add_argument("--store",required=True)
    ...
    print("Owner credentials saved; recovery revokes all previous sessions.")
if __name__=="__main__":main()
```
Mint prints the token once to standard output (pipe to the CLI), never as an argument; list and revoke print JSON without secrets. Comment "deliberately has no HTTP route" mirrors `auth.recover` line 33.

---

### `application/src/hyprn_mvp_app/agent_runtime/routes.py` (route, request-response)

**Analog:** `api.py` archive routes (lines 218-223) and the paginated listing helper `page()` (lines 169-177):
```python
@app.post("/api/1/studies/{study_id}/archive")
def archive_study(study_id:str,body:StudyArchiveCommand,request:Request,who:Actor):
    return response(request,store.set_study_archived(who,valid_id(study_id),body.command_id,True))
```
```python
def page(request,items,key,cursor,limit):
    if not 1<=limit<=100:raise DomainError("invalid_request",400)
    ...
    return response(request,selected,next_cursor=key(selected[-1]) if len(items)>limit else None)
```
- `valid_id` (lines 77-81) on every path id.
- `response()` envelope (lines 167-168) `{schema_version:"1", request_id, data, ...}`.
- Confirm route is `async def` (Pattern 6) so it can await the in-process client; no async route exists today (all handlers are sync `def`) - see "No Analog Found".
- Proposal list for the UI: History 25 per read (UI-SPEC); reuse `page()` semantics.

---

### `application/generate_contract.py` (generator, transform) - modify

**Analog:** itself. Per-route post-processing loop (lines 106-129) and the mutation header rule (lines 258-261):
```python
elif path in ("/studies/{study_id}/archive","/studies/{study_id}/restore"):
    schema=ref("Study")
    op["requestBody"]["content"]["application/json"]["schema"]=ref("StudyArchiveCommand")
    for parameter in op["parameters"]:
        if parameter["in"]=="path":parameter["schema"]=uuid
    op["description"]=("...")
...
if method in {"post","patch","delete"}:
    op["parameters"]+= [{"name":"Origin","in":"header","required":True,"schema":string}]
    if path!="/session" or method!="post":
        op["parameters"]+=[{"name":"X-CSRF-Token","in":"header","required":True,"schema":string}]
```
Schemas added with the local helper `obj(...)` (line 23), e.g. `schemas["StudyArchiveCommand"]=obj(dict(command_id=uuid))` (line 32). `OPERATION_NOTES` (lines 262-300) is also the human-readable source to cross-check tool descriptions against.

**Freshness test analog:** `application/tests/test_computational_api.py` lines 249-251:
```python
subprocess.run([sys.executable,'-B',str(ROOT/'application/generate_contract.py'),'--output',str(output)],check=True,capture_output=True)
assert output.read_bytes()==(ROOT/'contracts/hyprn-mvp.openapi.yaml').read_bytes()
```
Then `ui/generate_types.py` regenerates `ui/src/contract.ts`; `ui/check_ui_contract.py` (`checks[...]` dict of required source strings) gains rows for the new UI wiring.

---

### `application/tests/test_agent_principal.py`, `test_agent_runtime_admin.py` (test)

**Analog:** `application/tests/test_study_archive.py` (no modeling service, synthetic users, scoped `tmp_path` store).

**Fixture** (lines 42-61):
```python
def login(app, username):
    client = TestClient(app, base_url=ORIGIN)
    session = client.post('/api/1/session', json=dict(username=username, password=PASSWORD), headers={'Origin': ORIGIN})
    assert session.status_code == 200, session.text
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    return client

@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / 'archive.sqlite')
    auth = Auth(store, ORIGIN)
    actors = {name: uid() for name in ('owner', 'writer', 'reader', 'stranger')}
    with store.connection(write=True) as db:
        for name, actor in actors.items():
            db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)', (actor, name, password_hash()))
    app = create_app(store, auth, None)
```
Use `LOOPBACK_ORIGIN` from `application/tests/conftest.py` (line 12) instead of a literal origin.

**Authorization matrix** (lines 190-221): stranger 404, reader 403, unchanged snapshot after refusals, wrong CSRF 403, foreign Origin 403, anonymous 401. Copy for: agent read 200, write 403 (read-only delegation), other study 404, tool token on `/api/1` 401, revocation -> next call 401/`access_lost`, `POST /studies` by agent 403.

**Store-level checks** (lines 326-343 `test_store_interface_is_in_transaction_and_authorized`): call `store.authorize`/`store.command` directly with the agent actor.

**Unit-level auth analog:** `application/tests/test_authorization.py` lines 25-37 (expiry by `UPDATE sessions SET expires_at=0`, logout revocation, `pytest.raises(DomainError,match=...)`).

Test names state the invariant (AGENTS.md); do not copy the work-item prefixes ("P4-S6a", "14-C3") present in older docstrings.

---

### `application/tests/test_module_boundaries.py` (test) - modify

**Analog:** itself.

**Scans are top-level only** - `glob('*.py')` at lines 257, 506, 523, 570, 582, 604, 706, 731, 737 (Pitfall 6). Switch production scans to `rglob('*.py')` and assert the agent subpackages are scanned.

**Relative-import resolver assumes flat packages** (lines 187-204) - this will fail or mis-resolve for subpackages and must change in task 3.1:
```python
def imports(path):
    tree = ast.parse(path.read_text())
    package = path.parent.name            # 'agent_tools' for agent_tools/x.py: wrong root
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                # the project packages are flat; a deeper relative import would be
                # silently mis-resolved, so it fails closed instead.
                assert node.level == 1, (str(path), node.lineno, 'unsupported relative import level')
                module = package + ('.' + node.module if node.module else '')
```
Compute the dotted package from the path relative to `application/src` and support `level >= 1`. `module_path` (lines 180-184) already maps dotted names to `pkg/sub/mod.py`; add `__init__.py` resolution for subpackages.

**Direction rows** - copy the form of lines 487-496:
```python
def test_approach_never_depends_on_configuration_workflow():
    approach, configuration = 'hyprn_mvp_app.approach', 'hyprn_mvp_app.configuration'
    assert configuration not in reachable([approach]), sorted(reachable([approach]))
```
D-10 rows: `reachable(['…agent_tools…'])` ⊆ {agent_tools.*, contracts, package}; `agent_surface` -> `agent_runtime` only; `agent_runtime` -> `agent_tools`, `auth`, own modules (and `store` if its tables live there; record that decision).

**Attested set unchanged** - lines 282-289 and 305-317 already assert `files == ATTESTED_PROJECT_FILES`; add an explicit assertion that no `agent_*` module is in `attested_closure()` (Pitfall 7, T-3-17).

---

### `deployment/checks.py` (runner config) - modify (shared with Phase 2; serialize)

**Analog:** itself.

**Python groups** - target tuple in `GROUPS` (lines 157-158) plus membership in a closed group set with its interpreter (lines 533-536) and the union `PROJECT_PYTEST_GROUPS` (lines 545-546):
```python
'locality-contracts': ('application/tests/test_identity_golden.py', 'application/tests/test_module_boundaries.py',
                       'application/tests/test_contract_errors.py'),
...
LOCALITY_PYTEST_GROUPS = frozenset({'locality-contracts'})
GROUP_INTERPRETERS.update({group: fixture.APPROVED_CONTRACT_PYTHON for group in LOCALITY_PYTEST_GROUPS})
```
Create e.g. `AGENT_PYTEST_GROUPS = frozenset({'agent-tools', 'mcp', 'study-kit', 'agent-eval'})`, add to `PROJECT_PYTEST_GROUPS` and `CHILD_GROUPS` (line 550). `contracts_child` (lines 761-784) inserts `application/src`, `integration/src` and test roots on `sys.path`; local-edition tests also need `editions/local/src` (coordinate with Phase 2 task 2.1, which reworks interpreters).

**Docker-need split** (`agent-tools-native`): add to `DOCKER_GROUPS` (line 566) and, if it creates a native backend, `NATIVE_BACKEND_GROUPS` (line 544).

**Browser group** - copy `foundry-nav` registration (lines 134-135) and the closed child (lines 735-743):
```python
'foundry-nav': ('deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
                'ui/tests/model-configuration-run.spec.ts', 'ui/tests/foundry-zoom.spec.ts'),
...
def foundry_browser_child(group):
    scope = fixture.scope_from_environment()  # Before fixture import, build or writes.
    if group not in FOUNDRY_BROWSER_GROUPS:
        raise ValueError('Unknown foundry browser group')
    if sys.executable != scope.interpreter or scope.interpreter != GROUP_INTERPRETERS[group]:
        raise ValueError('Child must use the reviewed interpreter')
    targets_for(group)
    import foundry_ui_fixture
    return foundry_ui_fixture.run(group=group)
```
`agent-ui` joins `BROWSER_GROUPS` (line 570) and is dispatched like line 933. Every new `ui/tests/*.spec.ts` must appear in a group (guard `deployment/tests/test_repository_guard.py` lines 917-922). Opt-in groups are pinned by name in `test_opt_in_groups_are_the_served_and_fidelity_groups` (lines 924-932) - `agent-eval-live` requires updating that guard.

**Registry guards analog:** `deployment/tests/test_repository_guard.py` lines 596-614 (`LocalityContractsGuardTests`: exact targets, interpreter, disjoint from native groups). Add one guard class per new closed group.

---

### `design-system/components/AttributionChip.md` (doc) - new

**Analog:** `design-system/components/StatusTag.md` (purpose line, "The consumer provides", rules list) and `SourceChip.md` (chip semantics, "Never style a navigation link or a button like this chip"). Format: H1 component name, one-sentence purpose, bullet rules starting with "**The consumer provides**". Contents come from `03-UI-SPEC.md` "Surface 1 - Anatomy" and "Rule".

### `design-system/components/InferenceBlock.md` (doc) - modify

Current text (whole file, 8 lines) has `**Actions.**` "Save as a new model version", secondary "Preview", quiet "Discard" and `**Status.**` `proposed`, `applied`, `discarded`, `checking`. Replace both bullets per `03-UI-SPEC.md` "Design-system changes" (ten lifecycle statuses; `ai` Confirm, quiet Withdraw). `Naming.md` gains rows in the "Reader-facing names" table (line 46-50 header form `| Concept | Reader-facing name | Not in reader text |`); `Layouts.md` gains an "Assistant proposals" H2 between "Evidence" (line 64) and "Historical views" (line 68).

---

### `ui/src/design/components.tsx`, `index.ts`, `foundry.css` (component) - modify

**Analog for `AttributionChip`:** `StatusTag` (components.tsx lines 326-342) plus the `InferenceBlock` iris mark (lines 495-500):
```tsx
export function StatusTag({ tone = 'inert', children, className }: StatusTagProps): ReactElement {
  return (
    <span className={cx('hf-tag', 'hf-tag--' + tone, className)}>
      <Mark tone={tone} />
      {children}
    </span>
  );
}
```
```tsx
<span className="hf-infer__mark" aria-hidden="true">
  <Icon>
    <Glyph name="iris" />
  </Icon>
</span>
```
Hidden prefix uses the existing `.hf-visually-hidden` class (foundry.css line 16; used in components.tsx line 209). CSS: copy `.hf-tag` geometry (foundry.css line 74) but **without** `white-space: nowrap` (UI-SPEC wrapping rule; precedent `.hf-facet__v>.hf-tag{white-space:normal}` line 324) and `.hf-infer__mark` (line 122) for the mark, sized like `.hf-mark`.

**`InferenceBlock` statuses** (lines 467-474) - replace the record:
```tsx
export type InferenceStatus = 'proposed' | 'applied' | 'discarded' | 'checking';
const PSTATE: Record<InferenceStatus, [Tone, string]> = {
  proposed: ['advisory', 'not applied'],
  applied: ['ok', 'applied'],
  discarded: ['inert', 'discarded'],
  checking: ['running', 'checking outcome'],
};
```
New props `id`, `ref`, `headingLevel` go on the `<section>` at line 493 (`aria-label` already composed from `kind` and title). `Ref` is already imported (line 25); `Button` uses `ref?: Ref<HTMLButtonElement>` (line 109) as the prop precedent.

**Exports:** add `AttributionChip` and `AttributionChipProps` to `ui/src/design/index.ts` lines 7-43 (value exports and type exports are separate blocks).

### `ui/design_smoke.mjs` (component smoke) - modify

**Analog:** itself. `expected` export list (line 53, "exports all 12 components") gains `AttributionChip`; copy the StatusTag loop (lines 128-132) for the ten `InferenceBlock` statuses and replace the check at lines 155-158 ("labelled proposal, not applied" becomes "labelled proposal, Awaiting confirmation"):
```js
const html = render('InferenceBlock', h(F.InferenceBlock, { title: 'Set z to 0', basis: [h(F.SourceChip, { key: 'a', label: 'N-1' })] }, 'Because'));
check('InferenceBlock labelled proposal, not applied', html.includes('aria-label="Proposal: Set z to 0"') && html.includes('not applied') && html.includes('Rests on'), html);
```

---

### Record views with the chip (`Workspace.tsx`, `EvidenceView.tsx`, `RunPanel.tsx`, `RecordedConfiguration.tsx`, `OverviewRecords.tsx`, `ApproachPanel.tsx`) - modify

**Analog placement:** the model heading row puts a state tag after the title (`ui/src/Workspace.tsx` line 425):
```tsx
<p className="model-context"><StatusTag tone={dirty ? "advisory" : "inert"}>{revision ? 'Read-only model version' : dirty ? 'Unsaved local edits' : 'Draft · saved'}</StatusTag></p>
```
The chip follows that tag. Overview rows: `OverviewRecords.tsx` lines 72-75 (button, then `StatusTag` at row end). Record details dialogs use `<dl className="hf-record-details">` (Workspace.tsx line 428) - add "Saved by" / "Submitted by" / "Changed by", "Confirmed by", "Proposal ID" rows there. The attribution comes from a read (never from parsed names), added to `ui/src/api.ts` as an arrow member like line 66:
```ts
approach = async (sid: string, signal?: AbortSignal) => (await this.request<ApproachState2>(`/studies/${sid}/approach`, undefined, 'GET', signal)).data;
```

---

### `deployment/tests/agent_ui_fixture.py` (runner child, batch)

**Analog:** `deployment/tests/foundry_ui_fixture.py` (111 lines) - copy whole structure: `GROUP_SPECS`, `browser_environment(scope)`, `browser_config(scope, group)`, fail-closed `report_passed` (lines 52-56), `run(*, group)` (lines 70-111: reviewed interpreter check, vite build into scope, JSON Playwright config written into scope, report and `tests.json` evidence):
```python
def report_passed(returncode, stats, files, forbidden, group='foundry-nav'):
    """Fail closed: no zero selection, skip, flake, unexpected result or foreign/missing spec."""
    return (returncode == 0 and stats.get('expected', 0) > 0 and not forbidden
            and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky'))
            and bool(files) and set(files) == set(GROUP_SPECS[group]))
```
UI-SPEC says the `agent-ui` group runs "on the in-browser API double", so prefer this in-browser-double runner. The alternative (serving the real application with a fake modeling client in scope) is `deployment/tests/units_ui_fixture.py` lines 328-345 (`ThreadingHTTPServer`, `Store(guard.scoped_path(...))`, `create_app(store,auth,models.client)`); use it only if confirm semantics must be proven against the real routes in the browser.

### `ui/tests/agent-fixtures.ts` (in-browser API double)

**Analog:** `ui/tests/foundry-fixtures.ts`. Copy: scoped-build guard (lines 10-21), `startFixture`/`guardOrigin`/`stopFixture` (lines 23-41), the `harness(page)` router with `state.writes` and `state.unknown` (lines 57-148) and `login(page, hash, name)` (lines 149-155):
```ts
await page.route('**/api/1/**', async route => {
  if (new URL(route.request().url()).origin !== origin) return route.abort('blockedbyclient');
  const request = route.request(), path = new URL(request.url()).pathname.slice('/api/1'.length), method = request.method();
  const ok = (data: unknown) => route.fulfill({ json: { schema_version: '1', data, next_cursor: null } });
  ...
  state.unknown.push(method + ' ' + path);
  return route.fulfill({ status: 500, json: { error: { message: 'Unexpected isolated request', code: 'internal_error', fields: [], outcome: 'unchanged' } } });
});
```
Add the proposals, confirm, withdraw and attribution routes; a second user (`login(page, hash, 'writer')`) proves "Only {user} can confirm".

### `ui/tests/agent-attribution.spec.ts`, `ui/tests/agent-proposals.spec.ts` (browser)

**Analog:** `ui/tests/record-labels.spec.ts` lines 1-8 and 34:
```ts
test.skip(!process.env.HYPRN_MVP_NAV_BUILD, 'Isolated fixture build required');
test.beforeAll(startFixture); test.beforeEach(async ({page}) => { await guardOrigin(page); await page.emulateMedia({reducedMotion:'reduce'}); }); test.afterAll(stopFixture);
...
expect(state.writes).toEqual([]);expect(state.unknown).toEqual([]);
```
Both themes: loop `for(const colorScheme of ['light','dark'] as const){await page.emulateMedia({colorScheme}); ...}` (line 28); screenshots go under `process.env.HYPRN_MVP_UI_EVIDENCE_ROOT` (scoped, outside the repository). Genuine 200 % zoom (not a 720 px viewport): `ui/tests/foundry-zoom.spec.ts` lines 8-66 (extension + `chrome.tabs.setZoom(tab.id, 2)`) or the compact form in `ui/tests/unit-model-reading.spec.ts` lines 138-170. Note: the `test.skip` guard is a skip, but the runner's `report_passed` fails the group on any skip, so a missing build still fails.

---

### `agent_tools/api_client.py` (in-process client, request-response)

**Analogs:**
- Header discipline - `test_study_archive.py` lines 43-46 (Origin on every request, `X-CSRF-Token` on mutations, cookie from the session) and the browser client `ui/src/api.ts` lines 165-178:
```ts
const result = await fetch('/api/1' + path, { method, credentials: 'same-origin', signal: ...,
  headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrf },
  body: body === undefined ? undefined : JSON.stringify(body) });
...
if (!result.ok) { ... throw new ApiError(value.error ?? {...}) }
```
- Injection seam - `application/src/hyprn_mvp_app/modeling.py` lines 19-24 (`ModelingClient(base_url, key, *, transport=None)`): the registry receives the client; it never imports `api` (D-10).
- `base_url` equals the configured origin so `api.py` line 117 Host check passes; point the transport at the FastAPI app, not the outer dispatcher (RESEARCH Pattern 2).

### `agent_tools/spec.py`, `registry.py` (catalogue, transform)

**Partial analogs:** `generate_contract.py` `OPERATION_NOTES` (lines 262-300) is a dict keyed by `(path, method)` with prose per operation - the same key shape suits `api_operations` and the tool <-> OpenAPI parity test. Input validation uses Draft 2020-12 like `contracts.py` `validate` (line 120) and `test_study_archive.py` line 364 (`Draft202012Validator(..., format_checker=FormatChecker())`). Digests of arguments use `contracts.canonical`/`digest` (lines 36, 56) - called, never edited (attested file).

### `agent_tools/projections.py` (transform)

**Partial analogs:** cursor/limit validation in `api.py` `page()` (lines 169-177) and the approach cursor parser (lines 236-260: bounded length, strict JSON, schema validation). Never echo submitted input: `api.py` `request_diagnostics` docstring (line 88). Unavailable outputs stay `null` with a reason: fixture shape in `ui/tests/foundry-fixtures.ts` line 188 (`value: null, availability: 'unavailable', reason: 'producer_failed'`).

### `agent_tools/playbook.py` + `docs/agents/playbook.md` (generated doc)

**Analog:** `ui/design_tokens.py` lines 51-56 (generated header) and 69-88 (`--check` exits 1 when stale):
```python
if args.check:
    current = args.out.read_text(encoding='utf-8') if args.out.exists() else None
    if current != css:
        print('stale: ' + str(args.out) + ' does not match tokens.json; run python3 ui/design_tokens.py')
        return 1
```
Section ids already exist in `docs/agents/playbook.md` headings (`[workflow]`, `[field_map]`, `[style]`, `[numerical_models]`, `[platform_limits]`, `[conclusion]`, `[checklist]`) - keep them as the constant names.

### `agent_surface/jsonrpc.py` (strict parser, transform)

**Analog (exact for strict JSON):** `api.py` lines 126-148:
```python
def pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError("Duplicate key")
        result[key]=value
    return result
def bound(v,depth=0):
    if depth>32:raise ValueError("Depth")
    ...
value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
bound(value);canonical(value)
```
Because `agent_surface` may import only `agent_runtime` (D-10), copy the logic (or expose it from `agent_runtime`), do not import `api`.

### `agent_surface/mcp_server.py` (raw ASGI controller)

**Analogs:** refusal ordering and envelope from `api.py` middleware (lines 113-153) and `error_response` (lines 97-100); a Starlette subclass with hardened headers in `ui.py` lines 5-14; the body bound loop (lines 122-125) with 256 KB instead of 2 MiB:
```python
raw=bytearray()
async for part in request.stream():
    raw.extend(part)
    if len(raw)>2*1024*1024:raise DomainError("limit_exceeded",413)
```
Security headers on every response: line 152 (`Cache-Control: no-store`, `X-Content-Type-Options`, `Referrer-Policy`). JSON-RPC lifecycle itself has no analog (see below).

### `application/tests/mcp_client.py`, `test_mcp_server.py` (test)

**Analog:** `test_study_archive.py` fixture, but build the composed app (`compose(create_app(...), mcp_app)`) and post with `TestClient(composed, base_url=LOOPBACK_ORIGIN)`; assert `/mcp` absent from `create_app(None,None,None).openapi()["paths"]`. Lost-response and fault injection: `application/tests/test_api.py` `FaultTransport` lines 22-34.

### `agent_runtime/runtime.py`, `journal.py`, `proposals.py` (service, event-driven + CRUD)

**Analog:** `store.py` `command()` (lines 372-397) - receipt keyed by `(scope, category, command_id)`, payload digest, idempotent replay, rejected outcome recorded:
```python
old=self.command_receipt(db,scope,category,command)
if old:
    if old["payload_digest"]!=digest(dict(major="1",scope=scope,category=category,payload=payload)):raise DomainError("command_payload_conflict")
    ...
    return old["result"]
db.execute("SAVEPOINT domain_write")
try:
    result=operation(db)
    state=receipt_state
except DomainError as exc:
    db.execute("ROLLBACK TO domain_write")
    error=exc;result=None;state="rejected"
```
Journal row written **before** the API call (intended), outcome after; reconciliation reads `GET /api/1/studies/{study_id}/commands/{command_id}?category=` (`api.py` lines 458-476; approach categories at lines 461-463 require exactly one `category` query parameter). Uncertain outcomes are reconciled by lookup, never resent - same rule as `ui/src/api.ts` `mutate()` lines 187-200 (`pending_remote` -> "Command outcome is uncertain").

---

### `ui/src/AssistantProposals.tsx` (screen, request-response)

**Analogs:**
- Read state machine and per-host retry: `ui/src/OverviewRecords.tsx` lines 10-30 (`ReadState`, actor fence `actor === api.actor`, `retry`).
- Guarded read + shared access-loss seam: `ui/src/EvidenceIndex.tsx` lines 143-158:
```tsx
useAccessLoss(api, studyId, change => { generation.current++; setState({ owners: [], unlisted: [], lost: change.kind === 'access-lost' }); });
useEffect(() => {
  const token = ++generation.current, read = api.fence({ studyId }), run = limiter(2);
  const live = () => token === generation.current && read.valid();
  const failure = async (error: unknown) => { const outcome = await api.readFailed(error, read); return outcome === 'access-lost' || outcome === 'stale' ? null : outcome === 'transient' ? accessUnverifiedText : readText(error); };
```
- `accessLostText`, `accessUnverifiedText`: `ui/src/api.ts` lines 23-24 (reuse verbatim per UI-SPEC).
- Segmented tabs "Pending · History": Home's tabs in `Workspace.tsx` lines 407-412 (`role="tabpanel"` with `hidden`).
- Confirm/withdraw use `api.mutate`-style calls with the browser session only (`ui/src/api.ts` lines 187-200).

### `ui/src/ChangePreview.tsx` -> exported `ModelChangeTable` (component, render)

**Analog:** itself, `differences(before, after)` (lines 16-56) and `DifferenceTable` (lines 57-59):
```tsx
function DifferenceTable({ before, after }: { before: ModelDraftRead4; after: ModelDraftRead4 }) {
  return <><div className="table-scroll" tabIndex={0}><DataTable className="change-table"><thead><tr><th>Change</th><th>Before</th><th>After</th></tr></thead><tbody>{differences(before, after).map(row => ...)}</tbody></DataTable></div><UnreadableAssumptions models={[before, after]} /></>;
}
```
Extract with no behaviour change (rename/export only); `ChangePreview` keeps calling it at lines 95 and 98. Before/After words "None" for absent values come from line 18. The `HumanChanges` table (lines 111-114, "Changed field · Before · After") is the analog for the C2 study-description diff.

### `ui/src/ApproachPanel.tsx` -> exported `ApproachChanges`

**Analog:** itself line 141:
```tsx
{state.preview && state.local && controller.dirty && <Panel title="Approach changes"><ul>{state.preview.changes.map((change,i) => <li key={i}>{change.description}</li>)}</ul><p>These edits change the explanation and its references. They do not modify or execute the referenced models.</p></Panel>}
```
Evidence previews reuse `EvidenceRecordBody` (`ui/src/EvidenceView.tsx` line 12, `compact` prop).

### `ui/src/workspaceModel.ts` (link model) - modify

**Analog:** itself lines 70-113. Add `'proposals'` to `WorkspaceView` (line 70) and `views` (line 83); add `proposal` to the UUID-validated key loop (lines 92-96) and `workspaceHash` (line 110); copy the conflicting-context rule (line 98) so `proposal` is valid only with `view=proposals`:
```ts
if ((link.approach && link.view !== 'approach') || (link.view === 'approach' && (link.model || link.revision || link.configuration || link.run))) throw new Error('This approach link has conflicting resource context.');
```

### `ui/src/Workspace.tsx` (shell) - modify (shared with Phase 4)

**Analog:** itself. Study heading row (line 416) `<div className="study-heading"><h1>{study.name}</h1></div>` gets the quiet entry button; study tabs (line 417) map `view === 'approach' ? 'overview' : view` - for `proposals` pass no current tab; breadcrumb (line 397) adds `/ Assistant proposals`; view branch copies the approach branch (line 423) and navigation goes through `navigate(...)` (line 201) so the editor guard applies.

---

### `editions/local/src/hyprn_mvp_local/study_kit.py`, `study.py` (file-I/O)

**Analogs (current tree; Phase 2's `paths.py` becomes the primary one once it exists):**
- Off-cloud and symlink refusal, private modes: `store.py` `Store.__init__` lines 180-188:
```python
original=Path(path).absolute()
self.path = original.resolve()
if "CloudStorage" in self.path.parts or any(p.is_symlink() for p in (original, *original.parents) if p != Path("/tmp")):
    raise ValueError("Application storage must be off-cloud")
self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
fd=os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
```
  (Phase 2 plan line 105 lists the full synced-folder set; reuse Phase 2's checker, do not re-implement it.)
- Location resolution and normalized-absolute refusal: `deployment/local_paths.py` `absolute` (lines 135-141) and `located` (lines 158-170) - flag -> `HYPRN_MVP_STUDIES_DIR` -> `studies_root` -> per-OS default -> ask (PD-3.2).
- Token-free generated files: hygiene pattern `deployment/tests/test_hygiene_guard.py` line 47 (`'hyprn' + '_mvp_mcp_' + '[A-Za-z0-9_-]{16,}'`) - tests assemble token-shaped data at run time the same way.

### `editions/local/src/hyprn_mvp_local/mcp_tokens.py`, `mcp_relay.py`

**Analogs:**
- Subcommand argparse + JSON result printing: `deployment/application_runtime.py` `main()` lines 318-331 (`choices=[...]`, `parser.error(...)`, `print(json.dumps(result,indent=2))`). Phase 2's `output.py` envelope (`{operation_id, operation, installation_id, status, reason_code, observed, evidence_refs}`, 02-PLAN line 148) supersedes the print once it exists.
- Port-owner check: `deployment/application_runtime.py` `guard` (lines 41-43) + `check` port binding (line 87):
```python
def guard(info):
    if info["Name"]!="/"+NAME or info["Config"]["Labels"].get("org.hyprn-mvp.migration.owner")!=OWNER:
        raise ValueError("Application resource is not owned")
...
if h["PortBindings"]!={"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":str(PORT)}]}:raise ValueError("Unexpected public bind")
```
  The analog uses the `docker` CLI (`inspect`, lines 35-40); the relay must read the same fields through the Docker Engine API on the configured `docker.endpoint` (RESEARCH Pattern 5, Pitfall 11) - same label and binding checks, different transport.
- Credential store: only through Phase 2 `credentials.py` (`store`/`read`/`delete`/`list`, account `<installation_id>:<name>`, secrets on standard input; 02-PLAN lines 527-529).

### `editions/local/tests/*.py` (test)

**Analogs:** effect refusal `deployment/tests/test_deployment_hardening.py` lines 77-83 (`refuse_effects` monkeypatches `subprocess.Popen`/`run`); command recording with synthetic results `deployment/tests/test_attestation.py` lines 223-232. Use a recorder that stores every argument vector and assert no element contains the token. TOML read-back with `tomllib` (no analog; RESEARCH Code Examples).

---

## Factorization tasks (3.3a–3.3d) and the layer table of 3.4

Added for the product owner's factorization schedule (D-19, `.planning/codebase/FACTORIZATION.md`). Line numbers are those of the tree after task 3.1; re-locate them by symbol name.

### `application/src/hyprn_mvp_app/routes/<owner>.py` and the edge-helper module (3.3a) - new; `api.py` - modify

**Analog:** `api.py` itself. `create_app` (line 121) constructs the owners and defines every route inline in registration order, from the session routes (215) to the artifact route (534); `modeling_route` (399) registers four routes through `app.post(path)(route)` after setting `route.__name__`, which fixes their operation ids; the shared helpers are module functions (`valid_id` 78, `request_diagnostics` 88, `agent_boundary` 100, `delegated_scope` 111, `error_response` 116) or closures of `create_app` (`current_session`, `actor`, `response`, `page`, `remote_response`, 193–213). FastAPI derives each operation id from the endpoint function name and path, and `application/generate_contract.py` writes the paths in route order with `json.dumps(spec, indent=2)` (no key sorting), so the move keeps function names and registration order; where two owners' routes interleave today (configuration preview and commit, then the modified-run seed and result sources, then the configuration list and read), one router keeps them in that order. Byte freshness of both generated files: `application/tests/test_computational_api.py` `test_generated_routes_schemas_capabilities_and_types_match`. Boundary rows follow `AGENT_REACH` and `test_agent_policy_reaches_only_the_registry_and_contracts_and_only_api_imports_it` in `application/tests/test_module_boundaries.py`; the middleware's `request._body` entry of `PRIVATE_ALLOWLIST` names `api.py`, so the middleware stays there.

### `ui/src/views/registry.ts`, `ui/src/views/<view>.tsx`, `ui/src/ModelController.ts` (3.3b) - new; `Workspace.tsx`, `workspaceModel.ts` - modify

**Analogs:** `ui/src/workspaceModel.ts`: the closed view type and list (`WorkspaceView` line 70, `views` 83), `parseWorkspaceLink` (85: the `#v=1` envelope, then the per-view rules for `approach` and `case`), `workspaceHash` (108), the guard seam `GuardEntry` (13) and `useGuardSlot` (57), which the registry's `guard?` reuses. `ui/src/ApproachController.tsx`: the controller pattern for `ModelController` (class with state, `subscribe` and `getSnapshot`, line 24; `useApproachController` over `useSyncExternalStore`, line 181). The save sequence to move is the "Save model version" button of the model heading row in `ui/src/Workspace.tsx` (line 427). Source guards that name `src/Workspace.tsx` or `src/workspaceModel.ts` are in `ui/check_ui_contract.py` (lines 19, 103–104, 153, 170–182, 224–227, 270–294 and 328); a guard follows its text to the view module.

### One run-row read and `History.status` (3.3c): `history.py`, `execution.py`, `approach.py`, `result_bindings.py`, `store.py`

**Analogs:** `History.list` (`history.py` line 246: a `json_extract` projection of the public state, every statement exhausted before Python work, no payload loaded) is the model for `History.status`; `History.run_row` (274) is the authorized single-run read. The six `run_associations … JOIN outbox` statements are `execution.py` 93, 128, 135, 183 and `history.py` 258, 281; the direct run-association queries are `approach.py` 470 (usage union with SQL pagination) and `result_bindings.py` 92 and 105 (position paging). One-owner statement test: `test_model_association_reads_have_one_owner` with `ASSOCIATION_STATEMENTS` (`application/tests/test_module_boundaries.py` 635). Additive column migration: the `PRAGMA table_info` and `ALTER TABLE` step of `Store.__init__` (`store.py` 252–254). Fixtures: `integration/tests/test_submission.py` (`submission`, `accepted`) and `application/tests/test_history.py` (`recording`, `test_history_list_and_detail_agree_on_preclaim_state`).

### Receipt recovery (3.3d): `store.py`, `routes/commands.py`, `ui/src/api.ts`

**Analogs:** the rules that move to the server are `ui/src/api.ts` `reconcile` (line 209) and `retryOriginal` (227), with `mutate` (188) for the pending decision; the server-side states and next steps are architecture §6.6. `Store.receipt` (`store.py` 564) and `_agent_pre_study_outcome` (443) give the scoped 404; the receipt routes are `api.py` 496–518 before 3.3a (`approaches.receipt` validated as `ApproachReceiptRead2`; `coordinator.reconcile(…, receipt_view=True)` first for `model`). The spec to update is `ui/tests/command-recovery.spec.ts` (group `ported-isolated`); the API double's receipt answer is `ui/tests/foundry-fixtures.ts` line 85. Lost-response fixtures: `application/tests/test_api.py` `FaultTransport`.

### `LAYERS` in `application/tests/test_module_boundaries.py` and the §7 table (3.4)

**Analogs:** `project_imports` and `reachable` already follow function-local imports; `AGENT_REACH` is the row shape per package; `test_retained_run_owner_never_depends_on_its_consumers` (498) and `test_approach_never_depends_on_configuration_workflow` (526) are direction checks the table generalizes. Observed edges outside today's §7 diagram: `modeling → store`; `store → readiness` (function-local, in `publish_execution_observation` and `execution_observation`); `configuration → {modeling, readiness, scientific_configuration}`; `execution → readiness`; `modified_runs → readiness`; `dispatcher → computational_export`. `readiness` imports only `contracts`.

## Shared Patterns

### Error envelope and refusals
**Source:** `application/src/hyprn_mvp_app/api.py` lines 97-100 (`error_response`), 150-151, 155-162 (exception handlers).
**Apply to:** agent routes, `/mcp` HTTP-level refusals (401/403/405/413/503), API client error decoding.
```python
return JSONResponse(status_code=error.status,content={"error":dict(code=error.code,message=error.code.replace("_"," "),
    request_id=getattr(request.state,"request_id",uid()),command_id=getattr(request.state,"command_id",None),
    resource_id=None,current_revision=error.current_revision,fields=error.fields,outcome=error.outcome)})
```
`DomainError(code, status, fields=..., outcome=...)` comes from `contracts.py` line 83; scoped 404 is always `resource_not_found` (never disclose another study).

### Authorization and scoped 404
**Source:** `store.py` `authorize` lines 243-247; every route calls it inside `store.connection()` (e.g. `api.py` line 227).
**Apply to:** every agent-runtime read and command; the attribution read; proposal reads.

### Commands, receipts and idempotency
**Source:** `store.py` `command()` lines 372-397, `receipt()` lines 351-359, `api.py` receipt routes lines 458-480.
**Apply to:** journal, proposals (stored `command_id` reused on confirm), `two_phase.py`, reconciliation.

### Session, Origin and CSRF
**Source:** `auth.py` lines 72-80; `api.py` lines 118-121; tests `test_study_archive.py` lines 212-221.
**Apply to:** in-process API client (agent session), confirm and withdraw routes (human session only), UI calls.

### Single-writer store transactions
**Source:** `store.py` `connection(write=True)` lines 198-210 (`BEGIN IMMEDIATE`).
**Apply to:** all agent tables; never hold a write transaction across an awaited API call or `wait_for_runs` sleep.

### Scoped scratch stores in tests
**Source:** `application/tests/conftest.py` (lines 1-12, `LOOPBACK_ORIGIN`); `tmp_path` stores in `test_study_archive.py` line 52; browser scope guards in `ui/tests/foundry-fixtures.ts` lines 10-19 and `deployment/tests/foundry_ui_fixture.py` lines 70-74.
**Apply to:** every new test; no user installation, no fixed host path.

### UI reads with access loss
**Source:** `ui/src/accessLoss.ts` (14 lines), `ui/src/api.ts` lines 116-160 (`fence`, `confirmAccess`, `readFailed`), `ui/src/EvidenceIndex.tsx` lines 143-158.
**Apply to:** `AssistantProposals.tsx`, attribution reads in record views.

### Design-system-only screens
**Source:** `ui/src/design/index.ts` exports; `ui/check_design_system.py`; `ui/design_tokens.py --check`; `ui/design_smoke.mjs`.
**Apply to:** every UI file; no inline styles, tokens only, status is shape + word + colour.

### Code style
Older modules are dense (`auth.py`, `store.py`, `api.py`: one-line `def`s, no spaces around `=`); newer modules and tests use standard spacing (`ui.py`, `deployment/local_paths.py`, `test_study_archive.py`). Edits to existing dense files keep their local style; new modules (`agent_tools/`, `agent_runtime/`, `agent_surface/`, `hyprn_mvp_local/`) follow the newer standard-spacing style. Comments and test names state the invariant, not a task id (AGENTS.md) - do not copy the "P4-S6a", "14-B3", "14-C3" prefixes found in older comments.

## No Analog Found

Files or behaviours with no close match (planner should use RESEARCH.md patterns instead):

| File / behaviour | Role | Data flow | Reason |
|---|---|---|---|
| `agent_surface/mcp_server.py` JSON-RPC lifecycle (initialize, version negotiation, `Mcp-Session-Id`, `server/discover` -> -32601, tools/list, tools/call, resources, prompts) | controller | request-response | No JSON-RPC or MCP code exists; use RESEARCH Pattern 4 and "Code Examples" |
| Outer ASGI dispatcher in front of FastAPI | composition | request-response | No raw ASGI composition exists (only `app.mount` in `ui.py`); RESEARCH Pattern 3 sketch |
| `APIRouter` in a subpackage + `include_router` | route | request-response | All routes are inline in `create_app`; first router in the codebase |
| `async def` route awaiting the in-process client (confirm) | route | request-response | Every route handler is sync `def` today; only the middleware and exception handlers are async |
| Application subpackages (`agent_tools/`, `agent_runtime/`, `agent_surface/`, `catalogue/`) | package layout | - | Packages are flat; the boundary test asserts flat relative imports (`test_module_boundaries.py` lines 194-197) and must be changed first |
| `agent_tools/spec.py` `ToolSpec`, confirmation classes, annotations, `REGISTRY_VERSION` hashing | service | transform | No registry or tool abstraction exists; RESEARCH "Recommended project structure" and tooling spec §4 |
| `agent_tools/instructions.py` (under 2,000 characters, first 512 self-contained) | config | - | No comparable artefact; unit test of lengths only |
| Truncation notes and `untrusted_content` wrapping in projections | utility | transform | No precedent; tooling spec §5 |
| `mcp_relay.py` stdio framing (newline-delimited JSON-RPC, stdout only MCP, exit on stdin close) | utility | streaming | No stdio protocol code; RESEARCH "Relay core loop" |
| Docker Engine API over the configured Unix socket (stdlib `http.client`) | utility | request-response | Current managers use the `docker` CLI (`application_runtime.py` lines 33-40); fields to check are the same |
| `.codex/config.toml` generation and `tomllib` read-back | file-I/O | transform | No TOML in the repository; RESEARCH "Codex project configuration without a TOML library" |
| `wait_for_runs` backoff with `stalled` | service | polling | Nearest is `OverviewRecords.tsx` `RecentRunOutcome` (5 s / 10 s timers) in the UI; server-side bounded wait has no analog |

## Metadata

**Analog search scope:** `application/src/hyprn_mvp_app/`, `application/tests/`, `application/generate_contract.py`, `integration/src/hyprn_mvp_integration/launcher.py`, `deployment/` (runner, managers, path policy, fixtures, guards), `ui/src/`, `ui/src/design/`, `ui/tests/`, `ui/*.py|mjs`, `design-system/`, `docs/agents/`, `editions/local/`, `.planning/phases/02-local-edition/02-PLAN.md` (module names only).
**Files scanned:** about 60 (read or grepped).
**Pattern extraction date:** 2026-10-13.
**Validity:** line numbers hold until Phase 1 task 1.4 renames the application package and the contract; re-locate by symbol name after that.
