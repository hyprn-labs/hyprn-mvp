# Documents transport contract 1

Status: allocated wire and ownership contract for source documents (uploaded files with versions, collections, reading, annotation, citation and extraction). The schemas and the registry below are defined and tested; API handlers, native adapters, parser containment, storage and UI implement them separately, and the capability stays advertised as unavailable until they do. The product specification is `docs/specs/documents.md`. Structural rules live in the schemas; the runtime obligations below are mandatory for every implementation.

`model.schema.json` and `execution.schema.json` contain identical Documents definitions; all pre-existing definitions are unchanged, including the mixed Model2/Model3 unit branches. The additive `x-hyprn-mvp-documents-contract` registry names every route, permission, bridge verb, limit and transition. The registry is normative contract metadata, **not executable authorization or state-management code**. Validators must select the named `$defs` type; validating a bare definitions document does not validate a resource.

Collections use native logical deletion (section "Collection deletion and source fences"); there is no physical Group deletion. The PDF parser pin is `pypdf==6.20.0` (see `integration/document-parser-provenance.md`).

## Resource ownership and identity

| Resource | Authority and immutable identity | Mutable state |
|---|---|---|
| `Document1` | Application family UUID, study, creator and time | Title, tags, archive state and head, under revision compare-and-set |
| `DocumentVersion1` | Application public UUID mapped to the exact native original; original size, SHA-256, media type, filename, creator and time never change | Availability and lifecycle revision only; no bytes column |
| `DocumentCollection1` | Native Group metadata, lifecycle, revision and exact-version membership | Atomic compare-and-set mutations; no authoritative application membership table |
| `DocumentAnnotation1` | One bounded namespaced extras object on the exact original; UUID and source association | Locator, text, tags and attribution changed together under compare-and-set |
| `DocumentExtractionAttempt1` | A new public attempt for immutable original, configuration and extractor pins and the actual native process | Honest attempt state, separate from the native wrapper state |
| `DocumentExtractionResult1` | Native text `FolderData` and an immutable manifest `Dict` | No mutation after publication; the projection is rebuildable |
| `DocumentOperation1` | Application receipt and mailbox ownership, typed category and reserved public IDs | Durable finite transitions; no run foreign key or scientific outbox entry |
| `DocumentNativeAssociation1`, `DocumentNativeWitness1`, `DocumentCollectionTerminal1` | Internal exact study, store, native and public identity and immutable command outcome | Never public payloads or access grants |
| `DocumentDeletionFence1`, `DocumentTombstone1` | Application lifecycle boundary for exact versions | An unknown disposition keeps the fence; confirmed deletion keeps identity and digest |
| `DocumentAppCommit1` | Internal immutable application transaction receipt for metadata and archive commands | None |

Public IDs are lowercase canonical UUID strings. Digests are lowercase SHA-256; timestamps are UTC strings ending in `Z`. Unknown object keys fail. Schema bounds constrain syntax, not actual byte or hash relationships. User filenames are display metadata only: the native repository uses a fixed safe name, and no path, command or header is ever derived directly from a filename. Native IDs, stores, profiles, filesystem paths and parser arguments never enter public requests or responses.

A new family head or upload never retargets existing collection membership or citations. Archiving changes default browsing only: exact authorized reads, collections and historical references stay valid. Native lifecycle fields are validation data, never grants.

## Public transport and permissions

Paths are relative to `/api/1/studies/{study_id}`. The study comes from the authenticated route and the actor from the session. The registry types each path parameter separately. Inputs name JSON bodies or closed GET query objects. Successful JSON resources use the `{data: ...}` transport wrapper; the table names the data type. Raw byte routes use the descriptor as response metadata, not as a JSON replacement for file bytes.

Every route authorizes current study access **before any association or native lookup** and reauthorizes at delivery. Unknown and foreign identifiers get the same non-disclosing response. Every non-GET request requires the session, origin and CSRF controls, including read-oriented previews and exports. A reader can create an authorized export but cannot change source content. Permanent source deletion is owner-only; collection removal is ordinary owner or writer organization editing. Operator restore requires separately bounded operator authorization and an authorized, verified-empty destination; operator status grants no implicit access to study content.

