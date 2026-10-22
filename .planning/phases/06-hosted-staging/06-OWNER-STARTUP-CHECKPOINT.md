# Current status — private staging working and promoted

See [performance checkpoint](06-PERFORMANCE-CHECKPOINT.md) for authoritative current
release f7a33f5a / fd63aa0d / schema 8, root redirect, measured performance and next
obligations. Final Chrome login, real joint estimates/calculated points and Assistant
tool checks passed; ongoing named-user access is promoted. Earlier records below
are historical. Do not replay completed setup, migrations or recovery. Cold-start
latency, automatic delivery and full recovery/human qualification remain unfinished.

---

# Working private staging — 22 October 2026

Live: https://staging.hyprn.ai/ui/ . Restricted to the existing named email users.
Owner continuing authorization is recorded in
`/private/tmp/hyprn-staging-install-continuation/OWNER-AUTHORIZATION.md`.
Delayed approvals and prior repairs are completed; do not replay them.

Product `a1ee452cb30426637c19c46537da4ff3caeed344`; platform runtime artifact
`3488a518cbae96b283d3ab88e5096215744f756d`. Release
`eb6f7f8b3a5263d7370f3f2ec6a0c20f36b1dbc195839ce26a908e01dd024d8f`;
config `c0a35307a16364eb4deff92007c617a5e6602fbebda71a0673bf1addb2c2a73f`;
desired sequence 11, generation `1792622649640043`.
Exact packet and evidence: `/private/tmp/hyprn-staging-exploration-ready/`.
Amendment `bc8ddb2f879f440afab5982cb57510e39226fc2318b6145da6af901742fca747`.

Publication, staging, idle-stop, desired publication, native installation, fresh
containment, startup, all 19 real network probes and private activation passed.
Ongoing private access was promoted successfully (`mode: staging`), after live
verification. First promotion collided with the scheduled renewal's journal lock;
read-back proved no promotion had occurred. The same installed promotion was then
serialized with that timer, completed, and the timer restarted. Both receipts remain.
No initialization, migration, new secret version or scientific model run was repeated
in this update. Database schema remains 6. Budgets remain EUR100 shared Assistant
and EUR170–220/month infrastructure estimate.

## Observed user journey

Chrome retained the real email-authenticated session and opened the saved study.
The first exploration after a fresh app start completed without timeout or retry;
its basis was visible by 35.346 seconds and estimated outputs followed. This is an
observation upper bound, not a precise request timing. The installed predecessor's
isolated measurement was 28.716 s cold / 0.581 s warm, down from 11.888 s warm before
the database-maintained fingerprint change. Cold verification still has noticeable
latency; it is saved-record integrity checking, not model execution.

Moving both load and flow sliders produced estimated 11.8844605254 K and
-2.15751929548 kW at 13.5964175892 kW / 0.272354721279 kg/s, observed within 11.318 s.
Selecting calculated point 2 showed 9.52380952381 K / +0.6 kW within 0.403 s.
Both curves displayed real calculated and estimated points. No manual retry.
Assistant turn `0244dc5f-ef53-4813-b03f-49b0cccc0c5c` successfully called get_analysis
and get_surrogate (accepted receipts, no tool errors), confirmed validation, and
finished idle. Authoring counts stayed 27 runs, 26 configurations, 3 analysis versions,
1 answer. No surrogate refit, sampling or model rerun occurred during these checks.

Study `ae232ccb-d48b-4e9d-928d-879d97d86d22`; answer
`1fa6d0a2-78cb-4e61-82c5-6f3f00f20a80`; surrogate
`b90ad5f0-f7cd-5874-a239-6a4c86f1658a`. The Assistant authored the brief, model,
comparison, 24 real sample runs, checked surrogate and saved answer in earlier turns.
16 training points / 1 method-selection point / 7 independent validation points;
predeclared 0.05 K or kW absolute plus 1% relative tolerances remain unchanged and pass.
Original killed nominal run is preserved; the answer cites the successful replacement.

## Verification and cleanup

