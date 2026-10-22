# 06-05 native execution prerequisite checkpoint

This records source prerequisites and a passing installed Linux native calculation,
**not completion of 06-05** or full hosted artifact qualification. The latest
accepted native payload is source `18d872a`; its parent-run evidence is below.
Earlier sections retain the development history beginning with source `44b87a0`
and RED `bd8cee4`. Parent owns the Linux build and platform changes; no cloud
resource, live store, provider request or user record was touched. Global
STATE/ROADMAP remain parent-owned.

## Implemented boundary

- Closed `hyprn-cloud-execution/v1` projection in the existing attested installation
  loader. It accepts only execution identity/paths and refuses simultaneous local
  configuration/development roots. Local installation semantics remain unchanged.
- Platform consumer pinned to `231bad2`. Host-generated projection receives the
  release digest and the **execution-only configuration digest**; the latter hashes
  `preview.execution.configuration`, excluding mutable admission and its attestation
  digest. Full host/application controls still use the independent full preview
  digest. A configuration change cannot be disguised by updating admission.
- `cloud_native.py` reuses actual AiiDA initialization, NativeExecution and the
  restricted launcher. Its initialization refuses nonempty roots, copies verified
  packaged inventories, checks actual worker/source identity and creates real UUIDs.
  Root-owned host receipts pin the observed profile/repository/computer/code UUIDs
  to logical installation/store and release identity. Inspect never initializes.
- Existing private dispatcher transport extracted unchanged into
  `dispatch_bridge.py`; local manager imports/re-exports it. Cloud native startup
  uses one exclusive owner lock and one fixed attached dispatcher container.
  Native processes receive no database/provider credentials. The reviewed Unix
  socket must be root/execution-owned, non-world-accessible, with a non-root group;
  only that group is added to the execution UID's groups.
- Lifecycle source has actual initialize/inspect/attest/start/stop invocations,
  bounded observation, PID/start/command identity and quiescence checks. These
  aggregate invocations still require installed Linux rehearsal; a source check
  does not prove them.
- Attested inventory expanded from 52 to 54 entries for the cloud owner and shared
  bridge. Existing attestations are stale after this source change. Worker policy
  is unchanged. Explicit Linux build targets enter engine cache identity and both
  Docker build commands; worker building checks the resulting architecture.
- Native wheel packaging now admits only application-owned numbered migration SQL
  in its migration directory and verifies exact installed bytes. Other data files
  remain refused. Shared `select_inventory(root)` supports the parent bundle builder.

## Verification

Every command used `source /private/tmp/hyprn-collection-env.sh` then
`./hyprn-mvp dev check GROUP`. Logs are outside source, with prefix
`/private/tmp/hyprn-native-`; cloud selector log is
`/private/tmp/hyprn-cloud-config-green.log`. Tests ran on the changes committed as
`44b87a0`; parent acceptance on the committed tree remains separate.

| Group | Passed | Failed | Skipped | Test seconds |
|---|---:|---:|---:|---:|
| cloud-execution-config | 5 | 0 | 0 | 0.145 |
| hosted-native-owner | 3 | 0 | 0 | 3.501 |
| native-environment | 19 | 0 | 0 | 10.19 |
| hosted-lifecycle | 18 | 0 | 0 | 9.007 |
| bridge-history | 139 | 0 | 0 | 63.57 |
| release | 28 | 0 | 0 | 2.85 |
| deployment-hardening | 76 | 0 | 0 | 0.80 |
| locality-contracts | 165 | 0 | 0 | 12.60 |

The three native-owner tests use actual isolated AiiDA initialization/inspection,
test nonempty/existing-store refusal and changed profile-pin refusal. They do not
execute a calculation or establish an installed Linux owner. Native-environment
builds and inspects real wheels, including PostgreSQL migration SQL. Bridge-history
uses the existing scoped native history/transport checks; it does not establish a
PostgreSQL cloud dispatcher journey. Parent owns `hosted-native-bundle` test source;
this batch registers that group alongside the two new owner/config groups.

## Failures and corrections

1. Initial selector check could not access the pinned tool cache in the sandbox
   (exit 5). Retried with authorized scoped-check escalation; no test had run in
   the failed invocation.
