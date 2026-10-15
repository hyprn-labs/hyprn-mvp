# Modeling service provenance and scope

HYPRN MVP's private modeling service is a patched copy of WhatsOpt running behind the independently authored Modeling Backend Contract (`contracts/modeling.openapi.yaml`). It owns editable composition, definitions, ports, connections and source, immutable model and definition versions, model-local annotations and static OpenMDAO code generation. It holds no application or AiiDA store, launcher, container socket or provider credential, and never executes candidate code. Licensing facts and open items are summarized in `docs/legal/licensing.md`.

## Upstream material and reuse decisions

| Material | Origin and identity | Decision |
|---|---|---|
| WhatsOpt models, schema and Rails application | Official `WhatsOpt/WhatsOpt` commit `597f5abf18d4a6335c2f3b9174ab16acdf1de4bd`, source archive SHA-256 `4937188df6ea12daa8a2b00767005e3649d2974ab6e634409f7756043ef0b360`, pinned authoring image recorded in the deployment pins | Native database and model calls stay inside WhatsOpt. The repository licence is GNU AGPL v3; the frontend `package.json` declares `UNLICENSED`. No WhatsOpt product UI is copied into or distributed with HYPRN MVP |
| Contract, HTTP clients, tests and helper scripts | Independently authored from the HYPRN MVP contracts; no native serializer or UI code | Public IDs and engineering types only |
| In-process adapter and its successors | The ordered patches below: Ruby service, controller and model additions, native migrations, schema and tests | Explicit AGPL-3.0-only notices. Patches and their corresponding source stay in the service's compliance inventory. Deployment separation does not settle distribution licensing |
| Unit catalog | Derived from the pinned OpenMDAO 3.45.1 (Apache-2.0) in the reviewed worker image | No numerical engine or unit parser is reimplemented |

Independently authored files in this directory: `generate_unit_catalog.py`, `rehearsal.py` (builds a test image of the patched service exactly as the deployment manager builds it), `verify_rehearsal.py` (portable export, import into a second test service and restart retention) and `tests/`. The service bounds middleware, deterministic portable-record manifest and unit lookup live inside the AGPL patch.

## Ordered patches

Patches apply in this order, each exactly once with zero fuzz and no reverse application. All of them stay in both the provenance inputs and the corresponding-source notice directory of every image. The digest is the SHA-256 of the patch file.

| Patch | Scope | SHA-256 |
|---|---|---|
| `010-workspace-tests.patch` | Integration tests of the earlier in-service authoring workspace (removed from the image by the deployment policy) | `7c87f3d9296491ad8112b786edbb601e8781ca0c9cf16deec0705b5ad9bdc231` |
| `020-authoring.patch` | The earlier in-service authoring workspace: controller, service, views and routes (removed by the policy) and its analysis model change (retained) | `307854827065e53efa88ea38593f4b854e273b9e7a86253bbdbc7a2160197b1f` |
| `030-configuration.patch` | Configurations of that workspace, the generator's refusal of in-service execution, the array parser and the study-boundary migration (the generator, parser and migration are retained) | `05b318ea908336e2c7ce371f4250fdc1264c73c1bf0d719e381e80f43465adff` |
| `040-modeling-contract.patch` | The in-process Modeling Backend Contract adapter: typed commands, receipts in the native transaction, bounds, portable model records | `0ce5854d2c83a2a6def85b8d565155b29f430c592176eec546b5a0d22ba7730b` |
| `050-native-generation.patch` | The native static producer (section "Native static generation") | `051e1068e637487850e33490b3ce8a02b062255a7e85cbbe03a3503241f151a0` |
| `060-ui-discovery.patch` | Authorized discovery of immutable versions and transactional model display-name edits; replaces no generator or template | `0c06b429bcc08a6f0cd9561a0a3f8345a434869d71d32e29f0f6c2a4e5dd5030` |
| `070-assumptions-evidence.patch` | Model-local assumptions in the model identity metadata, covered by the native draft transaction and receipt; evidence IDs are opaque data resolved by the application | `3c07a1bc6f0d2078a0c4416894b8cb70915bcbb819ee3ca4f64041745fb8e6cd` |
| `080-unit-declarations.patch` | Unit accessors and validation, the native materializer, the frozen binding validator and the trusted unit catalog payload | `efa95728b550f32618854903bb47c6c3386137c0bce0f9b066c6cf5faad0085e` |
| `090-quantity-definitions.patch` | Model-owned quantity descriptions (`Definition4`) and `ModelRevision4` read dispatch; changes only `app/services/modeling_contract.rb` | `18cd7538f928d5fa5ca662d9b486fe11873214336a5595e8348535e93af0243e` |
| `deployment/modeling_policy.rb` | AGPL-3.0-only deployment adaptation (section "Reduced private service") | listed with the deployment source hashes |

