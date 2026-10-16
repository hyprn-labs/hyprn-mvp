# Verified preparation byte reuse

Owner authorization: reduce repeated preparation overhead as the next step; safely pause and resume the current samples if needed. This is the first performance increment, not completion of the six-second end-to-end target or a new batched worker.

## Change and invariants

`StaticPreparation` keeps a process-local LRU of inert verified bytes, keyed by actor, study, SHA-256, size and media type. It is bounded by the existing maximum expanded bundle bytes and file count. Every call still obtains a fresh authorized prepared manifest and validates the complete model, configuration, bindings, inventory and hashes. Failed preparations never populate the cache; eviction/restart causes downloads. No cached authority, manifests, candidate results or skipped admission checks. No API, dependency, schema or attested worker source change.

## Evidence

- Red regression: `./hyprn-mvp dev check units-bundle`: 1 failed / 123 passed; identical preparation downloaded all 194 fixture files twice. Scope `976fef18-8f14-4f29-ba52-c1c080584a2c`.
- Final development run: same group, 126 passed, 48.91 s. Scope `4c8519fd-bc57-4198-bddf-e273453fa0d9`. Tests cover reuse, fresh authority/refusal, actor isolation, changed manifest/content rejection, no failed-cache admission and eviction.
- `./hyprn-mvp dev check style-ratchet`: 33 passed. Scope `660725e9-d335-4d40-aaf7-b21b0c441399`. Two preceding runs caught long changed lines; both corrected. An initial unprivileged runner attempt could not open its external tool cache; it performed no tests and was rerun with the scoped runner permissions.
- Retained real preparation replay, identical command/model/configuration: 198 file downloads before, zero warm downloads after. With cProfile enabled, warm preparation fell from 4.631 s to 2.170 s. This measures preparation only; profiling overhead means these are not end-to-end production timings.
- A real public-API comparison of run `d63de383-cc93-4d55-81a7-ea77dedaf399` with `09cd3a07-844c-479c-9d53-329ef36c6ccb`, both configuration `914268ee-40f4-4845-ba58-6c8730a076fb`, returned identical 11 outputs, criteria, configuration/model/context/evidence/approach records, dependency pins and source/generated artifacts. Both recorded successfully with no retained-integrity errors. A diagnostic read initially used a nonexistent history subroute and returned 404; the documented run endpoint supplied the comparison without another submission.
- Subsequent warm dispatch durations observed at approximately 25–27 s. Dispatch excludes configuration authoring and client polling; do not compare it directly with the earlier approximately 31 s complete per-point cycle or claim a six-second result.

Profiling/timing wrappers and comparison records are external scratch artifacts (`hyprn-all-sliders`). No profiling code was added to the product. The temporary dispatcher wrapper records wall timings only; cProfile was removed before the subsequent run measurements.

## Recovery and remaining work

The client stopped between receipt polls. Its accepted last run completed successfully and was reconciled by its saved run ID, bringing the retained new-original count to 58. The saved manifest was preserved before pause; successful samples were not resubmitted. One additional controlled same-configuration run was explicitly used for the equivalence check. The unchanged attested runtime permits continued reuse of earlier exact samples.

Sampling resumed from this manifest; all-input/category coverage remains in progress and belongs to the [all-input checkpoint](all-input-curves.md). Full batching, reuse of worker initialization and deeper validation/provenance costs remain performance work. A worker change needs attestation and explicit handling of old/new runtime compatibility; never silently combine those runtimes in an assessed fit. No full release qualification or human acceptance is claimed.
