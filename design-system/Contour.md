# HYPRN Contour

Current visual amendment, authorized 2026-10-15. This supersedes system-font-only, machined-corner, flat two-layer, no-panel-shadow and blanket no-gradient clauses in earlier design rules. It does not change scientific state, public API, guards, exact pins, graph geometry, CSP or accessibility contracts.

## Foundation

Interface text uses original self-hosted Manrope variable font, weights 200–800, with system fallback. Font and original OFL text are audited in ui/src/design/assets/fonts/provenance.json and exposed through Third-party software notices. Quantities, units, identifiers and source retain tabular system monospace. Original logo bytes remain unchanged.

Tokens are authoritative: 6px chip, 12px control, 24px panel, 32px outer working canvas. Controls retain 28px compact, 36px standard and 48px touch minimums and grow for wrapped labels. Scientific marks preserve their shapes.

Shell-ground carries static low-contrast texture. The working canvas separates navigation from content; raised panels use surface-raised and shadow-panel. Sunken summaries, code and values use surface-sunken without shadow. Neutral gradients belong only to shell chrome. Texture never overlays text or plots and carries no interaction or status meaning. Semantic colours remain unchanged.

## Shared ownership

WorkspaceShell owns central canvas and navigation placement through React slots. NavigationRail owns brand, main navigation, current study identity and study-section controls. Neither fetches records, constructs routes or bypasses guards. Workspace supplies registry labels and existing navigate/chooseView callbacks. Desktop navigation stays in a rail; narrow and zoomed layouts stack it above the canvas with wrapping controls and no hidden destinations.

Panel's ordinary surface is raised; tone=sunken is an inset well. Existing scientific component contracts continue to apply. Screens arrange shared recipes and never override their internals.

## Adoption boundary

The shared layer covers foundations, shell/navigation, settings, cards, contextual statement/evidence readers and adjacent assistant capability slots. The matrix below reconciles every component export. Production capability remains bounded by its actual record owner; compatibility-only exports are explicit.

Automated browser fixtures establish UI behavior with public-API-shaped doubles. Served auth/CSP integration, full qualification, independent review and product-owner acceptance remain separate gates. No deployment is implied.

## Workspace reading and local preferences

Shared ResourceCard, SettingsSection, WorkflowNavigation, ContextualPanel, ClaimCard, ClaimButton and AssistantPane own their geometry in Foundry. Applications supply records and guarded callbacks. Statement sets count actual item identities under one owner/version. Answer-wide basis remains explicitly answer-wide. Context source reading reuses EvidenceRecordBody and restores selection, scroll and focus on Back. Study/version/session/access changes clear transient content. Profile appearance is browser-local; unavailable assistant state exposes no send. Engineering-pattern-map.md remains the full catalogue, with future capabilities excluded from production navigation.

## Complete component adoption and state matrix

This inventory covers all 49 component exports in `ui/src/design/index.ts`. Source paths below are relative to `ui/src/design/`; every recipe lives in `foundry.css`. Specimen names are accessible section labels in `ui/tests/DesignSpecimen.tsx`, exposed only by scoped test builds. The ui-reading group compares the actual barrel against rendered specimen groups so an added export cannot silently disappear from coverage. Pure utility `formatNumber` is separately checked for zero, tiny nonzero, large and nonfinite values; types have no DOM specimen.

Interactive states are exercised by browser input (hover/focus, tab keys, modal open/close and file selection), not CSS-only imitations. Disabled, selected, error, loading, empty and long states apply where the component contract supports them; passive records do not invent hover or loading behaviors. Compatibility exports retain explicit specimens and contracts without forcing unrelated product adoption. They are not claims of a delivered assistant or source-ranking feature.

