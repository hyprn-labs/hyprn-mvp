# Phase 3: Agent practices from primary sources

Research record of task 3.2a. Every finding below comes from a primary source fetched on 2026-10-13 and listed under "Sources"; nothing is taken from memory or from `03-RESEARCH.md`. Findings are paraphrased; numbers are quoted as the sources state them. Decisions are checked against ADR-0003 (human-only effects: deleting saved records, archive and restore, access management; the draft rule; approvals never widen rights) and ADR-0004 (one authoritative outcome per operation, owner operations of the API only, no client-held authoritative state, no duplicated orchestration, no re-execution to show a result). Binding decisions stay within the specifications and `03-CONTEXT.md`; a decision that would change a decided specification item or a locked D-xx is an open question (OQ-8) for checkpoint 3.2.

## Sources

- [S1] How we built Linear Agent (Linear, published 2026-08-10) — https://linear.app/now/how-we-built-linear-agent — accessed 2026-10-13
- [S2] Model Context Protocol: Versioning (current revision) — https://modelcontextprotocol.io/specification/versioning — accessed 2026-10-13
- [S3] Model Context Protocol 2026-07-28: Key changes — https://modelcontextprotocol.io/specification/2026-07-28/changelog — accessed 2026-10-13
- [S4] Model Context Protocol 2026-07-28: Versioning and compatibility — https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning — accessed 2026-10-13
- [S5] Model Context Protocol 2026-07-28: stdio transport — https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio — accessed 2026-10-13
- [S6] Model Context Protocol 2026-07-28: Streamable HTTP transport — https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http — accessed 2026-10-13
- [S7] Model Context Protocol 2026-07-28: Tools — https://modelcontextprotocol.io/specification/2026-07-28/server/tools — accessed 2026-10-13
- [S8] Model Context Protocol 2026-07-28: Discovery (`server/discover`) — https://modelcontextprotocol.io/specification/2026-07-28/server/discover — accessed 2026-10-13
- [S9] Model Context Protocol 2025-11-25: Tools — https://modelcontextprotocol.io/specification/2025-11-25/server/tools — accessed 2026-10-13
- [S10] Model Context Protocol 2025-11-25: schema source (`ToolAnnotations`, `InitializeResult.instructions`, `listChanged`) — https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2025-11-25/schema.ts — accessed 2026-10-13
- [S11] Model Context Protocol 2025-11-25: Prompts — https://modelcontextprotocol.io/specification/2025-11-25/server/prompts — accessed 2026-10-13
- [S12] Model Context Protocol 2025-11-25: Resources — https://modelcontextprotocol.io/specification/2025-11-25/server/resources — accessed 2026-10-13
- [S13] Model Context Protocol 2025-11-25: Key changes (against 2025-06-18) — https://modelcontextprotocol.io/specification/2025-11-25/changelog — accessed 2026-10-13
- [S14] Claude Code: Connect Claude Code to tools via MCP — https://code.claude.com/docs/en/mcp — accessed 2026-10-13
- [S15] Claude Code: Extend Claude with skills — https://code.claude.com/docs/en/skills — accessed 2026-10-13
- [S16] Codex: Model Context Protocol (redirect target of the Codex MCP page) — https://learn.chatgpt.com/docs/extend/mcp?surface=cli — accessed 2026-10-13
- [S17] Codex: Agent approvals and security — https://learn.chatgpt.com/docs/agent-approvals-security — accessed 2026-10-13
- [S18] Codex: Build skills (redirect target of the Codex skills page) — https://learn.chatgpt.com/docs/build-skills.md — accessed 2026-10-13
- [S19] Anthropic Engineering: Writing effective tools for agents (published 2025-09-11) — https://www.anthropic.com/engineering/writing-tools-for-agents — accessed 2026-10-13
- [S20] Claude Platform: Agent Skills overview — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview — accessed 2026-10-13
- [S21] Claude Platform: Tool search tool — https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool — accessed 2026-10-13
- [S22] Claude Platform: Prompt caching — https://platform.claude.com/docs/en/build-with-claude/prompt-caching — accessed 2026-10-13
- [S23] Claude Managed Agents: Overview — https://platform.claude.com/docs/en/managed-agents/overview — accessed 2026-10-13
- [S24] Claude Managed Agents: Tools — https://platform.claude.com/docs/en/managed-agents/tools — accessed 2026-10-13
- [S25] Claude Managed Agents: Start a session (configuration overrides) — https://platform.claude.com/docs/en/managed-agents/sessions — accessed 2026-10-13
- [S26] OpenAI API: Function calling — https://developers.openai.com/api/docs/guides/function-calling — accessed 2026-10-13
- [S27] OpenAI API: Tool search — https://developers.openai.com/api/docs/guides/tools-tool-search — accessed 2026-10-13
- [S28] OpenAI Agents API: Configuration — https://developers.openai.com/api/docs/guides/agents-api/configuration — accessed 2026-10-13

## Unreachable sources

None: every source above was fetched on 2026-10-13. Two limits of what was read are stated where they matter: the 2026-07-28 schema reference page (about 700,000 characters) was not read in full, so the annotation semantics below are cited from the 2025-11-25 schema source [S10]; and Codex's documentation does not state which MCP revision Codex speaks, so that fact is left to the live probe of task 3.17.

## Linear Agent practices

