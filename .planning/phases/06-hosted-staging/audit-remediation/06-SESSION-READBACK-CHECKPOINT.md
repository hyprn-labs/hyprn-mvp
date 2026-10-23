# Provider session readback correction — 2026-10-23

Public Chrome login and creation of the coolant verification study succeeded.
The provider created its session, then HYPRN refused its tool readback before
sending the first message: web_fetch contained the optional `url_sources: null`.
Provisioning already admitted exactly this default; runtime did not.

The shared normalizer now serves provisioning and runtime. Unknown properties,
added tools and actual URL restrictions still fail closed. No policy, scientific
record, budget, accuracy threshold or execution capability changes.

Verification on the implementation tree:
- `./hyprn-mvp dev check assistant-bridge`: regression first failed (1/194),
  then 194 passed in 32.91 seconds; cleanup exit 0.
- `./hyprn-mvp dev check hosted-assistant-setup`: 27 passed in 13.189 seconds;
  cleanup exit 0. Both use the pinned runner and isolated scratch stores.
- `git diff --check` passed.

Exact private logs are retained under hyprn-staging-reset-continuity in operator
scratch. The blocked turn was stopped through the public app; no database repair
was performed. Release build, deployment and resumed public journey subsequently completed
as recorded below. Previous baseline evidence is retained in COVERAGE.md; no unchanged
numerical or UI checks were repeated.

## Staging installation and public continuation

Implementation commit: `3f12d9d4`; published candidate `41c39ab4`.
The normal pre-push hook passed and origin/staging now points at the candidate.
Release `d626e342dee45eadabe8ef11a989d1cf4e458470f7a1c2a261c03fc95764a91d`;
configuration `3e9150e100530dd2ea4acfd34641a8e388ce6f6f20a08bead3a177a55060e328`;
desired sequence 20, generation `1792710031655600`; platform unchanged `492eeb2d`.
App image `032774ad6652a8713ba624fa56ae5be54352c424013924aff656644d49f9d30c`.
Native archive `36ced33fab075aef91c79ad57fad168bf01a7049ed370ba878b92438289f8c9a`.
Worker and modeling image inputs/archives were verified unchanged and reused.
Fresh native extraction verified 20,927 files and actual package imports;
built application retains the exact reviewed Assistant definition and UI assets.

The first backup attempt refused the active configuration binding's 0644 mode.
That file was produced by the prior clean-reset configuration operator; backup
requires 0600. Read-only reproduction confirmed exact bytes, root ownership and
one link. The authorized continuation tightened only this mode, verified the
original backup reader now accepts it, and retained the entire pre-backup failure.
No database backup had begun before the refusal; no uncertain backup was retried.
The configuration publisher must use backup-compatible 0600 binding permissions.
This is an operator artifact correction, not an application/scientific-data repair.

The coherent backup then completed, including 43,716 retained native files.
Qualification, startup and all 19 real network observations passed. No database
migration/reset, store initialization or credential reissue occurred. Schema 13
was observed unchanged. The helper's inherited result label
`application_migrated_to: 13` means observed target schema here; the actual upgrade
has no migrate call and the journal migration is null.

Public Chrome login and the preserved study/conversation passed after reopening.
The Assistant accepted a normal follow-up, made real playbook tool calls and
created a model. The final public answer and joint-slider acceptance subsequently
passed as recorded below; this does not establish full release qualification or
human acceptance. All exact receipts are in the private session-readback release
and deployment packet; the earlier failed receipts remain intact.

## Live execution and measured remaining overhead

Public Assistant continuation created the brief/model, two reference calculations
and a finite 48-point joint design (32 training, 16 held-out points), with
accuracy targets set before launch. Nominal rise is 9.5238095238095 K; simultaneous
adverse rise is 15.789473684211 K. The Assistant correctly waits on durable analysis
execution; it does not schedule point batches or repeatedly consume model turns.
A malformed initial edit received actionable diagnostics and was corrected by the
Assistant without operator data changes.

Measured worker durations are 2.656–3.901 s. Native two-point batches take 30–33 s,
and retained reads about 4.7–5.1 s (two observed outliers 8.5–9.6 s), yielding about
57 s between two-point worker batches. This is not laptop-equivalent throughput.
The observed host has 15.39 GB available of 16.78 GB, no OOM or memory pressure;
RAM enlargement is not supported by this evidence. The one-CPU service limits
and native preparation/retention paths require more specific profiling before a
hardware recommendation. Data-only cProfile probes on the actual saved records:
configuration validation 0.128 s cold / 0.011 s warm; prepared-bundle validation
1.259 s cold / 0.383 s warm. Neither alone explains the complete native delay.
These probes executed no candidate code and changed no records or queue state.

Database observations: approximately 92.5 transactions/s during authoring,
490 returned tuples/s, versus 27.9 transactions/s when idle after reset. The older
populated installation measured 360 transactions/s and 37,702 returned tuples/s;
different contents/workloads prohibit calling this a controlled speedup.

New UX finding: sampled configurations copy their reference's title even when
values differ. A point with 10 kW, 0.25 kg/s and 3.8 kJ/(kg K) displayed the nominal
12 kW title while its exact values and 10.526 K result were correct. The generic
configuration-generation owner should name sampled points distinctly; existing
immutable records must not be patched. This remains a product follow-up.

Private diagnostic scripts/receipts are in the session-readback release scratch.
Two read-only diagnostic probes initially failed (query quoting; outbox study
scope requires its run-association join), then ran with corrected queries. No
mutation or uncertain numerical launch was retried. Final answer/slider checks subsequently passed below.

