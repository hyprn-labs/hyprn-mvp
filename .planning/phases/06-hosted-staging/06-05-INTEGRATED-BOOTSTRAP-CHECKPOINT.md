# Integrated bootstrap preparation

Date: 2026-10-21. Parent-owned integration, not completed 06-05 acceptance.

Product source `63af9f041a321c175387eea1ef79643b631c9e45`; installed fixture
`294353e`. Platform schema/reconciliation source `68d04d3`, bootstrap `0884263`,
installer `7fb6cc8`, daemon endpoint correction `089db32`, preflight `821be76`.
Source and focused evidence are in the individual owner checkpoints.

## Parent verification

- `./hyprn-mvp dev check hosted-owner-schemas`: 9 passed, 22.848 s.
- `./hyprn-mvp dev check hosted-lifecycle`: 21 passed, 17.421 s.
- `tests/platform/run.sh reconcile`: 41 passed, 1.321 s.
- `tests/platform/run.sh bootstrap`: 25 passed, 0.364 s.
- `tests/platform/run.sh install`: 12 passed, 0.029 s.
- `tests/platform/run.sh images`: 9 passed, 0.029 s after endpoint correction.
- `tests/platform/run.sh preflight`: 18 passed, 0.025 s after IPv4 correction.

Product groups used the pinned entry point and dedicated fixture environment;
platform groups use isolated files and simulated external boundaries. Real
Cloud SQL backup/restore, host initialization/update and Access login remain open.

## Rebuilt artifacts and installed-wrapper refusal

`/private/tmp/hyprn-build-owner-schemas/artifacts/native.tar.gz`:
SHA256 `4fe86a9497593c5a361a6984d0d9a3e7e40002d78b27a7966fe61a610b273a10`,
229258001 bytes, 20846 files, immutable source `63af9f0`.
App OCI archive SHA256
`db17c7f6218ac1bf77ca02edb7b548e642a437b36535e7ac8bb70844b7c2d2f0`;
manifest `2f049a082ef22caa838b1af226b116dc7bea2e48d3290c43bf7c4deafe5543cb`
is byte-identical to the app whose actual HTTPS/private-study journey passed.
That unchanged image check was not repeated.

With `HYPRN_MVP_HOSTED_NATIVE_INPUT=/private/tmp/hyprn-owner-schema-native-input.json`,
`./hyprn-mvp dev check hosted-native-installed`: 1 error, 0 passed, 94.442 s.
Log: `/private/tmp/hyprn-installed-owner-schema-parent.log`.
Check identity: `0b44c3c9-9fc7-40e8-953a-93f251cd8a7c`.
Scope: `63493703-297c-425e-983c-4fdda9a1db43`.
Evidence retained under the check's `evidence/` folder in the dedicated scratch
registry, including actual containment probes, stderr and cleanup confirmation.

The fixture now invokes the released privileged lifecycle wrapper, not only its
native child. Initialize, repeated identity inspection, duplicate initialization
refusal and unattested-check refusal completed. Attestation then refused:
Docker's ARM host prepends an AMD64 emulation warning to probe output. The wrapper
correctly omits ambient DOCKER_DEFAULT_PLATFORM, exposing the earlier fixture's
architecture assumption. Strict JSON parsing yields no valid worker-import proof.
This is a failed qualification, not a passing containment receipt. Candidate
executions were zero. All random-scope containers and volumes were released.
No source workaround, warning stripping or relaxed attestation was applied.

## Next obligations

Parent owns actual AMD64 rehearsal, host prerequisite installation, full second
activation and recovery, admission opening, publication and continuous delivery.
Temporary staging host inventory has explicit owner approval for start, expiring
OS Login key, read-only inspection and stop; completion must be recorded separately.
No additional secret transfer or deployment is authorized by this checkpoint.

## Actual host inventory outcome

Both temporary inspections had separate exact owner approval. The first script
`79c1e4bdb24838ff97618d5b70b0c4651b76315c40b67f923594055d38e6aa59`
started the VM but SSH was not ready; its cleanup confirmed TERMINATED. Effective
firewall readback allowed IAP TCP22 and returned no inherited deny. Serial output
after stop was unavailable, recorded as a failed diagnostic read.

Revised script `d183a4ab1756448d9b9e4c10d86a6a695ac5b8e2035a23a12213d5938ea3a08f`
captured boot diagnostics while running and retried only the read-only SSH
inventory. Second SSH attempt succeeded; final VM state is TERMINATED. Actual
host: Debian 12, x86_64, kernel 6.1.0-53-cloud-amd64, systemd, no swap; Docker and
cloudflared absent, no execution UID10003 or Docker group. Data disk is 100 GB,
without a filesystem or mount; boot disk is 30 GB. iptables 1.8.9-2 is installed
but not on this unprivileged login's PATH; do not infer absence from `which`.
No packages, disk format, product data, secrets or app process were installed.

Private evidence: the `host-inspection` and `host-inspection-ready` directories
under `/private/tmp/hyprn-staging-inventory-3k0g1h31`; result.json records final
state, host-inventory.json and boot-1.log retain observed prerequisites. SSH keys
expire after 15 minutes. This establishes operator IAP/OS Login access only, not
external application sign-in or scientific execution.

Official package metadata preparation is outside the repository at
`/private/tmp/hyprn-staging-host-packages`. Docker's Bookworm index was retrieved;
Cloudflare's package-index request returned HTTP403, so its official GitHub release
metadata was read instead. No packages downloaded or installed yet. Compose is
currently major5; the preflight's major2-only rule must be reconciled with the
reviewed plugin release before host setup. Exact dependency closure, pinned
package hashes/licences, declarative host setup and actual host qualification
remain unfinished.
