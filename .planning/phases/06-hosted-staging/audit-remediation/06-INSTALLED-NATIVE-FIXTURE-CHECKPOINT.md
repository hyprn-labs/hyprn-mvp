# Installed-native cross-architecture fixture correction

The exact release candidate `7cbe3e` was rehearsed from its immutable Linux AMD64
native archive on an ARM Docker daemon. The original report showed actual canaries
executed, but Docker prefixed their combined output with an architecture warning.
Strict JSON parsing correctly refused that output. Setting DOCKER_DEFAULT_PLATFORM
only in the fixture's subprocess environment did not reach the lifecycle wrapper's
intentionally sanitized native-owner environment.

The fixture now mounts a fixed AMD64 platform shim in front of the exact unchanged
reviewed Docker CLI. It sets only DOCKER_DEFAULT_PLATFORM and execs the pinned CLI
with unchanged arguments; it never filters output or edits worker policy/source.
Both CLI and shim hashes and the fixture target are retained in success evidence.
Real staging attestation remains required on its AMD64 host.

Cleanup queried the cloud owner's label value directly, which correctly triggered
the live-installation fence. The fixture now queries only the owner-label key,
inspects candidate records and selects the exact randomized owner in Python. The
cleanup caller reinspects exact ownership before deleting a container. No fence
exception or live-resource access permission was added. A regression checks that
actual live installation names remain refused.

## Original failure and cleanup

Original group: `hosted-native-installed`, 1 test plus teardown, 2 errors in
98.703 seconds. Storage scope `02664bfa-4efc-4e41-b930-b10aa8aa013b`; fixture owner
UUID `9a6b47dd-1c1c-45e5-adf3-f362a9563628`. Original evidence remains under that
scope and the deployment packet's `application-evidence/installed-native-check.log`.
Canary exit states supported the expected isolation/resource bounds; this was not
reported as a passing attestation because the required JSON observations failed.

After inspecting exact test-scope labels, no matching containers remained. Removed
only the two matching `hyprn-installed-{release,state}-<UUID>` volumes without force;
Docker would refuse removal while in use. No broad prune, live data access or
staging mutation occurred. Retained diagnostic evidence was not deleted.

## Verification

The rerun uses the unchanged descriptor
`/private/tmp/hyprn-staging-build-audit-remediation/native-rehearsal.json`, with the reviewed external data/tools roots, through:

```
HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480 \
HYPRN_MVP_HOSTED_NATIVE_INPUT=/private/tmp/hyprn-staging-build-audit-remediation/native-rehearsal.json \
./hyprn-mvp dev check hosted-native-installed
```

Final result: **3 passed in 137.232 seconds**, process exit 0 and scoped cleanup
exit 0. Storage scope `62fcb5ce-d2f3-4dda-9af7-e82b8a9cb3ee`; fixture UUID
`b2d0bb79-c6b3-4c76-9e81-10420a32ef79` has `released: true`. The two fixture guards
and real released-owner initialization, containment attestation, calculation
(output 49), restart-identical read and duplicate-launch refusal all passed.

Exact tested release source: `7cbe3e4670583ec73635eb7d74dfb949776a176f`.
Native bundle SHA256:
`797a9792f6a4b2cea5a6d9c7e69a6407b8c9db538eb781eeb89600d50362beec`.
Worker image: `sha256:f82543b903a34ba52690b4b7f4a788ec7abd9513a78a299b6939798266b3deaa`.
Fixture attestation SHA256:
`b21ddec4e183854b7fe7e5f5b7def43786de65c4931caa50fba2d22fe09a0be6`.
Pinned Docker CLI SHA256:
`6f7a95d27f98fc8c5f6b220898988bf8f61dd9b040936797917cbdc72c6cabe6`.
Fixture platform shim SHA256:
`8aa41aa8b469d5cefbbdb1a51b1f36ed2038fe302857556ae9aa5ef2087f7e32`.
Log: `/private/tmp/hyprn-audit-remediation-release/application-evidence/installed-native-recheck.log`.
The test lane was released to the deployment parent after process completion.
No production file, release artifact, scientific data or live fence was changed.
