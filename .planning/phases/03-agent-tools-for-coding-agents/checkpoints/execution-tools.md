# Execution budgets and named owner tools

Local-demo batch authorized 2026-10-15. Implements the adjacent execution-tools
plan and existing owner-session amendment; delegated writer/MCP enablement and full
release qualification remain deferred.

## Implementation and focused verification

- Public submissions freeze an explicit 1–3600 second wall budget (300-second API
  and tool default). Command replay binds it; the native process stores an Int
  input, launcher enforces it, and the outer job allowance adds 60 seconds.
- Curated public run diagnostics read authenticated retained launcher bytes. Timeout,
  memory/output limits, normal exit and unavailable diagnostics stay distinct from
  numerical results and criteria. UI displays the timeout without fabricating values.
- Native computational exports verify the budget input, launcher envelope, command
  arguments and scheduler settings. Old recorded shapes remain readable.
- Named local JSON-lines study tools use the ordinary authorized public API. They
  normalize envelopes, verify downloaded artifact hashes, expose operation schemas,
  and supply model create/edit request formats. No retries, scheduler, candidate
  execution, delegated authority or second model graph is added.
- Capability discovery distinguishes model request formats from saved scientific
  versions. Wrong creation format identifies /schema_version with actionable text.
- Installed /hyprn is a symlink to the updated repository skill. It now uses named
  tools, explicit budgets, terminal diagnostics and deliberate recovery.

All commands below use `./hyprn-mvp dev check <group>` and isolated scopes. Logs and
artifacts are retained in the task scratch folder `hyprn-execution-tools`.

| Group | Result |
| --- | --- |
| units-api | 94 passed; budget bounds/default/replay and model format diagnostics |
| local-api-client | 15 passed; named operations, receipt category and binary artifacts |
| units-bundle | 121 passed |
| locality-contracts | 161 passed |
| units-guards | 138 passed |
| style-ratchet | 33 passed |
| combined-static | all 9 stages passed, including generated types and UI build |
| units-engineering | 1 passed; actual >20 s calculation under 60 s budget, 1 s timeout, native budget input, export and restart |

Native proof scope: b304b393-3b8d-4b63-b0cb-185f2a88b9db. Containment is rebuilt
and attested through the ordinary fixture; no runtime-policy bypass.

Recovered failures: sandbox refused initial tool-cache write; authorized scoped
checks ran normally. Three native journey attempts exposed the old archive-envelope
key whitelist and the scheduler quote flags (two flags describe executable/arguments,
not one per argument); corrected exact validation, then the full journey passed.
API numerical/timeout checks passed in those attempts; export did not. Style checks
caught new long lines. Registry checks caught the new untracked test plus stale
expectations for the already existing approach-ui-demo group; corrected and reran.
No failed invocation is represented as passed.

## Committed acceptance and live delivery

Implementation commit: `b782241`. On that commit, units-api passes 94 tests,
local-api-client passes 15, and combined-static passes all nine stages. The native
proof above used identical implementation bytes before the commit. This checkpoint
and the current-state update are the only subsequent delivery changes.

The existing demo was quiesced after public-API checks found no pending runs. Its
unchanged modeling service was retained; the launcher/runtime was rebuilt and
attested, then the app, dispatcher and built UI were restarted on the same local
address. A recovery snapshot and refresh logs remain in task scratch. Runtime digest:
`973795b9493ec89a23f63067b2d35bf2386b57d3c217448c690222973924b8aa`;
attestation digest:
`122535d66b9e8361899c9303c2e8ab0df8f4effddd2d824e1b21581fc175a0d1`.
The live demo scope f7145c6a-9848-4541-8aa4-0acf069102fb remains running deliberately.
Test scopes are isolated and released by their runners; evidence remains retained.

Fresh study: `cba1e324-06b9-4e7f-b716-37ac6ea2fba4`, “Coolant loop — verified
agent-tool study”. Named owner tools authored the model, evidence, approach,
configurations, runs and answers. Model creation and editing succeeded without
caller-selected request schema versions. All four configurations pin exact saved
model version `8b024f77-cf00-46f9-b95f-0ad1e774e053`.

| Case | Run | Rise / outcome |
| --- | --- | --- |
| Nominal | 33a3ec5e-4913-4e21-8648-ea6601a80d07 | 9.52381 K; requirement met |
| Zero load | c41f2194-8789-4658-9489-45b4a52798ee | 0 K; check passed |
| Joint adverse | 6ad9317e-4766-45ae-9442-a6930f136dd8 | 15.78947 K; requirement not met |
| Doubled flow | 8de6771c-8230-4927-b9b1-757e72217b30 | 4.76190 K; check passed |

All four executions completed normally with retained 300-second budgets. Launcher
elapsed times were 8.01, 7.67, 7.70 and 9.57 seconds, including startup/stopping.
Numerical targets, explicit engineering-unit conversions and finite outputs pass.
Three case answers and synthesis `dfe083da-111a-4b66-a562-a0dfef8c5a4c` were saved;
public readback verifies answer content, evidence, configurations and unchanged
question. The answer distinguishes a conditional thermal screen from design
qualification. Scratch `coolant/summary.json`, transcript and state retain full pins.

First API request through final readback: 365.45 seconds, including recovery of a
scratch orchestration variable-name collision after authoring. Recovery resumed the
same persisted study, without duplicate submissions. This timing excludes earlier
application implementation, deployment and preparation of the authoring script.

The existing browser session displayed the new study and the adverse run, including
“Completed” separately from “1 of 5 not met”. Reloading to load the new bundle
required sign-in, so the new timeout UI was not visually verified in that session.
Its build/contracts pass, and timeout behavior is verified through the public API
and real restricted worker. Human UI acceptance and full release qualification
remain unclaimed. The study link is left open at sign-in. Unrelated ROADMAP and
research changes are preserved.
