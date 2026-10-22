# Contour engineering mapping — research and C2/C3 handoff

## User Constraints (from CONTEXT.md)

The following decisions, discretion and deferred scope are copied verbatim from the lane context. This is a supplemental mapping note; the canonical lane research and task plan remain with their existing owner.

### Locked decisions

- **D-01 — Contour direction.** Build a complete, independently authored HYPRN visual language: premium interface typography, proportional controls, sophisticated curves, subtle texture and visible surface depth. Apply it to workspace UX, navigation, cards, settings, workflow wayfinding and contextual panels, not just the opening screen.
- **D-02 — Shared ownership.** Tokens and `ui/src/design` own reusable recipes and composites. Screens select variants and arrange content; they do not restyle component internals. Complete the existing component vocabulary as well as new composites.
- **D-03 — Typography and provenance.** Self-host the already reviewed Manrope variable font with its exact original OFL licence, revision and hashes. Keep numerical values, units, identifiers and source code in the existing tabular monospace roles. Preserve the supplied logo byte-for-byte. No runtime remote fonts, copied product source, copied visual assets or external inspiration names. Font authorship/licence attribution remains truthful.
- **D-04 — Narrow visual-rule amendment.** This user direction supersedes system-font-only, machined corners, flat two-layer surfaces, no panel shadows and blanket gradient prohibition only for this design-system evolution. Record the amendment beside authoritative rules, reconcile contradictory descriptions and the local UI skill, and retain self-only CSP, no inline styles, semantic colours, explicit focus, scientific-state wording and shared ownership.
- **D-05 — Truthful product scope.** Adopt the full vocabulary in real available UI: Home/Studies, Profile, study navigation, Overview/Cases, models and inspector, configurations, runs, evidence and agent attribution. Agent activity is described in upstream docs but has no implemented entrypoint on this base; preserve that existing separate obligation. Settings composites display the existing Profile account/sign-out capability and local presentation theme preference; do not invent a settings backend, workspace entity, collaboration, onboarding or job scheduler. Workflow navigation is existing section/record navigation, never a fabricated completion score or scientific approval.
- **D-06 — Scientific boundaries.** Preserve public API wiring, exact URLs and version pins, guards, drafts, source text, assertions and their evidence, outcome facets, graph coordinates/data geometry and exported diagram palette. Change no scientific API, execution, store, model or exploration logic. Missing values stay explicit, zero remains zero and record views remain read-only.
- **D-07 — Verification and delivery.** Three cohesive sequential numbered tasks, each a fresh executor, explicit atomic commits and a compact checkpoint; parent reruns required acceptance on each committed task before the next. All checks use `./hyprn-mvp dev check`. Include build/design/tokens/ownership, visual geometry, keyboard/reduced motion, desktop/mobile/genuine 200% zoom, both themes, real workflow navigation, evidence and record-guard regressions. Keep full qualification and genuine human acceptance explicit.
- **D-08 — Independent lane.** Preserve unrelated changes. Parent owns active AnswerExplorer and numerical work; this lane owns shared design and presentation only. Review overlap in shared tokens, Foundry styles, specimen and study shells before integration. Parent owns external HTML proposals; repository implementation must not depend on those files remaining available.
- **D-09 — Workspace composition.** Adapt the requested interaction model to HYPRN: persistent left navigation, central working canvas and contextual side panel for scientific statements, evidence and record details, alongside an assistant pane. This is a real workspace composition requirement, not a theme-only change. On small/zoomed screens provide a reachable drawer or stacked alternative with safe focus and close behavior.
- **D-10 — Claims and evidence.** Scientific statements are assumptions, inferences and conclusions supported or challenged by exact evidence and runs. They are not evidence themselves. Selecting a statement opens its existing meaning, limits, supporting/challenging sources, exact record identity and real related-record links in the shared contextual panel. Do not invent a persisted Claim entity, new API or scientific assessment. Preserve source relationship wording and unavailable reasons.
- **D-11 — Assistant integration.** Provide a shared adjacent assistant-pane/slot contract with explicit connection/capability state. If the separately owned assistant implementation is absent, show a truthful unavailable/not-connected state and no enabled fake send action. Parent owns backend/assistant integration and the explicitly simulated external chat proposal. No local chat transcript may masquerade as scientific history or an authoritative result.

