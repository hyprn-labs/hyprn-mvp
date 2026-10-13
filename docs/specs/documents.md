# Documents

Status: current specification. Related specifications: architecture and contracts (`docs/specs/architecture-and-contracts.md`), agents (`docs/specs/agents.md`, tool detail in `docs/agents/tooling-spec.md`), workspaces and access (`docs/specs/workspaces-identity-onboarding.md`), user interface (`docs/specs/ui-target.md`). Wire detail: `contracts/documents.md` and the shared schemas. Requirements: DOC-01, DOC-02, DOC-03; related HUM-06, RUN-02, OPS-01, OPS-03, AGENT-03 (`docs/specs/requirements.md`).

HYPRN MVP has two kinds of document. They are separate capabilities with separate storage, and this specification keeps them apart:

| Kind | What it is | Where it lives | Status |
|---|---|---|---|
| **Source document** | A file the engineer brings in: paper, datasheet, standard, test report, CSV export. Stored exactly as uploaded, versioned, organized in collections, read, searched, annotated and cited as evidence. | Bytes, collections, annotations and extraction provenance in AiiDA; identity, study scope, citations and evidence semantics in HYPRN MVP. | Decided and planned. Contracts and native storage of originals are implemented; the rest is not started (see §12). |
| **Authored document** | Text written inside HYPRN MVP: a study report, memo or review write-up. | HYPRN MVP records, edited with Tiptap. Live co-editing through Yjs, cloud edition only. | Later capability, not started (see §14). |

Sections 1–13 describe source documents. Where this document says "document" without a qualifier, it means a source document.

## 1. Outcome

Within a study, an engineer can:

1. upload source files and get the exact bytes back later, after restarts;
2. organize exact versions into collections without copying files;
3. read the extracted text, search titles, tags, annotations and text, and open a search hit at its exact page and passage;
4. annotate a passage and cite it (supports, challenges or gives context) in evidence attached to an assumption, model, configuration, approach step or case;
5. reopen an old run and read the exact cited source version and passage, even after the source was replaced, re-extracted or re-annotated, and even while the modeling service is down;
6. archive a source, remove it from a collection, delete a collection, or permanently delete an unreferenced version, each with a distinct, clearly stated effect;
7. export a selected set of sources and their citations as a portable package and import it elsewhere without running anything.

Everything must work manually through the UI. An agent gets the same operations through typed tools (§13); no document feature depends on an agent, a provider or the cloud.

A document being present, extracted or cited never establishes that a scientific statement holds. A citation records the engineer's interpretation; it does not validate anything.

## 2. Vocabulary

| Term | Meaning |
|---|---|
| Document (family) | Stable identity for one source across its versions. Has a title, tags, archive flag and a current head version. |
| Document version | Exact immutable original bytes: SHA-256, size, admitted media type, original filename, creator, time. Replacing content creates a new version; renaming the family does not. |
| Collection | Named, study-scoped selection of exact document versions. Many-to-many: one version can be in several collections without a second copy of its bytes. |
| Annotation | Editable working note anchored to an exact version and locator (page, passage or whole file). Mutable; not evidence by itself. |
| Extraction attempt / result | One processing run of a fixed parser over one exact version. Produces page-indexed text with hashes, coverage and errors. Each retry is a new attempt. |
| Locator | Where in a version a citation points: whole original file, physical PDF page, or exact extracted text span. |
| Citation | Immutable descriptor inside an evidence version that binds the evidence to an exact version, optional extraction, locator, server-verified quotation, optional frozen annotation snapshot, and a relationship. |
| Relationship | supports, challenges or contextualizes (UI labels: Supports, Challenges, Context). Chosen explicitly; never defaulted. |
| Usage ("Used by") | Every retained or pending record that depends on a version: evidence versions (including non-current ones), configurations, approach versions, runs, exports, pending operations, active collection memberships. |

## 3. Ownership: HYPRN MVP versus AiiDA

AiiDA provides storage, query, grouping and provenance primitives, not a document manager. HYPRN MVP adds identity, access, document semantics and citations on top, through a thin adapter. AiiDA's standard REST API is read-only and is not exposed; every mutation goes through the HYPRN MVP API and the authorized adapter.

