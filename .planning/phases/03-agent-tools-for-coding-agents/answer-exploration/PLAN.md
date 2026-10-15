---
phase: 03-agent-tools-for-coding-agents
plan: answer-exploration
status: ready-for-execution
owner: main-agent
scope: owner-local-fuel-validation
requirements: [RUN-06, RUN-02, UI-01, UI-02, UI-03, OPS-02, SEC-01]
---

# Interactive answer exploration — implementation plan

## Scope amendment — 2026-10-15

The user explicitly removed task **3.V6**, confirming that this means the final
qualification/Guerric acceptance stage, not UI decision 6. Execute 3.V1–3.V5 only.
Their focused checks, real public-API/browser journeys, scientific invariants and
current runtime attestation remain required. Deliver the working local demo after
those tasks; do not make the separate full qualification gate, independent final
review stage or Guerric acceptance a prerequisite. The 3.V6 text below is retained
as superseded context, not an active task or completion requirement. No general
release or human acceptance claim follows from this amendment.

Read CONTEXT.md and UI-SPEC.md in this directory first. They capture the user's latest scope and supersede the mockup. This named delivery plan follows the repository's plan-phase/execute-phase discipline, adapted to a scoped Phase 3 addition rather than replanning or dispatching the historical Phase 3 inventory. Planning was performed inline; no independent planner/checker result is claimed. The main agent owns execution, task checkpoints and qualification.

## Deliveries and stopping points

**First useful demonstration (3.V1):** in the real local app, open the selected fuel answer, move a sampled input, see a calculated baseline and an estimated response from a fitted OpenMDAO surrogate, and open the underlying result basis. It is a tracer, not completion of all-input exploration.

**Usable customer journey (3.V1–3.V5):** all free inputs, arbitrary supported categorical combinations, bounded sampling, additional calculations only in Sample settings, validated estimates, minimal three-box answer page and exact model editing navigation.

**Delivery stop (after 3.V5):** pass the required focused checks and demonstrate the
fuel journey in the local app. Task 3.V6 is removed by the scope amendment above.
No claim of human acceptance, physical validation, full mission closure, cloud
deployment or general release. Fuel is the only real scientific validation case;
synthetic fixtures cover generic contracts without a second study deliverable.

## Architecture and reuse decisions

| Existing capability | Reuse / implementation seam |
|---|---|
| `ui/src/GraphView.tsx`, `ModelView.tsx`, `ui/src/design/graph.tsx` | One graph projection and renderer. Add exploration mode/slots; do not copy the HTML graph or model editor. |
| `ui/src/VariablesTable.tsx`, `unitLabels.ts`, design `numbers.ts` | Existing quantity identity, context, formatting and unit semantics. Extend with a typed prediction context, not independent formatting or browser conversions. |
| `ApproachPanel.tsx`, `ApproachFindings.tsx`, `ApproachMethod.tsx` | Overview composition and interpretation; relocate methods to model context while preserving exact approach/model associations and editing ownership. |
| `application/.../answers.py`, configurations, routes/runs.py, execution.py | Keep immutable answer/run records. A new cohesive exploration module owns study designs, sample manifests, surrogate versions and public orchestration reads. Existing run operations remain the original-model authority. |
| `integration/.../calculation.py`, worker.py, native.py, launcher.py | Reuse AiiDA lifecycle and the attested restricted worker. Integrate sampling/training/prediction as bounded operations; no client scheduler or second provenance platform. |
| OpenMDAO `MetaModelUnStructuredComp`, `KrigingSurrogate`, `ResponseSurface` | Fit/predict from real samples; compare the simple response surface with Kriging using measured held-out error/latency. Default candidate Kriging, not an unconditional choice regardless of failure or speed. |
| SciPy `stats.qmc.LatinHypercube` and NumPy | Explicit seeded space-filling design, normalized inputs and numerical arrays. Retain actual generated vectors. Feed exact lists through OpenMDAO facilities where compatible. |
| OpenMDAO `DOEDriver` / `ListGenerator` | Reuse explicit design evaluation where it preserves isolated scalar execution and result identity. Default DOEDriver state reuse is not evidence of no cross-case state. |
| Existing SVG + native range + design primitives | No new graph or chart package required for the initial curves. No new surrogate package required until a measured limitation justifies one. |

