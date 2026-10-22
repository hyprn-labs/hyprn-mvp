# Embedded study assistant — current delivery

**Current delivery (2026-10-20):** `30dddd3`, `76d4b5d`, `b7f5898` replace per-study
reservations with fresh shared-allowance admission. Each new human turn can use the
remaining approved EUR 100 pool; study turns serialize spending, while child agents can
still reason in parallel. Spending is removed from the panel. Settings is now a modal
that retains workspace context. Shared card, form and exploration layouts are harmonized.
See `checkpoints/3.A7.md`; earlier per-study and spending-display notes below are historical.

Live provider ceiling updated successfully for mamamia, but the provider rejected its
connection check with `billing_error`: insufficient account credits. HYPRN now explains
this and permits a new explicit message after the owner funds the provider account.
No automatic retry or study-data modification. The UI is deployed; numerical worker,
dispatcher, attestation and Usersnap opt-in remain unchanged. Provider billing is the
remaining live-Assistant blocker; full release qualification and human acceptance remain
separate obligations.

Updated 2026-10-20. User selected Claude Managed Agents with one session per study
and authorized EUR 100 as the total initial live-test budget (not per session). An empty
owner-only credential file was prepared beneath the configured development data root,
application/credentials/anthropic-api-key, outside the repository and synced folders.
The user populated it and said ready. Owner-only permissions and the official
Managed Agents endpoint were verified (HTTP 200); no key was displayed or committed.
A restricted agent/environment and one USD 1-capped synthetic session were created.
The session read a real synthetic study through the delegated public API, then resumed
and saved/read back Brief version 1. Read-only turn reported USD 0.10 cumulative list cost;
authoring-turn total was USD 0.25. The later live journey below adds USD 1.02.
Before paid tests, set a conservative USD provider budget within the authorized EUR
allowance, accounting for documented in-flight overshoot and cumulative test spending.

## Product contract

- One durable HYPRN conversation for each study, not each browser tab or model version.
  Hide/show, navigation, refresh and application restart retain that conversation.
  Study membership governs access; messages retain their human/agent authorship.
- A provider session is attached to that conversation. Select one provider for the first
  delivery; changing providers must not silently reinterpret an existing session.
- The managed provider owns reasoning, continuation and its context. HYPRN owns tool
  authorization, study effects, operation receipts, durable delivery reconciliation,
  local conversation projection and the existing panel. No local Messages/Responses loop.
- Preserve one active turn per study. Reconnect retrieves state; ambiguous submissions
  are reconciled rather than repeated. Stop first fences further local tool admission,
  then requests remote interruption; admitted scientific work has its own lifecycle.
- Use the current /hyprn guidance and shared typed registry. No private domain calls,
  repository access or provider-side candidate execution. Read/write authority follows
  the human delegation and is checked per effect; never pass an owner cookie to a model.
- Provider credentials stay server-side. Configure the account, model and spending bound
  explicitly. Unknown usage remains unknown. Do not create fresh remote sessions to evade
  a limit. Trash retains the conversation alongside the study's existing records.
- UI uses the existing AssistantPane and design system: messages, composer, Send/Stop,
  real activity and actionable failures. Direct record links in conversation messages remain deferred; ordinary workspace navigation opens the saved records.

## First demonstration and usable outcome

Target: existing local Mac demo. First demonstration: send a message through the real
panel, receive a managed reply using authorized study reads, refresh and resume it.
This is not completion. Usable outcome: author a brief/model, run a real attested
calculation, inspect results and save an answer through the same public tools, preserving
human edits, exact versions, attribution, Stop and uncertain-operation recovery.
No broader cloud deployment or dual-provider implementation is required for this slice.

## Reconstructed implementation

The prior isolated branch `agent-embedded-assistant-3-a1` contains the accepted synthetic
read bridge (source `1784d6d`, checkpoint at branch `d3dec65`). Integrated as `0063509`.
Only the architecture dependency table conflicted: kept all current owners and added
assistant → agent_runtime, agent_tools, contracts. Unrelated current work remains intact.
The bridge is deliberately ephemeral and read-only: it is not a live assistant, durable
conversation owner, endpoint, provider adapter or deployed UI.

The older embedded-assistant proposal contains stale statements about an empty conclusion
catalogue, read-only LOCAL_STAGE and a Modeling approach primitive. Current tools include
study answers and authoring; LOCAL_STAGE serves the last registered stage; brief, model
explanation, analyses and study answer are the current domain. Do not reintroduce retired
primitives while implementing the adapter.

## Delivered local demonstration

Commits `5c631d6` (managed conversation) and `e010926` (component source guidance).
The live Assistant panel uses Claude Managed Agents, one persistent provider session
per study, custom HYPRN tools only. The private demo host now uses persistent uvicorn;
its dispatcher, modeling service, worker and attestation were not restarted or changed.
The verified UI build was published with source and runtime fingerprint checks.

Live study: b27f14ae-e101-448c-a9e5-aed5bc6d9cb1. Three human turns reused one remote
session. Browser send, refresh/re-login, reopen, Stop, web-server restart, resume and
navigation were exercised. Claude authored Brief 1, an explicit Python model, input
configuration, real attested run, analysis and Answer 2. The completed run
b291033f-8a83-4ca2-a17b-160bd72565ff has exit 0 and 9.5238095238095 K; the saved answer
pins that run and its met 10 K criterion. Correcting answer prose created a new answer
version without another model run. Final conversation is idle. This was a supervised
engineering demonstration, not an unattended first-attempt evaluation or full release
qualification.

