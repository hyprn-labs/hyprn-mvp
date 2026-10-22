# Joint exploration preparation

User authorization: prepare joint coverage and checked surrogates before publishing numerical
answers, fast interaction without model reruns, unchanged accuracy checks; replace the old
local demo and its data with a new study. Full release qualification is outside this batch.

## Implementation

- New boundary-supported sampling method, versioned calculation/sample envelopes. All joint
  corners belong to training, with seeded interior training and disjoint checks. Explicit
  budget refusal; no inferred dimension reduction or range change. Existing partitions stay
  immutable and a retained check cannot be silently moved into training.
- Read-only preparation report through the public API and owner-session tool. Publication
  requires all displayed outputs in all groups to pass independent assessment, geometric
  coverage of the whole declared box and available calculated outputs. Drafts remain usable.
- Exact-byte projection caching preserves authorization, run/receipt integrity and corruption
  checks. Worker membership solves are skipped only when all corners prove full convex support.
  OpenMDAO still owns prediction; no model run or fitting in slider interaction.
- `/hyprn` and its public-tool guidance prepare and check before publishing. UI accepts both
  retained and new formats and offers shared-control sampling-method selection.

## Verification

Scratch logs are under `/private/tmp/joint-*.log`; live replacement records/scripts under
`/private/tmp/hyprn-joint-ready`. No credentials are logged. All tests use isolated check scopes.

- calculations-api: first run 64 passed/1 failed (preparation diagnostic response shape).
  Corrected shape; 65 passed. Integrated committed-tree run also 65 passed (50.69 s).
- study-answer-api: 19 passed; contracts: 127 passed; guard: 117 passed;
  locality-contracts: 165 passed; agent-tools: 326 passed; local-api-client: 18 passed.
- exploration-numerics: 1 native journey passed: deterministic boundary design, disjoint checks,
  real assessed OpenMDAO state reuse, warm latency, outside-support and failed-output refusal.
- combined-static: 9/9, including design checks, UI contract, type checks, build. Published build
  from scoped fixture `b80b7e0f-5eeb-4c84-922e-cb4cb75ed26c` into the existing demo URL.
- style-ratchet: 32 passed/1 failed, broad inherited branch formatting debt (1089 findings).
  New preparation module is formatted; no broad unrelated reformat was attempted.
- Worker build initially failed: legacy Docker builder cannot parse per-RUN network flags.
  Build manager already supplies `--network=none` for every RUN. Removed the redundant
  per-RUN modifier; rebuilt and re-attested successfully without changing containment.

## Live verification

Old demo app store replaced in the identified local scope; recovery outside the repository.
New coolant study `1174be5a-8527-4a51-83d9-aad3c8e4aeaa`: saved brief, defined model,
explanation, three reference/verification configurations, 24 training + 9 check points.
All 36 originals recorded. Predeclared tolerances unchanged: rise 0.02 K + 0.2%; capacity
margin 0.01 kW + 0.2%. Eight independent assessment points pass for both outputs; maximum
absolute errors 0.008502 K and 7.82e-14 kW. A third, predeclared reference configuration,
excluded from fitting and method selection, passes a further prediction comparison.

Public tool/API verification (`verify_publish.py`, `interaction-proof.json` outside repo):
23 requests, all eight corners calculated, twelve joint interior selections and all three
axes return values throughout their 32-point curves, with other selected inputs unchanged.
Outside-range inputs remain unavailable. Original-run count remains exactly 36.
First prediction 3.658 s; twelve warm joint requests median 1.382 s, p95 1.428 s, maximum
2.159 s (each includes both selected outputs and the full curve). This is a measured public
API improvement, not an instant/client-only interaction claim. Native numerical work and
transport overhead remain; no original model is rerun during interaction.

Answer `026ac8e2-724f-4aec-9a76-8fd338216ae4` published only after readiness and the fresh
verification passed. Estimate `41d5dce9-ff67-4a4f-b6d2-6728bfe32762`, calculation version
`20b9f8e8-b4be-4bb5-9a23-39604ff6924e`. Nominal recorded rise 9.52381 K/margin +0.6 kW;
adverse 15.78947 K/−5.5 kW. This remains a thermal screen, not qualified cooling design.

Browser verification found prediction-dependent slider coordinates shifting while another
control was moved. `e93f3fb` fixes coordinate stability and preserves the selected value while
predictions are loading; a focused regression protects indices and prevents borrowing labels
from another full input vector. Updated UI build and final browser readback recorded below.

Implementation commit `f064690`; integrated contracts 127 passed (12.58 s). Later slider-only
commit leaves the tested API, worker and skill unchanged. Numerical runtime was re-attested.
Full continuous accuracy is not proven by finite checks. The all-corners design has an
explicit bounded budget (64 training points/group, requiring interior training as well),
so higher-dimensional studies are refused when unsupported rather than silently narrowed.

Old active app data is replaced, with recovery at `/private/tmp/hyprn-joint-ready/app-store-recovery`.
Older native/model artifacts are not claimed securely erased. Automated checks and browser
observations do not constitute human acceptance or full release qualification.

Unrelated ROADMAP and research/proposal changes are preserved and excluded from this batch.

## Commands and retained evidence

Checks used `./hyprn-mvp dev check <group>` with the configured development environment:
`calculations-api`, `study-answer-api`, `contracts`, `guard`, `locality-contracts`,
`agent-tools`, `local-api-client`, `exploration-numerics`, `combined-static`, `style-ratchet`.
Exact command arrays, counts and durations are retained in the group result JSON and the
`/private/tmp/joint-*.log` transcripts. The final slider delivery build uses
`./hyprn-mvp dev check combined-static --keep-scope`: prior successful invocations cleaned
the generated assets automatically, so retention was needed for deployment, not new testing.
Ordinary check scopes were released by the runner; deployment scopes use its 24-hour retention.
Live demo services and evidence remain intentionally available; no unrelated services stopped.

The first live verification attempt used group 0 in the URL query; the public read query is
one-based while prediction bodies and stored group identities are zero-based. Corrected the
verification caller to query group 1; no API behavior was changed and no model run was repeated.
Final UI publication first refused the already-cleaned build path; no live asset was changed
by that failure. The retained delivery build resolves that artifact availability failure.

## Delivery

Final committed UI checks: 9/9 pass (`joint-slider-integrated.log` and retained delivery
`joint-slider-delivery.log`). Published assets from scoped build
`f5899d69-673b-422c-aad5-e1fb2578bf96`; runtime identity unchanged.

Live browser on the updated build: rapid one-step changes to all three independent sliders
retain their positions (14/15/13) while loading and after prediction. At load 13.5153643 kW,
flow 0.27591304 kg/s, specific heat 3.99250613 kJ/(kg K), outputs display estimated
12.268 K and −2.500 kW. Switching plot axis from load to flow preserves the selected values
and predictions. Selecting Calculated point 1 displays recorded 12.632 K and −2.500 kW,
with black calculated endpoints and orange estimated curves. No transient “No prepared
estimate” warning remains for the prepared selected values. Browser evidence and screenshot:
`/private/tmp/hyprn-joint-ready/browser-verification.txt`, `demo.png`.

Demo: http://127.0.0.1:54821/ui/?workspace#v=1&view=overview&study=1174be5a-8527-4a51-83d9-aad3c8e4aeaa

Delivery complete for this bounded generic preparation workflow. Remaining: human visual
acceptance; faster-than-one-second public interactions and high-dimensional covering designs
are not claimed; inherited style/qualification debt remains separate. Final documentation
only records this evidence and does not change the tested implementation or installed skill.
