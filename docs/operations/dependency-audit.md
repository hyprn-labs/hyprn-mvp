# Dependency audit

Status: **approved by the product owner** (2026-10-13, decisions D-05, D-05a and D-05b of the local-edition plan). The decisions taken on §7 and what the repository applies are recorded in §10. The formatter and linter (ruff and prettier, decision D-13) are recorded in §11 to §13, approved by the product owner on 2026-10-13 before installation. The build backend of the checkout's packages (flit_core, decision D6) is recorded in §14 and §15, approved by the product owner on 2026-10-14 before installation. Any package or version that is not in this record is a separate blocking review and is never approved automatically. Recorded 2026-10-13 from official upstream sources only (see "Sources"). It is a provenance, licence and advisory inventory, not legal advice.

Every archive SHA-256 below was read from upstream release metadata and cross-checked against at least two independent published records, and all of them matched:

- uv: the release `sha256.sum`, the per-asset `.sha256` files, `dist-manifest.json` and the GitHub asset digests.
- CPython: uv's embedded download metadata, the release `SHA256SUMS` and the GitHub asset digests.

## 1. Selection (product-owner decisions, D-05)

- **uv 0.12.24**, the latest stable 0.12 release (published 2026-10-08). No age delay applies.
- **CPython 3.12.15** everywhere (host environments and images), in exactly the python-build-standalone build that uv 0.12.24's embedded download metadata names for 3.12.15. It is downloaded only from the python-build-standalone GitHub releases (`UV_PYTHON_INSTALL_MIRROR`, see §4).
- **Berkeley DB** in the Linux CPython builds is recorded as an open legal item (proposed text in §8). HYPRN MVP does not redistribute the interpreter, and Linux is not blocked.
- **Packages** stay at the reviewed sets. A version moves only when CPython 3.12.15 requires it or when a published security fix applies, and each move is re-audited. OpenMDAO 3.45.1 and AiiDA (aiida-core 2.9.3) do not move.

## 2. uv 0.12.24

### Identity

| Field | Value |
|---|---|
| Project | uv, Astral (`astral-sh/uv`) |
| Version | **0.12.24** |
| Published | 2026-10-08 20:06:20 UTC |
| Release page | https://github.com/astral-sh/uv/releases/tag/0.12.24 |
| Tag commit | `5411378eb76dc1ea1ad90aeb10e84e997e5bbd96` |
| Release properties | Not a prerelease or a draft; GitHub immutable release (`immutable: true`); published by the release bot |
| Release tooling | cargo-dist 0.32.0 (`dist-workspace.toml` at the tag, and `dist_version` in `dist-manifest.json`) |
| `sha256.sum` | 1,901 bytes; its own SHA-256 is `64a2cd5ba4fddb06558fd283cd80c69d133e67270358be859a5d942d0d09e403` |
| `dist-manifest.json` | 54,379 bytes; its own SHA-256 is `e74ba5c572cd58d72d7414d8cfdc3462b116943120b962ce3f13e6eb8c624ac0` |

Newer releases: 0.13.0 was published 2026-10-09. It is a new minor series with breaking changes, including Python 3.15 as the default download, so it falls outside the decision (see D3 in §7).

### Per-platform archives

Download base: `https://github.com/astral-sh/uv/releases/download/0.12.24/`

| Platform | Rust target | Archive | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| macOS arm64 | `aarch64-apple-darwin` | `uv-aarch64-apple-darwin.tar.gz` | 14,650,202 | `0c4346de7abdb49495b393b9ec809fe387aa43e586be20fecb972216c1e71732` |
| macOS x86_64 | `x86_64-apple-darwin` | `uv-x86_64-apple-darwin.tar.gz` | 18,120,254 | `4fa82e37cb94767661f532b001e470b67a186c7260e305bd84ddb78fd545c0b6` |
| Linux x86_64 (glibc) | `x86_64-unknown-linux-gnu` | `uv-x86_64-unknown-linux-gnu.tar.gz` | 17,249,236 | `b4dfaef47d491a7296981f8374a4595f55dbf84e8937c8ecd2983574d8bb3da6` |
| Linux aarch64 (glibc) | `aarch64-unknown-linux-gnu` | `uv-aarch64-unknown-linux-gnu.tar.gz` | 16,478,994 | `5231be65f496304623895dacdbf1de8504fec90303684bdf05805aa34414dd21` |

Full URLs:

- https://github.com/astral-sh/uv/releases/download/0.12.24/uv-aarch64-apple-darwin.tar.gz
- https://github.com/astral-sh/uv/releases/download/0.12.24/uv-x86_64-apple-darwin.tar.gz
- https://github.com/astral-sh/uv/releases/download/0.12.24/uv-x86_64-unknown-linux-gnu.tar.gz
- https://github.com/astral-sh/uv/releases/download/0.12.24/uv-aarch64-unknown-linux-gnu.tar.gz

Archive contents, according to `dist-manifest.json`: two executables, `uv` and `uvx`, in a top-level `uv-<target>/` folder. `auto-includes = false` is set in `dist-workspace.toml`, so **the archives contain no licence or README files.**

Minimum glibc, from `[dist.min-glibc-version]` in `dist-workspace.toml`: 2.17 for `x86_64-unknown-linux-gnu` and 2.28 for `aarch64-unknown-linux-gnu`.

### Licence

