# 06-05 installed application continuation

Status: incomplete; no release publication, host qualification or cloud activation.

## Scope and source

`ccb9464` registers `hosted-app-installed` and commits the image-side fixture,
isolated Docker/PostgreSQL orchestration and focused installed application test.
The aggregate `hosted-artifact` invokes this journey but still fails explicitly
until the whole host lifecycle and native integration are proven. Its helper
import landed in the earlier shared fixture handoff `a31439e`.

Only external provider and JWKS HTTP transports are synthetic. The fixture runs
the installed cloud factory, TLS PostgreSQL, public HTTPS API, authentication,
admission, persistence and packaged UI. It sends no model requests. Synthetic
prior spend is explicitly zero for the fixture's enumerated empty provider;
it is not a claim about staging's real allowance or retained sessions.

The app image manifest is
`75574b3895624a61ff877d0237b94e099eda2732952713faa524c2ff6a3a6774`,
Linux/amd64. Its archive SHA is
`bb2a0cded90e9720dbc85ac22b1ce7e989fcaafbfd51ff34ab53d5364e5f9abd`.
The input release SHA is
`440f7938e31eac3e72c2c6cd9a5eba06ee5022ca23b3e8ca328442028f46d6ac`,
with source `ffe2ef468be08584e483bc76e2321866e634ba8c` and pinned platform
contract `231bad2e62849f433e118a3dc21e356b48125e28`.
Parent verified all 446 application build inputs match the built image's
`8496606` source, including the later native-only source `18d872a`.
The supplied release evidence is explicitly unpublished and incompletely
qualified; its existence does not establish an installed release pass.

## Registered development checks and failures

Command: source the private development environment and six explicit artifact
input paths, set the reviewed 16 GiB build-cache budget, then run
`./hyprn-mvp dev check hosted-app-installed --keep-scope`.
No direct test interpreter or source-mounted application was used.

1. Preflight exited 2 before tests: retained build cache exceeded the default
   10 GiB budget. Parent authorized the 16 GiB override; no broad prune occurred.
2. Scope `8434e5e8-6209-46ee-839e-e50dca9c64b7`: one error, 4.248 seconds.
   Docker's containerd store addressed the imported OCI manifest rather than
   its config digest. The fixture now accepts only either identity from the
   verified OCI graph and verifies Linux/amd64.
3. Scope `a5fe66fb-5c3a-4adf-9264-20db762c7c79`: one error, 13.442 seconds.
   The deliberately refused uninitialized app exited without a host port;
   readiness now checks process exit before networking.
4. Scope `a35e2463-0230-4959-bb9c-0888e0615f4c`: one failure, 14.575 seconds.
   The fixture leaf certificate reused its CA subject and failed strict TLS
   verification. Distinct leaf subjects corrected the generated fixture PKI;
   certificate and hostname verification remain enabled.
5. Scope `0a83862f-f37d-4c87-adae-8a09c3d3c5b8`: one interrupted, incomplete
   test; child exit -2, outer exit 254, 355.223 seconds. Explicit initialize,
   repeat-initialize refusal, foreign-store refusal and uninitialized-start
   refusal completed. The first app stayed running, but Docker's internal
   network exposed no requested loopback port, so public HTTP checks were not
   reached. Parent authorized stopping that identified test child after the
   missing-port boundary was established. No passing test count is claimed.
6. Parent acceptance of `c3c9442`, scope
   `a722176f-b33f-4ace-a2e6-ca6210f26470`: one failure, 36.452 seconds
   (group 36.526 seconds), exit 1. Real HTTPS sign-in returned 403. The request
   passed JWT verification but used automatic `Host: application:8000`, while
   the configured external origin was `https://staging.hyprn.ai`. The actual
   application's Host check correctly refused that mismatch. The fixture now
   forwards the configured external authority in Host over the verified
   internal TLS connection, matching the ingress boundary, and asserts a
   different Host remains forbidden. No production or authentication checks
   changed. Parent log: `/private/tmp/hyprn-installed-app-parent.log`.
