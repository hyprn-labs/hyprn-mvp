# Requirements

Status: current requirements catalogue. Each requirement has a stable identifier that the specifications cite. The specifications hold the normative detail; a short requirement here never weakens them.

| Specification | Path |
|---|---|
| Architecture and contracts | `docs/specs/architecture-and-contracts.md` |
| Documents | `docs/specs/documents.md` |
| Agents | `docs/specs/agents.md` (tool detail: `docs/agents/tooling-spec.md`; working rules: `docs/agents/playbook.md`) |
| Workspaces, identity and onboarding | `docs/specs/workspaces-identity-onboarding.md` |
| UI target | `docs/specs/ui-target.md` |
| Licensing | `docs/legal/licensing.md` |

Status values:

| Status | Meaning |
|---|---|
| **delivered** | Implemented and verified by automated tests in the current product. Human acceptance by an engineer who did not implement it is tracked separately (ACPT-01). |
| **partial** | Part of the requirement is delivered; the notes say what remains. |
| **planned** | Decided and in the roadmap; not yet implemented. |
| **deferred** | Proposed but not decided, or postponed until a stated condition is met. |

## 1. Reuse and licensing

| ID | Requirement | Status | Notes |
|---|---|---|---|
| ADOPT-01 | Reused upstream components (WhatsOpt, OpenMDAO, AiiDA, later OpenTURNS) are pinned with recorded source, version, hash and licence, and their integration is measured before substantial custom expansion. | delivered | Architecture §3, §6.8 |
| ADOPT-02 | Each substantive custom extension traces to a requirement, a tested upstream gap and the smallest maintainable solution. | partial | Applies continuously; confirmed at integrated acceptance |
| ADOPT-03 | Licence obligations are met: WhatsOpt patches, extensions and templates stay inside the AGPL compliance scope; model-author, generated-code and runtime licences are tracked separately per artifact; new dependencies are permissive and reviewed before install; legal review precedes any commercial cloud launch; a permissive replacement modeling backend is scoped behind the contract. | partial | Compliance scope and per-artifact licence sets in place; legal review and replacement backend pending (`docs/legal/licensing.md`) |

## 2. Human modeling

| ID | Requirement | Status | Notes |
|---|---|---|---|
| HUM-01 | The engineer can create and reopen a study with its question, description, boundary and models. | delivered | |
| HUM-02 | The engineer can inspect a selected model element, its source, quantities and scoped assumptions through the HYPRN MVP UI (Graph and XDSM views, quantities table, component details) using the HYPRN MVP API. | delivered | UI target §3.5 |
| HUM-03 | The engineer can author and edit a Python component with explicit real-scalar input and output ports in the product. | delivered | |
| HUM-04 | The engineer can compose component instances, connect ports and edit nested groups with explicit boundary mappings. | partial | Flat composition and connections delivered; nested composites and boundary maps return `unsupported_capability` |
| HUM-05 | The engineer can assign each free input explicitly with units and provenance and receives actionable missing or incompatible-input errors. | delivered | Unspecified units may be saved in drafts; execution requires resolved units |
| HUM-06 | The engineer can attach and inspect assumptions with evidence, equations, omissions, applicability, sources and checks at their declared scopes. | partial | One Assumption concept with evidence delivered for approach, model, component and configuration; document citations (DOC-01), an authored equations field and applicability evaluation remain |
| HUM-07 | Input provenance is typed (brief, source, property, constant, judgement, numerical, result) and inherited from a study parameter register; configurations record only deviations. | planned | Agents §9 gap 2 |
| HUM-08 | Currency quantities carry a currency unit and price year. | planned | Agents §9 gap 6 |
| HUM-09 | The engineer can write a Modeling approach (question, context, method steps, assumptions, limits, cases) linked to exact model and configuration versions, and see cases with their results. | delivered | UI target §3.4 |
| HUM-10 | A study has one conclusion record: answer, claims labelled computed, sourced or judgement and linked to exact runs, outputs and evidence, confidence and open questions. | planned | Agents §9 gap 3; interim evidence note |

## 3. Versions and edits

| ID | Requirement | Status | Notes |
|---|---|---|---|
| VER-01 | The engineer can commit, reuse, selectively rebind and restore model definitions and instances without altering referenced versions or stable identities. | partial | Commit, reuse and explicit per-instance rebind delivered; definition restore and cross-model rebind deferred; automatic rebind after a definition edit is a product gap |
| VER-02 | The engineer can save immutable configurations pinned to an exact model version, with compatibility validation when the model changes. | delivered | |
| VER-03 | A client can apply an atomic, revision-checked edit, optionally preview it, and repeat a command without duplicate or partial effects. | delivered | Preview → digest → commit and command receipts (architecture §6.4); agent clients use the same semantics |
| VER-04 | An operation produces one authoritative outcome that every client can subsequently reference, inspect and act upon, without reconstructing or repeating the operation: each operation needing shared identity, durability, consistency, observability or recovery has one owner and a stored outcome; no client manages authoritative state, duplicates business orchestration or re-executes an operation to reproduce a result; no HYPRN MVP state duplicates an engine's authoritative state. | planned | ADR-0004, architecture §3.1; checked in the plans that add agent tools and document operations |

