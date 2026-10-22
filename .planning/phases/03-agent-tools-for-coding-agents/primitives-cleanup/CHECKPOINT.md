# Primitive cleanup — implementation and live transition

2026-10-17. User authorized complete Case retirement, consistent backend model names and Light/Dark appearance. ADR 0006 and the narrow contract exception supersede earlier case-based product rules. No general immutable-record rewrite or execution exception is introduced.

## Delivered behavior

- Backend model listing owns the current family name; bounded pagination occurs before remote reads. Models and Calculations use it, with exact saved version identity separate.
- Profile exposes only Light and Dark, default Light.
- Case fields, schemas, associations, navigation, filters and answer indirection are removed. One answer head per exact approach version cites configurations, runs and evidence directly. Old development stores are refused with an actionable export/reinitialize message; saved records are never edited in place.
- Supporting results load only explicit answer references and group each configuration with its cited run. Sampling, surrogate training, numerical execution and original/estimated distinctions are unchanged.
- Agent tools, `/hyprn`, product contracts and design guidance use the same primitives.

## Focused evidence

All commands use `./hyprn-mvp dev check <group> --keep-scope`, locked environments and isolated stores. Host variables are external; live port is fenced. Counts are tests except combined-static (stages).

| Group | Passed | Evidence scope UUID |
|---|---:|---|
| contracts | 127 | 7bbc19bd-f847-4e7c-b4ea-9619aa9846b0 |
| approach-contracts | 152 + 117 guard | 33465ce3-13fa-45b8-9812-bb289fc31e16 |
| units-contracts | 89 | 18b85940-a3ef-43a3-8335-10f0d6f1876b |
| documents-contracts | 57 | b4eaa3e8-ba50-4d03-b89f-491d97fd774e |
| documents-citation-contracts | 53 | d5ea6596-865d-414e-9cc9-ea3bbf3eb592 |
| findings-history | 116 | 23c1a0b8-acec-4cf7-8961-1789482a9564 |
| answers-api | 25 | e3d62526-c5c3-4b3f-9bf4-ed1cc4595911 |
| exploration-contracts | 31 | 08bce3a4-0b6c-44c3-a81e-23b0b1c0c231 |
| ae-authoring | 80 | 2b392823-5836-462b-a4e2-1473c313bb0d |
| approach-configuration | 59 | 15cc70bd-5ece-40e3-bd70-062445d8135d |
| approach-worker | 53 native | b55a2a44-1d9d-4f01-b96b-bf15067a8acd |
| agent-tools | 271 | 71d979c4-29d5-44b1-b736-58b1e303b782 |
| ui-navigation | 14 mocked API | ac31500d-405f-47f6-a2c0-20229fa658b5 |
| combined-static | 9 | 8647be67-dbd9-4d9a-aa8f-81a58073c0c7 |

Corrections during verification: retired-field assertions and fixtures; remaining history status tuple indexing; missing model-name fixture values; UI type/import errors; guard environment missing the protected live port; older history tests assuming retired result facets remained public and patching the earlier pairing table; old contract baselines omitting already approved additive units/public record-view metadata. Final focused checks above pass. Historical frozen baseline hashes remain intact except the explicitly listed Case removal digests; fixture repairs are pinned separately.

## Live data and actual execution

External recovery and operation manifests are under the task's `hyprn-primitives` scratch directory. The prior application database was atomically archived before a fresh store was created. Identity, memberships, studies, model associations and evidence were preserved. Authored approaches were restored as new records without cases; old authored versions/answers remain in recovery. Private model revisions and source bytes were not changed.

Eight baseline runs were recomputed through the public API/current attested worker. Every output equals its prior value. Eight initial attempts safely refused source drift because an old launcher wrapper referenced another checkout; all were terminal before explicit replacement submissions. The wrapper was rebound to the actual source and re-attested; no uncertain run was retried.

Browser inspection confirms direct configuration/run supporting cards, the same plain model name on draft/saved versions, no Cases navigation, and Light/Dark options. Automated browser evidence is not human acceptance. The joint reconstruction completed; final exploration evidence and its remaining coverage limit are recorded below.

