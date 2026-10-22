# Staging performance — current delivery evidence

Current runtime `f7a33f5a8681c7683e9376827a8b3fcd9586ce4f` adds only the site-root
redirect to tested performance runtime `cc5d6a19`. Platform runtime remains
`3488a518cbae96b283d3ab88e5096215744f756d`; one-time staging downloader correction
is separately committed at platform `73cfc06`. Current release
`fd63aa0ddbdd29c7b38f7509cb191132df95dea92d9da1d1b859c2e3e0e6831a`, config
`218083f696a20f73de592d3fda46220c4a0e1b32f4c60e5edf9fb2b4890df316`, desired
sequence 14 / generation 1792650593728076. Application schema 8 is unchanged.
No initialization, migration or credential reissue in this update. Previous release
6a69cfaa and backup 1792628416356 remain retained. Ongoing restricted staging was
promoted successfully after actual browser/Assistant verification; the renewal timer
was restarted. This is usable private staging, not full release qualification.

Root causes: repeated decoding/integrity validation of roughly 295 MB of execution
archives for compact reads; repeated JSON parsing for run lists; per-transaction
connection setup. Fixes: exclusive bounded role-specific pools, fingerprint-checked
persistent read projections with full validation on invalidation, batch receipts,
and database-generated lifecycle summaries. No scientific values, accuracy limits,
source pins, worker image, sampling or surrogate fitting changes. No UI bytes changed.

Integrated checks on preceding committed performance runtime (unchanged paths): hosted-postgres 38, api-a 125,
calculations-api 73, contracts 127 pass. Locality after doc correction: 164 pass,
one existing worker allowlist failure. Existing repository guard failures remain;
full qualification is not claimed. Recovery operator 11 and activation operator 1
pass. Fresh native extraction and unchanged worker/modeling/UI inputs verified.
Runtime startup, containment and all 19 actual network probes passed.

Packets: /private/tmp/hyprn-staging-performance (initial measurements and first
release); /private/tmp/hyprn-staging-readers (reader release); /private/tmp/hyprn-staging-landing
(root correction, actual final receipts and screenshot). Continuing owner
authorization applies; no new infrastructure, permissions, credential version or
budget increase. Do not replay completed recovery steps.

## Root correction and final acceptance

Chrome reproduced the reported JSON error at `/`; `/ui/` already worked with the
same email session. A generic same-origin GET/HEAD redirect now exists only when
the workspace is mounted. Unknown API paths, host checks and API authentication
are preserved. New tests reproduced 404 before the fix and pass against both the
static boundary and real application middleware. Contracts: 127 pass. Public-api:
62 pass, 23 fixture errors because the existing reviewed modeling image is stale;
no full-group pass claimed. Recovery 9 and activation 1 checks pass. Native fresh
extraction, 54 source identities, seven worker inputs and eight UI assets verified.
Actual containment, startup and all 19 network probes passed on the installed release.

Exact amendment 8ab482201f01b566bb7bb1473ecf304d2690922dfe4f48cca55209a2e8054591;
release policy def72d519cbba18e91fc9300c0db82abbbf6434dc4c8a1bd7ab5db99901077d5;
activation plan e50f9eb755bcf17c95109f033b86919df9644b510d4408c97acfa7a7d09f1b0a.
Continuing owner authority applies. Initial staging refused a valid Google token
with 740 seconds remaining because the downloader demanded 900. Read-only
reconciliation confirmed all 54 targets missing, no partial data or app change.
Platform 73cfc06 refreshes before expiry and refuses invalid refresh/changed host
identity; 13 tests pass on the commit (two regression errors before correction).
A separately frozen continuation used that loader, retaining the original failed
receipt and the exact application/runtime artifacts. Desired publication consumed
the successful continuation receipt with the same compare-and-swap guards.

Other retained development failures: short-commit source snapshot refused, corrected
with the full identity; local assembly stopped on a missing reuse-proof file before
publication, then resumed after actual hash comparison; one read-study invocation
used an unsupported label and stopped locally before a cloud call. No uncertain
mutation was blindly repeated. Full logs and exact helper reviews are in the packet.

