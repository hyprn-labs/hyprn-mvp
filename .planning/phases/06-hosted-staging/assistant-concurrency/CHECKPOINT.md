# Concurrent study Assistant turns

Owner request: run studies concurrently under the existing shared allowance, report
actual queue/progress stages through the design system, suppress duplicate original
wording, commit and publish through staging. No direct staging data repairs.

Implementation: serialize only allowance reconciliation/provisioning. Renewable
provider headroom retains global accounting, conservative rounding and uncertain
outcome protections. Same-turn renewal never replays messages or scientific tools.
Public read projection 2 retains read projection 1 unchanged. Queued cancellation
before dispatch is immediate; execution timing begins after admission. The shared
AssistantActivity presents lifecycle labels and explanation consistently. Original
question provenance is retained; identical reader text is hidden.

Initial checks: Assistant 145 then 152 passed as additional edge cases were added;
contracts 127 passed; UI navigation 29 passed; design/token and UI contract checks
passed. Initial test command could not access the default dependency cache; rerun
used the existing explicit pinned cache and isolated fixtures. No application test
failure at this stage. Integrated evidence and deployment are recorded below.

Scientific execution, tool authorization, saved records, sampling and surrogate
checks are unchanged. Provider thresholds still permit the documented in-flight
request overshoot; accounting refuses further allocation when no headroom remains.
No new dependency, database migration, provider resource or spending approval.

Deferred: full release qualification, automatic deployment pipeline and second-user
acceptance remain owned by the hosted deployment work. Existing unrelated source
changes are excluded. Private evidence is under /private/tmp/hyprn-assistant-concurrency-*
and /private/tmp/hyprn-staging-assistant-concurrency/.


Integrated source `280dae3d`: Assistant bridge 153 passed; contracts 127 passed
(unchanged schema source since that run); design/token/UI contract/build passed.
Browser 29 passed on `a0aa3211`, whose only delta is the draft-reader test locator.
The first final browser run had 1 failure because the test expected a saved-reader
See details button on a draft; no application failure. Corrected locator verifies
that original wording remains in the saved data but is absent from the draft display.

The exact AMD64 app image and native bundle for `280dae3d` are built and verified.
All recorded worker inputs match the prior release. Read-only staging observation
found the coolant turn ended naturally and the hypersonic turn now delivering real
tool calls. Initial wait-only preference was superseded by explicit owner approval
to Stop the Assistant through the app and deploy. The public Stop control was used;
all seven background categories were idle before admission closed and service stop.

Deployment (2026-10-22): remote staging `8fd348a9`; runtime `280dae3d`;
release `3a693c455c91b29cb84214307e3b42aa03242eb5f88aab6870f2b65a7d8f2bc0`,
configuration `8f3fbbfd936c7adb6074868ac8fe9e01218ed83c0c1448baf80a4c2f953745ff`,
desired sequence 16. Exact-image publication, staged files, clean stop, unchanged
store handoff, containment, startup and 19 network probes passed. No initialization,
migration, secret reissue or direct record manipulation. Post-start queues all idle.
Authenticated Chrome opened the preserved hypersonic study and its saved brief,
verified the question is not duplicated in details, and loaded the retained
conversation with an idle composer. No continuation message was sent. Evidence:
private deployment packet application-evidence and staging-after.png.

Concurrency and budget-renewal behavior are covered by the 153 Assistant tests;
this deployment did not start additional paid live conversations to repeat them.
Human acceptance and scientific assessment of the unfinished hypersonic study
remain separate. The user can send a new continuation message to resume it.

Normal named-user staging access promotion completed after Chrome verification;
no temporary access deadline remains. All deployment phases exited successfully.
