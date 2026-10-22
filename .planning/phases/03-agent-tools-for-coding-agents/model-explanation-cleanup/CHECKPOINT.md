# Model explanation cleanup — 2026-10-19

Shared PageHeader supports embedded level 3; RecordState names its optional subject;
RecordDetails supports Model explanation; VersionSelect supports explicit placeholder.
One model explanation header/metadata row, one read-mode Edit action. Publication moves
into the editor's dialog, checks the exact target (not just latest-version metadata),
saves changed draft text before publication and retains its acknowledged revision after
publication failure. Saved explanation is immutable and follows the selected model.
Empty optional sections are omitted. Evidence resolves exact attached versions and uses
the common side panel. Analysis description has its own Analysis details reader;
generic editor and agent guidance keep numerical sampling/assessment details there.
No hardcoded study content, automatic prose classification or live record mutation.

Development checks via ./hyprn-mvp dev check in isolated scopes:
- combined-static: 9/9, 4.77 s; scope 649cd9bb-e740-4717-9108-0054c4a7f0db.
- ae-ui-model: 7/7, 24.81 s; scope b442362d-b2a9-442d-b94d-a93a54b95e3a.
  Includes failed publication after acknowledged draft save, retry, immutable saved
  reads, original attached evidence after library revision, clean optional sections,
  metadata identities and light/dark screenshots at 1440/720/390 widths.
- calculations-ui: 6/6, 39.39 s; scope 4a5a2bfe-a896-46e1-b955-ecf8dca03f9e.
  Includes genuine 200% zoom and creation/retained analysis journeys.
Default scratch scopes released by runner, reports retained in .hyprn-checks.

Failures during development: edit script stopped before writing on an unmatched marker;
TypeScript caught an unexported versionLabel helper, replaced by shared VersionSelect;
two check commands did not start because the previous tool session's prefix was absent,
then ran successfully after explicit environment setup. No user data affected.

Implementation: `c834399`.
Broader release qualification and human acceptance remain separate.


## Committed verification and live review

Snapshot `2cb4253` (includes `c834399`), through the local edition entry point:
- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 6.00 s;
  scope 64123432-fbff-4674-8e6a-09c84b2211e4, archive a7d7c83c-5f9a-4558-912e-7b222771bf54.
- `./hyprn-mvp dev check ae-ui-model`: 7/7, 21.99 s;
  scope b109a128-a0c3-4611-929b-289eb21f0571, archive 59d67600-bc25-4a4c-9ff8-bfe19f352240.
- `./hyprn-mvp dev check calculations-ui`: 5/6, one failure in the concurrent
  configuration-reference spacing test: input-count span not yet in the snapshot.
  Scope 7f01e672-b8ea-429c-9143-5b3b48ded0e5; archive 9854f78e-1278-49f9-a0eb-abd4dcc3218a.
  That test edit landed between preflight and explicit staging of calculations.spec.ts;
  it was unintentionally included in c834399. No other work was reverted; an amend
  preflight stopped when HEAD advanced. Matching UI implementation landed in e09d32d.
  Rerun on e09d32d is recorded below. Browser scopes released by runner.

The concurrent compact-sampling delivery already included this implementation;
see ../analysis-creation/CHECKPOINT.md, Compact cards delivered. The live index changed
since this task's captured baseline, so no stale build was deployed over it.
Live review on port 54821 verified one heading, draft editor/cancel, publication dialog
with exact-version replacement refused, immutable saved explanation and Analysis details.
No authoring records changed. Screenshots and observed asset/runtime fingerprints:
`/private/tmp/hyprn-model-explanation/live-review.json`, `model-explanation-live.png`,
`analysis-details-live.png`. The existing saved prose still contains historical analysis
text; ownership guidance does not rewrite immutable records or infer a prose migration.
Generic model/analysis authoring rules are in the design system and agent playbook.
Full scientific release qualification and product-owner acceptance are not claimed.

- Integrated rerun `./hyprn-mvp dev check calculations-ui` on e09d32d (tree identical
  to subsequently amended 2937125): **6/6 passed**, 44.55 s. Scope
  81532e36-9cc0-45c0-bc60-98581a52b94c released; archive
  `/private/tmp/hyprn-configuration-checks/.hyprn-checks/33a02933-24b4-4644-a477-dcf50678e305`.
Next: product-owner review. This final delta records evidence only.


## Persistence wording correction — 2026-10-19