From [S1]. Each finding states what it means for HYPRN MVP.

1. **Boundaries, not scripts.** The team sets boundaries inside which the agent finds its own path, through five levers: the system prompt, tool design, the agent's model of the product, the scope of each run and a custom harness. *For HYPRN MVP:* the same levers exist (core rules, registry, playbook, delegation scope, the in-process API client), except the harness: HYPRN MVP never runs its own model loop (tooling spec §2.3), so the harness lever belongs to the desktop client or the provider.
2. **Many shallow product-operation tools, constraints in the parameters.** Tools are numerous but shallow, each tied to one product operation, with easy parameters and invalid actions made impractical by the tool's shape, unlike coding agents that use a few deep primitives; direct SDK, GraphQL, CLI or code-environment access was rejected as more error-prone on long-tail requests, accepting occasional refusals for predictability. *For HYPRN MVP:* this is the tooling spec's catalogue (task-level tools, closed schemas, patch operations, no raw API passthrough, D-01) and the local boundary (no direct `/api/1`, stores or source access). It supports keeping the catalogue's granularity (D-P5).
3. **The agent's model of the product.** For each product area the agent needs tools to read and change the data, an explanation of what the data means and how it relates to the rest of the product, and principles for using the feature well. *For HYPRN MVP:* the playbook's field map and workflow carry meaning and principles; they are organised by concern (workflow, field map, style), not by area, which is what decision (a) addresses (D-P2).
4. **System skills, progressively disclosed.** A system skill bundles metadata, a fragment of the system prompt and a set of tools; it is preloaded when the invocation context suggests it (for example a project page) and can be loaded mid-task when the agent discovers it needs it; this keeps threads focused and lets capability grow without bloating every prompt and tool set. *For HYPRN MVP:* the guidance half (metadata and prompt fragment) maps onto playbook sections loaded with `get_playbook`; the tool half would need a tool list that changes during a session, which D-P9 declines for the MCP surfaces.
5. **A short, high-level system prompt** covering communication style adapted to the surface, hard boundaries (including not substantially expanding a request without confirmation), the product's taxonomy, and default opinions on when to infer and when to ask. The article gives no length. *For HYPRN MVP:* the core rules (tooling spec §8.2, §8.3) cover style, boundaries and ask-versus-infer; the product taxonomy and the "do not expand the request" boundary are added by D-P4.
6. **Approval by context, not by tool name.** Whether an action pauses for approval depends on context (deleting something created earlier in the same conversation needs none; deleting an existing issue does; posting to a thread synced with a public repository pauses). *For HYPRN MVP:* assessed once, under "Options not adopted".
7. **Dynamic tool injection that preserves the prompt cache.** Tools of a skill loaded mid-turn are usable in the same turn without discarding the provider's prefix cache. *For HYPRN MVP:* on the MCP surfaces deferral and injection are done by the client (D-P10); on the cloud bridge by the provider's deferred loading (D-P11).
8. **Suspended sub-agent turns.** A parent waiting on a sub-agent appears to make a synchronous tool call; underneath, its turn is suspended and consumes no server resources until the sub-agent finishes. *For HYPRN MVP:* local sub-agents are the client's business; cloud sub-agents are recorded for the bridge (D-P12).
9. **Owned harness.** The team owns the stack above the provider APIs (provider-agnostic client, an agent loop on a durable workflow engine, a streaming layer). *For HYPRN MVP:* not adopted; tooling spec §13.1 and ADR-0004 rule out a model loop and a central orchestrator in HYPRN MVP.
10. The article does not discuss evaluation.

## MCP specification and client support

**Current revision.** The current MCP revision is `2026-07-28` [S2]. Revisions are dated by their last backwards-incompatible change; `Current` revisions can still receive compatible changes, `Final` ones do not [S2].

**What changed against the initialize-based revisions** (`2026-07-28` against `2025-11-25`, [S3]):

- Protocol sessions and the `Mcp-Session-Id` header are removed from Streamable HTTP; list endpoints no longer vary per connection; cross-call state uses explicit server-minted handles passed as tool arguments [S3, S7].
- The `initialize` / `notifications/initialized` handshake is removed: every request carries its protocol version and client capabilities in `_meta`, version mismatches return `UnsupportedProtocolVersionError` (`-32022`) [S3, S4].
- `server/discover` is mandatory for servers and returns supported versions, capabilities, server identity and optional `instructions` [S3, S8].
- The HTTP GET stream and resource subscriptions are replaced by `subscriptions/listen`, a long-lived POST response stream on which opted-in change notifications such as `notifications/tools/list_changed` arrive [S3, S6, S7].
- `ping`, `logging/setLevel` and roots list-change notifications are removed; Roots, Sampling and Logging are deprecated; server-initiated requests are replaced by multi-round-trip `InputRequiredResult`s; every result carries `resultType`; SSE resumability is removed [S3].
- `tools/list`, `prompts/list` and `resources/list` results carry `ttlMs` and `cacheScope`; servers SHOULD return tools in a deterministic order to help client caching and model prompt-cache hit rates [S3, S7].
- `inputSchema` and `outputSchema` accept any JSON Schema 2020-12 keyword and `structuredContent` any JSON value [S3].
- On Streamable HTTP every POST carries `MCP-Protocol-Version`, `Mcp-Method` and (for `tools/call`, `resources/read`, `prompts/get`) `Mcp-Name` headers, checked against the body (`HeaderMismatch`, `-32020`); an unknown method is `404` with `-32601` [S6].
- Unchanged and still required: servers MUST validate `Origin` and answer an invalid one with 403; local servers SHOULD bind to localhost; servers SHOULD authenticate every connection [S6].