The source image is built from the verified original archive and the dependency locks. Every retained file that patches 010–040 create or change is replayed at build time from that archive and the recorded patches, with zero fuzz and no offset; patches 050–090 then apply as listed above. Historical source-image layers are not inputs to the build.

## Reduced private service

The deployment policy removes the native product UI, controllers, templates and executable generation, check, run, monitor and sensitivity helpers, keeping the native graph and store and the contract adapter. It configures named primary and scratch SQLite connections inside the service's own store, disables schema dumps on the read-only root and uses an opaque internal analysis name while keeping the exact public engineering label. No native helper is moved into the HYPRN MVP application.

The modeling image is built from the pinned Ruby base, the installed gem tree, the Node binary (a native gem boot dependency) and the verified source image. Its acquisition stage installs the pinned gems and checks every cached archive against the published RubyGems SHA-256 recorded in `deployment/locks/whatsopt-gems.json`; Yarn uses the upstream immutable lock. The modeling stage performs no package installation or network fetch. Base images, upstream commit and archive, the resulting image, the effective runtime and source hashes are recorded in the deployment pin records. Python, AiiDA, the Docker CLI, the launcher, provider keys and application data are absent. The image still contains operating-system and build tooling; it is a reduced image, not a minimal production distribution.

The service runs on a private network only, as a fixed non-root user with a read-only root filesystem; its only writable mount is its own store. Ordinary setup keeps the existing database and both credentials, check verifies image, mount, user, network and source identity, and stop stops only this service. Setup never discovers, migrates, deletes or restarts unrelated resources; a failed initialization or identity check is kept and repaired forward, never by removing the database or resetting its schema.

## Corresponding source and notices

The image keeps `/native/LICENSE`, `/native/Gemfile`, `/native/Gemfile.lock`, `/native/package.json`, the modified native source, and `/usr/share/hyprn-mvp-modeling-source/` with the original upstream archive, every patch, the deployment policy, the source and modeling Dockerfiles, the upstream and gem locks, this provenance record and the source identity. The repository keeps the native, control and authoring build recipes and pins; the upstream corresponding source is identified by the official commit and archive hash above. Source access for recipients includes that upstream source, every modification and the matching build and install recipes, offered alongside any distribution or AGPL network offer. This is the compliance inventory, not legal certification, and network separation is not treated as removing obligations.

## Native static generation

`050-native-generation.patch` keeps the pinned `WhatsOpt::OpenmdaoGenerator` orchestration (code, discipline and main generation) and `CodeGenerator` ERB rendering, and permits only six native templates: analysis, analysis base, discipline, discipline base, base header and `__init__`. The static constructor cannot allocate the server or EGMDO generators. Convenience generation, formatting, check, run, monitor, run scripts, package and test scripts and sub-analysis or optimization helpers raise. Generated analysis and component classes stay native OpenMDAO `Group` and `ExplicitComponent` classes; the neutral entrypoint only returns the frozen model.

Declared adaptations: deterministic headers, native explicit connection endpoints without promotions, explicit `RunOnce` solvers, scalar NaN initial values, insertion of the authored body with separately recorded BOM, newline and indentation transforms, and a scalar symbol view with assignment and completion instrumentation. Original authored bytes are kept independently under `sources/`. Source is inserted as data into trusted ERB templates, never evaluated as Ruby or imported as Python.

