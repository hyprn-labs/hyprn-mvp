# SourceChip

A provenance link that opens the exact cited location (a page, section, table or line), never a document's home page.

- **The consumer provides** `label` (short source name), `locator` ("p. 2 §2", "Table 1", "line 3"), `authority` and `href` or `onClick`.
- **Authority dot.** `primary` (filled: the governing document, a measurement record), `secondary` (hollow: a derivative or older source), `unverified` (dashed: not yet checked). Low-authority sources stay visible so the reader can discount them.
- The underlined source label and shared inclined arrow form one opening target, through `OpenLink`. The source glyph and authority mark retain their provenance meaning.
- Teal (`trace`) is reserved for provenance. Never style a navigation link or a button like this chip.
- Group several chips after a claim in one row: "Rests on [N-1 · p. 2 §2] [Sellar et al. 1996]".
