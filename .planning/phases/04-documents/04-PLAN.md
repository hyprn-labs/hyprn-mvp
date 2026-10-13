---
phase: 04-documents
plan: 01
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - application/
  - integration/
  - contracts/
  - deployment/
  - modeling/
  - upstream/whatsopt-patches/
  - ui/
  - design-system/
  - editions/local/
  - docs/specs/ui-target.md
  - docs/specs/documents.md
  - docs/specs/requirements.md
  - docs/legal/licensing.md
  - THIRD_PARTY_NOTICES.md
autonomous: false
requirements: [DOC-01, HUM-06, RUN-02]
estimate:
  tokens: 5560000
  raw_tokens: 5560000
  tasks: 45
  confidence: low
must_haves:
  truths:
    - "Two collections hold the same document version without a second copy of its bytes; a stale collection or annotation edit changes nothing; a deleted collection is terminal and replaying its delete command returns the original outcome without reactivation"
    - "An upload is published only after native storage reads the bytes back; the published version's exact bytes (same SHA-256 and size) download after an application and native restart"
    - "Every upload and document-operation state (receiving, queued, running, committed, published, failed, expired, interrupted, uncertain) has its own words, tag and action in the library; an uncertain outcome offers only 'Check what happened' and is never resubmitted"
    - "While a deliberately blocked native run holds the writer, every document read completes within 2 s and before the run ends; queued document writes report 'Saving waits for a running calculation to finish.'"
    - "The read process admits read verbs only; write verbs, scientific methods and unknown verbs are refused before any I/O, and it exits when its supervising executor exits"
    - "Every Documents route authorizes the current study before any association or native lookup and again at delivery; unknown and foreign identifiers, cursors, snippets and cached replies get the same not-found response"
    - "Only the chunk PUT accepts a non-JSON body (application/octet-stream, at most 262,144 bytes); every other route keeps the JSON-only 2 MiB rule and the origin, session and CSRF checks"
    - "Downloads are attachments with an encoded filename, nosniff and no-store; the user's filename never becomes a path, command or raw header"
    - "Extraction is offered only with current containment evidence for the pinned parser image and policy; without it the original still downloads and the reader says text extraction is not available"
    - "The same original extracted twice gives identical per-page text hashes and locators; partial, truncated, unsupported (encrypted), needs-transcription (image-only) and interrupted outcomes are recorded as such and the original stays downloadable in every state"
    - "A search hit opens the reader at the exact version, extraction and passage; results state indexed and unindexed versions and coverage; an empty result reads 'No match in the searched material.'; a deleted or foreign collection filter is not found and never broadens"
    - "A citation freezes the exact version, locator, server-computed quotation and its SHA-256 and the annotation snapshot; a client-supplied quote is ignored; a new source version, a re-extraction or an annotation edit never changes a stored evidence version"
    - "Evidence create and revise keep admitting EvidenceCreate1-3 and EvidenceRevise3 unchanged and admit EvidenceCreate4 and EvidenceRevise4 in addition; earlier configuration, frozen, bundle, history, seed and closure versions are never widened"
    - "The umbrella capability 'documents' stays in capabilities.unavailable; a slice ID in document_slices is advertised only when every registry route of that slice is mounted; the UI renders a Documents surface only when its slice is advertised (D-08)"
    - "The reader shows uploaded text only as escaped text; HTML, Markdown, script and link payloads stay inert; bidirectional and zero-width controls appear as visible markers"
    - "Every Documents screen and state passes keyboard-only, light and dark, and genuine 200 % zoom checks without page-wide horizontal scroll, uses only ui/src/design components and tokens, and python3 ui/check_design_system.py prints no FAIL line"
    - "An old run opens its cited source during a modeling-service outage with the stored quotation and annotation snapshot, and marks the bytes unavailable when document storage is down (tasks 4.34-4.39, after OQ-1)"
    - "Every Documents operation has one owner and one stored outcome that the UI reads back instead of repeating it (ADR-0004 central invariant; 'Operation ownership and agent rights' table): an abandoned upload expires as a stored operation, a citation is the frozen evidence version, an extraction result is read from its attempt, and the search projection is rebuildable and never authoritative"
    - "Spans are half-open [start, end): two passages that just touch do not overlap, and start = end, reversed, negative or out-of-range spans are refused"
    - "An empty admitted text file completes without any chunk, is published as a 0-byte version and is shown as '0 bytes'; deleting an empty collection still advances its revision once"
    - "Identical chunk bytes at the same offset are a harmless retry; the same command_id with the same payload returns the original outcome; a changed payload, including a changed expected_revision, conflicts without effect"
    - "After a crash or lost reply the exact witness is looked up before current state; several witnesses or a timeout leave the operation uncertain and nothing is retried automatically"
    - statement: "Library, collection, member, annotation, attempt and search pages have a stable order with ties broken by public ID; following cursors neither repeats nor skips a row"
      verification: backstop
    - "Empty states: library 'No documents yet' with the upload hint and no second upload button; 'No collections yet.'; empty collection, empty search ('No match in the searched material.' plus coverage), 'No annotations yet.', the empty 'Used by' line, and reader no-text states each keep 'Download original' present"
    - "Loading states name what loads ('Loading documents…', 'Loading page N…'); old rows or text are never shown under a new filter or heading; upload progress is measured bytes, then 'Saving the file…', never a percentage"
    - "Error states: read failures show 'Not loaded' with a named retry; stale edits keep the user's text and offer 'Review latest version'; access loss clears protected content before its notice; a deleted or foreign collection link shows 'not available' with 'Show all documents' and never broadens"
    - "Partial and overflow states: 'Text is available for N of M pages.' with page tags; partial search coverage counts unsearched versions; each library panel fails independently; 100 rows per page then 'Load more documents'; the versions table scrolls only inside its own box"
    - "Counts use singular and plural forms ('1 document', 'N documents', 'N of 20 citations'); titles, filenames, annotations and quotations wrap and are never truncated without the full text available"
    - "Readers (study role reader) see read actions only: write actions are removed, not disabled; reading, search, download and the cited-source view stay available"
    - statement: "A 256 KiB extracted page and a 10,000-character unbroken line render without page-wide horizontal scroll at genuine 200 % zoom in both themes"
      verification: backstop
    - statement: "100 collections with 200-character titles wrap inside the panel-outline column at genuine 200 % zoom in both themes"
      verification: backstop
    - statement: "HTML, Markdown, script and bidirectional-control payloads in text, titles, filenames and annotations create no element, link or script in the browser"
      verification: backstop
    - statement: "A filename with path separators, quotes, CR/LF or non-ASCII characters downloads under the server's encoded attachment name with bytes equal to the original SHA-256"
      verification: backstop
    - statement: "A passage chosen with the keyboard fields (including astral characters and combining marks) gives the same span as pointer selection and can be cited without a pointer"
      verification: backstop
    - statement: "Each of the five citation paths reaches the cited version and locator, not the latest version, after the source was replaced, re-extracted and its annotation edited (paths 2-4 after OQ-1)"
      verification: backstop
    - "After a lost reply, a Documents command is recovered from the receipt's server-decided recovery field; the UI keeps no per-category recovery rule and never resends a command whose outcome is uncertain (D-03, D-18)"
    - "A confirmed loss of access to the open study clears every evidence, assumption, model, unit, configuration and study-shell host through the one shared seam; a denied saved configuration shows its message once (D-18)"
    - statement: "Historical reads accept exactly the same retained records before and after the version-family capability table; the table reproduces RETAINED_PAIRINGS and the golden identity corpus is unchanged (D-18)"
      verification: backstop
    - statement: "Every test group is one entry file under deployment/groups/<family>/; moving the groups changes neither the --list output (except the two new Documents groups) nor any group's pass count (D-18)"
      verification: backstop
  prohibitions:
    - "A document being present, extracted, annotated or cited never displays or implies that a scientific statement holds: no 'verified', 'validated' or confidence wording is derived from citations, and the line 'A citation records your interpretation; it does not validate the statement.' accompanies every citing surface"
    - "Numbers from extracted text, tables or CSV never become model inputs, quantities or criterion values; CSV is shown as text only"
    - "A historical view (evidence version, configuration, run, cited-source view) never shows the current document title, version, extraction or annotation in place of what was cited; 'View latest source' is always a separate, explicit navigation"
    # canon-referral (dropped as prohibitions, covered by the threat register): cross-study disclosure, upload injection, header and path injection, active content, parser exploits.
  assumptions:
    - "Upload survives reload (UI-SPEC unresolved row): until OQ-5 is answered and task 4.32 lands, the Uploads panel lists only uploads started in the current page session; success criterion 2 'every recovery state is visible in the library' is met only after task 4.32"
    - "Documents tab visibility per slice (UI-SPEC unresolved row): the tab appears only when documents_library/1 is advertised; each other surface appears only with its own slice (capability-slice decision in 'Decisions and defaults applied')"
    - "HUM-06 edge behaviour (probe row unclassified): assumed fully covered by 'an annotation edit never changes a stored evidence version' and the bound of at most 20 unique citations per evidence version; review manually"
    - "RUN-02 edge behaviour (probe row unclassified): assumed fully covered by 'historical reads never contact the modeling service and never substitute current content'; review manually after OQ-1"
  artifacts:
    - path: application/src/hyprn_mvp_app/documents.py
      provides: "Families, versions, uploads and spool, document operations and their state machine, associations, library reads, metadata and archive commands, collections, annotations and extraction attempts, usage, document_slices"
    - path: application/src/hyprn_mvp_app/document_bridge.py
      provides: "Closed document-write and document-read frames, the write drain step and the read mailbox drainer"
    - path: application/src/hyprn_mvp_app/document_search.py
      provides: "Rebuildable search projection, bounded matching, coverage and signed cursors"
    - path: application/src/hyprn_mvp_app/document_citations.py
      provides: "Locator validation, UTF-16 to code point conversion, server quotation and DocumentCitation1 freezing"
    - path: application/src/hyprn_mvp_app/routes/documents.py
      provides: "router(deps): every Documents route, composed by api.py (per-owner routers from Phase 3 task 3.3a)"
    - path: application/src/hyprn_mvp_app/execution_bundle.py
      provides: "Version-family capability table: family(record).has(capability), reproducing RETAINED_PAIRINGS, added inside the re-attesting task 4.37"
    - path: deployment/document_native_runtime.py
      provides: "Host-side closed handlers for document writes (single writer) and the supervised read process"
    - path: integration/src/hyprn_mvp_integration/documents.py
      provides: "NativeDocuments: originals, collections with logical terminal deletion, annotations, extraction start, reads, generalized reconcile"
    - path: integration/src/hyprn_mvp_integration/document_extraction.py
      provides: "Extraction calcfunction with real input and output links"
    - path: integration/src/hyprn_mvp_integration/document_parser_launch.py
      provides: "Parser container launch, reaping and containment evidence"
    - path: deployment/images/parser.Dockerfile
      provides: "Pinned parser image with the verified wheel"
    - path: deployment/group_registry.py
      provides: "Loader of every test group's entry file (deployment/groups/<family>/<group>.json): closed schema, derived class, needs, interpreter and runner sets"
    - path: deployment/documents_groups.py
      provides: "Documents runner modes, test selection and measured-artifact validators"
    - path: deployment/tests/browser_harness.py
      provides: "One browser-fixture harness: serve(...) and run_playwright(...), used by every scoped browser fixture"
    - path: ui/src/DocumentsLibrary.tsx
      provides: "Documents tab: library, uploads panel, collections, search"
    - path: ui/src/DocumentReader.tsx
      provides: "Text-first reader and the cited-source view"
    - path: ui/src/views/documents.tsx
      provides: "Documents library view module in the study-shell view registry (the reader and cited-source view modules sit beside it)"
  key_links:
    - from: application/src/hyprn_mvp_app/api.py
      to: application/src/hyprn_mvp_app/routes/documents.py
      via: "create_app composes routes.documents.router(deps); api.py keeps only the edge (middleware including the chunk-route body exemption, auth dependency, envelope)"
    - from: application/src/hyprn_mvp_app/routes/documents.py
      to: application/src/hyprn_mvp_app/documents.py
      via: "every Documents route calls Store.authorize for the route's study before any association or native lookup"
    - from: application/src/hyprn_mvp_app/store.py
      to: "GET commands/{command_id}?category=document_*"
      via: "each document receipt category has its rows in the store's server-decided recovery table (Phase 3 task 3.3d); the UI reads recovery"
    - from: application/src/hyprn_mvp_app/dispatcher.py
      to: deployment/document_native_runtime.py
      via: "the document_write bridge method carries closed DocumentBridgeWrite1 frames to the single host writer"
    - from: deployment/dispatch_runtime.py
      to: deployment/document_native_runtime.py
      via: "the executor starts and owns the read process (read verbs only, own lock, ends with the executor)"
    - from: integration/src/hyprn_mvp_integration/document_extraction.py
      to: integration/src/hyprn_mvp_integration/document_parser_launch.py
      via: "the calcfunction launches the pinned parser image only with current containment evidence"
    - from: application/src/hyprn_mvp_app/document_citations.py
      to: deployment/document_native_runtime.py
      via: "the fragment read verb supplies the exact artifact text the server slices and hashes"
    - from: deployment/parser_image.py
      to: integration/document-parser.lock.json
      via: "wheel filename, size and SHA-256 verified at acquisition and again inside the offline build"
    - from: ui/src/views/registry.ts
      to: "/api/1/capabilities document_slices"
      via: "each Documents view module's available(capabilities) shows the Documents tab and every Documents surface only when their slice is advertised"
    - from: deployment/checks.py
      to: deployment/group_registry.py
      via: "run_group and child dispatch on each entry's runner; registering a group adds an entry file and never edits checks.py"
---

# Phase 4: Documents — plan

<objective>
Within a study an engineer uploads source documents, organizes versions in collections, reads and searches the extracted text in a text-first reader, annotates passages and cites them from evidence, and reopens an old run with the exact cited source, also while the modeling service is down. Bytes, collections, annotations and extraction provenance live in AiiDA; identity, study scope, citations and evidence semantics live in HYPRN MVP. Everything works manually in the UI.

Purpose: source documents complete DOC-01's first deliverable (steps 1–13 of `docs/specs/documents.md` §12) and close the document-citation gaps of HUM-06 and RUN-02, which the first local release waits for (Phase 5 PD-5.1).
Output: the native collection, annotation and extraction adapters; the closed document bridge with a measured read loop; the study-scoped document API in its own router (`routes/documents.py`); the pinned, contained parser image; the search projection; citations inside evidence version 4 and the document-bearing scientific chain, read through version-family capabilities; the Documents tab, reader and citing UI as view modules of the study-shell view registry; the evidence hosts on the shared access-loss seam; one declarative registry for every test group and one browser-fixture harness; and one checkpoint per task (45 tasks).
</objective>

## How this plan is executed

