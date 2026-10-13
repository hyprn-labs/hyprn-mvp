# Phase 4: Documents - Research

**Researched:** 2026-10-13
**Domain:** Source documents on AiiDA (originals, collections, annotations, extraction), study-scoped document API, chunked upload, isolated PDF parser image, search projection, citations inside evidence version 4 and the document-bearing scientific chain, text-first reader UI
**Confidence:** MEDIUM overall. The codebase findings are HIGH (read this session). The parser supply chain and AiiDA concurrency facts are MEDIUM or LOW (external, partly unverified). Two contract or product conflicts block later steps until the product owner decides (see Open Questions).

## Summary

Phase 4 delivers steps 1–13 of `docs/specs/documents.md` §12 on top of a tree that already holds three things: the full wire contract (119 `Document*` definitions in both shared schemas, plus a registry with 47 routes, 7 read verbs, 15 write verbs, limits and transitions), one production adapter (`NativeDocuments`, which stores and reads originals only) and a qualified collection-deletion protocol. That protocol lives only as a test probe (`CollectionProtocolProbe` in `deployment/tests/documents_native_fixture.py`), not as product code. No application route, store table, bridge verb, parser image, search projection or UI exists. The application still advertises `"documents"` in `capabilities.unavailable` [VERIFIED: codebase grep and read of `application/src/hyprn_mvp_app/api.py:205-206`].

Three facts change what the plan can promise:

1. **The allocated chain predates the current model format.** The document-bearing scientific chain in `contracts/documents.md` (Configuration5 / private 4 / FrozenConfiguration6 / ExecutionBundle7 / RunHistory5 / ModifiedRunSeed5 / ApproachClosure2) pairs only with Model2 and Model3. The application already writes a newer chain for Model4 and approach closure 3: FrozenConfiguration7, ExecutionBundle8, RunHistory6, ModifiedRunSeed6 and ApproachClosure3 (the "polish envelope"). As allocated, step 11 cannot carry citations through a configuration of a current Model4 model. A contract amendment is needed, and it needs a product-owner decision.
2. **A security fix for pypdf was published today.** `pypdf 6.20.1` was published on PyPI on 2026-10-12, and its release notes list a security fix for cyclic trees. The audited pin is `6.20.0`. The provenance record's own rule ("a newly applicable advisory … blocks that installation for review") applies to step 6.
3. **The single writer is blocked during every run.** Today one host executor process serves every native call synchronously, and `launch` blocks it for the whole run (`runner.run_get_node(process)`). Document reads therefore need a second, read-only process pair supervised by the executor. Without it, every download and collection list would freeze during a run. Every native write (upload publication, collections, annotations, extraction) must join the existing single writer and report "Waiting for native storage" while a run holds it.

**Primary recommendation:** Build Phase 4 as four layers, each with its own test groups named after its capability:

- (a) Native adapter extensions in `hyprn_mvp_integration.documents` (collections, annotations, extraction calcfunction). Port the qualified probe protocol into product code with revision ≥ 1.
- (b) A document operations queue in the application store, drained by the existing executor loop (writes), plus a separate supervised read loop (reads).
- (c) A new application module (`documents`) behind study-scoped routes with a route-scoped raw-body exemption for chunk PUT only.
- (d) UI built only after design-system additions (Documents layout, study tab, measured progress, text reader surface) are made in `design-system/` and `ui/src/design`.

Do not start step 11 until the product owner decides how citations reach Model4 configurations. Do not install any parser wheel until the product owner decides 6.20.0 versus a re-audited 6.20.1.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Original bytes, collections (Groups), annotations (node extras), extraction provenance (calcfunction) | Native storage (AiiDA via execution integration, host executor) | — | D-01; AiiDA is the sole writer of its profile; the application holds no native credentials |
| Public identity, family metadata, archive, public↔native association, operations and mailbox | API / Backend (application store, SQLite) | — | D-01; `store` is the transaction owner |
| Upload chunk spool (transient, ≤ 24 h) | API / Backend (application container writes beneath its `/store` mount) | Host executor reads it by server-derived handle | Only the upload route takes raw bytes; the spool is never served |
| Native writes (store original, collection, annotation, extraction start) | Host executor single writer (existing serve loop) | Application dispatcher (app side of the bridge) | D-09 single-writer discipline |
| Native reads (descriptor, list, member, annotation, fragment, original, status) | Supervised read loop (separate host process plus app-side mailbox drainer) | — | Must stay responsive while `launch` blocks the writer |
| PDF and text extraction | Parser container (pinned image, no network) called from an AiiDA `@calcfunction` in the host writer | — | D-05; containment demonstrated before use |
| Search projection (bounded substring match, coverage) | API / Backend (application store, rebuildable) | — | §3: derived, keyed by extraction digest, never authoritative |
| Citation resolution, quotation hashing, evidence v4 commit barrier | API / Backend | Read loop (fragment verb for exact text) | Quotation comes from native artifact bytes; client quotes are never trusted |
| Library, reader, collections and citation UI | Browser (React, design-system components only) | — | Rendering and selection only; no authorization or authoritative outcome in the browser |
| Historical source display during a modeling outage | API / Backend (frozen descriptors in evidence and run records) | Read loop for bytes, if available | §8 and §15.4; the modeling service is never contacted |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Locked by `docs/specs/documents.md` and `contracts/documents.md`:

- **D-01** Ownership: original bytes (one `SinglefileData` node per version, fixed repository filename), collections (one AiiDA `Group` per collection, membership is the exact version nodes), annotations (one bounded namespaced metadata object per annotation on the exact original node) and extraction (a genuine `@calcfunction` with real input and output links) live in AiiDA. Public identity, study scope, family metadata, the public-to-native association, evidence, citations, relationships, usage and the rebuildable search projection live in HYPRN MVP. No second file, membership or text store; AiiDA's REST API is never exposed.
- **D-02** Every operation is study-scoped under `/api/1/studies/{study_id}`; study access is checked before any association or native lookup and again at dispatch, publication and every delivery; unknown and foreign identifiers return the same non-disclosing not-found; non-GET requests keep the origin, session and cross-site request checks.
- **D-03** Mutations take a client `command_id` and, where state is edited, an `expected_revision`; outcomes are typed operations; recovery looks up the exact immutable witness before current state; an uncertain outcome is never blindly retried.
- **D-04** Collection deletion is logical and terminal (§9.1); physical Group deletion is never used.
- **D-05** Admitted formats: PDF, strict UTF-8 text, Markdown, CSV; media type, header and extension must agree. The PDF parser is the audited `pypdf==6.20.0` wheel (SHA-256 recorded in `integration/document-parser.lock.json`), installed without dependency resolution in a separate pinned parser image (non-root, read-only, no network, capabilities, secrets, AiiDA profile, application database or host socket). The image build verifies the wheel bytes. Containment is demonstrated, not inferred; until then extraction stays unavailable while storage and download work.
- **D-06** Locators are `original_file`, `pdf_page` and `extracted_span` (half-open codepoint range, server-computed quotation); a client-supplied quote is never trusted. Citations live inside evidence version 4 and freeze a `DocumentCitation1` descriptor; the document-bearing contract chain is implemented as allocated, without widening earlier versions.
- **D-07** Limits per §11 (10 MiB originals, 256 KiB chunks, 500 PDF pages, 1 active extraction per installation, parser 30 s / 1 CPU / 512 MiB, …) live in reviewed configuration and are tested.
- **D-08** UI per §15: Documents is its own study tab immediately before Evidence; collections panel (190 px) beside a fluid list; reader with a fluid text column and a 350 px side column; escaped text only, never rendered uploads; plain language and the key copy of §15.5; only design-system components and tokens. Features appear only when implemented: no placeholders or disabled future controls.
- **D-09** Native writes keep the single-writer discipline; a narrow read loop with read verbs only runs under the existing execution manager so reads stay responsive during a blocked run (measured, not assumed).
- **D-10** Each step ends in working, tested behaviour; UI steps carry light and dark, keyboard and genuine 200 % zoom evidence; automated evidence is recorded separately from human acceptance.
- **D-11** Runtime data (stores, upload spool, parser scratch, logs) lives under the installation's data root, never in the repository or a synced folder.
- **D-12** Security per §16 (OWASP ASVS 5.0.0 Level 1; high findings block release): cross-study access, malicious upload, path and header injection, active content, parser exploit and overload, supply chain, duplicate or partial effects, prompt injection.

Open product decisions (recommended defaults):

- **PD-4.1 Steps 14–18** (deletion fences, portable policy, import, restore and backup drill, lifecycle and export UI, end-to-end acceptance). Default: a later phase, "Documents lifecycle and portability", after the first release. Until then permanent deletion, export, import and restore are advertised unavailable; archive and unarchive, remove from collection and delete collection are available. DOC-01 stays `partial`.
- **PD-4.2 Annotation label.** Default: "Annotations" in the UI (never "notes"), kept out of the Evidence page (§18 Q1).
- **PD-4.3 Archived studies.** Default: archiving a study makes its documents read-only with it; nothing is deleted; restore re-enables editing (§18 Q4).
- **PD-4.4 Rendered PDF pages.** Default: text-first reader only (§18 Q5).
- **PD-4.5 Upload transport.** Default: the contracted chunked protocol for every edition (§18 Q9).
- **PD-4.6 Access-protection depth in the local edition.** Default: the study-scope check on every route always; the full persona, revocation and cache matrix before multi-user cloud (§18 Q7).
- **PD-4.7 Parser wheel acquisition.** Default: the parser image build fetches the wheel from the package index by its pinned filename and verifies size and SHA-256 against `integration/document-parser.lock.json` (the same fail-closed acquisition as Phase 2); no vendored wheel.
- **PD-4.8 Release exposure.** Default: the Documents capability is advertised available in the first release only when steps 1–13 pass and the Phase 5 reviews close their high findings; otherwise it stays advertised unavailable.

### Claude's Discretion

- Task boundaries inside each step (one task per fresh executor), test fixtures, and the order of steps that have no dependency on each other (for example the parser image beside the library UI).
- Internal module layout inside `hyprn_mvp_app` and `hyprn_mvp_integration`, within the acyclic import rule.

### Deferred Ideas (OUT OF SCOPE)

- Steps 14–18: deletion fences, permanent deletion, portable export and import, restore and backup drill, lifecycle and export UI, end-to-end acceptance (PD-4.1).
- Agent document tools and agent upload.
- OCR, format conversion, rendered pages, ranking and semantic search.
- Authored documents (Tiptap) and live co-editing (Yjs, cloud only).
- Requalification of the native transaction and logical deletion on the cloud database backend.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOC-01 | The engineer can upload, store, read, browse, download, annotate, search and cite source documents, organize them in collections, and archive or safely delete them, with immutable source locations, visible processing failures and retries, and protected retained references. (Status `partial`; stays `partial` after this phase per PD-4.1.) | Steps 1–10 and 13: native collections and annotations (§Step map 1), operations queue plus read loop (2), chunked upload and library (3–4), collections (5), parser image and extraction (6–7), projection and search (8), reader (9), citation resolver (10), evidence UI (13). "Safely delete" (permanent deletion) is deferred (PD-4.1) |
| HUM-06 | The engineer can attach and inspect assumptions with evidence, … sources and checks at their declared scopes. (Remaining: "document citations (DOC-01) …") | Step 10 (EvidenceCreate4/Revise4 with `DocumentCitation1`), step 13 (all five citation paths of §15.4 reach the exact source from assumptions, configurations, approach items, runs and the Evidence page) |
| RUN-02 | The engineer can reopen an earlier run with its exact source, inputs, context, evidence … after edits, restarts or a modeling-service outage. ("Cited document passages join with DOC-01") | Steps 11–12: the document-bearing frozen configuration, bundle and run history keep the exact citation descriptors and quotations; a historical read uses only application records and the document read loop, never the modeling service. **Blocked for Model4 configurations until the chain decision (Open Question 1)** |
</phase_requirements>

