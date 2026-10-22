# Analyses within Experiments and coherent answer versions

Status: Accepted, 2026-10-19. Supersedes the Calculation terminology in ADR-0009,
ADR-0010 and ADR-0011, preserving their record and execution guarantees.

## Decision

Experiments is the model/version-scoped workspace, not a persisted aggregate. Its
Analyses, Configurations and Runs tabs list all records in that scope. An Analysis
is one purposeful investigation referencing configurations and runs. It does not
own those records exclusively. Revising the same investigation creates a version;
a complementary investigation creates a distinct analysis.

Publication of an answer rejects mixed versions of one analysis or of one model
across mappings, comparisons, justifications and exploration. Drafts may contain
conflicts while being edited; diagnostics are actionable and no pin is advanced
automatically. Historical answers stay immutable. Explicit revision comparison is
not supported in ordinary answer publication.

## Compatibility

Canonical API paths use analyses/analysis-versions/analysis-samples/analysis-estimates.
The former paths remain compatibility aliases of the same handlers and writer, with
the same authorization, concurrency, receipts and idempotency. No scientific payload
is rewritten: stored calculation_id/calculation_version_id keys, concrete schema
names, receipt categories, attribution kinds and numerical artifacts remain stable.
These wire identifiers now denote an Analysis; clients must not infer meaning from
legacy spelling. Agent tool names and product text use Analysis. This is an additive
API naming change, not another version family or a new store.

## Consequences

An answer can use several distinct analyses/models, each pinned to one version.
An analysis can include one or many configurations and repeated runs. Global lists
are never filtered by whichever analysis was last opened. The demo separates its
operating-point comparison from its sampled investigation by referencing existing
configurations/runs in a new analysis; the existing surrogate retains its exact pin.
