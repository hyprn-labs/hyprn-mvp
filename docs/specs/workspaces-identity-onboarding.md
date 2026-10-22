# Workspaces, identity and onboarding

Status: current specification. This document defines who can use HYPRN MVP, how they get in, what they can see and do, and how work is organised above the study. It covers both editions of the product monolith: the **local edition** (delivered first: clone, `./hyprn-mvp setup`, `./hyprn-mvp start`) and the **cloud edition** (multi-user, later). Scientific records, the agent tool catalogue, source documents and the cloud infrastructure have their own specifications; this one states only the identity, access and collaboration rules they rely on.

Related specifications: architecture and contracts (`docs/specs/architecture-and-contracts.md`), agents (`docs/specs/agents.md`, tool detail in `docs/agents/tooling-spec.md`), documents (`docs/specs/documents.md`), user interface (`docs/specs/ui-target.md`); cloud infrastructure in the `hyprn-platform` repository (`docs/specs/cloud-platform.md`). Requirements: IAM-01 to IAM-06, COLLAB-01, COLLAB-02, OPS-01, OPS-04; related AGENT-05 to AGENT-07, SEC-01 (`docs/specs/requirements.md`).

Markers used throughout:

- **Decided**: an adopted product decision or a delivered, verified behaviour. Changes need a new decision recorded as an ADR.
- **Proposed**: the recommended design, not yet approved. Implementation needs approval of the relevant slice.
- **Open**: a question with a recommended default (section 18).

---

## 1. Summary

The local edition has one Owner with a generated password, no invitations, and a desktop coding agent connected through a local MCP tool server. The cloud edition adds organisations, user-owned workspaces, Owner/Reviewer/Admin roles, invitations, OIDC sign-in behind HYPRN MVP's own session, and a provider-managed assistant. Both share one data model and one authorization seam; section 14 compares them in detail.

---

## 2. Invariants

These hold in every edition and every release. **Decided.**

1. **HYPRN MVP authorizes.** An identity provider authenticates; HYPRN MVP records decide access. Identity-provider group or organisation membership never grants HYPRN MVP access by itself.
2. **Workspaces belong to users.** Every workspace has one owning user inside one organisation. There is no organisation-owned workspace and no organisation-wide visibility flag on records.
3. **Organisation membership grants no content.** Being in the same organisation, or being its Admin, does not reveal anyone's workspace. Access needs active organisation membership **and** either workspace ownership or an active workspace grant covering the operation.
4. **Three roles.** Owner, Reviewer, Admin. No Author role, no implicit co-owner, no non-owner editing role in the initial design.
5. **Stable identifiers.** Users are keyed by internal id mapped to a verified issuer and subject. Email addresses and display names are never identity keys and never create memberships (no domain auto-join).
6. **Server-established context.** The server derives the acting principal from the session or delegation. Client-supplied organisation, workspace or study ids are selectors that are checked, never trusted. Payloads cannot reassign organisation, workspace, owner or authorship.
7. **Concealment.** A principal without access to a study or workspace gets `404 resource_not_found`, not `403`; a member lacking the role for an operation gets `403 forbidden`. Replaying a command must not reveal an old receipt to someone who has lost access.
8. **Check at every boundary.** Authorization is checked on reads, mutation admission, queued dispatch, result delivery and downloads. Revocation takes effect on the next check, even when an identity-provider session is still valid.
9. **Agents never exceed their human.** An agent acts as its own principal on behalf of one human, with authority equal to the intersection of that human's current access, the delegation and a role ceiling. It never deletes a saved record, never archives or restores anything and never manages access (ADR-0003).
10. **Never delete studies.** Studies are archived and restored, never deleted. Archive state rows are themselves undeletable.
11. **Admin is not a content role.** Admins manage membership and organisation settings; they cannot silently grant themselves workspace access or take ownership. Ownership transfer is an audited operator procedure.
12. **No secrets in records, logs, URLs or outputs.** Passwords, session tokens, CSRF values, tool tokens, invitation secrets and provider keys are stored hashed or as protected files and never logged or returned.

Access protection beyond what the local edition already enforces may be deferred while it is costly, but the cloud invariants above are release blockers before any external organisation is onboarded.

---

## 3. Concepts and data model

### 3.1 Vocabulary

| Term | Meaning |
|---|---|
| Organisation | Tenant boundary and membership administration. Not a shared content space. |
| User | A human with a stable internal id, a verified external identity (cloud) or local credentials (local edition), and a status. |
| Organisation membership | A user's active or removed membership in one organisation, with role `member` or `admin`. |
| Workspace | A user-owned container for studies, source documents and workspace-local resources (later: method packages), with explicit grants to same-organisation colleagues. |
| Workspace grant | A user's access to someone else's workspace, with role Reviewer. Created by accepting a workspace invitation. |
| Study | The engineering question and its scientific records. Belongs to exactly one workspace. Study identities never change when workspaces are introduced. |
| Operator | The installation's platform operator (cloud). Creates organisations and their first Admin, performs audited recovery and ownership transfer. Not one of the three product roles. |

