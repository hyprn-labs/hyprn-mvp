# Concise answers and the Experiments workspace

## Status

Accepted by the product owner on 2026-10-19. Refines the answer fields in ADR-0008 and
navigation terminology in ADR-0009–0010; exact pins and record ownership are unchanged.

## Decision

Name the model-version-scoped numerical workspace **Experiments**. Its records remain
calculations, configurations and runs; do not add a redundant stored grouping object.

New answer content uses Interpretation, Uncertainties and Next analysis, alongside its
outcome, comparison, justifications and prepared exploration. Qualifications belong within
Interpretation and unfinished work in Next analysis. A separate open-deliverables field is
retired. Comparison rows cite observations, not automatic winners: several runs per
alternative/criterion can be cited, and a calculation can hold many configurations.

## Consequences

Introduce answer content format 2 rather than modifying immutable format 1. Historical
reads retain their exact bytes; editing copies carry prior qualifications and unfinished work
forward. Output names and criterion evaluations are resolved from cited records by the owner.
Display one Alternatives comparison table; keep raw identities in record details and explain
selection rationale without implying that only one passing point exists.