`NativeProgram` invokes a fixed Ruby helper with the exact frozen model and configuration JSON in an owner-only per-request directory. The helper opens its own connection to a fresh derived SQLite schema; it never receives a draft or native ID or rebinds the server connection. Bounds: 20 s CPU, 28 s wall time for the helper and 30 s for the calling request, 1 GiB address space, 16 MiB per file, 128 descriptors, 2 MiB input, 32 MiB expanded artifact, 1,000 files and four concurrent generation slots. Orphan scanning is bounded to 128 entries older than 120 s, with active leases protected. A failure or timeout kills and reaps the child and removes its scratch. A successful artifact and its receipt are stored in the authoritative transaction.

The prepared artifact (format 2) contains the exact generated files, bindings and source-line mapping, the original sources, the original pinned source archive, the original and patched native helper and template inventories, all ordered patches, the original LICENSE, a generated-code notice, the model authors' licence declarations, the Ruby `Gemfile.lock` and the worker lock, plus the build and policy recipe and this provenance record. The public contract schemas, which are build inputs, are not copied into the artifact: `provenance/support/schema-identities.json` records each one by path, SHA-256 and length (the modeling schema the service reads stays in the patched inventory).

Identity digests use RFC 8785 SHA-256 over path-sorted provenance records: `generator_digest` covers patched records with role generator; `template_digest` covers role template; `adapter_digest` covers every other patched record (model helpers, schemas, static adapter, policy and recipe). `source_archive_sha256` is the audited upstream archive hash. Every inventory record and artifact byte has its own size and SHA-256. The prepared digest includes receipt and file IDs; the executable-content digest excludes them and covers the protocol, model, configuration and generator identities plus the sorted generated path, size and hash tuples. Closed schema checks and producer ownership, inventory and source-range checks run before an artifact is stored.

## Model-local assumptions

New models are written in format 2 (`model2`); older drafts and versions keep their original shape. Only an explicit `Preview2`/`Apply2` builds the upgrade, and only an accepted `Apply2` persists it. Stable assumption IDs, instance ownership, distinct citation limits and explicit removal are enforced before persistence and at import. The only materializer change selects the closed private configuration 3 type; prepared artifact format 2, program protocol 1, the generator, the six templates and numerical settings are unchanged. There is no second editable graph, evidence library, table or application credential in the service.

## Units

`generate_unit_catalog.py` builds the finite unit catalog at build time: 21 base spellings plus J/kg, kJ/kg, MJ/kg, kg/m**3, g/cm**3, m**2, cm**2 and mm**2. It requires OpenMDAO 3.45.1 and verifies the installed `units.py` SHA-256 (`9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92`). It runs inside the reviewed worker image as a non-root, read-only, network-disabled, resource-bounded process, with the trusted script on standard input and no candidate, store or credential mounts. Every compatible zero-offset factor, including identity temperatures, comes from the pinned engine; affine temperature conversion stays excluded.

The catalog digest is the SHA-256 of the sorted-key, compact, finite JSON encoding of the catalog body without `catalog_digest`. The emitted bytes are embedded in the 080 patch; build tests compare them with fresh trusted output and every pair with an independent probe of the pinned engine. Compatibility interpretation digests use the contract digest over the complete catalog. The deployment source hashes include the generator and every ordered patch.

Static readiness validates stored declarations and follows each active instance's `definition_version_id`, including every bound input and output port. Unused unspecified versions do not block resolved active versions; shared stable port IDs never select another version. Malformed declarations, or a mix of string and object ports in one definition, are rejected. Earlier empty-string units stay dimensionless. Only catalog members reach native interpolation and frozen binding records; original model, definition and source data are never edited.

## Quantity descriptions and execution capability

`Definition4` descriptions name exact ports in one immutable definition version and are authored through the native transaction, preview, expected definition version, receipt and explicit local-instance replacement. Earlier notes stay notes; earlier string units are never promoted by a descriptive revision; typed declarations keep their exact meaning. Each definition stays homogeneous, and active occurrences resolve through their exact definition version. Static preparation refuses unresolved units and keeps exact authored source bytes. The bounded schema evaluator combines object and array keyword constraints with `anyOf`, including constraint-only port branches, rather than bypassing closed `Definition4` fields. The adapter advertises the `quantity_definitions/1` capability and the execution bundle formats 2, 3, 4, 5, 6 and 8; format 7 is reserved for document citations and not advertised.

## Verification