`2025-11-25` against `2025-06-18` [S13]: icons on tools, resources and prompts; tool-name guidance (1–128 characters, letters, digits, `_`, `-`, `.`); input validation errors returned as tool execution errors (`isError: true`) rather than protocol errors so the model can correct itself; 403 for an invalid `Origin`; JSON Schema 2020-12 as the default dialect; experimental tasks; URL-mode elicitation; authorization changes. None of these changes the initialize lifecycle that ND-1 relies on.

**Tool annotations.** All annotation properties are hints; clients should never decide tool use on annotations from untrusted servers [S10], and clients MUST treat annotations as untrusted unless the server is trusted [S7, S9]. Defaults when absent: `readOnlyHint` false; `destructiveHint` **true** (meaningful only when not read-only); `idempotentHint` false; `openWorldHint` **true** [S10]. The specification also says a human SHOULD be able to deny tool invocations and clients SHOULD prompt for sensitive operations [S7, S9]; servers MUST validate inputs, enforce access control, rate-limit calls and sanitize outputs [S7].

**Dynamic tool lists.** A server declares `tools.listChanged` and SHOULD send `notifications/tools/list_changed` when its list changes: in `2025-11-25` as a server notification [S9], in `2026-07-28` only to clients that opened `subscriptions/listen` [S7]. In `2026-07-28` the list MUST NOT vary per connection or as a side effect of other requests, but MAY vary by the authorization presented on the request [S7].

**Instructions, resources and prompts.** Server `instructions` are a hint for the model that clients MAY add to the system prompt; in `2025-11-25` they are part of the `initialize` result [S10], in `2026-07-28` part of the `server/discover` result [S8]. Resources are application-driven (the host decides how to include them) with `audience` and `priority` annotations [S12]; prompts are user-controlled, typically surfaced as slash commands [S11].

**Claude Code** [S14]:

- Transports: stdio, `http` (Streamable HTTP; recommended for remote servers), deprecated `sse`, and `ws`.
- Protocol era: two client runtimes; the newer one (MCP TypeScript SDK 2.0) adds revision `2026-07-28`, is the default only in some sessions (from v2.1.274, on several cloud deployments and gateway sign-ins), asks HTTP and stdio servers whether they support the newer revision and connects to other servers as the older runtime does; `MCP_PROTOCOL_NEGOTIATION=legacy` turns the question off; stdio servers are asked by default.
- `list_changed`: in an interactive session Claude Code refetches the list on the notification; a failed refresh keeps the previous tools.
- Tool search is on by default: MCP tool definitions are deferred and only tool names and server instructions load at session start; a tool can ask to load upfront with `_meta["anthropic/alwaysLoad"]: true`; the person configuring a server can set `alwaysLoad` for the whole server. With tool search, the server instructions should say what category of tasks the tools handle and when to search for them.
- Each tool description and each server's instructions are truncated at 2,048 characters by default; key details belong at the start.
- Output: a warning above 10,000 tokens, a default maximum of 25,000 tokens, successful text results above 50,000 characters saved to a file; error results longer than about 11,000 characters keep their first and last 5,000 characters.
- Timeouts: the per-server `timeout` (milliseconds; values below 1000 ignored) overrides `MCP_TOOL_TIMEOUT`, which defaults to about 28 hours; the per-server timeout is a hard wall-clock limit; calls in the main conversation running longer than two minutes move to a background task.
- Root-level `anyOf`, `oneOf` or `allOf` in an input schema is flattened before sending; tools whose schemas fail the API's checks (top-level property names of 1–64 characters, valid 2020-12 schema) are excluded with a logged reason.
- `_meta["anthropic/requiresUserInteraction"]: true` forces a permission prompt on every call of that tool.
- Resources are referenced with `@server:uri` mentions and Claude Code provides tools to list and read them; MCP prompts appear as commands `/server:prompt (MCP)`.
- Project-scope `.mcp.json` servers need approval in interactive sessions.
- Not documented: handling of `structuredContent`, `outputSchema` and `readOnlyHint` / `destructiveHint`.

**Codex** [S16, S17]:

- Transports: stdio and Streamable HTTP; the ChatGPT desktop app, the Codex CLI and the IDE extension support MCP servers and share one configuration per Codex host [S16].
- Server instructions: read from the `instructions` field "returned during initialization" and used as server-wide guidance; the first 512 characters should be self-contained [S16].
- Approval: `default_tools_approval_mode` is `auto`, `prompt`, `writes` or `approve`, with `tools.<tool>.approval_mode` per tool; `writes` prompts for tools not marked read-only [S16]. Calls of tools that advertise a destructive annotation always require approval, and a read annotation takes priority [S17].
- `enabled_tools` (allow list) and `disabled_tools` (deny list); `startup_timeout_sec` defaults to 10, `tool_timeout_sec` to 60 [S16].
- Sandbox: no network and writes limited to the workspace by default; the command network proxy's `allow_local_binding` is false by default and blocks loopback; MCP server connections are not filtered by that proxy [S17].
- Not documented: the MCP revision Codex speaks and whether it probes `server/discover`; prompts and resources; `list_changed`; deferred loading of MCP tools; `structuredContent` and `outputSchema` [S16].

