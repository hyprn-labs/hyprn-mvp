# Brand and control consistency

2026-10-17. User requested owner-supplied branding adapted to both themes, Settings Home returning to the originating study, readable saved Python and vertically centred controls. Implementation: `72539a7`, integrated over `5713d58`. Existing layouts and scientific data are preserved.

## Delivered contract

- One BrandLogo uses the supplied mark geometry and wordmark silhouette with theme tokens and transparent ground. Selected original assets and SHA-256 provenance are retained under ui/src/design/assets/brand; favicon/touch icons are bundled locally.
- Settings remembers the originating study for Home; All studies remains available and session end clears the remembered origin.
- Verified saved Python uses the shared full-width, left-aligned SourceReader after the existing digest checks. No source bytes or model records change.
- Shared buttons, native selects and disclosures own text/arrow alignment. Ownership guards reject screen-specific summary/select overrides. Navigation respects the shared touch target size.

## Integrated acceptance

The isolated source was verified byte-for-byte against every tracked file in `72539a7`. Commands used the pinned local edition environment and isolated stores: `./hyprn-mvp dev check <group>` (`--keep-scope` only for static build artifacts).

| Group | Result | Scope UUID | Evidence store UUID |
|---|---|---|---|
| combined-static | 9/9 stages, exit 0 | 731b06ac-d13b-4e7d-8858-04e950c9fdd5 | 3330f05e-055e-4dce-8abb-f2ff7e43d164 |
| ui-navigation | 16 passed, 0 failures/skips/flaky, exit 0 | 2e08740c-47b9-4be7-915d-e3b90fe32525 | 9dec195b-c965-44f6-acc7-f266f673869d |
| ui-reading | 33 passed, 0 failures/skips/flaky, exit 0 | 0a843e35-8bdf-4105-a299-3d1b4cc402b4 | b9cb4dda-7803-4f85-9a74-b854ef3398f7 |

Evidence is outside the repository, in the task's hyprn-configuration-checks check-storage root. Browser suites use declared API fixtures, so they establish presentation/navigation rather than backend scientific correctness. They cover both themes, narrow layouts, disclosure expansion, Settings return/signout, source identity/alignment and touch sizing. Real-app verification is recorded below separately.

## Corrections and failures

- New source test initially matched hidden XDSM elements as well as the graph; scoped to the directed-diagram region. Native select line-height can be normal; geometry assertion uses its rendered font size in that case.
- Strengthened ownership guard identified five old screen summary overrides; removed them from screen ownership.
- Reading suite initially had six stale navigation/preview assertions; migrated to Calculations tabs and represented shared components in the design preview. The next run found a real 38px touch navigation row; changed it to the shared control-height token. Final preintegration suite passed 33/33.
- Concurrent `5713d58` changed model-name semantics. Integrated reading run passed 32/33 until its model listing fixture supplied name and its saved-model assertion expected that name; final committed acceptance above passes.
- A scratch integration script used an unsupported Python tar filter argument and stopped before changing files. Replaced with explicit member/path checks and extracted into a fresh folder. Redundant preintegration checks passed but are not the delivery evidence.

## Deployment and boundaries

UI delivery preserves the pre-existing, unrelated export-list padding change (space-5 to space-6) without including it in this task's commit. It is the only source delta from the accepted commit in the live build. Runtime identity and live index are fingerprint-guarded; previous index is retained for rollback. No backend restart, authored-record mutation or dependency installation belongs to this task.

Automated/browser checks are not human acceptance. This is a focused UI delivery, not full release qualification. User visual acceptance remains the next checkpoint. Unrelated roadmap, research and primitive-cleanup edits stay untouched. Browser test scopes are released by the runner; retained static scopes follow its timed cleanup policy.

## Real-app delivery verified

The live build passed all 9 combined-static stages in scope `6ab9fc05-d544-45d5-80b0-962ea4dd1fb9` (evidence store `f785a825-7c37-45a4-b617-5e934a930821`). Guarded UI-only delivery completed, with runtime fingerprint unchanged. Index SHA-256: `27996e740233e4ff06ccde1df636e70110e6d2e612a2a52abde6184137f5b209`. The external task directory retains `ui-delivery/delivery.json`, `baseline.json` and `previous-index.html`; assets are additive so the previous index is a recovery path.

Authenticated Chrome verification used the real study `50e423fd-a709-4e21-9381-0b09022b4115`, model `3f4d85eb-41bd-484f-a7a7-91729ddbf4e7`, saved version `b7083103-296f-4c45-b48a-58c1ed4be8c9`:

- Settings → Home returns to that study's Overview in both appearances. The original Dark appearance was restored.
- Saved Python occupies its reader's full 1172px width with the same 290px left edge and start alignment. Its displayed SHA-256 remains `1f1c5d1816caace6bde33d981f0407dfb42af8824c990a78bfeefef1a357b5d0`.
- Logo is transparent with light ink `rgb(17, 24, 32)` / dark ink `rgb(232, 237, 242)`; supplied wordmark and mark render in both themes.
- Real Export scope disclosure opens/closes normally, uses flex/center and has measured text centre offset 0px. Dialogs were dismissed without exporting or modifying study data.
- Screenshots in the external `hyprn-brand-fixes` task directory: `brand-overview-live-light.png`, `brand-overview-live-dark.png`, `brand-python-live-light.png`, `brand-python-live-dark.png`, `controls-live.png`. Inspected visually. The real current study is left open.

Human visual acceptance remains pending; automated checks do not claim it.
