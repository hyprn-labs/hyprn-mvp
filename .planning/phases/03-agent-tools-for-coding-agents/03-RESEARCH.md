# Phase 3: Agent tools for coding agents - Research

> Superseded in part by ADR-0002 (docs/adr/0002-agent-write-rights.md): proposals, confirmation classes, the proposals page and envelope grants are retired; sections on them are historical. 03-CONTEXT.md and 03-PLAN.md govern.

**Researched:** 2026-10-13
**Domain:** Agent principal and delegation, in-process tool registry over the public API, hand-written MCP server and stdio relay, proposals confirmed in the UI, local study folders for Codex and Claude Code, agent evaluation
**Confidence:** MEDIUM overall (codebase facts HIGH; MCP specification facts MEDIUM, cited; desktop-client behaviour LOW to MEDIUM until verified live)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Locked by `docs/specs/agents.md` and `docs/agents/tooling-spec.md`:

- **D-01** Agents are users of HYPRN MVP, not its developers. They reach HYPRN MVP only through the curated tool registry, which calls `/api/1` in process (ASGI transport into the same application) with a delegated agent session carrying the session cookie, the exact `Origin` and the cross-site request token. No raw API passthrough, store, modeling, AiiDA or executor access.
- **D-02** The agent is its own principal (actor kind `agent`, one per user, surface and installation) acting for one user under a delegation. Effective authority is re-checked on every call: delegation live, study in scope, effect allowed, the user's current role, the role ceiling. Receipts carry the agent actor; records show "{agent} for {user}"; confirmed proposals also record the confirming human. Access loss takes effect on the next call.
- **D-03** Attribution comes first in this phase. Tokens minted before the authoring stage's review are read-only; writer-capable tokens are minted only after that review passes.
- **D-04** Confirmation classes: C0 executes immediately (reads, drafts, validation, notes, issue reports); C1 returns a batchable proposal (model and approach versions, evidence, configuration save, run submission, conclusion); C2 is confirmed individually (study context change, approach draft restore). Only the delegating user confirms, in the HYPRN MVP UI, with a browser session; on confirmation HYPRN MVP recomputes the preview and executes the stored request with its stored command id; a changed candidate makes the proposal stale and it never executes. Proposals expire after 24 hours and are invalidated on access loss, Stop or the kill switch. Client approval prompts are never confirmations.
- **D-05** `/mcp`: Streamable HTTP with JSON responses (no server-sent events), written on the existing pinned dependencies; loopback only; any `Origin` header → 403; `Host` must equal the configured origin; bearer tool token required, cookies refused; tool tokens refused on `/api/1`; request body at most 256 KB; `Mcp-Session-Id` handling; one `agent_actions` row per call with argument digests, not raw bodies.
- **D-06** Tool token: 256-bit, prefixed `hyprn_mvp_mcp_`, stored hashed, audience `/mcp`, one study and one delegation, 8-hour default lifetime (24 hours maximum), shown once, renewed manually, minted only by the CLI, never in files, process arguments or logs. Stored through the Phase 2 credential-store adapter.
- **D-07** The client connection is the stdio relay `./hyprn-mvp mcp relay --study <id>`, which reads the token from the credential store and verifies that this installation's application container publishes the configured loopback port before sending it. The HTTP configuration with `HYPRN_MVP_MCP_TOKEN` is documented as the alternative.
- **D-08** The study folder is outside the source checkout and outside synced folders and holds only `AGENTS.md` (boundary and playbook pointer), `.mcp.json`, `.codex/config.toml`, client deny rules and `inputs/`. Scientific records live only in HYPRN MVP. A synced, symlinked or non-empty existing folder is refused.
- **D-09** Local tokens are study-scoped. `study_id` is never a tool argument. Local agents never create, archive or restore studies, manage memberships, mint tokens or record scientific reviews. (Superseded by ADR-0003 and the current D-09 in 03-CONTEXT: agents may create studies and, once the record exists, record agent-labelled reviews; archive, restore and access management stay human-only.)
- **D-10** Module boundaries: `hyprn_mvp_app.agent_tools` → `contracts` (plus the injected API client) only; `hyprn_mvp_app.agent_surface` → `agent_runtime` only; `agent_runtime` → `agent_tools`, `auth` and its own tables. None is imported by execution integration, so the attested execution source set is unchanged (a test asserts it).
- **D-11** Limits and controls per agents spec §3.4: 1 MCP session per token; 60 API calls per turn and 600 per session; tool results about 6,000 tokens with explicit truncation notes; at most 20 runs per proposal, 10 queued per actor, 60 per session; the kill switch `agent.enabled` (`HYPRN_MVP_AGENT_ENABLED`) refuses tokens and sessions, invalidates pending proposals and refuses MCP calls; append-only action journal.
- **D-12** Outputs: compact projections within their caps, units always present, unavailable never zero, ids paired with names, outcome facets separate, text written by others wrapped as `untrusted_content`; pagination `limit` default 10, maximum 25, opaque cursor.
- **D-13** Idempotency: command ids are journaled before each API call; duplicates return the stored outcome; lost responses reconcile through receipts; an uncertain run launch is never resubmitted.
- **D-14** Until the typed conclusion record exists, `record_conclusion` writes a tool-rendered "Study conclusion" evidence note, revised in place as new versions; structured claims stay in the journal.
- **D-15** Each local stage reaches an installation only through a fresh `./hyprn-mvp setup` after its reviews (there is no update path in this milestone); development and evaluation use scratch installations.
- **D-16** Evaluation per agents spec §10: scripted (no model) G2, G3 and G5 run on every commit; live scenarios are started manually because they cost money; a surface is supported only if it passes the reference criteria; human acceptance is recorded separately.

### Open product decisions (recommended defaults, from CONTEXT.md)

- **PD-3.1 Playbook location.** The agents spec calls `docs/agents/playbook.md` the playbook; the tooling spec ships it as sections in `hyprn_mvp_app/agent_tools/playbook/`. Default: the packaged sections are the single source (they version with the API and are hashed into the registry version); `docs/agents/playbook.md` is generated from them by a tool, and the `docs` check fails when it is stale. Both specs are updated to say so. Alternative: the document is the source and a build step splits it into sections.
- **PD-3.2 Study-folder location.** Default: adopt the tooling spec's chain — `./hyprn-mvp study new "<name>" --folder DIR`, then `HYPRN_MVP_STUDIES_DIR` (root under which `<study-slug>/` is created), then the installation configuration field `studies_root`, then the default `~/hyprn-mvp-studies`, then ask. Inside the checkout or a synced folder is refused.
- **PD-3.3 Generated client entries.** Default: stdio relay entries — `.mcp.json` `{"mcpServers": {"hyprn-mvp": {"type": "stdio", "command": "<installed hyprn-mvp command>", "args": ["mcp", "relay", "--study", "<study id>"], "timeout": 180000}}}` and `.codex/config.toml` `[mcp_servers.hyprn-mvp]` with the same command and arguments, `tool_timeout_sec = 180`, `default_tools_approval_mode = "writes"`. The CLI fills in the resolved command location in the generated user files; nothing in the repository holds a resolved path. The HTTP alternative is documented, never generated.
- **PD-3.4 Host without a credential store.** Default (same as Phase 2 PD-2.2): `study new` and `mcp token renew` refuse with an explanation; no file fallback.
- **PD-3.5 Token listing and revocation.** Default: `./hyprn-mvp mcp token list|renew|revoke <study>` in this phase; revocation through the CLI is enough for the first release. The UI token panel is deferred, so UI-04 stays `partial` (the Assistant proposals page and the attribution chip are delivered). Alternative: add list and revoke to the Assistant proposals page in stage 3.
- **PD-3.6 Requirement status.** Default: VER-03 stays `delivered` — agent clients reuse preview → digest → commit and command receipts with no separate mechanism, and the registry hides the protocol from the agent. AGENT-01 becomes `delivered` only after stage 4, the evaluation and Phase 5 qualification; AGENT-05 and AGENT-06 after stage 3 and its review.
- **PD-3.7 G2 fixture.** Default: the two-section pressure-loss screening fixture (110 kPa at 2 L/s, 121 kPa at 2.2 L/s, 120 kPa criterion), with a met and a violated criterion and a deliberate downstream-failure variant.
- **PD-3.8 G1 fuel-study fixture content.** Default: brief text and short locator extracts only; cite the paper, never redistribute it.
- **PD-3.9 Client and protocol verifications** (tooling spec §11.7 items 5–8: Codex prompts and resources, loopback from its sandbox, relay treatment; most reliable Claude Code deny mechanism and stdio timeout; `structuredContent` and annotations; credential stores per OS). Default: verify each in the first task that needs it, record the result in `docs/agents/tooling-spec.md` §11.7, and negotiate the MCP protocol version from the versions both clients send.

### Claude's Discretion (Planner's discretion, from CONTEXT.md)

- Task granularity within each stage (one task per fresh executor), test file layout, and the order of read tools within the read-only stage.
- Projection shapes inside the documented caps, and fixture design for golden projections and the secret-fuzz test.
- UI layout of the Assistant proposals page and the attribution chip, within the design system and `docs/specs/ui-target.md` §4.4.

### Deferred Ideas (OUT OF SCOPE)

- UI list and revoke of tool tokens (PD-3.5 default).
- Cloud managed agents, the provider bridge and the assistant panel.
- Envelope grants (after G1 passes reliably on a surface).
- Document tools for agents (after Phase 4), research helpers, public web search.
- Run cancellation tool (when run cancellation exists); model import and export tools.
- Typed records as product gaps close: conclusion record, typed inherited provenance, status channel, infeasible outcome, sweeps, currency units.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (verbatim, `docs/specs/requirements.md`) | Research support |
|----|-------------|------------------|
| AGENT-01 | A desktop coding agent (Codex or Claude Code) can work on one study through the local MCP tool server, using the same scoped typed operations as the UI, with writes confirmed in the HYPRN MVP UI. | In-process client (Pattern 2), `/mcp` outside the browser middleware (Pattern 3), initialize-based MCP lifecycle (Pattern 4), stdio relay (Pattern 5), study-folder kit and client facts (section "Client and protocol facts"), tasks 3.4–3.10 and 3.19–3.22 |
| AGENT-05 | An agent is its own principal acting for one user under a delegation; effective authority is the intersection of delegation, the user's current access and a role ceiling, and every record shows "{agent} for {user}". | Pitfalls 2–6 (sessions table, `authorize`, `list_studies`, pre-study commands, attribution read), Pattern 1, tasks 3.1–3.3 |
| AGENT-06 | Agent writes that create immutable records, consume compute or change shared context are proposals confirmed only by the delegating user in the HYPRN MVP UI; stale proposals never execute. | Pattern 6 (confirmation executes as the agent with the stored command id), tasks 3.12–3.13, 3.18 |
| AGENT-07 | Agent use is bounded and controllable: limits and budgets, installation, user, session and token kill switches, an append-only action journal, and transcript retention rules. | Decision ND-12 (kill switch), runtime limits (task 3.6), journal (tasks 3.6, 3.11) |
| AGENT-08 | Every supported agent surface passes the evaluation scenarios and parity gate before release, and changes to rules, tools, playbook or providers are re-evaluated. | Validation Architecture (`agent-eval`, scripted vs live vs human), tasks 3.10, 3.18, 3.22 |
| UI-04 | The UI offers an Assistant proposals page, attribution chips on agent-written records, and listing and revocation of local tool tokens. | Tasks 3.3 and 3.13; token UI deferred by PD-3.5 (open question OQ-1), so UI-04 ends `partial` |
</phase_requirements>

## Project Constraints (from AGENTS.md)