## Project Constraints (from AGENTS.md)

Binding directives the planner must verify each task against:

- **Namespaces.** Packages are `hyprn_mvp_app` and `hyprn_mvp_integration`. The public contract is `contracts/hyprn-mvp.openapi.yaml`. The environment prefix is `HYPRN_MVP_`. These are the final Phase 1 names.
- **Science.** Unavailable is never zero (null with a reason). Historical reads never substitute current content. Saved versions and recorded runs never change.
- **Execution.** Candidate code runs only in the attested worker. Saving, import, validation, preview and preparation never import candidate code. The modeling service never holds the launcher, socket, AiiDA profile or application DB.
- **Stores.** Each store has exactly one writer. An uncertain or ambiguous outcome is reconciled by lookup and never re-dispatched automatically.
- **Security and contracts.** OWASP ASVS Level 1 applies; high findings block a release. Every API change keeps the contract tests and the UI contract checker green.
- **Forbidden additions.** No second editable model graph, distributed transaction, custom scheduler or provenance platform. No WhatsOpt code copied into clients.
- **Import graph.** The application import graph stays acyclic; `application/tests/test_module_boundaries.py` pins it.
- **Locations.** No absolute path in code. Locations resolve flag → `HYPRN_MVP_*` → installation configuration → per-OS default (path-policy module) → ask. Live stores, logs, scratch, evidence and credentials never go in the repository or a synced folder. Tests run only in scoped scratch stores.
- **Dependencies.** A new dependency needs its source, exact version, hash and licence recorded before install. Licences must be permissive. Conflicts are raised before vendoring.
- **AGPL scope.** WhatsOpt patches stay in AGPL scope with notices and corresponding-source records. This matters for step 11: the modeling service must admit the private 4 projection through a new patch.
- **UI.** Components only from `ui/src/design`. Tokens only from `design-system/tokens.json` → generated `tokens.css`, which is never hand-edited. No inline styles, external fonts, URLs or CDNs. Status is shape + word + colour. `python3 ui/check_design_system.py` must print no FAIL line and `python3 ui/design_tokens.py --check` must pass. Screenshots stay outside the repository. Automated evidence is never human acceptance.
- **Process.** One numbered task per fresh executor. Commits are atomic and stage explicit paths only. Each task leaves a checkpoint file with commands, counts, failures, identities, released scratch scopes and risks. Tasks run in parallel only on disjoint file sets. Comments and test names state invariants, not work items.
- **Host-specific values.** User memory: no machine, account, email or other-company references anywhere in the repository or its history. Commits carry no co-author trailer.

## Current State (today's tree) and Phase 1 final names

### Rename map (Phase 1 → names Phase 4 code must use)

| Today | Final (Phase 1 task) | Source |
|---|---|---|
| `application/src/hyprn_mvp_app/` | `application/src/hyprn_mvp_app/` (1.4) | 01-PLAN.md task 1.4 |
| `integration/src/hyprn_mvp_integration/` | `integration/src/hyprn_mvp_integration/` (1.4) | 01-PLAN.md task 1.4 |
| `contracts/hyprn-mvp.openapi.yaml` | `contracts/hyprn-mvp.openapi.yaml` (1.4) | 01-PLAN.md task 1.4 |
| Session cookie `hyprn_mvp_session` | `hyprn_mvp_session` (1.4) | 01-PLAN.md task 1.4 identifier table |
| `HYPRN_MVP_APP_STORE`, `HYPRN_MVP_ORIGIN`, `HYPRN_MVP_MODEL_URL`, `HYPRN_MVP_MODEL_KEY_FILE` | `HYPRN_MVP_APP_STORE`, `HYPRN_MVP_ORIGIN`, `HYPRN_MVP_MODEL_URL`, `HYPRN_MVP_MODEL_KEY_FILE` (1.4) | 01-PLAN.md task 1.4 |
| Text extractor identity | `hyprn-mvp-utf8/1` | 01-PLAN.md task 1.4; documents.md §7 |
| OpenAPI extension `x-documents-contract`, `x-hyprn-mvp-file-schemas` | `x-hyprn-mvp-…` prefix (1.4); exact new key name not stated [ASSUMED: `x-hyprn-mvp-documents-contract`] | STATE.md blocker line; 01-PLAN.md task 1.1 step 8 |
| Native metadata namespace `NAMESPACE = 'hyprn_mvp_documents'` and probe protocol `'hyprn_mvp.documents.collection-probe2'` | renamed under the `hyprn-mvp` namespace by 1.4 (wire and record identifiers) [ASSUMED: `hyprn_mvp_documents`] | `integration/src/hyprn_mvp_integration/documents.py:18` [VERIFIED: Read] |
| `contracts/tests/test_documents_planning_gates.py` | `contracts/tests/test_document_parser_adoption.py` plus new `integration/document-parser.lock.json` (1.8) | 01-PLAN.md task 1.8 |
| `ui/check_ui_contract.py` | `ui/check_ui_contract.py` reading `ui/control-map.json` (1.6) | 01-PLAN.md task 1.6 |
| `deployment/migrate_runtime.py`, `approach_polish_release.py` | `deployment/modeling_runtime.py`, `deployment/release_binding.py` (1.5), then `deployment/release.py` (Phase 2 task 2.8) | 01-PLAN.md 1.5; 02-PLAN.md 2.8 |
| UI evidence variable `HYPRN_MVP_UI_EVIDENCE_ROOT`, nav build `HYPRN_MVP_NAV_BUILD` | `HYPRN_MVP_UI_EVIDENCE_ROOT`, `HYPRN_MVP_NAV_BUILD` (1.6) | 01-PLAN.md task 1.6 |
| Runner | `deployment/checks.py` already exists (task 1.1 done) | STATE.md |

The Documents groups already carry capability names after task 1.1 (quoted verbatim from `deployment/checks.py:165-187` [VERIFIED: Read]): `'documents-native-atomicity'`, `'documents-native-originals'`, `'documents-collection-protocol'` (mode `'native'`); `'documents-parser-adoption'`, `'documents-contracts'`, `'documents-citation-contracts'` (mode `'application/contracts'`); and `DOCUMENTS_MEASURED_GROUP = 'documents-collection-protocol'`. The parser-adoption target still names `'contracts/tests/test_documents_planning_gates.py'` until 1.8.

### What `NativeDocuments` delivers versus `contracts/documents.md`

Constants quoted verbatim from `integration/src/hyprn_mvp_integration/documents.py:16-21` [VERIFIED: Read]:

```
MAX_ORIGINAL = 10 * 1024 * 1024
CHUNK = 256 * 1024
NAMESPACE = 'hyprn_mvp_documents'
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
HASH_PATTERN = re.compile(r'^[0-9a-f]{64}$')
MEDIA = {'application/pdf', 'text/plain', 'text/markdown', 'text/csv'}
```

| Contract element | Delivered today | Gap for Phase 4 |
|---|---|---|
| `document-write / store_original` | `store_original(identity, payload, source)`: one transaction stores a `SinglefileData` (`original.bin`) with immutable attributes, reads it back and stores a `Dict` witness (`schema_version='documents-witness/1'`); `reconcile()` treats one witness as the outcome, several as uncertain and a changed digest as a conflict [VERIFIED: codebase read] | None in the adapter. The caller (bridge, transfer resolution, writer fencing, authorization) does not exist |
| `document-write / reconcile` | `reconcile(identity)` for uploads only | Generalize to every native category (collection, annotation, extraction) |
| `document-read / descriptor`, `original` | `descriptor()`, `stream()`, `read(offset, byte_length)` (≤ 256 KiB, base64, `nosniff`, `no-store`, attachment) | Wire into the read loop; `DocumentNativeOriginalReply1` framing |
| `collection_create/update/members/delete`, active-only list | **Not in the adapter.** The protocol exists only as test probes: `AtomicityProbe` and `CollectionProtocolProbe` in `deployment/tests/documents_native_fixture.py` (Group extras metadata, logical delete, witness, replay-before-visibility, active filter before `limit(100)`, crash and kill qualification, 10,000 members) [VERIFIED: codebase read] | Port into `hyprn_mvp_integration.documents` as product code. Fix the revision baseline: the probe starts collections at revision `0` (`revision=-1` create command), but the contract has `DocumentCollection1.revision` `"minimum": 1` and `lifecycle` `"const": "active"` [CITED: contracts/schemas/model.schema.json `$defs/DocumentCollection1`, extracted programmatically] |
| `annotation_create/revise/delete`, `annotation` read | Not started | Bounded extras object per annotation on the exact original node; ≤ 100 per version; revision CAS; witness per command |
| `extraction_start`, `fragment`, `status` | Not started | Calcfunction, parser launcher, manifest, text folder |
| `list`, `member` reads | Not started | Native active-filtered queries before pagination |
| `source_delete*`, `export`, `import`, `restore` | Not started | Deferred (PD-4.1); advertised unavailable |

The integration package is partly attested. `documents.py` is **not** in `ATTESTED_PROJECT_FILES` (`application/tests/test_module_boundaries.py`) [VERIFIED: codebase read]. Keep it that way: no attested module (`launcher`, `calculation`, `results`, `worker`) may import any document module. The two-sided coverage test would fail and the worker attestation would change.

### Contracts that exist (allocated, not consumed)

- **Shared schemas.** `contracts/schemas/model.schema.json` and `execution.schema.json` each hold 538 `$defs`, 119 of them `Document*`, plus the `x-documents-contract` registry with keys `version, definitions, routes, bridge, runtime_invariants, limits, operation_transitions, extraction_transitions, collection_protocol, scientific_allocations_owner, scientific_allocations, extraction_reconciliation, operation_commit_authorities`. The registry holds 47 routes, 7 read verbs and 15 write verbs [CITED: programmatic extract of `contracts/schemas/model.schema.json`].
- **Evidence and citations.** Allocated: `EvidenceCreate4`, `EvidenceRevise4`, `EvidenceRecord4`, `EvidenceSnapshot4`, `EvidenceCitationPreviewRequest4/Preview4`, `DocumentCitation1`, `DocumentCitationCandidate1`. The application validates only `"EvidenceCreate"` (union of 1–3) and `"EvidenceRevise3"` on its evidence routes [VERIFIED: codebase read of `api.py` evidence routes].
- **Document-bearing chain (allocated).** `ConfigurationRequest/Candidate/Revision/Preview/Commit5`, `ModelingConfiguration4`/`Revision4`, `FrozenConfiguration6{Model2,Model3,Model2WithModel3}`, `ExecutionBundle7{Model2,Model3}`, `RunHistory5*`, `ModifiedRunSeed5*`, `ApproachClosure2*`, `AssumptionEvidenceResolution2`. The registry status is `"contract_only_runtime_pending"` [CITED: programmatic extract].
- **Newer chain already in use (not document-bearing).** `FrozenConfiguration7{Model2,Model3,Model4}`, `ExecutionBundle8{…Model4}`, `RunHistory6*`, `ModifiedRunSeed6*`, `ApproachClosure3`, `ConfigurationPreview6`. Quoted from `application/src/hyprn_mvp_app/execution_bundle.py:174-182` [VERIFIED: Read]:

  ```
  def uses_polish_envelope(model,closure):
      return model['schema_version']=='4' or closure is not None and closure['schema_version']=='3'
  ...
  def frozen_version(model,closure):
      return '7' if uses_polish_envelope(model,closure) else '5' if uses_units_envelope(model,closure) else '4'
  ```

  Configurations pair as quoted from `application/src/hyprn_mvp_app/configuration.py:41-49` [VERIFIED: Read]: `if model['schema_version'] in ('3','4') and configuration['schema_version']!='4': raise DomainError('invalid_configuration',422)`. So **every current Model3 or Model4 configuration is Configuration4**, and Model4 or closure-3 runs freeze as FrozenConfiguration7 and ExecutionBundle8. The allocated document chain covers none of these. This is Open Question 1.
