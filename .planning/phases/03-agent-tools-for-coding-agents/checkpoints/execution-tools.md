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

Live demo refresh and the fresh coolant study verification follow this implementation
checkpoint. Preserve the unrelated ROADMAP change and unrelated research outputs.