### Discretion

Use neutral tonal depth, restrained gradients and noninteractive CSS texture in shell/panel chrome; keep reading surfaces and charts quiet. Start with the candidate's 12px control, 24px card and 32px outer-shell curvature and Manrope 200–800; define complete token recipes and adjust only to preserve control fit, scientific density and accessibility. Maintain compact 28px, standard 36px and touch 48px control minimums; wrapped labels grow. Study section labels and canonical entity homes remain unchanged. Persist a theme preference only as a browser presentation preference, never scientific state. The central canvas is the current study/model/record working area, not a second editable model graph.

### Deferred / separately owned

- New workspace/account/settings APIs, onboarding, collaboration and numerical workflow capabilities are outside this lane.
- Active answer-exploration implementation and assistant lane integration belong to their existing owners.
- Parent produces the external HTML proposals using the same design vocabulary; these are review artifacts, not product capabilities or scientific evidence.
- Full release qualification, existing cross-host obligations and genuine human acceptance remain mandatory under their existing owners; a design demo is not a qualified release.

## Summary

The complete [Engineering pattern map](../../../../design-system/Engineering-pattern-map.md) defines 58 numbered families and their HYPRN disposition: 19 Present, 28 Adapt now, 7 Future and 4 Not applicable. The coverage inventory is 10 foundations, 27 controls/content components, 17 composites and 4 communication families; engineering supplements add units, fidelity, criteria, exploration, uncertainty, history, review and collaboration. Counts were checked against all numbered rows; no family is silently omitted. [VERIFIED: design-system/Engineering-pattern-map.md, numbered rows 01–58]

The key implementation recommendation is to compose a statement reader from existing assertions/evidence and an ephemeral contextual navigation stack. The scientific record remains at its existing owner. The current assumption link has the exact values `"supports"`, `"challenges"`, `"context"`; the current answer basis names `"configuration_revision_ids"`, `"run_ids"`, `"evidence_version_ids"`, `"case_answer_version_ids"`. These are different association granularities, not interchangeable claim schemas. [VERIFIED: contracts/hyprn-mvp.openapi.yaml:22083-22103; contracts/hyprn-mvp.openapi.yaml:61345-61395]

The first observable C2 outcome should be: select an existing assumption, read its complete statement and correctly related evidence beside the working area, open that evidence directly, then return without losing selection or draft state. Add the adjacent assistant's truthful capability state and the local appearance setting in the same established shell. This is a planning recommendation within D-09–D-11, not a report of implementation or acceptance. [CITED: lane CONTEXT.md, D-05–D-11]

## Project Constraints (from AGENTS.md)

Applicable directives, retained as plan constraints: [CITED: AGENTS.md]

