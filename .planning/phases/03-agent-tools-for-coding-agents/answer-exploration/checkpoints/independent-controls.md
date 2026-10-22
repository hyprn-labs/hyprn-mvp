# Independent exploration controls — 2026-10-16

Implementation and skill guidance: `5d5292cf020071dd59d777ffee92119f99ab3bde`.

Removed the one-at-a-time/combined mode choice. Input edits preserve the full selected vector except declared covary bindings. Plot against chooses the response axis without editing inputs; slider focus/movement no longer changes that axis. Curves remain fenced to the complete selected vector. Coordinates prepared on other slices remain selectable but their markers explicitly say no result until this combination has available outputs. No baseline result is borrowed or stitched into a joint estimate. Linked-axis curves name the coupled inputs.

Inputs and outputs have separate bordered surfaces with a wider gutter. Each output separates its title, value/unit, noninteractive calculated/estimated basis, plot, explicit X caption and right-aligned Result basis action. A prediction-service/coverage notice appears once above the diagram instead of eleven times inside outputs. Shared /hyprn instructions now describe these controls and still require separately assessed joint coverage. Its installed path is a symlink to the repository source; no installation/configuration change was needed.

## Committed-tree verification

- `./hyprn-mvp dev check combined-static`: all 9 stages pass, including input-vector and coverage tests, color contrast, public UI contract, design ownership, render smoke, TypeScript and build. Session `aaa693a9-bb07-4924-9a97-996846b226a3` in `/private/tmp/hyprn-layout-acceptance/.hyprn-checks/`.
- `./hyprn-mvp dev check ui-reading`: 23 passed, 0 failures/skips/flakes, 21.13 s. Session `4ce0139f-adda-4c2a-b7fa-316514f26a47` in the same scratch root. Includes unequal component counts, narrow/desktop layout, both themes and touch controls.
- `npm --prefix ui run build`: passed; existing bundle-size advisory remains. `git diff --check`: passed.
- Live public UI: changing the plot axis leaves all 14 input values unchanged. Moving Mach keeps the heating-value axis selected. Moving heating value next preserves Mach, leaves sliders usable and correctly gives no results for the unsupported combination. Restoring only Mach restores all 11 calculated outputs and heating-value curves without resetting heating value. Final build shows 11 concise Not computed states and exactly one shared notice. At 390 px / 25% zoom, columns have no horizontal/vertical overflow and the page stays within the viewport. Evidence: `/private/tmp/hyprn-all-sliders/independent-controls-proof.json` and `independent-controls-desktop.png`.

No failing checks in this batch. All test stores were released, diagnostics retained outside the repo. Static demo assets and readiness UI commit were refreshed without changing backend source, worker attestation, studies or calculations. Browser viewport restored and selected inputs reset. Unrelated ROADMAP/research files preserved.

The native exploration browser specification was updated for the new control contract but its expensive native preparation suite was not rerun; actual control behavior was verified through the live public UI and pure full-vector tests. Existing independent-slice data does not establish joint coverage; the current demo's live predictor also reports unavailable. No new joint sampling, warming, original evaluations, skill-authored study or release qualification is claimed. Human acceptance remains separate.
