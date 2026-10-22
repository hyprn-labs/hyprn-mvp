# C1 — incremental Assistant progress and durable analysis waiting

Status: C1 implementation complete; integrated qualification and C2/C3 remain with
the orchestrator. No provider resource or live installation was mutated.

## Owned delivery

- RED: `3c7aae53` — public identity disclosure, pagination, retained provider
  cursor and large private-history regressions.
- GREEN: `0664cd0d7529c33d61fe3d949573da0ff8bf5648` — `assistant/records.py`,
  `assistant/conversation.py`, `test_assistant_conversation.py`.
- Ledger base: `7e6cac3408a242c17a718f1ce3ee3c521f615232`; measured source/test
  commits through GREEN: 2. Shared tree, no worktree or branch changes.

Raw retained events are preserved. Accepted insertions derive indexed event
metadata and one safe public transcript exactly once. Provider cursor progress is
durable; subsequent polls, message/result reconciliation, failure lookup, turn
timing and Stop no longer rebuild the retained event history. Public Assistant
identities are deterministic scoped application UUIDs, not provider identifiers.
Frozen public attribution is never rebuilt from later alias or legacy-record edits.

Public reads authorize before cursor lookup. First page returns the latest 200
messages in ascending order; `after` returns up to 200 subsequent messages;
`before` returns up to 200 preceding messages. Both at once and unknown/cross-study
cursors fail with `invalid_request`. Additive fields are `next_cursor`,
`earlier_cursor` and `has_more_messages`; `has_earlier_messages` is retained.

An unfinished `get_analysis_execution` result is retained with delivery `waiting`.
The application owner reads its exact study/version with adaptive 1–30 second
waiting, without reinvoking the tool or requesting LLM inference. Restart restores
the wait. Explicit delegation revocation, current membership, Stop and cumulative
allowance remain fences. Terminal completion or required review rechecks those
fences, starts a fresh bounded reasoning lease and delivers the original tool
result identity. The shared USD 20/user account is neither reset nor renewed.
This monitoring path does not resubmit or cancel scientific work.

## Parent integration interfaces

- Constructor: `Conversations(..., analysis_reader=AnalysisExecution(store).read)`.
  The callback is injected from the normal API owner; no new module-boundary edge.
- Parent owns `AssistantConversationRead4`, route `after`/`before`, generated
  contracts and UI. Local public call remains usable without cursor arguments.
- Parent owns migration `0011_assistant_projection.sql`: one public-message table,
  conversation provider cursor, event type/time/reference metadata and indexes.
  Legacy projection backfill is ordered, deterministic and leaves raw payloads,
  provider IDs and event positions intact. PostgreSQL policy/backfill qualification
  belongs to integrated acceptance; SQLite initialization is implemented here.
- C3 should instruct launch then monitor with `get_analysis_execution`; the
  Assistant owner now waits for completion without repeated inference polling.
- C2 reviewer tool restrictions remain a separate task; child messages stay private.

## Verification and every observed failure

All checks used `./hyprn-mvp dev check assistant-bridge`, the pinned local edition
entry point, configured external development/tool roots, and scoped scratch stores.
Development host paths and private audit contents are not copied here. Logs are
retained externally under the `hyprn-c1-*.log` names listed below.

| Run | Result | Scope / evidence |
|---|---|---|
| Initial sandbox invocation | Exit 5 before test collection: configured uv cache inaccessible; escalated invocation used the same approved cache | `hyprn-c1-red.log` initial error was superseded by successful runner invocation |
| RED full group | 151 passed, 2 intended failures, exit 1; 14.82 s | `e2406b65-1d16-4dab-94a9-d128aa798db0`, `hyprn-c1-red.log` |
| Reporter retry using root config | 151 passed, same 2 intended failures, exit 1; 15.14 s. Root config was ignored by the application project root | `5f42bb6d-37f5-491e-8584-469dfa5482c5`, `hyprn-c1-red-junit.log` |
| Focused reporter attempt during parent edit | 2 collection errors, exit 1: new monetary fields lacked registry string bounds. Parent corrected those fields | `1994fa37-6585-477d-a1f5-4ec343513976`; not RED evidence |
| Valid focused RED | 1 intended failure, 154 deselected, exit 1; 1.35 s. Temporary `application/pytest.ini` selected the identity-disclosure assertion and emitted JUnit, then was removed | `a34638f6-3668-4672-bec5-0594930e93ae`, `hyprn-c1-red-target.log`, `C1-RED.json` |
| First GREEN | 157 passed, 2 failed, exit 1; 17.71 s. New test counter included unrelated registry JSON and revocation fixture lacked required reason; both test fixtures corrected | `fd26efba-2eb3-4a54-8c83-3f1b72891c2a`, `hyprn-c1-green.log` |
| GREEN | 159 passed, 0 failed, exit 0; 19.21 s | `5310987e-f3c4-460f-9787-698a8375f78a`, `hyprn-c1-green-2.log` |
| Final source acceptance | 159 passed, 0 failed, exit 0; 17.02 s. Includes Stop cursor and measured-query assertions; exact owned source committed as `0664cd0d` | `d12de897-03de-4471-a7a2-767df9065cb9`, `hyprn-c1-final.log` |

`gsd-tools check tdd-red-evidence C1-RED.json --raw` returned
`RED_EVIDENCE_OK`. The named test executed and failed on raw provider identity
disclosure, not fixture setup. No implementation began before this validated RED.
All temporary reporter configuration was removed. `git diff --check` passed on
owned paths. The final scratch scope no longer exists, confirming its release.
No new dependency, stub, skipped test, generated runtime file, live data change,
or accidental tracked-file deletion was introduced.

## Measurements and practical limits

The synthetic conversation retains 300 private reviewer messages, each containing
32 KiB text: more than 9.8 MB of raw event payload. A public read decodes **zero
raw-event JSON bytes**, performs **at most 12 SQL statements**, and does not query
`assistant_events`. Overlapping provider pages produce no duplicate public
messages; the next provider read uses the stored timestamp and cursor paging is
study-bound. These are local SQLite regression bounds, not hosted PostgreSQL
query-plan or Cloud SQL traffic measurements.

Durable wait tests use the real Assistant owner/delegation records with an injected
deterministic analysis-reader callback. They prove restart, expiry, single original
result delivery, Stop, revocation and membership fences, not native 126-point
execution or live provider behavior. Parent must rerun committed-tree acceptance,
qualify PostgreSQL migration/RLS, and exercise the complete scientific lifecycle.
Automated evidence is not human acceptance or deployment.

## Self-check: PASSED

Owned implementation/test files and this checkpoint exist. RED and GREEN commits
are ancestors of current HEAD. No full-plan SUMMARY or global STATE advancement
is claimed: this executor was assigned C1 only; C2/C3 and integrated acceptance
remain open under the parent plan.