- Read domain language, architecture/contracts, requirements, current planning and the design rules before changes. Use one domain term per concept.
- Preserve explicit finite scalar inputs, units and provenance; no hidden defaults or conversion, unsafe numbers, cross-case state or missing-as-zero display.
- Saved versions and runs remain immutable, exact pins remain exact, and historical views never substitute current content. Execution, criteria and scientific judgment remain separate.
- Candidate execution stays in the currently attested restricted worker. Saving, importing, previewing and validation never execute candidate source. Modeling cannot acquire application/executor credentials or stores.
- Every client uses the public API; retain one writer per store, canonical operation outcomes and lookup reconciliation for uncertain launches. No second editable graph, scheduler, provenance platform or application import cycle.
- Keep all locations under the existing path policy; no host-specific absolute paths in product code, live stores or screenshots in the repository, or tests against user installations.
- New dependencies need official source, exact version, hash and permissive licence before installation. Preserve modelling-service licence boundaries and notices. This mapping requests no new package.
- Use shared design exports and tokens; never hand-edit generated tokens. Keep semantic colour, shape plus word, safe focus, self-only content policy, independently authored glyphs and existing brand bytes.
- The authorized Contour amendment permits self-hosted reviewed type, curvature, restrained chrome gradients, texture and depth; it does not waive scientific, access or source-provenance rules.
- Use numbered planned/executed tasks with explicit file ownership and atomic path-only staging. Preserve all unrelated work and index entries.
- Each implementing task records commits, commands/counts/failures, source/artifact identities, scratch cleanup and risks; the parent verifies committed-tree acceptance before the next task. Parallel work requires disjoint files and uncontested resources.
- Every project check runs through `./hyprn-mvp dev check`; required build/design/token/ownership/UI contract and final qualification remain. Automated evidence, human acceptance and deployment are separate.

The UI skill was read and applied to this mapping: shared-component ownership, native control semantics, both themes, genuine zoom, exact API behavior and external evidence storage remain requirements. [CITED: .claude/skills/hyprn-mvp-ui/SKILL.md]

## Architectural Responsibility Map

| Capability | Primary owner | Secondary owner | Planning decision |
|---|---|---|---|
| Shell, navigation layout, contextual panel, focus/back state | Browser presentation | Existing guarded workspace callbacks | Compose slots; do not move scientific authority into the shell. |
| Statements, evidence relationships, answer basis | Existing application/model record owner, according to resource | UI read projection | Preserve actual owner/version; no new Claim store or schema. |
| Saved run results and historical inputs | Existing execution integration and retained records | Public application read API | Open canonical records, never recompute or replace with current drafts. |
| Assistant conversation | Separately owned assistant client/runtime | Public API tools within authority | A pane supplies a slot and explicit capability state only. |
| Numerical exploration/uncertainty | Separately owned numerical capability | UI renders returned data | Styling cannot create sample distributions, confidence bands or fit scores. |
| Local appearance | Browser preference | Shared theme tokens | Presentation only; no scientific or account mutation. |

This responsibility split follows the application's distinction between domain, execution and interaction state. [CITED: docs/specs/architecture-and-contracts.md:64-114]

## Standard Stack and Package Legitimacy

Reuse the existing UI and public contract. The source manifest declares `"react": "19.3.0"`, `"react-dom": "19.3.0"`, `"typescript": "5.9.3"` and `"playwright": "1.62.1"`. These are observed repository pins, not registry freshness or package-legitimacy claims. No new install, external component package, icon/font library, chart package or schema is recommended. [VERIFIED: ui/package.json:1-9]

Shared component source already exposes `Assertion`, `AssertionList`, `EvidenceStack`, `ReadingSection`, `ReadingStack`, `ActionGroup`. Proposed ClaimCard and ClaimButton should compose those and existing buttons/readers. [VERIFIED: ui/src/design/compositions.tsx:6-44]

Package-legitimacy gate: not triggered by this documentation-only mapping, which requests no package installation. If implementation adds a package, the existing provenance/licence gate applies before install. [CITED: AGENTS.md, Dependencies and licences]

## Architecture Patterns and Contract Findings