2. RED: three tests ran and failed on intended missing cloud projection/refusal
   assertions. Machine classifier returned `RED_EVIDENCE_OK`; semantic evidence
   confirmed a fresh launcher process incorrectly accepted the development root.
   Original log and classifier record remain outside source. RED commit `bd8cee4`.
3. Locality initially had 161 passes/four failures because reviewed inventory counts
   still named 52 files. Added explicit wrapper/bridge membership and updated counts;
   final 165 passes. Static project import closure remains identical.
4. Native-environment initially had 15 passes/two failures: approved PyJWT 2.15.1
   was absent from native-host.txt. Parent regenerated the exact reviewed lock in
   `a46c943`; no alternate dependency was installed.
5. Parent's actual Linux preparation exposed migration SQL rejected by the old
   Python-only wheel allowlist. Added the narrowly owned SQL path and real installed
   byte verification. Final native-environment has 19 passes.
6. Projection digest test initially had four passes/one error: platform's reviewed
   host home is inside the execution store. Removed the unnecessary restriction
   on that containment-probe target; the root itself still cannot be the home and
   immutable source/native paths remain outside it. Final selector has five passes.
7. Existing Starlette, pytest-mark and AiiDA warnings remain; no unrelated upgrade.

## Remaining gates

- Exact Linux amd64 engine/worker/native bundle construction and fresh extraction.
  Parent build preparation is not a shipped artifact; consult its separate build
  preparation checkpoint for its failures and artifact identities.
- Installed initialization, UID/socket access, owner process lifecycle and worker
  attestation, then real PostgreSQL dispatcher discovery/actor scope/calculation,
  restart/reconciliation, saved joint sampling and validated predictions.
- Cross-release native rebind source is added in the follow-up below. Installed
  release replacement must still prove UUID/history preservation and fresh
  attestation before scientific admission.
- Hosted artifact group still fails closed without exact packaged inputs and a
  complete installed rehearsal. No source-only replacement was added.
- Admission opening, coherent backup/restore, platform host fencing/firewall,
  publication, real cloud attestation and human activation approval remain open.

## Cleanup and self-check

Registered scopes were released by the runner; no generated test data remains in
source. Final native-owner scope was `e0adf28c-6fd5-4be1-8b21-da7cacd1d52c`,
native-environment `358a061a-8c94-45d8-8e98-d4e1d6f393da`, lifecycle
`bbdc871a-ecd1-4f9d-85a4-5ae0f4dec82c`, and bridge-history
`d7e01112-61c0-4970-a4d6-903fbbc88902`. Protected live ports/stores were not used.
Explicit owned paths only were staged. Both commits exist; source files exist;
no tracked deletion occurred. No stub substitutes for a scientific result.

## Build helper follow-up — 55b6429

Parent review caught two defects before the actual engine build: the staging loop
shadowed the explicit target with a Path, and the final source identity omitted
the target. Both are corrected in `55b64290ed5cda03cc884b32b01ba6145631e05b`.
The regression exercises actual staging/command construction and cache identity
with Docker mocked; it does not claim an actual image build. The same commit
extracts worker-only inventory export from local extension, validating all notice
paths, distribution records, encoded bytes and owned output paths before writes.
It creates no native profile or attestation.

Checks used `source /private/tmp/hyprn-collection-env.sh` followed by
`./hyprn-mvp dev check cloud-execution-config` and
`./hyprn-mvp dev check native-environment`:

- Target regression RED: five passes/one error, reproducing the Path TypeError;
  `/private/tmp/hyprn-engine-target-red.log`.
- Target GREEN: six passes, 0.145 s;
  `/private/tmp/hyprn-engine-target-green.log`.
- Native environment: 26 passes, 10.50 s;
  `/private/tmp/hyprn-native-export.log`.
- Parent independently accepted the committed delta: six configuration and 26
  native-environment passes. Its preceding baseline acceptance had 459 passes
  across configuration, owner, native environment, lifecycle, bridge history,
  release, hardening, locality and bundle groups. Parent owns those logs and
  artifact-build observations.

