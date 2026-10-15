# Precise API errors and ordinary engineering units

Implementation: `a17a4061cf0bf666d1c9b533b307c6e90740261e` (2026-10-15).
User authorized the application fixes and explicitly approved the narrow additive
catalogue exception. `contracts/README.md` records its exact scope. This is a
focused local-demo delivery, not phase completion or release qualification.

## Delivered behavior

- Request diagnostics follow explicit `kind` and `schema_version` discriminators,
  including legacy forms that forbid those fields and nested union wrappers.
  Missing assumption roles, malformed question claims, linked-step remaining work
  and unsupported quantity units identify their actual JSON-pointer fields.
  Object-or-null errors explain required object fields. Error envelopes, status
  codes, bounded output and submitted-value redaction stay unchanged.
- Add 20 reviewed physical spellings: volumes, surface density, inverse area,
  specific heat, energy, power, flow, acceleration, torque and thermal transport.
  There are 48 physical spellings plus the separate dimensionless intent.
  Generator, private service, public schema/types, worker admission and result
  reader agree. All prior spellings and conversion factors are preserved.
- Catalogue discovery uses the new pin. Retained artifacts authenticate either
  exact reviewed catalogue by its own digest; their bytes and conversion proofs
  are never replaced with the current table. The original schema hash guard
  normalizes only the approved enum suffix and matching discovery count.
- New `units-engineering` check runs one isolated public HTTP authoring/execution
  journey and checks five independent SI conversions and results after restart.
  Existing archive qualification remains separate.

## Runtime identities

- Catalogue digest: `9453b65bb997da3568956a53125f53ec83521c5b78d014fde8d15b4538c81f45`;
  generated JSON 8,596 bytes, below the unchanged 16,384-byte bound.
- OpenMDAO 3.45.1 units source:
  `9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92`.
- Rebuilt modeling producer:
  `sha256:dbaa4f336c5925a55d49fe72a6a26ac86ef39e21511fccb982a04df230cd020b`.
- Final demo worker:
  `sha256:8159322361afb055b3f8383c889321121dcbfea3956a2550161820c08ce964f8`.
  Containment passes with all 49 attested source paths; no attestation bypass.
- Current producer fixture: 13 cases / 256 blobs, 2,931,627 compressed bytes,
  SHA-256 `303608e3ba09ff6f2c9498237321016d56bf1859f50afadfce0efe9cdcf0fbf0`.
  Historical fixture and golden-corpus bytes remain untouched.

## Verification

All check commands use `./hyprn-mvp dev check <group>` and isolated stores.
External logs, exact scope identities and runtime backups are under
`/private/tmp/hyprn-units-errors/` on the development host.

| Group | Result | Log |
|---|---|---|
| `locality-contracts` | 161 passed | `locality-4.log` |
| `units-contracts` | 89 passed | `contracts-delivery.log` |
| `units-api` | 80 passed | `units-api.log` |
| `units-bundle` | 121 passed | `bundle.log` |
| `units-staging` | 5 passed, 22 deselected by group selector | `staging.log` |
| `units-model` | 31 passed | `model-2.log` |
| `units-guards` | 138 passed, including final isolated-check registration | `guards-retry.log` |
| `combined-static` | all six commands passed, including UI contract, types and build | `static.log` |
| `style-ratchet` | 33 passed, including final isolated-check registration | `style-retry.log` |
| `units-engineering` | 1 passed on committed tree `a17a406` | `engineering-committed.log` |
| `units-worker` | 211 passed, 1 native-origin HTTP transport failure; isolated retry below | `worker-3.log` |
| `units-origin` | 1 passed; isolated retry of the failed native-origin test | `origin-retry.log` |

The isolated retry completed in 106.94 seconds in scope
`7c2a5f18-2096-48c5-8ffb-43f8efc23eef`. It exercises the unchanged existing
instrumented native-origin/restart/disabled-generator test. The preceding failure
was a nonzero Docker/Ruby HTTP subprocess during a second static preparation;
the available output does not establish its underlying cause. It did not recur.
The full 212-test invocation is not represented as having passed in one run.
The only post-implementation code delta adds this bounded check selector and its
registry guards; it changes no attested application or worker sources.

The real computation verified 2 cm³ → 0.000002 m³, 2 g/m² → 0.002 kg/m²,
2 kJ/(kg·K) → 2000 J/(kg·K), 2 MW → 2,000,000 W and 2 N·m → 2 J.
The final demo HTTP proof (`demo-api-proof.json`) confirms 48 physical units,
precise malformed-claim and nested-unit diagnostics, and unchanged approach
records/run lists for all four existing studies. No new scientific study was
created in the demo. Live authoring stores were backed up only after stopping
identified idle writers; the same stores, keys, native profile and URL were reused.

## Failures and corrections

- Initial public-contract generation used the native interpreter, which lacks
  FastAPI; generation succeeded with the existing locked application interpreter.
- First catalogue admission run exposed the need to authenticate retained old
  catalogues by their own exact pin. Added the two reviewed digest identities;
  golden identities and bundle tamper checks pass without rewriting fixtures.
- Older tests expected artifact format 2 and earlier execution advertisements.
  Corrected them to current format 3 / bundle 10 and retained narrow test-hash
  normalization for the earlier response-version change and shared checker.
- Whole model-preview requests still hid the unit error because pre-versioned
  forms reject `schema_version` as an extra field. The selected-form logic now
  recognizes that explicit contradiction; the real public endpoint regression
  passes with `/edits/0/ports/0/units/expression`.
- Initial broad native run: 12 passed, 2 failed, 1 existing deselection. The new
  engineering calculation produced correct raw outputs but the result reader
  still had its old unit list; fixed it and cover all worker-declared spellings.
  The other failure was the obsolete artifact-version expectation. The successful
  focused calculation replaces repeating unrelated archive/browser qualification
  for this small batch. Full `units-native` is not claimed passed on this tree.
- Earlier worker attempts included obsolete catalogue proof expectations and
  source-inventory drift while development edits were still underway. Corrected
  the proof to bind its retained catalogue and froze sources before final checks.
- Style and registry runs caught long changed lines, an untracked new test and
  the required fence annotation. Corrected and reran both gates successfully.
- The producer capture completed and closed its private container, then its
  scratch wrapper called a nonexistent cleanup helper. No capture bytes were
  lost; no live resources were used. The test scope retains evidence normally.
- Demo refresh initially refused the wrong scratch-root setting, then a later
  inventory pass rejected a process-list header. Both stopped before mutations;
  corrected the scoped environment/inventory and completed the guarded refresh.

No push, publication, new dependencies or user authoring-record migration.
Full qualification and human acceptance remain separate. The unrelated roadmap
working change was preserved.