| Finding | Evidence | Consequence for C2 |
|---|---|---|
| An assumption has an identity, statement and typed evidence links. | Exact properties `"assumption_id"`, `"statement"`, `"evidence_links"`; relationships `"supports"`, `"challenges"`, `"context"`. [VERIFIED: contracts/hyprn-mvp.openapi.yaml:22083-22103;22167-22199] | An actual assumption collection can supply a real statement count. Count stable owner/version/item tuples, not evidence links. |
| Approach links can carry a text locator. | Exact property `"locator"` with a string schema; it is not required in the link's required list. [VERIFIED: contracts/hyprn-mvp.openapi.yaml:25636-25663] | A locator string is not proof of authenticated document bytes or a parsed passage. Display its actual meaning; never fabricate page/offset authority. |
| Scientific answers expose prose and an answer-wide basis. | Exact fields `"observations"`, `"interpretation"`, `"qualifications"`, `"open_deliverables"`, `"basis"`; the closed basis properties are quoted in Summary. [VERIFIED: contracts/hyprn-mvp.openapi.yaml:61311-61395] | Use a named answer-basis reader. Do not split sentences into allegedly recorded claims or assign each basis source to each sentence. |
| Evidence display resolves exact versions and can show content and references. | Reader uses `evidence_version_id`, `record.content`, `inspected.content`, `inspected.source_refs`; saved callers don't enable library discovery implicitly. [VERIFIED: ui/src/EvidenceView.tsx:14-33;81-100;125-168] | Reuse the reader in the same contextual stack. If source text/locator is absent, show evidence content and an explicit passage-unavailable state. |
| Current direct evidence access is an explicit design invariant. | Each attached evidence record has its own View evidence, and aggregation must not add an intermediate evidence dialog. [CITED: design-system/Coherence.md, rule 3] | Claims count is additional statement navigation, not replacement evidence navigation. Keep direct-source action zero extra mandatory clicks. |
| Record comparison uses identities and preserves different contexts. | Comparison reads components, definitions, ports/units, connections, inputs, criteria, evidence scopes and numerical context. [CITED: ui/src/ComparisonView.tsx:19-48] | Style existing comparison; do not add an option rank, scientific equivalence, or preferred model from a diff. |
| Evidence and answer readers clear/invalidate state on identity or authority changes. | Existing request generation/session handling and exact-version reads. [CITED: ui/src/ApproachFindings.tsx:170-220; ui/src/EvidenceView.tsx:34-99] | New context stack must preserve the same fences, abort pending reads and clear protected content on access loss. |
| Existing Profile is account display and sign-out. | Exact displayed labels `Profile`, `Account name:`, `Sign out`. [VERIFIED: ui/src/Workspace.tsx:672-696] | Add presentation theme only; no workspace/account settings backend. |
| Registry owns which views are offered and how guards operate. | Registry selection and guard composition come from view entries. [CITED: ui/src/views/registry.ts:224-280] | Pass real destinations and existing callbacks into shell composites. No independent route parsing or dirty-state bypass. |

### Presentation example

Existing shared composition is sufficient for the body shape; the caller still owns the statement and evidence resolution:

```tsx
<Assertion statement={statement}>
  <EvidenceStack>{evidenceContent}</EvidenceStack>
</Assertion>
```

Here `statement` and `evidenceContent` are illustrative local variable names, not new record properties. The existing component accepts a `statement` prop and children; the evidence stack accepts ordinary container props. [VERIFIED: ui/src/design/compositions.tsx:6-27]

## Don't Hand-Roll

- Do not parse prose into a new authoritative claim store. Use the actual assumption/finding/answer owner and declare association granularity honestly. [CITED: contracts/hyprn-mvp.openapi.yaml, assumption and scientific answer schemas]
- Do not build a parallel navigation/guard controller or data-fetching design component. Use existing workspace registry, guarded callbacks and canonical readers. [CITED: ui/src/views/registry.ts; design-system/Coherence.md]
- Do not implement a numeric confidence/fit/authority score or invent uncertainty from a range of sources. Render actual criteria/outcomes and explicitly supported numerical methods. [CITED: design-system/Scientific-states.md; docs/specs/architecture-and-contracts.md]
- Do not create an assistant transcript/history authority in the design lane. The assistant owner supplies integration; current lane exposes capability state and slots. [CITED: lane CONTEXT.md, D-11]
- Do not replace native modal/focus behavior with ad hoc floating divs or inject rich source text as HTML. Keep the existing shared primitives and text-rendering boundary. [CITED: ui/src/design/primitives.tsx:57-79; lane 03-01-PLAN.md, threat model]

