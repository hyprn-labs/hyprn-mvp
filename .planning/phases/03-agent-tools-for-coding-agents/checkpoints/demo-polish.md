# Demo reading polish and notice review

User-directed batch, 2026-10-15. Target: the existing local demo; no calculation,
backend schema, worker policy or stored scientific record changes. Implementation
commit is the commit introducing this checkpoint; final verification is recorded below.

## Delivered journey

HYPRN logo-only branding and `Account name: owner`; study sections have equal border
spacing and no empty legacy-limit editor. Answer actions share compact button
sizing; answer prose and expanded run criteria/outputs have separated sections.
Model inspector actions precede the title and explanation; the narrative uses
`Calculation logic`. Saved draft, unsaved changes and saved read-only version states
share one neutral/warning presentation. Record actions identify their entity owner;
case record identity includes the approach version, and answer records remain distinct.
Cases use a list and dedicated detail. A run opens the exact version-qualified case
in Cases, including historical names, and supports an explicit return. Loading and
unknown cases are never presented as empty or replaced by another case. View run and
Run details form one vertical action group. Duplicate criterion summaries and the
requested list/method filler are removed.

The supplied logo was copied unchanged, SHA-256
`3ec5f72242e291ff570315ea60ae7b669ce20e8dea20d62d7a712e3d74b9ac43`.
Browser MIT notices match all three shipped runtime package licences. AiiDA's
installed licence and the running WhatsOpt source bundle/licence were inspected
read-only. [Licensing §8](../../../../docs/legal/licensing.md#8-demo-interface-notice-review--2026-10-15)
records delivery-specific obligations; external source-offer and release legal
review remain open. No unnecessary supplier branding was added.

## Verification and limits

- `./hyprn-mvp dev check approach-ui-demo`: 2 passed, 0 failed/skipped, 22.39s,
  scope `3e708d09-59ea-44c0-93e8-d806abac584e`. Actual browser/public API/store,
  declared private modeling fixture; no numerical execution. Checks branding,
  profile, empty-limit removal, inspector geometry, light/dark narrow layout,
  historical case navigation, scoped record identity and unknown-case refusal.
- `./hyprn-mvp dev check combined-static`: six stages passed, including 4 criterion
  render tests, type check, design/tokens/contracts and production build, 4.01s,
  scope `f3fdcbfb-1a76-45cf-9f6e-e7040d2e90ed` before final formatting.
- Live local browser inspected study detail/edit, answer dialog, case sources,
  expanded run and run-to-case navigation. The static build is refreshed in place;
  application, modeling/worker processes and stores stay unchanged.
- Broader `approach-ui-reading` attempt: 11 passed, 6 failed, 0 skipped,
  scope `e33a2e87-2d4f-43f2-bdcd-cf07c4ce364c`. The old suite still expects the
  previous About/Overview structure and return focus, plus an older study-context
  refusal flow. The sign-in wording assertion was updated. The remaining suite
  reconciliation is deferred; this batch does not claim full qualification.
- Corrected development failures: stale static text assertions, redundant TypeScript
  condition, old saved-state selector, a Profile check racing initial version load,
  changed-line style violations and two formatting delimiter errors. All retained
  evidence and final outcomes are under the external `hyprn-demo-polish` folder.

Automated browser checks are not human acceptance. The unrelated ROADMAP edits are
preserved. No push or external publication. Next: user demo review; maintainer owns
reconciling the older reading suite before release qualification.

## Committed verification

Implementation `d4a8c1c`: `approach-ui-demo` passes 2/2 (20.03s), scope
`3efe8550-c154-435c-99d8-b43e62dfe6a3`; `style-ratchet` passes 33/33 (14.38s),
scope `a118b08a-d7ec-466d-8936-4d66a58476fc`. The first committed static attempt
found formatting-sensitive source guards, not missing wiring. The only subsequent
executable delta normalizes whitespace in those guards; label and binding
requirements are retained. All six static stages then pass (3.49s), scope
`a6a75f63-305a-4f1a-ba53-1d4695908102`. Final gate logs and build manifest live in
`/private/tmp/hyprn-demo-polish`; no test runs against the user installation.