| Concern | Owner | Representation |
|---|---|---|
| Public identity, study scope, family metadata (title, tags, archive, head), archive state | HYPRN MVP | Family and version records with revision checks. No bytes column. |
| Public ↔ native association | HYPRN MVP (private) | Exact study, native store and node identity per public version; never sent to clients. |
| Original bytes | AiiDA | One `SinglefileData` node per version, fixed repository filename `original.bin`; identity metadata stored as immutable node attributes before the node is stored. |
| Collections and membership | AiiDA | One `Group` per collection; fixed internal label derived from scope and public ID; title, description, revision and lifecycle in namespaced Group metadata; membership is the exact version nodes. HYPRN MVP keeps only the association, never a membership table. |
| Annotations | AiiDA | One bounded namespaced metadata object per annotation on the exact original node (id, revision, locator, text, tags, attribution), changed atomically as one object. |
| Extraction | AiiDA | A genuine `@calcfunction` wrapper with real input links (original, configuration) and output links (text folder, manifest), calling the isolated parser. |
| Command outcomes (receipts) | AiiDA for native effects, HYPRN MVP for operations | An immutable native witness (`Dict`) per successful native command, stored in the same transaction as the effect; HYPRN MVP keeps the operation record and mailbox. |
| Evidence, citations, relationships, usage | HYPRN MVP | Immutable evidence versions with typed citation descriptors. "Supports" is application semantics, never an invented AiiDA data-to-data link. |
| Search projection | HYPRN MVP, rebuildable | Derived from native extraction artifacts and keyed by extraction digest; never authoritative. |

Rules: native IDs, stores, profiles and paths never appear in public requests or responses; native metadata is validation data, never an access grant; the application keeps no second file, membership or text store (the upload spool is a short-lived buffer, never served); no distributed transaction, event bus, scheduler or workflow engine, and a document operation is never a scientific run record; the application and modeling service hold no AiiDA profile, database, launcher or socket credentials.

## 4. Authorization by study scope

Every operation is study-scoped: all paths sit under `/api/1/studies/{study_id}`, the study comes from the route and the actor from the session. The server checks current study access **before** any association or native lookup, and again at dispatch, at publication and at every byte, fragment, snippet, status or cached delivery.

- Unknown and foreign identifiers return the same non-disclosing not-found. Counts, cursors, snippets, usage lists and error bodies must not reveal anything outside the study.
- All non-GET requests carry the existing origin, session and CSRF checks, including previews and exports.
- Archiving does not revoke access. Losing access stops pending reads and clears protected content in the UI; already committed outcomes stay recoverable for authorized users.

Current roles map as follows; the right column is the target when workspace access arrives (`docs/specs/workspaces-identity-onboarding.md`):

| Operation | Today's study role | Target role |
|---|---|---|
| Read library, versions, originals, extracted text, search, annotations, collections, usage | owner, writer, reader | Owner, invited Reviewer |
| Upload, edit metadata, archive, manage collections, annotate, extract, cite | owner, writer | Owner |
| Permanently delete source versions | owner only | Owner only |
| Export / import a package | any reader / destination owner, writer | Owner, Reviewer / destination Owner |
| Restore from backup | operator (no implicit content access) | operator; Admin without a grant sees no content |

Re-run the full access matrix (guessed IDs, snippets, cursors, caches, downloads, revocation) when workspace access arrives. Deep access hardening may wait while it is costly, but the study-scope check on every route is mandatory: it is cheap and is the only barrier between studies.

## 5. Operations

Closed typed operations; unknown fields are rejected. Paths relative to `/api/1/studies/{study_id}`. Mutations take a client `command_id` and, where state is edited, an `expected_revision`; they return a typed operation whose outcome can be checked later.

Every document operation has one owner and one authoritative outcome (architecture §3.1, ADR-0004): the application's documents module owns identity, operations, associations, usage and citations, and delegates bytes, collections, annotations and extraction to AiiDA through the single writer; the outcome is the operation resource (or, for citations, the evidence version), which every client reads back instead of repeating the operation. The search projection is derived and rebuildable.

| Family | Operations |
|---|---|
| Upload | `POST document-uploads` (begin: command id, optional family id + expected revision for a new version, filename, media type, byte length, SHA-256) · `PUT document-uploads/{id}/chunks/{offset}` · `POST document-uploads/{id}/complete` · `GET document-uploads/{id}` |
| Operation status | `GET document-operations/{id}`: reading status never retries a mutation or launches anything |
| Library | `GET documents` (filters: collection, type, tag, processing state, archived; signed cursor) · `GET documents/{id}` · `GET documents/{id}/versions` · `GET document-versions/{id}` · `PATCH documents/{id}` (title, tags) · `POST documents/{id}/archive` · `POST documents/{id}/unarchive` |
| Original | `GET document-versions/{id}/original` (whole file or bounded range) · `GET document-versions/{id}/fragments` |
| Collections | `POST/GET document-collections` · `GET/PATCH/DELETE document-collections/{id}` · `GET/POST document-collections/{id}/members` (add, remove, replace in one revision-checked batch) |
| Extraction | `POST document-versions/{id}/extractions` · `GET document-versions/{id}/extractions` · `GET document-extractions/{id}` · `GET document-extractions/{id}/result` · `POST document-extractions/{id}/retry` (names the prior attempt; creates a new attempt) |
| Search | `GET document-search` (query ≤ 256 codepoints; mode metadata, text or both; scoped filters) |
| Annotations | `GET/POST document-versions/{id}/annotations` · `GET/PATCH/DELETE document-versions/{id}/annotations/{annotation_id}` |
| Citations | `POST document-citations/preview` (one candidate) · `POST evidence-citations/preview` (full evidence intent with target scope) · existing evidence create/revise routes accept citation candidates |
| Usage | `GET document-versions/{id}/usage` |
| Permanent deletion | `POST document-deletions/preview` · `POST document-deletions/commit` · `GET document-deletions/{id}` (owner only) |
| Export | `POST document-exports/preview` · `POST document-exports` · `GET document-exports/{id}` · `GET document-exports/{artifact_id}/download` |
| Import / restore | `POST document-imports` + chunks + complete · `GET document-imports/{id}` · `POST document-restores` · `GET document-restores/{id}` (operator) |

