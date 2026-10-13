# Phase 4: Documents - Context

**Status:** Ready for planning

<domain>
## Phase Boundary

Within a study, an engineer uploads source documents (PDF, UTF-8 text, Markdown, CSV), organizes exact versions in collections, reads and searches the extracted text in a text-first reader, annotates passages, cites a passage, page or original from evidence, and reopens an old run with the exact cited source, even while the modeling service is down. Bytes, collections and annotations live in AiiDA; identity, study scope, citations and evidence semantics live in HYPRN MVP. Everything works manually in the UI; nothing depends on an agent.

Scope is steps 1–13 of `docs/specs/documents.md` §12, in dependency order. Start by verifying the existing native-originals adapter (`hyprn_mvp_integration.documents.NativeDocuments`) and its tests against `contracts/documents.md`.

| # | Step | Done when |
|---|---|---|
| 1 | Native collections and working annotations | Two collections share one original; stale edits change nothing; logical terminal deletion with replay before visibility |
| 2 | Bridge verbs; managed read loop | Read mode cannot launch science; reads complete during a deliberately blocked run |
| 3 | Upload and library API routes | Chunks → native bytes → published version → exact download after restart |
| 4 | Library UI | Upload, list, versions, download and every recovery state in the browser |
| 5 | Collections API and UI | One version in two collections; head changes never move members |
| 6 | Parser image | Pinned digest; containment demonstrated, otherwise extraction stays unavailable |
| 7 | Extraction | Repeatable locators; partial, unsupported and needs-transcription outcomes |
| 8 | Processing provenance; search | Real provenance; exact snippets with honest coverage |
| 9 | Reader and search UI | A search hit opens the exact passage |
| 10 | Annotations, citation resolver, evidence version 4 | Annotation edits cannot change stored evidence |
| 11 | Configuration chain | Citations survive preparation without widening earlier contracts |
| 12 | Frozen history | An old run opens its cited source during a modeling outage |
| 13 | Scientific evidence UI | All five citation paths of §15.4 reach the exact source |

Not in this phase (see PD-4.1): deletion fences and permanent deletion of source versions, portable export and import, restore and the backup drill, the lifecycle and export UI, the full end-to-end acceptance walk (steps 14–18). Agent document tools (§13) come after this phase. Authored documents and co-editing (§14) are a separate later capability.
</domain>

<decisions>
## Decisions

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

Recorded after planning (product owner; D-13 to D-17 are reserved for the answers to OQ-1 to OQ-5 of the plan):

- **D-18** Factorization schedule (2026-10-13; `.planning/codebase/FACTORIZATION.md`): Documents routes live in their own router `application/src/hyprn_mvp_app/routes/documents.py`, after the per-owner API routers of Phase 3 task 3.3a; Documents screens are view modules of the study-shell view registry of Phase 3 task 3.3b; document receipt categories declare their rows in the server-decided recovery table of Phase 3 task 3.3d; Documents-only schema definitions and the Documents registry live in the non-attested `contracts/schemas/documents.schema.json` after Phase 2 task 2.8 (the citation vocabulary that evidence 4 references stays in the attested model schema, as approved at checkpoint 2.8a). Phase 4 itself adds one declarative registry for every test group and one browser-fixture harness (tasks 4.4 and 4.4a), moves the remaining access-loss hosts to the shared seam (4.22a, before the citation UI of 4.23), and replaces the scientific chain's version literals with version-family capabilities (4.37–4.38; the attested table is added only inside the one re-attestation, in 4.37). The outbox history projection and authorization by effect come after the first release.

## Open product decisions (recommended defaults)

- **PD-4.1 Steps 14–18** (deletion fences, portable policy, import, restore and backup drill, lifecycle and export UI, end-to-end acceptance). Default: a later phase, "Documents lifecycle and portability", after the first release. Until then permanent deletion, export, import and restore are advertised unavailable; archive and unarchive, remove from collection and delete collection are available. DOC-01 stays `partial`.
- **PD-4.2 Annotation label.** Default: "Annotations" in the UI (never "notes"), kept out of the Evidence page (§18 Q1).
- **PD-4.3 Archived studies.** Default: archiving a study makes its documents read-only with it; nothing is deleted; restore re-enables editing (§18 Q4).
- **PD-4.4 Rendered PDF pages.** Default: text-first reader only (§18 Q5).
- **PD-4.5 Upload transport.** Default: the contracted chunked protocol for every edition (§18 Q9).
- **PD-4.6 Access-protection depth in the local edition.** Default: the study-scope check on every route always; the full persona, revocation and cache matrix before multi-user cloud (§18 Q7).
- **PD-4.7 Parser wheel acquisition.** Default: the parser image build fetches the wheel from the package index by its pinned filename and verifies size and SHA-256 against `integration/document-parser.lock.json` (the same fail-closed acquisition as Phase 2); no vendored wheel.
- **PD-4.8 Release exposure.** Default: the Documents capability is advertised available in the first release only when steps 1–13 pass and the Phase 5 reviews close their high findings; otherwise it stays advertised unavailable.

