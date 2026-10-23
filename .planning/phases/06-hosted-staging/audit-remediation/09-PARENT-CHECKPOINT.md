# Analysis recovery integration

Implementation `3046d905`, exact tree `323be5952c5de885dc44adb4cdd63fe1d8967c98`.
Staging release commit `0a0d8316` has that identical tree and previous staging
`679bb62b` as parent. Normal fast-forward push succeeded. The initial attempt to
push the development-history commit was refused as non-fast-forward; no remote
history was rewritten. Unrelated working-tree changes remain untouched.

Backend evidence: [executor checkpoint](09-BACKEND-CHECKPOINT.md). Parent adds the
public agent recovery tool, current eligibility projection, a backend-driven Resume
button, cancelled-state handling and guidance. Help/playbook and recovery semantics
remain generic. No direct staging study-data repair is authorized or performed.

## Focused verification

- Calculations API 91 and hosted PostgreSQL 53 pass on backend `6e997ee1`.
- Agent tools 331 pass (45.88 s): public API recovery, current grant, retained runs
  and explicit action. This ran before the final accepted-child preflight delta,
  covered by the final backend API/PostgreSQL groups.
- Integrated contracts 127 pass (9.58 s), locality contracts 166 pass (13.54 s).
- Browser calculations 7 pass (59.93 s), including Resume, preserved run link,
  responsive layout and light/dark variants. Recovery status is an explicit UI
  double; real recovery authorization is separately covered by API/PostgreSQL.
- First browser run 4 pass/3 fail: two stale Measured-label assertions and a
  metadata-spacing assertion assumed a prior field order. Screenshot inspection
  confirmed current Calculated wording and separated inputs/reference metadata.
  Assertions now protect the same numerical values and spacing in either order.
- TypeScript, design-system, generated-token, UI contract and ownership checks pass.
  OpenAPI parsed diff: four additive routes (canonical plus compatibility), two
  additive schemas, no changed existing schema or route.
- All groups used the pinned local entry point and scoped scratch stores. Logs and
  released session identities are under `/private/tmp/hyprn-analysis-authority-diagnosis`.
  First agent-tool invocation refused before tests because the default tool cache
  was absent; rerun used the existing configured pinned cache, no dependency change.

## Build/deployment status

Exact committed source snapshot; worker/modeling inputs and OCI hashes verified
unchanged. App image and native bundle built; fresh native extraction/imports pass.
Provider skill, reviewers and main Assistant definitions provisioned without creating
sessions; actual app definitions match. No budget, access or infrastructure change.
The first local build refused generated Python bytecode in its immutable snapshot;
only those untracked cache files were removed and source hashes reverified. A final
build uses the proper staging-lineage commit. Earlier build artifacts retained.

Staging installation/migration14, public recovery and run preservation verification
are pending. Full qualification and scientific/human acceptance are separate.

## First staging delivery and public continuation

Release commit `0a0d831684c887db6863acba9d616bab29e43aff` has exactly the tested
`3046d905` tree, with the current remote staging commit as parent (the development
branch uses a different lineage). Normal fast-forward push succeeded. Sequence24,
release `395a4423b761d6b2bdf83da5a2c45e9888c6a79f3d34678fc53c361ec48943f6`,
was deployed with coherent backup, additive migration14, native containment,
startup and all19 network probes passing. Named-user login and the real public
analysis page work. No study data was manually modified. Saved scientific records
and the original analysis request were hash-identical before/after deployment.
Evidence: `/private/tmp/hyprn-analysis-recovery-deploy/packet-1/application-evidence`.

The public Assistant invoked `resume_analysis` exactly once, returning the same
analysis to calculating. It then stopped on eight previously accepted child runs
whose operational preparation failures were all `analysis_authority_revoked`403.
Read-only proof: each child is accepted_run in both operation/outbox, has only
actor/frozen outbox data, no request or bundle, and empty operational results.
The first delivery therefore does not yet complete the user's recovery journey.
A follow-up adds narrowly audited recovery of these provably unstarted children,
through the existing public Resume command. Genuine/uncertain executions remain
excluded. The current Assistant turn has finished; no replacement analysis was
created. Details: `/private/tmp/hyprn-analysis-recovery-release/child-preparation-proof.json`.

Next: backend regression for public resume through child preparation, migration15,
normal sequence25 deployment, then repeat the public continuation and verify
progress with the same frozen inputs/run identities. Native backup took nearly ten
minutes; next packet allows a bounded twenty minutes without omitting any backup
or integrity checks. Ongoing-access promotion remains pending final verification.


## Follow-up delivery: provably unstarted child recovery

The follow-up source `6ca2c037` and staging commit
`17f27084d39b6d41f582c78acec45f6eb7e288a7` have identical trees. The latter was
fast-forward pushed on the staging lineage. Explicit public Resume now preserves
and audits the prior operational failure before recovering only accepted children
with the exact authority-revoked preparation error, no native claim and no prepared
bundle. Frozen source/input bytes and run identities remain unchanged. Genuine
failures, uncertain dispatches and actual permission revocation remain excluded.

Final focused checks: calculations-api 98, hosted-postgres 56, contracts 127 and
locality-contracts 166 pass (447 tests). Contracts/boundaries were repeated on the
committed tree; the final PostgreSQL group includes three independent real-PG,
public delegated-agent concurrent-resume cases. UI/tool/contract/numerical source
is unchanged from the previously verified delivery. A first PG test's concurrent
500 response remains unexplained; it is recorded, not claimed fixed, in
[the child checkpoint](09-CHILD-RECOVERY-CHECKPOINT.md). Subsequent independent
cases pass and test-only exception diagnostics are retained.

Sequence25 release `22dc5479c062ddbe02dac1ecd31f165d296b23ce4448ce8077fea9a7d2d27a99`,
configuration `bbec6d475abf2e909fd89dbdb899d998f443b59401fff790bbb6ca75f79619b3`,
schema15 deployed normally with a coherent backup, additive migration, containment,
startup and all19 network probes. Worker/modeling images, provider resources,
credentials, budgets and access policy are unchanged. Saved scientific records
and original execution request were hash-identical across deployment. Backup took
about twelve minutes within the bounded twenty-minute timeout; no integrity check
was omitted. Three owned temporary build volumes were removed.

Signed-in Chrome showed Resume on the existing analysis. A single new public chat
continuation caused the Assistant to call `resume_analysis` (event
`sevt_01WVF3y3N4GudM2qAw6nLc8X`). All eight original unstarted run IDs now have
recovery audit rows and identical frozen-input hashes. Six subsequently finished
native execution with exit status zero; two were still queued/preparing at this
observation. The same analysis returned to calculating and admitted further points.
No replacement analysis, manual database edit, accuracy relaxation or reset occurred.
The study's final answer and validated exploration remain pending normal completion.

Private evidence: `/private/tmp/hyprn-prelaunch-recovery-release/`
(`live-recovery-proof.json`, `child-progress-verified.json`,
`scientific-resumed-public.json`, `deployment-preservation.json`,
`resume-tool-proof.json`) and
`/private/tmp/hyprn-prelaunch-recovery-deploy/packet-1/application-evidence/`.
Ongoing named-user access promotion completed successfully under the existing
approved policy. A later read confirms all eight recovered original runs finished
with native exit status zero; see `child-progress-final.json`. The public page
shows Calculating points and the Assistant Waiting for calculations; screenshot
`live-recovery.png` records that state. Full qualification,
scientific acceptance and human acceptance are not claimed by this focused delivery.
