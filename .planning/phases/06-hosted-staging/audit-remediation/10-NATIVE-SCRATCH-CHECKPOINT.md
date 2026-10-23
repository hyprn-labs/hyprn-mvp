# Native execution temporary storage

## Scope and cause

The parent inspection found the boot filesystem full while the separately mounted
execution data volume retained capacity. AiiDA creates transient repositories via
Python's cached temporary-directory selection. The cloud owner did not override
that host default, so these pre-node writes could fail despite valid bundles,
attestation and native identities. No live records were modified or retried.

`deployment/cloud_native.py` derives private scratch from `execution_root/tmp`,
creates it only during explicit initialization/rebind, validates ownership/mode
and rejects links. Bootstrap sets both TMPDIR and Python's cached selection, so
failed data-volume writes cannot silently fall back to the boot filesystem.
Attested startup checks 64 MiB operational headroom and an actual write/fsync;
this is host admission, not a change to model resource/accuracy limits. Existing
scratch contents are retained. The parent owns safe dispatch diagnostics, any
ongoing per-call admission, storage-consumer diagnosis and deployment.

## Evidence

- `HYPRN_MVP_DATA_ROOT=… HYPRN_MVP_TOOLS_DIR=… ./hyprn-mvp dev check hosted-native-owner`:
  25 passed, 0 failed, native test runtime 14.813 s; runner exit 0.
- Private log: `/private/tmp/hyprn-native-scratch-final.log`.
- Initial invocation without explicit tools directory failed before tests because
  the default tool cache was inaccessible/missing its pinned interpreter. Retried
  using the existing reviewed tools directory. A prior group run passed 23 tests
  before the two headroom/write-failure checks were added; no red test is claimed.
- Cases include cached host-temp replacement, automatic transient-file cleanup,
  preserved existing files, missing/linked/permissive-directory refusal, ENOSPC
  and free-space startup refusal before native profile access. Existing real
  isolated AiiDA initialization/rebind checks passed with the change.
- Scoped check completed with cleanup exit 0. No Docker worker or staging model
  execution was submitted by this task. Real updated-host behavior awaits normal
  release/rebind/attestation and the user's own Assistant resume.

Only the owner module, its tests and this checkpoint belong to this commit.
