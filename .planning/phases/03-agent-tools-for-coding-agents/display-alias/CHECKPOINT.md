# Display alias — implementation checkpoint

2026-10-20. Code commit: `7a66f44e005e890b3ff6839c3ae5ecf4075620d8`.
Target: local HYPRN application. No live settings, authoring records, providers or
services were modified/restarted. Parent owns committed-tree integration acceptance
and any live publication.

## Delivered

- Human-only, self-only GET/PUT `/api/1/profile`; alias validation, trim/clear,
  revision comparison, existing Origin/CSRF protection. Login includes profile.
  Account names, credentials, actor IDs and permissions stay unchanged.
- One dependency-light `identity` owner supplies profile and human names.
  Additive user/profile, attribution and conversation migrations preserve records.
- New agent attribution captures the delegator's effective name; new human chat
  turns capture their actual author's name. Replay preserves names. Legacy rows
  fall back to account names, never later aliases or the current viewer.
- Shared Settings editor, navigation guard, alias account metadata, error recovery
  including lost save responses. Chat labels use saved names; Assistant remains
  distinct. Model explanation headers now include shared RecordAttribution.
- Public schema/TypeScript regeneration, architecture owner rules and design docs.

## Checks

All commands used `source /private/tmp/hyprn-collection-env.sh` then the pinned
`./hyprn-mvp dev check GROUP`; no direct test runner, dependency installs or paid
provider calls. Retained evidence is under the host temporary `.hyprn-checks`
directory; IDs below identify each exact check run.

| Group | Final result | Retained check ID |
|---|---|---|
| access-control | 11 passed, 0 failed | `3ec60e99-4d51-4351-9304-e7fe3e83112b` |
| agent-tools | 334 passed, 0 failed; existing Starlette warning | `15534678-f17f-429d-9946-8f52d6f0288a` |
| assistant-bridge | 123 passed, 0 failed | `1c650864-7e2e-442c-aa9d-5e3f6ff0c687` |
| locality-contracts | 165 passed, 0 failed; existing Starlette warning | `46fe29a6-fb38-4c1a-a865-c7e66b8d3123` |
| contracts | 127 passed, 0 failed; 2 existing schema-mark warnings | `0d1fde39-062b-467f-911a-957b9ad42fff` |
| combined-static | 9 stages passed, 0 failed | `cc427834-87c3-4a08-b4fa-e09456f38632` |
| ui-navigation | 23 passed, 0 failed/skipped/flaky | `0931291b-1b3b-4f55-be65-1d7162cd63b6` |

The final static/browser run includes unconfirmed-save recovery and its browser
case. The final access-control run includes a second authenticated human; the final
agent-tools run includes a genuine pre-alias attribution-table rebuild.
API checks use real application HTTP boundaries and scoped SQLite stores.
Conversation tests use a fake provider and real delegated tools. Browser tests
serve the real UI build with declared in-browser API doubles; they do not claim a
live end-to-end deployment. Pair browser evidence with real profile HTTP tests.

Attribution checks cover new evidence, explanation draft/version, replay and
legacy fallback. Chat checks cover captured names and replay after profile edits.
Browser checks cover literal markup-like names, persistence across sign-in,
clear/fallback, unsaved navigation, stale profile recovery, lost responses and
human/assistant role labels.

Light/dark screenshots inspected at 1440×1000. Final retained files:
`0931291b-1b3b-4f55-be65-1d7162cd63b6/evidence/hyprn-mvp-test-3fda906d-12f7-43c6-81fb-337232f92c6a/nav/display-alias-light.png`
and `display-alias-dark.png`. Earlier equivalent screenshots were visually
inspected from run `5fd9e9c4-48d2-4470-83fc-670ab22c0291`.
Automated/agent inspection is not product-owner acceptance.

## Failures and corrections

1. First sandboxed access-control invocation could not write the existing uv cache.
   Approved execution outside the sandbox succeeded; no dependency change.
2. First locality-contracts run: 164 passed, 1 failed. The separate route-owner
   allowlist omitted `identity`; added the explicit edge already documented in the
   architecture table. Rerun passed 165.
3. First ui-navigation run: 22 passed, 1 failed. New test assumed `#profile`
   navigation after sign-in; corrected to use the existing Settings action.
   Reruns passed 23. No product navigation change was made for that test.
4. Strengthened cross-user and legacy migration tests after initial green runs;
   affected checks were repeated. Final UI recovery wording now avoids claiming a
   save failed when its acknowledgement was lost, verified by a lost-response case.

## Concurrency, cleanup and remaining work

- Main's `78530e6` changes (dispatcher attribution/native labels) and `81440e4`
  (prepared surrogate pins) were preserved. The latter landed just before this
  commit; the parent should rerun agent-tools on the integrated committed tree
  because its added test may postdate the 334-test run.
- Only the explicit 29 owned files were committed. Existing RunPanel, Foundry,
  scientific-state, hosting, assistant planning and other session edits remain
  untouched. No tracked deletions. `git diff --check` passed.
- The runner removed scoped working stores and retained evidence under each
  `.hyprn-checks` run. No repository runtime data or generated scratch files added.
- No new dependencies, scientific defaults, execution paths or provider calls.
- Full release qualification, parent integrated acceptance and live publication
  are separate outstanding steps. Parent retains shared STATE/ROADMAP ownership.

## Orchestrator acceptance

Independently reviewed identity resolution, profile routes, Settings recovery,
schema migrations, immutable attribution/chat reads and light/dark screenshots.
At `ada3092`, reran every batch acceptance command with the same host environment
and `./hyprn-mvp dev check GROUP --keep-scope`:

| Group | Result | Retained check ID |
|---|---|---|
| access-control | 11 passed | `d47d5120-2e29-454f-8315-1e8873cfb4cc` |
| agent-tools | 335 passed | `d4b75d55-b0ac-4206-9c3b-f3f0d506e02c` |
| assistant-bridge | 123 passed | `291e12e0-6372-439f-949b-d3aef0db97cb` |
| locality-contracts | 165 passed | `3dfaab6b-6182-40ce-a818-dfa799951ec2` |
| contracts | 127 passed | `b1655aef-8537-4273-9201-ae096c88d49a` |
| combined-static | 9 stages passed | `2ffd5919-49e8-40f8-929f-3f1268f4b74a` |
| ui-navigation | 23 passed, no failures/skips/flaky | `3249e507-cea8-4301-8685-87dac569236b` |

Every command exited zero. Existing Starlette/schema-mark warnings remain.
The extra agent-tools test is the main session's prepared-answer regression.
The pre-existing uncommitted RunPanel/header-metric UI delta was included; no
alias implementation remained uncommitted. No live stores or providers were used.

Main's concurrent `f328c7e` changes only exploration input initialization and its
focused test. It landed during the acceptance window; the final static/build check
passed all nine stages at that commit, exit 0 (4.70 s reported check time), evidence
`aeed34a6-1719-47f2-a9b9-f1ff252f2697`. The alias code and the behavior checked by
the profile/navigation tests are unchanged. Publication, including the backend
restart for additive migrations, is coordinated by the main session after its
active live provider/sampling test; this task never interrupts that session.

Final UI artifact:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-f1bed3e5-10f1-430a-af63-9bd50c118d10/artifacts/ui`.
Only checkpoint/current-state evidence changed after this passing build.
