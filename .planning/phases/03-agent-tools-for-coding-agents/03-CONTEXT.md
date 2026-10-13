# Phase 3: Agent tools for coding agents - Context

**Status:** Ready for planning

<domain>
## Phase Boundary

A desktop coding agent (Codex or Claude Code) works on one HYPRN MVP study through HYPRN MVP's local MCP tool server, from a study folder created by `./hyprn-mvp study new`, as an attributed agent principal acting for the installation's Owner. It reads the study and, under ADR-0003 (`docs/adr/0003-agent-write-rights-revised.md`, which supersedes ADR-0002), writes directly within the Owner's authority: drafts (including removing draft content), model and approach versions, evidence, study context, new studies, configurations, run submissions and an interim conclusion, every write attributed and journaled, with outcome facets kept separate in results. It never deletes a saved record, archives or restores anything, or manages access. Every operation a tool triggers has one owner and one authoritative outcome that every client can reference, inspect and act upon without reconstructing or repeating it (ADR-0004, `docs/adr/0004-operation-ownership.md`). The Owner sees every agent action on the study's Agent activity page and stops an agent by revoking its access. Evaluation scenarios prove each stage.

Delivery order inside the phase (each stage ends with committed work, exact test results and a verified checkpoint before the next starts):

1. **Agent principal and attribution** — agent actors, delegations, the authorization intersection, the agent actor on receipts, the UI attribution chip, delegated agent sessions, revocation (agents spec §9 gap 1; tooling spec §12 Stage 1).
2. **Read-only tools and the local MCP server** — registry skeleton, in-process API client, study-scoped tool tokens and read-only delegated sessions, read tools and projections, `/mcp` server, playbook surfaces, `./hyprn-mvp study new`, `./hyprn-mvp mcp relay`, `./hyprn-mvp mcp token list|renew|revoke`, the study-folder kit, the evaluation harness skeleton (tooling spec §12 Stage 0).
3. **Local authoring** — action journal and reconciliation, the write policy (no tool that deletes a saved record, archives, restores or manages access on any surface; the draft rule; agent route allowlist refusals), the journal-backed Agent activity read and page with a revoke entry point, content guards, study and evidence tools (including `create_study`), approach tools, model tools with automatic rebind, error mapping (tooling spec §12 Stage 2). Writer-capable tokens are enabled only after the product owner's review of agent write and control behaviour (limits, kill switches, journal, attribution, Agent activity, refusal of deletion, archive and restore).
4. **Configurations, runs and results** — configuration tools with typed source rendering, `submit_runs` and `wait_for_runs`, light status adoption, the interim conclusion renderer (tooling spec §12 Stage 3).
5. **Evaluation** — scripted conformance and scenarios on both local clients: G2, G4, G5, G7, G8 after stage 3; G3, G6 and G1 after stage 4; human client smoke on both desktop clients after stage 2.

Not in this phase: the cloud bridge and assistant panel (tooling spec Stage 4), typed-record adoption beyond what lands as gaps close (Stage 5), document tools (after Phase 4 and its agent-parity section; this phase only fixes the route classification they will need), method packages, the scientific review record itself (the `record_scientific_review` tool is gated on it). Deleting saved records, archive, restore and access management by agents are never in scope (ADR-0003).
</domain>

<decisions>
## Decisions

Locked by `docs/specs/agents.md`, `docs/agents/tooling-spec.md`, ADR-0003 (`docs/adr/0003-agent-write-rights-revised.md`, accepted 2026-10-13, superseding ADR-0002, which had superseded the earlier confirmation-class decision in D-04) and ADR-0004 (`docs/adr/0004-operation-ownership.md`, accepted 2026-10-13):

