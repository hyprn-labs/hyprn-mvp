# Historical execution and hosted test guard integration

## Changes

Historical execution reads now exercise the authoritative merged run projection
while separately asserting immutable submission bytes. The source-disappearance
fixture preserves captured producer bytes and constructs an explicitly historical
configuration with fresh identities and the captured authenticated catalogue.
Real assembly must succeed before fault injection; deleted native sources and
uncertain launches still forbid redispatch.

Module/import guards retain exact inventories, including current monetary schemas,
attested modeling source count, and fixed identity-field reads used to protect file
permission changes. The generated execution root closure is parent-owned; its exact
membership is inferred from runtime source references and tested, not loosened.

Hosted test modules explicitly install unit or baseline live-installation fences.
The four artifact-dependent opt-in modules have exact group declarations; all other
tracked Python tests still need required qualification coverage or explicit retirement.
The cross-repository backup suite installs its hooks on the loaded test module so
unittest actually executes them. Missing hosted artifact inputs are checked before
scratch allocation. An empty ambient live-port list is no longer a fixture assumption.

## Prior failures retained

- bridge-history: 135 passed / 6 failed before observation-double/history migration.
- bridge-history: 139 passed / 2 failed; upfront real assembly exposed mixed catalogue
  provenance, not a production admission bug (75.90 s).
- bridge-history: 139 passed / 2 failed; historical catalogue on current authoring was
  correctly rejected (65.70 s). Replaced with explicit historical fixture, no producer
  bytes or authoring checks changed.
- locality-contracts: 161 passed / 4 failed (11.09 s): fixed identity-field getattr
  inventory; C3 owner-private access corrected through narrow public owner methods;
  parent corrected exact execution schema roots and monetary closure.
- guard: 117 tests, 13 failures / 1 error (3.393 s): missing fence declarations,
  outdated opt-in registry, and ambient empty live-port fixture.

## Current evidence

Commands used the pinned `./hyprn-mvp dev check` launcher with the reviewed external
data/tool roots and a 20 GiB test-build cache. All reported scoped cleanup exit 0.

| Group | Result | Seconds | Storage scope |
|---|---:|---:|---|
| bridge-history | 141 passed | 85.19 | d90d7560-cffc-4a23-b72a-39375bbf19dd |
| locality-contracts | 165 passed | 11.60 | 7ad1dda5-b871-437e-8f77-5504fe3c1097 |
| guard | 118 passed | 3.472 | 1b3698f3-cb37-45e3-8abc-de232c95bd15 |

Before the runner fix, the new allocation regression produced exactly four failing
subtests in 118 tests (3.563 s). All prior guard failures were already corrected.
No actual scratch scope was allocated by those regression cases: allocation is spied
with a mock while proving it was wrongly reached. The extraction moves the existing
artifact validation ahead of allocation and keeps values and destinations unchanged.

Commits: `5556a9a4` (historical fixture), `2fbf7993` (exact module/import guards).
C3's owner-seam fix and parent's exact 46-root execution schema closure were present.
Checks ran on the shared integration tree; these commits stage owned files/hunks only.

Raw logs: `/private/tmp/hyprn-history-final.log`, `/private/tmp/hyprn-locality-final.log`,
`/private/tmp/hyprn-guard-final.log`, `/private/tmp/hyprn-hosted-prerequisite-red.log`.

## Hosted fence acceptance on the committed delta

Runner/fence changes are committed as `ac5917a3`. The affected groups ran serially
through `./hyprn-mvp dev check <group>`, with the same reviewed data/tools roots and
`HYPRN_PLATFORM_ROOT=/private/tmp/hyprn-staging-platform-runtime-492eeb2` for the
cross-repository fixture. Every group exited 0 with its own released scope.

| Group | Passed | Seconds | Storage scope |
|---|---:|---:|---|

| hosted-cloud-build | 8 | 0.902 | 14ae4ee3-8a27-425f-a94e-bf753d3ee8af |
| cloud-execution-config | 17 | 0.150 | 8d410a00-ea65-44df-8f22-3843c547faf5 |
| hosted-native-bundle | 7 | 0.016 | 482a70c8-6b2c-4a66-bb6c-064775719b41 |
| hosted-native-owner | 21 | 15.623 | e8b685ad-c5a8-4ee2-bfa0-d0bb75e1c4d1 |
| hosted-backup | 9 | 2.374 | 3b835bd1-1348-4a55-a724-bb7e0d231f76 |
| hosted-lifecycle | 25 | 19.873 | 083ffa7c-638c-4942-9a57-70cf1b43d335 |
| hosted-owner-schemas | 9 | 389.581 | a62f3146-c014-4f20-858f-1dbf905831b4 |
| platform-backup-set | 16 | 19.146 | c0500188-4cbc-47f0-ac18-24da588c1fce |
| locality-contracts | 165 | 12.42 | 19b2d1ed-b92d-4baf-ad9f-fe1b79f848ef |

Logs are `/private/tmp/hyprn-fence-<group>.log`. Owner-schema acceptance built a real
isolated modeling image and exercised its migration ledger; its legacy Docker build
dominated the 389.581-second group duration. No fence policy was relaxed to pass.
The final locality run was necessary because the parent regenerated schemas and C3
added reviewed monetary export imports after the first passing run. Commit `59754209`
contains those two exact import edges and the authorized interpretation-spec link.
All source/tests are stable; the test lane was handed directly to C3. No owned test
process remains and no scientific record, installation or cloud state was mutated.

## Remaining acceptance and linked platform work

Installed-artifact groups `hosted-native-installed`, `hosted-app-installed` and
`hosted-artifact` need the final reviewed release descriptors; their full journeys
were not rerun here. Registry/fence declarations are not proof of those journeys.
The deployment parent owns final release qualification, those artifact checks and
live staging verification. No release-complete claim is made by this checkpoint.

Platform F17 retention is documented in
`hyprn-platform/.planning/phases/08-product-staging/08-F17-RETENTION-CHECKPOINT.md`.
Offline packet `/private/tmp/hyprn-retention-activation/REVIEW.md` verifies retained
host/deployment identity and pins the five imported retention sources from the same
immutable platform snapshot `492eeb2`. Final retention plan digest:
`46a5aba739d15588bd8beaa5844d92d85f552bede04d8992b590712acb2235ed`.
Source-manifest correction `31f42b1` was red at 5 pass / 1 fail, then 6 pass
(0.375 seconds); documentation commit `492eeb2` records the exact packet. No apply
was performed. Parent owns the explicit activation step and remote evidence.
