# Application dependency provenance

The `hyprn_mvp_app` source is independently authored. It contains no WhatsOpt application code, templates, authentication, schema adapters or product UI. Modeling interaction uses the separately authored Modeling Backend Contract.

## How dependencies are admitted

Every direct and transitive dependency is reviewed before installation. Wheels are downloaded without being executed, inspected as ZIP data, and each exact filename and hash is checked against its official versioned PyPI release. `dependency-pins.json` records, for each package, the release URL, artifact URL, source and documentation URLs, version, SHA-256, licence expression and classifiers, the licence file paths inside the wheel and the licence-text digest. `requirements.lock` installs exactly those reviewed hashes offline (`--no-index --require-hashes`). Targets are CPython 3.12 on macOS arm64 and Linux arm64; compiled Linux wheels are checked against their official release hashes and licences before the offline container build. The inventory covers 28 packages and 30 wheel artifacts.

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