The focused scopes `8b1ab4b9-7e1b-4640-b9c1-abbf0b791879` and
`c9e3f2cf-f26f-47f6-b33d-1803feb568e1` were released. The external scoped worker
build script was handed to the parent; the parent added the existing checked
buildx preparation before clearing HOME and owns its running build. Source changes
are held while those exact bytes are built. Parent reports complete-source Linux
native preparation passed; that remains preparation, not installed qualification.

Read-only rehearsal assessment found Docker Desktop and its existing Linux build
volume, but no separate local Linux VM tooling. A same-path daemon-volume mount
could preserve the worker's exact bind source without changing worker policy; it
requires an actual bounded mount probe before adoption. Container-side-only mount
paths are insufficient. No rehearsal resources were created by this assessment.
All remaining gates above stay open. This follow-up commit has no tracked deletion.

## Explicit release rebind — 784bbf9

Source `784bbf9a0de23c832cf7e7ed087ca016826b1687` adds an explicit migration
path for a stopped native owner. The host closes admission, verifies the target
artifact, drains and checks quiescence. The retained execution projection must
hash to the protected prior owner receipt before its interpreter can be invoked.
Installation/store/profile identity, execution root, host home and Docker endpoint
cannot change through rebind. The host supplies a root-owned narrow authorization;
the new owner checks actual profile/repository/computer/code UUIDs and refuses
unfinished AiiDA processes. Only packaged inventories, runtime metadata and the
launch wrapper change. Saved native records are not copied, reset or migrated.

Ordinary start does not rebind. Migration now requires the prior native service to
have been stopped explicitly; it does not signal an old owner using new paths.
Old containment evidence remains, but its runtime/configuration fingerprint is
stale. Qualification is explicit. A failed metadata replacement retains a pending
marker, and a failed owner operation cannot advance the protected host receipt.
Reconciliation and installed interruption/recovery proofs remain required.

Commands used the same sourced environment and registered entry point:

| Group | Result | Duration | Log in /private/tmp |
| --- | --- | --- | --- |
| `hosted-native-owner` | 12 passed | 9.489 s | `hyprn-native-rebind-final.log` |
| `cloud-execution-config` | 6 passed | 0.141 s | `hyprn-rebind-config.log` |
| `locality-contracts` | 165 passed | 10.78 s | `hyprn-rebind-locality.log` |

The owner tests initialize real scoped AiiDA stores and preserve actual UUIDs and
a stored synthetic Dict node. They prove native-process refusal, stale-attestation
refusal and partial-write refusal. Packaged inventory/image checks and positive
root authorization are mocked in this focused rebind test; it is not an installed
release or real calculation proof. Host tests exercise old-digest refusal,
unchanged Docker authority and protection of the previous receipt on failure.

Two harness corrections preceded the passing run: the first run had seven passes
and one failure because a fingerprint mock omitted the `root` keyword; the second
had ten passes and two errors because macOS cannot chown a fixture into a group
whose number happens to equal the current UID. The host-I/O test now asserts that
chown request at its privilege seam. Logs are `hyprn-native-rebind-focused.log` and
`hyprn-native-rebind-green.log`. Neither failure concealed a production change.
Final scopes `db1f6000-a1ff-4c73-930e-297ad364b59e`,
`a9784857-ad37-42e2-8d5d-a0a5985d3a79` and
`8ab68464-e17a-4028-a3dc-29145c5767d6` were released. The commit has no tracked
deletion. Parent owns integrated acceptance and exact rebuilt artifacts.

Parent separately reports the daemon-volume sibling bind probe succeeded and
Linux worker/native build and package preparation progressed. Those identities
and fresh-extraction evidence belong in its build checkpoint. This source delta
changes the attested inventory and requires a final rebuilt artifact; all
installed/native scientific journey gates remain open.

## Installed Linux native journey — fixture continuation

The opt-in `hosted-native-installed` group consumes an explicit bundle descriptor
through the guarded runner. It extracts only the identified regular-file archive
into a fresh labeled Linux volume at its immutable prefix, verifies every packaged
byte and imports using the extracted interpreter. A separate labeled execution
volume uses its daemon mountpoint in both owner and worker. No checkout, build
cache, existing native store, provider credential or application database is
mounted. UID 10003 owns the private execution root; an owned Unix socket forwards
unaltered daemon bytes without modifying the shared daemon socket. The controller
has one CPU and 1 GiB; the unchanged worker policy allows at most two 0.5 CPU,
256 MiB workers. Cleanup checks exact scope/worker labels before removal.

