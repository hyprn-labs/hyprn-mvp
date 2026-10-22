# Display alias and consistent authorship

Authorized 2026-10-20. Target: existing local HYPRN app. One complete account-to-
authorship journey. User requests a separate alias in Settings, used consistently
for human identity in evidence/explanation attribution and chat message metadata.
Implementation must preserve concurrent sessions' work.

## Decisions

- Account/sign-in username and stable actor IDs remain unchanged. Alias is an
  optional, non-unique display name, not a credential, permission or lookup key.
  Human-readable Unicode names/spaces are allowed within an explicit bound;
  reject invalid/control text and normalize surrounding whitespace consistently.
  Clearing the alias restores the account-name fallback.
- One server-owned profile value and shared identity resolution supply every
  consumer. No browser-only alias or separate alias per study/module.
- New attribution records and human chat messages capture their author's effective
  display name at creation. Changing a profile must not rename historical
  scientific authorship. Legacy attribution/chat reads retain their old account
  name fallback, never relabel them with the current viewer or a later alias.
- Assistant messages remain labelled Assistant. Role, actor/delegation identity
  and recorded authorship remain distinct from the mutable profile label.
- Existing shared RecordAttribution/AttributionChip consumers cover evidence,
  explanations, models, configurations, runs, answers and studies. Audit for
  hardcoded human labels and missing canonical explanation attribution.

## Task 1 — profile through every attribution surface

Build authenticated current-user profile read/update through the public API.
Mutation uses existing Origin/CSRF protections and rejects delegated agents.
No arbitrary actor target or account rename. Keep update recovery and stale edits
explicit. Add additive, idempotent storage migration without rewriting saved
scientific records or existing transcript text. Keep login/recovery working.

Use the shared identity owner to capture alias/account fallback in new agent
attribution entries and human chat turns; expose actual message-author display
name through the closed public conversation schema. Preserve replay names and
legacy schema migration, including the existing attribution-kind table rebuild.

Settings uses shared form/field/actions with Account name read-only and editable
Display alias, concise hint, Save, clear errors and recovery. Load persisted profile
on sign-in; retain it across navigation/re-login and clear on access loss/sign-out.
Sidebar/account metadata may display current alias; chat must use the recorded
speaker's identity, never the signed-in viewer's alias. Shared design components
accept API-supplied names as inert text with accessible wrapping.

Regenerate OpenAPI/TypeScript and update architecture owner rules, design docs
and fixtures where contracts change. No new dependencies or provider calls.

## Acceptance

Real public API tests: persisted alias, clear/fallback, restart, validation,
unauthenticated/CSRF/agent rejection, unchanged credentials/actor IDs and cross-user
isolation. New evidence/model-explanation attribution and new chat turn use alias;
alias change and replay preserve old names, legacy records remain readable.
Use fake provider for assistant numerical-free tests; no paid/live provider calls.

Browser: Settings save/error/reload, alias in account metadata and authored labels,
safe literal text, role distinction and navigation/unsaved guards. Exercise the
real served public profile boundary where fixture capabilities permit; label
in-browser doubles explicitly and pair them with real HTTP API tests.

Run pinned entry point with existing host environment:
access-control, agent-tools (attribution tests), assistant-bridge, contracts,
locality-contracts, combined-static and relevant profile/attribution browser groups.
Do not silently claim unavailable checks. Full release qualification is separate.

## Ownership and concurrency

Current batch owns profile/auth/identity changes, public schemas, Settings and
author display integration, additive attribution/chat name storage, related tests
and docs. The main session owns its active background-attribution/dispatcher fix
and live assistant/sampling validation. Coordinate overlapping files and preserve
all existing hunks; do not restart live services or write live account settings.
Use explicit atomic staging/commits and a checkpoint. Parent independently reviews
and reruns integrated acceptance before reporting completion.

## Plan check

The requested alias is distinguished from login identity; every surface obtains
the same effective name while saved authorship stays immutable. Coverage includes
security boundaries, legacy migration, more than one human, retry and UI behavior.
No hosted-account or organization directory work is required for this local slice.
