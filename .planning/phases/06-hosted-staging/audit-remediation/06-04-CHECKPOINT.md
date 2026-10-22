# Monetary catalogue implementation checkpoint

Status: monetary implementation and native API/execution/answer journey verified;
full native group remains blocked by stale browser selectors. The selectors are
migrated below, pending the integrated rerun. No deployment, user study mutation
or human acceptance is claimed.

Implementation commit: `34acfc61` (`feat(units): add catalogue-backed monetary quantities`).
Native evidence was collected on the integrated working tree with the parent’s
dependent route, answer and UI changes. The only later change within this commit’s
scope was the browser selector/readback migration described below. Parent will
record the final integrated revision and rerun; this checkpoint does not treat
the failed full group as a pass.

## Scope and identities

- New concrete unit/model/preparation/bundle/history formats: UnitDeclaration2,
  Model5, PreparedModelArtifact5, FrozenConfiguration10, ExecutionBundle12,
  RunHistory9 and their retained readers. All existing model-schema definitions
  compare equal to their pre-task definitions.
- Catalogue2: 61 internal entries, including the explicit dimensionless empty
  spelling; 60 nonempty public expressions. USD scales, passengers and
  cost per passenger/mass/volume/time/power/energy come from existing OpenMDAO
  3.45.1 definitions. No unit registration, exchange rate or inflation is added.
- Catalogue digest: `5abc0ae35d2e2fcc8beb1ca9267e709007c007d51f20f95d735122daeef54885`.
- Engine source SHA256: `9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92`.
- Engine unit-library SHA256: `8094fb7d3e8cb65a56311c2ea5ccfbc9c29cb8b4160f1486c39c19dd779a43d3`.
- Patch110 SHA256: `643578538b365bc6bbc502283205ea993e08574e83edab30f84958660d034cf2`.
- A quantity's immutable explanation references its exact catalogue expression,
  price year, economic basis and evidence. Configuration/analysis admission
  requires this saved basis. Cross-run input bindings reject differing price
  years or economic bases. Parent owns answer comparison/pin integration and UI.

## Verification so far

Every command uses `./hyprn-mvp dev check GROUP` with the host's documented
`HYPRN_MVP_DATA_ROOT` and `HYPRN_MVP_TOOLS_DIR`. Host-specific paths and evidence
remain outside the repository. Native checks additionally use the per-command
`HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184` ceiling after the default10GiB
ceiling refused the existing13.6GiB shared cache without deleting active layers.

| Group | Result | Evidence storage ID |
|---|---|---|
| units-contracts | 107 passed | 68fcf0cd-0463-40d5-911d-e0b3fd1fc6d8 |
| explanations-api | 19 passed | a2053300-9496-45f6-99e2-b69f6c95d730 |
| units-configuration | 70 passed | 903f6342-46b4-4c57-acc1-ea77061e9bfc |
| units-staging | 5 passed,17 deliberately deselected by this group | 181195b6-e40f-4463-9992-a370cae25b69 |
| units-model | 33 passed,2 existing unknown-marker warnings; rerun after capability2 advertisement | 4fd8f67c-903f-4748-b286-6d42930d9123 |

The final staging command additionally sets `HYPRN_MVP_ENGINE_IMAGE` to the
reviewed local image `sha256:2bff9e5c401fbcda6a9837c0d42e3cc719549f72b849aeb9c811eb8a1af38cce`.
The probe verifies the exact engine source/library pins before generating.

## Failures and corrections

- Initial execution projection generation with system Python lacked `rfc8785`;
  generation succeeded under the locked native interpreter. The first expanded
  units-contracts run had1 failure/106passes because this projection was stale;
  regenerated projection then passed107tests.
- Initial units-resolution:106passed/3failed. Old tests called USD unsupported,
  treated new format5 as unknown, and expected old generated public route refs.
  Expectations changed to EUR/format6; parent regenerated public routes. Integrated
  rerun belongs to parent.
- Initial units-model preflight refused the default cache budget; no tests ran.
- Initial units-model:28failed/5passed. Corrected stale private API response refs
  and the Ruby validator's missing JSON Schema `const` support. The next run had
 27passed/6failed, all stale test expectations for USD/49units/Capabilities3.
  Updated unsupported example to EUR, total units to61 and capability readers to4.
- Initial units-staging:2failed/3passed. One old USD-refusal expectation and one
  absent historical image. EUR now represents unsupported currency; the probe
  honors the explicit reviewed image selection. Final run passed.