The tested native payload source is
`ffe2ef468be08584e483bc76e2321866e634ba8c`, archive SHA-256
`717d9f764fbc4b85e04b140cb82a92787c93f641269938744a22b88ea5669406`
(229203240 bytes, 20828 inventoried files). Its worker identity is
`sha256:2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`.
The parent separately verified this against the exported OCI manifest and blobs.
Fixture-only source changes do not alter the bundle's attested source inventory;
they do require committed fixture acceptance. The binding is explicitly
`isolated-native-bundle`, not a complete platform release receipt.

### Existing Linux host utility prerequisite

The slim Python extractor image lacks `ps`. The exact shipped AiiDA 2.9.3 direct
scheduler executes `ps -xo pid,stat,user,time ... | tail -n +2`; without `ps`, the
pipeline emits no rows and AiiDA classifies the missing job as done, retrieving
empty result and stderr files before the background calculation finishes.

The owner fixture therefore reuses the already reviewed modeling image solely as
a Linux host environment, overriding its entrypoint with the extracted native
Python controller. It starts no Ruby/modeling service. Acquired index
`sha256:cfb49e197e7694f2e2b3498157174acc753c7fe63a058687b38680da38e84d78`
must resolve with explicit `linux/amd64` to
`sha256:fc4c6fa692effd856f783e1f7082a16653244c20348a2191b2f743fae928e9b9`.
No utility is copied into the native bundle and no new package is acquired.
The extractor and read-only diagnostic collector retain the pinned Python base.

Read-only inspection of that image recorded procps and libproc2-0 version
`2:4.0.2-3`, `/usr/bin/ps` SHA-256
`b2a1f7b6ae39ca71cf915d9553877df8f65e1b5ee39c4c269ee3c0d0bb282546`.
Its bundled Debian copyright names official source
`https://gitlab.com/procps-ng/procps` and LGPL-2.1+ for the default/ps files;
GPL-covered package files remain in their existing image scope. Both procps and
libproc2 copyright files hash to
`90a66617c36d83068b52bbb77cbfef1234f526bfa287156d9d05f7df4d339539`;
the bundled LGPL-2.1 text hashes to
`dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551`.
The existing shared libraries are libproc2, libc, libsystemd, libcap, libgcrypt,
liblzma, libzstd, liblz4 and libgpg-error. They are neither replaced nor copied.
Audit logs are `/private/tmp/hyprn-fixture-ps-audit.txt` and
`/private/tmp/hyprn-fixture-host-utilities.txt`. Parent authorized reuse of this
existing approved image scope after the nonpermissive licence was surfaced.
The Docker CLI is the previously audited Apache-2.0 binary from exact amd64 child
`docker@sha256:d329fa64f42e03248f9a6cb2e21b6d4aa4d76f5a80aa2ad7946d81fbf1860602`;
its provenance is recorded in `deployment/provenance.md`.

### Failures retained during fixture development

All registered commands source `/private/tmp/hyprn-collection-env.sh`, use
`HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184` and explicit
`HYPRN_MVP_HOSTED_NATIVE_INPUT=/private/tmp/hyprn-installed-native-input.json`, then
run `./hyprn-mvp dev check hosted-native-installed`. Logs below are in
`/private/tmp`; scoped evidence is retained by the check runner outside the repo.

