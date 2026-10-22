# Compact answer exploration

## Delivered

Generic compact Overview exploration displays authored independent controls and study outcomes. Without saved choices it derives controls from declared ranges and outcomes from criteria/terminal graph outputs. Explicit linked-input groups have one control; connected quantities remain in Expand calculation. Fixed inputs are inspectable at their current selected values. Choose quantities persists the presentation through the public API, scoped to the exact answer/configuration, with digest validation, idempotency and compare-and-swap. It does not alter numerical design identity, samples, surrogate, input vector or immutable answer. `/hyprn` guidance now authors these display choices.

Shared design-system components own layout, readouts, legend and responsive outcome grids. Existing quantity rendering/prediction machinery is reused in both views. No study-specific name or numerical default is encoded in the UI. Demo display choices were authored separately through the public tools for its three configurations.

## Verification

Commands used the local edition entry point with scoped stores and live ports protected:

- `./hyprn-mvp dev check exploration-api --keep-scope`: 64 passed; scope `33ed2a10-cd47-44d8-9fb2-361d14c04bfd`. HTTP coverage includes read/save/replay, stale revision, invalid targets, reader writes, removed access and unchanged numerical basis/native-call count.
- `./hyprn-mvp dev check contracts --keep-scope`: 127 passed; scope `2ff21c7d-63c5-4950-ab9a-6a916587fda6`.
- `./hyprn-mvp dev check combined-static --keep-scope`: final 9/9 stages passed, 5.20 s; scope `134aa83a-9dfd-4999-b788-8f2ab8bf391e`. Includes design system/tokens, ownership, UI contract, helper regression, TypeScript and Vite build.
- Real served app: compact 3 controls/3 outcomes, intermediate promotion/save/removal, expansion to 14 controls and all 11 outcomes, current-value fixed-input disclosure, collapse preserving a simultaneous-input vector. Interior selection returned actual estimates and curves; moving Mach 5.72 to 5.75 changed all three displayed estimates. No fixture or simulated outputs used.
- Public readback: operation `8a92245e-d59f-48d1-ae96-907709137e67` remains complete, 120 attempted/completed, 0 failed, 120 points. Surrogate `3c1fff8a-90f7-4e6c-bce2-05d260f2c7b0` remains ready with identical identity. Three saved display views verified.

External evidence in task scratch `hyprn-focused-exploration`: `verified-records.json`, `views.json`, `compact-live.png`, `web.json`, `ui-delivery/delivery.json` and recoverable previous UI index. Numerical runtime fingerprint unchanged. Only the identified demo web process was restarted for the additive endpoint; dispatcher and restricted runtime retained. No unrelated process stopped. Integrated UI includes the other session's pre-existing export-card padding delta; that file is excluded from this commit.

## Failures resolved

- Initial static run rejected nullable values passed to number formatter; shared nullable readout fixed it (`f325940d-03f5-457b-a256-032aa0a2cde1`).
- Initial API run: 63 passed, 1 test incorrectly expected 403 for removed membership; corrected to existing concealment 404, with separate reader-write 403 coverage (`8f0f6896-45a2-4733-a49c-5aafaa546322`).
- Last linked-representative refinement invalidated a helper expectation; updated test to assert the authored alias is shown (`454ae4b3-bf50-4705-bec2-d14b40460234`). Final static pass above supersedes earlier static passes.
- Web restart guard first refused an incorrect scratch-root environment before effects. The known old web child subsequently exited but remained an unreaped zombie; confirmed free port/exited state before starting its replacement. Failed login during the gap and wrong tool argument names occurred before view mutations; then all saves/readbacks succeeded.
- Browser exact-name locator did not match the composed fixed-input disclosure name; fresh accessibility control opened it successfully. Slider action itself succeeded.

## Remaining boundaries

Existing default-baseline boundary coverage is incomplete: exact baseline values work, some curves or changed vectors have no sampled support. This presentation change preserves rejection of unsupported estimates; it does not claim to repair coverage. Existing interior coverage works. Full release qualification and human visual acceptance remain separate and deferred. Checks retained their scoped evidence; no live data removed.

## Committed-tree check

Implementation commit `513345d` was checked in an isolated Git archive excluding concurrent changes. `./hyprn-mvp dev check combined-static --keep-scope` passed 9/9 stages in 4.85 s; scope `41b6551b-f1dd-4bfa-b91a-bf8df963d4c2`. The only later change in this batch is this evidence paragraph. The live UI uses the separately checked integrated build above, preserving the other session's padding delta. No further numerical execution or deployment change occurred during this check.