## 4. Execution and history

| ID | Requirement | Status | Notes |
|---|---|---|---|
| RUN-01 | The engineer can explicitly submit a frozen deterministic model and configuration through AiiDA and obtain verified OpenMDAO results from an isolated worker. | delivered | |
| RUN-02 | The engineer can reopen an earlier run with its exact source, inputs, context, evidence, outputs and diagnostics after edits, restarts or a modeling-service outage. | delivered | Cited document passages join with DOC-01 |
| RUN-03 | The engineer can observe, cancel and recover a run through native AiiDA lifecycle handling, with retries represented as new runs and ambiguous submissions reconciled. | partial | Lifecycle projection, uncertain state and no automatic redispatch delivered; cancellation and asynchronous recovery advertised unavailable |
| RUN-04 | The engineer can inspect partial results and actionable numerical or execution failures; failed or missing values are never reported as valid zeroes. | delivered | Ensemble extension with UQ-03 |
| RUN-05 | A model can return a typed "no feasible design" outcome with bounded diagnostics, distinct from execution failure. | planned | Agents §9 gap 5 |
| RUN-06 | The engineer can define and submit a parameter sweep as one operation. | planned | Interim: batched configurations and submissions |
| RUN-07 | Clients can read a light run status (state, outcome facets, submitted/started/finished times, criterion outcomes) and see executor liveness and queue position. | planned | |
| RUN-08 | The engineer can take an input from a retained run output with exact provenance, create a modified run from a retained run, and export computational records of selected runs. | delivered | Architecture §6.9–6.10 |

## 5. Scientific methods

| ID | Requirement | Status | Notes |
|---|---|---|---|
| SCI-01 | The engineer can run declared explicit-feedback and implicit-residual models with recorded initialization, solver scope, convergence and failure diagnostics. | planned | Typed configuration slots reserved |
| SCI-02 | The engineer can inspect local total derivatives including coupling, with recorded units and settings and an independent perturbation check. | planned | |
| SCI-03 | The engineer can run advanced optimization (gradient constrained, derivative-free, multi-objective, mixed-integer, global multistart, robust or reliability) with termination, feasibility and criteria kept separate. | deferred | Each family needs a scope decision; recommended first family: gradient-constrained on OpenMDAO drivers, after SCI-01 and SCI-02 |

## 6. Uncertainty

| ID | Requirement | Status | Notes |
|---|---|---|---|
| UQ-01 | The engineer can configure fixed, normal and uniform inputs with independent sources, shared source identity and validated correlated Gaussian dependence. | planned | OpenTURNS in the restricted worker |
| UQ-02 | The engineer can inspect retained joint draws and paired outputs with stable sample IDs and a population independent of scheduling or retries. | planned | |
| UQ-03 | The engineer can inspect honest partial-ensemble summaries, inclusion masks, evaluability-conditional frequencies and unresolved fraction bounds. | planned | |
| UQ-04 | The engineer can request recorded first and total Sobol indices for independent inputs; dependent inputs and incomplete structured designs are rejected. | planned | |

## 7. Criteria and evidence

| ID | Requirement | Status | Notes |
|---|---|---|---|
| CRIT-01 | The engineer can evaluate typed criteria as met, not met or unresolved while seeing execution, convergence, completeness and applicability separately. | partial | Fixed-threshold criteria and separate recorded facets delivered; applicability is recorded as not evaluated; convergence and completeness become non-constant with SCI and UQ |
| DOC-01 | The engineer can upload, store, read, browse, download, annotate, search and cite source documents, organize them in collections, and archive or safely delete them, with immutable source locations, visible processing failures and retries, and protected retained references. | partial | Wire contracts and native storage of originals delivered; collections, annotations, API, extraction, search, citations, deletion, portability and UI remain (`docs/specs/documents.md` §12) |
| DOC-02 | The engineer can write authored documents (reports, memos, review write-ups) in the product and freeze a finished or cited text into an evidence version. | deferred | Later; Tiptap editor when authored reports are scheduled |
| DOC-03 | Several users can co-edit an authored document live. | deferred | Cloud edition only, when needed (Yjs) |

## 8. Agents

