# Linux build preparation

This is build evidence, not a staged application or an installed-artifact pass.
No live installation, secret or cloud VM was changed.

- Application wheel portability: `31cd698` adds the existing Pydantic Core 2.50.0
  and rpds-py 2026.9.1 Linux amd64 hashes already in uv.lock. Official PyPI byte
  hashes and embedded MIT licences were checked before installation; inventory
  is in application/dependency-pins.json. No dependency version changed.
- The first cloud amd64 image build on `65e5411` failed its required hash check
  because the application lock admitted Mac/arm64 wheels only. The build on
  `31cd698` succeeded. Its Linux amd64 image index is
  `sha256:a9ed9287a612bd2948ddca8222c91736e76d276e9e81f52b9fd3a653f935bf28`,
  application manifest
  `sha256:1eacda92bb5cf261d850936d017bccd6afcc3eaf367a4dce3561386ff6866f08`.
  Actual unprivileged UID10002 imports of cloud ASGI/database CLI, dispatcher,
  pg8000, JWT and cryptography passed with network disabled and no secrets/stores.
  Built UI index exists. This does not establish startup/database/provider use.
- Native packaging helper `12c9f5b` and fixes `ef38efb`, `a625fdf` reject external
  links, cycles, special files, existing output, extraction tampering and relocation.
  Registered hosted-native-bundle: six tests passed; latest 0.116 seconds group
  duration. The complete Linux preparation/extraction remains unfinished.
- First native attempt failed on case-insensitive Mac-backed mount: Linux
  terminfo aliases collided. Its full source argument was also mistyped; no
  result is admitted from this attempt. Later invocations derive it with Git.
  A labelled disposable Linux Docker volume replaces that build mount. An early
  filesystem refusal prevents recurrence; archive safety was not weakened.
- Second attempt found that standalone archive bytes lack uv's BUILD installation
  marker. `a625fdf` records that marker from the already SHA-verified archive pin.
- Third attempt reached the native package audit and refused the new PostgreSQL
  migration SQL assets. Native executor owns the narrow wheel-data allowlist fix
  and real wheel inclusion proof; no broad file admission was substituted.
- `a46c943` regenerates native-host.txt with pinned uv export from unchanged
  uv.lock. The only addition is the already declared/audited PyJWT2.15.1 package.
  This changes native environment identity and requires a new artifact/attestation.

All native attempts above exited; no application/AiiDA store was initialized.
The isolated Linux build volume/cache is retained temporarily for the continuation;
failed scopes are never promoted into a release. Final source, worker inventory,
regular-file archive, fresh extraction and scientific tests remain required.
Parent owns these build operations; native executor owns native runtime integration.

## Native source and Linux preparation checkpoint

Source `44b87a0` passed parent acceptance through `./hyprn-mvp dev check GROUP`
with the reviewed development environment. All nine commands exited zero:
cloud-execution-config 5, hosted-native-owner 3, native-environment 19,
hosted-lifecycle 18, bridge-history 139, release 28, deployment-hardening 76,
locality-contracts 165 and hosted-native-bundle 6 (459 total). Logs use
`/private/tmp/hyprn-native-parent-GROUP.log`; runner scopes were released.
The last locality check overlapped the next narrow build-helper edits; those
edits do not change the import-boundary contract. The affected build/config and
native-environment checks will be repeated on their committed correction.

Actual Linux amd64 preparation at exact source `44b87a03e766d9d4665d4e27d79ec1014e3e578f`
now exits zero. Native lock is
`7beef37f4d3e0bf92a524e6c4abc56b4206fb1c3e294fcd93bde0e1047e2b434`.
This includes the reviewed interpreter, dependencies and project wheels; it
does not include the worker yet. Its source snapshot was a selected package
subset, so it is build evidence only: final preparation must use the complete
source closure including upstream/modeling files. Log:
`/private/tmp/hyprn-native-build-44b87a0/prepare.log`. Container removed on exit.

Parent inspection before the engine build found two target-selection errors:
a staging path shadowed the platform argument, and the final input comparison
omitted the platform. The native executor owns the narrow correction and a
command-construction/cache-identity test. Worker notice export is also being
separated from local-installation binding so cloud packaging does not fabricate
a local release or initialize a profile.

