---
status: accepted
date: 2026-10-13
decision-makers: Owner
---

# ADR-0003: Agent write rights, revised — only deletion of saved records, archive and restore, and access management are human-only

Supersedes [ADR-0002](0002-agent-write-rights.md).

## Context and Problem Statement

ADR-0002 let agents write directly within the delegating user's authority and retired proposals and confirmation. It also removed some effects from agents that are neither destructive nor access-changing: creating a study and recording a scientific review. And it forbade every deletion, including deletion of working material such as an annotation or part of a draft, which removes no saved history.

The product owner corrected the boundary on 2026-10-13. The human-only effects should be exactly the ones that remove saved work, change what everyone sees through lifecycle, or change who can act. Everything else a person may do in a study, their agent may do for them, within the same limits and safeguards. The question is which effects stay human-only, how draft (working) material is treated, and what that means for collections, run submissions and agent-recorded reviews.

## Decision Drivers

- **Immutable history makes writes recoverable.** Saved versions, evidence versions, configurations and recorded runs never change; an unwanted agent write is an extra record a person can ignore or supersede.
- **Draft material is working state.** A draft, or an annotation used as working material, is mutable by design and is never pinned by history; frozen copies (for example an annotation snapshot inside an evidence version) are separate immutable records. Removing working material loses no saved history.
- **Deletion of saved records, archive and restore, and access management are different in kind.** The first removes something history or other people may rely on; the second changes what everyone sees; the third changes who can act. These stay with people.
- **Attribution already distinguishes who acted.** Every record shows "{agent} for {user}", so an agent-created study or an agent-recorded review is visibly the agent's.
- **One rule set on every surface** (agents specification, principle A9).

## Considered Options

- **A: keep ADR-0002.** Agents never delete anything, never create studies and never record reviews.
- **B: narrow the human-only set to deletion of saved records, archive and restore, and access management**, with an explicit rule for draft material, collection membership and run submissions.
- **C: allow agents to delete saved records behind a per-deletion confirmation.**

## Decision Outcome

Chosen option: **B**, because it removes restrictions that protected nothing (study creation, reviews, working material) while keeping every effect that loses saved work, changes what everyone sees or changes access out of agents' reach. A keeps restrictions with no safety benefit and forces people to do routine steps by hand. C brings back confirmation for the most damaging effect, which ADR-0002 rightly removed from agents altogether.

### 1. Human-only effects

On every agent surface, local (desktop coding agents over MCP) and cloud (managed agent through the bridge):

- **Deleting a saved record**: any record that is saved, versioned or read-only. This covers model, approach, configuration and evidence versions, runs, the conclusion record, scientific reviews, documents and their source versions, collections (deleting a collection is deletion, even though its documents remain) and every other saved record. Studies are never deleted by anyone.
- **Archiving and restoring**: studies and documents. Restoring (for documents, unarchiving) is the undo of archiving and stays human-only.
- **Access management**: memberships, invitations, delegations, tool tokens, role changes and raising a ceiling.

No tool offers these effects on any surface, and the agent route allowlist refuses their API routes for agent sessions.

### 2. What agents may do

Everything else within the delegating user's **current** authority and the role ceiling, directly, attributed and journaled:

