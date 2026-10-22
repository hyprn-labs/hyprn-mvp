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

Full release qualification and human scientific acceptance remain separate obligations.

## Staging rollout and live verification

Product commit `0fe32eba6ad68d160240ac6b58116bd98e98c821`; staging publication
`b62fd35ae0e76d1983dae32ea03cfd02bf2ae5e3` (fast-forward, exact source tree).
Desired sequence 17, release `2e6d90ab2226c9f947122997e25853915bb2edb2200386a884aee84e01159416`.
The normal UI Stop completed before the old owner drained and stopped; all seven
queues were empty. No direct scientific/conversation record changes.

Deployment helper defects were corrected with exact hash-checked replacements:
owner schema observations are checksum ledgers, not integers; old-owner backup
must use its own pinned platform/interpreter; backup policy requires mode 0600;
managed SQL backup polling must cover the observed 91 seconds. Earlier failed
attempt scopes are retained and never treated as coherent backups. The first SQL
backup succeeded after the original lock had ended, so a fresh complete snapshot
is required under continuous locks before migration. Evidence and reviewed scripts:
`/private/tmp/hyprn-user-budget`, especially correction subdirectories and
`application-evidence/`. No runtime images, IAM or scientific checks were weakened.

The new coherent backup completed under uninterrupted deployment/native locks;
its managed database receipt and verified owner-file manifest are retained. Official
migration 8→9, containment, startup, all 19 network probes and ongoing named-user
activation passed. No initialization, scientific data repair or credential reissue.
Final recovery policy `b1084de33c8c5129043c50205b631f31b05dcab127f8bac0c3f7e854f5efa6bc`; release/image identities above are unchanged by helper corrections.

Chrome sign-in and affected-study conversation verified. Public allowance read:
USD limit 2000 cents, spent 1139, remaining 861, scope user, period cumulative,
resets_at null. A normal continuation message resumed the same provider session;
read-only provider inspection confirms budget null. Actual tool responses were
accepted, and real study runs advanced from 3 to 13 (five recorded, one
dispatching, seven accepted at the final read). UI accurately
shows Waiting for calculations; the progress card clears the composer separator.
Screenshot: `/private/tmp/hyprn-user-budget/assistant-live.png`.

The scientific analysis and answer publication remain in progress under the embedded
Assistant; do not claim a saved answer or surrogate validation yet. No accuracy
checks were relaxed. The exact historical exception remains unavailable; the new
code provides safe diagnostics and explicit recovery for future failures.

Remaining owners: embedded Assistant completes/validates the current study and
saves its answer; platform maintenance should incorporate sufficient backup polling
and policy modes into reusable deployment orchestration. Full release qualification,
automatic deployment and human acceptance are separate obligations. Failed helper
attempts and the interrupted first backup remain recorded; no partial backup was
used for recovery.