| Family | Method and path | Input | Success data / byte metadata | Roles |
|---|---|---|---|---|
| upload | POST `document-uploads` | DocumentUploadBegin1 | DocumentUploadStatus1 | owner, writer |
| upload | PUT `document-uploads/{upload_id}/chunks/{offset}` | DocumentUploadChunk1 | DocumentUploadChunkReceipt1 | owner, writer |
| upload | POST `document-uploads/{upload_id}/complete` | DocumentCommand1 | DocumentOperation1 | owner, writer |
| upload | GET `document-uploads/{upload_id}` | DocumentEmpty1 | DocumentUploadStatus1 | owner, writer, reader |
| operation | GET `document-operations/{operation_id}` | DocumentEmpty1 | DocumentOperation1 | owner, writer, reader |
| library | GET `documents` | DocumentListQuery1 | DocumentList1 | owner, writer, reader |
| library | GET `documents/{document_id}` | DocumentEmpty1 | Document1 | owner, writer, reader |
| library | GET `documents/{document_id}/versions` | DocumentPageQuery1 | DocumentVersionList1 | owner, writer, reader |
| library | GET `document-versions/{version_id}` | DocumentEmpty1 | DocumentVersion1 | owner, writer, reader |
| original | GET `document-versions/{version_id}/original` | DocumentOriginalQuery1 | DocumentByteDescriptor1 | owner, writer, reader |
| original | GET `document-versions/{version_id}/fragments` | DocumentFragmentQuery1 | DocumentFragment1 | owner, writer, reader |
| metadata | PATCH `documents/{document_id}` | DocumentMetadataPatch1 | DocumentOperation1 | owner, writer |
| metadata | POST `documents/{document_id}/archive` | DocumentArchiveChange1 | DocumentOperation1 | owner, writer |
| metadata | POST `documents/{document_id}/unarchive` | DocumentArchiveChange1 | DocumentOperation1 | owner, writer |
| collection | POST `document-collections` | DocumentCollectionCreate1 | DocumentOperation1 | owner, writer |
| collection | GET `document-collections` | DocumentPageQuery1 | DocumentCollectionList1 | owner, writer, reader |
| collection | GET `document-collections/{collection_id}` | DocumentEmpty1 | DocumentCollection1 | owner, writer, reader |
| collection | PATCH `document-collections/{collection_id}` | DocumentCollectionPatch1 | DocumentOperation1 | owner, writer |
| collection | DELETE `document-collections/{collection_id}` | DocumentCollectionDelete1 | DocumentOperation1 | owner, writer |
| collection | GET `document-collections/{collection_id}/members` | DocumentPageQuery1 | DocumentMemberList1 | owner, writer, reader |
| collection | POST `document-collections/{collection_id}/members` | DocumentCollectionMembersChange1 | DocumentOperation1 | owner, writer |
| extraction | POST `document-versions/{version_id}/extractions` | DocumentExtractionCreate1 | DocumentOperation1 | owner, writer |
| extraction | GET `document-versions/{version_id}/extractions` | DocumentPageQuery1 | DocumentAttemptList1 | owner, writer, reader |
| extraction | GET `document-extractions/{attempt_id}` | DocumentEmpty1 | DocumentExtractionAttempt1 | owner, writer, reader |
| extraction | GET `document-extractions/{attempt_id}/result` | DocumentEmpty1 | DocumentExtractionResult1 | owner, writer, reader |
| extraction | POST `document-extractions/{attempt_id}/retry` | DocumentExtractionRetry1 | DocumentOperation1 | owner, writer |
| search | GET `document-search` | DocumentSearchQuery1 | DocumentSearchResult1 | owner, writer, reader |
| annotation | GET `document-versions/{version_id}/annotations` | DocumentPageQuery1 | DocumentAnnotationList1 | owner, writer, reader |
| annotation | POST `document-versions/{version_id}/annotations` | DocumentAnnotationCreate1 | DocumentOperation1 | owner, writer |
| annotation | GET `document-versions/{version_id}/annotations/{annotation_id}` | DocumentEmpty1 | DocumentAnnotation1 | owner, writer, reader |
| annotation | PATCH `document-versions/{version_id}/annotations/{annotation_id}` | DocumentAnnotationRevise1 | DocumentOperation1 | owner, writer |
| annotation | DELETE `document-versions/{version_id}/annotations/{annotation_id}` | DocumentAnnotationDelete1 | DocumentOperation1 | owner, writer |
| citation | POST `document-citations/preview` | DocumentCitationCandidate1 | DocumentCitationPreview1 | owner, writer |
| usage | GET `document-versions/{version_id}/usage` | DocumentPageQuery1 | DocumentUsageList1 | owner, writer, reader |
| delete | POST `document-deletions/preview` | DocumentDeleteSelection1 | DocumentDeletePreview1 | owner |
| delete | POST `document-deletions/commit` | DocumentDeleteCommit1 | DocumentOperation1 | owner |
| delete | GET `document-deletions/{operation_id}` | DocumentEmpty1 | DocumentOperation1 | owner |
| export | POST `document-exports/preview` | DocumentPortablePreviewRequest1 | DocumentPortablePreview1 | owner, writer, reader |
| export | POST `document-exports` | DocumentPortableCreate1 | DocumentOperation1 | owner, writer, reader |
| export | GET `document-exports/{operation_id}` | DocumentEmpty1 | DocumentOperation1 | owner, writer, reader |
| export | GET `document-exports/{artifact_id}/download` | DocumentEmpty1 | DocumentPortableDownload1 | owner, writer, reader |
| import | POST `document-imports` | DocumentImportBegin1 | DocumentImportUploadStatus1 | owner, writer |
| import | PUT `document-imports/{upload_id}/chunks/{offset}` | DocumentImportChunk1 | DocumentImportChunkReceipt1 | owner, writer |
| import | POST `document-imports/{upload_id}/complete` | DocumentImportCommit1 | DocumentOperation1 | owner, writer |
| import | GET `document-imports/{operation_id}` | DocumentEmpty1 | DocumentOperation1 | owner, writer |
| restore | POST `document-restores` | DocumentRestoreRequest1 | DocumentOperation1 | operator |
| restore | GET `document-restores/{operation_id}` | DocumentEmpty1 | DocumentRestoreResult1 | operator |

`DocumentError1` references the closed `Error` envelope without modifying it: `request_id`, `command_id`, `resource_id`, `current_revision`, `fields` and `outcome` keep their meaning. Codes include `invalid_request`, `unauthenticated`, `forbidden`, `resource_not_found`, `stale_revision`, `command_payload_conflict`, `reference_conflict`, `limit_exceeded`, `backend_unavailable`, `operation_pending` and `dispatch_uncertain`. Runtime failures such as `source_unavailable`, `deletion_blocked` and `reupload_required` are bounded `DocumentFailure1` receipt reasons mapped to an existing public code and outcome; there is no second public error wrapper. A pending or unknown disposition is explicit, never a 200 empty list.

