# HYPRN MVP UI

The HYPRN MVP web interface: an independently authored React and TypeScript single-page application, built with Vite and served by the application under `/ui/`. It uses only the public HYPRN MVP API (relative `/api/1` requests) and is composed from the HYPRN MVP Foundry design system (`design-system/README.md`, implemented in `ui/src/design`). The interface target is specified in `docs/specs/ui-target.md`.

## What a user does

1. Sign in, then open or create a study from Home. Studies can be archived and restored from Home; they are never deleted.
2. On Overview, read the study question and description and open the modeling approach.
3. In Models, create a model, add components with explicit input and output quantities, edit each component's source, quantities and assumptions, connect output and input ports, and save a model version. The model view shows the Graph or XDSM view, the details of the selection (what it computes, why, assumptions) and the quantities table.
4. In Configurations, create a configuration for a model version: context, explicit input values with units and provenance, optional criteria and assumptions. Blank inputs never mean zero; a model without free inputs says "No inputs required". Saving creates an immutable configuration version. Source or study changes block running until a compatible configuration is saved again.
5. Run the configuration. Runs are listed newest first; failed and incomplete runs stay listed. A run opens on Results (Execution and Criteria, key outputs, the outputs table), with Model, Configuration and Evidence tabs showing exactly what it used and its files.
6. Start a modified run from a finished run: it creates a new editable configuration from the run's configuration and never executes by itself. A changed model must be saved and its compatibility checked before the copied configuration can run.

## Client rules

- The CSRF token stays in memory; the API uses its HttpOnly session cookie.
- Unsaved text stays in browser memory; failed saves keep the draft. Model edits are one revision-checked atomic batch.
- An unknown response keeps the original command and disables new writes until its receipt is checked; nothing silently overwrites a stale revision or retries with a fresh command ID. There is no automatic new run and no continuation of an uncertain process. Reload is a read and asks about unsaved changes.
- Uploaded UTF-8 Python files are kept as exact raw bytes (including BOM and CRLF); unchanged source is never resubmitted by an edit elsewhere. Typing uses the text area's text; a byte-preserving upload is available when original line endings matter. Size and null-character errors name the field and line; backend diagnostics are shown as returned. The editor does not claim complete Python syntax validation, and saving never imports or executes candidate source. Starters leave output equations to the author and contain no hidden physical values.

## Build

Dependencies are installed only after the audit described in `provenance.md`, in a directory outside the source tree and outside synced folders:

```sh
python3 ui/audit_dependencies.py <dependency directory>      # review the full origin and licence report
npm ci --ignore-scripts --no-audit --no-fund                  # inside that directory
```

Link that `node_modules` into `ui/`, then:

```sh
python3 ui/generate_types.py      # contract types from contracts/hyprn-mvp.openapi.yaml
npm --prefix ui run build         # tsc --noEmit && vite build
```

The application image contains the compiled static assets and the runtime notices (`public/THIRD_PARTY_NOTICES.txt`), not Node, the build dependency closure or any native product UI. `/ui` is served by the application with a self-only content security policy; no separate UI server is needed. Rebuilding the served assets goes through the local edition's setup (`./hyprn-mvp setup`), which rebuilds the application image.

## Tests

```sh
npm --prefix ui test -- --project=chromium tests/<spec>.spec.ts
```

Browser tests use Playwright with the installed Google Chrome (no browser download) against a running local installation. They create new synthetic studies through the public API; authoring tests never execute, and run tests submit only their own newly authored runs, which needs the current attested worker. They never open other stores. Each invocation writes screenshots and request evidence to a fresh directory outside the source tree, printed at startup; `HYPRN_MVP_UI_EVIDENCE_ROOT` selects an explicit fresh directory when a later check must read the same journey. Never reuse a finished run's evidence directory. Screenshots are taken after sign-in and full network traces are disabled, so credentials are never recorded; request evidence keeps method and path only. A 720px viewport is an equivalent reflow of a 1440px desktop at 200%, labelled as such; real browser zoom is tested separately. Human observation is a separate gate from automated tests.

## Design system checks

`python3 ui/check_design_system.py` (no new token violations), `python3 ui/design_tokens.py --check` (generated tokens current), `node ui/design_smoke.mjs` and `python3 ui/test_design_tooling.py`. See `design-system/README.md` for what they check.

## UI contract check

`python3 ui/check_ui_contract.py` checks source wiring and the public route and type bindings the screens rely on, and that every named control in `ui/control-map.json` maps to an existing test in its browser spec. It is a source guard: the browser groups that run the specs prove behaviour. Rules for agents working on the UI are in `.claude/skills/hyprn-mvp-ui/SKILL.md`.
