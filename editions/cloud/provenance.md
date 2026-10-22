# Cloud edition dependency provenance

The independently authored `hyprn_mvp_cloud` adapter verifies Cloudflare Access
assertions. It contains no provider source code and no application entry point.

## PyJWT audit — 2026-10-20

Implementation authorization: phase 06-03A and ADR-0014. Before installation,
the official versioned release metadata and wheel were downloaded as data,
the wheel SHA-256 was compared with PyPI and its embedded licence was read.

- Official source: https://github.com/jpadilla/pyjwt
- Release: https://pypi.org/project/PyJWT/2.15.1/
- Metadata: https://pypi.org/pypi/PyJWT/2.15.1/json
- Wheel: https://files.pythonhosted.org/packages/50/ca/44de4e75f8aadc457f0634be3b542815078ded46dca30efb960edeecad6e/pyjwt-2.15.1-py3-none-any.whl
- SHA-256: `42d59d631f7768a1028a64c7ff581a9bf7519804daf91fc5b6c56e30eec5e193`
- Licence: MIT; embedded `pyjwt-2.15.1.dist-info/licenses/LICENSE`, SHA-256
  `797a7a20231d4c433e9f1911db1731d06b5828b98f499819a034f7c0f56f5ce5`.
- CPython 3.12 requires no base transitive dependencies. RSA verification uses
  the explicitly pinned cryptography dependency below, not a handwritten verifier.
- Keep LICENSE and AUTHORS.rst with redistributed artifacts.

## Reused audited dependencies

The cloud adapter pins `cryptography==50.0.2` (Apache-2.0 OR BSD-3-Clause),
`httpx==0.28.1` (BSD-3-Clause). cryptography and its cffi/pycparser closure are
already in the reviewed native environment; httpx and its closure are recorded
in `application/dependency-pins.json` and `application/provenance.md`.
The exact platform wheel hashes remain in the root `uv.lock`. Cloud packaging
must retain those licences, cryptography's bundled OpenSSL notices and the
reviewed platform artifact identities. The final hosted release closure audit
belongs to 06-05; no distribution qualification is claimed by this adapter.

The native inventory's `locks/native-installed.json` was re-inspected for
cryptography 50.0.2: the recorded licence expression is Apache-2.0 OR BSD-3-Clause.
Embedded licence SHA-256 identities: `LICENSE`
`3e0c7c091a948b82533ba98fd7cbb40432d6f1a9acbf85f5922d2f99a93ae6bb`,
`LICENSE.APACHE` `aac73b3148f6d1d7111dbca32099f68d26c644c6813ae1e4f05f6579aa2663fe`,
`LICENSE.BSD` `602c4c7482de6479dd2e9793cda275e5e63d773dacd1eca689232ab7008fb4fb`.
The cloud check runs in that native dependency group without importing AiiDA,
OpenMDAO or OpenTURNS. Application/contract release pins remain unchanged.

Official sources: https://github.com/pyca/cryptography and
https://github.com/encode/httpx. Verification API reference:
https://pyjwt.readthedocs.io/en/2.15.1/api.html.
Provider contract: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/.

## Hosted session integration

The application contract/test environment now includes the already audited
PyJWT 2.15.1 and cryptography 50.0.2 closure (cffi 2.1.1, pycparser 3.1)
to exercise the real FastAPI/PostgreSQL ingress with signed fixtures. These are
the same versions, hashes and licences recorded above and in the native audit;
no new package version or upstream source is introduced by this group change.