`AGENTS.md` is the binding instruction file (`.planning/config.json` sets `claude_md_path` to it). Directives that bind this phase:

- **Scientific invariants:** finite real scalars; explicit inputs with units and provenance; empty differs from zero; exact pins; no hidden defaults, implicit conversions or randomness; an unavailable output is null with a reason, never zero; execution, convergence, termination, feasibility, completeness, applicability and criterion outcome stay separate; saved versions and runs never change.
- **Execution and security:** candidate code runs only in the current attested restricted worker; saving, import, validation, preview and preparation never import candidate code; each store has exactly one writer; an uncertain launch is reconciled by lookup and never re-dispatched; OWASP ASVS Level 1, high findings block a release; every API change keeps the contract tests and the UI contract checker green.
- **Architecture:** one cohesive application `hyprn_mvp_app`; every client (UI, agents, CLI) uses the public API `contracts/hyprn-mvp.openapi.yaml`; no client receives native modeling payloads; no second editable model graph, distributed transaction, custom scheduler or provenance platform; the application import graph stays acyclic and the module-boundary test pins it.
- **Locations:** no absolute path in code; every location resolves flag → `HYPRN_MVP_*` variable → installation configuration → per-OS default from the single path-policy module → ask the user; never invent a path. Live stores, logs, scratch folders, evidence and credentials never go in the repository or a synced folder. Tests run only in scoped scratch stores.
- **Dependencies:** before installing any new dependency, record official source, exact version, hash and licence; permissive licences only.
- **UI:** read `design-system/README.md`, `Layouts.md`, `Scientific-states.md` first; build screens only from `ui/src/design` components; tokens only (`design-system/tokens.json` → generated `tokens.css`); no inline styles, external fonts, URLs or CDNs; status is shape + word + colour; run `python3 ui/check_design_system.py` and `python3 ui/design_tokens.py --check`; automated browser evidence is never human acceptance.
- **Work:** one numbered task per fresh executor; atomic commits staging explicit paths; a checkpoint per task; comments and test names state the invariant they protect, not the work item.
- **Checks:** `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group <group>`; a missing target, fixture or environment fails a group, never passes or skips.

## Naming map: current tree → final names

Phase 1 is at task 1.3 of 10; task 1.4 performs the package and contract rename. This research uses the final names; line references below point at the current files. [VERIFIED: `.planning/STATE.md` "1.1–1.3 done and verified … next: 1.4"; `.planning/phases/01-repository-baseline/01-PLAN.md` task 1.4 identifier table]

| Current tree | Final name used in this research |
|---|---|
| (pre-rename identifiers) | see the note below this table |
| UI contract checker `ui/check_ui_contract.py` | renamed by Phase 1 if at all; re-read at execution |
| Runner `deployment/checks.py` | already final |
| `editions/local/` (README only today) | `editions/local/src/hyprn_mvp_local/` created by Phase 2 tasks 2.1–2.13 |

