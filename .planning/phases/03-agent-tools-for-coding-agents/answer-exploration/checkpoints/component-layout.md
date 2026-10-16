# Component layout delivery — 2026-10-16

Implementation: `e759698076a65ba82094e174df4acf0e78fc7429`.

Generic answer explorer cards use measured natural heights and matching columns. Outputs always show response plots; inputs divide the left column evenly, with consistent labels, value fields and units. Input minimum sizes can grow a card rather than clip content. The graph supports 25–250% zoom; arrows follow measured card bounds. No component has an internal scrollbar. Calculated samples use neutral black (light ink in dark mode), estimates use orange, with solid/outlined marks and explicit basis words. Removed response disclosures, component ordinals, redundant curve captions and interval-count prose. Connected inputs remain explicitly connected, not independently editable.

The owner-requested estimate palette is recorded in Scientific-states.md. No schema, saved scientific record, computation, backend source or worker policy changed. The storage session's files and unrelated ROADMAP/research edits were preserved.

## Verification

On the committed implementation, using the pinned local entry point and an isolated scratch root:

- `./hyprn-mvp dev check combined-static`: all 9 stages pass, including design ownership, tokens, public UI contract, tooling, render smoke, color/input checks, TypeScript and production build. Evidence session `b1795d8f-3fef-4198-b97f-786990e0995f` under `/private/tmp/hyprn-layout-acceptance/.hyprn-checks/`.
- `./hyprn-mvp dev check ui-reading`: 23 pass, 0 failures/skips/flakes. Includes generic 2-input/4-output and 7-input/1-output cards, long names, 25/50/75/100% zoom, desktop/narrow layouts and both themes. Evidence session `842a96be-7a81-4d69-8b0b-dd228e4f428e` under that same scratch root.
- `npm --prefix ui run build`: pass; existing bundle-size advisory remains.
- `git diff --check`: pass before commit.
- Live public UI at port 54821: all three components have equal-height columns, no internal overflow and 11 visible plots. A calculated selection and an estimated selection update all 11 outputs. Slider dot/track center lines match exactly. At 390 px width and 25% zoom, document width remains 390 px. Proof and desktop/narrow screenshots: `/private/tmp/hyprn-all-sliders/component-layout-proof.json`, `component-layout-desktop.png`, `component-layout-narrow.png`.

Test stores were released automatically; compact diagnostics were retained outside the repository. The live static UI is built from the implementation commit and the readiness file records that UI identity; backend and its attestation remain unchanged. Browser viewport override was reset. Automated browser verification is not human acceptance or release qualification.

## Failures corrected

Initial sandboxed check could not write the existing tool cache; reran through the approved escalation. The first reading run had 22 passes and one pre-existing specimen-inventory gap for AnswerProse; added the missing specimen. The next run exposed intrinsic graph width expanding a narrow page; added inline size containment. The third exposed 36 px output controls on touch; restored the 48 px touch minimum. The final committed-tree reading run passes all 23 tests. No checks were weakened or skipped.

Remaining obligations: human demo review; existing slow historical overlays, six-second performance target and storage-owned style findings remain in the batching checkpoint. No new sampling was needed for presentation changes.
