# Nested contract validation CPU — 2026-10-23

Source commit: `70bb9631d33a7751869a9ef81e4632ce8e3a1be3`.
Owner: validation-performance subtask. Scope: `contracts.py` and focused contract-error tests.

## Finding and correction

The retained-run profile showed most schema CPU inside nested version unions: incompatible
branches still visited the complete model/preparation tree before rejecting its version tag.
The application already selected provably disjoint version branches at the root. The same
rule now applies inside a compiled static local schema namespace. Every field in the selected
branch is validated. Ambiguous, unversioned, external, nested-resource/dialect or dynamic
schemas retain ordinary library behavior. Failed validation uses the original union's full
diagnostics. Namespace branch metadata is compiled per validator; no new cache of successful
records, failures, authority or scientific admission was introduced.

Digest, source-byte, unit, preparation binding and scalar admission checks are unchanged.
The initial scoped successful-reference memo experiment improved cold validation only about
4%; it was discarded. `execution_bundle.py` remains unchanged.

## Evidence

- `./hyprn-mvp dev check locality-contracts` with the host's existing development data root
  and pinned tool-cache environment
  — **174 passed**, one existing FastAPI deprecation warning, 13.06 s.
- Eight added cases cover 8× fewer expensive leaf checks for an eight-version nested union,
  complete diagnostic parity, mutation and closed fields, boolean/nonfinite/unsafe input
  rejection, ambiguous/unversioned branches, separate schema namespaces, and fallback for
  nested resource identifiers, anchors and dialect changes.
- The first checkpoint commit was refused because its command included a host-specific path;
  that path was removed from this portable checkpoint. First test-command attempt stopped before tests: sandbox denied the pinned uv cache. The same
  entry-point command with authorized filesystem access passed. Test scope
  `hyprn-mvp-test-58c13773-78a6-496f-b061-e3a4039ee73e` confirmed removed.
- `git diff --check` passed. Only a blank-line removal separates the tested source from commit.

Read-only actual staging retained payload was extracted by the parent and replayed locally,
with all bundle files decoded and the real `validate_retained_bundle` boundary. No model code
ran, no staging records changed. Three alternating fresh processes per revision, pinned native
interpreter, no profiler: **median 0.4247 s → 0.2782 s (34.5% reduction)**. Individual before:
0.4756/0.4224/0.4247 s; after: 0.2782/0.3131/0.2781 s. The instrumented profile separately went
1.398 s → 0.903 s; these local timings are not claims of staging elapsed-time improvement.

Private evidence: `/private/tmp/hyprn-analysis-performance/validation-measurements.json`,
`validation-before.txt`, `validation-after.txt`, `validation-locality.log`,
`replay-validation.py`, `measure-validation.py`. The original retained fixture and baseline
source are private and deliberately uncommitted. No dependencies added.

## Integration obligations

Parent owns integrated contract checks, deployment and real public before/after verification.
Shared contract validation is part of runtime source, so regenerate normal runtime artifacts
and attest the resulting worker identity; do not reuse an old attestation with changed bytes.
The large elapsed analysis delay also involves repeated retained-result reads and is not
claimed solved by this optimization alone. No full qualification or human acceptance claimed.