`POST document-citations/preview` resolves one typed source candidate. The full target-aware evidence preview with document citations is `POST /api/1/studies/{study_id}/evidence-citations/preview` (section "Evidence with document citations").

## Byte transfer and publication

Begin durably reserves the command identity, public IDs, exact original metadata and a transient scoped lease. Adding a version requires both `family_id` and `expected_revision`; a new family supplies neither. A chunk PUT has a raw body, the exact path offset, the declared `byte_length` and a SHA-256 header; `DocumentUploadChunk1` types that metadata, and body bytes are bounded independently while streaming. An offset duplicated by the transport must agree. No general binary-body exception is added to unrelated JSON routes.

Chunks are at most 256 KiB. The same offset with identical bytes is an idempotent retry; gaps, overlap mismatch, changed length or digest, or excess bytes fail without effect even without `Content-Length`. Completion names the original command and reserved upload, requires the contiguous exact length and full SHA-256 agreement, then queues native work. Empty admitted text can complete without any chunk; media validity is checked independently. An interrupted upload is never visible as a source. A lost spool with no native commit is `failed` with `reupload_required`.

The internal `transfer_id` is an opaque server-reserved handle resolved beneath the scoped transient spool, never a client path or reusable public URL. Native storage and readback validate the exact original before application publication. One successful logical command yields one version and one original; independent explicit commands may keep identical bytes independently. Every read validates hash, length and current authorization, including pending replies and cache hits. Downloads use a safely encoded attachment filename, `nosniff` and `no-store`. The original body stays inert: no inline uploaded HTML, Markdown or PDF, no render execution and no source-code import.

Public original downloads may stream the entire 10 MiB source or a bounded range. Internal base64 replies carry at most 262,144 decoded bytes (349,528 encoded characters) with exact descriptor metadata. Strict base64 decoding, payload length and hash, and range containment are runtime obligations, not consequences of a pattern match.

**Import.** Import begin returns `DocumentImportUploadStatus1`: the reserved `upload_id` and `operation_id`, expected and received bytes, SHA-256, expiry and operation state. It does not reserve a single source family or version for a multi-resource archive. Chunks and completion use the returned `upload_id`; status uses the returned `operation_id`. The original `command_id`, route and body `upload_id`, archive hash and length and the durable lease must agree; a repeated begin returns the same reservation after current authorization. Import chunks use the same protocol with the larger portable limits.

## Fixed bridge

| Mode / verb | Input | Result |
|---|---|---|
| document-read / descriptor | DocumentVersionKey1 | DocumentVersion1 |
| document-read / list | DocumentNativeList1 | DocumentNativeListResult1 |
| document-read / member | DocumentNativeMemberRead1 | DocumentMemberList1 |
| document-read / annotation | DocumentNativeAnnotationRead1 | DocumentAnnotation1 |
| document-read / fragment | DocumentNativeFragmentRead1 | DocumentFragment1 |
| document-read / original | DocumentNativeOriginalRead1 | DocumentNativeOriginalReply1 |
| document-read / status | DocumentNativeStatus1 | DocumentNativeStatusResult1 |
| document-write / store_original | DocumentNativeStoreOriginal1 | DocumentVersion1 |
| document-write / collection_create | DocumentNativeCollectionCreate1 | DocumentCollection1 |
| document-write / collection_update | DocumentNativeCollectionUpdate1 | DocumentCollection1 |
| document-write / collection_members | DocumentNativeCollectionMembers1 | DocumentCollection1 |
| document-write / collection_delete | DocumentNativeCollectionDelete1 | DocumentCollectionDeleted1 |
| document-write / annotation_create | DocumentNativeAnnotationCreate1 | DocumentAnnotation1 |
| document-write / annotation_revise | DocumentNativeAnnotationRevise1 | DocumentAnnotation1 |
| document-write / annotation_delete | DocumentNativeAnnotationDelete1 | DocumentAnnotationDeleted1 |
| document-write / extraction_start | DocumentNativeExtractionStart1 | DocumentExtractionAttempt1 |
| document-write / source_delete_preview | DocumentDeleteSelection1 | DocumentDeletePreview1 |
| document-write / source_delete | DocumentDeleteCommit1 | DocumentDeletionResult1 |
| document-write / export | DocumentPortableCreate1 | DocumentPortableArtifact1 |
| document-write / import | DocumentImportCommit1 | DocumentImportResult1 |
| document-write / restore | DocumentRestoreRequest1 | DocumentRestoreResult1 |
| document-write / reconcile | DocumentOperationKey1 | DocumentNativeWitness1 |

Read frames bind the current authorized study and `request_id`; replies echo both and the fixed verb. List and status results also carry a closed resource discriminator, so an empty collection list cannot be confused with empty versions. Write frames carry the server-derived `DocumentCommandIdentity1`. Every reply is correlated with the full original identity, digest, reserved IDs and store before use. A write result is either the named type or the typed error. Metadata and archive are application-authoritative commands and do not invent native metadata ownership.

