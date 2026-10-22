# Evidence

One presentation for evidence everywhere: the library, the picker, the model details panel, input, criterion and context attachments, and run history.

- Each item or claim exposes one **View evidence (n)** button with the shared navigation affordance through the shared `EvidenceButton` and application `EvidenceDisclosure`. Count distinct attached evidence versions, including unavailable attachments, not source-reference strings or claims. No attachment means no reading button. Source titles and citation controls belong inside the panel, not beside repeated buttons.
- The action opens `ContextualPanel` in the workspace details slot, never an evidence-content popup. The panel uses the available viewport height, a stationary header and one scrolling content region. Each source is a plain reading section, separated by whitespace and a hairline: record title with discreet Record details, explicit Source, Source excerpt with page/location, then Explanation. No nested card borders, numbered reference lists or repeated section headers. Source references remain inert text. Saved notes are labelled **Evidence note**; absent quoted passages must never be invented or presented as authenticated snippets. Answer-wide evidence remains labelled as such, not reassigned to individual claims.
- Editable citation/remove controls stay with their source inside the panel; Add evidence remains beside the owning item. Opening from an editor keeps the panel inside that editor's focus boundary. Opening from Study details preserves the parent reader for Back. Close/Escape restores the invoking action. Navigation, version changes and lost access clear the reader.
- Use Assistant explanation only when the exact record has agent attribution; otherwise use Explanation. Agent authorship remains visible beside the explanation or evidence note. It identifies who wrote the note, separately from the authority of its cited source.
- Study details retains one action beside each assumption or limit, even when sources are shared. The panel preserves every citation relationship and location; conflicting evidence stays visibly marked beside the claim.
- **Record details** in the evidence panel shows the evidence family, version and resource identifiers. A record without a stored scope says **No scope.** here only. Raw `kind` and scope format version are not product fields; **Download evidence record** keeps the entire stored JSON. Empty or redundant context and reference sections are omitted. Version discovery is explicit in the attachment picker; choosing another version never silently replaces an attachment.
- A missing attached record says **Evidence unavailable**. A historical view reads the stored snapshot, never today's library.
- Run Evidence puts "Evidence used by this run" before the "Run files" table. File categories are presentation filters: Calculation records, Executable program, Provenance & licenses, All files. Search and 20-row pages never hide a file permanently. Details shows the SHA-256 and ID; previews are bounded at 64 KiB and downloads keep all bytes. Generated files are read-only provenance ("Read-only run file"); a missing file says "This run file is unavailable."
- A note kept with a run is evidence of its recorded context, not scientific validation.

## Excerpts and explanations

New sourced notes use the explicit `HYPRN evidence/1` content format defined in
`contracts/schemas/evidence-content.schema.json`. The immutable evidence record
remains the sole owner; its content carries source reference, page/location,
verbatim excerpt and explanatory text as distinct fields. These are author-supplied
transcriptions, not authenticated document extractions. Never parse a legacy note
into a quotation or infer its page. Legacy notes remain labelled Evidence note.

Use the shared EvidenceReading component everywhere. Source reference and location
are compact, selectable text. A quotation has a quiet left rule and generous line
height; explanation is ordinary body text under one small label. Authorship belongs
to the explanation, not to the quoted source. Record details sits below the source
title; record download and raw references belong inside it. No duplicate source
reference if it already appears in the excerpt attribution.

Place the button left aligned on its own action row below prose, with space-3
separation. In tables, use the dedicated evidence/provenance cell, left aligned.
Never run the button directly into the end of a sentence or indent it like a source
quotation. Editors may share that row with Add evidence. Count distinct attached
versions, including unavailable ones.

## Referenced evidence library

Evidence lists the distinct evidence versions explicitly attached to claims elsewhere in
this study, including saved brief/answer/model/configuration/run history. It does not
list assumptions as evidence, infer new claim relationships from scope, or replace a cited version
with its family head. A newly created unattached version remains available to pickers;
it joins this page when attached. Creation and revision never retarget existing claims.

The library renders the shared full reader directly. There is no View evidence inside
a library card or inside the details panel. Claim owners (including brief assumptions,
limits, criteria and answer justifications) each expose one View evidence (n) button.
Use Assertion/AssertionList for the prose-to-action rhythm. Missing referenced versions
stay visible as unavailable; failed owner reads label the library incomplete and allow retry.

Record details remains the first quiet action below the evidence title. Version discovery remains explicit in the attachment picker; the library does not
switch a cited record to another version. Source reference text is visible
above the quote, never buried among IDs. Page/location sits beside Source excerpt.
Explanation is separately attributed and does not appear inside quotation marks.
Legacy notes do not acquire a fabricated excerpt, page, source or assistant attribution.

The library uses `ReadingStack` for toolbar-to-record spacing and `EvidenceStack` with `hf-evidence-list` for separated records. The same reader limits source, quotation and explanation lines to `prose-measure`; edit actions sit one `space-4` below the content.

Library membership also includes explicit model/component resource bindings already exposed by the selection inspector. Resolve frozen configuration/model/approach owners once; sampled runs with the same retained owner must not trigger repeated full history reads. If an owner is unavailable, one retained run may supply its exact closure.
