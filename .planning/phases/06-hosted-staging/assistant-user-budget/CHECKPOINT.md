# Cumulative user budget and conversation recovery

Owner request: USD 20 per user across all studies, no session ceilings or renewal,
no reset; accept in-flight overshoot. Fix the blocked conversation through released
code and the public application, never direct staging record edits. Include shared
progress-card/composer spacing.

Implementation: user ownership derives from the first human conversation turn;
prior study costs survive archive and membership changes. Fresh provider usage is
checked on admission and periodically during dispatch. Existing provider caps are
removed on normal admission; new sessions omit them. Schema migration 9 adds only
a restricted accounting read function, with no scientific or conversation updates.
Legacy installation approval remains deployment-continuity evidence, not an active
spending limit. Historical installation-only prior costs lack user attribution.

Explicit Resume retains the accepted message and completed tool responses, renews
its delegation, and refuses replay of an uncertain write. A restart preserves a
blocked delivered conversation; uncertain initial message delivery still reconciles
once without resend. Diagnostics log exception class and code location, no payloads.

Read-only staging diagnosis: last reported sampling-status response was successful
and accepted by Claude; the sampling operation subsequently completed. The generic
internal failure occurred afterward. Its exact historical exception cannot be
recovered from the old code's diagnostic; no claim that sampling or a cap caused it.
The new code also tolerates nullable provider usage/stop-reason records safely.

Checks through ./hyprn-mvp dev check (isolated scopes): assistant-bridge 151 passed;
hosted-postgres 39 passed; contracts 127 passed; ui-navigation 29 passed.
Design-system checker, token freshness, UI contract and TypeScript build pass.
Evidence: /private/tmp/hyprn-user-budget/*.log. Initial checks exposed an isolated
fixture bootstrap issue and restart-reconciliation regressions, corrected before
the passing runs. Hosted check initially refused shared build-cache size; rerun
with explicit 15 GiB test cache budget preserved other sessions' image layers.
Browser evidence uses an API double, not live provider acceptance.

Deployment and real interrupted-study continuation remain pending. Full release
qualification and human scientific acceptance remain separate obligations.
