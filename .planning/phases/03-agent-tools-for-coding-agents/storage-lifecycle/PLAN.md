# Bounded local test storage

Owner request (2026-10-16): automatic cleanup of test scopes, storage budgets and
image reuse; preserve scientific safeguards and verify repeated runs stop growing
disposable storage. This is one maintenance task, executed inline under the skill's
spawn-restricted fallback. Unrelated roadmap/research work is excluded.

## 1. Implement and verify the complete check lifecycle

- Supervise public `dev check` group runs. Register only newly allocated scopes;
  never adopt existing/resumed stores. Terminate owned child processes, release
  scope-labelled Docker resources, and remove disposable files after completion.
- Keep bounded, short-lived diagnostic evidence separately. Explicit retention
  remains possible within the scratch budget. Check aggregate scratch and free
  disk budgets before admission and while the child runs; recover abandoned
  managed sessions on later invocation without touching live sessions.
- Reuse worker images using exact build inputs instead of a random test identity.
  Keep runtime ownership, source identities, base-layer verification and attestation.
- Bound project-attributed build cache, avoiding unrelated Docker resources.
  Verify actual post-cleanup state; report unresolved budget excess as failure.
- Add behavioural tests for success, failure, interruption, quota refusal,
  preservation of existing stores, and repeatable storage/image reuse. Exercise
  the installed CLI and real Docker where available, not only mocks.

## Scope amendment

Successful disposable test stores are no longer evidence to retain. Evidence is a
bounded result/log record; full failed scopes require explicit retention. This
amends older operational practice of retaining every scope, not the invariants for
authored studies, saved versions, execution containment or source provenance.
One integrated acceptance run on the committed implementation covers this batch;
repeat only after a relevant change/failure. Full product release qualification
remains distinct, and missing pre-existing fixtures must be reported explicitly.

## Acceptance

Repeated successful representative CLI runs leave zero owned scratch scopes or
containers, stable image IDs, and bounded diagnostic/cache usage. Failure and
interruption also release resources. Invalid paths, foreign owners, symlink
substitution and unowned/live stores are refused. Budget excess stops work with
an actionable report. Record exact commands, sizes, failures and remaining limits
in the adjacent checkpoint.
