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
failure at this stage. Final integrated evidence and deployment remain pending.

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
tool calls. Do not stop it for deployment; release activation waits for idle queues.
