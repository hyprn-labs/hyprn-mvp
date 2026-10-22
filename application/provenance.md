# Application dependency provenance

The `hyprn_mvp_app` source is independently authored. It contains no WhatsOpt application code, templates, authentication, schema adapters or product UI. Modeling interaction uses the separately authored Modeling Backend Contract.

## How dependencies are admitted

Every direct and transitive dependency is reviewed before installation. Wheels are downloaded without being executed, inspected as ZIP data, and each exact filename and hash is checked against its official versioned PyPI release. `dependency-pins.json` records, for each package, the release URL, artifact URL, source and documentation URLs, version, SHA-256, licence expression and classifiers, the licence file paths inside the wheel and the licence-text digest. `requirements.lock` installs exactly those reviewed hashes offline (`--no-index --require-hashes`). Targets are CPython 3.12 on macOS arm64 and Linux arm64/x86_64; compiled Linux wheels are checked against their official release hashes and licences before the offline container build. The inventory covers 33 packages and 37 wheel artifacts.

A new or changed dependency repeats this review. Only permissive licences are admitted for new dependencies; see `docs/legal/licensing.md`.

## Licences

| Package | Version | Licence |
|---|---|---|
| FastAPI | 0.143.0 | MIT |
| Pydantic | 2.14.0 | MIT |
| Starlette | 1.7.0 | BSD-3-Clause |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| jsonschema | 4.26.0 | MIT |
| rfc8785 (RFC 8785 canonical JSON) | 0.1.4 | Apache-2.0 |
| certifi (transitive) | 2026.7.22 | MPL-2.0 |
| opentelemetry-api (transitive) | 1.45.1 | Apache-2.0 |

The other recorded packages are MIT, BSD, Apache-2.0 or PSF licensed, as inventoried in `dependency-pins.json`.

- Upstream notices are preserved on redistribution.
- certifi is an unmodified CA-data package under MPL-2.0: keep its licence and the availability of its corresponding source.
- opentelemetry-api is present only as an upstream dependency; no exporter is configured.
- pluggy's wheel and PyPI metadata omit project URLs; its official project is https://github.com/pytest-dev/pluggy and its included LICENSE is MIT. The rfc8785 source and licence are verified at https://github.com/trailofbits/rfc8785.py.

No material provenance conflict or native source extraction was found. This is a dependency inventory, not a legal opinion or a vulnerability certification.

## References

- FastAPI: https://github.com/fastapi/fastapi
- Pydantic models: https://pydantic.dev/docs/validation/latest/concepts/models/
- Starlette: https://starlette.dev/
- Python password hashing (scrypt): https://docs.python.org/3/library/hashlib.html#hashlib.scrypt

## Hosted PostgreSQL driver — 2026-10-20

Phase 06-01 authorizes audited permissive dependencies for the PostgreSQL boundary.
The official versioned PyPI metadata and each wheel's embedded licence were inspected
before installation; downloaded bytes matched the published SHA-256. Exact artifact
URLs, hashes, dependency declarations and licence digests are in `dependency-pins.json`.
No native psycopg dependency is introduced into the application.

| Distribution | Version | Embedded licence |
|---|---|---|
| pg8000 | 1.31.5 | BSD-3-Clause |
| scramp | 1.4.17 | MIT-0 |
| asn1crypto | 1.5.1 | MIT |
| python-dateutil | 2.9.0.post0 | Apache-2.0 or BSD-3-Clause |
| six | 1.17.0 | MIT |

Official sources: https://pypi.org/project/pg8000/1.31.5/ and each release URL in
the inventory. pg8000's DB-API uses a module-level `paramstyle`; this application
sets it once to the existing qmark convention. Wheel contents were read as ZIP
data, not executed during the audit. All five artifacts are platform-neutral.

The isolated server fixture uses the official `docker-library/postgres` image
`17.6-bookworm`, Linux amd64 manifest
`sha256:45cd22f8d32e189d245403954882f88e7a8714301fda80dab6da90f1265b25a3`,
published by https://hub.docker.com/_/postgres from upstream commit
`5ec89312491bdaa2c42377a65ec0af2ecb774480`. PostgreSQL is under the PostgreSQL
License; Docker packaging is MIT. The Debian distribution retains its upstream
component notices. This fixture is not shipped as the production database or
scientific worker and does not qualify a Cloud SQL release.

## Linux amd64 wheel coverage — 2026-10-20

The existing Pydantic Core 2.50.0 and rpds-py 2026.9.1 pins now include their
CPython 3.12 manylinux x86_64 wheels. Both exact hashes already occur in uv.lock;
the downloaded bytes also matched official versioned PyPI metadata. Their embedded
MIT licences were inspected as ZIP data before installation. The additional
artifact URLs and licence digests are recorded in dependency-pins.json. Existing
versions, Mac/arm64 hashes and hash-required installation remain unchanged.