Errors reuse the existing envelope (`invalid_request`, `forbidden`, `resource_not_found`, `stale_revision`, `command_payload_conflict`, `reference_conflict`, `limit_exceeded`, `backend_unavailable`, `operation_pending`, `dispatch_uncertain`, …); specific failures are bounded receipt reasons. Pending or unknown outcomes are explicit, never an empty success.

## 6. Upload, storage and recovery

**Transfer.** Begin reserves the command, public document and version IDs, expected metadata and a transient spool lease. Bytes arrive in chunks of at most 256 KiB at exact offsets. Resending identical bytes at the same offset is a harmless retry; gaps, overlaps, changed bytes or excess bytes fail without effect, whether or not `Content-Length` is present. Complete requires the exact full length and SHA-256. Only this upload route accepts a raw binary body; all other routes keep the existing JSON-only, 2 MiB request limit.

**Publication.** The integration side stores the original and its immutable witness in one native transaction, reads the stored bytes back and verifies the hash, then the application publishes the version. Only published versions appear in the library. One successful logical command yields exactly one version; two separate explicit uploads of identical bytes are two independent versions.

**Operation states.** Uploads: `receiving → queued → running → committed → published`. Other mutations start at `queued`. Terminal alternatives: `failed`, `expired`, `interrupted`, `uncertain`, each with a reason. Published, failed and expired have no outgoing transitions.

**Recovery.** After a lost reply or crash, the writer looks up the exact immutable witness (scope, command, payload digest, reserved IDs, store) **before** looking at current state or revisions:

- one exact match → return the original outcome, publish it once if needed;
- same command with a changed payload (including a changed expected revision) → conflict;
- several or mismatched witnesses → uncertain; no blind retry, scoped diagnosis;
- no witness → retry only after the previous writer is proven stopped and absence is proven. A timeout alone is never proof.

A lost spool with no native commit becomes "re-upload required", never a fabricated success. Lost native bytes become "unavailable", never an empty document. Spool and transfer handles are server-derived, scoped, bounded and expiring; they are never client paths or reusable URLs.

**Fixed bridge and concurrency.** The application reaches the integration side through a closed verb set: read mode (descriptor, list, member, annotation, fragment, original, status) and write mode (store original, collection create/update/members/delete, annotation create/revise/delete, extraction start, source-delete preview and commit, export, import, restore, reconcile). No generic dispatch, path access, profile selection or scientific verb. Document reads must stay usable while a numerical run blocks the scientific loop: a narrow read loop runs under the existing execution manager with read verbs only. All native writes, including extraction admission, keep the single-writer discipline; a waiting mutation says so instead of freezing the page. Responsiveness is measured against a deliberately blocked run, not assumed.

## 7. Reading, extraction and search

**Admitted formats.** PDF, strict UTF-8 plain text, Markdown and CSV. Anything else, including generic binary and executable types, is refused. Media type, file header and extension must agree; a mismatch is refused or classified unsupported, never executed. CSV is displayed as escaped bounded text; it is never interpreted as a table of model inputs.

**Parser.** PDF text uses `pypdf==6.20.0` (BSD-3-Clause, Python 3.12, no extras, zero additional runtime dependencies; exact wheel SHA-256 `f003fc2014814d264fe7dd3f9d435c158e23e1a85a2233f87a0a2d6d21c914ad`), installed from the audited artifact with dependency resolution disabled. Text formats use strict standard-library UTF-8 decoding (`hyprn-mvp-utf8/1`), no charset guessing, newlines normalized to LF in the extracted copy only. Any version, extra or package change needs a fresh provenance and licence audit; a failure never triggers substitution of a similar package. Advisory status must be rechecked before installation.