**Skills in the desktop clients.** Both clients read skills only from files: Claude Code from `.claude/skills/<name>/SKILL.md` (project, personal, enterprise, nested, plugin), with descriptions always in context (description and `when_to_use` truncated at 1,536 characters in the listing) and the body loaded when invoked [S15]; Codex from `.agents/skills` between the working directory and the repository root, personal and admin locations, loading names, descriptions and paths first (at most 2 % of the context window, or 8,000 characters when unknown) and the body when used, with an optional `agents/openai.yaml` that can declare MCP server dependencies [S18]. Neither documentation says an MCP server can provide skills; Claude Code says MCP prompts appear as commands [S15].

## MCP era for OQ-3

**Facts.** The current revision `2026-07-28` is "modern" (per-request metadata, no `initialize`, no `Mcp-Session-Id`); `2025-11-25` and earlier are "legacy"; an implementation supporting both is "dual-era" [S4]. A dual-era client on stdio SHOULD first send `server/discover`: a `DiscoverResult` or a recognized modern error means a modern server; any other error, or no answer within a reasonable timeout, means a legacy server and the client falls back to `initialize`; the fallback MUST NOT depend on one error code (legacy servers commonly answer `-32601` or `-32602`) [S5]. On HTTP a dual-era client sends a modern request and falls back on a `400` without a recognized modern error body [S6]. Modern-only clients fail against legacy servers and legacy clients fail against modern-only servers [S4]. Claude Code's newer runtime asks stdio servers for the newer revision by default and otherwise connects as before [S14]; Codex's era is not documented [S16].

**Consequence for ND-1 as planned.** The desktop clients talk stdio to the relay (D-07), so the stdio rules apply to them. An initialize-based `/mcp` that answers `server/discover` (and any request before `initialize`) at once with `-32601` gives a dual-era client the immediate "other error" that triggers its fallback [S5]; answering quickly also avoids the timeout path. The relay must pass that error back unchanged and promptly. ND-1's versions `2025-11-25` and `2025-06-18` are both legacy revisions [S4, S13].

**What the live probe 3.17 must confirm, per client (Claude Code and Codex):**

1. The first message the client writes to the relay (`server/discover` or `initialize`), and for `initialize` the requested `protocolVersion` and the reported client name and version.
2. After the immediate `-32601` to `server/discover`, the client falls back to `initialize`, completes `notifications/initialized`, lists the tools and calls one read tool on the G2 fixture.
3. The negotiated version (`2025-11-25` or `2025-06-18`).
4. Whether the client uses the server `instructions`, surfaces the playbook resources and the `start_study_work` prompt, honours the annotations (Codex's approval on destructive and read annotations; Claude Code's handling) and how it renders `structuredContent` (tooling spec §11.7 items 5 and 7).
5. For Claude Code: whether `_meta["anthropic/alwaysLoad"]` keeps `get_study_overview` and `get_playbook` loaded upfront (D-P10), and whether the per-server `timeout` applies to the stdio entry.
6. With `MCP_PROTOCOL_NEGOTIATION=legacy` (Claude Code), the same session still works (control case).

**What each outcome means:**

| Outcome | ND-1 | D-05 | D-11 |
|---|---|---|---|
| A. Both clients fall back to `initialize` (or start with it) | Confirmed as planned: initialize-only, `-32601` before `initialize` | Unchanged: `Mcp-Session-Id` sessions and session deletion hold | Unchanged: one MCP session per token; a new `initialize` ends the previous session (ND-7) |
| B. A client speaks only the modern era over stdio | Changes: `/mcp` (or the relay) needs a modern path (`server/discover`, per-request `_meta`, `UnsupportedProtocolVersionError`, `resultType`, `ttlMs` and `cacheScope` on lists; on HTTP the `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` headers) | Changes: no `Mcp-Session-Id` in that era; the agent session must be anchored without a protocol session (for example on the token and the relay process), and `preview_ref` becomes an explicit server-minted handle carried as a tool argument with a stated lifetime [S7]; a modern-only HTTP server answers GET and DELETE with 405 [S6] | Changes: "one MCP session per token" and its ending by `initialize` have no protocol anchor; per-session limits (600 API calls, 60 runs) need the new anchor. Whether the era is translated in the relay (which today holds no protocol logic) or served by `/mcp` is a 3.18 choice |
| C. A client cannot connect in either era | Escalation per OQ-3 option C: the plan stops until the product owner approves a change to the client claim | — | — |

## Vendor guidance

**Designing tools.** Anthropic: tools are a contract with a non-deterministic caller and should be designed for agents rather than wrap every endpoint; build a few targeted tools for high-impact workflows, consolidate multi-step operations, avoid overlapping tools, namespace by service and resource, return high-signal fields (names rather than low-level identifiers), offer concise and detailed response formats, paginate, filter and truncate with sensible defaults and steer the agent when truncating, write actionable error messages, describe tools as to a new colleague with unambiguous parameter names and strict data models, and iterate through evaluations on realistic multi-step tasks [S19]. For Managed Agents custom tools: detailed descriptions of three to four sentences (what, when, when not, each parameter, caveats) are the most important factor; consolidate related operations into fewer tools, for example with an `action` parameter; namespace; return only high-signal information [S24]. OpenAI: keep fewer than 20 functions available at the start of a turn as a soft guideline, write clear names, parameter descriptions and when-to-use guidance, use enums and object structure to prevent invalid states, do not make the model fill arguments the code already knows, always enable strict mode (`additionalProperties: false`, every property required, optional as nullable), group tools in namespaces [S26].