| Log | Result | Cause / retained observation |
| --- | --- | --- |
| `hyprn-native-installed-first.log` | Refused before tests | Wrong cache-budget variable; default budget refused the run |
| `hyprn-native-installed-run.log` | 1 error, 40.821 s | Fixture Unix socket path exceeded AF_UNIX limit; switched to owned short socket directory |
| `hyprn-native-installed-retry.log` | 1 pass, 42.678 s | Earlier 8496606 bundle proved real initialization, fresh-process identity reads, reinitialization refusal and refusal before attestation only |
| `hyprn-native-installed-calculation.log` | 1 error, 217.577 s | Portable bundle attestation refused; owner initially 0.25 CPU, changed to 1 CPU during read-only inspect; only stderr retained |
| `hyprn-native-installed-probes.log` | 1 error, 58.049 s | All containment probes passed individually, but Docker's arm64/amd64 warning contaminated strict JSON; actual report retained |
| `hyprn-native-installed-platform.log` | 1 error, 80.121 s | Explicit verified DOCKER_DEFAULT_PLATFORM=linux/amd64 gave real passing attestation; calculation exit 300 with missing ps warning |
| `hyprn-native-installed-calculation-diagnostics.log` | 1 error, 77.305 s | Actual retained result.json and launcher.stderr both empty; scheduler ps warning confirmed host utility prerequisite |
| `hyprn-native-installed-host-utilities.log` | 1 error, 94.262 s | Real scheduler and launcher ran; restricted worker refused `/input/manifest.json` with PermissionError; production permission boundary remains unresolved |

The platform selection does not filter output or relax attestation. The fixture
retains bounded actual `containment.json` and fixed native calculation artifacts
on failure before removing the store. Every failed scope was released, including
`5a715dcf-fa52-489b-ba13-5fcef5ea0d9d`,
`a4d3edb6-8b12-4dd8-a50e-47aa80b81566` and
`b11f751d-66ad-433d-9585-223ab5a5795f`. No original request is re-dispatched;
each experiment has a new isolated store/request and exact cleanup ownership.

The final diagnostic scope `19ce7865-9c2f-478b-9a10-c8a20c8bd88a` was also
released. Its retained `calculation.json` lives under check-storage session
`abe3ed4e-43a2-4189-953e-bba4779d6689`. Real worker exit status was 1 and AiiDA
process `6179a23d-60a0-4cfe-8e90-8e225bc1d902` finished with status 300. This
proves the failure reaches the restricted worker; it does not prove calculation
success. Parent was notified before any production permission change. The
registered fixture is intentionally red until that boundary is fixed and the
exact rebuilt artifact passes. No passing receipt or expected result is invented.

The full hosted-artifact gate remains deliberately incomplete. PostgreSQL/app
dispatch, per-actor authorization, saved sampling/prediction gates and replacement
rehearsal are a separate parent-assigned continuation. This fixture alone does
not qualify 06-05 or staging activation.

## Authenticated worker input permissions

The installed failure exposed AiiDA's private working-copy modes on Linux. The
launcher now normalizes only the already authenticated work copy, after exact
bundle/runtime verification and before creating the worker: `manifest.json` and
manifest-listed regular files become 0444; their owned directories through the
mounted input root become 0755. The worker remains UID 65534 with the same
read-only mount, network denial and limits. No ancestor, profile, native store or
frozen AiiDA repository changes. Directory owner-write permission is retained for
normal cleanup; the distinct worker UID cannot write those directories.

All selected paths are validated before mutation. Symlinks, hardlinks and foreign
owners are rejected. Mutation uses no-follow descriptors and compares the opened
inode identity with its preflight snapshot. The existing bundle writer uses the
same normalization so a restrictive host umask cannot silently remove worker
traversal. Scientific bytes, hashes, saved configurations and cached results are
unchanged; this is access preparation of immutable execution copies only.

`./hyprn-mvp dev check cloud-execution-config` passed 10 tests in 0.156 s under
the environment above; log `/private/tmp/hyprn-native-input-permissions.log`.
Tests use real files, nested private directories, restrictive umask, symlinks and
hardlinks, and confirm private ancestor/sentinel modes remain unchanged. The
foreign-owner case injects the effective owner identity because the focused test
runs unprivileged; cross-UID readability still requires installed Linux proof.
An invalid bundle test asserts permission preparation and Docker are never
reached. Scope `db14801d-7810-4344-bd5d-de71d67a74ae` was released.

This production source delta invalidates the old source fingerprint and requires
parent rebuild, fresh installed attestation and calculation/restart proof. The
prior installed failure is not relabeled as passing, and all full artifact gates
remain open.

### Deterministic host prerequisites

The cloud owner now checks real `bash`, `ps`, `tail` and `whoami` using its actual
PATH before initialization, rebind, attestation, launch or attested admission.
Missing/unusable commands produce an actionable refusal naming the command,
before store initialization or worker execution. The bounded `ps` probe selects
only the owner's current PID; it does not list other processes. Other probes
execute an empty shell, fixed stdin through tail and the owner's account name.
Ordinary historical inspection remains available without scheduler utilities.
No dependency is acquired and the local edition is unchanged.