## Linux artifact and replacement checkpoint — 2026-10-21

- `55b6429` fixes explicit engine target selection and provides worker-only notice
  export without initializing a profile. Parent configuration 6 and native
  environment 26 checks passed on that committed delta.
- `e7ee14f` admits four audited Linux amd64 wheels for the existing worker versions;
  no version changed. Official PyPI metadata, exact bytes and embedded notices
  were checked. Worker lock digest is
  `a74350573571cc4647ab9dbdca53b173c2a04daee5cb1735b9dfb3fb162de584`.
- Real engine `sha256:ec5c47f9ef6d0237a013fefa2eae5460814cdff48a0856a807096ebff1e8d712`
  and worker `sha256:dd7c0acd4e09783168dbf3ea9e1c16d1dbada461bd72f014446bb9b90eaf3257`
  built for amd64. Restricted, offline, readonly UID65534 imports of OpenMDAO,
  NumPy and SciPy passed. No candidate or store was executed/initialized.
- The e7ee14f native archive contains 20,826 regular files, 229,186,387 bytes,
  SHA-256 `26593273b964db02f4e164427309f0063eab8425ae9c676095890f84e5999245`.
  Platform bundle validation passed. Independent Linux-volume extraction at its
  exact prefix passed every file hash and actual CPython 3.12.15/AiiDA/scalar
  plugin imports with no build-cache or checkout mount. This older artifact is
  preparation evidence, not the final integrated release.
- Fresh-extraction failures were retained: AiiDA tried to create configuration
  in readonly HOME; direct wheel import lacked the released contract layout;
  Python 3.12 EntryPoints rejected integer indexing. Verifier corrections
  `b747458`, `a14fd17`, `8496606` isolate import side effects in temporary HOME,
  use only the bundled source as the real bootstrap does, and load the selected
  entry point through iteration. The final actual extracted proof exited zero.
  Logs: `/private/tmp/hyprn-native-build-e7ee14f/verify-extracted*.log`.
- `2d26093` adds explicit target handling to modeling source/runtime builds.
  Parent upstream 32, bundle 7, hardening 76 checks passed. Real amd64 modeling
  image `sha256:cfb49e197e7694f2e2b3498157174acc753c7fe63a058687b38680da38e84d78`
  built; its scoped resources were released, no service/store started. Evidence:
  `/private/tmp/hyprn-modeling-build-2d26093/build/evidence/`.
- Rebind source `784bbf9`: parent native-owner 12, hosted-lifecycle 18,
  configuration 6 and locality 165 checks passed (201 total). The default 10 GiB
  build-cache guard refused lifecycle before running; active/shared layers were
  preserved. Only the refused remaining groups resumed with a bounded temporary
  16 GiB allowance, after confirming disk capacity. Logs use
  `/private/tmp/hyprn-rebind-parent-*`. No checks were silently skipped.

Current native build source is `8496606dc9d359f5c171a7206c08d80d8cbc4c16`.
Its complete snapshot and refreshed worker inventory are isolated under
`/private/tmp/hyprn-native-build-8496606/`; preparation passed. Parent owns packaging
and exact artifact handoff. Native executor owns installed Linux fixtures and
real native behavior. The installed full application/PG/dispatcher journey,
containment attestation, replacement proof and platform reconciler remain open.
VM remains stopped. No further provider request, secret transfer or live-store
mutation occurred in this batch.

## Exported image identity correction

Actual platform-specific OCI export of the 8496606 worker exposed a portability
problem: the runtime named the BuildKit index, while the offline archive contained
its runnable platform manifest. `a94ed85` selects the explicit platform identity;
its first actual build then failed because that child was not independently
registered for tagging. `ffe2ef4` makes explicit-platform worker builds emit one
runnable image and includes that artifact choice in cache identity. Default local
builds are unchanged. Release provenance remains a separate recorded artifact.
The worker's Python/numerical source and dependency versions did not change.

