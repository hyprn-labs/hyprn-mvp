# hyprn-mvp

HYPRN MVP is an engineering-study workbench: studies, modeling approach, models, configurations, runs, evidence and assumptions, built over WhatsOpt (modeling), OpenMDAO (numerical solving) and AiiDA (process and provenance management).

One product repository with **editions**:

- shared core: `application/`, `ui/`, `integration/`, `contracts/`, `modeling/`, `upstream/whatsopt-patches/`, `design-system/`, `deployment/`;
- `editions/local/`: the local edition (installer CLI, local tool server for coding agents, study-folder kit, smoke test);
- `editions/cloud/`: later, created when the cloud work starts.

The edition is chosen by installation configuration; there are no edition branches.

## Target user journey (local edition)

```
git clone <repo> && cd hyprn-mvp
./hyprn-mvp setup
./hyprn-mvp start
./hyprn-mvp study new "My study"
```

Supported: macOS and Linux; Windows through WSL2. No location is hard-coded: setup proposes a per-OS default for each folder and asks when none is safe.

## Layout (target)

```
AGENTS.md  README.md  CONTEXT.md  THIRD_PARTY_NOTICES.md  hyprn-mvp  pyproject.toml  uv.lock
application/ ui/ integration/ contracts/ modeling/ upstream/whatsopt-patches/ design-system/
deployment/            component managers, images, locks, tests
editions/local/        local edition
docs/adr/              decisions governing this repository (MADR)
docs/specs/            current product specifications
docs/architecture/ docs/operations/ docs/agents/ docs/research/ docs/legal/
.claude/skills/        project skills
.planning/             active shared planning (current roadmap only)
```

## Licensing

No licence is granted for this repository yet. The modeling service includes WhatsOpt patches under GNU AGPL v3; their notices and corresponding-source obligations are kept, and a legal review is pending before any cloud or commercial distribution.