Structured interpolation (`MetaModelStructuredComp`) remains an optional small-dimensional method, not the many-input default. Do not add SALib, OpenTURNS, SMT, scikit-learn, Dash, Panel or browser Python for this slice. In particular, the existing OpenTURNS licensing conflict is not a prerequisite to this work. Use already-pinned dependency artifacts; audit exact version/hash/licence/notices before any addition and re-attest changed runtimes. Current public docs are facility references; prove compatibility with the pinned OpenMDAO 3.45.1 implementation in 3.V1.

### Cohesive data/API boundary

Add closed versioned public definitions and generated client types for:

- **Exploration design version:** study/answer association; categorical dimensions and allowed combination map; exact model version per combination; complete baseline/configuration assignments; numerical free-input ranges/steps/units/provenance; declared co-varying bindings; per-output tolerances; algorithm/settings/seed; total evaluation and wall/concurrency budgets.
- **Sample operation:** frozen design and exact generated vectors; command/receipt identity; per-point configuration/run reference and output availability; progress, cancellation, failure/unknown/reconciliation state; budget allocation. A table of scalar rows does not weaken scalar quantity validation.
- **Surrogate version:** category/model/runtime identity; input normalization; training/check partition manifests; method/settings; data-only artifacts with hashes; per-output validation metrics/coverage and eligibility domain; resource/training limits. No executable pickle/joblib upload or client-supplied model code accepted by the prediction path.
- **Prediction response:** request selection token, exact surrogate version, full input vector, per-output Estimated/Calculated/unavailable value plus reason/basis, and bounded curve slice. It is not a Run or ScientificAnswer and cannot be silently submitted as one.

Proposed operations (names finalized against route conventions during 3.V1): save/preview exploration design; prepare/refine sample operation; read/cancel/reconcile it; request prediction + curve slice; request a selected original-model calculation through the same exploration operation. All clients use public API only; agent tools mirror these operations rather than implementing queues. Reads/previews do not execute candidate physics. Training/prediction are explicit bounded computation operations even if ephemeral results are not saved as runs.

Application is the sole writer of exploration metadata; AiiDA retains processes/artifacts through the existing integration. The modeling service remains limited to its current graph/source/preparation contract and never obtains prediction jobs, application storage or launcher authority. Review explicit store/schema changes under current path/version rules; do not reset stores or execute DDL on ordinary startup. A named current-store migration/creation step is an implementation prerequisite if required, not authorization to erase authoring data.

### Numerical behavior

1. Measure original-model execution, launch overhead, training and prediction separately. If exact evaluation is fast enough, use it through the same bounded path; still deliver the requested estimated/calculated interface and surrogate fallback for costly models. Never optimize away containment.
2. Sample joint input space under an explicit total budget, not a Cartesian product. Allocate across chosen categories, training/refinement and independent checks before launching. The preview refuses an underfunded minimum design with an actionable choice; it does not silently exceed the cap. Failed attempted evaluations consume budget. Training/prediction also have memory/CPU/time limits.
3. Every original-model point has fresh case state. Initially use the existing isolated scalar execution path. Reuse prepared immutable source bytes and orchestration machinery; any in-process/batched optimization must first pass order/permutation/repeated-case and malicious-state-contamination tests. Recreating OpenMDAO Problem alone is not proof that Python module/global state was reset.
4. Category resolution supplies exact model + complete values. Train separately per combination/model; use true dependency reachability to exclude structurally irrelevant inputs per output if useful, never statistical screening to hide an input. All free numerical inputs remain configurable/slidable, including category-bound property overrides with explicit provenance. Derived ports remain read-only.
5. Fit all displayed intermediate/final outputs or mark individual unsupported outputs unavailable. A whole-model vector of independently fitted outputs need not satisfy physical identities exactly: assess model identities and decision-critical residuals, and do not present estimated values as a sequential exact solve. Retain same-vector provenance for every overlay value.
6. Normalize inputs with saved transforms. Reject invalid training rows per output with reasons; never drop failures silently and claim full-domain accuracy. Do not fit through incompatible regimes/models. Keep training, refinement and independent check sets distinct; if checks later become training, create new independent checks and a new version.
7. Use per-output acceptance `abs(predicted - reference) <= absolute_tolerance + relative_tolerance * abs(reference)` in declared output units. Report observed maxima/RMSE, assessed/evaluable/failed counts and decision-boundary errors. Unmet target, incomplete assessment and unavailable prediction are distinct. Targets do not become universal error bounds. Kriging's optional error estimate is not calibrated physical uncertainty or a confidence guarantee.
8. Refine in bounded batches where independent errors, decision crossings or relevant coverage warrant it, through existing lifecycle ownership. Reuse public SciPy/OpenMDAO routines for candidate generation and prediction-error ranking; no new general optimizer framework. Stop on target/budget/cancel; report unmet accuracy honestly. Never reuse final evaluation points as selection evidence while still calling that assessment independent.
9. Domain policy includes bounds, categorical identity, failure/regime exclusions and assessed coverage; a bounding box alone is insufficient support in high dimensions. Initially refuse predictions in unsupported regions and offer settings-based calculation/refinement. Do not globally enable extrapolation.
10. Exact compatible calculated output takes precedence at a matching vector. A missing/failed calculated output remains unavailable unless a separately labelled estimated alternative is explicitly selected in details. Cache key includes model/source/runtime/numerical settings, category assignments, full canonical vector and surrogate version as applicable. A runtime/model change cannot silently reuse obsolete results.

