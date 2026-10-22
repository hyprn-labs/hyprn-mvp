# Collection loading consistency

User request, 2026-10-19: “2 analyses for this model version; 36 saved versions loaded; 20 of 20 loaded runs (whereas there were more)” must become a coherent experience governed by the design system.

## Decisions

- D-01: One shared design-system contract owns collection count wording, loading, completeness, filtering, empty/error states and pagination actions. Screen-specific copy patches do not satisfy the request.
- D-02: Cursor metadata is authoritative. A received page count is not the server total. No backend total-count feature is needed or authorized by this task.
- D-03: Existing rows remain visible on append failure; retry requests the failed cursor. Initial loading/failure never claims an empty collection. Scope/session/access changes fence late responses and clear protected data.
- D-04: Apply the contract coherently to current collection surfaces, including the reported Experiments collections, evidence/results pickers and version-history collections. Inventory complete-list consumers explicitly; do not invent paging for an API helper that already follows every cursor.
- D-05: Use the isolated `codex/collection-loading` worktree based on `4c6335c`. Do not edit the main checkout, contact or interrupt the main agent, change scientific progress/results, introduce dependencies, change the API, or deploy.

## Scoped workflow amendment

The orchestrator explicitly requested one numbered cohesive task for this shared invariant, applying the user's supplied working preferences about proportionate process. Keep one fresh executor, explicit owned paths, atomic commits, integrated acceptance and parent replay. The number of consumer files does not create independently shippable behavior here. This is a scoped addition to Phase 3, not a replan or completion claim for the whole phase. Do not edit global ROADMAP or STATE.

## Discretion

Use concise “N … shown” with an explicit more-available cue while partial; use the same neutral count without transport language after exhaustive success. Filter matching is a separate sentence from collection coverage. Preserve each domain's precise noun and existing resource/action ownership.

## Out of scope

Scientific run progress, fitting/prediction lifecycle, backend pagination contracts, global server search, document features not implemented in this checkout, full release qualification and deployment.
