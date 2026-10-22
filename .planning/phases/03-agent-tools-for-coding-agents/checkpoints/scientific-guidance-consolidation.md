# Scientific engineering guidance consolidation

User-directed batch, 2026-10-15. Implementation and tested tree: `1388d2e`.

The repository skill now connects question framing, physical formulation, source
interpretation, verification, validation, uncertainty and decision depth to actual
HYPRN primitives. Separate references cover primitive operations, scientific
acceptance and stopping, and the primary-source basis (NASA and BIPM/JCGM). A
synthetic pump example distinguishes hydraulic, shaft and electrical power and
exposes an interaction missed by individual perturbations. Nine computational
reasoning scenarios extend the earlier provenance/coherence exercises.

The packaged playbook includes the essential rules through the existing nine
sections and current public tool/resource surfaces. Invalid physics is no longer
described as a calculated infeasible design. Guidance distinguishes current
read-only delegated tools from the separately authorized owner API, and does not
invent writers, an optimizer or an uncertainty engine. No API schema, UI, scientific
record, numerical worker or live installation was changed.

## Verification

Commands ran on `1388d2e` with the existing unrelated ROADMAP edit excluded.

- `./hyprn-mvp dev check agent-tools`: 270 passed, zero failures, 41.05 seconds.
  Existing Starlette/httpx deprecation warning. Includes generated-document freshness,
  all playbook sections through supported surfaces/stages and response-size limits.
  Scope `21f78da8-a8f0-4f98-a154-c868f2869c70`.
- `./hyprn-mvp dev check style-ratchet`: 33 passed, zero failures, 9.15 seconds.
  Scope `b0594793-4028-4568-a6a5-fbb7c6ca7acb`.
- Skill-creator `scripts/quick_validate.py docs/agents/scientific-engineering`, using
  the pinned native environment's Python: `Skill is valid!`, exit 0. This checks
  skill metadata/structure, not scientific behavior.
- `git diff --check`: exit 0. No verification failures or corrective test reruns.

Both completed test scopes were identity-checked, their evidence archived, and
released. External artifact folder `hyprn-scientific-guidance-1388d2e` contains the
scope markers, results/logs and `guidance-sha256.json`. No live study stores touched.
The following checkpoint/state commit changes administrative records only; it does
not change the tested behavioral guidance.

## Boundaries and next action

Maintainer review checked consistency of the guidance and synthetic examples.
No new independent agent behavioral evaluation or live study-authoring trial was
performed. The older nine-exercise result at `5cd430f` remains evidence only for that
revision. The workflow-agent integration owner retains evaluation of the expanded
scenarios and a real supported-client trial. Full release qualification and human
acceptance remain separate.

The skill remains repository-owned, with core rules packaged in `get_playbook`;
it was not installed globally or copied into a study. Scientific coherence correction
of the existing demo remains a separate content task. No push or publication.
