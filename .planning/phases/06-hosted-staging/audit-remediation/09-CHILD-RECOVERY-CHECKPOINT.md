# Unprepared analysis child recovery — backend checkpoint

Source commit: `6ca2c037`. This follows the parent-only recovery in
[09-BACKEND-CHECKPOINT.md](09-BACKEND-CHECKPOINT.md). Parent owns integrated
contracts/locality verification, release packaging, deployment and live progress.
No staging or user-store writes occurred in this backend task.

## Observed failure and recovery boundary

After migration 14, the public resume reopened the original parent but its dispatcher
stopped on eight previously accepted children. Parent's read-only live evidence
(`child-preparation-proof.json`, `run-failures.json` under the external release
workspace) established the same exact false authority refusal: run receipt
`preparation_failed`, error `analysis_authority_revoked` / 403 / unchanged; operation
and outbox still `accepted_run`; operational payload `{}`; source only actor/frozen;
no prepared request, bundle or native process identity. Thus no numerical execution
had occurred for these children.

The existing public recovery read and explicit resume command now also accept that
proven prelaunch interruption, including a parent already failed/stopped on it.
Submissions owns the preflight and operational recovery. Every child must retain its
original immutable analysis link, command, actor, run identity and exact source; the
original finite authority continuity check still applies. Actual preparation or
numerical failure, prepared source, claimed/uncertain execution and true revocation
cannot be reset. Completed runs expose only the execution-state scalar during
preflight; full operational/source bytes are read only for failed preparation.

Migration 15 adds immutable `analysis_run_resumptions` audits with the full previous
receipt/error, previous operational state and source fingerprint, linked to the
explicit parent recovery command. Only the proven failure flag and operational
receipt state/error are released. Frozen outbox bytes, scientific versions, requests,
child commands, associations and run IDs remain unchanged. PostgreSQL requires exact
prior-state/source proof and a current-transaction audit before clearing the flag.
Unaudited clearing is rejected. Migration SHA-256:
`978e9d0aea295429cd3dc83838dd788a757389b5539d3ef39044706df2bfa5c4`.

No public schema or endpoint changed in this batch. The architecture import/audit
exception amendment is parent commit `e8f2d31f`.

## Verification and every failure

All commands used the configured pinned tool environment and official entry point;
checks were serialized. Logs are external at
`/private/tmp/hyprn-task09-child-<suffix>.log` with suffixes below. Each scope was
released; retained check-session evidence contains stdout, results and test records.

| Command | Suffix | Result | Seconds | Check session | Released scratch |
|---|---|---:|---:|---|---|
| `./hyprn-mvp dev check calculations-api` | `calculations-api` | 98 passed, 0 failed | 64.99 | `150e3476-afb7-4d2a-a110-6d84fd59fa28` | `ae33eadd-3c5a-4d9a-9e1f-3c7a33fbad65` |
| `./hyprn-mvp dev check hosted-postgres` | `hosted-postgres` | 53 passed, 1 failed | 51.13 | `aae4a09f-1dcc-4a0e-bd87-cbb1fd94fe33` | `0e8379f3-25bf-4c2b-b881-774298b772ed` |
| `./hyprn-mvp dev check hosted-postgres` | `hosted-postgres-diagnostic` | 54 passed, 0 failed | 86.44 | `ae3b430f-64a2-49ef-93e2-e8dab4a44cdb` | `98f32871-fcfe-4475-a8d3-86fc75e9ccc4` |
| `./hyprn-mvp dev check hosted-postgres` | `hosted-postgres-repeat` | 54 passed, 0 failed | 81.86 | `e3ba88cf-1cc4-47c4-981e-d4a65c90ea08` | `043ee7e3-ab0f-4e17-83ee-9412ab1a91a9` |
| `./hyprn-mvp dev check calculations-api` | `calculations-api-final` | 98 passed, 0 failed | 88.94 | `650741aa-5e7a-43a7-8069-ce11b2bd9322` | `c9bb0233-1fc7-41e9-aaa2-b80f4a0da8ad` |
| `./hyprn-mvp dev check hosted-postgres` | `hosted-postgres-final` | 56 passed, 0 failed | 90.37 | `ba47428c-bfe0-43e9-817e-433f2e664529` | `2e50ee95-25f5-4d20-922c-a50bd7c3912b` |

The first PostgreSQL run failed the new public test: both concurrent resume requests
returned 500 after recoverability returned true. Production error projection hid the
underlying exception and retained stderr was empty. This failure remains unexplained;
no root cause is claimed. A test-only traceback wrapper was added. Two unchanged
production-source reruns passed, so their success is not presented as a fix.

Final verification followed the narrower completed-run projection and expansion to
three independent PostgreSQL fixtures covering stopped/revoked parents. It retains
concurrent public delegated-agent requests and traceback capture, with no production
instrumentation or timing workaround. Both final groups cover exactly the committed
source. No source changes followed them. All runs had one existing Starlette/httpx
deprecation warning, no skips; explicit-path `git diff --check` passed.

The regression first reproduces the actual prelaunch refusal through Submissions by
injecting the old false authority decision, then uses public HTTP recovery. It checks
unchanged frozen source, a single immutable audit, same run/child identity, duplicate
command replay, actual preparation/bundle validation and claim, and lookup-only
behavior after an uncertain launch. PostgreSQL repeats that journey in three fresh
bounded databases with concurrent identical resume calls and rejects raw unaudited
flag clearing. SQLite additionally denies actual preparation failure, prepared source,
uncertain/recorded work and true revocation followed by regrant. Earlier continuity,
foreign-study, membership/narrowed-grant and uncertain-child tests remain green.

## Limits and next owner

Preparation uses a valid captured fixture and real bundle validation; the native
boundary is an explicit double returning an uncertain launch, counted exactly once.
These tests establish operational recovery and no automatic redispatch, not live
numerical success. Parent must run integrated contracts/locality on `6ca2c037`, apply
migration 15 through normal deployment, and verify public recovery advances the live
children. Full qualification and human scientific acceptance remain separate open
obligations. The initial unexplained PostgreSQL 500 remains in the evidence record.