The seven read verbs and fifteen write verbs are the entire admitted set: no generic method, HTTP path, profile selection, native script, launch, submit, resume or cancel. The managed read loop has a fixed process identity, lock and a lifecycle that ends when its supervising process exits and no scientific dispatch capability. Native writes stay serialized through the single writer, including extraction admission. The API and the modeling service hold no native profile, database, host launcher or socket credentials. Waiting mutations report "Waiting for native storage". Responsiveness while scientific work runs, writer exclusion and shutdown with the supervising process are runtime properties to verify; this contract is not evidence of them.

**Creation identities.** Public collection and annotation create bodies reject client-supplied creation IDs. The internal `DocumentNativeCollectionCreate1` carries `collection_id` plus the request; `DocumentNativeAnnotationCreate1` adds `annotation_id` beside `version_id` and the request. The application reserves the creation ID once before dispatch; native input, result, association, the immutable witness's `reserved_ids` and the application operation all carry that exact identity. The request `command_id` equals the frame's `identity.command_id`. Witness lookup precedes new allocation, compare-and-set and visibility; replay returns the exact original result, never a replacement ID.

**Extraction start.** `DocumentNativeExtractionStart1.kind` is required: `initial` accepts only the create input; `retry` accepts only the retry input with `prior_attempt_id`. The server resolves the authorized retry route to that same predecessor and its exact source and policy, checks retry eligibility and reserves a distinct new command and attempt. An initial result has `retry_of: null`; a retry result has `retry_of` equal to `prior_attempt_id`. The immutable witness and replay keep the complete attempt.

## State and reconciliation

The registry holds complete operation and extraction transition tables. `DocumentOperationTransition1` encodes admitted transitions and proof labels; proof verification and atomic application are runtime work. There is no outbound transition from published, failed or expired operation states or from terminal extraction states. A failed-processing retry creates a **new** attempt and command. A proven-uncommitted interrupted operation may be retried with its ID only after the earlier writer is excluded and absence of effect is proven.

Uploads begin `receiving`, then `queued → running → committed → published`. Other mutations begin `queued`. Running failures end `failed`, `interrupted` or `uncertain` with bounded reasons. `committed` requires an exact result; `published` means verified application publication. `uncertain → committed` needs the category's proof object; `uncertain → failed` needs proof that no effect was applied. A timeout alone never gives either proof or permission to retry. Category, result type, reserved IDs, state and revisions must agree at runtime.

**Commit proofs.** A transition to `committed` from `running`, `interrupted` or `uncertain` carries the category and a complete proof object. Native categories use `verified_native_witness` with the witness; metadata and archive use `verified_app_transaction` with `app_commit`. The alternatives are disjoint, require matching nested categories and reject the other authority's fields. Native transitions also constrain the witness result to the category's resource type. `DocumentAppCommit1` holds the exact command identity and digest, category, reserved `document_id`, the full resulting `Document1` and the previous and resulting revisions; it has no native store, node or association fields. Metadata or archive compare-and-set, the family mutation and this receipt commit atomically in the application transaction. After a lost reply, current authorization precedes exact receipt lookup, which precedes current-family compare-and-set; replay returns the recorded result even after later edits. Missing or conflicting proof stays unresolved.

Current authorization precedes receipt lookup. Within the writer boundary, the exact immutable witness is looked up **before active visibility and compare-and-set**. The same command identity and payload returns its original immutable outcome; a changed payload, including `expected_revision`, conflicts. Several or mismatched witnesses are `uncertain`. Zero matches permit execution only after the earlier writer is excluded and absence is shown. Recovering original uploads verifies bytes separately; replaying historical collection outcomes does not require former members' bytes to still exist.

Extraction separates the native wrapper lifecycle from the outcome. A finished calculation function may report failed or partial extraction. The actual original and configuration input links and the text and manifest output links must exist; completed processes and semantic scientific links are never forged. The original stays downloadable, subject to current authorization, through every extraction state. Partial or truncated pages expose coverage; image-only pages need transcription; encrypted PDFs are unsupported; no confidence is invented. An `uncertain` extraction can reconcile to `unsupported` or `needs_transcription` as well as the other terminal outcomes: `DocumentExtractionReconciliation1` requires the exact stored `ExtractionResult1` and `verified_exact_retained_result`, and its outcome must match the destination. Runtime verifies original, configuration, process and result associations, attempt, version and study IDs, manifest and artifact hashes and coverage before applying it; missing or conflicting bytes stay `uncertain`. These outcomes are terminal, keep the original downloadable and never imply an automatic retry.

## Exact locators and source semantics

- `original_file` binds the exact original. An optional `section_label` is human and unverified; no extraction or machine-verified quote is allowed.
- `pdf_page` is a physical 1-based page within a successfully established page inventory. Page 500 is structurally valid only; a two-page original rejects it at runtime. Without an inventory, use `original_file`.
- `extracted_span` binds the exact extraction and artifact UUIDs and the artifact SHA-256, with a half-open Unicode code point range `[start, end)`. Bounds, source association, artifact digest and optional derived line labels are server-validated. Browser UTF-16 offsets are converted and checked. The server computes the substring and the SHA-256 of its UTF-8 encoding; client quotations are not authoritative.

JSON Schema cannot compare fields, so a fixture with reversed start and end is structurally admissible; runtime enforces `0 ≤ start < end ≤ artifact length` and the exact associations. A quote of at most 4,096 code points is distinct from fragment UTF-8 bytes and source file size. `DocumentSourceDescriptor1` is the preview source snapshot. Source availability never asserts scientific validity.

