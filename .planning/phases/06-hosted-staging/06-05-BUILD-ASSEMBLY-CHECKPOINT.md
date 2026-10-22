# Cloud release assembly preparation

2026-10-21. Code-only preparation; no publication or cloud mutation.

The new `deployment/cloud_build.py` snapshots an exact Git commit, builds and
verifies its AMD64 cloud application image, and freezes an explicitly supplied
release/runtime/desired/workload plus payload files. It preserves supplied
evidence verbatim and never invents qualification. Native assembly continues to
use `cloud_native_bundle.py`. Commands and remaining inputs are documented in
`deployment/cloud-build.md`.

## Verification

With the configured development tool/data roots:

- `./hyprn-mvp dev check hosted-native-bundle`: 7 passed, 0.017 s. The first
  registration attempt did not discover new build tests; this was identified and
  corrected by adding a dedicated group, not counted as coverage of new code.
- `./hyprn-mvp dev check hosted-cloud-build`: 8 passed, 0.857 s; exit 0.
  Check identity `96012fc7-9b56-4021-bc6b-8c524d98f821`, scope
  `e99205a4-0125-4efa-ac32-d85810f0359f`. Scoped files were released by the runner.
  This covers source isolation/tamper refusal and evidence byte preservation.
  OCI/native verification in the new payload unit test is stubbed; actual full
  payload acceptance remains required on the final bytes.
- First attempt was refused by sandbox access to the existing tool cache before
  any tests. The authorized pinned-cache rerun passed; no cache was modified
  manually.
- Existing modeling and worker archives were checked with the real
  `cloud_release.verify_oci` graph verifier, without loading/executing images.
  `/private/tmp/hyprn-release-reuse-verified.json` records actual hashes and sizes.
  All 54 recorded worker source inputs still match the current product source.

After initial commit `d51c06be3f90e15eae041d0a9a500b7e70a1163a`, an actual CLI
snapshot exposed the operator's Python 3.9 lacking `tarfile` extraction filters.
The helper now copies admitted regular Git entries explicitly, without applying
archive ownership or link metadata. Rerun `hosted-cloud-build`: 8 passed,
0.905 s, check `0d36ffa3-9aac-4d11-85f7-e6034a2c3892`. The real snapshot of that
commit succeeded in `/private/tmp/hyprn-build-assembly-smoke-d51c06b-v2`, source
record SHA256 `7d3fa78a2b974a82a616ffd381f5a15f1fe5580a5f8ffb7012d1536edf893c48`.
The failed first attempt remains separate; no Docker build or external publication
was attempted by either smoke check.

Modeling OCI: manifest `fc4c6fa692effd856f783e1f7082a16653244c20348a2191b2f743fae928e9b9`,
archive `d801107a46bf3f169991a3e094c254ce37e3e55ea2ecb752b3daa77ce770a359`,
500301824 bytes. Worker OCI: manifest
`2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`,
archive `36f2e16625bbce30e72c5c3709806a7bcca7a953c4fa12c2fec04e8b810f451a`,
168793088 bytes. Recheck input equivalence at final source selection.

## Remaining work and limits

Parent owns the test-group registration, final platform-contract pin, final
product commit, actual AMD64 app/native build, real runtime descriptors and
installation review. No heavy Docker build was started in this task. The current
rehearsal descriptors contain synthetic identities and incomplete publication
evidence; they must not be reused as a staging release.

Release evidence hashes can bind factual build records with runtime acceptance
explicitly pending. The existing `hosted-artifact` check deliberately fails until
aggregate native/application lifecycle and trusted admission are demonstrated.
Do not replace that failure with a fabricated acceptance field or receipt.

## Actual staging payload assembled — 2026-10-21

The preparation-only paragraph above is superseded for build and descriptor
assembly. Deployment and runtime acceptance remain open.

Product `ac1fe308b7936e951c90caf0de6a60cd0d0ccb33` pins platform contract
`2a3cc534ac1e044ecb15c327b37f97cc77293323`. The pin's consumer checks passed:
`hosted-lifecycle` 21 tests, 15.842 s, check
`c6a22565-efcb-4bf9-82ff-302b9b829d25`; `cloud-execution-config` 16 tests,
0.145 s, check `4a60f2ef-f402-4781-936a-9df759a8c584`.
The lifecycle group's first attempt refused before tests because the shared
Docker cache exceeded 10 GiB; an explicit 20 GiB allowance permitted the rerun
without deleting active/shared image layers. Scoped PostgreSQL files/containers
were released by the test runner.

Actual build root: `/private/tmp/hyprn-staging-build-ac1fe30`. The app was built
from its exact committed snapshot; native preparation used isolated AMD64
containers, two CPUs and 3 GiB, with no credentials, Docker socket or live stores
mounted. Native prepare, worker attachment, pack and fresh extraction/import
verification all exited zero. The fresh extraction uses the exact final prefix
`/srv/hyprn/staging/releases/ac1fe308b7936e951c90caf0de6a60cd0d0ccb33`.