A subsequent read-only cProfile of the native owner's exact `read_record` path
identified the retained-read bottleneck. Two reads traversed the bundle four times
(`read_record -> retained_bundle -> inspect -> retained_bundle`, then another
retained_bundle), opening 1,928 logical objects with 3,856 repository/backend open
calls and 3,972 SQLAlchemy session executions. Object-store lookup/open accounted
for 19.67 of 22.64 profiled seconds; cProfile overhead means these absolute times
must not replace the ordinary 4.7–5.1 s telemetry. Consolidating the duplicate
bundle traversal and bulk object lookup is the next generic optimization; retain
all bounds, hashes, exact-request checks and rejection of corrupt records. This
is stronger evidence than a VM-size hypothesis. The probe loaded one completed
request as the existing execution owner and invoked only read_record; it submitted
no candidate run, changed no records and did not restart the active service.

All 50 model runs completed (two named scenarios plus48 sample points), and the
Assistant resumed automatically after its durable wait. The automatic surrogate
selected Kriging using one held-out selection point; the remaining15 independent
validation points passed unchanged targets. Max error0.00526345076086443 K,
RMSE0.0025631447565753313 K; declared target0.1 K plus1% of the calculated magnitude.
The Assistant then called prepare_answer_exploration and predict_answer through
its normal tools. Final publication/browser interaction passed below.


## Public answer and joint exploration acceptance

Study `bbb6474b-33cc-497f-ba2d-85345eac42ad`, “Coolant loop — staging
verification”, was authored solely through the public Assistant. Turn
`5bdb697e-0f77-46c7-bcc8-4024e9978f77` completed at 23:49:24 UTC on October 22;
public continuation began at 23:14:54 UTC, approximately 34m30s end to end.
The saved answer `3bb8a05c-a432-4c2a-a002-4bfa88ba2c1f` is complete, with both
requested deliverables fulfilled. It retains the illustrative thermal-screen
limits and does not claim a qualified physical cooling design.

The publication guard caught missing criterion bindings on the sampled analysis.
The Assistant created version 2 `a7bd4017-0f10-449d-be69-38e89d72e71a`, reusing all
48 recorded samples with unchanged ranges and accuracy targets. Final estimate
`01c8b4da-7517-5abd-a6e6-6dd3ddbe0b42` passed. Of the 16 held-out points, one
selected the method and the remaining 15 independently assessed it; the selection
point is not counted as independent validation.

Signed-in Chrome verification:
- All three independent sliders are available, including specific heat.
- Loaded exact point (15 kW, 0.25 kg/s, 3.8 kJ/(kg K)) displays Calculated
  15.789473684211 K.
- Changed all three together to (14.938443272249529, 0.25028431161045006,
  3.806074042932727), displaying Estimated 15.682439643977592 K and a real curve.
- Changed the plot axis independently to specific heat, preserving selected inputs
  and output. No unavailable-result state or manual retry occurred.
- Run count was 50 before and 50 after all browser actions. Final read-only receipt:
  private `application-evidence/run-timings-1792713372.json`.
- Native automation roundtrips were 1.713 s for the combined slider actions and
  1.388 s for the axis change. These include accessibility capture and are not
  isolated HTTP latency measurements.
- Screenshot: private `public-answer-exploration.png` in the session-readback
  release evidence. Browser automation is not human acceptance.

## Remaining work discovered during the real journey

The batch is not a claim that every audit obligation or all performance work is
complete. Parent owns these generic follow-ups; scientific records stay intact:

1. Remove duplicate retained-bundle traversal and batch object-store lookup while
   preserving every hash, bound and request-identity check. Measure exact live
   read and batch durations again; no RAM resize is justified by current evidence.
2. Refresh the saved answer when the Assistant publishes, and preserve study route
   on browser reload. The current journey required a reload and reopening the study.
3. Give generated sample points distinct names through their authoring owner;
   improve human-readable quantity names through canonical agent guidance.
4. Clarify method-selection versus independent-validation counts in agent responses.
   The final chat unnecessarily questioned why only 15 of 16 held-out points were
   assessed although one had selected the method.
5. Improve answer-write union diagnostics. Two rejected section updates pointed at
   derived `monetary_basis`; the final merged content and save envelope both pass
   their direct validators. Root cause of those earlier payload failures remains
   unproven; do not remove money metadata or weaken validation to silence them.
6. Require criterion bindings before sample launch in the agent workflow so the
   publication guard need not trigger an avoidable new analysis version.
7. Make configuration publication write backup-compatible 0600 binding permissions.
8. Retain open live source-fetch/reviewer evaluation, concurrency/restart/revocation
   acceptance, full release qualification, second-user acceptance, safe retention
   lifecycle and automatic deployments. This study did not exercise all of them.

No scientific data was repaired directly. No thresholds were relaxed, new model
runs triggered by exploration, or hardware/subscription changes made. The focused
checks above cover the deployed source; these later evidence-only edits require
no repeated application tests.


## Ongoing staging access

The previously approved conditional promotion ran only after the public journey
passed. `promote-verified.py` accepted packet preparation SHA256
`3aef850d652b3c6fb9494cdd855e1b9f7e82a47bd4f7759920c5202bd0e0db05` and exited 0.
Receipt: `promotion: reviewed-staging-operation`, `mode: staging`, exact release
`d626e342` / configuration `3e9150e`. The qualification timer was restarted for
normal renewal. No new permissions, users, budgets or service versions were added.
Private receipt: session-readback deployment `packet-1/application-evidence/
promotion-resume-result.jsonl`. The infrastructure receipt deliberately retains
`human_acceptance: not-established` and `user_journeys: not-established`; it does
not attest browser journeys. The separately recorded public checks above provide
that automated journey evidence and are not human acceptance.