- Historical worker image `a2c452…` was absent. No image was pulled or replaced;
  the present reviewed image above provided the exact pinned engine.

Completed check scopes were released by the runner; failed evidence was retained
under its `.hyprn-checks` storage. Native run evidence, final source revision,
commits, integrated qualification and any remaining risks will be recorded below.

- First units-native:13passed/2failed (storage3781a0c6-ca0b-4197-853a-5ac630dda614). Preparation refused the new retained catalogue because the parent validator confused internal `library_source_sha256` with public `engine_library_sha256`; the parent corrected this plus the retained bundle reader. The separate monetary test attempted to create the already-used fixture directory. It is now part of the existing isolated journey, adding a seventh retained record and exact history9/seed9 browser checks. No numerical monetary result was claimed from this failed run.
- Second units-native:13passed/1failed (storage79de5ff7-7290-4f7d-94b5-8c01c7d66a54). Six real engineering runs, exact retained result links and criterion evaluations succeeded. The old test then called retired `/approach` and received404, so monetary/answer/browser assertions had not yet run. Migrated the fixture to current brief, analyses and study-answer version APIs. The next run includes monetary execution before answer authoring, derives its exact price basis into a saved Content3 answer, rejects Content2 for monetary answers, and checks two immutable answer versions after restart and in the UI.
- Third units-native:13passed/1failed (storagebf7e1cdb-3941-4501-adfb-4f54b5dc0428). The migrated answer fixture's local loop variable `output` shadowed the pre-existing output lookup helper. Renamed it `chosen_output`; this was a test-only correction before the monetary case executed.
- Fourth units-native:13passed/1failed (storage0624f528-d663-463f-b231-a4af19670c5b). Six engineering runs passed; monetary public model5 authoring, connection/currency refusals, saved exact price basis and configuration10 passed. Monetary preparation failed because application bundle admission expected required capability `unit_declarations/2` while producer records retained `/1`. Concrete format5 and catalogue2 already distinguish the new unit declaration; capability2 is advertised and negotiated for new writes. Parent owns the bundle-admission alignment. The fixture now retains the complete failed monetary run detail for diagnosis.
- Fifth units-native:13passed/1failed in383.03s (storage22b12777-b7c4-4b21-8f39-0099e50ec61a). After the parent aligned retained capability admission, all seven real restricted executions passed, including USD scaling and per-mass/per-energy costs. Mismatched price years were refused. Two immutable Content3 answer versions pinned the exact monetary model and explanation; Content2 monetary answers were refused. Offline/restart reads, three native computational archives and all modified-run-seed contracts passed. The producer browser test then failed at obsolete `Edit ports`; migrated it to `Component actions` → `Manage quantities`, current quantity field labels, and Model5 readback. Browser tests remain unverified until the full group rerun. The disposable scope was released.

## Native monetary evidence

The fifth run retained `monetary-units.json`, `monetary-run-detail.json`,
`native-seed-operation-contract.json` and the three `units-native-*.zip` archives
under the storage above. Monetary run `9d4829a5-5aa8-4e53-b0cc-d8dfb8f1e12b`
recorded `2000000 USD`, `2000 kUSD`, `4 USD/kg`, `0.000006 USD/J` and an ordinary
dimensionless value7. It used Model5 revision
`8d330783-add8-4b04-a817-a1f401ae01d0`, configuration
`a7c1f0d7-d6bf-43c0-817b-c68a6635321f`, and bundle12 digest
`7bb2d4b7f1edba721a5ed23043bff13bdfd612d973c637197ccdb1efedf6d47b`.
The saved 2025 price basis pinned explanation
`07c42f03-e63b-40ea-8c69-8b6c7cedb225`, digest
`bf6f15a3fee66b18bfeb65c4b024cfc3a04499c46ad51357b4dbd640bd79d5f8`.
The evidence is a synthetic units calculation, not an economic forecast or a
qualified release. Parent owns the integrated rerun and final qualification.

The successor execution cascade includes launcher preflight, AiiDA calculation
admission, output/result interpretation, retained bundle readers and archive
admission. Bundle12 keeps input-layout11 and result-protocol3; historical approach
closures retain their existing version restrictions.

## Current authoring and retained-history browser migration

Implementation and focused evidence commit: `a9d23096` (seven explicit owned
paths). The subsequent checkpoint-only commit records this identity; no tested
source changes follow the passing groups in this batch.

Follow-up batch on integrated parent commits `9fea921e`, `cb18a0fa` and
`801a63ce`: the current public Model5 portable export now invokes the closed
reader and semantic identity/digest checks. Explicit Model5 preview and edit
requests cannot silently return Model4. Seven public-boundary regressions cover
valid export, wrong digest/identity, and preview/edit format preservation.

