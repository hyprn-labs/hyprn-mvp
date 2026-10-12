---
status: accepted
date: 2026-10-12
decision-makers: Owner
---

# ADR-0001: Repository strategy — two repositories, one product monolith with editions

## Context and Problem Statement

HYPRN MVP needs a portable local installation that any engineer can clone and run on macOS or Linux (Windows through WSL2), a cloud deployment governed through infrastructure code later, and a place for durable decisions that humans and coding agents can find. The question is how to structure and name the repositories, and where the design system, brand, decisions and planning live.

## Decision Drivers

- One cohesive Python application with separately deployed modeling and worker units; no split into services or repositories without a measured trigger.
- Platform authority (cloud identities, infrastructure, environment desired state) separated from product code.
- Local first, cloud later, without forking the product.
- Company-level names stay independent of any one product; a product that may be retired or replaced carries its own name.
- Names encode neither a person nor a partner.
- Current authority is quick to find: short agent instructions, decisions next to the code, the current roadmap only.
- Design tokens and UI rules stay versioned with the screens that use them; brand and marketing assets are not product source.

## Considered Options

- **A:** two repositories, `hyprn-mvp` (product monolith with editions) and `hyprn-platform` (the company's cloud platform: infrastructure and governance).
- **B:** one repository for product and infrastructure.
- **C:** one repository per deployment unit (application, modeling, worker, UI, design system).
- **D:** separate product repositories per edition plus a platform repository.

For names:

- **N1:** the company codename `hyprn` for company-level things, and a product codename for the product repository and everything inside it.
- **N2:** the company codename for the product repository and everything inside it.

## Decision Outcome

Chosen option: **A**. It keeps the cohesive application intact, separates platform authority, and serves local and cloud editions from one codebase. B mixes platform authority with product code, C contradicts the architecture, and D forks the product.

Chosen naming: **N1**. A product codename lets the product be retired or replaced without touching company-level names; N2 ties the company name to one product.

### 1. Repositories and names

| Repository | Owns |
|---|---|
| **`hyprn-mvp`** | The product: application/API, UI, integration (AiiDA bridge, launcher, worker), contracts, WhatsOpt modeling patches, deployment managers, design system, editions, product docs and ADRs |
| **`hyprn-platform`** | The company's cloud platform, able to host this and later products: Terraform, staging and prod environments, cloud identities, repository governance, the deployment contract, host reconciler, runbooks. No product code |

- `hyprn` is the company codename, used for company-level things: the organisation, the domain, the `hyprn-platform` repository and company-wide infrastructure.
- Each product gets its own codename, used for its repository and everything inside it: the CLI, Python packages, the environment prefix, contracts, data and study folders, container and image names, labels and the wordmark.
- The first product's codename is `hyprn-mvp`: the `./hyprn-mvp` command, `hyprn_mvp_*` Python packages, the `HYPRN_MVP_` environment prefix, `hyprn-mvp` data and study folders, `hyprn-mvp-*` container and image names, and the wordmark "HYPRN MVP". It was chosen because the product is a first iteration that may be retired or replaced; a product codename keeps that independent of the company name.
- Names never contain a person or a partner.

### 2. Editions in one product repository

- A **shared core** plus edition directories. `editions/local/` holds local adapters and packaging only: the `./hyprn-mvp` CLI, prerequisite checks, the path policy, OS credential-store and clipboard adapters, the study-folder kit for coding agents, the local MCP relay and the smoke test.
- `editions/cloud/` is created only when the first cloud adapter code exists.
- The edition is chosen by the installation configuration. No edition branches, forks or build flags. Scientific, API and security behaviour is identical in every edition.
- **Cross-platform:** no absolute path in code. Every location is resolved as command-line flag → `HYPRN_MVP_*` environment variable → installation configuration → per-OS default from one path-policy module → otherwise the user is asked and the answer is recorded.

### 3. Design system as an in-repository package

- The design system lives in `hyprn-mvp/design-system/` (tokens, rules, component notes, reference images) and is consumed by `ui/` in the same history as the screens.
- It becomes a separately published package only when a second consumer exists.

### 4. Brand outside git

- Brand and marketing assets live in the company design and document tools, not in git. A single exported asset the product ships (for example a favicon) may be added under `ui/public/` with a provenance note.

### 5. ADRs in git, per governed repository

- Each repository keeps its ADRs in `docs/adr/NNNN-kebab-title.md` using MADR 4: `hyprn-mvp` for product decisions, `hyprn-platform` for platform decisions; decisions spanning both live here.
- Git is the source of truth. The company workspace tool may index ADRs by link but never copies them. Accepted ADRs change only through a superseding ADR.

### 6. Shared `.planning/`

- `hyprn-mvp/.planning/` is committed and shared by humans and agents. It holds the current roadmap only: project, roadmap, state, active plans, checkpoints and review records. Evidence and runtime data never enter git.
- One short `AGENTS.md` per repository is the agent entry point; there is no `CLAUDE.md` (Claude Code and Codex both read `AGENTS.md`).

### Consequences

- Good: the application stays one unit; contracts, UI, design system and decisions change together in one review.
- Good: platform authority can be protected separately without slowing product work.
- Good: one codebase serves local and cloud editions.
- Bad: cross-repository changes (deployment contract ↔ product CI) need pinning discipline once both repositories are active.

### Confirmation

- `editions/cloud/` does not exist until cloud adapter code is added.
- A guard test rejects absolute user-home paths in tracked code.
- `docs/adr/README.md` lists every ADR.