### Interaction/performance contract

The last focused/changed slider determines every output curve's axis; compact axis labels/units remain. API requests carry full input vector plus axis. Curve predictions are batched, bounded and cached separately from original-model evaluations; increasing display resolution does not increase the scientific sample budget. Filled calculated markers appear only on matching slices. Input/category changes cancel or supersede pending responses; no late result replaces newer selection.

Target for the local fuel demo: immediate slider-thumb response and warm prediction+render p95 at or below 250 ms over a recorded 50-change session. This is an engineering acceptance target, not measured evidence yet. Throttle/coalesce requests and evaluate only necessary visible curves; keep every input reachable. If latency misses, profile the existing restricted path and revise the implementation, rather than executing translated physics in the browser or calling a slow view complete. Cache/warm-process optimizations require bounded resources, no cross-user data leakage and immutable model isolation.

## Task sequence and ownership

One numbered task per fresh executor context. Main agent serializes shared files and reruns the task's required acceptance commands on its committed tree before dependent dispatch. Explicit-path atomic commits only. Each checkpoint in this directory's `checkpoints/` records commit, commands/counts/failures, artifact identities, scratch cleanup and open risks. The scope can be split further only with preserved acceptance/dependencies; do not call a partial task complete.

### 3.V1 — Real fuel tracer, runtime proof and contract seam

**Owner:** one executor; application/contracts/integration/UI tracer and test registry are exclusively its files during this task.
**Actions:** inventory exact selected fuel sources/assignments through API; create isolated representative fixture; enumerate every free/connected port and units; benchmark actual worker latency; prove pinned sampling/metamodel APIs on a small real dataset; introduce the minimal versioned design/prediction contract and public route; render the existing graph with a calculated baseline and an estimated response for one input/output using shared provisional design primitives. Use existing scalar runs and a fixed small sample budget; no exhaustive sampler or manual fixture arithmetic. Add a selected-point calculation **in Sample settings**, not a temporary external button. Establish full request/result identity, unavailable semantics and source isolation now.
**Files:** existing seams above plus new cohesive `application/src/hyprn_mvp_app/exploration.py`, `routes/exploration.py`, `integration/src/hyprn_mvp_integration/exploration.py`, `ui/src/AnswerExplorer.tsx`, design exports/recipes, versioned schema source, generated OpenAPI/client types, corresponding tests. Names are proposed new modules, not claims they already exist.
**Done:** one real user journey works over the public API in an isolated served app; calculated/estimated labels and true provenance verified; startup vs compute timings captured; no source execution on preview. Small tracer limitations explicitly recorded.
**Verify:** register/run new `exploration-contracts`, `exploration-native`, `exploration-ui` groups; run existing `contracts`, `units-worker`, `units-attestation` and affected contract/design checks. Existing run fixtures remain green. Missing groups are failures, never skipped placeholders.

### 3.V2 — Bounded sample operations and retained recovery

**Depends:** 3.V1. **Owner:** application/integration/contracts/deployment and their tests.
**Actions:** persist complete design/sample operation manifest; implement study/category budget partition and point generation using pinned SciPy and explicit seed; reuse AiiDA to launch isolated scalar points with command receipts and exact pins; add progress/cancel/reconcile/restart, dedup and budget admission; retain training/check partitions and failed outputs; expose through public API and existing owner tool catalogue. Add trusted data-only numerical artifacts and safe readers. Integrate runtime/source inventory and re-attestation once per cohesive changed-runtime batch; do not rebuild unrelated services without need.
**Done:** interruption after uncertain launch resumes by lookup, not duplicate execution; point/time caps are enforced; partial sample remains inspectable; retained results read after restart/model service outage; no candidate code on preview and no external model/pickle loading.
**Verify:** `exploration-contracts`, new `exploration-api`, `exploration-native`, existing `bindings`, `bridge-history`, `units-attestation`; malicious payload, nonfinite/bool/unsafe integers, permission isolation, resource exhaustion and uncertain launch failures. Check agent catalogue through its existing group discovered from `dev check --list`.