- drafts (model and approach drafts, approach draft restore, which writes an earlier version's content into the draft as a new draft revision and is not a lifecycle restore), model and approach versions, evidence (create and revise), configurations, study context changes, the conclusion record and run submissions;
- **creating studies**: the new study's Owner is the delegating user (an agent never holds a membership); the study shows the agent attribution. Creating a study does not widen the agent's delegation: the agent works in the new study only after it receives access there the way any study is opened to an agent (in the cloud, opening it in a workspace-scope session after the membership check; locally, a study token the Owner mints through the command line);
- **recording scientific reviews**, once the review record exists, under the same eligibility rules as the delegating user (a self-review is labelled as such);
- collection organization, annotations, extraction requests, citations and, when they exist, comments and review requests.

Run submissions need no confirmation and stay bounded by the existing limits: at most 20 runs per call, 10 queued per actor and 60 per session, plus budgets and the kill switches.

### 3. Draft rule

Anything in draft (mutable working) state may be operated on freely by an agent, including deletion: removing a component, step, case or limit from a draft, discarding draft content, or deleting a working annotation. Each such change is revision-checked (it needs the agent's last-read revision) and attributed. Once a record is saved, versioned or read-only, an agent can never delete it. Frozen copies, such as an annotation snapshot inside an evidence version, are saved records and are never affected by changes to the working material they were taken from.

### 4. Collections

Agents may change collection membership (add, remove, replace a member version) in revision-checked batches. Membership never pins history: every run, configuration and evidence version stays pinned to the exact versions it used, and removing a member deletes no document, version or citation. Deleting a collection is deletion and is human-only.

### 5. Runs

A run submission whose configuration is not ready to run (it would fail before computing anything, for example because a free input is unassigned, a reference does not resolve or execution readiness is not ready) is refused outright: no run is created and nothing is queued; the refusal states the reasons. The check belongs to the execution owner behind the API, so it holds whatever the client checked beforehand.

### 6. Labelling of agent-recorded reviews

A scientific review recorded by an agent carries the standard "{agent} for {user}" attribution and is shown as **agent-recorded**, so later policy (for example a method package that requires an independent human review) can tell it apart. This is labelling only; it adds no restriction now.

### 7. Retired and unchanged

- Still retired (from ADR-0002): confirmation classes C1 and C2, agent proposals, proposal confirmation and withdrawal, envelope grants, the local "Assistant proposals" page and the cloud proposal cards.
- Unchanged safeguards: attribution "{agent} for {user}" on every record from the receipt actor; the authorization intersection (live delegation, scope, allowed effect, the delegating user's current membership, the role ceiling) rechecked on every call; the append-only action journal; limits, budgets and kill switches (installation, user, session, token); content guards before every write and labelled untrusted content; overwrite protection (the agent's last-read revision, no automatic retry); idempotency through journaled command ids and never resubmitting an uncertain run launch; provider and client approval prompts never widen rights.
- Unchanged oversight: the study's **Agent activity** page locally (journal-backed, read-only, with a way to stop an agent by revoking its access) and the same activity with Stop in the cloud assistant panel; attribution chips on every agent-written record.
- Role ceilings are unchanged: an agent acting for a Reviewer stays read-only, so it cannot record reviews. Letting a Reviewer's agent record reviews would need a separate decision to widen that ceiling.

### Consequences

- Good: agents can start a study and record attributed reviews; clean-up of working material (annotations, draft content) no longer needs a person.
- Good: the human-only set has one reason each: saved work is never lost, lifecycle changes for everyone stay with people, access stays with people.
- Good: run submissions that would fail are refused at the owner, so agents cannot fill a study with runs that never computed anything.
- Bad: an agent can delete a person's working annotation or draft content. Mitigation: revision checks keep a person's concurrent edit, every change is attributed and listed in agent activity, and frozen copies in evidence are untouched.
- Bad: an agent can create studies nobody asked for. Mitigation: attribution, the activity list, the delegation scope (the agent cannot act in the new study without access a person grants) and archive (by a person).
- Bad: agent-recorded reviews may be taken for human judgement. Mitigation: the agent-recorded label on every such review and the self-review label.

### Confirmation

- No registered tool on any surface deletes a saved record, archives, restores (or unarchives) anything, or manages memberships, invitations, delegations, tokens or roles; a test asserts the absence in the registry for every surface and stage.
- An agent session calling such a route directly is refused (403) by the agent route allowlist; a test covers each route, including the document and collection deletion, archive, unarchive and restore routes.
- A test shows an agent creating a study: the delegating user is its Owner, the receipt actor is the agent, and the agent's delegation does not reach the new study.
- Tests show the draft rule: an agent removes draft content and deletes a working annotation with its last-read revision; a stale revision conflicts with no effect; a frozen annotation snapshot in evidence is unchanged.
- A test shows a run submission with a configuration that is not ready refused with reasons and no run created.
- When the review record exists, a test shows an agent-recorded review attributed "{agent} for {user}" and labelled agent-recorded.
- Evaluation scenario G8 is reframed: with every provider or client approval set to auto-approve, deletion of saved records, archive, restore and access changes stay refused, and every write is attributed and journaled.
- A product review of control behaviour (limits, kill switches, journal, attribution, refusal of the human-only effects) precedes the first writer-capable agent tokens.