7. Parent acceptance of `68418b1`, scope
   `1c309c63-7a02-456d-b741-e23128409ad8`: one error, 36.430 seconds
   (group 36.505 seconds), exit 1. External-session POST failed at the HTTPS
   client after readiness. The fixture collapsed DNS, TLS, connection and timeout
   errors into one generic message, and did not retain the first app's log.
   Consequently the evidence cannot identify a production defect or justify
   changing authentication. A narrow diagnostic correction now retains the
   bounded transport reason and app state/logs before cleanup; readiness includes
   its last transport failure in its timeout. Parent log:
   `/private/tmp/hyprn-installed-app-parent-host.log`. No speculative behavior
   fix or independent full Docker rerun was made.
   Inspection found no explicit redirect in the session route or its API
   composition. To avoid urllib hiding an unexpected redirect behind a later
   transport failure, this test client now returns redirects as their actual
   status and headers, including Location in a failed sign-in diagnostic. It
   uses a direct internal connection rather than ambient proxy configuration.
8. Parent diagnostic acceptance of `33fffeb`, scope
   `4aeda4a5-5665-4694-adf2-35bfeaf8ca85`: one error, 39.230 seconds
   (group 39.300 seconds), exit 1. The retained transport reason was a ten-second
   read timeout; the server remained running without an exception. Source
   investigation then found the actual production collision: immutable migration
   `0003_external_identity.sql` used advisory lock 68272602 for session creation,
   while the application writer holds that same lock for its entire lifetime.
   Parent log: `/private/tmp/hyprn-installed-app-parent-diagnostic.log`.
9. Parent accepted the committed lock correction with 19 lifecycle tests and
   90 hosted-identity tests, then rebuilt the exact `a1dec2e` application.
   Its image manifest is
   `2f049a082ef22caa838b1af226b116dc7bea2e48d3290c43bf7c4deafe5543cb`;
   the accompanying native archive SHA is
   `7210cd22822cb2741f1fa7c0017f905b322cc26d8c7123862d7d23e1e10987fb`.
   Descriptor inputs live in `/private/tmp/hyprn-installed-release-session-lock`.
   Installed-app scope `00abf2ee-38d0-449f-adfb-e490736cf682` advanced through
   actual HTTPS sign-in, both private users' studies and cross-user denial,
   packaged UI bytes, scientific admission denial and closed/expired/missing
   controls. It then failed before starting the schema-refusal instance: the
   admission-state loop overwrote the outer `state` variable captured by the
   Docker mount helper, producing `missing/environment.json` instead of the
   owned volume's absolute path. Result: one error, 56.563 seconds (group 56.633
   seconds), exit 1. Parent log:
   `/private/tmp/hyprn-installed-app-session-lock-parent.log`.
   The fixture now gives the volume source and admission state distinct names;
   no application source or artifact rebuild is required for that correction.

For each resource-owning run, fixture cleanup removed its scoped containers,
network and state volume. For the interrupted run, `finally` wrote
`installed-hosted-cleanup.json` with `released: true`; independent exact-label
container, network and volume inventories were empty. Evidence remains in the
runner's retained scratch scope. Unrelated live containers, stores and ports
were preserved.
Parent acceptance scope `a722176f-b33f-4ace-a2e6-ca6210f26470` likewise records
`released: true`; independent exact-label container, network and volume
inventories were empty after its failed sign-in check.
The same cleanup record and independent empty label inventories were confirmed
for scope `1c309c63-7a02-456d-b741-e23128409ad8`.
Scope `00abf2ee-38d0-449f-adfb-e490736cf682` also records `released: true`,
and independent exact-label container, network and volume inventories were empty.

## Session lock correction

The initial proposal to move the writer key was superseded before any production
edit. Parent selected the compatible correction: preserve the writer protocol
and add `0005_session_lock.sql`, replacing only session-function serialization
with previously unused key 68272605. The same signature, validation, pinned
search path, security-definer ownership and authentication-role grant remain.
No prior SQL migration bytes changed. The exact new migration SHA-256 is
`a95eac3cbad6208fc1b624926984001acebace745add1bbcc4ef03724daf1cb0`.
The application schema now includes `0005_session_lock`; the exact schema check
therefore rejects an older image against the updated store.

