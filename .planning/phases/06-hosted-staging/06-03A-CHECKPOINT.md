# 06-03A — isolated Access assertion verification

Status: implemented and focused automated verification passed. Full 06-03 and
hosted sign-in remain incomplete. Scope: only cloud verification adapter,
audited native check dependency and `hosted-assertions` runner registration.

## Commits and reviewed source

- `daf4875`: tests-first fixtures, audited PyJWT/native lock, fail-closed interface.
- `06a43f6272826ff5a1776502897d8dc2f97d2068`: implemented adapter and 71-case coverage.
- Base before task commits: `aa53449` (concurrent domain task's RED commit;
  that task's application implementation was not staged by this executor).
- Adapter SHA-256: `f05e0d6cbeb58bd41ad7a9e3287df766e38207a16fffb5fb88afc0803c55924b`.
- Test SHA-256: `856468d6ea767f4e442420f989f309475a54b34b10b9c0d044bbb60f990be02c`.
- `uv.lock` SHA-256: `60be2beacf4e612ab5b75c1fbf68e860930d45265033a9a04a798d08cc4de066`.

## Commands and results

Every check sourced `/private/tmp/hyprn-collection-env.sh`, then ran
`./hyprn-mvp dev check hosted-assertions` with scoped stores. No live Cloudflare,
application data, container or execution runtime was used.

| Run | Exit | Passed | Failed | Skipped | Result |
|---|---:|---:|---:|---:|---|
| Initial registration | 2 | 0 | 0 | 0 | Runner refused missing group dispatch; added group to application pytest dispatch |
| RED, fail-closed interface | 1 | 44 | 10 | 0 | Correctly signed identity assertion failed, as did rotation/outage and configuration behavior |
| First GREEN | 0 | 54 | 0 | 0 | 0.29 seconds pytest; 0.553 seconds child |
| Expanded network coverage | 0 | 71 | 0 | 0 | 0.30 seconds pytest; 0.550 seconds child |
| Exact delivered source after unused import removal | 0 | 71 | 0 | 0 | 0.33 seconds pytest; 0.594 seconds child |

The RED target `test_signed_assertion_returns_immutable_issuer_subject` executed
and failed its explicit non-null identity assertion. Import, discovery and fixture
setup succeeded. No implementation bug or failed GREEN check was encountered.
Workflow `tdd_mode` is false and this bounded plan has no `type: tdd`; the actual
tests-first sequence and failures are retained without claiming a machine TDD gate.

Final console capture: `/private/tmp/hyprn-hosted-assertions-final.log`, SHA-256
`adfd2f5c3b9dc4a0c6d6f04e201fb44e268282efc70f2571566964a11a3535fd`.
RED capture: `/private/tmp/hyprn-hosted-assertions-red.log`, SHA-256
`c1892e209cabdbdebe86db5685ed92e6e8e798aae7e5ad42803e57893c4f0734`.
The final runner scope `hyprn-mvp-test-b38a3dd9-3349-48cf-9c35-fa258232618b`
was confirmed absent after cleanup. Other successful/failed runs were released
by the standard runner; only console captures remain outside the repository.

`git diff --check -- editions/cloud application/tests/test_hosted_assertions.py`
passed. Pinned ruff formatted only the owned Python files before the final run.
No tracked deletions or generated repository artifacts were introduced.

## Dependency and documentation evidence

`editions/cloud/provenance.md` records PyJWT 2.15.1's official release, wheel URL,
SHA-256 and embedded MIT licence digest, audited before installation. Existing
cryptography 50.0.2 licence inventory was re-inspected; httpx 0.28.1 retains its
application audit. Cloud packaging lists exact direct versions. The root lock
adds only PyJWT in native; contract/application release closure is unchanged.
Pinned uv 0.12.24 `lock --no-config --no-sources` resolved 105 packages and added
only PyJWT 2.15.1. Normal launcher provisioning succeeded; no package install failed.

The initial metadata fetch was refused by sandbox DNS; an authorized escalated
read fetched official PyPI metadata and the wheel as data. Context7 MCP/CLI were
unavailable; official PyJWT API and Cloudflare validation documentation were read.

## Invariants and remaining integration

`AccessVerifier(issuer, audience)` derives only the configured origin's fixed
`/cdn-cgi/access/certs` URL. `verify(assertion)` returns frozen
`VerifiedIdentity(issuer, subject)` or generic `InvalidAssertion`. Close the verifier
at process shutdown. Synchronous verification belongs in the application's bounded
thread pool, not on its async event loop. One process shares one verifier instance.

RS256 only; exact issuer and audience membership; required issuer/audience/subject/
expiry/issued-at; optional not-before validated when present; all dates are safe
nonnegative integers. Only application-token type is admitted when type is supplied.
Token limit 16 KiB, key body 64 KiB, 16 public RSA keys of 2048–8192 bits, 300-second
key lifetime, one refresh attempt per 30 seconds across concurrent/unknown IDs.
Requests have 2-second connect/read/write/pool timeouts and a 5-second elapsed
streaming budget. The budget is checked between blocking operations; it is not
a hard wall-clock deadline for DNS/TLS/header processing. Redirects, compressed
responses and ambient proxy/TLS trust are disabled. No token or claim logging.

Signed fixtures exercise real PyJWT/cryptography; network fixtures use httpx's
transport boundary without live credentials. They do not prove Cloudflare account
configuration, DNS/TLS availability, admitted-user policy, ASGI/session mapping,
private study permissions, human acceptance or release qualification. Those belong
to 06-03/05 and final hosted acceptance. Later integration must preserve the internal
delegated API path without a spoofable network bypass header.

The orchestrator owns committed acceptance rerun and global STATE/ROADMAP updates.

## Orchestrator committed acceptance

The parent independently reran `./hyprn-mvp dev check hosted-assertions` against
committed source `06a43f6`: 71 passed, 0 failed, 0 skipped in 0.32 seconds;
registered child 0.582 seconds, exit 0. Scope identity:
`632acab6-72a5-4f21-a3cb-29fd3d74ca83`; wrapper identity:
`209d5aa3-5540-479e-a938-0a82b566d9d1`. Human acceptance remains separate.

## Public provider key compatibility

At the parent's request, a separate read-only GET to the verified issuer's
`/cdn-cgi/access/certs` endpoint returned HTTP 200, 5,116 bytes, two keys. Each
has fields `alg,e,kid,kty,n,use`, `alg=RS256`, `use=sig`, `kty=RSA`, 64-character
key ID and 2048-bit modulus. `key_ops` is absent, which the adapter accepts.
The response fits the adapter's strict schema and resource bounds. Response
SHA-256: `d7748496c7b19fe25e091cb52c0797d16b90e8716ebe6c09ebea4b28f6c587fd`.
No key material or credentials were printed or retained. This checks current
public-key schema compatibility only; it does not establish sign-in or policy.
