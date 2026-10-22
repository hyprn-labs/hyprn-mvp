# A1 — durable finite analysis admission

Status: implementation delivered for parent integration; A2/A3, native acceptance,
qualification, human acceptance and deployment remain separate obligations.

## Implementation

One receipt pins the saved version, selected/reused runs, actor, original delegation,
member commands and estimate tolerances. Missing runs are admitted by the existing
submission owner, at most ten per pass and within its actor queue cap. Stable member
commands recover interrupted acknowledgements. Each admission persists progress;
receipt merges preserve already accepted identities under stale concurrent passes.
Busy admission, unavailable admission, invalid attestation, preparation failure and
uncertain execution remain distinct. Uncertain runs block further unsafe admission.
Cancellation commits the analysis receipt and stops new commands without deleting runs.

Accepted authority survives reasoning credential expiry, but checks current study
write permission and original delegation revocation. Store command guards permit only
frozen member/estimate commands. Immutable child identities retain existing owner
attribution and allow the run owner to reconcile accepted work. Batch dispatch groups
by actor and parent authority. Reused pending runs of the same actor retain identity.
Legacy pending receipts do not receive retroactive authority.

Migration 0012 adds explicit scoped RLS policies and child mapping. The ordinary
`hyprn_member` expiry predicate is unchanged. Scoped immutable dependency reads stay
within the current study; configuration reads include exact upstream dependencies.
There is no scoped authoring/session/membership write policy. The original authority
request and accepted child mapping cannot change. Tests exercise expired ordinary SQL,
foreign actors, arbitrary commands/authoring writes, immutable authority, reused runs,
child preparation, and revocation against real PostgreSQL roles.

The agent launch tool uses public finite-plan admission directly. Sampling guidance
states the 128-point capacity, independent validation and refinement rules; oversize
requests report their total and stop before sending a design.

## Delivery identity

Code commit: `f410dbd2ce7746fececb74dfdce1bcca8f3d316a`.
Migration 0012 SHA-256: `46b1f243a71f8b945026627bfb86ce397602f4628813ea1b2759d728cdfeb5bc`.
Focused checks ran on identical A1 source content plus concurrent parent integration
changes in the shared working tree; they are not a clean-release qualification.
Parent integration supplies public routes, regenerated schemas/UI and playbook updates.
Only the dispatch_batch hunk of execution.py belongs to this commit; concurrent
monetary-schema changes were preserved unstaged.

## Acceptance evidence

All checks use `./hyprn-mvp dev check <group>` with the existing pinned development
runtime and scoped stores. Host-specific environment values remain outside Git.
PostgreSQL used the existing reviewed fixture image and an explicit 20 GiB shared
build-cache budget; no shared image was deleted.

- calculations-api: 78 passed, 0 failed, 1 upstream deprecation warning; 62.85 s.
  Log: `/private/tmp/hyprn-a1-accept-calculations-api.log`.
- agent-tools: 324 passed, 0 failed, 1 upstream deprecation warning; 55.55 s.
  Log: `/private/tmp/hyprn-a1-accept-agent-tools.log`.
- hosted-postgres: 45 passed, 0 failed, 1 upstream deprecation warning; 39.86 s.
  Log: `/private/tmp/hyprn-a1-accept-hosted-stable.log`.
- `git diff --check` on owned implementation/tests: passed.

The API/tool checks prove durable admission and recovery using synthetic model/native
fixtures. PostgreSQL proves actual role/RLS behavior and operational discovery, not
restricted-worker numerical throughput or scientific validity. Parent must rerun
acceptance on the integrated committed tree before dependent task dispatch.

## Failures and recovery

The inherited RED evidence was reused rather than rerun (`hyprn-a1-red.log`, parent
reported 315 passed/6 failed; its focused follow-up had 315 passed/8 failed).
Initial pinned-check invocation was sandbox-refused by the existing uv cache; approved
execution used the same pinned runtime. A nonqualification system-Python syntax attempt
was refused by its bytecode-cache location; no evidence was claimed from it.

During implementation: calculations-api 70 passed/6 failed because the parent route
still validated schema 1; fixed by the versioned public integration. Agent-tools
323 passed/1 failed exposed a missing Store.command guard; fixed and rerun green.
Hosted runs: 43 passed/2 failed exposed B fixture transaction/terminal-state issues;
43 passed/2 failed then exposed pre-group batch bounds and leaked synthetic queue
receipts; corrected with actor/parent grouping and exact fixture-scope cleanup.
A default-cache preflight refused the existing shared cache without deleting layers.
A later 41 passed/4 failed run was invalidated by concurrent migration-registration
edits; a frozen-migration rerun supplies final evidence.

Extra locality-contracts check: 158 passed/7 failed (12.10 s), all parent monetary/schema
inventory and api/explanations layer-table deltas; see `/private/tmp/hyprn-a1-boundaries.log`.
Parent owns resolution and final qualification; these failures are not treated as passes.

## Cleanup and remaining obligations

Check-owned application scratch roots are released by the runner. PostgreSQL fixture
teardown is fenced by its unique ownership label; shared images/cache are retained.
External check logs and compact runner evidence remain available. No installation,
authoring record, staging service or production data was changed.

Parent retains A2 readiness/backoff, A3 >60-point completion/fairness/session-close and
budget coverage, integrated native agent-to-application acceptance, complete contract/UI
checks, final qualification and genuine human acceptance. No phase/release is declared
complete by this checkpoint.
