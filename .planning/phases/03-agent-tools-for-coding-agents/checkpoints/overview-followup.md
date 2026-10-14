# Overview follow-up: editing and supporting records

User-directed refinement, 2026-10-14. Implementation commit: `62bfba0`.

The question box and page order stay as requested. See more details opens the
existing Study details fields; Edit all edits the shared approach draft and saves
a new version. Existing revision/receipt and navigation guards apply. Model details
is at the bottom-right of the complete method. Case support appears once, grouped
by exact configuration with its runs underneath; cited records are labelled. Usage
pages load automatically, so pagination no longer implies a configuration has no
run. Study support groups those same records by authored case, with aligned actions.
The redundant bottom Study details action and usage-loading counters are removed.
No fuel-specific case taxonomy or selected output set is hardcoded.

The repository scientific skill and packaged playbook now require cross-record
coherence review and method explanations following the actual input-to-output
calculation. Two qualitative scenarios were added to the reference set; they have
not received a new independent behavioral evaluation. Existing scientific demo
content was not revised or newly certified by this UI batch.

## Verification

- `./hyprn-mvp dev check combined-static`: all six stages pass on `62bfba0`
  (3.57s); design system, tokens, public contract wiring, criterion-record tests,
  TypeScript and production build.
- `./hyprn-mvp dev check style-ratchet`: 33 pass on `62bfba0` (10.81s).
- `./hyprn-mvp dev check approach-ui-method`: 19 pass, 0 fail, 0 skip on
  `62bfba0` (123.31s), including save/reopen through the real API,
  old-version immutability, exact source, narrow layout and genuine 200% zoom.
- `./hyprn-mvp dev check agent-tools`: 270 pass (existing Starlette deprecation
  warning). The tested guidance bytes are identical to `62bfba0`; later changes
  only affected UI/test formatting and navigation. Skill metadata validator passed.
- Live demo served from the exact final build at the retained loopback address.
  Verified See more details → Edit all → cancel; method-footer model dialog;
  first two case configurations each grouped once with their real runs; all 11
  methane outputs; study support grouped across all eight cases. No live authoring
  data was changed for UI testing. Web process reloaded to serve updated guidance;
  the restricted worker and stores were not rebuilt. Automated browser observation
  is not human acceptance.

## Failures and recovery

Early static failures were obsolete wiring checks and a removed prop still passed
by one caller; corrected. The style ratchet identified changed long lines, then
passed after wrapping. First browser attempt: 17 pass / 2 fail (missing zoom browser
and test navigating before the selected approach finished loading). Second: 17 pass /
2 fail (desktop Chrome refused the zoom extension; a test label matched both section
and textbox). Explicit role selectors and the installed testing Chromium resolved
both. No new browser dependency was installed.

Initial tool-cache access required sandbox escalation. Missing development-root
settings refused early style/demo-refresh attempts; explicit verified settings
resolved them. The scope guard refused demo restart twice before any service was
changed. Cleanup initially refused missing tool-cache configuration; explicit cache
resolved it. All failures were environmental/test wiring or corrected implementation
issues; no failed operation was treated as successful.

## Artifacts and remaining scope

External evidence folder: `hyprn-overview-followup` under the system temporary root.
It contains the final UI SHA-256 manifest, previous entrypoint/web script for recovery,
web refresh identity, screenshots and indexed check evidence. The completed test
scopes (18) are archived and released in `cleanup.json`; the live demo scope is retained.
Final browser scope `248e2c32-a9cb-463c-a61d-74a6b137f3be`;
static scope `aa5f76dc-97d8-4cef-9134-9e2713c6055e`; style scope
`79fbd15c-9f84-4def-a182-617ee0b93058`; agent-tools scope
`d161804a-fef8-4336-a53c-c9cff49776ed`.

Unrelated ROADMAP edits are untouched. No push or publication. Full release
qualification and an actual scientific coherence pass on existing content remain
outside this UI iteration. Next action: user review of the refreshed Overview.
