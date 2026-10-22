# Calculations navigation delivery — 2026-10-17

Implementation commits: `d1f1a9e`, `b65c9ac` (final tested source). Overview / Models / Calculations; configurations and runs share saved model/version selection and exact-pin filtering. Models still includes its editable draft. Existing record readers, evidence controls and scientific execution paths retained. Compact input sliders change presentation only. Source-result inspection uses the displayed record's pin. Design contract: `design-system/components/Calculations.md`.

## Committed acceptance

Both commands used the installed development data root and tool cache, with `HYPRN_MVP_TEST_SCRATCH_BYTES=17179869184` (16 GiB aggregate scratch allowance; the default 10 GiB was exceeded by unrelated retained scopes). Host paths remain in the local evidence manifests:

- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9 stages, exit 0. Scope `665b0f6b-b7ed-4bb0-ac3f-9e82ae95657c`; archive `3081fc70-dcdb-442a-b255-b6ec7f4952a7`.
- `./hyprn-mvp dev check ui-navigation`: 11 tests, 0 failures/skips/flakes, exit 0. Scope `7d7bf40c-4493-4200-a1dd-bd05c010b031`; archive `21820d2d-2fff-4109-a00c-9db365e263b9`.

Navigation tests use isolated declared API doubles: version filtering, tab transitions, reload/sign-in persistence, draft without a saved version, existing ownership/dirty navigation. They do not establish native scientific execution. Final static scope retained under its scoped retention policy for deployment; browser scope released by runner. No other session's scopes removed.

Earlier failures: default tool-cache sandbox/provisioning refused (resolved by existing installed development cache); default scratch allowance refused (explicit allowance above); four TypeScript interface mistakes corrected; one reload test assumed a persisted session and was corrected to sign in. Earlier navigation run: 10/11, final 11/11. Earlier/final static stages all pass after corrections. Exact logs remain in local check archives.

## Live demo

Study `50e423fd-a709-4e21-9381-0b09022b4115`, port 54821, existing live scope `f7145c6a-9848-4541-8aa4-0acf069102fb`. Guarded UI-only asset replacement from final checked build; backend runtime fingerprint unchanged. Source/live fingerprints checked before swapping index, old hashed assets preserved for open readers. Recovery index and asset hashes: `/private/tmp/hyprn-calculations-delivery/`; local refresh script `/private/tmp/hyprn-calculations-refresh.py`. No authoring records changed or new sampling requested. Includes concurrent evidence reader commits `17ec020` and `e0138be`; evidence-owned sources untouched.

Real joint slider interaction (Mach and range together) returned 11/11 Estimated outputs with no alert; Reset inputs restored calculated originals. Sample values include speed 1865.137 m/s, fuel 353138.997 kg, mass margin 33577.682 kg. This confirms real saved surrogate prediction through the UI, not a new physical validation or full sampling qualification. Light/dark screenshots and 390 px viewport checked (no page overflow); appearance restored to System.

The answer's model version `420b8ed0-dbc6-465b-968b-3e1ca7dc0df6` shows 332 saved configuration versions (331 logical configurations); latest `b7083103` correctly has none. Initial large catalogue reads remain slow; tab/version switches reuse the loaded immutable configuration catalogue. This is not a backend performance fix. Human visual acceptance and full release qualification remain separate/deferred.

Final live index SHA-256: `2a9de1cfca14e469c502605537d935bb1b7abcc69d4728f542f65d4a3e912c00`; JS `e178bb5a5a05a5e9b77d16149beb93f26255a218e1a574963443a18d5e225766`; CSS `9cda4b9abd54ff6b4c769a0e91144332fe9a844c2f5e61fa995c4cc50c04c2d8`.

Final live follow-up: Models → Calculations retained version 420b8ed0 and loaded the correct named model / 332 configuration versions. Runs tab retained the same selector, but its real large-history request ended with `signal timed out`; live run-list completion is therefore unverified despite passing fixture filtering tests. Returned to Configurations. This batch does not fix backend listing latency. Viewport override reset. No new run or scientific write was made.

Checkpoint commit initially refused by the term hook because a host-specific path was included; removed the path and retained only portable environment-variable names and local evidence references.
