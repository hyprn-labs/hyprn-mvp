# Embedded study assistant

The Assistant panel uses one Claude Managed Agents conversation per study.
Hiding the panel or switching pages does not stop a turn. Reopening it reads the
same stored conversation. The conversation belongs to the study; messages retain
their human actor and tool effects retain the delegated Assistant attribution.

Claude owns reasoning and context. HYPRN forwards complete custom tool requests
to the same registry and runtime used by coding agents. The managed agent has
no built-in execution tools, MCP servers or provider workflows. Scoped managed
subagents use the same authorized HYPRN tools and cumulative user allowance. Scientific
execution still happens only in HYPRN's attested worker.

## Installation

The application uses the existing locked httpx dependency. No provider SDK or
agent-side shell is needed. Keep the API key in an owner-only regular file outside
the repository and synchronized storage. Never put the key in browser code.

Configuration is explicit through the application environment:

| Setting (prefix `HYPRN_MVP_ASSISTANT_`) | Meaning |
| --- | --- |
| `KEY_FILE` | Absolute private credential-file location |
| `AGENT_ID`, `AGENT_VERSION` | Exact provisioned custom-tool agent version |
| `ENVIRONMENT_ID` | Restricted managed environment |
| `DEFINITIONS_SHA256` | Digest of the offered Claude writer tool definitions |
| `TOTAL_CENTS` | Legacy installation approval retained for deployment continuity; not an active spending cap |
| `PRIOR_CENTS` | Previously incurred USD list cost outside this installation (default 0) |
| `APPROVED_MINOR`, `APPROVED_CURRENCY` | Optional paired original approval amount in cents and three-letter currency |
| `CONVERSION_DATE` | Optional date of the explicitly configured approval conversion |

`HYPRN_MVP_AGENT_ENABLED=true` is also required. Missing configuration disables
the panel. Partial configuration fails startup; a changed catalogue disables new
work until the explicitly pinned provider definition is reviewed and reprovisioned.

Use the release's `deployment.managed_assistant` command for provider resource setup.
It calls `assistant.claude.agent_definition` with the current registry's
`claude_managed` definitions at `LOCAL_STAGE` and writer effects, and embeds the
packaged playbook. Tools and guidance are never copied into a second registry.
The model and effort are explicit installation choices; the command has no model
default. The currently reviewed configuration is `claude-sonnet-5-5`, high effort,
standard speed. Updating the reviewed choices requires a new offline plan.

## Reviewable provider setup

Run this module with the release's locked Python application environment, with the
repository root and `application/src` available on its module path. In the commands
below, `APP_PYTHON` is that interpreter, `PRIVATE_SETUP_DIR` is an existing owner-controlled
directory outside the checkout and synchronized storage, and `KEY_FILE` is an owner-only
credential file. These are locations supplied by the operator, never key values.

```sh
PYTHONPATH=application/src "$APP_PYTHON" -m deployment.managed_assistant plan \
  --plan "$PRIVATE_SETUP_DIR/assistant-plan.json" --deployment staging \
  --model claude-sonnet-5-5 --effort high
```

Plan is entirely offline: it requires no key and makes no provider calls. Review the
complete JSON payload, including its `configuration_sha256`, the tool-list and playbook
digests, the custom tools, inline subagent policy and restricted cloud environment.
The environment has no added packages and limited networking with an empty host list;
package-manager and MCP network access are disabled. The agent has no built-in tools,
MCP servers, skills, advisor or workflows. Scientific code remains confined to HYPRN's
attested worker. Environment configuration does not itself attest that worker.

Only after approval of that exact artifact, set `REVIEWED_SHA256` to its reviewed
configuration digest and run:

```sh
PYTHONPATH=application/src "$APP_PYTHON" -m deployment.managed_assistant apply \
  --plan "$PRIVATE_SETUP_DIR/assistant-plan.json" \
  --state "$PRIVATE_SETUP_DIR/assistant-state.json" --key-file "$KEY_FILE" \
  --approve "$REVIEWED_SHA256"
```

Apply validates the artifact against this release before contacting the fixed Anthropic
endpoint. It discovers resources using deployment and definition-digest metadata,
then checks their actual fields. It creates only missing resources, retaining an
fsynced intent before each POST. A lost reply or interrupted request is never blindly
repeated, even when a later listing finds nothing. Reconcile uses only provider GETs:

```sh
PYTHONPATH=application/src "$APP_PYTHON" -m deployment.managed_assistant reconcile \
  --plan "$PRIVATE_SETUP_DIR/assistant-plan.json" \
  --state "$PRIVATE_SETUP_DIR/assistant-state.json" --key-file "$KEY_FILE"
```

Reconcile can record a discovered creation but cannot create a missing resource.
After partial setup, a later approved apply can create a resource that has never been
attempted. Definitive provider rejection permits a later explicit apply after correcting
the cause. An uncertain creation with no matching resource, conflicting matches, drift,
or incomplete listing requires operator investigation; preserve the journal and do not
erase it to force another attempt. One lock serializes commands sharing that journal;
all operators for a deployment must use the same durable journal. Copying or losing the
journal removes that concurrency guarantee. The command does not delete or archive resources.

On success, stdout is a JSON binding object with `HYPRN_MVP_ASSISTANT_AGENT_ID`,
`AGENT_VERSION`, `ENVIRONMENT_ID`, `DEFINITIONS_SHA256` and `CONFIGURATION_SHA256`
(each uses the same `HYPRN_MVP_ASSISTANT_` prefix). The version is read back using the
explicit `version` query parameter, never a latest-version alias. The configuration
hash is deployment evidence for platform verification; the application currently checks
the tool-definition digest. Environments are not versioned, so the command rereads their
full restrictions before exporting bindings. Reconcile before activating a deployment;
this is a point-in-time check, not continuous provider drift monitoring.

Changed model, policy, tools or playbook produces a distinct content-addressed agent;
an unchanged environment is reused. Existing resources and study sessions remain in
place. Existing resources without the command's metadata are not silently adopted or
modified. The application retains its existing in-place idle-session tool refresh;
resource provisioning does not reset conversations or upgrade their immutable delegation
policy. The private binding object contains identifiers, never credential material.
Supply the runtime `KEY_FILE` separately through the approved secret-file delivery.

Setup does not create a session, submit a message, provision a new allowance or change
spending. Each user has one cumulative allowance (USD 20 by default) across their study
conversations and subagents, without automatic resets. The first human who starts
a conversation is its billing owner; archiving or membership changes do not transfer
or erase its cost. Admission and active turns read provider list cost for all of that
user’s sessions, including earlier sessions. No session cap is created or renewed.
Existing caps are removed on admission after checking the user’s remaining allowance.
Active work checks spending between provider polls and tool dispatches and stops at
the user limit. In-flight requests and delayed usage reporting can overshoot; this is
accepted, not a provider-enforced hard ceiling. Unknown usage refuses further work.
Legacy installation-only prior cost has no user attribution and remains an operator
continuity record, not a silently reset study balance. Deployments preserve all usage.