- **D-01** Agents are users of HYPRN MVP, not its developers. They reach HYPRN MVP only through the curated tool registry, which calls `/api/1` in process (ASGI transport into the same application) with a delegated agent session carrying the session cookie, the exact `Origin` and the cross-site request token. No raw API passthrough, store, modeling, AiiDA or executor access.
- **D-02** The agent is its own principal (actor kind `agent`, one per user, surface and installation) acting for one user under a delegation. Effective authority is re-checked on every call: delegation live, study in scope, effect allowed, the user's current role, the role ceiling. Receipts carry the agent actor; records show "{agent} for {user}". Access loss takes effect on the next call.
- **D-03** Attribution comes first in this phase. Tokens minted before the authoring stage's review are read-only; writer-capable tokens are minted only after the product owner's review of agent write and control behaviour passes.
- **D-04** Write policy (ADR-0003). Agent tools execute directly within the delegating user's current authority and the role ceiling; effects are `read`, `draft` (model and approach drafts, including removing draft content; approach draft restore, which writes an earlier version's content into the draft as a new draft revision), `record` (study creation, model and approach versions, evidence create and revise, configuration save, study context change, conclusion; later scientific reviews and collection membership), `submit` (runs, at most 20 per call, 10 queued per actor, 60 per session) and `outside_study` (notes, issue reports). Every write is attributed and journaled; every change to mutable state needs the agent's last-read revision and never retries automatically. **Draft rule:** anything in draft (mutable working) state may be changed or deleted by an agent under revision checks; a saved, versioned or read-only record is never deleted by an agent; frozen copies never change. **Human-only, on every surface and stage:** deleting saved records (collections included), archive and restore (unarchive) of studies and documents, and access management (memberships, invitations, delegations, tool tokens, roles, ceilings): no tool exists for these and the agent route allowlist refuses their API routes (403). **Study creation:** `create_study` makes the delegating user the Owner (never the agent actor), the receipt actor is the agent, and the delegation does not widen to the new study. **Reviews:** `record_scientific_review` is gated on the review record; when registered it records attributed reviews labelled agent-recorded, within the delegating user's eligibility; an agent for a Reviewer stays read-only. **Runs:** `submit_runs` submits nothing when execution readiness is not `ready`, and the API refuses an agent's submission whose configuration is not ready to run, with reasons and no run created. Confirmation classes C0/C1/C2, agent proposals, confirm and withdraw routes, staleness, batch confirm and envelope grants stay retired. Client and provider approval prompts never widen rights.
- **D-05** `/mcp`: Streamable HTTP with JSON responses (no server-sent events), written on the existing pinned dependencies; loopback only; any `Origin` header → 403; `Host` must equal the configured origin; bearer tool token required, cookies refused; tool tokens refused on `/api/1`; request body at most 256 KB; `Mcp-Session-Id` handling; one `agent_actions` row per call with argument digests, not raw bodies.
- **D-06** Tool token: 256-bit, prefixed `hyprn_mvp_mcp_`, stored hashed, audience `/mcp`, one study and one delegation, 8-hour default lifetime (24 hours maximum), shown once, renewed manually, minted only by the CLI, never in files, process arguments or logs. Stored through the Phase 2 credential-store adapter.
- **D-07** The client connection is the stdio relay `./hyprn-mvp mcp relay --study <id>`, which reads the token from the credential store and verifies that this installation's application container publishes the configured loopback port before sending it. The HTTP configuration with `HYPRN_MVP_MCP_TOKEN` is documented as the alternative.
- **D-08** The study folder is outside the source checkout and outside synced folders and holds only `AGENTS.md` (boundary and playbook pointer), `.mcp.json`, `.codex/config.toml`, client deny rules and `inputs/`. Scientific records live only in HYPRN MVP. A synced, symlinked or non-empty existing folder is refused.
- **D-09** Local tokens are study-scoped. `study_id` is never a tool argument. A study an agent creates is reachable by an agent only after the Owner mints its token through the CLI. Agents never delete saved records, archive or restore studies or documents, manage memberships, mint tokens or change roles (ADR-0003).
- **D-10** Module boundaries: `hyprn_mvp_app.agent_tools` → `contracts` (plus the injected API client) only; `hyprn_mvp_app.agent_surface` → `agent_runtime` only; `agent_runtime` → `agent_tools`, `auth` and its own tables. None is imported by execution integration, so the attested execution source set is unchanged (a test asserts it).
- **D-11** Limits and controls per agents spec §3.4: 1 MCP session per token; 60 API calls per turn and 600 per session; tool results about 6,000 tokens with explicit truncation notes; at most 20 runs per call, 10 queued per actor, 60 per session; the kill switch `agent.enabled` (`HYPRN_MVP_AGENT_ENABLED`) refuses tokens, sessions and MCP calls; append-only action journal.
- **D-12** Outputs: compact projections within their caps, units always present, unavailable never zero, ids paired with names, outcome facets separate, text written by others wrapped as `untrusted_content`; pagination `limit` default 10, maximum 25, opaque cursor.
- **D-13** Idempotency: command ids are journaled before each API call; duplicates return the stored outcome; lost responses reconcile through receipts; an uncertain run launch is never resubmitted.
- **D-14** Until the typed conclusion record exists, `record_conclusion` writes a tool-rendered "Study conclusion" evidence note, revised in place as new versions; structured claims stay in the journal.
- **D-15** Each local stage reaches an installation only through a fresh `./hyprn-mvp setup` after its reviews (there is no update path in this milestone); development and evaluation use scratch installations.
- **D-16** Evaluation per agents spec §10: scripted (no model) G2, G3 and G5 run on every commit; live scenarios are started manually because they cost money; a surface is supported only if it passes the reference criteria; human acceptance is recorded separately. G3, G4 and G8 follow their ADR-0003 framing: G3 keeps the human's concurrent edit (the agent's overwrite fails with a conflict, no automatic retry); G4 injected content triggers no write, study creation, archive, deletion or run submission and the agent flags it; G8 provider and client approvals never widen rights, and deletion of saved records, archive, restore and access changes are always refused.
- **D-18** Unified operations and explicit ownership (ADR-0004). Central invariant: an operation produces one authoritative outcome that every client can subsequently reference, inspect and act upon, without reconstructing or repeating the operation. Each tool names the API operations it calls, their owning modules and the stored outcome; every tool or operation that needs shared identity, durability, consistency, observability or recovery has one owner and a stored outcome; no tool manages authoritative state, duplicates business orchestration owned behind the API, or re-executes an operation to reproduce a result; no new state duplicates an engine's authoritative state (receipts record command intent and dispatch reconciliation; AiiDA's lifecycle is projected, never re-modelled). Task 3.2a stays free to choose iteration, sub-agent, skill-loading and tool-granularity patterns within this principle.
- **D-17** Oversight (ADR-0002 default, kept by ADR-0003). The local "Assistant proposals" page becomes a study-scoped, read-only **Agent activity** page: recent agent actions from the action journal, newest first, with the agent attribution, the operation in plain language, the outcome, guard warnings and links to the records created or changed, plus the agents' current access to the study with an entry point to stop an agent by revoking its access (the owner-session revoke route) and the CLI renew command. Attribution chips stay on every agent-written record ("{agent} for {user}", no confirmer). The cloud assistant panel shows the same activity later (Stage 4).
- **D-19** Factorization schedule (product owner, 2026-10-13; `.planning/codebase/FACTORIZATION.md`). Where a planned task would otherwise add a second copy, the factorization comes first: per-owner API routers before the agent routes (item 8) and a study-shell view registry with a model controller before the agent views (item 9), both pure refactors with no behaviour change; one run-row read and a light run-status read (item 4, RUN-07) before the run read tools, so no tool keeps a status cache; a server-decided `recovery` value on command receipts (item 2) before the journal's reconciliation, with the UI switched to it at once; and the whole module layer table pinned by the boundary test (item 6). Items 13 (outbox history projection) and 14 (authorization by effect) wait until after the first release; the other items belong to Phases 1, 2 and 4.