## Collection deletion and source fences

Collection delete removes **all current members, up to 10,000**, advances the revision once, marks the Group deleted and stores one immutable terminal witness in one supported transaction. The 100-member edit limit never truncates deletion. Deletion uses supported member removal, never physical Group deletion or a premature clear. Deleting an empty collection still advances the revision once. The empty terminal Group cannot be reactivated or reused. No physical cleanup, sweeper or secure erasure is claimed.

Native queries filter on active lifecycle **before** pagination, counts, member lists, search, pickers and badges. A deleted-collection filter returns not found, never broadens to all documents. A malformed lifecycle, absent or conflicting terminal witness, or non-empty tombstone fails closed as an integrity error. Replaying an exact historical create, edit or delete never republishes an active association. Originals and other collections are untouched by collection removal or deletion.

Source deletion is a separate destructive path. In one application transaction it creates a fence for the explicit exact versions and reserves against new admissions from citations, evidence, configurations, approaches, exports and collection create, add or replace. It checks **all** stored non-head evidence, configurations, approaches, runs, portable jobs and results and every queued, running, committed-unpublished or uncertain reservation. Active memberships block deletion; removing members may lift that, and adding versions requires reservations. Both interleavings serialize, and uncertainty never releases a reservation.

The native writer rechecks the exact source and provenance closure and memberships immediately before deleting. Foreign, shared, unknown or scientific descendants block; immutable receipts survive. Only a confirmed native disposition permits tombstones. A refusal or proven non-application clears the fence atomically; an ambiguous outcome keeps it. Preview closure tokens are advisory until the authorization, revision and closure checks repeat at commit.

## Limits and parser boundary

All numeric ceilings are in the machine-readable registry. Bytes mean bytes; code points mean Unicode code points, not JavaScript string length.

| Limit | Value |
|---|---|
| original_bytes | 10485760 |
| chunk_bytes | 262144 |
| pdf_pages | 500 |
| page_text_bytes | 262144 |
| total_text_bytes | 8388608 |
| filename_codepoints | 200 |
| title_codepoints | 200 |
| description_codepoints | 4096 |
| note_codepoints | 4096 |
| notes_per_version | 100 |
| tags | 20 |
| tag_codepoints | 64 |
| list_rows | 100 |
| members_per_mutation | 100 |
| collection_members | 10000 |
| search_codepoints | 256 |
| snippet_codepoints | 512 |
| quote_codepoints | 4096 |
| citations_per_evidence | 20 |
| incomplete_uploads_per_study | 4 |
| staged_bytes_per_study | 104857600 |
| active_extractions_per_installation | 1 |
| spool_retention_seconds | 86400 |
| response_cache_seconds | 300 |
| parser_wall_seconds | 30 |
| parser_cpus | 1 |
| parser_memory_bytes | 536870912 |
| parser_pids | 64 |
| parser_scratch_bytes | 67108864 |
| portable_compressed_bytes | 104857600 |
| portable_expanded_bytes | 268435456 |
| portable_entries | 10000 |
| portable_originals | 100 |

Admitted originals are PDF, strict UTF-8 text, Markdown and CSV. Other media types, `application/octet-stream` and executable formats are not admitted by this version. A media type, header or extension mismatch fails or receives an explicit unsupported classification; nothing is executed. CSV gets no automatic scientific table interpretation. Text newlines are normalized to LF in extracted text; original bytes stay exact. The PDF extractor pins `pypdf 6.20.0`; built-in text decoding pins `hyprn-mvp-utf8/1`. Both record exact parser image and configuration digests. The isolated parser image enforces every ceiling before page counting or decompression: non-root, read-only root and input, no network, secrets, native profile, application database or socket, no capabilities, no-new-privileges, bounded scratch and output, and an external timeout with descendant cleanup. Containment is proven on the adopted image before processing is offered.

Scope quotas (notes, uploads, staged bytes, active extractions) and aggregate byte sums are runtime checks. The collection count is bounded by installation policy; its configured maximum is exposed and checked by the owning admission code, never inferred from 100-row pagination. A limit failure never silently splits one atomic command. Transient spool and replies expire within 24 hours and the response cache within 5 minutes; current authorization still runs on every delivery.

## Portability and restoration

Exports select exact original and evidence IDs; collection and annotation snapshots are optional explicit selections. An active collection snapshot freezes identity, revision and the intersection with the selected members. Terminal Group and witness data are kept only as origin or backup evidence, never as an active destination collection or destination command authority. No whole Group or profile export is implied.

The envelope inventories exact role, path, size and hash, scopes, the native node and link closure, original, derived, configuration and outcome data, and application mappings. Traversal, absolute paths, duplicate names, symlinks, expansion bombs, missing or extra files, undeclared binaries and mismatched links or hashes are rejected before publication. Originals are byte-safe within their declared media role, never a global bypass for sensitive content. Authentication, profile and connection data and executable checkpoints are excluded.

Import is data-only into a destination-authorized isolated scope, quarantined until the closure is verified. Immutable origin descriptors are kept; destination mappings are separate. Native processes are never reconstructed, resumed or launched. Crash reconciliation binds one import receipt to the envelope digest. Restore requires one coordinated generation across all writers (application, native, scientific, citation, collection, annotation, import and export); sequential uncoordinated store copies are not a backup. A partial copy stays unusable. Current populated stores are never overwritten.