- **Modeling contract.** `contracts/modeling.openapi.yaml` admits only `ModelingConfiguration2/3` and `ModelingConfigurationRevision2/3` [VERIFIED: grep]. Private 4 needs a modeling contract change plus a new WhatsOpt patch after `090-quantity-definitions.patch` (AGPL scope), and a rebuilt modeling image.

### Application today

- **Routes** live in one `create_app()` in `api.py`, under `/api/1/studies/{study_id}/…`. The `boundaries` middleware applies to every request:
  - exact host check;
  - origin, session and CSRF checks on POST, PATCH, DELETE and PUT;
  - a read of the **whole body** up to 2 MiB;
  - a rejection of any non-empty body whose content type is not `application/json`.

  Quoted from `api.py:122-128` [VERIFIED: Read]: `if len(raw)>2*1024*1024:raise DomainError("limit_exceeded",413)` … `if request.headers.get("content-type","").split(";")[0]!="application/json": raise DomainError("invalid_request",400,…)`. **The chunk PUT needs a route-exact exemption** (raw body, ≤ 262,144 bytes, `application/octet-stream`) without loosening any other route.
- **Authorization** is `Store.authorize(db, actor, study, write=False, owner=False)`. It returns `resource_not_found` 404 for a missing membership and `forbidden` 403 for an insufficient role [VERIFIED: Read `store.py:243-247`]. Documents reuse it unchanged, called before any association lookup.
- **Store** is SQLite with `isolation_level=None` and explicit `BEGIN IMMEDIATE` for writes. The schema is applied with `CREATE TABLE IF NOT EXISTS` in `Store.__init__` (additive migration pattern), and immutability triggers protect evidence and configurations [VERIFIED: codebase read]. No document table exists.
- **Receipts and outbox.** `receipts(scope, category, command_id, …)`, `outbox` (runs) and `computational_record_requests` (an export queue drained by the executor loop with `--with-exports`) exist. That export queue is the closest existing pattern for a document operations queue drained by the executor [VERIFIED: codebase read of `dispatcher.py` main loop].
- **Executor bridge.** The app-side dispatcher (`docker exec -i <app container> python -m hyprn_mvp_app.dispatcher --with-exports`) and the host executor (`deployment/dispatch_runtime.py --serve`) exchange one JSON line per call over stdio. The executor holds `executor.lock` (flock) and serves calls sequentially. The fixed method set is quoted from `dispatcher.py:50-51` [VERIFIED: Read]: `BRIDGE_ARITIES={'require_attestation':0,'bundle_runtime':0,'launch':2, 'matches':1,'inspect':1,'read_record':2,'resolve_results':1,'archive_record':1}`.
- **Run blocking.** `NativeExecution.launch` runs the calculation synchronously, quoted from `calculation.py:344-347` [VERIFIED: Read]: `metadata={'disable_cache': True, 'options': {'max_wallclock_seconds': 60}})` … `runner.run_get_node(process)`. **Every bridge call waits while a run executes.**
- **Capabilities.** `"documents"` is in `unavailable` [VERIFIED: codebase read `api.py:205-206`].
- **Signed cursors.** No server signing key exists. Approach "signed" values are content digests only (`approach.py:23-25` [VERIFIED: Read]). A signed document cursor needs a new server-side key or stateful cursor rows (see Open Question 8).

### UI today

- **Study tabs** are hard-coded in `Workspace.tsx`: `(['overview', 'model', 'configurations', 'runs', 'evidence'] as const)` [VERIFIED: codebase grep line 417]. `design-system/Layouts.md` and `Naming.md` "Fixed labels" list "Overview, Models, Configurations, Runs, Evidence"; `docs/specs/ui-target.md` §3.1 says the same. All three need "Documents" before Evidence (design-system change first).
- **Design components available** (`ui/src/design/index.ts`, read via cat): `Button, DataTable, Field, InferenceBlock, Ledger, ModelNode, Panel, Readout, RecordBar, SourceChip, StatusTag, Tabs, ActionIcon, CriterionRecord, TextInput, TextArea, Select, Checkbox, Disclosure, DialogFrame, SectionHeader, ActionDialog, DetailTabs, FilePicker, Progress, GraphCanvas, SourceSurface, formatNumber`.
- **Tokens that match §15.** `panel-outline` = `190px` and `panel-inspector` = `350px` already exist in `design-system/tokens.json` (programmatic read). Also usable: `search-width` 300px, `dialog-max` 760px, `trace` and `trace-soft` (provenance and "highlighted cited passage").

Reusable components per Documents screen:

| Need (§15) | Reuse | Missing (design-system work first) |
|---|---|---|
| Library list rows, versions, usage tables | `DataTable` (local scroll, selection), `Panel`, `StatusTag`, `SectionHeader`, `ActionDialog` (Record details) | Row-level actions inside `DataTable` ("Read source", "Download original") — verify `DataTable` supports interactive cells, else compose rows like `study-row` in `Workspace.tsx` |
| Collections panel (190 px) | `Panel` + quiet `Button`s in a list (pattern of the model "Components" panel) | Only a CSS layout class (library grid: `panel-outline` + fluid; stack at the narrow breakpoint), in `foundry.css` or screen CSS with tokens |
| Upload dialog with measured byte progress | `DialogFrame`/`ActionDialog`, `FilePicker` | **`Progress` is indeterminate only** ("Indeterminate progress only. No percentage is inferred"). It needs a measured variant ("N of M bytes", `<progress value max>` plus words), consistent with `Scientific-states.md` §Progress ("Use measured counts") |
| Reader: escaped text column, line and page gutter, selection, highlighted cited passage, labelled start/end fields | `TextInput`, `Select` (extraction attempt), `Button` | **No read-only text reader surface.** `SourceSurface` is a Python-highlighting editor overlay over a textarea, not a reader. Needs a new `TextReader` (escaped `pre`, line numbers, `trace-soft` highlight, selection to UTF-16 offsets, keyboard selection) |
| Citation chip in evidence and history | `SourceChip` ("opens the exact cited location … never a document's home page"), `RecordBar` (historical views) | — |
| Recovery banners ("Check what happened", "Saving the file…", stale edit) | `StatusTag` + text, `role="status"`/`alert` | A banner component is not exported. The README describes banners as `*-soft` ground; confirm whether one exists in `foundry.css` before adding it |

- **UI contract checker.** Today `ui/check_ui_contract.py` asserts source wiring strings and binds public routes to response types in the generated OpenAPI (`routes={ '/studies/{study_id}/result-sources':('get','ResultSourcePage'), … }`). Phase 1 task 1.6 replaces it with `ui/check_ui_contract.py` and the control-to-spec map `ui/control-map.json`, which "fails on any control without an existing spec test". New Documents routes and controls must be registered there, in the same task that adds them.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiida-core | 2.9.3 (pinned in the native inventory; probes refuse anything else: `version('aiida-core') != '2.9.3'`) | Originals, Groups, extras, `@calcfunction`, `StorageBackend.transaction()` | Already the native store; the collection protocol is qualified on it [VERIFIED: codebase read of `documents_native_fixture.py`] |
| pypdf | 6.20.0 (audited); **6.20.1 published 2026-10-12 with a security fix** | PDF text extraction inside the parser image only | Audited BSD-3-Clause, zero runtime dependencies on Python 3.12 [CITED: `integration/document-parser-provenance.md`]; PyPI wheel `pypdf-6.20.0-py3-none-any.whl` 401,710 bytes, SHA-256 `f003fc2014814d264fe7dd3f9d435c158e23e1a85a2233f87a0a2d6d21c914ad`, `vulnerabilities: []` [VERIFIED: PyPI JSON API this session] |
| Python standard library (`codecs` strict UTF-8, `hashlib`, `unicodedata` if needed) | CPython 3.12.11 (Phase 2 D-05) | `hyprn-mvp-utf8/1` text decoding, hashing, codepoint slicing | No dependency; spec mandates strict stdlib decoding |
| FastAPI / Starlette (existing) | fastapi 0.143.0 (`application/requirements.lock`) | Routes; raw-body chunk route via `Request.stream()` | Already the API framework [VERIFIED: grep of the lock] |
| SQLite (application store, existing) | system | Document families, versions, associations, operations, spool leases, search projection, evidence v4 | Single application store, single writer [CITED: architecture §8] |
| React + design system (existing) | per `ui/package-lock.json` | Documents tab, library, reader, citing | Mandated by AGENTS.md |
| Playwright (existing) | per lock | Browser groups, genuine 200 % zoom via the Chromium extension pattern in `ui/tests/foundry-zoom.spec.ts` | Existing evidence pattern |

### Supporting

| Library / artifact | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python base image for the parser | Phase 2's digest-pinned CPython 3.12 base (index and platform digests in `deployment/pins.json`, Phase 2 task 2.7) | Parser image base | Reuse the same pinned base; do not introduce a second Python base |
| Docker engine (existing) | 29.8.2 on the development host | Parser container, isolation flags | Steps 6–7 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bounded substring match over a projection table | SQLite FTS5 | FTS5 adds ranking and tokenization (out of scope §17: "No ranking"), tokenizer-dependent offsets and non-exact snippets. Reject |
| Host-side spool resolution beneath the app `/store` mount | Bytes inside the bridge frame (base64) | The `DocumentNativeStoreOriginal1` frame has only `transfer_id`; adding bytes widens the bridge contract. Host-side resolution keeps the contract and the 64 MiB frame bound |
| Separate read-loop process pair | Threads in the executor | AiiDA storage and session objects are not designed for cross-thread use [ASSUMED]; a separate process also gives a fixed identity, its own lock and a clean kill |

**Installation:** nothing goes into the application or native environments. The parser image installs the single audited wheel:

```
pip install --no-deps --no-index --require-hashes --only-binary=:all: -r <parser lock requirements file>
# The requirements file names exactly: pypdf==6.20.0 --hash=sha256:f003fc2014814d264fe7dd3f9d435c158e23e1a85a2233f87a0a2d6d21c914ad
# (or the 6.20.1 values after a fresh audit, Open Question 2)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pypdf (6.20.0 wheel) | PyPI | Project is long-established; this version was released 2026-10-09; latest 6.20.1 released 2026-10-12 | unknown (seam reported null) | github.com/py-pdf/pypdf | [SUS] (seam reasons: `too-new`, `unknown-downloads`, driven by today's 6.20.1 upload) | Flagged. The planner inserts a `checkpoint:human-verify` before the parser image first installs a wheel. This matches the provenance record's own rule ("the advisory check is repeated immediately before building") |

The seam check (`gsd-tools query package-legitimacy check --ecosystem pypi pypdf`) returned `"verdict": "SUS"`. The registry, size, SHA-256 and `yanked: false` of the 6.20.0 wheel match the audited record [VERIFIED: PyPI JSON]. The GitHub advisory query for `pypdf@6.20.0` returned no advisories this session [VERIFIED: api.github.com advisories query]. The 6.20.1 release notes list "**Security:** One fix prevents problems when handling cyclic trees (PR #4188)" with no GHSA identifier [CITED: github.com/py-pdf/pypdf/releases/tag/6.20.1].

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** pypdf. The planner adds a human-verify checkpoint before the first install and decides 6.20.0 versus 6.20.1 (Open Question 2).

No npm package is added. The UI needs no new dependency.

## Architecture Patterns

### System Architecture Diagram

```
Browser (Documents tab, reader, evidence citing)
   │  HTTPS/loopback, cookie + CSRF, JSON (chunk PUT: raw bytes ≤ 256 KiB)
   ▼
