# Exact monetary interpretation in computational records

Portable computational record format 3 adds associated scientific context for
monetary model quantities. Formats 1 and 2, frozen configurations and native
execution bundles retain their original definitions and bytes.

For each monetary model version used by the selected runs or their required
ancestors, the export contains one immutable model explanation and the exact
evidence versions it cites. The explanation is resolved by the retained model
version ID and checked against its digest; neither the current draft nor another
model version's explanation may substitute. The explanation's monetary quantity
identities and expressions must exactly match the model's units catalogue. Its
price year and economic basis are preserved without currency, inflation or scale
conversion.

The `interpretations` manifest index binds the model revision and digest,
explanation version and digest, closure digest, path, length and byte hash. The
closure is marked `associated_scientific_context`: it explains the frozen
calculation but is not presented as a file inside the native execution bundle.
Each exact model version admits at most one immutable saved explanation, and
monetary configuration authoring requires that explanation before saving.

Preview identity includes the interpretation closure. Export publication and
download recheck authorization and exact retained identities. The offline reader
checks the complete closure, rejects missing, duplicate, foreign or extraneous
interpretations, and reconstructs the full declared inventory. Source text is
inspected as data only; export never imports or executes candidate code. Existing
archive bounds and secret/private-path checks also apply to the added context.

An archive's internal digests establish consistency, not authenticity against an
external signer or scientific validity. The cited evidence and stated economic
assumptions still require engineering review.
