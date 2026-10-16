# Joint sampling and surrogate preparation — 2026-10-16

## Delivered

- `7b0f062`: generic bounded deterministic Kriging starts, owned by pinned OpenMDAO, plus a 12-input nonlinear regression. No fuel-specific algorithm or tolerance relaxation. The first reserved check selects the fit; three other checks assess it.
- `7615f52`: show the actual prediction failure instead of prescribing warm-up for every error.
- Runtime checkout cherry-pick `5b14d48a534c9da672656c92cb6f5f24d46cbaac`; rebuilt restricted worker and current attestation. Existing originals retain their original runtime identity.
- Reused 122 distinct calculated points: 120 retained joint/support points and two additional existing axis points. Eight adoption requests correctly deduplicated six already-present points. Earlier working count of 128 was incorrect. No sampling originals were rerun for the fit.
- All 33 category/output assessments pass the unchanged absolute 1e-6 plus relative 1% criterion. Three fresh, predeclared independent joint vectors also pass all 33 comparisons (74.61 seconds for authoring, execution and readback). This is numerical checking, not physical validation.

## Exact saved records

Study `50e423fd-a709-4e21-9381-0b09022b4115`; answer `5a2786ed-d321-4aa7-b0b9-ebfabe5131c1`; model revision `420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`.
Design `d2f37d8f-6116-440e-9c1c-eaf6f3a34460`; retained operation `0836d5c7-1034-4e41-98b5-f8ef9b21be7f`; enriched operation `40bd5f36-04da-41a7-9242-e644da751ec0`; assessed surrogate `350bbb53-7407-4910-9b7b-e7aaefe9ce23`.

Fresh checks (configuration → run):
- Kerosene: `a98f79ff-e926-4892-8965-9706ffad82d0` → `8592d3b9-3788-4d45-8281-0edbe9e82c1e`.
- Methane: `00fc5147-3568-4483-bbde-bb999ec495ad` → `3cbe8782-f7e5-47b4-be98-7a45874c2053`.
- Hydrogen: `e9382407-d87e-474e-9db8-e7a43840525b` → `46c899aa-70a3-424b-865b-5adc3c25c065`.

Original image `sha256:e9896e2900cb8096d740721a3869ab382138480d0006063d0a1823c51144a910`; computation image `sha256:27e8d91e40f6772cdd287b8eeb44514d642b14d6417e4c4d31120d36a32688d3`; runtime digest `85d8ac1dbbf1b8023c85aa3fef954f818211d0d321594a56b8e7de58f72a620d`.

## Verification

Commands use the approved host environment, isolated scratch root, and `./hyprn-mvp dev check`:
- `exploration-numerics`: first candidate failed the new 12D regression (1 failed); corrected bounded starts passed (1 passed). Committed `7b0f062` rerun: 1 passed, 32.00 s. Includes coverage, failure, zero, restart, warm-latency and 12D cases.
- `units-attestation`: 80 passed, 92.86 s.
- `combined-static`: all 9 stages passed; repeated on clean committed `7615f52` archive to exclude concurrent UI edits: all 9 passed, 6.28 s. Design/ownership/tokens/contracts/tooling/unit controls/TypeScript/build included.
- Public prediction API: 15 full-vector queries across three categories, baseline calculated and all 12 changed combinations estimated; 17 curve points per output. Observed request round trips 0.086–0.167 s.
- Real browser: Mach, heating value and range changed together with an independent plot axis; 11 estimated outputs. Methane and hydrogen joint selections also return all 11 estimates after settling. A later methane linked-mass attempt coincided with worker expiry and is not counted as successful browser verification; linked-input API verification passes.
- Fresh verification runs retain exact model pins; originals execute only in attested worker. All 33 comparisons pass.

Compact external evidence: host scratch `hyprn-joint` contains numerics logs, `attestation-check.log`, `static-clean.log`, `verification.json`, `fresh-checks.json`, `refit.json`, `deployment-proof.json`, `ui-hydrogen.json`, `joint-sliders.png`. Check runner sessions release isolated stores; durable demo and runtime backup intentionally retained. Credentials never committed.

## Failures, recovery and limits

- Initial enriched fit with previous optimizer still failed most error targets. Retained as surrogate `d09d18d9-5eee-4a63-857d-72ffa1fbd3fb`; final fit is separate.
- Build transport exceeded 120 s. Reconciled the existing operation; did not resubmit an uncertain mutation. A helper initially named inspect.py shadowed stdlib inspect and failed before mutation; renamed.
- Sampling list exceeded the client response bound; inspected known individual records instead of raising the limit.
- Estimates remain limited to convex training support and assessed outputs. Arbitrary simultaneous extreme corners are not qualified. Sliders may briefly display not computed while a request settles.
- Warm worker lifetime remains 900 seconds / 4096 queries. Expiry was observed; explicit Sample settings → Prepare fast predictions restored estimates. Automatic renewal remains an application usability obligation, not delivered here.
- An initial transient prediction failure disappeared after reload; its cause remains unproven. Error wording is improved but this is not claimed as a lifecycle fix.
- Another session published UI assets during final verification. Do not overwrite that session's work. Clean `7615f52` static checks establish this task's UI change; final hydrogen browser proof uses the concurrently served assets recorded by `live-ui-identity.json` (index SHA256 `669168e6bd943aa617e5d2237b01dcefdc8af3201a1b5ffe61f54508cd83cbd9`). Removed this task's stale UI commit label; backend identity unchanged.
- Concurrent model-workspace/ROADMAP/research changes preserved. No full release qualification or human acceptance claimed; user removed task 3.V6 from this batch.
