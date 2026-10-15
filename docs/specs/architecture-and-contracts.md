# Architecture and contracts

Status: current specification. It states what HYPRN MVP is, what it must guarantee, who owns what and the rules every contract follows. Wire detail lives in `contracts/` (JSON Schema 2020-12 and the generated OpenAPI 3.1 document `contracts/hyprn-mvp.openapi.yaml`); if this text and a schema disagree on a field, the schema governs and this text is corrected. Decisions here change only through an ADR in `docs/adr/`.

Companion specifications, which must respect the rules below:

- agents: `docs/specs/agents.md`, with the tool detail in `docs/agents/tooling-spec.md` and the working rules in `docs/agents/playbook.md`;
- source and authored documents: `docs/specs/documents.md`;
- workspaces, identity and onboarding: `docs/specs/workspaces-identity-onboarding.md`;
- user interface: `docs/specs/ui-target.md`;
- requirements catalogue: `docs/specs/requirements.md`;
- licences and obligations: `docs/legal/licensing.md`;
- glossary of record: `CONTEXT.md` (section 5 below states the same terms).

Requirements covered: HUM-01 to HUM-06, HUM-09, VER-01 to VER-04, RUN-01 to RUN-04, RUN-08, SCI-01 to SCI-03, CRIT-01, OPS-01 to OPS-03, SEC-01, ADOPT-01 to ADOPT-03 (`docs/specs/requirements.md`).

## 1. Product purpose

HYPRN MVP is an engineering feasibility workspace. An engineer states a question, collects evidence, explains a modeling approach, builds an executable model from Python components, runs it on explicit cases, inspects recorded results with the exact basis they were computed on, and reaches a conclusion whose scientific basis is visible. An agent can perform the same operations for the engineer, within an explicit delegation, with every change attributed to the agent acting for that engineer.

Core value: an engineer can build and understand a model, run it with explicit inputs, inspect the evidence behind its results and refine it, without needing an agent or a custom-built modeling platform.

HYPRN MVP reuses established tools for the hard parts: a private modeling service (initially a patched WhatsOpt) for composition and code generation, OpenMDAO for numerical computation, AiiDA for execution lifecycle and retained artifacts, OpenTURNS (later) for uncertainty. HYPRN MVP owns the domain, API, UI, authorization, scientific context and the honesty of what is shown.

The first journey is human and manual: create a study, author two connected components, inspect them, set inputs, validate, run, inspect values, change something, rerun, reopen the earlier run unchanged. Reference fixture: `u = 2*x + z`, `y = u*u` with `x = 2`, `z = 3` gives `u = 7`, `y = 49`. Fixtures are authored through normal operations; nothing domain-specific is hard-coded.

## 2. Scientific guarantees

Product invariants. Every component, client, agent tool and refactoring preserves them.

| Guarantee | Meaning |
|---|---|
| Real scalars | Quantities are finite real scalars. Non-finite numbers, booleans posing as numbers and unsafe integers are rejected at every boundary. Arrays are optional future scope. |
| Explicit inputs and provenance | Every free input is supplied in the configuration with units and provenance (manual, or a source with exact evidence versions), or as an exact binding to a retained run output. Empty differs from zero. Missing inputs are actionable errors, never filled in. |
| Exact pins | Configurations pin exact model versions; model versions recursively pin definition versions and exact source bytes; runs freeze configuration, model snapshot, context, evidence, generated program, dependencies and runtime identities. Display names, collections or tags never pin history. |
| No hidden defaults | No hidden physical defaults, implicit conversions, broadcasting, randomness or cross-case state. Unsupported settings are rejected, never ignored or approximated. Internal unavailable sentinels are never physical defaults. |
| Unavailable is not zero | An output is available only if its producer completed normally, actually assigned it, and the value is finite; otherwise its value is `null` with a reason. Upstream outputs are kept when a downstream component fails. |
| Separate outcome facets | Current explicit scalar results record execution, per-output value/availability/reason and criterion outcome. They omit aggregate convergence, optimization, completeness and applicability. Exact historical records retain their fields; public views omit them with explicit source/view identities. Future computed facets remain separate: "recorded" is not success, and a met criterion is not validity. |
| Immutable history | Saved versions never change. Historical reads use retained records only and never substitute the current model, configuration or evidence. |
| One authoritative outcome | An operation produces one authoritative outcome that every client can subsequently reference, inspect and act upon, without reconstructing or repeating the operation (section 3.1, ADR-0004). |
| Units | Conversion happens once, in OpenMDAO inside the worker. The API admits only linear conversions listed in an engine-generated catalog; affine conversions are rejected. Each port declares physical (one supported spelling), dimensionless or unspecified units. Unspecified units may be saved, but commit, preparation and execution require resolved units for every port in the selected executable closure. |
| No code execution outside the worker | Save, import, static validation, preview and preparation never import or execute candidate code. |
| Honest partial results | Missing or corrupt artifacts are explicit partial errors; unreachable execution leaves visibly pending work, never a fictitious result. |

For uncertainty (later), the same honesty applies: retain actual draws, paired outputs, failed attempts and disjoint terminal classes; with N cases, s evaluable, k successes and u = N - s unresolved, show k/s only when s > 0 plus [k/N, (k+u)/N] as generated-ensemble bounds, never as a confidence interval; Sobol indices only for independent inputs on a complete structured design.

## 3. Component ownership

```text
Custom UI ───────────┐
Agent tool surface ──┼── HYPRN MVP API (/api/1)
Other clients ───────┘        │
                       HYPRN MVP application
                       │                  │
          Modeling Backend Contract    Execution integration
               (/modeling/1)              │
                       │               AiiDA
          Private modeling service        │
          (WhatsOpt + adapter)         Restricted worker (OpenMDAO; OpenTURNS later)
```

One cohesive Python application holds API, application logic and execution integration. The modeling service and the restricted worker are separate deployment units. No further microservices.