## Structural checks versus runtime verification

The schemas prove closed fields, version incompatibility, distinct locator modes, literal accepted and rejected snapshots, duplicate objects, bounds, disjoint mixed branches and unchanged prior definitions. The following obligations need runtime tests:

- **current_authorization**: current session and centralized study authorization precede every lookup and delivery; reauthorize before dispatch, publication, cache use and byte delivery. Native receipts are never access grants.
- **scope_association**: public resource, study, native store and node match the authoritative association; unknown and foreign IDs are indistinguishable.
- **revision_cas**: for a new command, the current revision equals `expected_revision`; a refusal leaves state and witnesses unchanged.
- **canonical_command_digest**: the canonical complete command is bound to actor, study, operation, reserved IDs and store; the same ID with a changed payload conflicts; several witnesses stay uncertain.
- **span_bounds_and_hash**: `0 ≤ start < end ≤` artifact code point length; same version, extraction, artifact and hash; a safe known PDF page inventory; derived line labels; server UTF-8 slice and hash; browser UTF-16 indices converted.
- **byte_length_and_hash**: original, chunk, extracted and decoded bytes counted; every SHA-256 and offset validated; contiguous complete upload; `Content-Length` never trusted. `utf8_bytes` matches the encoded text.
- **delete_fences**: one application transaction reserves the exact source set and blocks new citation, configuration, approach, export and membership admissions, inspecting non-head, pending and uncertain usages; the native serialized closure recheck precedes deletion; uncertain outcomes keep the fence.
- **replay_before_visibility_and_cas**: authorize, then look up the exact immutable witness before active visibility and compare-and-set; a historical outcome never reactivates a terminal collection; zero witnesses permit retry only after the earlier writer is excluded and absence is shown.
- **terminal_integrity**: the empty terminal Group, revision and immutable witness commit atomically; missing or malformed lifecycle or witness, non-empty terminal state and conflicting receipts are rejected; native active filtering precedes pagination, counts and search.
- **publication**: publish only after exact native readback and byte validation; an operation is not a scientific run; results match category, reserved IDs and operation state; transitions need proof, never an optimistic timeout retry.
- **cursor_binding**: an opaque signed cursor binds scope, query, filters and revision; invalid or deleted collection filters are rejected without broadening; counts and snippets are authorized.
- **parser_containment**: fixed image and configuration, strict UTF-8 and newline policy, real native input and output provenance, external resource limits applied before parsing; a finished wrapper does not imply successful extraction.
- **portable_closure**: explicit selection only, typed role inventory; missing or extra paths and hashes, traversal, symlinks, zip bombs, unknown binaries, credentials and executable checkpoints rejected; native import stays data-only and quarantined until destination authorization and full closure.
- **backup_barrier**: a verified empty destination and one coordinated generation across all writers; a partial copy is unusable; imported witnesses are origin data, never destination command authority.
- **bridge_isolation**: the read loop has fixed verbs only and write mode a single writer; neither launches science; no application, model, profile, launcher or socket credentials; handles are server-resolved scoped expiring transfers, never filesystem paths.

`test_documents_contract.py` validates literal wire fixtures, rejection of unknown, mixed and native-capability fields, limits, locator distinctions, finite bridge modes, empty-result discrimination, state shapes, error-envelope compatibility and exact preservation of prior definitions. It does **not** establish authorization, compare-and-set or digest comparisons, native atomicity, extraction containment, source deletion, backup consistency or HTTP delivery.

## Evidence with document citations

These scientific record types are allocated in the schemas for document citations. Existing evidence, configuration, bundle, history and seed types are unchanged, including every older read alias; consumers select the new read unions explicitly. Evidence4 is never appended to an older nested alias, because that would make older configuration or closure types accept new meanings indirectly. `x-hyprn-mvp-documents-contract.scientific_allocations` records the additive types, exact pairings and the commit barrier.

### Evidence intent, preview and immutable record

`EvidenceCreate4` and `EvidenceRevise4` keep title, content, kind, resource scope and unverified `source_refs`, and add up to 20 unique `DocumentCitationCandidate1` values, `expected_context_revision` and `expected_preview_digest`. Revise keeps the exact expected predecessor evidence version. Candidates contain exact public IDs, the locator, the relationship and an optional annotation revision only; they cannot carry a source hash, native identity, server quote or full frozen descriptor.

`EvidenceCitationPreviewRequest4` contains the complete authoring intent without command or digest authority; `evidence_id` and `expected_revision` are paired only for a revision preview. `EvidenceCitationPreview4` returns request and preview digests, expiry, target scope and context revision, predecessor version, recorded context and the complete resolved citations. It supplements the single-source `DocumentCitationPreview1`, whose route body keeps its meaning. The route is `POST /api/1/studies/{study_id}/evidence-citations/preview`, with the evidence authoring role policy, CSRF and current study authorization.

`DocumentCitation1` freezes the same-study document, family and version identity; original hash, byte size and media type; title and filename; exact extraction ID and manifest digest and the extractor name, version, image, configuration and policy; the locator; the server-derived quotation and its UTF-8 hash; the complete attributed annotation snapshot (or null); and the supports, challenges or contextualizes relationship. `citation_id` is the SHA-256 of the canonical complete descriptor excluding its own ID. Stored evidence supplies the evidence identity, scientific target and recorded context. No original file bytes enter the descriptor.