The corrected committed source passed configuration 7 and native-environment 26
checks (33 total). The new native archive is source
`ffe2ef468be08584e483bc76e2321866e634ba8c`, 20,828 files, 229,203,240 bytes,
SHA-256 `717d9f764fbc4b85e04b140cb82a92787c93f641269938744a22b88ea5669406`.
Its runtime worker pin exactly matches the exported OCI manifest:
`sha256:2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`.
All referenced OCI configuration/layer bytes and the target architecture passed
verification. Worker archive SHA-256:
`36f2e16625bbce30e72c5c3709806a7bcca7a953c4fa12c2fec04e8b810f451a`.
Evidence is under `/private/tmp/hyprn-native-build-portable/`.

The 8496606 application archive independently passed complete OCI verification:
manifest `sha256:75574b3895624a61ff877d0237b94e099eda2732952713faa524c2ff6a3a6774`,
archive SHA-256 `bb2a0cded90e9720dbc85ac22b1ce7e989fcaafbfd51ff34ab53d5364e5f9abd`.
Modeling archive manifest is
`sha256:fc4c6fa692effd856f783e1f7082a16653244c20348a2191b2f743fae928e9b9`,
archive SHA-256 `d801107a46bf3f169991a3e094c254ce37e3e55ea2ecb752b3daa77ce770a359`.
These archives are isolated build evidence, not a published release descriptor.

Native executor already proved real initialization/inspect/reinitialize refusal
on the 8496606 extracted bundle (one test, 42.678 seconds), releasing its scoped
volumes/containers. It now owns real attestation/calculation/restart proof on the
portable bundle. The earlier e7ee14f verification volume was removed after its
label and absence of containers were checked. Only the owned build volume/cache
is retained for continued release assembly; no unrelated resource was stopped.

Portable-bundle installed rehearsal subsequently reached real native
initialization but containment attestation refused execution; no candidate
calculation was launched. Log:
`/private/tmp/hyprn-native-installed-calculation.log` (217.642 seconds).
The original fixture owner cap was 0.25 CPU under amd64 emulation and was raised
to 1 CPU after initialization; this development observation is not final
committed-fixture acceptance. The executor is retaining bounded probe diagnostics
and using 1 CPU from startup for the next isolated run. Production worker limits
and attestation conditions remain unchanged. Both fixture volumes and containers
were released. Scientific readiness remains unverified until the refusal is
understood and corrected without weakening containment.

The bounded diagnostic rerun (58.049 seconds) identified the refusal: all real
containment cases satisfied their conditions, including OOM, network/filesystem
isolation, resource limits, concurrent isolation and worker-source hashes. Docker
Desktop's arm64 host prepended an amd64 platform-warning line to worker output;
strict JSON decoding therefore refused attestation. The fixture now explicitly
sets its already-verified Linux amd64 target via DOCKER_DEFAULT_PLATFORM. No
output is filtered and no production attestation condition or limit is changed.
The executor retains the failed containment report and will rerun real execution
with that fixture correction before claiming scientific readiness.

## Installed rehearsal assembly and host prerequisites

Explicit AMD64 selection made containment pass with every access probe and
worker import hash satisfied. The subsequent actual AiiDA calculation finished
with exit 300 and empty retrieved result/launcher diagnostics; its direct
scheduler reported `ps: command not found`. The minimal Python fixture host lacks
that real OS prerequisite. No production code, scientific output, attestation
parser or worker limit was relaxed. The native executor is reusing the already
reviewed modeling image solely as the isolated owner host (entrypoint replaced
with the extracted native Python controller); no Rails service starts and no
LGPL utility is copied into the product. Exact modeling platform manifest remains
`fc4c6fa692effd856f783e1f7082a16653244c20348a2191b2f743fae928e9b9`.
The bounded failures and cleanup are retained in the executor's evidence.

The parent assembled a **local rehearsal only** descriptor at
`/private/tmp/hyprn-installed-release-rehearsal/`. It pins the actual portable
native bundle, OCI manifests and built UI listed above. Complete OCI blob/hash,
native bundle and pinned platform document checks passed. Release digest:
`440f7938e31eac3e72c2c6cd9a5eba06ee5022ca23b3e8ca328442028f46d6ac`.
Its runtime uses explicitly synthetic isolated-test identities, no live secrets.
`purpose.json`, tests and provenance declare publication forbidden and installed
qualification incomplete. Existing source checks are retained honestly; the
preliminary SBOM/notices/source records are not a completed distribution review.
This descriptor enables the packaged app/PostgreSQL fixture without pretending
that a source-only check or copied fixture is a working hosted installation.