**Skills.** Claude Agent Skills are folders with a `SKILL.md` (required `name` of at most 64 characters and `description` of at most 1024 characters that says what the skill does and when to use it) disclosed in three levels: metadata always loaded (about 100 tokens per skill), instructions when triggered (under 5k tokens), resources and scripts as needed; they run in an environment with filesystem access, and skills should come only from trusted sources [S20]. Codex skills follow the same pattern with name, description and path loaded first [S18]; Claude Code skills likewise [S15].

**Managed runtimes and custom-tool bridges.** Claude Managed Agents (beta header `managed-agents-2026-04-01`): an agent holds model, system prompt, tools, MCP servers and skills; event history is stored server-side; not eligible for zero data retention; sessions can be deleted [S23]. Built-in tools (bash, read, write, edit, glob, grep, web fetch, web search) come only with the agent toolset and can be disabled one by one or all by default; custom tools are executed by the application, which returns the result to the session; custom tool names cannot start with `mcp__` or `ant__`; tool outputs above 100,000 characters are written to a sandbox file [S24]. A session can override `model`, `system`, `tools`, `mcp_servers` and `skills` for that session only; a `tools` override replaces the list in full; clearing `tools` is refused while the session has skills, because skills require the `read` tool; agents are versioned and a session can pin a version; sessions take an optional budget [S25]. The OpenAI Agents API session cannot change `tools` or `instructions` after creation (only `model`, reasoning effort and service tier); a session override of `tools` replaces the saved list; instructions plus tool configuration stay below 4 MiB [S28].

**Prompt caching.** The cached prefix runs `tools`, then `system`, then `messages`; changing tool definitions (names, descriptions, parameters) invalidates the whole cache; keep tool definitions stable; the default lifetime is 5 minutes, refreshed on use, with a 1-hour option; an inline-tools beta adds or changes a tool mid-conversation through a `tool_addition` block without editing `tools` [S22]. OpenAI: tools count as input tokens; `allowed_tools` restricts callable tools per request without changing the tool list, which preserves cache savings [S26]; newly discovered tools are injected at the end of the context, and changing the loaded set breaks the cache from that point on [S27].

**Tool search and deferred loading.** Anthropic's tool search keeps deferred tools out of the prefix and appends `tool_reference` blocks inline, so the cache is preserved; tool selection degrades beyond 30–50 tools; use it from about 10 tools or 10k tokens of definitions; keep the 3–5 most used tools non-deferred; at least one tool must stay non-deferred; descriptions and argument names are what search matches [S21]. OpenAI's `tool_search` (from `gpt-5.4`) defers functions marked `defer_loading`, recommends namespaces of fewer than 10 functions, and can run hosted or client-side [S27]. Claude Code applies tool search to MCP tools by default [S14].

## Decisions

### D-P1 (a) The playbook stays one versioned source disclosed in layers, and every tool points to its section

Rationale: Linear discloses guidance per capability, preloaded from context and loaded mid-task [S1], and Claude and Codex skills load a short description first and the body only when needed [S15, S18, S20]; HYPRN MVP already has these layers on every surface: the compact core in the server instructions, the full sections through `get_playbook(section)` (plus resources and the `start_study_work` prompt where the client surfaces them [S11, S12, S14]). What is missing is the mid-task trigger: each tool description ends with one short pointer to the playbook section that governs its fields (for example `edit_model` points to `numerical_models`, `add_evidence` to `field_map`), placed after the key details so the 2,048-character truncation never cuts what matters [S14]. `get_playbook` returns one section within the result cap. Checks: ADR-0003, guidance only, no effect and no right changes; ADR-0004, the playbook is versioned static guidance (`outcome: none`), nothing stored and no orchestration moved to the client.
Status: Binding
Applied by: 3.8 (tool descriptions, `get_playbook`), 3.9, 3.24–3.26, 3.31–3.33 (descriptions of the tools they register)

### D-P2 (a) Re-cut the playbook into area sections, each with a one-line trigger and its tool list

Rationale: Linear's product model needs, per area, the meaning of the data, how it relates to the rest and principles for using it well, bundled as a skill with metadata and tools [S1]; skills are matched on a description that says what and when [S20, S18]. Today's sections are organised by concern (`workflow`, `field_map`, `style`, `numerical_models`, `platform_limits`, `conclusion`, `checklist`), so an agent entering one area (say configurations) must load the whole field map and workflow. Area sections (`approach`, `evidence`, `model`, `configuration_and_runs`, `conclusion`) next to the cross-cutting `workflow`, `style`, `platform_limits` and `checklist`, each opening with a one-line "load when" trigger and the names of its tools, give the same progressive disclosure on every surface with the tool list unchanged (D-P9). The section names are a decided item (tooling spec §4.1 `get_playbook`, §8.1; agents spec §6.1; PD-3.1 and the 3.8 artifact list), so this is put to the product owner; nothing has been built yet, so the change is cheapest now. Checks: ADR-0003, guidance only; ADR-0004, static guidance with no stored outcome. No conflict with either record.
Status: Open question OQ-8a
Applied by: 3.3 (specification text), 3.8 (playbook sections, resources), 3.9 and 3.12 (resource URIs), 3.13 (evaluation of the guidance change)

