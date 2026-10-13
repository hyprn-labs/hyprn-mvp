# Phase 5: Qualification and first local release - Context

**Status:** Ready for planning (after Phases 2, 3 and 4)

<domain>
## Phase Boundary

The local edition, with agent tools and documents, is independently reviewed, fixed, fully qualified on macOS and Linux, installed by the product owner on a fresh macOS user account, and then installed as the first and only HYPRN MVP installation on the product owner's machine. The product owner's acceptance of the UI is recorded separately from automated evidence.

In scope:

1. **Independent code review** of every change since the start of the milestone (Phases 1–4), on two axes: standards (`AGENTS.md`, design-system rules, module boundaries, the acyclic import rule) and specification (`docs/specs/`, the phase plans and contexts).
2. **Independent security review** (OWASP ASVS Level 1) with a threat register and `threats_open` count. Mandatory scope: CLI, installation configuration and path policy; owner password generation, storage and clipboard handling; the credential-store adapter; tool tokens, the stdio relay and the `/mcp` endpoint (Origin, Host, token, session, audit, kill switch); agent delegation, the authorization intersection and proposal confirmation; the checkout-mode snapshot, binding and attestation start path; supply-chain acquisition (uv, CPython, packages, gems, npm, base images, WhatsOpt archive); uninstall and purge; document upload, parser containment, downloads and citations; and an independent recheck of the UI access-loss handling (`docs/specs/ui-target.md` §7).
3. **Independent UI review** against `design-system/`, `docs/specs/ui-target.md` and the Documents and agent UI sections: light and dark themes, genuine 200 % zoom, keyboard reach, honest and access-loss states, plain-language copy (`design-system/Naming.md`), the Documents tab, the Assistant proposals page and the attribution chip. Evidence from isolated fixtures; screenshots outside the repository.
4. **Fixes** for every BLOCK and every high finding, each with RED/GREEN evidence; WARN findings triaged with a recorded disposition.
5. **Qualification run** on the final commit, sequentially: every must-pass group (`./hyprn-mvp dev check qualification`), `./hyprn-mvp test`, `./hyprn-mvp dev check clean-room` on macOS and on Linux, the full browser suite, and a run proof that a multi-version model executes exactly the model version snapshot its configuration pinned, on a scratch installation.
6. **Design-system reference images** regenerated from the running local edition into `design-system/reference/`; the `ui-fidelity` group becomes must-pass.
7. **Fresh-account run by the product owner**: a step-by-step checklist (clone, `./hyprn-mvp setup`, `./hyprn-mvp test`, `./hyprn-mvp study new`, connect Codex and Claude Code from the study folder, ask one read-only question, open the UI) executed by the product owner on a standard macOS user account the product owner created; the outcome recorded.
8. **First install** on the product owner's machine, with no other HYPRN MVP installation present: clone, `./hyprn-mvp setup` with defaults or confirmed answers, `start`, `status`, `doctor`, `test`; a handoff record with URL, data root, release id, attestation digest and how to open (`./hyprn-mvp open`).
9. **Product-owner UI acceptance**, recorded separately from automated evidence; requirement statuses updated in `docs/specs/requirements.md`.

Not in this phase: publishing anywhere beyond the local repository, the cloud edition, backup and update commands, new product features.
</domain>

<decisions>
## Decisions

- **D-01** Reviews are independent: the reviewer did not implement the reviewed work. Review records live next to this phase in the planning directory (`phases/05-qualification-and-first-local-release/reviews/`).
- **D-02** A high or critical security finding blocks the release (`security_block_on: high`); the release requires `threats_open` high = 0.
- **D-03** Automated evidence is never human acceptance. The product owner's fresh-account run and UI acceptance are recorded separately and are release gates.
- **D-04** The fresh-account run happens before the first install. Agents never create operating-system accounts; the product owner creates the test account and runs the checklist.
- **D-05** The first install uses the documented defaults or the answers the product owner confirms; nothing is installed half-way: any failed gate stops the install with the scratch state removed.
- **D-06** Cold clean-room builds (30–45 minutes) run once in this phase per OS; later runs reuse content-tagged images.
- **D-07** Only Docker Desktop (macOS) and Docker Engine (Linux) are qualified; other engines stay unqualified.