The current browser fixture authors Model5/configuration6; older retained models
and configurations are seeded explicitly as historical records. A real browser
journey saves an exact USD quantity, attaches price evidence and publishes its
2025 economic basis, downloads and inspects the portable Model5 record, then
changes the same quantity IDs to catalogue kUSD. Inherited price fields clear;
the user explicitly saves a new 2026 basis while the original version stays
unchanged. A delayed revisions response proves configuration creation remains
disabled until the selected model version is fully loaded.

Retired-surface substitutions preserve observable guarantees: saved context is
checked through Record details and the public modified-run seed; retained model
assumptions expose their adjacent exact evidence; run Quantities check explicit
zero, physical results and unavailable outputs. Current portable export/import
replaces the removed comparison dialog, including keyboard focus, themes,
narrow layout and genuine 200% browser zoom. Model CSV still tests the actual
displayed declaration columns. Computational-record export remains covered by
its dedicated tests and the final native journey. During a modeling outage only
revision-list navigation metadata is permitted; retained content cannot be
replaced by a current-model read.

All commands remain `./hyprn-mvp dev check GROUP` with the documented data/tools
variables and the 16 GiB cache ceiling above. Browser groups explicitly select
the existing Playwright Chromium executable via `HYPRN_MVP_CHROMIUM`; no new
browser or dependency was installed. Host-specific paths remain outside source.

| Group | Result | Evidence storage ID |
|---|---|---|
| units-ui-authoring | 14 passed, 39.37s | 46d4de22-8e7c-4d69-b580-40ed94ad83e7 |
| units-ui-configuration | 7 passed, 25.53s | a89b350e-8179-4249-a100-f85a38d8248e |
| units-ui-history | 14 passed, 43.00s | 7a644b37-1da1-4f2d-bf04-a932f3af1964 |
| units-resolution | 109 passed, 1.90s | 1ab8b80d-3431-4d9a-9530-e8e4d0e90116 |
| units-api | 107 passed, 49.43s; includes all seven added regressions and generator test | 3075e6a4-21e6-4f04-93c6-32c2bc0d7519 |

Browser failures retained and corrected in this batch:

- Authoring first: 10 passed/4 failed, 66.39s,
  `00fbf741-038c-45e9-adfb-6e0f8fdb1963`: a real model-loading navigation race
  (parent fixed), unavailable default Chromium executable (selected installed
  reviewed executable), a removed edit selector, and a missing explanation-tab
  navigation in the final historical assertion.
- Configuration first: 5 passed/2 failed, 42.55s,
  `f15cb48a-c1e5-4e65-b333-7925ab788660`: parent corrected modified-seed9 dispatch
  and intrinsic input overflow in the shared unit editor.
- History first: 0 passed/14 failed, 102.74s,
  `941592d4-dd6b-48c2-901a-0bb1289f1316`: stale table/import selectors plus an
  invalid `kind` in the explicitly historical ResolvedInput2 fixture. Corrected
  exact fixture shape and migrated removed surfaces as described above.
- Authoring second: 13 passed/1 failed, 46.72s,
  `c25eb126-7955-4c50-a63f-a55172868521`: the new export/import journey reopened
  an already-open Model actions dialog. Corrected the actual nested navigation.
- History second: 8 passed/6 failed, 77.58s,
  `b6a0db54-35bd-49b3-9887-d66a18e15eb4`: removed context/run CSV controls,
  old Record details name, and navigation metadata mistaken for current-content
  substitution. The retained model package/import/tamper checks already passed.
- History third: 12 passed/2 failed, 48.99s,
  `75686f0e-89d5-40f0-bfb7-cbec71e76390`: the outage intercept incorrectly
  included application-owned explanation routes. These now reach the real API;
  a saved exact explanation followed by a changed current draft proves retained
  run Model explanation never substitutes that draft's basis. Assumptions
  dialogs without an explanation renderer continue to state its absence.
- units-public-types first: 1 failed/93 deliberately deselected, 2.01s,
  `07048372-5c45-4ac5-97ef-14d6b01197c5`: its generator-only selector exposed
  stale ModelDraftEditResponse4 mapping in current edits/preview routes. Parent
  corrected the mappings to5 and regenerated public contracts. The seven new API
  regressions run in `units-api`, not `units-resolution` or the generator-only
  `units-public-types` group.