| Owner | Owns | Must not own or reach |
|---|---|---|
| Application | API, authentication, authorization; studies, workspaces, memberships; evidence and assumptions; Modeling approach; configurations; receipts and run associations; execution bundle assembly; historical reads; agent sessions, action journal and tool registry; document families (bytes in AiiDA) | A second editable graph, scheduler or provenance store; candidate imports; native payloads in public contracts |
| Modeling service (WhatsOpt + adapter) | Editable composition, definitions, instances, ports, connections, source; immutable model and definition versions; model-local annotations; static OpenMDAO generation; prepared artifacts | Application or AiiDA databases; launcher or container socket; provider credentials; candidate execution (routes disabled) |
| AiiDA (via execution integration) | Process lifecycle; retained bundles, results, artifacts and provenance; document bytes and collections | Study catalog; authorization inferred from native IDs or extras |
| Restricted worker | Runs the exact frozen generated program through a generic harness | Rebuilding the model from JSON; silent fallback; network, secrets, modeling access |
| OpenMDAO | Units, solvers, derivatives, optimizers during execution | (HYPRN MVP never writes a replacement) |
| OpenTURNS (later) | Joint sampling and uncertainty methods | — |
| Browser | Rendering, selection, unsaved buffers | Authorization; authoritative outcomes |
| Managed agent runtime | Reasoning loop and conversation | Scientific authority; store access; operation lifecycles; deletion of saved records, archive, restore or access changes |
| Platform | Installation, configuration and secrets, host executor, backup and recovery | Scientific policy |

Model-local annotations (description, short assumption text) may live with the model; claims, citations, document locations, applicability and evidence belong to the application, scoped by stable element identities. HYPRN MVP may keep immutable model snapshots and disposable caches, never an editable copy of the graph.

**Native generation.** Model commands go to the adapter, which translates them to the native representation. The pinned native generator emits OpenMDAO source statically (no import, discovery or setup). The adapter packages it with exact identities and hashes as a prepared model artifact; the application assembles the execution bundle; the worker loads the generated Group through a fixed entrypoint and never reconstructs topology. No second generator, no fallback. Generation targets an exact committed version and configuration, never a draft; any native materialization is per-request, derived and discarded.

**Replaceability.** Replacing WhatsOpt changes only the modeling-service implementation, its deployment configuration and its data migration, never clients, provided contract version, capabilities and behavior are preserved. Readiness is shown by the independently authored contract, export/import round trips, backend-independent contract tests and numerical-equivalence checks, not by a second production backend. Historical artifacts stay readable without either backend.

### 3.1 Unified operations and explicit ownership

Decided (ADR-0004, `docs/adr/0004-operation-ownership.md`).

**Central invariant.** An operation produces one authoritative outcome that every client can subsequently reference, inspect and act upon, without reconstructing or repeating the operation.

The rest of this section is how the invariant is upheld.

**Principle.** All HYPRN MVP capabilities are exposed through one consistent application API (`/api/1`), whether users, agents or other clients invoke them. Every shared resource has a single authoritative owner responsible for its state and lifecycle. Operations that require durable coordination expose stable identities and observable outcomes. Agents and clients may freely compose capabilities, but must not independently manage authoritative state, duplicate business orchestration or re-execute operations to reproduce shared results. The application delegates execution and persistence to the appropriate domain owners and avoids parallel representations of authoritative state. The agent decides what to do; the platform owns what actually happened.

**When an operation needs its own identity and lifecycle.** Not by counting steps or stores: an operation gets a command with a receipt, or an operation resource its owner advances (202 for accepted work), when it requires shared identity, durability, consistency, observability or recovery. Reading several records to prepare an edit needs none of this; a single run submission or upload completion does.

**Three kinds of state.**

| Kind | Owner |
|---|---|
| Domain state: studies, memberships, archive state, approach, configurations, evidence and citations, document identity and associations, model references, command receipts and run associations, agent sessions and the action journal | The application's domain modules (section 7), one owner per resource |
| Execution state: model composition and versions; process lifecycle, results, artifacts and provenance; document bytes, collections and extraction results | The modeling service for models; AiiDA, through execution integration, for processes, results, artifacts and document storage; OpenMDAO in the worker for computation. HYPRN MVP keeps stable references, associations, command and dispatch receipts and a projection of execution status, never a parallel execution state machine |
| Interaction state: conversation, an agent's plan, unsaved browser edits, temporary exploration | The client or agent holding it; never authoritative |

Command receipts comply: they record a command's intent and the reconciliation of its dispatch (section 6.6), so launches stay unique and recoverable, while the AiiDA lifecycle stays authoritative in AiiDA and is projected separately for display.

