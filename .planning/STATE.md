# Project State

## Project Reference

See [PROJECT.md](PROJECT.md), [ROADMAP.md](ROADMAP.md) and [HANDOVER.md](HANDOVER.md).

**Core value:** An engineer can reach a defensible feasibility answer whose every number is reproducible and traceable, without shell or database steps, on their own machine.
**Current focus:** Phases 2 and 3, ordered by the approved [delivery plan](DELIVERY-PLAN.md).

## Current Position

- Phase 1 is recorded complete. Its original gate passed 102/103 groups on `a66a1f3`; the remaining findings chain passed later on the continuation branch. That history is not a claim of full qualification on today's tree.
- Phase 2 completed: 2.1, 2.1a, 2.2–2.8 and 2.8a–2.8c. Phase 3 completed: 3.1, 3.2, 3.2a, 3.3, 3.3a–3.3d and 3.4–3.10. Checkpoints retain exact commands, failures, counts, artifact identities and cleanup. Full 3.16 remains partial; its paths slice is verified.
- Task 2.8 closes the combined schema/study-path/release attestation window. The current modeling producer and native captures are verified; the final runtime retains exactly 49 reviewed source paths and one unreplaced attestation. See [checkpoint 2.8](phases/02-local-edition/checkpoints/2.8.md).
- Latest integrated acceptance: all 23 initial groups pass at `b5a7b62`; the docstring-only correction passes affected release checks at `a5ef4eb`; the final native journey passes 14 tests plus its existing one deselection, with seven runs, four archive pairs and three browser checks. The two-constant durable pin at `d4467eb` passes guards 17 and preflight 1, preserving seven processes and 5,675 original files; final style 33 and term scan 0. All 29 allocated orchestrator scopes and the fresh materialized copy are released; the referenced worker image and immutable captures are retained.
- Every current-image/native group deferred by 2.8c now passes, including public-api 70, ae-model 26 and fuel-native-provenance 16 (one added historical-export case). The earlier 30-group schema/path acceptance remains recorded in [2.8c](phases/02-local-edition/checkpoints/2.8c.md#integrated-orchestrator-verification) and [3.16-paths](phases/03-agent-tools-for-coding-agents/checkpoints/3.16-paths.md); unchanged checks are not repeated.
- First useful product checkpoint C: both local clients save an evidence note visible in the UI with attribution, activity and revocation. D adds the complete engineering workflow. E retains portability and broad operational proofs; F retains Documents and final qualification. A partial slice never closes its original task.

## Decisions and Authority

- [DELIVERY-PLAN.md](DELIVERY-PLAN.md) governs task slices, dependency replacements, batches and parallel scheduling. Use focused executor checks, one integrated union of required acceptance, and complete final gates. Two independent implementation lanes follow the exclusive attestation window; one integrator owns shared runner/guard registration. Preserve real dependencies and serialize contested resources.
- PD-2.4 option a and its exact packet are approved: move 108 Documents-only definitions and registry; retain 11 shared citation definitions, 37 launch roots, their 140-definition closure and all 49 attested inputs. Preserve the exact pre-split capture and historical identities. [Checkpoint 2.8a](phases/02-local-edition/checkpoints/2.8a.md) is authoritative.
- Build backend: approved flit_core 4.1.0. Task 2.7's three approved packaging transformations must preserve runtime-file bytes, dependencies and entry points; only enumerated metadata differences are accepted. No setuptools licence exception. The exact proposal hashes, transformations and equivalence evidence are retained in [checkpoint 2.7](phases/02-local-edition/checkpoints/2.7.md) and its dependency audit.
- Namespace and historical identity: `hyprn-mvp` is the product namespace; no compatibility readers for records outside it. Prepared artifacts record schema identities instead of copies. The golden corpus retains its captured blobs; historical reads never substitute current content.
- Modeling producer builds are not bit-reproducible. A changed modeling source requires a rebuild, a new `modeling_producer` pin and native fixture recapture. [Checkpoint 2.8](phases/02-local-edition/checkpoints/2.8.md) records the current images, 49-file inventory and durable fixture `native-20261014T143925Z`; [2.6](phases/02-local-edition/checkpoints/2.6.md) retains the preceding identities. Preserve historical captures and unpinned old fixture folders.
- Store rule D-12: before the pilot-retention boundary, ordinary open/start never creates or migrates stores. Task 2.11 adds explicit creation, schema-version refusals and confirmed identity-checked `setup --reset-data`; no automatic reset or migration. After the retention boundary, the full retention, backup and migration rules apply.
- Authority and ownership follow ADR-0003, ADR-0004 and ADR-0005. Agents cannot delete saved records, archive/restore or manage access; working material stays revision-checked. Reviewer delegations may record labelled scientific reviews. One operation has one authoritative outcome; the UI follows server-decided receipt recovery. Method-package release remains human-only.
- Phase 3 decisions and practices are in [checkpoint 3.2](phases/03-agent-tools-for-coding-agents/checkpoints/3.2.md) and [03-PRACTICES.md](phases/03-agent-tools-for-coding-agents/03-PRACTICES.md): runtime-owned progress notes, packaged playbook sections, explicit revisions, interactive-only token display, CLI token administration and WSL2-local clients. OQ-3 is decided after both-client evidence at 3.17/3.18.
- No credential-file fallback when a credential store is unavailable. Study folders resolve flags/environment/configuration/defaults through the common path policy. OPS-04 stays planned until qualification; VER-03 semantics are reused by clients.
- The approved formatter ratchet uses ruff 0.16.10 and prettier 3.9.10, line limit 100 and single quotes. Task 2.8c formatted the attested sources in separate syntax-equivalent commits and removed their exclusion; hash-pinned tests stay excluded. A history rewrite that removes the baseline requires regeneration.
- Toolchain and licensing decisions are retained in [the Phase 2 dependency audit](phases/02-local-edition/2.1-dependency-audit.md) and `docs/legal/licensing.md`: pinned uv/CPython, only audited package changes, and recorded residuals. The later approved Flit decision supersedes the earlier setuptools choice.
- Supported hosts: Apple-silicon macOS, Linux x86_64/aarch64 with glibc, and Windows through WSL2. Intel macOS is refused until a reviewed dependency build exists. Current-host evidence does not qualify the other hosts.
- Phase 4 decisions, capability slices, parser re-audit, document-bearing version chain and one-owner operation rules remain in [04-CONTEXT.md](phases/04-documents/04-CONTEXT.md) and its plan. Documents stays unavailable until its release gate. Lifecycle/portability follow-ups and cloud work remain deferred.
- [FACTORIZATION.md](codebase/FACTORIZATION.md) and the original phase plans retain later module-boundary, browser-fixture, group-registry, access-loss and version-family work. Earlier completed refactors are evidence, not pending dependencies.

## Remaining Obligations

| Owner / checkpoint | Obligation |
|---|---|
| 2.9 / 2.10-host and 3.11 / 3.12 | Next two independent batches: local CLI/adapters and runtime notes/MCP. One integrator owns runner/guard registration; preserve the verified attested inputs. |
| 2.11 | Explicit store creation and versions; no DDL on ordinary open. Serialize the mechanical migration of test store constructors with agent work. |
| 3.17-host / 3.18 | Human probe on both installed clients, exact client names/versions and protocol/kit decision. Neither scripted tests nor one client substitutes for both. |
| 3.28-evidence / 3.28-full | Human capability reviews; for D resolve whether the queue cap counts only runs waiting before a call, since the current 10 waiting/running cap makes 20-per-call unreachable. |
| 3.32 | Remove the unsupported run-read cache claim from tooling-spec §5.4; finish the planned run-status work. |
| Next UI dependency task | Regenerate `ui/dependency-audit.json` for prettier. |
| Documents / final qualification | Make the parser lock's real-wheel verification runnable through the scoped entry point; it currently depends on a wheel variable not passed by the runner. |
| E / Phase 5 | Real served-installation browser evidence, remaining OS/clean-room proofs, final gate and genuine human acceptance. `ui-fidelity` still needs reference images. |
| Product owner | Decide whether to retain or remove old unpinned durable-fixture folders; preserve them until then. |
| Later performance work | `get_study_overview` reads whole owner lists; large-study scaling remains unqualified. |

## Verification Constraints and Known Limits

- Every check uses `./hyprn-mvp dev check`; missing environments fail. Qualification freezes its tree and excludes competing heavy work. Durable-fixture groups and units-native share one dedicated scratch lane.
- A findings continuation consumes its working copy; rebuild that copy through preflight before repeating. Never alter immutable authoring records to make a test pass.
- Test stores are scoped; live roots, ports and names are protected by the development environment. No host-specific value belongs in repository content.
- API test modules retain their synthetic loopback origins when browser fixtures shadow conftest imports.
- The old unregistered-test, obsolete fixture-path, namespace and worker-read-permission issues have completed owners; their checkpoints retain failures and fixes. They are not current blockers. Any recurrence needs fresh evidence.
- Automated acceptance, human acceptance and deployment status remain separate. Neither Phase 2 nor Phase 3 is complete, and the current tree is not a qualified release.

## Session Continuity

Work branch: `feat/local-edition-continued`, no upstream. No push or pull request is authorized.

Next: use fresh worktree executors for the approved batches 2.9 + 2.10-host and 3.11 + 3.12 from the verified integration commit. Root owns shared runner/guard registration and integrated acceptance. The attestation window is closed; repeat prior checks only for changed inputs or unresolved concerns. Continue toward C, stopping for the real 3.17 client probe and 3.18 decision. Preserve the later 3.28 and both-client acceptance gates.