Final root-only release measurements: changed-reader cache preparation 27.077 s,
repeated answer 0.128 s; fresh-process prepared answer 5.353 s / repeated 0.119 s.
The fresh-process 5-second assertion FAILED; record this residual, not a passing
latency gate. No retry-to-green was performed. Three real joint queries after browser
warmup, each a selection plus a 32-point curve, took 0.371, 0.364 and 0.353 seconds.
They are warm-worker measurements, not cold starts or browser end-to-end times.
No model runs were added. The preceding detailed reader comparison remains below.

## Measured results

The same saved staging study was measured through its actual actor-scoped owner
readers. These are server-side timings, not browser load or concurrent-load metrics.
The before/after scripts and raw JSON lines are retained in the two packets.

| Journey | Before | Final release |
| --- | --- | --- |
| Answer, first fresh process with prepared verified projections | 25.210 s baseline without projection | 4.752 s |
| Answer, repeated | 0.498 s | 0.115 s |
| Run list, first / repeated | 6.080 / 10.033 s | 0.702 / 0.254 s |
| Ten analysis run evaluations, first / repeated | 7.831 / 5.696 s | 1.791 / 1.227 s |
| Run detail, first / repeated | 1.635 / 1.215 s | 1.217 / 0.102 s |
| Joint surrogate, first / repeated | 5.026 / 1.395–2.045 s | 3.416 / 0.279 s |

Study/configuration/analysis lists remain about 0.01–0.07 seconds. The one-time
rebuild after invalidating the reader cache is still 28.884 seconds in the final
release (first release 19.309 seconds); it now prepares public run details too.
It is performed by publication verification or explicit preparation, and must not
be described as a subsecond cold-cache read. A new process over that prepared data
still takes 4.752 seconds, largely initialization/validation setup. Prediction
measurements evaluate one selection plus a 32-point curve through the real isolated
surrogate worker. All 27 model runs remained unchanged, with no refit or resampling.

## Browser, Assistant and current stopping point

The final installed root URL redirected to `/ui/`, retained real Cloudflare email
authentication and displayed Home and the saved study in Chrome. Joint load/flow
changes to 14.2709320588 kW / 0.263186078984 kg/s produced estimated 12.9110244876 K
and -3.21711674148 kW, with real curves. Loading nominal point 2 immediately showed
calculated 9.52380952381 K / +0.6 kW. No manual retry, refit or resampling.
Final Assistant turn 7dd8b66d-b5b5-4f91-99a9-49e0b8131cab called get_surrogate with
an accepted, non-error receipt and returned a validation summary. Conversation idle;
27 runs, 26 configurations, 3 analysis versions and 1 answer remained unchanged.
Previous reader release also passed analysis pagination, pinned run/model/configuration
readers and actual get_analysis/get_surrogate turn aac4c44e-f007-419f-ab83-b1409d8cef37.
The root-only delta leaves those readers and all UI bytes unchanged.

Final promotion completed in staging mode. Receipt:
/private/tmp/hyprn-staging-landing/application-evidence/promotion-resume-result.jsonl.
Screenshot: application-evidence/staging-live.png in that packet. Automated evidence
is not human acceptance. Next: cold-start and renewal CPU profiling, then outstanding
automatic delivery and recovery qualification. Do not replay setup or migrations.

## Remaining bottlenecks and obligations

- First-time validator/reader setup and invalidated projection rebuilding remain
  measurable; cold-start parity with local execution is not established.
- Host access renewal consumes roughly 29–30 CPU seconds per cycle, with a 30-second
  pause. Profile the verification stages before optimizing; retain fail-closed
  identity/containment checks. Memory saturation was not observed (app about 205 MiB
  of 2 GiB; surrogate about 112 MiB of 256 MiB).
- Per-request admission still creates a separate maintenance-lock database session;
  frontend analysis uses several per-row reads. These are candidates for bounded
  reuse/batched public projections, not grounds to remove authorization checks.
- Expired-Access handling should clearly lead to fresh sign-in rather than an opaque
  in-page retry. Authentication expiry must not be confused with a backend outage.
- Concurrent users, larger studies, local/cloud matched timing and full recovery/
  reboot qualification remain unverified. Automatic staging-branch deployment and
  second-user human acceptance remain separate unfinished delivery obligations.

Nine exact, unattached build volumes from the three builds were removed;
shared images and other sessions were preserved. The expired temporary private keys
were removed; the active two-hour connection remains for final verification.
All unrelated repository edits and planning files were preserved.
