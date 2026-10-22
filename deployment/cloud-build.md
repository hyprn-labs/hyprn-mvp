# Assemble a staging payload

This builds bytes for a reviewed deployment. It does not publish images, upload
secrets, initialize stores, attest execution or open browser admission.

## Freeze source first

Finish and commit the platform contract pin and every behavioral change before
selecting the product commit. Use the full commit, not a branch name. Choose a new
build folder outside the repository, installations and synced storage.

```sh
python3 -B deployment/cloud_build.py snapshot \
  --repository "$PRODUCT_REPOSITORY" --commit "$PRODUCT_COMMIT" --output "$BUILD_ROOT"
python3 -B deployment/cloud_build.py app --root "$BUILD_ROOT"
```

The snapshot comes from Git objects, so local edits, untracked credentials and
generated folders cannot enter it. The committed Docker ignore rules still apply.
Tracked links, environment files and credential directories are refused. The
application build uses the locked AMD64 base images and hash-locked dependencies;
the exported OCI graph is checked in full. The builder verifies that source bytes
and executable modes are unchanged before and after building.

`source.json` records the complete source inventory. `artifacts/app.oci.tar` and
`artifacts/app.oci.verification.json` identify actual application bytes. A failed
build retains its log and intermediate evidence. Inspect it before selecting a
new build directory; do not overwrite a previous attempt.

## Assemble native payload at its final prefix

Use the existing `cloud_native_bundle.py` commands inside Linux AMD64. The prefix
must equal the platform renderer's native release prefix, including the
final product commit. The native environment cannot be relocated afterwards.
Mount only the source snapshot, reviewed worker assets and a fresh output folder;
never mount operator credentials, the Docker socket or any live store.

Use a dedicated Linux Docker volume for both the release prefix and build cache.
macOS bind mounts are not sufficiently case-sensitive for the interpreter tree.
The build container uses the pinned AMD64 Python base from `deployment/pins.json`.
Serialize this CPU-intensive step with other native builds.

Run in that isolated container with explicit paths:

```sh
python3 -B "$SOURCE/deployment/cloud_native_bundle.py" prepare \
  --source "$SOURCE" --prefix "$RELEASE_PREFIX" --cache "$BUILD_CACHE" \
  --source-commit "$PRODUCT_COMMIT"
python3 -B "$SOURCE/deployment/cloud_native_bundle.py" add-worker \
  --prefix "$RELEASE_PREFIX" --worker-assets "$WORKER_ASSETS"
python3 -B "$SOURCE/deployment/cloud_native_bundle.py" pack \
  --prefix "$RELEASE_PREFIX" --output "$OUTPUT/native.tar.gz"
```

`add-worker` checks the recorded worker source hashes against the selected source
and the dependency lock. Reuse a worker or modeling image only when its recorded
inputs remain identical and `cloud_release.verify_oci` verifies its actual OCI
archive against its original manifest digest. This is build reuse, not transfer
of an execution attestation. Retain original build provenance alongside the new
input-equivalence record. Do not copy old qualification claims into a new release.

Verify a fresh native extraction at the exact release prefix with
`verify-extracted`; that proves imports, not containment or scientific execution.
The actual AMD64 host must separately perform current containment attestation.

## Freeze reviewed deployment documents and bytes

Supply the actual deployment's `workload.json`, `release.json`, `runtime.json`
and `desired.json` in a documents directory. Never repurpose the installed-test
fixture's synthetic project, database, identity or registry values.

Create an input JSON object mapping each role to its absolute source file:
`app`, `modeling`, `worker`, `native_bundle`, `ui`, and every evidence role in the
release (`tests`, `provenance`, `sbom`, `licenses`, `sources`). Evidence describes
checks actually performed, their exact source/artifact identities and unfinished
acceptance. In particular, mark runtime checks pending until they happen.
The UI manifest must describe assets extracted from this application image.

```sh
python3 -B deployment/cloud_build.py payload \
  --platform-root "$PLATFORM_REPOSITORY" --documents "$DOCUMENTS" \
  --inputs "$PAYLOAD_INPUTS" --output "$PAYLOAD_ROOT"
```

The helper verifies the product's exact platform-contract pin, validates the
four documents, copies the explicitly selected bytes and checks every payload
hash, OCI graph, native bundle and evidence pin. It creates `payload.json` and
does not generate replacement evidence or silently change a release descriptor.

`release/v1` binds evidence hashes; it does not require a fabricated qualification
boolean before deployment. Installed aggregate acceptance remains a separate gate.
The current `hosted-artifact` group intentionally refuses complete qualification
until installed native/application lifecycle and trusted admission are proven.
Build integrity, successful deployment, automated acceptance and human acceptance
are distinct claims.