Application API (/api/1/studies/{sid}/…)  ── authorize(study) FIRST ──► not-found if foreign
   │                     │                           │
   │ library/search/     │ mutations                 │ reads that need native data
   │ evidence reads      ▼                           ▼
   │              application store txn:      read mailbox row (verb, input, study, request_id)
   │              operation + reserved IDs    ── wait bounded ──► reply row (≤ 5 min cache,
   │              + receipt (+ spool lease)                        reauthorized at delivery)
   ▼                     │                           ▲
search projection        │ queued operations         │
(app store, rebuildable) ▼                           │
                 App-side dispatcher loop        App-side read loop (docker exec, read verbs only)
                 (existing, + documents queue)       │ stdio frames (DocumentBridgeRead1)
                         │ stdio frames               ▼
                         ▼ (DocumentBridgeWrite1) Host read process (own lock, NativeDocuments
                 Host executor (single writer,      read-only verbs; ends when executor exits)
                 executor.lock)                       │
                   │        │                         ▼
                   │        └─ launch (blocks) ──► attested worker container
                   ▼                                 AiiDA profile (SQLite + disk-objectstore)
                 NativeDocuments write verbs ───────► (originals, Groups, extras, witnesses,
                   │  extraction_start                 calcfunction nodes, text FolderData, manifest Dict)
                   ▼
                 @calcfunction ──docker run──► parser container (pinned image, --network none,
                                                read-only, non-root, 1 CPU / 512 MiB / 64 PIDs /
                                                64 MiB scratch, 30 s external wall clock)
   Spool: app container writes beneath its /store mount; host writer resolves transfer_id there
   (server-derived, scoped, O_NOFOLLOW, exact size + SHA-256), deletes after publication/expiry.
```

### Recommended Project Structure (final names)

```
integration/src/hyprn_mvp_integration/
├── documents.py            # NativeDocuments: originals (existing) + collections, annotations, reads, reconcile
├── document_extraction.py  # @calcfunction wrapper, manifest/text folder builders, outcome mapping
├── document_parser.py      # stdlib + pypdf entry run INSIDE the parser image (copied in, like worker.py)
└── document_parser_launch.py # docker run flags, limits, descendant cleanup, parser containment canaries
application/src/hyprn_mvp_app/
├── documents.py            # families, versions, associations, operations, spool leases, upload protocol
├── document_search.py      # projection build/rebuild, bounded matching, coverage, signed cursors
├── document_citations.py   # locator validation, UTF-16→codepoint, resolver, DocumentCitation1 freezing
└── document_bridge.py      # app side: closed verb frames, write queue drain, read mailbox loop
deployment/
├── images/parser.Dockerfile           # Phase 2 image conventions
├── locks/ (or integration/document-parser.lock.json, Phase 1 1.8)  # wheel identity
└── document_reads_runtime.py (or a mode of dispatch_runtime.py) # host read process, supervised
ui/src/
├── Documents*.tsx (library, collections, upload dialog, reader, annotations side column)
└── design/ (TextReader, measured Progress variant; design-system notes first)
```

Module placement must respect the acyclic graph (architecture §7). Recommended:

- `documents` → `contracts`, `store`.
- `document_citations` → `contracts`, `store`, `documents`.
- `document_search` → `contracts`, `store`, `documents`.
- `api` → all of the above.
- `configuration`, `execution_bundle` and `history` gain citation handling only through pure functions owned by `document_citations` or `contracts`.
- **Never** let `execution_bundle` (attested and pure) import storage-touching modules.

Add the new modules to `application/tests/test_module_boundaries.py` in the same task.

### Pattern 1: Single-writer document operations queue (drained by the existing executor loop)

**What:** A mutation route runs one application transaction: authorize, look up the receipt, reserve IDs, insert a `document_operations` row in `queued` (uploads go `receiving → queued`), then return 202 with `DocumentOperation1`. The existing dispatcher serve loop (which already drains `outbox` and computational-record requests) also drains queued document operations and calls `document-write` verbs over the bridge. The host side runs them on `NativeDocuments` inside `backend.transaction()`, witness first. The app side publishes in a second application transaction after an exact readback proof.

**When to use:** every native write (store_original, collection_*, annotation_*, extraction_start).

**Key rules:**

- Look up the witness before compare-and-set or visibility. `uncertain` is never retried.
- `waiting_for_native_storage: true` while the executor is busy (a run holds it).
- A timeout is never proof.

**Example** (shape only; the frames already exist as `DocumentBridgeWrite1`):

```python
# Source: contracts/documents.md "Fixed bridge"; documents.py store_original() pattern
frame = {"mode": "document-write", "verb": "collection_members",
         "identity": {"study_id": sid, "actor_id": actor, "command_id": cmd,
                      "operation_id": op, "payload_sha256": digest(payload)},
         "input": {"collection_id": cid, "request": body}}
validate("DocumentBridgeWrite1", frame)   # closed schema before any I/O
```

### Pattern 2: Supervised read loop (D-09)

**What:** a second process pair started and owned by the executor's `--serve`:

- **Host side:** a read process with a fixed identity, its own lock file and a `NativeDocuments` instance. It admits only `descriptor, list, member, annotation, fragment, original, status` and refuses any write or scientific method before I/O.
- **App side:** a mailbox drainer (`docker exec -i … python -m hyprn_mvp_app.document_bridge --reads`) that reads `document_read_requests` rows, sends `DocumentBridgeRead1` frames and writes `DocumentBridgeReadReply1` replies.

The executor closes the read loop's stdin and kills its process group when it exits (the same "detect owner exit" pattern as `dispatcher.py`: `select.select([sys.stdin],[],[],1)`).

**Measured property:** while a deliberately blocked run holds the writer, reads complete. The test records the timeline: block start, each read's start and end, block release. It requires every read to end before release, within a bound such as ≤ 2 s per read on the fixture; the planner sets the bound and the measured-artifact validator enforces it.

### Pattern 3: Logical terminal collection deletion (port of the qualified probe)

```python
# Source: deployment/tests/documents_native_fixture.py CollectionProtocolProbe.mutate (qualified)
with backend.transaction():
    prior = lookup_witness(command)            # BEFORE active filter and CAS
    if prior: return prior                      # exact historical outcome
    state = validate_state(group_uuid)          # fail closed on malformed lifecycle/witness
    if state["lifecycle"] == "deleted": raise not_found
    if state["revision"] != command["expected_revision"]: raise stale_revision
    group.remove_nodes(list(group.nodes))       # never Group delete, never clear()
    extras.update(lifecycle="deleted", revision=rev + 1, deletion={command_id, payload_digest})
    store_witness(...)                          # same transaction