Until Phase 1 task 1.4 lands, the tree still carries the pre-rename package, integration-package, contract, session-cookie, environment-variable, container-label and capability identifiers. This document writes only the final names (`application/src/hyprn_mvp_app/`, `integration/src/hyprn_mvp_integration/`, `contracts/hyprn-mvp.openapi.yaml`, cookie `hyprn_mvp_session`, `HYPRN_MVP_*` variables, labels `org.hyprn-mvp.*`); before task 1.4, locate a file by its basename and a symbol by its name (task 1.4's identifier table gives the exact pairs).

## Summary

The phase builds four things on top of an application that today knows only one kind of actor (a human with a password and a cookie): an **agent principal** with delegations and an authorization intersection; a **tool registry** that calls the real `/api/1` in process through `httpx.ASGITransport`; a **hand-written MCP endpoint** at `/mcp` plus a **stdio relay** in the local CLI; and **proposal confirmation** on an "Assistant proposals" page. Every dependency needed is already pinned (FastAPI 0.143.0, Starlette 1.7.0, HTTPX 0.28.1, jsonschema 4.26.0, anyio 4.15.1); the CLI side needs only the Python standard library and the OS credential tools Phase 2 already uses. **No new dependency is required**, so no supply-chain review needs scheduling, provided the plan keeps to the stdlib TOML emission and the Phase 2 credential adapter described below.

The current code has several human-only assumptions the plan must change deliberately: the `sessions` table references `users`; `store.authorize` looks up `memberships` by actor id (an agent would get 404 everywhere, and `/api/1/capabilities` would degrade because it probes the actor's first study); `store.command` skips authorization for pre-study commands (an agent session could create a study); the browser middleware applies cookie and CSRF checks to every POST on every path, so `/mcp` cannot be a normal FastAPI route; record reads do not expose the receipt actor (only approach versions carry `created_by`), so the attribution chip needs a new read path; the module-boundary test scans only top-level `*.py` files, so the new subpackages would be invisible to it; and `contracts.py`, the package `__init__.py` and `contracts/schemas/model.schema.json` are in the attested execution source set, so no agent schema may be added there.

The MCP landscape moved since the specs were written: the **current MCP revision is 2026-07-28**, which removes the `initialize` handshake and `Mcp-Session-Id`. Claude Code's v2 runtime probes for that revision and falls back to the initialize-based handshake; the Codex documentation still describes instructions "returned during initialization". The recommended default is an initialize-based server negotiating 2025-11-25 or 2025-06-18 that answers a pre-initialize `server/discover` probe with a JSON-RPC error so dual-era clients fall back; this keeps D-05's `Mcp-Session-Id` semantics valid. Whether Codex connects that way is the first live verification the plan must schedule.

**Primary recommendation:** Build stage 1 as a tracer through `auth`/`store`/middleware (agent session → read 200, write 403, other study 404, revocation → next call refused), mount `/mcp` through an outer ASGI dispatcher in front of the FastAPI app, keep all agent schemas out of the attested files, and gate every client-dependent fact behind a recorded live verification on both desktop clients.

## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|------------|-------------|----------------|-----------|
| Agent actors, delegations, tool-token and agent-session minting and verification | API / Backend (`auth`, tables in the application store) | — | Credentials are verified server-side; `authorize` must see them on every call |
| Authorization intersection (delegation × delegator membership × ceiling × effect) | API / Backend (`store.authorize` + middleware route allowlist) | — | Same enforcement point as human calls (agents principle A2) |
| Tool registry, projections, guards, two-phase protocol | API / Backend (`agent_tools`, in process) | — | The registry is a client of `/api/1`; it never reaches scientific modules |
| Agent sessions, journal, proposals, limits, kill switch, notes, attribution index | API / Backend (`agent_runtime`) | Database (own tables) | Agent-side records outside the study; one writer (the application) |
| MCP protocol endpoint `/mcp` | API / Backend (`agent_surface.mcp_server`, same ASGI listener) | — | Same process; loopback exposure comes from the published port |
| Stdio ↔ HTTP relay, credential-store read, port-owner check | Local CLI (`hyprn_mvp_local`, user's machine) | OS credential store, Docker engine | Desktop apps spawn stdio servers; the token must never be in a file |
| Study-folder kit, client configuration, deny rules, location chain | Local CLI | Path-policy module | User files outside the repository |
| Assistant proposals page, attribution chip | Browser / Client (React UI) | API (`/api/1/agent/...` reads, confirm routes) | Confirmation uses the human browser session, Origin and CSRF |
| Evaluation harness (scripted) | Test tier (application tests, runner groups) | — | No model; in-process application |
| Live evaluation and human smoke | Desktop clients on a scratch installation | — | Costs money; started manually (D-16) |

## Standard Stack

### Core (all already pinned; nothing to install)

| Library | Version | Purpose | Why standard |
|---------|---------|---------|--------------|
| FastAPI | 0.143.0 | Existing API app; agent routes as an `APIRouter` | Already the API framework [VERIFIED: `application/requirements.lock:7` "fastapi==0.143.0"] |
| Starlette | 1.7.0 | Raw ASGI app for `/mcp` (`Request`, `JSONResponse`) | FastAPI's base; D-05 "written on the existing pinned dependencies" [VERIFIED: `application/requirements.lock:25` "starlette==1.7.0"] |
| HTTPX | 0.28.1 | `AsyncClient(transport=ASGITransport(app=...))` in-process API client | Decided in tooling spec §2.3 [VERIFIED: `application/requirements.lock:10` "httpx==0.28.1"] |
| anyio | 4.15.1 | Thread-pool bridging for sync route handlers under async callers | Transitive, pinned [VERIFIED: `application/requirements.lock:3` "anyio==4.15.1"] |
| jsonschema | 4.26.0 | Draft 2020-12 validation of tool inputs before any API call | Already used by `contracts.py` [VERIFIED: `application/requirements.lock:13` "jsonschema==4.26.0"] |
| pydantic | 2.14.0 | Closed request models for new agent routes (keeps them out of `model.schema.json`) | Existing `Closed` base-model pattern in `api.py` [VERIFIED: `application/requirements.lock:18` "pydantic==2.14.0"] |
| Python standard library (`http.client`, `json`, `socket`, `subprocess`, `tomllib`, `secrets`, `hashlib`) | CPython 3.12.11 (Phase 2 pin) | Relay, study kit, TOML read-back check, token generation and hashing | No dependency; `tomllib` exists from Python 3.11 [CITED: Phase 2 plan D-05 "CPython is 3.12.11 everywhere"] |

### Supporting

| Library | Version | Purpose | When to use |
|---------|---------|---------|-------------|
| pytest | 9.1.1 | Application, contract and local-edition tests | Every Python group [VERIFIED: `application/requirements.lock:21` "pytest==9.1.1"] |
| Playwright | 1.62.1 | `agent-ui` browser group | Assistant proposals page and attribution chip [VERIFIED: `ui/package.json` devDependencies `"playwright": "1.62.1"`] |
| React | 19.3.0 | UI screens from `ui/src/design` | [VERIFIED: `ui/package.json` `"react": "19.3.0"`] |
| OS credential tools | system | macOS `security`; Linux `secret-tool` | Only through Phase 2's adapter (Phase 2 D-10) |

### Alternatives considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Hand-written MCP server | Official MCP Python SDK | Rejected by the specs (tooling §2.2: no MCP libraries in `agent_tools`; the server is "written directly on existing pinned dependencies"); would also need a licence and provenance review |
| Hand-written scripted MCP client in tests | MCP SDK or MCP Inspector as a test-only client | Independent conformance oracle, but a new dependency; the live desktop-client smoke covers interoperability instead. Not recommended |
| Fixed TOML template with `json.dumps` values and a `tomllib` read-back test | `tomli_w` | New dependency for a six-line file; not needed |
| OS tools through the Phase 2 adapter | `keyring` package | New dependency; Phase 2 D-10 already decided OS tools with secrets on standard input |
| Docker Engine API over the configured endpoint (stdlib `http.client` on a Unix socket) | `docker` CLI from `PATH` | Desktop apps may start the relay with a reduced `PATH` [ASSUMED] |

**Installation:** none. No package is added to `application/requirements.lock`, `ui/package.json` or the Phase 2 root lock.

## Package Legitimacy Audit

No external package is installed by this phase. Every library above is already pinned with hashes in `application/requirements.lock` and recorded in `application/dependency-pins.json` (source, licence and hash per package), or belongs to the Python standard library or the operating system.

| Package | Registry | Age | Downloads | Source repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none new) | — | — | — | — | — | Not applicable |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

If the plan later chooses any library not listed above (an MCP SDK, `keyring`, `tomli_w`, a UI library), the AGENTS.md dependency rule applies: record official source, exact version, hash and licence before install, permissive licences only, and add a `checkpoint:human-verify` before the install task.

## Architecture Patterns

### System architecture diagram

```text
 Desktop client (Codex / Claude Code) opened on the study folder
   │  reads AGENTS.md, .mcp.json or .codex/config.toml, client deny rules
   │  spawns stdio server: <installed hyprn-mvp command> mcp relay --study <id>
   ▼
 Relay (hyprn_mvp_local, stdlib)
   ├─ read installation configuration (flag → HYPRN_MVP_CONFIG → default)
   ├─ read token from the OS credential store (account <installation_id>:mcp-token:<study_id>)
   ├─ verify through the Docker endpoint that this installation's labelled application
   │  container publishes 127.0.0.1:<port>  ── no → refuse with an MCP error; token never sent
   └─ forward each newline-delimited JSON-RPC message as one POST
   │  Authorization: Bearer <token>, Host = configured origin, no Origin, no Cookie
   ▼
 Application listener 127.0.0.1:<port> (published) → outer ASGI dispatcher
   ├─ path == /mcp ─► agent_surface.mcp_server
   │      ├─ refuse: Origin present 403 · Host mismatch 403 · Cookie 401 · bad token 401
   │      │          body > 256 KB 413 · kill switch off 503 · GET 405
   │      ├─ JSON-RPC: initialize (version negotiation, instructions) · tools/list ·
   │      │            tools/call · resources/list|read · prompts/list|get · DELETE session
   │      └─ Runtime.call_tool(surface_ctx, call_id, name, arguments)
   │              ├─ admission: session live, limits, journal row (intended)
   │              └─ Registry.invoke → handler → ApiClient (in-process ASGI, agent session)
   │                        │ Cookie hyprn_mvp_session, Origin, X-CSRF-Token
   │                        ▼
   └─ otherwise ─► FastAPI app (/api/1, /ui)
          middleware: Host · Origin · cookie+CSRF on mutations · agent route allowlist ·
                      read-only agent sessions refuse mutations · 2 MiB · strict JSON
          routes → store.authorize(db, actor, study, write, owner)
                      agent actor → live delegation ∩ delegator membership ∩ ceiling
          receipts carry actor_id = agent actor
   ▼
 Proposals (C1/C2) stored by agent_runtime → "Assistant proposals" page (browser session)
   confirm (delegating user only) → re-check delegation → re-preview → execute the stored
   request with the stored command id under a fresh agent session → outcome in the journal →
   the agent learns it through list_pending_proposals or the next tool result
```

### Recommended project structure

```text
application/src/hyprn_mvp_app/
├── auth.py                  # extended: agent sessions, tool tokens (mint, verify, revoke)
├── store.py                 # extended: agent tables DDL, authorize intersection, study listing
├── api.py                   # composition root: router mount, middleware rules, outer dispatcher
├── agent_tools/             # → contracts only (+ injected ApiClient)
│   ├── spec.py              # ToolSpec, effects, confirmation classes, annotations
│   ├── registry.py          # Registry.definitions / invoke, REGISTRY_VERSION, hashes
│   ├── api_client.py        # ApiClient over httpx.ASGITransport; envelope and error decoding
│   ├── catalogue/           # one module per area: orient, study, approach, model,
│   │                        # evidence, configuration, runs, conclusion, housekeeping
│   ├── projections.py       # caps, truncation notes, untrusted_content wrapping
│   ├── two_phase.py         # preview → digest → commit helper (digests never surface)
│   ├── guards.py            # section 7.1 pure checks
│   ├── backmaps.py          # API JSON pointer → tool input path
│   ├── playbook.py          # playbook sections as text constants (PD-3.1 source)
│   └── instructions.py      # compact MCP server instructions (< 2,000 characters)
├── agent_runtime/           # → agent_tools, auth, its own tables
│   ├── schema.py            # agent_sessions, agent_actions, agent_proposals, notes, issues, attribution
│   ├── runtime.py           # Runtime.call_tool, admission, budgets, kill switch
│   ├── journal.py           # intended → outcome, reconciliation through receipts
│   ├── proposals.py         # create, confirm (re-preview, execute), withdraw, expire, stale
│   ├── attribution.py       # index of agent-written records, cross-checked with receipts
│   ├── routes.py            # APIRouter: /api/1/agent/...
│   └── __main__.py          # operator commands: mint, list, revoke tool tokens (no HTTP mint)
└── agent_surface/           # → agent_runtime only
    ├── jsonrpc.py           # strict JSON-RPC 2.0 parsing and error objects
    └── mcp_server.py        # ASGI app for /mcp
editions/local/src/hyprn_mvp_local/
├── study.py                 # study new
├── study_kit.py             # AGENTS.md, .mcp.json, .codex/config.toml, deny rules, inputs/
├── mcp_tokens.py            # mcp token list | renew | revoke
└── mcp_relay.py             # stdio ↔ /mcp relay (stdlib only)
ui/src/
├── AssistantProposals.tsx   # proposals page (InferenceBlock cards)
└── (attribution chip per the UI design contract 03-UI-SPEC.md)
```

### Pattern 1: Agent principal without changing `authorize`'s signature

**What:** Keep `authorize(db, actor, study, write=False, owner=False)` and resolve agent actors inside it.
**When:** Every study-scoped read and command, including receipt replay.
**Facts it builds on:** `authorize` queries `memberships` by the actor id and returns 404 when absent [VERIFIED: `application/src/hyprn_mvp_app/store.py:243-247` `row=db.execute("SELECT role FROM memberships WHERE study_id=? AND actor_id=?",(study,actor)).fetchone()` / `if row is None: raise DomainError("resource_not_found",404)` / `if owner and row["role"]!="owner" or write and row["role"]=="reader":` / `raise DomainError("forbidden",403)`].
**Design rules:**
- At most one **live** delegation per (agent actor, study); renewal revokes the previous token or replaces the delegation. `authorize` can then find the delegation without a session argument. [ASSUMED design]
- `owner=True` is always refused for agent actors locally (membership management; lifecycle effects are not offered locally).
- `write=True` requires a delegation whose allowed effects include a write effect; read-only delegations (before the authoring review, D-03) refuse.
- The effect per route (draft, record, submit) is enforced by a **route allowlist for agent sessions** in the middleware, derived from the registry's `api_operations` for the delegation's allowed effects (Decision ND-4), because `authorize` only distinguishes read, write and owner.

```python
# Sketch only [ASSUMED]: table and column names are proposals.
def authorize(self, db, actor, study, write=False, owner=False):
    agent = db.execute("SELECT delegator_actor_id FROM agent_actors WHERE actor_id=?", (actor,)).fetchone()
    subject = actor
    if agent is not None:
        delegation = db.execute(
            "SELECT role_ceiling, allowed_effects FROM agent_delegations "
            "WHERE agent_actor_id=? AND study_id=? AND revoked_at IS NULL AND expires_at>?",
            (actor, study, time.time())).fetchone()
        if delegation is None:
            raise DomainError("resource_not_found", 404)
        if owner or (write and not writes_allowed(delegation)):
            raise DomainError("forbidden", 403)
        subject = agent["delegator_actor_id"]          # the user's CURRENT membership decides
    row = db.execute("SELECT role FROM memberships WHERE study_id=? AND actor_id=?", (study, subject)).fetchone()
    if row is None:
        raise DomainError("resource_not_found", 404)
    if owner and row["role"] != "owner" or write and row["role"] == "reader":
        raise DomainError("forbidden", 403)
```

### Pattern 2: In-process API client

**What:** `httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url=<installation origin>)`.
**Transport behaviour (HTTPX 0.28.1):** constructor `ASGITransport(app, raise_app_exceptions=True, root_path="", client=("127.0.0.1", 123))`; the scope's `server` comes from the request URL; lifespan is never sent; the response body is fully buffered; with `raise_app_exceptions=True` an app exception is re-raised to the caller. [CITED: https://raw.githubusercontent.com/encode/httpx/0.28.1/httpx/_transports/asgi.py]
**Rules:**
- Point the transport at the **FastAPI app**, not at the outer dispatcher, so tools can never reach `/mcp` through the client.
- Use `base_url` = the configured origin so the middleware's Host check passes [VERIFIED: `application/src/hyprn_mvp_app/api.py:117` `if request.url.netloc!=auth.origin.split("://",1)[-1]:raise DomainError("forbidden",403)`].
- Send the cookie as a header on each request (`Cookie: hyprn_mvp_session=<agent session>`), plus `Origin` and, on mutations, `X-CSRF-Token` [VERIFIED: `api.py:121` `auth.authorize_mutation(request.cookies.get("hyprn_mvp_session"),request.headers.get("origin"),request.headers.get("x-csrf-token"))`].
- Set `raise_app_exceptions=False` so an unexpected exception becomes the same 500 envelope a browser would see.
- Call it only from `async` code (MCP handler, confirm route). Never wrap it in `asyncio.run` inside a sync route handler.

```python
# Sketch [ASSUMED module API]; httpx calls per the cited source.
import httpx

class ApiClient:
    def __init__(self, api_app, origin):
        self._origin = origin
        self._http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api_app, raise_app_exceptions=False),
            base_url=origin)

    async def request(self, session, method, path, json_body=None):
        headers = {"Origin": self._origin, "Cookie": "hyprn_mvp_session=" + session.cookie}
        if method != "GET":
            headers["X-CSRF-Token"] = session.csrf
        response = await self._http.request(method, "/api/1" + path, json=json_body, headers=headers)
        return response.status_code, response.json()
```

### Pattern 3: Mount `/mcp` outside the browser middleware

**Why:** The FastAPI `http` middleware checks Origin, cookie and CSRF on every mutating request except `POST /api/1/session`, on every path [VERIFIED: `api.py:118-121` `if request.method in {"POST","PATCH","DELETE","PUT"}:` / `auth.authorize_origin(request.headers.get("origin"))` / `if request.url.path!="/api/1/session" or request.method!="POST":` / `auth.authorize_mutation(...)`], and bounds bodies at 2 MiB [VERIFIED: `api.py:125` `if len(raw)>2*1024*1024:raise DomainError("limit_exceeded",413)`]. `/mcp` needs the opposite rules (no Origin allowed, no cookie allowed, bearer token, 256 KB).
**How:** an outer ASGI callable selects `mcp_app` for `scope["path"] == "/mcp"` and the FastAPI app otherwise. `from_environment()` returns the composed app; `generate_contract.py` keeps calling `create_app(...).openapi()`, so `/mcp` never appears in the OpenAPI document [VERIFIED: `application/generate_contract.py:12` `spec=create_app(None,None,None).openapi()`].

```python
# Sketch [ASSUMED]
def compose(api_app, mcp_app):
    async def app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/mcp":
            await mcp_app(scope, receive, send)
        else:
            await api_app(scope, receive, send)
    return app
```

**`/mcp` request checks, in order:** method (POST, or DELETE with a session id; GET → 405 because no SSE stream is offered [CITED: MCP 2025-11-25 transports, "or else return HTTP 405 Method Not Allowed"]) → Host equals the configured origin's host and port (403) → any `Origin` header → 403 [CITED: MCP 2025-11-25 transports: "If the `Origin` header is present and invalid, servers **MUST** respond with HTTP 403 Forbidden"; D-05 treats every Origin as invalid] → any `Cookie` header → 401 → `Authorization: Bearer` tool token valid for audience `/mcp` (401) → kill switch (503) → body read with a 256 KB bound (413) → strict JSON (no duplicate keys, no non-finite numbers, depth bound), one JSON-RPC object (arrays → 400) → session id and `MCP-Protocol-Version` checks.

### Pattern 4: MCP lifecycle (initialize-based era)

**Facts:**
- The current MCP revision is **2026-07-28**; it removes the `initialize` handshake and protocol-level sessions (`Mcp-Session-Id`), requires `server/discover`, a per-request `_meta` version and new headers. [CITED: https://modelcontextprotocol.io/specification/versioning; https://modelcontextprotocol.io/specification/2026-07-28/changelog]
- A dual-era client probes a stdio server with `server/discover`; "The server returns any other error, or does not respond within a reasonable timeout: the server is legacy. Fall back to the `initialize` handshake." [CITED: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio]
- Claude Code: "The v2 runtime is the same code on MCP TypeScript SDK 2.0, which adds MCP protocol revision 2026-07-28"; on v2 it "asks HTTP, stdio, and claude.ai connector servers whether they support the newer revision, and uses it with those that do. It connects to every other server as v1 does." `MCP_PROTOCOL_NEGOTIATION=legacy` keeps every server on the earlier handshake. [CITED: https://code.claude.com/docs/en/mcp]
- Initialize-based negotiation: "If the server supports the requested protocol version, it **MUST** respond with the same version. Otherwise, the server **MUST** respond with another protocol version it supports." The result carries `protocolVersion`, `capabilities`, `serverInfo`, `instructions`. [CITED: https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle]
- Streamable HTTP (2025-11-25): a request may be answered with `Content-Type: application/json`; accepted notifications and responses get `202` with no body; a session id is assigned in `MCP-Session-Id` on the initialize response; servers requiring it "SHOULD respond to requests without an `MCP-Session-Id` header (other than initialization) with HTTP 400"; a terminated session gets 404; DELETE may terminate (or 405); an invalid or unsupported `MCP-Protocol-Version` → 400. [CITED: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports]
- Tools: a tool returning structured content "SHOULD also return the serialized JSON in a TextContent block"; with `outputSchema`, "Servers **MUST** provide structured results that conform"; input validation failures are tool execution errors (`isError: true`); unknown tools are protocol errors (-32602); clients "**MUST** consider tool annotations to be untrusted unless they come from trusted servers". [CITED: https://modelcontextprotocol.io/specification/2025-11-25/server/tools]

**Recommended server behaviour (Decision ND-1):** support `2025-11-25` and `2025-06-18` (the first revision with `structuredContent`, `outputSchema` and `title`); answer an unknown requested version with `2025-11-25`; answer `server/discover` and any other request before `initialize` with JSON-RPC `-32601` immediately (no silence, so the client's probe never waits for a timeout); record the negotiated version and `clientInfo` on the agent session; return every tool result as `structuredContent` plus a text rendering; do not declare `outputSchema` until both clients are verified to handle it (item 7). Defer the 2026-07-28 era unless a target client turns out to be modern-only (OQ-3).

### Pattern 5: Stdio relay (stdlib only)

- Messages are newline-delimited JSON-RPC; nothing but MCP messages on stdout; diagnostics on stderr. [CITED: MCP 2025-11-25 transports, stdio]
- The relay forwards each line as one POST and writes the JSON body of a `200` as one line; a `202` writes nothing; a `401` for an expired or revoked token becomes a JSON-RPC error whose message tells the user to run `./hyprn-mvp mcp token renew --study <id>`.
- Before the first POST it checks the port owner through the installation's Docker endpoint (stdlib `http.client` over the configured Unix socket), not through the `docker` CLI on `PATH`. [ASSUMED: endpoint available from the Phase 2 configuration field `docker.endpoint`, per `02-PLAN.md:109`]
- It never prints, logs or passes the token as an argument, and exits promptly when stdin closes. [CITED: MCP 2026-07-28 stdio: "Servers **SHOULD** exit promptly when their standard input is closed"]
- Startup must stay well under Codex's 10-second default `startup_timeout_sec`; avoid any environment synchronization in the entry path. [CITED: https://learn.chatgpt.com/docs/extend/mcp?surface=cli "Timeout (seconds) for the server to start. Default: `10`."]

### Pattern 6: Proposal confirmation executes as the agent

- The confirm route uses the **human** browser session, Origin and CSRF; it refuses agent actors and any request carrying a tool token; only the delegating user may confirm.
- On confirm: re-check the delegation, mint a fresh agent API session, re-run the preview, compare the candidate digest with the stored one; equal → execute the stored exact request with the stored `command_id` through the in-process client (receipt actor = agent); different → mark `stale`, execute nothing.
- Record `confirmed_by` and `confirmed_at` on the proposal and in the attribution index ("Submitted by {agent} for {user}, confirmed by {user}").
- The confirm route is `async def` so it can await the in-process client in the same event loop.

### Anti-patterns to avoid

- **`/mcp` as a FastAPI route:** inherits cookie and CSRF rules and appears in OpenAPI.
- **Agent schemas in `contracts/schemas/model.schema.json`:** that file is attested, and `generate_contract.py` merges its `$defs` into the OpenAPI components [VERIFIED: `application/generate_contract.py:20` `schemas.update(rewrite(SCHEMA["$defs"]))`]. Use closed pydantic models for agent routes and keep tool input schemas inside `agent_tools`.
- **Checking `request.client` for loopback inside the container:** the application binds `0.0.0.0:8000` inside the container and the host publishes the loopback port [VERIFIED: `deployment/application.Dockerfile:11` `"--host","0.0.0.0","--port","8000"`]; client addresses seen by uvicorn are the engine's, not 127.0.0.1. Rely on the published binding, the Host check and the relay's port-owner check.
- **A generic `call_endpoint` tool, or tools taking `study_id`:** forbidden (D-01, D-09).
- **`wait_for_runs` loops holding a SQLite transaction:** the local store serializes writers (tooling §2.3).

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Calling the API from tools | Direct calls into `store`, `configuration`, `approach`, `modeling` | In-process `ASGITransport` client | Same middleware, schemas, receipts and errors as the UI (D-01) |
| Authorization for agents | A second permission system in `agent_runtime` | `store.authorize` intersection + middleware route allowlist | One enforcement point |
| Idempotency and reconciliation | New idempotency keys | Existing `command_id` receipts and `GET /studies/{study_id}/commands/{command_id}?category=` | Architecture §6.4, §6.6 |
| Preview and commit protocol | Digest handling exposed to the agent | One `two_phase` helper over the existing preview → digest → commit | Tooling §5.1; VER-03 unchanged |
| JSON Schema validation | Custom validator | `jsonschema` Draft 2020-12 | Already pinned and used |
| Canonical digests of arguments | Ad hoc hashing | `contracts.canonical` / `digest` (RFC 8785), called, never edited | Existing identity rules |
| Credential storage | Files, env files, `keyring` | Phase 2 credential-store adapter (OS tools, secrets on standard input) | D-06, Phase 2 D-10 |
| TOML generation | A general TOML library | A fixed template with values serialized by `json.dumps` and a `tomllib` read-back test | Values are strings, string arrays and integers [ASSUMED: JSON string escapes are a subset of TOML basic-string escapes; the read-back test proves it] |
| Token-shaped test data | Literal fake tokens | Tokens assembled at run time | The hygiene guard rejects the product prefix followed by 16 or more token characters in any tracked file [VERIFIED: `deployment/tests/test_hygiene_guard.py:47` `'hyprn' + '_mvp_mcp_' + '[A-Za-z0-9_-]{16,}',                   # product agent tokens`] |

**Key insight:** every safety property this phase needs already exists for humans (receipts, compare-and-set, previews, strict JSON, authorization). The work is to route agents through those properties, not to re-implement them; each shortcut around the API is a second rule set that drifts.

## Common Pitfalls (in the current code)

### Pitfall 1: The browser middleware governs every path
**What goes wrong:** a `/mcp` FastAPI route fails every POST with 403 (no Origin) or 401 (no cookie).
**Why:** the `http` middleware wraps the whole app (`api.py:113-152`).
**Avoid:** outer dispatcher (Pattern 3). **Warning sign:** `/mcp` in the generated OpenAPI.

### Pitfall 2: `sessions` references `users`
**What goes wrong:** inserting an agent API session into `sessions` fails the foreign key, or forces agents into `users` (where they could sign in).
**Evidence:** [VERIFIED: `store.py:74-77` `CREATE TABLE IF NOT EXISTS sessions(` / `token_hash TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(actor_id),` / `csrf_hash TEXT NOT NULL, expires_at REAL NOT NULL`].
**Avoid:** a separate agent API session table (hashed cookie and CSRF, delegation id, read-only flag, 15-minute expiry); `Auth.authenticate` consults both and returns the actor kind, delegation and read-only flag to the middleware. Agent actors never enter `users`, so `POST /api/1/session` can never sign them in.

### Pitfall 3: Agent actors have no membership
**What goes wrong:** every study read returns 404; `/api/1/capabilities` silently reports reduced capabilities because it probes the actor's first study.
**Evidence:** [VERIFIED: `store.py:280-283` `def list_studies(self,actor):` … `"SELECT s.* FROM studies s JOIN memberships m USING(study_id) WHERE m.actor_id=? ORDER BY s.study_id"`; `api.py:196-199` `studies=store.list_studies(who)` / `caps=configs.native_capabilities(who,studies[0]["study_id"]) if studies else None`].
**Avoid:** Pattern 1, and resolve `list_studies` and `study_listing` for agent actors through the delegation scope (exactly the delegated study). Direct `memberships` queries exist only in `store.py`.

### Pitfall 4: Pre-study commands skip authorization
**What goes wrong:** with a writer session, `POST /api/1/studies` would create a study owned by the agent actor.
**Evidence:** [VERIFIED: `store.py:372-375` `def command(self,actor,study,category,command,payload,operation,*,owner=False,receipt_state="committed",request=None):` … `if study:self.authorize(db,actor,study,write=True,owner=owner)`; `store.py:402-408` `create_study` runs `db.execute("INSERT INTO memberships VALUES(?,?,?)",(sid,actor,"owner"))`].
**Avoid:** refuse every command with `study=None` for agent actors (403) in `store.command`, and leave `POST /studies` out of the agent route allowlist.

### Pitfall 5: Records do not expose who wrote them
**What goes wrong:** the attribution chip has nothing to render for evidence, configurations, runs, model versions, study context and archive transitions.
**Evidence:** receipts store `actor_id` [VERIFIED: `store.py:108-111` `CREATE TABLE IF NOT EXISTS receipts(` / `scope TEXT NOT NULL, category TEXT NOT NULL, command_id TEXT NOT NULL,` / `actor_id TEXT NOT NULL, payload_digest TEXT NOT NULL, state TEXT NOT NULL,`], but in the public contract only `ApproachVersion1`, `ApproachVersion2`, `ApproachVersionSummary1`, `ApproachVersionSummary2` (and the Documents schemas) carry `created_by`, and no record read carries `command_id` [VERIFIED: scan of `contracts/hyprn-mvp.openapi.yaml` components this session].
**Avoid:** an attribution index owned by `agent_runtime` (record id, version id, command category and id, agent actor, delegator, confirmer), written when the runtime sees the API outcome, cross-checked against the receipt actor on every read, and exposed by a new study-scoped read for the UI (Decision ND-10). Human-written records have no entry.

### Pitfall 6: The module-boundary test cannot see subpackages
**What goes wrong:** the new boundary rows pass vacuously because `agent_tools/*.py` is never scanned.
**Evidence:** [VERIFIED: `application/tests/test_module_boundaries.py:257` `for path in sorted(root.glob('*.py')):` — the same top-level glob appears at lines 506, 523, 570, 582, 604, 706, 731 and 737].
**Avoid:** switch production scans to `rglob('*.py')`, assert that files under `agent_tools`, `agent_runtime` and `agent_surface` are scanned, and add the D-10 direction rows.

### Pitfall 7: Attested files
**What goes wrong:** editing `contracts.py`, the package `__init__.py` or `contracts/schemas/model.schema.json` changes the execution source set; the attestation goes stale and the two-sided coverage test fails.
**Evidence:** [VERIFIED: `integration/src/hyprn_mvp_integration/launcher.py:116-136` the reviewed literal includes `'application/src/hyprn_mvp_app/__init__.py'`, `'application/src/hyprn_mvp_app/contracts.py'`, `'contracts/schemas/model.schema.json'`, `'contracts/schemas/execution.schema.json'`].
**Avoid:** no Phase 3 task lists these files; the D-10 test asserts that no agent module is in the static launch-path closure and that the attested list is unchanged; each checkpoint confirms the commit diff touches none of them.

### Pitfall 8: Owner recovery leaves agent credentials alive
**Evidence:** [VERIFIED: `auth.py:33-38` `# Local administrative operation only; deliberately has no HTTP route.` … `db.execute("DELETE FROM sessions")`].
**Avoid:** recovery also revokes agent API sessions, tool tokens and pending proposals.

### Pitfall 9: Existing API tests need the real modeling service
**What goes wrong:** copying the `test_api.py` fixture makes agent tests depend on a running modeling container and a fixed key-file location.
**Evidence:** [VERIFIED: `application/tests/test_api.py:22-35` `FaultTransport.__call__` calls `raw_request(method,path,body,headers)` imported from `deployment.tests.model_client`; `test_api.py:41-42` reads a fixed key-file path] (a location issue Phase 1 owns).
**Avoid:** application-owned reads (study, approach, evidence, configurations, run history) need no modeling call; for model reads use a recorded-response `ModelingClient` transport in tests, and keep model, configuration and run tools in a Docker-need group on the existing native fixtures.

### Pitfall 10: Playbook text missing from the installed package
**What goes wrong:** sections stored as `.md` package data pass in source tests but are absent from the wheel Phase 2 builds from the snapshot. [ASSUMED: `application/pyproject.toml` declares no package data; verified only that it has no `[tool.setuptools]` table]
**Avoid:** keep sections as text constants in `agent_tools/playbook.py`; generate `docs/agents/playbook.md` from them and test equality.

### Pitfall 11: Desktop apps start the relay with a different environment
**What goes wrong:** `docker` or the installation configuration is not found; on Linux the Secret Service is unreachable.
**Facts:** Codex offers `env` ("Environment variables to set for the server") and `env_vars` ("Environment variables to allow and forward") [CITED: https://learn.chatgpt.com/docs/extend/mcp?surface=cli]; Claude Code sets `CLAUDE_PROJECT_DIR` for stdio servers [CITED: https://code.claude.com/docs/en/mcp].
**Avoid:** generated entries pass `--config <resolved configuration file>` when the configuration is not at its default; the relay reaches Docker through `docker.endpoint`; on Linux the Codex entry lists `env_vars = ["DBUS_SESSION_BUS_ADDRESS"]`. Verify on each client (PD-3.9).

### Pitfall 12: Claude Code limits and transforms
**Facts:** "Claude Code truncates each tool description and each server's instructions at 2,048 characters by default"; a warning above 10,000 output tokens and a default maximum of 25,000 (`MAX_MCP_OUTPUT_TOKENS`); text results over 50,000 characters are saved to a file; root-level `anyOf`/`oneOf`/`allOf` are flattened; top-level property names must be 1–64 characters of ASCII letters, digits, `_`, `.`, `-`; project `.mcp.json` servers prompt for approval in interactive sessions, and `enableAllProjectMcpServers` committed in an untrusted folder is ignored. [CITED: https://code.claude.com/docs/en/mcp]
**Avoid:** keep the spec's caps (6,000 tokens ≈ 24 KB), no root combinators, short property names; never generate auto-approval settings.

### Pitfall 13: Codex approval and sandbox semantics
**Facts:** `default_tools_approval_mode` accepts `auto`, `prompt`, `writes`, `approve`, and "The `writes` mode prompts for tools that aren't marked read-only"; project `.codex/config.toml` applies to "trusted projects only"; `tool_timeout_sec` defaults to 60; "Destructive app/MCP tool calls always require approval when the tool advertises a destructive annotation", unless a read annotation is present; by default "`allow_local_binding = false` blocks loopback, link-local, and private destinations" for commands; the command network proxy "does not filter … MCP server connections". [CITED: https://learn.chatgpt.com/docs/extend/mcp?surface=cli; https://learn.chatgpt.com/docs/agent-approvals-security]
**Avoid:** every read tool sets `readOnlyHint: true` (otherwise every read prompts); C2 tools set `destructiveHint: true` (friction only, never a confirmation).

### Pitfall 14: Two vocabularies for proposal state
**Evidence:** today `InferenceBlock` statuses are `proposed`, `applied`, `discarded`, `checking` [VERIFIED: `design-system/components/InferenceBlock.md` "**Status.** `proposed` (not applied), `applied`, `discarded`, and `checking`"]; the proposal lifecycle needs awaiting confirmation, confirmed, withdrawn, stale, expired, failed, uncertain.
**Avoid:** the draft UI design contract (`03-UI-SPEC.md`, present in the phase folder, status draft) replaces the `InferenceBlock` statuses with the proposal lifecycle and adds `Naming.md` rows; task 3.13 follows that contract once verified.

### Pitfall 15: Capabilities advertise "assistance" as unavailable
**Evidence:** [VERIFIED: `api.py:206` the `unavailable` list ends with `"cancellation","assistance"]`].
**Avoid:** when the registry is active, advertise the local MCP surface and its registry version; keep `cancellation` unavailable.

### Pitfall 16: Shared files with Phases 2 and 4
`deployment/checks.py` (group registration), `application/src/hyprn_mvp_app/api.py`, `contracts/hyprn-mvp.openapi.yaml` (and the generated `ui/src/contract.ts`), the UI study shell (`ui/src/Workspace.tsx`, `ui/src/workspaceModel.ts`), and the files Phase 2 creates in `editions/local/` (`cli.py`, `paths.py`), `deployment/config.schema.json` and `docs/operations/cli.md` (Phase 2's `docs` group compares it with `--help`). Each is edited by one task at a time.

## Code Examples

### Initialize-based lifecycle with a fast answer to the modern probe

```python
# Sketch [ASSUMED module API]; rules per MCP 2025-11-25 lifecycle and 2026-07-28 stdio backward compatibility.
SUPPORTED = ("2025-11-25", "2025-06-18")

def handle_before_initialize(message):
    if message.get("method") == "initialize":
        requested = message["params"].get("protocolVersion")
        version = requested if requested in SUPPORTED else SUPPORTED[0]
        return {"jsonrpc": "2.0", "id": message["id"], "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "hyprn-mvp", "version": REGISTRY_VERSION},
            "instructions": SERVER_INSTRUCTIONS}}           # < 2,000 chars, first 512 self-contained
    if "id" in message:                                       # e.g. a server/discover probe
        return {"jsonrpc": "2.0", "id": message["id"],
                "error": {"code": -32601, "message": "Method not found before initialize"}}
    return None                                               # a notification: 202, no body
```

### Tool result with structured and text content

```python
# Per MCP 2025-11-25 tools: structuredContent plus the serialized JSON in a TextContent block.
def tool_result(projection, *, error=False):
    text = json.dumps(projection, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return {"content": [{"type": "text", "text": text}],
            "structuredContent": projection, "isError": error}
```

### Relay core loop (stdlib)

```python
# Sketch [ASSUMED]; framing per the MCP stdio rules. The token stays in memory only.
import http.client, json, sys

def relay(host, port, origin_host, token):
    session_id = protocol = None
    for line in sys.stdin:                                    # one JSON-RPC message per line
        headers = {"Host": origin_host, "Authorization": "Bearer " + token,
                   "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if session_id: headers["Mcp-Session-Id"] = session_id
        if protocol: headers["MCP-Protocol-Version"] = protocol
        connection = http.client.HTTPConnection(host, port, timeout=200)
        connection.request("POST", "/mcp", body=line.encode("utf-8"), headers=headers)
        response = connection.getresponse(); body = response.read()
        session_id = response.getheader("Mcp-Session-Id") or session_id
        if response.status == 202:
            continue
        if response.status == 200:
            message = json.loads(body)
            protocol = protocol or message.get("result", {}).get("protocolVersion")
            sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n"); sys.stdout.flush()
        else:
            sys.stdout.write(relay_error(line, response.status) + "\n"); sys.stdout.flush()
```

### Codex project configuration without a TOML library

```python
# [ASSUMED] JSON string escapes (\" \\ \n \r \t \b \f \uXXXX) are valid TOML basic-string escapes;
# the study-kit test parses the output with tomllib and compares every value.
def codex_config(command, args):
    q = lambda s: json.dumps(s, ensure_ascii=True)
    return ("[mcp_servers.hyprn-mvp]\n"
            f"command = {q(command)}\n"
            f"args = [{', '.join(q(a) for a in args)}]\n"
            "startup_timeout_sec = 30\n"
            "tool_timeout_sec = 180\n"
            'default_tools_approval_mode = "writes"\n')
```

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| HTTP+SSE transport | Streamable HTTP (JSON or SSE per request) | 2025-03-26 | `/mcp` returns `application/json` only; GET → 405 |
| Text-only tool results | `structuredContent`, `outputSchema`, `title` | 2025-06-18 | Return structured and text content |
| `initialize` handshake, `Mcp-Session-Id` sessions | Stateless per-request `_meta` version, `server/discover`, no protocol sessions | 2026-07-28 | Clients become dual-era; a legacy server must answer the probe with an error; D-05 session semantics apply only to the initialize-based era |
| Restricted `inputSchema` keywords | Any JSON Schema 2020-12 keyword; `structuredContent` any JSON value | 2026-07-28 | No change needed; keep schemas simple for provider rules |
| Claude Code MCP on TS SDK 1.x | v2 runtime on TS SDK 2.0 negotiates 2026-07-28 and falls back | Claude Code v2.1.232+ in flag-fetching sessions | An initialize-based server stays compatible |

**Out of date in the specs:**
- Tooling spec §5.4 says the generated Claude Code `timeout` raises the limit; the documented default without `MCP_TOOL_TIMEOUT` is "about 28 hours", so `"timeout": 180000` is a cap, not a raise. Keep it (it exceeds the 45-second wait and the roughly 60-second full run read). [CITED: https://code.claude.com/docs/en/mcp]
- Tooling spec §11.6 cites the MCP 2025-06-18 transports page; the current revision is 2026-07-28.

## Client and protocol facts mapped to tooling spec §11.7 items 5–8 (PD-3.9)

| Item | Fact | Status | Where the plan verifies it |
|---|---|---|---|
| 5a | Codex reads the MCP `instructions` "returned during initialization"; "Keep the first 512 characters self-contained" | Settled from docs [CITED: learn.chatgpt.com/docs/extend/mcp] | Unit test of instructions length; live check in task 3.10 |
| 5b | Whether Codex surfaces MCP prompts and resources | **Not documented** | Live, task 3.10; the `get_playbook` tool is the fallback either way |
| 5c | Loopback from Codex's sandboxed shell commands | Settled: blocked by default (`allow_local_binding = false`) [CITED: agent-approvals-security] | Live G7 confirmation, task 3.18 |
| 5d | Whether the relay runs inside the Codex sandbox and can reach loopback and the Docker endpoint | **Not documented** (only "does not filter … MCP server connections") | Live, task 3.10 (blocking for Codex support) |
| 5e | Which MCP era Codex speaks and whether it probes `server/discover` | **Not documented** | Live, task 3.10: record the initialize parameters and versions (OQ-3) |
| 6a | Claude Code per-server `timeout` in milliseconds overrides `MCP_TOOL_TIMEOUT`; "Values below 1000 are ignored"; not restricted to a transport in the docs | Settled from docs [CITED: code.claude.com/docs/en/mcp] | Live confirmation for stdio, task 3.10 |
| 6b | `Read`/`Edit` deny rules do not cover scripts that open files themselves; the OS sandbox covers shell commands and their children; "MCP servers, and hooks run outside it"; absolute paths in rules use `//`; the sandbox proxy refuses hosts that resolve only to local addresses except `localhost` names | Settled from docs [CITED: code.claude.com/docs/en/permissions; code.claude.com/docs/en/sandboxing] | Generate deny rules (`//`-anchored data root and checkout, `Bash(curl *)`, `Bash(wget *)`, `Bash(docker *)`, `Bash(sqlite3 *)`) plus sandbox settings with the resolved locations filled in by the CLI; live G7, task 3.18 |
| 6c | Whether sandbox settings in a generated project `.claude/settings.json` take effect in the study folder once trusted | **Partly documented** (project settings cannot switch filesystem isolation off) | Live, task 3.10 |
| 7 | Handling of `structuredContent`, `outputSchema` and annotations | Partly: Codex uses read-only and destructive annotations; Claude Code not documented | Live, task 3.10; default: no `outputSchema` until verified |
| 8 | macOS Keychain through `security`, Linux Secret Service through `secret-tool`; hosts without a provider refuse | Settled in Phase 2 D-10 and PD-2.2; behaviour tested by Phase 2 task 2.10 | Reuse; the relay test asserts that recorded process arguments hold no token |

## Decisions: recommended defaults

### Context open decisions

| ID | Recommended default | Risky? | Notes |
|---|---|---|---|
| PD-3.1 | Adopt; store sections as Python text constants (Pitfall 10); an equality test in `agent-tools` rather than an edit to Phase 2's `docs` tool; update `docs/specs/agents.md` and the tooling spec | No | Spec text changes in the same task |
| PD-3.2 | Adopt; the per-OS default lives in Phase 2's path-policy module; add an optional `studies_root` to the closed configuration schema | No (coordination) | Phase 2's field list has no `studies_root` [VERIFIED: `02-PLAN.md:109` "Fields: `schema`, `edition` (`local`), `installation_id` … `agent.enabled` (default true), `agent.token_ttl_hours` (default 8), `upstream.cache`"] |
| PD-3.3 | Adopt, plus `startup_timeout_sec = 30` for Codex, `--config` in arguments when the configuration is not at its default, Linux `env_vars`; never generate auto-approval settings | No, but items 5d and 6a need live checks | — |
| PD-3.4 | Adopt (refuse, no file fallback) | No | WSL2 consequence in OQ-4 |
| PD-3.5 | CLI list, renew and revoke; also add owner-session API routes for list and revoke so a later UI panel is cheap | **Yes** — contradicts `docs/specs/agents.md` §11 (token list/revoke UI in the local read-only step), tooling spec §11.4 and Stage 0 task 0.3, workspaces §9.3 and the UI-04 wording | OQ-1 |
| PD-3.6 | Adopt | No | — |
| PD-3.7 | Adopt; the numbers fit a linear total coefficient of 55 kPa per L/s (110 = 55 × 2; 121 = 55 × 2.2), for example two sections of 30 and 25 kPa per L/s | No | Fixture design is planner's discretion |
| PD-3.8 | Adopt | No | — |
| PD-3.9 | Adopt, with the verification schedule above; record results in tooling spec §11.7 | Partly (OQ-3, OQ-4) | — |

### New decisions surfaced by this research

| ID | Decision (recommended default) | Risky? |
|---|---|---|
| ND-1 | Initialize-based MCP only, versions 2025-11-25 and 2025-06-18; requests before `initialize` (including `server/discover`) get `-32601` at once | **Yes** (depends on unverified Codex behaviour) → OQ-3 |
| ND-2 | Tool tokens are minted by an operator command inside the application container (`python -m hyprn_mvp_app.agent_runtime mint-token …`) that the CLI invokes; the token returns once on the pipe's standard output, never in arguments; no HTTP route mints; list and revoke through owner-session routes | No (consistent with "minted only by the CLI" and with owner recovery having no HTTP route) |
| ND-3 | "Shown once": the token is printed only with an explicit `--show-token` on an interactive terminal; refused with `--json` or a non-terminal standard output | **Yes** — tension between D-06 "shown once" and Phase 2's "No secret ever appears in output" → OQ-2 |
| ND-4 | Agent sessions are limited by a middleware route allowlist (method + route template) derived from the registry's `api_operations` for the delegation's allowed effects; pre-study commands are refused for agent actors | No |
| ND-5 | A separate agent API session table; 15-minute agent API sessions; cookie and CSRF values only in memory, hashes in the table | No |
| ND-6 | At most one live delegation per (agent actor, study); renewal replaces tokens | No |
| ND-7 | One active MCP session per token: a new `initialize` ends the previous session, so a restarted relay never locks the user out | No |
| ND-8 | `/mcp` is mounted by an outer ASGI dispatcher, absent from OpenAPI, unreachable from the in-process client | No |
| ND-9 | Progress notes and platform-issue reports are written by `agent_runtime` into its own tables, not through `POST /api/1/agent/...` under the agent session, so "any POST through the token's session → 403" holds in the read-only stage | **Yes (minor)** — deviates from tooling spec §4.9 → OQ-7 |
| ND-10 | Attribution index in `agent_runtime`, cross-checked against receipts; a new study-scoped read for the chip | No |
| ND-11 | Agent route request bodies are closed pydantic models; tool input schemas stay in `agent_tools`; nothing is added to attested schema files | No |
| ND-12 | Kill switch: the application reads `HYPRN_MVP_AGENT_ENABLED` at start (passed from `agent.enabled` by Phase 2's application manager) and consults it on every call; absent → agents disabled (fail closed); toggling needs `stop`/`start`; locally the per-user switch is the installation switch | No (needs Phase 2 wiring) |
| ND-13 | Read tools annotated `readOnlyHint: true`; C2 tools `destructiveHint: true`; no `outputSchema` until item 7 is verified | No |
| ND-14 | Test tiers: no-need groups use application-owned reads and recorded modeling responses; Docker-need groups cover model, configuration and run tools | No |
| ND-15 | Tool fields `expected_version` and `version_token` carry revisions, while the glossary entry "Revision" says _Avoid_: Version | **Yes (minor)** — contradicts either the tooling spec or `CONTEXT.md` → OQ-6 |
| ND-16 | Proposal status vocabulary per the UI design contract (`03-UI-SPEC.md`) | No |

## Open questions for the product owner (risky items; not guessed)

1. **OQ-1 Token panel deferral (PD-3.5).** The agents spec §11, tooling spec §11.4 and task 0.3, workspaces §9.3 and UI-04 all say the UI lists and revokes local tokens. Deferring it leaves UI-04 `partial` at release. Recommended: accept the deferral and add the owner-session list and revoke API routes now. Needs explicit acceptance and a spec note.
2. **OQ-2 "Shown once" versus "no secret in output".** Recommended: print only on an explicit `--show-token` to an interactive terminal (for the documented HTTP alternative); otherwise never. Needs a choice.
3. **OQ-3 MCP protocol era.** Recommended: an initialize-based server (ND-1), the 2026-07-28 era deferred. If the live check finds Codex modern-only, Codex support needs a modern-era server (stateless; agent session keyed by token instead of `Mcp-Session-Id`) and D-05/D-11 wording changes. Decide after task 3.10's verification.
4. **OQ-4 WSL2 with Windows desktop apps.** A Windows desktop app cannot start the POSIX relay inside WSL2 without a wrapper, and WSL2 often has no Secret Service. Recommended: in this phase WSL2 is supported only with clients running inside WSL2; Windows desktop apps are unsupported. Needs acceptance.
5. **OQ-5 G7 audit evidence.** A filesystem and network audit of a desktop-client run normally needs elevated tools, which the product never requests. Recommended evidence: the client transcript, the application's 401 log lines for `/api/1` during the run window, a study-folder diff, and client deny-rule and sandbox denials. Needs acceptance as the G7 "filesystem and network audit".
6. **OQ-6 Revision naming in tool schemas.** Rename `expected_version`/`version_token` to `expected_revision`/`revision_token` (and update the tooling spec), or keep the spec's names as a documented exception to `CONTEXT.md`.
7. **OQ-7 Progress-note path (ND-9).** Accept the deviation from tooling spec §4.9 and update the spec.

## Proposed stage → task breakdown

One task per fresh executor. Files marked shared are edited by one task at a time across Phases 2–4.

### Stage 1 — Agent principal and attribution (backend can run beside Phase 2)

| Task | Scope | Files | Depends on |
|---|---|---|---|
| **3.1 (tracer)** Agent principal and authorization intersection | Agent tables in the store schema (agent actors, delegations, agent API sessions, tool tokens); `Auth.mint_agent_session`, `mint_tool_token`, `verify_tool_token`, revocation; `authenticate` returns kind, delegation and read-only flag; middleware: bearer tool tokens on `/api/1` → 401, read-only agent sessions refuse mutations (403), agent route allowlist (read routes only at first); `authorize` intersection; agent study listing; pre-study commands refused; recovery revokes agent credentials; boundary test: `rglob`, D-10 rows, attested set unchanged | `application/src/hyprn_mvp_app/{auth,store,api}.py` (`api.py` shared), `application/tests/test_agent_principal.py`, `application/tests/test_module_boundaries.py`, `deployment/checks.py` (shared: register `agent-tools`) | Phase 1 complete |
| **3.2** Agent runtime administration and attribution read | `agent_runtime` skeleton: delegation lifecycle, operator mint/list/revoke command, owner-session token list and revoke routes, attribution index and its study-scoped read, agent display names ("Codex (local) for {user}"); regenerate OpenAPI and UI types | `application/src/hyprn_mvp_app/agent_runtime/{__init__,schema,delegations,tokens,attribution,routes,__main__}.py`, `api.py` (router mount), `contracts/hyprn-mvp.openapi.yaml`, `ui/src/contract.ts` (generated), `application/tests/test_agent_runtime_admin.py` | 3.1 |
| **3.3** Attribution chip | Chip on study context changes, evidence versions, model versions, approach drafts and versions, configurations, runs, archive transitions; "confirmed by" on confirmed records; design-system additions per `03-UI-SPEC.md`; fixture app with agent-written records | `ui/src/design/*` (if the contract adds a component), `design-system/components/*.md`, `design-system/Naming.md`, record views in `ui/src/`, `ui/src/api.ts`, `deployment/tests/agent_ui_fixture.py`, `ui/tests/agent-attribution.spec.ts`, `deployment/checks.py` (register `agent-ui`) | 3.2; verified UI design contract |

### Stage 2 — Read-only tools and the local MCP server

| Task | Scope | Files | Depends on |
|---|---|---|---|
| **3.4** Registry skeleton, in-process client, guidance surfaces | `ToolSpec`, `Registry.definitions` (deterministic per surface), `REGISTRY_VERSION`, playbook and tool-definition hashes, the full catalogue skeleton (one module per area, gated by stage, so later tasks edit disjoint files), `ApiClient` with a parity test on 10 routes, `api_operations` ⇔ OpenAPI parity, provider schema rules, compact instructions, playbook constants and the generated `docs/agents/playbook.md`, spec updates for PD-3.1 | `agent_tools/{__init__,spec,registry,api_client,playbook,instructions}.py`, `agent_tools/catalogue/*.py`, `docs/agents/playbook.md`, `docs/specs/agents.md`, `docs/agents/tooling-spec.md`, `application/tests/{test_agent_registry,test_agent_api_client}.py` | 3.1 |
| **3.5** Read tools and projections | Tooling §4.1 tools, approach, model, evidence, configuration and run reads, interim `get_run_status`, `compare_runs`, result sources; caps, truncation notes, pagination cursors, `untrusted_content`; golden projections; secret fuzz | `agent_tools/projections.py`, `agent_tools/catalogue/{orient,approach,model,evidence,configuration,runs}.py`, `application/tests/fixtures/agent/*.json`, `application/tests/{test_agent_read_tools,test_agent_secret_fuzz}.py` | 3.4 |
| **3.6** Agent runtime core | Agent sessions, `Runtime.call_tool`, journal rows with argument digests, limits (calls per session, result size), kill switch, progress notes and platform-issue reports (ND-9) with `post_progress_note` and `report_platform_issue` | `agent_runtime/{runtime,sessions,journal,limits,notes}.py`, `agent_tools/catalogue/housekeeping.py`, `application/tests/test_agent_runtime.py` | 3.4 (parallel with 3.5: disjoint files) |
| **3.7** `/mcp` server | Outer dispatcher; Pattern 3 checks; initialize-based lifecycle (ND-1); tools/list, tools/call, resources `hyprn-mvp://playbook/<section>`, prompt `start_study_work`; MCP session ↔ agent session; DELETE; revocation → `access_lost`; scripted MCP client conformance | `agent_surface/{__init__,jsonrpc,mcp_server}.py`, `api.py` (shared), `application/tests/{mcp_client,test_mcp_server}.py`, `deployment/checks.py` (register `mcp`) | 3.5, 3.6 |
| **3.8** Study-folder kit and token commands | `study new` (study through the API as the Owner, operator mint, credential store, kit), `mcp token list|renew|revoke`, location chain and refusals (synced, symlinked, non-empty, inside the checkout), generated files without secrets, `studies_root` field, CLI documentation | `editions/local/src/hyprn_mvp_local/{study,study_kit,mcp_tokens}.py`, `cli.py` and `paths.py` (Phase 2 files), `deployment/config.schema.json` (Phase 2 file), `docs/operations/cli.md` (Phase 2 file), `editions/local/tests/{test_study_kit,test_mcp_tokens}.py`, `deployment/checks.py` (register `study-kit`) | 3.2; Phase 2 tasks 2.2, 2.9, 2.10, 2.11 (2.14 for the docs file) |
| **3.9** Stdio relay | Pattern 5; port-owner check through the Docker endpoint; credential-store read; renewal message; conformance through the relay against a scratch loopback server | `editions/local/src/hyprn_mvp_local/mcp_relay.py`, `cli.py`, `editions/local/tests/test_mcp_relay.py` (in `mcp`) | 3.7, 3.8; Phase 2 tasks 2.10, 2.11 |
| **3.10** Evaluation skeleton, client verifications, human smoke | `agent-eval` runner and deterministic graders; scripted MCP client scenarios (G2 read-only questions, G5 revocation and kill switch, G7 checklist); the G2 fixture; live verification of items 5–8 on both clients recorded in tooling spec §11.7; human smoke per client on a scratch installation after a fresh `setup` (D-15) | `application/tests/{test_agent_eval_scripted,agent_eval_fixtures}.py`, `docs/agents/tooling-spec.md` §11.7, `deployment/checks.py` (register `agent-eval`) | 3.7, 3.9; Phase 2 task 2.13 |

### Stage 3 — Local authoring (writer tokens only after the product owner's review)

| Task | Scope | Depends on |
|---|---|---|
| **3.11** Journal reconciliation and error mapping | Tooling §5.7 for every category; the §6 envelope; back-maps with a coverage test | 3.6, 3.7 |
| **3.12** Proposals and confirmation | Proposals table; confirm (batch for C1, single for C2), withdraw, expiry, invalidation on access loss and kill switch; Pattern 6; `list_pending_proposals`, `withdraw_proposal`; agents and tokens cannot confirm | 3.11 |
| **3.13** Assistant proposals page | Page from `InferenceBlock` per `03-UI-SPEC.md`; Confirm N for C1, individual C2 with a diff; stale and expired states; only the delegating user sees Confirm; links from tool results | 3.12; verified UI design contract |
| **3.14** Content guards | Tooling §7.1 checks; text-inventory fixture assembled at run time | 3.4 (parallel with 3.12) |
| **3.15** Study context and evidence tools | `update_study_context` (C2), `add_evidence`, `revise_evidence` (C1), conflict diffs, description-copy warning | 3.12, 3.14 |
| **3.16** Approach tools | Patch operations, preview diagnostics mapped to the operation index, `save_approach_version`, `restore_approach_draft` | 3.12, 3.14 (parallel with 3.15: disjoint catalogue modules) |
| **3.17** Model tools | `create_model`, `edit_model` (source encoding, units, automatic rebind, rewire diagnostic), `validate_model`, `commit_model_version`; Docker-need tests on the native fixtures | 3.12, 3.14 |
| **3.18** Review gate, writer tokens, local evaluation | `checkpoint:decision` — the product owner's review of proposal and control behaviour; then writer-capable tokens; live G2, G4, G5, G7, G8 on both clients; scripted structural parts of G4 and G8 | 3.13, 3.15–3.17 |

### Stage 4 — Configurations, runs and results

| Task | Scope | Depends on |
|---|---|---|
| **3.19** Configuration tools | `preview_configuration`, `save_configuration`, typed source rendering, `default_source`, result-linked inputs | 3.18 |
| **3.20** Run tools and light status | `submit_runs` with readiness pre-check and caps; `wait_for_runs` (≤ 45 s, 3–15 s backoff, `stalled`, no tight loops); list-based change detection | 3.19 |
| **3.21** Interim conclusion | `record_conclusion` deterministic note, no ids, claims in the journal | 3.19 (parallel with 3.20: disjoint) |
| **3.22** Evaluation and status | Scripted G3, G6; live G3, G6 and G1 per client; parity table; requirement status updates per PD-3.6 | 3.20, 3.21 |

### Parallelism summary

- **Beside Phase 2 (file-disjoint):** 3.1–3.7, 3.11–3.17 and 3.19–3.21 touch `application/`, `contracts/`, `ui/`, `docs/agents/`, `docs/specs/`; their only overlap with Phase 2 is `deployment/checks.py` registrations, which the orchestrator serializes.
- **After Phase 2:** 3.8 and 3.9 need tasks 2.9–2.11 (2.2 for the configuration schema, 2.14 for `docs/operations/cli.md`); 3.10, 3.18 and 3.22 need task 2.13's scratch installations and a fresh `setup` per stage (D-15). Phase 2's application manager must pass `HYPRN_MVP_AGENT_ENABLED` to the application container (ND-12).
- **Within Phase 3:** 3.3 ∥ 3.4; 3.5 ∥ 3.6; 3.12 ∥ 3.14; 3.15 ∥ 3.16 (∥ 3.17 when the environment allows); 3.20 ∥ 3.21.
- **With Phase 4:** `api.py`, the contract and the UI study shell are serialized.

## Threats and mitigations

| ID | Threat (STRIDE) | Severity | Mitigation | Task |
|---|---|---|---|---|
| T-3-01 | A browser page posts to `/mcp` (cross-site request; Tampering) | high | Any `Origin` → 403; bearer token required; cookies → 401 | 3.7 |
| T-3-02 | DNS rebinding to the loopback port (Spoofing) | high | `Host` must equal the configured origin; port published only on 127.0.0.1 | 3.7 |
| T-3-03 | Token leaks through files, arguments, logs or output (Information disclosure) | high | Credential store only; the relay reads it into memory; tokens hashed at rest; log redaction; hygiene guard; study-folder grep; recorded-argument tests; ND-3 | 3.2, 3.8, 3.9 |
| T-3-04 | Tool token used on `/api/1`, cookie used on `/mcp` (Elevation) | high | Explicit 401 both ways; audience bound to `/mcp` | 3.1, 3.7 |
| T-3-05 | Port squatting before the relay sends the token (Spoofing) | medium | Port-owner check through the Docker endpoint against this installation's labelled container; refuse otherwise | 3.9 |
| T-3-06 | Self-confirmation of proposals (Elevation) | high | The confirm route refuses agent actors and tokens; only the delegating user; browser session, Origin, CSRF | 3.12 |
| T-3-07 | Prompt injection from stored text (Tampering) | high | `untrusted_content`; `study_id` never an argument; C1/C2 need confirmation; caps per proposal; G4 | 3.5, 3.12, 3.18 |
| T-3-08 | Missing audit trail (Repudiation) | medium | Append-only `agent_actions` with argument digests; receipts carry the agent actor; confirmer recorded | 3.6, 3.11, 3.12 |
| T-3-09 | Duplicate runs after lost responses (Tampering, Denial of service) | high | Command ids journaled first; reconciliation through receipts; `uncertain` never resubmitted; per-session run caps | 3.11, 3.20 |
| T-3-10 | Agent exceeds the user's authority or scope (Elevation) | high | Intersection in `authorize`; route allowlist; pre-study commands refused; read-only sessions; G5 | 3.1 |
| T-3-11 | Agent creates studies or manages memberships (Elevation) | high | Pitfall 4 refusal; no membership routes; `owner=True` refused for agents | 3.1 |
| T-3-12 | A stale proposal executes after a human edit (Tampering) | high | Re-preview at confirm; digest mismatch → stale, never executed | 3.12 |
| T-3-13 | Agent bypasses the tools through its shell (local boundary) | medium (accepted residual: local mode is not a boundary against a hostile agent) | Instructions, `AGENTS.md`, client deny rules and sandbox, token refused on `/api/1`, G7 | 3.8, 3.18 |
| T-3-14 | Kill switch fails open | high | Fail closed when the variable is absent; checked per call; pending proposals unconfirmable | 3.6, 3.12 |
| T-3-15 | Secrets in tool outputs (Information disclosure) | high | Allowlist projections; secret fuzz on every read tool | 3.5 |
| T-3-16 | Resource exhaustion through `/mcp` (Denial of service) | medium | 256 KB body bound; 600 calls per session; one session per token; 6,000-token results | 3.6, 3.7 |
| T-3-17 | Attested source set changed by agent work (Elevation) | critical | No edits to attested files; D-10 test; checkpoint diff check | 3.1 and every task |

## Environment Availability

Probed on the development host during research (versions omitted because they are host-specific).

| Dependency | Required by | Available | Fallback |
|------------|------------|-----------|----------|
| Docker engine | Native groups (model, configuration and run tools), relay port-owner checks, scratch installations | Yes | — |
| Node.js and the Playwright toolchain | `agent-ui` | Node present; `ui/node_modules` not probed | `npm --prefix ui ci` |
| uv and the pinned CPython 3.12.11 | All Python groups (the host's system `python3` is older and lacks `tomllib`) | uv present; CPython through Phase 2 | Phase 2 `./hyprn-mvp dev check` |
| macOS `security` | Credential store on macOS | Yes | — |
| `secret-tool` with a Secret Service | Credential store on Linux | No: absent on this host (macOS) | A Linux host or VM for Linux evidence |
| Claude Code (desktop app or CLI) | Live verification, human smoke, live evaluation | No: absent on `PATH` (desktop app not probed) | Operator installs; required for AGENT-08 |
| Codex (desktop app or CLI) | Same | No: absent on `PATH` (desktop app not probed) | Same |
| Phase 2 CLI, adapters, scratch installations | 3.8, 3.9, 3.10, 3.18, 3.22 | No (not built yet) | None — sequencing dependency |

**Missing dependencies with no fallback:** the Phase 2 CLI and scratch-installation harness (sequence after tasks 2.9–2.13); both desktop clients for the live and human items.
**Missing dependencies with fallback:** a Linux Secret Service (use a Linux host for the Linux evidence).

## Validation Architecture

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (application, contracts, local edition); Playwright 1.62.1 (UI); stdlib `unittest` in the runner guards |
| Config file | `application/pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`); `ui/playwright.isolated.config.ts` for fixture-served specs |
| Quick run command | `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group agent-tools` (after Phase 2: `./hyprn-mvp dev check agent-tools`) |
| Full suite command | `HYPRN_MVP_DATA_ROOT=<development data root> python3 -B deployment/checks.py --group qualification` |

### Groups to register in `deployment/checks.py`

The runner declares classes `must-pass` and `opt-in` and needs `docker`, `browser`, `fixtures`, `installation` [VERIFIED: `deployment/checks.py:556-557` `CLASSES = ('must-pass', 'opt-in')` / `NEEDS = ('docker', 'browser', 'fixtures', 'installation')`].

| Group | Class | Needs | Content |
|---|---|---|---|
| `agent-tools` | must-pass | — | Principal and intersection, route allowlist, registry and schema rules, OpenAPI parity, projections on recorded fixtures, caps, `untrusted_content`, secret fuzz, guards, back-maps, playbook equality, instructions limits, journal and proposal logic on application-owned records |
| `agent-tools-native` (recommended split) | must-pass | docker | Model, configuration and run tools against the existing native fixtures |
| `mcp` | must-pass | — | Scripted MCP client against the in-process `/mcp`; the relay against a scratch loopback server with a fake credential adapter and a stub Docker endpoint |
| `study-kit` | must-pass | — (add a `credential-store` need if real OS-store round trips are included) | Kit generation, no token anywhere, TOML and JSON read-back, deny rules, location refusals |
| `agent-ui` | must-pass | browser | Proposals page and attribution chip on a fixture app |
| `agent-eval` | must-pass | — | Scripted G2, G3, G5 (and the structural parts of G4 and G8) on every commit (D-16) |
| `agent-eval-live` (or a recorded manual runbook) | opt-in | installation (and a desktop client) | Live G1–G8 per client; started manually |

### Phase requirements → test map

| Req | Behavior | Type | Automated command | File exists? |
|-----|----------|------|-------------------|-------------|
| AGENT-05 | Agent session: read 200, write 403 before writer tokens, other study 404, token on `/api/1` 401, revocation → next call refused, membership removal → `access_lost` | unit and integration | `checks.py --group agent-tools` | No (Wave 0) |
| AGENT-05 | Receipts carry the agent actor; the chip renders "{agent} for {user}" and the confirmer | integration and browser | `--group agent-tools`, `--group agent-ui` | No |
| AGENT-06 | An agent cannot confirm; stale re-proposes; batch C1, individual C2; expiry; confirmer recorded | integration and browser | `--group agent-tools`, `--group agent-ui` | No |
| AGENT-07 | Kill switch off refuses every call; 600-call budget; one session per token; journal rows with digests only | integration | `--group mcp`, `--group agent-tools` | No |
| AGENT-01 | Conformance in process and through the relay; Origin, Host, cookie and body rules; tools listed from a study folder | integration | `--group mcp`, `--group study-kit` | No |
| AGENT-01 | Both desktop clients list the tools and answer a read-only G2 question | manual (human smoke) | recorded per client | manual-only: needs the real clients |
| AGENT-08 | Scripted G2, G3, G5 | integration | `--group agent-eval` | No |
| AGENT-08 | Live G2, G4, G5, G7, G8; G3, G6; G1 per client; parity table | live | started manually | manual-only: costs money (D-16) |
| UI-04 | Proposals page and chip | browser | `--group agent-ui` | No |

### Sampling rate

- **Per task commit:** the task's own group or groups, plus `locality-contracts` (boundary and identity tests) and `contracts`; the design checks for UI tasks.
- **Per stage end:** every Phase 3 group plus `qualification`.
- **Phase gate:** `qualification` green; live evaluation and human smoke records present per client; human acceptance recorded separately.

### Wave 0 gaps

- [ ] Recorded modeling responses (or a test `ModelingClient` transport) for the no-need groups
- [ ] Scripted MCP client helper (`application/tests/mcp_client.py`)
- [ ] Golden projection fixtures; secret-seeded fixtures assembled at run time
- [ ] Text-inventory fixture for the guards (blocked items assembled at run time)
- [ ] Fake credential-store adapter and stub Docker endpoint for relay tests
- [ ] `deployment/tests/agent_ui_fixture.py` serving the fixture app
- [ ] G2 pressure-loss fixture (met, violated and downstream-failure variants)
- [ ] Runner registrations and, if used, a `credential-store` need probe

## Security Domain

### Applicable ASVS categories (Level 1)

| ASVS category | Applies | Standard control |
|---------------|---------|-----------------|
| V2 Authentication | yes | 256-bit `secrets` tokens, SHA-256 hashes at rest (high-entropy tokens), constant-time comparison, expiry, revocation |
| V3 Session management | yes | 15-minute agent API sessions held in memory; random MCP session ids bound to the token; DELETE and expiry end them |
| V4 Access control | yes | `authorize` intersection, route allowlist, delegating-user-only confirmation, scoped 404 |
| V5 Validation | yes | Closed JSON Schemas (jsonschema), strict JSON (duplicates, non-finite numbers, depth), 256 KB bound, content guards |
| V6 Cryptography | limited | Standard-library `secrets` and `hashlib` only; nothing hand-rolled |
| V7 Errors and logging | yes | One error envelope; no tokens, cookies or bodies in logs; digests in the journal |
| V8 Data protection | yes | Allowlist projections; credential store; nothing secret in the study folder |
| V13 API | yes | Origin and Host rules on `/mcp`; CSRF on browser routes |
| V14 Configuration | yes | Fail-closed kill switch; loopback-only publication |

### Known threat patterns for this stack

| Pattern | STRIDE | Standard mitigation |
|---------|--------|---------------------|
| Localhost cross-site requests and DNS rebinding against a local MCP endpoint | Spoofing, Tampering | Origin rejection, Host check, bearer token (MCP transport security warning) |
| Confused deputy through a generic API tool | Elevation | Task-level tools only; `study_id` injected |
| Prompt injection from stored records | Tampering | Untrusted wrapping, structural confirmation, caps |
| Token in shell history or configuration | Information disclosure | The relay reads the credential store; never add a server with an expanded token in a header |
| Replay of a lost write | Tampering | Command ids and receipts |

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | `json.dumps` string output is a valid TOML basic string | Code Examples | Malformed `.codex/config.toml`; caught by the read-back test |
| A2 | Codex connects to an initialize-based server (directly or after a probe) | Pattern 4, ND-1 | Codex unsupported until a modern-era server exists (OQ-3) |
| A3 | Stdio servers started by Codex can reach loopback and the Docker endpoint | Client facts 5d | The relay cannot connect from Codex |
| A4 | Desktop clients start stdio servers with a reduced environment | Pitfall 11 | Only over-engineering |
| A5 | Claude Code's per-server `timeout` applies to stdio servers | Client facts 6a | The default (about 28 hours) applies; harmless |
| A6 | Reading a Keychain item created by `security` through `security` raises no prompt | Pattern 5 | Interactive prompt when the relay starts |
| A7 | The Docker endpoint in the Phase 2 configuration exposes published ports and installation labels | Pattern 5 | The port-owner check needs another source |
| A8 | Sandbox settings in a generated project `.claude/settings.json` take effect once the folder is trusted | Client facts 6c | Weaker G7 enforcement; deny rules only |
| A9 | Claude Code reads `AGENTS.md` when no `CLAUDE.md` exists (cited by the tooling spec, not re-fetched) | Study kit | Generate a `CLAUDE.md` that imports `AGENTS.md` |
| A10 | `application/pyproject.toml` declares no package data for non-Python files | Pitfall 10 | None if sections are Python constants |
| A11 | Table and column names in the sketches | Patterns 1–2 | Naming only; the planner decides |
| A12 | One live delegation per (agent actor, study) is acceptable product behaviour | ND-6 | Renewal semantics change |

## Open Questions (technical, for the planner)

1. **Where the owner-API client lives in `editions/local/`.** Phase 2's smoke test acts as the Owner over the API; whether it exposes a reusable module is not stated. Recommendation: task 3.8 reuses it if present, otherwise adds a small stdlib client.
2. **Light run status.** RUN-07 is planned, not delivered; `wait_for_runs` uses list-based change detection and cached full reads (tooling §5.4) until it exists.
3. **Attribution of C0 draft edits.** The index covers draft revisions written by agents; the chip on a draft may show only its latest writer. Settle in the UI design contract.

## Sources

### Primary (in the repository, read this session)
- `docs/agents/tooling-spec.md` (full), `docs/specs/agents.md` (full), `docs/agents/playbook.md`, `docs/specs/architecture-and-contracts.md` §4, §6–8, `docs/specs/ui-target.md` §3–7, `docs/specs/workspaces-identity-onboarding.md` §9, `docs/specs/requirements.md`, `CONTEXT.md`, `design-system/README.md`, `design-system/components/InferenceBlock.md`, `design-system/tokens.json`
- `.planning/PROJECT.md`, `ROADMAP.md`, `STATE.md`, `config.json`, `phases/01-repository-baseline/01-PLAN.md`, `phases/02-local-edition/02-PLAN.md`, `phases/03-agent-tools-for-coding-agents/03-CONTEXT.md`, `phases/03-agent-tools-for-coding-agents/03-UI-SPEC.md` (draft, read for alignment only)
- `application/src/hyprn_mvp_app/{auth,store,api,contracts}.py`, `application/generate_contract.py`, `application/requirements.lock`, `application/pyproject.toml`, `application/tests/{conftest,test_api,test_module_boundaries}.py`, `integration/src/hyprn_mvp_integration/launcher.py`, `deployment/checks.py`, `deployment/local_paths.py`, `deployment/application.Dockerfile`, `deployment/tests/test_hygiene_guard.py`, `contracts/hyprn-mvp.openapi.yaml` (path and schema scan), `ui/package.json`, `ui/src/design/index.ts`, `ui/src/Workspace.tsx`, `ui/src/api.ts`

### Secondary (official documentation, fetched this session)
- MCP 2025-11-25 transports: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- MCP 2025-11-25 lifecycle: https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
- MCP 2025-11-25 tools: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- MCP versioning: https://modelcontextprotocol.io/specification/versioning
- MCP 2026-07-28 versioning and compatibility: https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
- MCP 2026-07-28 changelog: https://modelcontextprotocol.io/specification/2026-07-28/changelog
- MCP 2026-07-28 stdio: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio
- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Claude Code permissions: https://code.claude.com/docs/en/permissions
- Claude Code sandboxing: https://code.claude.com/docs/en/sandboxing
- Codex MCP: https://learn.chatgpt.com/docs/extend/mcp?surface=cli (redirect target of https://developers.openai.com/codex/mcp)
- Codex approvals and security: https://learn.chatgpt.com/docs/agent-approvals-security
- HTTPX 0.28.1 ASGI transport source: https://raw.githubusercontent.com/encode/httpx/0.28.1/httpx/_transports/asgi.py

### Tertiary (search results, not relied on)
- Third-party Codex MCP guides returned by a web search; no claim in this document rests on them.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library is already pinned and quoted from the lock file; no new dependency.
- Architecture and code pitfalls: HIGH — each rests on files read this session, with line references.
- MCP protocol facts: MEDIUM — official specification pages fetched this session.
- Desktop-client behaviour: LOW to MEDIUM — documented facts cited; items 5b, 5d, 5e, 6c and 7 need live verification.

**Research date:** 2026-10-13
**Valid until:** 2026-11-12 for codebase facts (Phase 1 task 1.4 onward moves files); 7 days for client and protocol facts (fast-moving)
