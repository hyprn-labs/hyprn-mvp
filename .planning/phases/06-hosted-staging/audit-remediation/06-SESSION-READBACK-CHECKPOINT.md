# Provider session readback correction — 2026-10-23

Public Chrome login and creation of the coolant verification study succeeded.
The provider created its session, then HYPRN refused its tool readback before
sending the first message: web_fetch contained the optional `url_sources: null`.
Provisioning already admitted exactly this default; runtime did not.

The shared normalizer now serves provisioning and runtime. Unknown properties,
added tools and actual URL restrictions still fail closed. No policy, scientific
record, budget, accuracy threshold or execution capability changes.

Verification on the implementation tree:
- `./hyprn-mvp dev check assistant-bridge`: regression first failed (1/194),
  then 194 passed in 32.91 seconds; cleanup exit 0.
- `./hyprn-mvp dev check hosted-assistant-setup`: 27 passed in 13.189 seconds;
  cleanup exit 0. Both use the pinned runner and isolated scratch stores.
- `git diff --check` passed.

Exact private logs are retained under hyprn-staging-reset-continuity in operator
scratch. The blocked turn was stopped through the public app; no database repair
was performed. Normal release build, deployment and resumed public journey remain
pending. Previous baseline evidence is retained in COVERAGE.md; no unchanged
numerical or UI checks were repeated.