The lifecycle executor owns the exact packaged app/database HTTP slice, including
private-study isolation and restart. Full aggregate host installation/replacement,
backup/restore and final publication evidence remain open. VM and live stores are
unchanged. No provider conversation was started.

## Linux execution corrections under final rebuild

The host-utility corrected test reached the actual restricted worker, which
refused `/input/manifest.json` with PermissionError. `fa8272c` fixes only the
verified AiiDA working copy's access modes: exact listed regular files 0444,
owned directories through the input root 0755. Links and foreign ownership are
refused before mutation; private ancestors and stored scientific records remain
unchanged. Parent committed acceptance: cloud-execution-config **10 passed**
(0.144 s; `/private/tmp/hyprn-input-permissions-parent.log`).

`18d872a` additionally checks the real host's bash/ps/tail/whoami before native
initialization, attestation, launch, admission and rebind. A missing scheduler
utility now refuses before mutation; ordinary historical inspection stays
available. Parent committed acceptance: hosted-native-owner **15 passed**
(9.253 s; `/private/tmp/hyprn-host-prerequisites-parent.log`).

The next immutable native source is
`18d872aba952dffa946bf1fec6062ecce59d2ebf`, assembled under
`/private/tmp/hyprn-native-build-readable/`. All 446 application Docker copy/build
inputs are byte-identical to the already built 8496606 application snapshot;
`application-reuse-proof.json` records this comparison. Native/worker fingerprints
must be rebuilt and re-attested; the previous installed descriptor remains stale
and must not be silently reused.

The first full packaged app slice has reached actual TLS PostgreSQL initialization
and preserved refusals for reinitialization/foreign identity. Its HTTPS readiness
check could not reach a host-published port on Docker's internal-only network.
The known failed fixture was interrupted after 355.223 s (child exit -2, runner
254), with no claimed pass; all labeled containers, volumes and networks were
confirmed removed. The executor is moving the HTTPS client inside the same
isolated network and adding a monotonic readiness deadline. TLS, authentication,
application code and database behavior are unchanged. No cloud activation.

## Committed installed native acceptance

The `18d872a` rebuild completed with native archive SHA-256
`76f4946d5b10a573f666ab915e1623b1a91e7f16dc285dbc0a3444f512fcfbe5`
(229,220,760 bytes; 20,834 files). The worker image remains
`2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`.
Parent `hosted-native-installed` acceptance passed **1 test in 107.771 s**,
exit 0, using `/private/tmp/hyprn-installed-native-readable-input.json`.
Actual outputs were 49 and 7; restart preserved the recorded result, a duplicate
request was refused, and all restricted-worker attestation probes passed.
This is the real installed native journey, not an application or aggregate-host pass.
See [native checkpoint](06-05-NATIVE-CHECKPOINT.md) for identities and cleanup.

The log is `/private/tmp/hyprn-installed-native-readable-parent.log`; retained
evidence is under check session `2a124215-c5e7-4c51-97d0-6724cc8ef0ac`, fixture
`c94ceef5-4681-479e-bd87-1c230a5bbfdb`. The runner moved evidence from its printed
temporary fixture path into the check session before releasing scratch resources.
All fixture containers, volumes and workers are removed. No identical rerun is needed.

Packaged application fixture `c3c9442` failed sign-in with HTTP 403 after actual
TLS/database readiness (36.452 s). The fixture's Host/Origin was corrected to the
declared ingress authority in `68418b1`, preserving an explicit wrong-host refusal.
Parent acceptance on that commit failed with a bounded HTTPS client error at
sign-in (36.430 s): `/private/tmp/hyprn-installed-app-parent-host.log`, retained
check session `b0b967de-e81d-4743-9aed-3fe50cccb054`. The fixture currently obscures
the transport cause; the executor owns a narrow diagnostic correction before
the next run. No production authentication/TLS relaxation or successful app
journey is claimed. Full lifecycle, coherent backup/restore, platform reconciliation,
publication and live acceptance remain open.

## Packaged sign-in correction