Two failed runs remain honest history. The first revealed that the playbook omitted the
compute-body interface; the second was the agent's diagnostic probe. The authoritative
model section now specifies inputs/outputs symbol access and discourages probing worker
internals. The same section is served to all agent surfaces. Claude then completed the
physical calculation. Its initially uncomputed percentage sensitivity claim was removed
through a follow-up authoring turn; no direct scientific-record edits were made.

Reported cumulative provider list cost: isolated smoke USD 0.25; live conversation USD
1.02; total USD 1.27. Live configuration reserves USD 5 per conversation and USD 10 total;
smoke reserved USD 1 separately. These conservative limits leave substantial headroom
within the authorized EUR 100. Provider in-flight overshoot still applies; there is no
automatic budget raise. Credential bytes never enter UI, source, logs or worker.

## Delivered complete-study Assistant demonstration

Commits fd9f9a8, 222a021, 3af1780, 78530e6, 81440e4 and f328c7e expose 56 shared
scientific tools, managed subagents, and Home start/switch/continue behavior. Home keeps
the attached study header and composer; opening another study switches its conversation.
Existing sessions gain new tools in place; provider multiagent settings remain immutable,
so delegated reviews are enabled for newly created sessions.

The live Assistant authored study cca019d8-a6ad-43bc-8afa-156ee72b99f2 through public
tools: explicit brief/evidence, an explained two-component model, 26 real recorded runs
(25 joint samples plus nominal), two analyses and Answer version 1
538a685f-9570-4d3b-abca-ec8cc38b385e. A managed child performed a read-only review.
The answer pins analysis d81edadc-317d-45d9-852d-420d1f21fa4e and checked estimate
ef9798c8-941c-5b12-a921-6c8467259b73. Numerical allocation: 17 training, 1 method
selection, 7 independent validation points. Both outputs pass unchanged absolute 1e-6 kW
and relative 1e-6 tolerances; full joint domain preparation passes. This was supervised
recovery of a live engineering demonstration, not an unattended first-attempt evaluation.

Public prediction checks return calculated and estimated finite values with 26 runs before
and after, about 1.08–1.29 s per warm request. Browser movement of all three independent
sliders returned real estimates and curves; final run count remains 26. One transient
prediction timeout recovered with Retry predictions; a subsequent combined movement
completed without retry. At that delivery its cause was unconfirmed; the prediction-recovery follow-up below
reproduced and corrected interference between concurrent requests.

Four defects were fixed generically: development fixture display-name policy, background
agent attribution composition, discarded surrogate pin in answer tools, and averaging of
fixed UI inputs. No scientific records were hand-patched, validation loosened, or worker
attestation changed. Failed operations remain recorded history. Checks and recovery
artifacts, including the public-boundary rounding reproduction, are in checkpoints/3.A3.md.

The integrated navigation/profile-alias delivery passed its own seven check groups.
Backend now runs the normal repository source again (web PID 79505 at delivery); the
temporary 81440e4 snapshot is no longer active. UI build 6cf14855-6029-4fde-af08-473a22ab09c2
was published after all nine static/design/build stages passed. Dispatcher unchanged.
A consistent pre-profile-migration backup is retained privately. No live alias value was
changed. Provider definition 3 remains capped at USD 5/session and USD 10 aggregate.
This study's reported provider list cost is USD 2.97; cumulative known tests USD 4.24.

## Remaining work and limits
- Owner: assistant UX follow-up. Expose
  method-selection versus independent-validation counts directly in the tool projection.
  Direct links to changed records, safe rich-text formatting,
  shorter progress/final prose and less frequent run-status polling. Navigation refreshes
  saved records; the panel deliberately does not overwrite an open human editor.
- Owner: scientific agent evaluation. Improve first-attempt authoring and prevent unsupported
  quantitative extensions of a point result. Keep the supervised correction in evidence.
- Owner: release orchestration. Full qualification, independent review and human acceptance
  remain outstanding; the earlier unrelated style-ratchet debt is still recorded.

Checks and precise evidence scopes are in `checkpoints/3.A2.md` and `checkpoints/3.A3.md`. Private live evidence is
in the host's `hyprn-managed-smoke` scratch folder. Unrelated hosted planning remains outside this batch. The evidence-reader branch, including
its identical RunPanel change, was integrated by the prediction-recovery follow-up.

## Prediction recovery follow-up (2026-10-20)

Active prediction receipts no longer delete one another. The UI retries only transient
read-only prediction failures, at most three attempts, cancels recovery for a superseded
selection, and keeps a loading state. Invalid inputs, changed pins and failed accuracy
checks are not retried as successful results. Sampling, model execution, fitting and
validation thresholds are unchanged. See `checkpoints/3.A4.md` for before/after evidence,
worktree integration dispositions and the exact live delivery.

## Confirmed-send refusal follow-up (2026-10-20)

The first message in study mamamia was refused by the installation reservation ceiling:
two USD 5 reservations filled the private USD 10 demo ceiling, even though reserved funds
are not actual spend. The generic send UI incorrectly called every rejection uncertain.
`7c13a11` adds the structured `assistant_budget_reserved` diagnostic and distinguishes
`outcome: unchanged` (editable draft) from unknown delivery (same locked command).

At that checkpoint, private demo configuration reserved at most USD 20 cumulatively, retaining USD 5
per provider conversation, within the user's earlier EUR 100 authorization. Prior durable
reservations were not reset. No automatic cap increase was added to the product. The
original mamamia message was recovered once through the real Chrome panel; one accepted
turn and one provider conversation were verified. The Assistant is continuing the user's
study, not a synthetic diagnostic prompt. See `checkpoints/3.A5.md`.
