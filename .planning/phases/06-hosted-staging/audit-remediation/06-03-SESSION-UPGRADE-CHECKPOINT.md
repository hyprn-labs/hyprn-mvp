# Managed provider session upgrades

Status: implemented and focused verification passed. No staging mutation.

## Outcome and plan

A newly published pinned agent/skill/reviewer definition becomes available on the
next fresh human turn, while HYPRN retains one study conversation and all previous
messages, source receipts, saved work and cumulative user spending.

1. Retain a scoped generation ledger: exact agent/environment/catalogue/reviewer
   binding, stable provisioning correlation, first human billing owner and bounded
   handoff. Provisioning advances once; accepted identity cannot change or disappear.
2. Upgrade only before delivery of a new human turn, after confirming the previous
   provider session is idle/terminated, no tool deliveries are unresolved and fresh
   cumulative spending remains below the same user cap. Active/accepted work stays
   on its original provider session and retained reviewer policy.
3. Keep ambiguous creation as intended; reconcile its stable correlation on explicit
   safe resume, without recreating or replaying scientific work. Reset only the
   current provider cursor on an admitted successor; immutable local history stays.
4. Include all generations in accounting, deduplicate provider IDs, preserve legacy
   conversations and refuse unknown usage. Do not reset cost or add session caps.
5. Verify through real delegated/public app journeys and PostgreSQL migration/RLS.

The official session update contract permits tools/MCP changes only; system, skill
and reviewer definition changes require a new pinned session:
https://platform.claude.com/docs/en/api/beta/sessions/update .
Session creation and message delivery remain separate operations:
https://platform.claude.com/docs/en/managed-agents/sessions .

## Boundaries

Migration 0013 adds the ledger, scoped request-role policies, immutable identity and
one-way provisioning transitions, and updates the restricted billing discovery
function. Historical sessions are imported with unknown binding, not falsely labelled
as current. Their reviewer authority fails closed. SQLite receives equivalent local
DDL. No provider creation, deletion or cost mutation is performed during migration.

Handoff is a bounded snapshot of prior public conversation excerpts and actual tool
record references, explicitly labelled historical/untrusted. It directs the agent
to read current saved study records; it invents no scientific conclusion and replays
no prior user command. The conversation ID shown by the application remains stable.

## Evidence and outstanding work

Production writes were held until the monetary native freeze was released. Parent
owns release integration/deployment. Required focused commands: assistant-bridge,
hosted-postgres; parent boundary/contract/agent-tool checks remain integrated work.
Tested base: `3ec772376b5e2fcdb188ec68045c403ab98c24f5` plus this explicit working
change and concurrent integrated parent changes. All commands used the configured
external data/tool roots and `HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480`.

- `./hyprn-mvp dev check assistant-bridge`: 190 passed, 1 failed (32.38 s).
  The only failure was an old fixture monkeypatching `_authorize` after that boundary
  became public `authorize_turn`. Corrected the fixture; production source unchanged.
  Log: `/private/tmp/hyprn-session-upgrade-assistant-bridge.log`.
- `./hyprn-mvp dev check hosted-postgres`: 47 passed (46.33 s), one existing
  Starlette/httpx deprecation warning. Actual PostgreSQL migration, restricted-role
  isolation, immutable binding/cost owner and no legacy accounting duplication pass.
  Log: `/private/tmp/hyprn-session-upgrade-postgres.log`; scope
  `5c4bf5f3-0424-4462-ad69-b7d93a887dfe`, runner exit 0, cleanup completed.
- Final `./hyprn-mvp dev check assistant-bridge`: 191 passed (33.64 s).
  Log: `/private/tmp/hyprn-session-upgrade-assistant-bridge-final.log`; scope
  `7c93b9c1-e64f-474a-afd7-87c45d4fa601`, runner exit 0, cleanup completed.
  New scenarios verify retained messages, cumulative costs across generations,
  accepted-turn/reviewer-policy continuity, no repeated tool dispatch, ambiguous
  creation reconciliation and refusal of running/unknown/unsettled sessions.

These are real application/public API tests with a deterministic provider double;
they do not establish live provider rollout or staging readiness. Parent owns live
verification and integrated boundary/contract checks. Native skill/application
artifacts must include these bytes and migration 0013 before staging qualification.