- App manifest: `b100ee82f5e02115030e7cabadb76edd0f87b68471bf6bbc1403cf425f11f55a`.
  OCI archive: `46acc0d8474399c3880e541dd6f9178d9b8482210ae9fee835c537ed6bda28e4`,
  91181568 bytes; full OCI graph verified.
- Native archive: `9f3099ecf995d967f67576164ae99a41483cee6b88e1954a353ccb941eedcf3d`,
  229276902 bytes, 20853 files, actual CPython 3.12.15/AiiDA imports passed.
- Modeling and worker reuse retains the verified manifests above. All 54 recorded
  source inputs match the frozen source; each archive was verified again.
- Eight UI assets were extracted from the stopped app image; their bytes equal
  the previous UI. New canonical manifest:
  `78ffb3fa53dd5ea85d1fe9001ffef2f00b0086b55147b0a15b3661962bd20a61`.
  Its JSON equals the prior manifest; the prior file had a trailing newline.
- The built app's offline `managed_assistant.definition` exactly equals the
  reviewed provider plan, including tools, playbook and subagent settings.
  No provider request or model execution occurred. Thirty-seven installed app
  Python distributions and their retained notice files were inventoried; the
  excluded `_dbm` extension is absent.
- Matching modeling corresponding source was extracted from the stopped image;
  its upstream archive and ordered patches match their recorded source hashes.
  Native/worker notice records were read from the actual native archive.

Actual descriptors are in `/private/tmp/hyprn-staging-final-plan`, using the
parent-supplied actual runtime rather than fixture identities. Release digest
`62e216ca44884eb96868b2210c11c08e3dc28371d3a150179641f12a2f0b4b0f`,
config `87260647f735dafffe0f771a5bdfb396d35167fb27089cbf7740a6968e6650d8`,
desired `89edb18a300ff896339285b90a3c36605e3a0d63afd34596acbfc4376e140cf3`.
`cloud_build.py payload` copied and fully verified the complete payload at
`/private/tmp/hyprn-staging-payload-ac1fe30`; inventory digest
`8e4886c567601f6468335f4857859f33f9427e93cb56f48c7a9ad9ba5005bfa4`.
Evidence explicitly marks runtime acceptance pending and internal staging scope;
neither commercial legal clearance nor live execution qualification is claimed.

No build containers remain (verified by the exact build label). Dedicated native,
cache and verification volumes remain for inspection, named
`hyprn-staging-build-ac1fe308b793-{native,cache,verify}`. Parent owns their eventual
scoped removal after review. No unrelated Docker resources were removed by this
build. This later checkpoint is documentation only; frozen product source remains
`ac1fe308b7936e951c90caf0de6a60cd0d0ccb33`.


## Corrected database deployment payload — 2026-10-21

Supersedes the earlier payload identities for the next reviewed deployment only.
Platform8af657a permits an explicit safe database name and uses Google's exact
absolute TLS hostname. Product3744603 changes the consumer pin only; product behavior
and all three runtime image manifest digests remain unchanged. Actual native bundle
was rebuilt from the exact Git snapshot at its3744603 installation prefix, and fresh
extraction/import/source comparison passed. No installed execution qualification is
claimed. Evidence: `/private/tmp/hyprn-staging-build-3744603`; verified payload:
`/private/tmp/hyprn-staging-payload-3744603`. Source/archive hashes remain in its actual
payload inventory, not inferred from test fixtures.

Final `./hyprn-mvp dev check hosted-lifecycle`:21passed,21.622s,
checkda13d781-dad0-4f2b-95ed-9b248f6eb50b. `cloud-execution-config`:16passed on4d0c727,
0.168s; final delta is database-name schema/pin only. Build-helper8 retained unchanged.
Initial platform fixture-pin mismatch was fixed and contracts passed; final safe-name
schema test makes25passed. Full logs/limits are in the correction packet EVIDENCE.md.

Release839a67dc216d20d301e71093b4de9e604901644293f9c156147747023b70c46e.
Correction review `/private/tmp/hyprn-staging-database-correction/REVIEW.md`,
approval SHA6e474f7755de53f07f2362eab83e4d5cde1d9f09f1938cb1db9ca265068e8461.
Prepared, not applied. Original user-type fix was approved/applied, then real CloudSQL
reads established exact TLS SAN and actual empty hyprn database. No application roles,
runtime credential versions or product processes have been created yet. Preserve
original temporary password/receipts. Current operational next action is recorded in
the platform08-FIRST-DEPLOYMENT-CHECKPOINT.md. No unrelated changes staged; no check
rerun merely for these checkpoint records. Own build volumes retained for review.
