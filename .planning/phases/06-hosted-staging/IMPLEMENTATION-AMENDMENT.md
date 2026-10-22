# Hosted implementation amendment — 2026-10-20

Authority: the owner approved the shortest path to working staging, then explicitly
authorized a fresh application database and removal of MCP/ChatGPT functionality.
This amendment overrides conflicting scope in the phase 6/8 plans and coordination
ledger. Scientific, security, dependency and operational approval gates remain.

- Deliver the embedded Assistant, authoring, real restricted execution, joint
  sampling, checked surrogates and answer exploration in usable staging.
- Remove external MCP/ChatGPT transport, grants and connection features. Retain
  the protocol-independent agent tool catalogue, public API, attribution and
  delegated authority used by the embedded Assistant.
- No transfer or migration of current demo data is required. Initialize fresh
  PostgreSQL stores explicitly. Keep schema identity/version checks and the
  infrastructure for safe subsequent schema upgrades; ordinary startup never
  silently resets a database.
- Do not delete the current installation until its identity is verified and the
  replacement needs that deletion. Permission to discard data is not a reason
  to touch unrelated installations, fixtures or credentials.
- Skip 06-04's remote transport implementation and its dependencies/audits.
  Replace its verification with embedded-Assistant authoring and access controls.
- Reuse the two repositories and existing plans in cohesive implementation
  batches. First dependencies remain the deployment contract (08-01) and real
  PostgreSQL boundary (06-01/02); remove unused protocol requirements from both.
- Start with one application process and one dispatcher, bounded workers,
  private GCP staging, Cloudflare Access/Tunnel and explicit study permissions.
  No Kubernetes, application replica autoscaling, production provisioning,
  Keycloak migration or external ChatGPT integration on this critical path.
- Automatic staging deployments consume checked immutable release artifacts.
  Provisioning/IAM/GitHub settings await the exact reviewed operational plan and
  cost approval under platform AGENTS.md. No cloud change is implied by this file.
- Infrastructure is code in `hyprn-platform`: Terraform owns compute, disks,
  databases, object storage, networking, firewall rules, identities and secret
  metadata. Host setup, services, backups and release reconciliation are versioned.
  Cloudflare deployment configuration is declarative where supported. Secret
  values and Terraform state remain outside Git. Record any bootstrap exception
  explicitly; reproduce the workload from the reviewed code during acceptance.

Acceptance: two admitted identities remain isolated; a fresh study can be authored,
run and published with checked joint predictions through the embedded Assistant;
sliders use real saved calculations/validated estimates without model reruns;
a second staging-branch deployment and restart preserve the new records; recovery
is exercised. Automated verification is distinct from human acceptance.

## Current implementation state

Updated 2026-10-20. Product foundation `2f9c629` passed parent acceptance:
855 tests in seven registered groups; [evidence](06-core-ACCEPTANCE.md).
Build-context/private-file hardening is committed as `74ae2a4` with 76 tests.
External MCP/ChatGPT token/operator surfaces are retired; embedded Assistant
delegation and tools remain. Full PostgreSQL domain implementation `4c40f08`
passed parent acceptance: 731 tests across hosted-postgres, access-control,
public-api, agent-tools, contracts and locality-contracts, plus nine combined
static/build checks. See [domain checkpoint](06-02-CHECKPOINT.md).

Platform contract `edc022f` and offline infrastructure `2c35587` passed parent
acceptance: 12 contract tests and two infrastructure tests covering seven mocked
Terraform plans. These do not establish cloud provisioning or host execution.

Signed Cloudflare assertion verification `06a43f6` passed 71 parent tests.
Managed Assistant declarative provisioning `1e0c10a` passed 16 parent tests;
its approved exact plan has now created and verified both provider resources;
no conversation or application activation has occurred.
See [Assistant checkpoint](06-03B-CHECKPOINT.md). Exact Assistant definition/environment pins and shared-budget carry-forward
are implemented in the platform contract. Hosted sign-in source `1c5a4d2` passed
parent acceptance: 255 tests plus nine combined static checks; see
[session checkpoint](06-03-CHECKPOINT.md).

Platform main/Access infrastructure, protected state bootstrap and dispatcher
contract passed their registered parent checks. The owner approved the isolated
state-bucket creation and three reviewed state namespaces on 2026-10-20.
The approved state bucket and remote state initialization are complete. The owner
approved the exact main/Access plans and EUR 170–220 monthly cost envelope. Both
applied successfully: 76 GCP creates and six Cloudflare creates, no updates or
deletes. Actual readback confirms a stopped private shielded VM, private
PostgreSQL 17 with encrypted connections/backups/PITR, private versioned buckets
and initially ten empty secret containers (provider version1 added later as
recorded below). GCP refresh is no-change; Cloudflare had only
a computed policy app_count/review-output refresh, no resource drift. The
post-hostname-correction Access plan is now fully no-change.

