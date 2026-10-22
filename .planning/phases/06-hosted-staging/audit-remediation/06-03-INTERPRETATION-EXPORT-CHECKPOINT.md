# Monetary interpretation retained with computational exports

The exact model's catalogue monetary units alone do not preserve price year,
economic basis or cited evidence. Portable Manifest3 therefore includes indexed
associated scientific context: the immutable saved ModelExplanationVersion3 and
its complete exact evidence-version closure. No native execution payload or
historical concrete schema is changed. Exact model identities and catalogue
expressions are checked; current drafts and other revisions cannot substitute.

This is associated interpretation, explicitly distinct from native bytes.
Preview identity includes its digest; publication and download recheck the same
closure and authorization. The offline reader verifies the declared index,
model/explanation/closure hashes, evidence scope and complete payload inventory.
Existing secret/private-path and bounded-expansion rules apply. No code is
executed during export or inspection. See
`docs/specs/computational-record-interpretation.md`.

Owned implementation: computational_export.py, new manifest registration and
generated OpenAPI/UI types, focused explanation API tests, and an extension of
the existing real monetary units-native journey (no extra worker fixture).
The generator commit also includes the parent's reviewed ModelDraftEditResponse5
route correction, replacing its outdated current-response alias while keeping
historical Response4 bytes unchanged. Parent owns the architecture cross-link;
B owns the reviewed computational_export → explanations/units module edges.

Verification commands use the pinned runner with development data/tool roots and
`HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480`:

- `./hyprn-mvp dev check contracts`: 127 passed, 9.81 s, exit 0; scope
  `93c9028c-29da-45f6-be38-b79294cf9a6f` released. Log:
  `/private/tmp/hyprn-monetary-export-contracts.log`.
- `./hyprn-mvp dev check explanations-api`: 28 passed, 25.99 s, exit 0; scope
  `db2a34d4-798a-476e-b010-4bd55e39e05c` released. Log:
  `/private/tmp/hyprn-monetary-interpretation-api.log`.

Initial archive-service attempt failed at collection because the newly reused
HTTP fixture imported FastAPI into the native-only archive environment (one
collection error, 2.59 s, exit 1, scope
`3b0fcf6d-0fcb-406c-9455-c7172d3f021f` released). Correction moved only those new
HTTP tests into the existing explanations-api group; no dependency or runner
change. Failure log: `/private/tmp/hyprn-monetary-export-check.log`.

The focused tests demonstrate immutable pinning, authorization, deduplication and
refusal of mismatched models/catalogue expressions, missing/foreign/extra evidence,
changed explanation hashes and unsafe context. Real downloaded Manifest3/native
archive readback remains the units-native handoff obligation; passing mocked
model authoring does not establish that native journey.

Final archive-service rerun: 44 passed in 274.88 s, exit 0; scope
`66284507-796e-431b-aba8-557008041556` released. Command:
`./hyprn-mvp dev check archive-service`, same pinned environment above. Log:
`/private/tmp/hyprn-monetary-export-check-final.log`. This covers the actual AiiDA
archive adapter and existing export lifecycle, safety, boundedness, replay,
authority and historical closure behavior. The extended real Model5/Bundle12
Manifest3 journey remains for the monetary agent's final units-native run.