Naming note (Proposed): the current UI uses "workspace" for the study screen component. When the workspace container arrives, rename that component to the study workbench so the word keeps one meaning.

### 3.2 Entities (target)

The local edition uses User, Workspace, Study, Session, agent records and audit; organisation, membership, grant and invitation records are cloud-only (the local organisation and workspace are implicit, Proposed).

| Entity | Essential attributes and constraints |
|---|---|
| User | `user_id`, kind `human`, display name, status (`active`, `suspended`, `departed`); cloud: unique (`issuer`, `subject`); local: username, scrypt hash, failure counter, lock-until |
| Organisation | `org_id`, name, status |
| OrgMembership | unique (`org_id`, `user_id`), role `member` or `admin`, status; one active membership per user initially |
| Workspace | `workspace_id`, `org_id`, `owner_user_id`, name, status (`active`, `suspended`, `archived`) |
| WorkspaceGrant | unique (`workspace_id`, `user_id`), role `reviewer`, status, `granted_by`; grantee is an active member of the same organisation |
| Invitation | kind (`organisation`, `workspace`), target, recipient (verified email, or user id for workspace kind), role, token hash (organisation kind), expiry, inviter, state (`pending`, `accepted`, `declined`, `revoked`, `expired`) |
| Study | existing record plus `workspace_id`, not null once workspaces exist |
| Session | token hash, principal, CSRF hash, expiry; cloud adds the identity-provider session reference |
| Agent actor, delegation, tool token, action | As in `docs/specs/agents.md` and `docs/agents/tooling-spec.md` |
| Audit event | time, organisation, actor and on-behalf-of, action, target, outcome, request id; no secrets or private content |

Every tenant-owned record has an enforced path to its organisation and workspace (explicit keys and same-scope foreign keys; immutable records may carry scope through their owning aggregate). Ownership and scope fields are server-controlled. **Decided** (principle); exact schema **Proposed**.

The model does not impose one workspace per user; the initial cloud UI may still show a single "My workspace" (Open question O4).

---

## 4. Information architecture

### 4.1 Target navigation (cloud)

**Proposed** (workbench direction, not yet decided):

```text
Home
├── My workspace                      (the signed-in user's own workspace)
├── Shared with me                    (workspaces where the user holds a grant; shows owner and role)
└── Settings                          (account; organisation administration for Admins)

Workspace
├── Studies  |  Archived              (open, archive, restore; find a study)
├── Documents                         (source documents and collections; see docs/specs/documents.md)
├── Collaboration                     (members and invitations, review requests, activity)
└── Methods                           (later: workspace-local method packages)

Study workbench
├── Overview · Modeling approach · Model (Graph | XDSM, quantities below) · Configurations · Runs · Evidence
├── Canvas                            (views and typed commands only; never a second editable graph)
└── Assistant panel                   (study-scoped managed agent; shows agent activity and Stop)
```

Rules (**Decided** unless marked):