### D-P3 (a) No client-native skill files in the study folder in this phase

Rationale: both desktop clients read skills only from files in the project or user folders (`.claude/skills/…`, `.agents/skills`) and no documentation lets an MCP server provide them [S15, S18]; shipping the playbook that way would add files to the study folder beyond D-08's closed list, place a second copy of the guidance outside the registry's version and hash stamp (tooling spec §8.4), and is not needed for deferral, because Claude Code already defers MCP tools behind tool search with names and server instructions loaded first [S14] and the playbook is served on every surface by `get_playbook`. Skills are also a trust surface that should come only from trusted sources [S20]. Keeping D-08 as it is stays within the specifications; a later phase may reconsider after the live evaluations (3.30, 3.35) show a need. Checks: ADR-0003, no right changes; ADR-0004, nothing authoritative moves to the client.
Status: Binding
Applied by: 3.16 (study-folder kit stays as specified), 3.36 (recorded as a deferred idea)

### D-P4 (b) Core rules and server instructions: Linear's four areas, tool categories first, within the client limits

Rationale: Linear's short system prompt covers style, hard boundaries (including not substantially expanding a request without asking), the product's taxonomy and when to infer versus ask [S1]; the drafts of tooling spec §8.2 and §8.3 already cover style, boundaries and ask-versus-infer. The final texts add: one line naming the study's record kinds and what each holds (question and approach, model, evidence, configuration, run, conclusion), so the agent knows the taxonomy before it reads the playbook; one boundary line "do what the user asked; ask before adding studies, sweeps or records beyond the plan you stated" (conversation behaviour only, no approval mechanism and no change of rights); and, because Claude Code loads only tool names and server instructions until a tool is searched [S14], the opening of the MCP instructions names the tool categories (orient and read, approach, model, evidence, configurations and runs, conclusion, progress notes and issue reports) and says to search for HYPRN MVP tools by these words. Limits stay: the MCP form under 2,000 characters with a self-contained first 512 [S16] and under Claude Code's 2,048-character truncation [S14]; the cloud form 12–15 lines with `{user_name}` filled per session so the cached prefix stays identical [S22]. The §8.2 and §8.3 texts are drafts, so this stays within the specifications. Checks: ADR-0003, the texts keep stating that the agent never deletes saved work, archives, restores or changes access, and add no approval rule; ADR-0004, guidance only.
Status: Binding
Applied by: 3.3 (records the final texts in tooling spec §8.2 and §8.3), 3.8 (`instructions.SERVER_INSTRUCTIONS`, length tests), 3.16 (study-folder `AGENTS.md` mirrors the boundary line)

### D-P5 (c) Keep task-level tools with one effect and one owner each; no `action`-parameter consolidation

Rationale: Linear's many shallow tools with constraints in their parameters [S1] and Anthropic's advice to build targeted tools for workflows rather than wrap endpoints [S19] match the catalogue as it stands: each tool is one owner's operation or two-phase sequence (Tool ownership table), multi-step protocol work is hidden inside it (preview, digest, rebind), and patch operations inside `update_approach_draft` and `edit_model` are the consolidation that keeps calls few. The Managed Agents advice to merge related operations behind an `action` parameter [S24] is not followed, because one tool would then mix effects (for example read and record), and the effect class drives the route allowlist (ND-4), the annotations (D-P7), the per-stage availability (§4.11) and the ownership check of each `ToolSpec`. No catalogue change. Checks: ADR-0003, effect classes stay per tool so a write can never hide behind a read tool and no human-only effect gains a tool; ADR-0004, each tool keeps one owner and one stored outcome and composes owner operations without orchestration of its own.
Status: Binding
Applied by: 3.8 (registry rules: one effect per `ToolSpec`), 3.9, 3.24–3.26, 3.31–3.33

### D-P6 (c) Tool counts per stage are accepted and measured; descriptions follow the vendor rules

Rationale: with the catalogue, a local session lists 22 tools at the read-only stage (20 reads, progress note, issue report), 33 at the authoring stage for a writer delegation and 38 at the runs stage; read-only delegations keep 22 throughout. That is above OpenAI's soft guideline of fewer than 20 tools at the start of a turn [S26] and inside the 30–50 range where Anthropic reports selection degrading [S21]. Claude Code defers MCP tools by default, so its model sees names only until it searches [S14]; Codex documents no deferral [S16]. The registry therefore keeps the counts, and the evaluation records wrong-tool and unknown-tool calls per client as a tracked metric (G1, G2) so a later catalogue change rests on evidence. Every description follows one pattern: what the tool does, when to use it and when not, what each parameter means, caveats, then the playbook pointer (D-P1); three to four sentences or more, key facts first, under 2,048 characters [S14, S19, S24]; parameter names unambiguous (`model_version_id`, not `version`) [S19]; enums and closed objects for invalid states [S26]; names stay `verb_object` within the MCP name rules [S7, S13]. No root-level `oneOf`, `anyOf` or `allOf`, which Claude Code flattens [S14] and tooling spec §11.3 forbids for the bridge, and top-level property names of 1–64 characters [S14]. Checks: ADR-0003 and ADR-0004 unaffected (descriptions and metrics only).
Status: Binding
Applied by: 3.8 (description and schema lint tests), 3.13 (tracked metric in the runbook and graders), 3.30, 3.35

