# Assistant publication refresh and hosted route persistence

Task 2 of 07-PERFORMANCE-UX-PLAN.md. Owner: UI executor. Source changes are
limited to workspace navigation, Assistant read lifecycle, brief/answer readers,
the shared dock host, its design contract and isolated navigation regressions.
No schema, sampling, surrogate, model execution or saved scientific record changes.

## Causes and changes

- Hosted session bootstrap clears the previous session and URL, and the signed-in
  path then unconditionally opened Home. Capture the requested hash before that
  reset and restore it through the same authorized route reader as local sign-in.
  Exact model/version selections survive browser reload.
- Assistant polling updated only conversation state. It did not invalidate the
  visible answer or model. A transition to a settled turn now invalidates the
  attached study once, after forward message catch-up, without refreshing on each
  status poll. Reopening a conversation can also detect unseen settled replies.
- Dock visibility and conversation lifetime are separate. The shared shell hosts
  the visible panel; hiding it leaves active-turn polling alive until completion.
  Hidden idle conversations stop timer polling. Closing the dock does not discard
  the message draft. Session/access fences and study-specific component identities
  still reject late replies from a prior session or study.
- Overview refresh retains the mounted brief and answer readers, preserving their
  chosen saved versions. It waits while either human editor is open or dirty.
  Model refresh updates the catalogue, current draft and version list but never
  substitutes a selected immutable version. A human-edit epoch rejects replies
  that crossed an edit/save cycle and schedules a fresh read afterward.

## Verification

- TypeScript: `ui/node_modules/.bin/tsc --noEmit -p ui/tsconfig.json`, exit 0.
- Design: `python3 ui/check_design_system.py`, exit 0, no new violations (six
  existing exports.ts warnings); `python3 ui/design_tokens.py --check`, exit 0.
- First `./hyprn-mvp dev check ui-navigation`: 33 passed, 2 failed, 66.343s.
  Both failures were new test selectors: the outcome paragraph includes a bold
  prefix and the cancel command is named “Cancel editing”. Saved browser evidence
  already showed the newly published answer. Corrected selectors, added immutable
  version and message-catch-up coverage before final verification.
  Evidence: /private/tmp/hyprn-ui-performance-navigation.log; check session
  9d1e1c8c-5011-4854-8d60-259aa07db70e. Test scratch scope c48217aa was released.

Final browser rerun and commit identity are recorded below after completion.
The browser group builds the current UI into a fresh scoped Vite output and serves
only controlled public API fixtures. It proves UI state/navigation behavior, not
hosted provider, scientific execution, staging deployment or human acceptance.
Parent owns those integrated/live checks; this executor performs no live writes.

## Final focused acceptance

`./hyprn-mvp dev check ui-navigation` passed 36 tests, 0 failures/skips/flakes,
38.094s, including a fresh isolated Vite build. Command used the reviewed DATA_ROOT
and TOOLS_DIR installation described by the parent. Evidence log:
/private/tmp/hyprn-ui-performance-navigation-green.log; retained check session
1a94f64f-a53c-4f0f-a91f-499c1f1b0d7c. Scratch scope b6674ed1 was released.

New regression journeys establish hosted exact-version reload; visible answer
publication after a collapsed dock drains multiple catch-up pages; no repeated
answer reads for unchanged idle polling; preservation/deferred refresh of a human
brief editor; model draft refresh; preservation of a selected saved model version;
and rejection of a late old-study conversation reply after navigation.
TypeScript and both design checks above pass on the final source, and scoped
`git diff --check` passes. No source changed after final browser acceptance.
