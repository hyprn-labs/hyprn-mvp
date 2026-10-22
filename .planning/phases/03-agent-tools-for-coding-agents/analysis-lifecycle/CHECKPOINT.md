# Analysis execution lifecycle — 2026-10-20

Owner approved: choose estimation and error limits before launch; automatically calculate,
fit and validate; read-only completion; revised settings require a new analysis version.

Implementation batch: saved content 4 / sample requests 5–6, one durable execution receipt
per version in the existing dispatcher, exact launch-time run pins, stable missing-run
commands, automatic all-output assessment, shared compact settings UI and reader-only
surrogate panel. Historical records and numerical worker/protocol are unchanged.
Owner helper exposes launch_analysis / get_analysis_execution; /hyprn and playbook aligned.
Restricted delegated tool catalogues still report their actual capability gap.

Initial focused evidence (isolated scoped stores through the pinned launcher):
- calculations-api: 71 passed, 43.94 s; initial lifecycle implementation. Later delta caches
  confirmed immutable member completion to avoid repeated heavy reads; rerun pending below.
- contracts: 127 passed, 9.15 s. New closed schemas; predecessors unchanged.
- combined-static --keep-scope: 9/9, 4.37 s; later delta adds run pins to progress signature.
- calculations-ui: 5/6, 46.96 s. New automatic sample/fitting/failure journey passed;
  old separate run-request/refresh test correctly refused by new managed version. Updated
  test to launch once, reuse existing result, submit missing member, display exact run pins.
- Initial sandbox check could not access pinned uv cache; repeated with approved tool access.
- Initial TypeScript output-unit union mismatch corrected via existing resolvedUnit helper.

Final delivery: implementation `f96ae25`, ownership documentation `bd7f848`.
All commands use the pinned `./hyprn-mvp dev check <group>` entry point with the existing
host environment. Final log prefix: `/private/tmp/hyprn-analysis-lifecycle-`.

| Group | Result | Log suffix |
| --- | --- | --- |
| calculations-api | 71 passed, 44.65 s | api-final.log |
| contracts | 127 passed, 9.15 s | contracts.log |
| calculations-ui | 6 passed, 47.86 s | ui-final.log |
| combined-static --keep-scope | 9/9 passed, 4.45 s | static-final.log |
| locality-contracts | 165 passed, 10.20 s | boundaries-final.log |
| local-api-client | 18 passed, 9.09 s | tools.log |
| agent-tools | 326 passed, 50.50 s | agents.log |

The initial locality run passed 164/165: the exact architectural allow-import table lacked
the new owner module edges. `bd7f848` adds those documentation entries; rerun passes.
The final browser journey covers one launch, retained-run reuse, missing-member submission,
automatic failed validation, read-only settings and explicit new versions. Numerical transport
is mocked there. The subsequent progress-signature delta includes run IDs; final static build
and live verification cover it. Other application source is unchanged after focused acceptance.
`git diff --check` passes. Later checkpoint/state edits only record evidence.

Scopes released by the runner except final static build scope
`8cb2050a-b61c-4773-8263-b08e414c882a`, retained as the deployed artifact. Test stores remained
isolated from the live installation. Existing unrelated planning, run-reader, design-system
and research changes remain unstaged and untouched. No dependency or worker changes.

Live verification on localhost:54821, study `1174be5a-8527-4a51-83d9-aad3c8e4aeaa`:
- Public API saved analysis version 3 `70bed7e2-50ae-4ba9-8bc2-29e7a5f3aaff`, preserving
  the exact 33 configurations/design and original error limits, adding the declared plan.
- Real browser Launch analysis completed automatically using the current attested native
  worker. All 33 recorded runs reused; no new engineering model runs. Estimate
  `d2e6e6df-4587-55db-bb06-0e9a5b251ec1` is the execution receipt's exact retained result.
- 24 training + 9 validation points: one selects method, eight independently assess it.
  Both outputs pass all eight; temperature-rise max absolute error 0.008502031154989709 K
  under 0.02 K + 0.2% tolerance; capacity-margin error 7.815970093361102e-14 kW under
  0.01 kW + 0.2%. No tolerance relaxed.
- Public preparation reports ready. A midpoint and five-point curve (five unique points)
  return finite available estimates for both outputs. Verification helper initially expected
  six points, overlooking midpoint deduplication; corrected assertion passes, no app change.
- Public reads confirm old analysis, old estimate and new saved settings unchanged. Existing
  study answer retains its original exact pins; not republished by this verification.
- Browser displays Completed, read-only settings, no manual fit, and Validation passed for
  both outputs. Screenshot and public response artifacts: `/private/tmp/hyprn-lifecycle-demo/`.
- Live web/dispatcher restarted after idle check; final checked UI build published. Dispatcher
  remains running for the demo. Historical records and attestation preserved.

Limits: human acceptance and full release qualification remain separate and unperformed.
Restricted delegated tool catalogues retain their capability gap; the owner helper and
installed /hyprn guidance use the new launch/read execution flow. Independent validation
supports interpolation in the checked domain; it is not a global mathematical error bound.