- Original-file citations carry no extraction or machine quote; any section label stays human and unverified.
- PDF-page citations require PDF media and a validated physical page inventory. Optional extraction ID, digest and extractor form one complete group; page-only citations carry no verified quote.
- Extracted spans require complete extraction pins and a non-empty server quote and hash, over half-open Unicode code point bounds. Runtime verifies that locator, extraction and artifact identities agree and hashes the exact UTF-8 substring; JSON Schema cannot prove those equalities.
- Later annotation edits cannot change a frozen descriptor; its copied locator, text, tags, revision and attribution stay historical data.
- Exact duplicate candidates or records are rejected by `uniqueItems`; runtime also rejects a repeated source, version, locator and annotation revision even when another field or the relationship differs. Conflicting identities are never collapsed silently.

`EvidenceRecord4` and `EvidenceSnapshot4` have the same full immutable shape. `EvidenceCreateRead4`, `EvidenceReviseRead4`, `EvidenceRecordRead4` and `EvidenceSnapshotRead4` combine the supported older and new contracts. `EvidenceFamily4` and `EvidencePage2` carry the new record union; older family and page types are unchanged. `AssumptionEvidenceResolution2` changes only its envelope version and nested evidence union, keeping exact draft-versus-model-version discrimination and resolved or unavailable links. Model1–3 already hold evidence version references, so no new model, portable record or port version is needed.

### Exact scientific pairings

| Selected model and approach | Full / private configuration | Frozen | Bundle | History | Modified seed |
|---|---|---|---|---|---|
| Model3; no pin, or an exact closure | Configuration5 / private4 | FrozenConfiguration6Model3 | ExecutionBundle7Model3 | RunHistory5Model3 | ModifiedRunSeed5Model3 |
| Model2; no pin, or a closure containing only Model1/2 | Configuration5 / private4 | FrozenConfiguration6Model2 | ExecutionBundle7Model2 | RunHistory5Model2 | ModifiedRunSeed5Model2 |
| Exact selected Model2 with a valid pin and an explanatory Model3 closure | Configuration5 / private4 | FrozenConfiguration6Model2WithModel3 | ExecutionBundle7Model2 | RunHistory5Model2WithModel3 | ModifiedRunSeed5Model2WithModel3 |

Each frozen, history and seed family is a disjoint union of these branches. Model1 gets no new Configuration5 pairing; its older records stay readable. Model2 never acquires typed-unit meaning from an explanatory Model3. A mixed closure requires exact selected-model membership, binding, source and digest equality and scientific reachability beyond structural acceptance. Unused or explanatory unresolved declarations do not block the selected executable model. Only a selected Model3 requires the typed unit catalog and capability. The existing Configuration4/private3 → Frozen5/Bundle6/History4/Seed4 pairings are untouched.

`ConfigurationRequest5`, `Candidate5`, `Revision5`, `Preview5` and `Commit5` keep the request-versus-resolved separation, assumptions, result dependencies, context choice and approach selection. Full 5 and private 4 are new because `evidence_snapshots` can now contain Evidence4. The private projection removes `approach_binding`, `context_source`, `derivation`, `assumptions`, `general_context_evidence_version_ids`, every input `result_binding` and the two application-only capabilities `result_linked_inputs/1` and `configuration_assumptions/1`, sets private `schema_version` 4 and keeps every other field, including complete context and Evidence4 descriptors. The private immutable digest is recomputed excluding `digest`; the full application digest is kept separately. Citations are never dropped to make an older private format validate.

`ApproachClosure2` and `ApproachResolution2` carry `ConfigurationRevisionRead5` and `EvidenceSnapshotRead4`. Approach version, content, binding and run-context identities do not change. The incompatible wrappers are `ApproachSaved2`, `ApproachVersionSaved2` and `ApproachPreview2`. `ApproachClosureRead2` accepts exactly the older version 1 or the new version 2; Model2-only and WithModel3 sub-unions distinguish older and document-bearing closures. An older closure's version or digest is never rewritten because a new run references it. Response and receipt wrappers are generated deliberately with the public contract; unversioned resolution containers need explicit context-based selection rather than an ambiguous `oneOf` when empty.

The new read names are `ConfigurationCandidateRead5`, `ConfigurationRevisionRead5`, `ConfigurationRequestRead5` (requests 2–5; the earlier candidate 1 stays its own public branch), `ConfigurationPreviewRead5`, `ConfigurationCommitRead5`, `FrozenConfigurationRead6`, `ExecutionBundleRead7`, `RunHistoryRead5` and `ModifiedRunSeedRead5`. Existing aliases stay closed to their historical set; public generated route aliases switch explicitly, keeping their earlier candidate 1 branch and any public metadata.

`ExecutionBundle7` keeps the `BundleFileV5` roles, separate full, private and result-dependency files, an optional exact `approach/closure.json`, prepared, executable, runtime and lock hashes and program protocol 1. Selected-model capability vectors distinguish Model3 and Model2; raw manifest validation cannot inspect referenced JSON, so every reader authenticates the actual bytes and validates the full, private, model and closure combination. PDF, original and derived document bytes stay in native document storage and the explicitly selected portable closure; none enters modeling preparation or a scientific bundle. A semantic evidence citation creates no numerical upstream data link. `PreparedModelArtifact2`, the generated program, bindings and source-line mapping (version 1), `RetainedResults1` and `ResultDependencies1` are unchanged.