- units-api first: 105 passed/2 failed, 51.88s,
  `4dc5fdfc-3041-4996-bbbb-bbbb85dc3c44`: all seven new regressions passed;
  two existing tests still validated catalogue2 responses with the frozen
  catalogue1 envelope. Updated those exact expected response readers to2,
  retaining the streaming size-before-parse boundary checks.
- History fourth: 13 passed/1 failed, 56.69s,
  `8fab0d89-0742-4a00-8f6d-3d0fc6ddb37c`: the added exact-explanation assertion
  targeted an assumptions-only dialog, whose ModelView has no explanation
  renderer. Moved that assertion to the real Run → Model → Model explanation
  surface, and retained truthful-absence assertions in assumptions dialogs.

Completed runner scopes were released; diagnostic artifacts remain in the
listed check storage. Automated browser evidence is not human acceptance.
Final integrated native execution/browser/export qualification remains owned by
the parent after the computational interpretation closure is integrated.
The API run retained the existing Starlette deprecation and ten unknown `quick`
marker warnings. No native numerical execution occurs in these typed-browser
fixtures. The final API and browser scopes exited0 and cleanup completed before
the shared lane was handed to the hosted-fence checks. The generated-route test
is included in the passing API group, so its generator-only group was not repeated.

## Integrated native export attempt and remaining browser qualification

Native fixture migration `c5cfd8df` replaced the removed Context heading with
exact Configuration record details JSON and seed context equality, and limited
permitted model-path reads to navigation metadata and application-owned
explanations. The integrated run used committed `d5cf6314`, including Manifest3.

Command: `./hyprn-mvp dev check units-native`, with the data/tools/cache/Chromium
variables above, explicit `HYPRN_MVP_SCRATCH_ROOT` pointing to the existing
development data root's `scratch` folder and
`HYPRN_MVP_TEST_SCRATCH_BYTES=17179869184`. The first start was refused before any
scope/test allocation because existing scratch used12,369,235,968 bytes against
the default10GiB ceiling. No old fixture was deleted; the bounded16GiB retry ran.

Result: **13 passed/1 failed**,622.04s (test phase619.37s), storage
`cd5902c9-cab8-45ee-87c9-0368a08d8f10`, scope
`ca69dd1e-d10c-4874-a505-8c5242f2b7fd`. Seven actual restricted executions, exact
immutable answers, rejection cases, offline/restart reads, three earlier archives
and the new monetary Manifest3 archive download/native inspection passed. The
producer browser stopped on obsolete `Draft · saved` text after a successful
edit; current save status is `Component saved`. Retained browser checks therefore
did not run. This is not a passing native group.

The complete selector audit also found the removed full-precision dialog. The
fixture now checks the real Output values table's exact-value titles against the
public retained records, explicit scientific unit rendering, keyboard output
inspection and Model/Results tab focus, with the same light/dark/narrow/200%
geometry checks. Other producer and retained selectors were checked against
current UI definitions and the already-green typed browser journeys. There is no
existing units-browser resume group: exploration-only continuation does not
apply, and the isolated native scope was released. No resume framework was added.

Compact build/attestation provenance and complete monetary archive bytes were
copied outside the repository before normal cleanup. External bundle directory
name: `hyprn-monetary-native-d5cf6314-ca69dd1e` (absolute host path supplied to the
parent). Its SHA-256 inventory covers runtime/source hashes, dependency selection,
builder/engine identities, image labels/layers,11 verified worker assets,
containment attestation, modeling overlays, monetary proof, native archive and
the7,337,889-byte Manifest3 archive. Archive SHA-256:
`604e0e2ccdf88de2cc94b519539e7130f62fe31a414e79305eb1b62be085fd1f`.
Monetary run `852228af-02d4-4eef-8546-93231ac0885f` pins model
`949ec93f-06f6-4591-a836-5359c5c14983` and explanation
`3f3d6732-9771-4d66-b21c-3f0e23a84f3e`; the archive interpretation closure digest
is `abed9bf4d282f0b7d30092211564c2715246dd28a82b444fa2faba7a863bb0d9`.

Inspected native worker `92dde98d…`, engine `d6814311…` and modeling fixture
`43e1e7c6…` are all Linux ARM64. The modeling fixture mounts reviewed current
overlays onto its pinned image; this does not qualify a fresh AMD64 staging
image. AMD64 target builds and release assembly remain parent-owned. The622s
dedicated-scratch test duration and earlier383s default-temp duration are test
environment observations, not product performance measurements. Cleanup journal
confirms `keep=false`, scope released and no supervisor failure.