## Open product decisions (recommended defaults)

- **PD-5.1 Release scope.** Default: the release waits for Phase 4. If Documents does not reach its acceptance, release with the capability advertised unavailable only by an explicit product-owner decision recorded here.
- **PD-5.2 Engineer acceptance (ACPT-01).** Default: the manual journey by an engineer who did not implement HYPRN MVP is scheduled right after the first release and is not a gate for it; ACPT-01 stays `planned`.
- **PD-5.3 Windows through WSL2.** Default: one clean-room run under WSL2 with Docker Desktop is recorded; WSL2 is supported but not a release gate unless that run fails on a product defect.
- **PD-5.4 Requirement statuses after release.** Default: OPS-04 → `delivered`; IAM-01 setup flow delivered; AGENT-01, AGENT-05, AGENT-06, AGENT-07 → `delivered` for the local surface; AGENT-08 → `delivered` for the local clients; UI-04 → `partial` (token panel deferred); DOC-01 → `partial` (steps 14–18 remain); SEC-01 → `delivered` for the local edition, `partial` overall (cloud).
- **PD-5.5 Reference images.** Default: regenerate the design-system reference images at 1440 × 1000 in light and dark from the first qualified build; their provenance note records the build they came from.

## Planner's discretion

- Review checklist formats, the order of the three reviews (they may run in parallel), and how fixes are batched into tasks with disjoint files.
- The fresh-account checklist wording, as long as it follows `docs/operations/install.md` and contains no step the documentation does not describe.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `phases/01-repository-baseline/01-PLAN.md`, `phases/02-local-edition/02-PLAN.md`, the Phase 3 and Phase 4 contexts and plans, and every phase SUMMARY and checkpoint.
- `AGENTS.md`, `docs/specs/architecture-and-contracts.md` (§2 guarantees, §4 trust boundaries, §7 module ownership).
- `docs/specs/agents.md` §10–11 and `docs/agents/tooling-spec.md` §10 (security).
- `docs/specs/documents.md` §16 (security) and §12 (acceptance).
- `docs/specs/ui-target.md` §2, §7; `design-system/README.md`, `Layouts.md`, `Scientific-states.md`, `Naming.md`, `Coherence.md`.
- `docs/operations/` (install, CLI, troubleshooting, uninstall).
- `docs/legal/licensing.md` (notices and corresponding source shipped with the local edition).
- `docs/specs/requirements.md` — SEC-01, OPS-04, UI-02, UI-03, ACPT-01 and the statuses to update.
</canonical_refs>

<code_context>
## Existing Code Insights

- The runner's `qualification` aggregate lists every must-pass group; `clean-room` and `ui-fidelity` are the long or reference-dependent groups.
- `./hyprn-mvp test` and the clean-room harness create and purge throwaway installations; the first install must not reuse their scratch state.
- `./hyprn-mvp doctor` lists resources without this installation's label as foreign; the first install expects none.
</code_context>

<specifics>
## Acceptance (phase level)

- Three review records with dispositions; `threats_open` high = 0; every BLOCK fixed with RED/GREEN evidence.
- A verification record with exact counts per group, failures (none), timings, commit, image and attestation identities.
- The fresh-account checklist outcome recorded by the product owner.
- `./hyprn-mvp status --json` on the first install reports `ready`; `GET /ui/` returns 200 on its origin; the handoff record exists.
- The product owner's UI acceptance recorded, with any accepted deviations listed.
</specifics>

<deferred>
## Deferred Ideas

- ACPT-01 journey by a non-implementing engineer (PD-5.2).
- Qualification of other container engines.
- Backup, restore and update commands; the cloud edition.
</deferred>

---

*Phase: 05-qualification-and-first-local-release*