The diagnostic run on fixture `33fffeb` proved a read timeout (39.230 s).
Source inspection and a bounded real PostgreSQL regression established the
production cause: external-session creation took transaction lock 68272602,
already held for the application's lifetime by its writer lease. This was a
real packaged sign-in defect, not a reason to increase the timeout.

`a1dec2e16084bb8b38257c1cca3b7544cac43179` adds explicit migration
`0005_session_lock.sql`, moving only session serialization to unused key 68272605.
Earlier migrations and the application/dispatcher writer fences remain unchanged.
The new schema identity refuses an older incompatible app; no rolling mixed-schema
exception was introduced. Parent acceptance passed hosted-lifecycle **19 tests
in 8.426 s** and hosted-identity **90 tests in 11.89 s**. Logs:
`/private/tmp/hyprn-session-lock-parent.log` and
`/private/tmp/hyprn-session-lock-identity-parent.log`.

Rebuilt immutable source and artifacts are in
`/private/tmp/hyprn-app-build-session-lock/`:

- App manifest: `2f049a082ef22caa838b1af226b116dc7bea2e48d3290c43bf7c4deafe5543cb`.
- App archive: `db17c7f6218ac1bf77ca02edb7b548e642a437b36535e7ac8bb70844b7c2d2f0`,
  91,181,056 bytes; full OCI graph verified.
- Native archive: `7210cd22822cb2741f1fa7c0017f905b322cc26d8c7123862d7d23e1e10987fb`,
  229,246,157 bytes; 20,839 files at the new exact source prefix.
- All recorded worker source hashes remain identical; the reviewed worker assets
  were reused only after checking each input and the packager's own checks.
  No native execution regression is inferred from the unrelated session migration.

New local-only rehearsal descriptor
`/private/tmp/hyprn-installed-release-session-lock/` has release hash
`827daa1c4dd8646766e4e03761668f790168e0d7cd09a15eae4e6b6399675e06`.
It remains explicitly ineligible for publication. The installed run progressed
through actual HTTPS sign-in, two-user private study writes/reads/denial, UI assets
and admission failure checks. It then failed at a fixture mount-path error before
schema/refusal/restart verification (56.563 s). No full pass is claimed; the
fixture owner is correcting the shadowed path variable. Existing artifact bytes
do not change for that fixture-only fix.


## Committed packaged app and owner-backup acceptance

Fixture-only correction `4fc9ab3c1ca1ee57f0e60745169045ffda0c183c` removes the
shadowed mount variable. Parent `hosted-app-installed` passed **1 test in 56.591 s**,
exit 0, on the unchanged a1dec2e artifacts above. This proves HTTPS sign-in,
two-user study create/read and cross-user denial, served UI, admission refusals,
schema compatibility and restart preservation through the installed application.
Log: `/private/tmp/hyprn-installed-app-final-parent.log`; check session
`e7888ed5-07d2-4569-ab66-ae31d39f5dbb`, fixture
`d927e4ed-40b6-4a6b-b743-c9d75033579d`. Provider/JWKS boundaries are isolated
HTTP fixtures; this does not establish real Cloudflare or Assistant operation.
See [installed app checkpoint](06-05-INSTALLED-APP-CHECKPOINT.md).

Owner-file snapshot/restore foundation `661c8b858da9474b57078400a414933265541c0b`
passed parent `hosted-backup`: **9 tests in 2.217 s**, exit 0. The real pinned
AiiDA and SQLite checks cover retained UUIDs, object content, WAL data, locks,
corruption and interrupted restore. Log: `/private/tmp/hyprn-backup-parent.log`;
check session `0244fab2-ec16-41fc-b421-f4c0bd9a03ae`, fixture
`c8644946-37ca-4fa4-b5d5-cec9526fcee5`. No Docker or cloud operations were used.
See [backup checkpoint](06-05-BACKUP-CHECKPOINT.md). PostgreSQL remains explicitly
excluded and `coherent_backup` false; lifecycle backup/restore remains disabled.

Next is the cross-store Cloud SQL recovery choice and full Linux host integration.
These focused successes do not satisfy the aggregate artifact publication gate,
complete legal/source delivery, branch automation or live/human acceptance.
