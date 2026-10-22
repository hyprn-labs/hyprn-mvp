# Calculation listing performance — 2026-10-17

Implementation: `c33a4a4`. Integration UI build includes evidence work through `e4b3667` plus that session's captured CSS delta; exact source/asset hashes are in the external delivery manifest. This is a usable local demo update, not full release qualification or human acceptance.

## Outcome

SQL scopes and paginates configurations/runs before decoding or projecting records. Full record validation remains on selected records. Additive configuration summaries contain metadata only. Calculations loads 50 summaries or 20 newest runs, with explicit Load more; Overview does not fetch hidden run history. Model/version metadata is reused across calculation tabs. Model pins, authorization, cursor scope, full detail reads, sampling and surrogate execution remain intact. No store schema migration or scientific record rewrite.

Same authenticated live study (`50e423fd-a709-4e21-9381-0b09022b4115`), same one-item requests, wall time:

| Read | Before | After |
| --- | ---: | ---: |
| Full configuration page, limit 1 | 0.540 s | 0.010 s |
| Run history, limit 1 | timed out at 40.002 s | 0.242 s |
| Study / model metadata | 0.005 / 0.005 s | 0.006 / 0.005 s |

Actual new UI page sizes, three sequential measurements: 50 summaries 0.677 / 0.717 / 0.831 s (15,813 bytes); 20 runs 9.595 / 2.044 / 1.871 s (11,178 bytes). Cold run-page latency remains material; no claim that all navigation is subsecond. Measurements are API read latency, not simulation speed or controlled CPU benchmarks. Evidence: `/private/tmp/hyprn-list-performance/{before,after,pages-after}.jsonl`; timing scripts beside them and `/private/tmp/hyprn-read-latency.py`.

Live browser: saved model version `420b8ed0` retained; 50 configuration summaries displayed; run page displayed 20, then 40 after Load more. Overview: Mach and range moved together, 11/11 outputs updated to Estimated; Reset inputs restored 11/11 Calculated. No sampling request was made. Screenshot: `/private/tmp/hyprn-list-performance/live-overview.png`.

## Focused checks

All check commands used `./hyprn-mvp dev check <group>` with existing development data/tools roots and scoped fixtures. No tests used the live store.

| Group | Result | Evidence scope / archive suffix |
| --- | --- | --- |
| api-a | 123 passed | `3db89720-9a7e-4fea-9896-ba85a7de53f7` / `db9e5074-a8b1-46f7-a8a5-5955762e20de` |
| contracts | 127 passed | `872450be-91e3-4262-94ff-546474fe6188` / `bf3ac583-6e59-4830-b289-8662f5ca1aa9` |
| locality-contracts | 164 passed | `24520799-0f5b-4b51-a03f-26e2eaa5f858` / `83b6763f-2702-452e-85cb-19a8718e79f5` |
| ui-navigation, final integration | 12 passed, 0 failed/skipped/flaky | `f233c7a4-47e9-493d-ab5c-3fefdfd808a5` / `2b9f6d2d-e5a5-4edb-aade-0263444f4310` |
| combined-static, deployed build | all 9 stages passed | `f8e6d283-4039-4d80-ba65-2558e3194c39` / `dd1a2663-9bc0-4140-b6a3-1818a8f2cba0` |

API/contract checks started before the implementation commit; their tested source is unchanged in that commit. Static/navigation/locality were also run on the integrated committed implementation. UI navigation uses an explicit API fixture; real live paging and prediction verification above covers the public running app separately. Static includes design ownership/tokens/contracts/tooling, unit checks, TypeScript and build.

Failures retained: initial red api-a 121 passed / 1 failed demonstrated a one-item page projecting two rows; corrected before green. Initial static had two TypeScript unknown-to-ReactNode errors, corrected. Broader public-api: 48 passed / 1 failed / 22 errors, scope `05b3311d-96be-4476-9ae5-b229f8dd592e`, archive `53d84c84-af3d-4685-99c8-1597ce5b95ef`: 22 setup errors from unavailable reviewed modeling source image `sha256:b6c668…`; one execution namespace test assertion outside changed paths (not independently baseline-verified). Broader suite is not green and release qualification remains deferred. Repeated static builds were necessary because concurrent evidence CSS changed and the deployment fingerprint guard refused an older build; no stale bundle was published.

## Deployment and recovery

Only the existing demo web process was replaced (old PID 23763, new PID 37727); dispatcher 23773, launcher parent 23757, modeling/gateway/surrogate containers and runtime identity retained. Five read-path source files deployed to the existing runtime checkout; before/after hashes and backups: `/private/tmp/hyprn-list-performance/web-delivery.json` and `backup/`. No complete-backend-at-HEAD claim: only listed files were replaced. Startup initially refused a mismatched scratch-root setting without writing; corrected using the configured root. Stopped old web became a zombie while its parent waited for the dispatcher; port ownership and process state reconciled before starting replacement, without duplicate workers.

UI atomically refreshed after assets copied; original index retained. Manifest `/private/tmp/hyprn-list-performance/ui-delivery/delivery.json`; index SHA256 `fd18c15b52a26d0ceefc120fa5fa4e648dda9ff2f8a7f3ada47b09d7d7a12c75`. Runtime hash unchanged. Check runner archived/released ordinary scopes; final checked UI build scope intentionally retained for delivery evidence. External temporary timing/manifests contain local identities and stay outside the repository. Concurrent evidence/store/research edits were preserved.

## Memory findings and remaining work

Diagnostic snapshot: 16 GiB RAM, about 24 GiB swap and active swapping. Chrome/Codex process families had roughly 2.2/2.7 GiB resident respectively; RSS excludes compressed/swapped pages and is not a full attribution. Three live containers total about 460 MiB and are required. Node/CUA processes may belong to other sessions. Mockup server on 54932 is still in use and tiny; two other small servers have unverified ownership. No substantial process is proven both unused and safe to stop. Nothing unrelated was terminated. Temporary checks exited normally. Final memory_pressure reported 33% free; a sandboxed final swap read was denied, so no updated swap figure is claimed.

Next: human demo acceptance. If cold run-page latency persists, profile its selected-record validation/I/O separately; retain scientific integrity checks. Full API environment repair and release qualification remain separate obligations. Closing confirmed-unused browser tabs may help RAM; do not kill session processes by age or low CPU alone.