**Containment.** The parser runs in a separate pinned image: non-root, read-only root and input, no network, capabilities, secrets, AiiDA profile, application database or host socket. External limits apply before page counting or decompression (§11). Containment must be demonstrated (network and write denial, each limit, descendant cleanup on timeout and on exit of the supervising process, refusal of an invalid image or configuration), not inferred from arguments. Until then extraction stays unavailable; storage and original download do not depend on it.

**Outcomes.** Each attempt records parser identity, image and configuration digests, original hash, per-page text hashes, locator map and coverage. Outcomes per attempt and page: succeeded, partial, truncated, failed, interrupted, needs transcription (scanned page), unsupported (e.g. encrypted PDF). A finished wrapper process is not a successful extraction; successful pages of a partial result are kept; a controller crash marks the attempt interrupted and it is never silently resumed. The original stays downloadable in every state. No invented confidence; tables and symbols carry a "check against the original" warning and never become trusted numbers.

**Search.** Metadata (title, filename, tags, annotation text) and available extracted text, by bounded string matching over a rebuildable projection. Every hit carries exact version, extraction, artifact and locator, and results state coverage (unindexed, partial, failed sources). An empty result means "no match in the searched material". A deleted collection filter is not found and never broadens. No ranking, semantic search or OCR.

## 8. Locators, annotations and citations

**Locators** (closed union):

| Locator | Binds | Quotation |
|---|---|---|
| `original_file` | The exact original | None machine-verified; an optional section label is marked human and unverified |
| `pdf_page` | Physical 1-based page, valid only against a safely established page inventory | Optional, only if an extraction is also pinned; otherwise "no extracted quotation" |
| `extracted_span` | Exact extraction, artifact and artifact hash; half-open Unicode codepoint range `[start, end)` | Required; computed and hashed by the server from the exact slice |

Browser selections arrive as UTF-16 offsets and must be converted to codepoints and verified. Negative, reversed, out-of-range or mixed version/extraction spans are rejected. A client-supplied quote is never trusted. If the page inventory cannot be established, cite the original file rather than invent a page.

**Annotations** are working material. Creating, editing or deleting one requires its current revision and changes only that annotation. Annotation edits never change evidence.

**Citations** live inside evidence versions (evidence contract version 4). An evidence create or revise carries up to 20 citation candidates (exact public IDs, locator, optional annotation ID and revision, relationship) plus the expected target context revision and preview digest. The server resolves each candidate, authorizes the target scope and every source, verifies bytes and text, and freezes a `DocumentCitation1` descriptor: family, version, original hash, size, media type, retained title and filename, extraction ID and manifest digest, parser identity, locator, quotation and its hash, full annotation snapshot (or none), and relationship. The citation ID is the hash of the canonical descriptor. Commit re-resolves and rechecks the source deletion fence inside the evidence transaction. Duplicate citations of the same source, locator and annotation revision are rejected.

Consequences:

- A new version, a re-extraction, a title change or an annotation edit never changes an existing citation. Historical citations never follow the current head.
- Older evidence with free-text `source_refs` stays readable as unverified text references and is never promoted to verified citations.
- Configurations, approach versions and runs freeze the exact evidence descriptors in their closures, through new explicitly versioned contracts (configuration v5 / private projection v4 / frozen configuration v6 / execution bundle v7 / run history v5 / modified-run seed v5; approach closure v2). Earlier versions are not widened. Citation metadata travels with the scientific record; PDF bytes never enter modeling requests or execution bundles.
- Historical source resolution goes through the document API and works during a modeling-service outage.

## 9. Lifecycle: archive and delete

| Action | Effect | Who |
|---|---|---|
| Archive / unarchive source | Hides the family from default browsing. Bytes, versions, collections, citations and direct authorized reads remain. | owner, writer |
| Remove from collection | Removes one exact membership. Source and citations remain. | owner, writer |
| Delete collection | Removes the organization only (§9.1). Documents and evidence remain. | owner, writer |
| Delete annotation | Removes the working annotation. Copies frozen in evidence remain. | owner, writer |
| Permanently delete source versions | Removes the bytes of an explicit set of unreferenced versions and their exclusively owned processing artifacts (§9.2). | owner only |

Studies are never deleted, only archived. Development run data may be discarded, but discarding runs never authorizes deleting documents, evidence or other protected authoring data in the same store.

Agents (ADR-0003): they may remove or replace collection members and delete working annotations (draft material, revision-checked); they never delete a collection, permanently delete source versions, or archive or unarchive a source.

### 9.1 Collection deletion (logical, terminal)