## Open product decisions (recommended defaults)

- **PD-3.1 Playbook location.** The agents spec calls `docs/agents/playbook.md` the playbook; the tooling spec ships it as sections in `hyprn_mvp_app/agent_tools/playbook/`. Default: the packaged sections are the single source (they version with the API and are hashed into the registry version); `docs/agents/playbook.md` is generated from them by a tool, and the `docs` check fails when it is stale. Both specs are updated to say so. Alternative: the document is the source and a build step splits it into sections.
- **PD-3.2 Study-folder location.** Default: adopt the tooling spec's chain — `./hyprn-mvp study new "<name>" --folder DIR`, then `HYPRN_MVP_STUDIES_DIR` (root under which `<study-slug>/` is created), then the installation configuration field `studies_root`, then the default `~/hyprn-mvp-studies`, then ask. Inside the checkout or a synced folder is refused.
- **PD-3.3 Generated client entries.** Default: stdio relay entries — `.mcp.json` `{"mcpServers": {"hyprn-mvp": {"type": "stdio", "command": "<installed hyprn-mvp command>", "args": ["mcp", "relay", "--study", "<study id>"], "timeout": 180000}}}` and `.codex/config.toml` `[mcp_servers.hyprn-mvp]` with the same command and arguments, `tool_timeout_sec = 180`, `default_tools_approval_mode = "writes"`. The CLI fills in the resolved command location in the generated user files; nothing in the repository holds a resolved path. The HTTP alternative is documented, never generated.
- **PD-3.4 Host without a credential store.** Default (same as Phase 2 PD-2.2): `study new` and `mcp token renew` refuse with an explanation; no file fallback.
- **PD-3.5 Token listing and revocation.** Default (as amended by ADR-0002's oversight default and the recorded OQ-1 decision): `./hyprn-mvp mcp token list|renew|revoke <study>` and owner-session list and revoke API routes in this phase; the Agent activity page shows the agents' current access to the study and offers revocation as the way to stop an agent; no separate token-management panel. UI-04 (as reworded for ADR-0002: Agent activity page, attribution chips, token list and revoke through the CLI and the API) can become `delivered` once the page and chips land and pass their checks.
- **PD-3.6 Requirement status.** Default: VER-03 stays `delivered` — agent clients reuse preview → digest → commit and command receipts with no separate mechanism, and the registry hides the protocol from the agent. AGENT-01 becomes `delivered` only after stage 4, the evaluation and Phase 5 qualification; AGENT-05 and AGENT-06 after stage 3 and the product owner's review of control behaviour.
- **PD-3.7 G2 fixture.** Default: the two-section pressure-loss screening fixture (110 kPa at 2 L/s, 121 kPa at 2.2 L/s, 120 kPa criterion), with a met and a violated criterion and a deliberate downstream-failure variant.
- **PD-3.8 G1 fuel-study fixture content.** Default: brief text and short locator extracts only; cite the paper, never redistribute it.
- **PD-3.9 Client and protocol verifications** (tooling spec §11.7 items 5–8: Codex prompts and resources, loopback from its sandbox, relay treatment; most reliable Claude Code deny mechanism and stdio timeout; `structuredContent` and annotations; credential stores per OS). Default: verify each in the first task that needs it, record the result in `docs/agents/tooling-spec.md` §11.7, and negotiate the MCP protocol version from the versions both clients send.

## Planner's discretion

- Task granularity within each stage (one task per fresh executor), test file layout, and the order of read tools within the read-only stage.
- Projection shapes inside the documented caps, and fixture design for golden projections and the secret-fuzz test.
- UI layout of the Agent activity page and the attribution chip, within the design system and `docs/specs/ui-target.md` §4.4.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `docs/adr/0003-agent-write-rights-revised.md` — supersedes ADR-0002: human-only deletion of saved records, archive and restore, and access management; study creation and agent-labelled reviews; draft rule; collections; refusal of unready run submissions; Agent activity oversight.
- `docs/adr/0004-operation-ownership.md` — unified operations and explicit ownership; the central invariant every plan check traces to.
- `docs/specs/agents.md` — principles, roles, identity and delegation (§3), local mode (§4.2), product gaps (§9), evaluation (§10), delivery gates (§11), open questions (§13).
- `docs/agents/tooling-spec.md` — layering and code placement (§2), principal and permissions (§3), tool catalogue (§4), cross-cutting behaviours (§5), errors (§6), guardrails (§7), guidance surfaces (§8), observability and evaluation (§9), security (§10), local mode and client facts (§11.4–11.7), Stages 0–3 (§12), decisions and open questions (§13).
- `docs/agents/playbook.md` — the working rules served to agents.
- `docs/specs/architecture-and-contracts.md` §4.6 (agents as principals), §6.4 (commands, idempotency, compare-and-set), §7 (module ownership).
- `docs/specs/ui-target.md` §4.4 (agent activity and the local Agent activity page), §7 (missing affordances).
- `docs/specs/requirements.md` — AGENT-01, AGENT-05–08, UI-04, VER-03, HUM-10, RUN-07.
- `design-system/README.md`, `design-system/components/InferenceBlock.md` (assistant-originated content; agent tool writes are not proposals), `design-system/Naming.md`.
- `phases/02-local-edition/02-PLAN.md` — CLI contract, credential-store adapter, scratch installations.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- `hyprn_mvp_app.auth`: local sessions, cross-site request token and origin checks — extended with agent actors, delegated sessions and tool tokens.
- `hyprn_mvp_app.store.authorize(db, actor, study, write, owner)`: keeps its signature; gains the delegation intersection.
- Command receipts and the preview → digest → commit sequence (architecture §6.4): the API client and journal build on them.
- `application/tests/test_module_boundaries.py`: gains the agent rows.
- `ui/src/design`: `StatusTag`, `DataTable`, `RecordBar`; screens only from these components.
- `editions/local/src/hyprn_mvp_local/`: CLI, output envelope, credential-store adapter and scratch installations from Phase 2.

### Integration points
- `/mcp` is mounted outside `/api/1` in `hyprn_mvp_app.api`.
- New test groups registered in `deployment/checks.py`: `agent-tools`, `mcp`, `study-kit`, `agent-ui`, `agent-eval`.
- Shared files with Phase 4: `contracts/hyprn-mvp.openapi.yaml`, `application/src/hyprn_mvp_app/api.py`, the UI study shell; one task at a time.

### Dependencies
- Phase 1 (namespace, runner). Backend stages need nothing from Phase 2 and may run beside it.
- `./hyprn-mvp study new`, the relay and token commands need Phase 2 tasks 2.9–2.11; evaluation on scratch installations needs task 2.13's harness.
</code_context>

<specifics>
## Acceptance (phase level)

- A tool token's session gets 403 on any POST, PATCH or DELETE before writer tokens exist; other studies return 404; a token on `/api/1` → 401; a cookie on `/mcp` → 401; a browser `Origin` → 403; a foreign `Host` → 403; the kill switch off refuses every call; revocation makes the next call return `access_lost`.
- `grep -r hyprn_mvp_mcp_` over a generated study folder finds nothing; recorded credential-store process arguments contain no token; the relay passes the scripted MCP conformance suite.
- Both desktop clients list the HYPRN MVP tools from a study folder and answer a read-only question on the G2 fixture (human smoke, recorded per client).
- Server instructions are under 2,000 characters with a self-contained first 512; every tool description is under 2,048 characters; the tool ⇔ OpenAPI parity check passes.
- No registered tool deletes a saved record, archives, restores or manages access on any surface or stage; an agent session gets 403 on those routes; an agent-created study is owned by the Owner and outside the agent's delegation; draft content removed by an agent needs its last-read revision; every agent write appears in the Agent activity read with the agent actor and links to its records; a concurrent human edit is never overwritten.
- A scripted definition edit and commit produce a model version with no instance on a superseded definition.
- `wait_for_runs` never polls faster than once per run per 15 s and returns `stalled` rather than resubmitting.
- G2, G4, G5, G7 and G8 pass on both local clients; G3 and G6 pass; G1 is recorded per client; the parity table is release evidence.

## Threats to cover in plans

Localhost cross-site requests and DNS rebinding on `/mcp`; token leakage through files, arguments or logs; a tool token used on `/api/1` or a cookie on `/mcp`; port squatting before the relay sends a token; an agent session reaching deletion, archive, restore or access routes; an agent-created study widening the agent's reach; a client or tool duplicating orchestration or re-executing to reproduce a result; prompt injection from stored text, including injected but attributed writes and runs (bounded by run caps and kill switches); missing audit trail; agent-driven duplicate runs.
</specifics>

<deferred>
## Deferred Ideas

- A separate UI token-management panel (PD-3.5: revocation is on the Agent activity page; listing through the CLI and the API).
- Cloud managed agents, the provider bridge and the assistant panel.
- Envelope grants: retired by ADR-0002, not deferred.
- Document tools for agents (after Phase 4), research helpers, public web search.
- Run cancellation tool (when run cancellation exists); model import and export tools.
- Typed records as product gaps close: conclusion record, typed inherited provenance, status channel, infeasible outcome, sweeps, currency units.
</deferred>

---

*Phase: 03-agent-tools-for-coding-agents*