| Export | Source / shared recipe | Specimen | Supported states / invariant | Current product consumer or explicit boundary |
|---|---|---|---|---|
| AttributionChip | components.tsx / hf-attr | Scientific records; Workspace recipes | agent/user, long names | Workspace attribution |
| Button | components.tsx / hf-btn | Control recipes; all contexts | sizes, variants, icon, disabled, focus, hover, wrapping | Workspace, dialogs, EvidenceView |
| DataTable | components.tsx / hf-table | Form and states; Native inputs and dialogs | default/dense, selected, empty, zero/missing, local scroll | VariablesTable, RunPanel, ComparisonView |
| Field | components.tsx / hf-field | Form and states; Native inputs and dialogs | assigned/unassigned/invalid/readonly, compact, units | ConfigurationPanel, ConfigurationRecord |
| InferenceBlock | components.tsx / hf-infer | Scientific records | proposed/applied/discarded/checking; basis | Compatibility export; no current production consumer; connected assistant owner must supply real proposals |
| Ledger | components.tsx / hf-ledger | Scientific records | independent execution/criteria/applicability facets | runStatus → RunPanel |
| ModelNode | components.tsx / hf-node | Source and graph chrome | selected/default/incomplete/proposed, all port states | GraphCanvas → GraphView → ModelView |
| Panel | components.tsx / hf-panel | Form and states; Native inputs and dialogs | raised/sunken, header/actions, unavailable | ModelView, RunPanel, Workspace |
| Readout | components.tsx / hf-readout | Scientific records | four bases, zero/unavailable, small nonzero, both sizes | Compatibility export; current products use QuantityResult and tables; no invented adoption |
| RecordBar | components.tsx / hf-record | Scientific records | read-only, return action, long detail | RunPanel, views/model |
| RecordState | components.tsx / hf-record-state | Scientific records; Workspace recipes | new/draft/changed/saved | ConfigurationPanel, views/model |
| SourceChip | components.tsx / hf-chip | Scientific records | primary/secondary/unverified, locator, action | Compatibility export; actual evidence actions use EvidenceRecordBody; no guessed authority |
| StatusTag | components.tsx / hf-tag | Scientific records; Form and states | all six tones, wrapping, shape+word+colour | RunPanel, EvidenceView, Assumptions |
| Tabs | components.tsx / hf-tabs | Native inputs and dialogs | underline/segmented, selected, keyboard roving, long labels | ModelView, RunPanel, Workspace |
| ActionIcon | primitives.tsx / hf-glyph | Control recipes | labelled icon-only; decorative beside text | Workspace and ActionDialog |
| CriterionRecord | primitives.tsx / hf-criterion | Scientific records | threshold/units, unassigned, null actual, reason, tolerances | ConfigurationPanel, ConfigurationRecord, ApproachFindings |
| TextInput | primitives.tsx / hf-input | Form and states; Native inputs and dialogs | editable/disabled, long value | Workspace, ModelEditor, UnitEditor |
| TextArea | primitives.tsx / hf-textarea | Native inputs and dialogs; Source and graph chrome | editable/readonly, exact source, long prose | SourceEditor, ModelMethodDetails |
| Select | primitives.tsx / hf-input | Workspace recipes; Native inputs and dialogs | exclusive choice, selected, long label | ContextDetails appearance, configuration editors |
| Checkbox | primitives.tsx / hf-input | Native inputs and dialogs | checked/unchecked/disabled | ApproachReferences, ApproachMethod |
| Disclosure | primitives.tsx / details | Native inputs and dialogs | closed/open, keyboard | SelectionInspector, RunPanel |
| DialogFrame | primitives.tsx / hf-dialog | Native inputs and dialogs | native modal, Escape, tab boundaries | ModelMethodDetails, Workspace, EvidencePicker |
| SectionHeader | primitives.tsx / section-header | Native inputs and dialogs | long heading, wrapping actions | ConfigurationRecord, EvidenceView, ModelEditor |
| ActionDialog | primitives.tsx / action-dialog | Native inputs and dialogs | trigger, open, Escape, return focus, long body | EvidenceView, ModelEditor, ContextDetails |
| DetailTabs | primitives.tsx / detail-tabs | Native inputs and dialogs | three panes, roving focus, hidden content | Compatibility export; current SelectionInspector is a continuous reader |
| FilePicker | primitives.tsx / hf-file-picker | Native inputs and dialogs | empty/selected/disabled; actual file name | ModelEditor import, ComparisonView |
| Progress | primitives.tsx / hf-progress | Native inputs and dialogs | named indeterminate stage, explanation | RunPanel, ComputationalExportDialog |
| GraphCanvas | graph.tsx / graph chrome | Source and graph chrome; real model browser tests | empty, selected nodes, port reveal, graph controls | GraphView → ModelView; geometry unchanged |
| SourceSurface | source.tsx / source-frame | Source and graph chrome | exact glyphs/newlines, readonly overlay, scroll | SourceEditor; text never executed by rendering |
| BrandLogo | BrandLogo.tsx / hf-brand-logo | top of specimen; Workspace recipes | Day/Control room, narrow, original bytes | Workspace, NavigationRail |
| QuantitySlider | exploration.tsx / hf-quantity-slider | Answer exploration recipes; Source and graph chrome | prepared values, unassigned, unavailable range | AnswerExplorer; numerical behavior owned by main lane |
| QuantityResult | exploration.tsx / hf-quantity-result | Answer exploration recipes | calculated/estimated/unavailable, explicit zero | AnswerExplorer; estimated is never calculated |
| ResponseCurve | exploration.tsx / hf-response-curve | Answer exploration recipes; Source and graph chrome | calculated point, unavailable gap, no data | AnswerExplorer; data scales unchanged |
| Assertion | compositions.tsx / hf-assertion | Assertion rhythm | zero/one/multiple evidence, long text | Assumptions, ApproachAssumptions; ClaimCard |
| AssertionList | compositions.tsx / hf-assertions | Assertion rhythm | separator, empty evidence, multiple statements | ApproachAssumptions |
| EvidenceStack | compositions.tsx / hf-evidence-stack | Assertion rhythm; Workspace recipes | empty hidden, single/multiple, full title | EvidenceView, Assumptions |
| ReadingSection | compositions.tsx / hf-reading-section | all specimen sections | section rhythm, optional content | ApproachAssumptions |
| ReadingStack | compositions.tsx / hf-reading-stack | entire specimen | first/middle/last section rhythm | ApproachAssumptions |
| ActionGroup | compositions.tsx / hf-actions | Control recipes; all contexts | wrapping, start/end, empty hidden | EvidenceView, Assumptions; workspace composites |
| WorkspaceShell | workspace.tsx / hf-workspace | Workspace recipes | four regions, stacked narrow/zoom | ContextDetails → Workspace |
| NavigationRail | workspace.tsx / hf-navigation | Workspace recipes | selected, long study identity, narrow | Workspace registry destinations |
| ResourceCard | workspace.tsx / hf-resource-card | Workspace recipes | full text, metadata, separate actions | Workspace Home, ApproachFindings Cases |
| SettingsSection | workspace.tsx / hf-settings | Workspace recipes | labelled section, exclusive local appearance | Workspace Profile, ContextDetails |
| ContextualPanel | workspace.tsx / hf-context-panel | Workspace recipes | close/back, dock/stack, long body, keyboard | SelectionInspector, ContextDetails exact reader |
| WorkflowNavigation | workspace.tsx / hf-navigation__sections | Workspace recipes | current destination, wrapped labels, independent buttons | NavigationRail → Workspace registry |
| AssistantPane | workspace.tsx / hf-context-panel | Workspace recipes | disconnected/unavailable, no send | ContextDetails; connected transcript slots reserved for real integration |
| ClaimCard | workspace.tsx / hf-claim | Workspace recipes | kind, full statement, scope, limits, attribution, evidence | ContextDetails over actual statement owners |
| ClaimButton | workspace.tsx / hf-claim-button | Workspace recipes | identity dedup; complete/partial/unknown/empty; singular | ContextDetails.StatementActions |
| ReadingContents | workspace.tsx / hf-reading-contents | Native inputs and dialogs | local destinations; keyboard focus; source disclosure | SelectionInspector.MethodExplanation |

## Measured shared rhythm

Button size is independent of location: shell, resource card, settings, context, evidence, heading and dialog use identical font, line, padding, gap and minimum height. NavigationRail does not silently promote a desk Button to floor; request `size="floor"` when that intent is needed. Navigation destination tabs remain their distinct 48px rail recipe. Link and icon variants retain the documented intentional padding exceptions.

Assertion → evidence is 12px; evidence → evidence is 8px; assertion separators have 16px on each side; section separators have 24px on each side. ClaimCard uses the same 12px grid interval with zero outer margins on its heading, statement, scope and limits. The source sub-block uses an 8px internal interval. Paragraphs inside a statement preserve authored paragraphs, with no first/last margin added to the outer grid. Empty EvidenceStack is hidden. Long controls and sources wrap; wide data remains in a named local scroll region.

Day/Control room at 1440×1000 and 390×844, genuine browser zoom factor 2, reduced motion, coarse-pointer 48px buttons, keyboard and modal focus, same-origin loaded Manrope, token contrast and rendered chrome samples are C3 automated evidence. The checkpoint names their exact tested tree/results; this inventory itself is not a test result. Independent review, served API/CSP/auth, final qualification and product-owner acceptance remain separately recorded gates.
