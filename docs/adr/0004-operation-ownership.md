---
status: accepted
date: 2026-10-13
decision-makers: Owner
---

# ADR-0004: Unified operations and explicit ownership

## Context and Problem Statement

HYPRN MVP has several stores with one writer each (application, modeling service, AiiDA) and several clients: the UI, agents through the tool registry, and the command line. Many operations involve more than one call or more than one component: preview then commit, model edits then a version, upload transfer then publication, citation resolution inside an evidence version, run submission then dispatch and recording, extraction, collection deletion.

When a client manages authoritative state itself, or drives business orchestration that a server component should own (writes in one place, then another, then asks a third component to re-execute something so it can show the result), nobody owns what actually happened. A client that stops halfway leaves state no server component knows how to finish or recover; two clients repeat the same orchestration differently; a result recomputed for display can differ from the recorded one; and a second representation of an engine's state drifts from the engine.

The architecture already forbids distributed transactions and requires cross-store operations to persist intent and adopt the owner's receipt (architecture and contracts §6.6), but it does not state who owns which kind of state, when an operation needs its own identity and lifecycle, or what clients and agents may and may not do. The product owner asked for an explicit, testable principle that constrains agent tool design without deciding it in advance (the agent-practices research of Phase 3 task 3.2a stays open).

## Decision Drivers

- **One writer per store**, no distributed transaction or cross-store lock (architecture §6.4, §6.6, §8).
- **What happened is owned by the platform.** Every number stays traceable to the record that produced it; a displayed result is the recorded one, never a recomputation.
- **Reuse, not re-implementation.** OpenMDAO, AiiDA and the modeling service own what they already do well; HYPRN MVP keeps references and associations, not copies of their state.
- **Clients are interchangeable.** The UI, agents and the command line use one API with the same checks; none needs private coordination logic another client lacks.
- **Agent design stays open** (iteration, sub-agents, progressively loaded skills, tool granularity, provider bridges) inside a clear boundary.

## Considered Options

- **A: leave it implicit** in the existing receipt and cross-store rules.
- **B: a principle with explicit ownership of each kind of state and verifiable consequences**, checked in every plan.
- **C: a mechanism**: a central orchestrator, workflow engine or saga service through which every operation and all agent activity pass.

## Decision Outcome

Chosen option: **B**. A leaves agent tools and new document operations without a rule to check against. C adds the scheduler or workflow engine the architecture rules out (architecture §10), would duplicate lifecycle that AiiDA already owns, and would decide the agent tool design before the research that should inform it.

### Central invariant

**An operation produces one authoritative outcome that every client can subsequently reference, inspect and act upon, without reconstructing or repeating the operation.**

Everything below is the means of upholding this invariant, and every plan check traces to it.

### Principle

All HYPRN MVP capabilities are exposed through one consistent application API (`/api/1`), whether they are invoked by users, agents or other clients. Every shared resource has a single authoritative owner responsible for its state and lifecycle. Operations that require durable coordination expose stable identities and observable outcomes. Agents and clients may freely compose capabilities, but must not independently manage authoritative state, duplicate business orchestration or re-execute operations to reproduce shared results. The application delegates execution and persistence to the appropriate domain owners and avoids parallel representations of authoritative state.

In short: **the agent decides what to do; the platform owns what actually happened.**

### When an operation needs its own identity and lifecycle

This criterion decides where the central invariant needs an explicit, durable outcome. The criterion is not the number of steps or stores. An operation needs a durable, identified and observable lifecycle (a command with a receipt, or an operation resource whose state its owner advances) when it requires **shared identity, durability, consistency, observability or recovery**: other people or clients must find it, it must survive a restart or a lost reply, it must not apply twice or halfway, or its progress and outcome must be visible. Many multi-step interactions need none of this (reading several records to prepare an edit, previewing before saving), and a single call may need it (a run submission, an upload completion).

### Three kinds of state

Each kind has one owner, so an outcome is authoritative in exactly one place.

| Kind | Examples | Owner |
|---|---|---|
| **Domain state** | Studies, memberships and archive state, Modeling approach, configurations, evidence and citations, document identity and associations, model references, command receipts and run associations, agent sessions and the action journal | The domain modules of the application (architecture §7), each the single owner of its resources |
| **Execution state** | Model composition and versions; process lifecycle, results, retained artifacts and provenance; document bytes, collections and extraction results | The execution subsystem and the engines: the modeling service for models, AiiDA (through execution integration) for processes, results, artifacts and document storage, OpenMDAO inside the worker for numerical computation. HYPRN MVP keeps stable references, domain associations, command and dispatch receipts and a projection of execution status, never a parallel execution state machine |
| **Interaction state** | A conversation, an agent's plan and working memory, unsaved edits in the browser, temporary exploration | The client or agent that holds it; never authoritative and never read by a server component |