**Responsibilities.** Business resources, authoritative state and business operation lifecycles: domain modules. Execution of multi-step workflows across components: application and domain services behind the API, delegating to the engines. Reasoning and planning: the agent (or the person). Routing, authentication and transport: the API edge (the application's HTTP layer, plus the edge proxy in the cloud; no separate gateway with its own store). Presentation and ephemeral interface state: the frontend.

**Checkable consequences.**

- Every tool or API operation that needs shared identity, durability, consistency, observability or recovery names its single owner and produces a stored outcome with a stable identity that any client can read back.
- No client or agent duplicates business orchestration: it keeps no outbox, compensation or rollback of its own; if stopping between two of its calls would leave stores inconsistent, that coordination belongs to a server owner.
- Results are read from their stored resource (run, extraction attempt, operation, export); running again is an explicit new command that creates a new resource.
- After a lost reply a client reads the owner's receipt or operation resource and never resends a command whose outcome is unknown.
- No new HYPRN MVP state duplicates an engine's authoritative state. Projections (search index, status projection, cached reads) are rebuildable and never the source for authorization, quotations, writes or history.
- Nothing a server component or another client depends on lives only in a client.
- The agent tool registry runs in the application process but is a client of the API under this rule (section 4.6).

**Not mandated:** a single physical backend or database; a durable workflow for every operation; a central orchestrator for agent activity; re-implementing what OpenMDAO, AiiDA or the modeling service already provide.

The rule constrains agent tool design without fixing it: iterative read loops, sub-agents within the agent rules, progressively loaded skills and tool sets, tool granularity and provider bridges stay open. Plans that add agent tools or document operations trace their checks to the central invariant: each such tool or operation names its owner and stored outcome, and no planned client flow manages authoritative state, duplicates orchestration or re-executes to reproduce a result.

## 4. Trust boundaries and security invariants

### 4.1 Units, credentials, networks

| Unit | Holds | Network |
|---|---|---|
| Application | Application store; read-only model-service credential; session secrets | Client listener (loopback locally; behind an edge proxy in the cloud); private link to modeling |
| Modeling service | Own store, service key, framework secret | Private network only |
| Trusted host executor | AiiDA profile and repository; authority to start workers | No inbound listener; bounded framed bridge to the application |
| Restricted worker | Read-only frozen input; bounded scratch and output | None |

Containers run as fixed non-root users, read-only root, dropped capabilities, no-new-privileges, bounded CPU, memory and processes. No writable directory is shared by all components. The executor's container authority is root-equivalent and trusted as such. All databases, artifacts, logs and scratch live under one data root outside source repositories and cloud-synced folders; a synced data root is refused. The data root is resolved as command-line flag → `HYPRN_MVP_*` environment variable → installation configuration → per-OS default (an application-data folder named `hyprn-mvp`) → otherwise the user is asked.

### 4.2 Execution security

- Candidate code is imported only in the restricted worker, after checking the current attestation of target, image, launcher and policy. Any change to these or to the attested source set invalidates it; execution is refused until containment is re-verified.
- The attested source set is exactly the static import closure of the launcher, calculation and results modules plus deployment inputs, enforced by a two-sided coverage test; dynamic loading is banned there.
- Worker containment: non-root, read-only input and root, no network, socket, home or secrets, bounded CPU, memory, processes, wall time, files and output. Fixed entrypoint; launcher-owned paths.
- Admission is independent at each boundary: the application checks the prepared artifact and assembles the bundle; launcher and worker each re-admit it (paths, sizes, hashes, version, identities) before any import.
- Bundles are self-contained; workers never contact the modeling service. Worker output is untrusted and parsed with bounds, no executable deserialization, and identity and hash checks.
- AiiDA launches are never retried on lease expiry, disconnect, a `created` process or an absent lookup. Exactly one matching process may be adopted; otherwise the run is `uncertain`. Old or uncertain jobs are never dispatched automatically.

### 4.3 Public authentication and authorization

- Browser sessions: HttpOnly, SameSite=strict cookie (Secure over HTTPS), exact Origin, `X-CSRF-Token` on mutations; only HTTPS or an explicit loopback development origin. Scrypt password hashes, no default password, initial credential written once to an owner-only file and never logged; recovery is a local operator command that revokes all sessions.
- Every operation authorizes actor, study and resource, including reads, exports and receipt replay. Replay requires current permission. Scoped 404 where enumeration matters.
- Studies are archived and restored, never deleted. Removing a resource referenced by retained history is refused.
- Target: OWASP ASVS Level 1, high-severity items mandatory.

### 4.4 Private modeling authentication

Calls carry a separate service credential and an authenticated scoped envelope `{actor_id, study_id, resource_ids, permissions, expires_at, request_id}` bound to method, full path, body hash and a short expiry. The service checks resource-to-study binding, permission and expiry itself and rejects identity headers.

### 4.5 Bounds

Advertised as policy through capabilities: JSON body 2 MiB; source file 256 KiB; 256 edits per batch; 1,000 elements per model; nesting 32; export or import 32 MiB expanded. Duplicate keys, unknown properties, non-finite numbers, unsafe paths, unsupported schemas and oversized or deep data are rejected before mutation. Archive members that are absolute, contain `..`, duplicate, symlink, hardlink or device are rejected.

### 4.6 Agents as principals

- An agent is its own actor acting for a human under a delegation (scope, role ceiling, allowed effects, budgets, expiry). Effective authority is the intersection of the live delegation, the delegator's current membership and the ceiling, rechecked on every call. Agents never grant access, delegate, mint tokens or raise their ceiling.
- Agents use only a curated, provider-neutral tool registry that calls the HYPRN MVP API in-process with a short-lived delegated session (same middleware, schemas, receipts, errors as the UI). No raw API passthrough, no store, modeling, AiiDA or executor access, no shell, file or web tools. `study_id` is never a tool argument.
- Write policy (ADR-0003, `docs/adr/0003-agent-write-rights-revised.md`): agents write directly within the delegating human's current authority and the role ceiling, including creating studies (the delegating human becomes Owner) and recording scientific reviews (labelled agent-recorded). Every agent write is attributed ("{agent} for {user}") and journaled, and overwrites need the agent's last-read revision. Draft (mutable working) material, such as draft content or a working annotation, may be changed or deleted under revision checks; a saved, versioned or read-only record is never deleted by an agent. Human-only on every surface: deleting saved records (collections included), archiving and restoring studies and documents, and access management (memberships, invitations, delegations, tool tokens, roles). No tool offers these effects and the agent route allowlist refuses them. Provider or client approvals never widen what an agent can do. Run submissions stay bounded by the run limits, budgets and kill switches, and a submission whose configuration is not ready to run is refused with its reasons, no run created.
- Agent tools are clients of the API under unified operations and explicit ownership (section 3.1): each names the API operations it calls, their owners and the stored outcomes they produce; no tool manages authoritative state, duplicates business orchestration or re-executes an operation to reproduce a result.
- Cloud: OpenAI or Claude managed agent; default adapter is the provider custom-tool bridge (HYPRN MVP executes tool calls over an outbound connection; the provider holds no HYPRN MVP credential); remote MCP is the fallback with a short-lived delegation token.
- Local: MCP is the only sanctioned path from a desktop coding agent. Study work happens in a study folder outside the source repository; the per-study token lives in the OS credential store (the macOS Keychain on macOS), 8 hours by default, revocable. The coding agent is a user of HYPRN MVP, not its developer.

Detail: `docs/specs/agents.md` and `docs/agents/tooling-spec.md`.

### 4.7 Licensing boundary

WhatsOpt is GNU AGPL v3; HYPRN MVP runs a patched copy as its private modeling service. Patches, in-process extensions and native templates are inside the AGPL compliance scope (notices, corresponding source, access offers). Network and container separation are technical isolation, not legal immunity. Proprietary product, agent and assessment logic stay outside WhatsOpt; no WhatsOpt code is copied into clients. Model-author, generated-code/template and runtime licences are tracked as separate sets in every artifact and bundle. New dependencies need source, version, hash and licence review before install; only permissive licences are admitted. Detail: `docs/legal/licensing.md`.

## 5. Domain model and glossary

### 5.1 Relationships

```text
Organization ─ User ─owns─ Workspace ─ Study (active or archived)
Study ─ question, context, boundary, Assumptions, Evidence versions
      ─ Modeling approach (draft → versions): method steps, cases, links to exact versions
      ─ Model (draft → versions) ─ instances ─pin─ definition versions ─ ports; connections
      ─ Configuration versions ─pin─ a model version; inputs, criteria, numerical settings, frozen context and evidence
      ─ Run ─freezes─ execution bundle; results and outcome facets
      ─ Assessment, Scientific review (of exact subjects)
Method package ─ Package release ─applied into─ a study's Modeling approach (later)
```

Frozen snapshots never point forward: evidence and reusable assets → package application (when used) → approach and model versions → configuration and evidence closure → run → assessment and review.

### 5.2 Identity, version, revision

- **Public identity**: server-issued opaque UUID in typed fields, independent of database keys, names and numerical paths; stable across export, import and backend replacement. Temporary client keys exist only within one atomic batch, resolved through `created_ids`.
- **Version**: immutable saved state with its own identity (wire `model_revision_id`, `configuration_revision_id`; `/revisions` routes mean versions).
- **Revision**: changing concurrency marker of an editable item (wire `revision`, `expected_revision`, `draft_revision`); never history.
- **Record format version**: how a record's shape is read (`schema_version`, suffixes like `Model4`); a newer format never upgrades meaning.

Distinguish definition from definition version, instance from the version it pins, stable port identity from name or code symbol, draft from version, model version from configuration version, run from command. Editing a definition never updates instances; rebinding is an explicit validated edit per instance (with a port map if port identities change). Rename keeps identity, duplicate creates one, restore creates a new version, commit never implies execute.

### 5.3 Glossary

One term, one concept, one owner and lifecycle. No term implies a capability, approval, validity or executability the record lacks. "Avoid" aliases must not be used for that concept in copy, API descriptions, docs or new identifiers.

| Term | Definition | Avoid |
|---|---|---|
| Study | The engineering question and shared context organizing models, configurations, evidence and runs. Archived, never deleted. | |
| Modeling approach | Study-owned explanation of method, choices, assumptions, evidence, intended cases and links to exact versions. Explains and references; never an executable or editable graph. | approach graph, workflow, pipeline |
| Method step | A scientific contribution within an approach; not a scheduler task. | |
| Case | A situation the approach examines, with its question and rationale; may link to the configuration that specifies it. | configuration, run |
| Model | A composition of component instances and connections expressing a calculation; a model version is one immutable composition and source. | |
| Component definition / instance | Reusable transformation with ports and source (versioned) / one use of a definition version in a model. | |
| Quantity | An input or output with meaning and units at a port; distinct from its value in a configuration or run. | |
| Connection | Directed transfer from a producer output to a consumer input. | |
| Assumption | A scoped condition or approximation a choice or case depends on: text with attached evidence. One concept; free-form notes are not separate (a `notes` wire field may persist). Recording it does not establish that it holds. | note |
| Rationale | Explanation for a choice of method, model or case. | |
| Evidence | Retained source, observation or note supporting, challenging or contextualizing a statement; a version identifies exact content. | |
| Configuration | A specified case: exact model version, explicit inputs, numerical choices, criteria, frozen context. Immutable once saved. | case, setup, scenario |
| Criterion | Explicit requirement a computed output is evaluated against; not an optimizer constraint or applicability condition. | |
| Criterion evaluation | Deterministic comparison of a recorded output with a criterion: met, not met or unresolved. Not validity, applicability or feasibility. | assessment, check result |
| Run | One execution of a configuration with retained inputs, outputs and outcome facets; not the command receipt. "Recorded" means stored. | job, calculation, case |
| Result-linked input | An input taken from a retained run output with exact provenance and unit interpretation; not a live connection. | |
| Modified run | A new configuration derived from a retained run with its recorded changes. | |
| Assessment | Interpretation of results against question, criteria, assumptions and evidence. A criterion evaluation is one input to it. | criterion evaluation, validation |
| Scientific review | Attributed judgment of exact work for a stated use, with limitations and objections. One recorded by an agent for a person shows "{agent} for {user}" and is labelled agent-recorded (ADR-0003). | |
| Record | A stored, identified piece of scientific work; history shows its own stored content. | package, file |
| Portable model record | Self-contained copy of a model's versions, definitions, exact source and identity relationships for import into a conforming backend. | model package, package |
| Prepared model artifact | The modeling service's generated program and model-side files bound to an exact model version and configuration; input to bundle assembly. | bundle |
| Execution bundle | Frozen, self-contained input of one run: exact copies, generated program, provenance, integrity data. | execution package, package, job |
| Computational record export | Downloadable archive of retained runs with what they used, for inspection; not a model record or backup. | package, backup |
| XDSM view | Diagram of a model version's components and data flow; structure only, not executable. | XDSM model |
| Method package / Package release | Reusable scientific procedure with applicability, evidence, assets, cases, checks and review requirements / its immutable version. The only "package". Later scope. | |
| Organization / Workspace | Tenant boundary / user-owned place for studies (no organization-owned workspaces). | organization workspace |
| Owner / Reviewer / Admin | Owns a workspace and edits its work / invited to inspect and review (role does not prove expertise) / manages membership, with no implicit content access. | author |
| Development run / Pilot run | Disposable runs before the declared pilot retention boundary / retained runs after it. | |
| Source document / Authored document | Uploaded file with versions and collections (bytes in AiiDA) / text written in the product (later); a cited authored text is frozen into an evidence version. | |

### 5.4 Wire names that differ from the glossary

Persisted names stay; nothing is renamed or migrated for terminology.

| Wire name | Read as |
|---|---|
| `assessment` (`fixed-threshold-1`, `ASSESSMENT_VERSION`, AiiDA link `assessment`) | Criterion evaluator identity; evaluations are `results.criteria[]` |
| `applicability: {state: "unassessed"}` | Applicability not evaluated |
| `ModelPackageN`, `package` field, `model_package_manifest` | Portable model record |
| `ExecutionBundleN`, `bundle`, `bundle_digest` | Execution bundle |
| `approach_*`; `case_id`, `case_name` | Modeling approach references; Case |
| `model_revision_id`, `configuration_revision_id` | Version |
| `revision`, `expected_revision`, `draft_revision` | Revision |
| run `state: "recorded"` | Stored (not success) |

A lightweight check rejects user-visible "package" copy outside method-package contexts.

## 6. API and contract principles

### 6.1 One API

The UI, agent tools and every other client use only `/api/1`. It exposes HYPRN MVP terminology, identifiers, schemas, errors and semantics; never WhatsOpt routes, IDs, serializers, authentication or CLI. No native escape hatch, untyped options or payload forwarding. Capability identifiers describe engineering behavior; unsupported behavior fails with `unsupported_capability`.

### 6.2 Versioning

- HTTP major version in the path (`/api/1`, `/modeling/1`), changed only for breaking semantics.
- Records carry a format version. New shapes are added as closed alternatives (`ConfigurationRevision4`, `ExecutionBundle8`); existing shapes are never edited; historical readers are data-only.
- Authoring admits only current formats; reading uses a closed table of supported historical combinations. The two are never merged.
- Version interpretation lives in few named points (one retained pairing table, one port-units rule, a few UI record projections). Unknown versions give `unsupported_record_version`, never guessed compatibility.
- `GET /capabilities` advertises versions, capability IDs, limits and the unit vocabulary, and never promises untested workflows.
- Schemas are closed. OpenAPI (`contracts/hyprn-mvp.openapi.yaml`) is generated from the routes and the authored schemas; UI types are generated from OpenAPI.

### 6.3 Envelopes and errors

Responses: `{schema_version, request_id, ...data}`. GET has no side effects; cursor pagination is stable and study-scoped. 201 for creates, 202 with a receipt URL for accepted cross-store work, 200 otherwise.

Errors: `{error: {code, message, request_id, command_id|null, resource_id|null, current_revision|null, fields: [{path, code, message, element_ref|null}], outcome: unchanged|committed|pending|unknown}}`.

| Status | Codes |
|---|---|
| 400, 401, 403/404 | `invalid_request`, `unauthenticated`, `forbidden` (or scoped `resource_not_found`) |
| 409 | `stale_revision`, `command_payload_conflict`, `reference_conflict`, `identity_collision`, `source_result_unavailable` |
| 413, 429 | `limit_exceeded` (with the limit named), `rate_limited` |
| 422 | `invalid_model`, `invalid_configuration`, `unsupported_capability`, `incompatible_rebind`, `incomplete_record`, `unsupported_record_version` |
| 503, 202 | `backend_unavailable`, `isolation_unverified`; `operation_pending`, `dispatch_uncertain` |

A 5xx or timeout never implies rollback or permission to send a new command. Schema failures carry field diagnostics. Messages never contain stack traces, SQL, native tables, paths or secrets. Clients keep unsaved work and returned field errors.

### 6.4 Commands, idempotency, compare-and-set

- Every mutation carries `command_id` and a typed body; edits to mutable state carry `expected_revision`; creates send `null` (model creation and import consume the current study revision).
- Scope: (study or the actor's pre-study namespace, resource category, `command_id`). Same command and payload return the original outcome; a different payload is `command_payload_conflict`; a stale revision is `stale_revision` with no partial effect.
- Batches commit completely or not at all, inside the authoritative store's own transaction (domain rows, identity map, receipt). Several native writes never make an atomic edit.
- Preview has no persistent effect and reserves nothing. Preview → digest → commit: preview returns request and candidate digests; commit carries `expected_preview_digest` = candidate digest and re-resolves everything (mismatch: `reference_conflict`).
- A repeated scientific attempt is a new command and a new run.

### 6.5 Canonical form and digests

RFC 8785 canonical JSON over finite I-JSON values; arrays keep order unless a schema defines set order. Source is hashed as decoded bytes (SHA-256 plus length) and stored exactly (line endings, BOM, non-ASCII). Command digests cover contract major, operation, target, scope, expected revision and normalized payload, not request ID, credentials or command ID. A golden identity corpus pins canonical bytes and digests of configurations, model versions, bundle manifests, executable digests, evidence snapshots and receipts; refactoring leaves it unchanged.

### 6.6 Receipts and cross-store operations

No distributed transaction or cross-store lock. Each cross-store operation has one server-side owner (section 3.1, ADR-0004), never a client. The owner persists intent locally, invokes the remote store with the same command ID, adopts its authoritative receipt, and reconciles before any retry. Legitimate remote results are never deleted to simulate rollback.

| State | Meaning | Next step | Recovery |
|---|---|---|---|
| absent | No receipt in this store | Same ID and payload may be sent (store-local only) | `resend_same_command`; for a run `wait` with `retry_after_s` (a run is never resent) |
| rejected / committed | Rejection, or effect with receipt, recorded atomically | Exact replay returns the original outcome | `refused` / `adopt` |
| pending_remote | Intent stored; remote command sent or uncertain | Query the same remote command; adopt one proven result | `resend_same_command` for a model command (the owner re-queries the modeling service with the same command ID before any remote resend); `wait` with `retry_after_s` for any other category |
| accepted_run | Run and outbox durable | One serialized dispatcher may claim | `adopt` (also `prepared` and `preparation_failed`) |
| dispatching | AiiDA boundary may be crossed | Reconcile only | `adopt` |
| recorded | One matching native process associated | Return the run and lifecycle projection | `adopt` |
| uncertain | No proof of no-effect or unique process | Investigate; never redispatch | `uncertain` |

Unknown is not absent. AiiDA lifecycle (created, waiting, running, finished, excepted, killed, unknown, plus exit data) is projected separately.

**Recovery.** The owner decides how a client recovers after a lost reply: every receipt read carries one `recovery` value, held once in `store` (`receipt_recovery`, `RECEIPT_RETRY_AFTER_S` = 2 s), and every client (the UI, the agent journal, the command line) follows it and keeps no table of its own. `adopt`: the result is the outcome (for a run, the run; its lifecycle is read from the run, never from the receipt); `refused`: the stored rejection is the outcome, and a resend replays it; `wait`: read again after `retry_after_s`; `resend_same_command`: send the same command ID and body again, and the mutation route re-checks authorization and exact idempotency; `uncertain`: never resend, investigate through the record's read. A run is never resent: after its own bounded waits a client reports the outcome as uncertain. A missing receipt in a scope the reader may see is `resource_not_found` 404 whose error object carries `recovery` (and `retry_after_s`); a reader who may not see the scope gets the same 404 without them.

### 6.7 Modeling Backend Contract

Independently authored, versioned HTTP contract at `/modeling/1` with the same identity, error and canonical rules: capabilities (versions, limits, generator identity); create and read models; preview edits (in-memory projection, temporary identities, no effects); apply closed discriminated edits atomically against `expected_revision` (definitions, ports, instantiate, replace an instance's version, connect, disconnect, rename, remove, annotate); commit (recursively pinned version); static validate; export and import of portable model records (IDs, bytes and relationships preserved; collisions rejected unless identical; no lossy migration); pure configuration compatibility; prepare execution from an exact configuration snapshot supplied by HYPRN MVP (idempotent, never reads HYPRN MVP storage); authoritative command outcome. Unsupported constructs (nested composites, implicit components, feedback, cross-model rebind) keep their schema identity and return `unsupported_capability`; they are never flattened or dropped.

### 6.8 Artifact, bundle, program protocol

- The prepared artifact holds the model snapshot, source and generated files, generator identity (pinned upstream commit and archive hash, generator, template and adapter digests), dependency requirements, licence notices, entrypoint and `executable_content_digest`. Identical pinned inputs yield identical executable bytes; IDs, paths, clocks and URLs are excluded.
- The application assembles the bundle after allocating the run identity: verifies every prepared hash, size, path and binding, adds its configuration, context and evidence bytes, the verified runtime, image, policy, full lock bytes and licences. Any mismatch or unresolved dependency rejects; current dependencies are never silently chosen. AiiDA retains artifact and bundle before launch.
- Program protocol `hyprn_mvp.openmdao.program/1`: a fixed `build_model` factory returns the generated Group; bindings list exactly the free inputs and declared outputs with private paths; a line mapping ties generated lines to the original source bytes through a closed set of transforms. The worker sets explicit inputs, runs OpenMDAO and observes availability; it never translates symbols or builds components.
- Current `results.json` format2 records execution, per-output value and availability, criterion outcomes and hashed artifacts. Format1 remains an exact historical reader with its original aggregate fields. Prepared artifact3 and bundle10 explicitly pin result protocol2; no historical schema is reinterpreted.

### 6.9 Configurations

A configuration version pins study, model, model version, inputs, criteria, numerical settings, frozen context and exact evidence snapshots, with required capabilities and a digest. Inputs are literal or result-linked (source run, output, expected results digest, recorded unit interpretation). Criteria use fixed operators (`lt`, `le`, `eq`, `ge`, `gt`) with finite thresholds; no expressions.

Typed numerical slots are reserved so future capabilities need no escape hatch: mode (deterministic, coupled, optimization, uncertainty), initialization, scoped solvers, derivatives, bounded design variables with scaling, objectives, constraints, optimizer family and algorithm, uncertainty method. Today only flat deterministic configurations are supported; non-empty unsupported slots are rejected. The slots preserve direction, not a commitment to every algorithm.

Commit gets a pure compatibility result for the exact candidate, then allocates identities and freezes candidate, context and evidence in one local transaction with study-revision compare-and-set. A modeling outage blocks new configurations, never reads of old ones.

### 6.10 Historical reads and exports

Historical reads use application authorization and retained application and AiiDA records only, and work with the modeling service offline or replaced. Re-execution also needs the recorded runtime. Computational record exports carry the full ancestor closure of selected runs within a bounded size and expose only curated diagnostics.

## 7. Module ownership and the acyclic import rule

The application import graph is acyclic, function-local imports included:

```text
contracts ← units ← {scientific_configuration, approach_closure} ← execution_bundle
  ← {history ← {result_bindings, modified_runs}, execution, configuration, approach, computational_export} ← api
modeling → {units, contracts};  store → contracts
integration → {contracts, units, scientific_configuration, approach_closure, execution_bundle} only
worker → results only (standard library otherwise)
```

| Module | Owns | Must not |
|---|---|---|
| `contracts` | Canonical bytes, digests, IDs, strict JSON, schema validation, public error envelope, field-level schema errors | Touch storage, HTTP, auth, workflows, candidate code |
| `units` | Unit labels, active-port admission, resolved units, the single port-units rule | Convert values; reach stores or clients |
| `scientific_configuration`, `approach_closure` | Literal scientific snapshots; reference-only approach closure validation | Do live lookups |
| `execution_bundle` | Bundle assembly, admission and re-admission, version predicates, the single retained pairing table | Reach store, HTTP, dispatch or worker |
| `store` | Transactions, receipts, studies, membership, archive state, exact evidence read and snapshot, in-transaction read interface, run associations | Canonicalize or load schemas |
| `modeling` | Private contract transport, model command coordination, portable record and model integrity checks | Hold an editable graph |
| `history` | Authorized retained-run reading, outcome completeness, read integrity | Read the current model, configuration or evidence |
| `result_bindings`, `modified_runs` | Result-linked sources, modified-run seeds, via `history` | Read each other's private rows |
| `configuration`, `approach` | Configuration preview and commit with write-time rechecks; approach authoring | `approach` never imports `configuration` |
| `execution` | Static preparation, submissions (receipt, outbox, dispatch) | Own bundle checks |
| `computational_export` | Export requests and archive publication | Use native imports or current models |
| `readiness`, `dispatcher`, `auth`, `ui`, `api` | Observations, executor bridge, local auth, static assets, HTTP surface | — |
| `agent_tools`, `agent_runtime`, `agent_surface` (planned) | Registry and API client; sessions, delegations, journal and agent activity; MCP server and provider bridge | Reach scientific modules (tools see only `contracts` and the injected API client) |

The diagram summarizes the layers; the table below is complete. Every direct import between application modules, function-local imports included, is one of its edges, the table is acyclic, and the boundary test holds the same table and fails on any import outside it (`application/tests/test_module_boundaries.py`, `LAYERS`). The route package (`routes`, the per-owner routers) and each agent package are one row each; `edge` holds the helpers the routers share; `hyprn_mvp_app` is the package root. Six edges the diagram does not draw are part of it: `modeling → store`; `store → readiness` (function-local: `store` calls the observation owner's two pure validators, `runtime_identity` and `valid_observation_time`, inside the trusted observation write and read, and `readiness` reaches only `contracts`, so the edge cannot close a cycle); `configuration → {modeling, readiness, scientific_configuration}`; `execution → readiness`; `modified_runs → readiness`; `dispatcher → computational_export`. A new edge is added here and in the test together.

Scientific case answers and study synthesis are application-owned immutable records in `answers`.
Each targets an exact saved approach version and, for case answers, a case in that version. Explicit
basis IDs cite same-study configurations, runs and evidence; a synthesis may cite exact case-answer
versions from that approach. One current head per target is only a listing convenience: revisions
never change earlier answers, and execution/criteria never infer an answer. The owner registers its
tables through the Store connection and saves answer, head and command receipt in one authorized
transaction. These records do not enter modeling or execution bundles.

**Allowed imports**

| Module | May import directly |
|---|---|
| `hyprn_mvp_app` (package root) | — |
| `contracts` | — |
| `locations` | — |
| `units` | `contracts` |
| `scientific_configuration` | `contracts` |
| `approach_closure` | `contracts`, `units` |
| `execution_bundle` | `approach_closure`, `contracts`, `scientific_configuration`, `units` |
| `readiness` | `contracts` |
| `store` | `contracts`, `locations`, `readiness` |
| `history` | `contracts`, `execution_bundle`, `units` |
| `result_bindings` | `contracts`, `execution_bundle`, `history`, `units` |
| `modified_runs` | `contracts`, `history`, `readiness` |
| `modeling` | `contracts`, `store`, `units` |
| `approach` | `approach_closure`, `contracts`, `execution_bundle`, `history`, `store` |
| `answers` | `approach`, `contracts`, `history` |
| `exploration` | `answers`, `contracts`, `execution_bundle`, `history`, `units` |
| `sampling` | `contracts`, `exploration`, `history`, `readiness` |
| `configuration` | `approach`, `contracts`, `execution_bundle`, `history`, `modeling`, `modified_runs`, `readiness`, `result_bindings`, `scientific_configuration`, `store`, `units` |
| `execution` | `contracts`, `execution_bundle`, `history`, `readiness`, `result_bindings`, `scientific_configuration` |
| `computational_export` | `approach_closure`, `contracts`, `execution_bundle`, `history`, `locations`, `modified_runs`, `result_bindings` |
| `dispatcher` | `computational_export`, `configuration`, `contracts`, `execution`, `execution_bundle`, `exploration`, `modeling`, `readiness`, `sampling`, `store` |
| `auth` | `contracts`, `store` |
| `ui` | — |
| `edge` | `contracts` |
| `routes` (package) | `answers`, `approach`, `auth`, `computational_export`, `configuration`, `contracts`, `edge`, `execution`, `exploration`, `history`, `modeling`, `modified_runs`, `readiness`, `result_bindings`, `sampling`, `store` |
| `agent_tools` (package) | `contracts` |
| `agent_policy` | `agent_tools`, `contracts` |
| `agent_runtime` (package) | `agent_tools`, `auth`, `contracts`, `edge`, `store` |
| `agent_surface` (package, planned) | `agent_runtime` |
| `api` | `answers`, `agent_policy`, `agent_runtime`, `approach`, `auth`, `computational_export`, `configuration`, `contracts`, `edge`, `execution`, `history`, `modeling`, `modified_runs`, `result_bindings`, `routes`, `store`, `ui` |

Rules: each shared capability, and each operation that needs a durable, observable outcome (section 3.1), has one owner with a narrow public interface; no cross-module private access (remaining framework or same-module cases are allowlisted); move pure functions to their owner instead of creating service objects; `store` remains the transaction owner (no repository-per-table, plugin framework or universal resolver); integration never imports persistence or orchestration for helpers. A boundary test pins directions, attested-source coverage and forbidden imports; checks are added only against a concrete regression. In the UI, presentation consumes typed record projections instead of branching on wire versions; the study shell handles navigation and composition while domain controllers own their workflow state behind one editor-guard interface (dirty, save, discard) and one session and access-loss seam.

Package names: `hyprn_mvp_app` (application), `hyprn_mvp_integration` (execution and document integration), `hyprn_mvp_local` (local edition CLI and adapters).

## 8. Persistence

| Store | Sole writer | Content |
|---|---|---|
| Application | Application | Studies, memberships, archive state, evidence, approaches, configurations, receipts, run associations, outbox, exports, agent records |
| Modeling | Modeling service | Models, definitions, versions, identity maps, modeling receipts |
| AiiDA profile and repository | Execution integration | Processes, bundles, results, artifacts; document bytes |

The local edition uses SQLite in rollback-journal mode (no WAL: host-side readers cross the container VM boundary and rollback is harder); reads stay short so dispatch is not starved. A multi-tenant cloud targets PostgreSQL for the application store, adding row-level policies on top of application authorization. Ordinary start never creates stores; initialization runs only on a blank data root or this installation's own partial-setup marker; a missing or changed store identity is a visible error. Development run data is discardable and never migrated; authoring records are never deleted for convenience.

Before the pilot-retention boundary (the point from which an installation holds data that must outlive a release), the store rule is: every store records its schema version; opening a store never creates it and never alters its schema; a recorded version that differs from the release's makes start refuse, with a message that names the reset command and says the stored data is not migrated; a fresh start is an explicit, confirmed reset (`./hyprn-mvp setup --reset-data`, confirmed interactively or with an explicit `--yes` in non-interactive mode) that discards the installation's stores and initializes new ones, and never runs automatically; no migration code exists. From that boundary on, retention, backup and migration rules apply in full and replace this rule.

## 9. Editions and repositories

- `hyprn-mvp`: the product monolith. Shared core (application, UI, integration, contracts, modeling patches, design system, deployment managers) plus `editions/local/` (CLI, prerequisite checks, path policy, OS credential-store and clipboard adapters, study-folder kit, local MCP relay, smoke test). `editions/cloud/` appears only with real cloud adapter code.
- The edition is chosen by the installation configuration's `edition` field, never by branches, forks or build flags. Editions hold adapters and packaging only; scientific, API and security behavior is identical.
- `hyprn-platform`: Terraform, staging and production, cloud identities, governance; no product code. Its cloud platform specification lives in that repository (`docs/specs/cloud-platform.md`).
- The product name is HYPRN MVP; technical identifiers use `hyprn-mvp` (the `./hyprn-mvp` command, the `HYPRN_MVP_` prefix, labels, images, the MCP server name). No durable name encodes a phase, architecture style or person.
- Local first: clone, `./hyprn-mvp setup`, `./hyprn-mvp start`. Setup snapshots the committed checkout into an installed release, builds and re-attests when execution sources change; start never rebuilds. Supported on macOS and Linux, Windows through WSL2. The cloud edition follows.
- ADRs (MADR) live in each governed repository's `docs/adr/`.

## 10. Deferred and out of scope

| Item | Status |
|---|---|
| Nested composites, boundary maps, cross-model rebind, definition restore | Required later; schema reserved; `unsupported_capability` now |
| Automatic rebind after a definition edit | Product gap; explicit per-instance edit until then (agent tools add it in the same batch) |
| Run cancellation, asynchronous recovery | Required later; advertised unavailable; cancellation is a request until confirmed |
| Coupled solves, total derivatives | Required direction, own scoped slice |
| Advanced optimization | Required direction; each family (gradient constrained, derivative-free, multi-objective, mixed-integer, global multistart, robust or reliability) needs a scope decision |
| Uncertainty with OpenTURNS | Later |
| Source documents on AiiDA (store, versions, collections, read, annotate, cite, extract) | Planned; only native storage of originals is implemented; advertised unavailable (`docs/specs/documents.md`) |
| Authored documents (Tiptap); live co-editing (Yjs) | Later; co-editing only for multi-user cloud |
| Agent slices: local MCP read-only, local authoring (ADR-0003 write policy), cloud managed agent | `docs/specs/agents.md`; first slice is agent principal and attribution |
| Workspaces, organizations, invitations, Keycloak sign-in; permission store | Cloud multi-tenant; permission store deferred until inheritance needs it (`docs/specs/workspaces-identity-onboarding.md`) |
| Method packages, package releases, scientific review records | Later |
| Workbench shell (React Flow and XDSMjs canvas, dockview layout, assistant panel) | Proposed, not decided (`docs/specs/ui-target.md`) |
| Currency execution, parameter sweeps, conclusion record, typed "no feasible design" outcome, typed inherited provenance, status channel | Product gaps awaiting a reviewed plan |
| Out of scope | High-fidelity long simulations, Bayesian inference, arbitrary distributions, dependent-input attribution, uncertain arrays, IDE or debugger, marketplace, formal approvals, in-product notebooks, second editable graph, custom scheduler or provenance platform, distributed transactions |

## 11. Open questions (recommended defaults)

1. **WhatsOpt AGPL for the cloud product.** Legal review pending. Default: no commercial cloud launch before it; keep all WhatsOpt material inside the modeling service's compliance scope; scope a permissive replacement backend behind the contract in parallel.
2. **Licence of generated model code.** Templates carry no generated-code exception. Default: treat generated files as inside the AGPL scope and record template licences per artifact until counsel decides; a replacement backend uses permissive templates.
3. **Open interchange format.** The intended direction is XDSM or similar, but XDSM carries no executable source. Default: the portable model record stays the exact exchange; XDSM is an export-only view.
4. **Field pointer on configuration-commit `reference_conflict`.** Default: add one as an additive error detail.
5. **Light run-status read.** Full run reads can be slow. Delivered: `GET /api/1/studies/{study_id}/run-status?run_id=…` (1 to 20 distinct runs of the study, answered in request order, all or none) returns `RunStatus1` per run from the stored run state, owned by `history`: state, configuration name, the stored lifecycle projection (`process_state`, `exit_status`), the outcome facets and criterion outcomes as the retained results hold them (null with reason `not_recorded` until recorded), and `times`. `submitted_at` is the acceptance time the application records (`run_associations.accepted_at`; null with `not_recorded` for runs accepted before it was recorded). Open: `started_at` and `finished_at` are held by AiiDA and are null with reason `not_projected` until the attested execution integration projects them (a re-attesting change); liveness and queue position stay open. The full run record is unchanged.
6. **Study roles vs workspace roles.** Today: owner, writer, reader per study; target: Owner, Reviewer, Admin per workspace. Default: owner → Owner, reader → Reviewer; writer stays a local-edition role until workspaces land.
7. **Cloud application database.** Default: PostgreSQL with row-level policies when multi-organization operation starts; SQLite stays local.
8. **Pilot retention boundary.** Default: declared before inviting pilot users; later runs follow full retention, backup and migration rules.
9. **First optimization family.** Default: gradient-constrained on OpenMDAO's native drivers, after coupled solves and derivatives.