## Planner's discretion

- Task boundaries inside each step (one task per fresh executor), test fixtures, and the order of steps that have no dependency on each other (for example the parser image beside the library UI).
- Internal module layout inside `hyprn_mvp_app` and `hyprn_mvp_integration`, within the acyclic import rule.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `docs/specs/documents.md` — outcome, vocabulary, ownership (§3), authorization (§4), operations (§5), upload and recovery (§6), extraction and search (§7), locators and citations (§8), lifecycle (§9), limits (§11), implementation status and steps (§12), UI (§15), security (§16), open questions (§18).
- `contracts/documents.md` and the shared schemas — wire contracts, registry of routes, roles, verbs, limits and transitions.
- `integration/document-parser-provenance.md` and `integration/document-parser.lock.json` — parser identity and policy.
- `docs/specs/architecture-and-contracts.md` §3 (ownership), §6 (API principles), §7 (module ownership), §8 (persistence).
- `docs/specs/ui-target.md` and `design-system/README.md`, `Layouts.md`, `Scientific-states.md`, `Naming.md`.
- `docs/legal/licensing.md` §4 (pypdf notices) and §5 (new dependencies).
- `docs/specs/requirements.md` — DOC-01, HUM-06, RUN-02.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- `hyprn_mvp_integration.documents.NativeDocuments`: stores an original and its witness in one transaction, verifies readback, reconciles by command, refuses conflicting identities and serves bounded authenticated reads; tested on AiiDA 2.9.3 with SQLite, including forced kills around commit. No caller yet.
- Contract definitions (about 130) for all document operations, the bridge, locators, citations, evidence version 4 and the document-bearing version chain, generated into OpenAPI components and TypeScript types; capabilities list `documents` as unavailable.
- Tests: `contracts/tests/test_documents_contract.py`, `integration/tests/test_documents_native.py`, `integration/tests/test_documents_collection_protocol.py` (logical deletion qualified, including 10,000 members), `contracts/tests/test_document_parser_adoption.py`; fixtures `deployment/tests/documents_native_fixture.py` and `documents_ui_fixture.py`.
- The execution manager, receipts and the evidence version chain in `hyprn_mvp_app`.

### Integration points
- Routes in `hyprn_mvp_app.api` under `/api/1/studies/{study_id}/…`; capability advertisement switches per delivered step.
- The UI study shell gains the Documents tab; the evidence editors gain citation candidates.
- The parser image joins the deployment managers and follows the Phase 2 image conventions (digest-pinned base, `--network none` outside acquisition, content-tagged).
- New test groups in `deployment/checks.py`, named after the capability (for example `documents-collections`, `documents-library-ui`, `documents-reader-ui`).

### Dependencies
- Phase 1 (namespace, renamed Documents groups, parser adoption record).
- Independent of Phase 2 except the parser image (after Phase 2 task 2.7) and acceptance on scratch installations (after task 2.11). Shared files with Phase 3 (`contracts/hyprn-mvp.openapi.yaml`, `hyprn_mvp_app/api.py`, the UI study shell) are edited one task at a time.
</code_context>

<specifics>
## Acceptance (phase level)

- Steps 1–13 each meet their "done when" with automated evidence; UI steps with light and dark, keyboard and genuine 200 % zoom screenshots kept outside the repository.
- The product owner walks through: upload and reopen an original; organize two collections; search, read and annotate; create and attach an exact citation; change the source, the annotation and the extraction, then reopen an old run (also with the modeling service down); try a failed extraction. Recorded separately from automated evidence.
- `python3 ui/check_design_system.py` reports no FAIL line; the UI contract checker covers every new route the UI calls.

## Threats to cover in plans

Cross-study access through guessed identifiers, snippets, cursors and caches; malicious or mismatched uploads; header and filename injection on download; active content in the reader; parser exploits and resource exhaustion; parser supply chain; duplicate or partial effects after crashes; prompt injection through document text (labelled untrusted for later agent use).
</specifics>

<deferred>
## Deferred Ideas

- Steps 14–18: deletion fences, permanent deletion, portable export and import, restore and backup drill, lifecycle and export UI, end-to-end acceptance (PD-4.1).
- Agent document tools and agent upload.
- OCR, format conversion, rendered pages, ranking and semantic search.
- Authored documents (Tiptap) and live co-editing (Yjs, cloud only).
- Requalification of the native transaction and logical deletion on the cloud database backend.
</deferred>

---

*Phase: 04-documents*
