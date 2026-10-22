# Cold run-page read and Calculations layout — 2026-10-17

Implementation `2c175e8`; integrated UI includes concurrent assistant work `f325eb4` and its captured CSS delta. Existing local demo, usable update; full release qualification and human acceptance remain separate.

## Change and evidence

Profiling the existing read-only 20-run query separated SQL (0.165 s) from repeated full configuration admission (7.387 s under cProfile). The latter visited the same model/closure schemas repeatedly across distinct sampled configurations. A request-local, bounded successful-reference cache now keys the schema namespace, reference and exact JSON bytes (including numeric types). It never caches failures or trusts IDs/digests as a substitute for bytes. Every row still receives complete schema and scientific semantic admission. Historical wrappers use their existing admission path; full run/detail validation and all execution/sampling/prediction code are unchanged. No database schema changes, dependency additions or scientific record writes.

The focused profile fell to 2.329 s for context validation under cProfile. Those instrumented figures are diagnostic, not user-perceived latency. Actual first-page HTTP measurements below are the delivery evidence.

Same study `50e423fd-a709-4e21-9381-0b09022b4115`, exact model version `420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`, request for 20 newest runs; authenticated, same 11,178-byte response size:

| Condition | Before | After |
| --- | ---: | ---: |
| First run-page request after restarting only web process | 2.899 s | 1.276 s |
| Following two requests during concurrent activity | 0.407 / 0.445 s | 1.618 / 0.659 s |
| Repeated reads after focused checks exited | — | 0.496 / 0.478 / 0.428 s |

The original 9.595-second observation did not recur in this session. The first-process comparison is 56% faster; these are local-host observations with concurrent work, not a guarantee under arbitrary RAM pressure. OS disk caches were not flushed, so “cold” here means fresh web process, not forced cold filesystem. Logs/scripts: `/private/tmp/hyprn-cold-read/{fresh-before,fresh-after,quiet-after}.jsonl`, `timing.py`, `profile-{before,after}.txt`, `profile_read.py`. Earlier warm baseline is `/private/tmp/hyprn-list-performance/cold-before.jsonl`.

The shared CalculationNavigation component owns visible Model / Model version labels and spacing below tabs. CollectionToolbar owns the count/action row inside the list panel. The duplicate Configurations heading is removed. No screen-level layout overrides. Desktop live toolbar begins 41 px below the tab separator; the automated geometry check covers 1280 and 390 px widths. Screenshot: `/private/tmp/hyprn-cold-read/calculations-desktop.png`; temporary live viewport reset afterwards.

Live Overview verification moved Mach and range together: all 11 outputs became Estimated with the same values as the prior verification; Reset inputs restored all 11 Calculated values. No sampling was requested. All existing workers, dispatcher, modeling service and surrogate service stayed running.

## Focused checks

Commands used `./hyprn-mvp dev check <group>` with the configured development roots and isolated fixture scopes. No project tests accessed the live store; profiling was explicitly read-only diagnostics and live verification used the public API/UI.

- `approach-configuration`: 62 passed on committed implementation, scope `3bbcce61-194c-45f1-9054-cd9a346cb5ef`, archive `280ef373-8f31-4b43-a6d9-0531b6ef5be1`. Regression verifies shared-model validation is reused for distinct configurations, and modified schemas, extra fields, model/source bytes, closure content, pins, digests, numeric types and foreign-study requests remain unavailable exactly as with full admission.
- `ui-navigation`: 12 passed, 0 failed/skipped/flaky, scope `2d34a3d0-0bf6-45ea-8c01-e72a17c06133`, archive `e24b31eb-6d77-4046-94c0-57dc83b2e96c`. Explicit fixture API; live verification above is separate.
- `combined-static --keep-scope`: all 9 stages passed, deployed build scope `0ed1e7a6-6937-4c2c-900d-35add48a6726`, archive `2174b8c4-0461-4f97-b784-cbcc5f7bdb17`. Includes design/token/ownership/UI contract checks, design tests, TypeScript and build. Earlier static pass scope `7c3e4847-4085-471c-9b89-52c0c24f27c0` preceded concurrent UI changes; rebuilt to capture those.
- `git diff --check HEAD`: pass. No debug instrumentation retained.

Failures during regression authoring: initial total-reference-count assertion was too broad (43 versus 43 because a changed configuration adds its own checks); replaced by the exact shared-model reference count. Failed twice in scopes `ed20fa86-d753-473b-976c-91aa7d8b9565` and `b59f9e38-3366-496e-9437-c9f5f2951602`. Two subsequent tests assumed populated source/input arrays in a deliberately empty fixture, raising IndexError (`1171c618-557a-42c6-97a7-a30d2d9c7389`, `eea300d5-b0ed-42e2-a06c-82c3a39c84ff`); corrected to append a corrupt source and mutate the populated version number. Each run was 61 passed / 1 failed; then 62 passed (`fd0e87bf-a382-4d08-a1f9-2b6ec1bd40da`) and the final committed pass above. First UI navigation run was 11 passed / 1 failed on the other session's renamed assistant button (scope `8213e7a8-c81f-4ab9-88f7-54d2b979bf5e`); that session updated its test and final integration passed. The Calculations geometry case passed throughout.

## Deployment and recovery

Only history.py was replaced in the identified live runtime checkout; web PID 45086 replaced 44053 after the before comparison. Exact before/after source hashes, runtime-unchanged assertion, backup and script: `/private/tmp/hyprn-cold-read/web-delivery.json`, `backup/`, `deploy_web.py`. Deployment source at integrated HEAD `f325eb4` matches history.py from `2c175e8`; no claim that unrelated backend source was deployed. The prior code was also restarted once for the matched baseline. No execution/attestation files changed.

UI refresh compared source and live-index fingerprints, copied hashed assets before atomically replacing index, and preserved the other session's changes. Manifest, captured source fingerprints and previous index: `/private/tmp/hyprn-cold-read/ui-delivery/`. Ordinary test scopes were archived/released by the runner; final UI build scope retained as delivery evidence. Only owned hunks were committed in shared design files/tests; unrelated edits and index state were preserved.

Remaining: human acceptance; general memory contention can still affect reads. No substantial unrelated process was stopped. Broader API environment/release obligations from the preceding checkpoint are unchanged and were not repeated for this read-only optimization.
