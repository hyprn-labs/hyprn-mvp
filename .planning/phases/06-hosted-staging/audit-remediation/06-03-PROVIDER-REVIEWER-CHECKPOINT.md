# Provider reviewer delegation configuration

The real coordinator request failed with HTTP 400: a referenced reviewer had
`multiagent` set, even though every delegation mechanism inside it was disabled.
The provider forbids that block on referenced agents because delegation depth is
one. Exact rejection evidence is retained privately at
`/private/tmp/hyprn-audit-remediation-release/coordinator-provider-rejection.json`.

Diagnosis first reconciled the journal and listed/read existing resources to
confirm the coordinator was absent. One authorized retry of the exact rejected
plan captured the actual provider error; it created no coordinator or session.
Temporary credential material was removed in `finally`. The existing confirmed
skill, environment and reviewers remain intact.

Reviewer definitions now omit `multiagent`. Readback accepts only an absent or
null block, refusing even an explicitly disabled block. The coordinator still
uses exact predefined reviewer versions, disables inline agents and dynamic
reuse, and retains the existing shared user allowance. New reviewer identities
will be recorded in the same setup journal; old resources are not deleted.

Official contract inspected on 2026-10-22:
https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration

The provider double reproduces the real nested-delegation rejection and the
optional null readback. Verification and new offline plan identity are recorded
below after the focused setup group finishes. No application session, spending
limit, scientific data or live runtime binding was changed by this correction.

Verification completed:

```text
HYPRN_MVP_DATA_ROOT=<development-root> HYPRN_MVP_TOOLS_DIR=<pinned-tools>
HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480
./hyprn-mvp dev check hosted-assistant-setup
```

27 tests passed, 13.14 s, exit 0; scope
`9b586b94-f856-4dee-930f-13a2d1a89f53` released. Log:
`/private/tmp/hyprn-assistant-reviewer-check.log`. Public setup command tests cover
bootstrap creation, exact skill/reviewer pins, full coordinator provisioning,
reconciliation without duplicate writes, and refusal of added reviewer delegation.

New offline bootstrap: deployment `staging`, model `claude-sonnet-5-5`, effort
`high`, configuration digest
`830014d65e9b089634064d184174399e867d6791c24c97541492e638358b5bc1`.
The exact plan is retained at
`/private/tmp/hyprn-audit-remediation-release/assistant-bootstrap-v2-reviewed.json`.
Skill bundle bytes remain unchanged, digest
`6349cb87f0c60f69973a29f60017371a6fb45222653266504eec16433323d4ab`.
Parent owns applying this corrected bootstrap and generating/readback-verifying
the final coordinator plan. Real successful setup remains unverified here.

Subsequent real provisioning (deployment orchestrator): the corrected bootstrap
and bound coordinator plan both applied successfully with exact readback. The
same journal reused the confirmed native skill and restricted environment; no
provider session was started. Final plan digest:
`1dc1567c910e9092c01f2482831990682dfd9bfb9d8fb2d75b5f378d80785ca8`.
Plan and returned bindings are retained privately under
`/private/tmp/hyprn-audit-remediation-release/` as `assistant-plan-v2.json`,
`bootstrap-bindings-v2.json` and `assistant-bindings-v2.json`.
This proves live resource acceptance/readback, not runtime skill use or study
completion; those remain deployment acceptance checks.