On committed product a1ee452c: calculations-api 73 passed (44.43 s); UI build,
design guard, token freshness and UI contract checks passed. Nine operator guards
passed. Verified 37 actual packages, unchanged Assistant definition, 54 unchanged
worker/modeling input hashes, 8 actual UI assets and fresh native extraction.
Earlier unchanged hosted-postgres 29 and contracts 127 evidence retained.
Development failures are preserved: sandbox cache refusal before tests; new test's
initial exact recheck-count assertion corrected because internal integrity checking
adds another check; build output-file collision before Docker started; UI extraction
attempt before the completed image receipt was copied. All affected checks completed
successfully before publication. No test targeted live stores.

Six explicitly labelled, unattached build volumes were removed after delivery;
one expired temporary private key was deleted. Release archives, nonsecret receipts,
live stores/containers and the current time-limited operator key were preserved.
Evidence: `application-evidence/live-verification.json`, `final-assistant-tools.json`,
`study-before-browser.json`, `study-after-sliders.json`, `promotion-resume-result.jsonl`,
`local-build-cleanup.json`, `expired-key-cleanup.json`, and `staging-study.png`.

The prior fingerprint deployment completed one additive application migration with
successful database-only backup `1792621192860`; its packet is
`/private/tmp/hyprn-staging-stored-fingerprint`. That backup is not a qualified
whole-installation recovery proof. No new database backup or migration in this release.

## Remaining obligations

This establishes a first working private staging product, not a qualified release.
- Product/platform orchestration: automatic deployment from protected staging-branch
  merges is not implemented; product 06-06 and platform 08-03 remain open.
- Platform: full reboot and coherent whole-installation restore qualification.
- Owner: second-user sign-in/isolation human acceptance; do not impersonate Guerric.
- Product: native cancellation hardening and further cold-load/prediction performance.
- Product UI: Assistant table/Markdown rendering remains rough; no cosmetic fix was
  folded into the deployment repair.
No subscription changes or wider access are authorized by this completion record.

# Earlier runtime correction evidence

21 October2026: Assistant enablement applied successfully. Live product3aa4415,
platform3488a51, release131f3e8bfef7feb85d0c476baf9f45452efb9b93886060695ad92ecda8f04a64.
Chrome email login, private study creation and actual Assistant scientific authoring pass.
Containment/start and19 network probes pass. Execution/answer exploration do not yet pass.
The coolant study ae232ccb-d48b-4e9d-928d-879d97d86d22 retains its brief, model,
configurations and analysis. Do not delete or resubmit the two accepted requests.
Native processe8ca1e78-da90-4467-bf8d-ad26d9004b41 is paused before upload with no
scheduler job, remote workdir or outputs; nominal5666c078 is dispatching, adverse0495c773 queued.

Runtime fixes committedfb6ee97; test-only correction3529f76c13e8794d7a24a8b4a7d89a6f2168d7c3:
- PostgreSQL run reads use octet_length instead of SQLite BLOB; same byte bound/pins.
- Assistant history writes and repeated tool-result reads leave the HTTP event loop.
- Explicit native initialization/rebind prepares the private transport home; admission
  checks it without implicit repair. Native identities and attestation remain binding.
- Existing history test now validates current RunHistoryItem2, not its frozen predecessor.

Final ./hyprn-mvp dev check results on these exact runtime bytes:
assistant-bridge139 pass24.25s(f056caa7);hosted-postgres25 pass41.40s(44481178);
api-a125 pass83.23s(af5b1d27);hosted-native-owner18 pass10.94s(ab9f21b7).
Only the test-format reference changed after the first three runtime groups; no runtime
bytes changed after their final passing runs. All logs and initial failures are retained
in /private/tmp/hyprn-staging-assistant-enablement/{assistant-final,hosted-run-green,
history-sqlite-final,native-home-green}.log. Original red checks:1/138 Assistant,
1/24 PostgreSQL; native3 new-helper errors then1 mode/umask fixture failure; history1/124
old-format test failure. Cache preflight refused once;16GiB allowance preserved shared
images. No new dependency. Test scopes cleaned; labelled build volumes retained.

