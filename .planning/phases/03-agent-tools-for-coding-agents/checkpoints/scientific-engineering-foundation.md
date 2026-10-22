# Scientific engineering foundation — focused authoring checkpoint

Date: 2026-10-14. Scope: the user-requested foundation for scientific and engineering
judgment alongside the Study details cleanup. This is neither runtime integration
nor completion of a Phase 3 agent task.

## Delivered

Commit `b6f2b58b2635b230b7b6bd0c9f73119636bc1332`, based on `7085926`:

- `docs/agents/scientific-engineering/SKILL.md`: question preservation, method versus
  limits, source interpretation, unit ambiguity, discriminating checks, comparison
  design, cost boundaries and conditional conclusions.
- `docs/agents/scientific-engineering/references/behavioral-scenarios.md`: seven
  contrasting reasoning exercises with observable decisions and material failures.

These repository-owned instructions are explicitly not installed, loaded or served.
No API, execution source, dependency pin, generated playbook, client permission or
study-folder distribution changed. The runtime playbook remains authoritative.
Later activation must reconcile the guidance into its single source and evaluate
supported surfaces. Existing demo access exceptions remain scoped to the demo.

Review clarified that tolerances must be physically justified before inspecting
agreement, and that mixed-input comparisons cannot establish separate causal effects
without controlled sensitivities. The seven scenarios received static coverage
review only. No live behavioral evaluation, human acceptance or scientific validation
is claimed. The skill frontmatter and local links were inspected; the external skill
validator was not invoked outside the repository's check entry point.

## Verification

Focused checks through the pinned entry point, after staging the complete content:

| Command | Result |
|---|---|
| `./hyprn-mvp dev check naming` | 9 passed; 0 failures, errors or skips |
| `./hyprn-mvp dev check hygiene` | 5 passed; 0 failures, errors or skips |
| `./hyprn-mvp dev check style-ratchet` | 33 passed; 0 failures, errors or skips |
| `git diff --cached --check` | Exit 0 |
| `python3 -B deployment/tools/term_scan.py` | Exit 0; total 0 |

Two earlier style attempts each reported 4 tests, 1 failure and 2 setup errors
because the new worktree lacked the pinned Prettier installation. Provisioning the
existing lock with `npm --prefix ui ci --offline` resolved the environment problem;
no dependency changed. Initial naming/hygiene attempts passed 9/5 but preceded
staging of new files and do not establish new-file coverage. One initial tool reply
omitted process completion; a second logged invocation was made before the original
scope evidence was recovered. Both attempts and the final successful run are retained.

Nine scoped test folders were identified by their result metadata naming this
worktree, archived and released. No live study, runtime or other worktree scope was
touched. External evidence bundle: `hyprn-scientific-skill-verification`, including
`results.json`, all nine original scope records and complete check logs. Its location
is supplied in the executor handoff, not embedded in portable documentation.

Final scope identities:

- naming: `6c252dc2-fb9d-4e19-a7a8-c11adf9998e2`
- hygiene: `b2b37d6f-0fe3-43c7-a8d2-e91b882642bf`
- style-ratchet: `5a105f1f-f000-482a-a363-d30ccd0e26a5`

SHA-256 identities:

| Artifact | SHA-256 |
|---|---|
| `SKILL.md` | `496af1eec172aec741f08186a8d876a84bf00eaf5aacae1ee9fe99825434db42` |
| `references/behavioral-scenarios.md` | `df9223d8737e617689a79c152ebbd6e51d71ef1fa366dd6736979dc074998654` |
| External `results.json` | `d6d01857d93b11153b30af356cdb2f02d23419435036034e1907fdab2bbb3815` |

The checkpoint is the only later delta to the tested content. The orchestrator owns
committed-tree integration verification. The workflow-agent integration task owns
independent scenario responses, real-client authoring evidence, reconciliation with
the packaged playbook and any later activation. This foundation changes no current
agent behavior and establishes no domain-specific aircraft model qualification.