In one native transaction: remove every current member (up to the 10,000-member maximum; the 100-per-edit limit does not apply to deletion), advance the revision once, mark the Group's lifecycle `deleted`, and store one immutable terminal witness. The empty Group is kept. It can never be reactivated or reused; a new collection with the same title gets a new identity. Physical Group deletion is not used: on the pinned AiiDA version it commits early and cannot be rolled back, so it is unsafe.

Ordinary reads, counts, filters, badges and pagination see active collections only, filtered at the native query boundary. Replay looks up the witness before that filter, so recovery after deletion works, and an earlier create or edit replays its historical outcome without reactivation. A deleted marker without witness, a non-empty deleted Group or conflicting witnesses fail closed. Terminal Groups and witnesses accumulate by design (accepted risk); there is no automatic cleanup.

### 9.2 Permanent deletion of source versions

Two fences, no distributed transaction:

1. **Application fence.** In one application transaction, check revisions and mark the exact versions deletion-pending, which blocks new citations, evidence revisions, configuration and approach snapshots, exports and collection additions referencing them. Then compute all usage: every evidence version (not only current ones), configurations, approach versions, runs, exports, pending or uncertain operations, active memberships. Any usage blocks and is shown as "Used by". In-flight collection additions hold source reservations, so both race orders resolve safely.
2. **Native fence.** Under the serialized writer, dry-run AiiDA's deletion closure and recheck membership. Only exclusively owned, uncited original and processing nodes may go; any scientific descendant or foreign, shared or unknown node blocks. The deletion receipt survives the nodes.

A tombstone (identity, digest, outcome, no bytes) follows only confirmed native disposition; an unknown outcome keeps the fence ("deletion outcome uncertain"). The preview is advisory; commit repeats every check. Deletion is not secure erasure; garbage collection is an operator concern. Native node deletion still needs its own crash qualification.

## 10. Portable export, import and backup

**Export** selects exact versions and evidence. Collection and annotation snapshots are optional and explicit, frozen at their revision; deleted collections cannot be selected and a whole Group is never exported implicitly. The package (portable envelope v3) inventories each file by role, path, size and hash (original, extraction text, manifest, citation, collection and annotation snapshots, operation witness) plus native node/link closure, mappings and origin identities. Credentials, profiles and executable checkpoints are excluded.

**Import** is data-only into an authorized destination, quarantined until the closure verifies, then published under new identities with immutable origin descriptors. It rejects traversal, symlinks, duplicates, expansion bombs, missing or extra files, undeclared binary roles, hash or link mismatches and foreign scope; it never resumes a process or triggers science. One import receipt, bound to the package digest, reconciles a crash.

**Backup** is distinct: a coordinated barrier drains every writer (documents, evidence and configuration publication, science, imports, exports) before the stores are copied; a crash between copies yields an unusable snapshot. Restore targets a verified empty destination and never overwrites populated stores.

## 11. Limits

All limits live in reviewed configuration and are tested. Bytes mean bytes; codepoints mean Unicode codepoints, not JavaScript string length. A limit failure never silently splits an atomic command.

| Limit | Value |
|---|---|
| Original file | 10 MiB |
| Upload chunk / native read reply | 256 KiB |
| PDF pages | 500 |
| Extracted text | 256 KiB per page, 8 MiB total |
| Filename, title | 200 codepoints |
| Description, annotation text, quotation | 4,096 codepoints |
| Annotations per version | 100 |
| Tags | 20 × 64 codepoints |
| List page / search page | 100 rows |
| Search query / snippet | 256 / 512 codepoints |
| Collection members / per membership edit | 10,000 / 100 |
| Citations per evidence | 20 |
| Incomplete uploads / staged bytes per study | 4 / 100 MiB |
| Active extractions per installation | 1 |
| Spool and transfer retention / response cache | 24 h / 5 min |
| Parser | 30 s, 1 CPU, 512 MiB, 64 PIDs, 64 MiB scratch |
| Portable package | 100 MiB compressed, 256 MiB expanded, 10,000 entries, 100 originals |

These are design parameters qualified on synthetic fixtures, not measured production capacity. Original delivery currently verifies the whole file (≤ 10 MiB) in memory before sending; constant-memory streaming is not promised.

## 12. Implementation status

The target above is decided. Nothing is visible to users yet.

| Area | Status |
|---|---|
| Wire contracts | **Done.** About 130 closed definitions (all operations, bridge, locators, citations, evidence v4, document-bearing version chain) in both shared schemas, a machine-readable registry of routes, roles, verbs, limits and transitions, and the normative contract document `contracts/documents.md`. Generated into OpenAPI components and TypeScript types, but **no route exists**; capabilities list `documents` as unavailable. Contract tests are structural only. |
| Native originals | **Done.** The adapter `hyprn_mvp_integration.documents.NativeDocuments` stores an original plus witness in one transaction, verifies readback, reconciles by command, refuses conflicting or corrupt identities, and serves bounded authenticated reads. Tested on AiiDA 2.9.3 with SQLite, including a forced kill before and after commit. No caller yet: authorization, transfer resolution and writer fencing are not built. |
| Prerequisites | **Qualified.** Logical collection deletion (§9.1) is proven on the pinned backend, including crash, replay and 10,000 members; physical Group deletion is proven unsafe. Parser pin audited, not installed. |
| Everything else | **Not started** (steps below). |

