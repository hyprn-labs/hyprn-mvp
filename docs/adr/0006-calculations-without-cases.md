# Calculations without cases

- Status: accepted
- Decision date: 2026-10-17
- Authority: product owner request to remove cases throughout the platform.

## Decision

A study owns models, configurations, runs, evidence and scientific answers. A configuration specifies an exact calculation; a run records its execution. A study answer cites configurations, runs and evidence directly. There is no Case entity, case answer, case selector or case association. Qualitative exploration choices remain data-defined input combinations and do not require an intermediate entity.

Model names are model-family metadata owned by the modeling service, exposed consistently by the application API. A saved version keeps its immutable identity independently of the current family name. Both Models and Calculations show that name and a separate version selector.

## Consequences

This intentionally replaces earlier case-based specifications and workflows. The authorized demo transition may discard development runs, but must preserve authored scientific material in an export before replacing incompatible records. Never edit an immutable record in place while keeping its identity or digest. Execution containment and current runtime attestation remain mandatory.