### 3.V3 — All-input and categorical exploration

**Depends:** 3.V2. **Owner:** application design resolution/contracts, UI explorer/graph slots and their tests; shared files serialized.
**Actions:** generalize from tracer to every scalar free input using public model metadata and design assignments, not fuel-specific names. Complete independent categorical-dimension selectors and supported tuple mapping to exact models/configurations. Add numerical sliders for free fuel properties, explicit overrides and integer steps; linked numerical assignments update only through declared bindings. Resolve each sample to a complete vector and validate applicable ranges/units. Handle model-switch input/port remapping by identities, not display names. Add empty design/range errors and two-category synthetic contract fixture. Keep common-comparison controls available across fuel categories without accidentally retaining a fuel-property override.
**Done:** fuel free-input inventory equals rendered slider inventory; connected ports are read-only. Arbitrary valid two-category combinations select intended model/values in a synthetic fixture. No silent physical defaults/conversions/clamps; model switches never reuse incompatible curves.
**Verify:** `exploration-contracts`, `exploration-api`, `exploration-ui`, existing `units-resolution`, `units-configuration`; real UI edit/drag/keyboard on every fuel input, unit conversions, property override/category switch, unknown/unsupported tuples and late-response races.

### 3.V4 — Assessed surrogates, refinement and fast prediction

**Depends:** 3.V3. **Owner:** integration numerical implementation, application prediction/lifecycle, public contracts and corresponding tests.
**Actions:** fit and compare OpenMDAO Kriging/ResponseSurface on the actual fuel samples; retain per-output fits, normalization, thresholds and independent validation artifacts; implement finite prediction/curve requests in the bounded numerical path; check intermediate/output consistency and regime exclusions. Implement budgeted refinement with new version adoption only after a complete result is available; retain previous versions. Add prediction caching/request generation cancellation and the performance measurements above. Include true unknown/unmet/partial states and selected-point original-model enrichment from settings. Do not paint GP variance as a validated ± interval.
**Done:** every display output has a justified prediction or explicit unavailability; target failure survives budget exhaustion without fabricated success; failed regions don't become smooth curves; warm end-to-end latency target met or remains a named blocker. Actual training samples and checks are reproducible from retained manifests.
**Verify:** new `exploration-numerics` plus `exploration-native`, `exploration-api`, `exploration-ui`; independent reference points, zero/near-zero output, nonlinear/crossing/failed cases, source-order invariance, out-of-domain refusal, retrain/restart/cache invalidation, deterministic design reconstruction. Check failure directions explicitly: impossible target and tiny budget must not produce a success state.

### 3.V5 — Minimal answer composition and coherent design system

**Depends:** 3.V4. **Owner:** UI/design-system documentation/components/specimens/checkers and affected answer/model navigation tests.
**Actions:** implement UI-SPEC in full. Consolidate provisional primitives into design exports/recipes; enforce usage with existing component ownership checks. Question → exploration → interpretation, with no supporting-results inventory or methods on Overview. Move methods/approach editing access into canonical model context, preserving multi-model associations and saved references. All calculate actions in Sample settings; Open model in exploration footer. No Curves against, reset/helper/meta banners or redundant buttons. Scientific qualifiers and per-value traceability remain concise. Preserve exact model-version navigation and explicit current-draft editing flow. No production fixture data, variant switcher or fake validation.
**Done:** UI-SPEC acceptance all passes; all inputs slidable, axes explicit by active input, no unsolicited controls/prose. Methods remain editable at the model owner and old answer/model references still resolve. Original model/configuration/run readers remain functional.
**Verify:** `exploration-ui`, existing `approach-ui-reading`, `approach-ui-method`, `answers-api`, `style-ratchet`; design/token/ownership/smoke/build checks through registered groups (see validation matrix). Day/dark, keyboard, genuine 200% zoom and bounded rendering measured in the served app. Human acceptance not inferred from screenshots.

### 3.V6 — Fuel rehearsal and delivery qualification — superseded, out of scope