**Next step.** Add native collections and working annotations to the existing adapter: Group create/read/update with revision checks, membership add/remove/replace in one checked batch, the logical terminal deletion of §9.1 with replay-before-visibility ordering and active-only projections, and atomic bounded annotation create/revise/delete on exact original nodes. Start by verifying the existing originals implementation and its tests against `contracts/documents.md`.

**Remaining work, in dependency order.** Each step ends in working, tested behaviour; UI steps carry light/dark, keyboard and genuine 200 % zoom evidence.

| # | Step | Done when |
|---|---|---|
| 1 | Native collections and annotations | Two collections share one original; stale edits change nothing; delete/replay as §9.1 |
| 2 | Bridge verbs; managed read loop | Read mode cannot launch science; reads complete during a blocked run |
| 3 | Upload and library API | Chunks → native bytes → published version → exact download after restart |
| 4 | Library UI | Upload, list, versions, download and all recovery states in the browser |
| 5 | Collections API and UI | One version in two collections; head changes never move members |
| 6 | Parser image | Pinned digest; containment demonstrated, else extraction blocked |
| 7 | Extraction | Repeatable locators; partial/unsupported/needs-transcription outcomes |
| 8 | Processing provenance; search | Real provenance; exact snippets with honest coverage |
| 9 | Reader and search UI | A hit opens the exact passage |
| 10 | Annotations, citation resolver, evidence v4 | Annotation edits cannot change stored evidence |
| 11 | Configuration chain | Citations survive preparation without widening earlier contracts |
| 12 | Frozen history | An old run opens its cited source during a modeling outage |
| 13 | Scientific evidence UI | All five paths of §15.4 reach the exact source |
| 14 | Deletion fences | Every dependency blocks deletion, in both race orders |
| 15–16 | Portable policy; import, restore, backup drill | Bytes, citations, origins survive isolated restart; tampering rejected |
| 17 | Lifecycle and export UI | Archive, remove, delete, export visibly distinct |
| 18 | End-to-end acceptance | Full manual journey plus failure cases |

**Acceptance.** Documents is complete only when the product owner and an engineer who did not implement it have walked through: upload and reopen an original; organize two collections; search, read and annotate; create and attach an exact citation; change the source, annotation and extraction and reopen an old run (also with the modeling service down); try a failed extraction and a blocked deletion; export and import a package. Automated evidence is recorded separately from that human acceptance.

## 13. Agent parity through typed tools

Agents get the same document operations through HYPRN MVP's curated, provider-neutral tool registry, which calls the HYPRN MVP API in process as an agent principal acting for a user. Cloud: a provider-managed agent through the provider's custom-tool bridge (remote MCP as fallback). Local: the MCP tool server is the only sanctioned path. Binding rules from `docs/specs/agents.md` and `docs/agents/tooling-spec.md` apply unchanged:

- `study_id` is never a tool argument; HYPRN MVP binds the session to a study, with at most the delegating user's authority.
- Agent writes execute directly within the delegating user's authority, attributed and journaled (ADR-0003, `docs/adr/0003-agent-write-rights-revised.md`); provider or client approval prompts never widen what an agent can do.
- Agents never delete a saved record (documents, source versions, collections) and never archive or unarchive documents. Working annotations are draft material: an agent may create, revise and delete them with their current revision; frozen annotation snapshots in evidence never change. Collection membership may change (add, remove, replace); every evidence version, configuration and run keeps the exact versions it cited.
- Each tool names the document operations it calls, their owner and the stored outcome (ADR-0004); a tool never repeats an extraction or upload to show its result, it reads the operation or attempt.
- Document text, titles, annotations and snippets come back as labelled untrusted content: data, never instructions.
- Private text may go to the delegated managed agent within its scope, with the transmitted versions and fragments recorded; never to public search implicitly.
- Agent-created annotations and evidence show their origin. A recommendation alone never changes a model or launches a run.

Proposed tools once the matching manual feature exists (effects follow the agents write policy, see open question 2):

