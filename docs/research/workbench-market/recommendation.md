# Workbench market study — recommendation

Research date: 2026-10-12. Status: **research recommendation, proposed, not decided.** It synthesises three reports, each with licences verified from the current LICENSE files (read through the GitHub API on 2026-10-12) and dated sources:

- [Engineering workbench platforms and capability map](engineering-workbench-platforms.md)
- [Workspace, collaboration, documents and canvas foundations](workspace-collaboration-canvas.md)
- [Assistant and chat layer](assistant-chat-layer.md)

Criteria: (1) do not duplicate what WhatsOpt, OpenMDAO and AiiDA provide; (2) open source under a permissive licence with unrestricted commercial use; (3) genuinely faster than building it ourselves. Target: a home with workspaces and settings; workspaces holding studies, documents and collaboration; a study workbench with the HYPRN MVP screens, a canvas and an assistant (an OpenAI or Claude managed agent).

The decisions that depend on this study are recorded in the UI target specification (`docs/specs/ui-target.md`), the agents specification (`docs/specs/agents.md`) and the licensing record (`docs/legal/licensing.md`).

## 1. Answer

There is no open-source base that would play for an engineering workbench the role a forked editor plays for a coding IDE. Every whole-platform candidate fails at least one criterion:

- notebook platforms (JupyterHub/Lab, AiiDAlab, marimo, Renku) run arbitrary user code, bypassing the attested worker and the HYPRN MVP API;
- workflow platforms (Galaxy, pyiron, RCE, SimStack) duplicate AiiDA; GEMSEO and CoSApp duplicate OpenMDAO;
- model-graph tools (Sirius Web, SysON) would be a second editable model graph;
- IDE shells (Theia, VS Code forks) impose a file and code workflow and fight the design system;
- every real workspace application worth forking (AppFlowy, Plane, Docmost, Twenty, Outline, AFFiNE's backend) is AGPL, BSL or paid.

The commercial market (ESTECO VOLTA, Optimus, 3DEXPERIENCE, HEEDS, Rescale, PhysicsX, Ansys 2026 agents and others) converges on what HYPRN MVP already is: a governed project and data hub first, deterministic numerical workflows, scoped assistants that propose changes for explicit human approval, and the report as the deliverable. That validates the architecture; it does not offer a base to adopt.

The fastest route is therefore to **build the thin domain shell on the current stack, adopt a small set of permissive engines for the hard generic parts, and surface what WhatsOpt, OpenMDAO and AiiDA already produce instead of rebuilding it.**

## 2. Buy and build map

| Need | Recommendation | Choice | Licence | What it saves |
|---|---|---|---|---|
| Home, workspaces, studies, settings, members | **Build** on React (design system) + FastAPI | HYPRN MVP records and screens | — | Nothing permissive exists without duplicating HYPRN MVP's API, auth or records; the shell is thin over existing domain screens |
| Sign-in, SSO, MFA, organisation invites (cloud) | **Adopt when going multi-tenant** | Keycloak 26+ Organizations, Authlib in FastAPI, Keycloakify for themed login | Apache-2.0 / BSD-3 / MIT | Months of identity and SSO work. HYPRN MVP keeps its own session, CSRF and workspace and study memberships |
| Hierarchical permissions | **Defer** | Start with one `can(user, relation, object)` check over the current tables; OpenFGA when organisation → workspace → study → document inheritance arrives | Apache-2.0 | Avoids a second permission store until it is needed |
| Source documents (uploaded PDFs, papers, datasheets: store, collections, read, annotate, cite, extract) | **Reuse underneath, as planned** | The source-documents design on AiiDA (SinglefileData versions, Groups as collections, QueryBuilder, extraction processes with provenance) | MIT | Nothing here replaces it; Yjs and Tiptap do not store files or provenance |
| Authored documents (study reports, memos written in the app) and live co-editing | **Adopt only when needed** | Tiptap core as the editor once authored reports exist; Yjs + pycrdt-websocket (Hocuspocus as fallback) only when several people edit the same text at once in the cloud | MIT | The rich-text editor and real-time sync. A finished or cited text is frozen into a HYPRN MVP evidence version (and can be stored in AiiDA as a file), so live editing never becomes a second source of truth. Comments and review threads are HYPRN MVP records (Tiptap's comments and history are paid) |
| Canvas | **Adopt** | xyflow (React Flow) + dagre; XDSMjs for XDSM views; Excalidraw only if a free whiteboard is truly needed | MIT / MIT / Apache-2.0 / MIT | The canvas engine. Every structural edit becomes a typed, revision-checked command to the modeling service, never a second graph |
| Workbench docking panels | **Adopt, pinned** | dockview core inside one HYPRN MVP layout component; FlexLayout as fallback | MIT | Docking, tabs, splits. dockview moved advanced features into a paid package on 2026-07-07, so wrap it to stay replaceable |
| Assistant panel | **Adopt primitives, build cards** | assistant-ui unstyled primitives styled with the design system; AG-UI events over HYPRN MVP's own authenticated SSE | MIT / MIT | Streaming chat, tool-call display, threads. Proposal cards and confirmation stay HYPRN MVP components and routes |
| Managed agent runtime | **Buy (provider)** | Claude Managed Agents or OpenAI Agents API, built-in sandbox off, HYPRN MVP tools as custom or function tools (the custom-tool bridge of `docs/agents/tooling-spec.md`) | Provider terms | The agent loop and sessions. An MIT AG-UI adapter exists for Claude Managed Agents; HYPRN MVP writes a small one for OpenAI |
| Model diagrams, reports, results views | **Reuse underneath** | OpenMDAO N2, reports and CaseViewer generated in the restricted worker and kept as AiiDA artifacts, shown in a sandboxed frame; AiiDA provenance through the HYPRN MVP API; WhatsOpt exports | Apache-2.0 / MIT | Rebuilding viewers OpenMDAO already ships |
| Notebooks, 3D fields, SysML exchange | **Defer** | JupyterHub or marimo as an isolated add-on, Kitware trame, SysON — each only on an explicit trigger | Various | — |

Rejected for the assistant: OpenAI ChatKit (closed CDN script, OpenAI domain key, cannot render HYPRN MVP components), Open WebUI (branding clause), LobeChat (commercial licence for derivatives). CopilotKit is kept only as a fallback (paid "Intelligence" tier, install telemetry).

Licence drift to watch: dockview enterprise (2026-07), tldraw 4.0 licence keys (2025-09), Permify to AGPL (2025-05), ZITADEL AGPL since v3, Ory and SuperTokens multi-tenancy paid, Liveblocks server AGPL, y-redis AGPL.

## 3. A finding that affects criterion 2 directly: WhatsOpt is AGPL-3.0

- WhatsOpt's repository licence is GNU AGPL v3; its frontend package says UNLICENSED; WhatsOpt-CLI is Apache-2.0.
- HYPRN MVP runs a **patched** WhatsOpt as its private modeling service. Those patches are in AGPL compliance scope (notices, corresponding-source obligations), and container or HTTP separation is not legal clearance.
- The native OpenMDAO code templates carry no generated-code exception, and their emitted bodies are substantive, so the licence status of generated model code is unresolved.

Consequence: the cloud product cannot meet "permissive, no constraints" while the modeling service is WhatsOpt, unless counsel concludes otherwise. The architecture anticipates this: WhatsOpt sits behind the independently authored Modeling Backend Contract as a replaceable service. Recommendation, consistent with the licensing record: get a legal review of the AGPL obligations before any commercial cloud launch, and in parallel scope a permissive replacement modeling backend (composition, XDSM, OpenMDAO code generation on Apache-2.0 OpenMDAO, with XDSMjs for diagrams) behind the same contract. This is not legal advice.

## 4. Recommended order of work after the local edition

1. Local edition and the agent tool server (the local stages of `docs/agents/tooling-spec.md`).
2. Legal review of WhatsOpt AGPL and the decision on a replacement modeling backend.
3. Cloud foundations: Keycloak behind HYPRN MVP authentication, workspace records and screens, the `can()` check.
4. Study workbench: dockview layout hosting the existing screens, assistant panel (assistant-ui + AG-UI), managed-agent bridge.
5. Authored documents and presence (Yjs, Tiptap, pycrdt-websocket), with comments and review as records.
6. Canvas on xyflow, wired to typed modeling commands.

Every new dependency still goes through the provenance and licence review (source, version, hash, licence; permissive licences only) before install.
