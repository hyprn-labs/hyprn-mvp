# Discrete exploration points — 2026-10-16

Implementation commit `eef1ab7`. User requested smaller controls, simpler visible
arrows, working discrete transitions, and an initial five-original minimum with
assessed estimates. Fuel is evaluation data; all UI and skill behavior is generic.

Delivered: compact named input/value rows; index-based native sliders over available
full-vector points only; calculated/estimated markers; direct adjacent-component
arrows and orthogonal skip links; retained one-axis prepared query results remain
usable without a live predictor. Exact runs take precedence where available.
Changing another input excludes an incompatible slice. Unit/identity matching and
explicit covary groups remain binding. Original output gaps stay null; there is no
browser interpolation, automatic original launch, automatic refit or weaker target.
Optional calculated overlays load sequentially after the basis, avoiding a large
concurrent read queue. Sample settings start with five training calculations.

`/hyprn` now requires justified explicit ranges, at least five successful originals
across each presented slice (all values for smaller discrete domains), disjoint
checks, exact native seeded partitions, and cold-session/transition checks. Its
installed files resolve to the same source; `cmp` confirms identical skill bytes.
A new behavioral scenario describes the required outcome; this is not a claim of
independent evaluation of arbitrary future agent behavior.

## Verification

Commands use `source /private/tmp/hyprn-orchestration-env.sh` followed by:

- `./hyprn-mvp dev check combined-static`: 9 stages pass on `eef1ab7`, including
  design/tokens, ownership, public UI contract, regression tests, TS and production
  build. Scope `cea9fd5b-defa-4711-9a4b-0a6170e10be0`.
- `./hyprn-mvp dev check exploration-ui --exploration-ui-resume
  /private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/hyprn-mvp-test-e485db7c-4a1d-4f04-919c-1c6e549aa544`:
  1/1 group passes on `eef1ab7`; real HTTP/browser retained numerical fixture,
  discrete keyboard movement, complete-vector fencing and no writes on movement.
- `./hyprn-mvp dev check style-ratchet`: 33 pass on `eef1ab7`, scope
  `bca0200b-4c68-4389-94b9-10c22e395ca3`.
- `./hyprn-mvp dev check exploration-answer-ui`: 1/1 passes before the final
  covary-overlay/track styling delta; saved-answer rendering is unchanged by that
  delta. Scope `96c6e48b-e99a-4e26-88c8-af862ec05c60`.

Logs are `/private/tmp/hyprn-discrete-{committed-static,committed-ui,committed-style,answer}.log`.
Earlier failures are retained: two TS nullable-history failures; a browser selector
expected the removed input heading; changed long lines failed the style ratchet.
All were corrected and the relevant checks rerun. Visual review rejected a narrow
three-column layout that buried outputs and stretched SVG stops; the delivered
layout preserves paired input/output columns with simple arrows and CSS markers.
Fixture services finalized; historical replay evidence remains retained.

The checked static artifact was copied to the same demo's static directory, with
atomic index replacement and old hashed assets preserved. No service, worker,
attestation, execution policy, saved answer or existing run was modified. Live
scope remains `f7145c6a-9848-4541-8aa4-0acf069102fb`, port 54821.

## Live preparation and remaining scope

Preparation manifest and failure/recovery evidence:
`/private/tmp/hyprn-discrete-prep/`. Existing declared ranges and 1% relative / 1e-6
absolute targets were retained. The first hand-picked grid fit failed inside the
worker because it did not match the native seeded partition. The recorded AiiDA
process was confirmed excepted; one bounded data-only diagnostic exposed the
cause, without rerunning any engineering model. The failed receipt remains
unchanged. A new public design supplied the exact required coordinates. The two
earlier adopted originals were reconciled by reading the sample operation; the
interrupted third adoption is not retained and was not repeated.

The full-axis draft was narrowed to the initial displayed axis in each category;
other existing controls retain their available originals and explicitly show where
more preparation is needed. Broad simultaneous-input surrogate coverage is still
incomplete. No claim is made that five originals suffice for arbitrary models or
that the demo's every input has five points. No full release qualification or human
acceptance is claimed; prior broad served-suite debt remains separately recorded.


Final live result: 33 additional original calculations completed; preparation,
including the diagnosed failed fit and corrected seeded design, took 35m06s.
Each category has a Mach 4–8 fixed-baseline fit with five training runs, two
separate checks and 17 retained query coordinates. All 11 output targets passed
for every category. API preparation request IDs:

- Category 0: `92827c1c-02a9-43cd-97df-906bd1ff5a97`; identity `151bc34945324a0713a33b5b08a16d41f51b895ceb046712aebc60d640c2d7cf`.
- Category 1: `92b8eff1-11bd-403b-b252-7a975ab0f04b`; identity `a7c9862cc718ef788a1d7fb2d74c896fd6eb6d12110b7ac2e2b9e58c5c746a6b`.
- Category 2: `f30c976f-746e-462f-8b5d-c01a2421645d`; identity `8ec2336e8285812c24356d8bddeaadf0892d26353a449f86d3f1670f0140265b`.

Live CUA verified 11/11 estimated outputs and zero missing outputs at Mach 4.25
(kerosene), 4.5 (methane), and 4.75 (hydrogen), including category changes without
warming the expired predictor. A prior cold-session endpoint selected Mach 8 and
returned 11 calculated outputs, zero missing. Desktop 1440×1000 and narrow
390×844 layouts were inspected. These observations are automated verification,
not human acceptance. Screenshots are `/private/tmp/hyprn-discrete-prep/final-*.png`.

Follow-up `85a539a` adds Reset inputs: a local return to the exact frozen baseline
without writes. Its focused browser regression also asserts restoration of the
baseline and output state. Static/build checks pass in `hyprn-discrete-reset-static.log`;
committed replay evidence is `hyprn-discrete-reset-committed-ui.log`.

Remaining app friction: the legacy numerical-preparation failure response hides
its exact seeded-partition error as “uncertain”; backend loading of full run
histories still takes time. Their broader API redesign is not claimed complete.

Final reset replay: 1/1 passes on `85a539a`. Live Reset inputs returned Mach 6,
11 calculated outputs and zero missing values. No writes were triggered.
