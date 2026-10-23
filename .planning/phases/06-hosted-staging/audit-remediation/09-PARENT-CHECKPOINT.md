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
