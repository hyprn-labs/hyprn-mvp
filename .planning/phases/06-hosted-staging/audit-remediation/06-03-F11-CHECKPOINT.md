# F11 — Bound source-retrieval receipts

Status: implemented; focused bridge verification passed. Parent owns public route,
contract generation, agent read projection and integrated/staging qualification.

## Claim boundary

A receipt establishes only that HYPRN retained a successful provider fetch for the
exact cited requested URL, and that a saved verbatim excerpt occurs in returned
text. It does not authenticate a redirect destination, prove a scientific claim,
certify interpretation or replace applicability review. `scientific_review` remains
an author self-assessment. Human/uploaded/older/unmatched evidence remains usable
as author-supplied material; no saved evidence or study content is rewritten.

The receipt is derived only after a real delegated runtime add/revise succeeds,
never from a provider custom-tool-result assertion. Its private payload pins the
exact evidence version and content digest, quoted-text and returned-text digests,
and paired provider event IDs. The public projection has no provider IDs or source
bytes. Server receipt time is named `observed_at`, not retrieval time. A new evidence
version cannot inherit a predecessor's receipt.

## Implementation and scope

- assistant/research.py owns closed public definitions, write-time derivation and
  authorized exact-version reads. Existing event storage holds immutable receipts;
  no new table, editable record or source-ingestion subsystem.
- conversation.py refuses provider-supplied `hyprn.*` internal events and invokes
  receipt derivation within actual tool-result retention.
- records.py indexes built-in results by their existing tool-use reference column.
- Pairing requires successful `web_fetch`, a prior call/result, exact cited URL,
  non-error text/plain-document content and exact excerpt. Search, denied/failed
  or unknown-status fetches, URL-only documents and later fetches do not qualify.
- Write inspection is bounded to 256 recent built-in calls; older/missing
  observations conservatively remain author supplied. Public reads use the receipt
  key, avoiding a session-history scan on polling.
- Canonical evidence guidance explains these distinctions without claiming platform
  certification. Parent final skill generation must use these updated bytes.

Official event shapes inspected at
https://platform.claude.com/docs/en/api/beta/sessions/events/list and
https://platform.claude.com/docs/en/managed-agents/tools-web-restrictions .
CMA built-in tool-result text/plain-document blocks are supported; no unsupported
Messages-API web-fetch-result schema is assumed.

## Verification

- First `./hyprn-mvp dev check assistant-bridge`: 173 passed, 12 failed,
  31.45 seconds; log `/private/tmp/hyprn-f11-assistant-bridge.log`.
  Scope `21c232c8-2ac1-4021-953b-3dd1dbcf0eb7` released by runner.
  All new receipt and public-route assertions reached their expected results;
  each parameterized test then failed because the test tried the intentionally
  first-user-only provisioning method for its outsider user. Corrected to the
  existing synthetic second-user fixture pattern; production logic unchanged.
- Final `./hyprn-mvp dev check assistant-bridge`: **185 passed**, 28.29 seconds;
  log `/private/tmp/hyprn-f11-assistant-bridge-final.log`. Scope
  `2c52502c-0062-4ee4-8544-fc77faed6ff2` released by runner. This includes actual
  delegated writes, successful/public receipt reads, exclusion cases, exact-version
  revision behavior, cross-study access refusal and provider namespace refusal.
- Explicit owned-path `git diff --check`: clean. No live stores/provider mutations.
- Remaining: parent agent-tools and contract/module-boundary checks, final native
  bundle and live provider qualification. Fake-provider tests exercise the real public API and delegated
  runtime, but do not establish live provider fetch support or scientific validity.