**Depends:** 3.V5. **Owner:** main integrator with fresh independent review context(s) under existing execution/review workflow.
**Actions:** run integrated union acceptance on committed tree; independent numerical, security and UI review; qualify exact final runtime and source inventory; then update the existing demo through ordinary supported deployment with recovery instructions. Seed a reviewed fuel exploration design through the public API using the user-selected study and exact pins; no fixture writes to live stores. Exercise real sample preparation, sliders, category change, adding a point from settings, unmet accuracy and restart; inspect retained original-model checks. Ask Guerric to perform the intended decision journey and record his response. Update authoritative docs/requirements/state with actual evidence and limitations, superseding proposal text without deleting old evidence.
**Done:** complete automated evidence and a user-ready local fuel demonstration. If Guerric has not accepted, record human acceptance pending; no complete customer-validation or release claim. Scientific conclusions retain known structural-unit/full-mission/ticket-price limits.
**Verify:** full `./hyprn-mvp dev check qualification` on exact delivery tree; all new groups included in the applicable must-pass set; committed integrated browser/API/native suite; no open high security or scientific-meaning defect. No new platform/release claim beyond tested local environment. Do not defer the required qualification merely because focused tests passed.

## Verification and delivery discipline

All execution checks use `./hyprn-mvp dev check <group>`. The new group names above are **planned**, not currently runnable. The owning task must register actual scoped fixture/test targets, cleanup and required runtimes in `deployment/checks.py` before using them; no direct runner or arbitrary interpreter. Use `./hyprn-mvp dev check --list` to confirm names. Design checks must invoke `python3 ui/check_design_system.py` (no FAIL), `python3 ui/design_tokens.py --check`, `python3 ui/test_design_tooling.py`, `node ui/design_smoke.mjs`, ownership checker and UI contract checker inside the appropriate registered runtime/group. Build `npm --prefix ui ci && npm --prefix ui run build` under the declared check environment. Determine and retain precise existing group names rather than inventing a passing alias.

Trace acceptance through the real public API and served browser, with representative real numerical results. Synthetic fixtures cover failure/edge invariants, not scientific qualification. Evidence stays outside the repository; checkpoints contain identities/paths resolved via existing policy, not committed machine-specific source locations. Never run tests against the user installation; the final authorized demonstration uses its ordinary API only after isolated checks.

## Threats and required mitigations

- **V-T1 execution bypass:** candidate source, malicious serialized surrogate or training callback executes in app/browser. Mitigation: immutable data-only fit inputs/artifacts; approved numerical operations inside bounded restricted runtime; no user pickle; adversarial execution tests.
- **V-T2 budget amplification:** exponential category/grid expansion or rapid slider requests launches unbounded jobs. Mitigation: total preview/admission budgets, bounded body/row counts/concurrency, no original-model launch on drag, rate/coalescing limits, explicit retries charged and authorized.
- **V-T3 identity/permission contamination:** another study/category/model/runtime supplies a cached result. Mitigation: complete identity/cache keys, access checks on every read/predict, version invalidation, no cross-user worker residuals; denial tests.
- **V-T4 duplicate/ambiguous execution:** interrupted operation blindly retries launch. Mitigation: reuse existing receipts/process lookup/reconciliation, durable manifest and bounded AiiDA lifecycle; crash-window tests.
- **V-T5 misleading scientific state:** estimates labelled calculated, fit error called physical confidence, missing output zero, failure gaps interpolated. Mitigation: closed per-output result kinds/reasons, independent validation, domain exclusions and shared design status/curve recipes; numerical/UI failure tests.

## Coverage review and execution handoff

Inline plan review: latest decisions are covered by 3.V3 (all inputs/categories), 3.V4 (OpenMDAO reuse/validation), 3.V5 + UI-SPEC (minimal UI/design enforcement), 3.V6 (fuel/human acceptance). Calculation placement and Open model placement have explicit negative UI assertions. Planned groups are distinguished from existing ones. Model/source pins, no hidden defaults, safe execution, one writer and run recovery remain requirements. No independent review or test pass is implied by this planning review.

Deferred with main-agent ownership: a second real study, sensitivity ranking/top-K, optimization, broad uncertainty propagation, surrogate sharing across categories, cloud deployment, external installations and a chart-library migration. These are outside this authorized slice. Runtime compatibility, full-input ranges/tolerances and actual latency are addressed by tasks, not assumptions treated as achieved.

Next action: main agent accepts this named delivery plan into its execution queue, reconciles current branch/unrelated work, commits the planning packet, and starts 3.V1 with the execute-phase/task checkpoint discipline. This user authorization is sufficient to begin; no repeat approval of the direction or sample UI is required. Any new destructive operation, scientific scope change or unresolved licensing conflict follows existing rules.