The registered `hosted-native-owner` group passed 15 tests in 9.674 s; log
`/private/tmp/hyprn-native-host-prerequisites.log`. This includes actual host
commands, each missing-command refusal before any initialization write, and an
unusable ps refusal before attested admission. Existing real AiiDA identity and
rebind tests still pass. Scope `13b14c84-545d-4d43-a925-4aeb50f3cd16` was
released. Parent independently accepted the preceding permission fix's ten
configuration tests; exact Linux artifact rebuild and installed proof remain open.

## Parent accepted installed native calculation and restart

The parent ran the committed `hosted-native-installed` fixture once on the rebuilt
artifact; this executor reviewed its retained evidence without repeating the test.
The exact command was:

```sh
source /private/tmp/hyprn-collection-env.sh
HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184 \
HYPRN_MVP_HOSTED_NATIVE_INPUT=/private/tmp/hyprn-installed-native-readable-input.json \
./hyprn-mvp dev check hosted-native-installed
```

Result: **1 passed, 0 failed, exit 0**, 107.771 seconds (runner 107.831 seconds).
Log: `/private/tmp/hyprn-installed-native-readable-parent.log`. Artifact source:
`18d872aba952dffa946bf1fec6062ecce59d2ebf`; archive
`/private/tmp/hyprn-native-build-readable/artifacts/native.tar.gz`, SHA-256
`76f4946d5b10a573f666ab915e1623b1a91e7f16dc285dbc0a3444f512fcfbe5`,
229220760 bytes, 20834 inventoried files. Runtime source fingerprints were rebuilt;
the numerical worker remains exact OCI identity
`sha256:2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`.
Owner host image remains the reviewed `fc4c6fa...` child identified above.

Fresh read-only extraction verification, actual native initialization and repeated
fresh-process identity inspection passed. Reinitialization and unattested admission
were refused. Real containment passed all ten access checks, memory OOM enforcement,
wall/output bounds, file/PID bounds, concurrent isolation and exact worker imports.
Attestation executed zero candidate models. The subsequent real calculation
finished with exit status 0 and available outputs 49.0 and 7.0. Native process
`f2fa5a15-409a-4cfb-aa3e-b3c3b6dc3cae` belongs to actual repository
`2836cfdbfc6342a4b6a9a04cb748a060`. Its retained bundle equals the submitted bundle;
a new interpreter read the identical saved result, found one matching request
and refused a duplicate launch. The final native check retained the same owner
identity and current attestation. Controller stderr was empty.

Evidence was moved by the runner to
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/.hyprn-checks/2a124215-c5e7-4c51-97d0-6724cc8ef0ac/evidence/hyprn-mvp-test-c94ceef5-4681-479e-bd87-1c230a5bbfdb/`.
`installed-native.json`, `containment.json`, `calculation.json` and
`installed-native-cleanup.json` contain the observations. The check-storage session
is `2a124215-c5e7-4c51-97d0-6724cc8ef0ac`; the actual fixture scope is
`c94ceef5-4681-479e-bd87-1c230a5bbfdb`. Both runner and fixture report release.
Independent read-only Docker queries found no container/volume with that scope
label and no worker with its exact cloud-owner label.

Retention detail: the fixture's Docker text helper strips the final newline from
the copied containment report. The native receipt records original SHA-256
`774e05409f77fc8970fc1ba2b97b63b160da180d41b2f75c2d81f7c56c859808`;
adding the original single LF to the retained report reproduces that exact hash.
The retained file itself hashes to
`75f559b5ebea182ee56ba6d5f997785ed40028df7c3516764fb7f0bfd9b65ce0`.
No JSON content differs. This is documented rather than silently treating the
normalized evidence copy as byte-identical; no test or production code was changed
after this acceptance.

This closes the isolated installed-native calculation/restart slice. It does not
prove the PostgreSQL dispatcher-to-native path, actor authorization across that
path, saved sampling/prediction journeys, installed cross-release replacement or
coherent backup/restore. Full hosted-artifact qualification and 06-05 stay open.
