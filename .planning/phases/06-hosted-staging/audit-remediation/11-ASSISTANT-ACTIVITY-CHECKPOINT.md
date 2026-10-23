# Observable Assistant activity checkpoint — 2026-10-23

Implementation commits: `f4b0b255`, `b0295621`.

The public conversation successor `AssistantConversationRead6` adds a closed,
bounded activity projection. Predecessors 1–5 are unchanged. It reads the latest
40 current-turn tool calls and their observed delivery/result state. Catalogue
ToolSpec titles supply labels; unknown provider names receive generic labels.
Arguments, result bodies, private reasoning, provider/thread identities and
credentials never enter this projection. Reviewer activity is explicitly marked.
No new provider request, persistent record, migration or scientific effect is added.

The query selects only necessary JSON fields, not retained payloads. Queued turns
without a provider message skip event storage entirely. Event position and study
identity fence the current turn; result joins include study and tool identity.
Settled/new turns clear the activity. Completion is a tool outcome, not scientific
validity; result receipt without an explicit success flag remains Result received.
Timing is observed start/completion, not estimated finish or execution duration.

AssistantActivity owns the collapsed Activity details disclosure beneath the live
status. Expanded details sit outside its live region. Token spacing, wrapping,
status labels and times work with the existing conversation scroll in both themes.
No raw thought streaming is exposed. Parent owns staging observation without sending
messages or altering studies, and hosted PostgreSQL/integrated locality checks.

A browser regression exposed a pre-existing model-title inconsistency: refreshing
the model catalogue after Assistant completion changed a selected saved version's
title to the current draft name. The header now uses a saved record's name when
present and a string, preserving the fallback for old formats without that field.
The exact model pin, graph and editing behavior are unchanged.

## Verification

Commands use the established development data root and tool cache.

- `./hyprn-mvp dev check assistant-bridge`: 213 passed, 42.44s.
  `/private/tmp/hyprn-activity-assistant-check.log`.
- `./hyprn-mvp dev check contracts`: 127 passed, 12.49s (two existing warnings).
  `/private/tmp/hyprn-activity-contract-check.log`.
- `ui/node_modules/.bin/tsc --noEmit -p ui/tsconfig.json`: passed after the historical
  model-name string guard.
- `python3 ui/check_design_system.py`: no new violations (six existing export warnings).
- `python3 ui/design_tokens.py --check`: fresh.
- `python3 ui/check_component_ownership.py`: zero violations.
- `python3 ui/check_ui_contract.py`: passed.
- `./hyprn-mvp dev check ui-navigation` on integrated creation/activity source:
  48 passed, zero failures/skips/flaky, group duration 56.87s. Runner exited 0 and
  scope cleanup confirmed. `/private/tmp/hyprn-creation-navigation-2.log`;
  shared browser tests committed in `114f186d`, evidence `39e1abb7`.
- `git diff --check`: clean.

Failures retained: initial Assistant check stopped before tests on sandbox access to
the approved external dependency cache; the authorized scoped check was rerun with
cache access. First completed Assistant run: 212 passed, one existing privacy test
failed because an undelivered queued turn unnecessarily referenced assistant_events.
Production now checks the delivery pointer first; the unchanged privacy test passes.
The failed log is `/private/tmp/hyprn-activity-assistant-check-first.log`.

Initial integrated browser run: the new activity test passed. Two new creation
locator tests and one existing selected-version-title test failed; creation owns the
locator fixes and integrated rerun, while this batch corrects the model title.
The first title change also required a compile-time guard across historical schema
variants; subsequent tsc passed. No test assertion was weakened.

The backend checks use real HTTP/public projections and isolated stores with a
provider double. Browser checks use the documented API double; they cannot prove
provider integration or human acceptance. Test scopes were released; no live data
was touched. The shared study-navigation test changes are committed by the creation
worker with its integrated browser evidence, not staged separately here.
