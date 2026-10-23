# Analysis execution recovery — backend checkpoint

Owner: backend executor. Source commit: `6e997ee1`. Parent owns the agent/UI
integration, architecture amendment, integrated checks and deployment. No live
study, run, model, configuration, membership or credential was modified here.

## Delivered behavior

- Accepted finite work survives repeated normal credential replacement and expiry.
  Every retained grant from the pinned grant onward must retain writer/submit
  authority; a true revocation or narrower grant permanently blocks continuation.
  SQLite and PostgreSQL also persist membership downgrade/removal and delegation
  interruption barriers, so a later regrant cannot revive accepted authority.
- PostgreSQL migration 14 checksummed in the normal migration ledger. Legacy
  analyses with a later successful membership command are conservatively blocked:
  the old membership receipt does not identify the changed member/role and cannot
  establish continuous authority. Migration does not rewrite frozen requests.
- Additive public GET `/studies/{study_id}/analysis-versions/{version_id}/execution/recovery`
  returns `AnalysisExecutionRecovery1` (`can_resume`, `reason`). POST sibling
  `/resume` accepts `AnalysisResume1` (`command_id`) and returns `AnalysisExecution2`.
  Compatibility calculation paths remain available. No existing schema changes.
- Resume requires current writer/submit authority, the original actor or its
  delegating engineer, a failed/revoked operational projection and proven original
  authority. A separate `analysis_resume` receipt and immutable recovery audit
  retain the prior outcome. PostgreSQL rejects unaudited terminal reopening.
  Ordinary launch replay does not initiate recovery. Frozen requests, child
  command ids, member/run pins and scientific versions remain unchanged.
- Before new admission, the dispatcher reconciles every immutable accepted-child
  link, including a child committed before a crash prevented its parent projection
  update. An uncertain child anywhere in the plan prevents new admission.
- Forbidden/missing-resource failures no longer claim explicit authority revocation.

## Verification and failures

All check groups used `./hyprn-mvp dev check` with the existing configured pinned
local tool environment; isolated scratch stores only. Native numerical execution
was not needed for these authorization, receipt and HTTP persistence changes.

1. `./hyprn-mvp dev check calculations-api`: **90 passed**, 0 failed, 58.31 s;
   session `198fef43-6e66-45aa-a8ec-bd3ed04f4d46`; scratch
   `6c4adf44-4a0a-44b2-a911-cc905007cf06` released. Superseded by the final run
   after adding the unprojected uncertain-child preflight and permanent barriers.
2. First `./hyprn-mvp dev check hosted-postgres`: **48 passed, 4 failed**, 51.31 s;
   session `8a3cfebe-594b-45a5-a144-3e57dca300cc`; scratch
   `25efffcd-83d0-484b-a240-73ace58ef4aa` released. The new test incorrectly reused
   the module fixture's human/agent; earlier pending runs consumed its actor quota.
   Fixed by giving each new scenario an isolated human and delegated agent.
3. Final `./hyprn-mvp dev check calculations-api`: **91 passed**, 0 failed, 64.23 s;
   session `3228fcf1-b7ca-42cd-90b1-5061370ac5ce`; scratch
   `edb05b50-4c63-4382-8ed2-46d60f731edd` released. Covers real public recovery,
   concurrent identical resume, fresh-command refusal after resume, unchanged pins,
   explicit revoke/narrowed grant/membership downgrade followed by regrant,
   foreign-study privacy, uncertain unprojected children and precise diagnostics.
4. Second `./hyprn-mvp dev check hosted-postgres`: **50 passed, 3 failed**, 45.69 s;
   session `c3f9a87f-afc9-48b2-bfd9-79693e7c0f42`; scratch
   `afbf471f-7d53-4920-a5c6-30fee6da04e6` released. PostgreSQL exhausted its existing
   256 MiB fixture tmpfs while four new cases each retained 12 full frozen member
   payloads. Positive concurrent recovery and explicit revocation already passed.
   Reduced PostgreSQL cases to two members; the SQLite capacity scenario remains
   12 members. No fixture resource limit or application behavior was weakened.
5. Final `./hyprn-mvp dev check hosted-postgres`: **53 passed**, 0 failed, 45.92 s;
   session `4cb2cb5f-86da-4a66-b0c2-04a8063c91aa`; scratch
   `4becf0b5-4a69-4274-b9d1-48601359a1a2` released. Includes migration checks,
   actual delegated-agent HTTP concurrent resume, immutable-request and pending-run
   reuse, unauthorized raw terminal-receipt update refusal, true authority-loss
   persistence, foreign reads and uncertain-child reconciliation.

The final two passing groups cover source committed as `6e997ee1`. Only PostgreSQL
fixture sizing/session coverage changed after the final calculation API run; the
final PostgreSQL run exercised that exact delta. Existing Starlette/httpx deprecation
warning remained (one warning per group); no tests skipped.

OpenAPI generation first attempted a native environment lacking FastAPI and failed
before writing output. Regenerated successfully with the existing locked contract
Python, followed by `python3 ui/generate_types.py`. A parsed old/new comparison
confirmed exactly four additive paths (two canonical, two compatibility) and two
additive schemas; no existing path/schema changed. Explicit-path `git diff --check`
passed. Generated-file ordering accounts for the larger textual OpenAPI diff.

Logs outside the repository:
- `/private/tmp/hyprn-task09-calculations-api.log`
- `/private/tmp/hyprn-task09-calculations-api-final.log`
- `/private/tmp/hyprn-task09-hosted-postgres.log`
- `/private/tmp/hyprn-task09-hosted-postgres-final.log`
- `/private/tmp/hyprn-task09-hosted-postgres-green.log`

## Remaining obligations

Parent: integrated contract/UI checks, source packaging and normal staged migration /
deployment, then public live recovery and progress verification. Full qualification
and human scientific acceptance remain open. These synthetic frozen models establish
public authorization, idempotency, containment of admission and retained identity;
they do not establish numerical or scientific success of the live study.