The official CLI provides declarative `ant apply`, but it is not a locked dependency
of this repository. This narrowly scoped command uses the official resource payloads
through the existing audited HTTP adapter; it adds no CLI/SDK dependency or general
infrastructure engine. Provider API references checked for this implementation:
[agent creation](https://platform.claude.com/docs/en/api/http/beta/agents/create),
[agent readback](https://platform.claude.com/docs/en/api/http/beta/agents/retrieve),
[agent listing](https://platform.claude.com/docs/en/api/http/beta/agents/list),
[environment creation](https://platform.claude.com/docs/en/api/http/beta/environments/create)
and [restricted environments](https://platform.claude.com/docs/en/managed-agents/environments).

`./hyprn-mvp dev check hosted-assistant-setup` covers the command with isolated private
files and the real HTTP adapter against an in-process provider transport. This evidence
does not establish live resource creation, account/model access, provider enforcement,
end-to-end assistant acceptance or a qualified hosted release.

The server must have one persistent ASGI lifespan, such as the existing local
edition's uvicorn server. A per-request TestClient wrapper is unsuitable: it
would close the conversation delivery task at the end of every HTTP request.

## Delivery and access

The public routes are study-scoped `GET assistant`, `POST assistant/messages`
and `POST assistant/stop` / `POST assistant/resume`. They are human-only; an agent cannot invoke another
assistant or grant itself a turn.

Each message has a client-generated command ID. Repeating that ID with the same
text reads the admitted turn; changing its text is rejected. One active turn
occupies the study. A remote creation or message with an uncertain outcome is
looked up by correlation; it is never submitted again blindly. Stored custom-tool
results are delivered using their original provider tool-use identity. A tool
whose local effect was interrupted before its response was retained needs review,
not speculative replay. Resume renews the human delegation for the same accepted
turn, reuses retained tool results and can repeat only an interrupted read. An
uncertain write remains blocked. Restart leaves blocked conversations for explicit
human continuation. Safe diagnostic logs retain exception type and code location,
without transcript, credentials or raw exception messages.

Stop fences new local tool admission before requesting provider interruption.
It does not cancel a scientific run that was already admitted; that run retains
its own lifecycle. Access loss stops further tool dispatch and conversation
delivery. Scientific records remain governed by their ordinary owners and exact
version rules.

User allowance admission is described below. Stop, Trash and restart never erase
incurred usage or bypass uncertain session creation. HYPRN stops work when observed
user cost reaches their configured allowance; in-flight requests can exceed that threshold. A confirmed billing
failure is shown as a provider-credit problem and permits a new explicit human request
after funding; the failed request is never replayed automatically.

## Evidence

The focused `assistant-bridge` check covers the wire adapter and persistent
conversation API as well as the original synthetic read bridge. Real account
tests use an isolated synthetic study and a separately recorded small provider
budget. A mock transport pass is not provider acceptance; a read/brief-authoring
pass is not a completed engineering workflow.

Wire reference: [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/quickstart),
[custom-tool events](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)
and [session budgets](https://platform.claude.com/docs/en/managed-agents/budgets).

## Complete authoring and delegation

The provider uses the shared scientific catalogue: brief, evidence, model graph and
quantities, versioned model/component description and limits, assumptions, configurations,
point runs, analyses, joint sampling, frozen surrogate plans, validation, exploration
readiness, prediction and study answers. A human still owns access management, Trash,
restore and destructive installation operations (ADR-0003). Unimplemented capabilities
are not advertised as tools.

`create_sampled_analysis` records explicit ranges, seed, training/validation counts and
output tolerances. `get_sampling_status` returns the generated version. Submit missing
runs through the normal admitted batches and `wait_for_runs`, then `launch_analysis`
reuses recorded runs and validates the frozen plan. It refuses missing run coverage,
so the asynchronous execution owner cannot bypass the agent run budgets. Read
`get_surrogate` and `prepare_answer_exploration` before publishing its returned answer
basis. `predict_answer` reads calculated/saved-surrogate values without model reruns.
All surfaces share this catalogue; no study-specific application code is involved.

Managed subagents inherit only the primary's custom tools. Their cross-posted tool
calls pass the same current human delegation, study scope, run limits and Stop fence.
Tools are dispatched serially; independent provider reasoning may run concurrently.
Child messages remain private to orchestration; the primary synthesizes its answer.
Shell, unrestricted network, advisor and dynamic workflow execution remain disabled.

Existing idle provider sessions receive the current custom-tool list in place before
a new human turn. Provider multiagent settings are immutable per session: older
sessions retain their original delegation capability; new studies receive the enabled
subagent configuration. Never reset a session to upgrade it. Budget removal follows cumulative user admission.

Provider semantics verified against the official [multiagent guide](https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration),
[session threads](https://platform.claude.com/docs/en/managed-agents/session-threads) and
[session operations](https://platform.claude.com/docs/en/managed-agents/session-operations).


## Cumulative user allowance

The application checks actual provider cost across all conversations owned by the
user, including child agents and previous studies. The fixed default limit is USD 20, with
no reset and no per-session cap or renewal. See the ownership and overshoot rules
above. One user's cost never reduces another user's allowance. Concurrent studies
are admitted independently against current aggregate cost; they share the same
stop threshold, rather than reserving separate portions of the allowance.

The authenticated budget read reports only the requesting user's cumulative total,
remaining amount and check time. Unknown usage is null, never a cached successful
zero. Existing legacy configuration remains for deployment continuity, not as a
second runtime limit. The app keeps spending out of the study conversation.

Operators may set `HYPRN_MVP_ASSISTANT_USER_LIMITS_CENTS` to a JSON object mapping
account actor IDs to positive integer USD-cent ceilings. The cloud runtime exposes
these as `assistant.user_limits` records (`actor_id`, `limit_cents`). This changes
only those users' cumulative ceilings, not recorded spending, sessions or reset
policy. Absent users retain the default. Invalid settings refuse enablement.