| ID | Requirement | Status | Notes |
|---|---|---|---|
| AGENT-01 | A desktop coding agent (Codex or Claude Code) can work on one study through the local MCP tool server, using the same scoped typed operations as the UI, with every write attributed and journaled and no deletion of saved records, archive, restore or access management (ADR-0003). | planned | First slice read-only, with the local edition |
| AGENT-02 | The engineer can work with a provider-managed agent in an assistant panel that inspects and modifies the actual study, with budgets, visible activity, Stop and interruption recovery. | planned | Cloud edition; custom-tool bridge by default |
| AGENT-03 | The engineer can delegate scoped document or public research that retains citations, contradictions and inference labels without leaking private content into search. | deferred | Until documents reach agents and a measured benefit exists |
| AGENT-04 | The engineer can obtain run-grounded assessments and next-investigation suggestions that keep their limitations, carry a claim level and become visibly stale when their context changes. | planned | With the conclusion record (HUM-10) |
| AGENT-05 | An agent is its own principal acting for one user under a delegation; effective authority is the intersection of delegation, the user's current access and a role ceiling, and every record shows "{agent} for {user}". | planned | First agent slice; prerequisite for agent writes |
| AGENT-06 | Agents never delete a saved record, archive or restore studies or documents, or manage access (memberships, invitations, delegations, tokens, roles); no tool offers these effects and agent sessions are refused on their routes. Within the delegating user's current authority and the role ceiling they write directly, including creating studies (owned by the delegating user) and recording scientific reviews (labelled agent-recorded); draft material may be changed or deleted under revision checks; collection membership may change while every record keeps its exact versions; a run submission whose configuration is not ready is refused. Every agent write is attributed "{agent} for {user}" and journaled; overwrites never silently replace a person's concurrent edit; provider or client approvals never widen these rights. | planned | ADR-0003; product review of control behaviour before writer-capable tokens |
| AGENT-07 | Agent use is bounded and controllable: limits and budgets, installation, user, session and token kill switches, an append-only action journal, and transcript retention rules. | planned | |
| AGENT-08 | Every supported agent surface passes the evaluation scenarios and parity gate before release, and changes to rules, tools, playbook or providers are re-evaluated. | planned | Agents §10 |

## 9. Method packages and review

| ID | Requirement | Status | Notes |
|---|---|---|---|
| PKG-01 | An Owner can author and release a workspace-local method package (procedure, applicability, assets, cases, checks, review requirements) and apply a release to a study's Modeling approach, with requirements enforced by HYPRN MVP. | planned | After identity and invited collaboration |
| PKG-02 | A person, or an agent acting for an eligible person, can record an attributed scientific review of exact subjects for a named use, with limitations and objections; a review recorded by an agent is labelled agent-recorded. | planned | With method packages; ADR-0003 |

## 10. Identity, access and collaboration

| ID | Requirement | Status | Notes |
|---|---|---|---|
| IAM-01 | The local edition has exactly one Owner with a generated password, secure sessions, CSRF and origin checks, lockout and CLI-only recovery. | delivered | Setup flow joins with OPS-04 |
| IAM-02 | Every operation authorizes actor, study and resource, including reads, exports, downloads and receipt replay, with non-disclosing not-found outside the study. | delivered | Study memberships today |
| IAM-03 | One authorization function `can(principal, action, resource)` is used by every route, tool handler, background consumer and download path. | planned | Starts as a wrapper over today's check |
| IAM-04 | The cloud edition provides organisations, user-owned workspaces, Owner/Reviewer/Admin roles, organisation and workspace invitations, and OIDC sign-in behind HYPRN MVP's own sessions. | planned | Identity provider choice open |
| IAM-05 | The cloud application store enforces row-level security from verified transaction context in addition to `can()`. | planned | PostgreSQL |
| IAM-06 | A relationship-based permission store handles inherited and per-resource access. | deferred | Until inheritance or per-resource sharing arrives |
| COLLAB-01 | Owners and Reviewers can comment on exact subject versions, request reviews and receive in-app notifications, all as HYPRN MVP records. | deferred | Proposed for the cloud edition |
| COLLAB-02 | Users see who else is viewing a workspace or study. | deferred | Only after a multi-user pilot shows a need |

## 11. User interface

| ID | Requirement | Status | Notes |
|---|---|---|---|
| UI-01 | The UI is HYPRN MVP's own React application over the public API only, built from the design-system components and tokens. | delivered | |
| UI-02 | Every entity has one canonical editable home and read-only views reuse the canonical component; the run headline shows Execution and Criteria; one Assumption concept without notes; the canonical model view shows Graph or XDSM with quantities below. | delivered | Human acceptance pending; defaults may be revised |
| UI-03 | Every action is keyboard-reachable, both themes and genuine 200 % zoom stay usable, and states are honest (loading, dirty, stale, partial, uncertain, access loss). | partial | Access-loss residuals in evidence hosts and study-shell lists (UI target §7) |
| UI-04 | The UI offers a study-scoped, read-only Agent activity page (recent agent actions from the journal with links to the records, and an entry point to stop an agent by revoking its access) and attribution chips on agent-written records; local tool tokens are listed and revoked through the CLI and the owner-session API. | planned | With AGENT-05 and AGENT-06; ADR-0003 |
| UI-05 | The study workbench offers docked panels, a canvas over typed modeling commands and an assistant panel. | deferred | Proposed, not decided |