New app4776c06ec80bed1b08e3397556d95ccbae9a8635936e4878e5cc965b022c829e and
native bundle built/freshly extracted. All8 UI files unchanged; actual37 app packages
and unchanged provider definition verified. Worker/modeling images reused with exact
input proof. Native packaging first rejected changed cloud_native.py fingerprint;
regenerated host inventory and resumed only unfinished steps; fresh VM attestation required.

Prepared NOT APPLIED: /private/tmp/hyprn-staging-runtime-correction/REVIEW.md.
Amendment0b528369d92a6c7ab4b6e13a1e3e7a682447d49e33ef4fbf61cfece93449a046;
new releasefd809f9f61e0af811298b45d0f9ad867fc547e7e3552f29df8a624aceec2af5c.
Recovery guards6 Linux+6 state+4 handoff pass. Packet fully verified. Approval requested.
Next: apply approved phases, explicitly reconcile original paused process through its
existing handler, retain its killed record; then real new nominal run, held-out validated
sampling/surrogate, saved answer and joint sliders with no model reruns.
No schema migration, authoring deletion, secret reissue, budget/IAM change. EUR100 shared
Assistant and EUR170–220/month unchanged. Automatic branch deployment, two-user human
acceptance and reboot/recovery qualification remain unfinished.

Authoritative cloud state and next action:
../hyprn-platform/.planning/phases/08-product-staging/08-FIRST-DEPLOYMENT-CHECKPOINT.md
(resolve from the product repository root). Exact review/evidence:
/private/tmp/hyprn-staging-owner-startup-recovery/REVIEW.md and EVIDENCE.md.
Amendmentbe5ce61f60be56259ac28c4f6d261e01c187cf6dc6c62c53f265c7b0c05e4c84.

Final commands on committed batch:
- ./hyprn-mvp dev check runtime-observation:61 passed,22.626s;
  check2313f5e6-0889-4d2d-ae46-d68f523b45f0.
- ./hyprn-mvp dev check hosted-lifecycle:23 passed,35.116s;
  checkbed0d230-a96f-482a-a7eb-525d4b5445cf.
- platform tests/platform/run.sh bootstrap:32 passed,0.751s.
- packet test_recovery.py:6 passed. verify-packet.py and all frozen hashes pass.

Initial regression run3 failed/58 passed reproduced the missing-row crash and missing
new readiness method. Platform fixture initially lacked its mock import, then1 fail/31
pass reproduced the missing guard. Final runs pass. First product invocation was
sandbox-denied before any test; repeated with the existing external tool cache.
No candidate model or paid provider request in these checks. Isolated test scopes
released by runner. Build volumes are scoped to commit7881480 and retained; temporary
containers removed by --rm. Unrelated session changes preserved.

New app imagefe70d83261e96f635dfec29d6781d98e49872090f8b15e4c64e43ea5fa94e886;
native996e62a995e49e35db71a1bd98e6a57ffe7c0e91e8988ee2dcd8a4ef27e26edb.
Fresh native extraction/imports, exact OCI graph, actual dependency inventory and8
unchanged UI files verified. No new dependency, schema or API. Real staging login,
execution, Assistant, joint sliders and later qualification remain unverified.

## Earlier handoff attempt — superseded by successful corrections above

Approvedbe5ce61f applied images/files/stage/desired; desiredgeneration1792597479844287.
Recover refused platform_root_mismatch: new platform attempted to load old binding.
No stop intent, initialization, migration or secret reissue; previous closed service
states/journal retained. The corrected handoff runs the old owner in a separate
interpreter with its own pinned platform. Actual VM read-only preflight plus10 focused
checks pass. Product bytes/tests unchanged; no rebuilding or repeating product checks.

Prepared review /private/tmp/hyprn-staging-owner-handoff-repair/REVIEW.md,
amendment3919b6df74d0efa0855e01146c1fb3cc8edfb879b759c8c14a79d06ca184ba0f.
Approval pending for two protected helper files; next phases stage/recover/network-probe/activate.
Live login/execution/Assistant/exploration still unverified. Authoritative platform
checkpoint records exact runtime and the used replacement-key expiry17:47:38UTC.
