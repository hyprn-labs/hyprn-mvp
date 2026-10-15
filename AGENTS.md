# hyprn-mvp — agent instructions

This is the HYPRN MVP product repository. HYPRN MVP is an engineering feasibility workspace: an engineer states a technical question, builds a model from Python components, runs it on explicit cases and judges what the results are worth, with every number traceable to the exact model, inputs and evidence it came from. One product, several editions: the shared core plus `editions/local/` (local edition, first); `editions/cloud/` appears only with real cloud adapter code. Infrastructure belongs in the separate `hyprn-platform` repository.

This is the only agent instruction file in the repository.

## Read first

| Need | Read |
|---|---|
| Product overview | `docs/product/overview.md` |
| Domain language (binding terms, words to avoid) | `CONTEXT.md` |
| Guarantees, ownership, module boundaries, persistence | `docs/specs/architecture-and-contracts.md`, `contracts/README.md` |
| Requirements and their status | `docs/specs/requirements.md` |
| Documents, agents, UI, workspaces | `docs/specs/*.md`; agent tools `docs/agents/tooling-spec.md`; agent working rules `docs/agents/playbook.md` |
| Design system | `design-system/README.md`, `Layouts.md`, `Scientific-states.md`, then `Naming.md`, `Coherence.md`, `components/` |
| Licences and dependency rules | `docs/legal/licensing.md` and each component's `provenance.md` |
| Decisions | `docs/adr/` (MADR; an accepted record is superseded by a new one, never edited) |
| Current work | the hidden planning directory at the repository root: `PROJECT.md`, `ROADMAP.md`, `STATE.md`, `phases/` |

## Scientific invariants (never weakened)

- Quantities are finite real scalars; non-finite numbers, booleans posing as numbers and unsafe integers are rejected at every boundary.
- Every free input is explicit, with units and provenance. Empty differs from zero. Missing inputs are actionable errors, never filled in.
- Exact pins: configurations pin exact model versions, model versions pin definition versions and source bytes, runs freeze everything they used. Names, tags and collections never pin anything.
- No hidden physical defaults, implicit conversions, broadcasting, randomness or cross-case state. Unsupported settings are rejected, never approximated.
- An unavailable output is never a valid zero: its value is null with a reason.
- Execution, convergence, termination, feasibility, completeness, applicability and criterion outcome stay separate facets. A met criterion is not validity.
- Saved versions and recorded runs never change; historical reads never substitute current content.

## Execution and security

- Candidate model code runs only in the current attested restricted worker (no network, no secrets, bounded resources). A changed runtime, image or worker policy invalidates the attestation; execution is refused without a current one.
- Saving, import, static validation, preview and preparation never import or execute candidate code.
- The modeling service never holds the launcher, the container socket, the AiiDA profile, the application database or provider credentials.
- Each store has exactly one writer. An uncertain or ambiguous launch is reconciled by lookup and never re-dispatched automatically.
- OWASP ASVS Level 1 applies; high-severity findings block a release. Every API change keeps the contract tests and the UI contract checker green.

## Architecture and ownership

- One cohesive Python application (`hyprn_mvp_app`) owns the API, auth, studies, configurations, evidence, assessments and execution integration; the modeling service and the restricted worker are separate deployment units. Execution integration is `hyprn_mvp_integration`; the local edition CLI is `hyprn_mvp_local`.
- Every client (UI, agents, CLI) uses the public HYPRN MVP API (`contracts/hyprn-mvp.openapi.yaml`). No client receives native modeling payloads.
- WhatsOpt is the private, replaceable modeling service behind the versioned Modeling Backend Contract. OpenMDAO owns numerical iteration, AiiDA owns processes and artifacts, OpenTURNS comes later for uncertainty.
- Never add a second editable model graph, a distributed transaction, a custom scheduler or provenance platform, or copied WhatsOpt product UI or application code. UI code is written from `docs/specs/ui-target.md` and the public contracts only.
- The application import graph stays acyclic; the module-boundary test pins it.

## Locations and data

- No absolute path in code. Every location resolves as: command-line flag → `HYPRN_MVP_*` environment variable → installation configuration → per-OS default from the single path-policy module → otherwise ask the user and record the answer. Never invent a path.
- Live stores, logs, scratch folders, evidence and credentials never go in this repository or in a cloud-synced folder.
- Tests run only in scoped scratch stores created by the fixtures and released afterwards, never against a user installation.
- Development run data is discardable; authoring records are never deleted for convenience.

## Dependencies and licences