## Required C2 Additions

These are concrete amendments for the parent to incorporate in task ownership and acceptance; this researcher changes no plan/state or implementation.

Latest parent-relayed user direction places Overview content in this order: question → generic exploration canvas → interpretation/still-to-answer. Methods keep their canonical Model owner. Apply this direction when reconciling older Overview/method descriptions; do not use the catalogue to create a competing method composition or edit the separately owned numerical feature. [CITED: parent steering in this research session, 2026-10-15]

1. Name proposed **ClaimCard** and **ClaimButton** in shared ownership, with real consumers over existing assertion sets. Their public presentation props must not create a persisted Claim entity.
2. Count distinct statement identities in explicit passage or section scope. Missing passage association uses a clearly named answer-wide basis action. Verify duplicate sources, shared statements, same words under different owners, empty and partial sets.
3. Preserve each direct View evidence action. Reconcile the claims-versus-evidence distinction beside Coherence/Assertion documentation without adding a mandatory aggregate step.
4. Specify one contextual stack: statement set → statement/evidence content → Back, keeping selected item/group, filter, scroll, focus and exact record context. Use stored source text/locator when available; otherwise label evidence content or unavailable passage honestly.
5. Keep supported/challenged/context relationships and run/configuration/case-answer links at their true scope; retain complete text and conditions. No confidence, authority, recency or source-count truth heuristics.
6. Compose assistant and reader safely around the central canvas; prove narrow/zoom focus and close behavior. Disconnected assistant has no fake send/messages; parent owns integration.
7. Extend card/settings/list/navigation adoption with real records only. Keep Profile account/sign-out plus local theme, actual section navigation, and numerical exploration untouched.

These recommendations implement the authorized lane decisions; they are not additional backend requirements or new approval gates. [CITED: lane CONTEXT.md, D-05–D-11]

## Required C3 Additions and Validation Architecture

The catalogue's 58 families and all existing shared exports need a disposition, owner and state/consumer coverage row. Future/Not applicable rows count as documented scope, not implemented component coverage. The engineering supplements are mandatory semantic checks, not decorative examples. [CITED: Engineering-pattern-map.md, complete catalogue and engineering supplements; lane 03-01-PLAN.md, C3]

| Acceptance | Required check |
|---|---|
| Counts and relationships | Two statements with many evidence links still count two; challenge and context stay distinct; answer-wide basis is never passage support. |
| Direct source and stack return | Existing direct evidence action adds no mandatory intermediate click; Back restores scope, selected statement/group, scroll and focus. |
| Long/partial/unavailable content | Complete statement text, explicit partial coverage, missing source reason, no false zero and no invented quotation. |
| Authority and history | Denied/session-changed content clears; stale reads cannot populate a new context; historical pins remain unchanged. |
| Layout and accessibility | Day/Control room, mobile, genuine 200% zoom, keyboard, reduced motion; hidden panes non-focusable and controls reachable. |
| Scientific invariants | Zero/unassigned/uncomputed distinct; units, exact source text, estimated/calculated values, criterion facets and graph geometry unchanged. |
| Real public journey | Use served isolated API boundary for record/evidence reads and auth/CSP integration; browser doubles remain limited evidence. |

Existing group names include `'combined-static'`, `'foundry-nav'`, `'ported-isolated'`, `'ui-navigation'`, `'ui-reading'`. Their registration includes isolated browser fixtures, so passing them alone cannot prove the served integration. [VERIFIED: deployment/checks.py:301-345]

Run the plan's complete named groups through the required local entry point; do not replace them with this note's subset. Parent retains exact integrated-tree verification and full qualification; product owner retains human acceptance. This documentation work ran no browser/native acceptance and claims none. [CITED: lane 03-01-PLAN.md, verification; AGENTS.md, Running checks]

## Security Domain

