# Frozen native program fixtures

`native-programs.json.gz` holds exact prepared model artifacts fetched through the authenticated private Modeling Backend Contract from the reviewed modeling-service producer image (`modeling_producer` in `deployment/pins.json`). Each case is an authored model-format-1 revision, the format these cases use, imported into the producer as a portable model package through the authenticated import (the producer writes new drafts in format 2); the producer validates the package and its digests, and the pinned native generator produced every executable byte. No candidate was imported or executed during capture.

Cases: the two-component chain (`y = 49` and `y = 81`), an unrelated rational response, native length units, an unwritten output, NaN, infinity, a downstream exception, an exception after a stored result, an unsupported in-place output mutation, an import side-effect canary, a Kelvin input/output case, and a three-instance mapping case (two instances of one definition, a leading-underscore source input, disconnected outputs sharing a symbol, and fan-out to two distinct `km` inputs). Preparing again after renaming the live draft keeps the committed executable digest.

The file is data, never a Python import path. It keeps exact manifests, configuration and model snapshots, public target references and base64 raw blobs deduplicated by SHA-256. Gzip only compresses the outer fixture document; tests never extract or import the enclosed source archive.

Each artifact keeps the original authored bytes, generated classes and support files, the entrypoint, bindings and source-line mapping, the full original and patched generator inventories, the source archive and patches, dependency locks and the actual author and generated-code notices. Those notices and the corresponding source stay within their original artifact scope. The fixture is not runtime trust, an attestation or proof of numerical execution.

Negative cases are derived in the tests, not in the fixture: the Kelvin worker test changes the frozen input unit to `degC` and recomputes the contract digests (the producer itself rejects a `degC` preparation with 422). Format-version 1 data for refusal tests is built by `legacy_fixture` in `execution_fixtures.py`. The test runtime lock is a labelled test double and cannot authorize a real worker.

## Capturing

The whole fixture is captured anew with `integration/tests/capture_native_programs.py` against a disposable test service that runs the pinned producer image (the tool refuses another image); it lists every case, fetches every declared immutable file by its authenticated file ID, verifies raw hashes and sizes and keeps the manifests and blobs. Add a case to that tool and capture again. Never synthesize generated classes, rebind generated identifiers or add a parallel graph generator.
