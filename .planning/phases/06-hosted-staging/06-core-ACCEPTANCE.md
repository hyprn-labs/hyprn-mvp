# Core PostgreSQL and embedded-only agent boundary

Tested source: `2f9c629`. Date: 2026-10-20.
The parent reviewed the executor changes and ran the combined acceptance after
the atomic source commit. No application source changed during these checks.

Each command was `./hyprn-mvp dev check GROUP`, with the existing nonsecret
development environment loaded. Checks used isolated fixtures, not live stores.

| Group | Passed | Test seconds |
|---|---:|---:|
| hosted-postgres | 10 | 6.97 |
| access-control | 11 | 3.80 |
| public-api | 83 | 93.12 |
| agent-tools | 321 | 51.25 |
| assistant-bridge | 138 | 24.51 |
| contracts | 127 | 9.72 |
| locality-contracts | 165 | 12.12 |

All seven commands exited 0: 855 tests passed. Existing warnings are retained
in `/private/tmp/hyprn-integrated-core-GROUP.log`; each log identifies its
registered scratch evidence folder. No second identical run is needed before
the full-domain task starts.

The first commit attempt was rejected by the naming hook because the inherited
plan embedded a machine-specific home path. It was replaced with `$HOME` before
the successful commit. No hook was bypassed. Later changes to these acceptance
records are documentation only.

The task's test-first process was not followed by its executor; the checkpoint
states that deviation. The parent accepts the implementation on the actual
public-boundary and negative tests above, not as evidence of a test-first
development sequence. Subsequent new behavior retains the prescribed test-first
requirement.

## What this establishes

The core study API can use an explicitly initialized PostgreSQL database with
scoped request authority, separate authentication lookup, cross-user isolation
and membership revocation. External token/operator surfaces are removed while
the embedded Assistant's tool catalogue, delegation and local bridge tests pass.

## What remains

Full scientific-domain persistence and background authority (06-02), verified
cloud identity/session integration (06-03), release lifecycle, deployment
automation and actual hosted acceptance remain required. The fixture disables
TLS only for its isolated loopback database; it does not establish Cloud SQL
certificate behavior. The embedded tests do not establish live provider delivery.
No current data was reset, no cloud resources changed, and no new demo deployed.