The project applies OWASP ASVS Level 1 and release-blocking high-severity findings. This mapping preserves that policy and makes no claim of an ASVS audit or a newly selected standard version. [CITED: AGENTS.md, Execution and security]

| Security area | C2/C3 planning control |
|---|---|
| Authentication/session and access control | Clear all contextual reads/back-stack content on access loss, actor or study change; preserve existing authorization and session fences. |
| Untrusted source/assistant content | Render text through existing React/shared readers; no unsafe HTML insertion, execution of source, remote asset loads or source-directed tool actions. |
| Mutation integrity | Reader navigation is read-only; edits run at existing owner through public API and guards; unknown command outcome is reconciled, not replayed. |
| Information disclosure | Keep source documents/private materials and screenshots outside the repository; only independently authored HYPRN rules belong in product docs. |
| Scientific misrepresentation | No invented status, relationship, source excerpt, support count, confidence score or operational capability. |

Controls derive from existing trust boundaries and lane decisions; no new authentication/cryptographic implementation is recommended. [CITED: docs/specs/architecture-and-contracts.md:64-114; lane CONTEXT.md, D-03–D-11]

## Environment, Confidence and Open Questions

Environment audit for this mapping is limited to repository/source reading and documentation writing; it requires no external service, runtime installation or scientific computation. Implementing tasks retain the plan's environment/fixture and verification obligations. [CITED: lane 03-01-PLAN.md, verification]

The confidence seam returned LOW for the local provider identifier `codebase` even with `--verified`. This note does not promote that provider classification into behavioral verification. The schema/implementation observations above instead show the exact opened sources and verbatim discrete values; proposed interactions remain recommendations and unexecuted acceptance criteria. [VERIFIED: session command output, query classify-confidence --provider codebase --verified]

| Open point | Current evidence | Required treatment |
|---|---|---|
| Arbitrary passage-to-statement associations | Answer schema supplies answer-level basis; explicit assumption links supply statement-level relationships. [CITED: public contract schemas quoted above] | Use only existing explicit associations now. Rich authored-document passage association belongs to its own capability; do not silently approximate. |
| Authenticated source snippet locations | Current evidence reader displays retained evidence text and source references. [CITED: ui/src/EvidenceView.tsx:125-168] | Display exact evidence content; authenticated document snippets require a source-backed locator and document owner. |
| Connected assistant availability | D-11 explicitly leaves integration with its separate owner. [CITED: lane CONTEXT.md] | Truthful unavailable state and a shared slot now; connection state comes from the real integration. |
| Current foundation completion | Research inspected the working tree based on `fc650ab`, with concurrent foundation edits. [VERIFIED: session git rev-parse/status output] | Reconcile real component names/props at C2 dispatch after C1 committed-tree acceptance. Do not call draft presence delivered. |

## Assumptions Log

No scientific validity claim, source-authority heuristic, numeric performance target or new backend entity is assumed. Future rows name prerequisites rather than promise availability. Interaction choices in the pattern map are proposed within the user's authorized design scope; they still require the existing implementation and human acceptance gates. [CITED: lane CONTEXT.md, D-06–D-11]

## Sources and Output

Primary local authorities read: root instructions/domain language; product overview; architecture/contracts; public OpenAPI assumptions/answers; design README, Layouts, Scientific states, Naming, Coherence, SOURCE and Assertion notes; UI skill; lane context/plan; shared design components, workspace shell, view registry, assumptions, evidence and answer readers; record comparison; exploration presentation; package manifest and check registration. The table citations identify the particular evidence used. [CITED: sources linked/cited throughout this note]

Only two assigned documentation outputs are written: the engineering catalogue and this supplemental mapping research. No implementation, central state, canonical lane research, task plan or external asset is changed by this work. The parent owns incorporation into C2/C3 and integration of these new documents. [CITED: assigned task ownership]

Research date: 2026-10-15. Re-check mapping against the committed C1/C2 interface before implementation; source line numbers refer to the tree inspected during this research.

