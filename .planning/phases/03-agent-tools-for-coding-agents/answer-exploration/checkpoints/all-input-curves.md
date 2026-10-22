# All-input prepared curves — in progress

Owner request: every slider needs calculated points and assessed estimates, with generic behavior across inputs and category combinations. Implementation: `e86f23d`.

## Delivered implementation

- Additive exploration V2 declares linked inputs explicitly and returns verified original output rows with their immutable run identities. V1 remains readable; the numerical worker is unchanged.
- Discrete controls use available exact and assessed estimated points. The explicit default, **One input at a time**, restores other inputs to the saved baseline; linked assignments move together. **Combined inputs** retains full-vector eligibility and does not combine independent curves into a joint prediction.
- Earlier unsuccessful methods cannot hide a later preparation with more assessed outputs. The skill requires coverage of every input in every category, numerical vector equality, exact run/runtime pins and disjoint checks.
- Intervals with fewer than five admissible discrete values expose those values only. The evaluation's passenger interval has three integers, all calculated; fractional passengers are not manufactured.

## Verification of implementation

All commands ran through `./hyprn-mvp dev check <group>` with the configured development environment.

| Group | Result | Retained scope |
|---|---|---|
| exploration-contracts | 32 passed | `906617ca-ad92-4fda-b810-5ff3413497bf` |
| contracts | 127 passed, 2 warnings | `262d0ac1-0a49-4d62-9825-c0de467916a9` |
| combined-static | 9 stages passed, including design checks, public UI contract, types and build | `b2277304-4c47-4322-b931-d3575f552a3b` |
| style-ratchet | 33 passed | `c4a8c295-ceb7-4139-a906-9341e751f699` |
| exploration-ui | group passed, two browser scenarios; 129.28 seconds | `e485db7c-4a1d-4f04-919c-1c6e549aa544` |

The final browser group ran on committed `e86f23d`. Earlier style failures were overlong lines, corrected before the final passes. No full release qualification or human acceptance is claimed. The user removed task 3.V6 from this delivery.

## Live preparation and recovery

Evaluation study: `50e423fd-a709-4e21-9381-0b09022b4115`; answer: `5a2786ed-d321-4aa7-b0b9-ebfabe5131c1`; exact model: `420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`. The resumed preparation uses saved public command/run receipts, five seeded training points and two disjoint checks per continuous independent slice, with the original absolute `1e-6` / relative `0.01` targets. No tolerance relaxation or browser physics.

The remaining preparation manifest and progress are outside the repository under `/private/tmp/hyprn-all-sliders`. Three existing Mach fits were projected through V2 without repeating their original calculations. Thirty additional fits require 150 new originals, reusing compatible endpoints. The first linked-input Kriging attempt assessed 10/11 outputs; a response surface on the same original/check partition assessed 11/11 and is preferred.

At the resume checkpoint, local storage cleanup had removed the running containers, Python environments, service credentials, scope/profile metadata, dependency selection and some native artifact copies. Recovery used the pinned repository entry point, retained database identities, original container mounts/image, and exact content hashes. The recovered dependency-selection bytes match the original attested SHA-256; the worker/runtime/containment proof was not changed. The local demo password was regenerated through the existing owner-recovery operation because its file was gone; previous sessions were revoked.

Recovered 660 deleted native objects from exact application copies; 2,636 stored native objects have verified hashes. **212 historical native submission/output-log objects for 53 older runs remain missing after cleanup.** Their missing-object report is retained alongside recovery evidence. Application authoring records and retained outcomes were not replaced. Historical native export completeness is not claimed. This is separate from new curve qualification.

Original check run `02901b52-d873-4e62-838a-e0fad102692a` had recorded worker exit 300 with no usable output. The rejected fit returned HTTP 400 with outcome unchanged and no command receipt. Only that failed check was replaced, by `e2643b05-491a-48a1-91ca-3c256c865b05`; the revised fit passed all 11 targets. The preparation client now checks terminal exit status before accepting an original, instead of equating `recorded` with success.

Configuration preview after recovery passed in 0.68 seconds (the earlier diagnostic returned 503 after 21.22 seconds). Recent originals take approximately 31 seconds end to end; inspected native execution was about 6 seconds. Bulk preparation remains expensive and is not evidence of acceptable onboarding performance.

## Next action and limits

Continue the saved preparation, then verify every slider/category through the live page, including cold reload, original/estimated markers and response values. Kerosene's ten additional fits currently meet all 11 targets; methane/hydrogen are still being prepared. Do not mark this delivery complete yet. Joint multi-input coverage remains separately assessed; baseline slices do not establish it.

No new dependencies or candidate-worker source changes. Earlier compact/discrete checkpoint records initial scratch cleanup. The interrupted backup was partial and removed; no successful full-store backup is claimed. Unrelated ROADMAP and research edits were preserved.