Lock ownership after migration: 68272600 migration serialization; 68272601
ordinary write transactions; 68272602 application writer and migration fence;
68272603 dispatcher writer and migration fence; 68272604 request/drain gate;
68272605 external-session creation. Migration 0003's historical use of 02 is
superseded explicitly by 0005 rather than edited or silently changed at startup.

Registered command for RED and GREEN:
source the private development environment, set the already reviewed
`HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184`, then
`./hyprn-mvp dev check hosted-lifecycle --keep-scope`.
An initial invocation without that override exited 2 at the default cache
preflight and ran no tests.

- RED commit `3e30339`: 19 tests, 18 pass and one targeted error, 10.721 seconds
  (group 11.641 seconds), exit 1; scope
  `72cd31c1-ee7b-4055-bc6a-b23ac84e08c3`. PostgreSQL returned SQLSTATE 55P03
  explicitly at the old session advisory lock while a real writer lease was
  held. The GSD classifier returned `RED_EVIDENCE_OK`; semantic assessment
  confirms this was the intended behavior failure, not a fixture/import error.
- GREEN with migration 0005: all 19 tests pass, 7.724 seconds (group 8.558
  seconds), exit 0; scope `ea9b688e-456d-4452-83d2-a9cb5021a258`. The regression
  creates a real external session under a live writer with one-second lock and
  two-second statement bounds, then proves second-writer and migration refusal.
  No timeout was increased. No refactor was needed.

The registered checks completed cleanup; independent Docker inventory showed
no `hyprn-pg-test` containers remaining. Parent owns committed-tree acceptance
and rebuilding the app OCI/release descriptor before rerunning installed-app
acceptance. The prior app image is not evidence for the corrected application
schema and must not be reused as though it contains migration 0005.

## Parent installed acceptance — completed

Fixture `4fc9ab3` and rebuilt production artifact source `a1dec2e` passed
`hosted-app-installed`: **1 test in 56.591 s**, exit 0. Exact invocation used
`/private/tmp/hyprn-installed-app-session-lock-env.sh` and the registered check
with `--keep-scope`. Log: `/private/tmp/hyprn-installed-app-final-parent.log`.
Check session `e7888ed5-07d2-4569-ab66-ae31d39f5dbb`; fixture
`d927e4ed-40b6-4a6b-b743-c9d75033579d`. Evidence remains in that retained
fixture's `evidence/installed-hosted-application.json`, alongside cleanup receipt.

The parent reviewed the evidence: actual packaged factory, TLS database, HTTPS
sign-in and two private studies; foreign reads/Host/store denied; initial install,
reinitialize refusal, conflicting writer, live migration refusal, incompatible
schema refusal, missing/expired/closed admission, eight UI assets and replacement
retaining both studies. Image manifest is
`2f049a082ef22caa838b1af226b116dc7bea2e48d3290c43bf7c4deafe5543cb`;
payload hash is `a902e10747ea16d0c1acaa08e2eb9cb4eea03c9dc8a1e0201544d4bc94858fc3`.
All five schema identities match the rebuilt migration set.

The fixture's cleanup receipt reports released. Exact `org.hyprn-mvp.test-scope`
Docker container/volume/network queries returned no retained resources. Test
stores and synthetic credentials remain only in the private retained test scope;
no live installation or cloud service was touched. No identical rerun is needed.

## Remaining gates

JWKS/provider HTTP boundaries are synthetic; no real external login or Assistant
request is established by this test. Aggregate Linux host lifecycle, trusted
qualification receipts/admission opening, coherent PostgreSQL-plus-file backup
and restore, complete publication evidence and live/human acceptance remain
unverified. The local rehearsal descriptor is explicitly not publishable.
Parent owns these cross-repository obligations. This focused installed app
journey is complete; the overall 06-05 task is not.
