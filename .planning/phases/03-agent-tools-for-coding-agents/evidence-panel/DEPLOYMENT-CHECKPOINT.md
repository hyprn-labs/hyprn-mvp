# Evidence deployment and independent assistant — 2026-10-17

Delivered `535c6df` and `d0a76f4`. This supersedes the live-validation and
source-curation deferrals in READER-CHECKPOINT.md. Existing page layouts remain.
The user's reference application was inspected directly in Chrome: assistant
alone, details alone, both docks, full-width expansion/restoration, hide, resize
and reset. No reference code or assets were copied.

## Observable result

- One shared assistant launcher, present only while hidden. Independent details
  and assistant docks, available viewport height, full-width mode retaining the
  hidden reader, restore, hide, focus return, pointer/keyboard resize and reset.
- Shared configuration headers wrap commands below a readable title when docks
  reduce available width. Resize reserves reading space; a workspace container
  breakpoint stacks details when three readable columns cannot fit.
- Live backend now validates marked evidence content. Public POST of malformed
  structured content returned 400 `/content`, outcome unchanged; all heads stayed
  identical. Worker runtime hash and dispatcher were preserved.
- Six existing evidence families received new versions through the owner helper.
  Three cited PDFs were retrieved and their relevant pages visually checked:
  Andro printed/PDF p.3; atmosphere printed p.33 / PDF p.39, Table A1; hydrogen
  printed p.5 / PDF p.17. Study/run records have explicit unpaginated locators.
  Quotations/transcriptions and explanations are distinct. Table/JSON whitespace
  normalization is disclosed. The historical 75-seat comparison is distinguished
  from the current 100-passenger study.
- All eight earlier evidence records and the complete sampled recorded run were
  read back and remained identical. Frozen models/configurations/runs retain their
  historical pins; revised heads are available in the evidence library.

## Verification

All checks used `./hyprn-mvp dev check` with the host's configured isolated roots.

| Group | Result | Evidence |
|---|---|---|
| `combined-static` on final delivery | 9 stages pass, 0 fail | delivery-static.log |
| `ae-ui-evidence` on final delivery | 13 pass, 0 fail, 0 skip | delivery-evidence.log |
| `ui-navigation` | 12 pass, 0 fail, 0 skip | navigation-check.log |

Focused evidence acceptance exercises the actual HTTP/API/store boundary and
includes both docks, full-width restore, keyboard resize/reset, readable minimum
canvas, disabled disconnected composer and immutable evidence revisions. Navigation
uses a declared API double. Live Chrome additionally verified pointer drag/reset,
closing either panel independently, source/explanation separation, 1440×1000 light
and dark themes, and a 720px viewport with no horizontal page overflow. Original
System appearance and viewport were restored. No scientific calculations launched.

External evidence root: `/private/tmp/hyprn-evidence-deploy`. It retains public API
transcript, before/after records, prepared command IDs, revisions, source PDFs and
page renders, source fingerprints, web backup/delivery, UI backup/delivery, logs,
source-retention verification and browser screenshots. UI delivery hashes are in
`ui-delivery/delivery.json`; source build scope ends `e0c4f06e-3d7e-416c-a214-b710c8856dab`.

## Failures, recovery and remaining boundaries

- Initial web guard rejected the wrong ambient scratch setting before mutation;
  the installation's recorded setting passed. One malformed-note probe used the
  wrong endpoint (404, unchanged); the documented endpoint then proved 400 validation.
- Two initial API inspection scripts had local name/import errors, with no writes.
- A passing build had been automatically cleaned, so a retained build was produced.
  A concurrent UI refresh then tripped the index guard; all six served files matched
  the checked build exactly. The later header correction was deployed atomically
  with a fresh baseline and rollback index.
- A concurrent commit landed during partial staging. The working files stayed
  intact. Automatic review initially rejected an index repair; hashes proved that
  it restored only parent-commit bytes, and review then permitted amending our own
  commit. No new concurrent work was staged. ROADMAP/research/export-spacing work
  remains untouched.
- Browser verification found the squeezed title; the shared header/resize fix was
  added, retested and deployed. Fixture shutdown logged benign BrokenPipe errors;
  all 13 cases still passed. No failed check is counted as a pass.
- Routine test scopes were automatically released. Two explicitly retained static
  builds remain under the check runner's 24-hour retention/budget for rollback;
  no live authoring store was cleaned.

Human visual acceptance and full release qualification remain separate. Assistant
chat integration remains disconnected; this delivery implements panel behavior.
Source passages were manually checked, not produced by authenticated extraction.
Existing broad reading/generated-contract baseline failures remain documented in
READER-CHECKPOINT.md; those groups were not claimed as passing here.
