# Document interruption recovery and truthful collection states

Owner: UI executor. Task 08, alongside the provider/backend executor. UI source
commits: `52aceb22`, `cd038b01`, `b6cb2fcd` and `ec48700e`. Backend changes
were integrated alongside these commits; final UI source is `ec48700e`.
No scientific records, model behavior, sampling, surrogate checks, version selection,
execution permissions or deployment operations are changed by this UI work.

## Changes

- The shared collection-read hook now represents disabled requests as idle, clears
  previous-scope rows and aborts previous requests. It does not report a loading
  request, zero records or successful emptiness when no request was made.
- Configuration lists explain the missing saved model version and direct the user
  to Models. Once a saved version is selected, the real request supplies loading,
  empty, populated or failed states through the existing shared CollectionStatus.
- Reviewed other disabled hook consumers: evidence version discovery, compact
  brief evidence, analysis version history and inactive runs. Their disabled
  readers need no new message; idle prevents false loading without enabling any
  request or changing record choices.
- AssistantActivity owns cause and next-action wording. Oversized event responses
  display Application problem instead of implying missing scientific input.
  Resume instructions and action remain driven solely by the API can_resume.
  Unsafe/oversize attachments explain Stop and a new source request only when
  can_stop is granted; unavailable recovery directs the engineer to the app
  administrator. No tool is retried by this presentation change.
- Design contracts updated in Collections and AssistantPane; unrelated dirty
  Scientific-states and Calculations files were preserved.

## Verification

- `ui/node_modules/.bin/tsc --noEmit -p ui/tsconfig.json`: pass.
- `python3 ui/check_design_system.py`: pass, no new violations; six existing
  exports.ts warnings retained.
- `python3 ui/design_tokens.py --check`: pass; generated tokens unchanged.
- `node ui/design_smoke.mjs`: pass, 119 renders, including idle prerequisites
  with aria-busy false and no invented loading/count/empty state.
- First navigation invocation was refused before building/tests: workspace
  sandbox denied the existing uv tool cache (exit 5). Retried with authorized
  access to the existing pinned cache.
- Second invocation was refused before tests: 4,858,847,232 bytes free, below the
  unchanged required 5,368,709,120 bytes (exit 2; session
  `ab1a424a-794c-480e-9668-7ebbc5e2802e`). Parent reclaimed only verified obsolete
  scratch build volumes; no data or retained artifacts deleted by this executor.
- First actual browser run: 39 passed, 4 failed, 0 skips/flakes in 88.576s;
  retained session `a1b8001d-87c7-4bb7-ae07-ac653abfa12c`, scratch `d1b4793a`
  released. All four failures were new fixture mechanics: two second-login calls
  performed fragment navigation rather than reload; two Resume mocks did not
  match the nested /assistant/resume route. Existing 36 journeys passed.
  Corrected the explicit reload and route predicate; shortened new recovery copy
  without changing its meaning before final rerun.
- Second browser run: 41 passed, 2 failed in 46.465s; retained session
  `052563bd-95c1-464f-8c36-a0dfab051dd5`, scratch `103f0ab0` released. The
  two tests clicked the already selected Configurations tab after reloading,
  deliberately causing a second navigation/read; replaced that click with a
  selected-tab assertion. All five new Assistant recovery journeys passed.
- Also fixed stale local Resume/Stop errors surviving a later successful action;
  the uncertain-resume regression now covers a failed response then successful
  safe retry, without sending the user message again.
- Final focused navigation: **43 passed, 0 failures/skips/flakes**, 38.788s,
  exit 0 on committed UI source `ec48700e`. The group built the current UI fresh
  in scope; no UI source changed after acceptance. Retained check session
  `923ad3f8-98b4-49fb-9b70-14025ecaa1b3`; scratch `ccaa8393` released.
  This is public API fixture verification in
  isolated browser scope, not the live hosted provider. Parent owns live recovery
  and deployment checks. No human acceptance is claimed here.

Logs outside the repository:
`/private/tmp/hyprn-ui-document-recovery-navigation.log` (first browser run)
`/private/tmp/hyprn-ui-document-recovery-navigation-green.log` (second browser run)
`/private/tmp/hyprn-ui-document-recovery-navigation-final.log` (43 passing)
`/private/tmp/hyprn-ui-document-recovery-design-smoke.log`