| Tool | Effect |
|---|---|
| `list_documents`, `get_document`, `list_collections`, `search_documents`, `read_document_fragment`, `get_document_usage`, `get_extraction_status` | Read |
| `annotate_document` (create, revise or delete a working annotation with its current revision; frozen snapshots in evidence are unaffected) | Draft (working annotation, attributed to the agent) |
| `organize_collection` (create a collection, rename it; add, remove or replace members in a revision-checked batch; documents and citations remain) | Record |
| `request_extraction` | Record (bounded by extraction limits); the result is read from the attempt, never re-run to show it |
| Citation candidates inside `add_evidence` / `revise_evidence` | Record (existing evidence tools gain a typed `document_citations` field) |
| Collection deletion, permanent deletion of source versions, document archive and unarchive | Never offered to agents (ADR-0003) |
| Upload, import | Not in the first version (open question 3); a scope choice, not a rights rule |
| Restore from backup | Operator only |

Until the manual features exist, `search_documents` and `read_document_fragment` stay registered as blocked, and agents use `read_evidence`.

## 14. Authored documents and live co-editing (later, separate)

Authored documents are text written in HYPRN MVP: study reports, memos, review write-ups. They are not source documents and do not share their storage path.

- **Editor:** Tiptap core (MIT), styled with the design system, adopted only once authored reports are scheduled.
- **Storage:** HYPRN MVP records owned by the study, under the same study-scope authorization.
- **Freezing:** a finished or cited text is frozen into an immutable HYPRN MVP evidence version, and can additionally be exported as a file and stored as a source document version in AiiDA. Live editing state is never a source of truth for scientific records.
- **Comments and review threads:** HYPRN MVP records, not editor-vendor features (the vendor's comments and history are paid add-ons).
- **Live co-editing:** Yjs with pycrdt-websocket (Hocuspocus as fallback), cloud edition only, and only when several people need to edit the same text at the same time. The local edition is single-user and has no co-editing server.
- **Agents:** may draft authored text through typed tools, change or delete it while it is a draft, and save a version or freeze it into evidence directly, attributed and journaled (ADR-0003); they never delete a saved version or frozen evidence.
- Every dependency needs provenance and licence review before installation; permissive licences only (some real-time sync servers are AGPL and are excluded). See `docs/legal/licensing.md`.

Not started; nothing is planned in detail. Source documents do not depend on it.

## 15. UI behaviour

Built only from the design-system components and tokens (`design-system/README.md`); no new style library, font, external URL or inline style. Plain-language wording throughout: user-facing text names documents, versions, pages and statements, never backend classes, schema numbers or storage internals.

### 15.1 Placement

Documents is its own study tab, placed immediately before Evidence. Documents is the home for source files, collections, reading, search and annotations; Evidence is the home for scientific statements and their exact citations. The existing evidence views are not replaced by a file browser. Features appear only when implemented: earlier slices omit future panels rather than showing placeholders or disabled controls.

### 15.2 Library

Collections panel (190 px) beside a fluid document list, stacking at the narrow breakpoint. Header "Documents" with an "Upload documents" action. Search and filters lead the list, then coverage and processing state. Each row shows title, format, exact version, processing state in words and a direct "Read source" action; hashes and IDs sit in "Record details". Collection controls (create, rename, delete, add, remove, replace a member version explicitly) sit with the collections panel. The upload dialog lists admitted types and limits, shows measured byte progress then processing in words; only published uploads become rows.

### 15.3 Reader

"Back", "Download original" and "Record details" above the title and exact version. A fluid text column plus a 350 px side column (annotations, "Used by", source actions), stacking at narrow width or zoom. The main heading names what is shown ("Extracted text · page N" or "Source text · lines A–B"). Page and line navigation and the extraction attempt selector sit next to the text. The reader is text-first: escaped text only; uploaded PDF, Markdown or HTML is never embedded or rendered. Original download is always available when authorized, independent of extraction state.

### 15.4 Citing and history

Selecting a passage (pointer or keyboard, with labeled start/end fields as an accessible fallback) offers "Cite passage", "Cite page" or "Cite original". The user must choose a relationship (Supports, Challenges, Context); "Preview citation" shows the server-verified quotation; any field change invalidates the preview. Saving creates a new evidence version; attaching it to an assumption, configuration or approach item is a separate explicit step on that owner, and a created evidence record survives if the owner's draft is discarded.

The cited source is reachable from: (1) a model or component assumption → View evidence → Read cited source; (2) a configuration's context, input, criterion or assumption → View evidence; (3) the modeling approach's question, step, assumption or case; (4) a run's models, configuration or evidence; (5) the Evidence page. The historical view shows the frozen quotation and annotation snapshot ("Recorded note — later edits and reprocessing do not change this citation"); "View latest source" is a separate, explicit navigation. If the native store is down, retained descriptors and quotations still display and the bytes are marked unavailable.

### 15.5 States, recovery and accessibility

- Empty, loading, error, partial, overflow and long-text states are explicit. "No text found" never means "no original".
- Uncertain outcomes offer a status check before any retry; nothing is resubmitted automatically or disappears optimistically. Stale edits keep the user's text and offer the latest version.
- Dirty forms join the existing unsaved-changes guard; access loss clears protected content first.
- Every control keyboard-reachable; dialogs trap and restore focus; light and dark themes; genuine 200 % zoom without page-wide horizontal scroll.

Key copy: "No readable text was found. The original is kept." · "Text is available for N of M pages." · "Check tables and symbols against the original before using numbers." · "A citation records your interpretation; it does not validate the statement." · "Delete [collection]? This removes the collection, not its documents or evidence." · "Deletion blocked. This version is used elsewhere. Review Used by, or archive the source." · "Saving the file…" · "Check what happened". Copy never names internals such as native storage or command identities.

## 16. Security requirements

Standard: OWASP ASVS 5.0.0 Level 1; high-severity findings block release. Additional higher-level controls are named where relevant.

| Threat | Required control |
|---|---|
| Cross-study access | Authorize before any lookup; fixed public → native mapping; non-disclosing errors; reauthorize at every delivery, including caches (≤ 5 min) and signed cursors (ASVS 8.3.1). |
| Malicious upload | Media/header/extension agreement; byte, length and hash checks; no executable types; bounded spool and quotas (5.2.1, 5.2.2). |
| Path or header injection | Fixed repository filename; user filename is display only; encoded attachment filename; `nosniff`, `no-store` (5.3.1, 5.3.2, 5.4.1, 5.4.2). |
| Active content | Escaped text reader; no inline rendering of uploads; nothing executed. |
| Parser exploit or overload | Isolated networkless parser, external limits before parsing, bounded output (13.2.2, 13.3.2). |
| Supply chain | Audited wheel hash, pinned image, no substitution (15.2.4). |
| Duplicate or partial effects | Witness in the same transaction; replay before visibility; no retry without proven absence. |
| Deletion races, package tampering | Two fences (§9.2); closed package inventory, quarantine, data-only import. |
| Prompt injection | Untrusted-content labelling; no agent deletion of saved records, archive or restore; working-annotation changes revision-checked; every agent write attributed and journaled; no public search with private text. |
| Retention | Archive is not deletion; deletion is not secure erasure; terminal collection records retained by design. |

Runtime data (stores, spool, parser scratch, logs) lives under the product data root (`<data root>`, resolved as flag → `HYPRN_MVP_*` environment variable → installation configuration → per-OS default folder named `hyprn-mvp` → ask), never in the source repository or a cloud-synced folder.

## 17. Out of scope

OCR; Office or other format conversion; image preview; rendered PDF page view; relevance ranking and semantic or vector search; nested collections; automatic numeric binding from tables or CSV; executing anything found in a document; physical cleanup of deleted collections; secure erasure; a second evidence browser; per-study secret areas inside a shared workspace; authored documents and co-editing until separately scheduled (§14).

## 18. Open questions (with recommended defaults)

1. **Annotation label.** The UI has one Assumption concept and no notes. Default: call document annotations "Annotations" in the UI (never "notes") and keep them out of the Evidence page.
2. **Agent effects for document tools.** Decided by ADR-0003, as in §13: reads; working annotations as draft material (create, revise, delete); collection organization, extraction requests and citations as direct, attributed writes; never collection deletion, permanent deletion, archive or unarchive.
3. **Agent upload.** Default: none in the first version; humans upload in the UI. Revisit for the local edition once the MCP server is stable.
4. **Study archive.** Default: archiving a study makes its documents read-only along with the study; nothing is deleted; restore re-enables editing.
5. **Rendered PDF pages.** Default: text-first reader only; add a rendered page view later only through an audited, permissively licensed renderer under a strict content security policy.
6. **Cloud backend.** The native transaction and logical-deletion protocol are proven on SQLite only. Default: requalify both on the cloud PostgreSQL backend before the cloud edition offers Documents.
7. **Access-protection depth in the local edition.** Default: the study-scope check on every route always; the full persona, revocation and cache matrix is required before multi-user cloud.
8. **Document-bearing version chain.** Development run data is discardable, but the document-bearing scientific contracts are allocated as new versions beside the earlier ones. Default: implement the allocated chain as specified; build no additional compatibility for discarded run data.
9. **Upload transport for the local edition.** Default: keep the contracted chunked protocol (one path for local and cloud) rather than a single-request shortcut.
10. **Plain-language copy.** Default: all user-facing document copy follows §15.5 and `design-system/Naming.md` before the UI ships.
11. **Authored documents versus conclusion records.** Default: an authored report is a separate later record type; claims and conclusions keep their own typed record, and a report cites them rather than replacing them.