The live HTTPS check found the reviewed staging.app.hyprn.ai hostname cannot use
Cloudflare Free's first-level Universal SSL coverage. The owner approved the exact
three-update correction to staging.hyprn.ai; it applied successfully. Verified
HTTPS now redirects to the configured Access team and Terraform reports no
changes. Platform source/runtime contract and fixture pins fb7bf11 passed
20 contract, two infrastructure and one Access-infrastructure tests. No paid
certificate subscription or TLS weakening was needed. Access itself admits the two
owner-supplied emails through email PIN, with matching assertion enforcement
on the configured tunnel; no connector runs.

The owner separately approved the pinned Assistant resources and existing-key
transfer. The restricted environment was created and verified; initial agent creation
was rejected for insufficient API credit. After the owner replenished credit,
the same approved definition succeeded: agent version1 and environment readback
match the exact released plan.
Independent key transfer succeeded into numeric Secret Manager version1,
verified ENABLED by metadata. Preserve the private receipt; never repeat it.
No model request or conversation was started.
Application activation remains unapproved until readiness checks pass. Assistant runtime bindings (platform 1f9a7fa) passed 20 parent contract
tests. Secret transfer/delivery 5f317c9 passed 18 parent CLI tests; attached
service-account/tmpfs delivery still needs Linux qualification. Full 06-03 session/UI integration is accepted on the committed source. Next:
06-05 Linux release/lifecycle implementation, followed by platform host startup
and automatic publication; those remain unfinished.

Credentials and machine-specific bindings stay outside Git. Dedicated Google
Cloud CLI login works; its ADC refresh is expired, so reviewed operations use
short-lived CLI OAuth tokens in memory. Cloudflare resource readback works;
certificate-pack reads are outside the token's permissions.

Remaining activation gates: GitHub protection support
for private repositories (currently Free), Linux release/lifecycle implementation,
Linux execution attestation, final Assistant spending refresh and old-delivery fencing, automatic second deployment
and recovery acceptance. No current data reset or hosted application activation
has occurred. Infrastructure provisioning is not a working staging application.


Runtime wiring source in platform `1e5915d` passed parent contracts (21 tests,
4.566 seconds) and secrets (18 tests, 8.300 seconds). Its final store-identity
addition `72d533e` passed the affected contracts (21 tests, 4.540 seconds); no
secret consumer or delivery changed, so the prior secret check remains applicable. It adds read-only host
identity/admission/Assistant control inputs, explicit application paths and CA
hash, and aligns modeling mounts with its actual image entrypoint. These are
source and contract checks, not evidence of a booted cloud release.

Read-only budget reconciliation confirms five provider sessions totaling 501
USD cents: 476 in the retained local ledger and the same 25-cent session already
carried as prior usage. The approved EUR 100 ceiling remains 11215 USD cents at
the previously recorded conversion. Fresh cloud data must carry all five once.
Before admission, refresh spending and fence local Assistant delivery so two
installations cannot independently spend the same remaining allowance. Private
session identities and transition evidence remain outside Git.


06-05 is being delivered as two cohesive prerequisites: the application/modeling
lifecycle and PostgreSQL dispatcher batch, then the
[cloud native owner and Linux artifact continuation](06-05-NATIVE-PLAN.md).
The latter needs a fresh execution context because the existing native installer
is local-only and the prepared virtual environment is not inherently relocatable.
Both portions and the original required acceptance remain mandatory; an interim
source checkpoint is not full lifecycle conformance or a usable staging release.
The reviewed Linux amd64 Python base was acquired and its architecture/digest
verified in an isolated build preparation scope. No native bundle has been built
or qualified yet, and no live installation was touched by this acquisition.

The application/modeling prerequisite source `eba4618` passed parent acceptance:
18 hosted-lifecycle, 24 hosted-postgres, 28 release, 76 deployment-hardening,
165 locality-contracts and one release-container test (312 total). The container
check covers the existing local image target; it does not qualify a cloud amd64
artifact. The native adapter and installed-artifact gates remain unfinished.
Linux dependency acquisition completed in an isolated amd64 container using the
existing exact uv/CPython/native lock identities; the temporary cache is reusable
build preparation only, not a shipped artifact or scientific attestation.