### D-P7 (c) Every tool carries explicit annotations

Rationale: when annotations are absent MCP defaults are `destructiveHint` true and `openWorldHint` true for a non-read tool [S10]; Codex always asks approval for a tool advertising a destructive annotation, and its `writes` mode prompts for every tool not marked read-only [S16, S17]. Leaving the hints implicit would mark every write, including additive ones, as destructive and open-world. Each `ToolSpec` therefore emits all four hints: read tools (including `validate_model` and `preview_configuration`) `readOnlyHint: true`; every other tool `readOnlyHint: false`, `idempotentHint: false` (repeats are safe only through journaled command ids, which the client cannot see), `openWorldHint: false` (the domain is the one study and installation), and `destructiveHint: true` exactly for the ND-13 set (`update_study_context`, `restore_approach_draft`, `update_approach_draft`, `edit_model`) and `false` for the additive writes. Annotations are hints that clients must not trust as authority [S7, S10]; HYPRN MVP's own authorization never reads them. This complements ND-13 and §11.2 without changing them. Checks: ADR-0003, annotations only add client friction and never widen rights; ADR-0004, no state involved.
Status: Binding
Applied by: 3.8 (`ToolSpec.annotations` and a test that every tool emits all four), 3.17 and 3.19 (client handling recorded in §11.7 item 7)

### D-P8 (c) No vendor approval-forcing metadata on HYPRN MVP tools

Rationale: Claude Code offers `_meta["anthropic/requiresUserInteraction"]` to force a prompt on every call of a tool [S14], and MCP recommends a human able to deny invocations [S7]. HYPRN MVP's rights do not depend on any prompt (ADR-0003 §7: client and provider approvals never widen rights; confirmation stays retired); the client's ordinary prompts stay as extra friction (tooling spec §11.4), and PD-3.3 already sets Codex to `writes`. Forcing a prompt per call would reintroduce a confirmation step through the client for no change in what an agent may do. Checks: ADR-0003, rights stay with the delegation and the human-only classification; ADR-0004, unaffected.
Status: Binding
Applied by: 3.8 (no such `_meta` key emitted), 3.16 (generated client settings unchanged)

### D-P9 (d) One fixed, deterministically ordered tool list per MCP session; no list changes during a session

Rationale: changing tool definitions invalidates the whole provider cache [S22], and changing a loaded set breaks it from that point [S27]; MCP asks for a deterministic `tools/list` order for client and prompt caching [S3, S7] and lets the list vary by the authorization presented but not per connection [S7]. The registry computes the list once per MCP session from the surface, the registry version (stage), the delegation's effects and the advertised capability gates (§4.11), returns it in registry order with byte-stable definitions within a registry version, and declares `tools.listChanged`, `prompts.listChanged` and `resources.listChanged` false. A capability gate or stage changes only with a release, which starts new sessions. Linear's skill-driven tool injection [S1] is therefore not reproduced on the MCP surfaces: D-05's JSON-only responses give no stream for a legacy `list_changed` notification, the modern era needs `subscriptions/listen` [S7], and Codex documents no handling [S16]; deferral is left to the clients (D-P10). This stays within §4.11 and §11.2. Checks: ADR-0003, the list is a view of rights decided elsewhere and can only narrow them; ADR-0004, the registry holds no per-session tool state beyond the delegation it already reads.
Status: Binding
Applied by: 3.8 (`Registry.definitions` determinism test, tool-definitions hash), 3.12 (capabilities in the `initialize` result), 3.29 and 3.34 (stage changes only through registry versions)

### D-P10 (d) Deferred loading stays with the clients; the two entry tools load upfront in Claude Code

Rationale: Claude Code defers MCP tools behind tool search by default and lets a server mark a tool to load upfront with `_meta["anthropic/alwaysLoad"]: true` [S14]; Anthropic recommends keeping the most used tools non-deferred [S21]. The instructions make `get_study_overview` and then `get_playbook` the mandatory first calls (§8.3), so these two carry the always-load flag and every other tool is left to the client's search, which the server instructions steer with the tool categories (D-P4). The flag is ignored by clients that do not know it; the probe records whether Claude Code honours it (MCP era item 5), and the flag is dropped if it is not honoured. Adding a `_meta` key changes no decided item of §11.2. Checks: ADR-0003 and ADR-0004 unaffected (loading only).
Status: Binding
Applied by: 3.8 (tool metadata), 3.17 and 3.19 (verified and recorded)

### D-P11 (e) Cloud bridge: stable versioned agent definitions, deferral by the provider, no provider skills while built-in tools are off

