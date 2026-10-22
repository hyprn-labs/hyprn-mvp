# Answer exploration integration — 2026-10-19

Implementation: `e5a67c7` on `codex/resume-domain-integration`. No live deployment yet.

The saved study answer now selects an exact calculation version, assessed estimate (optional)
and bound outcomes. Its figure reads that basis through the public API, shows all independent
inputs, expands the actual model graph and links calculated values to their exact runs.
Slider selections and plot-axis changes are disposable; they never rewrite the saved answer.
The plot axis is independent of the changed input. Explicit linked inputs use their declared
mapping. Inputs outside the design retain their saved assignment. Exact original values,
including unavailable outputs, take precedence; assessment-pinned runs are not replaced by
later runs. Unassessed output predictions remain unavailable.

Prediction uses the existing native surrogate bridge with its 33-query bound. A cold worker
reloads the identity/hash-checked assessed artifact, never refitting or dispatching samples.
The request queue is bounded by actor/study/estimate and expires; authorization is rechecked.
Pure quantity projection was extracted without changing its behavior.

## Focused evidence

All checks used `./hyprn-mvp dev check <group>` in isolated scoped stores. Logs are in the
external `hyprn-domain-resume` directory; the runner retained and released scopes.

| Group | Result | Check storage ID |
|---|---|---|
| calculations-api | 57 passed | 166a18c4-15eb-4a83-81eb-82a4f8d5d8a0 |
| contracts | 127 passed | d75598c7-fd7d-419f-a0b0-0b9231f36fbd |
| combined-static | 9 checks passed | b9f6370c-fa14-4a1b-9cd8-6512ea40bebb |
| study-answer-ui | 2 passed | 6524ac8a-53a9-4111-9ff1-d56886b20130 |
| guard | passed | e8facedb-6daf-4586-81e7-cb300df98d14 |

The first browser run reached the figure/model/settings, then failed an exact close-button
label lookup. Its corrected rerun passed. Initial API evidence (56 passed) was superseded by
57 after adding joint-input/independent-axis/outside-domain coverage. A final diagnostic-string
line wrap has the identical Python AST; all other tested source bytes are the committed batch.
Light/dark screenshots were retained; light screenshot inspected. The old About/approach box
is still visible pending retirement. Numerical transports in these tests are declared doubles;
real native fit/predict and containment remain to be verified in the rebuilt demonstration.
Automated browser evidence is not human acceptance.

## Remaining

- Remove old approach API/UI/store/tool/workflow ownership and old exploration owners after
  extracting any remaining numerical design helpers. Preserve unrelated research/ROADMAP edits.
- Integrate exploration of/compared alternatives with explicit saved scientific basis: the
  current answer basis pins one calculation version/estimate; do not silently use newer
  estimates for other alternatives or imply cross-model input correspondence from names.
- Update /hyprn and its tools to prepare sampled calculations/estimates through their owners.
- Rebuild/re-attest where required, preserve source evidence, reset authorized development
  records and re-create the fuel demonstration with real joint samples and assessed predictions.
- Keep the inherited qualification limitations in RESUME.md; no full qualification claim.
