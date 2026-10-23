# Assistant progress checkpoint — 2026-10-23

Source commit: `af1a30d6` (Help source `6e0b7a14` already integrated).

Outcome: the study conversation exposes the exact pending analysis stage, completed/total
counts, authoritative reused count, last observed change and a link to the owning saved
analysis. Backend facts remain separate from reasoning state. No elapsed-time threshold
invents a stall. Invalid attestation/unavailable admission is shown as a warning.

`AssistantConversationRead5` adds a nullable closed progress projection; formats 1–4 stay
unchanged. The existing durable wait appends compact observations only when owner facts
change, and its public projection reads the latest observation for the current turn AND
still-pending tool. This prevents stale cards in later waits/turns. It performs no provenance
reads, provider inference requests or repeated writes of retained tool results. Restart and
access fencing remain in the existing owner. No migration or scientific-data changes.

The packaged playbook and get_analysis_execution description explain that the embedded
Assistant can hold the response beyond wait_seconds until accepted analysis execution
settles; provider Idle during that wait is not failed computation. Changed tool definitions
and generated skill need provisioning with the new release (parent deployment ownership).

## Verification

All groups through `./hyprn-mvp dev check`, with the established development data/tool roots:

- assistant-bridge: 211 passed, 39.47s; rerun after adding exact pending-tool fence:
  211 passed, 49.32s. Final log `/private/tmp/hyprn-task10-progress-assistant-final.log`.
- agent-tools: 331 passed, 1 existing warning, 49.55s.
  `/private/tmp/hyprn-task10-progress-agent-tools.log`.
- ui-navigation, integrated Help + progress: 45 passed, zero failures/skips/flaky,
  49.45s. `/private/tmp/hyprn-task10-progress-navigation.log`. Includes real browser
  light/narrow progress card, counts, validation stage, exact link and composer spacing.
- `ui/node_modules/.bin/tsc --project ui/tsconfig.json --noEmit`: passed.
- `python3 ui/check_design_system.py`: no new violations (six pre-existing export warnings).
- `python3 ui/design_tokens.py --check`: fresh.
- `python3 ui/check_ui_contract.py`: passed.
- `python3 ui/check_component_ownership.py`: zero violations.
- `git diff --check`: clean.

Initial two group attempts exited before tests: default tools cache sandbox refusal, then
missing default-cache Python. Supplying the existing reviewed HYPRN_MVP_TOOLS_DIR resolved
both; no dependency was installed. All four test scopes confirmed released. Durable logs
remain in /private/tmp; no live store was touched.

Browser tests use a declared API double; backend tests use the real delegated runtime and
an isolated store with a provider double. They do not establish staging public/provider
integration or human acceptance. Parent owns exact integrated contract/locality checks,
release provisioning and live verification. Numerical sampling and accuracy checks are
unchanged by this slice.
