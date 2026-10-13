# HYPRN MVP overview

## What it is

HYPRN MVP is an engineering feasibility workspace. An engineer states a technical question, builds a computational model from Python components, runs it on explicit cases and judges what the results are worth, with every number traceable to the exact model, inputs and evidence it came from.

HYPRN MVP reuses established open tools for the hard parts: WhatsOpt for model composition and code generation (behind a private, replaceable modeling service), OpenMDAO for numerical computation, AiiDA for execution lifecycle and retained records, and later OpenTURNS for uncertainty. HYPRN MVP owns the study, the API, the user interface, access control and the honesty of what is shown.

## Who it is for

Engineers and engineering teams who assess technical ideas early: is a concept feasible, which option is better, what would have to be true for it to work. They need models they can read and change, results they can reproduce, and a record a reviewer can check. A non-implementing engineer must be able to do all of this without shell or database steps and without needing an agent.

## The study workflow

| Step | What the engineer does |
|---|---|
| Question | States the study question, context, scope and limits. |
| Modeling approach | Explains the method: steps, choices, assumptions, evidence and the cases to examine. |
| Model | Composes Python components connected through quantities with meanings and units; views it as a graph or an XDSM diagram; saves immutable model versions. |
| Configurations | Specifies a case: an exact model version, explicit inputs with units and provenance, and criteria the outputs are checked against. Saved configurations never change. |
| Runs | Executes a configuration in an isolated worker; the run keeps exactly what it used and what it produced, including failures. |
| Evidence and assumptions | Attaches sources and assumptions where they apply, and sees every current assumption with its evidence in one place. |
| Conclusion | Answers the question, with each claim marked as computed, sourced or judgement and linked to the runs and evidence behind it. |

Any earlier run can be reopened unchanged, even after the model was edited or the modeling service is unavailable.

## Guarantees

- **Nothing is invented.** Every free input is supplied explicitly with its units and origin. There are no hidden defaults, and an empty value is never treated as zero.
- **Missing is not zero.** An output that was not computed is shown as not computed, with the reason.
- **Outcomes are not merged.** Whether the run executed, whether criteria were met and whether the model is applicable are separate facts. A met criterion does not prove the model is right.
- **History does not change.** Saved versions and recorded runs are immutable; history never shows today's model in place of what was used.
- **Model code runs only in a contained worker** with no network, no secrets and bounded resources. Saving, validating and previewing never execute it.
- **Studies are archived, never deleted.**
- **One API for everyone.** The UI, agents and any other client use the same API with the same checks.
- **One outcome per operation.** An operation produces one authoritative outcome that every client can later reference, inspect and act upon, without reconstructing or repeating the operation.

## Editions

HYPRN MVP is one product with two editions over the same core; the installation configuration chooses the edition.

- **Local edition (first).** One engineer on one machine (macOS or Linux; Windows through WSL2): clone the repository, run `./hyprn-mvp setup` and `./hyprn-mvp start`. All data lives in a local data folder outside the source checkout and outside cloud-synced folders. One Owner account with a generated password.
- **Cloud edition (later).** Organisations, user-owned workspaces, invited Reviewers, single sign-on and a built-in assistant, operated from the `hyprn-platform` repository.

## Agent assistance

Agents are users of HYPRN MVP, not its developers. They act for a person, never with more authority than that person, and reach HYPRN MVP only through a curated set of typed tools that call the same API as the UI.

- **Local:** a desktop coding agent (Codex or Claude Code) works on one study through the local MCP tool server, from a study folder outside the source repository, with a short-lived per-study token.
- **Cloud:** a provider-managed agent works in an assistant panel; HYPRN MVP executes its tool calls and the provider holds no HYPRN MVP credential.
- **Writes:** agents create studies, versions, evidence, configurations, runs and (later) scientific reviews directly, within the person's authority; every write is attributed to the agent acting for that person and listed for them in HYPRN MVP, and a review an agent records is labelled as such. Agents may change or remove draft material, but never delete saved work, archive or restore anything, or change who has access (ADR-0003).

## Roadmap horizon

| Horizon | Content |
|---|---|
| Now | Manual modeling workflow: studies, modeling approach, models, configurations, runs, evidence and assumptions, archive and restore. |
| Next | Local edition packaging (`./hyprn-mvp setup` / `start`); agent tools for the local edition (read-only first, then attributed authoring); source documents (upload, collections, reading, search, annotation, exact citations). |
| Later | Cloud edition with workspaces, identity and the assistant panel; conclusion records and typed provenance; coupled solves and derivatives; uncertainty; method packages and scientific reviews; selected optimization families. |

## Further reading

- Architecture and contracts: `docs/specs/architecture-and-contracts.md`
- Requirements and status: `docs/specs/requirements.md`
- Documents: `docs/specs/documents.md`
- Agents: `docs/specs/agents.md`, `docs/agents/tooling-spec.md`, `docs/agents/playbook.md`
- Workspaces, identity and onboarding: `docs/specs/workspaces-identity-onboarding.md`
- User interface: `docs/specs/ui-target.md`
- Licensing: `docs/legal/licensing.md`