- Before installing any new dependency, record its official source, exact version, hash and licence. New dependencies must have permissive licences. Raise any provenance or licence conflict for review before extraction, vendoring or distribution.
- WhatsOpt patches, templates and generated-code questions stay inside the modeling service's AGPL compliance scope; their notices and corresponding-source records are kept.

## Design system and UI

- Before UI work read `design-system/README.md`, `Layouts.md` and `Scientific-states.md`; the UI skill under `.claude/skills/` restates the rules.
- Build screens only from `ui/src/design` components. Colours, sizes, spacing, radii and type come only from tokens (`design-system/tokens.json`, generated into `ui/src/design/tokens.css`; never hand-edit the generated file).
- [Contour](design-system/Contour.md) is the current visual amendment: audited self-hosted Manrope, shared curvature and tonal elevation. Scientific, accessibility and ownership guarantees remain binding.
- No inline styles, runtime remote fonts, external URLs or CDNs. Status is shape + word + colour. Blank is "unassigned", missing output is "not computed", zero is an explicit value.
- Run `python3 ui/check_design_system.py` (no FAIL line) and `python3 ui/design_tokens.py --check`. Screenshots and other evidence stay outside the repository.
- Automated browser evidence is never human acceptance; record the two separately.

## How work is done

- Phases are planned with `plan-phase` and executed with `execute-phase`. One numbered task per fresh executor context.
- Each task ends with atomic commits that stage explicit paths only (never `git add -A` or `git add .`) and a checkpoint file next to its plan: commits, exact commands with pass and fail counts, every failure, source and artifact identities, scratch scopes released, remaining risks.
- The orchestrating session reruns the task's acceptance commands on the committed tree and verifies the checkpoint before it dispatches the next task. Tasks run in parallel only when their file sets are disjoint.
- Never stage, stash, revert or reformat another task's files. Preserve unrelated work.
- Comments and test names state the invariant they protect, not the work item that introduced them.

## Running checks

Every check runs through the local edition entry point:

    ./hyprn-mvp dev check <group>
    ./hyprn-mvp dev check --list [--class must-pass|opt-in]
    ./hyprn-mvp dev check qualification [--jobs N]

- `./hyprn-mvp` acquires the pinned uv, lets it provision the pinned CPython (both pinned with their hashes in `deployment/locks/tools.json`) and the locked environments of `uv.lock`, and runs the test-group runner `deployment/checks.py` in the locked native environment. A group run under any other interpreter is refused; do not call the runner directly.
- `qualification` is the phase gate: every must-pass group, each in its own scope, at most `--jobs` at once (default 3; `--jobs 1` runs them one after the other). Groups that depend on one another or share a fixed resource are serialized, as the runner documents. After a failure no group starts; results are printed in gate order with their seconds and counts.
- Groups are defined in the runner. A missing target, fixture or environment fails a group; it never passes or silently skips.
- Development variables (values are specific to the development host and never written into the repository; `deployment/local_paths.py` documents the location variables):
  - `HYPRN_MVP_DATA_ROOT` (required): the development data root, outside the repository and outside any synced folder. It holds the reviewed native dependency inventory, durable test fixtures and the verified upstream archive cache.
  - `HYPRN_MVP_TOOLS_DIR`: the tool cache for uv, CPython and the locked environments; default per operating system.
  - `HYPRN_MVP_SCRATCH_ROOT`: the folder that holds scoped test folders; default the operating system's temporary folder. The durable-fixture groups and `units-native` use the dedicated scratch folder inside the data root.
  - `HYPRN_MVP_ENGINE_IMAGE`, `HYPRN_MVP_MODELING_SOURCE_IMAGE`: the reviewed base image ids that native builds start from.
  - `HYPRN_MVP_LIVE_ROOTS`, `HYPRN_MVP_LIVE_PORTS`, `HYPRN_MVP_LIVE_NAMES`: folders, ports and Docker names of other installations on the same host that tests must never touch.
  - `HYPRN_MVP_CHROMIUM`: the Chromium executable for browser groups, when Playwright's own is not used.
  - `HYPRN_MVP_TERM_SCAN_FILES`: the term pattern files for `python3 -B deployment/tools/term_scan.py`, supplied by the development environment and never committed.
- Native groups need Docker; browser groups need Node and Playwright on the development host.
- Design checks: `python3 ui/check_design_system.py`, `python3 ui/design_tokens.py --check`, `python3 ui/test_design_tooling.py`, `node ui/design_smoke.mjs`.
- UI build: `npm --prefix ui ci && npm --prefix ui run build`.