## Boundaries and remaining obligations

This is a working demo change, not full release qualification. Broad legacy UI qualification and durable historical demo-fixture requalification remain outside this focused pass; no pass is claimed for them. Recovered old Case artifacts are offline historical recovery, not active platform primitives. Native fixture code is updated, but only the native groups listed above were executed. Retained check scopes are evidence; no unrelated live process or session was stopped. Other-session branding/navigation/source-reader changes are excluded from this commit.

## Committed-tree verification

Implementation commit `5713d58`. An isolated archive of that exact commit excludes concurrent working-tree edits. Its `combined-static` passed all 9 stages (6.90 s, scope `08a1d502-c406-4616-ab46-a9bdc316a99f`) and `ui-navigation` passed (21.90 s, scope `6676981b-4265-448a-ad2e-651857f9e120`). The first archive setup used a Python tarfile option unsupported by the host helper interpreter; it failed before extraction/check execution. Recreated from the trusted local Git archive after checking member paths; the checks above then completed normally.

## Exploration rebuild and coverage limit

The new operation `8a92245e-d59f-48d1-ae96-907709137e67` finished 120/120 real original calculations, zero failures, in 2303.72 s. Surrogate `3c1fff8a-90f7-4e6c-bce2-05d260f2c7b0` is ready: all 11 outputs in each of 3 combinations meet the unchanged absolute `1e-6` / relative `0.01` error targets on reserved assessment points. This is observed numerical agreement, not physical validation.

Build preparation exceeded the local client's 120-second HTTP timeout. The request identifier was retained and reconciled through read-only `get_exploration_surrogate`; the original build progressed and completed. No mutation retry, duplicate build or additional original computation was dispatched. Long synchronous build preparation remains a separate performance limitation.

Actual public-API queries moved all declared inputs together for each combination and requested nine axis-curve points: 11/11 outputs returned estimates for each selected vector, without reasons for unavailability. Original completed count remained exactly 120 before/after predictions. External `prediction-verification.json`, `joint.json`, `restored.json` and recovery manifests retain exact identities and results. The integrated live UI includes the other session's `72539a7` changes; its guarded UI-only delivery and static evidence are linked in the sibling `brand-controls/CHECKPOINT.md`.


## Final live slider correction

Final browser inspection found that the lightweight overlay optimization discarded joint input coordinates, disabling all but the active curve's slider. The UI now retains recorded sample input vectors without fetching their full histories. Every input uses those coordinates; calculated/estimated status still requires a returned result for the exact full vector. No invented output, extrapolation or numerical guard change is involved. A regression exercises multi-input coordinates, returned prediction status, units, bounds and steps. `combined-static` passed all 9 stages (6.68 s, scope `35fccb89-fe0f-47af-aa9e-eb843e3fa167`). Guarded UI-only delivery retained the previous index and left runtime identity unchanged.

Actual browser check: all 14 controls enabled; an all-input interior selection resolves to 11 estimated outputs. The unchanged convex-support guard correctly rejects some boundary selections, including moving Mach/range from the baseline's full-occupancy face. The recreated joint-only sample lacks the prior axis anchors. Therefore **full restoration of default-baseline slider coverage is not complete**, despite all numerical assessment targets passing. Do not claim that every slider combination has a result. Further preparation must include baseline/axis and decision-relevant boundary support within the bounded sample-operation size, preserve reserved checks, then reassess. No extra originals were launched after the 120-point operation; no numerical restriction was relaxed. This remains separate from the completed naming/theme/Case retirement changes.

Slider correction commit `7ea5b37` passed all 9 combined-static stages on an isolated exact-commit archive (6.95 s, scope `a838f35c-9e5c-409f-a9b1-778e07120d3f`). The live build additionally preserves the other session's uncommitted export-scope padding; that integrated build passed the earlier 9-stage check. Two independently moved controls from the supported interior selection returned 11 estimates and zero unavailable outputs; Reset inputs restored 11 calculated baseline values. The saved model-name screenshot is external (`hyprn-primitives/model-name-live.png`). No release qualification or human acceptance is claimed.