## 12. Operations and security

| ID | Requirement | Status | Notes |
|---|---|---|---|
| OPS-01 | The engineer can archive and restore a study; studies are never deleted; illegal transitions and removal of resources referenced by retained history are rejected. | delivered | Home archive and restore |
| OPS-02 | Candidate code runs only in a verified isolated worker with bounded resources and no network, host secrets or modeling access; execution is refused without current attestation. | delivered | |
| OPS-03 | The operator can restart and consistently back up the independent stores outside cloud-synced folders, with missing or corrupt storage visibly reported. | partial | Restart and store-identity checks delivered; coordinated backup and restore drill remain |
| OPS-04 | Any engineer can install the local edition on macOS or Linux (Windows through WSL2) with clone, `./hyprn-mvp setup` and `./hyprn-mvp start`, with no hard-coded location: every path is resolved as flag → `HYPRN_MVP_*` variable → installation configuration → per-OS default → ask. | planned | |
| OPS-05 | The cloud edition is deployed and operated from the platform repository with separate staging and production environments. | planned | After the local edition |
| SEC-01 | The product meets OWASP ASVS Level 1, with high-severity items mandatory before release. | partial | Local-edition controls in place; access-loss recheck pending; cloud tenant isolation with IAM-04 and IAM-05 |

## 13. Integrated acceptance

| ID | Requirement | Status | Notes |
|---|---|---|---|
| ACPT-01 | An engineer who did not implement HYPRN MVP completes the manual journey and, later, the agent journeys across all supported numerical modes without undocumented administrative steps. | planned | See section 14 |

## 14. Acceptance journeys

**First manual journey.** An engineer creates a small study and two components, edits Python in the product, connects quantities, inspects assumptions, supplies explicit values, validates and runs. For `u = 2*x + z`, `y = u*u`, `x = 2`, `z = 3`, the recorded outputs are `u = 7`, `y = 49`. The engineer changes an input or equation, reruns and reopens the earlier result with the original bytes and inputs intact. Missing inputs and incompatible units are actionable errors. Saving or editing never executes code. The fixture is authored through normal operations, not hard-coded.

**Later journeys.** Documents (DOC-01 acceptance in `docs/specs/documents.md` §12), agent scenarios G1–G8 on every supported surface (`docs/specs/agents.md` §10), cloud access release blockers (`docs/specs/workspaces-identity-onboarding.md` §16), and each numerical mode as it is delivered. Automated evidence never substitutes for human acceptance; both are recorded separately.

## 15. Scientific acceptance rules

These apply to every requirement above.

- Model structure and equations, and configuration values and settings, have distinct immutable version boundaries; frozen context and evidence stay inspectable.
- No hidden physical defaults, unintended broadcasting, untested affine conversions, hidden randomness or cross-case state.
- Non-convergence is unresolved. Local derivatives are not global importance or causation; self-tests are not independent scientific validation.
- Correlation validation covers symmetry, diagonal, range and positive semidefiniteness. Singular matrices are tested or explicitly rejected, never silently repaired.
- Uncertainty runs retain actual draws, paired outputs, failed attempts and disjoint terminal classes: succeeded, input_invalid, execution_failed, cancelled, not_attempted.
- For N generated cases, s evaluable, k event successes and u = N - s unresolved: show k/s only when s > 0, plus [k/N, (k+u)/N] as generated-ensemble bounds, never as a population confidence interval. Zero-evaluable summaries are unavailable.
- Sobol analysis uses a distinct complete structured independent-input design and freezes estimator, seed, ordering, budget and precision. Failed rows are never deleted to obtain apparently valid indices.
- Cancellation is a request until confirmed. Repeated identical command IDs resolve the original result; changed payloads conflict. Ambiguous outcomes require lookup before resubmission.
- Documents never grant authority. Claims distinguish computed facts, sourced statements and inference; sensitivity-based recommendations require actual sensitivity evidence.

## 16. Out of scope

High-fidelity long-running simulations; Bayesian inference; arbitrary input laws and dependent-input attribution; uncertain arrays; a full IDE or debugger; a model marketplace; formal approval workflows; in-product notebooks; a second editable model graph; a custom scheduler or provenance platform; distributed transactions; deleting studies. Deterministic arrays are optional once unit and shape behaviour is tested. Nothing is required only because an upstream tool supports it.
