# Performance and UX follow-up — deployed, 2026-10-23

User authorized the remaining generic fixes, identical before/after measurements
and staging deployment. No additional infrastructure, permission or budget change.
Unrelated planning/design edits are preserved. Plan: 07-PERFORMANCE-UX-PLAN.md.

Baseline: same completed staging run, five `NativeExecution.read_record` calls:
5.9935, 5.7698, 5.2172, 5.8837, 5.5532 seconds; median 5.7698 seconds.
The private benchmark saves the exact request/association and SHA-256 of the full
normalized returned record. After measurement must use those identical inputs and
produce the same full-record digest. No candidate model execution or store write.
Evidence: private hyprn-performance-ux-release/native-read-before.json.
The first attempt stopped before remote work because the temporary SSH key had
expired. Same identity/privileges renewed under continuing deployment authority;
the read-only baseline then passed.

Implementation partition:
- Native executor: one retained bundle verification and bounded bulk object reads;
  host-only code so numerical worker bytes and saved surrogate runtime pins stay
  unchanged. All original semantic/hash/bound/corruption checks remain.
- UI executor: preserve incoming study/version route on hosted sign-in; refresh
  displayed study state after settled Assistant work without overwriting drafts.
- Authoring executor: unique generated point names, explicit surrogate sample roles,
  intended criterion binding before launch, quantity naming guidance, and schema
  discriminator-aware errors. Recorded immutable configurations are not renamed.
- Parent: source closure registration, integration, exact artifacts and deployment.

Deployment stays on the existing reviewed platform commit. No migration or reset.
Current preparation generator already stages bindings as 0600; the older reset
publisher's 0644 failure does not require another live chmod or product workaround.
Private deployment packet is prepared from existing reproducible build/recovery
helpers and current sequence 20, promoting to 21 only after tests and real artifacts.
No release is claimed deployed at this checkpoint.

## Integrated checks before staging

Runtime source is committed in 07cacb56, authoring in 42afefb5 and UI in 5ea94c71.
Parent ran the pinned entry point with isolated scopes and explicit 20 GiB build
cache allowance, without removing shared images:
- locality-contracts: 166 passed (11.27 s pytest; 26.56 s runner).
- contracts: 127 passed (11.14 s pytest; 35.25 s runner).
- native-execution: 114 passed (228.49 s pytest); retained exact results, refused
  forged associations and actual restricted worker journeys pass. Cleanup exit 0.
- hosted-assistant-setup: 27 passed (12.58 s); exact skill bundle generated offline.
- units-attestation: 26 passed / 57 failed: its copied source list omitted two
  already-attested cloud deployment modules. Production inventory is correct;
  the executor is correcting the fixture list and will rerun this affected group.

The first candidate snapshot 036d1535 is superseded before any artifact publication
because required archive/attestation test-fixture repairs are still in progress.
No runtime source changed during those fixture repairs. No deployment performed yet.

Required fixture corrections now pass on 467dfed6: units-launcher 64 passed and
units-attestation 85 passed, all isolated scopes released. Final tested runtime
source is unchanged after the earlier native/contract/UI checks. Final source
candidate ea1497cd1fd2cd3ad51959a69fda9ca724a09817 uses that exact tree
5dbc29539e2a802b744224d907266df544298024, with origin/staging as its parent.
Normal pre-push gate passed and origin/staging advanced from 41c39ab4 to ea1497cd.
Published provider resources contain the exact new native skill bundle and 57
unchanged tool identities; model, research hosts and reviewer limits unchanged.
The app image's installed definition matches that plan. Numerical worker/modeling
OCI digests equal the existing release. Host native build/deployment still pending.


## Delivery and measured acceptance

Origin/staging candidate `ea1497cd1fd2cd3ad51959a69fda9ca724a09817` is deployed
as sequence 21, release
`1339acb05d5a2591e945e8a3b220f6725fad5b8a1135a8d3e991e2eba96dc3b5`,
configuration `62a5eaa18bc48b308949a5e36c0d752fdaaa5cbca7b1d62e23876fdfcd29f06b`.
Platform remains `492eeb2d`; schema 13, all credentials, cumulative USD 20/user,
modeling image and numerical-worker image remain unchanged. No migration/reset.
All scoped queues were empty before service replacement. Managed SQL backup and
68,611-file native backup completed and remain retained. Build, installed native,
containment/startup and all 19 live network checks passed. Private frozen packet:
`/private/tmp/hyprn-performance-ux-deploy/packet-1`, preparation SHA-256
`93cc72f3ef706bd4e0811f299279adfbea68719ae2ecd830d2222ce5d346043e`.

Focused integrated evidence totals 1,189 passing tests: bridge-history157,
units-launcher64, native-execution114, units-attestation85, locality-contracts166,
contracts127, calculations-api83, agent-tools330, ui-navigation36 and
hosted-assistant-setup27. TypeScript/design/token checks and fresh build passed.
Earlier fixture failures and their corrections are retained above and in executor
checkpoints. No full qualification or human acceptance is claimed.

Same retained run, same request, same native process, five reads each:
- Before: 5.993532, 5.769841, 5.217179, 5.883732, 5.553174 seconds.
- After: 0.751977, 0.203400, 0.187246, 0.185891, 0.192387 seconds.
- Median 5.769841 → 0.192387 seconds: 29.99 times faster, 96.67% reduction.
- First measured read after startup: 0.751977 seconds.
- Complete normalized record SHA-256 unchanged:
  `abff65d350fd34b492104a3f6391866eecda6e9308fe7cacf6bf2799104bfc34`.
Controlled 480-file loose/packed repository queries fell from 1,920/1,919 to 2;
exact bytes still verified. This measures retained reads, not end-to-end study speed.

Public Chrome verification on study `bbb6474b-33cc-497f-ba2d-85345eac42ad`:
- Authorized login works; authenticated reload preserves the study route.
  External Cloudflare OTP return does not preserve the URL fragment; this is
  distinct from the repaired application bootstrap routing.
- Loading an exact sample displays Calculated (10.526315789474 K).
- Moving all three inputs together displays real Estimated values, including
  10.453176312147699 K and 10.51836987283424 K, without unavailable output.
- A bounded normal Assistant message saved answer version 2 clarifying actual
  sample roles: 32 training, 1 method selection, 15 independent validation.
  The answer selector updated to version 2 while Assistant remained collapsed.
  Captured accessibility evidence predates the work-profile window closing.
- All 50 run IDs/process IDs and original answer bytes match before/after; one
  new answer version was published through the public Assistant, without model
  reruns, new samples, refitting or direct scientific-record repair.

Private evidence: `/private/tmp/hyprn-performance-ux-release/`, specifically
`performance-comparison.json`, native-read before/after, study before/after snapshots,
`answer-refresh-collapsed.txt`, `live-calculated.png`, and build/deployment logs.
No remaining implementation blocker in this batch. Broader research/reviewer and
concurrency evaluations, safe retention, automatic deployment and full qualification
remain explicitly separate obligations; this delivery does not close them. Full
fresh-study elapsed time and laptop-speed parity were not remeasured. Backup object
verification still adds deployment downtime; no backup checks were weakened.

Ongoing named-user staging access promotion completed successfully after the public
checks, with the exact sequence21 release/configuration identity. Receipt:
`packet-1/application-evidence/promotion-resume-result.jsonl`. The promotion
mechanism does not itself attest human acceptance; public journey evidence is
recorded separately above. Final checkpoint-only delta does not alter deployed
artifacts or invalidate the tested tree.