```

### Pattern 4: Exact span and quotation

The browser sends UTF-16 start and end offsets. The server converts them to codepoint indices over the exact artifact text (`DocumentFragment1.positions` is `"unicode_codepoints"`) and checks `0 ≤ start < end ≤ len`. It slices the native artifact text (from the read loop, never from the projection), encodes it as UTF-8, hashes it and freezes it. The browser's quote is ignored.

### Anti-Patterns to Avoid

- **Group deletion or `group.clear()`.** Both are proven unsafe on the pinned AiiDA version (the probe hazard controls `clear` and `delete`).
- **Membership or text in the application.** No application membership table; no serving of projection text as the authoritative text.
- **Widening the middleware.** Accepting non-JSON bodies on more than the one chunk route.
- **Importing a document module from an attested module.**
- **Running the parser in the host executor's process**, or with arguments only. Containment must be measured with canaries, like `launcher.attest()`.
- **Blind retry.** Retrying a write after a timeout or a missing reply.
- **Placeholders.** Showing a Documents panel or a disabled future control before its capability works.

## Step Map (§12 steps 1–13): files, tests, dependencies, parallelism

Group names follow the runner rule quoted from `deployment/checks.py:162-164` [VERIFIED: Read]: "Python targets select the functions named test_<group with underscores>_*; browser targets carry the @<group> tag". Each group is registered in `DOCUMENTS_ROUTES` with a mode. The existing modes are `'native'` (docker need, AiiDA allowed), `'application/contracts'` (contract interpreter, no native imports) and `'browser'` (browser need). All proposed groups are `must-pass` unless noted. The table uses final names.

| # | Step | Files likely touched | New groups (mode; needs) | Depends on | Parallel with Phase 2 / 3? |
|---|---|---|---|---|---|
| 1 | Native collections and working annotations | `integration/src/hyprn_mvp_integration/documents.py`; new `integration/tests/test_documents_collections.py`, `test_documents_annotations.py`; `deployment/tests/documents_native_fixture.py` (shared probe helpers only); `deployment/checks.py` (registry entries) | `documents-collections` (native; docker), `documents-annotations` (native; docker). Measured kill and replay artifacts like `documents-collection-protocol` | Phase 1 complete | Yes: disjoint from Phase 2 (`deployment/` managers) and Phase 3 (`application/` agent modules), except the `checks.py` registry edit (serialize) |
| 2 | Bridge verbs; managed read loop | new `application/src/hyprn_mvp_app/document_bridge.py`; `dispatcher.py` (drain the document queue); host read process (new `deployment/document_reads_runtime.py` or a mode of `deployment/dispatch_runtime.py`); `deployment/dispatch_runtime.py` (start and supervise); store tables for operations and read mailbox | `documents-bridge` (application/contracts: closed verb set, frame bounds, refusal before I/O); `documents-read-loop` (native; docker: measured blocked-run timeline, shutdown with the supervisor, read mode cannot launch) | 1 | **Conflicts with Phase 2 tasks 2.3 (execution side from the installation) and 2.8 (`release_binding` → `release.py`, importers in the managers).** Put the read-loop core in new files; run the small `dispatch_runtime.py` hook task after Phase 2 2.8 or serialize it |
| 3 | Upload and library API | new `hyprn_mvp_app/documents.py`; `store.py` (additive tables); `api.py` (routes, chunk-route body exemption); `application/generate_contract.py` → `contracts/hyprn-mvp.openapi.yaml` → `ui/src/contract.ts` (regenerate); `application/tests/test_module_boundaries.py` | `documents-upload-api` (native; docker: chunk protocol, restart, recovery states), `documents-library-api` (native), `documents-access` (native: foreign or unknown IDs, cursors, caches, non-disclosing errors) | 2 | **Shared files with Phase 3** (`api.py`, OpenAPI, `contract.ts`): one task at a time |
| 4 | Library UI | design-system first: `design-system/Layouts.md` (Documents section; study tabs), `Naming.md` (fixed labels, reader-facing names), `components/Progress.md` (measured) and the `ui/src/design` implementation; then `ui/src/Documents*.tsx`, `ui/src/Workspace.tsx` (tab), `ui/src/api.ts`; `deployment/tests/documents_ui_fixture.py` (`start_isolated_api`); `ui/tests/documents-library.spec.ts`; `ui/control-map.json` | `documents-library-ui` (browser + native backend; see the interpreter pitfall) | 3 | Study shell (`Workspace.tsx`) shared with the Phase 3 proposals page: serialize |
| 5 | Collections API and UI | `api.py`, `hyprn_mvp_app/documents.py`, OpenAPI regeneration, `ui/src/DocumentCollections.tsx`, spec | `documents-collections-api` (native), `documents-collections-ui` (browser) | 1, 3, 4; **Open Question 3 ("replace" semantics)** | Serialize shared files |
| 6 | Parser image | new `deployment/images/parser.Dockerfile`; `integration/src/hyprn_mvp_integration/document_parser.py` (in-image entry), `document_parser_launch.py` (flags, canaries); `integration/document-parser.lock.json` (exists after 1.8); parser cache below the data root; `deployment/pins.json` (base digest); notice bundle; `docs/legal/licensing.md` (status "planned" → "adopted") | `documents-parser-image` (native or a new container mode; docker: build verifies wheel bytes, refuses a mismatch, offline build), `documents-parser-containment` (docker: measured canaries) | Phase 2 task 2.7 (image conventions); **Open Question 2** | Parallel with steps 3–5 (disjoint files) after Phase 2 2.7; serialize `checks.py` and `pins.json` |
| 7 | Extraction | `document_extraction.py` (calcfunction), `documents.py` (extraction_start, status, fragment), app routes `document-versions/{id}/extractions`, `document-extractions/{id}[/result|/retry]` | `documents-extraction` (native; docker: complete, partial, truncated, unsupported (encrypted), needs_transcription (image-only), interrupted (writer killed), repeatable locators and hashes) | 2, 3, 6 | Serialize `api.py` |
| 8 | Processing provenance; search | `document_search.py`, `store.py` (projection tables), `GET document-search` | `documents-extraction-provenance` (native: real input and output links, node types), `documents-search` (native or application: exact snippets, coverage counts, deleted-collection filter not found, cursor binding) | 7 | Serialize `api.py` |
| 9 | Reader and search UI | design-system `TextReader`; `ui/src/DocumentReader.tsx`; specs | `documents-reader-ui` (browser) | 4, 8 | Serialize the study shell |
| 10 | Annotations, citation resolver, evidence v4 | `document_citations.py`; `store.py` (EvidenceRecord4 storage, source reservations table); `api.py` (annotation routes, `document-citations/preview`, `evidence-citations/preview`, evidence create and revise accept EvidenceCreate4/Revise4) | `documents-citations` (native: resolver verifies bytes and text, UTF-16 conversion, duplicates, 20-citation bound), `documents-evidence-v4` (application: commit barrier, annotation edits never change stored evidence) | 1, 3, 7 (span citations), 8 | **Phase 3 evidence tools** use the same evidence routes; keep EvidenceCreate1–3 admitted |
| 11 | Configuration chain | `configuration.py`, `scientific_configuration.py`, `execution_bundle.py`, `approach.py`, `approach_closure.py`, `history.py`, `modified_runs.py`, `result_bindings.py`, `modeling.py`; integration `results.py`, `calculation.py`, `worker.py`, `launcher.py` (**attested set** → re-attestation, two-sided coverage test); `contracts/modeling.openapi.yaml`; new `upstream/whatsopt-patches/100-…patch`; modeling image; generated OpenAPI and TS | `documents-configuration-chain` (application), `documents-bundle-admission` (native: worker re-admission of Bundle7/next), `documents-modeling-private` (docker: modeling image admits private 4) | 10; **Open Question 1 (Model4 chain)**; Phase 2 2.6 (modeling image from patches), 2.8 (release binding) | Not parallel with Phase 2 2.6–2.8; large; split into several tasks |
| 12 | Frozen history | `history.py`, `modified_runs.py`, read-loop availability states, `RunPanel.tsx` | `documents-frozen-history` (native: modeling service stopped; native read loop stopped → descriptors and quotations still display, bytes "unavailable") | 11 | Serialize |
| 13 | Scientific evidence UI | `EvidencePanel.tsx`, `EvidencePicker.tsx`, `EvidenceView.tsx`, `Assumptions.tsx`, `ConfigurationPanel.tsx`, `ApproachAssumptions.tsx`, `RunPanel.tsx`, `EvidenceIndex.tsx`, `recordViews.ts` | `documents-evidence-ui` (browser: all five §15.4 paths), `documents-ui-zoom` (browser: genuine 200 % zoom across every Documents screen, light and dark) | 10, 12 | Serialize the study shell and evidence screens |

## Parser Image (step 6) — conventions and "containment demonstrated"

**Phase 2 conventions (task 2.7)** [CITED: 02-PLAN.md]:

- Images are built in `deployment/images/*.Dockerfile` from digest-pinned bases, recording both the index digest and the resolved platform digest for arm64 and amd64.
- Locks are installed with `--require-hashes`.
- A recorded build identity replaces fixed image IDs, and image tags follow `hyprn-mvp-<role>:<build-input-digest16>` (01-PLAN.md 1.5).
- Non-acquisition builds run without network.
- Acquisition caches verified bytes under the data root, 0400, verified at fetch and at every read (the same pattern as the WhatsOpt archive in `cache/upstream/whatsopt/<sha256>/`).

**Wheel acquisition (PD-4.7):**

1. Fetch the exact filename from the index into `<data root>/cache/parser/<sha256>/`.
2. Verify size `401710` and the SHA-256 against `integration/document-parser.lock.json`. Refuse a symlinked cache, a group-readable file or a mismatch.
3. Copy the wheel into a scratch build context.
4. `docker build --network none` installs it with `--no-deps --no-index --require-hashes`.
5. The build re-hashes the wheel inside the image and fails on mismatch.
6. Record the image digest, the configuration digest and the notice bundle (the BSD-3-Clause LICENSE with SHA-256 `a97ac230e5f33ef10a5367a850eb01f91f1a0b064e34742c7794d2294557f524` plus the Adobe, Unicode and contributor notices listed in the provenance record).

**Launch flags.** Model them on `launcher.isolated()`, quoted from `launcher.py:267-272` [VERIFIED: Read]: `'--network','none', '--user',POLICY['user'],'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges', '--memory',POLICY['memory'],'--memory-swap',POLICY['memory'],'--cpus',POLICY['cpus'],'--pids-limit',POLICY['pids']`, `--tmpfs` scratch, input bind `readonly`. Parser values per §11: `--cpus 1`, `--memory 512m --memory-swap 512m`, `--pids-limit 64`, tmpfs scratch `size=64m`, an output cap, a 30 s external wall clock and a fixed command.

Put the parser policy in a reviewed configuration file (D-07), not in code literals. Phase 2 says worker policy and limits are never in the installation configuration ("Never in the configuration: secrets, worker policy or limits, image ids"), so the reviewed parser policy belongs in a tracked policy file next to the existing worker policy, hashed into the parser's configuration digest.

**"Containment demonstrated"** means canary runs on the adopted image, recorded as parser containment evidence, with extraction refused while that evidence is absent or stale (the same structure as `launcher.attest()`). Required cases per spec §7 and the provenance record:

- non-root;
- read-only root and input (write denied);
- network denied;
- no Docker socket, home, secrets or `AIIDA_*` variables;
- memory limit enforced (OOM kill);
- PID limit;
- CPU quota;
- scratch bound (64 MiB);
- output bound;
- 30 s wall clock with descendant cleanup;
- **cleanup when the supervising process exits** (kill the host writer during a parser run, then show that no labelled parser container survives after the executor restarts);
- refusal of an invalid image digest or configuration digest.

Note that the Docker CLI process dying does not stop the container. Cleanup must label parser containers and reap them by label at writer start and in a `finally` block [ASSUMED: standard Docker behaviour; verify in the canary test].

## Upload Chunk Protocol, Spool and Limits (step 3)

- **Protocol** [CITED: contracts/documents.md "Byte transfer and publication"]:
  - Begin reserves the command, document and version IDs, the expected metadata and a lease.
  - `PUT …/chunks/{offset}` takes a raw body ≤ 262,144 bytes plus `byte_length` and a SHA-256 header (`DocumentUploadChunk1`: `offset` 0..10485760, `byte_length` 1..262144, `sha256`).
  - An identical retry at the same offset is idempotent. A gap, an overlap mismatch, changed bytes or excess bytes fail without effect, with or without `Content-Length`.
  - Complete requires the contiguous exact length and full SHA-256.
  - An empty admitted text completes with no chunk.
- **Middleware change.**
  - Exempt exactly one method and path pattern from the JSON-only rule.
  - Cap that route at 262,144 bytes while streaming.
  - Keep the origin, session and CSRF checks.
  - The Content-Type must be `application/octet-stream`.
  - A test asserts every other route still refuses non-JSON bodies.
- **Spool location.** Beneath the application container's existing `/store` bind mount, quoted from `application_runtime.py:85` [VERIFIED: Read]: `expected={"/store":(str(ROOT/"application"),True),"/run/model.key":(…,False)}`. The app container's `/tmp` is a 16 MiB tmpfs [VERIFIED: Read `application_runtime.py:256`], too small for 100 MiB of staged bytes per study. A dedicated folder under the `/store` mount (for example `document-spool/<study_id>/<upload_id>`) avoids changing the mount set, which Phase 2 task 2.4 owns.
  - Files are created `O_NOFOLLOW`, 0600, with server-derived names only.
  - Leases expire after 24 h.
  - The spool is deleted after publication or expiry.
  - The host writer resolves `transfer_id` to that exact file and checks length and hash. `NativeDocuments.store_original` already re-verifies.
- **Quotas.** 4 incomplete uploads and 100 MiB staged per study are runtime checks in the begin transaction.
- **Limits in reviewed configuration (D-07).** The registry `limits` object already carries every value (for example `"original_bytes": 10485760, "chunk_bytes": 262144, "pdf_pages": 500, …` [CITED: programmatic extract]). Recommend one tracked application limits module or file whose values a test asserts equal to the registry, so code and contract cannot drift.
- **Recovery states visible in the library** (`DocumentUploadStatus1.state` enum: `receiving, queued, running, committed, published, failed, expired, interrupted, uncertain` [CITED: programmatic extract]). Failure reasons include `reupload_required` for a lost spool with no native commit.

## Search Projection (step 8)

- **Location.** Application store tables keyed by `(study_id, version_id, extraction_id, artifact_id, artifact_sha256)`. Each row holds per-page text and a folded copy. The projection is rebuilt from native artifacts through the read loop and verified against the manifest's page hashes at index time.
- **Never authoritative.** Fragments, quotations and citation slices always come from native artifacts (read-loop `fragment` verb). The projection only finds candidate positions.
- **Matching.**
  - Bounded substring match (query ≤ 256 codepoints, snippet ≤ 512, page size ≤ 100 rows). No ranking.
  - For case-insensitive matching, use a per-codepoint fold that preserves length: map a codepoint to `c.lower()` only when the result is one codepoint, else keep it. Offsets in the folded text then equal offsets in the original text and snippets stay exact.
  - Full `str.casefold()` changes lengths (for example `ß`→`ss`) and would corrupt locators [ASSUMED: Python semantics, well known; confirm with a unit test].
- **Coverage honesty.** `DocumentSearchResult1` requires `indexed_versions`, `unindexed_versions` and `coverage` (`complete | partial | unavailable`). Unextracted, failed and partial versions are counted. An empty result means "no match in the searched material".
- **Collection filter.** Membership is native, so a collection filter asks the read loop for active member version IDs (active filter at the native query boundary). A deleted or foreign collection is not found and never broadens the search.
- **Cursors.** Opaque, bound to scope, query, filters and projection revision, re-authorized per page. See Open Question 8 for the signing key.

## UI: §15 versus Layouts.md, contract checker, browser conventions

- **Layout.**
  - Library: `[collections Panel panel-outline 190px] [fluid list]`, stacked below the narrow breakpoint.
  - Reader: `[fluid text column] [side column panel-inspector 350px]`, stacked at narrow width or zoom.
  - Both reuse existing tokens, but `Layouts.md` has no Documents section and its study tabs exclude Documents. **Add a Documents section to `Layouts.md` and update `Naming.md` (fixed labels; reader-facing names such as "Annotations", "Read source", "Download original", "Upload documents") before UI code**. The UI-phase gate is enabled in config (`ui_phase: true`, `ui_safety_gate: true`), so the planner should schedule `/gsd-ui-phase` (UI-SPEC) before step 4.
- **Copy conflicts with Naming.md.**
  - Naming.md plain-language rule 1 bans "recorded" as an adjective for stored content in reader text, while §15.4's key copy is "Recorded note — later edits and reprocessing do not change this citation".
  - §15.2 says rows show the "exact version", but "exact" is banned in reader text.

  Both must be resolved in `Naming.md` with the UI change (Open Question 6).
- **Contract checker.** After 1.6, `ui/check_ui_contract.py` with `ui/control-map.json` maps every control to an existing spec test. Each Documents UI task registers its controls and the routes it calls. Each API task regenerates OpenAPI (`application/generate_contract.py`) and TS types (`ui/generate_types.py`) and never hand-edits them.
- **Browser fixture.** The `documents_ui_fixture.py` placeholder raises `'Documents isolated API/native/browser capability unavailable: '`. Implement `start_isolated_api` on the `ae_ui_fixture` pattern ("Serves actual Workspace/client/API/Auth/Store on an ephemeral guarded socket"), plus a scratch AiiDA profile (`scoped_fixture.create_native_fixture`), an in-process writer and read loop (the `run_export_dispatcher` pattern), and a declared modeling double.
- **Interpreter pitfall.** `documents_interpreter()` returns the contract interpreter for non-native modes, and `guarded_scope()` uses `guard.APPROVED_CONTRACT_PYTHON`. A native-backed browser fixture needs the native interpreter and both `docker` and `browser` needs. Add a mode (for example `'browser-native'`) to `DOCUMENTS_ROUTES`, `DOCKER_GROUPS` and `BROWSER_GROUPS`.
- **Evidence.**
  - Light and dark, keyboard and genuine 200 % zoom use the `foundry-zoom.spec.ts` pattern (Chromium extension plus `chrome.tabs` zoom at a native 1440 × 1000 window, not viewport emulation).
  - Screenshots go to `HYPRN_MVP_UI_EVIDENCE_ROOT` (outside the repository).
  - The checkpoint records automated evidence separately from the product-owner walk-through (D-10).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Collection deletion atomicity | New delete logic, `Group.clear()`, physical delete | Port the qualified `CollectionProtocolProbe.mutate/validate_state/active_ids` protocol | Already proven: crash and kill at four boundaries, 13 integrity faults, 10,000 members |
| Original storage and readback | A new store path | Existing `NativeDocuments.store_original`/`reconcile`/`read` | Qualified with SIGKILL before and after commit |
| Wire validation | Hand-written field checks for public shapes | `contracts.validate("<$defs name>", value)` against the shared schemas | 119 closed definitions exist; the generator already emits them |
| PDF parsing | Custom PDF or stream decoding | `pypdf` (audited pin) inside the parser image | Supply-chain-audited; decompression bombs are bounded externally |
| Isolation | Resource limits inside Python | Docker flags + canary attestation (`launcher.attest()` pattern) | Containment must be measured, not inferred |
| Canonical digests | `json.dumps` variants | `contracts.canonical`/`digest` (RFC 8785) | The golden identity corpus pins canonical bytes |
| Command receipts and recovery | Ad hoc retry | `receipts` table + native witness lookup (state machine in `operation_transitions`) | Uncertain must never be retried |
| 200 % zoom evidence | CSS zoom or viewport scaling | `foundry-zoom.spec.ts` Chromium extension approach | "Genuine" zoom is the acceptance criterion |
| Text highlighting in the reader | `dangerouslySetInnerHTML` or a Markdown renderer | Escaped React text nodes; `trace-soft` highlight via token classes | Active content threat; the reader never renders uploads |

**Key insight:** almost every hard problem in this phase (atomic native effects, replay, closed shapes, isolation proof) already has a qualified pattern in the tree. The risk lies in wiring and concurrency, not in algorithms.

## Common Pitfalls

### Pitfall 1: The allocated chain does not reach Model4

**What goes wrong:** step 11 implements Configuration5 → Frozen6 → Bundle7 as allocated, but current models are Model4 or carry closure 3, which freeze as Frozen7 and Bundle8. Citations then cannot reach current configurations.
**Why it happens:** the documents allocation predates the Model4 "polish envelope".
**How to avoid:** get a product decision and a contract amendment before step 11 (Open Question 1).
**Warning signs:** any Model4 configuration preview with citation candidates is refused, or code "widens" Frozen7.

### Pitfall 2: The middleware swallows the chunk body

**What goes wrong:** the global middleware reads up to 2 MiB and refuses non-JSON bodies.
**How to avoid:** add a route-exact exemption with a 256 KiB cap, and test that every other route still refuses.

### Pitfall 3: Reads freeze during runs

**What goes wrong:** reads go through the existing executor bridge, which blocks for the whole `launch`.
**How to avoid:** use a separate read-loop process pair; measure it against a deliberately blocked run.

### Pitfall 4: SQLite lock contention between the writer and the read loop on the AiiDA profile

**What goes wrong:** the AiiDA SQLite storage helper sets `PRAGMA case_sensitive_like` and `foreign_keys` but no `journal_mode` or busy timeout. This was observed in aiida-core v2.7.0 [CITED: raw.githubusercontent.com/aiidateam/aiida-core/v2.7.0/src/aiida/storage/sqlite_zip/utils.py]; 2.9.3 is unverified [ASSUMED same]. In rollback-journal mode, readers are blocked during a commit and can starve the writer.
**How to avoid:** keep read transactions short, use bounded busy retries in the read process, and measure under a blocked run.
**Warning signs:** `database is locked` in the read loop or writer logs.

### Pitfall 5: Extras are mutable and unprotected

**What goes wrong:** Group metadata and annotations live in AiiDA extras, which stay writable after store and carry no provenance.
**How to avoid:** integrity rests on witnesses and on validation that fails closed (the `validate_state` pattern). Never treat extras as grants.

### Pitfall 6: The collection revision baseline

**What goes wrong:** the probe uses revision 0, but the contract requires ≥ 1.
**How to avoid:** create at revision 1, and test the shapes against `DocumentCollection1`.

### Pitfall 7: Attested-set drift

**What goes wrong:** step 11 edits `launcher.py`, `calculation.py`, `results.py`, `worker.py` and pure application modules. That changes `execution_source_hashes()`, the release manifest and the attestation.
**How to avoid:** isolate step 11 in tasks that recompute pins and re-attest, after Phase 2 2.8.

### Pitfall 8: The interpreter and mode for native-backed browser groups

**What goes wrong:** browser mode uses the contract interpreter.
**How to avoid:** add a mode with the native interpreter and both needs. STATE.md also notes "Documents groups refuse a parent other than the native development interpreter", so run them with `"$HYPRN_MVP_NATIVE_PYTHON" -B deployment/checks.py --group …` until Phase 2's `./hyprn-mvp dev check`.

### Pitfall 9: Parser containers survive a writer crash

**What goes wrong:** killing the host writer leaves the container running.
**How to avoid:** label the container, reap it at start, and add a canary case for it.

### Pitfall 10: Codepoint versus UTF-16 versus bytes

**What goes wrong:** JavaScript string offsets are UTF-16; spans are codepoints; limits are bytes.
**How to avoid:** convert on the server, and test with astral characters (emoji, mathematical symbols) and combining marks.

### Pitfall 11: Projection text served as authority

**What goes wrong:** snippets or quotations are taken from the projection.
**How to avoid:** quotations always come from the native artifact via the read loop; snippets come from verified projection text with an artifact hash.

### Pitfall 12: Overlap with Phase 3 evidence tools

**What goes wrong:** Phase 3 agent evidence tools use the evidence routes; step 10 changes them.
**How to avoid:** keep EvidenceCreate1–3 and EvidenceRevise3 admitted, add 4 explicitly, and serialize the `api.py` and `store.py` tasks.

## Code Examples

### Route-exact raw-body exemption (sketch)

```python
# Source: application/src/hyprn_mvp_app/api.py boundaries middleware (existing JSON-only rule)
CHUNK_ROUTE = re.compile(r'^/api/1/studies/[0-9a-f-]{36}/document-uploads/[0-9a-f-]{36}/chunks/(0|[1-9][0-9]{0,7})$')
raw_ok = request.method == "PUT" and CHUNK_ROUTE.fullmatch(request.url.path)
limit = 262_144 if raw_ok else 2 * 1024 * 1024
# stream with `limit`; if raw_ok require content-type application/octet-stream and skip JSON parsing
```

### Codepoint conversion and server quotation (sketch)

```python
def utf16_to_codepoint(text: str, utf16_offset: int) -> int:
    units = 0
    for i, ch in enumerate(text):
        if units == utf16_offset: return i
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > utf16_offset: raise ValueError("offset inside a surrogate pair")
    if units == utf16_offset: return len(text)
    raise ValueError("offset out of range")

quote = artifact_text[start:end]                      # artifact bytes from the read loop
quote_sha256 = hashlib.sha256(quote.encode("utf-8")).hexdigest()
```

### Calcfunction shape (sketch; verify against aiida-core 2.9.3 docs)

```python
from aiida.engine import calcfunction
from aiida import orm

@calcfunction
def extract_document(original: orm.SinglefileData, configuration: orm.Dict):
    # runs in the host writer; launches the parser container with fixed flags
    manifest, text_folder = run_parser_and_collect(original, configuration)
    return {"manifest": manifest, "text": text_folder}   # real CREATE links; outcome lives in the manifest
```

[ASSUMED: dict return of multiple outputs from a calcfunction is supported. It is standard AiiDA, but confirm on 2.9.3 in the first extraction task.]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Physical Group deletion | Logical terminal deletion with a witness | Qualified before this phase | Never call `Group` delete or `clear()` |
| Document chain allocated over Model2 and Model3 (Frozen6/Bundle7) | Product now writes Model4 / closure 3 → Frozen7/Bundle8/History6/Seed6 | After the documents allocation (single import commit; date not recoverable) | Re-allocation needed (Open Question 1) |
| pypdf 6.20.0 (audited) | pypdf 6.20.1 with a security fix (cyclic trees) | 2026-10-12 | Re-audit decision before the image build |

**Deprecated/outdated:**

- `test_documents_planning_gates.py`: its JSON block expects absolute evidence paths. It is replaced by the lock-based adoption test in Phase 1 task 1.8.
- The `documents_ui_fixture.py` stub: replaced in step 4.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 1 renames the native metadata namespace to `hyprn_mvp_documents` and the registry key to `x-hyprn-mvp-documents-contract` | Rename map | Low: the executor uses whatever 1.4 lands; check after 1.4 |
| A2 | AiiDA storage objects should not be shared across threads, so the read loop is a separate process | Alternatives | Low: a separate process is safer either way |
| A3 | aiida-core 2.9.3 SQLite storage sets no WAL and no busy timeout (seen in 2.7.0) | Pitfall 4 | Medium: read-loop latency and lock errors; measured in `documents-read-loop` |
| A4 | Killing the docker CLI does not stop the container | Parser image | Medium: orphaned parser containers; canary test |
| A5 | A calcfunction may return a dict of several outputs on 2.9.3 | Code Examples | Medium: extraction design; verify in step 7 task 1 |
| A6 | Length-preserving per-codepoint lowercase folding is acceptable "bounded string matching" | Search | Low: product may want accent or casefold behaviour; a decision for the UI-SPEC |
| A7 | The read-loop API waits a bounded time and then returns `backend_unavailable` (reads are side-effect free) | Pattern 2 | Low: UX choice; planner's discretion |
| A8 | The spool beneath the app `/store` mount is acceptable under "no writable directory shared by all components" (shared by the app as writer and the executor as reader only) | Upload | Medium: if rejected, a dedicated mount must be added to `application_runtime.py` after Phase 2 2.4 |

## Open Questions

Each question carries its disposition from planning (`04-PLAN.md`). DEFERRED means the product owner decides, the answer is recorded in `04-CONTEXT.md` as the decision named, and only the tasks named wait for it. The plan's OQ-1 to OQ-4 are questions 1 to 4 below; the plan's OQ-5 (D-17, recent uploads after a reload, task 4.32) comes from `04-UI-SPEC.md` Q4, not from question 5 below.

1. **Document-bearing chain versus the Model4 / closure-3 chain (NEEDS PRODUCT OWNER; blocks steps 11–13 for current models).**
   - **Status: DEFERRED to the product owner** as plan OQ-1, answer recorded as **D-13**; decision checkpoint task 4.3; tasks 4.34–4.39 wait for it (blocked lane in `04-PLAN.md`).
   - What we know: the allocated chain covers Model2 and Model3 (Configuration5 → Frozen6 → Bundle7 → History5 → Seed5, closure 2). The application now writes Configuration4 for Model3 and Model4, and Frozen7, Bundle8, History6, Seed6 and closure 3 for Model4 or closure 3. §18 Q8's default "implement the allocated chain as specified" no longer covers current authoring.
   - What's unclear: whether to allocate a new document-bearing chain over the current one (for example Configuration5 pairing with Model4 → Frozen8, Bundle9, History7, Seed7, closure 4; numbers are illustrative), or restrict citations to Model2/3 (which conflicts with "authoring admits only current formats").
   - Recommendation: amend `contracts/documents.md` and the schemas in a contract-only task before step 11. This needs product-owner approval because D-06 says "as allocated". **RISKY: conflicts with D-06 and §18 Q8 as written.**
2. **pypdf 6.20.0 versus 6.20.1 (NEEDS PRODUCT OWNER; blocks step 6 install).**
   - **Status: DEFERRED to the product owner** as plan OQ-2, answer recorded as **D-14**; decision checkpoint task 4.2; tasks 4.6, 4.11, 4.15, 4.18, 4.21 and 4.24–4.30 wait for it.
   - What we know: 6.20.1 (2026-10-12) contains a security fix for cyclic trees, with no GHSA yet. 6.20.0 still shows no PyPI vulnerabilities. Containment (30 s, 512 MiB) bounds denial of service.
   - Recommendation: re-audit 6.20.1 (same evidence set: registry, wheel RECORD, tag correspondence, notices, advisories), update the lock and provenance through the Phase 1 1.8 adoption test, and bump D-05. The alternative is to keep 6.20.0 with a recorded accepted risk. **RISKY either way: D-05 names 6.20.0.**
3. **Meaning of the `replace` member action (NEEDS PRODUCT OWNER or contract clarification; blocks step 5 API).**
   - **Status: DEFERRED to the product owner** as plan OQ-3, answer recorded as **D-15**; task 4.31 waits for it. Until then `replace` is refused before any effect (task 4.14); add and remove ship in 4.7, 4.14 and 4.16.
   - `DocumentCollectionMembersChange1` has `action: add|remove|replace` with one `version_ids` list (≤ 100). §15.2 says "replace a member version explicitly", which reads as a swap of one family's version for another.
   - Recommendation: define "replace" as: for each listed version, remove any active member of the same family and add the listed version, in one revision-checked batch. Record this in `contracts/documents.md` (wording only, no schema change).
4. **PD-4.3 conflicts with existing study-archive semantics (NEEDS PRODUCT OWNER).**
   - **Status: DEFERRED to the product owner** as plan OQ-4, answer recorded as **D-16**; task 4.33 waits for it.
   - Quoted from `application/generate_contract.py:31` [VERIFIED: Read]: archive is "Presentation state only: archived studies keep every read and command; nothing is deleted."
   - Making only documents read-only in an archived study creates two archive meanings. Recommendation: keep documents writable like every other record in an archived study (consistent), or make archive read-only study-wide in a separate decision. **RISKY as the default reads.**
5. **Capability advertisement per step versus PD-4.8 (NEEDS PRODUCT OWNER).**
   - **Status: RESOLVED in planning** with the recommended default, which honours both the CONTEXT line and PD-4.8 without changing either: additive slice IDs in `document_slices`, each advertised only when every route of its slice is mounted, with `documents` kept in `unavailable` until the Phase 5 release gate (`04-PLAN.md` "Capability slices"; task 4.9a; `04-UI-SPEC.md` Q3). The product owner can still override it at the phase walk-through (task 4.41).
   - CONTEXT says "capability advertisement switches per delivered step"; PD-4.8 keeps `documents` unavailable until steps 1–13 pass and the reviews close.
   - Recommendation: add slice capability IDs (for example `documents_library/1`, `documents_collections/1`, `documents_extraction/1`, `documents_citations/1`) advertised as each step lands. The UI shows only advertised slices (D-08 "features appear only when implemented"). Remove `documents` from `unavailable` only at the PD-4.8 gate.
6. **Copy conflicts with Naming.md (product owner, low risk).**
   - **Status: RESOLVED in planning:** Naming.md wins on conflict; "Version <short ID>" replaces "exact version", and the frozen copy reads "Annotation saved with this citation — later edits and reprocessing do not change it" ("Annotations", never "notes", per PD-4.2). Task 4.5 records the names in Naming.md.
   - "Recorded note — …" and "exact version" versus Naming.md rule 1.
   - Recommendation: "Note saved with this citation — later edits and reprocessing do not change it", and "version" in place of "exact version". Update Naming.md in the UI-SPEC task.
7. **Step 11 needs a WhatsOpt patch and modeling-image rebuild (planner and owner awareness).**
   - **Status: RESOLVED in planning (owners assigned):** the `modeling` consumer and the patch go to task 4.36 (after Phase 2 task 2.6, AGPL scope); the `approach` consumer goes to task 4.35 and its UI path to task 4.39. These tasks still wait for D-13 (question 1).
   - The private 4 projection must be admitted by the modeling service (`contracts/documents.md` consumers table). That is AGPL-scope work after Phase 2 2.6.
   - The `approach` and `modeling` consumers are marked "**Open:** needs an assigned implementation owner"; Phase 4 must assign them to tasks in steps 11 and 13.
8. **Signed-cursor key (planner's discretion, security-relevant).**
   - **Status: RESOLVED in planning (planner's discretion):** an HMAC-SHA-256 key generated at application start by `secrets.token_bytes(32)` and held only in process memory, so no key is stored anywhere; a restart invalidates outstanding cursors and the client restarts the listing; every page re-authorizes (`04-PLAN.md` "Signed cursor key"; task 4.9a). This replaces the store-row option recommended below.
   - There is no server signing key today.
   - Recommendation: an HMAC key generated once into an application-store row on first use (no new mount, no file), or stateful cursor rows that expire with the 5-minute cache. Either way, re-authorize on every page.
9. **§18 defaults not owned by this phase.** Q2 (agent confirmation classes), Q3 (agent upload), Q6 (cloud backend requalification) and Q11 (authored documents) are out of scope; no risk.
   - **Status: OUT OF SCOPE** (CONTEXT "Deferred Ideas"; `04-PLAN.md` "Out of this phase").

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker engine | Native groups, parser image, containment | ✓ | 29.8.2 (client and daemon) | None. Native groups fail with `environment absent: docker` |
| Node.js | Browser groups, UI build | ✓ | v25.2.1 | — |
| Playwright in `ui/node_modules` | Browser groups | ✗ in this worktree (run `npm --prefix ui ci`) | — | Install per task; fails as `environment absent: browser` otherwise |
| Native development interpreter with aiida-core 2.9.3 (`HYPRN_MVP_NATIVE_PYTHON`) | All `native` and Documents groups (parent interpreter) | Not checked: `HYPRN_MVP_DATA_ROOT` is unset in this session | — | Set the development variables per the 01-PLAN "Development environment" section |
| System `python3` | Design checks only | ✓ | 3.9.6 | Groups use the reviewed interpreters, not the system one |
| PyPI reachability (wheel acquisition only) | Step 6 acquisition | ✓ (queried this session) | — | Pre-verified cache under the data root |
| Phase 2 pinned Python base digest | Parser image | ✗ until Phase 2 task 2.7 | — | Blocks step 6 |

**Missing dependencies with no fallback:** the Phase 2 2.7 base-image conventions (step 6), the Phase 2 2.6 modeling image from patches (step 11), and Phase 2 2.11 scratch installations (served acceptance).
**Missing dependencies with fallback:** Playwright (install), the development variables (export).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest under the runner's scoped child (`--noconftest`, plugin autoload disabled), stdlib unittest guards, Playwright for browser groups |
| Config file | `deployment/checks.py` (group registry: `DOCUMENTS_ROUTES`, `DOCKER_GROUPS`, `BROWSER_GROUPS`, `OPT_IN_GROUPS`, measured-group validators); `ui/playwright.isolated.config.ts` |
| Quick run command | `HYPRN_MVP_DATA_ROOT=<dev data root> "$HYPRN_MVP_NATIVE_PYTHON" -B deployment/checks.py --group <documents-group>` |
| Full suite command | `HYPRN_MVP_DATA_ROOT=<dev data root> "$HYPRN_MVP_NATIVE_PYTHON" -B deployment/checks.py --group qualification` (Phase 2: `./hyprn-mvp dev check qualification`) |

The runner fails a group when a target is missing, a selector matches no test, a test is marked skip or xfail, or an environment need is absent. A child exit without measured results is never accepted (`documents_report_passed`). Measured groups must also leave artifacts (the `documents_collection_evidence` pattern). Generalize `DOCUMENTS_MEASURED_GROUP` into a mapping from group to validator.

### Phase Requirements → Test Map

| Req ID / step | Behavior | Test Type | Automated Command (`CHECK g` = `HYPRN_MVP_DATA_ROOT=… "$HYPRN_MVP_NATIVE_PYTHON" -B deployment/checks.py --group g`) | What it samples | Failing signal | File Exists? |
|---|---|---|---|---|---|---|
| DOC-01 / 1 | Two collections share one original; stale CAS changes nothing; logical terminal delete with replay before visibility; annotations CAS and bounds | native integration + kill | `CHECK documents-collections`; `CHECK documents-annotations`; regression `CHECK documents-native-originals`, `documents-native-atomicity`, `documents-collection-protocol` | Fresh-process inspections of Group extras, members and witnesses; SIGKILL at each boundary; 10,000 members; 100 annotations | Members changed after a stale edit; a deleted collection visible; missing measured artifacts | ❌ Wave 0 |
| DOC-01 / 2 | Closed verb set; read mode cannot launch science; reads complete during a blocked run; the loop dies with its supervisor | contract unit + measured native | `CHECK documents-bridge`; `CHECK documents-read-loop` | Frames for every verb (accepted and refused); a timeline JSON of block start, reads and release; read-process liveness after executor exit | Any read ends after the block release or over the bound; a write or launch verb admitted in read mode; an orphaned read process | ❌ |
| DOC-01 / 3 | Chunks → native → published → exact download after restart; every recovery state; non-disclosing errors | native API integration | `CHECK documents-upload-api`; `CHECK documents-library-api`; `CHECK documents-access` | HTTP via TestClient or ephemeral socket against scratch stores; app and native restart between upload and download; foreign or unknown IDs, cursors, caches | Byte or hash mismatch; a foreign ID distinguishable; a lost spool reported as success | ❌ |
| DOC-01 / 4 | Library UI with upload, list, versions, download, recovery states; light, dark, keyboard, 200 % | browser (native-backed) | `CHECK documents-library-ui` | Playwright on an isolated real API; screenshots to `HYPRN_MVP_UI_EVIDENCE_ROOT` | Spec failure; page-wide horizontal scroll at 200 %; unreachable control | ❌ |
| DOC-01 / 5 | One version in two collections; head change never moves members; delete is terminal | native API + browser | `CHECK documents-collections-api`; `CHECK documents-collections-ui` | Membership after a new head version; delete then re-create with the same title | Member moved to the new head; deleted collection reused | ❌ |
| DOC-01 / 6 | Pinned digest; build verifies the wheel; containment demonstrated, else extraction refused | docker | `CHECK documents-parser-image`; `CHECK documents-parser-containment` | Image build with a tampered wheel (must fail); canaries for network, write, memory, PIDs, CPU, scratch, output, wall clock, orphan cleanup, invalid digest | A canary passes a forbidden action; extraction admitted without evidence | ❌ |
| DOC-01 / 7 | Repeatable locators; partial, unsupported (encrypted), needs_transcription (image-only), truncated, interrupted outcomes; original always downloadable | native + docker | `CHECK documents-extraction` | Synthetic PDF and text fixtures generated at run time; the same input twice gives identical page hashes; writer killed mid-extraction | Different hashes on retry; a finished wrapper reported as success; an interrupted attempt resumed | ❌ |
| DOC-01 / 8 | Real provenance links; exact snippets; honest coverage; deleted-collection filter not found | native + application | `CHECK documents-extraction-provenance`; `CHECK documents-search` | Input and output links of the calcfunction node; snippet equals the artifact slice; coverage counts | Forged links; a snippet differing from the artifact; empty results claimed complete with unindexed versions | ❌ |
| DOC-01 / 9 | A search hit opens the exact passage; escaped text only | browser | `CHECK documents-reader-ui` | Click a hit → reader heading names the page and highlighted range; HTML or Markdown payload shown inert | Script execution; wrong page or range | ❌ |
| HUM-06 / 10 | Annotation edits never change stored evidence; server-verified quotation; ≤ 20 citations; duplicates refused; commit barrier | native + application | `CHECK documents-citations`; `CHECK documents-evidence-v4`; regression `ae-evidence`, `ae-contracts`, `documents-citation-contracts` | Evidence record bytes before and after an annotation revise; UTF-16 astral offsets; forged client quote ignored | Stored evidence digest changes; client quote accepted | ❌ |
| RUN-02 / 11 | Citations survive preparation without widening earlier contracts | application + native + docker | `CHECK documents-configuration-chain`; `CHECK documents-bundle-admission`; `CHECK documents-modeling-private`; regression `locality-contracts` (golden corpus), `units-attestation`, `approach-closure` | Golden digests of older versions unchanged; new bundle re-admitted by launcher and worker; modeling image admits private 4 | Older golden changed; private projection drops citations | ❌ (blocked: Open Question 1) |
| RUN-02 / 12 | An old run opens its cited source during a modeling outage; bytes marked unavailable when native is down | native | `CHECK documents-frozen-history` | History read with the modeling service stopped; then with the read loop stopped | Modeling call attempted; current head substituted; missing bytes shown as empty | ❌ |
| HUM-06, RUN-02 / 13 | All five §15.4 paths reach the exact source; light, dark, keyboard, 200 % | browser | `CHECK documents-evidence-ui`; `CHECK documents-ui-zoom` | Navigation from assumption, configuration, approach, run and the Evidence page | A path opens the latest source instead of the cited one | ❌ |
| All UI steps | Design system and contract wiring | static | `python3 ui/check_design_system.py` (no FAIL); `python3 ui/design_tokens.py --check`; `python3 ui/test_design_tooling.py`; `node ui/design_smoke.mjs`; `CHECK combined-static` (runs `ui/check_ui_contract.py`) | Token use, inline styles, control-to-spec map | Any FAIL line; an unmapped control | partial |

### Sampling Rate

- **Per task commit:** the task's own Documents groups plus `CHECK documents-contracts` and `CHECK naming` (with `CHECK combined-static` for UI tasks).
- **Per wave merge:** every Documents group, plus `ae-evidence`, `locality-contracts` and `guard`.
- **Phase gate:** `CHECK qualification` green (the new must-pass groups join it automatically), plus the product-owner walk-through recorded separately.

### Wave 0 Gaps

- [ ] `deployment/checks.py`: a mode for native-backed browser groups (native interpreter; `docker` + `browser` needs); generalize `DOCUMENTS_MEASURED_GROUP` into per-group validators (read-loop timeline, parser canaries).
- [ ] `deployment/tests/documents_ui_fixture.py`: implement `start_isolated_api` (real API, store and auth; scratch AiiDA; in-process writer and read loop; modeling double).
- [ ] `deployment/tests/documents_native_fixture.py`: production-adapter probes (reuse inspection and kill helpers against the new `NativeDocuments` methods rather than the probe's own mutate).
- [ ] Runtime-generated fixtures: minimal PDFs (text, encrypted, image-only, malformed, > 500 pages, cyclic tree), UTF-8 edge cases (BOM, CRLF, astral characters, invalid bytes), all built at run time. Nothing binary is committed (the hygiene guard forbids secret-like literals; keep fixtures generated).
- [ ] `application/tests/test_module_boundaries.py`: register the new modules and their allowed imports.

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high` [VERIFIED: `.planning/config.json` read via cat].

### Applicable ASVS Categories (5.0.0 L1; requirement IDs as cited by `docs/specs/documents.md` §16)

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V1 Encoding and Sanitization | yes | Escaped React text only; no `dangerouslySetInnerHTML`; encoded `Content-Disposition` filename |
| V2 Validation and Business Logic | yes | Closed `$defs` validation (`contracts.validate`), revision CAS, receipts; limits from the registry |
| V4 API and Web Service | yes | Existing origin, session and CSRF checks on every non-GET including previews; JSON-only except the one chunk route |
| V5 File Handling | yes | 5.2.1/5.2.2 size, type and header-extension agreement, quotas; 5.3.1/5.3.2 fixed repository filename, no path from a filename; 5.4.1/5.4.2 attachment, `nosniff`, `no-store` [CITED: documents.md §16] |
| V6/V7 Authentication and Session | yes (unchanged) | Existing `Auth` (scrypt, HttpOnly SameSite=strict cookie, CSRF) |
| V8 Authorization | yes | 8.3.1: `Store.authorize` before any association or native lookup; reauthorize at dispatch, publication and delivery, including the ≤ 5 min cache and signed cursors |
| V11 Cryptography | yes | SHA-256 via `hashlib`; HMAC for cursors via `hmac` (stdlib), never hand-rolled |
| V13 Configuration | yes | 13.2.2/13.3.2 isolated networkless parser; reviewed limits file; no secret in configuration |
| V15 Secure Coding and Architecture | yes | 15.2.4 audited wheel hash, pinned image, no substitution |
| V16 Logging | yes | No document text, filenames or IDs from other studies in logs; no secrets |

### Known Threat Patterns (CONTEXT "Threats to cover") → mitigations and tests

| Pattern | STRIDE | Standard Mitigation | Test (group) |
|---|---|---|---|
| Cross-study access via guessed IDs, snippets, cursors, caches | Information disclosure / Elevation | Authorize first; one non-disclosing 404 for unknown and foreign IDs; cursor bound to study, query and filters; cache key includes the study and is reauthorized at delivery | `documents-access`, `documents-search` (foreign IDs in every route and parameter, cross-study cursor reuse, cached reply after membership removal) |
| Malicious or mismatched upload | Tampering / DoS | Header, extension and media agreement; strict UTF-8; length and hash per chunk and whole; quotas; spool O_NOFOLLOW | `documents-upload-api` (polyglot, PDF-named HTML, executable, octet-stream, gap, overlap, changed bytes, excess, missing Content-Length) |
| Header or filename injection on download | Tampering / Spoofing | Fixed native `original.bin`; filename display-only; RFC 6266/5987 encoded attachment filename; `nosniff`, `no-store` | `documents-library-api` (CRLF, quotes, non-ASCII, path separators in the filename) |
| Active content in the reader | Elevation (XSS) | Escaped text; uploads never rendered; CSP `default-src 'none'; script-src 'self'; style-src 'self'` (existing) | `documents-reader-ui` (HTML, script and Markdown-link payloads stay inert) |
| Parser exploit or resource exhaustion | DoS / Elevation | Isolated container, limits before parsing, external wall clock, output bound, orphan reaping | `documents-parser-containment`, `documents-extraction` (bombs, cyclic trees, > 500 pages, huge page text) |
| Parser supply chain | Tampering | Lock with size and SHA-256; build re-verifies; offline build; advisory recheck checkpoint; pinned base digest | `documents-parser-image` (tampered wheel refused), `documents-parser-adoption` |
| Duplicate or partial effects after crashes | Tampering / Repudiation | Witness in the same native transaction; replay before visibility; no retry without proven absence; uncertain stays uncertain | `documents-collections`, `documents-annotations`, `documents-upload-api` (SIGKILL around commit, lost reply, same command with changed payload) |
| Prompt injection through document text | Tampering (later agent use) | Text labelled untrusted in every API projection meant for agents; no agent tools in this phase | Contract check that projections carry the untrusted label when agent tools arrive (Phase after 4); document it now |
| Read loop used to launch science or write | Elevation | Fixed read verb set refused before I/O; no launcher, profile-write or socket in the read process | `documents-bridge`, `documents-read-loop` |

## Sources

### Primary (HIGH confidence)

- Repository files read this session: `.planning/phases/04-documents/04-CONTEXT.md`, `.planning/STATE.md`, `ROADMAP.md`, `PROJECT.md`, `config.json`, `01-PLAN.md`, `02-PLAN.md`, `03-CONTEXT.md` (overlaps), `05-CONTEXT.md` (overlaps); `docs/specs/documents.md` (full); `contracts/documents.md` (full); `docs/specs/architecture-and-contracts.md` §3–§8; `docs/specs/ui-target.md` §2.7–§3.8, §7; `docs/specs/requirements.md` (DOC-01, HUM-06, RUN-02); `docs/legal/licensing.md` §4–§5; `integration/document-parser-provenance.md`; `design-system/README.md`, `Layouts.md`, `Naming.md`, `Scientific-states.md`, component notes; `integration/src/hyprn_mvp_integration/documents.py`, `launcher.py`, `calculation.py`; `application/src/hyprn_mvp_app/api.py`, `store.py`, `dispatcher.py`, `configuration.py`, `execution_bundle.py`, `approach.py`; `application/generate_contract.py`; `deployment/checks.py`, `dispatch_runtime.py`, `application_runtime.py`, `tests/documents_native_fixture.py`, `tests/documents_ui_fixture.py`; `application/tests/test_module_boundaries.py`; `contracts/schemas/model.schema.json` (programmatic extraction); `ui/src/design/*`, `ui/src/Workspace.tsx`, `ui/check_ui_contract.py`, `ui/tests/foundry-zoom.spec.ts`.
- PyPI JSON API: https://pypi.org/pypi/pypdf/6.20.0/json and https://pypi.org/pypi/pypdf/6.20.1/json (sizes, SHA-256, upload times, vulnerabilities).
- GitHub advisories API: https://api.github.com/advisories?ecosystem=pip&affects=pypdf@6.20.0 (no matches).

### Secondary (MEDIUM confidence)

- https://github.com/py-pdf/pypdf/releases/tag/6.20.1 (security fix for cyclic trees, PR #4188).

### Tertiary (LOW confidence)

- https://raw.githubusercontent.com/aiidateam/aiida-core/v2.7.0/src/aiida/storage/sqlite_zip/utils.py (`create_sqla_engine` pragmas; version differs from the pinned 2.9.3).
- https://aiida-core.readthedocs.io/en/stable/_modules/aiida/storage/sqlite_dos/backend.html (search result only).

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH for in-repo components; MEDIUM for pypdf (the version decision is pending).
- Architecture: MEDIUM-HIGH. It derives from the existing executor, bridge and store code. Read-loop concurrency on the AiiDA SQLite profile is unmeasured.
- Pitfalls: HIGH for codebase-derived items (middleware, chain versions, attested set, revision baseline); MEDIUM for AiiDA and Docker runtime behaviour.

**Research date:** 2026-10-13
**Valid until:** 2026-10-20 for the parser supply-chain facts (fast-moving: a new pypdf release was published during research); 2026-11-12 for codebase facts, re-check after Phase 1 tasks 1.4–1.8 land.
