# Generic authoring friction follow-up

Scope: sampled configuration names, surrogate read projection and canonical authoring
instructions, plus the reproduced answer diagnostic. No live records were changed.
Owner: authoring executor. Parent owns integration, provider packaging and staging.

## Changes

- New sampled configurations use the analysis name and deterministic Point N suffix
  (bounded to the existing name limit). Reused configurations retain their exact
  snapshots and names. Numerical replay identity stays unchanged so a partially
  completed older sampling command reuses already saved points.
- `get_surrogate.groups[].sample_roles` separates reserved training, held-out pool,
  method selection and independent validation. Actual assessed/unavailable counts
  remain per-output metrics. This projects the qualified fitter's existing first
  held-out point policy; it changes no numerical partition, fitting or accuracy target.
- Canonical playbook and `/hyprn` references require human quantity labels, intended
  criterion bindings before launch (including answer exploration), and clear counts.
  Analyses serving other purposes need not bind unrelated criteria.
- Reproduced the misleading answer error using synthetic schema3 content with valid
  `monetary_basis: null`: removing only `outcome.alternative_id` made the old envelope
  branch blame the monetary field. Diagnostic branch selection now follows explicit
  nested `schema_version` constraints. Accepted schemas and validation are unchanged.

## Verification and limitations

Pinned commands use the existing development data/tool roots and explicit 20 GiB
build-cache allowance; tests use runner-owned isolated stores. Logs below are outside
the repository. No candidate model code, cloud service or user installation was run.

- Initial locality command could not access the sandboxed tool cache; no tests ran.
- `./hyprn-mvp dev check locality-contracts` red: 162 passed / 4 failed, 11.22 s.
  One failure reproduced the false monetary diagnostic. Three native static closure
  failures came from the parallel native helper change before inventory registration.
  Log: `/private/tmp/hyprn-authoring-locality-red.log`.
- `./hyprn-mvp dev check calculations-api`: 83 passed, 57.20 s; exit 0 and storage
  cleanup exit 0. Generated names, unchanged values/pins, retained version behavior
  and interrupted older-command replay exercised through the real app owners/API.
  Log: `/private/tmp/hyprn-authoring-calculations.log`.
- Locality rerun: 162 passed / 4 failed, 10.95 s. The new diagnostic regression passed.
  All four remaining failures were native static inventory numeric expectations
  (56 vs 55, 44 vs 43, 58 vs 57); native owner notified. Parent must run the integrated
  group after that owner's correction. Log: `/private/tmp/hyprn-authoring-locality-green.log`.
- `./hyprn-mvp dev check agent-tools`: first run 329 passed / 1 failed, 46.46 s.
  Existing monetary preview fixture advertised/requested model format 5 but returned
  its unchanged format-4 draft; the production exact-format response guard correctly
  refused it. Corrected only the modeling double's negotiated response format and
  added an informative failure assertion. No monetary production behavior changed.
  Log: `/private/tmp/hyprn-authoring-agent-tools.log`.
- Agent-tool rerun after the fixture correction: **330 passed**, 50.00 s; exit 0 and
  storage cleanup exit 0. Read projection preserves per-output metrics independently
  of reserved counts; generated playbook and bundled skill references pass.
  Log: `/private/tmp/hyprn-authoring-agent-tools-green.log`.
- `git diff --check` on owned paths passed. Generated `docs/agents/playbook.md`
  regenerated from its sole source; changed Python lines fit the style limit.

No OpenAPI schema or input shape changes. Tool descriptions and a field description
change the provider definition fingerprint; the new read projection adds sample_roles.
The parent must provision/adopt the exact committed tool definitions and native skill
bundle. `/hyprn` on this host links to the canonical repository skill. No live provider
or deployment was touched by this executor. Broad release qualification and public
Assistant behavior remain parent-owned; these scoped checks do not prove them.