- One canonical editable home per entity. Study archive state lives on the Home study row; everything else shows a read-only view or a link.
- Organisation administration is a Settings function, never a workspace switcher. Admins without grants see no organisation-wide study list.
- When a user opens someone else's workspace, the header shows the owner and the user's role.
- "My workspace" and "Shared with me" are distinct.
- Before an Owner sends a workspace invitation, the dialog states that the grant covers all existing and future studies in the workspace. There are no secret per-study sub-areas in a shared workspace.
- Workbench docking (dockview core, wrapped behind one HYPRN MVP layout component), canvas (React Flow with XDSMjs) and assistant panel primitives (assistant-ui with AG-UI events over HYPRN MVP's own authenticated stream) are the **Proposed** engines; every one needs licence and provenance review before install (`docs/legal/licensing.md`).

### 4.2 Local edition navigation

**Decided** (delivered for Home; the rest follows the current study screens):

- Home lists studies with a **Studies | Archived** switch, Find a study, and per-row **Open study** and **Archive** (or **Restore** in Archived). No workspace switcher, no Shared with me.
- The study workbench is the current set of study screens. In the local edition the assistant is an external desktop coding agent; HYPRN MVP's UI hosts the **Agent activity** page where the Owner sees what that agent did, with links to the records, and can revoke its access (ADR-0003).
- Settings (Proposed): account (sign out; password recovery is a CLI operation), connected coding agents (list and revoke per-study tool tokens; minting is CLI-only; a separate token-management panel is deferred, so until it exists tokens are listed through the CLI and revoked through the CLI, the owner-session API and the Agent activity page), read-only installation facts. Installation configuration stays in the CLI.

---

## 5. Roles and permissions

### 5.1 Target matrix (cloud)

**Decided:**

| Operation | Owner | Reviewer (grant) | Admin without a grant | Agent for Owner | Agent for Reviewer |
|---|---|---|---|---|---|
| See the workspace and read its studies | Yes | Yes | No | Yes | Yes |
| Create a study | Yes | No | No | Yes, attributed; the Owner owns the new study and the delegation does not widen | No |
| Edit approach, evidence, models, configurations | Yes | No | No | Yes, directly: drafts under revision checks, new versions and records, attributed and journaled | No |
| Submit runs | Yes, subject to policy | No | No | Yes, directly, within the run limits and budgets | No |
| Archive or restore a study | Yes | No | No | Never | No |
| Record a scientific review | If eligible; self-review is labelled | If eligible for the named use | No | Yes, under the Owner's eligibility, attributed and labelled agent-recorded | Yes, under the Reviewer's eligibility, attributed and labelled agent-recorded (ADR-0005) |
| Request a review (Proposed) | Yes | No | No | Yes, attributed | No |
| Comment (Proposed) | Yes | Yes | No | Yes, attributed (O9) | No |
| Invite or remove workspace Reviewers | Yes | No | No | Never | Never |
| Delete a saved record (permanent deletion of source versions, collection deletion) | Yes, where the record allows it | No | No | Never | Never |
| Start an assistant session | Yes | Yes (review assistant) | No | n/a | n/a |
| Mint (CLI) or revoke (UI) a local study tool token | Yes (local edition) | No | No | Never | Never |
| Manage organisation members, invitations, settings | Only if also Admin | Only if also Admin | Yes | Never | Never |
| Share or publish a method package outside the workspace | Later, when that feature exists | No | No | Never | Never |

Additional rules (**Decided**):

- A user is Owner of their own workspace and may be Reviewer in others. Admin is an organisation attribute orthogonal to both.
- Agents never delete a saved record, archive or restore studies or documents, or manage access, whoever delegates them (ADR-0003, `docs/adr/0003-agent-write-rights-revised.md`). Draft (mutable working) material, such as draft content or a working annotation, they may change or delete under revision checks. An agent-recorded review is labelled as such, so later policy (for example a method package requiring an independent human review) can tell it apart.
- Review eligibility depends on the review's scope and independence rules, not on role alone. Role assignment never certifies competence. If policy requires independent review, the creator of the subject cannot satisfy it by changing roles.
- An Owner may publish their own unreviewed method where policy permits, with review status shown honestly (later scope).

### 5.2 Current implementation

**Decided** (delivered):

- Access is per study through `memberships(study_id, actor_id, role)` with roles `owner`, `writer`, `reader`. Creating a study makes the creator its `owner`.
- Read needs any membership; non-members get `404`. Writes need `owner` or `writer`; `reader` gets `403`. Membership changes need `owner`, are revision-checked commands with receipts, and refuse to remove the last owner.
- Membership management is not exposed by the API: the capability `membership_management` is listed as unavailable to every client. In practice each installation has one user, the owner of every study.
- Archive and restore are allowed for `owner` and `writer`.

### 5.3 Role mapping

| Current | Target | Rule |
|---|---|---|
| `owner` | Owner of the workspace containing the study | Decided |
| `reader` | Reviewer (workspace grant) | Decided |
| `writer` | No target equivalent | Proposed: retire `writer` when workspaces arrive; map any existing `writer` membership to Reviewer (narrowing, never broadening). Until then, keep it unassignable through any client (Open O3). |

---

## 6. Authentication

### 6.1 Local edition

**Decided** (delivered in the application; setup flow decided for the local edition):

| Aspect | Rule |
|---|---|
| Account | Exactly one human user; provisioning refuses a second. Username defaults to the operating-system short name. |
| Password | Generated at setup (at least 24 URL-safe random characters), provisioned on stdin, stored in an owner-only (0600) file under the data root, never printed. `./hyprn-mvp open` copies it to the clipboard (cleared after 90 s) and opens the UI. Accepted length 16–1,024; scrypt (N = 2^17, r = 8, p = 1) with a per-user salt. |
| Sign-in | `POST /api/1/session`. Unknown users are checked against a dummy hash (no timing oracle). Five consecutive failures lock the account for 60 s (`429`). |
| Session | Opaque 256-bit token stored hashed, 8-hour absolute lifetime, HttpOnly `SameSite=Strict` cookie scoped to `/api/1`, `Secure` under HTTPS. Sign-out deletes it. |
| CSRF and origin | Per-session CSRF token (stored hashed) in a header on every mutation; mutations must come from the configured origin and Host. The origin must be HTTPS or loopback HTTP. |
| Recovery | Local CLI only (no HTTP route): new password, lockout cleared, every session revoked. |
| Owner CLI | Acts as the Owner over loopback with the stored password (in memory only, never argv or environment), exact origin and CSRF. |

The local edition is a single-owner tool on one machine. It is not a security boundary against a hostile same-user process or coding agent; the residual risk of a same-user agent reading the password file is accepted and documented.

### 6.2 Cloud edition

Principles (**Decided**): managed sign-in through an identity provider for authentication, HYPRN MVP records for authorization; validation of issuer, subject, audience and expiry through an adopted, reviewed integration; HYPRN MVP's own secure session cookie, CSRF and origin rules; targeted session revocation; stronger authentication for Admins and operators (exact factors chosen at provider adoption); no duplicate customer password store in HYPRN MVP.

Design (**Proposed**):

| Aspect | Proposal |
|---|---|
| Identity provider | Keycloak 26 or later (Apache-2.0), self-hosted, using its Organizations feature for tenant identity, per-organisation enterprise identity-provider brokering (SSO) and email domains. Themed login pages with Keycloakify, styled with the design-system tokens. Lighter alternative: Casdoor (after a security-history review). Excluded by the permissive-licence rule: identity servers under AGPL or with paywalled multi-tenancy. |
| Integration | HYPRN MVP acts as a backend-for-frontend: it runs the OIDC authorization-code flow with PKCE (Authlib in FastAPI), validates the ID token, maps (`issuer`, `subject`) to the internal user, then issues its existing opaque session cookie and CSRF token. Browsers and agents never hold identity-provider tokens for the HYPRN MVP API. |
| Membership ownership | HYPRN MVP owns organisation memberships, roles, workspace grants and invitations. Keycloak organisations are used only to route sign-in to the right identity provider and verify email domains; their membership lists are not consulted for authorization, so membership is never owned twice. |
| Factors | MFA required for Admins and operators. For members: identity-provider default (password plus optional MFA, or enterprise SSO); email magic links only if data sensitivity allows. |
| Session | Same mechanics as local, 8-hour absolute lifetime. Every request rechecks active organisation membership and status. Users can list and end their other sessions; Admins can end a member's sessions; removal ends them all. Sign-out also ends the identity-provider session. |
| Agents | Never sign in. They receive server-minted delegated sessions (section 9). |

Adopting an external identity service changes the approved architecture (credentials move out of the Python application) and therefore needs an explicit decision recorded as an ADR. It must also remain self-hostable: cloud-only identity must not become a mandatory dependency for disconnected or customer-hosted installations.

---

## 7. Onboarding and invitations

### 7.1 Local edition setup

**Decided:**

1. `git clone` the product repository.
2. `./hyprn-mvp setup`: checks prerequisites (container engine, git, disk, memory, port free, checkout and data folder not in a cloud-synced location), asks first-run questions with defaults (data folder: the per-OS default folder named `hyprn-mvp` unless a flag, `HYPRN_MVP_*` variable or installation configuration says otherwise; port; owner username), initialises stores, provisions the Owner with a generated password, builds and attests the worker. Idempotent.
3. `./hyprn-mvp start`, then `./hyprn-mvp open` (copies the password and opens the UI).
4. `./hyprn-mvp study new "<name>"`: creates the study through the API as the Owner, mints a study-scoped tool token, stores it in the OS credential store (the macOS Keychain on macOS), and creates a study folder outside the source repository (default `~/hyprn-mvp-studies/<slug>/`) holding agent instructions and MCP client configuration but no token.

There are no invitations in the local edition.

### 7.2 Cloud organisation onboarding

Decided principles: invitation-only; first release is an invited pilot; organisation creation and first-Admin onboarding are operator-controlled; invitations are bounded, single use where acceptance is needed, and recheck inviter authority at acceptance; email-domain matching never creates membership; one active organisation membership per user initially.

Flow (**Proposed** details):

1. The operator creates the organisation and invites its first Admin.
2. An Admin invites members into an organisation they administer, choosing role `member` or `admin`.
3. The invitation binds a single-use 256-bit random token (only its hash is stored) to the organisation, the recipient's email, the role, the inviter and an expiry of 72 hours. The link carries the token in the URL fragment or a one-time path segment, never with personal data in query parameters.
4. The recipient signs in through the identity provider. HYPRN MVP checks, in one transaction, that the verified email matches, the invitation is pending and unexpired, and the inviter is still an active Admin.
5. Acceptance consumes the invitation and creates or reactivates the membership atomically. Concurrent acceptance yields exactly one membership.
6. On first sign-in with an active membership, HYPRN MVP creates the user's own workspace ("My workspace").
7. Signing in without an active membership shows a neutral "no access" page and grants nothing.

Admins can resend (which revokes and reissues) and revoke pending invitations. The last active Admin cannot be removed or demoted until a replacement exists; losing every Admin requires operator recovery.

### 7.3 Workspace invitations

Decided: only the Owner invites; the recipient must already be an active member of the same organisation; a workspace invitation never creates organisation membership or cross-organisation access; it grants Reviewer.

Flow (**Proposed** details):

1. The Owner picks a colleague from the organisation's member directory (name and email only; no visibility of their workspaces) and confirms the scope statement (section 4.1).
2. HYPRN MVP creates a pending workspace invitation addressed to that user id, expiring after 14 days. No email token is needed because the recipient is already a signed-in member; an email notification only links to HYPRN MVP.
3. The recipient sees it under Shared with me and accepts or declines. Acceptance rechecks both users' active membership in the same organisation, the Owner's authority and the invitation state, then creates the grant atomically.
4. The Owner can revoke a pending invitation or remove a Reviewer at any time. Removal ends access on the next check, cancels the Reviewer's pending agent work, and stops delivery of results to them. Already downloaded files cannot be recalled.

### 7.4 Removal, departure and recovery

**Decided:**

- Removing an organisation membership disables all access in that organisation, including workspace grants, pending invitations sent by that user, assistant sessions and tool tokens, and pending queued work, even while the identity-provider session remains valid.
- If an Owner departs, the workspace and its history are preserved; new writes and dispatch are suspended by default. Existing Reviewers may keep read access under the retention policy. Reactivation or transfer to another same-organisation user is an explicit, audited operator procedure; Admins do not inherit content; cross-organisation transfer and casual reassignment are excluded; reactivation never relaunches queued work silently.
- Already started scientific processes keep their honest lifecycle outcomes after access is lost.

---

## 8. Authorization model and its evolution

### 8.1 Current check

**Decided** (delivered): `Store.authorize(db, actor, study, write, owner)` runs inside the same transaction as the operation and implements the rules in section 5.2. All study-scoped reads and commands go through it; idempotent replays reauthorize before returning an earlier outcome.

### 8.2 One seam: `can()`

**Proposed:** introduce one function in the application, `can(principal, action, resource)`, used by every route, tool handler, background consumer and download path. Routes never query memberships directly. It starts as a thin wrapper over today's study membership check, so behaviour does not change.

Evaluation once workspaces exist:

```text
human may do action on resource  ⇔
    user.status = active
  ∧ active membership in resource.org
  ∧ ( resource.workspace.owner = user  ∨  active grant(user, resource.workspace) whose role permits action )
  ∧ resource.workspace.status permits action        (suspended workspaces refuse writes and dispatch)

agent may do action on resource  ⇔
    delegation live, unexpired, not revoked, kill switches off
  ∧ resource within delegation scope  ∧  action's effect in allowed effects  ∧  action within role ceiling
  ∧ the delegating human may do action on resource   (evaluated now, not at delegation time)
```

Admin status never appears in content rules; it is checked only for organisation administration actions.

### 8.3 Second layer in the cloud

**Decided** target for multi-organisation operation: the application store moves to PostgreSQL, with restricted request roles and row-level security policies driven by verified transaction-local user and organisation context. Missing context denies; pooled connections never carry a prior identity; migration and operator credentials are separate; policy-bypassing roles and functions are audited. Row security is additional protection, not a substitute for `can()`. Database provisioning belongs to the cloud platform specification in `hyprn-platform`.

### 8.4 When to adopt OpenFGA

**Proposed, deferred:** keep `can()` backed by SQL while access is "owner or grant on one workspace". Adopt OpenFGA (Apache-2.0) behind the same seam when inheritance arrives: organisation → workspace → study → document or comment, plus per-resource sharing such as same-organisation method package grants. Then:

- HYPRN MVP records stay authoritative; relationship tuples are written from an outbox in the same transaction as the record change, and a reconciler detects drift.
- List queries ("which studies can this user see") use the authorization service's list operations or a reconciled projection, never client-side filtering.
- Fall back to SpiceDB if strong consistency tokens become necessary. Exclude AGPL or deprecated authorization engines.

---

## 9. Agent principals and delegation

This section restates only the identity rules; tools, the write policy and runtime behaviour are in `docs/specs/agents.md` and `docs/agents/tooling-spec.md`. **Decided** unless marked.

### 9.1 Principal and delegation

- Each agent is an actor of kind `agent` (display name, delegating human, surface, provider and model), one per delegator, surface and installation. It has no password and cannot reach the session endpoint. Receipts record the agent actor; the UI shows "<agent name> for <delegator>".
- A human-created delegation fixes the agent actor, delegator, surface, scope (one study, or the workspace in the cloud panel), role ceiling, allowed effects, budgets, expiry and revocation.
- `study_id` is never a tool argument; the runtime injects it from the delegation. A workspace-scoped cloud session can list, open and create studies; opening re-scopes after checking the delegator's access. Local tokens are always study-scoped. A study an agent creates is owned by the delegator; the agent's delegation does not reach it until the delegator gives access.
- HYPRN MVP mints a 15-minute delegated API session for the agent, held only in server memory and never sent to the provider, desktop client, browser or logs.

### 9.2 Role ceiling

| Delegator's role | Ceiling | Effects |
|---|---|---|
| Owner | writer | read, draft, record (including study creation and, once the record exists, reviews), submit, outside-study notes; directly, attributed and journaled (ADR-0003) |
| Reviewer | reader + review | read, record scientific reviews, progress notes and platform-issue reports (review assistant, ADR-0005) |
| Admin without grant | none | none |

An agent can never delete a saved record, archive or restore studies or documents, grant access, change membership, invite, delegate further, mint tokens, change roles, raise its ceiling or sign in. Provider or client approvals never widen these rights.

### 9.3 Surfaces

| Surface | Credential | Notes |
|---|---|---|
| Cloud, custom-tool bridge (default) | None at the provider. HYPRN MVP maps provider session → agent session → delegation. | The provider-managed agent (OpenAI or Claude) calls HYPRN MVP's curated tools; HYPRN MVP executes them in-process through the API. |
| Cloud, remote MCP (fallback) | Short-lived OAuth access token per delegation, audience-bound to `/mcp`, held in the provider's credential vault. | Only if the bridge cannot meet requirements. |
| Local MCP | Per-study tool token: 256-bit random, stored hashed, audience `/mcp`, never valid on `/api/1`. Minted by the Owner through the CLI, shown once (printed only with `--show-token` on an interactive terminal), listed and revoked through the CLI and the owner-session API, revocable from the Agent activity page; 8-hour default lifetime (24 h maximum), manual renewal. Kept in the OS credential store (the macOS Keychain on macOS) and passed by the CLI's stdio relay; never in files, argv or logs. A writer's or Owner's token writes within that user's current authority, every write attributed; a reader's token reads. Further controls come with a later product decision. | MCP is the only sanctioned path from a local coding agent to HYPRN MVP. Archive and restore stay human actions; a study an agent creates needs its own token, minted by the Owner, before the agent can work in it. Browser sessions are never valid on `/mcp`. |

Kill switches: installation-wide (`agent.enabled` off refuses new sessions, tokens and tool calls), per user, per session (Stop), per token (Revoke). Stopping the assistant is not cancelling a run.

---

## 10. Collaboration

Collaboration features exist only in the cloud edition. Every collaboration artefact is a HYPRN MVP record under the same authorization and audit rules; none is owned by an editor library or a hosted service.

### 10.1 Presence

**Proposed, deferred until multi-user cloud:** show who else is viewing a workspace or study (avatars in the header), delivered over HYPRN MVP's authenticated event stream and filtered by current authorization. Live cursors and co-editing use the Yjs awareness protocol only where authored documents are co-edited (Tiptap with Yjs, served by a Python sync endpoint that reuses the HYPRN MVP session, origin checks and study authorization). Presence is ephemeral and never stored as history.

### 10.2 Comments

**Proposed:** a comment thread is a HYPRN MVP record anchored to an exact subject version (study context, approach, model, configuration, run, evidence, or a range in an authored document anchored with Yjs relative positions). Owner and Reviewers comment; the author or the Owner resolves and reopens; only authors edit, with edits retained. Comments are discussion, never assumptions, rationale or evidence, which keep their single canonical homes (a comment may link to them), preserving the one-Assumption-concept rule. Editor vendors' paid comment and history features are not used.

### 10.3 Review requests and reviews

**Proposed** (the review record itself belongs to the method packages and review work): a review request records the requester (Owner), requested Reviewer, exact subject versions, the named use, a message, state (`open`, `accepted`, `declined`, `withdrawn`, `completed`) and an optional due date. Completing it creates a review: an attributed decision about those exact subjects for that use, with evidence, limitations and unresolved objections, marked self or independent. Later versions of a subject show the review as applying to the earlier version and never rewrite it.

### 10.4 Notifications

**Proposed:** in-app notifications only at first (invitation received, review requested, review completed, comment mention, access removed). Email is used only for organisation invitations and, optionally, a link-only notice that carries no study content.

---

## 11. Settings

**Proposed** structure; behaviours referenced are decided where marked elsewhere.

| Area | Who | Contents |
|---|---|---|
| Account | Every user | Display name, theme (System, Light, Dark), active sessions with "sign out other sessions"; cloud: link to the identity provider's account page for password and MFA; local: password change and recovery are CLI operations. |
| Assistant | Every user | Enable or disable my assistant; my spend this month against the per-user cap (cloud); connected coding agents and their tool tokens with revoke (local; renewal is a CLI operation, and the panel itself is deferred, see section 4.2). |
| Workspace | Owner | Name; members and pending invitations; remove a Reviewer. Reviewers see the member list read-only. |
| Organisation | Admin | Members and roles, organisation invitations, last-Admin protection, sign-in configuration (SSO and verified domains, through the identity provider), organisation assistant policy (allowed providers, spend caps within installation limits), administrative audit log. No content access. |
| Installation | Operator (cloud) or CLI (local) | Edition, data folder, ports, agent kill switch, provider keys. Never editable from the product UI. |

---

## 12. Archive and restore

**Decided** (delivered):

- Archive applies to the whole study for everyone with access: it leaves Home and appears under **Archived**, where it can be opened and restored, after a confirmation ("It disappears from Home for everyone. Nothing is deleted; restore it from Archived.").
- `POST /api/1/studies/{id}/archive` and `/restore` are idempotent commands (body `command_id`) with durable receipts. The study record, its revision and its scientific records do not change.
- Archive state has its own table whose rows a database trigger refuses to delete; each transition records actor and time.
- `GET /api/1/studies` lists non-archived studies by default and only archived ones with `archived=true`; the study read includes `archived`.
- Authorization today: `owner` or `writer`; `reader` `403`; non-members `404`. Agents never archive or restore, on any surface (ADR-0003).

**Proposed** for the cloud edition:

- Archive and restore become Owner-only (Reviewers cannot hide the Owner's work).
- Workspace archive (hide a whole workspace from Home and Shared with me, never delete) follows the same pattern if multiple workspaces per user are offered.
- Archiving does not revoke grants; removing access is a separate operation.

Studies are never deleted. Disposable development run data may be reset under the separate development-run rules; that never touches studies, users, credentials or authoring records.

---

## 13. Audit

**Decided** (current): every study mutation is a command with a receipt recording scope, category, command id, actor, payload digest, state and outcome; the receipt actor is the authenticated principal (human or agent). Sign-in failures and lockout are tracked on the user. Agent sessions and actions are recorded in append-only agent tables (`docs/specs/agents.md`), with argument digests rather than raw source or evidence bodies.

**Proposed** (target): append-only audit events for authentication (sign-in, failure, lockout, sign-out, session revoked, recovery), organisation administration (invitations, role changes, removals, last-Admin refusals), workspace access (invitations, grants, removals, suspension, transfer), assistant control (delegations, token mint, renew and revoke, kill switches, Stop) and operator procedures. Users see their own authentication events; Admins see their organisation's administrative events; the Owner and Reviewers see their workspace's access events; operators see all of these but no content.

Audit events are append-only, carry request ids, and never include passwords, tokens, invitation secrets or private study content. Retention: one year for administrative and access events (Proposed); agent transcripts follow the agents specification (90 days, with provider-side sessions deleted at the same point).

---

## 14. Local edition versus cloud edition

The edition is chosen by installation configuration over one shared core (**Decided**). The shared core holds the data model, `can()`, sessions, CSRF, receipts and archive; editions supply adapters.

| Capability | Local edition | Cloud edition |
|---|---|---|
| Users and sign-in | One Owner, generated password, local CLI recovery | Invited users, OIDC through the identity provider, MFA for Admins and operators |
| Organisations | One implicit organisation, not shown (Proposed) | Operator-created, Admin-managed |
| Workspaces | One implicit workspace owned by the Owner, not shown (Proposed) | User-owned, with Reviewer grants |
| Invitations and collaboration | None | Organisation and workspace invitations; comments, review requests, presence later |
| Authorization | Study membership check behind `can()` | `can()` with workspace grants, PostgreSQL row security; OpenFGA later |
| Application store | SQLite today (engine for the local edition after IAM is Open O7) | PostgreSQL |
| Assistant | Codex or Claude Code desktop apps over local MCP, per-study token in the OS credential store, oversight on the local Agent activity page | Provider-managed agent over the custom-tool bridge, assistant panel with agent activity and Stop |
| Agent writes | Direct, attributed and journaled, study creation included; no deletion of saved records, archive, restore or access management (ADR-0003) | Same |
| Archive | Owner (and today `writer`) | Owner only (Proposed) |
| Security boundary | Single user on one machine; not a boundary against same-user processes | Full tenant isolation; cross-organisation or private-workspace disclosure is a release blocker |

Modelling the local edition as one organisation with one workspace keeps a single code path: a local installation's studies can later be exported to a cloud workspace without re-keying, and nothing in the core branches on edition for access decisions.

---

## 15. Evolution from the current implementation

**Decided:**

- Introduce organisation and workspace ownership through explicit mappings that preserve each study's current owner access. Never assign existing studies to one shared workspace if that would broaden access.
- Study ids and scientific records stay stable. Development runs need no migration; scoped resets are allowed under the development-run rules. Protected authoring and access records are preserved and transferred with a write freeze and backup, rehearsed on copies first; after PostgreSQL accepts new protected writes, falling back to the earlier SQLite file is not a rollback.

**Proposed order** (each step behind its release gate):

1. `can()` seam over today's checks, no behaviour change.
2. Agent principal, delegation and per-study tool tokens (the first agent slice).
3. Implicit local organisation and workspace; `studies.workspace_id` populated for every study.
4. Cloud: identity-provider sign-in behind HYPRN MVP sessions; organisation memberships and invitations; "My workspace" on first sign-in.
5. Workspace grants, Shared with me, Reviewer role; retire `writer`.
6. PostgreSQL with row security; protected-data cutover; fresh runs prove history.
7. Comments and review requests as records; presence and co-editing only when authored documents need them.
8. OpenFGA when inheritance or per-resource sharing arrives.

---

## 16. Acceptance

Cloud release blockers (**Decided**):

| Test | Required outcome |
|---|---|
| Two users in one organisation | Separate private workspaces; an invitation grants only the chosen workspace and role |
| Foreign-organisation user | Cannot accept an invitation or retrieve content by guessed ids, history, snippets, logs, exports, search, downloads or provider context |
| Reviewer | Cannot edit, submit runs, archive or invite |
| Owner | Can create, edit and manage the workspace; cannot label own work as independently reviewed |
| Admin without grant | Cannot inspect private content or take ownership |
| Invitations | Expired, replayed, revoked or wrong-recipient invitations fail; concurrent acceptance creates one membership or grant |
| Revocation | Affects API requests, downloads and pending agent and job admissions; started processes keep honest outcomes |
| Database context | Missing or stale transaction context denies; an unfiltered query under the request role exposes no unauthorized rows |
| Dependency closure | Sharing a workspace exposes its dependency closure but no other workspace; unauthorized references cannot be smuggled into shared records |
| Owner departure | Suspends writes and dispatch without giving Admins content access or deleting history |
| Agent parity | An agent for a Reviewer cannot write except recording scientific reviews (ADR-0005); an agent for an Owner loses access the moment the Owner does and can never delete saved records, archive, restore or manage access; a study it creates belongs to the Owner; tokens and sessions of one user are invisible to another |

Local edition (**Decided**): second-user provisioning refused; wrong origin or missing CSRF refused on mutations; lockout after five failures; recovery revokes sessions; tool token refused on `/api/1` and for other studies; browser session refused on `/mcp`; no token or password in study folders, argv or logs; archived studies hidden from Home and restorable; archive rows undeletable.

---

## 17. Out of scope

**Decided** exclusions for the initial cloud release:

- Organisation-owned workspaces, organisation-wide visibility, and Admin access to content.
- Non-owner editing roles, an Author role, co-ownership and collaborative source or model editing by Reviewers.
- Multiple simultaneous organisation memberships per user, cross-organisation invitations and organisation transfers.
- Self-service public sign-up.
- SCIM provisioning and custom per-record collaborator lists.
- Resource-level sharing outside a workspace (starts later with same-organisation method package grants, then explicit public releases).
- Deleting studies.
- A professional-credential registry for reviewers.

---

## 18. Open questions

| # | Question | Recommended default |
|---|---|---|
| O1 | Adopt Keycloak as the cloud identity provider, accepting a self-hosted JVM service and an ADR changing where credentials live? | Yes, behind HYPRN MVP's own sessions, with HYPRN MVP authoritative for memberships; decide before cloud onboarding work starts. |
| O2 | Use Keycloak's built-in organisation invitations, or HYPRN MVP's own? | HYPRN MVP's own, so invitation state, audit and authority checks have one owner. |
| O3 | What happens to the `writer` role? | Keep it unassignable now; retire it when workspaces arrive, mapping any existing `writer` to Reviewer. |
| O4 | One workspace per user in the first cloud UI, or several? | One ("My workspace"); the model allows more later. |
| O5 | Workspace invitation lifetime and acceptance | In-app acceptance, 14-day expiry. Organisation invitations 72 hours. |
| O6 | Who may archive and restore in the cloud? | Owner only. |
| O7 | Does the local edition move to PostgreSQL when IAM lands, or stay on SQLite? | Follow the single-engine rule (no permanent dual-engine business behaviour): PostgreSQL for both once IAM lands, run locally as a container, unless local install cost proves unacceptable, in which case record a scoped exception. |
| O8 | Are local organisation and workspace records explicit rows or implicit constants? | Explicit rows created at setup, hidden in the UI, so export to cloud keeps ids. |
| O9 | May an assistant post comments or request reviews? | Yes for an Owner's assistant, attributed, once comments and review requests exist (ADR-0003); a Reviewer's assistant stays read-only. Status and own work notes still go to progress notes outside the study. |
| O10 | Member login factors in the cloud | Identity-provider password plus optional MFA, enterprise SSO where the organisation has it; MFA mandatory for Admins and operators. |
| O11 | Audit log retention | One year for administrative and access events, configurable per installation. |
| O12 | Presence before co-editing? | Only after the first multi-user pilot shows a need; start with header avatars over the existing event stream. |
