# Automatic prediction renewal — 2026-10-16

## Outcome and scope

Implementation `f076a56`; runtime-only deployment `55eb0cd`. Moving inputs now reloads the exact saved numerical surrogate when its temporary prediction process is absent, stopped or expired, then retries prediction once. The UI shows running “Updating…” values/curves and a shared “Updating predictions…” status while awaiting the selected vector. No prior selection is presented as a new result. Existing calculated values matching the selection remain available.

Renewal checks the saved group identity, artifact SHA256, computation runtime and current study access. Revocation and supersession are checked again before the renewed prediction. Loading only reconstructs serialized numerical state; it never fits, samples or executes candidate code. Worker lifetime/request/resource bounds remain unchanged. Query admission allows 40 seconds total for bounded loading; warm prediction execution remains bounded to two seconds. The UI transport allows 45 seconds. Persistent failure ends after one renewal attempt and remains visible; there is no retry loop or coverage extrapolation.

## Verification

All checks ran through `./hyprn-mvp dev check` with the approved host environment and isolated scratch scopes:
- `exploration-api`: 63 passed, 59.75 s. New public-boundary cases cover cold renewal, persistent failure, corrupted saved state, access revocation during loading and supersession during loading. First run: 62 passed / 1 failed because the test transport returned one output for a multi-output fixture; corrected the fixture inventory and reran successfully.
- `exploration-numerics`: 1 passed, 74.82 s, including existing numerical checks and a real restricted-child expiry/reload assertion. Exact prediction values survive renewal; numerical model building occurs only before the renewal test. Source bytes match the committed implementation.
- `combined-static`: all 9 stages passed, then all 9 passed on a clean `f076a56` archive (9.31 s) excluding concurrent UI edits. Includes contracts, design, token/ownership checks, component loading-state assertions, TypeScript and production build.
- Live demo containment attestation refreshed successfully. The numerical image remains `sha256:27e8d91e40f6772cdd287b8eeb44514d642b14d6417e4c4d31120d36a32688d3`, preserving saved surrogate runtime pins; no surrogate rebuild.
- Real browser: cold service startup prepares predictions automatically. After changing Mach and heating value, all 11 outputs are estimated. Stopped only the owner-labelled temporary prediction container, then moved range: the rendered UI showed “Updating predictions…” and running output states, followed by all 11 estimates. No Settings/manual preparation action. New container identity confirmed with the same numerical image.
- Before/after saved counts identical: 405 original outbox entries, 77 sampling receipts, 3 surrogate builds, 3 manual-warm receipts. Automatic renewal creates none of these. Live UI index matches the committed clean build, SHA256 `524b0a04c2600323155283fafd6035e3ad22d8cab52c7a784d86fbcee084f71b`.

External host evidence in the task's `hyprn-renewal` scratch folder: API/numerical logs, `static-committed.log`, `deployment-proof.json`, `loading-state.txt`, `browser-proof.json`, `recovery-proof.json`, `restored.png`. Browser timing is an observation upper bound including tool round trips, not a latency benchmark. Test scopes released by the runner. Runtime recovery files and live demo intentionally retained.

## Deployment and remaining limits

The full cherry-pick into the old dedicated runtime checkout conflicted with its UI history; aborted cleanly, then applied only the two runtime source files. UI is separately built from the clean application commit. All other session changes, index entries, ROADMAP and research files were preserved. Initial git staging required the configured sandbox escalation, which succeeded.

This supersedes the manual-renewal limitation in the joint-preparation checkpoint. Genuine unsupported combinations still have no estimate. Capacity, authorization, runtime mismatch and persistent infrastructure failures remain honest errors. No full qualification or human acceptance claim; task 3.V6 remains excluded by user instruction.