`RunHistory5` keeps null or unverified fields and honest read errors; the null-model partial case belongs only to the Model3 alternative to avoid `oneOf` ambiguity and does not assert that a missing model was Model3. `retained_integrity` stays optional `PublicRunDetail` metadata produced from the same authorized history read; it is not added to `RunHistory5`, stored payloads or digest inputs, and its verified pairing table extends to the new 5/7/5/2 and 5/7/5/3 combinations with the same null and absent semantics. `ModifiedRunSeed5` keeps the exact source configuration, evidence and approach pin until an explicit previewed change; it never reruns a record automatically.

### Consumers that adopt these types

Until each consumer below is implemented and verified, the generator and private transport keep refusing the new shapes.

| Area | Required change |
|---|---|
| Application `store` and evidence routes | Closed create and revise 4 → resolver proof → `EvidenceRecord4`; exact predecessor and context compare-and-set; new family and page read shapes; no client-supplied frozen snapshot |
| `scientific_configuration` | Admit full 5 and the deterministic private 4 projection with exact Evidence4 snapshots and separate canonical digests; keep the 1–4 mappings |
| `configuration` | Request, candidate and revision 5; full snapshot 4 preserved; private 4 support advertised; source-fence reservations; the new frozen branch |
| Modeling contract (`modeling.openapi.yaml`, a dedicated adapter patch, `modeling/tests`) | Explicit private 4 request and revision admission and capability; static preparation keeping descriptor bytes; no parser, source fetch or model-version promotion. Existing compatibility and preparation definitions stay unchanged until a new binding is assigned |
| `result_bindings` | Configuration 5 as source and destination, full, private and citation hashes, exact units, values and zero, current authorization; older sources keep their original rules |
| `execution`, `execution_bundle` | Explicit full 5 / private 4, Frozen6 and Bundle7 admission, raw payload version, digest and role equality, selected-model readiness and the common source reservation |
| `approach_closure` | Dispatch on closure version 1 or 2, nested full 5 and Evidence4 validation, reachability and digest reconstruction using the actual closure version |
| `approach` | `EvidenceRecordRead4` plus the new resolution, preview and saved wrappers; source rechecks inside the publication transaction. **Open:** this consumer needs an assigned implementation owner before approach support is functional |
| `modeling` (model assumption evidence) | `EvidenceRecordRead4` and `AssumptionEvidenceResolution2` with exact saved or draft selection and scoped unavailable behaviour. **Open:** needs an assigned owner before contextual citations are delivered; it is an application projection, not a private-model graph change |
| `history`, `modified_runs` | Choose History5 from the actual frozen and bundle versions with exact error and null fields and no modeling lookup; Configuration 5 eligibility and Seed5 |
| `dispatcher` | Transport exact descriptors and raw bytes on the existing bounded operations; no general native path, source fetch or scientific privilege |
| Integration `results`, `calculation`, `worker`, `launcher` | Explicit Bundle7 readers, Config5 → private 4 reconstruction and equality, closed Evidence4 citation keys and hashes, closure 2 digest reconstruction and the selected-model matrix, all before loading candidate code; the worker keeps no parser, lookup or credential. A citation is not a numerical dependency |
| Computational record export (application and integration) | Explicit document policy, envelope 3, Bundle7 and closure 2 consumers; role, hash, scope and byte closure; export reservations under the source fence; import stays data-only |
| `application/generate_contract.py` → `hyprn-mvp.openapi.yaml` → `ui/src/contract.ts` | Generate explicit unions of supported older and new types for actual routes; add the Evidence4 preview, Config5, Frozen6, History5, Seed5, assumption 2 and approach 2 contracts; keep optional `retained_integrity` unchanged; generated types and typed API methods without unknown casts or direct fetches |
| UI evidence, configuration and approach screens | Consume the new snapshot and read types and exact source navigation, keeping unverified source text and unavailable states. **Open:** every screen that consumes the older closure, saved, resolution, configuration-version or evidence-snapshot read types needs typed propagation before acceptance; the older shared aliases are not broadened |

### Commit, deletion and retention boundary

Evidence preview is advisory. In the **same application write transaction** as evidence, configuration, approach or export publication: reauthorize actor, study, target and each source; compare the exact predecessor, context and preview digests; verify published immutable source associations and complete descriptors; reserve every referenced exact source version; reject deletion-pending, unknown or uncertain source state. A changed source descriptor or annotation revision requires a new preview, never a silent refresh. A lost reply replays the exact authorized command result; it never resolves mutable heads anew.

Source deletion establishes its fence in the same transaction domain and checks all stored non-head evidence, configurations, approaches, runs and pending, committed-unpublished or uncertain reservations, plus native memberships. Either the source reservation comes first and blocks the deletion, or the deletion fence comes first and blocks the new reference. The native serialized closure recheck and a durable disposition still precede application tombstones; uncertainty keeps reservations and fences. Authorized historical reads and archived source identity stay exact. The coordinated all-writer backup generation includes these admissions as well as scientific completion, import and export. There is no second source or membership authority or database.

Schema fixtures prove closed fields, version incompatibility, distinct locator modes, literal accepted and rejected older and new snapshots, duplicate objects, bounds, disjoint mixed branches and unchanged prior definitions. They do not prove equal IDs across fields, canonical digest equality, duplicate identity with differing bytes, Unicode slices, authorization, compare-and-set, runtime source reservations, worker admission or liveness; those remain runtime tests.