User correction supersedes subject-qualified persistence labels above. Removed the
RecordState subject option: all versioned primitives use New draft, Saved draft,
Unsaved changes, Saved version · read-only. Model history banner follows the same wording.
Naming/Scientific-states/RecordBar docs and existing browser expectations updated.
Layout, saved records and scientific states unchanged. Concurrent badge-tone/run edits
preserved separately; staged only the wording hunks in the two shared files.
Precommit `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 4.85 s;
scope 93579490-6ece-4008-8f5e-7c9672983067, archive 25815464-5039-4853-acaa-23380a477055.
Implementation `418ac11`. `./hyprn-mvp dev check ae-ui-model`: 7/7 passed,
24.03 s; scope 4e6cd1e5-39c0-40c8-91fb-0f68a9a2402e released; archive
9456a5de-c7de-499f-99a5-e27109f25d0d. Includes light/dark and narrow reader screenshots.
The passing static build was published after source/live fingerprint checks; concurrent
run/badge changes were included in that integrated build but preserved outside this commit.
Runtime and study records unchanged. Delivery manifest and live draft/saved screenshots:
`/private/tmp/hyprn-record-language/ui-delivery/delivery.json`, `saved-draft-live.png`,
`saved-version-live.png`. Live model and explanation labels match in both states.
No failures in this correction. User acceptance remains separate; next: user review.


## Future authoring ownership — 2026-10-19

User explicitly excludes migration of earlier studies. Updated the installed /hyprn
skill (symlink to docs/agents/scientific-engineering), primitive and joint-exploration
references, the authoritative packaged playbook and generated document, delegated
field descriptions, and owner describe_tool guidance. Model explanations own physical
meaning/basis and input-to-output logic; Analysis details owns sampling/check design,
error-target rationale and numerical checks, alongside exact structured records.
Pre-save/readback review is explicit; no keyword filter, schema restriction, automatic
rewrite, new replacement model version, or scientific-data mutation. Existing physical
numbers and model algorithm details remain valid model content. Registry guidance patch
version is 0.1.1. The prior generated-only playbook amendment is now represented in
its authoritative source rather than being lost on generation.

Initial checks through ./hyprn-mvp dev check:
- agent-tools: 326 passed, 54.85 s; scope cc5efda8-c921-45f1-b7ca-2ff8cb47ceae;
  archive 11c4fb67-59d1-4d4d-bb9f-6a5c72a8664a.
- local-api-client: 18 passed, 9.07 s; scope 739cb5b5-deb7-48aa-8aa9-5b4352d83d0f;
  archive f37311d6-d693-41b4-9293-0b374fcee4a2.
- Skill Creator quick_validate.py docs/agents/scientific-engineering: valid.
- Owner describe_tool public dispatch readback saved outside repo at
  /private/tmp/hyprn-explanation-ownership/owner-tool-guidance.json (no HTTP writes).
Focused source-read review added a generic pump authoring scenario and checked physical
logic versus investigation counts/tolerances and immutable historical content. This is
maintainer review, not an independent live-model behavioral evaluation.

Installed skill and freshly launched owner helper use the new guidance immediately.
Packaged MCP/backend playbook and registry changes require the next application rollout;
no server restart or release is claimed. Full supported-surface agent evaluation remains
the existing release qualification obligation; passing tool tests establishes delivery
and immutable-write behavior, not guaranteed semantic compliance by a model.
Committed acceptance for 129cbe9, with ee28ae1 wrapping only identical Python
string literals (AST identity checked):
- agent-tools: 326/326, 66.13 s; scope 9ae02d65-3e2f-4d6c-abb3-8940e1899350;
  archive e80a17b1-c7e7-4eb3-8bae-7975146092a7.
- local-api-client: 18/18, 9.16 s; scope 80a48936-d21e-4819-ac70-b497fce266e0;
  archive d4379e69-a0a1-452a-b743-99eecbf3ee51.
All scoped test stores released by the runner. Authoring records untouched.
Next: use updated local skill for new studies; packaged backend rollout and independent
agent evaluation remain release obligations. This final change records evidence only.

Style-ratchet: 32/33 tests passed; repository-wide current-tree test failed against
its earlier baseline, reporting existing long/unformatted files across application,
deployment and UI plus two new long explanation description literals. Wrapped those
two literals and verified exact AST/string identity; guidance and behavior unchanged.
Pre-existing catalogue/calculation.py and study_tools.py violations confirmed against
129cbe9 parent. Did not reformat unrelated files or raise the style baseline.
Failure archive 267028e3-a1d7-48c8-bedb-b60c47e530c3, scope
2f6c0c1a-4dd0-456a-b842-10b77363ea90, 15.46 s. This group remains failing.

## Current model/analysis authoring structure — 2026-10-20

Delivered `b7faa44`: /hyprn entrypoint, primitive/joint-exploration references,
one focused authoring map and a maintainer behavioral scenario. No application
code, packaged tool descriptions or study data changed in this follow-up.

Observed through Chrome/CUA against localhost:54821, study
1174be5a-8527-4a51-83d9-aad3c8e4aeaa, model
eeb583c9-e2d4-4cbf-a7b6-eb9475fbc00f:
- Diagram/Component/Python/Quantities structure and Model explanation fields.
- Component edit dialog and new-model name/template scaffold.
- New analysis: select saved configurations or generate samples; blank fixed values,
  range bounds/optional step, method/training/validation/seed, opt-in output estimates.
- Estimate checkbox exposes explicit absolute and percent relative limits.
- Saved analysis version 3: Description, Results, Surrogate validation; settings
  read-only, Create new version opens unsaved editor with retained settings.
- All editing/creation views closed without Save; no analysis launch or model run.

Source review: ModelEditor annotation writes, ModelExplanation field/persistence
mapping, model creation, CalculationDesign/samplingInputs, CalculationsPanel,
AnalysisEstimateSettings and owner tool descriptions. Existing lifecycle guidance
already matches the managed launch; no backend redeployment needed for this skill delta.

Acceptance rerun on committed b7faa44:
- `python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py docs/agents/scientific-engineering`
  — valid, exit 0.
- Inline Python resolved 18 Markdown links across the five edited skill files and
  asserted installed /hyprn resolves to repository source — pass, exit 0.
- `git diff --check HEAD -- docs/agents/scientific-engineering` — exit 0, no delta.
No test stores created. Broader runtime suites not rerun for this guidance-only delta.
One initial PLAN patch failed to match and made no change; corrected patch applied.
The evidence commit initially failed the staged term guard on a machine-specific
home path; replaced it with the equivalent home-relative validator invocation.

Maintainer scenario review covers component/system ownership, explicit inputs,
0.2% → 0.002, save versus launch and validation-pool versus independent counts.
It is not independent agent behavior evaluation or human acceptance. Those existing
release obligations remain; new guidance is available on the next skill load.