`python3 modeling/rehearsal.py --native-static` builds the modeling image offline from the pinned source image, exactly as the deployment manager does, and prints its identity; the reviewed result is pinned as the producer image in the deployment pins (`modeling_producer`), and the static generation tests (`modeling/tests`) run that image. These tests run disposable non-root, read-only-root, network-disabled containers with fresh in-memory databases and no store or secret mounts, and they inspect generated Python bytes without importing or executing candidate code. Numerical execution is verified separately in the restricted worker.

Generation behaviour relies on [ActiveRecord transactions](https://api.rubyonrails.org/classes/ActiveRecord/Transactions/ClassMethods.html) (savepoints keep domain rejections while rolling back graph changes; uncaught infrastructure faults roll back both receipt and effects) and canonical JSON per [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785).

## Recorded model-source baseline

`upstream/whatsopt-patches/005-model-source-baseline.patch` is AGPL-3.0-only. It records seven existing files from the reviewed modeling reference `sha256:55979e903b5ad398ee8e990ae42c2e2290f34c3a8fc118c6cbc58beedb64f33f` that were absent from the previously recorded patch chain. It preserves source storage, the 65,536-character bound, copying and serialization, ownership-scoped implementation updates, and the existing receipt column. It introduces no new behavior. Before hashes refer to the pinned original WhatsOpt archive; “absent” means the migration is added. After hashes are the exact reference bytes. Staging verifies both identities and refuses patch fuzz or offset.

| File | Original SHA-256 | Reference SHA-256 |
|---|---|---|
| `app/models/discipline.rb` | `7ba0317e631e302c9aefc71c9086a436c5c900d8b16260ac2bcc39100fa5024d` | `4d9da03c6700b5bc9fe688d0492758eeba0207e5a4d52a18c00b1afbbed97d5c` |
| `app/models/openmdao_analysis_impl.rb` | `8f04bb65ea8b79c142434ef65826e6ec86aecf26e0511d853f335bb91fec0b18` | `931e505d3c1e54b08794894837024b6e9f65c00e07c290cbe1d49b5219c4456c` |
| `app/models/openmdao_discipline_impl.rb` | `794d06392db73074fa68581c0a0ddb56bcd4f557edbccd4e0a3d88cae738d4a4` | `1126b37908764c579d50194d5f799b09b086ca65ad3d3d6bcf6ac54def06f044` |
| `app/serializers/discipline_attrs_serializer.rb` | `1933dca2dc1e8a955fd6a21ba4dafa6e363938d88086c3cf077ce5db56f3aab8` | `79c393e3186a7d5374cb6cd2de314e742524fe61b33ca4e6d25cc9219b729304` |
| `app/serializers/openmdao_discipline_impl_serializer.rb` | `fca004ce2a1502395aaa49e3f6776605226c08d01c5a1717d4762c1a6f22dda6` | `eb2f0860161af83bf5bd5b4d9894519427655a0ce74e6c65d7c898e3df13ddc3` |
| `db/migrate/20261008140000_add_probe_source.rb` | absent | `0312e376caf96f675553f341641dc86c46cf19d4156186b061763918f2f3df96` |
| `db/migrate/20261008140100_add_probe_receipts.rb` | absent | `467eeb429337a6dc674c915e2528160d01d2f9e8ba911fc8ced273c761bcc240` |

Patch 050 replaces the entire discipline template. Its complete reviewed postimage is materialized against the pinned original template and must equal SHA-256 `d9c720054302de48dd43116b7dc4cc563d1ca120c5ce278a2708e1b981bfcec7`. This removes a dependency on four intermediate authoring-template lines without changing the final template. The adapter-only 060 patch and the adapter section of 050 are represented by the cumulative 040–090 adapter, so their duplicate build-stage hunks are omitted; all complete patches remain in the corresponding source.

## Ordinary engineering catalogue extension (2026-10-15)

The approved additive catalogue extension is generated from the same reviewed
OpenMDAO 3.45.1 units source. Patch 080 carries the generated 49-entry internal
catalogue (48 physical spellings plus dimensionless). Existing spellings and
conversion factors are preserved; no affine conversion or general parser is added.
The exact schema exception and permitted suffix are recorded in contracts/README.md.