| Field | Value |
|---|---|
| Licence | `MIT OR Apache-2.0` (dual, at the user's option), declared as `license` in `Cargo.toml` at the tag |
| MIT text | https://github.com/astral-sh/uv/blob/0.12.24/LICENSE-MIT (git blob `014835144877ea9c926d027ece3e1a26290cf481`, 1,077 bytes) |
| Apache-2.0 text | https://github.com/astral-sh/uv/blob/0.12.24/LICENSE-APACHE (git blob `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`, 11,357 bytes) |
| Statically linked third-party code | The binary embeds third-party Rust crates, among them `rustls` and the Mozilla root certificates. The release publishes no per-crate licence inventory. Because HYPRN MVP downloads uv on the user's machine from upstream and does not redistribute it, the two texts above are enough for this record. Bundling uv would first need a crate licence inventory built from `Cargo.lock` at the tag |

### Attestations

- Each of the four archives has two GitHub artifact attestations, queried by SHA-256 from the GitHub attestations API:
  - an SLSA provenance v1 attestation (`https://slsa.dev/provenance/v1`), signed by workflow `.github/workflows/release.yml` at `refs/heads/main`. Releases are started by workflow dispatch, so the signer ref is `main`, not the tag.
  - an immutable-release attestation (`https://in-toto.io/attestation/release/v0.2`).
- `dist-workspace.toml` attests `*.json`, `*.sh`, `*.ps1`, `*.zip` and `*.tar.gz`. The checksum files themselves are not attested. The archives they describe are.
- Verification is optional and manual; the GitHub CLI is not a prerequisite of `./hyprn-mvp`. The commands are:

      gh attestation verify uv-aarch64-apple-darwin.tar.gz --repo astral-sh/uv \
        --signer-workflow astral-sh/uv/.github/workflows/release.yml
      gh release verify-asset 0.12.24 uv-aarch64-apple-darwin.tar.gz --repo astral-sh/uv

  Do not add `--source-ref refs/tags/0.12.24`, because the provenance records `refs/heads/main`.

### Release notes relevant to HYPRN MVP

0.12.24 verifies supplied hashes even when hash presence is disabled (#22369) and honours exact managed-Python patch pins (#22360). The relocking fix from 0.12.22 (#22083) checks unchanged requirements against existing lockfile hashes, and 0.12.24 includes it.

## 3. CPython 3.12.15 as provisioned by uv 0.12.24

### Identity

| Field | Value |
|---|---|
| CPython | 3.12.15, released 2026-09-30, the latest 3.12 security release (no `v3.12.16` tag exists) |
| Builder | python-build-standalone (`astral-sh/python-build-standalone`) |
| Build tag | **`20261003`**. uv 0.12.24's metadata names only this build for 3.12.15, on every platform |
| Release page | https://github.com/astral-sh/python-build-standalone/releases/tag/20261003 |
| Tag commit | `5e46737f6480fc315ebfea83866910cbfcc772f0` |
| Published | 2026-10-03 14:56:28 UTC; GitHub immutable release |
| Flavour fetched by uv | `install_only_stripped`: the `install/` tree of the full distribution, with debug symbols stripped and the test packages and static `libpython` removed |
| Hash source used by uv | `crates/uv-python-managed/download-metadata.json` at the uv tag commit (git blob `260bfabeb42d3dbf964495a43fde73c0b665e766`, SHA-256 `70f6e2872d43589fc34a7d04b6e4506bfd395ddf94663122d9448dd7766bda54`). The metadata is compiled into the uv binary, and uv refuses a mismatching download (`HashMismatch` in `crates/uv-python-managed/src/downloads.rs`). The file moved from `crates/uv-python/` in #22301 |
| Cross-check | The release `SHA256SUMS` (128,236 bytes; its own SHA-256 is `d629718db5cfecb28494e6ba83386ee9a1205975493f904392dac2e3fe5f8813`) and the GitHub asset digests. All agree with uv's metadata |
| Attestations | Each of the four archives has SLSA provenance v1 (`.github/workflows/release.yml` at `refs/heads/main`) and an immutable-release attestation. Command: `gh attestation verify <archive> --repo astral-sh/python-build-standalone --signer-workflow astral-sh/python-build-standalone/.github/workflows/release.yml` |
| Architecture variant | uv selects the baseline `x86_64` build. `Arch::from_env()` in `crates/uv-platform/src/arch.rs` sets `variant: None`, so the `x86_64_v2`, `v3` and `v4` builds are not used |

### Per-platform archives

Download base: `https://github.com/astral-sh/python-build-standalone/releases/download/20261003/`. In URLs, `+` is encoded as `%2B`.

| Platform | uv key | Archive | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| macOS arm64 | `cpython-3.12.15-darwin-aarch64-none` | `cpython-3.12.15+20261003-aarch64-apple-darwin-install_only_stripped.tar.gz` | 25,013,243 | `ad8d0c637c0a36b967b310e2c07254f4d2ca8cabaa7699e55ed6290aceb481a2` |
| macOS x86_64 | `cpython-3.12.15-darwin-x86_64-none` | `cpython-3.12.15+20261003-x86_64-apple-darwin-install_only_stripped.tar.gz` | 24,733,148 | `562c30864ece2cb1d3e0ad66a1acd498611a47e5a10ce81b99158bef1ccbd355` |
| Linux x86_64 (glibc) | `cpython-3.12.15-linux-x86_64-gnu` | `cpython-3.12.15+20261003-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz` | 34,285,590 | `731af898886c5f821890dc901eca3c651cca8e51fa7308c159d12a1194aeac91` |
| Linux aarch64 (glibc) | `cpython-3.12.15-linux-aarch64-gnu` | `cpython-3.12.15+20261003-aarch64-unknown-linux-gnu-install_only_stripped.tar.gz` | 29,215,308 | `6541297dd1798dec8b98c3ad7492808a5b9d1c126801ceb2011e7754cd20d1ce` |

Full URLs (as recorded in uv's metadata):

- https://github.com/astral-sh/python-build-standalone/releases/download/20261003/cpython-3.12.15%2B20261003-aarch64-apple-darwin-install_only_stripped.tar.gz
- https://github.com/astral-sh/python-build-standalone/releases/download/20261003/cpython-3.12.15%2B20261003-x86_64-apple-darwin-install_only_stripped.tar.gz
- https://github.com/astral-sh/python-build-standalone/releases/download/20261003/cpython-3.12.15%2B20261003-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
- https://github.com/astral-sh/python-build-standalone/releases/download/20261003/cpython-3.12.15%2B20261003-aarch64-unknown-linux-gnu-install_only_stripped.tar.gz

Minimum OS levels:

- glibc 2.17 for both Linux builds (`docs/running.md`).
- macOS 11.0 for arm64 and macOS 10.15 for x86_64 (`-mmacosx-version-min` in `cpython-unix/targets.yml`).

### Bundled libraries and licences

Sources for this table, all at the tag commit `5e46737f…`:

- `pythonbuild/downloads.json`: versions, SPDX identifiers and licence files.
- `cpython-unix/targets.yml`: which components each target links.
- `cpython-unix/extension-modules.yml` and `cpython-unix/build-cpython.sh`: how each component is linked.

Build-only tools are not shipped and are not listed: autoconf, m4, pkgconf, binutils, patchelf, LLVM, the Linux UAPI headers and xorgproto. The build tooling itself is MPL-2.0 (repository `LICENSE`) and is not part of the install tree.

| Component | Version | Licence (as recorded upstream) | macOS | Linux |
|---|---|---|---|---|
| CPython | 3.12.15 | `Python-2.0` and `CNRI-Python` (the CPython licence stack, including the PSF-2.0 agreement) | yes | yes |
| OpenSSL | 3.5.9 (latest 3.5 release, 2026-09-29) | Apache-2.0 | yes | yes |
| SQLite | 3.53.1 (`3530100`) | public domain (empty SPDX list, `LICENSE.sqlite.txt`) | yes | yes |
| expat | 2.8.5 (linked with `--with-system-expat`, which replaces CPython's bundled copy) | MIT | yes | yes |
| libffi | 3.4.8 | MIT | yes | yes |
| bzip2 | 1.0.8 | bzip2-1.0.6 | yes | yes |
| xz (liblzma) | 5.8.4 | 0BSD | yes | yes |
| zstd | 1.5.7 | BSD-3-Clause, as recorded upstream (zstd itself is dual BSD-3-Clause or GPL-2.0-only) | yes | yes |
| mpdecimal | 4.0.0 | BSD-2-Clause | yes | yes |
| libuuid | 1.0.3 | BSD-3-Clause | yes | yes |
| Tcl / Tk | 9.0.4 / 9.0.4 (`_tkinter` is a shared extension module) | TCL | yes | yes |
| zlib | 1.3.2 | Zlib | system | yes |
| libedit | 20240808-3.1 | BSD-3-Clause | system | yes |
| ncurses | 6.5 | X11 | system | yes |
| libX11 / libXau / libxcb | 1.8.13 / 1.0.12 / 1.17.0 | MIT and X11 / MIT / MIT | — | yes (for Tk) |
| **Berkeley DB** | **6.0.19** | **Sleepycat** (source-availability clause) | — (macOS `_dbm` uses the system ndbm) | **yes** |

Notes on the table:

- **Berkeley DB on Linux.** It is linked into the `_dbm` extension module, and `extension-modules.yml` sets `build-mode: shared` for that module. The comment there says this is "to allow people who want to avoid the Sleepycat license to remove `_dbm` entirely". In these builds `_dbm` is therefore a separate `lib-dynload/_dbm.cpython-312-*.so` file and not part of `libpython`. The upstream issue astral-sh/python-build-standalone#836 ("Remove Berkley DB library from distributions") is still open. See §8.
- **Not linked:** GNU readline (GPL-3.0; libedit is used instead) and GDBM (GPL-3.0; `_gdbm` is disabled for every target), according to `docs/running.md` "Licensing" and `extension-modules.yml`.
- **No pip or setuptools.** They are not in the `install_only` tree; `--without-ensurepip` is set.

### Licence texts in the archive

This is established from the build metadata only and has not yet been checked on an extracted archive.

- `src/release.rs` (`convert_to_install_only`) keeps only entries under `python/install/`.
- In the full distribution, the third-party licence texts are under `python/licenses/` (`license_path: licenses/LICENSE.cpython.txt` in `cpython-unix/build.py`). **The `install_only_stripped` archives therefore do not carry the third-party licence texts.**
- CPython's own `LICENSE` is installed as `lib/python3.12/LICENSE.txt` (`Makefile.pre.in` at `v3.12.15`) and is present.
- The third-party texts are published in the python-build-standalone repository at the tag (`LICENSE.*.txt`, `python-licenses.rst`).
- Step 2 of task 2.1 confirms all of this on the first verified extraction. That is enough because HYPRN MVP does not redistribute the interpreter.

### Residual in the selected build

The build python-build-standalone published after uv 0.12.24, **`20261009`**, links expat **2.9.0** and libffi 3.8.0 and is otherwise identical in the components above. uv 0.13.0 names that build.

expat 2.9.0 (2026-10-05) fixes two issues that 2.8.5 still has:

- CVE-2026-77214: `XML_ParseBuffer` does not validate `len`. This is reachable in principle through `xml.parsers.expat` `ParseFile`.
- CVE-2026-102633: an integer overflow on 32-bit platforms only. It does not apply to the four targets above.

Severity and actual reachability from HYPRN MVP have not been assessed. See D2 in §7.

## 4. Network and TLS

- **Shell entry point (uv download):** `curl --proto '=https' --tlsv1.2 -fsSL`.
  - `github.com` answers with a 302 redirect to `release-assets.githubusercontent.com`. `--proto =https` also restricts the protocols of redirects.
  - Hosts to allow: `github.com` and `release-assets.githubusercontent.com`.
  - curl uses the operating system's trust store.
- **uv (CPython download):** set `UV_PYTHON_INSTALL_MIRROR=https://github.com/astral-sh/python-build-standalone/releases/download`.
  - In 0.12.24, a user-configured mirror is used **exclusively, with no automatic fallback** (`download_urls_with_astral_mirror` in `crates/uv-python-managed/src/downloads.rs`). The URL is the mirror followed by the suffix after the canonical GitHub prefix, which gives exactly the URLs above.
  - Without this setting, uv tries the Astral mirror (`releases.astral.sh`) first and falls back to GitHub.
  - The embedded SHA-256 is enforced in both cases.
- **TLS:** uv uses rustls with bundled Mozilla roots. On networks with TLS interception, `UV_SYSTEM_CERTS=true` (or `SSL_CERT_FILE`) is needed.
- **Hermetic invocation:** these settings exist in 0.12.24 (`crates/uv-static/src/env_vars.rs`):
  - `UV_NO_CONFIG=1`
  - `UV_PYTHON_PREFERENCE=only-managed`
  - `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` under the tool cache
  - `UV_FROZEN` or `UV_LOCKED`
- **Checksum file formats:**
  - uv `sha256.sum`: `<hex> *<name>`
  - uv per-asset `.sha256`: `<hex>  <name>`
  - python-build-standalone `SHA256SUMS`: `<hex>  <name>`, with a literal `+`

  The entry point compares against the 64-hex value pinned in `deployment/locks/tools.json` (`shasum -a 256` on macOS, `sha256sum` on Linux) and never parses a downloaded checksum file at run time.

## 5. Package security review (Python)

### Method

- **Query.** OSV batch API (`https://api.osv.dev/v1/querybatch`, ecosystem `PyPI`), queried 2026-10-13 for every exact name and version. Each advisory's detail came from `https://api.osv.dev/v1/vulns/<id>`.
- **Control query.** `jinja2==2.10` and `vite@5.0.0` returned advisories, which confirms that name normalisation and the endpoint work.
- **Compatibility.** Wheel availability for CPython 3.12 (`cp312`, `abi3` or pure `py3-none-any`) was checked per platform from the PyPI JSON API. Wheel tags are the same across 3.12 patch releases, so 3.12.15 changes nothing relative to the reviewed 3.12 sets.

### Sets reviewed

These are the inputs that task 2.1 step 3 locks, plus the worker sets for completeness: 112 distinct name and version pairs.

| Key | Set | Pinned distributions |
|---|---|---|
| A | `application/requirements.lock` | 28 |
| T | `integration/test-requirements.lock` | 5 |
| W | `integration/worker-requirements.lock` | 20. The reviewed worker image also has pip 25.0.1, which no lock lists |
| N | Phase 1 native development interpreter (reviewed installed inventory) | 89, including aiida-core 2.9.3 |
| C | Phase 1 contract development interpreter | Equal to A, plus pip 25.1.1 |

The repository has no other Python lock file. `integration/pyproject.toml` declares the build requirement `setuptools>=61`, which is unpinned (see D6 in §7).

### Advisories affecting pinned versions

| Package | Pinned | Set | Advisory (aliases) | Severity | Fixed in | Fix compatible with the set? |
|---|---|---|---|---|---|---|
| pytest | 9.0.2 | T | GHSA-6w46-j5rx-g56g (CVE-2025-71176, PYSEC-2026-1845): tmpdir handling | Moderate (CVSS 3.1 AV:L) | 9.0.3 | **Yes.** 9.1.1 is already the reviewed version in A and N. Its requirements (`iniconfig>=1.0.1`, `packaging>=22`, `pluggy>=1.5,<2`, `pygments>=2.7.2`) are met by the pins in T. AiiDA's `pytest~=7.0` applies only to its `tests` extra, which is not installed |
| pip | 25.0.1 | worker image | GHSA-4xh5-x5gv-qwph (CVE-2025-8869): fallback tar extraction does not check that symbolic links stay in the extraction directory | Moderate | 25.3 | pip is in no lock. See D4 |
| | | | GHSA-6vgw-5pg2-w6jp (CVE-2026-1703): path traversal | Low | 26.0 | |
| | | | GHSA-58qw-9mgm-455v (CVE-2026-3219): concatenated tar and ZIP files handled as ZIP | Moderate | 26.1 | |
| | | | GHSA-jp4c-xjxw-mgf9 (CVE-2026-6357): inclusion of functionality from an untrusted control sphere | Moderate | 26.1 | |
| | | | GHSA-wf93-45jw-7689 (CVE-2026-8643): path traversal in entry-point names | Moderate | 26.1.2 | |
| | | | GHSA-qwm4-qh6w-59xr (CVE-2026-13346): doubly encoded index URLs | Moderate | 26.2 | |
| pip | 25.1.1 | C | The same six advisories | as above | 26.2 (latest 26.2.1) | The contract interpreter is retired by the locked environment. uv does not seed pip into its environments |
| paramiko | 3.5.1 | N | GHSA-r374-rxx8-8654 (CVE-2026-44405, PYSEC-2026-2858): `rsakey.py` allows SHA-1 | Low (CVSS 3.1 AV:A/AC:H) | No 3.x fix. Last affected: 4.0.0. 5.0.0 is not affected | **No.** aiida-core 2.9.3 requires `paramiko~=3.0`, and AiiDA does not move. The code path is AiiDA's SSH transport. HYPRN MVP configures only `core.local` computers (`deployment/native_environment.py`, `integration/src/hyprn_mvp_integration/computational_export.py`), so paramiko's RSA signing is not exercised. Record as an accepted residual (D5) |

No other pinned Python distribution has a known advisory, and that includes OpenMDAO 3.45.1, aiida-core 2.9.3, numpy 2.5.3, scipy 1.18.1, cryptography 50.0.2, urllib3 2.8.0, requests 2.34.2, starlette 1.7.0 and fastapi 0.143.0. The full list follows.

### CPython 3.12.15 compatibility

No pinned version needs to change for CPython 3.12.15. Every `requires_python` admits 3.12, and the only upper bounds (`<4`) are in aio-pika, aiormq and click-spinner. Three findings concern platforms and artifacts rather than the CPython version:

1. **cryptography 50.0.2 (N) publishes no macOS x86_64 wheel.** cryptography stopped publishing macOS x86_64 wheels from 49.0.0. 48.0.1 still has them, but it is affected by GHSA-g6cj-pr64-35w5 (High, fixed in 50.0.0), GHSA-jwv3-5hgf-82ww (High, fixed in 49.0.0) and GHSA-m2h6-j472-rp4c (Moderate, fixed in 49.0.0). Downgrading is therefore not acceptable, and asyncssh 2.24.1 requires `cryptography>=48.0.1` anyway. On macOS x86_64, the native environment would have to build cryptography from its sdist (`cryptography-50.0.2.tar.gz`, SHA-256 `7b46165bb56eb4704e2eaaf86f3c940d19154535d9b0ca7d6d590b04060e00d5`), which needs a Rust toolchain. See D1.
2. **Three worker packages are sdist-only on PyPI:** `openmdao_extensions` 1.6.3, `wop` 2.6.1 and `xdsmjs` 2.1.0. The hashes in `integration/worker-requirements.lock` are for wheels built locally in the reviewed engine image, not for PyPI artifacts. The PyPI sdist SHA-256 values are:
   - `openmdao_extensions-1.6.3.tar.gz`: `f9ef20afd886a6b21f62e23be29ba14d4502897cc7b4603d4da0187024ee3e59`
   - `wop-2.6.1.tar.gz`: `3aa59f30a99c505227328e9a152c8563537318e3b98e32e45d427b67611f9d88`
   - `xdsmjs-2.1.0.tar.gz`: `55a0bb065496edfcf92fb751b33cdcbcbdf4d8237bdbe317b938f94d46be0746`

   This matters only if the worker set is ever locked with uv; task 2.1 does not lock it.
3. **Platform hash coverage.** The hashes in the existing locks cover only some platforms:
   - In A, `pydantic_core` and `rpds-py` have hashes for macOS arm64 and Linux aarch64 only.
   - In W, `numpy`, `scipy`, `charset-normalizer` and `tomli` have hashes for Linux aarch64 only.

   A universal `uv.lock` adds the wheel hashes for the other platforms. The versions are the same, but those artifact hashes are new and are part of the review of the lock diff.

The reviewed sets disagree with each other. Step 3 of task 2.1 already plans two locked projects for this case (contract and native), and none of these differences is a security bump:

| Package | N | A, T or W |
|---|---|---|
| click | 8.2.1 | 8.5.0 (A and W). AiiDA requires `click>=8.1.0,<8.3` |
| pydantic and pydantic-core | 2.13.5 and 2.46.5 | 2.14.0 and 2.50.0 (A) |
| tabulate | 0.9.0 | 0.10.0 (W). AiiDA requires `tabulate>=0.9.0,<0.10.0` |
| pytest | 9.1.1 | 9.0.2 (T) |

### All pinned Python distributions

Sets: A application, T integration test, W worker lock (and worker image), N native interpreter, C contract interpreter extra. "OSV result" lists GHSA identifiers; the PYSEC and CVE aliases are in the table above.

| Package | Version | Sets | OSV result |
|---|---|---|---|
| aiida-core | 2.9.3 | N | none |
| aio-pika | 9.5.8 | N | none |
| aiormq | 6.9.4 | N | none |
| alembic | 1.20.0 | N | none |
| annotated-doc | 0.0.5 | A | none |
| annotated-types | 0.8.0 | A, N | none |
| anyio | 4.15.1 | A, N | none |
| archive-path | 0.4.2 | N | none |
| asttokens | 3.0.2 | N | none |
| asyncssh | 2.24.1 | N | none |
| attrs | 26.1.0 | A, N | none |
| bcrypt | 5.0.0 | N | none |
| build | 1.6.1 | W | none |
| certifi | 2026.7.22 | A, W, N | none |
| cffi | 2.1.1 | N | none |
| charset-normalizer | 3.5.2 | W, N | none |
| circus | 0.19.0 | N | none |
| click | 8.2.1 | N | none |
| click | 8.5.0 | A, W | none |
| click-spinner | 0.1.11 | N | none |
| cryptography | 50.0.2 | N | none |
| deprecation | 2.1.0 | N | none |
| disk-objectstore | 1.5.0 | N | none |
| docstring-parser | 0.18.0 | N | none |
| executing | 2.2.1 | N | none |
| fastapi | 0.143.0 | A | none |
| graphviz | 0.21 | N | none |
| greenback | 1.3.0 | N | none |
| greenlet | 3.5.6 | N | none |
| h11 | 0.16.0 | A, N | none |
| httpcore | 1.0.9 | A, N | none |
| httpx | 0.28.1 | A, N | none |
| idna | 3.20 | A, W, N | none |
| importlib-metadata | 6.11.0 | N | none |
| iniconfig | 2.3.1 | A, T, N | none |
| ipython | 9.17.1 | N | none |
| ipython-pygments-lexers | 1.1.1 | N | none |
| jedi | 0.18.2 | N | none |
| jinja2 | 3.1.6 | N | none |
| jsonschema | 4.26.0 | A, N | none |
| jsonschema-specifications | 2025.9.1 | A, N | none |
| kiwipy | 0.9.0 | N | none |
| mako | 1.4.3 | N | none |
| markupsafe | 3.0.4 | N | none |
| matplotlib-inline | 0.2.2 | N | none |
| multidict | 7.0.0 | N | none |
| networkx | 3.7 | W | none |
| numpy | 2.5.3 | W, N | none |
| openmdao | 3.45.1 | W | none |
| openmdao-extensions | 1.6.3 | W | none |
| opentelemetry-api | 1.45.1 | A | none |
| outcome | 1.3.0.post0 | N | none |
| packaging | 26.3 | A, T, W, N | none |
| pamqp | 3.3.0 | N | none |
| paramiko | 3.5.1 | N | GHSA-r374-rxx8-8654 |
| parso | 0.8.7 | N | none |
| pexpect | 4.9.0 | N | none |
| pgsu | 0.3.0 | N | none |
| pip | 25.0.1 | Wi | GHSA-4xh5-x5gv-qwph, GHSA-58qw-9mgm-455v, GHSA-6vgw-5pg2-w6jp, GHSA-jp4c-xjxw-mgf9, GHSA-qwm4-qh6w-59xr, GHSA-wf93-45jw-7689 |
| pip | 25.1.1 | C | GHSA-4xh5-x5gv-qwph, GHSA-58qw-9mgm-455v, GHSA-6vgw-5pg2-w6jp, GHSA-jp4c-xjxw-mgf9, GHSA-qwm4-qh6w-59xr, GHSA-wf93-45jw-7689 |
| pkginfo | 1.13 | W | none |
| pluggy | 1.6.0 | A, T, N | none |
| plumpy | 0.26.1 | N | none |
| prompt-toolkit | 3.0.53 | N | none |
| propcache | 0.5.4 | N | none |
| psutil | 7.2.2 | N | none |
| psycopg | 3.3.6 | N | none |
| psycopg-binary | 3.3.6 | N | none |
| ptyprocess | 0.7.0 | N | none |
| pure-eval | 0.2.4 | N | none |
| pycparser | 3.1 | N | none |
| pydantic | 2.13.5 | N | none |
| pydantic | 2.14.0 | A | none |
| pydantic-core | 2.46.5 | N | none |
| pydantic-core | 2.50.0 | A | none |
| pygments | 2.21.0 | A, T, N | none |
| pynacl | 1.6.2 | N | none |
| pyproject-hooks | 1.3.3 | W | none |
| pytest | 9.0.2 | T | GHSA-6w46-j5rx-g56g |
| pytest | 9.1.1 | A, N | none |
| pytray | 0.3.4 | N | none |
| pytz | 2021.3 | N | none |
| pyyaml | 6.0.3 | N | none |
| pyzmq | 27.2.0 | N | none |
| referencing | 0.37.0 | A, N | none |
| requests | 2.34.2 | W, N | none |
| rfc8785 | 0.1.4 | A, N | none |
| rpds-py | 2026.9.1 | A, N | none |
| ruff | 0.16.10 | N | none (formatter and linter added to the native development set, §11) |
| scipy | 1.18.1 | W | none |
| shortuuid | 1.0.13 | N | none |
| sniffio | 1.3.1 | N | none |
| sqlalchemy | 2.1.4 | N | none |
| stack-data | 0.6.3 | N | none |
| starlette | 1.7.0 | A | none |
| tabulate | 0.10.0 | W | none |
| tabulate | 0.9.0 | N | none |
| tomli | 2.5.0 | W | none |
| tomli-w | 1.2.0 | W | none |
| tornado | 6.5.10 | N | none |
| tqdm | 4.70.1 | N | none |
| traitlets | 5.16.1 | N | none |
| typing-extensions | 4.16.0 | A, N | none |
| typing-inspection | 0.4.4 | A, N | none |
| upf-to-json | 0.9.5 | N | none |
| urllib3 | 2.8.0 | W, N | none |
| uvicorn | 0.54.0 | A | none |
| wcwidth | 0.9.2 | N | none |
| wop | 2.6.1 | W | none |
| wrapt | 1.17.3 | N | none |
| xdsmjs | 2.1.0 | W | none |
| yarl | 1.25.1 | N | none |
| zipp | 4.1.1 | N | none |


## 6. Package security review (UI, npm)

- **Method:** OSV batch API, ecosystem `npm`, queried 2026-10-13 for every package entry in `ui/package-lock.json` (lockfile version 3). That is 52 distinct name and version pairs:
  - 8 direct packages;
  - 44 transitive packages, 28 of which are optional platform-specific binaries for rolldown, lightningcss and fsevents.
  - Since §12, a ninth direct package: `prettier@3.9.10` (development only, no dependencies; OSV none), so the lock holds 53 pairs.
- **Result: no known advisory affects any pinned npm package.**
- **Direct packages:**
  - `react@19.3.0`
  - `react-dom@19.3.0`
  - `vite@8.3.4`
  - `typescript@5.9.3`
  - `@types/react@19.3.0`
  - `@types/react-dom@19.3.0`
  - `@types/node@26.6.4`
  - `playwright@1.62.1`
- **Transitive packages:**
  - `@oxc-project/types@0.153.0`
  - `@rolldown/binding-*@1.2.13` (15 platform packages)
  - `@rolldown/pluginutils@1.0.1`
  - `csstype@3.2.3`
  - `detect-libc@2.1.2`
  - `fdir@6.5.0`
  - `fsevents@2.3.2` and `fsevents@2.3.3`
  - `lightningcss@1.33.0` and `lightningcss-*@1.33.0` (12 platform packages)
  - `nanoid@3.3.20`
  - `picocolors@1.1.1`
  - `picomatch@4.0.7`
  - `playwright-core@1.62.1`
  - `postcss@8.5.29`
  - `rolldown@1.2.13`
  - `scheduler@0.28.0`
  - `source-map-js@1.2.2`
  - `tinyglobby@0.2.17`
  - `undici-types@8.9.0`
- **No npm change is recommended.**

## 7. Recommended changes and decisions

### Minimal bump list

| Package | From | To | Where | Reason |
|---|---|---|---|---|
| pytest | 9.0.2 | **9.1.1** | `integration/test-requirements.lock` and the integration test set in `uv.lock` | GHSA-6w46-j5rx-g56g (CVE-2025-71176), fixed in 9.0.3. 9.1.1 is already the reviewed version in the application and native sets, so no unreviewed version enters. Its dependency pins are unchanged |

That is the only version move for the locked environments. Every other pinned version stays at the reviewed sets.

### Kept out of the locked environments

pip appears in no reviewed lock. uv creates environments without pip unless `--seed` is passed, so the locked environments contain no pip and the six pip advisories do not apply to them. Keep `--seed` out of the entry point.

### Decisions for the product owner

- **D1. Native environment on macOS x86_64 (blocking for that platform only).** cryptography 50.0.2 has no macOS x86_64 wheel, and the last version that has one (48.0.1) carries two High advisories. Options:
  - (a) support the native environment on macOS arm64 and Linux x86_64/aarch64 only, and have `./hyprn-mvp` refuse the native environment on macOS x86_64 with an explanation. The contract environment works on all four platforms. Recommended.
  - (b) allow a source build of cryptography 50.0.2 on macOS x86_64. This needs a Rust toolchain and OpenSSL headers, makes the build non-hermetic, and brings in new build-time dependencies that would need their own audit.
  - (c) run the native environment in a Linux container on macOS x86_64.
- **D2. expat residual in build `20261003`.** Options:
  - (a) accept build `20261003` (expat 2.8.5) as uv 0.12.24 pins it, record CVE-2026-77214 as a residual, and move with the next uv update. Recommended; it follows the decision literally.
  - (b) point uv 0.12.24 at a reviewed metadata file naming build `20261009` (expat 2.9.0) with `UV_PYTHON_DOWNLOADS_JSON_URL`. This adds a second pinned artifact to `deployment/locks/tools.json`.
  - (c) see D3.
- **D3. uv 0.13.0 (information).** 0.13.0 (2026-10-09) names build `20261009`. It is a breaking minor series: Python 3.15 is the default download, `--require-hashes` is honoured in included constraints files, and the cache format changes. The decision fixes 0.12.24, so 0.13 is not adopted here.
- **D4. pip in the worker image.** The reviewed worker image contains pip 25.0.1, which has six advisories (fixed in 26.2). The worker runs without network, and pip is not used at run time. Options:
  - (a) remove pip from the worker image at its next rebuild. Recommended, because the worker never installs packages.
  - (b) upgrade it to 26.2.1.
  - (c) record it as a residual until the worker image is rebuilt.

  This is outside task 2.1's files. It belongs to the worker image's own review.
- **D5. paramiko 3.5.1 residual.** GHSA-r374-rxx8-8654 is Low severity, has no fix in 3.x, and is pinned in place by aiida-core 2.9.3 (`paramiko~=3.0`). HYPRN MVP uses only AiiDA's `core.local` transport. Recommended: accept it as a recorded residual until AiiDA moves.
- **D6. Workspace build backend.** `integration/pyproject.toml` has `setuptools>=61` as its build requirement, unpinned. Building the workspace member would fetch a setuptools release that is not in the reviewed sets; the latest is 84.0.0 (MIT), which has no OSV advisory. Options:
  - (a) mark workspace members as non-packaged (`[tool.uv] package = false`) and import them from source. No build backend is fetched. Recommended if the tests do not need installed entry points.
  - (b) pin `setuptools==<exact>` and audit it as a new dependency.

  AiiDA's `aiida.calculations` and `aiida.parsers` entry points come from installed distribution metadata, so the native project may need (b) or an equivalent.

## 8. Proposed open legal item for `docs/legal/licensing.md`

| ID | Item | Interim handling |
|---|---|---|
| L6 | Berkeley DB 6.0.19 (Sleepycat licence) is linked into the `_dbm` extension module of the Linux CPython builds that uv provisions (python-build-standalone `20261003`). Sleepycat requires redistributions to offer the complete source of the DB software and of any software that uses it | HYPRN MVP does not redistribute the interpreter: each installation downloads it from the python-build-standalone GitHub release with a pinned SHA-256. Linux is not blocked. Before any distribution that ships an interpreter (local-edition bundle, images), either remove `lib-dynload/_dbm*.so`, which upstream builds as a separate shared module for this purpose (no HYPRN MVP code uses `dbm`; to be confirmed by a scan), or obtain counsel's view together with L4. Upstream: astral-sh/python-build-standalone#836 |

## 9. Sources

uv:

- Release 0.12.24: https://github.com/astral-sh/uv/releases/tag/0.12.24 (API: https://api.github.com/repos/astral-sh/uv/releases/tags/0.12.24)
- Checksums: https://github.com/astral-sh/uv/releases/download/0.12.24/sha256.sum and the per-asset files https://github.com/astral-sh/uv/releases/download/0.12.24/uv-aarch64-apple-darwin.tar.gz.sha256 (same pattern for the other three targets)
- Dist manifest: https://github.com/astral-sh/uv/releases/download/0.12.24/dist-manifest.json
- Release list: https://api.github.com/repos/astral-sh/uv/releases
- Attestations: `https://api.github.com/repos/astral-sh/uv/attestations/sha256:<digest>`
- Licence: https://github.com/astral-sh/uv/blob/0.12.24/LICENSE-MIT, https://github.com/astral-sh/uv/blob/0.12.24/LICENSE-APACHE, https://github.com/astral-sh/uv/blob/0.12.24/Cargo.toml
- Release configuration: https://github.com/astral-sh/uv/blob/0.12.24/dist-workspace.toml
- Python download metadata and logic:
  - https://github.com/astral-sh/uv/blob/0.12.24/crates/uv-python-managed/download-metadata.json
  - https://github.com/astral-sh/uv/blob/0.12.24/crates/uv-python-managed/src/downloads.rs
  - https://github.com/astral-sh/uv/blob/0.12.24/crates/uv-platform/src/arch.rs
  - https://github.com/astral-sh/uv/blob/0.12.24/crates/uv-static/src/env_vars.rs
- Comparison: https://github.com/astral-sh/uv/releases/tag/0.13.0 and https://github.com/astral-sh/uv/blob/0.13.0/crates/uv-python-managed/download-metadata.json

python-build-standalone:

- Release 20261003: https://github.com/astral-sh/python-build-standalone/releases/tag/20261003
- Checksums: https://github.com/astral-sh/python-build-standalone/releases/download/20261003/SHA256SUMS
- Attestations: `https://api.github.com/repos/astral-sh/python-build-standalone/attestations/sha256:<digest>`
- Components, linkage and packaging, all at the tag:
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/pythonbuild/downloads.json
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/cpython-unix/targets.yml
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/cpython-unix/extension-modules.yml
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/cpython-unix/build-cpython.sh
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/cpython-unix/build.py
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/src/release.rs
- Documentation and licence texts:
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/docs/running.md
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/docs/distributions.md
  - https://github.com/astral-sh/python-build-standalone/blob/20261003/python-licenses.rst
  - the `LICENSE.*.txt` files at the tag
- Berkeley DB issue: https://github.com/astral-sh/python-build-standalone/issues/836
- Comparison build: https://github.com/astral-sh/python-build-standalone/releases/tag/20261009 (`pythonbuild/downloads.json` at that tag)

CPython and bundled libraries:

- CPython 3.12.15: https://www.python.org/downloads/release/python-31215/, https://github.com/python/cpython/blob/v3.12.15/Makefile.pre.in
- libexpat changes: https://github.com/libexpat/libexpat/blob/master/expat/Changes
- OpenSSL releases: https://github.com/openssl/openssl/releases (3.5.9, 2026-09-29)

Package review:

- OSV: https://api.osv.dev/v1/querybatch and https://api.osv.dev/v1/vulns/<id>
- Advisories: https://github.com/advisories/GHSA-6w46-j5rx-g56g, https://github.com/advisories/GHSA-r374-rxx8-8654, https://github.com/advisories/GHSA-4xh5-x5gv-qwph, https://github.com/advisories/GHSA-6vgw-5pg2-w6jp, https://github.com/advisories/GHSA-58qw-9mgm-455v, https://github.com/advisories/GHSA-jp4c-xjxw-mgf9, https://github.com/advisories/GHSA-wf93-45jw-7689, https://github.com/advisories/GHSA-qwm4-qh6w-59xr, https://github.com/advisories/GHSA-g6cj-pr64-35w5, https://github.com/advisories/GHSA-jwv3-5hgf-82ww, https://github.com/advisories/GHSA-m2h6-j472-rp4c
- PyPI metadata (requirements, wheels, hashes): `https://pypi.org/pypi/<name>/<version>/json`, notably https://pypi.org/pypi/aiida-core/2.9.3/json, https://pypi.org/pypi/pytest/9.1.1/json, https://pypi.org/pypi/cryptography/50.0.2/json, https://pypi.org/pypi/paramiko/json

## 10. Decisions and what the repository applies

### Decisions on §7

| Item | Decision | Where it is applied |
|---|---|---|
| D1 | (a) macOS on Intel (x86_64) is refused (D-05b). Supported hosts: macOS on Apple silicon, Linux x86_64 and aarch64 (glibc), Windows through WSL2 | `./hyprn-mvp` refuses `darwin-x86_64` (and musl Linux) before any download, with the reason recorded in `deployment/locks/tools.json` (`refused_platforms`); `tools.json` pins uv and CPython for the three supported hosts only; `uv.lock` is restricted to them (`environments` and `required-environments` in `pyproject.toml`) |
| D2 | (a) build `20261003` as uv 0.12.24 pins it; expat 2.8.5 (CVE-2026-77214) is an accepted residual until the next uv update | `cpython_build` in `tools.json`; the BUILD file of the managed interpreter is reported by `./hyprn-mvp version` |
| D3 | uv 0.13 is not adopted | `uv_version` in `tools.json` |
| D4 | (a) pip is removed from the worker image at its next rebuild | Outside the locked development environments (worker image) |
| D5 | paramiko 3.5.1 is an accepted residual while aiida-core 2.9.3 pins `paramiko~=3.0`; only the `core.local` transport is used | Native group of `uv.lock` |
| D6 | (b) the build backend is pinned exactly and audited when a workspace package is built | The locked development environments build and install no package of the checkout, so no build backend is fetched: the root project is not packaged (`package = false`) and every install uses `--no-build --no-install-project`. The integration package's AiiDA entry points are registered in the native environment by an authored metadata-only distribution (metadata and entry points, no code, no startup path file), as the native environment manager already does. The exact setuptools pin and its audit come with the first wheel build of the checkout's packages |

### Applied package change

| Package | From | To | Where |
|---|---|---|---|
| pytest | 9.0.2 | 9.1.1 | `integration/test-requirements.lock` (wheel hash `37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c`, the reviewed hash of the application set) |

### Locked development environments (`pyproject.toml`, `uv.lock`)

- One resolution cannot satisfy both reviewed sets (click 8.2.1 and 8.5.0, pydantic 2.13.5 and 2.14.0, pydantic-core 2.46.5 and 2.50.0), so `uv.lock` holds two conflicting dependency groups, each pinned exactly:
  - `contract` = set A (28 distributions), which contains set T after the pytest change;
  - `native` = set N (89 distributions, the reviewed native development set; 90 since ruff 0.16.10 joined it, §13).
- The lock holds 97 distributions: the union of A and N (20 name and version pairs are shared). Its versions equal the reviewed sets; the only difference from the inputs is the approved pytest change in T. No other package and no other version entered. Since §13 it holds 98: ruff 0.16.10 is the only addition.
- Every hash of `application/requirements.lock` and `integration/test-requirements.lock` is in `uv.lock`. The lock adds the published wheel hashes of the same versions for the supported hosts that the older locks did not cover (§5, "Platform hash coverage"); it also lists musllinux wheels and sdists that uv records but never installs (`./hyprn-mvp` refuses musl hosts and every install uses `--no-build`).
- Neither environment contains pip or setuptools (no `--seed`). The worker set W and its sdist-only packages (`openmdao_extensions`, `wop`, `xdsmjs`) are not locked here.
- Installs: `uv sync --frozen --no-build --no-install-project --no-default-groups --group <group>` into `<tool cache>/envs/<group>-<first 16 hex of the uv.lock SHA-256>`, with `UV_NO_CONFIG=1`, `UV_PYTHON_PREFERENCE=only-managed`, `UV_PYTHON_INSTALL_MIRROR` set to the python-build-standalone releases, and the interpreter, cache and binary folders inside the tool cache. After each install the CLI compares the environment's distributions with its group and refuses any difference.

### First verified acquisition (macOS arm64)

- uv: `uv-aarch64-apple-darwin.tar.gz` downloaded by `./hyprn-mvp`, SHA-256 and size equal to §2 before extraction; `uv --version` reports `uv 0.12.24 (5411378eb 2026-10-08 aarch64-apple-darwin)`.
- CPython: installed by uv from the mirror above (uv enforces the embedded SHA-256 of §3). The installation's BUILD file reads `20261003`; it reports CPython 3.12.15, OpenSSL 3.5.9, SQLite 3.53.1, expat 2.8.5 and the system zlib, as §3 records.
- Licence texts: the `install_only_stripped` tree holds only CPython's `lib/python3.12/LICENSE.txt`, confirming §3 "Licence texts in the archive". HYPRN MVP does not redistribute the interpreter.
- Berkeley DB (L6): no source file of HYPRN MVP (`application`, `contracts`, `deployment`, `editions`, `integration`, `modeling`) imports `dbm` or `shelve`. The Linux builds were not extracted on this host.

## 11. ruff 0.16.10 (Python formatter and linter)

Recorded 2026-10-13 from the PyPI JSON API and the GitHub release. ruff and prettier are build and check tools only: neither is shipped in a served bundle, an image or a distribution, and neither is redistributed.

### Identity

| Field | Value |
|---|---|
| Project | ruff, Astral (`astral-sh/ruff`) |
| Version | **ruff 0.16.10**, the latest patch of the 0.16 series. 0.17.0 (2026-10-09) is a breaking minor series and is not adopted |
| Official source | PyPI `ruff`, https://pypi.org/project/ruff/0.16.10/ (download base `https://files.pythonhosted.org/packages/`) |
| Published | 2026-10-01 (wheels uploaded 18:02:36 to 18:03:21 UTC); not yanked |
| Release page | https://github.com/astral-sh/ruff/releases/tag/0.16.10 (not a prerelease or draft; GitHub immutable release, published 2026-10-01 18:04:27 UTC) |
| Tag commit | `3265ed1f944c98bb4c04d632fbefb1257cdb583d` |
| Requires Python | `>=3.7`; the wheel is `py3-none-<platform>` and carries the native binary |
| Dependencies (`requires_dist`) | **none** |
| Known advisories | **none** (OSV batch API, ecosystem `PyPI`, `ruff==0.16.10`, queried 2026-10-13; the control query `jinja2==2.10` returned advisories) |
| Attestations | None: PyPI reports no provenance for the 0.16.10 files (`https://pypi.org/integrity/ruff/0.16.10/<file>/provenance` answers 404). Integrity rests on the SHA-256 that `uv.lock` records and uv verifies on every install |

### Wheels the lock resolves (supported hosts)

The SHA-256 values are those of the PyPI JSON API (`https://pypi.org/pypi/ruff/0.16.10/json`); `uv lock` wrote the same values into `uv.lock`.

| Host | Wheel | Size (bytes) | SHA-256 |
|---|---|---|---|
| macOS arm64 | `ruff-0.16.10-py3-none-macosx_11_0_arm64.whl` | 9,774,282 | `3031a4a2e8e7b8a46f70be45f198c35a11ece509a94b80334d8d397a33c67550` |
| Linux x86_64 (glibc) | `ruff-0.16.10-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` | 10,387,968 | `f33f43a864a8483eebd160e713336c8bab02c934feaff0a33cf5ccb41546d09a` |
| Linux aarch64 (glibc) | `ruff-0.16.10-py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64.whl` | 9,920,895 | `494401c86df4c4c25f69b9419605d944467ee98c42fb6ad405ef4fa40b8fb67d` |
| Linux x86_64 (musl; recorded, never installed) | `ruff-0.16.10-py3-none-musllinux_1_2_x86_64.whl` | 10,741,702 | `7ae7375f803b5520dc9f546bed7e3a0acb70b91812e9bb4b19927de22f25b77d` |
| Linux aarch64 (musl; recorded, never installed) | `ruff-0.16.10-py3-none-musllinux_1_2_aarch64.whl` | 10,012,938 | `6553498afc35f580f036030795810b9e6bcea31604b0fd9e8d352795473042e3` |
| Source (recorded, never built: `--no-build`) | `ruff-0.16.10.tar.gz` | 4,958,724 | `eff4728c4eaae93f0955cd264d24b2ab348e74bf59986ccf282ba6dc16b3b017` |

### Licence

| Field | Value |
|---|---|
| Licence | **MIT** (PyPI `license_expression` is `MIT`; `license = "MIT"` in `pyproject.toml` at the tag) |
| Text | https://github.com/astral-sh/ruff/blob/0.16.10/LICENSE. The file adds the permission notices of the projects the linter and formatter derive from (pycodestyle, Pyflakes, Flake8 plugins, isort, pyupgrade, rome/tools, RustPython and others); all are permissive MIT-style notices, none is copyleft |
| Statically linked crates | The binary embeds third-party Rust crates without a published per-crate inventory (as for uv, §2). Not redistributed, so the `LICENSE` text is enough for this record |

### What ruff does not do

- It parses source text; it never imports or executes project code and loads no plugins (rules are compiled in).
- The ratchet calls only `ruff check` (read-only) and `ruff format --check`, both with `--no-cache`, so ruff writes nothing into the checkout. A developer running ruff by hand should pass `--no-cache` or set `RUFF_CACHE_DIR` outside the checkout.
- Its formatter makes a best-effort attempt at the line limit only; `E501` still reports lines it cannot wrap.

### Behaviour that the configuration pins

- Since 0.16.0 the default rule set is large and no longer contains `E701` to `E703`, so `select = ["E501", "E702", "E703"]` replaces it explicitly.
- Since 0.16.0 `ruff format` also formats Python code blocks in Markdown files; `extend-exclude = ["*.md"]` keeps the documentation out, and the ratchet never formats.
- The default target version of 0.16 is Python 3.10; `target-version = "py312"` is set explicitly. `preview = false` is explicit; no import sorting (`I001` is not selected).

## 12. prettier 3.9.10 (TypeScript formatter)

### Identity

| Field | Value |
|---|---|
| Project | Prettier (`prettier/prettier`) |
| Version | **prettier 3.9.10** (npm dist-tag `latest` on 2026-10-13) |
| Official source | npm `prettier`, https://registry.npmjs.org/prettier/-/prettier-3.9.10.tgz (56 files, 9,959,033 bytes unpacked) |
| Published | 2026-10-10 08:35:28 UTC by GitHub Actions through npm trusted publishing |
| `dist.integrity` | `sha512-skGHTH1Yb9QvaTC4hWnRTzEYtCpApF0UMBPz+t/0ZPzP8ihefo/btKd+QA7pUE0fEwA1SbS/NmhyEcstdXOIdA==` (the value `ui/package-lock.json` records) |
| `dist.shasum` (SHA-1, legacy) | `ac378e432f1a7381518f2e080816bbaefa38d585` |
| Tag | `3.9.10` in `prettier/prettier` |
| `dependencies` | **none**; no `scripts`, so no install-time script |
| Runtime | Node `>=14` (`engines`) |
| Known advisories | **none** (OSV batch API, ecosystem `npm`, `prettier@3.9.10`, queried 2026-10-13) |
| Signatures | `npm audit signatures` after installation: every installed package, prettier included, has verified registry signatures |

### Licence

| Field | Value |
|---|---|
| Licence | **MIT** (`license` in `package.json`; `LICENSE` is the MIT text, 1,065 bytes, "Copyright © James Long and contributors") |
| Bundled code | The artifact bundles about 250 third-party parsers and utilities (TypeScript-ESLint, Babel, acorn, postcss and others) that are not npm dependencies. Its `THIRD-PARTY-NOTICES.md` (362,597 bytes, inside the tarball) states their licences as MIT, ISC, BSD-3-Clause, Apache-2.0, BSD-2-Clause and BlueOak-1.0.0, all permissive |

### What prettier does not do

- It parses and prints source text; it never executes project code and runs no plugin (the configuration lists none). The configuration is JSON (`ui/.prettierrc.json`), never an executable `prettier.config.js`.
- The ratchet runs it with `--list-different` only (no `--write`, no `--cache`) and `--no-editorconfig`, so it writes nothing and only `ui/.prettierrc.json` sets its options.
- `printWidth` is a target, not a limit; the ratchet measures long lines itself (§13).

## 13. Formatter decisions and what the repository applies

### Decisions (product owner, 2026-10-13, before any installation)

| Item | Decision |
|---|---|
| Versions | ruff 0.16.10 and prettier 3.9.10, both MIT, both hash-pinned |
| Line limit | 100 characters for both tools |
| Quotes | single quotes (`quote-style = "single"`, `singleQuote: true`), matching the existing code |
| Rules | ruff `select = ["E501", "E702", "E703"]`, explicit `target-version = "py312"`, no preview mode, no import sorting |
| Ratchet | line-level: a new file must be fully formatted and free of violations; in an existing file no violation may sit on a line added or changed since the baseline's base commit and no per-file count may rise; existing files are never reformatted as a whole |

### Applied

- `pyproject.toml`: `ruff==0.16.10` in the `native` dependency group, and the `[tool.ruff]` configuration. The native group is the environment `./hyprn-mvp dev check` runs the test-group runner in, so the ratchet finds ruff next to its interpreter. The `contract` group is not used because it must equal `application/requirements.lock`, the application image's lock, which must not carry a development tool; a third group would need a third locked environment in the local edition. `uv lock` (uv 0.12.24) added exactly one package, ruff 0.16.10 with the six hashes of §11, and nothing else.
- `ui/package.json` and `ui/package-lock.json`: `"prettier": "3.9.10"` in `devDependencies`, and exactly one lock entry, `node_modules/prettier`, with the integrity of §12. `npm --prefix ui ls --all` differs from the earlier tree only by `prettier@3.9.10`.
- `ui/.prettierrc.json`: `printWidth` 100, `singleQuote`, `semi`, `trailingComma` `all`, `endOfLine` `lf` (the last three restate defaults so a later default change cannot move the format silently).
- `deployment/style_ratchet.py`, `deployment/style_baseline.json` and the must-pass group `style-ratchet`. For TypeScript and JavaScript the ratchet counts the lines over the limit itself (`long-line`, with the exemptions of `E501`: a single word, or a trailing URL), because prettier has no line-length rule.

### First verified acquisition (macOS arm64)

- ruff: installed by `./hyprn-mvp` with `uv sync --frozen --no-build` into the native environment of the new lock (uv verifies the wheel SHA-256 of §11); `ruff --version` reports `ruff 0.16.10`.
- prettier: installed by `npm --prefix ui ci --ignore-scripts`, which verifies the lock's SHA-512; `prettier --version` reports `3.9.10`; `npm audit signatures` verified the registry signatures of all 29 installed packages.

### Sources

- ruff: https://pypi.org/pypi/ruff/0.16.10/json, https://pypi.org/simple/ruff/, https://github.com/astral-sh/ruff/releases/tag/0.16.10 (API: https://api.github.com/repos/astral-sh/ruff/releases/tags/0.16.10), https://github.com/astral-sh/ruff/blob/0.16.10/LICENSE, release notes https://github.com/astral-sh/ruff/releases/tag/0.16.0, documentation https://docs.astral.sh/ruff/settings/ and https://docs.astral.sh/ruff/rules/line-too-long/
- prettier: https://registry.npmjs.org/prettier/3.9.10, https://github.com/prettier/prettier/blob/3.9.10/LICENSE, https://github.com/prettier/prettier/blob/3.9.10/docs/options.md, https://github.com/prettier/prettier/blob/3.9.10/docs/cli.md
- Advisories: OSV batch API https://api.osv.dev/v1/querybatch (PyPI `ruff` 0.16.10 and npm `prettier` 3.9.10: no results)

## 14. flit_core 4.1.0 (build backend of the checkout's packages)

Recorded 2026-10-14 from the PyPI JSON API, the PyPI integrity API and the GitHub tag. flit_core builds the `hyprn-mvp-app` and `hyprn-mvp-integration` wheels that the native host environment installs (task 2.5). It runs only inside the isolated build environment, offline. It is never installed into an environment that runs HYPRN MVP, never shipped in an image and never redistributed.

### Identity

| Field | Value |
|---|---|
| Project | flit_core, PyPA (`pypa/flit`); the backend part of Flit |
| Version | **flit_core 4.1.0**, the latest release when recorded |
| Official source | PyPI `flit-core`, https://pypi.org/project/flit-core/4.1.0/ (download base `https://files.pythonhosted.org/packages/`) |
| Published | 2026-09-16 (wheel uploaded 10:46:56 UTC, sdist 10:46:58 UTC); not yanked |
| Tag commit | `75b1c909d587c1ff5e0fd5f3df1046f74ee249d4` (tag `4.1.0` in `pypa/flit`; the project publishes no GitHub release page for it) |
| Requires Python | `>=3.8`; the wheel is pure Python (`py3-none-any`, 22 files, 142,338 bytes unpacked) |
| Dependencies (`requires_dist`) | **none**. A vendored tomli 1.2.3 (MIT) is used only on Python older than 3.11, so never on CPython 3.12.15 |
| Contents | `flit_core` and its vendored tomli only. There is no startup path file (`.pth`), no executable and no other bundled code |
| Known advisories | **none** (OSV batch API, ecosystem `PyPI`, `flit-core==4.1.0`, queried 2026-10-14; the control queries `setuptools==78.1.0` and `jinja2==2.10` returned advisories) |
| Attestations | PEP 740 publish attestation on PyPI for the wheel (`https://pypi.org/integrity/flit-core/4.1.0/flit_core-4.1.0-py3-none-any.whl/provenance`). Publisher kind GitHub, repository `pypa/flit`, workflow `test.yml`. The attested subject digest equals the wheel SHA-256 below |

### Artifacts

| Artifact | Size (bytes) | SHA-256 |
|---|---|---|
| `flit_core-4.1.0-py3-none-any.whl` (pinned in `deployment/locks/build-backend.json`) | 45,622 | `17398cdd2c38b24047a5a9c93089ec5c0bf12ec3d1469bbf69c27ed7965299db` |
| `flit_core-4.1.0.tar.gz` (recorded, never fetched or built) | 54,678 | `62e12b63ead8335b37f59fabb977c7167fe476dafb5e41785dfa8c9aff843bc6` |

A copy of the wheel was downloaded into a scratch folder outside the repository and re-hashed. Its size and SHA-256 equal the PyPI values.

### Licence

| Field | Value |
|---|---|
| Licence | **BSD-3-Clause** (PyPI `license_expression`; `License-Expression: BSD-3-Clause` in the wheel metadata) |
| Texts in the wheel | `flit_core-4.1.0.dist-info/licenses/LICENSE`: the BSD 3-clause text, "Copyright (c) 2015, Thomas Kluyver and contributors", 1,525 bytes, SHA-256 `35b4f1dec512e617077fd6980dbb43ef8c2887adc5d0185edb4c04da175dd816`. The vendored tomli's MIT text: 1,072 bytes, SHA-256 `b80816b0d530b8accb4c2211783790984a6e3b61922c2b5ee92f3372ab2742fe` |

### Release history relevant to HYPRN MVP

- **4.0 is a breaking series:** `[tool.flit.metadata]` is no longer read. Both packages already use the `[project]` table, so nothing else changes.
- **4.0.3 fixes wheels written with mode 0600.** This matters because `./hyprn-mvp` runs with umask 077.
- **4.1 accepts licence expressions with `WITH`.** No other change affects these packages.
- **flit requires `description`** in `[project]`, or listed as dynamic, so `integration/pyproject.toml` gained one line.

### Alternatives considered (not adopted)

| Candidate | Why not |
|---|---|
| setuptools 84.0.0 (MIT; wheel `51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670`, 818,216 bytes) | Vendors autocommand 2.2.2 under **LGPL-3.0**, which conflicts with the permissive-licence rule even for a build-time tool. Also ships a startup path file (`distutils-precedence.pth`) and eight Windows launcher executables. No PyPI attestation |
| uv_build 0.12.24 (`MIT OR Apache-2.0`, the same release as the audited uv) | Needs one native binary per platform. Its embedded CycloneDX inventory of 259 Rust crates contains one MPL-2.0 crate (`astral-version-ranges` 0.2.2). No PyPI attestation for the wheels |

## 15. Build-backend decision and what the repository applies

### Decision (product owner, 2026-10-14, before installation)

D6 (b) of §10 is applied with **flit_core 4.1.0** instead of setuptools. The build backend is pinned exactly, verified by hash and audited here. Installing exactly this version needs no further checkpoint. Any other version or backend is a new blocking review.

### Applied

- **`deployment/locks/build-backend.json`** records the name, version and licence, the requirement `flit_core==4.1.0`, the backend `flit_core.buildapi`, and the wheel's URL, size and SHA-256 of §14.
- **`application/pyproject.toml` and `integration/pyproject.toml`** both declare `requires = ["flit_core==4.1.0"]` and `build-backend = "flit_core.buildapi"`. Before this, the application package had no `[build-system]` and the integration package named an unpinned `setuptools>=61`.
- **`deployment/native_environment.py` `prepare`** acquires and builds as follows:
  1. It fetches the wheel from its pinned URL and refuses it unless its size and SHA-256 equal the pin.
  2. It builds each package from a staged copy of the release snapshot with `uv build --wheel --offline --no-index --find-links <verified wheel folder> --build-constraints <hashed constraint> --require-hashes`.
  3. `SOURCE_DATE_EPOCH` is fixed, so the wheels of one snapshot are byte-identical.

  A package whose build system is not exactly this pin is refused before any effect.
- **`deployment/locks/native-host.txt`** holds the reviewed native set N of §5: 89 distributions, the `native` group of `uv.lock` without ruff, exported from `uv.lock` with all its hashes. It contains no package or version outside this record. It is installed with `uv pip sync --require-hashes --no-build --strict`, and the project wheels are then installed with `--no-deps`.

### First verified acquisition (macOS arm64)

- **flit_core:** `prepare` fetched and verified it in a scratch installation. Two scratch builds of the same snapshot produced byte-identical wheels.
- **Native host environment:** it held exactly the 89 distributions of N plus the two project wheels. The five `licenses/native/` METADATA files that `AUDITED_LICENSES` pins were byte-equal.

### Sources

- https://pypi.org/pypi/flit-core/json, https://pypi.org/project/flit-core/4.1.0/, https://pypi.org/integrity/flit-core/4.1.0/flit_core-4.1.0-py3-none-any.whl/provenance
- https://github.com/pypa/flit (tag `4.1.0`, API https://api.github.com/repos/pypa/flit/git/ref/tags/4.1.0), release history https://github.com/pypa/flit/blob/main/doc/history.rst
- Alternatives: https://pypi.org/pypi/setuptools/json, https://pypi.org/pypi/uv-build/0.12.24/json, and the integrity API for both
- Advisories: OSV batch API https://api.osv.dev/v1/querybatch (PyPI `flit-core` 4.1.0, `setuptools` 84.0.0 and 83.0.0, `uv-build` 0.12.24: no results)

## 16. Numerical source-wheel packaging decision

On 2026-10-14 the product owner explicitly approved the Flit proposal for
`openmdao_extensions==1.6.3`, `wop==2.6.1` and `xdsmjs==2.1.0`. This authorizes the
three packaging-only transformations in `upstream/engine-packaging/`; it does not
authorize setuptools or a licence exception. The approved proposal SHA-256 is
`e60ff64202d200fa085bef63270ec3457bd4362bc43e04991a576696f2afdcf7`; its manifest is
`2faa1a433783ea23e8851d901f9e57d7b0f12ad69c147333969586167895bf91`.

`deployment/locks/engine-sources.json` records official archive URLs, sizes, hashes,
the exact original and replacement packaging metadata, patch hashes and every runtime
source/resource hash. Only `pyproject.toml` changes. Every other upstream file remains
unchanged. The XDSMjs generated sdist excludes its upstream test before wheel creation;
its four runtime files remain exact. No dependency, extra, Python requirement or entry
point changes. All three packages retain Apache-2.0; XDSMjs has no standalone licence
file in its published sdist, so its existing declarations and embedded notices remain.

The already audited BSD-3-Clause Flit 4.1.0 is used only in the build stage, with its
MIT-licensed vendored TOML parser. Source builds run offline from verified artifacts.
Each wheel is built twice and must be byte-identical. Flit, setuptools, pip and their
build-time vendored dependencies are absent from the engine runtime environment.
The managed CPython distribution excludes its separate `_dbm` extension as required
by the existing distribution decision in `docs/legal/licensing.md` L6.

Approved metadata differences are the Flit generator, reproducible ZIP/RECORD layout,
metadata 2.5 serialization, Import-Name, redundant Dynamic/top-level/zip-safe bookkeeping,
and the documented equivalent Apache-2.0, homepage and author serialization. Runtime
payloads, dependencies, extras, Python requirements, non-licence classifiers and entry
point mappings remain equivalent. Flit's initial XDSMjs wheel additionally advertises
Python 2; the recipe strictly recognizes that exact intermediate WHEEL and removes only
its Python 2 tag, rewrites RECORD and restores the reference `py3-none-any` filename.
No Python requirement is added, and any unexpected intermediate WHEEL field is refused.

The rebuilt engine and retained reference have 20 matching runtime distribution
versions and 4,430 identical recorded file hashes, with zero unexpected differences or
runtime RECORD integrity errors. The reference's additional pip is a build tool and is
excluded. Explicit installation differences are bytecode, generated console launchers,
INSTALLER/REQUESTED/direct-url/RECORD bookkeeping and three inspected uv cache records;
these do not exempt arbitrary package or metadata files. The exact metadata comparison
report SHA-256 is `82aa685393b0a97e0dc51a30f932c3aee84299beed27cf8b366a074729cb45af`;
the complete RECORD comparison report is
`0c8c0243322d02071af3eb46e189bcdeafc56ade3fc98ffe2a909fc6c42b9d31`.

Whole-image inspection covers all interpreter and site-packages locations, not only the
active venv. The engine has 4,481 package files and the application has 1,228, with zero
unrecorded files. The managed interpreter site-packages is empty, the base interpreter
is removed, and no pip, Flit, setuptools, `_dbm` or `.pth` files remain. Only the managed
CPython 3.12.15 binary and its aliases remain executable. Engine whole-image evidence
SHA-256: `ad4f365cd6fa38de7c909f4318d6dd71fc6690e1f4d409ea77e482267d954b1f`;
application: `1d2a6e012d9c3ad1aaa1c8622cb2626756e4934469b5c3e56c92fb2405519b3f`.