Rationale: recorded for the cloud-bridge work and not built here. Tool changes invalidate the provider cache [S22]; Managed Agents agents are versioned, a session can pin a version, and a session override replaces the tool list in full [S25]; OpenAI Agents API sessions cannot change tools or instructions after creation [S28]. The bridge therefore keeps one agent definition per (provider, registry version, profile) with tools in registry order and pins sessions to that version; per-delegation narrowing uses the session-override `tools` field only if the parity evaluation shows the cache cost is acceptable, otherwise a separate definition per profile; a tool list above the selection thresholds of the sources (fewer than 20 at the start of a turn [S26]; degradation beyond 30–50 [S21]) uses the provider's deferred loading (`defer_loading` with tool search, 3–5 tools non-deferred [S21]; `tool_search` namespaces of fewer than 10 functions [S27]) or `allowed_tools` per request [S26], never a tool list that changes mid-session. Provider skills are not used: Managed Agents skills require the built-in `read` tool [S25] and run with filesystem access [S20], while agents spec §4.3 disables every built-in tool; the playbook stays a HYPRN MVP tool. Custom tool names must avoid the `mcp__` and `ant__` prefixes [S24]. Checks: ADR-0003, the bridge executes every call through the same registry and delegation, and provider approvals never widen rights; ADR-0004, the provider holds interaction state only, and outcomes stay with the owners behind the API.
Status: Binding
Applied by: the cloud-bridge phase (tooling spec Stage 4), after the refresh required by "Deferred work and entry criteria"

### D-P12 (e) Sub-agents act only through the same bridge and delegation; read-only by default

Rationale: Linear suspends a parent's turn while a sub-agent works [S1] and Managed Agents supports sub-agents declared on the agent (`subagents` with predefined agents) [S24]; ADR-0004 keeps read-only sub-agents and research helpers open. For the cloud, any sub-agent's HYPRN MVP tool calls arrive through the same bridge, under the parent session's delegation, journaled with the same agent actor; a sub-agent gets read tools only unless the product owner decides otherwise when the bridge is planned; no sub-agent receives a HYPRN MVP credential. Locally, sub-agents are the desktop client's own feature and use the same MCP session and token, so nothing changes. Checks: ADR-0003, no new principal and no wider rights; ADR-0004, the sub-agent's work is interaction state and every effect remains an owner operation with its own stored outcome.
Status: Binding
Applied by: the cloud-bridge phase (recorded); no Phase 3 task

## Open questions for checkpoint 3.2

| ID | Question | Recommended default | Alternatives | Specification sections and tasks affected |
|---|---|---|---|---|
| OQ-8a | Should the playbook be re-cut into area sections (`approach`, `evidence`, `model`, `configuration_and_runs`, `conclusion`) next to the cross-cutting `workflow`, `style`, `platform_limits` and `checklist`, each opening with a one-line "load when" trigger and its tool names (D-P2)? | A: adopt now, before 3.8 builds the playbook constants; the field-map rows move into their areas; the tool list stays fixed (D-P9) | B: keep the seven sections as specified and rely on the tool-description pointers of D-P1 only | Tooling spec §4.1 (`get_playbook`), §8.1; agents spec §6.1; `docs/agents/playbook.md`; PD-3.1; tasks 3.3, 3.8, 3.9, 3.12, 3.13 |

## Options not adopted

- **Approval by context as the authority for an effect.** Linear decides per context whether an action pauses for user approval [S1]. HYPRN MVP does not adopt it: client and provider approvals never widen rights and confirmation stays retired (ADR-0003 §7); what an agent may do is decided by the delegation, the role ceiling and the closed human-only classification, on every call. The case Linear uses to motivate it, removing something the agent itself just created, is already a direct `draft` effect under the draft rule (ADR-0003 §3): draft content may be changed or removed under revision checks, while saved records are never deleted by an agent.
- **Raw API, SDK or code access for agents.** Linear rejected direct SDK, GraphQL, CLI and code-environment access for predictability [S1]; HYPRN MVP already excludes it (D-01, the local boundary).
- **An owned agent loop or durable workflow engine in HYPRN MVP.** Linear owns its harness [S1]; HYPRN MVP never runs a model loop (tooling spec §13.1) and ADR-0004 rules out a central orchestrator.
- **Per-skill tool injection on the MCP surfaces** and **`action`-parameter tools**: see D-P9 and D-P5.

## Cloud bridge implications

Decisions D-P11 and D-P12 are the decision (e) record. Before the cloud-bridge work is planned, this research is refreshed from the primary sources with new access dates, and the following findings are re-checked first:

1. Managed Agents status and beta header, session overrides of `tools` and `skills`, agent versioning and pinning, whether an agent with custom tools only needs an environment or sandbox, and data retention [S23, S24, S25]; tooling spec §11.7 items 1 and 2.
2. Whether Managed Agents skills still require the built-in `read` tool [S25], which decides whether the playbook can ever be a provider skill.
3. OpenAI Agents API: whether tools and instructions become updatable on a session, the 4 MiB limit, multi-agent settings, and `tool_search` support in that API [S27, S28]; tooling spec §11.7 items 3 and 4.
4. Prompt-caching rules for tool definitions and the inline-tools beta [S22], and the deferral rules and thresholds of both providers [S21, S27].
5. Sub-agent features of both runtimes and how their tool calls reach the application (D-P12).
6. The MCP revision then current, for the remote-MCP fallback: sessions, `server/discover`, `subscriptions/listen`, authorization changes [S3, S6].
7. The tool-count and selection-accuracy figures [S21, S26] against the cloud tool list at that stage.
