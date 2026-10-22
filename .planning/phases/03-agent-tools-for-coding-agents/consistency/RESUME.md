# Domain integration recovery — 2026-10-19

Owner: Codex. Integration branch: `codex/resume-domain-integration`, based on `371bc63`.
Implementation head: `073ae7c`; the later checkpoint commit changes planning records only.

## Recovered and completed

The pasted handover predates the completed configuration migration. `371bc63` already
contains the model-format-4 creation fix and the browser migrations. Its inherited evidence
and outstanding qualification failures remain in `configurations-without-criteria-PLAN.md`.
They were not repeated as a broad sweep.

Four workstreams were snapshotted before integration. Their original HEADs, tracked diffs
and untracked source files are unchanged (byte comparison against the snapshots). The
original branch, unrelated ROADMAP edits and research documents remain untouched. An inherited
agent-ui check was left running; it finished with the already recorded legacy failures.

| Recovered work | Integration and completion |
|---|---|
| Calculation agent tools (`agent-calc-tools-e665e7`) | `9cff9d5`: format-6 configurations, calculation/reference tools, projection corpus, playbook and exact brief-pin preservation when updating bindings |
| Sampling/estimates (`calc-designs-a2ff2c`, `e10ac24`/`ce45ad0`) | `bd34304`: sampled calculation versions, member run requests, assessed estimates and calculation UI; contract additions combined |
| Model explanations (`model-explanations-0ffefb`, `7f7415c`/`d6148c1` plus unfinished UI) | `9c84fff`, `217f08c`, `56cdf15`, `bd06f7f`: API/tools, canonical exact-version reader, editor, navigation guard, session-fenced reads and stable accessible labels |
| Study answer (`study-answer-fde50a`, `67a40db`/`3d9f087` plus unfinished UI) | `3dacaa8`, `af28911`: API/tools, Overview editor and guard, saved comparison from exact run evaluations, immutable history, refreshed references, paginated run choices, and completed-estimate citation validation |

`073ae7c` finishes formatting of recovered changes and refreshes clean brief/answer readers
when returning to Overview. Unsaved edits stay guarded. Python formatting changes were
checked for identical ASTs; TypeScript changes preserve control semantics apart from the
explicit reader refresh. No newly added source line exceeds the repository's 100-character limit.

## Verification

All commands used `./hyprn-mvp dev check <group>` under the configured locked environment,
with isolated stores. The runner released test scopes and retained evidence. Complete logs,
source snapshots and `verification-index.json` are in the external `hyprn-domain-resume`
scratch directory. The scope identifiers below locate retained `.hyprn-checks` evidence.
No dependency, worker image, live store or running demo was changed.

| Group | Tested commit | Result | Retained check scope |
|---|---|---|---|
| `agent-tools` | `af28911` | 332 passed | `af0e03e5-c6d2-4e93-bb0b-7908045bdfb6` |
| `calculations-api` | `bd34304` | 49 passed | `85a09bb6-9d92-43c0-a455-3e7d62cff8b4` |
| `explanations-api` | `217f08c` | 10 passed | `b8da8e6b-84e4-4336-bef3-ceace5ff5aeb` |
| `ae-authoring` | `bd06f7f` | 80 passed | `7ddfe8dd-b7d2-4c36-811e-df3ed0aa03a7` |
| `study-answer-api` | `af28911` | 18 passed | `8c65d354-7ad8-4769-ab82-64f940e548e0` |
| `locality-contracts` | `af28911` | 162 passed | `28b9220d-a5e4-4521-8f13-5063a808d63d` |
| `guard` | `af28911` | 117 passed | `edf7f978-c089-43ad-ad61-0c5e0ed0c924` |
| `units-guards` | `af28911` | 134 passed | `9e478ccf-ae47-47cd-8653-50d28a9f4929` |
| `calculations-ui` | `af28911` | 4 passed | `684bbb75-04ea-4656-8858-3fb9cfac0046` |
| `ae-ui-model` | `af28911` | 7 passed | `2a7cbb24-216a-4963-91f8-be7d9174798b` |
| `combined-static` | `073ae7c` | 9/9 passed (design, tokens, ownership, UI contract, tooling, smoke, numerical display, TypeScript, build) | `e8e5e413-4500-4311-abf4-7677124804a3` |
| `contracts` | `073ae7c` | 127 passed | `7cd48af3-55e6-4721-b16d-7b7936790f7e` |
| `study-answer-ui` | `073ae7c` | 2 passed | `450a0608-ec0e-42fb-a7d8-61097051cbe4` |
| `brief-ui` | `073ae7c` | 2 passed | `9ba99f98-4051-44c1-85e1-ad7097eccd4a` |
| `style-ratchet` | `073ae7c` | 32 passed, 1 failed (existing tree debt) | `2b528ffd-c866-4c6d-b949-fcc74ff04a84` |

The style tree assertion reports 1,211 findings against its older baseline. Comparing each
reported line/file with the recovery starting commit finds none on newly added lines or files;
these are inherited findings. Full details remain in `delivery-style-ratchet.log` and
`style-issues.json`, without expanding the baseline or reformatting unrelated work.

Earlier evidence was repeated only after integration or a failure invalidated it. Focused
model browser failures exposed exact accessible-label lookup errors (the edited text was
preserved) and a fixture's zero-wait database lock probe racing independent HTTP writes.
Explicit labels fixed the first. The browser-only probe now waits two seconds; unit probes
stay immediate, and holding a write lock across a modeling call still fails.

The final browser journeys cover drafting, exact saved-version reads, cancelled navigation,
comparison cells derived from retained runs, explicit insufficient evidence and fresh brief
choices. Light/dark screenshots are retained with the answer and model browser reports.
Screenshot review caught and verified the clean Overview refresh correction. Automated
browser evidence is not human acceptance. Scientific execution in these fixtures is a declared
transport double; these checks do not establish native numerical accuracy or containment.

## Recovery-era next steps — superseded by the delivery checkpoint

- **M3 exploration owner:** rebuild answer exploration over calculation versions/estimates,
  per alternative and compared. This was explicitly excluded from the recovered answer agent's
  assignment. The recovered estimate owner supports building/assessment; the new figure's
  prediction and presentation journey still needs implementation and native verification.
- **M5 domain integrator:** retire the old modeling approach across API/UI/tools/workflow,
  then reset/recreate the development demonstration through the approved reset path. The
  legacy About/approach projection still exists below the new Overview records until this batch;
  the UI is therefore not presented as the final unified demo.
- **Qualification owner:** retain the earlier missing-image, durable-fixture, licence metadata,
  naming/style and retired-suite failures documented in the configuration migration plan.
  Full qualification and human acceptance are not claimed. No demo deployment or remote push.

Next: M3 answer exploration, followed by M5 retirement and the rebuilt demonstration.

## Current continuation

The exploration figure, active approach retirement and rebuilt native demonstration now have
[delivery evidence](RETIREMENT-CHECKPOINT.md). The preceding recovery-era next-step list records
what was pending at `073ae7c`; it is not the current task queue. Remaining work is limited to the
explicit deferred items in that delivery checkpoint and the inherited qualification debt.