- One numbered task per fresh executor context, in the wave order below. A task starts only after the orchestrating session has verified the checkpoints of the tasks it depends on. Phase 1 must be complete (namespace, renamed Documents groups, `integration/document-parser.lock.json` from task 1.8, `ui/check_ui_contract.py` and `ui/control-map.json` from task 1.6).
- Cross-phase prerequisites (product owner's factorization schedule, D-18): Phase 3 task 3.3a (per-owner API routers) before 4.1, so every Documents route lives in `routes/documents.py`; Phase 3 task 3.3b (study-shell view registry) before 4.13, so Documents screens are view modules; Phase 3 task 3.3d (server-decided recovery on receipts) before 4.9b; Phase 2 task 2.8 (completing the 2.8c contract-schema split — non-attested `contracts/schemas/documents.schema.json` — and re-attesting) before 4.32, 4.34 and 4.37, and before 4.19 as already planned.
- Each task stages explicit paths only and ends with atomic commits plus a checkpoint file `phases/04-documents/checkpoints/<task>.md` in the planning directory: commits; exact commands with pass and fail counts and every failure; source and artifact identities (generated contract digests, image digests, containment and evidence file hashes); scratch scopes created and released; remaining risks.
- The orchestrating session reruns the task's acceptance commands on the committed tree, compares the commits' files with the task's Files list, and only then dispatches dependent tasks. Tasks run in parallel only when their file sets are disjoint; the shared files listed under "Parallel work" are edited by one task at a time across Phases 2, 3 and 4.
- Evidence (logs, timelines, canary reports, screenshots) stays outside the repository: under `HYPRN_MVP_EVIDENCE_ROOT`, and browser screenshots under `HYPRN_MVP_UI_EVIDENCE_ROOT`. Tests run only in scoped scratch stores. Automated evidence is never human acceptance; the product owner's walk-through is recorded separately in task 4.41 (D-10).
- A task marked **Blocked by OQ-n** starts only after the product owner's answer is recorded by the orchestrating session in `04-CONTEXT.md` under Decisions, with this mapping: OQ-1 → D-13, OQ-2 → D-14, OQ-3 → D-15, OQ-4 → D-16, OQ-5 → D-17. Unblocked tasks keep flowing. Tasks 4.31–4.39 then run under the "Blocked lane" rules below (fixed order, explicit not-beside lists).
- Paths name the final Phase 1 identifiers (`hyprn_mvp_app`, `hyprn_mvp_integration`, `contracts/hyprn-mvp.openapi.yaml`, `HYPRN_MVP_*`); today's equivalents are listed in the rename map of `04-PATTERNS.md`. Line numbers in `04-PATTERNS.md` are re-checked after Phase 1.

### Development environment

The values are specific to the development host and never committed; they are the Phase 1 variables plus the ones this phase adds:

    export HYPRN_MVP_DATA_ROOT=<development data root, outside the repository and outside synced folders>
    export HYPRN_MVP_NATIVE_PYTHON=<native development interpreter>      # until Phase 2 task 2.1 replaces it
    export HYPRN_MVP_CONTRACT_PYTHON=<contract development interpreter>  # idem
    export HYPRN_MVP_EVIDENCE_ROOT=<evidence folder outside the repository>
    export HYPRN_MVP_UI_EVIDENCE_ROOT=<screenshot folder outside the repository>
    export HYPRN_MVP_PARSER_CACHE=<verified parser wheel cache>           # added by task 4.15; default below the data root

`CHECK <group>` and every `<automated>` command below mean `python3 -B deployment/checks.py --group <group>` with these variables exported. From task 4.1 on, a Documents group started from any parent interpreter re-runs itself under its registered interpreter (the path `qualification` already takes), so the acceptance form needs no interpreter choice. Phase 2 wraps the same command as `./hyprn-mvp dev check <group>`. Design checks: `python3 ui/check_design_system.py` (no FAIL line), `python3 ui/design_tokens.py --check`, `python3 ui/test_design_tooling.py`, `node ui/design_smoke.mjs`. UI build: `npm --prefix ui ci && npm --prefix ui run build`.

### Waves

Waves follow real dependencies and the one-task-at-a-time rule for shared files. Tasks blocked only by OQ-2 keep their numbered wave and wait in place. Tasks blocked by OQ-1, OQ-3, OQ-4 or OQ-5 (4.31–4.39) run in the blocked lane below as soon as their answer and dependencies are verified.

| Wave | Tasks | Why |
|---|---|---|
| 1 | 4.1 (tracer) ∥ 4.2 ∥ 4.3 | The end-to-end upload slice (after Phase 3 task 3.3a); the two one-way decisions are taken while it is built |
| 2 | 4.4 ∥ 4.5 ∥ 4.6 | The group registry for every group, design-system additions and the parser pin record touch disjoint files |
| 3 | 4.4a ∥ 4.7 ∥ 4.8 ∥ 4.9a ∥ 4.10 | Browser-fixture harness and isolated API (after 4.4: shared `deployment/tests/test_repository_guard.py` and the registry loader), native collections, bridge and read loop, library routes with signed cursors, reader and citation components: disjoint files |
| 4 | 4.9b ∥ 4.12; 4.11 → 4.15 | Upload recovery states (after Phase 3 task 3.3d) and the access matrix, native annotations; the parser image after the human wheel check and Phase 2 task 2.7 |
| 5 | 4.13 ∥ 4.14 ∥ 4.18 ∥ 4.19 | Library UI (after Phase 3 task 3.3b and 4.4a), collections API, parser containment, production wiring (after Phase 2 tasks 2.3 and 2.8) |
| 6 | 4.16 ∥ 4.17 | Collections UI, annotations API |
| 7 | 4.20 ∥ 4.21 ∥ 4.22a | Citation resolver and evidence 4; native extraction; the remaining hosts on the shared access-loss seam (after 4.16 and Phase 3 task 3.3b) |
| 8 | 4.22 | "Used by", assumption evidence, the Evidence4 admission boundary |
| 9 | 4.23 ∥ 4.24 | Citations in the evidence UI, built on the seam of 4.22a; extraction API |
| 10 | 4.25; 4.30 when Phase 2 task 2.11 is done | Search; parser at setup and the served journey |
| 11 | 4.26 ∥ 4.27 | Reader and search UI; page and passage locators |
| 12 | 4.28 | Annotations, "Used by" and source actions in the reader |
| 13 | 4.29 | Citing from the reader; the cited-source view; paths 1 and 5 |
| lane | 4.34 → 4.31 → 4.32 → 4.33 → 4.35 → 4.38 → 4.39 (lane order); 4.36, 4.37 and 4.37b outside the lane, by their dependencies | Blocked work, one lane task at a time in this order, beside the numbered waves only where "Blocked lane" allows |
| 14 | 4.40 | Cross-screen theme, keyboard and zoom sweep, after 4.29 and after each blocked UI task (4.31, 4.32, 4.33, 4.39) is verified or recorded out of this phase |
| 15 | 4.41 | Phase acceptance |

### Blocked lane

Tasks 4.31–4.39 wait for OQ-1, OQ-3, OQ-4 or OQ-5 and can become ready at any time. They share the application documents module, the Documents router `application/src/hyprn_mvp_app/routes/documents.py` (4.35 and 4.38 edit other owners' route modules instead), the generator and the regenerated contract and types, `contracts/documents.md`, the non-attested `contracts/schemas/documents.schema.json` (after Phase 2 task 2.8), `docs/specs/documents.md`, `ui/src/DocumentsLibrary.tsx`, `ui/src/api.ts` and `ui/control-map.json`, with each other and with numbered-wave tasks. Two rules serialize them:

1. **One lane task at a time, in a fixed order.** At most one of 4.34, 4.31, 4.32, 4.33, 4.35, 4.38 and 4.39 runs at any moment. When several are ready, the first in that order starts. A task whose answer or dependencies are missing is passed over, never waited for. 4.36 edits no file of another lane task, 4.37 shares files only with its dependency 4.35 (`configuration.py`, `approach.py`), and 4.37b only with 4.36 (`deployment/pins.json`), a dependency through 4.37, so all three follow their dependencies only (4.35 ∥ 4.36 is allowed).
2. **Not beside the numbered-wave tasks that share its files.** A ready lane task starts only when no task in its "Not beside" cell is running, and those tasks do not start while it runs. Its own dependencies, direct or through other dependencies, are finished by then and are not listed. A dependency that holds under one option of its decision only (4.33 with option a depends on 4.29) orders nothing under the other option, so every numbered-wave task that writes one of the lane task's files and is not ordered before it under every option is listed.

| Lane order | Task | Blocked by | Depends on | Not beside (shared files) |
|---|---|---|---|---|
| 1 | 4.34 | OQ-1 | 4.3, 4.4, Phase 2 2.8; ordering prerequisites 4.4a, 4.22, 4.22a (see "Stale-attestation window") | 4.6 (`contracts/documents.md`, `docs/specs/documents.md`); 4.9a, 4.9b, 4.14, 4.17, 4.20, 4.22, 4.24, 4.25 (generator, contract and types) |
| 2 | 4.31 | OQ-3 | 4.14, 4.16 | 4.6 (`contracts/documents.md`); 4.12, 4.21 (native adapter); 4.17, 4.20, 4.22, 4.24, 4.25, 4.27 (application documents module); 4.22a, 4.23, 4.26, 4.28, 4.29 (`ui/control-map.json`) |
| 3 | 4.32 | OQ-5 | 4.9b, 4.13, Phase 2 2.8 | 4.6 (`contracts/documents.md`); 4.14, 4.17, 4.20, 4.22, 4.24, 4.25, 4.27 (application documents module, `routes/documents.py`, generator); 4.16, 4.22a, 4.23, 4.26, 4.28, 4.29 (library and upload views, `ui/src/api.ts`, `ui/control-map.json`) |
| 4 | 4.33 | OQ-4 | 4.9b, 4.13; option a also 4.29 | 4.6 (`docs/specs/documents.md`); 4.14, 4.17, 4.20, 4.22, 4.24, 4.25, 4.27 (application documents module, generator); 4.16 (`ui/src/DocumentsLibrary.tsx`), 4.26 (`ui/src/DocumentsLibrary.tsx`, `ui/src/DocumentReader.tsx`), 4.28, 4.29 (`ui/src/DocumentReader.tsx`), listed whatever the option because only option a makes them dependencies |
| 5 | 4.35 | OQ-1 | 4.34, 4.22 | 4.24, 4.25 (`store.py`, generator); 4.27 (`document_citations.py`) |
| outside the lane | 4.36 | OQ-1 | 4.34, Phase 2 2.6 | 4.8, 4.18, 4.30 (`deployment/documents_groups.py`); 4.15 (`deployment/pins.json`) |
| outside the lane | 4.37 | OQ-1 | 4.35, 4.36, Phase 2 2.8 | 4.25 (`application/tests/test_module_boundaries.py`) |
| outside the lane | 4.37b | OQ-1 | 4.37 | 4.15 (`deployment/pins.json`) |
| 6 | 4.38 | OQ-1 | 4.37b, 4.19 | 4.24, 4.25 (generator, contract and types) |
| 7 | 4.39 | OQ-1 | 4.38, 4.29 | none (every task sharing its files, including 4.22a and 4.23 for `ui/src/ConfigurationPanel.tsx` and `ui/src/EvidencePicker.tsx`, is among its dependencies) |

Task 4.40 runs after the lane's UI tasks (see its dependencies), so the sweep covers every state they deliver.

#### Stale-attestation window (4.34 → 4.35/4.36 → 4.37 → 4.37b)

The chain changes attested execution inputs in several tasks and re-attests once. The window opens with the commit of its first attested-input edit (4.34's `model.schema.json` definitions under the split approved at Phase 2 checkpoint 2.8a; then 4.35's `scientific_configuration.py` and `approach_closure.py`; then 4.36's modeling inputs: the new patch, `deployment/modeling_runtime.py`, `deployment/pins.json`, `modeling/provenance.md`). 4.37 re-attests once; the window closes when 4.37b is verified (the `modeling_producer` re-pin and the native fixture recapture, with every group on the binding list passing again). In between, the shared development runtime and the pinned native captures no longer match the execution sources.

- **Ordering, so the window stalls no other Phase 4 track:** 4.34 starts only after 4.22, 4.4a and 4.22a are verified (they are the numbered-wave tasks whose verification names window groups, for example `units-native`, `findings-native-read` and `approach-ui-history`); the lane order is unchanged. With them done, the window spans only 4.34 → 4.35/4.36 → 4.37 → 4.37b.
- **Binding window list (measured, not assumed).** 4.34's checkpoint runs the candidates on its committed tree and records which fail: the durable-fixture groups, which continue from the durable native fixture captured with the earlier attested inventory and producer (`findings-native-preflight`, `findings-native`, `findings-native-read`, `approach-ui-history`), and every check against the development installation's attested runtime (`doctor`, `status`, served groups on the development installation). 4.36's checkpoint re-measures the post-modeling candidates on its committed tree (`units-worker` with its native-program part `test_native_program.py`, `units-native`, `fuel-native-provenance`, `ae-model`, `units-model`, and any other group reading the pinned modeling producer or the frozen native programs) and adds every failing group to the list. Groups that build and attest a worker inside their own scope (`units-attestation`, the scoped native journeys) rebuild from the current sources and keep passing unless a measurement says otherwise.
- **Rule:** while the window is open, no task of Phase 2, 3 or 4 whose verification names a group on the binding list runs; it waits for 4.37b's verification. 4.35 names none of them, 4.36 runs its candidates only to measure them, 4.37 runs only the worker-admission cases of `units-worker`, and 4.37b runs the whole list to close the window. A branch that predates 4.37b's merge rebases before running one of them. The window cannot overlap Phase 2 task 2.8's own re-attestation window, because 4.34 depends on 2.8.

### Task index

"Beside Phase 2" and "Beside Phase 3" name the other phases' tasks a task may run beside; "no" lists the shared files that serialize it (see "Parallel work"). After Phase 3 task 3.3a, a Documents route task edits `routes/documents.py` (Phase 4 only), so what still serializes it with Phase 3 is `store.py`, the generator and the regenerated contract and types, or another owner's route module.

| Task | Title | Wave | Depends on | Blocked by | Beside Phase 2 | Beside Phase 3 |
|---|---|---|---|---|---|---|
| 4.1 | (tracer) Upload to exact download through the single writer and the read mailbox | 1 | Phase 1, Phase 3 3.3a | — | only 2.4 and 2.7 (disjoint from 4.1's files; 2.3 shares `test_module_boundaries.py`) | no (`api.py` composition, `store.py`, `test_module_boundaries.py`, generator, contract and types) |
| 4.2 | Decision: parser wheel version | 1 | — | — | yes (no files) | yes |
| 4.3 | Decision: document-bearing chain for current models | 1 | — | — | yes (no files) | yes |
| 4.4 | Declarative registry for every test group, the Documents groups and the native-backed browser mode | 2 | 4.1 | — | only 2.3, 2.7; never beside a task that edits `checks.py` or `test_repository_guard.py` or registers a group | not beside a task that edits `checks.py` or `test_repository_guard.py` or registers a group |
| 4.4a | One browser-fixture harness and the isolated Documents API on it | 3 | 4.4 | — | not beside a task that edits a migrated browser fixture or `test_repository_guard.py` | not beside a task that edits a browser fixture or `test_repository_guard.py` |
| 4.5 | Design-system additions for the library (A1–A4, A7) | 2 | 4.1 | — | yes | not beside edits of `Naming.md` or `ui/src/design` |
| 4.6 | Parser pin record per the version decision | 2 | 4.2 | OQ-2 | not beside 2.6 or 2.14 when `licensing.md` changes | yes |
| 4.7 | Native collections with logical terminal deletion | 3 | 4.4 | — (`replace`: OQ-3) | yes | yes |
| 4.8 | Closed bridge verb sets and the measured read loop | 3 | 4.4 | — | yes | yes |
| 4.9a | Library routes, signed cursors and the library slice | 3 | 4.4 | — | yes | no (`store.py`, the capabilities route, generator, contract and types) |
| 4.9b | Upload recovery states, quotas, the document recovery rows and the study-scope access matrix | 4 | 4.9a, Phase 3 3.3d | — | yes | no (`store.py`, the receipts route, generator, contract and types) |
| 4.10 | TextReader and CitationRecord components (A5, A6) | 3 | 4.5 | — | yes | not beside `ui/src/design` edits |
| 4.11 | Verify the parser wheel before its first install (human) | 4 | 4.6, Phase 2 2.7 | OQ-2 | — | — |
| 4.12 | Native working annotations | 4 | 4.7 | — | yes | yes |
| 4.13 | Library UI | 5 | 4.4a, 4.5, 4.9b, Phase 3 3.3b | — (reload part: OQ-5) | yes | no (`ui/src/views/registry.ts`, `ui/src/api.ts`, `ui/control-map.json`) |
| 4.14 | Collections API | 5 | 4.7, 4.8, 4.9b | — (`replace`: OQ-3) | yes | no (`store.py`, generator, contract and types) |
| 4.15 | Parser image from the verified wheel | 4 | 4.11, Phase 2 2.7 | OQ-2 | after 2.7; not beside 2.6 or 2.14 | yes |
| 4.16 | Collections UI | 6 | 4.13, 4.14 | — | yes | no (`ui/src/api.ts`, `ui/control-map.json`) |
| 4.17 | Annotations API | 6 | 4.12, 4.14 | — | yes | no (`store.py`, generator, contract and types) |
| 4.18 | Parser launcher and demonstrated containment | 5 | 4.15, 4.8 | OQ-2 | yes | yes |
| 4.19 | Production wiring: read loop and document writes under the executor | 5 | 4.8, Phase 2 2.3, 2.8 | — | after 2.8; not beside other `dispatch_runtime.py` or `release.py` edits | yes |
| 4.20 | Citation resolver for whole files and evidence version 4 | 7 | 4.17 | — | yes | no (the evidence route module, `store.py`, `test_module_boundaries.py`, generator, contract and types) |
| 4.21 | Native extraction | 7 | 4.18, 4.12, 4.17 | OQ-2 | yes | yes |
| 4.22 | "Used by", assumption evidence with citations, the Evidence4 admission boundary | 8 | 4.20 | — | yes | no (the model route module, `configuration.py`, `approach.py`, `modeling.py`, generator, contract and types) |
| 4.22a | Access-loss seam for the remaining hosts (no behaviour change except the single denial message and the study-shell lists cleared on access loss) | 7 | 4.16, Phase 3 3.3b | — | yes | no (`ui/src/Workspace.tsx` and the view modules, evidence, model, unit and configuration views, `ui/control-map.json`, the AE and units specs) |
| 4.23 | Citations in evidence: editor, View evidence and assumptions | 9 | 4.22, 4.10, 4.16, 4.22a | — | yes | no (evidence views, `ui/src/api.ts`, `ui/control-map.json`) |
| 4.24 | Extraction API and fragments | 9 | 4.21, 4.22 | OQ-2 | yes | no (`store.py`, the capabilities route, generator, contract and types) |
| 4.25 | Processing provenance and search | 10 | 4.24, 4.14 | OQ-2 | yes | no (`store.py`, `test_module_boundaries.py`, generator, contract and types) |
| 4.26 | Reader and search UI | 11 | 4.25, 4.10, 4.23 | OQ-2 | yes | no (`ui/src/views/registry.ts`, `ui/src/api.ts`, `ui/control-map.json`) |
| 4.27 | Page and passage locators for annotations and citations | 11 | 4.20, 4.25 | OQ-2 | yes | yes |
| 4.28 | Annotations, "Used by" and source actions in the reader | 12 | 4.26, 4.27, 4.22 | OQ-2 | yes | no (`ui/src/api.ts`, `ui/control-map.json`) |
| 4.29 | Citing from the reader, the cited-source view, paths 1 and 5 | 13 | 4.28 | OQ-2 | yes | no (`ui/src/views/registry.ts`, `ui/src/api.ts`, `ui/control-map.json`) |
| 4.30 | Parser image and containment at setup; served Documents journey | 10+ | 4.24, 4.19, Phase 2 2.11, 2.14 | OQ-2 | after 2.11 and 2.14; not beside 2.12 (`setup.py`) | not beside `editions/local` CLI edits |
| 4.31 | Replace a collection member version | lane 2 | 4.14, 4.16 | OQ-3 | yes | no (`ui/control-map.json`) |
| 4.32 | Recent uploads and recovery after reload | lane 3 | 4.9b, 4.13, Phase 2 2.8 | OQ-5 | after 2.8 | no (generator, contract and types, `ui/src/api.ts`, `ui/control-map.json`) |
| 4.33 | Document writes in archived studies | lane 4 | 4.9b, 4.13; option a also 4.29 | OQ-4 | yes | no (generator, contract and types) |
| 4.34 | Document-bearing chain contract amendment | lane 1 | 4.3, 4.4, Phase 2 2.8; after 4.4a, 4.22 and 4.22a are verified (window ordering) | OQ-1 | after 2.8 | not beside contract schema or generator edits |
| 4.35 | Configuration and approach chain in the application | lane 5 | 4.34, 4.22 | OQ-1 | yes (after 2.8 through 4.34), within the stale-attestation window rule | no |
| 4.36 | Modeling service admits the private projection | outside the lane | 4.34, Phase 2 2.6 | OQ-1 | after 2.6 | yes |
| 4.37 | Version-family capabilities, bundle, launcher and worker admission with re-attestation | outside the lane | 4.35, 4.36, Phase 2 2.8 | OQ-1 | after 2.8; not beside attested-set edits | not beside a task that edits `execution.py` or `approach.py` (3.3c, 3.32) or `test_module_boundaries.py` |
| 4.37b | Producer re-pin and native fixture recapture; the stale-attestation window closes | outside the lane | 4.37 | OQ-1 | not beside `pins.json` or native-fixture-pin edits | yes, if it names no window group |
| 4.38 | Frozen history with cited sources | lane 6 | 4.37b, 4.19 | OQ-1 | yes | no (`history.py`, the runs route module, generator, contract and types) |
| 4.39 | Citation paths 2–4 and run evidence in the UI | lane 7 | 4.38, 4.29 | OQ-1 | yes | no |
| 4.40 | Documents screens: themes, keyboard and genuine 200 % zoom sweep | 14 | 4.29, 4.31, 4.32, 4.33, 4.39 (each verified or recorded out of this phase) | through its dependencies | yes | yes (new files only) |
| 4.41 | Phase acceptance | 15 | all tasks | — | after 2.11 | — |

## Target design

### Layers and module ownership

| Module | Owns | May import |
|---|---|---|
| `integration/src/hyprn_mvp_integration/documents.py` (`NativeDocuments`) | Originals, collections (one `Group` each, logical terminal deletion), annotations (one bounded extras object each), extraction start, reads, witnesses, generalized `reconcile` | AiiDA (lazily), stdlib. Never imported by `launcher`, `calculation`, `results` or `worker`; never in the attested source set |
| `integration/src/hyprn_mvp_integration/document_extraction.py` | The extraction `@calcfunction`, manifest and text `FolderData` builders, outcome mapping | `documents`, `document_parser_launch`, AiiDA |
| `integration/src/hyprn_mvp_integration/document_parser.py` | The fixed in-image entry (strict UTF-8 `hyprn-mvp-utf8/1` and `pypdf`) | stdlib and `pypdf` only; copied into the parser image |
| `integration/src/hyprn_mvp_integration/document_parser_launch.py` | Parser container flags, reaping, containment canaries and evidence, `require_parser_containment` | stdlib; reads `integration/document-parser-policy.json` |
| `deployment/document_native_runtime.py` | Host handlers: `handle_write` (single writer) and the read-process entry `--reads` (own lock, read verbs only) | `hyprn_mvp_integration.documents`, `document_extraction` (writes only), the dispatcher codec |
| `application/src/hyprn_mvp_app/documents.py` | Families, versions, uploads and spool, operations (state machine with proofs), associations, library, metadata and archive, collections, annotations, extraction attempts, usage, `DOCUMENT_LIMITS`, `DOCUMENT_SLICES` | `contracts`, `store` |
| `application/src/hyprn_mvp_app/document_bridge.py` | Closed frames, `documents_once` (write drain step), `reads_once` and the `--reads` mailbox entry | `contracts`, `store`, `documents`, `dispatcher` codec |
| `application/src/hyprn_mvp_app/document_search.py` | Projection build and rebuild, bounded matching, coverage, signed cursors | `contracts`, `store`, `documents` |
| `application/src/hyprn_mvp_app/document_citations.py` | Locator validation (page inventory, code point span bounds, artifact identity and hash), server quotation and its hash, `freeze_citation` → `DocumentCitation1`, the untrusted-field inventory | `contracts`, `store`, `documents` |
| `application/src/hyprn_mvp_app/routes/documents.py` | Every Documents HTTP route as `router(deps) -> APIRouter` (request shape, authorization order, response envelopes); composed only by `api.py` | the edge-helper module of Phase 3 task 3.3a, `contracts`, `store`, `documents`, `document_bridge`, `document_citations`, `document_search` |
| `ui/src/documentOffsets.ts` | The one browser conversion of a reader UTF-16 range to code point offsets (refuses a split surrogate pair) | — |

`execution_bundle` and every attested root never reach a document module; `test_module_boundaries.py` pins this in the task that adds each module. Only `api` imports `routes.documents`, and no domain module imports a route module.

### Writes, reads and publication (D-03, D-09)

- A mutation route runs one application transaction: authorize the study (D-02), look up the receipt, reserve public IDs, insert a `document_operations` row (`queued`; uploads go `receiving → queued`), return 202 with `DocumentOperation1`.
- The existing dispatcher serve loop calls `document_bridge.documents_once` every iteration, also while attestation is not ready. It claims one operation under a generation fence, asks `documents.next_write` for the closed frame, sends it through the bridge method `document_write` (one argument, a validated `DocumentBridgeWrite1`), and hands the reply to `documents.apply_write_reply`, which validates it against the reserved identity and publishes after an exact readback proof. A missing reply leaves the operation `uncertain`; recovery sends `reconcile`, which looks up the exact witness before current state. Nothing is retried blindly.
- While a run holds the single writer, queued writes report waiting ("Saving waits for a running calculation to finish.").
- Reads go to the `document_read_requests` mailbox. A separate read process, started and owned by the executor (task 4.19), answers read verbs only, with its own lock and AiiDA handle; the application waits a bounded time and otherwise answers `backend_unavailable` (reads have no side effects). Replies are cached at most 5 minutes and re-authorized at every delivery.

### Upload spool (D-11)

The spool lives in the application store's own folder, `document-spool/` beside the application database (inside the application container's existing `/store` bind mount). The application is its only writer: it creates chunk files (`O_EXCL|O_NOFOLLOW`, 0600, server-derived names), appends, and deletes them after publication or after the 24-hour lease expires. The host writer resolves the opaque `transfer_id` to exactly one regular file beneath that folder and opens it read-only with `O_NOFOLLOW`; it never creates, writes or deletes there. No container shares a writable directory with another component (architecture §4.1), so no mount changes and no conflict with Phase 2 task 2.4.

### Capability slices (D-08, PD-4.8)

`ApplicationCapabilities` gains the closed array `document_slices` (task 4.9a). `DOCUMENT_SLICES` maps each slice to its registry routes; the capabilities route advertises a slice only when every one of its routes is mounted, so advertisement cannot run ahead of implementation. `documents` stays in `unavailable` through this phase; Phase 5 removes it at the release gate.

| Slice | Registry routes | Advertised from |
|---|---|---|
| `documents_library/1` | 4 upload, 1 operation, 4 library, version original, 3 metadata and archive | 4.9a |
| `documents_collections/1` | 7 collection | 4.14 |
| `documents_annotations/1` | 5 annotation | 4.17 |
| `documents_citations/1` | `document-citations/preview` (plus `evidence-citations/preview` and evidence 4 admission) | 4.20 |
| `documents_usage/1` | `document-versions/{id}/usage` | 4.22 |
| `documents_extraction/1` | 5 extraction, version fragments | 4.24 |
| `documents_search/1` | `document-search` | 4.25 |
| none (not mounted, PD-4.1) | 3 delete, 4 export, 4 import, 2 restore | — |

### Code locations fixed by the factorization schedule (D-18)

- **Routes.** Phase 3 task 3.3a splits the API into per-owner routers (`application/src/hyprn_mvp_app/routes/<owner>.py`, each `router(deps) -> APIRouter`); `api.py` keeps the edge (middleware, auth dependency, envelope, `create_app` composition), and the HTTP helpers routers share live in the edge-helper module 3.3a names. Task 4.1 creates `routes/documents.py`; every later Documents route goes there. A non-Documents route that a task changes (evidence create and revise, model assumption evidence, configuration and approach, run history, receipts, capabilities) goes to the module that checkpoint 3.3a records for its owner. In this phase `api.py` changes only to compose the Documents router and for the chunk-route body exemption in the edge middleware (4.1).
- **Views.** Phase 3 task 3.3b gives the study shell a closed view registry: `ui/src/views/registry.ts` and one module per view (`{name, parseLink, render(ctx), guard?, available(capabilities)}`). The Documents library (4.13), reader (4.26) and cited-source view (4.29) are view modules under `ui/src/views/`, named after the convention of the modules 3.3b creates. `ui/src/Workspace.tsx` changes only for view-independent shell behaviour (4.22a clears the shell's lists on a confirmed access loss).
- **Groups.** After task 4.4 every test group is one entry file `deployment/groups/<family>/<group>.json`, loaded by `deployment/group_registry.py`; `deployment/checks.py` changes only for runner behaviour. Documents entries stay in `deployment/groups/documents/`; the Documents runner modes, test selection and measured validators live in `deployment/documents_groups.py`. After task 4.4a every scoped browser fixture serves the UI and runs Playwright through `deployment/tests/browser_harness.py`.
- **Contract schemas.** After Phase 2 task 2.8 the Documents-only definitions and the registry live in the non-attested `contracts/schemas/documents.schema.json`, loaded through `contracts.validator(name)`, and the execution schema is generated as the closure of what execution validation and worker admission name. Documents code reads definitions and the registry only through `hyprn_mvp_app.contracts`, never by opening a schema file, so the split moves no Documents code. A Documents-only definition change (4.32, the Documents part of 4.34) re-attests nothing. Under the split approved at Phase 2 checkpoint 2.8a, the citation vocabulary that evidence 4 references stays in `model.schema.json`, an attested input; the chain amendment (4.34) adds its non-Documents definitions there, so the attested inventory drifts from 4.34 until the chain's single re-attestation in 4.37, as it did before the split. The execution schema changes only by regeneration inside that re-attestation.
- **Recovery.** Phase 3 task 3.3d adds the server-decided `recovery` field to command receipts (closed values as 3.3d defines them, for example `adopt`, `wait`, `resend_same_command`, `uncertain`, `refused`), owned by `store`. Task 4.9b declares the rows of every document receipt category in that table; the UI reads the field and keeps no rule per category (D-03).
- **Version families (4.37–4.38).** The scientific chain reads record versions through version-family capabilities in `execution_bundle` (`family(record).has(capability)`: `carries_dependencies`, `typed_units`, `polish_envelope`, `approach_closure`, `document_citations`). The attested `execution_bundle` change happens only in the re-attesting task: 4.37 adds the table as its first step (with property tests that it reproduces `RETAINED_PAIRINGS` and the replaced predicates, and before and after counts) and moves `configuration`, `approach`, `execution` and `computational_export` to capability questions, replacing the explicit version checks 4.35 adds for its new versions; 4.38 moves `history` and `modified_runs`. The worker keeps its own table (trust boundary). The chain re-attests the worker once, in 4.37 (see "Stale-attestation window").

### Parser, extraction and search

- Parser image: Phase 2's digest-pinned CPython 3.12 base; the wheel fetched by pinned filename into the parser cache and verified (size, SHA-256) against `integration/document-parser.lock.json`, then installed in an offline build with `--no-deps --no-index --require-hashes --only-binary=:all:` and re-hashed inside the build (PD-4.7). Tag `hyprn-mvp-parser:<build-input-digest16>`.
- Launch: `--network none`, non-root, read-only root and input, `--cap-drop ALL`, no-new-privileges, 1 CPU, 512 MiB with equal swap, 64 PIDs, 64 MiB scratch tmpfs, an output cap, a 30 s external wall clock, a fixed command, the label `org.hyprn-mvp.parser`; containers are reaped by label at writer start and in a `finally` block. Limits come from the tracked policy file `integration/document-parser-policy.json` (D-07), hashed into the parser configuration digest.
- Containment evidence is recorded like worker attestation; extraction start refuses without current evidence for the exact image and policy digests (D-05).
- Search: application-store projection keyed by version, extraction, artifact and artifact SHA-256, rebuilt from native artifacts through the read loop and checked against manifest page hashes. Case-insensitive matching uses a length-preserving per-code-point lowercase fold, so snippet offsets equal source offsets. Quotations never come from the projection.
- Cursors: opaque, HMAC-SHA-256 over the canonical token (actor, study, route, query and filter digest, projection revision, position, expiry 5 minutes) with a key generated at application start by `secrets.token_bytes(32)` and held only in process memory. A restart invalidates outstanding cursors; the client restarts the listing. No key in a file, environment variable or the repository; every page re-authorizes.

### Operation ownership and agent rights (ADR-0004, ADR-0003)

Traced to the central invariant of ADR-0004: an operation produces one authoritative outcome that every client can subsequently reference, inspect and act upon, without reconstructing or repeating the operation. Every Documents operation below has one owner in the application, delegates execution and persistence to the engine that owns it, and leaves a stored outcome that the UI (and later agents) read back. "Lifecycle" says whether the operation needs a durable, identified, observable outcome (shared identity, durability, consistency, observability or recovery). The agent column is the ADR-0003 class that the later agent document tools and Phase 3's route classification (`agent_tools/write_policy.py`, which reads the route table of `contracts/documents.md`) must follow; no agent tool is built in this phase.

| Operation (routes under `/api/1/studies/{study_id}/`) | Owner (application) | Delegated to | Stored outcome | Lifecycle | Agent class (ADR-0003) | Tasks |
|---|---|---|---|---|---|---|
| Upload: `POST document-uploads`, `PUT …/chunks/{offset}`, `POST …/complete`, `GET document-uploads/{id}`, (OQ-5) `GET document-uploads` | `documents.py` (upload, spool, operation state machine) | Host single writer → AiiDA original node (`document_bridge.py`, `NativeDocuments`) | `DocumentOperation1` (`receiving → … → published`) and the published document version | yes | record; not offered in the first agent version (documents §18 Q3, a scope choice) | 4.1, 4.9a, 4.9b, 4.32 |
| Operation status: `GET document-operations/{id}`; receipts `GET commands/{id}?category=document_*` | `documents.py`; `store` receipts, with the server-decided `recovery` row of each document category (Phase 3 task 3.3d) | — | the operation and its receipt (read only; never retries or launches) | — | read | 4.1, 4.9b |
| Library and originals: `GET documents`, `documents/{id}`, `…/versions`, `document-versions/{id}`, `…/original` | `documents.py` | Read process (read verbs only) → AiiDA bytes | none (reads) | — | read | 4.1, 4.8, 4.9a |
| Metadata: `PATCH documents/{id}` | `documents.py` | — (application store) | family revision | yes | record | 4.9a |
| Archive and unarchive: `POST documents/{id}/archive`, `…/unarchive` | `documents.py` (archive state) | — | archive state with actor and time | yes | **human-only** | 4.9a, 4.33 |
| Collections: `POST/GET document-collections`, `GET/PATCH document-collections/{id}`, `GET/POST …/members` (add, remove, replace) | `documents.py` (operation, association) | Host single writer → AiiDA Group with witness | `DocumentOperation1` and the collection revision; membership never pins history | yes | record (membership changes allowed; exact pins kept) | 4.7, 4.14, 4.31 |
| Collection deletion: `DELETE document-collections/{id}` | `documents.py` | Host single writer → terminal Group and witness (§9.1) | `DocumentOperation1` and the terminal witness | yes | **human-only** (deletion of a saved record) | 4.7, 4.14 |
| Annotations: `GET/POST document-versions/{id}/annotations`, `GET/PATCH …/{annotation_id}` | `documents.py` (operation, association) | Host single writer → AiiDA annotation object | `DocumentOperation1` and the annotation revision | yes | draft (working material) | 4.12, 4.17, 4.27 |
| Annotation deletion: `DELETE …/annotations/{annotation_id}` | `documents.py` | Host single writer | `DocumentOperation1`; frozen snapshots in evidence never change | yes | draft (working material: allowed with the current revision) | 4.12, 4.17 |
| Extraction: `POST/GET document-versions/{id}/extractions`, `GET document-extractions/{id}`, `…/result`, `POST …/retry`, `GET document-versions/{id}/fragments` | `documents.py` (attempts) | AiiDA calcfunction → contained parser | the extraction attempt (each retry a new attempt); results are read from it, never recomputed for display | yes | record (bounded by extraction limits) | 4.21, 4.24 |
| Search: `GET document-search` | `document_search.py` | — | none: a rebuildable projection keyed by extraction digest, never authoritative (rebuild-equals test, 4.25) | — | read | 4.25 |
| Citations: `POST document-citations/preview`, `POST evidence-citations/preview`; evidence create and revise with `EvidenceCreate4`/`EvidenceRevise4` | `document_citations.py` resolves; the evidence owner in `store` freezes in one evidence transaction | Read process for fragments | the evidence version with frozen `DocumentCitation1` descriptors (preview has no persistent effect) | yes (evidence commit) | record | 4.20, 4.22, 4.27 |
| Usage: `GET document-versions/{id}/usage` | `documents.py`, computed from authoritative records | — | none (read) | — | read | 4.22 |
| Document-bearing chain (configuration, approach closure, bundle, history, seed) | `configuration`, `approach`, `execution_bundle` (version families and their capabilities), `history`, `modified_runs` | Modeling service (private projection), restricted worker (its own version table) | the frozen records of each owner; no new execution state | yes | as the owning record | 4.34–4.39 |
| Permanent deletion: `document-deletions/*` | not mounted (PD-4.1) | — | — | — | **human-only** (deletion of saved records) | later |
| Export: `document-exports*` | not mounted (PD-4.1) | — | — | — | read / record (not human-only) | later |
| Import: `document-imports*` | not mounted (PD-4.1) | — | — | — | not offered to agents (scope choice, documents §18 Q3) | later |
| Restore from backup: `document-restores*` | not mounted (PD-4.1) | — | — | — | operator only | later |

Rules this plan keeps, each a form of the central invariant:

- **No client orchestration.** The UI composes operations whose outcomes stand alone: an abandoned upload is a stored operation that expires under its lease (never a half-published version); saving a citation creates the evidence version, and attaching it to an owner is a separate operation on that owner (§15.4); a status check reads the operation and never resubmits; recovery after a lost reply follows the receipt's server-decided `recovery`, so no client holds its own recovery table (ADR-0004 consequences 2 and 4).
- **No parallel representation.** The application keeps identity, associations, operations, receipts and the search projection; bytes, collections, annotations and extraction results stay in AiiDA; the operation state machine records command intent and publication proof, not a second copy of the AiiDA process lifecycle.
- **Results are read, not repeated.** Reader text, fragments and quotations come from the stored extraction artifacts; a new extraction is an explicit new attempt.
- **Interaction state stays in the client.** Until task 4.32, the Uploads panel lists uploads started in the current page session; that list is interaction state, and recovery always reads the server's operation (after 4.32, `GET document-uploads`).
- **Route table is the classification source.** Any task that adds or changes a mutating Documents route also updates the route table in `contracts/documents.md`, so Phase 3's classification test sees it, whichever phase lands first.

## Decisions and defaults applied

- **D-01 to D-12** and **D-18** (locked in `04-CONTEXT.md`) are implemented as written; each task cites the ones it implements.
- **PD-4.1** Steps 14–18 are a later phase. Permanent deletion, export, import and restore routes are not mounted and stay outside every advertised slice. Archive and unarchive (API, library slice), remove from collection and delete collection are available. Archive and unarchive controls are part of the deferred lifecycle UI (UI-SPEC Q2 default: no archive controls this phase). DOC-01 stays `partial`.
- **PD-4.2 / §18 Q1** The UI says "Annotations", never "notes"; annotations stay off the Evidence page. The frozen copy reads "Annotation saved with this citation — later edits and reprocessing do not change it" (UI-SPEC Q1).
- **PD-4.4 / §18 Q5** Text-first reader only; uploads are never rendered.
- **PD-4.5 / §18 Q9** The contracted chunked upload protocol for every edition.
- **PD-4.6 / §18 Q7** The study-scope check on every route always (task 4.9b's matrix covers IDs, cursors, caches, snippets and downloads); the full persona, revocation and cache matrix waits for multi-user cloud.
- **PD-4.7** The parser image build fetches the wheel by pinned filename and verifies size and SHA-256 against the lock (fail closed); no vendored wheel. The version itself is OQ-2.
- **PD-4.8** `documents` stays in `capabilities.unavailable` through Phase 4; removing it is a Phase 5 action at the release gate.
- **Capability slices** (reconciles "advertisement switches per delivered step" with PD-4.8; research OQ5 / UI-SPEC Q3): additive slice IDs in `document_slices`, defined in task 4.9a with contract tests, each advertised only when its routes are mounted. Rationale: features appear only when implemented (D-08) while the umbrella capability honours the release gate.
- **§18 Q10** Copy follows §15.5 and `design-system/Naming.md`; Naming.md wins on conflict ("Version <short ID>" instead of "exact version"; "Annotation saved with this citation…"). Task 4.5 records the names in Naming.md.
- **ADR-0003 and ADR-0004** (accepted 2026-10-13): every Documents operation is listed with its owner, delegated engine, stored outcome and agent class in "Operation ownership and agent rights"; collection deletion, permanent deletion, archive and unarchive are human-only; collection membership and working annotations (including their deletion) are agent-eligible for the later document tools; each task that adds or changes a mutating route keeps the route table of `contracts/documents.md` current, which Phase 3's route classification reads.
- **Out of this phase:** §18 Q2 and Q3 (agent document tools, whose effects ADR-0003 now fixes, and agent upload), Q6 (cloud backend requalification), Q11 (authored documents).
- **UI-SPEC Q6–Q11 defaults** applied: "Used by" with step 10 (task 4.22 API, task 4.28 UI); one file per upload dialog; extensions `.pdf .txt .md .markdown .csv`; case-insensitive, length-preserving search folding with the help line "Finds the words as typed. Upper and lower case are treated the same."; explicit "Extract text" (nothing starts after upload); "Check what happened" for document operations.
- **Signed cursor key** (research OQ8, planner's discretion): the in-memory per-process HMAC key above. Rationale: satisfies "signed cursor" without storing a key anywhere; cursors are short-lived page tokens.
- **Upload spool** (research A8): the application store folder, with the application as its single writer and the host as a read-only resolver (see "Upload spool"). No dedicated mount is needed.
- **Study archive** (OQ-4 pending): document writes behave exactly like every other record in an archived study today (archive is presentation state only); task 4.33 applies whichever answer the product owner gives.
- **Collection `replace`** (OQ-3 pending): `action: "replace"` is refused before any effect with `unsupported_capability` 422 until task 4.31; add and remove proceed.
- **Factorization schedule (D-18, product owner; `.planning/codebase/FACTORIZATION.md`):** items 3 and 5 are folded into this phase as tasks 4.4 (one declarative registry for every test group: one entry file per group under `deployment/groups/<family>/`, loaded by `deployment/group_registry.py`, with the Documents runner modes and validators in `deployment/documents_groups.py`) and 4.4a (one browser-fixture harness, `deployment/tests/browser_harness.py`, with the isolated Documents API on it); item 10 as task 4.22a (the remaining hosts on the shared access-loss seam, immediately before the citation UI of 4.23); item 12 into 4.37–4.38 (version-family capabilities, added inside the one re-attestation of 4.37). Items 8, 9 and 2 arrive as Phase 3 prerequisites (3.3a before 4.1, 3.3b before 4.13, 3.3d before 4.9b) and item 11 as a Phase 2 prerequisite (2.8 before 4.32, 4.34 and 4.37). Items 13 and 14 come after the first release ("Deferred work"). Rationale: after 4.4 no Phase 4 task edits `checks.py` and no Phase 2 or Phase 3 task needs to, so the runner stops being a serialization point; after 4.4a a containment or header fix in a browser fixture is made once.
- **Tracer** (planner's discretion): the upload → published version → exact download slice, run in-process through the real codecs, because it crosses every backend layer (API, application store, write queue, single writer, native storage, publication, read mailbox). The executor supervision hook waits for Phase 2 tasks 2.3 and 2.8 (task 4.19); it is wiring, not architecture.

## Open questions for the product owner

Each blocks only the tasks named; everything else proceeds. Answers are recorded as D-13 to D-17 in `04-CONTEXT.md`.

| # | Question | Options and recommendation | Blocks |
|---|---|---|---|
| OQ-1 (D-13) | The allocated document-bearing chain (Configuration5 → Frozen6, Bundle7, History5, Seed5; closure 2) pairs only with Model2 and Model3, while the application writes Model4 and closure 3 (Frozen7, Bundle8, History6, Seed6, Closure3). | (a) Amend `contracts/documents.md` and the schemas with a document-bearing chain over the current versions (recommended; RISKY: departs from D-06 "as allocated"); (b) restrict citations in configurations, approaches and runs to Model2/3 (conflicts with authoring current formats). | 4.34–4.39 (steps 11, 12 and citation paths 2–4 of step 13); checkpoint 4.3 precedes them |
| OQ-2 (D-14) | pypdf 6.20.1 (published 2026-10-12, security fix for cyclic trees) or the audited 6.20.0. | (a) Re-audit and adopt 6.20.1 (recommended): update lock, provenance, licensing, `contracts/documents.md` and `docs/specs/documents.md` pins; (b) keep 6.20.0 with a recorded accepted risk (containment bounds denial of service). | 4.6, 4.11, 4.15, 4.18, 4.21, 4.24–4.30 (parser image and everything that needs extraction: search, reader, page and passage locators, annotations and citing in the reader); checkpoint 4.2 precedes them |
| OQ-3 (D-15) | Meaning of the `replace` member action in `DocumentCollectionMembersChange1`. | Recommended: per family, swap the active member for the listed version in one revision-checked batch; wording only in `contracts/documents.md`. | 4.31 (only `replace`; add and remove ship in 4.7, 4.14, 4.16) |
| OQ-4 (D-16) | Archived studies (PD-4.3 versus "archive is presentation state only" in `application/generate_contract.py`). | (a) Documents read-only in an archived study (PD-4.3; creates a second archive meaning, RISKY); (b) documents writable like every other record (consistent). | 4.33 |
| OQ-5 (D-17) | No route lists a study's unfinished or failed uploads, so recovery states disappear from the library after a reload (success criterion 2). | Recommended: a study-scoped read of recent uploads within the 24-hour retention (`GET document-uploads`, contract addition). | 4.32 (the route and the reload part of the Uploads panel) |

One planning finding is recorded rather than asked: `DocumentExtractedSpanLocator1` carries `start` and `end` as Unicode code points and has no UTF-16 field, so the server cannot receive browser UTF-16 offsets. The browser converts the reader's UTF-16 range to code points with one tested helper (`ui/src/documentOffsets.ts`, task 4.28), and the server verifies bounds, artifact identity and hash and computes the quotation itself (tasks 4.20, 4.27). This keeps the closed wire contract and the server's authority over every quotation (D-06).

## Tasks

### Task 4.1 (tracer) — Upload to exact download through the single writer and the read mailbox

<task type="tracer" id="4.1">

<name>Task 4.1 (tracer) — Upload to exact download through the single writer and the read mailbox</name>

<reversibility rating="costly">The application document tables become the store layout every later Documents task extends; changing them later needs a store migration (development run data is discardable, authoring records are not).</reversibility>

<files>

- create `application/src/hyprn_mvp_app/documents.py`, `application/src/hyprn_mvp_app/document_bridge.py`, `application/src/hyprn_mvp_app/routes/documents.py` (`router(deps)` with the six routes), `deployment/document_native_runtime.py`, `deployment/tests/documents_bridge_fixture.py`, `application/tests/test_documents_upload_api.py`;
- modify `application/src/hyprn_mvp_app/store.py` (additive tables), `application/src/hyprn_mvp_app/api.py` (composition only: `create_app` includes the Documents router; plus the chunk-route body exemption in the edge middleware), `application/src/hyprn_mvp_app/dispatcher.py` (bridge method `document_write`; one `documents_once` call per serve iteration), `application/generate_contract.py`, the regenerated `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts`, `application/tests/test_module_boundaries.py`, `deployment/checks.py` (register `documents-upload-api`; Documents groups re-run under their registered interpreter);
- `integration/src/hyprn_mvp_integration/documents.py` and `integration/tests/test_documents_native.py` only where step 1 finds a gap against the contract.

</files>

<read_first>

- `docs/specs/documents.md` §§3–6, 11, 16; `contracts/documents.md` ("Byte transfer and publication", "Fixed bridge", "State and reconciliation", "Structural checks versus runtime verification")
- the Documents registry (`routes`, `bridge`, `limits`, `operation_transitions`), read through `hyprn_mvp_app.contracts`: in `contracts/schemas/documents.schema.json` once Phase 2 task 2.8 has landed, otherwise in `contracts/schemas/model.schema.json`
- `integration/src/hyprn_mvp_integration/documents.py`, `integration/tests/test_documents_native.py`
- `application/src/hyprn_mvp_app/api.py` (the edge after Phase 3 task 3.3a), the per-owner route modules under `application/src/hyprn_mvp_app/routes/` and the edge-helper module 3.3a names (checkpoint `phases/03-agent-tools-for-coding-agents/checkpoints/3.3a.md`), `store.py`, `dispatcher.py`, `computational_export.py`, `contracts.py`; `application/generate_contract.py`; `application/tests/test_module_boundaries.py`, `application/tests/test_computational_api.py`
- `deployment/dispatch_runtime.py` (`bridge_child`, `native_call`), `deployment/tests/test_bridge.py` (`wire`), `deployment/checks.py` (`DOCUMENTS_ROUTES`, `run_documents`, `run_qualification`)
- `04-PATTERNS.md` sections for these files; `04-RESEARCH.md` Patterns 1 and 2, Pitfalls 2 and 3

</read_first>

<action>

- **Goal:** a 300 KiB UTF-8 text file uploaded in two chunks through the public API becomes a published version whose exact bytes download through the read mailbox, again after the application and the native side restart; a reply lost after the native commit publishes exactly once. This is the thinnest path through every backend layer the phase touches: API (the Documents router) → application store → write queue drained by the dispatcher serve loop → closed write frame → host handler → `NativeDocuments` → publication → read mailbox → closed read frame → host handler → bytes (D-01, D-02, D-03, D-09; the contracted chunked protocol of PD-4.5; the per-owner router of D-18).
- **Depends on:** Phase 1 complete; Phase 3 task 3.3a (per-owner API routers) verified. **Parallel:** Phase 2 tasks 2.4 and 2.7 only (disjoint from 4.1's files; 2.3 shares `application/tests/test_module_boundaries.py`); no Phase 3 task (`api.py` composition, store, module boundaries and contract files).
- **Steps:**
  1. Check `NativeDocuments` (`store_original`, `reconcile`, `descriptor`, `read`) and its tests clause by clause against `contracts/documents.md`; record each clause as met or fixed in the checkpoint. Fix only real gaps; keep lazy AiiDA imports.
  2. Store, additive (`CREATE TABLE IF NOT EXISTS`): `document_families`; `document_versions` (update and delete refused by trigger); `document_uploads` (reserved IDs, expected metadata, received bytes, per-offset chunk digests, 24-hour lease, spool name); `document_operations` (state `CHECK` over the registry operation states, `generation`, category, command id, payload digest, reserved IDs, result, failure); `document_associations` (private: version → native store and node; immutable); `document_read_requests` (mailbox: request id, study, actor, verb, input, state, reply, expiry 5 minutes). Receipts go through `Store.command` with the category `document_upload`.
  3. `hyprn_mvp_app.documents`: `DOCUMENT_LIMITS` equal to the registry `limits` without the portable keys (D-07); class `Documents(store, *, spool_root, native_store_id)` with `begin_upload`, `put_chunk`, `complete_upload`, `upload_status`, `version`, `original`, `next_write(operation)` and `apply_write_reply(operation, reply)`. Media type, file header and extension must agree, and text formats must decode as strict UTF-8, at begin and at complete. `spool_root` is `document-spool/` beside the application database; the application is its only writer (D-11). A missing reply leaves the operation `uncertain`; the next pass sends `reconcile` and publishes once on one exact witness.
  4. `hyprn_mvp_app.document_bridge`: frames validated as `DocumentBridgeWrite1` or `DocumentBridgeRead1` before any byte is written; `bridge_encode`, `bridge_decode` and `MAX_MESSAGE` reused from `dispatcher` (no second codec); `documents_once(store, bridge)` claims one queued or uncertain operation under the generation fence; `reads_once(store, bridge)` answers one mailbox row. In `dispatcher.py`, the bridge method `document_write` has arity 1 (the closed frame, validated on both ends), and the serve loop calls `documents_once` once per iteration, also while attestation is not ready.
  5. `deployment/document_native_runtime.py`: `handle_write(frame, *, documents, spool_root)` admits `store_original` and `reconcile`; `handle_read(frame, *, documents)` admits `descriptor` and `original`; every other verb, method or shape is refused before any native or file access. `transfer_id` resolves to exactly one regular file beneath the spool root, opened read-only with `O_NOFOLLOW`, exact size and SHA-256; the host never creates, writes or deletes spool files.
  6. Routes, in `routes/documents.py` as `router(deps) -> APIRouter` on the pattern of the routers 3.3a created (shared helpers from 3.3a's edge-helper module, never from `api.py`), composed by `create_app`: `POST document-uploads`, `PUT document-uploads/{upload_id}/chunks/{offset}`, `POST document-uploads/{upload_id}/complete`, `GET document-uploads/{upload_id}`, `GET document-versions/{version_id}`, `GET document-versions/{version_id}/original`. Authorize the route's study before any lookup and again after the native read (D-02). The `boundaries` middleware exempts exactly the chunk PUT (route-exact pattern) from the JSON-only rule, caps its streamed body at 262,144 bytes, requires `application/octet-stream`, and keeps the host, origin, session and CSRF checks. Downloads return the whole file as an attachment with an RFC 6266 / RFC 5987 encoded filename and `X-Content-SHA256`; the middleware adds `nosniff` and `no-store`.
  7. Generator mappings for the six routes (the chunk PUT gets an `application/octet-stream` request body and the `Origin` and `X-CSRF-Token` headers); regenerate `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts`; never hand-edit them.
  8. `test_module_boundaries.py`: `documents` imports only `contracts` and `store`; `document_bridge` imports only `contracts`, `store`, `documents` and the `dispatcher` codec; `routes.documents` imports only 3.3a's edge-helper module, `contracts`, `store`, `documents` and `document_bridge`, and only `api` imports it; none of them is reachable from `execution_bundle` or any attested root.
  9. `documents_bridge_fixture.py`: an in-process wire from `document_bridge` to `document_native_runtime` through the real codecs (the `test_bridge.wire` pattern), on the scratch AiiDA profile and a scratch spool root.
  10. Runner: register `documents-upload-api` (mode `native`, target `application/tests/test_documents_upload_api.py`). A direct `--group documents-*` started under another parent interpreter re-runs itself under the registered one, as `run_qualification` does.
- **Risks:** scope creep into library features (exactly the six routes); the body exemption leaking to other routes (acceptance test over every mounted route); two writers on the spool (test that the host never creates or deletes there).

</action>

<acceptance_criteria>

- `test_documents_upload_api_two_chunks_publish_exact_bytes`: the download body's SHA-256 and size equal the upload's; `X-Content-SHA256` equals it; the response is an attachment with `nosniff` and `no-store`.
- `test_documents_upload_api_bytes_survive_restart`: new `Store`, `create_app` and native backend objects on the same scratch files return identical bytes.
- `test_documents_upload_api_lost_reply_publishes_once`: a reply dropped after the native commit leaves the operation `uncertain`; the next pass reconciles; exactly one version row, one native original and one witness exist.
- `test_documents_upload_api_only_chunk_route_takes_raw_bytes`: every other mounted route answers 400 `invalid_request` to an `application/octet-stream` body; a 262,145-byte chunk gets 413 with the ledger unchanged; a chunk without the CSRF header gets 403.
- `test_documents_upload_api_foreign_and_unknown_ids_are_indistinguishable`: unknown and foreign upload and version IDs get the same status and body.
- `test_documents_upload_api_host_refuses_other_verbs_before_io`: any verb outside `store_original`, `reconcile`, `descriptor` and `original` fails with no native query and no file opened.
- `test_documents_upload_api_limits_equal_registry`: `DOCUMENT_LIMITS` equals the registry `limits` without the portable keys.
- `test_documents_upload_api_routes_come_from_the_documents_router`: every mounted route under `/api/1/studies/{study_id}/document` has its endpoint in `hyprn_mvp_app.routes.documents`; `api.py` defines no Documents route (its middleware's chunk-route pattern is its only Documents path).
- `GET /api/1/capabilities` still lists `documents` in `unavailable`; the module-boundary test passes with the three new modules registered.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-upload-api</automated>
<fails_when>exit status is non-zero, or the group's `tests.json` reports `passed` false, `tests` 0 or `skipped` above 0</fails_when>
<automated>python3 -B deployment/checks.py --group documents-native-originals</automated>
<fails_when>exit status is non-zero: an adapter fix from step 1 broke the qualified originals behaviour</fails_when>
<automated>python3 -B deployment/checks.py --group locality-contracts</automated>
<fails_when>exit status is non-zero, including a module-boundary assertion naming `documents`, `document_bridge` or `routes.documents`</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero: the committed OpenAPI or TypeScript differs from the generator output or names an unregistered route</fails_when>
<automated>python3 -B deployment/checks.py --group combined-security</automated>
<fails_when>exit status is non-zero: the middleware change weakened an existing request or recovery check</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.1.md` is verified by the orchestrating session.</done>

</task>

### Task 4.2 — Decision: parser wheel version (OQ-2)

<task type="checkpoint:decision" id="4.2" gate="blocking">

<name>Task 4.2 — Decision: parser wheel version (OQ-2)</name>

<reversibility rating="costly">Every extraction attempt records the parser identity; changing the pinned wheel later means a new audit, a new image and new attempts, never a rewrite of recorded ones.</reversibility>

<decision>Which pypdf wheel the parser image installs: the audited 6.20.0 or 6.20.1 after a fresh audit.</decision>

<context>D-05 and `integration/document-parser-provenance.md` pin 6.20.0. pypdf 6.20.1 was published on 2026-10-12 with a security fix for cyclic trees (PR #4188, no advisory identifier yet). The provenance record says a newly applicable advisory blocks installation for review; the research legitimacy check rated the package suspicious only because of that fresh release. Tasks 4.6, 4.11, 4.15, 4.18, 4.21 and 4.24–4.30 wait for this answer.</context>

<options>
<option id="option-a"><name>Re-audit and adopt 6.20.1 (recommended)</name><pros>Ships the cyclic-tree fix; no parser with a known fixed defect</pros><cons>A full audit (registry, wheel RECORD, tag correspondence, notices, advisories) and pin updates in the lock, provenance, `docs/legal/licensing.md`, `contracts/documents.md` and `docs/specs/documents.md` §7</cons></option>
<option id="option-b"><name>Keep 6.20.0 with a recorded accepted risk</name><pros>No new audit; D-05 as written</pros><cons>Ships a version with a known fixed defect; relies on containment (30 s, 512 MiB, 64 PIDs, no network) to bound it</cons></option>
</options>

<read_first>

- `04-RESEARCH.md` "Package Legitimacy Audit" and Open Question 2; `integration/document-parser-provenance.md`; `docs/legal/licensing.md` §5

</read_first>

<action>

- **Goal:** the product owner chooses the wheel; the orchestrating session records the answer as `D-14 (OQ-2)` in `04-CONTEXT.md` (for option b, with the accepted-risk statement in the product owner's words).
- **Depends on:** nothing; take it while task 4.1 runs.

</action>

<acceptance_criteria>

- `04-CONTEXT.md` holds exactly one decision line containing `D-14 (OQ-2)` that names one version and, for option b, the accepted risk.

</acceptance_criteria>

<verify>
<automated>grep -c "D-14 (OQ-2)" .planning/phases/04-documents/04-CONTEXT.md</automated>
<fails_when>prints 0 and exits 1: no recorded answer</fails_when>
</verify>

<resume-signal>The product owner answers "6.20.1" or "6.20.0 with accepted risk"; the orchestrating session records it as D-14 (OQ-2).</resume-signal>

<done>The decision is recorded, and the checkpoint `phases/04-documents/checkpoints/4.2.md` names the answer, who gave it and when.</done>

</task>

### Task 4.3 — Decision: document-bearing chain for current models (OQ-1)

<task type="checkpoint:decision" id="4.3" gate="blocking">

<name>Task 4.3 — Decision: document-bearing chain for current models (OQ-1)</name>

<reversibility rating="one-way">The chosen configuration, frozen, bundle, history, seed and closure versions become stored record formats and public read types; changing them after runs exist needs new versions and readers, never edits of saved records.</reversibility>

<decision>How citations reach configurations, approach versions and runs when the application writes Model4 and approach closure 3.</decision>

<context>`contracts/documents.md` allocates Configuration5 / private 4 → FrozenConfiguration6, ExecutionBundle7, RunHistory5, ModifiedRunSeed5 and ApproachClosure2, paired only with Model2 and Model3. Current Model3 and Model4 configurations are Configuration4, and Model4 or closure-3 runs freeze as FrozenConfiguration7 and ExecutionBundle8 with History6, Seed6 and Closure3. D-06 says "implemented as allocated". Tasks 4.34–4.39 (steps 11, 12 and citation paths 2–4) wait for this answer.</context>

<options>
<option id="option-a"><name>Amend the contract with a document-bearing chain over the current versions (recommended)</name><pros>Citations work for every model engineers author today</pros><cons>Departs from D-06 "as allocated"; a contract-only task (4.34) allocates new versions before step 11</cons></option>
<option id="option-b"><name>Restrict citations in configurations, approaches and runs to Model2 and Model3</name><pros>D-06 as written</pros><cons>Current Model4 and closure-3 work cannot cite documents through configurations or runs; conflicts with authoring only current formats</cons></option>
</options>

<read_first>

- `04-RESEARCH.md` Open Question 1 and Pitfall 1; `contracts/documents.md` "Exact scientific pairings"; `application/src/hyprn_mvp_app/execution_bundle.py` (`uses_polish_envelope`, `frozen_version`); `application/src/hyprn_mvp_app/configuration.py`

</read_first>

<action>

- **Goal:** the product owner chooses; the orchestrating session records the answer as `D-13 (OQ-1)` in `04-CONTEXT.md`, including the version names when option a is chosen (recommended: the next free version of each family).
- **Depends on:** nothing; take it while task 4.1 runs.

</action>

<acceptance_criteria>

- `04-CONTEXT.md` holds exactly one decision line containing `D-13 (OQ-1)` naming option a (with the allocated version names) or option b.

</acceptance_criteria>

<verify>
<automated>grep -c "D-13 (OQ-1)" .planning/phases/04-documents/04-CONTEXT.md</automated>
<fails_when>prints 0 and exits 1: no recorded answer</fails_when>
</verify>

<resume-signal>The product owner answers "amend" (with version names) or "restrict"; the orchestrating session records it as D-13 (OQ-1).</resume-signal>

<done>The decision is recorded, and the checkpoint `phases/04-documents/checkpoints/4.3.md` names the answer, who gave it and when.</done>

</task>

### Task 4.4 — Declarative registry for every test group, the Documents groups and the native-backed browser mode

<task type="auto" id="4.4">

<name>Task 4.4 — Declarative registry for every test group, the Documents groups and the native-backed browser mode</name>

<files>

- create `deployment/group_registry.py` (stdlib only: entry loading, closed schema, derived sets), `deployment/groups/<family>/<group>.json` (one entry per group registered when the task runs: every group of `deployment/checks.py` today, the Documents groups including `documents-upload-api` from 4.1, the Phase 2 groups present, the Phase 3 groups present under `deployment/groups/agent/`, and the new `documents-registry`), `deployment/documents_groups.py` (Documents runner modes, test selection, capability check, result checks and measured validators moved out of `deployment/checks.py`), `deployment/tests/test_documents_registry.py`;
- modify `deployment/checks.py` (sets derived from the entries; `run_group` and `child` dispatch on `runner`; `--list` printed from the entries), `deployment/tests/test_repository_guard.py` (registry guard cases read the loader; the new cases of step 8).

</files>

<read_first>

- `.planning/codebase/FACTORIZATION.md` item 5 (and item 1 for the test-module orphan guard); `.planning/codebase/TESTING.md` "Group Registry"
- `deployment/checks.py`, whole file: `GROUPS`, `DOCUMENTS_ROUTES`, `DOCUMENTS_MEASURED_GROUP`, the `documents_*` helpers and `run_documents`, `GROUP_INTERPRETERS`, the `AE_*`, `APPROACH_*` and `UNITS_*` families and selections, `NATIVE_PYTEST_GROUPS`, `APPLICATION_PYTEST_GROUPS`, `CHILD_GROUPS`, `AGENT_PYTEST_GROUPS` and `AGENT_DIRECTORY_TARGETS` (`directory_target`), `OPT_IN_GROUPS`, `DOCKER_GROUPS`, `BROWSER_GROUPS`, `FIXTURE_GROUPS`, `FIXTURE_BROWSER_SPECS`, `must_pass_groups`, `list_groups`, `run_group`, `child`, `guard_child`, `contracts_child`, `findings_guards_passed`
- `deployment/tests/test_repository_guard.py` (`RegistryGuardTests`, `DocumentsGuardTests`, `AgentGroupsGuardTests`, `BrowserSpecRegistryTests`), `deployment/tests/test_units_fixture_guards.py` (registry reads); the test-module orphan guard added by Phase 1 task 1.11
- every module that imports names from `checks` (`git grep -n "from checks import\|import checks" -- deployment application integration`)
- `deployment/tests/documents_ui_fixture.py`, `deployment/tests/documents_native_fixture.py` (`start`)
- `04-PATTERNS.md` "deployment/checks.py" and "Group registry for every group"

</read_first>

<action>

- **Goal:** every test group, not only the Documents ones, is registered by one entry file and never by editing `deployment/checks.py`; the runner derives class, needs, interpreter and dispatch from the entries; the move changes no group's behaviour (`--list` identical except the new `documents-registry` line; every group passes or fails exactly as before); and native-backed browser groups get their own Documents mode (D-10, D-18; FACTORIZATION.md item 5).
- **Depends on:** 4.1 (its `documents-upload-api` group and the re-run under the registered interpreter). **Parallel:** with 4.5 and 4.6; Phase 2 tasks 2.3 and 2.7 only; not beside any Phase 2 or Phase 3 task that edits `deployment/checks.py` or `deployment/tests/test_repository_guard.py` or registers a group (a group registered concurrently would be missed by the migration).
- **Steps:**
  1. Before any edit, on the parent commit: record `python3 -B deployment/checks.py --list`, `--list --class must-pass` and `--list --class opt-in`, and run every registered group once (must-pass groups one by one or through `qualification`; opt-in groups record their refusal line), keeping each group's exit status and pass, fail and skip counts for the checkpoint. A group that already fails is recorded, not repaired here. The runs may be recorded in sub-steps per family within the same executor context (one family's groups at a time, each sub-step appending its rows to the checkpoint table); the summary evidence is the `qualification` run (exit status and per-group counts) and the opt-in refusal lines.
  2. Entry schema (closed; an unknown key or value fails loading): `group` (equal to the file name), `rank` (unique integer that orders `--list` and the qualification sequence as today, numbered with gaps so a later entry needs no renumbering), `class` (`must-pass` or `opt-in`), `needs` (a subset of `docker`, `browser`, `fixtures`, `installation`), `interpreter` (`native` or `contract`, mapped to the reviewed interpreters of `scoped_fixture`), `runner` (closed set: `pytest`, `unittest-guard`, `browser-isolated`, `browser-served`, `fixture`, `static`, `documents`), `targets`, and runner-specific keys from a closed list that express as data what `run_group` and `child` express by group name today: the pytest `-k` selections, the browser grep tag and fixture module (closed set of fixture modules), the exact test count of `findings-native-guards`, the guard step that `approach-contracts` runs first, the extra suite of `units-guards`, the mixed-repair targets of `units-native`, the `design-system/reference` precondition of `ui-fidelity`, a directory target admitted only where `directory_target` admits one today (the Phase 3 agent groups), and for `documents` the `mode` (`application/contracts`, `native`, `browser`, `browser-native`; tasks 4.30 and 4.36 add `served` and `modeling`), `selector` and `measured` validator id. Families are folders: `deployment/groups/documents/`, `deployment/groups/agent/` for Phase 3, and one folder per family of today's sets for the others (the checkpoint lists the mapping).
  3. `deployment/group_registry.py` loads `deployment/groups/*/*.json` and fails loading on an unknown key or value, a duplicate group or rank, a file name differing from its group, a missing target, or a runner-specific key under another runner. `deployment/checks.py` derives from it every set it keeps by hand today, under the same names and with the same values (`GROUPS`, `DOCUMENTS_ROUTES`, `GROUP_INTERPRETERS`, `AE_BROWSER_GROUPS`, `APPROACH_BROWSER_GROUPS`, `UNITS_BROWSER_GROUPS`, `AE_SELECTIONS`, `UNITS_SELECTIONS`, `CHILD_GROUPS`, `DOCKER_GROUPS`, `BROWSER_GROUPS`, `FIXTURE_GROUPS`, `OPT_IN_GROUPS`, `FIXTURE_BROWSER_SPECS` and the others), so every fixture and guard that imports them keeps working unchanged; `run_group` and `child` dispatch on `runner` and name no group; `list_groups` prints from the entries.
  4. `deployment/documents_groups.py` (stdlib only) takes `documents_interpreter`, `documents_targets`, `documents_capabilities`, `documents_results_passed`, `documents_report_passed`, `documents_child`, `run_documents` and the measured hook from `checks.py`; `DOCUMENTS_MEASURED` maps validator ids to functions, and `collection_protocol` keeps today's `documents_collection_evidence` semantics. Every name that tests and fixtures read from `checks` (`git grep -ohE "runner\.[A-Za-z_]+|from checks import [A-Za-z_, ]+" -- deployment`, for example `DOCUMENTS_ROUTES`, `documents_targets`, `documents_child`, `run_documents`, `documents_results_passed`, `documents_collection_evidence`) stays readable from `checks` with the same behaviour, and the scope globals the native tests read (`checks.PROJECTION_SCOPE`, `checks.NATIVE_BACKEND`) are still set on `checks`, whichever module the child code moves to.
  5. Mode `browser-native`: native interpreter, needs `docker` and `browser`, the child runs `documents_ui_fixture.run`, and the capability check requires `documents_ui_fixture.start_isolated_api` (task 4.4a provides it; until then a `browser-native` group refuses before any allocation). The existing `browser` mode keeps the contract interpreter. `documents_native_fixture.start` keeps refusing every mode except `native`.
  6. The test-module orphan guard of Phase 1 task 1.11 (every tracked `test_*.py` is selected by a group or listed as retired with a reason) reads targets through `group_registry`, so a module named only in an entry file counts as registered.
  7. `documents-registry` (`runner: documents`, mode `application/contracts`): `deployment/tests/test_documents_registry.py` covers the Documents entry refusals, checks that every `test_documents_*` function and every `@documents-*` tag in the tree is selected by exactly one registered group, and that a `browser-native` entry derives the native interpreter and both needs.
  8. Registry guard cases in `test_repository_guard.py` (`RegistryGuardTests`), named after the invariant, for example `test_every_group_is_registered_by_exactly_one_entry_file`, `test_registry_entries_refuse_unknown_keys_runners_needs_and_interpreters`, `test_runner_dispatch_names_no_registered_group` (no registered group name is a literal in `deployment/checks.py`) and `test_listing_and_qualification_order_follow_the_entry_ranks`. The existing registry guard cases pass unchanged, because the derived sets keep their names and values.
  9. After the edit, repeat step 1 on the committed tree, in the same per-family sub-steps: `--list` differs only by the added `documents-registry` line, and every other group's exit status and counts equal step 1's. Both tables, the two `qualification` summaries and the opt-in refusal lines go in the checkpoint.
- **Risks:** a group silently dropped, re-classed or moved to another interpreter (steps 1 and 9; orphan guards); qualification order drift (ranks reproduce today's order); a concurrent group registration lost (serialization in "Parallel work"); a fixture importing a name that disappeared (derived names kept).

</action>

<acceptance_criteria>

- `python3 -B deployment/checks.py --list` (and with `--class must-pass` and `--class opt-in`) on the committed tree equals the parent commit's output except one added `documents-registry` line; both outputs and the diff are in the checkpoint.
- Every group registered before the task has the same exit status and the same pass, fail and skip counts after it (table in the checkpoint, one row per group, opt-in refusals included).
- `deployment/groups/*/*.json` holds exactly one entry per group that `--list` prints, the `qualification` aggregate excepted; `deployment/checks.py` contains no registered group name as a literal.
- `test_documents_registry_refuses_unknown_keys_duplicates_and_missing_targets`, `test_documents_registry_every_documents_test_has_one_group`, `test_documents_registry_browser_native_runs_under_the_native_interpreter_with_docker_and_browser` and the `RegistryGuardTests` cases of step 8 pass.
- `findings-native-guards` still runs exactly 17 tests; `approach-contracts` still runs the guard first; `agent-tools` still takes its directory target.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-registry</automated>
<fails_when>exit status is non-zero, or an orphan Documents test, a duplicate selection or a malformed entry is reported</fails_when>
<automated>python3 -B deployment/checks.py --group guard</automated>
<fails_when>exit status is non-zero, including a registry guard case or a group-name literal left in `deployment/checks.py`</fails_when>
<automated>python3 -B deployment/checks.py --list</automated>
<fails_when>the output differs from the parent commit's `--list` output (recorded in the checkpoint) by anything other than the added `documents-registry` line</fails_when>
<automated>python3 -B deployment/checks.py --group documents-collection-protocol</automated>
<fails_when>exit status is non-zero, including a measured-artifact validation failure after the move</fails_when>
<automated>python3 -B deployment/checks.py --group findings-native-guards</automated>
<fails_when>exit status is non-zero, or the run does not count exactly 17 tests</fails_when>
<automated>python3 -B deployment/checks.py --group approach-contracts</automated>
<fails_when>exit status is non-zero, or the guard step did not run before the contract tests</fails_when>
<automated>python3 -B deployment/checks.py --group agent-tools</automated>
<fails_when>exit status is non-zero, or its directory target is refused</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero (the static runner)</fails_when>
<automated>python3 -B deployment/checks.py --group naming</automated>
<fails_when>exit status is non-zero (a new file, label or variable outside the `hyprn-mvp` namespace)</fails_when>
<automated>python3 -B deployment/checks.py --group qualification</automated>
<fails_when>its exit status differs from the parent commit's run, or a group's counts differ from its row in the checkpoint's before table</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.4.md` (both listings and their diff, the per-group before and after table, the family mapping) is verified by the orchestrating session.</done>

</task>

### Task 4.4a — One browser-fixture harness and the isolated Documents API on it

<task type="auto" id="4.4a">

<name>Task 4.4a — One browser-fixture harness and the isolated Documents API on it</name>

<files>

- create `deployment/tests/browser_harness.py` (stdlib plus the existing `TestClient`), `ui/playwright.documents.config.ts`, `ui/tests/documents-isolated-api.spec.ts`, `deployment/groups/documents/documents-isolated-api.json` (`runner: documents`, mode `browser-native`);
- modify the proxy copies `deployment/tests/ae_ui_fixture.py`, `deployment/tests/approach_ui_fixture.py`, `deployment/tests/units_ui_fixture.py`, `deployment/tests/ui_fixture.py`, `deployment/tests/combined_fixture.py`, `deployment/tests/findings_native_fixture.py`, the Playwright staging copy `deployment/tests/units_native_fixture.py`, and any Phase 3 browser fixture present when the task runs (for example `deployment/tests/agent_ui_fixture.py`); `deployment/tests/documents_ui_fixture.py` (`start_isolated_api`, `run`); the guard tests that patch or pin fixture internals: `deployment/tests/test_repository_guard.py`, `deployment/tests/test_units_fixture_guards.py`, `deployment/tests/test_findings_native_guards.py` (patch targets only).

</files>

<read_first>

- `.planning/codebase/FACTORIZATION.md` item 3
- `deployment/tests/ae_ui_fixture.py` (`run`: handler, write predicate, `/fixture/*` controls, 2 MiB cap, static `dist` containment, Playwright staging and `stats`), `approach_ui_fixture.py` (`run`), `units_ui_fixture.py` (`run`, `guarded_request`), `ui_fixture.py` (`run`), `combined_fixture.py` (`write_http_response`, the `web` mode handler; the modeling-contract double server is not a browser proxy), `findings_native_fixture.py` (the handler before its `ThreadingHTTPServer` call; the Playwright run with `durable_write`), `units_native_fixture.py` (Playwright staging), `foundry_ui_fixture.py` (`run`, `report_passed`; not migrated, see step 3)
- `deployment/tests/documents_ui_fixture.py`, `deployment/tests/scoped_fixture.py` (`run_export_dispatcher`, `create_native_fixture`, `clean_environment`, `validate_url`), `deployment/tests/documents_native_fixture.py` (`start`); `application/src/hyprn_mvp_app/document_bridge.py` (`documents_once`, `reads_once`, from 4.1)
- `deployment/tests/test_repository_guard.py` (`test_ae_browser_fixture_guards_before_server_or_application`; the `DocumentsGuardTests` cases that import `documents_ui_fixture`), `deployment/tests/test_units_fixture_guards.py`, `deployment/tests/test_findings_native_guards.py`
- `ui/playwright.isolated.config.ts`, `ui/tests/foundry-zoom.spec.ts`; `deployment/group_registry.py` and `deployment/documents_groups.py` (from 4.4)
- `04-PATTERNS.md` "deployment/tests/browser_harness.py" and "documents_ui_fixture.py"

</read_first>

<action>

- **Goal:** one harness serves every scoped browser fixture and runs its Playwright specs, so a containment, header or reporting fix is made once; each fixture keeps only its seed data, its `/fixture/*` controls, its write predicate and its body cap; and on that harness a real isolated API (real store and auth, scratch AiiDA, in-process writer and read loop, a declared modeling double) serves the UI to the Documents browser groups (D-10, D-18; FACTORIZATION.md item 3).
- **Depends on:** 4.4 (the `browser-native` mode, the loader and the shared `deployment/tests/test_repository_guard.py`). **Parallel:** with 4.7, 4.8, 4.9a and 4.10; not beside a Phase 2 or Phase 3 task that edits one of the fixtures above or `test_repository_guard.py`.
- **Steps:**
  1. Before any edit, run every group whose targets or fixture import a fixture this task changes (the checkpoint derives the list from the entries and the fixture imports; at least `ae-ui-evidence`, `ae-ui-model`, `ae-ui-configuration`, the six `approach-ui-*` groups, the four `units-ui-*` groups, `ui-a`, `ui-a-retained`, `ui-b`, `ui-c`, the native journeys that use `combined_fixture.py` (`native-a`, `native-b`, `combined-native`, `approach-native`, `ae-native`, `units-native`), `findings-native-preflight`, `findings-native`, `findings-native-read`, and any Phase 3 browser group) and the guard groups `guard`, `units-guards` and `findings-native-guards`; record each exit status and its counts.
  2. `browser_harness.serve(scope, app, *, dist, writable, controls, body_cap)` starts a `ThreadingHTTPServer` on `127.0.0.1` port 0 (URL checked with `scoped_fixture.validate_url`); forwards `/api/1/*` through `TestClient(app)` with today's header filtering (hop-by-hop and length headers dropped); refuses with 403 a non-GET route that `writable(route, method)` does not admit; applies `body_cap` (a byte count, a per-route function, or none where a fixture has no cap today, so the difference stays visible in one place); serves the static UI from `dist` with path containment (`is_relative_to`, regular files only); dispatches `controls` (`{path: handler}`) under `/fixture/`; tolerates a client disconnect after the response as `combined_fixture.write_http_response` does; and returns the URL and a stop function. `run_playwright(scope, *, tag, config_base, evidence)` writes the staging configuration inside the scope (`import base from` the given base configuration plus the fixture's spec match), runs the installed Playwright CLI with `--grep <tag>` and `--reporter=json`, writes the report and stderr into `evidence`, and returns the parsed `stats`. Neither adds behaviour that no copy has today.
  3. Move every proxy copy (`ae_ui_fixture.py`, `approach_ui_fixture.py`, `units_ui_fixture.py`, `ui_fixture.py`, `combined_fixture.py`, `findings_native_fixture.py`, any Phase 3 browser fixture present) onto `serve`, and every Playwright staging or run copy (`ae_ui_fixture.py`, `approach_ui_fixture.py`, `units_ui_fixture.py`, `units_native_fixture.py`, `findings_native_fixture.py`, `ui_fixture.py`) onto `run_playwright`. Write allowlists, body caps, controls and each fixture's own file-writing rules (for example the durable write in `findings_native_fixture.py`) stay per fixture and unchanged. `foundry_ui_fixture.py` serves no API and builds its own configuration and snapshot policy; it stays as it is, and the checkpoint records this one reviewed exclusion.
  4. Guard tests that patch fixture internals point at the harness instead (for example `test_ae_browser_fixture_guards_before_server_or_application` patches `browser_harness.ThreadingHTTPServer` and still proves that no server starts before the scope check); no guard assertion is dropped or weakened, and `findings-native-guards` still runs exactly 17 tests.
  5. `documents_ui_fixture.start_isolated_api(scope)` on the harness: `create_app`, `Store` and `Auth` on scratch stores; a scratch AiiDA profile; the production `documents_once` and `reads_once` driven by one background thread through the real codecs; a modeling double that refuses every call the Documents UI does not make; the Documents write predicate; PUT admitted only on the chunk route with its 262,144-byte cap, and 2 MiB elsewhere; controls under `/fixture/` to hold the writer (a running calculation), stop and start the read loop, toggle advertised slices, and stop the modeling double. `run(group=…)` calls `run_playwright` with `ui/playwright.documents.config.ts` (`testMatch` `documents-*.spec.ts`, grep on the group tag, evidence inside the scope, `HYPRN_MVP_UI_EVIDENCE_ROOT` admitted). The `DocumentsGuardTests` cases that pinned the refusal before this capability existed now pin its guards (scope check before any server, application or native import).
  6. `documents-isolated-api` (`browser-native`): `ui/tests/documents-isolated-api.spec.ts` proves the fixture: the served shell loads; an upload through `page.request` publishes and downloads exact bytes; holding the writer leaves the operation queued with waiting set; stopping the read loop makes a read answer `backend_unavailable` within the wait bound; nothing of the scope survives teardown.
  7. After the edit, repeat step 1 on the committed tree.
- **Risks:** a fixture's write allowlist or cap widened by the shared code (each stays a per-fixture argument; guard groups and the before and after counts); a disconnect or header difference between copies (the harness keeps the most conservative existing behaviour, and the checkpoint lists every difference found between copies and how it was kept); the isolated API loosening native-mode checks (`documents_native_fixture.start` unchanged).

</action>

<acceptance_criteria>

- Every group of step 1 has the same exit status and the same counts after the task as before it (table in the checkpoint); `guard`, `units-guards` and `findings-native-guards` (exactly 17 tests) pass.
- `git grep -n "ThreadingHTTPServer(" -- deployment/tests` matches only `browser_harness.py` and the private modeling-contract double in `combined_fixture.py`; `git grep -n "playwright/cli.js" -- deployment/tests` matches only `browser_harness.py` and `foundry_ui_fixture.py`.
- `python3 -B deployment/checks.py --list` on the merged tree differs from the `--list` output of 4.4a's own parent commit, taken on the merged tree, only by the added `documents-isolated-api` line, after excluding the entries that concurrent tasks added (each named in the checkpoint with its task).
- The `@documents-isolated-api` spec passes; after teardown no container with the scope's label and no scope folder remains.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-isolated-api</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or the spec reports a failed or skipped test</fails_when>
<automated>python3 -B deployment/checks.py --group guard</automated>
<fails_when>exit status is non-zero, including a fixture guard whose patch target no longer intercepts the server</fails_when>
<automated>python3 -B deployment/checks.py --group findings-native-guards</automated>
<fails_when>exit status is non-zero, or the run does not count exactly 17 tests</fails_when>
<automated>python3 -B deployment/checks.py --group units-guards</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-evidence</automated>
<fails_when>exit status is non-zero, or its counts differ from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-controller</automated>
<fails_when>exit status is non-zero, or its counts differ from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group units-ui-authoring</automated>
<fails_when>exit status is non-zero, or its counts differ from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group ui-c</automated>
<fails_when>exit status is non-zero, or its counts differ from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group units-native</automated>
<fails_when>exit status is non-zero, or its counts differ from the before table (combined web proxy and Playwright staging)</fails_when>
<automated>python3 -B deployment/checks.py --group findings-native-read</automated>
<fails_when>exit status is non-zero, or its counts differ from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group naming</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group hygiene</automated>
<fails_when>exit status is non-zero (an absolute path or a location literal in the harness)</fails_when>
<automated>python3 -B deployment/checks.py --list</automated>
<fails_when>the output differs from the `--list` output of 4.4a's own parent commit on the merged tree by anything other than the added `documents-isolated-api` line and the entries of concurrent tasks named in the checkpoint</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.4a.md` (the per-group before and after table, every difference found between the copies and how it was kept, the foundry exclusion) is verified by the orchestrating session.</done>

</task>

### Task 4.5 — Design-system additions for the library (A1–A4, A7)

<task type="auto" id="4.5">

<name>Task 4.5 — Design-system additions for the library (A1–A4, A7)</name>

<files>

- modify `design-system/Layouts.md`, `design-system/Naming.md`, `design-system/components/Tabs.md`, `design-system/components/Progress.md`, `docs/specs/ui-target.md` (§3.1), `ui/src/design/primitives.tsx` (`Progress`), `ui/src/design/components.tsx` (`Notice`), `ui/src/design/foundry.css`, `ui/src/design/index.ts`, `ui/design_smoke.mjs`, `ui/src/main.tsx` (imports the new stylesheet once);
- create `design-system/components/Notice.md`, `ui/src/documents.css`.

</files>

<read_first>

- `04-UI-SPEC.md` "Design-system additions" A1–A4 and A7, "Copywriting Contract", "Reader-facing names"
- `design-system/README.md`, `Layouts.md`, `Scientific-states.md`, `Naming.md`, `Coherence.md`, `components/Progress.md`, `components/Tabs.md`, `components/StatusTag.md`
- `ui/src/design/primitives.tsx` (`Progress`), `ui/src/design/components.tsx` (`StatusTag`, `Tone`), `ui/src/design/foundry.css` (`.hf-progress`, `.evidence-recovery`, `.overview-grid` media rules), `ui/src/design/index.ts`, `ui/design_smoke.mjs`, `ui/check_design_system.py`

</read_first>

<action>

- **Goal:** the design system names and contains everything the library screen needs before any Documents screen exists (UI-SPEC A1–A4 and A7; D-08, D-10).
- **Depends on:** 4.1. **Parallel:** with 4.4 and 4.6; any Phase 2 task; not beside a Phase 3 task that edits `design-system/Naming.md` or `ui/src/design`.
- **Steps:**
  1. A1: study tabs "Overview, Models, Configurations, Runs, Documents, Evidence" in `Layouts.md`, `components/Tabs.md` and `docs/specs/ui-target.md` §3.1; a "Documents" section in `Layouts.md` with the library, reader and cited-source compositions and the narrow-screen and 200 % rules of UI-SPEC A1.
  2. A2: `Naming.md` fixed labels with Documents; the rows of UI-SPEC "Reader-facing names" with their "Not in reader text" column; the plain-language resolutions ("Version <short ID>", never "exact version"; "Annotation saved with this citation — later edits and reprocessing do not change it"; "Saving waits for a running calculation to finish."; "Check what happened"), per §18 Q10 and PD-4.2.
  3. A3: `Progress({label, message, value, max, valueText})` per UI-SPEC A3: measured only for finite, non-negative safe integers with `value ≤ max` and `max > 0`; anything else renders exactly today's indeterminate markup with `label` only; never a percentage or remaining time. `Progress.md` gains a "Measured" paragraph.
  4. A4: `Notice({tone, title, children, actions, live})` per UI-SPEC A4, with `.hf-notice--<tone>` rules generalized from the existing `.evidence-recovery` banner, tokens only; `Notice.md`.
  5. A7: `ui/src/documents.css`: library grid `var(--panel-outline)` plus a fluid track, reader grid fluid plus `var(--panel-inspector)`, `var(--space-3)` gaps, `var(--space-6)` section separation; stacking below 1050px and single-column wrapping below 600px written only inside `@media` preludes.
  6. `design_smoke.mjs`: Progress indeterminate, measured and invalid pair; Notice in every tone and live mode; `Notice` in the expected export list.
- **Risks:** a colour or size literal outside tokens (checker); `Naming.md` edited concurrently by Phase 3 (serialize).

</action>

<acceptance_criteria>

- `python3 ui/check_design_system.py` prints no FAIL line; `python3 ui/design_tokens.py --check` and `python3 ui/test_design_tooling.py` pass.
- `node ui/design_smoke.mjs` passes, and its invalid-pair case renders a `<progress>` element without a `value` attribute.
- `git grep -n "Overview, Models, Configurations, Runs, Documents, Evidence"` matches `design-system/Layouts.md`, `design-system/Naming.md` and `docs/specs/ui-target.md`.
- `ui/src/Workspace.tsx` and, once Phase 3 task 3.3b has created it, `ui/src/views/registry.ts` are unchanged (no Documents tab before its slice exists).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero or a `FAIL` line is printed</fails_when>
<automated>python3 ui/check_design_system.py</automated>
<fails_when>any output line starts with `FAIL` or the exit status is non-zero</fails_when>
<automated>python3 ui/design_tokens.py --check</automated>
<fails_when>exit status is non-zero (stale generated tokens)</fails_when>
<automated>node ui/design_smoke.mjs</automated>
<fails_when>exit status is non-zero or a smoke check names `Progress` or `Notice`</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.5.md` is verified by the orchestrating session.</done>

</task>

### Task 4.6 — Parser pin record per the version decision

<task type="auto" id="4.6">

<name>Task 4.6 — Parser pin record per the version decision</name>

<precondition>`04-CONTEXT.md` records D-14 (OQ-2).</precondition>

<files>

- `integration/document-parser.lock.json`, `integration/document-parser-provenance.md`, `contracts/tests/test_document_parser_adoption.py`;
- with option a also `contracts/documents.md` (pin line), `docs/specs/documents.md` (§7 pin), `docs/legal/licensing.md` (§4 row).

</files>

<read_first>

- `04-CONTEXT.md` D-05, PD-4.7 and D-14; `integration/document-parser-provenance.md`; `integration/document-parser.lock.json`; `contracts/tests/test_document_parser_adoption.py`; `docs/legal/licensing.md` §§4–5; `04-RESEARCH.md` "Package Legitimacy Audit"

</read_first>

<action>

- **Goal:** the lock and the provenance record name exactly the wheel the product owner chose, with the evidence the adoption test checks (D-05, PD-4.7).
- **Depends on:** 4.2. **Blocked by:** OQ-2. **Parallel:** with 4.4 and 4.5; not beside Phase 2 tasks 2.6 or 2.14 when `docs/legal/licensing.md` changes; any Phase 3 task.
- **Steps:**
  1. Option a (6.20.1): repeat every audit step of `document-parser-provenance.md` for 6.20.1 without executing package code: the PyPI JSON (filename, size, SHA-256, upload time, yanked, vulnerabilities), wheel RECORD sizes and hashes, file-set and byte correspondence with the official tag archive, METADATA (no runtime dependency for Python 3.12 without extras), the top-level LICENSE SHA-256 and the embedded Adobe, Unicode and contributor notices, and the advisory queries. Downloads go to a new empty scratch folder outside the repository and are read only with isolated interpreters. Update the lock, the identity table, the vulnerability review and the pins in `contracts/documents.md`, `docs/specs/documents.md` §7 and `docs/legal/licensing.md` §4.
  2. Option b (6.20.0): the provenance vulnerability review records the 6.20.1 release, its cyclic-tree fix, the product owner's accepted risk and the containment limits that bound it; the lock is unchanged.
  3. The adoption test checks lock ↔ provenance identity equality, and the wheel bytes when `HYPRN_MVP_PARSER_WHEEL` names a local copy.
- **Risks:** an audit error (task 4.11 repeats the registry and advisory evidence immediately before the first install).

</action>

<acceptance_criteria>

- `test_documents_parser_adoption_lock_matches_provenance` passes and the lock's version equals D-14.
- Option a: `git grep -n "pypdf==6.20.1" -- contracts docs integration` matches `contracts/documents.md`, `docs/specs/documents.md` and the provenance record, and `git grep -n "pypdf==6.20.0" -- contracts docs integration` matches only the provenance record's history paragraph.
- Option b: the provenance record contains the accepted-risk paragraph naming 6.20.1 and the containment limits.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-parser-adoption</automated>
<fails_when>exit status is non-zero or the lock and provenance identity tables differ</fails_when>
<automated>python3 -B deployment/checks.py --group documents-contracts</automated>
<fails_when>exit status is non-zero (a pin edit broke a contract fixture)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.6.md` is verified by the orchestrating session.</done>

</task>

### Task 4.7 — Native collections with logical terminal deletion

<task type="auto" id="4.7">

<name>Task 4.7 — Native collections with logical terminal deletion</name>

<reversibility rating="costly">Group labels, namespaced Group metadata and witnesses accumulate in the AiiDA profile by design; changing their layout later needs a native migration.</reversibility>

<files>

- `integration/src/hyprn_mvp_integration/documents.py`, `deployment/tests/documents_native_fixture.py` (production-adapter probes);
- create `integration/tests/test_documents_collections.py`, `deployment/groups/documents/documents-collections.json` (mode `native`, measured `collection_protocol`).

</files>

<read_first>

- `docs/specs/documents.md` §§3, 9.1; `contracts/documents.md` "Collection deletion and source fences", "State and reconciliation"; the registry `collection_protocol` and the `DocumentCollection1`, `DocumentCollectionDeleted1`, `DocumentMemberList1`, `DocumentNativeCollection*1` definitions
- `integration/src/hyprn_mvp_integration/documents.py`; `deployment/tests/documents_native_fixture.py` (`CollectionProtocolProbe`: `mutate`, `validate_state`, `active_ids`, delete; `_child`, `inspect_fresh`, `kill_at`, `record`); `integration/tests/test_documents_collection_protocol.py`, `integration/tests/test_documents_native.py`
- `integration/src/hyprn_mvp_integration/calculation.py` (the `fault` hook pattern only; never import it)
- `04-PATTERNS.md` "integration/src/hyprn_mvp_integration/documents.py"; `04-RESEARCH.md` Pattern 3, Pitfalls 5 and 6

</read_first>

<action>

- **Goal:** `NativeDocuments` owns collections as product code: create, update, member add and remove in one revision-checked batch, logical terminal deletion with replay before visibility, and active-only listing at the native query boundary (D-01, D-03, D-04, §9.1). The qualified probe protocol becomes product behaviour.
- **Depends on:** 4.4. **Parallel:** with 4.4a, 4.8, 4.9a, 4.10; any Phase 2 or Phase 3 task.
- **Steps:**
  1. Port the probe protocol into `NativeDocuments`: `collection_create(identity, payload)` at revision 1 with the reserved `collection_id` (Pitfall 6); `collection_update`; `collection_members` with actions `add` and `remove` (at most 100 version IDs per change, at most 10,000 members), refusing `replace` before any effect until OQ-3 is answered; `collection_delete`, which in one `backend.transaction()` removes every member, advances the revision once, sets lifecycle `deleted` with the terminal marker `{command_id, payload_digest}` and stores one witness (never the Group's clear or delete calls); `collection(collection_id)`, `collections(page)` and `members(collection_id, page)` filter `lifecycle = active` in the query before ordering and `limit`. One fixed Group label derived from scope and public ID; title, description, revision and lifecycle live in the namespaced Group metadata (the module's namespace constant, never retyped).
  2. Generalize `reconcile(identity)` across categories: the unfiltered command lookup first; zero witnesses → `None`; several → uncertain; a changed digest → conflict; replaying a historical create, update or delete returns its original outcome and never reactivates a terminal collection.
  3. Fail closed on integrity faults: malformed lifecycle or revision, a deleted marker without its witness, a non-empty deleted Group, conflicting witnesses.
  4. Product methods take an injectable `fault` callable for boundary tests (the `NativeExecution.fault` pattern); the probe's own `mutate` stays test-only.
  5. Results validate against `DocumentCollection1`, `DocumentCollectionDeleted1` and `DocumentMemberList1`.
  6. Fixture: production-adapter probes reuse `_child`, `inspect_fresh`, `kill_at` and `record` against the new methods; every measured case writes its artifact with `record`.
- **Risks:** drift from the qualified probe (each probe case is re-run against the product method; both results side by side in the checkpoint); an unbounded delete (10,000-member case).

</action>

<acceptance_criteria>

- `test_documents_collections_one_version_in_two_collections_shares_one_node`: two Groups list the same `SinglefileData` node; the node count does not change.
- `test_documents_collections_stale_revision_changes_nothing`: Group metadata, members and witnesses are identical before and after a stale update or member change, inspected in a fresh process.
- `test_documents_collections_delete_is_terminal_and_replays`: a deleted collection is absent from lists and counts; replaying its delete, create and update commands returns the original outcomes without reactivation; a new collection with the same title gets a new identity.
- `test_documents_collections_sigkill_at_each_boundary`: a kill before the witness, after the witness, before commit and after commit leaves either the prior state or exactly one committed outcome with one witness; every case leaves a measured artifact.
- `test_documents_collections_delete_removes_ten_thousand_members_in_one_transaction`.
- `test_documents_collections_replace_is_refused_without_effect`.
- `test_documents_collections_integrity_faults_fail_closed` covers each fault of step 3.
- Created collections report revision 1 and validate as `DocumentCollection1`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-collections</automated>
<fails_when>exit status is non-zero, or the `collection_protocol` validator reports a missing or failed measured artifact</fails_when>
<automated>python3 -B deployment/checks.py --group documents-collection-protocol</automated>
<fails_when>exit status is non-zero (the qualified probe no longer holds)</fails_when>
<automated>python3 -B deployment/checks.py --group documents-native-originals</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-native-atomicity</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.7.md` is verified by the orchestrating session.</done>

</task>

### Task 4.8 — Closed bridge verb sets and the measured read loop

<task type="auto" id="4.8">

<name>Task 4.8 — Closed bridge verb sets and the measured read loop</name>

<files>

- `deployment/document_native_runtime.py` (admitted sets; the read-process entry `--reads`), `application/src/hyprn_mvp_app/document_bridge.py` (admitted sets; the application-side `--reads` entry), `deployment/documents_groups.py` (validator `read_loop_timeline`);
- create `application/tests/test_documents_bridge.py`, `integration/tests/test_documents_read_loop.py`, `deployment/groups/documents/documents-bridge.json` (mode `native`), `deployment/groups/documents/documents-read-loop.json` (mode `native`, measured `read_loop_timeline`).

</files>

<read_first>

- `contracts/documents.md` "Fixed bridge"; the registry `bridge` (7 read and 15 write verbs) and `runtime_invariants` (`bridge_isolation`)
- `deployment/document_native_runtime.py`, `application/src/hyprn_mvp_app/document_bridge.py` (from 4.1); `application/src/hyprn_mvp_app/dispatcher.py` (`BRIDGE_ARITIES`, `bridge_request`, owner-exit `select`); `deployment/dispatch_runtime.py` (lock handling, `bridge_child`)
- `deployment/tests/test_bridge.py`; `deployment/documents_groups.py` (from 4.4)
- `04-RESEARCH.md` Pattern 2, Pitfalls 3 and 4, assumption A3

</read_first>

<action>

- **Goal:** the bridge admits exactly the verbs that have handlers, all drawn from the registry; the read process cannot write or launch science; and document reads stay responsive while a deliberately blocked native run holds the writer, measured rather than assumed (D-09).
- **Depends on:** 4.4. **Parallel:** with 4.4a, 4.7, 4.9a, 4.10; any Phase 2 or Phase 3 task.
- **Steps:**
  1. `READ_VERBS` and `WRITE_VERBS` exist in both `document_bridge` and `document_native_runtime`; each is a subset of the registry's `bridge.read` and `bridge.write`, and both ends are equal. `source_delete_preview`, `source_delete`, `export`, `import` and `restore` are never admitted in this phase (PD-4.1). Anything else is refused before any I/O on both ends.
  2. Read process: `deployment/document_native_runtime.py --reads --spool-root <folder> --lock <file>` (both paths are arguments supplied by the supervisor; no default literal). It takes its own lock (`O_CREAT|O_RDWR|O_NOFOLLOW`, 0600, exclusive non-blocking `flock`), opens one AiiDA storage handle, answers one framed request per line from its paired application-side drainer within `READ_VERBS` only, keeps read transactions short with bounded busy retries (each counted in its log), and exits when its input closes or its parent exits. Its static import closure contains no `launcher`, `calculation`, `results` or `worker` module.
  3. Application side: `python -m hyprn_mvp_app.document_bridge --reads` drains `document_read_requests` and exits when the host closes its input (the owner-exit `select` pattern).
  4. `integration/tests/test_documents_read_loop.py`: a separate writer process runs a test-only calcfunction on the scratch profile that blocks for 20 s inside a running native process (process node and links written at start and end); a second scenario holds an open AiiDA write transaction for 10 s with periodic commits. Meanwhile the read process answers at least 40 reads: `descriptor`, and `original` in 256 KiB ranges of a 10 MiB original. The timeline (block start, each read's start and end, block release, busy retries) is written to the scope's evidence folder.
  5. Validator `read_loop_timeline` in `documents_groups.py`: at least 40 reads, every read ends before the block's release, every read lasts at most 2.0 s, no read failed; otherwise the group fails even when pytest passed.
  6. Killing the supervising test process leaves no read process alive after 5 s.
- **Risks:** SQLite lock contention on the AiiDA profile (Pitfall 4): a failure here blocks every read-dependent task and comes back to this task; timing noise (the bound applies to the fixture; timings recorded in the checkpoint).

</action>

<acceptance_criteria>

- `test_documents_bridge_admitted_sets_are_registry_subsets_and_equal_on_both_ends`.
- `test_documents_bridge_read_mode_refuses_writes_and_science_before_io`: every write verb, every scientific bridge method and unknown verbs produce no output frame and no native call.
- `test_documents_bridge_read_entry_imports_no_scientific_module` (static import closure of the read entry).
- `test_documents_read_loop_reads_complete_during_blocked_native_run` and `test_documents_read_loop_reads_complete_during_open_write_transaction` pass, and the `read_loop_timeline` validator accepts both timelines.
- `test_documents_read_loop_exits_with_its_supervisor`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-bridge</automated>
<fails_when>exit status is non-zero or an admitted verb is outside the registry</fails_when>
<automated>python3 -B deployment/checks.py --group documents-read-loop</automated>
<fails_when>exit status is non-zero, or the `read_loop_timeline` validator reports a read above 2.0 s, a read ending after the block release, fewer than 40 reads or a failed read</fails_when>
<automated>python3 -B deployment/checks.py --group documents-upload-api</automated>
<fails_when>exit status is non-zero (the tracer path regressed)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.8.md` (including both timelines' summary figures) is verified by the orchestrating session.</done>

</task>

### Task 4.9a — Library routes, signed cursors and the library slice

<task type="auto" id="4.9a">

<name>Task 4.9a — Library routes, signed cursors and the library slice</name>

<reversibility rating="costly">`document_slices` becomes a public capabilities field that the UI and agent clients read; removing or renaming it later breaks them.</reversibility>

<files>

- `application/src/hyprn_mvp_app/documents.py`, `application/src/hyprn_mvp_app/routes/documents.py`, the capabilities route (`document_slices`; in the module that checkpoint 3.3a names for it), `application/src/hyprn_mvp_app/store.py`, `application/generate_contract.py`, the regenerated `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts`;
- create `application/tests/test_documents_library_api.py`, `deployment/groups/documents/documents-library-api.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §§4–5, 11; `contracts/documents.md` "Public transport and permissions", "State and reconciliation" (commit proofs, `DocumentAppCommit1`); the registry routes; `DocumentListQuery1`, `DocumentPageQuery1`, `DocumentOriginalQuery1`, `DocumentMetadataPatch1`, `DocumentArchiveChange1`, `DocumentFailure1`
- `application/src/hyprn_mvp_app/documents.py`, `routes/documents.py` (from 4.1), the capabilities route and the pagination helper (`page`, in 3.3a's edge-helper module), `store.py` (`list_evidence` cursor binding, `command`, `cas`); `application/src/hyprn_mvp_app/computational_export.py` (re-authorized download)
- `application/generate_contract.py` (`ApplicationCapabilities`)
- `04-PATTERNS.md` "application/src/hyprn_mvp_app/documents.py", "api.py", "Per-owner routers"; `04-RESEARCH.md` Open Question 8; "Target design" → "Parser, extraction and search" (cursors) in this plan

</read_first>

<action>

- **Goal:** the library slice's routes work end to end with stable, signed pagination: list, family, versions, version, original (whole or bounded range), metadata and archive commands and operation status; `documents_library/1` is advertised (D-02, D-03, D-07, PD-4.1, PD-4.8). Recovery states, quotas and the access matrix follow in 4.9b.
- **Depends on:** 4.4. **Parallel:** with 4.4a, 4.7, 4.8, 4.10; any Phase 2 task; no Phase 3 task (store, the capabilities route, generator and contract files).
- **Steps:**
  1. Routes, in `routes/documents.py`: `GET documents` with the `DocumentListQuery1` filters (a `collection_id` matches no association until task 4.14 and gets the same not-found as a foreign one), `GET documents/{document_id}`, `GET documents/{document_id}/versions`, `GET document-operations/{operation_id}`, `PATCH documents/{document_id}` (title and tags under revision compare-and-set, committed atomically with a `DocumentAppCommit1` receipt), `POST documents/{document_id}/archive` and `/unarchive`; `GET document-versions/{version_id}/original` gains bounded ranges; a new version of a family uses `family_id` and `expected_revision` at begin. Every route authorizes the study before any lookup and re-authorizes at delivery (D-02).
  2. Signed cursors per "Target design" for every page route: in-memory HMAC key generated at start, token bound to actor, study, route, filter digest and revision, 5-minute expiry, re-authorized on every page; ties ordered by public ID.
  3. Capabilities: `ApplicationCapabilities.document_slices` (a closed enum of the seven slice IDs) in the generator; `DOCUMENT_SLICES` maps each slice to its registry route keys; the route advertises a slice only when all its routes are mounted; `documents_library/1` is advertised from now on and `documents` stays in `unavailable` (PD-4.8).
  4. Regenerate the contract and types.
- **Risks:** cursor keys lost on restart (by design; the client restarts the listing and the test covers it).

</action>

<acceptance_criteria>

- `test_documents_library_api_*`: list, filters and pagination with a stable order and no repeated or skipped row; version list ordering; a cursor issued before an application restart or older than 5 minutes gets 400 and the listing restarts from the first page; a stale metadata patch gets 409 `stale_revision` with nothing changed; archive hides the family from the default list while direct reads still work.
- `test_documents_library_api_download_filename_is_encoded`: CR/LF, quotes, path separators and non-ASCII filenames download under an encoded attachment name with bytes equal to the original SHA-256.
- `test_documents_library_api_slice_advertised_only_with_all_routes_mounted`: `document_slices` equals `["documents_library/1"]` and `documents` is in `unavailable`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-library-api</automated>
<fails_when>exit status is non-zero or `tests.json` reports a failure or skip</fails_when>
<automated>python3 -B deployment/checks.py --group documents-upload-api</automated>
<fails_when>exit status is non-zero: the family-version begin or the ranged original broke the qualified upload path</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero (generated contract or types out of date)</fails_when>
<automated>python3 -B deployment/checks.py --group api-a</automated>
<fails_when>exit status is non-zero (study listing or archive behaviour changed)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.9a.md` is verified by the orchestrating session.</done>

</task>

### Task 4.9b — Upload recovery states, quotas and the study-scope access matrix

<task type="auto" id="4.9b">

<name>Task 4.9b — Upload recovery states, quotas and the study-scope access matrix</name>

<files>

- `application/src/hyprn_mvp_app/documents.py`, the receipts route (`GET commands/{command_id}?category=`; document receipt categories; in the module that checkpoint 3.3a names for it), `application/src/hyprn_mvp_app/store.py` (quotas; the document categories' rows in the server-decided recovery table of Phase 3 task 3.3d), `application/generate_contract.py`, the regenerated `contracts/hyprn-mvp.openapi.yaml` and `ui/src/contract.ts`, `application/tests/test_documents_upload_api.py` (recovery and rejection cases), `deployment/tests/documents_bridge_fixture.py` (a subprocess host mode for kill tests);
- create `application/tests/test_documents_access.py`, `deployment/groups/documents/documents-access.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §§4, 6, 11, 16; `contracts/documents.md` "State and reconciliation" (commit proofs, witnesses); the registry `operation_transitions`; `DocumentFailure1`
- `application/src/hyprn_mvp_app/documents.py` and `routes/documents.py` (after 4.9a), the receipts route module, `store.py` (`command`; the recovery table and its completeness test from Phase 3 task 3.3d, checkpoint `phases/03-agent-tools-for-coding-agents/checkpoints/3.3d.md`), `readiness.py`; `application/src/hyprn_mvp_app/computational_export.py` (quota, owned file I/O)
- `deployment/tests/documents_bridge_fixture.py`, `application/tests/test_documents_upload_api.py`, `application/tests/test_documents_library_api.py`
- `04-RESEARCH.md` "Upload Chunk Protocol, Spool and Limits"

</read_first>

<action>

- **Goal:** every upload and document-operation recovery state is reached and reported without blind retries, every document receipt category tells clients how to recover through the server-decided `recovery` field, quotas bound the spool, and a matrix over every mounted Documents route proves that identifiers, cursors, cached replies and downloads never cross a study (D-02, D-03, D-07, D-12, D-18, PD-4.6).
- **Depends on:** 4.9a; Phase 3 task 3.3d (server-decided recovery on receipts) verified. **Parallel:** with 4.12 and 4.15; any Phase 2 task; no Phase 3 task (store, the receipts route, generator and contract files).
- **Steps:**
  1. Recovery: an expired lease → `expired` and the application deletes the spool; a writer crash while `running` → `interrupted`, then `reconcile` → published on one exact witness, `failed` only with proof of absence after the earlier writer is excluded, otherwise `uncertain`; a lost spool with no native commit → `failed` with `reupload_required`; `GET commands/{command_id}?category=document_*` re-authorizes and returns the immutable original result (D-03). Each document receipt category present (`document_upload` and the metadata and archive commands of 4.9a) declares its rows in the store's server-decided recovery table: a committed receipt → `adopt` with the original result; a rejected one → `refused`; a receiving, queued or running operation → `wait`; an uncertain operation → `uncertain` (only "Check what happened"; never resent); an absent receipt of a document category → `resend_same_command` (the same `command_id` and payload replay idempotently, D-03). Each later task that adds a document receipt category (4.14, 4.17, 4.24) declares its rows the same way.
  2. `waiting_for_native_storage` is true while an operation is queued and the runtime observation reports an active launch.
  3. Quotas inside the begin transaction: 4 incomplete uploads and 100 MiB staged per study.
  4. Logs carry no document text, filename, title or other study's identifier.
  5. `test_documents_access.py` enumerates the mounted Documents routes from the registry and the application's route table, so each later API task that mounts a route is covered by the same matrix without editing it.
  6. Regenerate the contract and types when the receipt categories change them.
- **Risks:** the recovery matrix needing native kills (subprocess host mode in `documents_bridge_fixture.py`, killed at a monkeypatched boundary in the child, no product hook); a route escaping the matrix (it enumerates mounted routes instead of listing them).

</action>

<acceptance_criteria>

- `test_documents_upload_api_each_recovery_state_is_reached_and_reported`: receiving, queued (with waiting), running, committed, published, failed (integrity mismatch, type mismatch, limit, `reupload_required`), expired, interrupted and uncertain are each produced by a scripted fault and reported by `GET document-uploads/{id}` and `GET document-operations/{id}`; repeated status reads of an uncertain operation never add a host call.
- `test_documents_upload_api_rejects_mismatched_and_malformed_uploads_without_effect`: PDF-named HTML, an executable header, `application/octet-stream`, a mismatched extension, invalid UTF-8, a gap, an overlap mismatch, changed bytes at the same offset, excess bytes, a missing `Content-Length`, a fifth incomplete upload and more than 100 MiB staged in one study.
- `test_documents_access_*`: for every mounted route and parameter, foreign and unknown IDs get identical 404 bodies; a cursor from another study, actor or query gets an identical 400; a cached read reply after membership removal gets 404; a download after membership removal sends no bytes; a reader gets 403 on writes; non-GET without CSRF or origin gets 403; the captured logs hold no document text, filename, title or foreign identifier.
- `test_documents_upload_api_receipts_carry_server_recovery`: for each document receipt category and each receipt or operation state, `GET commands/{command_id}?category=` returns the declared `recovery`; an uncertain operation's receipt never says `resend_same_command`; the recovery table's completeness test from 3.3d passes with the document categories.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-access</automated>
<fails_when>exit status is non-zero: a foreign identifier, cursor or cached reply was distinguishable or delivered</fails_when>
<automated>python3 -B deployment/checks.py --group documents-upload-api</automated>
<fails_when>exit status is non-zero: a recovery state was not reached, misreported or re-dispatched</fails_when>
<automated>python3 -B deployment/checks.py --group documents-library-api</automated>
<fails_when>exit status is non-zero (library routes or cursors regressed)</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero (generated contract or types out of date)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.9b.md` is verified by the orchestrating session.</done>

</task>

### Task 4.10 — TextReader and CitationRecord components (A5, A6)

<task type="auto" id="4.10">

<name>Task 4.10 — TextReader and CitationRecord components (A5, A6)</name>

<files>

- create `design-system/components/TextReader.md`, `design-system/components/CitationRecord.md`, `ui/src/design/reader.tsx`;
- modify `ui/src/design/primitives.tsx` (`CitationRecord` beside `CriterionRecord`), `ui/src/design/foundry.css`, `ui/src/design/index.ts`, `ui/design_smoke.mjs`, `design-system/README.md` (implementation list).

</files>

<read_first>

- `04-UI-SPEC.md` A5 (TextReader) and A6 (CitationRecord), "Numbers and sizes", "Keyboard, focus, themes and zoom"
- `design-system/README.md`, `Scientific-states.md` ("Basis of a claim"), `components/SourceChip.md`, `components/Evidence.md`
- `ui/src/design/primitives.tsx` (`CriterionRecord`, `Disclosure`), `ui/src/design/components.tsx` (`SourceChip`), `ui/src/design/source.tsx` (not to be reused as the reader), `ui/src/design/foundry.css`, `ui/design_smoke.mjs`

</read_first>

<action>

- **Goal:** the escaped reader surface and the single citation presentation exist as design-system components with documented contracts and smoke coverage before any screen uses them (UI-SPEC A5, A6; D-08).
- **Depends on:** 4.5. **Parallel:** with 4.4a, 4.7, 4.8, 4.9a; any Phase 2 task; not beside a Phase 3 task that edits `ui/src/design`.
- **Steps:**
  1. `TextReader` per A5 with props `text, firstLine, label, selection, cited, onSelect, focusOffset`. Text is rendered only as React text nodes; U+202A–U+202E, U+2066–U+2069, U+200B–U+200D, U+FEFF and C0 controls other than LF and TAB appear as visible inert markers mapped to their offset ranges. Pointer selection maps to UTF-16 offsets within `text` (clipped, normalised, collapsed → `null`). When `onSelect` is given, the "Choose passage" fieldset (Start line, Start character, End line, End character; characters count code points, start at 1, end inclusive) mirrors and edits the selection, with "Start must come before end." and "Line N is not on this page."; without `onSelect` the fieldset is not rendered. Highlights: `accent-soft` for the selection; `trace-soft` and a 2px `trace` edge for the cited range. No fetching, no code point conversion. Pure helpers `readerLines`, `fieldsToRange` and `rangeToFields` are exported for tests.
  2. `CitationRecord` per A6 (presentation only): `number, relationship, title, versionShortId, mediaLabel, locatorLabel, authority, quotation, quotationAbsent, annotation, actions, compact`; `SourceChip` inside; the quotation block with the same markers; "Show full quotation" `Disclosure` in compact mode; the sub-block "Annotation saved with this citation" with "Later edits and reprocessing do not change it."
  3. `TextReader.md` and `CitationRecord.md` state props, states, keyboard behaviour and the never-rules (no HTML or Markdown rendering, no link detection, no fetching).
  4. Smoke cases: plain text; a 10,000-character unbroken line; an HTML and Markdown payload; bidirectional controls; a selection; a cited range; `fieldsToRange` and `rangeToFields` round trips over astral characters and combining marks; CitationRecord with and without quotation and annotation, compact and full.
- **Risks:** offset mapping errors around surrogate pairs (round-trip cases); a raw-HTML shortcut (forbidden; checked below).

</action>

<acceptance_criteria>

- `node ui/design_smoke.mjs` passes, including: the hostile payload's rendered HTML contains no `<script`, `<a ` or `<img` element from the payload; the marker `⟨U+202E⟩` is present for a right-to-left override; round trips are exact for "a😀b" and "é".
- `git grep -n "dangerouslySetInnerHTML" -- ui/src` returns no line.
- `python3 ui/check_design_system.py` prints no FAIL line; `python3 ui/design_tokens.py --check` and `python3 ui/test_design_tooling.py` pass.

</acceptance_criteria>

<verify>
<automated>node ui/design_smoke.mjs</automated>
<fails_when>exit status is non-zero or a check names `TextReader` or `CitationRecord`</fails_when>
<automated>python3 ui/check_design_system.py</automated>
<fails_when>any output line starts with `FAIL`</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.10.md` is verified by the orchestrating session.</done>

</task>

### Task 4.11 — Verify the parser wheel before its first install (blocking human check)

<task type="checkpoint:human-verify" id="4.11" gate="blocking-human">

<name>Task 4.11 — Verify the parser wheel before its first install (blocking human check)</name>

<precondition>Task 4.6 is verified and Phase 2 task 2.7 is verified; task 4.15 starts immediately after this check.</precondition>

<read_first>

- `integration/document-parser.lock.json`, `integration/document-parser-provenance.md` (as updated by 4.6), `04-CONTEXT.md` D-14

</read_first>

<what-built>The lock and provenance record for the wheel chosen in D-14 (task 4.6). Nothing has been installed yet.</what-built>

<how-to-verify>

1. Open `https://pypi.org/project/pypdf/<version>/` for the locked version and confirm the project, version, wheel filename, size and SHA-256 equal `integration/document-parser.lock.json`, and that the release is not yanked.
2. Open the advisory query for `pypdf@<version>` (GitHub advisories, ecosystem pip) and the maintainer advisory feed; confirm no advisory applies beyond what D-14 accepted.
3. Confirm the date of this check in the checkpoint; the parser image build (4.15) must start on the same day.

</how-to-verify>

<action>

- **Goal:** a human confirms the package's legitimacy immediately before the first install (package legitimacy gate; T-4-SC). This check is never auto-approved, whatever the workflow's auto-advance setting.
- **Depends on:** 4.6, Phase 2 task 2.7. **Blocked by:** OQ-2.

</action>

<acceptance_criteria>

- The checkpoint records the reviewer's answer "approved", the version, filename, size and SHA-256 seen on the registry, the advisory query result and the date.
- `documents-parser-adoption` passes on the same commit.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-parser-adoption</automated>
<fails_when>exit status is non-zero (lock and provenance disagree)</fails_when>
</verify>

<resume-signal>"approved" with the date, or a description of the mismatch (which stops tasks 4.15 onward).</resume-signal>

<done>The checkpoint `phases/04-documents/checkpoints/4.11.md` holds the human answer and the registry evidence, and is verified by the orchestrating session.</done>

</task>

### Task 4.12 — Native working annotations

<task type="auto" id="4.12">

<name>Task 4.12 — Native working annotations</name>

<files>

- `integration/src/hyprn_mvp_integration/documents.py`, `deployment/tests/documents_native_fixture.py`;
- create `integration/tests/test_documents_annotations.py`, `deployment/groups/documents/documents-annotations.json` (mode `native`, measured `collection_protocol`).

</files>

<read_first>

- `docs/specs/documents.md` §§3, 8 (annotations); `contracts/documents.md` "Resource ownership and identity" (`DocumentAnnotation1`), "Fixed bridge" (creation identities); `DocumentAnnotation1`, `DocumentAnnotationCreate1`, `DocumentAnnotationRevise1`, `DocumentAnnotationDelete1`, `DocumentNativeAnnotation*1`, `DocumentAnnotationDeleted1`
- `integration/src/hyprn_mvp_integration/documents.py` (after 4.7), `deployment/tests/documents_native_fixture.py`, `integration/tests/test_documents_collections.py`

</read_first>

<action>

- **Goal:** annotations are bounded working objects on the exact original node, created, revised and deleted atomically with witnesses and replay before compare-and-set (D-01, D-03).
- **Depends on:** 4.7. **Parallel:** with 4.9b and 4.15; any Phase 2 or Phase 3 task.
- **Steps:**
  1. `annotation_create(identity, payload)` with the reserved `annotation_id` at revision 1; `annotation_revise` and `annotation_delete` under revision compare-and-set; each annotation is one namespaced metadata object on the original node (id, revision, locator, text up to 4,096 code points, up to 20 tags of up to 64 code points, attribution, times), written as one object; at most 100 per version; one witness per command in the same transaction; the witness is looked up before compare-and-set.
  2. `annotation(version_id, annotation_id)` and `annotations(version_id, page)` with a stable order by creation time then ID; `reconcile` covers the annotation categories.
  3. Locators are stored as given and validated structurally; checks against a page inventory or an extraction artifact belong to the application (tasks 4.17 and 4.27).
  4. Fail closed on malformed annotation objects or conflicting witnesses.
- **Risks:** an edit touching sibling annotations (byte comparison of the other objects).

</action>

<acceptance_criteria>

- `test_documents_annotations_create_revise_delete_round_trip` with shapes validated as `DocumentAnnotation1` and `DocumentAnnotationDeleted1`.
- `test_documents_annotations_stale_revision_changes_nothing` and `test_documents_annotations_edit_leaves_other_annotations_byte_identical`.
- `test_documents_annotations_hundred_and_first_is_refused_without_effect`.
- `test_documents_annotations_replay_returns_original_outcome` and `test_documents_annotations_sigkill_at_each_boundary` (prior state or exactly one outcome; measured artifacts recorded).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-annotations</automated>
<fails_when>exit status is non-zero or the measured-artifact validator fails</fails_when>
<automated>python3 -B deployment/checks.py --group documents-collections</automated>
<fails_when>exit status is non-zero (shared adapter regression)</fails_when>
<automated>python3 -B deployment/checks.py --group documents-native-originals</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.12.md` is verified by the orchestrating session.</done>

</task>

### Task 4.13 — Library UI

<task type="auto" id="4.13">

<name>Task 4.13 — Library UI</name>

<files>

- modify `ui/src/views/registry.ts` (the Documents view entry immediately before Evidence), `ui/src/api.ts` (document reads, `putChunk`, verified `downloadOriginal`, document command categories that read the receipt's `recovery`), `ui/control-map.json`, `ui/src/documents.css`, `deployment/tests/documents_ui_fixture.py` (seeded states and controls on the harness); `ui/src/workspaceModel.ts` only if Phase 3 task 3.3b left a shared link type that must name the document and version fields;
- create `ui/src/views/documents.tsx` (the Documents library view module: `name`, `parseLink` for document and version links, `render`, a `guard` covering an active transfer, `available` with `documents_library/1`), `ui/src/DocumentsLibrary.tsx`, `ui/src/DocumentUpload.tsx`, `ui/src/DocumentVersions.tsx` (Versions and "Document version record" dialogs), `ui/src/documentFormat.ts` (sizes, format words, short IDs, dates), `ui/tests/documents-library.spec.ts`, `deployment/groups/documents/documents-library-ui.json` (mode `browser-native`).

</files>

<read_first>

- `04-UI-SPEC.md` S1, S2, "State vocabulary → Uploads", "Numbers and sizes", "Keyboard, focus, themes and zoom", "Copywriting Contract"
- `design-system/README.md`, `Layouts.md` (Documents section from 4.5), `Scientific-states.md`, `Naming.md`
- `ui/src/views/registry.ts` and the view modules Phase 3 task 3.3b created (checkpoint `phases/03-agent-tools-for-coding-agents/checkpoints/3.3b.md`), `ui/src/Workspace.tsx` (the shell: tabs, guards, dirty dialog; read only), `ui/src/workspaceModel.ts`, `ui/src/api.ts` (`request`, `mutate`, `reconcile` reading `recovery` after Phase 3 task 3.3d, `downloadComputationalRecord`), `ui/src/ComputationalExportDialog.tsx`, `ui/src/EvidenceView.tsx` (abortable reads), `ui/src/accessLoss.ts`
- `ui/check_ui_contract.py`, `ui/control-map.json`; `ui/tests/foundry-zoom.spec.ts`, `ui/tests/assumptions-evidence.spec.ts`; `deployment/tests/documents_ui_fixture.py`

</read_first>

<action>

- **Goal:** an engineer uploads, lists, inspects versions of and downloads documents in the Documents tab, and sees every upload state in words with its next safe action (UI-SPEC S1, S2; D-08, D-10; the view registry of D-18).
- **Depends on:** 4.4a (the isolated API on the harness), 4.5, 4.9b; Phase 3 task 3.3b (study-shell view registry) verified. **Parallel:** with 4.14, 4.18, 4.19; any Phase 2 task; no Phase 3 task (`ui/src/views/registry.ts`, `api.ts`, `control-map.json`).
- **Steps:**
  1. The Documents tab is the library view module, registered in `ui/src/views/registry.ts` immediately before Evidence; its `available(capabilities)` is true only when `document_slices` contains `documents_library/1`; the breadcrumb section is "Documents"; its `guard` joins the shell's ordered editor guard. `ui/src/Workspace.tsx` is not edited for Documents: a need the registry does not meet is met by a view-independent shell change recorded in the checkpoint, never by a Documents branch in the shell.
  2. S1 library per UI-SPEC: header with the one primary "Upload documents"; the Uploads panel; the documents list as `<ul>` of `<article>` rows (title, format word, size, "Version <short ID>", upload time, availability tag); actions "Download original", "Versions" and "Record details"; "Load more documents"; empty, loading and error states with their exact copy. Controls whose slices are not advertised (Read source, Add to collection, search modes) are absent, not disabled. Readers see read actions only.
  3. S2 upload dialog: admitted types and limits; client pre-checks (type, size; 0 bytes allowed and shown as "0 bytes"); local SHA-256 with Web Crypto ("Preparing the file…"); begin; chunks through `putChunk` (`application/octet-stream`, CSRF header, the same timeout, actor and 401 handling as `request`); measured `Progress` "N of M MiB sent"; complete; indeterminate "Saving the file…" with the waiting message; "Saved" notice; closing while sending asks "Stop sending this file?"; "Continue upload" within the page session checks size and SHA-256; the unsaved-changes guard covers an active transfer.
  4. Upload state vocabulary exactly as UI-SPEC (receiving, saving, published, failed by reason, expired, interrupted, uncertain); an uncertain upload offers only "Check what happened", which reads status and never resends; a command whose reply was lost is recovered through the receipt's server-decided `recovery`, with no client-side rule per document category (D-03). The Uploads panel lists uploads started in this page session; listing them after a reload is task 4.32 (OQ-5).
  5. `downloadOriginal` verifies the streamed size and SHA-256 against the version before handing the file to the browser; access loss clears rows and dialogs before the access notice.
  6. Register every new control and route in `ui/control-map.json`; `ui/check_ui_contract.py` must map each control to an existing spec test.
  7. Evidence: light and dark screenshots of empty, populated, uploads (each state family), error and reader-role states, a keyboard-only upload and download, and genuine 200 % zoom (the `foundry-zoom.spec.ts` Chromium pattern at a native 1440 × 1000 window), written under `HYPRN_MVP_UI_EVIDENCE_ROOT`.
- **Risks:** chunk transfer timing in the browser (fixture holds the writer to show waiting deterministically); the study shell edited concurrently by Phase 3 (serialize).

</action>

<acceptance_criteria>

- `@documents-library-ui` tests pass: the tab is absent when the fixture withdraws `documents_library/1`; a 0-byte text uploads and shows "0 bytes"; a 300 KiB upload shows measured progress, then "Saving the file…", then the waiting message while the fixture holds the writer, then "Saved"; each terminal upload state shows its notice and action; "Check what happened" sends no write request (request log); the downloaded file's SHA-256 equals the version's; a hostile filename downloads under the encoded name; keyboard-only upload and download succeed.
- At genuine 200 % zoom in both themes, `document.documentElement.scrollWidth ≤ innerWidth + 1` for every captured state, and "Upload documents", the dialog commit button and "Download original" are reachable and unobstructed.
- `python3 ui/check_design_system.py` prints no FAIL line; `ui/check_ui_contract.py` (in `combined-static`) maps every new control and route.
- `ui/src/Workspace.tsx` has no Documents-specific change (its diff is empty, or a view-independent shell change named in the checkpoint).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-library-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero, including an unmapped control or route reported by the UI contract checker</fails_when>
<automated>python3 ui/check_design_system.py</automated>
<fails_when>any output line starts with `FAIL`</fails_when>
<automated>python3 -B deployment/checks.py --group ui-navigation</automated>
<fails_when>exit status is non-zero (study navigation regressed with the new tab)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.13.md` (with the screenshot list under `HYPRN_MVP_UI_EVIDENCE_ROOT`) is verified by the orchestrating session.</done>

</task>

### Task 4.14 — Collections API

<task type="auto" id="4.14">

<name>Task 4.14 — Collections API</name>

<files>

- `deployment/document_native_runtime.py` (write verbs `collection_create`, `collection_update`, `collection_members`, `collection_delete`; read verbs `list`, `member`, collection `status`), `application/src/hyprn_mvp_app/documents.py`, `application/src/hyprn_mvp_app/document_bridge.py` (admitted sets), `application/src/hyprn_mvp_app/routes/documents.py`, `application/src/hyprn_mvp_app/store.py` (collection associations; the collection receipt category's recovery rows), `application/generate_contract.py`, the regenerated contract and types;
- create `application/tests/test_documents_collections_api.py`, `deployment/groups/documents/documents-collections-api.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §§5, 9.1, 15.2; `contracts/documents.md` "Fixed bridge" (creation identities), "Collection deletion and source fences"; collection routes in the registry; `DocumentCollectionCreate1`, `DocumentCollectionPatch1`, `DocumentCollectionDelete1`, `DocumentCollectionMembersChange1`, `DocumentNativeList1`, `DocumentNativeMemberRead1`
- `integration/src/hyprn_mvp_integration/documents.py` (after 4.7), `deployment/document_native_runtime.py`, `application/src/hyprn_mvp_app/documents.py`, `document_bridge.py`, `routes/documents.py`

</read_first>

<action>

- **Goal:** collections are managed through the public API: one version can sit in two collections, a new family head never moves a member, deletion is terminal, and the library list filters by collection without ever broadening (D-02, D-04; step 5).
- **Depends on:** 4.7, 4.8, 4.9b. **Parallel:** with 4.13, 4.18, 4.19; any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Routes `POST/GET document-collections`, `GET/PATCH/DELETE document-collections/{collection_id}`, `GET/POST document-collections/{collection_id}/members`; creation IDs are reserved once in the application before dispatch; mutations are document operations through the single writer; reads go through the read mailbox with active filtering at the native query boundary.
  2. `GET documents?collection_id=…` asks the read loop for the active member version IDs; a deleted, unknown or foreign collection is not found and never broadens; member counts come from native active membership.
  3. `action: "replace"` is refused before any effect with `unsupported_capability` 422 until task 4.31 (OQ-3).
  4. Extend the admitted sets on both bridge ends; `documents_collections/1` becomes advertised once all seven routes are mounted.
  5. The collection receipt category declares its rows in the server-decided recovery table (the 4.9b rule).
- **Risks:** a membership table creeping into the application (forbidden by D-01; the association stores identity only).

</action>

<acceptance_criteria>

- `test_documents_collections_api_one_version_in_two_collections`; `test_documents_collections_api_new_head_never_moves_members`.
- `test_documents_collections_api_delete_is_terminal`: GET returns 404, lists exclude it, a create with the same title returns a new ID, and a replayed delete returns its original outcome.
- `test_documents_collections_api_stale_revision_changes_nothing` (PATCH and members get 409, state identical); 101 version IDs get 400; foreign IDs in the path or body get the identical 404.
- `test_documents_collections_api_deleted_collection_filter_is_not_found`; `test_documents_collections_api_replace_is_unsupported_without_effect`; `test_documents_collections_api_lost_reply_reconciles_once`.
- `document_slices` contains `documents_collections/1`; the application stores no member list (store schema test).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-collections-api</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-bridge</automated>
<fails_when>exit status is non-zero (admitted sets differ between the two ends or leave the registry)</fails_when>
<automated>python3 -B deployment/checks.py --group documents-access</automated>
<fails_when>exit status is non-zero (a collection route disclosed a foreign identifier)</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.14.md` is verified by the orchestrating session.</done>

</task>

### Task 4.15 — Parser image from the verified wheel

<task type="auto" id="4.15">

<name>Task 4.15 — Parser image from the verified wheel</name>

<precondition>Task 4.11 is approved on the day this task starts; Phase 2 task 2.7 (digest-pinned bases, `deployment/images/`) is verified.</precondition>

<files>

- create `deployment/images/parser.Dockerfile`, `deployment/parser_image.py`, `integration/src/hyprn_mvp_integration/document_parser.py`, `integration/tests/test_documents_parser_image.py`, `deployment/groups/documents/documents-parser-image.json` (mode `native`; needs `docker`);
- modify `deployment/local_paths.py` (`HYPRN_MVP_PARSER_CACHE`, default `<data root>/cache/parser`, documented in the module docstring), `docs/legal/licensing.md` (pypdf row: adopted in the parser image; notice bundle), `THIRD_PARTY_NOTICES.md` (parser image notices), and `deployment/pins.json` only if Phase 2 has not already pinned the CPython 3.12 base the image reuses.

</files>

<read_first>

- `docs/specs/documents.md` §§7, 11; `integration/document-parser-provenance.md`, `integration/document-parser.lock.json`; `04-CONTEXT.md` D-05, D-11, PD-4.7, D-14
- `deployment/images/*.Dockerfile` and `deployment/execution_runtime.py` (Phase 2 task 2.7 build pattern), `deployment/modeling_runtime.py` (`upstream_archive` cache verification), `deployment/local_paths.py`, `deployment/pins.json`
- `integration/src/hyprn_mvp_integration/worker.py` (copied-in entry convention), `docs/legal/licensing.md` §§4–5, `THIRD_PARTY_NOTICES.md`
- `04-RESEARCH.md` "Parser Image (step 6)"

</read_first>

<action>

- **Goal:** the parser image is built only from the verified wheel and the pinned base, offline, with its notices, and its fixed entry turns an original into a deterministic manifest and page texts (D-05, D-11, PD-4.7; step 6).
- **Depends on:** 4.11, Phase 2 task 2.7. **Blocked by:** OQ-2. **Parallel:** with 4.9b and 4.12; not beside Phase 2 tasks 2.6 or 2.14 (`licensing.md`, `THIRD_PARTY_NOTICES.md`); any Phase 3 task.
- **Steps:**
  1. `parser_image.acquire_wheel(cache)`: fetch the lock's exact filename over HTTPS from the lock's index host into `<cache>/<sha256>/` (file 0400, folder 0700); verify size and SHA-256 at fetch and at every read; refuse a symlinked cache, a group- or other-accessible or writable file, a foreign owner or any mismatch; never fetch another version.
  2. Advisory recheck at acquisition: the registry's `vulnerabilities` list for the pinned version must be empty or contain only advisories D-14 accepted; otherwise refuse and name the advisory identifiers.
  3. `deployment/images/parser.Dockerfile`: `FROM` the digest-pinned CPython 3.12 base; copy the wheel and `document_parser.py` from a scratch build context; install with `--no-deps --no-index --require-hashes --only-binary=:all:`; re-hash the wheel inside the build and fail on mismatch; copy the wheel's LICENSE and the carried notices into `/usr/share/hyprn-mvp-parser-notices/`; run as a non-root user; labels `org.hyprn-mvp.parser.*` for the wheel, entry and build-input digests. Build with `--network none --pull=false`; tag `hyprn-mvp-parser:<build-input-digest16>`; record the image digest, build-input digest and notice hashes in a runtime record below the data root, never in the repository.
  4. `document_parser.py` (stdlib and pypdf only; no project imports): fixed entry reading `/input/original.bin` and `/config/parser.json`, writing `/output/manifest.json` and `/output/pages/<n>.txt`. Text formats: strict UTF-8 (`hyprn-mvp-utf8/1`), newlines normalized to LF in the extracted copy only. PDF without extras: an encrypted file is `unsupported`; more than 500 pages is refused before page extraction; page text is bounded at 256 KiB per page (`truncated`) and 8 MiB in total; a page without text is `needs_transcription`; a page that raises is `failed` while others are kept; output is deterministic (sorted keys, LF).
  5. Licensing record: the pypdf row says "adopted in the parser image" and points to the notice bundle; `THIRD_PARTY_NOTICES.md` lists the parser image's notices.
- **Risks:** base digest drift (reuse Phase 2's recorded index and platform digests); registry availability (cached verified wheel reused without network).

</action>

<acceptance_criteria>

- `test_documents_parser_image_refuses_tampered_or_resized_wheel_before_build`; `test_documents_parser_image_refuses_symlinked_or_shared_cache`.
- `test_documents_parser_image_builds_offline_and_runs_non_root`: the build log shows `--network none`; the container user is not root.
- `test_documents_parser_image_carries_licence_and_notices`: the bundled LICENSE SHA-256 equals the provenance record's value and the listed notice files exist.
- `test_documents_parser_image_entry_is_deterministic`: the same input twice gives byte-identical manifests and page files.
- The image tag starts with `hyprn-mvp-parser:` and the labels start with `org.hyprn-mvp.`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-parser-image</automated>
<fails_when>exit status is non-zero, `environment absent: docker` is printed, or a tampered wheel was accepted</fails_when>
<automated>python3 -B deployment/checks.py --group documents-parser-adoption</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group naming</automated>
<fails_when>exit status is non-zero (image, label or variable outside the namespace)</fails_when>
<automated>python3 -B deployment/checks.py --group hygiene</automated>
<fails_when>exit status is non-zero (an absolute path or cache location committed)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.15.md` (image digest, build-input digest, wheel SHA-256, notice hashes) is verified by the orchestrating session.</done>

</task>

### Task 4.16 — Collections UI

<task type="auto" id="4.16">

<name>Task 4.16 — Collections UI</name>

<files>

- create `ui/src/DocumentCollections.tsx`, `ui/tests/documents-collections.spec.ts`, `deployment/groups/documents/documents-collections-ui.json` (mode `browser-native`);
- modify `ui/src/DocumentsLibrary.tsx`, `ui/src/api.ts`, `ui/src/views/documents.tsx` (collection link in `parseLink`), `ui/control-map.json`.

</files>

<read_first>

- `04-UI-SPEC.md` S1 (collections panel), S3, "Other document operations" vocabulary
- `ui/src/DocumentsLibrary.tsx`, `ui/src/api.ts`, `ui/src/views/documents.tsx` (after 4.13); `ui/src/design/index.ts` (`Panel`, `Button`, `DialogFrame`, `ActionDialog`, `Checkbox`, `Select`, `Notice`)
- `ui/tests/documents-library.spec.ts`, `ui/control-map.json`

</read_first>

<action>

- **Goal:** an engineer organizes versions in collections from the library: create, rename, add documents, add from a row, remove and delete, with honest pending, waiting, uncertain and stale states (UI-SPEC S3; D-08, D-10; step 5).
- **Depends on:** 4.13, 4.14. **Parallel:** with 4.17; any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Collections panel (only with `documents_collections/1`): "All documents" then each active collection with its member count, `aria-pressed` selection, description and the stacked actions "Add documents", "Rename collection", "Delete collection"; "No collections yet."; panel-level loading and error states independent of the list.
  2. Dialogs per S3: New collection, Rename collection, Add documents (checkbox and version select per document, the latest preselected and visible, at most 100 per change, "Already in this collection"), Add to collection from a row, Delete collection (danger, the two-sentence copy, "Keep collection"); Remove from collection without confirmation and with its status line. "Replace version" is not shown until task 4.31.
  3. Every mutation shows "Saving…"; waiting, uncertain ("Check what happened") and stale ("Changed elsewhere", user's text kept, "Review latest version") use `Notice`; nothing disappears before the operation is published.
  4. A link to an unknown or deleted collection shows "This collection is not available…" with "Show all documents" and never broadens.
  5. Evidence: every S3 state in light and dark, keyboard-only create, add and delete, genuine 200 % zoom, and the backstop of 100 collections with 200-character titles.
- **Risks:** optimistic removal (tests assert the row stays until publication).

</action>

<acceptance_criteria>

- `@documents-collections-ui` tests pass for each step above, including: one version added to two collections shows in both; after a new version of the document is uploaded, the collection still lists the old version with "A newer version exists"; deleting returns the selection to "All documents" with "Collection deleted. Its documents and evidence are unchanged."; a stale rename keeps the typed title.
- At genuine 200 % zoom in both themes, 100 collections with 200-character titles wrap inside the panel without page-wide horizontal scroll.
- `python3 ui/check_design_system.py` prints no FAIL line; every new control is mapped in `ui/control-map.json`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-collections-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group documents-library-ui</automated>
<fails_when>exit status is non-zero (the library regressed)</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.16.md` is verified by the orchestrating session.</done>

</task>

### Task 4.17 — Annotations API

<task type="auto" id="4.17">

<name>Task 4.17 — Annotations API</name>

<files>

- `deployment/document_native_runtime.py` (write verbs `annotation_create`, `annotation_revise`, `annotation_delete`; read verb `annotation`), `application/src/hyprn_mvp_app/document_bridge.py` (admitted sets), `application/src/hyprn_mvp_app/documents.py`, `application/src/hyprn_mvp_app/routes/documents.py`, `application/src/hyprn_mvp_app/store.py` (annotation association: annotation → version; the annotation receipt category's recovery rows), `application/generate_contract.py`, the regenerated contract and types;
- create `application/tests/test_documents_annotations_api.py`, `deployment/groups/documents/documents-annotations-api.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §8 (annotations), §11; annotation routes in the registry; `DocumentAnnotationCreate1`, `DocumentAnnotationRevise1`, `DocumentAnnotationDelete1`, `DocumentAnnotationList1`, `DocumentLocator1`
- `integration/src/hyprn_mvp_integration/documents.py` (after 4.12), `deployment/document_native_runtime.py`, `application/src/hyprn_mvp_app/documents.py`, `routes/documents.py`

</read_first>

<action>

- **Goal:** working annotations are created, listed, revised and deleted through the API with revision checks, bounds and non-disclosing errors (D-02, D-03; step 10).
- **Depends on:** 4.12, 4.14. **Parallel:** with 4.16; any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Routes `GET/POST document-versions/{version_id}/annotations`, `GET/PATCH/DELETE document-versions/{version_id}/annotations/{annotation_id}`; creation IDs reserved once; writes through the single writer; reads through the mailbox.
  2. Locator checks in the application: `original_file` always; `pdf_page` only against the version's established page inventory and `extracted_span` only against an existing extraction artifact of that version, so both are refused with `invalid_request` (field path named) while the version has no extraction; task 4.27 adds the inventory and artifact checks.
  3. Bounds: text 4,096 code points, 20 tags of 64 code points, 100 annotations per version (`limit_exceeded`).
  4. Extend the admitted sets; `documents_annotations/1` becomes advertised.
  5. The annotation receipt category declares its rows in the server-decided recovery table (the 4.9b rule).
- **Risks:** an annotation edit touching evidence (impossible by design; evidence does not exist yet, and task 4.20 proves it).

</action>

<acceptance_criteria>

- `test_documents_annotations_api_crud_with_revision_checks`: a stale PATCH or DELETE gets 409 with nothing changed.
- `test_documents_annotations_api_bounds`: the 101st annotation, 4,097 code points and 21 tags are refused without effect.
- `test_documents_annotations_api_page_and_span_need_an_extraction`; foreign version or annotation IDs get the identical 404; a lost reply reconciles once.
- `document_slices` contains `documents_annotations/1`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-annotations-api</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-bridge</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-access</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.17.md` is verified by the orchestrating session.</done>

</task>

### Task 4.18 — Parser launcher and demonstrated containment

<task type="auto" id="4.18">

<name>Task 4.18 — Parser launcher and demonstrated containment</name>

<files>

- create `integration/src/hyprn_mvp_integration/document_parser_launch.py`, `integration/document-parser-policy.json`, `integration/tests/test_documents_parser_containment.py`, `integration/tests/document_fixtures.py`, `deployment/groups/documents/documents-parser-containment.json` (mode `native`, measured `parser_canaries`);
- modify `integration/src/hyprn_mvp_integration/document_parser.py` (fixed canary cases), `deployment/documents_groups.py` (validator `parser_canaries`).

</files>

<read_first>

- `docs/specs/documents.md` §§7, 11, 16; `integration/document-parser-provenance.md` "Security baseline and parser policy"; the registry `limits` (`parser_*`)
- `integration/src/hyprn_mvp_integration/launcher.py` (`POLICY`, `isolated`, `attest`, `fingerprint`, `require_attestation`); `integration/tests/test_isolation.py`
- `deployment/parser_image.py`, `integration/src/hyprn_mvp_integration/document_parser.py` (from 4.15), `deployment/documents_groups.py`
- `04-RESEARCH.md` "Containment demonstrated", Pitfall 9, assumption A4

</read_first>

<action>

- **Goal:** the parser runs only inside the pinned image under external limits, and containment is demonstrated by canaries and recorded as evidence; without current evidence extraction is refused (D-05, D-07, D-11, D-12; step 6).
- **Depends on:** 4.15, 4.8. **Blocked by:** OQ-2. **Parallel:** with 4.13, 4.14, 4.19 (and 4.16, 4.17 if it waits for OQ-2 that long); any Phase 2 or Phase 3 task.
- **Steps:**
  1. `integration/document-parser-policy.json`: wall clock 30 s, 1 CPU, 512 MiB memory with equal swap, 64 PIDs, 64 MiB scratch, output cap, page and text limits; a test asserts equality with the registry `limits`; its SHA-256 enters the parser configuration digest (D-07).
  2. `launch_parser(image, policy, input_dir, output_dir)`: `docker run` with `--network none`, non-root user, `--read-only`, `--cap-drop ALL`, no-new-privileges, the policy's CPU, memory, swap and PID limits, a size-bounded scratch tmpfs, the input bound read-only, a server-owned output folder below `<execution root>/parser-scratch/<attempt>` (D-11), a fixed command, the label `org.hyprn-mvp.parser` and an owner label; an external wall clock with descendant cleanup (kill, then forced removal, in a `finally` block); bounded output collection. `reap_parser_containers()` at writer start removes labelled parser containers whose owner process is gone.
  3. `attest_parser(image, policy)` runs fixed canary cases of the in-image entry: non-root; root and input write denied; network denied; no container socket, home, secrets or `AIIDA_*` variables; the memory limit kills; the PID limit holds; the CPU quota is set; the scratch bound holds; the output bound holds; the 30 s wall clock ends the container and its descendants; a supervisor killed mid-run leaves no labelled container after `reap_parser_containers`; an unknown image digest or policy digest is refused. Evidence JSON (passed, fingerprint of image digest, policy digest and entry SHA-256) goes to the execution root's evidence folder; earlier evidence is archived by hash. `require_parser_containment(image, policy)` raises unless current passed evidence matches.
  4. `integration/tests/document_fixtures.py` generates every input at run time, nothing binary committed: a text PDF, an encrypted PDF, an image-only page, a malformed cross-reference table, 501 pages, a cyclic page tree, a decompression bomb stream, a page above 256 KiB of text, and UTF-8 edge cases (byte-order mark, CRLF, astral characters, combining marks, invalid bytes).
  5. Validator `parser_canaries`: every canary case present and passed, else the group fails.
- **Risks:** Docker keeping a container alive after its client dies (assumption A4; the supervisor-kill canary proves the reaping); host differences in cgroup reporting (canaries read the container's own limits and record them).

</action>

<acceptance_criteria>

- `test_documents_parser_containment_canaries_pass` with the `parser_canaries` validator accepting the evidence (every case listed in step 3).
- `test_documents_parser_containment_policy_equals_registry_limits`.
- `test_documents_parser_containment_refuses_without_current_evidence`: missing, failed, or changed image or policy fingerprints make `require_parser_containment` raise.
- `test_documents_parser_containment_bombs_and_cycles_are_bounded`: the bomb, cyclic tree and 501-page inputs end within the wall clock with a bounded outcome and no surviving container.
- After the group, `docker ps -a --filter label=org.hyprn-mvp.parser` lists no container of the scope.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-parser-containment</automated>
<fails_when>exit status is non-zero or the `parser_canaries` validator reports a missing or failed canary</fails_when>
<automated>python3 -B deployment/checks.py --group documents-parser-image</automated>
<fails_when>exit status is non-zero (the canary entry changed the image contract)</fails_when>
<automated>python3 -B deployment/checks.py --group units-attestation</automated>
<fails_when>exit status is non-zero (worker attestation affected)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.18.md` (canary report hash and fingerprint) is verified by the orchestrating session.</done>

</task>

### Task 4.19 — Production wiring: read loop and document writes under the executor

<task type="auto" id="4.19">

<name>Task 4.19 — Production wiring: read loop and document writes under the executor</name>

<precondition>Phase 2 tasks 2.3 and 2.8 are verified (`dispatch_runtime.py` from the installation; `deployment/release.py`).</precondition>

<files>

- `deployment/dispatch_runtime.py`, `deployment/release.py` (release binding and module-origin record gain the document host runtime module's path; that module itself is not edited here), `deployment/tests/test_bridge.py` (host-side `document_write` refusal cases);
- create `deployment/tests/test_documents_supervision.py`, `deployment/groups/documents/documents-supervision.json` (mode `native`).

</files>

<read_first>

- `deployment/dispatch_runtime.py` (`native_call`, `bridge_child`, `--serve`, lock), `deployment/release.py` (binding paths), `deployment/application_runtime.py` (container name, store root)
- `deployment/document_native_runtime.py`, `application/src/hyprn_mvp_app/document_bridge.py` (`--reads`), `application/src/hyprn_mvp_app/dispatcher.py`
- `deployment/tests/test_bridge.py`, `deployment/tests/native_deployment_fixture.py`, `deployment/tests/test_native_journey.py`
- `02-PLAN.md` tasks 2.3 and 2.8

</read_first>

<action>

- **Goal:** in an installation the executor routes document writes to the single host writer and starts, owns and stops the read process, and reads stay responsive during a real blocked run (D-09; step 2).
- **Depends on:** 4.8, Phase 2 tasks 2.3 and 2.8. **Parallel:** with 4.13, 4.14, 4.18 (and 4.16, 4.17 if Phase 2 holds it back); not beside another Phase 2 edit of `dispatch_runtime.py` or `release.py`; any Phase 3 task.
- **Steps:**
  1. `native_call`: one branch for `document_write` that calls `document_native_runtime.handle_write` with the installation's application spool folder and native store identity; every other refusal stays as it is.
  2. `--serve` starts the read process (`document_native_runtime.py --reads`, lock `<execution root>/locks/document-reads.lock`, spool folder from the installation) paired with `docker exec -i <application container> python -B -m hyprn_mvp_app.document_bridge --reads`; if the pair dies while the executor lives, it is restarted with a bounded back-off and logged; on executor exit its input is closed and its process group killed.
  3. The release binding covers `deployment/document_native_runtime.py`, so a copy imported from the checkout instead of the snapshot is refused.
  4. On the scoped native deployment fixture: a submitted run of a fixture component that sleeps 10 s (inside the worker's wall clock) holds the executor; reads through the supervised loop complete within 2 s each before the run completes; a document write queued meanwhile reports waiting and publishes after the run; killing the executor leaves no read process or application-side drainer after 5 s.
- **Risks:** this is the security-critical start path that Phase 5 reviews; the release binding test from Phase 2 must stay unchanged except for the added path.

</action>

<acceptance_criteria>

- `test_documents_supervision_reads_complete_during_real_blocked_run` (timeline in the scope's evidence: each read ≤ 2 s, all before run completion).
- `test_documents_supervision_write_waits_then_publishes_after_run`.
- `test_documents_supervision_read_pair_ends_with_executor` and `test_documents_supervision_restarts_dead_read_pair_with_backoff`.
- `deployment/tests/test_bridge.py` cases: a malformed or non-document frame on `document_write` is refused before any native call.
- The release binding refuses a modified or checkout-imported `document_native_runtime.py`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-supervision</automated>
<fails_when>exit status is non-zero, or the timeline shows a read above 2 s or after the run completed</fails_when>
<automated>python3 -B deployment/checks.py --group archive-bridge</automated>
<fails_when>exit status is non-zero (bridge refusal cases)</fails_when>
<automated>python3 -B deployment/checks.py --group release</automated>
<fails_when>exit status is non-zero (release binding)</fails_when>
<automated>python3 -B deployment/checks.py --group deployment-hardening</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.19.md` is verified by the orchestrating session.</done>

</task>

### Task 4.20 — Citation resolver for whole files and evidence version 4

<task type="auto" id="4.20" tdd="true">

<name>Task 4.20 — Citation resolver for whole files and evidence version 4</name>

<reversibility rating="costly">`EvidenceRecord4` rows are immutable scientific records once saved; their storage shape is fixed by the contract and later changes need a new evidence version.</reversibility>

<files>

- create `application/src/hyprn_mvp_app/document_citations.py`, `application/tests/test_documents_citations.py`, `application/tests/test_documents_evidence_v4.py`, `deployment/groups/documents/documents-citations.json` and `documents-evidence-v4.json` (mode `native`);
- modify `application/src/hyprn_mvp_app/store.py` (Evidence4 storage, `document_source_reservations`, immutability triggers), `application/src/hyprn_mvp_app/routes/documents.py` (`POST document-citations/preview`, `POST evidence-citations/preview`), the evidence route module that checkpoint 3.3a names (evidence create and revise admit 4), `application/src/hyprn_mvp_app/documents.py` (reservation hook), `application/tests/test_module_boundaries.py`, `application/generate_contract.py`, the regenerated contract and types.

</files>

<read_first>

- `docs/specs/documents.md` §8; `contracts/documents.md` "Evidence with document citations" (intent, preview, record; commit barrier); `EvidenceCreate4`, `EvidenceRevise4`, `EvidenceRecord4`, `EvidenceCitationPreviewRequest4`, `EvidenceCitationPreview4`, `DocumentCitation1`, `DocumentCitationCandidate1`, `DocumentCitationPreview1`; the registry `scientific_allocations`
- `application/src/hyprn_mvp_app/store.py` (`exact_evidence`, `evidence_snapshot`, `add_evidence`, `revise_evidence`, `evidence_record`), the evidence route module from 3.3a (evidence routes), `routes/documents.py`, `contracts.py` (`canonical`, `digest`, `validate`); `application/tests/test_module_boundaries.py` (`EVIDENCE_WITNESSES`, single evidence-read owner); `application/tests/test_evidence_revisions.py`
- `docs/agents/tooling-spec.md` §10.1 (`untrusted_content`); `.planning/phases/03-agent-tools-for-coding-agents/03-CONTEXT.md` (evidence tools)

</read_first>

<behavior>

- A whole-file candidate resolves to a `DocumentCitation1` whose version, original SHA-256, size, media type, title and filename come from the published version, and whose `citation_id` is the SHA-256 of the canonical descriptor without its own ID.
- A candidate carrying a quotation, hash, native identity or frozen descriptor fails schema validation.
- An annotation candidate with a stale `expected_annotation_revision` gets `stale_revision`; with the current one the full annotation snapshot is frozen.
- Revising the annotation after the evidence is saved leaves the stored evidence bytes and digest identical.
- A preview digest or context revision that no longer matches at commit gets 409 with no record written.
- 21 citations, or two citations of the same version, locator and annotation revision, are refused.
- `EvidenceCreate1`–`3` and `EvidenceRevise3` fixtures behave exactly as before.

</behavior>

<action>

- **Goal:** evidence can cite a whole document version: the server resolves and freezes the citation, the evidence version 4 commit barrier re-checks every source in the same transaction, and annotation edits can never change stored evidence (D-02, D-06, PD-4.2; step 10, HUM-06).
- **Depends on:** 4.17. **Parallel:** with 4.21 and 4.22a; any Phase 2 task; no Phase 3 task (evidence routes, store, module boundaries).
- **Steps:**
  1. `document_citations.resolve_candidate(db, actor, study, candidate)`: authorize the study; require a published version association; verify the original through the read loop's `descriptor` verb; when an annotation is named, read it through the `annotation` verb at the exact revision. `freeze_citation(...)` builds `DocumentCitation1` (title and filename as saved now, relationship as chosen, annotation snapshot or null) with `contracts.canonical` and `contracts.digest`. `pdf_page` and `extracted_span` candidates get `unsupported_capability` 422 with the locator field named until task 4.27 adds their resolution.
  2. `DOCUMENT_UNTRUSTED_FIELDS` lists every document-derived string (quotation, annotation text and tags, title, filename, section label, snippet); a test asserts that every string field of `DocumentCitation1`, `DocumentFragment1` and `DocumentSearchResult1` is classified. If the Phase 3 `read_evidence` tool exists when this task runs, its projection returns these fields inside `untrusted_content` with the provenance kind `document`, with a test; otherwise the checkpoint hands this rule to Phase 3 (T-4-11).
  3. Routes, in `routes/documents.py`: `POST document-citations/preview` (`DocumentCitationCandidate1` → `DocumentCitationPreview1`) and `POST evidence-citations/preview` (`EvidenceCitationPreviewRequest4` → `EvidenceCitationPreview4`, with request and preview digests and expiry), both with the authoring role policy and CSRF.
  4. Evidence create and revise (in the evidence route module) admit `EvidenceCreate4` and `EvidenceRevise4` in addition to the existing unions. For version 4: authorize target and sources, resolve every candidate outside the write, then inside the write transaction re-authorize, compare the predecessor, context revision and preview digest, re-check associations and annotation revisions, insert `document_source_reservations` rows, validate and store `EvidenceRecord4` under the immutability triggers. Reads return the explicit `EvidenceRecordRead4` union; older records are untouched. Evidence is read only through `Store.evidence_record` (single owner).
  5. `documents_citations/1` becomes advertised.
- **Risks:** Phase 3 agent evidence tools depend on the same routes (older versions stay admitted unchanged; `ae-*` groups prove it).

</action>

<acceptance_criteria>

- Every `<behavior>` case is a test named `test_documents_citations_*` or `test_documents_evidence_v4_*` and passes.
- `test_documents_evidence_v4_annotation_revise_never_changes_stored_evidence`: the stored record's canonical bytes and digest are identical before and after.
- `test_documents_citations_untrusted_inventory_covers_every_document_string`.
- `ae-evidence`, `ae-public`, `ae-generated` and `ae-contracts` pass unchanged; `document_slices` contains `documents_citations/1`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-citations</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-evidence-v4</automated>
<fails_when>exit status is non-zero, including a changed stored evidence digest after an annotation edit</fails_when>
<automated>python3 -B deployment/checks.py --group ae-evidence</automated>
<fails_when>exit status is non-zero (older evidence versions regressed)</fails_when>
<automated>python3 -B deployment/checks.py --group ae-public</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-citation-contracts</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group locality-contracts</automated>
<fails_when>exit status is non-zero (module boundary or single evidence-read owner)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.20.md` is verified by the orchestrating session.</done>

</task>

### Task 4.21 — Native extraction

<task type="auto" id="4.21">

<name>Task 4.21 — Native extraction</name>

<files>

- create `integration/src/hyprn_mvp_integration/document_extraction.py`, `integration/tests/test_documents_extraction.py`, `deployment/groups/documents/documents-extraction.json` (mode `native`);
- modify `integration/src/hyprn_mvp_integration/documents.py` (`extraction_start`, `attempt`, `extraction_result`, `fragment`), `deployment/document_native_runtime.py` (write verb `extraction_start`; read verbs `fragment` and attempt and extraction `status`; parser reaping at writer start), `application/src/hyprn_mvp_app/document_bridge.py` (admitted sets), `application/tests/test_documents_bridge.py` (final-set equality), `integration/tests/document_fixtures.py`.

</files>

<read_first>

- `docs/specs/documents.md` §7; `contracts/documents.md` "Fixed bridge" (extraction start), "State and reconciliation" (extraction); the registry `extraction_transitions`, `extraction_reconciliation`; `DocumentNativeExtractionStart1`, `DocumentExtractionAttempt1`, `DocumentExtractionResult1`, `DocumentFragment1`, `DocumentPageCoverage1`
- `integration/src/hyprn_mvp_integration/calculation.py` (`FolderData` retention, CREATE-link reads, `matches` before launch — patterns only, never import), `integration/src/hyprn_mvp_integration/document_parser_launch.py`, `documents.py`
- `04-RESEARCH.md` "Calcfunction shape", assumption A5

</read_first>

<action>

- **Goal:** one extraction attempt runs the contained parser through a genuine calcfunction with real provenance links, records honest outcomes and repeatable locators, and is never silently resumed (D-01, D-05; step 7).
- **Depends on:** 4.18, 4.12, 4.17. **Blocked by:** OQ-2. **Parallel:** with 4.20 and 4.22a; any Phase 2 or Phase 3 task.
- **Steps:**
  1. First confirm on aiida-core 2.9.3 that a `@calcfunction` can return several outputs as a dictionary (assumption A5); record the result. If not, return one output per call of an explicitly linked second calcfunction, recorded as the design.
  2. `extract_document(original, configuration)`: inputs `original` (`SinglefileData`) and `configuration` (`Dict` with parser identity, image digest, policy digest); calls `require_parser_containment`, then `launch_parser`; outputs `manifest` (`Dict`: parser identity, image and configuration digests, original SHA-256, per-page text SHA-256, locator map, coverage, outcome) and `text` (`FolderData` of pages), linked by CREATE. A finished calcfunction may report a failed or partial outcome; the outcome lives in the manifest, never in the process state.
  3. `extraction_start(identity, payload)` under the single writer: kinds `initial` and `retry` (with `prior_attempt_id`; `retry_of` set); at most one active extraction per installation; witness first; on writer start, a process left running by a dead writer is marked `interrupted` and never resumed; parser containers of a dead writer are reaped.
  4. `fragment(...)` returns at most 256 KiB of one page or line window with code point positions after verifying the artifact SHA-256; `status` covers attempts and results.
  5. Outcomes from generated fixtures: complete (text PDF, plain text, Markdown, CSV), partial, truncated, unsupported (encrypted), needs transcription (image-only), failed (malformed), refused above 500 pages, bounded cyclic tree and bomb, interrupted (writer killed mid-run).
  6. Admitted sets reach their final form: `READ_VERBS` equals the registry read set; `WRITE_VERBS` equals the registry write set without `source_delete_preview`, `source_delete`, `export`, `import` and `restore`.
- **Risks:** the writer blocked for up to 30 s per extraction (reported as waiting; reads stay on the read loop); assumption A5.

</action>

<acceptance_criteria>

- `test_documents_extraction_links_are_real`: the calcfunction node has incoming links from the exact original and configuration and outgoing CREATE links to the manifest and text.
- `test_documents_extraction_is_repeatable`: the same original extracted twice gives identical per-page SHA-256 values and locator maps.
- `test_documents_extraction_outcomes`: each fixture in step 5 yields its stated outcome, and the original stays downloadable after each.
- `test_documents_extraction_interrupted_is_never_resumed` and `test_documents_extraction_one_active_per_installation`.
- `test_documents_extraction_refused_without_containment_evidence`: no process node is created.
- `test_documents_bridge_admitted_sets_are_final` (in `documents-bridge`).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-extraction</automated>
<fails_when>exit status is non-zero, `environment absent: docker` is printed, or an outcome differs from its fixture's</fails_when>
<automated>python3 -B deployment/checks.py --group documents-bridge</automated>
<fails_when>exit status is non-zero (admitted sets not final or not equal on both ends)</fails_when>
<automated>python3 -B deployment/checks.py --group documents-parser-containment</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-annotations</automated>
<fails_when>exit status is non-zero (shared adapter regression)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.21.md` (A5 result, outcome table) is verified by the orchestrating session.</done>

</task>

### Task 4.22 — "Used by", assumption evidence with citations, and the Evidence4 admission boundary

<task type="auto" id="4.22">

<name>Task 4.22 — "Used by", assumption evidence with citations, and the Evidence4 admission boundary</name>

<files>

- `application/src/hyprn_mvp_app/documents.py` (usage), `application/src/hyprn_mvp_app/routes/documents.py` (usage route), the model route module that checkpoint 3.3a names (assumption-evidence response), `application/src/hyprn_mvp_app/modeling.py` (`EvidenceRecordRead4`, `AssumptionEvidenceResolution2`), `application/src/hyprn_mvp_app/configuration.py` and `application/src/hyprn_mvp_app/approach.py` (Evidence4 refusal), `application/generate_contract.py`, the regenerated contract and types;
- create `application/tests/test_documents_usage.py`, `deployment/groups/documents/documents-usage.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §§2 (Usage), 8; `contracts/documents.md` "Consumers that adopt these types" (`modeling`, `configuration`, `approach` rows), "Commit, deletion and retention boundary"; `DocumentUsageList1`, `DocumentUsage1`, `AssumptionEvidenceResolution2`, `EvidenceRecordRead4`
- `application/src/hyprn_mvp_app/modeling.py` (assumption evidence resolution), `configuration.py`, `approach.py`, the model route module (`/models/{model_id}/assumption-evidence`) and the approach route module (its usage route is the read-only analog of the document usage route); `application/tests/test_assumption_configuration.py`, `test_approach_configuration.py`

</read_first>

<action>

- **Goal:** each version shows what uses it; model and component assumptions can show evidence that cites documents; and every older scientific contract refuses an Evidence4 reference explicitly instead of widening (D-06, UI-SPEC Q6; step 10; the `modeling` consumer gets its owner here).
- **Depends on:** 4.20. **Parallel:** any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. `GET document-versions/{version_id}/usage` (`DocumentUsageList1`): evidence versions including non-current ones, configurations, approach versions, runs, pending or uncertain operations, and active collection memberships (through the read loop); authorized, paginated with a stable order, `complete` set honestly, non-disclosing. `documents_usage/1` becomes advertised.
  2. `GET models/{model_id}/assumption-evidence` returns `AssumptionEvidenceResolution1` exactly as today when no referenced evidence version is version 4, and `AssumptionEvidenceResolution2` otherwise; the generated response is the explicit union; the exact saved-versus-draft selection and scoped unavailable behaviour stay.
  3. Until tasks 4.35–4.37 land (OQ-1), configuration save and preview and approach save refuse, before any effect, an Evidence4 reference made directly or through the selected model version's assumptions, with `unsupported_capability` 422 naming the field path; older contract versions never accept an Evidence4 shape.
- **Risks:** changing a response type other clients read (the union keeps version 1 byte-identical when no Evidence4 is involved; `ae-*` groups prove it).

</action>

<acceptance_criteria>

- `test_documents_usage_lists_every_dependant`: evidence (current and non-current), pending operations and memberships appear; a foreign version gets 404; pages are stable.
- `test_documents_usage_assumption_evidence_resolution_two_only_with_evidence4` and the unchanged version 1 body for older evidence.
- `test_documents_usage_configuration_and_approach_refuse_evidence4_without_effect` (direct and through model assumptions).
- `ae-configuration`, `approach-configuration`, `approach-api` and `ae-authoring` pass unchanged; `document_slices` contains `documents_usage/1`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-usage</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group ae-configuration</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-configuration</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-api</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.22.md` is verified by the orchestrating session.</done>

</task>

### Task 4.22a — Access-loss seam for the remaining hosts (no behaviour change except the single denial message and the study-shell lists cleared on access loss)

<task type="auto" id="4.22a">

<name>Task 4.22a — Access-loss seam for the remaining hosts (no behaviour change except the single denial message and the study-shell lists cleared on access loss)</name>

<files>

- modify `ui/src/EvidenceView.tsx` (the local `evidenceAccessLost` classification removed), `ui/src/EvidencePicker.tsx`, `ui/src/EvidencePanel.tsx` (the evidence library), `ui/src/Assumptions.tsx`, `ui/src/ModelEditor.tsx`, `ui/src/UnitEditor.tsx`, `ui/src/ConfigurationPanel.tsx` and `ui/src/RecordedConfiguration.tsx` (configuration-editor reads; one message for a denied saved configuration), `ui/src/OverviewRecords.tsx`, `ui/src/ComparisonView.tsx` and the study-shell list holders as Phase 3 task 3.3b leaves them (`ui/src/Workspace.tsx`, and the overview, configurations and evidence view modules under `ui/src/views/` where 3.3b moved their lists), `ui/control-map.json` (`session-access-*` controls), `docs/specs/ui-target.md` (§7 "Access-loss residuals");
- access-loss cases in the existing specs of the groups that serve those hosts: `ui/tests/assumptions-evidence.spec.ts` (`@ae-evidence`, `@ae-model`, `@ae-configuration`) and `ui/tests/unit-authoring.spec.ts` (`@units-authoring`), using the membership controls the AE and units fixtures already have.

</files>

<read_first>

- `.planning/codebase/FACTORIZATION.md` item 10; `docs/specs/ui-target.md` §7 "Access-loss residuals"
- `ui/src/accessLoss.ts` (`useAccessLoss`); `ui/src/api.ts` (`accessDenied`, `accessLostText`, `fence`, `confirmAccess`, `readFailed`, `onSessionChange`); hosts already on the seam as the pattern: `ui/src/EvidenceIndex.tsx`, `RecordedConfiguration.tsx`, `ApproachFindings.tsx`, `executionReadiness.ts`
- the local classification `evidenceAccessLost` in `ui/src/EvidenceView.tsx` and its callers (`EvidencePanel.tsx`, `EvidencePicker.tsx`, `Assumptions.tsx`, `ModelEditor.tsx`, `UnitEditor.tsx`, `ConfigurationPanel.tsx`); `ui/src/Workspace.tsx` (`clearSession`) or the view modules 3.3b created (checkpoint `phases/03-agent-tools-for-coding-agents/checkpoints/3.3b.md`), `OverviewRecords.tsx`, `ComparisonView.tsx`
- `ui/tests/approach.spec.ts` (its `@approach-*` access-loss cases), `ui/tests/assumptions-evidence.spec.ts` (the denied states), their `session-access-*` rows in `ui/control-map.json`; the membership controls of `deployment/tests/ae_ui_fixture.py` and `units_ui_fixture.py` (on the harness after 4.4a)
- `04-PATTERNS.md` "Access-loss seam — residual hosts"

</read_first>

<action>

- **Goal:** a confirmed loss of access to the open study is classified once, by the shared seam, in every evidence, assumption, model, unit, configuration and study-shell host, so that the citation UI of 4.23 is built on the seam (D-02, D-18; FACTORIZATION.md item 10). Behaviour stays what the existing access-loss cases pin, except the two residual defects `docs/specs/ui-target.md` §7 records: a denied saved configuration shows its message once, and the study-shell lists are cleared on a confirmed loss of access to the open study as they already are on sign-out.
- **Depends on:** 4.16 (the UI chain), Phase 3 task 3.3b (study-shell view registry) verified. **Parallel:** with 4.20 and 4.21; any Phase 2 task; no Phase 3 task (`ui/src/Workspace.tsx` and the view modules, the evidence, model, unit and configuration views, `ui/control-map.json`, the AE and units specs).
- **Steps:**
  1. Before any edit, record the exit status and counts of the browser groups that cover access loss or serve these hosts: `ae-ui-evidence`, `ae-ui-model`, `ae-ui-configuration`, `approach-ui-controller`, `approach-ui-reading`, `approach-ui-configuration`, `approach-ui-history`, `units-ui-authoring`, `units-ui-configuration`, `ui-c` and `ui-reading`.
  2. Every host that §7 lists under "Access-loss residuals" subscribes through `useAccessLoss` and classifies a failed read with `api.readFailed` (a confirmed denial through the shared `accessDenied`; a `resource_not_found` confirmed by the study probe), and `evidenceAccessLost` is removed, so no host keeps its own list of denial codes: the evidence view, picker and library (`EvidenceView.tsx`, `EvidencePicker.tsx`, `EvidencePanel.tsx`), the assumption list (`Assumptions.tsx`), the model editor and unit editor (`ModelEditor.tsx`, `UnitEditor.tsx`, whose direct `api.onAuthorizationLoss()` call on a refused read goes through the seam), the configuration-editor reads (assumption evidence, unit preview and saved copies in `ConfigurationPanel.tsx`), and the study-shell lists (Overview records, the configuration and evidence lists, the comparison scope). A denied saved configuration shows its message once (`ConfigurationPanel.tsx` and `RecordedConfiguration.tsx` no longer both report it). Each host clears protected content only, unsaved authoring keeps its own rule, and nothing is submitted; the message a host shows for one record that is not found while study access holds stays as today.
  3. New access-loss cases, named after the invariant, in `ui/tests/assumptions-evidence.spec.ts` and `ui/tests/unit-authoring.spec.ts`, one per host family (evidence view, picker and library; assumption list; model editor; unit editor; configuration-editor reads with the single message; study-shell lists), each mapped in `ui/control-map.json` as a `session-access-*` control. `docs/specs/ui-target.md` §7 records these hosts as on the shared seam and keeps the recommendation of an independent security recheck before they are recorded as mitigated (Phase 5).
  4. After the edit, rerun the groups of step 1: every existing test keeps passing, and each group's count equals its before count plus the new cases of step 3 (table in the checkpoint).
- **Risks:** a host forgotten (the §7 list and the cases of step 3 are compared in the checkpoint); a host that clears more or less than before (the existing access-loss cases keep their counts, and the two intended differences have their own cases).

</action>

<acceptance_criteria>

- The access-loss cases of step 3 pass: after a confirmed loss of access, each host family shows the shared access-lost text, keeps no protected content and sends no write; a denied saved configuration shows the message once; the study-shell lists are empty after a confirmed loss of access to the open study.
- Every group of step 1 passes with its before count plus exactly the new cases of step 3 (table in the checkpoint).
- `git grep -n "evidenceAccessLost" -- ui/src` prints nothing, and `git grep -L "useAccessLoss" -- ui/src/EvidenceView.tsx ui/src/EvidencePicker.tsx ui/src/Assumptions.tsx ui/src/ModelEditor.tsx ui/src/UnitEditor.tsx ui/src/OverviewRecords.tsx ui/src/ComparisonView.tsx` prints nothing.
- `python3 ui/check_design_system.py` prints no FAIL line; the UI contract checker maps every new `session-access-*` control.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group ae-ui-evidence</automated>
<fails_when>exit status is non-zero, or its count is not the before count plus its new access-loss cases</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-model</automated>
<fails_when>exit status is non-zero, or its count is not the before count plus its new access-loss cases</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-configuration</automated>
<fails_when>exit status is non-zero, or its count is not the before count plus its new access-loss cases</fails_when>
<automated>python3 -B deployment/checks.py --group units-ui-authoring</automated>
<fails_when>exit status is non-zero, or its count is not the before count plus its new access-loss case</fails_when>
<automated>python3 -B deployment/checks.py --group units-ui-configuration</automated>
<fails_when>exit status is non-zero, or its count differs from the before table (configuration-editor unit preview)</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-controller</automated>
<fails_when>exit status is non-zero, or its count differs from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-reading</automated>
<fails_when>exit status is non-zero, or its count differs from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-configuration</automated>
<fails_when>exit status is non-zero, or its count differs from the before table (existing access-loss cases)</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-history</automated>
<fails_when>exit status is non-zero, or its count differs from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group ui-c</automated>
<fails_when>exit status is non-zero, or its count differs from the before table</fails_when>
<automated>python3 -B deployment/checks.py --group ui-reading</automated>
<fails_when>exit status is non-zero, or its count differs from the before table (evidence workspace on the in-browser double)</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero, including an unmapped `session-access-*` control</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.22a.md` (the before and after table, the host list compared with ui-target §7) is verified by the orchestrating session.</done>

</task>

### Task 4.23 — Citations in evidence: editor, View evidence and assumptions

<task type="auto" id="4.23">

<name>Task 4.23 — Citations in evidence: editor, View evidence and assumptions</name>

<files>

- create `ui/src/DocumentCitationDialog.tsx` ("Add citation"), `ui/tests/documents-evidence.spec.ts`, `deployment/groups/documents/documents-evidence-ui.json` (mode `browser-native`);
- modify `ui/src/EvidencePanel.tsx` (editor "Citations" section, whole-evidence preview), `ui/src/EvidenceView.tsx` ("Citations" section in `EvidenceRecordBody`), `ui/src/EvidencePicker.tsx` (configuration and approach owners), `ui/src/Assumptions.tsx` (resolution 2), `ui/src/recordViews.ts`, `ui/src/api.ts`, `ui/control-map.json`.

</files>

<read_first>

- `04-UI-SPEC.md` S5 ("Evidence editor", "Add citation"), S6, A6, "Copywriting Contract"
- `ui/src/EvidencePanel.tsx`, `EvidenceView.tsx`, `EvidencePicker.tsx`, `EvidenceIndex.tsx`, `Assumptions.tsx`, `recordViews.ts`, `api.ts` (all on the shared access-loss seam after 4.22a); `ui/tests/assumptions-evidence.spec.ts`, `ui/tests/evidence-workspace.spec.ts`
- `design-system/components/CitationRecord.md`, `components/Evidence.md`, `Naming.md`

</read_first>

<action>

- **Goal:** an engineer adds whole-file citations to evidence in the evidence editor with a server-checked preview, and every "View evidence" dialog shows the stored citations (UI-SPEC S5 evidence editor, S6; D-08, D-10; step 13, HUM-06). The new citation content is protected content of hosts already on the shared access-loss seam (4.22a, D-18).
- **Depends on:** 4.22, 4.10, 4.16, 4.22a. **Parallel:** with 4.24; any Phase 2 task; no Phase 3 task (evidence views and shared UI files).
- **Steps:**
  1. Editor: a "Citations" section after "Source references" with compact `CitationRecord` drafts, "Remove citation", "Add citation" and "N of 20 citations"; with citations present, "Preview citations" is required before "Save evidence" or "Save new version", and any change shows "Fields changed after the preview. Preview citations again before saving."
  2. "Add citation" dialog: find a source from the document list (title and annotation filters; text search appears with task 4.26), "Version" select with the newest marked "(latest)", "What to cite" offering "Whole file" (page and passage options arrive with task 4.29), "Relationship" with none preselected, "Include annotation", "Preview citation" showing the server-checked `CitationRecord`; the duplicate message; the line "A citation records your interpretation; it does not validate the statement."
  3. `EvidenceRecordBody`: a "Citations" section between the content and "Source references", built only from the stored descriptors; "Read cited source" is not shown until task 4.29; old free-text references stay inert text. On a confirmed access loss the citations clear with the rest of the record through the seam.
  4. Model and component assumptions (path 1) and the Evidence page (path 5) show these citations through the same dialog; historical views pass no live library and never fetch (the UI contract checker's no-live-fetch guard covers the citations section).
  5. Configuration and approach evidence pickers omit evidence versions that cite documents and say "N evidence records that cite documents can't be attached here." (OQ-1; task 4.39 lifts it).
  6. Evidence: light and dark, keyboard-only citation add and save, genuine 200 % zoom for the editor, dialog and View evidence states.
- **Risks:** regressions in the existing evidence screens (the `ae-ui-*` groups keep the counts 4.22a recorded).

</action>

<acceptance_criteria>

- `@documents-evidence-ui` tests pass: a whole-file citation is previewed, saved and shown in View evidence from the Evidence page and from a model assumption; a field change clears the preview; a duplicate is refused with its message; 20 citations is the visible maximum; configuration and approach pickers show the omission line; after a confirmed access loss no citation stays on screen.
- `ae-ui-evidence`, `ae-ui-model` and `ae-ui-configuration` pass with the counts checkpoint 4.22a recorded after its edit.
- `python3 ui/check_design_system.py` prints no FAIL line; the UI contract checker maps every new control and route.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-evidence-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-evidence</automated>
<fails_when>exit status is non-zero, or its count differs from checkpoint 4.22a's after count</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-model</automated>
<fails_when>exit status is non-zero, or its count differs from checkpoint 4.22a's after count</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-configuration</automated>
<fails_when>exit status is non-zero, or its count differs from checkpoint 4.22a's after count</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero, including the no-live-fetch guard on historical evidence views</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.23.md` is verified by the orchestrating session.</done>

</task>

### Task 4.24 — Extraction API and fragments

<task type="auto" id="4.24">

<name>Task 4.24 — Extraction API and fragments</name>

<files>

- `application/src/hyprn_mvp_app/documents.py` (attempts, outcomes, reconciliation, runtime availability), `application/src/hyprn_mvp_app/store.py` (`document_extraction_attempts`; the extraction receipt category's recovery rows), `application/src/hyprn_mvp_app/routes/documents.py`, the capabilities route (`documents_extraction/1` in `unavailable`; in the module that checkpoint 3.3a names for it), `application/generate_contract.py`, the regenerated contract and types;
- create `application/tests/test_documents_extraction_api.py`, `deployment/groups/documents/documents-extraction-api.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §7; extraction and fragment routes in the registry; `DocumentExtractionCreate1`, `DocumentExtractionRetry1`, `DocumentAttemptList1`, `DocumentExtractionAttempt1`, `DocumentExtractionResult1`, `DocumentFragmentQuery1`, `DocumentFragment1`, `DocumentExtractionReconciliation1`
- `application/src/hyprn_mvp_app/documents.py`, `routes/documents.py`, the capabilities route; `integration/src/hyprn_mvp_integration/documents.py` and `document_extraction.py` (from 4.21)

</read_first>

<action>

- **Goal:** an engineer starts, inspects and retries extraction attempts and reads exact fragments through the API; attempt states are honest and the original stays downloadable (D-02, D-05; step 7).
- **Depends on:** 4.21, 4.22. **Blocked by:** OQ-2. **Parallel:** with 4.23; any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Routes `POST document-versions/{version_id}/extractions`, `GET document-versions/{version_id}/extractions`, `GET document-extractions/{attempt_id}`, `GET document-extractions/{attempt_id}/result`, `POST document-extractions/{attempt_id}/retry`, `GET document-versions/{version_id}/fragments`.
  2. Extraction operations queue until the single writer is free; a second request waits (one active per installation). Retry is admitted only after a failed or interrupted attempt and creates a new attempt with `retry_of`. The attempt state stays separate from the wrapper state; `uncertain` moves to a terminal state only with a `DocumentExtractionReconciliation1` proof.
  3. Runtime availability: when the host refuses an admission for missing or stale containment evidence, the operation fails before any effect with `backend_unavailable` and the message "Text extraction is not available in this installation."; no attempt is created; while the most recent admission was refused this way, `capabilities.unavailable` also lists `documents_extraction/1`.
  4. Fragments use code point positions, verify the artifact hash and re-authorize at delivery.
  5. `documents_extraction/1` becomes advertised; the extraction receipt category declares its rows in the server-decided recovery table (the 4.9b rule).
- **Risks:** a stale availability flag (cleared by the next successful admission; test).

</action>

<acceptance_criteria>

- `test_documents_extraction_api_outcomes_through_the_api`: complete, partial, unsupported, needs transcription, failed and interrupted attempts are reported with their states, and `GET …/original` returns the exact bytes in each.
- `test_documents_extraction_api_retry_creates_new_attempt` and `test_documents_extraction_api_second_request_waits`.
- `test_documents_extraction_api_unavailable_without_containment_evidence`: 503 before effect, no attempt row, `documents_extraction/1` listed in `unavailable`, cleared after evidence returns and an admission succeeds.
- Foreign attempt or version IDs get the identical 404; an out-of-range fragment span gets 400; `document_slices` contains `documents_extraction/1`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-extraction-api</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-extraction</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-access</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.24.md` is verified by the orchestrating session.</done>

</task>

### Task 4.25 — Processing provenance and search

<task type="auto" id="4.25">

<name>Task 4.25 — Processing provenance and search</name>

<files>

- create `application/src/hyprn_mvp_app/document_search.py`, `application/tests/test_documents_search.py`, `integration/tests/test_documents_extraction_provenance.py`, `deployment/groups/documents/documents-search.json` and `documents-extraction-provenance.json` (mode `native`);
- modify `application/src/hyprn_mvp_app/store.py` (projection tables), `application/src/hyprn_mvp_app/routes/documents.py` (`GET document-search`), `application/src/hyprn_mvp_app/documents.py` (projection build after a result is published; rebuild entry), `application/tests/test_module_boundaries.py`, `application/generate_contract.py`, the regenerated contract and types.

</files>

<read_first>

- `docs/specs/documents.md` §§3 (search projection), 7 (search), 11; `contracts/documents.md` `cursor_binding`; `DocumentSearchQuery1`, `DocumentSearchResult1`
- `application/src/hyprn_mvp_app/store.py` (`list_evidence` cursor binding), `documents.py`, `routes/documents.py`; `integration/src/hyprn_mvp_integration/document_extraction.py`
- `04-RESEARCH.md` "Search Projection (step 8)", assumption A6; `04-UI-SPEC.md` Q9

</read_first>

<action>

- **Goal:** extraction provenance is real and checked; search over metadata and extracted text returns exact snippets with honest coverage, from a projection that is rebuildable and never authoritative (D-01, D-02; step 8).
- **Depends on:** 4.24, 4.14. **Blocked by:** OQ-2. **Parallel:** any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Provenance test: for published results, the calcfunction node's input links (original, configuration) and CREATE output links (manifest, text) match the attempt; no completed process or semantic link is forged.
  2. Projection rows keyed by study, version, extraction, artifact and artifact SHA-256 hold per-page text and a folded copy, built from native artifacts through the `fragment` verb and checked against the manifest page hashes; a full rebuild from native artifacts equals the incremental projection.
  3. Matching: metadata (title, filename, tags, annotation text) and text; query at most 256 code points; snippets at most 512 code points with exact offsets; a per-code-point lowercase fold that keeps length (a code point maps to its lowercase only when that is one code point); no ranking; order by version creation time, version ID, page and offset.
  4. Coverage: indexed and unindexed versions (no attempt, failed, partial) and `coverage` `complete`, `partial` or `unavailable`; an empty result keeps its coverage.
  5. A collection filter uses active native members; a deleted, unknown or foreign collection is not found and never broadens. Signed cursors bind the query, filters and projection revision.
  6. `documents_search/1` becomes advertised; `document_search` is registered in the module-boundary test (imports `contracts`, `store`, `documents` only; reached from `routes.documents`).
- **Risks:** case folding that changes lengths (the fold test uses "ß", "İ" and astral letters).

</action>

<acceptance_criteria>

- `test_documents_extraction_provenance_links_match_attempts` and `test_documents_extraction_provenance_rejects_forged_links`.
- `test_documents_search_snippet_equals_artifact_slice` and `test_documents_search_fold_keeps_offsets`.
- `test_documents_search_coverage_is_honest`: unextracted, failed and partial versions are counted, and an empty result still reports coverage.
- `test_documents_search_deleted_collection_filter_is_not_found`, `test_documents_search_cursor_is_bound`, `test_documents_search_projection_rebuild_equals`.
- `document_slices` contains `documents_search/1`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-search</automated>
<fails_when>exit status is non-zero, including a snippet that differs from the artifact slice</fails_when>
<automated>python3 -B deployment/checks.py --group documents-extraction-provenance</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-access</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group locality-contracts</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.25.md` is verified by the orchestrating session.</done>

</task>

### Task 4.26 — Reader and search UI

<task type="auto" id="4.26">

<name>Task 4.26 — Reader and search UI</name>

<files>

- create `ui/src/DocumentReader.tsx`, `ui/src/DocumentSearch.tsx`, `ui/src/views/documentReader.tsx` (the reader view module, shown under the Documents tab: `parseLink` for document, version, extraction and locator links, `render`, `available` with `documents_extraction/1`), `ui/tests/documents-reader.spec.ts`, `deployment/groups/documents/documents-reader-ui.json` (mode `browser-native`);
- modify `ui/src/DocumentsLibrary.tsx` (search toolbar and results; "Read source"), `ui/src/DocumentCitationDialog.tsx` (text search in "Find a source"), `ui/src/views/registry.ts` (the reader view entry), `ui/src/api.ts`, `ui/control-map.json`, `deployment/tests/documents_ui_fixture.py` (the real parser image and containment evidence inside the scope); `ui/src/workspaceModel.ts` only if Phase 3 task 3.3b left a shared link type that must name the extraction and locator fields.

</files>

<read_first>

- `04-UI-SPEC.md` S1 (search), S4 (text column and reader states), "State vocabulary → Text" and "→ Pages", A5
- `ui/src/design/reader.tsx` (`TextReader`), `ui/src/DocumentsLibrary.tsx`, `ui/src/views/registry.ts` and `ui/src/views/documents.tsx` (from 4.13), `api.ts`; `ui/tests/documents-library.spec.ts`; `deployment/tests/documents_ui_fixture.py`

</read_first>

<action>

- **Goal:** a search hit opens the exact passage in the text-first reader; the reader shows extracted or source text only as escaped text with honest coverage and every extraction state (UI-SPEC S1 search, S4 text column; D-08, D-10, PD-4.4; step 9).
- **Depends on:** 4.25, 4.10, 4.23. **Blocked by:** OQ-2. **Parallel:** with 4.27; any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Reader (with `documents_extraction/1`): back link "All documents", "Download original" always present when authorized, "Record details", the title block with "Latest version" or "Read latest version"; the text column heading names what is shown; page or line navigation with edge buttons removed at the ends; the extraction attempt `Select`; "Extract text" and "Retry extraction" for writers; coverage and per-page tags; the persistent warning line and the CSV and Markdown notes; `TextReader` with the "Choose passage" fieldset and the selection line; old text cleared with "Loading page N…" on navigation; every reader state of UI-SPEC S4 including "extraction is not available".
  2. Search (with `documents_search/1`): toolbar, segmented scope, format and tag filters, coverage notices, hit rows with escaped snippets, "Open passage" (opens the reader with that passage selected and in view) and "Read source", "Load more results", "Clear search", the help line of Q9; "Find a source" in "Add citation" gains text search.
  3. Deep links (the reader view module's `parseLink`) name explicit study, document, version, extraction and locator; an unavailable or foreign target shows "This document is not available. No other document is shown in its place." The reader is a registry view (D-18); `ui/src/Workspace.tsx` gets no Documents-specific change.
  4. Evidence: every reader and search state in light and dark, keyboard-only navigation, genuine 200 % zoom, the backstop of a 256 KiB page with a 10,000-character unbroken line, and hostile HTML, Markdown, script and bidirectional payloads shown inert.
- **Risks:** the fixture needs the parser image (the group's `docker` need; built through `parser_image` into the scope).

</action>

<acceptance_criteria>

- `@documents-reader-ui` tests pass: a text hit opens the reader at the hit's version, extraction, page and range, with the range named in words; each S4 state renders its copy; "Download original" is present in every state; hostile payloads create no element, link or script and bidirectional controls appear as markers.
- At genuine 200 % zoom in both themes, the 256 KiB page and the unbroken line cause no page-wide horizontal scroll.
- `python3 ui/check_design_system.py` prints no FAIL line; every new control and route is mapped.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-reader-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group documents-library-ui</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.26.md` is verified by the orchestrating session.</done>

</task>

### Task 4.27 — Page and passage locators for annotations and citations

<task type="auto" id="4.27" tdd="true">

<name>Task 4.27 — Page and passage locators for annotations and citations</name>

<files>

- `application/src/hyprn_mvp_app/document_citations.py` (page inventory and span resolution, server quotation), `application/src/hyprn_mvp_app/documents.py` (annotation locator checks use the same functions);
- create `application/tests/test_documents_citation_spans.py`, `deployment/groups/documents/documents-citation-spans.json` (mode `native`).

</files>

<read_first>

- `docs/specs/documents.md` §8 (locators); `contracts/documents.md` "Exact locators and source semantics", `span_bounds_and_hash`; `DocumentPdfPageLocator1`, `DocumentExtractedSpanLocator1`, `DocumentFragment1`, `DocumentCitation1`
- `application/src/hyprn_mvp_app/document_citations.py` (from 4.20), `documents.py` (annotation locator checks from 4.17); `04-RESEARCH.md` Pattern 4, Pitfall 10

</read_first>

<behavior>

- An `extracted_span` with `0 ≤ start < end ≤` the artifact's code point length, the same version, extraction, artifact and artifact SHA-256 freezes a quotation equal to the artifact slice and its UTF-8 SHA-256.
- start = end, start > end, negative values, end beyond the artifact, a mismatched extraction or artifact hash, or another version's extraction are refused.
- Two spans that just touch ([a, b) and [b, c)) are distinct citations that do not overlap.
- Slices over astral characters and combining marks keep exact code points.
- A `pdf_page` is admitted only within the PDF's established page inventory; without an inventory the error advises citing the original file.
- A client-supplied quotation never reaches the record (closed schema); the server's quotation is the only one stored.

</behavior>

<action>

- **Goal:** page and passage citations and annotations bind exact, server-verified locations; the quotation is always computed and hashed by the server from the native artifact (D-06; step 10).
- **Depends on:** 4.20, 4.25. **Blocked by:** OQ-2. **Parallel:** with 4.26; any Phase 2 or Phase 3 task (Phase 4 files only).
- **Steps:**
  1. `page_inventory(version, extraction)` from the manifest (PDF media only); `resolve_span(...)` reads the exact text through the read loop's `fragment` verb (never the projection), checks bounds and identities, slices by code points, and hashes the UTF-8 encoding; optional derived line labels are computed by the server.
  2. Remove the `unsupported_capability` refusal of task 4.20 for `pdf_page` and `extracted_span`; citations freeze extraction ID, manifest digest and extractor identity as one complete group.
  3. Annotation create and revise check page and span locators with the same functions.
  4. Every `<behavior>` case is a test written before the implementation.
- **Risks:** offset confusion (the wire carries code points; the browser converts in task 4.28; this task never accepts UTF-16 values).

</action>

<acceptance_criteria>

- Every `<behavior>` case passes as a `test_documents_citation_spans_*` test.
- `test_documents_citation_spans_quote_comes_from_native_artifact`: corrupting the projection row does not change the frozen quotation.
- `documents-citations` and `documents-annotations-api` pass with the refusal removed.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-citation-spans</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-citations</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-annotations-api</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-evidence-v4</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.27.md` is verified by the orchestrating session.</done>

</task>

### Task 4.28 — Annotations, "Used by" and source actions in the reader

<task type="auto" id="4.28">

<name>Task 4.28 — Annotations, "Used by" and source actions in the reader</name>

<files>

- create `ui/src/DocumentAnnotations.tsx`, `ui/src/DocumentUsage.tsx`, `ui/src/documentOffsets.ts`, `ui/tests/documents-annotations.spec.ts`, `deployment/groups/documents/documents-annotations-ui.json` (mode `browser-native`);
- modify `ui/src/DocumentReader.tsx` (side column), `ui/src/DocumentUpload.tsx` (new-version mode), `ui/src/DocumentVersions.tsx` ("Edit title and tags"), `ui/src/api.ts`, `ui/control-map.json`.

</files>

<read_first>

- `04-UI-SPEC.md` S4 (side column, annotation dialogs), S2 (new-version title), "Other document operations", "Keyboard, focus, themes and zoom"
- `ui/src/DocumentReader.tsx`, `DocumentUpload.tsx`, `DocumentVersions.tsx`, `api.ts`; `ui/src/design/reader.tsx`; `design-system/Naming.md` (Annotations, Used by)

</read_first>

<action>

- **Goal:** in the reader's side column an engineer annotates a passage, a page or the whole file, sees what uses the version, and reaches the source actions (UI-SPEC S4; D-08, D-10, PD-4.2; step 10).
- **Depends on:** 4.26, 4.27, 4.22. **Blocked by:** OQ-2. **Parallel:** any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. `documentOffsets.ts`: `utf16RangeToCodePoints(text, range)` converts the reader's UTF-16 range to code point offsets within the fragment and refuses a range that splits a surrogate pair; the artifact ID and SHA-256 come from the fragment; unit cases in the spec cover astral characters and combining marks.
  2. "Annotations" section (with `documents_annotations/1`): up to 100 annotations with locator label, escaped text, tags and update time; "Go to passage", "Edit annotation", "Delete annotation" (confirmation copy and "Keep annotation"); the "Add annotation" dialog with the anchors "Selected passage", "This page", "Whole file", text and tags limits; stale and uncertain notices keep the user's text. The label is always "Annotations".
  3. "Used by" (with `documents_usage/1`) with its rows, actions and empty line; "Source actions": "Upload new version" (upload dialog in new-version mode with family and expected revision), "Edit title and tags" (revision-checked), "Add to collection", "Versions".
  4. Evidence: every side-column state in light and dark, a keyboard-only annotation of a passage using the "Choose passage" fields, genuine 200 % zoom.
- **Risks:** offset conversion errors (unit cases plus the server's bound checks).

</action>

<acceptance_criteria>

- `@documents-annotations-ui` tests pass: a passage annotation made with the keyboard fields stores the same code point span as one made by pointer selection (astral and combining cases); editing one annotation leaves the others unchanged; a stale edit keeps the typed text; "Used by" lists a citing evidence version after task 4.20's flow creates one.
- At genuine 200 % zoom in both themes, the side column stacks below the text without page-wide horizontal scroll.
- `python3 ui/check_design_system.py` prints no FAIL line; every new control and route is mapped.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-annotations-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group documents-reader-ui</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.28.md` is verified by the orchestrating session.</done>

</task>

### Task 4.29 — Citing from the reader, the cited-source view, and citation paths 1 and 5

<task type="auto" id="4.29">

<name>Task 4.29 — Citing from the reader, the cited-source view, and citation paths 1 and 5</name>

<files>

- create `ui/src/DocumentCite.tsx` ("Cite source"), `ui/src/views/citedSource.tsx` (the cited-source view module: `parseLink` for the cited-source link with version, extraction, locator and origin; the record bar "Cited source · Read-only" with the origin's return label through its registry entry; `render` from the stored descriptor only), `ui/tests/documents-cite.spec.ts`, `deployment/groups/documents/documents-cite-ui.json` (mode `browser-native`);
- modify `ui/src/DocumentReader.tsx` (cite group; cited mode), `ui/src/views/registry.ts` (the cited-source entry), `ui/src/DocumentCitationDialog.tsx` (page and passage options), `ui/src/EvidenceView.tsx` ("Read cited source"), `ui/src/api.ts`, `ui/control-map.json`; `ui/src/Workspace.tsx` only for a view-independent record-bar slot if the registry offers none (named in the checkpoint).

</files>

<read_first>

- `04-UI-SPEC.md` S5 ("Cite source"), S6, S7, "Copywriting Contract" (scientific honesty, citation snapshot)
- `docs/specs/documents.md` §15.4; `design-system/components/RecordBar.md`, `CitationRecord.md`
- `ui/src/DocumentReader.tsx`, `DocumentCitationDialog.tsx`, `EvidenceView.tsx`, `ui/src/views/registry.ts` and the reader view module (from 4.26), `Workspace.tsx` (the record bar; read only), `documentOffsets.ts`; `ui/tests/documents-evidence.spec.ts`

</read_first>

<action>

- **Goal:** an engineer cites a passage, page or original from the reader into new or existing evidence, and every citation opens its exact cited source read-only from the Evidence page and from model and component assumptions, even when the source changed later or storage is down (UI-SPEC S5, S6, S7; D-06, D-08, D-10; step 13, HUM-06).
- **Depends on:** 4.28. **Blocked by:** OQ-2. **Parallel:** any Phase 2 task; no Phase 3 task.
- **Steps:**
  1. Cite group in the reader (with `documents_citations/1` and write access): "Cite passage" only while a passage is selected, "Cite page" for a PDF with a known page count, "Cite original". The "Cite source" dialog per S5: summary with `SourceChip`, optional "Section label" for the whole file, required relationship, "Include annotation", segmented "New evidence · Existing evidence", the honesty line, "Preview citation" with the server-checked quotation, invalidation on change and on expiry, "Save evidence" or "Save new version", "Discard citation", and the after-save notice that attaching is a separate step.
  2. "Add citation" in the evidence editor gains "Page" and "Passage from search result".
  3. Cited-source view per S7 (the cited-source view module of the registry, D-18), built only from the stored descriptor: the record bar with "Version <short ID>" and the origin's return label; the text column at the cited extraction with the cited range highlighted and its heading; the attempt line instead of the select; no write actions, no selection fieldset; the saved `CitationRecord` first, then "View latest source" as a separate navigation. When the bytes or text cannot be read (storage or modeling service down), the citation, quotation and annotation snapshot still show with the "Source unavailable" notice, "Original unavailable" and "Retry loading source" (a read, never a resubmission). The UI contract checker's no-live-fetch guard covers this view.
  4. "Read cited source" appears on every saved `CitationRecord` (Evidence page, model and component assumptions).
  5. Evidence: S5 and S7 states in light and dark, a keyboard-only passage citation without a pointer, genuine 200 % zoom, and the backstop: after a new version, a re-extraction and an annotation edit, paths 1 and 5 still open the cited version, extraction and range.
- **Risks:** a historical view borrowing current titles (descriptor-only rendering; test changes the title before reopening).

</action>

<acceptance_criteria>

- `@documents-cite-ui` tests pass: a passage cited from the reader shows the server quotation in the preview and in the saved record; changing any field clears the preview; paths 1 (model assumption → View evidence → Read cited source) and 5 (Evidence page) open the cited version and range after the source got a new version, a new extraction and an edited annotation, and after the document title changed; with the read loop stopped the cited view shows the stored quotation and "Original unavailable"; a keyboard-only passage citation succeeds.
- `@documents-evidence-ui` and `@documents-reader-ui` still pass.
- At genuine 200 % zoom in both themes, the cite actions and the dialog's commit button stay reachable without page-wide horizontal scroll; `python3 ui/check_design_system.py` prints no FAIL line.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-cite-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group documents-evidence-ui</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-reader-ui</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero, including the no-live-fetch guard on the cited-source view</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.29.md` is verified by the orchestrating session.</done>

</task>

### Task 4.30 — Parser image and containment at setup; served Documents journey

<task type="auto" id="4.30">

<name>Task 4.30 — Parser image and containment at setup; served Documents journey</name>

<precondition>Phase 2 tasks 2.11 (setup, start, stop on scratch installations) and 2.14 (operations documentation and the `docs` group) are verified.</precondition>

<files>

- `editions/local/src/hyprn_mvp_local/setup.py` (acquire wheel, build parser image, run containment canaries), `editions/local/src/hyprn_mvp_local/doctor.py` and `status.py` (parser image and containment lines), `deployment/parser_image.py` (installation-driven entry), `deployment/documents_groups.py` (mode `served`; the group's entry file declares class `opt-in`), `docs/operations/cli.md` (any new status or reason code);
- create `deployment/tests/test_documents_served.py`, `deployment/groups/documents/documents-served.json` (mode `served`).

</files>

<read_first>

- `02-PLAN.md` "Target design" (locations, checkout mode, CLI contract) and tasks 2.11, 2.13, 2.14
- `editions/local/src/hyprn_mvp_local/setup.py`, `doctor.py`, `status.py`; `deployment/parser_image.py`, `integration/src/hyprn_mvp_integration/document_parser_launch.py`; `deployment/documents_groups.py`; `docs/operations/cli.md`

</read_first>

<action>

- **Goal:** an installation builds the parser image and demonstrates containment at setup, reports parser state read-only, and the whole Documents journey works on a scratch installation (D-05, D-09, D-11).
- **Depends on:** 4.24, 4.19, Phase 2 tasks 2.11 and 2.14. **Blocked by:** OQ-2. **Parallel:** not beside Phase 2 task 2.12 (`setup.py`); not beside a Phase 3 task editing `editions/local`.
- **Steps:**
  1. `setup` after worker attestation: acquire and verify the wheel into the installation's parser cache, build the parser image from the snapshot, run `attest_parser`, record the evidence; a containment failure leaves the installation usable with extraction unavailable and is reported, never hidden. `start` never rebuilds; a changed image or policy makes extraction admission refuse until the next `setup`.
  2. `doctor` and `status` report the parser image identity and containment as current, stale or absent, read-only.
  3. `documents-served` (opt-in, scratch installation per Phase 2's harness): setup → start → sign in → two-chunk upload → exact download → a run of a fixture component that sleeps 10 s with reads completing within 2 s each during it → stop and start → exact download → extract a generated PDF → a search hit → stop the modeling service → evidence with a citation still readable → `uninstall --purge`; afterwards nothing labelled with the scratch installation remains.
- **Risks:** a long cold build (content-tagged images reused; timings recorded).

</action>

<acceptance_criteria>

- `python3 -B deployment/checks.py --group documents-served` exits 0 on the development host, with the timeline and timings in the checkpoint.
- A scratch setup with a deliberately failing canary completes with `status` showing extraction unavailable, and an extraction request gets `backend_unavailable`.
- `local-lifecycle` and `docs` pass (every new code documented).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-served</automated>
<fails_when>exit status is non-zero, or a labelled resource of the scratch installation remains after the run</fails_when>
<automated>python3 -B deployment/checks.py --group local-lifecycle</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group docs</automated>
<fails_when>exit status is non-zero (an emitted code or command missing from `docs/operations/cli.md`)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.30.md` is verified by the orchestrating session.</done>

</task>

### Task 4.31 — Replace a collection member version (blocked by OQ-3)

<task type="auto" id="4.31">

<name>Task 4.31 — Replace a collection member version (blocked by OQ-3)</name>

<precondition>`04-CONTEXT.md` records D-15 (OQ-3).</precondition>

<reversibility rating="costly">The meaning of `replace` is recorded in native witnesses and replayed forever; a later change of meaning needs a new action, not an edit.</reversibility>

<files>

- `integration/src/hyprn_mvp_integration/documents.py` (`collection_members` replace), `application/src/hyprn_mvp_app/documents.py` (lift the 422), `contracts/documents.md` (the meaning of `replace`), `ui/src/DocumentCollections.tsx` ("Replace version" dialog), `ui/control-map.json`;
- tests: `integration/tests/test_documents_collections.py`, `application/tests/test_documents_collections_api.py`, `ui/tests/documents-collections.spec.ts`.

</files>

<read_first>

- `04-CONTEXT.md` D-15; `04-UI-SPEC.md` S3 ("Replace version"); `contracts/documents.md` "Collection deletion and source fences"; the files above

</read_first>

<action>

- **Goal:** "Replace version" swaps a collection member for another version exactly as D-15 defines, in one revision-checked batch (D-04; step 5).
- **Depends on:** 4.14, 4.16. **Blocked by:** OQ-3. **Parallel:** any Phase 2 task; no Phase 3 task; blocked lane position 2 (one lane task at a time); not beside 4.6, 4.12, 4.17, 4.20, 4.21, 4.22, 4.23, 4.24, 4.25, 4.26, 4.27, 4.28 or 4.29 (see "Blocked lane").
- **Steps:**
  1. Record D-15's meaning in `contracts/documents.md` (wording only, no schema change). With the recommended meaning: for each listed version, the active member of the same family is removed and the listed version added; a listed version whose family has no active member, or two listed versions of one family, are refused; the revision advances once; one witness.
  2. Native, API and UI: lift the `unsupported_capability` refusal; add the S3 "Replace version" dialog with "Current member: Version <short ID>", "Replace with" and the help line "Only this collection changes. Other collections and evidence keep their versions."
- **Risks:** replay of a replace after later edits (historical outcome returned; test).

</action>

<acceptance_criteria>

- Native, API and browser tests (`test_documents_collections_replace_*`, `test_documents_collections_api_replace_*`, `@documents-collections-ui` replace cases) pass, including: other collections keep their versions; a stale replace changes nothing; replay returns the original outcome.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-collections</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-collections-api</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-collections-ui</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.31.md` is verified by the orchestrating session.</done>

</task>

### Task 4.32 — Recent uploads and recovery after reload (blocked by OQ-5)

<task type="auto" id="4.32">

<name>Task 4.32 — Recent uploads and recovery after reload (blocked by OQ-5)</name>

<precondition>`04-CONTEXT.md` records D-17 (OQ-5); Phase 2 task 2.8 (which completes the 2.8a → 2.8b → 2.8c chain — the contract schemas split by consumer is task 2.8c — and re-attests) is verified.</precondition>

<reversibility rating="costly">A new public route and schema that clients read; removing it later breaks them.</reversibility>

<files>

- `contracts/schemas/documents.schema.json` (new list and query definitions; registry route; the non-attested Documents schema of Phase 2 task 2.8), `contracts/documents.md` (route row), `contracts/tests/test_documents_contract.py`, `application/src/hyprn_mvp_app/documents.py`, `application/src/hyprn_mvp_app/routes/documents.py`, `application/generate_contract.py`, the regenerated contract and types, `ui/src/DocumentsLibrary.tsx`, `ui/src/DocumentUpload.tsx`, `ui/src/api.ts`, `ui/control-map.json`, `ui/tests/documents-library.spec.ts`;
- create `application/tests/test_documents_upload_recovery.py`, `deployment/groups/documents/documents-upload-recovery.json` (mode `native`).

</files>

<read_first>

- `04-CONTEXT.md` D-17; `04-UI-SPEC.md` S1 (Uploads panel), Q4, "State vocabulary → Uploads"; `contracts/documents.md` "Public transport and permissions"; `contracts/schemas/documents.schema.json` and `contracts.validator(name)` (Phase 2 task 2.8); `application/src/hyprn_mvp_app/documents.py`, `routes/documents.py`; `ui/src/DocumentsLibrary.tsx`, `DocumentUpload.tsx`

</read_first>

<action>

- **Goal:** every unfinished or attention-needing upload of the study stays visible in the library after a reload, which completes success criterion 2 (D-02; step 4); its new definitions live in the non-attested Documents schema, so the worker is not re-attested (D-18).
- **Depends on:** 4.9b, 4.13, Phase 2 task 2.8 (Documents definitions in the non-attested schema). **Blocked by:** OQ-5. **Parallel:** any Phase 2 task after 2.8; no Phase 3 task; blocked lane position 3 (one lane task at a time); not beside 4.6, 4.14, 4.16, 4.17, 4.20, 4.22, 4.23, 4.24, 4.25, 4.26, 4.27, 4.28 or 4.29 (see "Blocked lane").
- **Steps:**
  1. Contract per D-17 (recommended `GET document-uploads`, roles owner, writer and reader): uploads of the study within the 24-hour retention that are not published or that ended failed, expired, interrupted or uncertain; signed cursor; stable order; the route joins `documents_library/1` in `DOCUMENT_SLICES`.
  2. The Uploads panel loads this list on mount and after each state change; "Continue upload" after a reload asks for the same file and checks size and SHA-256.
- **Risks:** disclosure of another study's uploads (access matrix extended to the new route).

</action>

<acceptance_criteria>

- `test_documents_upload_recovery_*`: the list shows each attention state and nothing published or older than 24 hours; foreign IDs and cursors get identical errors.
- `@documents-library-ui` reload cases: after a page reload, receiving, failed, expired, interrupted and uncertain uploads are listed with their notices and actions; "Continue upload" with a different file shows "This is not the same file…".
- `documents-contracts` passes with the new definitions; the earlier definitions are unchanged; the attested inventory (`launcher.execution_source_hashes()`) and the generated execution schema are byte-identical before and after (a Documents-only definition re-attests nothing; both digests in the checkpoint).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-upload-recovery</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-library-ui</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-contracts</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-access</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.32.md` is verified by the orchestrating session.</done>

</task>

### Task 4.33 — Document writes in archived studies (blocked by OQ-4)

<task type="auto" id="4.33">

<name>Task 4.33 — Document writes in archived studies (blocked by OQ-4)</name>

<precondition>`04-CONTEXT.md` records D-16 (OQ-4).</precondition>

<reversibility rating="costly">Option a gives "archive" a second meaning that every later write path must honour.</reversibility>

<files>

- `application/src/hyprn_mvp_app/documents.py` (one writable-study check in the document command path), `application/generate_contract.py` and the regenerated contract (archive description, option a only), `docs/specs/documents.md` (§18 Q4 records the decision), `ui/src/DocumentsLibrary.tsx` and `ui/src/DocumentReader.tsx` (option a only), `ui/tests/documents-library.spec.ts`;
- create `application/tests/test_documents_archived_study.py`, `deployment/groups/documents/documents-archived-study.json` (mode `native`).

</files>

<read_first>

- `04-CONTEXT.md` PD-4.3 and D-16; `application/generate_contract.py` (study archive description); `application/src/hyprn_mvp_app/store.py` (`set_study_archived`); `04-UI-SPEC.md` "UI Considerations" (archived study row)

</read_first>

<action>

- **Goal:** documents in an archived study behave exactly as D-16 decides, for every document write route present and future (D-02).
- **Depends on:** 4.9b and 4.13 (it edits the library view and spec that 4.13 creates, and runs `documents-library-ui`); with option a also 4.29, so every reader write action exists when the archived-study rule is applied. **Blocked by:** OQ-4. **Parallel:** any Phase 2 task; no Phase 3 task; blocked lane position 4 (one lane task at a time); not beside 4.6, 4.14, 4.16, 4.17, 4.20, 4.22, 4.24, 4.25, 4.26, 4.27, 4.28 or 4.29 (see "Blocked lane"; 4.16, 4.26, 4.28 and 4.29 write `ui/src/DocumentsLibrary.tsx` or `ui/src/DocumentReader.tsx` and are listed whatever the option, because only option a makes them dependencies).
- **Steps:**
  1. Option a: every document write passes one check in the document command path and is refused before any effect with `forbidden` 403 and a field issue naming the archived study; reads continue; restoring the study re-enables writes; the generator's archive description names the documents exception; the UI removes write actions through the same write-access check that removes them for the reader role (4.13), so a Documents surface that lands later in the lane (4.31, 4.32) honours it without its own change, and shows "This study is archived. Its documents are read-only until the study is restored."
  2. Option b: tests prove that document writes in an archived study behave like every other record's; no UI change.
  3. `docs/specs/documents.md` §18 Q4 records the decision.
- **Risks:** a write route added later bypassing the check (the check lives in the single command path every write uses; a test enumerates the mounted write routes).

</action>

<acceptance_criteria>

- `test_documents_archived_study_*` covers every mounted document write route under the chosen option; `api-a` (study archive) passes unchanged.
- Option a: `@documents-library-ui` archived cases show the line and no write action.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-archived-study</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group api-a</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group documents-library-ui</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.33.md` is verified by the orchestrating session.</done>

</task>

### Task 4.34 — Document-bearing chain contract amendment (blocked by OQ-1)

<task type="auto" id="4.34">

<name>Task 4.34 — Document-bearing chain contract amendment (blocked by OQ-1)</name>

<precondition>`04-CONTEXT.md` records D-13 (OQ-1); checkpoint 4.3 is verified; Phase 2 task 2.8 (which completes the 2.8a → 2.8b → 2.8c chain — the contract schemas split by consumer is task 2.8c — and re-attests) is verified.</precondition>

<reversibility rating="one-way">New scientific record versions and public read unions; the checkpoint:decision in task 4.3 precedes this task.</reversibility>

<files>

- `contracts/documents.md` ("Exact scientific pairings", "Consumers that adopt these types"), `contracts/schemas/documents.schema.json` (Documents-only definitions; registry `scientific_allocations`), `contracts/schemas/model.schema.json` (the chain's non-Documents definitions and any shared citation definition, as the split approved at Phase 2 checkpoint 2.8a places them; an attested input), never the generated `contracts/schemas/execution.schema.json` (its closure grows only when 4.37 names the new versions in execution admission), `contracts/tests/test_documents_contract.py` (selector `test_documents_chain_contracts_`), `docs/specs/documents.md` (§8 version list), `application/generate_contract.py` and the regenerated contract and types (new definitions flow into components);
- create `deployment/groups/documents/documents-chain-contracts.json` (mode `application/contracts`).

</files>

<read_first>

- `04-CONTEXT.md` D-06 and D-13; `contracts/documents.md` "Evidence with document citations"; checkpoint `phases/02-local-edition/checkpoints/2.8a.md` (the approved split); the schemas as Phase 2 task 2.8 leaves them (`model.schema.json`, `documents.schema.json`, the generated execution schema and the generated-equals-closure test): `FrozenConfiguration7*`, `ExecutionBundle8*`, `RunHistory6*`, `ModifiedRunSeed6*`, `ApproachClosure3` and the allocated document-bearing definitions; `integration/src/hyprn_mvp_integration/launcher.py` (`execution_source_hashes`); `application/src/hyprn_mvp_app/execution_bundle.py`; `application/tests/test_identity_golden.py`

</read_first>

<action>

- **Goal:** the contract states, in closed definitions and the registry, how citations travel with configurations, approach versions and runs for current models, without widening any earlier definition (D-06 as amended by D-13; step 11).
- **Depends on:** 4.3, 4.4 (its group file needs the group registry), and Phase 2 task 2.8 (the contract schema split); starts only after 4.4a, 4.22 and 4.22a are verified, so the stale-attestation window it opens stalls no numbered-wave task. **Blocked by:** OQ-1. **Parallel:** any Phase 2 task; not beside a Phase 3 task that edits the contract schemas; blocked lane position 1 (one lane task at a time); not beside 4.6, 4.9a, 4.9b, 4.14, 4.17, 4.20, 4.22, 4.24 or 4.25, the Phase 4 tasks that edit `contracts/documents.md`, `docs/specs/documents.md` or regenerate the contract (see "Blocked lane").
- **Steps:**
  1. Option a: allocate the document-bearing versions D-13 names over the current chain (Model4 and closure 3), each a disjoint union branch with explicit read unions; update the pairings table and the consumers table; keep the existing Model2 and Model3 allocations.
  2. Option b: state in the registry and the document that document-bearing configurations pair only with selected Model2 and Model3, and add structural tests that a Model4 or closure-3 pairing with Evidence4 is refused.
  3. Every pre-existing definition's canonical JSON is byte-identical before and after (test compares against the committed pre-amendment copy); the golden identity corpus is unchanged. Documents-only definitions go to `documents.schema.json` and the others to `model.schema.json`, as the approved split places them; the generated execution schema is byte-identical before and after. The checkpoint lists every attested input that changed (`model.schema.json`) and names 4.37 as the chain's single re-attestation (D-18). This commit opens the stale-attestation window (see "Blocked lane"): the checkpoint runs the window's candidate groups on the committed tree and records which fail; that measured list is the binding forbidden list until 4.37 is verified.
- **Risks:** an accidental widening through a shared alias (the byte-identity test and `oneOf` disjointness tests).

</action>

<acceptance_criteria>

- `test_documents_chain_contracts_*` pass: new definitions are closed, branches disjoint, accepted and rejected fixtures behave as the pairings table says, and no earlier definition changed.
- `locality-contracts` (golden corpus) and `ae-generated` pass.
- `contracts/schemas/execution.schema.json` is byte-identical before and after and the generated-equals-closure test passes; every definition added to `model.schema.json` is referenced by a non-Documents definition or is one (none is Documents-only); digests in the checkpoint.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-chain-contracts</automated>
<fails_when>exit status is non-zero, including a changed pre-existing definition</fails_when>
<automated>python3 -B deployment/checks.py --group documents-contracts</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group locality-contracts</automated>
<fails_when>exit status is non-zero (golden identities changed)</fails_when>
<automated>python3 -B deployment/checks.py --group ae-generated</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.34.md` is verified by the orchestrating session.</done>

</task>

### Task 4.35 — Configuration and approach chain in the application (blocked by OQ-1)

<task type="auto" id="4.35">

<name>Task 4.35 — Configuration and approach chain in the application (blocked by OQ-1)</name>

<files>

- `application/src/hyprn_mvp_app/configuration.py`, `scientific_configuration.py`, `approach.py`, `approach_closure.py`, `result_bindings.py`, `modeling.py` (private projection request), `document_citations.py` (shared source reservation), `store.py` (reservations at configuration and approach publication), the configuration and approach route modules that checkpoint 3.3a names (they accept the new versions), `application/generate_contract.py`, the regenerated contract and types;
- create `application/tests/test_documents_configuration_chain.py`, `deployment/groups/documents/documents-configuration-chain.json` (mode `application/contracts`).

</files>

<read_first>

- `contracts/documents.md` "Exact scientific pairings", "Consumers that adopt these types" (`scientific_configuration`, `configuration`, `result_bindings`, `approach_closure`, `approach`), "Commit, deletion and retention boundary"; D-13
- the application files above; `application/tests/test_scientific_configuration.py`, `test_approach_configuration.py`, `test_approach_closure.py`
- "Stale-attestation window" under "Blocked lane" in this plan

</read_first>

<action>

- **Goal:** configurations and approach versions carry evidence with citations through preparation, with separate full and private digests and source reservations, and without widening earlier versions (D-06, D-13; step 11, RUN-02).
- **Depends on:** 4.34, 4.22. **Blocked by:** OQ-1. **Parallel:** with 4.36; any Phase 2 task after 2.8 (through 4.34) whose verification does not depend on a stale-attestation window group; no Phase 3 task; blocked lane position 5 (one lane task at a time); not beside 4.24, 4.25 or 4.27 (see "Blocked lane").
- **Steps:**
  1. Admit the D-13 configuration request, candidate, revision, preview and commit versions; the deterministic private projection with exact Evidence4 descriptors and its own digest; the full application digest kept separately; older mappings unchanged. The new versions are admitted with explicit version checks in the style of today's code, each listed in the checkpoint; task 4.37 replaces them with capability questions when it adds the version-family table inside the re-attesting task (D-18), so this task does not edit `execution_bundle`.
  2. Inside the publication transaction: re-authorize every cited source, check descriptors and annotation revisions, reserve sources; a changed source needs a new preview.
  3. Approach closure dispatch on the closure version; the new saved, version and preview wrappers; result bindings with the new configuration as source and destination.
  4. Lift task 4.22's Evidence4 refusal exactly for the admitted pairings (option b keeps it for Model4 and closure 3).
  5. The modeling client sends the private projection only when the modeling service advertises it (task 4.36); tests use the modeling double.
  6. This task changes attested sources (`scientific_configuration.py`, `approach_closure.py`) inside the stale-attestation window that 4.34 opened; it does not re-attest (4.37 does, once).
- **Risks:** large surface (each consumer row of the contract has its own test).

</action>

<acceptance_criteria>

- `test_documents_configuration_chain_*` pass: a configuration with cited evidence previews and commits; the private projection keeps citations and its digest differs from the full digest; older configuration and approach fixtures produce identical bytes; reservations are written in the publication transaction.
- `approach-configuration`, `ae-configuration`, `approach-closure`, `units-configuration` and `locality-contracts` pass.
- The checkpoint lists every explicit version check this task added (file and line), which 4.37 replaces.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-configuration-chain</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-closure</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group ae-configuration</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-configuration</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group units-configuration</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group locality-contracts</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.35.md` (the explicit version checks added) is verified by the orchestrating session.</done>

</task>

### Task 4.36 — Modeling service admits the private projection (blocked by OQ-1)

<task type="auto" id="4.36">

<name>Task 4.36 — Modeling service admits the private projection (blocked by OQ-1)</name>

<precondition>Phase 2 task 2.6 (modeling image from verified upstream and ordered patches) is verified.</precondition>

<files>

- `contracts/modeling.openapi.yaml` (private projection request and revision admission; capability), create `upstream/whatsopt-patches/100-document-citations.patch` (AGPL-3.0-only notice), create `modeling/tests/test_documents_private_projection.py`, `modeling/provenance.md` (patch list and digests), the patch digests in `deployment/modeling_runtime.py` and `deployment/pins.json`;
- create `deployment/groups/documents/documents-modeling-private.json` (`runner: documents`, mode `modeling`; the mode is added to `deployment/documents_groups.py` with the same interpreter, needs and modeling setup as the existing `ae-model` entry).

</files>

<read_first>

- `contracts/documents.md` "Consumers that adopt these types" (modeling row); `contracts/modeling.openapi.yaml`; `upstream/whatsopt-patches/090-quantity-definitions.patch`; `modeling/provenance.md`; `docs/legal/licensing.md` §§2–3; `modeling/tests/test_assumptions.py`
- "Stale-attestation window" under "Blocked lane" in this plan; checkpoint 4.34 (the binding window list)

</read_first>

<action>

- **Goal:** the modeling service admits the private projection that carries citation descriptors, keeps them byte-exact through static preparation, and never fetches or parses a source (D-13; AGPL scope; step 11).
- **Depends on:** 4.34, Phase 2 task 2.6. **Blocked by:** OQ-1. Runs inside the stale-attestation window; it runs the post-modeling window candidates only to measure them. **Parallel:** with 4.35 and any other lane task (outside the lane: no shared file); not beside Phase 2 task 2.6; not beside 4.8, 4.15, 4.18 or 4.30 (`deployment/documents_groups.py`, `deployment/pins.json`); any Phase 3 task that names no group on the binding window list.
- **Steps:**
  1. Modeling contract: explicit request and revision admission and capability for the private projection; existing compatibility and preparation definitions unchanged.
  2. The patch applies after `090` with `patch --batch --fuzz=0`, carries the AGPL-3.0-only notice, and enters the corresponding-source directory and the provenance record with its digest.
  3. Rebuild the modeling image from pins; tests in the image prove admission, byte-exact descriptors and the absence of any parser, source fetch or model-version promotion.
  4. Re-measure the window: on this task's committed tree, run the post-modeling candidates (`units-worker`, including its native-program part `integration/tests/test_native_program.py`; `units-native`; `fuel-native-provenance`; `ae-model`; `units-model`; and any other group the checkpoint finds reading the pinned modeling producer or the frozen native programs) and add every failing group, with its failure, to the binding window list that checkpoint 4.34 started. This checkpoint holds the updated list, which stays binding until 4.37b closes the window.
- **Risks:** generated-code licence questions (unchanged; recorded per prepared artifact as today); a post-modeling group failing for a reason other than the pinned producer (the checkpoint names the failing cases; only pinned-producer or fixture-identity failures may join the window list, any other failure is repaired here).

</action>

<acceptance_criteria>

- `test_documents_private_projection_*` pass in the rebuilt modeling image; the patch applies with zero fuzz.
- `ae-model` and `units-model` pass, or each fails only on pinned-producer or fixture-identity cases and is on the updated binding window list with its failure.
- Checkpoint 4.36 records the outcome of every post-modeling candidate and the updated binding window list.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-modeling-private</automated>
<fails_when>exit status is non-zero or the patch does not apply with zero fuzz</fails_when>
<automated>python3 -B deployment/checks.py --group ae-model</automated>
<fails_when>exit status is non-zero and the group is not on the updated binding window list in checkpoint 4.36, or it fails on a case other than a pinned-producer or fixture-identity case</fails_when>
<automated>python3 -B deployment/checks.py --group units-model</automated>
<fails_when>exit status is non-zero and the group is not on the updated binding window list in checkpoint 4.36, or it fails on a case other than a pinned-producer or fixture-identity case</fails_when>
<automated>python3 -B deployment/checks.py --group units-worker</automated>
<fails_when>its outcome is missing from checkpoint 4.36, or it fails and is not on the updated binding window list</fails_when>
<automated>python3 -B deployment/checks.py --group units-native</automated>
<fails_when>its outcome is missing from checkpoint 4.36, or it fails and is not on the updated binding window list</fails_when>
<automated>python3 -B deployment/checks.py --group fuel-native-provenance</automated>
<fails_when>its outcome is missing from checkpoint 4.36, or it fails and is not on the updated binding window list</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.36.md` (patch and image digests, the post-modeling measurement and the updated binding window list) is verified by the orchestrating session.</done>

</task>

### Task 4.37 — Version-family capabilities, bundle, launcher and worker admission with re-attestation (blocked by OQ-1)

<task type="auto" id="4.37">

<name>Task 4.37 — Version-family capabilities, bundle, launcher and worker admission with re-attestation (blocked by OQ-1)</name>

<precondition>Phase 2 task 2.8 (release binding and the re-attestation that completes the 2.8c contract-schema split with the generated execution schema) is verified.</precondition>

<files>

- `application/src/hyprn_mvp_app/execution_bundle.py` (the version-family capability table; the new frozen and bundle families; one more tuple each in `RETAINED_PAIRINGS`), `application/src/hyprn_mvp_app/configuration.py` and `application/src/hyprn_mvp_app/approach.py` (capability questions replace the version literals, including the explicit checks 4.35 added), `application/src/hyprn_mvp_app/execution.py` and `application/src/hyprn_mvp_app/computational_export.py` (capability questions instead of version literals; the explicit refusal for document-bearing bundles), `integration/src/hyprn_mvp_integration/results.py`, `calculation.py`, `worker.py` (its own independent table), `launcher.py` (attested set), the regenerated `contracts/schemas/execution.schema.json` (produced by the Phase 2 task 2.8 generator, never hand-edited), the attested-set pins and the two-sided coverage test, `application/tests/test_module_boundaries.py` (capability property tests; `HISTORIC_PAIRINGS`, `HISTORIC_FAMILIES`);
- create `integration/tests/test_documents_bundle_admission.py`, `deployment/groups/documents/documents-bundle-admission.json` (mode `native`).

</files>

<read_first>

- `contracts/documents.md` "Exact scientific pairings", the `execution`, `execution_bundle` and integration rows of "Consumers that adopt these types"; D-13
- `.planning/codebase/FACTORIZATION.md` items 11 and 12 and "Not recommended" (the worker keeps its own table)
- `application/src/hyprn_mvp_app/execution_bundle.py` (the "Version interpretation points" comment, `RETAINED_PAIRINGS`, `BundleFamily` with `carries_dependencies` and `carries_approach`, `bundle_family`, `UnsupportedRetainedVersion`, `uses_typed_units`, `uses_polish_envelope`, `uses_units_envelope`, `frozen_version`, `validate_retained_bundle`, `assemble_bundle`); `application/src/hyprn_mvp_app/history.py` (`stored_family`); the literal version comparisons in `configuration.py`, `approach.py`, `execution.py` and `computational_export.py`, and checkpoint 4.35 (the explicit checks it added)
- `application/tests/test_module_boundaries.py` (`HISTORIC_PAIRINGS`, `HISTORIC_FAMILIES`, `FAMILY_LITERALS`, `PRODUCER_MAPS`, `test_application_holds_no_second_retained_pairing_table`, `test_unlisted_bundle_versions_are_explicitly_unsupported`); `application/tests/test_identity_golden.py`
- `integration/src/hyprn_mvp_integration/launcher.py` (`execution_source_hashes`, `attest`); the Phase 2 task 2.8 execution-schema generator and its generated-equals-closure test; `04-RESEARCH.md` Pitfall 7; "Stale-attestation window" under "Blocked lane" and checkpoints 4.34 and 4.36 (the binding window list)

</read_first>

<action>

- **Goal:** the application asks version families for capabilities instead of comparing version literals, so the chain's versions are threaded through one table that lives in the re-attesting task; document-bearing runs freeze, bundle and execute with citation descriptors re-admitted by the launcher and the worker before any candidate code loads; a citation is never a numerical dependency; and the worker is re-attested once for the whole chain, after which 4.37b re-pins the producer, recaptures the native fixtures and closes the stale-attestation window (D-06, D-13, D-18; step 11, RUN-02; FACTORIZATION.md item 12).
- **Depends on:** 4.35, 4.36, Phase 2 task 2.8. **Blocked by:** OQ-1. **Parallel:** with any lane task that is not a dependant (outside the lane: it shares files only with 4.35, its dependency); not beside a Phase 2 task that edits the attested set; not beside 4.25 (`application/tests/test_module_boundaries.py`); not beside a Phase 3 task that edits `execution.py`, `approach.py` (3.3c, 3.32) or `test_module_boundaries.py`.
- **Steps:**
  1. Version-family capabilities, first, with no behaviour change. Before any edit, record the counts of the groups that read or interpret retained and authored records: `locality-contracts` (golden identity corpus, module boundaries), `units-configuration`, `ae-configuration`, `approach-configuration`, `approach-closure`, `documents-configuration-chain`, `units-history`, `approach-history`, `ae-history`, `ae-export`, `approach-export`, `units-bundle` and `approach-bundle`. Then extend the family object in `execution_bundle` so each record family declares its capabilities (`carries_dependencies`, `typed_units`, `polish_envelope`, `approach_closure`, `document_citations`) behind `family(record).has(capability)`, where `record` is a stored or authored model, configuration, frozen configuration, approach closure or bundle manifest and an unlisted version raises `UnsupportedRetainedVersion` as today; `bundle_family`, `BundleFamily.carries_dependencies` and `carries_approach` read the same table, and the configuration versions 4.35 admitted are declared with `document_citations`. Producers and admission sets stay explicit and strict (`assemble_bundle`, `Configurations.require_version_pair`, the `PRODUCER_MAPS` of the boundary test). `configuration.py`, `approach.py`, `execution.py` and the application `computational_export.py` replace their literal version comparisons, including the explicit checks 4.35 added, with capability questions. Property tests in `test_module_boundaries.py`, named after the invariant (for example `test_version_family_capabilities_reproduce_the_retained_pairings` and `test_version_family_capabilities_answer_as_the_replaced_predicates`): the table reproduces `RETAINED_PAIRINGS` and `HISTORIC_FAMILIES` exactly, and for every version string `'0'`–`'9'` and the malformed values of `test_unlisted_bundle_versions_are_explicitly_unsupported`, each capability answers as the literal predicate it replaces (a copy of the replaced predicates is kept in the test). Rerun the recorded groups: identical counts (historical reads accept exactly the same records) before any new frozen or bundle version is added.
  2. Frozen and bundle versions per D-13: one more family each in the capability table, with `document_citations` and the capabilities the bundle carries, and one more tuple each in `RETAINED_PAIRINGS` (and in `HISTORIC_PAIRINGS` and `HISTORIC_FAMILIES` of the boundary test, so the property tests cover them); full, private and closure files with role, size and hash equality; no document bytes in any bundle.
  3. Launcher and worker readers: explicit admission of the new bundle, reconstruction and equality of the private projection, closed citation keys and hashes, closure digest reconstruction; the worker holds no parser, lookup or credential and keeps its own independent version table (the trust boundary; it imports nothing from `execution_bundle`).
  4. Regenerate the execution schema with the 2.8 generator (its closure now names the new versions) and keep the generated-equals-closure test green. Recompute the attested-set pins, keep the two-sided coverage test green, and re-attest once: this re-attestation covers every attested change of the chain since 4.34 (4.34's `model.schema.json` definitions, 4.35's configuration and closure changes, 4.36's modeling inputs, this task's capability table and admission). Document modules stay outside the attested set.
  5. The computational record export refuses a document-bearing run with the existing unavailable-reason path; adopting a document-aware export envelope belongs to the deferred portability phase (PD-4.1).
  6. Older goldens and pairings stay byte-identical. Rerun the groups of step 1: every count equals step 1's record plus the new cases only. Groups on the binding window list are not run here except `units-worker` for its worker-admission cases; the window stays open until 4.37b.
- **Risks:** attestation drift (recomputed digests listed path by path in the checkpoint); a capability that answers differently from the literal it replaces for one historical version (the predicate-equality property test over every version value, and step 1's before and after counts); context size (step 1 is a separate commit with its own before and after table, so a failure there stops the task before any new version is added).

</action>

<acceptance_criteria>

- The capability property tests pass; the groups recorded in step 1 have identical counts after the capability move as before it, the golden identity corpus included (table in the checkpoint); every literal version comparison left in `configuration.py`, `approach.py`, `execution.py` and `computational_export.py` is an admission or producer site listed in the checkpoint with its reason.
- `test_documents_bundle_admission_*` pass: a document-bearing bundle is admitted by launcher and worker; a tampered citation key or hash is refused before candidate code loads; the export of such a run is refused with its reason.
- The generated execution schema equals its closure; one re-attestation is recorded, with every attested digest change of the chain listed path by path.
- `units-attestation`, `units-launcher`, `units-bundle`, `approach-bundle`, `approach-worker` and `locality-contracts` pass; `units-worker` passes except the pinned-producer cases on the binding window list; the two-sided coverage test passes.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group locality-contracts</automated>
<fails_when>exit status is non-zero, including a capability property test or the golden identity corpus</fails_when>
<automated>python3 -B deployment/checks.py --group documents-bundle-admission</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group units-attestation</automated>
<fails_when>exit status is non-zero (stale attestation or coverage mismatch)</fails_when>
<automated>python3 -B deployment/checks.py --group units-worker</automated>
<fails_when>a case fails that is not a pinned-producer case on the binding window list (worker admission regressed)</fails_when>
<automated>python3 -B deployment/checks.py --group units-launcher</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-worker</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-bundle</automated>
<fails_when>exit status is non-zero, or its count is not step 1's record plus the new cases</fails_when>
<automated>python3 -B deployment/checks.py --group units-bundle</automated>
<fails_when>exit status is non-zero, or its count is not step 1's record plus the new cases</fails_when>
<automated>python3 -B deployment/checks.py --group units-configuration</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group ae-configuration</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group approach-configuration</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group approach-closure</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group documents-configuration-chain</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record (4.35's versions answered through capabilities)</fails_when>
<automated>python3 -B deployment/checks.py --group units-history</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record (a historical record accepted or refused differently)</fails_when>
<automated>python3 -B deployment/checks.py --group approach-history</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group ae-history</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group ae-export</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group approach-export</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.37.md` (the before and after table of step 1, the remaining literal sites with their reasons, every attested digest change) is verified by the orchestrating session.</done>

</task>

### Task 4.37b — Producer re-pin and native fixture recapture; the stale-attestation window closes (blocked by OQ-1)

<task type="auto" id="4.37b">

<name>Task 4.37b — Producer re-pin and native fixture recapture; the stale-attestation window closes (blocked by OQ-1)</name>

<files>

- `deployment/pins.json` (`modeling_producer`: image and `artifact_source_hashes`), `integration/tests/fixtures/native-programs.json.gz` (new capture), `deployment/tests/durable_fixture.py` (`NATIVE_FIXTURE`, `NATIVE_MANIFEST_SHA256`), and only where the tracked capture tools change a pinned value, the files that pin it (each listed in the checkpoint with its old and new value).

</files>

<read_first>

- `.planning/STATE.md` decision on the pinned modeling producer (a modeling-source change needs a rebuild, a new pin and a fixture recapture); checkpoint `phases/01-repository-baseline/checkpoints/1.9.md` (the last recapture) and Phase 2 checkpoint 2.8 (its recapture after re-attestation)
- `deployment/tests/durable_fixture.py` (capture, manifest pin, `native_scope`), `integration/tests/capture_native_programs.py`, `integration/tests/fixtures/README.md`, `integration/tests/test_native_program.py`, `deployment/pins.json`
- "Stale-attestation window" under "Blocked lane"; checkpoints 4.34 and 4.36 (the binding window list) and 4.37 (the re-attestation)

</read_first>

<action>

- **Goal:** after the chain's single re-attestation, the pinned modeling producer and the native captures match the committed tree again, so every group on the binding window list passes and the stale-attestation window closes (D-18; the STATE rule for a modeling-source change).
- **Depends on:** 4.37. **Blocked by:** OQ-1. **Parallel:** outside the lane; not beside 4.15 (`deployment/pins.json`); not beside a Phase 2 task that edits `deployment/pins.json` or the native fixture pins; any Phase 3 task that names no group on the binding window list.
- **Steps:**
  1. Rebuild the modeling image once from the committed tree through the reviewed manager rebuild for the development fixture roots, and re-pin `modeling_producer` (image and `artifact_source_hashes`) in `deployment/pins.json`.
  2. Recapture the frozen native programs with `integration/tests/capture_native_programs.py` from the re-pinned producer, and the durable native fixture with `python3 -B deployment/tests/durable_fixture.py capture --scope <producer scope root>` from a fully passing `units-native` producer run on the committed tree; pin the new manifest digest. Earlier captures are never modified; the checkpoint records old and new identities.
  3. Run every group on the binding window list (checkpoints 4.34 and 4.36) and the durable-fixture guard cases (`guard`): all pass. The window closes when this task is verified.
- **Risks:** a capture taken from a run that did not fully pass (the capture tool refuses it; the checkpoint records the producer run's counts); a pinned value outside the listed files (the guard's pin checks and the window groups fail).

</action>

<acceptance_criteria>

- `deployment/pins.json` names the rebuilt producer; the frozen native programs and the durable native fixture are new captures with old and new identities in the checkpoint.
- Every group on the binding window list passes on the committed tree, at least `findings-native-preflight`, `findings-native`, `findings-native-read`, `approach-ui-history`, `units-worker`, `units-native` and `fuel-native-provenance` when 4.34 or 4.36 listed them.
- `guard` passes (durable-fixture pins and manifests).

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group findings-native-read</automated>
<fails_when>exit status is non-zero: the durable native fixture does not match the re-attested tree, so the window is still open</fails_when>
<automated>python3 -B deployment/checks.py --group findings-native</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-history</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group units-worker</automated>
<fails_when>exit status is non-zero, including a pinned-producer case of `test_native_program.py`</fails_when>
<automated>python3 -B deployment/checks.py --group units-native</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group fuel-native-provenance</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group guard</automated>
<fails_when>exit status is non-zero (a durable-fixture pin or manifest check)</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, every other group on the binding window list passes and is listed with its counts, and the checkpoint `phases/04-documents/checkpoints/4.37b.md` (old and new pins and capture identities, the window closed) is verified by the orchestrating session.</done>

</task>

### Task 4.38 — Frozen history with cited sources (blocked by OQ-1)

<task type="auto" id="4.38">

<name>Task 4.38 — Frozen history with cited sources (blocked by OQ-1)</name>

<files>

- `application/src/hyprn_mvp_app/history.py` and `application/src/hyprn_mvp_app/modified_runs.py` (cited sources; capability questions instead of version literals), the runs route module that checkpoint 3.3a names (history read unions), `application/generate_contract.py`, the regenerated contract and types;
- create `application/tests/test_documents_frozen_history.py`, `deployment/groups/documents/documents-frozen-history.json` (mode `native`).

</files>

<read_first>

- `contracts/documents.md` (`history`, `modified_runs` rows; `RunHistory` and `ModifiedRunSeed` notes); D-13; `application/src/hyprn_mvp_app/history.py` (`read`, `retained_read_integrity`, `stored_family`), `modified_runs.py` (its version literals); the version-family capability table in `execution_bundle.py` (from 4.37); `application/tests/test_history_reuse.py`

</read_first>

<action>

- **Goal:** an old run opens with its exact cited sources from stored records alone, during a modeling-service outage and with document storage down, and a modified-run seed keeps the exact citation pins (D-06, D-13; step 12, RUN-02); the history and seed readers ask version families for capabilities (D-18).
- **Depends on:** 4.37b (the window closed), 4.19. **Blocked by:** OQ-1. **Parallel:** any Phase 2 task; not beside a Phase 3 task that edits `history.py` (3.3c), the runs route module or the generator; blocked lane position 6 (one lane task at a time); not beside 4.24 or 4.25 (see "Blocked lane").
- **Steps:**
  1. Before any edit, record the counts of `units-history`, `approach-history`, `ae-history`, `modified` and `projection`; `history.py` and `modified_runs.py` replace their literal version comparisons with capability questions; rerun those groups: identical counts before the new history and seed versions are added.
  2. Choose the history version from the actual frozen and bundle families; keep null or unverified fields and honest read errors; never contact the modeling service.
  3. Cited sources come from the stored evidence snapshots (descriptors, quotations, annotation snapshots); byte availability comes from the read loop and reads "unavailable" when it does not answer; nothing substitutes the current head.
  4. Modified-run seeds keep the exact configuration, evidence and approach pins until an explicit previewed change.
- **Risks:** a silent fall-back to current content (tests change source, extraction and annotation first); a capability question answering differently for a historical record (step 1's before and after counts).

</action>

<acceptance_criteria>

- `test_documents_frozen_history_*` pass: a run's history read is identical before and after a new source version, a re-extraction and an annotation edit; with the modeling double stopped the read succeeds with no modeling call; with the read loop stopped descriptors and quotations show and bytes read "unavailable".
- The groups of step 1 give the same counts after the capability move as before it (table in the checkpoint).
- `units-history`, `approach-history`, `ae-history` and `modified` pass.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-frozen-history</automated>
<fails_when>exit status is non-zero, including any modeling call or a current-content substitution</fails_when>
<automated>python3 -B deployment/checks.py --group ae-history</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-history</automated>
<fails_when>exit status is non-zero, or its count differs from step 1's record</fails_when>
<automated>python3 -B deployment/checks.py --group modified</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.38.md` (the before and after table of step 1) is verified by the orchestrating session.</done>

</task>

### Task 4.39 — Citation paths 2–4 and run evidence in the UI (blocked by OQ-1)

<task type="auto" id="4.39">

<name>Task 4.39 — Citation paths 2–4 and run evidence in the UI (blocked by OQ-1)</name>

<files>

- `ui/src/ConfigurationPanel.tsx`, `ui/src/ApproachAssumptions.tsx`, `ui/src/RunPanel.tsx`, `ui/src/recordViews.ts`, `ui/src/EvidencePicker.tsx` (lift the omission for the admitted pairings), `ui/src/api.ts`, `ui/control-map.json`;
- create `ui/tests/documents-history.spec.ts`, `deployment/groups/documents/documents-history-ui.json` (mode `browser-native`).

</files>

<read_first>

- `04-UI-SPEC.md` S6 (paths 2–4), S7, Q12; `docs/specs/documents.md` §15.4; the UI files above; `ui/tests/documents-cite.spec.ts`

</read_first>

<action>

- **Goal:** citations reach the exact source from a configuration's context, inputs, criteria and assumptions (path 2), from the modeling approach (path 3) and from a run's model, configuration and evidence tabs (path 4), from stored snapshots only (D-08, D-10; step 13, HUM-06, RUN-02).
- **Depends on:** 4.38, 4.29. **Blocked by:** OQ-1. **Parallel:** any Phase 2 task; no Phase 3 task; blocked lane position 7 (one lane task at a time); every Phase 4 task sharing its files is among its dependencies.
- **Steps:**
  1. Attach lists for configurations and approach items admit evidence that cites documents for the pairings D-13 admits.
  2. Each path opens the shared View evidence dialog and "Read cited source" into the cited-source view with the return label of its origin; run and saved-configuration views never fetch today's library (no-live-fetch guard).
  3. Evidence: paths 2–4 in light and dark, keyboard-only, genuine 200 % zoom, including the modeling-service outage state; these states are also rows of the cross-screen sweep in task 4.40, which runs after this task.
- **Risks:** regressions in configuration, approach and run views (their browser groups run unchanged).

</action>

<acceptance_criteria>

- `@documents-history-ui` tests pass: paths 2, 3 and 4 open the cited version and range after source, extraction and annotation changes and during a modeling outage.
- `ae-ui-configuration`, `approach-ui-assumptions`, `units-ui-history` and `combined-static` pass.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-history-ui</automated>
<fails_when>exit status is non-zero, `environment absent` is printed, or a spec test fails or is skipped</fails_when>
<automated>python3 -B deployment/checks.py --group ae-ui-configuration</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group approach-ui-assumptions</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero, including the no-live-fetch guard on run evidence</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.39.md` is verified by the orchestrating session.</done>

</task>

### Task 4.40 — Documents screens: themes, keyboard and genuine 200 % zoom sweep

<task type="auto" id="4.40">

<name>Task 4.40 — Documents screens: themes, keyboard and genuine 200 % zoom sweep</name>

<precondition>Tasks 4.29, 4.31, 4.32, 4.33 and 4.39 are each verified, or `04-CONTEXT.md` records the product owner's decision that the task leaves this phase.</precondition>

<files>

- create `ui/tests/documents-zoom.spec.ts` (a state table covering S1–S7 and the blocked tasks' states), `deployment/groups/documents/documents-ui-zoom.json` (mode `browser-native`).

</files>

<read_first>

- `04-UI-SPEC.md` "Keyboard, focus, themes and zoom", "UI Considerations", S3 ("Replace version"), S1 (Uploads panel), S6 (paths 2–4), S7; `ui/tests/foundry-zoom.spec.ts`; every `ui/tests/documents-*.spec.ts`
- `04-CONTEXT.md` D-13, D-15, D-16, D-17 and any scope decision for tasks 4.31, 4.32, 4.33 or 4.39

</read_first>

<action>

- **Goal:** one sweep, run after the last Documents UI task, proves every delivered Documents screen and state in both themes, by keyboard and at genuine 200 % zoom, including the states the blocked tasks deliver (success criterion 5; D-10).
- **Depends on:** 4.29, 4.31, 4.32, 4.33 and 4.39, each verified or recorded out of this phase by the product owner (see the precondition). No Documents UI task runs after this one; if a task recorded out of this phase is later brought back, 4.40 runs again after it. **Parallel:** any Phase 2 or Phase 3 task (new files only).
- **Steps:**
  1. A state table lists S1–S7 and each state family; for each, light and dark at a native 1440 × 1000 window with genuine 200 % browser zoom (the `foundry-zoom.spec.ts` Chromium pattern, never viewport emulation): no page-wide horizontal scroll; every focusable control shows its focus outline; "Upload documents", dialog commit buttons, "Download original" and the cite actions are reachable and unobstructed; the keyboard tab order matches UI-SPEC.
  2. The table has rows for each verified blocked UI task: the S3 "Replace version" dialog (4.31); uploads listed after a reload with their notices and "Continue upload" (4.32); the archived-study line with write actions absent (4.33, option a only); citation paths 2–4 from configuration, approach and run, and the cited-source view during a modeling-service outage (4.39). A task recorded out of this phase is an excluded row naming its decision line, so the comparison with UI-SPEC's state vocabulary stays exhaustive.
  3. Screenshots go to `HYPRN_MVP_UI_EVIDENCE_ROOT` as `documents-zoom-<screen>-<state>-<theme>.png`; the checkpoint lists them for the product owner.
- **Risks:** a state missing from the table (the table is compared with the state vocabulary in UI-SPEC by a spec assertion).

</action>

<acceptance_criteria>

- `@documents-ui-zoom` passes for every row; the table covers every state family of UI-SPEC's state vocabulary for delivered slices, including the rows of 4.31, 4.32, 4.33 (option a) and 4.39, or their excluded rows.
- `combined-static` and `foundry-nav` pass.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group documents-ui-zoom</automated>
<fails_when>exit status is non-zero, or a row reports page-wide horizontal scroll, an invisible focus or an unreachable control, or a state family of a verified task has neither a row nor an excluded row</fails_when>
<automated>python3 -B deployment/checks.py --group foundry-nav</automated>
<fails_when>exit status is non-zero</fails_when>
<automated>python3 -B deployment/checks.py --group combined-static</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, and the checkpoint `phases/04-documents/checkpoints/4.40.md` (screenshot index) is verified by the orchestrating session.</done>

</task>

### Task 4.41 — Phase acceptance

<task type="auto" id="4.41">

<name>Task 4.41 — Phase acceptance</name>

<precondition>Tasks 4.1–4.40 are verified (4.4a, 4.9a, 4.9b, 4.22a and 4.37b included), including the blocked tasks once answered; Phase 2 task 2.11 is verified. A task still blocked keeps the phase open unless the product owner records a scope decision.</precondition>

<files>

- `docs/specs/documents.md` (§12 implementation status for steps 1–13), `docs/specs/requirements.md` (notes of DOC-01, HUM-06 and RUN-02; DOC-01 stays `partial` per PD-4.1).

</files>

<read_first>

- `04-CONTEXT.md` "Acceptance (phase level)"; `ROADMAP.md` Phase 4 success criteria; every checkpoint in `phases/04-documents/checkpoints/`; `docs/specs/documents.md` §12; `docs/specs/requirements.md`

</read_first>

<action>

- **Goal:** prove the phase on the committed tree and record the product owner's acceptance separately from automated evidence (D-10, PD-4.8).
- **Depends on:** every other task. **Parallel:** none.
- **Steps:**
  1. Run `CHECK qualification` (every must-pass group, including the Documents groups of this phase) and `CHECK documents-served` on a scratch installation; record each group's counts and timings.
  2. Prepare the walk-through script and the evidence index (screenshots under `HYPRN_MVP_UI_EVIDENCE_ROOT`, timelines, canary report).
  3. **Blocking human checkpoint, never auto-approved:** the product owner walks through: upload and reopen an original; organize two collections; search, read and annotate; create and attach an exact citation; change the source, the annotation and the extraction, then reopen an old run (also with the modeling service down); try a failed extraction; review light, dark, keyboard and 200 % screens. The answer is recorded in the checkpoint, separately from the automated evidence.
  4. After approval: `docs/specs/documents.md` §12 marks steps 1–13 delivered (with any open decision named); `docs/specs/requirements.md` notes what DOC-01, HUM-06 and RUN-02 gained; `documents` stays in `capabilities.unavailable` (PD-4.8 is a Phase 5 action).
- **Risks:** a long qualification run (sequential; timings recorded).

</action>

<acceptance_criteria>

- `CHECK qualification` exits 0 with no group reported as environment absent; `CHECK documents-served` exits 0.
- The checkpoint holds the product owner's walk-through answer with date, separate from the automated evidence list.
- `GET /api/1/capabilities` on the scratch installation lists `documents` in `unavailable` and all seven slices in `document_slices`.

</acceptance_criteria>

<verify>
<automated>python3 -B deployment/checks.py --group qualification</automated>
<fails_when>exit status is non-zero or any group prints `environment absent`</fails_when>
<automated>python3 -B deployment/checks.py --group documents-served</automated>
<fails_when>exit status is non-zero</fails_when>
</verify>

<done>Every acceptance check above passes on the committed tree, the product owner's acceptance is recorded, and the checkpoint `phases/04-documents/checkpoints/4.41.md` is verified by the orchestrating session.</done>

</task>

## Artifacts this phase produces


### Application (`application/src/hyprn_mvp_app/`)

| Artifact | Contents | Task |
|---|---|---|
| `documents.py` (new) | `DOCUMENT_LIMITS`, `DOCUMENT_SLICES`; class `Documents`: `begin_upload`, `put_chunk`, `complete_upload`, `upload_status`, `version`, `original`, `next_write`, `apply_write_reply`, library reads, metadata and archive commands, collection, annotation, extraction-attempt and usage operations, the writable-study check | 4.1, 4.9a, 4.9b, 4.14, 4.17, 4.22, 4.24, 4.33 |
| `routes/documents.py` (new) | `router(deps) -> APIRouter` holding every Documents route; composed by `api.py`, which keeps only the edge and the chunk-route body exemption | 4.1, 4.9a, 4.14, 4.17, 4.20, 4.22, 4.24, 4.25, 4.32 |
| `document_bridge.py` (new) | `READ_VERBS`, `WRITE_VERBS`, `documents_once`, `reads_once`, the `--reads` entry | 4.1, 4.8, 4.14, 4.17, 4.21 |
| `document_citations.py` (new) | `resolve_candidate`, `freeze_citation`, `page_inventory`, `resolve_span`, `DOCUMENT_UNTRUSTED_FIELDS` | 4.20, 4.27 |
| `document_search.py` (new) | projection build and rebuild, length-preserving fold, `search`, coverage, signed cursors | 4.25 |
| `dispatcher.py` | bridge method `document_write`; `documents_once` per serve iteration | 4.1 |
| `store.py` tables | `document_families`, `document_versions`, `document_uploads`, `document_operations`, `document_associations`, `document_read_requests`, collection and annotation associations, `document_extraction_attempts`, search projection, `document_source_reservations`, Evidence4 rows with immutability triggers; the document categories' rows in the server-decided recovery table (Phase 3 task 3.3d) | 4.1, 4.9b, 4.14, 4.17, 4.20, 4.24, 4.25 |
| Other owners' route modules (from Phase 3 task 3.3a) | evidence create and revise admit 4; model assumption-evidence resolution 2; configuration and approach accept the chain versions; run history read unions; receipts with document categories; capabilities with `document_slices` | 4.9a, 4.9b, 4.20, 4.22, 4.24, 4.35, 4.38 |
| `modeling.py` | `AssumptionEvidenceResolution2` with `EvidenceRecordRead4` | 4.22 |
| `execution_bundle.py` | version-family capability table: `family(record).has(capability)` with `carries_dependencies`, `typed_units`, `polish_envelope`, `approach_closure`, `document_citations`; reproduces `RETAINED_PAIRINGS`; added inside the re-attesting task | 4.37 |
| `configuration.py`, `scientific_configuration.py`, `approach.py`, `approach_closure.py`, `result_bindings.py`, `execution.py`, `history.py`, `modified_runs.py`, `computational_export.py` | Evidence4 boundary, then the document-bearing chain per D-13 (4.35 admits its versions with explicit checks); capability questions instead of version literals in `configuration`, `approach`, `execution`, `computational_export` (4.37) and `history`, `modified_runs` (4.38) | 4.22, 4.35, 4.37, 4.38 |

### Public routes (paths under `/api/1/studies/{study_id}/`)

| Slice | Routes | Task |
|---|---|---|
| `documents_library/1` | `POST document-uploads`; `PUT document-uploads/{upload_id}/chunks/{offset}`; `POST document-uploads/{upload_id}/complete`; `GET document-uploads/{upload_id}`; `GET document-operations/{operation_id}`; `GET documents`; `GET documents/{document_id}`; `GET documents/{document_id}/versions`; `GET document-versions/{version_id}`; `GET document-versions/{version_id}/original`; `PATCH documents/{document_id}`; `POST documents/{document_id}/archive`; `POST documents/{document_id}/unarchive`; (OQ-5) `GET document-uploads` | 4.1, 4.9a, 4.32 |
| `documents_collections/1` | `POST/GET document-collections`; `GET/PATCH/DELETE document-collections/{collection_id}`; `GET/POST document-collections/{collection_id}/members` | 4.14 |
| `documents_annotations/1` | `GET/POST document-versions/{version_id}/annotations`; `GET/PATCH/DELETE document-versions/{version_id}/annotations/{annotation_id}` | 4.17 |
| `documents_citations/1` | `POST document-citations/preview`; `POST evidence-citations/preview`; evidence create and revise admit `EvidenceCreate4` and `EvidenceRevise4` | 4.20 |
| `documents_usage/1` | `GET document-versions/{version_id}/usage`; `GET models/{model_id}/assumption-evidence` returns resolution 2 when needed | 4.22 |
| `documents_extraction/1` | `POST/GET document-versions/{version_id}/extractions`; `GET document-extractions/{attempt_id}`; `GET document-extractions/{attempt_id}/result`; `POST document-extractions/{attempt_id}/retry`; `GET document-versions/{version_id}/fragments` | 4.24 |
| `documents_search/1` | `GET document-search` | 4.25 |
| — | `GET commands/{command_id}?category=document_*` (receipts with the server-decided `recovery`, 4.9b); `GET /api/1/capabilities` gains `document_slices` (4.9a) | 4.9a, 4.9b |

### Integration (`integration/`)

| Artifact | Contents | Task |
|---|---|---|
| `src/hyprn_mvp_integration/documents.py` | `collection_create`, `collection_update`, `collection_members`, `collection_delete`, `collection`, `collections`, `members`; `annotation_create`, `annotation_revise`, `annotation_delete`, `annotation`, `annotations`; `extraction_start`, `attempt`, `extraction_result`, `fragment`; generalized `reconcile`; injectable `fault` | 4.7, 4.12, 4.21, 4.31 |
| `src/hyprn_mvp_integration/document_extraction.py` (new) | `extract_document` calcfunction | 4.21 |
| `src/hyprn_mvp_integration/document_parser.py` (new) | in-image entry and canary cases | 4.15, 4.18 |
| `src/hyprn_mvp_integration/document_parser_launch.py` (new) | `launch_parser`, `reap_parser_containers`, `attest_parser`, `require_parser_containment` | 4.18 |
| `document-parser-policy.json` (new) | reviewed parser limits | 4.18 |
| `document-parser.lock.json`, `document-parser-provenance.md` | chosen wheel per D-14 | 4.6 |
| `results.py`, `calculation.py`, `worker.py`, `launcher.py` | document-bearing bundle admission (the worker keeps its own version table); one re-attestation for the chain | 4.37 |

### Deployment, edition and modeling

| Artifact | Contents | Task |
|---|---|---|
| `deployment/document_native_runtime.py` (new) | `handle_write`, `handle_read`, the `--reads` process | 4.1, 4.8, 4.14, 4.17, 4.21 |
| `deployment/group_registry.py` (new), `deployment/groups/<family>/*.json` (new, one per group) | the loader of every test group's entry (closed schema: `group`, `rank`, `class`, `needs`, `interpreter`, `runner`, `targets` and runner-specific keys); the derived sets of `deployment/checks.py` | 4.4 (every group present), then one entry file per later group |
| `deployment/documents_groups.py` (new), `deployment/groups/documents/*.json` | Documents runner modes `application/contracts`, `native`, `browser`, `browser-native`, `served`, `modeling`; test selection; validators `collection_protocol`, `read_loop_timeline`, `parser_canaries` | 4.4, 4.8, 4.18, 4.30, 4.36 |
| `deployment/tests/browser_harness.py` (new) | `serve(scope, app, *, dist, writable, controls, body_cap)`, `run_playwright(scope, *, tag, config_base, evidence)`; every scoped browser fixture on it | 4.4a |
| `deployment/tests/documents_ui_fixture.py` | `start_isolated_api` and `run` on the harness; seeded states and controls | 4.4a, 4.13, 4.26 |
| `deployment/images/parser.Dockerfile`, `deployment/parser_image.py` (new) | `acquire_wheel`, offline build, runtime record; tag `hyprn-mvp-parser:<build-input-digest16>`; labels `org.hyprn-mvp.parser*` | 4.15 |
| `deployment/local_paths.py` | `HYPRN_MVP_PARSER_CACHE` (default `<data root>/cache/parser`) | 4.15 |
| `deployment/dispatch_runtime.py`, `deployment/release.py` | `document_write` routing; supervised read pair; binding path | 4.19 |
| `deployment/pins.json` (`modeling_producer`), `integration/tests/fixtures/native-programs.json.gz`, the durable native fixture pins in `deployment/tests/durable_fixture.py` | producer re-pin and native fixture recapture after the chain's single re-attestation; closes the stale-attestation window | 4.37b |
| `editions/local/src/hyprn_mvp_local/setup.py`, `doctor.py`, `status.py` | parser image and containment at setup; read-only reporting | 4.30 |
| `contracts/modeling.openapi.yaml`, `upstream/whatsopt-patches/100-document-citations.patch` | private projection admission (AGPL scope) | 4.36 |
| `contracts/documents.md` | `replace` wording (no schema change); recent-uploads route row; chain pairings and consumers | 4.31, 4.32, 4.34 |
| `contracts/schemas/documents.schema.json` (non-attested, from Phase 2 task 2.8), `contracts/schemas/model.schema.json` (chain definitions per the approved split), the generated `contracts/schemas/execution.schema.json` | recent-uploads definitions; chain amendment; the execution schema regenerated only inside the 4.37 re-attestation | 4.32, 4.34, 4.37 |
| `docs/legal/licensing.md`, `THIRD_PARTY_NOTICES.md` | parser adopted in its image; notice bundle | 4.6, 4.15 |
| `docs/specs/documents.md`, `docs/specs/requirements.md`, `docs/specs/ui-target.md` | §12 status, §18 Q4, requirement notes; §7 access-loss residuals resolved | 4.22a, 4.33, 4.41 |

Runtime locations (never in the repository, all below the installation's data root, D-11): the upload spool `document-spool/` in the application store folder; the parser cache; the parser scratch `<execution root>/parser-scratch/<attempt>`; the read-process lock `<execution root>/locks/document-reads.lock`; containment evidence and runtime records in the execution root's evidence folder.

### Design system and UI

| Artifact | Contents | Task |
|---|---|---|
| `design-system/Layouts.md`, `Naming.md`, `components/Tabs.md`, `docs/specs/ui-target.md` | Documents tab and section; reader-facing names | 4.5 |
| `Notice` (`ui/src/design/components.tsx`, `components/Notice.md`); measured `Progress` (`primitives.tsx`, `components/Progress.md`); `ui/src/documents.css` | A3, A4, A7 | 4.5 |
| `TextReader` (`ui/src/design/reader.tsx`, `components/TextReader.md`); `CitationRecord` (`primitives.tsx`, `components/CitationRecord.md`) | A5, A6 | 4.10 |
| `ui/src/views/documents.tsx`, `ui/src/views/documentReader.tsx`, `ui/src/views/citedSource.tsx` (new view modules; names follow the convention of the modules Phase 3 task 3.3b creates) and their entries in `ui/src/views/registry.ts` | the Documents library, reader and cited-source views: `parseLink`, `render`, `guard`, `available(capabilities)` per slice | 4.13, 4.16, 4.26, 4.29 |
| `ui/src/DocumentsLibrary.tsx`, `DocumentUpload.tsx`, `DocumentVersions.tsx`, `documentFormat.ts` | S1, S2 | 4.13 |
| `ui/src/DocumentCollections.tsx` | S3 | 4.16, 4.31 |
| `ui/src/DocumentCitationDialog.tsx`; evidence editor and View evidence citations | S5 (editor), S6 | 4.23, 4.29 |
| Evidence view, picker and library, assumption list, model and unit editors, configuration-editor reads, study-shell lists | on the shared access-loss seam (`useAccessLoss`, `api.readFailed`, `accessDenied`); `evidenceAccessLost` removed | 4.22a |
| `ui/src/DocumentReader.tsx`, `DocumentSearch.tsx` | S4 text column, search | 4.26 |
| `ui/src/DocumentAnnotations.tsx`, `DocumentUsage.tsx`, `documentOffsets.ts` | S4 side column | 4.28 |
| `ui/src/DocumentCite.tsx`; cited-source view | S5 (reader), S7 | 4.29 |
| `ui/src/api.ts` (`putChunk`, `downloadOriginal`, document command categories reading `recovery`), `ui/control-map.json`, `ui/playwright.documents.config.ts`; `ui/src/Workspace.tsx` only for view-independent shell behaviour | client, contract checker, browser config, shell | 4.4a, 4.13–4.39 |

### Test groups

Every group below is one entry file under `deployment/groups/documents/` (after task 4.4; `documents-upload-api` is migrated by 4.4).

| Group | Mode | Target | Task |
|---|---|---|---|
| `documents-upload-api` | native | `application/tests/test_documents_upload_api.py` | 4.1, 4.9b |
| `documents-registry` | application/contracts | `deployment/tests/test_documents_registry.py` | 4.4 |
| `documents-isolated-api` | browser-native | `ui/tests/documents-isolated-api.spec.ts` | 4.4a |
| `documents-collections` | native, measured | `integration/tests/test_documents_collections.py` | 4.7 |
| `documents-bridge` | native | `application/tests/test_documents_bridge.py` | 4.8 |
| `documents-read-loop` | native, measured | `integration/tests/test_documents_read_loop.py` | 4.8 |
| `documents-library-api` | native | `application/tests/test_documents_library_api.py` | 4.9a |
| `documents-access` | native | `application/tests/test_documents_access.py` | 4.9b |
| `documents-annotations` | native, measured | `integration/tests/test_documents_annotations.py` | 4.12 |
| `documents-library-ui` | browser-native | `ui/tests/documents-library.spec.ts` | 4.13 |
| `documents-collections-api` | native | `application/tests/test_documents_collections_api.py` | 4.14 |
| `documents-parser-image` | native | `integration/tests/test_documents_parser_image.py` | 4.15 |
| `documents-collections-ui` | browser-native | `ui/tests/documents-collections.spec.ts` | 4.16 |
| `documents-annotations-api` | native | `application/tests/test_documents_annotations_api.py` | 4.17 |
| `documents-parser-containment` | native, measured | `integration/tests/test_documents_parser_containment.py` | 4.18 |
| `documents-supervision` | native | `deployment/tests/test_documents_supervision.py` | 4.19 |
| `documents-citations`, `documents-evidence-v4` | native | `application/tests/test_documents_citations.py`, `test_documents_evidence_v4.py` | 4.20 |
| `documents-extraction` | native | `integration/tests/test_documents_extraction.py` | 4.21 |
| `documents-usage` | native | `application/tests/test_documents_usage.py` | 4.22 |
| `documents-evidence-ui` | browser-native | `ui/tests/documents-evidence.spec.ts` | 4.23 |
| `documents-extraction-api` | native | `application/tests/test_documents_extraction_api.py` | 4.24 |
| `documents-search`, `documents-extraction-provenance` | native | `application/tests/test_documents_search.py`, `integration/tests/test_documents_extraction_provenance.py` | 4.25 |
| `documents-reader-ui` | browser-native | `ui/tests/documents-reader.spec.ts` | 4.26 |
| `documents-citation-spans` | native | `application/tests/test_documents_citation_spans.py` | 4.27 |
| `documents-annotations-ui` | browser-native | `ui/tests/documents-annotations.spec.ts` | 4.28 |
| `documents-cite-ui` | browser-native | `ui/tests/documents-cite.spec.ts` | 4.29 |
| `documents-served` | served (opt-in) | `deployment/tests/test_documents_served.py` | 4.30 |
| `documents-upload-recovery` | native | `application/tests/test_documents_upload_recovery.py` | 4.32 |
| `documents-archived-study` | native | `application/tests/test_documents_archived_study.py` | 4.33 |
| `documents-chain-contracts` | application/contracts | `contracts/tests/test_documents_contract.py` | 4.34 |
| `documents-configuration-chain` | application/contracts | `application/tests/test_documents_configuration_chain.py` | 4.35 |
| `documents-modeling-private` | modeling | `modeling/tests/test_documents_private_projection.py` | 4.36 |
| `documents-bundle-admission` | native | `integration/tests/test_documents_bundle_admission.py` | 4.37 |
| `documents-frozen-history` | native | `application/tests/test_documents_frozen_history.py` | 4.38 |
| `documents-history-ui` | browser-native | `ui/tests/documents-history.spec.ts` | 4.39 |
| `documents-ui-zoom` | browser-native | `ui/tests/documents-zoom.spec.ts` | 4.40 |

## Source coverage audit

| Source | Item | Covered by |
|---|---|---|
| GOAL | Upload, organize, read, search, annotate, cite, reopen an old run with its cited source | 4.1–4.41 |
| REQ | DOC-01 (stays `partial`, PD-4.1) | 4.1, 4.4–4.33, 4.40, 4.41 |
| REQ | HUM-06 (document citations at declared scopes) | 4.20, 4.22, 4.23, 4.27, 4.29, 4.39 |
| REQ | RUN-02 (cited document passages in old runs, also during a modeling outage) | 4.34–4.39 |
| RESEARCH | Step map 1–13 | 1: 4.7, 4.12 · 2: 4.1, 4.8, 4.19 · 3: 4.1, 4.9a, 4.9b · 4: 4.13, 4.32 · 5: 4.14, 4.16, 4.31 · 6: 4.15, 4.18, 4.30 · 7: 4.21, 4.24 · 8: 4.25 · 9: 4.26 · 10: 4.17, 4.20, 4.22, 4.27, 4.28 · 11: 4.34–4.37 · 12: 4.38 · 13: 4.23, 4.29, 4.39 |
| RESEARCH | Pitfalls 1–12 | 1: 4.3, 4.34 · 2: 4.1 · 3: 4.8, 4.19 · 4: 4.8 · 5: 4.7, 4.12 · 6: 4.7 · 7: 4.37, 4.37b · 8: 4.4 · 9: 4.18 · 10: 4.10, 4.27, 4.28 · 11: 4.25, 4.27 · 12: 4.20 |
| RESEARCH | Wave 0 gaps | browser-native mode and validators 4.4, 4.8, 4.18; isolated API 4.4a; production-adapter probes 4.7; run-time fixtures 4.18; module boundaries in 4.1, 4.20, 4.25 |
| RESEARCH | Package legitimacy (pypdf flagged) | 4.2, 4.6, 4.11 |
| RESEARCH | Open questions 1–9 (each marked DEFERRED, RESOLVED or OUT OF SCOPE in `04-RESEARCH.md`) | OQ-1 4.3, then 4.34–4.39; OQ-2 4.2; OQ-3 4.31; OQ-4 4.33; OQ-5 slices 4.9a; OQ-6 copy 4.5; OQ-7 4.35, 4.36; OQ-8 cursor key 4.9a; OQ-9 out of scope |
| CONTEXT | D-01 … D-12 | D-01 4.1, 4.7, 4.12, 4.21, 4.25 · D-02 4.1, 4.9a, 4.9b, 4.14, 4.17, 4.20, 4.22a, 4.24, 4.25 · D-03 4.1, 4.7, 4.9a, 4.9b, 4.12, 4.13 · D-04 4.7, 4.14, 4.31 · D-05 4.6, 4.15, 4.18, 4.21, 4.30 · D-06 4.20, 4.22, 4.27, 4.29, 4.34–4.38 · D-07 4.1, 4.9a, 4.9b, 4.18 · D-08 4.5, 4.10, 4.13, 4.16, 4.23, 4.26, 4.28, 4.29, 4.39 · D-09 4.1, 4.8, 4.19, 4.30 · D-10 every UI task, 4.4, 4.4a, 4.40, 4.41 · D-11 4.1, 4.15, 4.18, 4.30 · D-12 4.9b, 4.15, 4.18 and the threat register |
| CONTEXT | D-18 (factorization schedule) | 4.1, 4.4, 4.4a, 4.9b, 4.13, 4.22a, 4.23, 4.26, 4.29, 4.32, 4.34, 4.35, 4.37, 4.37b, 4.38 (rows below) |
| CONTEXT | PD-4.1 … PD-4.8 | "Decisions and defaults applied"; PD-4.3 through OQ-4 (4.33); PD-4.8 in 4.9a and 4.41 |
| CONTEXT | Phase acceptance and threats | 4.41; threat register below |
| FACTORIZATION | Item 2: server-decided recovery on receipts | Phase 3 task 3.3d (prerequisite of 4.9b); 4.9b declares the document categories' rows, 4.14, 4.17, 4.24 add theirs; 4.13 reads `recovery` |
| FACTORIZATION | Item 3: one browser-fixture harness | 4.4a |
| FACTORIZATION | Item 5: declarative registry for every test group | 4.4 |
| FACTORIZATION | Item 8: per-owner API routers | Phase 3 task 3.3a (prerequisite of 4.1); 4.1 creates `routes/documents.py`; 4.9a, 4.9b, 4.14, 4.17, 4.20, 4.22, 4.24, 4.25, 4.32, 4.35, 4.38 edit `routes/documents.py` or the owner's route module |
| FACTORIZATION | Item 9: study-shell view registry | Phase 3 task 3.3b (prerequisite of 4.13); 4.13, 4.26, 4.29 add their view modules; 4.16 extends the library view's links |
| FACTORIZATION | Item 10: remaining hosts on the access-loss seam | 4.22a (before the citation UI of 4.23) |
| FACTORIZATION | Item 11: contract schemas split by consumer | Phase 2 task 2.8c, completed and re-attested by 2.8 (2.8 is the prerequisite of 4.32, 4.34, 4.37); 4.32, 4.34 edit `contracts/schemas/documents.schema.json`; 4.37 regenerates the execution schema inside its re-attestation |
| FACTORIZATION | Item 12: version-family capabilities | 4.37–4.38: 4.37 (the table, inside the one re-attestation; `configuration`, `approach`, `execution`, `computational_export`, replacing 4.35's explicit checks; the bundle and frozen families), 4.38 (`history`, `modified_runs`) |
| FACTORIZATION | Items 13 and 14 | after the first release ("Deferred work") |
| FACTORIZATION | Items 1, 4, 6, 7 | other phases: Phase 1 task 1.11 (item 1; 4.4 keeps its guard working off the registry), Phase 3 tasks 3.3c (item 4) and 3.4 (item 6), Phase 2 task 2.8b (item 7) |

Not planned, by decision: steps 14–18, agent document tools and upload, OCR, rendered pages, ranking, authored documents, cloud requalification (CONTEXT "Deferred Ideas"); a document-aware computational record export belongs with portable export (PD-4.1, task 4.37 refuses it explicitly).

## Deferred work

- **Outbox history projection made explicit and rebuildable** (FACTORIZATION.md item 13): after the first release.
- **Authorization by effect instead of boolean flags** (FACTORIZATION.md item 14): after the first release.
- Already out of this phase: steps 14–18 and the other items under "Not planned, by decision" above (PD-4.1, CONTEXT "Deferred Ideas"), and the open product decisions listed in `04-CONTEXT.md`.

## Validation map

| Success criterion / decision | Tasks | Groups |
|---|---|---|
| 1. Collections share originals; stale edits change nothing; deletion terminal and replay-safe | 4.7, 4.14, 4.16 | `documents-collections`, `documents-collections-api`, `documents-collections-ui` |
| 2. Upload → published version → exact bytes after restart; every recovery state visible | 4.1, 4.9a, 4.9b, 4.13, 4.19, 4.30, 4.32 | `documents-upload-api`, `documents-library-api`, `documents-library-ui`, `documents-supervision`, `documents-served`, `documents-upload-recovery` |
| 3. A search hit opens the exact passage with honest coverage | 4.21, 4.24, 4.25, 4.26 | `documents-extraction`, `documents-extraction-api`, `documents-search`, `documents-reader-ui` |
| 4. Citations freeze exact source and quotation; old runs show it during an outage | 4.20, 4.27, 4.29, 4.34–4.39 | `documents-citations`, `documents-evidence-v4`, `documents-citation-spans`, `documents-cite-ui`, `documents-frozen-history`, `documents-history-ui` |
| 5. Keyboard, light and dark, genuine 200 %; design-system only | 4.5, 4.10, 4.13, 4.16, 4.23, 4.26, 4.28, 4.29, 4.31, 4.32, 4.33, 4.39, 4.40 (after every other UI task, so its sweep includes the blocked tasks' states) | `documents-ui-zoom`, every `*-ui` group, `combined-static`, design checks |
| D-02 study scope | 4.1, 4.9b and every API task | `documents-access` |
| D-03 recovery from the owner's receipt | 4.9b (with Phase 3 task 3.3d), 4.13, 4.14, 4.17, 4.24 | `documents-upload-api`, `documents-library-ui` |
| D-05 containment | 4.15, 4.18, 4.30 | `documents-parser-image`, `documents-parser-containment` |
| D-09 responsiveness | 4.8, 4.19 | `documents-read-loop`, `documents-supervision` |
| Stale-attestation window opened, measured and closed | 4.34, 4.36, 4.37, 4.37b | the binding window list of checkpoints 4.34 and 4.36; `findings-native-read`, `units-worker`, `units-native` passing again in 4.37b |
| D-18 group registry: one entry per group, `--list` and pass counts unchanged | 4.4 | `documents-registry`, `guard`, `qualification` before and after |
| D-18 browser-fixture harness: every migrated group keeps its counts | 4.4a | `documents-isolated-api`, `guard`, `units-guards`, `findings-native-guards`, the migrated browser and native-journey groups before and after |
| D-18 access loss through one seam | 4.22a | `ae-ui-evidence`, `ae-ui-model`, `ae-ui-configuration`, `units-ui-authoring`, `units-ui-configuration`, `approach-ui-controller`, `approach-ui-reading`, `approach-ui-configuration`, `approach-ui-history`, `ui-c`, `ui-reading`, `combined-static` |
| D-18 version-family capabilities: historical reads accept the same records | 4.37–4.38 | `locality-contracts` (golden corpus, capability property tests), `units-history`, `approach-history`, `ae-history`, `ae-export`, `modified`, `units-attestation` |

The per-task commands are listed in `04-VALIDATION.md` "Per-Task Verification Map".

## Parallel work

- **Shared files, edited by one task at a time across Phases 2, 3 and 4:** `application/src/hyprn_mvp_app/api.py` (composition only after Phase 3 task 3.3a; in this phase only 4.1 edits it) and each per-owner route module `application/src/hyprn_mvp_app/routes/<owner>.py` (`routes/documents.py` is created by 4.1 and edited only by Phase 4 tasks; the evidence, model, configuration, approach, runs, receipts and capabilities route modules are shared); `application/src/hyprn_mvp_app/store.py`; `application/tests/test_module_boundaries.py` (exactly 2.3, 2.8b, 2.8c, 3.3a, 3.3c, 3.4, 4.1, 4.20, 4.25, 4.37); `contracts/hyprn-mvp.openapi.yaml` + `ui/src/contract.ts` + `application/generate_contract.py`; `contracts/schemas/*.json` (after Phase 2 task 2.8, Documents-only definitions and the registry live in the non-attested `contracts/schemas/documents.schema.json`, the shared citation vocabulary and the chain definitions in the attested `model.schema.json`; the execution schema is generated and changes only in 4.37); `ui/src/Workspace.tsx` + `ui/src/workspaceModel.ts` + `ui/src/views/registry.ts` (after Phase 3 task 3.3b, `Workspace.tsx` changes only for shell behaviour; a view is a module under `ui/src/views/`); `ui/src/api.ts`; `ui/control-map.json`; `design-system/Naming.md`; `ui/src/design/index.ts`; `ui/src/design/foundry.css`; `ui/design_smoke.mjs`; `deployment/checks.py` + `deployment/tests/test_repository_guard.py` (Phase 4 edits `checks.py` in 4.1 and 4.4 only; after 4.4 only runner changes edit it and a group is an entry file under `deployment/groups/<family>/`, so a task that adds a group shares no file with another); the scoped browser fixtures under `deployment/tests/` (4.4a moves them onto `browser_harness.py`); `deployment/pins.json` and the native fixture pins (`integration/tests/fixtures/native-programs.json.gz`, `deployment/tests/durable_fixture.py`; recaptured by 2.8 and by 4.37b after their re-attestations); `deployment/local_paths.py`; `deployment/dispatch_runtime.py`; `deployment/release.py`; `docs/legal/licensing.md`; `THIRD_PARTY_NOTICES.md`; `editions/local/src/hyprn_mvp_local/setup.py`.
- **Phase 4 internal chains** (sequential by shared files): API chain (`routes/documents.py`, `store.py`, generator, contract and types) 4.1 → 4.9a → 4.9b → 4.14 → 4.17 → 4.20 → 4.22 → 4.24 → 4.25; host runtime 4.1 → 4.8 → 4.14 → 4.17 → 4.21; native adapter 4.1 → 4.7 → 4.12 → 4.21; UI chain (`ui/src/views/registry.ts` and the view modules, `api.ts`, `control-map.json`, the evidence and access-loss hosts) 4.13 → 4.16 → 4.22a → 4.23 → 4.26 → 4.28 → 4.29 → the blocked UI tasks (4.31, 4.32, 4.33, 4.39) → 4.40; design chain 4.5 → 4.10; test infrastructure 4.4 → 4.4a (`test_repository_guard.py`), Documents runner modes 4.4 → 4.8 → 4.18 → 4.30 → 4.36 (`deployment/documents_groups.py`), isolated API fixture 4.4a → 4.13 → 4.26 (`deployment/tests/documents_ui_fixture.py`); version families 4.37 → 4.38 (`execution_bundle.py`, `test_module_boundaries.py`, the consumers; 4.37 also replaces the explicit checks of 4.35, its dependency). Then 4.37 → 4.37b → 4.38 (`deployment/pins.json` and the native fixture pins; 4.38 waits for the window to close). The stale-attestation window (see "Blocked lane") runs from 4.34's first attested-input edit to 4.37b's verification. The blocked tasks 4.31–4.39 join these chains under the "Blocked lane" rules: a fixed lane order among themselves and an explicit not-beside list per task.
- **Phase 2:** tasks 2.3 and 2.8 precede 4.19; 2.7 precedes 4.11 and 4.15; 2.6 precedes 4.36; 2.8 (which completes the chain 2.8a → 2.8b function-keyed dynamic-loading allowlist → 2.8c contract schemas split by consumer, and re-attests) precedes 4.32, 4.34 and 4.37; 2.11 precedes 4.30 and 4.41. From task 4.4 on, Phase 4 never edits `deployment/checks.py`, and a Phase 2 group added after 4.4 is an entry file, so the runner no longer serializes Phase 2 with Phase 4. No Phase 2 task whose verification names a group on the stale-attestation window's measured list runs while that window (4.34 → 4.37b) is open; 2.8's own re-attestation and fixture recapture come first, because 4.34 depends on 2.8.
- **Phase 3:** task 3.3a (per-owner API routers) precedes 4.1 and so every Documents route task; 3.3b (study-shell view registry) precedes 4.13 and 4.22a, and through the UI chain 4.23, 4.26 and 4.29; 3.3d (server-decided recovery on receipts) precedes 4.9b; 3.3c (one run-row read) edits `history.py`, `execution.py` and `approach.py`, so 4.37 and 4.38 do not run beside it. No Phase 3 task whose verification names a group on the stale-attestation window's measured list runs while that window is open. Evidence routes keep `EvidenceCreate1`–`3` and `EvidenceRevise3` unchanged (4.20); if the Phase 3 `read_evidence` tool exists when 4.20 runs, citation text returns inside `untrusted_content` (otherwise the rule is handed to Phase 3 in the 4.20 checkpoint). The study shell, `ui/src/views/registry.ts`, `api.ts`, `control-map.json` and `Naming.md` are serialized with the Agent activity page (the `activity` view module of 3.23) and the attribution chip. A Phase 3 group added after 4.4 is an entry file under `deployment/groups/agent/`; a Phase 3 browser fixture added after 4.4a serves and runs Playwright through `browser_harness.py`.
- **Phase 5:** removes `documents` from `capabilities.unavailable` at the release gate (PD-4.8) after its reviews close every high finding; reviews the read loop, the parser containment and the chunk route as security-critical paths, and rechecks the access-loss hosts moved by 4.22a before they are recorded as mitigated.

## Must-pass groups after Phase 4

After task 4.4 this list is generated from the entry files (`python3 -B deployment/checks.py --list --class must-pass`); the table names the Documents groups this phase adds or keeps.

| Class | Groups |
|---|---|
| Contract and static | `documents-contracts`, `documents-citation-contracts`, `documents-parser-adoption`, `documents-registry`, `documents-chain-contracts`, `documents-configuration-chain` |
| Native (Docker, AiiDA) | `documents-native-atomicity`, `documents-native-originals`, `documents-collection-protocol`, `documents-upload-api`, `documents-collections`, `documents-bridge`, `documents-read-loop`, `documents-library-api`, `documents-access`, `documents-annotations`, `documents-collections-api`, `documents-parser-image`, `documents-annotations-api`, `documents-parser-containment`, `documents-supervision`, `documents-citations`, `documents-evidence-v4`, `documents-extraction`, `documents-usage`, `documents-extraction-api`, `documents-search`, `documents-extraction-provenance`, `documents-citation-spans`, `documents-upload-recovery`, `documents-archived-study`, `documents-bundle-admission`, `documents-frozen-history` |
| Modeling image | `documents-modeling-private` |
| Browser on a native backend | `documents-isolated-api`, `documents-library-ui`, `documents-collections-ui`, `documents-evidence-ui`, `documents-reader-ui`, `documents-annotations-ui`, `documents-cite-ui`, `documents-history-ui`, `documents-ui-zoom` |
| Opt-in | `documents-served` (scratch installation) |

<threat_model>

## Trust boundaries

| Boundary | Description |
|---|---|
| Browser → application API | Untrusted uploads, identifiers, offsets, cursors, filenames, annotation and evidence text cross here |
| Application → host writer (write bridge) | Closed `DocumentBridgeWrite1` frames; the host trusts nothing outside the frame |
| Application → read process (read bridge) | Read verbs only; the read process holds no launcher, worker or write capability |
| Application spool → host writer | The application writes; the host resolves an opaque, server-derived handle read-only |
| Host writer → parser container | Untrusted file bytes parsed in isolation under external limits |
| Package index → parser image build | The only network-facing acquisition of this phase |
| Document text → UI and later agents | Text, titles, filenames, annotations, snippets and quotations are untrusted content |
| Stored records → historical reads | History never contacts the modeling service and never substitutes current content |

## STRIDE threat register

| Threat ID | Category | Component | Severity | Disposition | Mitigation plan |
|---|---|---|---|---|---|
| T-4-01 | Information disclosure / Elevation of privilege | Every Documents route (guessed IDs) | high | mitigate | `Store.authorize` for the route's study before any lookup and again at delivery; one non-disclosing 404 for unknown and foreign IDs; every Documents route registered from `routes/documents.py` (a test pins it) so the access matrix enumerates one router; access matrix over every route and parameter (4.1, 4.9b, `documents-access` extended by 4.14, 4.17, 4.24, 4.25, 4.32) |
| T-4-02 | Information disclosure | Search snippets, counts, cursors | high | mitigate | Signed cursors bound to actor, study, query, filters and revision with an in-memory key; coverage and counts computed after authorization; deleted or foreign collection filters not found (4.9a, 4.9b, 4.25) |
| T-4-03 | Information disclosure | Cached read replies and the read mailbox | high | mitigate | Replies cached at most 5 minutes and re-authorized at every delivery; access-loss tests (4.9b) |
| T-4-04 | Tampering / Denial of service | Uploads (polyglots, mismatched types, oversize, gaps, changed bytes) | high | mitigate | Media, header and extension agreement; strict UTF-8; per-chunk and whole-file length and SHA-256; quotas; route-exact raw body with a streamed cap (4.1, 4.9b) |
| T-4-05 | Spoofing / Tampering | Download headers and filenames | high | mitigate | Fixed native filename; encoded attachment filename; `nosniff`, `no-store`; filename matrix tests (4.1, 4.9a, 4.13) |
| T-4-06 | Elevation of privilege (cross-site scripting) | Reader, snippets, titles, annotations, quotations | high | mitigate | React text nodes only; visible markers for bidirectional and zero-width controls; the existing content security policy; hostile-payload browser tests (4.10, 4.13, 4.26, 4.28, 4.29) |
| T-4-07 | Denial of service / Elevation of privilege | PDF parser (bombs, cyclic trees, page floods, exploits) | high | mitigate | Pinned image, no network, non-root, read-only, dropped capabilities, CPU, memory, PID, scratch and output limits, external wall clock with descendant cleanup, reaping by label; canaries as evidence; extraction refused without current evidence (4.15, 4.18, 4.21) |
| T-4-08 | Tampering | Parser supply chain (wheel, base image) | high | mitigate | Lock with size and SHA-256 verified at acquisition and inside an offline build; digest-pinned base; advisory recheck; no substitution (4.6, 4.15) |
| T-4-SC | Tampering | Parser wheel installation (flagged suspicious by the legitimacy check) | high | mitigate | Version decision checkpoint (4.2) and a blocking human legitimacy check immediately before the first install, never auto-approved (4.11) |
| T-4-09 | Tampering / Repudiation | Duplicate or partial effects after crashes or lost replies | high | mitigate | Witness in the same native transaction; exact witness lookup before current state; uncertain never retried; kill tests at every boundary (4.1, 4.7, 4.9b, 4.12, 4.21) |
| T-4-10 | Elevation of privilege | Read process used to write or launch | high | mitigate | Closed verb sets on both ends refused before I/O; no scientific module in the read entry's import closure; own lock; ends with the executor (4.8, 4.19) |
| T-4-11 | Tampering (prompt injection) | Document-derived text reaching agents later | medium | mitigate | `DOCUMENT_UNTRUSTED_FIELDS` inventory with a coverage test; citation text inside `untrusted_content` for agent evidence reads (4.20, Phase 3 hand-off); no agent document tools this phase; the human-only Documents routes (collection deletion, archive, unarchive, permanent deletion) and the routes not offered to agents (import, backup restore) stay listed in `contracts/documents.md` so Phase 3's agent route classification refuses them (ADR-0003) |
| T-4-12 | Tampering | Forged quotations or offsets in citations | high | mitigate | Closed candidate schema without quote fields; the server slices and hashes the native artifact; bounds and identity checks; the projection is never the source (4.20, 4.27) |
| T-4-13 | Tampering | Widening earlier contract versions; attested-set drift | high | mitigate | Byte-identity tests of earlier definitions; golden corpus unchanged; two-sided coverage and re-attestation (4.34, 4.35, 4.37) |
| T-4-14 | Denial of service | Spool exhaustion | medium | mitigate | 4 incomplete uploads and 100 MiB per study; 24-hour lease with deletion by the application (4.9b) |
| T-4-15 | Information disclosure | Native identities, paths and document text in responses or logs | medium | mitigate | Native IDs, stores and paths never in public shapes or copy; log tests without document text or foreign IDs (4.1, 4.9b) |
| T-4-16 | Tampering (cross-site request) | Non-GET routes including the chunk PUT and previews | high | mitigate | Origin, session and CSRF checks kept on every non-GET; chunk PUT without the CSRF header refused (4.1, 4.20) |
| T-4-17 | Denial of service | Orphaned parser containers after a writer crash | medium | mitigate | Owner labels; reaping at writer start and in `finally`; supervisor-kill canary (4.18, 4.21) |
| T-4-18 | Tampering | Mutable AiiDA extras holding collection and annotation state | medium | mitigate | Fail-closed state validation against witnesses; extras never treated as grants (4.7, 4.12) |
| T-4-19 | Repudiation | Terminal collection Groups and witnesses accumulate | low | accept | Retained by design (§9.1); no automatic cleanup |
| T-4-20 | Information disclosure | Same-user processes reading the data root | low | accept | Local mode is not a boundary against the logged-in user (as T-2-06) |
| T-4-21 | Information disclosure | Protected content left on screen by an evidence, assumption, model, unit, configuration or study-shell host after a confirmed loss of study access | medium | mitigate | One classification through the shared seam (`useAccessLoss`, `api.readFailed`, `accessDenied`); the local `evidenceAccessLost` removed; one browser case per host family; Phase 5 rechecks independently (4.22a) |
| T-4-22 | Tampering / Repudiation | A client resending a document command whose outcome is unknown | high | mitigate | Recovery reads the receipt's server-decided `recovery`; an uncertain operation's receipt is never `resend_same_command`; no client keeps its own recovery table (4.9b with Phase 3 task 3.3d, 4.13) |
| T-4-23 | Tampering | Shared browser-fixture harness widening a fixture's write allowlist or body cap, or a moved group running under another interpreter or with fewer needs | low | mitigate | Write predicates, caps and controls stay per fixture; group entries carry class, needs and interpreter in a closed schema; before and after counts and `--list` diffs recorded (4.4, 4.4a) |
| T-4-24 | Tampering | A historical record accepted or refused differently after version literals become capability questions | high | mitigate | Property tests that the capability table reproduces `RETAINED_PAIRINGS` and answers as each replaced predicate; golden identity corpus and history, export and bundle groups with identical counts before and after; the worker keeps its own table; the table added only inside the one re-attestation (4.37, 4.38) |

</threat_model>

<verification>
- `python3 -B deployment/checks.py --group qualification` exits 0 on the development host with every Documents group listed above.
- `python3 -B deployment/checks.py --group documents-served` exits 0 on a scratch installation.
- `python3 ui/check_design_system.py` prints no FAIL line; `python3 ui/design_tokens.py --check`, `python3 ui/test_design_tooling.py` and `node ui/design_smoke.mjs` pass; the UI contract checker maps every new control and route.
- `GET /api/1/capabilities` lists `documents` in `unavailable` and every delivered slice in `document_slices`.
</verification>

<success_criteria>
- All five Phase 4 success criteria in `ROADMAP.md` are true (criterion 4's run part after OQ-1 and tasks 4.34–4.39; criterion 2's reload part after OQ-5 and task 4.32).
- Forty-five checkpoints exist (tasks 4.1–4.41, with 4.4a, 4.22a and 4.37b added and 4.9 split into 4.9a and 4.9b), each verified before its dependants started; the decision checkpoints (4.2, 4.3) and the blocking human check (4.11) record their human answers; the product owner's walk-through is recorded separately from automated evidence (4.41).
</success_criteria>

<output>
After task 4.41, write `phases/04-documents/04-SUMMARY.md` in the planning directory: groups and counts, read-loop and supervision timelines, parser image and containment identities, the answers to OQ-1 to OQ-5, slices advertised, and any assertion that could not be kept.
</output>
