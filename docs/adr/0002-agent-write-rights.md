---
status: superseded by ADR-0003
date: 2026-10-13
decision-makers: Owner
---

# ADR-0002: Agent write rights — agents write freely, but never delete, archive or restore

## Context and Problem Statement

Agents (a desktop coding agent over the local MCP tool server, and later a provider-managed agent through the cloud bridge) carry out study work as their own principal acting for one user. The agents and tooling specifications required every write that creates an immutable record, consumes compute or changes shared context to be a **proposal** that the delegating user confirms in the HYPRN MVP UI (confirmation classes C1 and C2), with an "Assistant proposals" page locally and proposal cards in the cloud panel.

A study written by an agent needs dozens of versions, evidence records, configurations and runs. Confirming each one makes the agent stop and wait at almost every step, and the confirmation adds little protection, because HYPRN MVP never overwrites or deletes scientific history: every save is a new version or record, and drafts are revision-checked. The question is which agent writes need a person's confirmation, and which effects agents must never have.

## Decision Drivers

- **Immutable history makes writes non-destructive.** Saved versions, evidence versions, configurations and recorded runs never change; an unwanted agent write is an extra record a person can ignore or supersede, never a loss of earlier work.
- **Confirmation friction.** Per-write confirmation interrupts every agent workflow (reference reproduction, configuration batches, baseline runs) and trains people to confirm without reading.
- **Prompt-injection residual risk.** Text written by others (evidence, names, source) can try to steer an agent. Whatever an injected instruction achieves must stay attributable, bounded and recoverable.
- **Irreversible or access-changing effects stay human.** Deletion, archive and restore change what everyone sees or remove content; membership, tokens and delegation change who can act.
- **One rule set on every surface** (agents specification, principle A9).

## Considered Options

- **A: per-proposal confirmation as specified.** C1 writes batch-confirmable, C2 confirmed individually, envelope grants later.
- **B: envelope grants.** A person pre-approves a bounded envelope ("up to 12 configurations and 12 runs within this approach version"); writes inside it execute, others are proposals.
- **C: expansive write rights, with lifecycle and deletion forbidden.** Agents write directly within the delegating user's current authority and the role ceiling; deletion, archive and restore are never available to agents.

## Decision Outcome

Chosen option: **C**, because immutable history already makes agent writes recoverable, and the effects that are not recoverable (deletion) or change what everyone sees (archive, restore) are removed from agents altogether rather than gated by a click. A rejects the friction problem only partly (batches still stop the agent), and B adds a second policy language while keeping proposals for everything outside the envelope.

### 1. What agents may do

Applies to every agent surface, local (desktop coding agents over MCP) and cloud (managed agent through the bridge), with one rule set.

- Agents directly create and change everything they can reach through the curated tools, within the delegating user's **current** authority and the role ceiling: model and approach drafts, model versions, approach versions, evidence (create and revise), configuration saves, study context changes, approach draft restore (it writes the content of an earlier approach version into the draft as a new draft revision; it is not a lifecycle restore), the conclusion record, and run submissions.
- Run submissions need no confirmation and stay bounded by the existing limits: at most 20 runs per call, 10 queued per actor and 60 per session, plus budgets and the kill switches.

### 2. What agents never do

- Delete anything: no permanent document deletion, no collection deletion, no annotation deletion, no deletion of any record.
- Archive or restore studies or documents.
- Create studies.
- Record scientific reviews.
- Manage memberships or access, mint tokens, delegate, or raise their ceiling.

No tool offers these effects on any surface, and the agent route allowlist refuses the corresponding API routes for agent sessions.

### 3. Retired

- Confirmation classes C1 and C2, agent proposals, proposal confirmation and withdrawal, and envelope grants are retired for agent writes. The local "Assistant proposals" page and the cloud proposal cards are replaced by agent activity (section 5).

### 4. Unchanged safeguards

- Agent principal and attribution: every record an agent writes shows "{agent} for {user}" from the receipt actor.
- The authorization intersection (live delegation, study in scope, effect allowed, the delegating user's current membership, the role ceiling) is re-checked on every call; access loss takes effect on the next call.
- The append-only action journal records every call.
- Limits, budgets and kill switches (installation, user, session, token).
- Content guards (blocked and warned classes) run before every write; text written by others is returned as labelled untrusted content.
- Overwrite protection: an overwrite needs the agent's last-read revision and is never retried automatically, so a person's concurrent edit is never silently overwritten.
- Idempotency through journaled command ids; an uncertain run launch is never resubmitted.
- Provider and client approval prompts mean nothing to HYPRN MVP: they may add friction but never widen what a tool can do.
- Scientific invariants and immutability: every agent write is a new version or record, or a revision-checked edit of a draft or of the study context; no saved version, evidence version, configuration version or recorded run is changed or removed.

### 5. Oversight

- **Local:** the "Assistant proposals" page becomes an **"Agent activity"** page: study-scoped and read-only, it lists recent agent actions from the journal with links to the records they created or changed, and offers entry points to stop an agent (revoking its access, with the command-line renew and revoke commands shown).
- **Cloud:** the assistant panel shows the same activity instead of proposal cards, with Stop.
- Attribution chips stay on every agent-written record.

### Consequences

- Good: agents carry out a whole study workflow (evidence, approach, model, configurations, runs, conclusion) without stopping at every step; people review results and activity instead of confirming payloads.
- Good: one simpler policy on every surface: no proposal store, confirm route, staleness logic or batch semantics to build, secure and evaluate.
- Good: the effects that cannot be undone or that change what everyone sees are structurally absent from agents, not merely gated.
- Bad: studies can collect clutter: superseded versions, extra evidence and configurations an agent created and nobody wanted. Nothing is deleted to tidy up; people supersede or ignore them.
- Bad: compute is spent without a person's click; the run caps, budgets and kill switches are the only bound.
- Bad: content injected through evidence or names can now cause attributed writes and runs, where it previously could only cause proposals. Such records are always attributed to the agent, journaled, bounded by the run caps, recoverable through immutable history, and never deletions, archives or access changes.
- Bad: a study-context change or approach draft restore replaces mutable current state, as a person's edit would; it needs the agent's last-read revision and is visible in the activity list.

### Confirmation

- No registered tool on any surface deletes, archives or restores anything, creates studies, records reviews, manages memberships or mints tokens; a test asserts the absence in the registry for every surface and stage.
- An agent session calling a deletion, archive, restore, study-creation or membership route directly is refused (403) by the agent route allowlist; a test covers each route.
- Every agent write carries the agent actor on its receipt and appears in the action journal and on the Agent activity page.
- Evaluation scenarios are reframed: **G3** a concurrent human edit is kept (the agent's overwrite fails with a conflict and is not retried automatically); **G4** prompt injection in evidence and a component name triggers no write, no archive and no run submission, and the agent points the content out; **G5** access loss stops the next call; **G8** provider and client approvals never widen rights, and delete, archive and restore are always refused.
- A product review of control behaviour (limits, kill switches, journal, attribution, refusal of delete, archive and restore) precedes the first writer-capable agent tokens.