**How the existing receipt and run-association design complies.** Command receipts track a command's intent and the reconciliation of its dispatch (`absent`, `rejected`, `committed`, `pending_remote`, `accepted_run`, `dispatching`, `recorded`, `uncertain`; architecture §6.6). They answer "was this command applied, and with which native process is the run associated", which is domain state the application must own to keep launches unique and recoverable. They do not model how a process runs: the AiiDA lifecycle (created, waiting, running, finished, excepted, killed, unknown, exit data) stays authoritative in AiiDA and is projected separately for display, and results and artifacts are read from AiiDA's retained records. The same pattern applies to documents: the application keeps document identity, operations and associations; bytes, collections, annotations and extraction results stay in AiiDA, and the search index is a rebuildable projection.

### Responsibilities

The division of work that keeps each outcome with its owner:

| Responsibility | Owner in HYPRN MVP |
|---|---|
| Business resources and authoritative state | Domain modules of the application |
| Lifecycle of a business operation (receipts, operation resources, recovery) | Domain modules of the application |
| Execution of multi-step workflows across components | Application and domain services behind the API, delegating to the engines that own execution |
| Reasoning and planning: which operations to call, in what order | The agent (or the person using the UI or command line) |
| Routing, authentication, transport | The API edge: the application's HTTP layer, and the edge proxy in the cloud; no separate gateway service with its own store |
| Presentation and ephemeral interface state | The frontend |

### Verifiable consequences

Each consequence is a checkable form of the central invariant.

1. **One owner and a stored outcome.** Every tool or API operation that needs shared identity, durability, consistency, observability or recovery names its single owner and produces a stored outcome with a stable identity that any client can read back.
2. **No duplicated business orchestration.** A client or agent composes capabilities (reads, previews, commits, submissions) but never re-implements the coordination a server owner performs: it keeps no outbox, compensation or rollback of its own, and if the stores would be inconsistent when it stopped between two calls, that coordination belongs to a server owner.
3. **No re-execution to reproduce shared results.** Showing a result reads the stored resource (run, extraction attempt, operation, export). Running again is an explicit new command that creates a new resource, never a way to display an earlier one.
4. **Recovery reads the owner.** After a lost reply a client reads the owner's receipt or operation resource; it never resends a command whose outcome is unknown.
5. **No parallel representations.** No new HYPRN MVP state duplicates an engine's authoritative state; the application stores references, associations, receipts and projections. A projection (search index, status projection, cached read) is rebuildable from its source and is never used as the source for authorization, quotations, writes or history.
6. **Interaction state stays with the client.** Nothing a server component or another client depends on lives only in a client.

The agent tool registry runs inside the application process but is a client of the API under this rule: it composes API operations (fetch the current revision, preview, commit) and keeps its own journal of calls, but every effect it causes is an operation owned by the module behind the API route it calls.

### Not mandated

Upholding the invariant does not require:

- A single physical backend or database.
- A durable workflow for every operation.
- A central orchestrator for all agent activity.
- Re-implementing capabilities that OpenMDAO, AiiDA or the modeling service already provide.

### What stays open

The agent-practices research (Phase 3 task 3.2a) and later agent work remain free to choose iterative read loops, planning and re-reading strategies, read-only sub-agents and research helpers within the existing agent rules, progressively loaded skills, playbook sections and tool sets, tool granularity, and provider bridges and protocol mechanics, as long as every effect on shared state goes through owner operations of the API.

### What plan checks verify

Every plan check traces to the central invariant: after the planned operation, every client can reference, inspect and act on its one authoritative outcome without reconstructing or repeating it.

- Each agent tool and each document operation that needs shared identity, durability, consistency, observability or recovery names one owner and a stored outcome (consequence 1).
- No planned client flow (UI, tool or command-line command) duplicates business orchestration, holds authoritative state, or re-executes an operation to reproduce a shared result (consequences 2 to 4 and 6).
- No planned HYPRN MVP state duplicates an engine's authoritative state; each projection is rebuildable and non-authoritative, with a test that a rebuild equals the incremental state (consequence 5).

### Consequences

- Good: what happened is always recoverable from its owner; clients stay thin and interchangeable; displayed results are the recorded ones.
- Good: plan checks have a concrete criterion for agent tools and document operations.
- Good: agent design stays open inside a clear boundary, and engines keep owning what they own.
- Bad: an interaction that a client could have chained quickly may first need a server-side command and an operation resource when it needs durability or recovery; this is accepted as the cost of one owner.
- Bad: the principle is enforced by review and plan checks, plus the tests each plan adds, rather than by one mechanism.

### Confirmation

- Plan checks apply the criteria above to every phase that adds agent tools or document operations.
- Tests in those phases show, for each coordinated operation they add, that a client stopped between calls leaves consistent stores and a readable outcome, and that a rebuilt projection equals the incremental one.
- The module-boundary test keeps the agent tool registry away from store, scientific and integration modules, and the UI contract checker keeps the UI on the public API.
