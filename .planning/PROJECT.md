# HYPRN MVP

## What This Is

HYPRN MVP is an engineering feasibility workspace. An engineer states a technical question, writes a Modeling approach, composes a model from Python components connected through quantities with units, saves immutable configurations with explicit inputs and provenance, runs them in an isolated worker, and judges the results with evidence and assumptions in view. Every number traces to the exact model version, inputs and evidence it came from.

HYPRN MVP reuses established tools for the hard parts: WhatsOpt for model composition and native OpenMDAO code generation (a private, replaceable modeling service behind the Modeling Backend Contract), OpenMDAO for numerical computation in the restricted worker, AiiDA for execution lifecycle, retained artifacts and document bytes, and later OpenTURNS for uncertainty. HYPRN MVP owns the study, the API, the UI, access control and the honesty of what is shown.

It is one product with editions. The **local edition** is first: one engineer on one machine (macOS or Linux natively, Windows through WSL2) runs `git clone`, `./hyprn-mvp setup` and `./hyprn-mvp start`. The cloud edition (organisations, workspaces, invited reviewers, an assistant panel) follows later and is operated from the `hyprn-platform` repository.

## Core Value

An engineer can reach a defensible feasibility answer whose every number is reproducible and traceable, without shell or database steps, on their own machine.

## Requirements

The catalogue with stable identifiers and current status lives in `docs/specs/requirements.md`; the specifications in `docs/specs/` hold the normative detail. This file does not duplicate them.

### Validated (delivered in the current product)

- Manual modeling workflow: studies, Modeling approach, Python components, models, connections, units, immutable model versions (HUM-01–03, HUM-05, HUM-09, VER-02, VER-03).
- Configurations, runs through AiiDA in the attested restricted worker, retained history, result-linked inputs, modified runs, computational record exports (RUN-01, RUN-02, RUN-04, RUN-08, OPS-02).
- Local Owner account with secure sessions, CSRF and origin checks; study-scoped authorization; archive and restore (IAM-01, IAM-02, OPS-01).
- UI built from the design system over the public API (UI-01, UI-02).
- Documents wire contracts and native storage of originals (DOC-01, partial).

### Active (milestone: first local release)

- [ ] Repository baseline: one `hyprn-mvp` namespace, clean tree, every must-pass test group green (Phase 1).
- [ ] Local edition install and lifecycle on macOS and Linux with no hard-coded location (OPS-04, IAM-01 setup flow; Phase 2).
- [ ] Agent tools for desktop coding agents: attribution, read tools, local MCP server, confirmed authoring, configurations and runs, evaluation (AGENT-01, AGENT-05–08, UI-04; Phase 3).
- [ ] Source documents: collections, annotations, upload and library, reader, search, citations from evidence (DOC-01; Phase 4).
- [ ] Independent reviews, qualification and the first local release with product-owner acceptance of the UI (SEC-01, ACPT-01 groundwork; Phase 5).

### Out of Scope (this milestone)

- Cloud edition, `editions/cloud/`, staging and production, organisations and workspaces — they need the platform repository and an approved cloud pilot.
- Backup and update commands for installed editions — `uninstall` is the only lifecycle command beyond setup, start and stop; coordinated backup (OPS-03) follows.
- A backlog of architecture decision records for decisions already captured in `docs/specs/` — deferred; ADR-0001 stays the only record.
- Cloud agent bridge, envelope grants, method packages, scientific review records.
- Coupled solves and derivatives, advanced optimization families, uncertainty — required directions with their own scoped phases; typed contract slots stay reserved.
- Authored documents and live co-editing.

## Context

- The product source, specifications (`docs/specs/`), agent documents (`docs/agents/`), legal record (`docs/legal/licensing.md`), design system (`design-system/`) and domain glossary (`CONTEXT.md`) are in the repository. ADR-0001 records the repository strategy.
- The test suite is organised in named groups run by one stdlib runner; groups are must-pass, opt-in or retired, and an absent environment is a failure, never a pass.
- Human acceptance by the product owner and by an engineer who did not implement HYPRN MVP is tracked separately from automated evidence.

## Constraints

- **Science:** real scalars, explicit inputs and provenance, exact pins, no hidden defaults, unavailable is never zero, separate outcome facets, immutable history.
- **Execution:** candidate code only in the current attested restricted worker; saving and validation never import candidate code; the modeling service holds no launcher, socket, AiiDA or application store credentials.
- **Security:** OWASP ASVS Level 1; high findings block a release.
- **Portability:** macOS and Linux natively, Windows through WSL2; no absolute path in code; every location resolved flag → `HYPRN_MVP_*` variable → installation configuration → per-OS default → ask.
- **Data:** live stores, logs and credentials never in the repository or a synced folder.
- **Licences:** new dependencies permissive and reviewed before install; WhatsOpt material stays in the modeling service's AGPL compliance scope; legal review precedes any commercial cloud launch.
- **Design:** screens only from design-system components and tokens; no inline styles, external fonts or URLs.
- **Process:** one numbered task per fresh executor, atomic commits, verified checkpoint before the next task.

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| One product repository with editions; infrastructure in `hyprn-platform` | Keeps the cohesive application intact and separates platform authority | Accepted (ADR-0001) |
| `hyprn-mvp` is the only product namespace (packages, contracts, CLI, env prefix, labels, wire identifiers, wordmark HYPRN MVP) | Product identifiers carry the product codename; names never encode a person or a partner | Phase 1 |
| No compatibility readers for records outside the `hyprn-mvp` namespace | Development run data is discardable; compatibility code would be untested weight | Phase 1 |
| Checkout-mode installs: setup snapshots the committed checkout, builds, attests; start never rebuilds | Every change of executed code passes an explicit, attested step | Phase 2 |
| Pinned acquisition (uv, exact CPython, hash-locked packages, digest-pinned images, SHA-pinned WhatsOpt archive) | Reproducible installs on a clean machine | Phase 2 |
| Local agent clients connect through a stdio relay that reads the OS credential store | Desktop apps do not reliably inherit shell variables; tokens stay out of files | Phase 3 |
| Agent principal and attribution before any agent write | Every agent write must show "{agent} for {user}" | Phase 3 |
| Tool tokens are minted by the CLI only | The UI never displays a minted secret | Phase 3 |
| Documents keep bytes, collections and annotations in AiiDA; identity, scope and citations in HYPRN MVP | No second file or membership store | Phase 4 |
| First release requires independent code, security and UI reviews and a fresh-account install by the product owner | Packaging changes the start path and the supply chain | Phase 5 |
