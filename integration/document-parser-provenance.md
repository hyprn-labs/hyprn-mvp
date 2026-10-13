# Document parser provenance

**Adopted exact pin: `pypdf==6.20.0`, Python 3.12, no extras.** The official artifact, source and dependency evidence was audited; no material provenance or licence conflict was found for the unmodified wheel with its notices kept. This record covers package identity, licence and permitted use only. It does not install the parser and grants no containment, production security, deployment or acceptance qualification: those belong to the parser image and its tests.

The machine-readable adoption record is `integration/document-parser.lock.json`. Its name, version, Python target, extras, dependency closure, wheel filename, size, SHA-256, index host, licence and source must equal this record; `contracts/tests/test_document_parser_adoption.py` checks that equality. The parser image build must verify the wheel bytes against the lock before installing them.

## Exact identity and origin

| Field | Audited value |
|---|---|
| Registry and project | [PyPI pypdf 6.20.0](https://pypi.org/project/pypdf/6.20.0/); source `https://github.com/py-pdf/pypdf` |
| Artifact | `pypdf-6.20.0-py3-none-any.whl`, 401,710 bytes, pure-Python universal wheel |
| SHA-256 | `f003fc2014814d264fe7dd3f9d435c158e23e1a85a2233f87a0a2d6d21c914ad` |
| Release | Released 2026-10-09T10:49:13Z; wheel uploaded 2026-10-09T10:49:36Z; not a draft, prerelease or yanked release |
| Source | [Tag 6.20.0](https://github.com/py-pdf/pypdf/releases/tag/6.20.0), annotated tag object `ddf094e4fe97f878275a005993ed63f043a4a8f6`, commit `0309ab701a192fbd3228701a44dd009765a1629b` |
| Source correspondence | All 60 packaged `pypdf/` files, including `py.typed`, match the official tag archive byte for byte, and the file sets match exactly. The source LICENSE equals the wheel LICENSE. No package code was executed during the audit |
| Metadata | Name, version, Python requirement, licence, extras and dependencies agree between the wheel METADATA and the official registry. Every wheel RECORD size and hash and the file inventory were verified |
| Publisher evidence | PyPI provenance binds this wheel digest to `py-pdf/pypdf`, GitHub workflow `publish-to-pypi.yaml`, environment `pypi`; the tag API reports a verified signature. These are upstream verification reports; Sigstore or PGP signatures were not verified independently and no reproducible build is claimed |
| Confidence | Verified registry-to-source correspondence and immutable artifact identity. A changed artifact, version or extra requires a new audit |

The GitHub-generated source tarball digest is a snapshot identity, not a promise that regenerated tarballs stay identical; the commit and every packaged source byte establish correspondence. Upstream setup and build scripts were never run, and nothing was extracted into the repository.

## Dependency closure and permitted use

`Requires-Python: >=3.9`; the target is 3.12. The only base conditional requirement is `typing_extensions>=4.0; python_version < "3.11"`, false for 3.12. The other 24 requirement entries are guarded by extras. Marker evaluation against wheel and registry metadata gives **zero additional runtime dependencies** for the target with no extras; the evaluation was also checked for Python 3.10 and the crypto extra to show the empty result is conditional, not a dropped list.

Do not install the extras `full`, `crypto`, `cryptodome`, `brotli`, `fonts`, `image`, `rtl-text`, `dev` or `docs`. The source build backend `flit_core>=3.11,<5` is build-only and outside this wheel-only adoption; no source build or resolver substitution is approved. The parser image locks this wheel and hash and installs it from the audited artifact with dependency resolution disabled, on Python 3.12. Incidental extras installed at runtime must never silently extend the parser's capability.

Supported use is bounded text extraction. Encrypted PDFs are unsupported even where upstream could decode some encryption without extras. Streams or font and encoding cases that need optional packages receive explicit unsupported or partial outcomes and never trigger a package installation. Scanned or image-only pages report `needs_transcription`. No OCR, renderer, office conversion, semantic index, numeric binding or source execution is adopted.

## Notices and distribution obligations

The top-level BSD-3-Clause LICENSE (1,605 bytes, SHA-256 `a97ac230e5f33ef10a5367a850eb01f91f1a0b064e34742c7794d2294557f524`) is kept with its copyrights, conditions and disclaimer in source and in any accompanying binary or container distribution; no author endorsement is implied. Package metadata alone is not the complete notice inventory:

- `pypdf/_codecs/adobe_glyphs.py` carries the Adobe Glyph List and LettError / Erik van Blokland / TypeMyType / Frederik Berlaen notices and conditions.
- `pypdf/_codecs/core_font_metrics.py` carries the Adobe Core14 AFM permission, its required notices and modification-marking conditions; the embedded paragraph and per-font copyrights are kept.
- `pypdf/_codecs/symbol.py` and `zapfding.py` carry Unicode mapping notices, including the attached-notice requirement.
- Other package files carry contributor BSD notices, including the crypt-provider and extraction modules. Keeping optional dependencies disabled does not remove notice obligations for files shipped in the wheel.

The parser image keeps the unmodified wheel files and all embedded notices, and its distribution notice bundle contains the top-level licence plus these carried notices. Stripping, modifying or vendoring source, or changing the distribution relationship, requires a new review if it creates a material conflict. No source patch, relicensing or blanket legal clearance is claimed.

## Vulnerability review

At the audit (October 2026), the [PyPI exact-version record](https://pypi.org/pypi/pypdf/6.20.0/json) listed no vulnerabilities, the [GitHub advisory query for pypdf 6.20.0](https://api.github.com/advisories?ecosystem=pip&affects=pypdf%406.20.0&per_page=100) returned no matches, and the [maintainer advisory feed](https://api.github.com/repos/py-pdf/pypdf/security-advisories?per_page=100) held 55 published records, every affected range excluding 6.20.0. The three most recent advisories, GHSA-php9-fj8v-98fj, GHSA-w23x-9jrw-r45c and GHSA-v247-6f48-mgcj, concern CPU and memory exhaustion and were fixed in 6.19.0; 6.20.0 further limits stream-decoding work.

No recorded advisory is not the absence of vulnerabilities. External resource containment stays mandatory, and the advisory check is repeated immediately before building or distributing a parser image. A newly applicable advisory or a material provenance conflict blocks that installation for review.

## Security baseline and parser policy

Security requirements use **OWASP ASVS 5.0.0, Level 1, with high-severity items blocking**, cited by versioned requirement identifiers ([release](https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release)). Stricter file-handling controls the product already requires remain additional obligations; no full Level 2 or 3 compliance is claimed.

Parser policy ceilings: original 10 MiB, 500 PDF pages, extracted text 256 KiB per page and 8 MiB in total; strict UTF-8 for text, Markdown and CSV with a fixed newline normalization of extracted text, original bytes unchanged. Before any page inspection or decompression the parser runs as a non-root process with a read-only root, no network, no capabilities, no-new-privileges, no secrets, native profile, application database, launcher, socket or sibling files, 1 CPU, 512 MiB memory, 64 processes, 64 MiB writable scratch, an external 30 s wall-clock timeout and bounded output collection, with fixed server-owned input, configuration and output paths. These are qualification limits, not measurements.

Still to be established by the parser image and its tests: image and base-image digests, the complete environment lock and notice bundle, the fixed launcher and real resource, network, secret, mount and shutdown tests; deterministic page and span hashes, truncation, and encrypted, malformed and image-only coverage; native provenance, process and attempt links and interrupted outcomes; document reads while scientific work runs; and separate human acceptance.
