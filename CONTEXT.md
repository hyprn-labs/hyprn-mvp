# HYPRN MVP domain language

The shared language for HYPRN MVP scientific records and collaboration. Each term names one concept with one owner and lifecycle; an _Avoid_ line lists words that must not be used for that concept in the interface, API descriptions, documentation or new identifiers. A glossary entry does not imply that the capability is delivered: executable contracts live in `contracts/`, and product status lives in `docs/specs/`.

## Language

**Study**: The place where one engineering decision is framed and investigated: its brief, models, calculations, evidence and answer. Its name and list description are plain metadata. A study is archived and restored, never deleted.

**Study brief**: How the study frames its decision: the question (with its original wording and elaboration), the alternatives, the study criteria, scope, global assumptions, limits and open questions. It has a draft and immutable saved versions; a study answer pins the exact brief version it answers.
_Avoid_: Modeling approach, study context, boundary

**Alternative**: A named option under consideration in a study brief, with its description and reason for inclusion. It may be realised by its own model or by reference configurations of a shared model. A study with one alternative asks a go / no-go feasibility question.
_Avoid_: Option set, scenario, case, variant

**Study criterion**: A criterion defined once in the study brief, with units, either as a constraint or an objective. Each analysis binds it to the output of its own model version that measures it.

**Constraint**: A study criterion that sets a threshold that must hold for an alternative to be acceptable.
_Avoid_: Optimizer constraint, requirement (unqualified)

**Objective**: A study criterion that sets a direction (minimise or maximise) along which alternatives are compared. Objectives are listed in priority order: alternatives that meet every constraint are ranked by the first objective, then the next. An objective carries no weight or score unless the brief states one explicitly.
_Avoid_: Score, weight, goal

**Limit**: A stated bound on what the study or a result can claim, such as an excluded regime or an unmodelled effect. It is part of the study brief and is not an assumption.

**Open question**: A question the study brief records as not yet answered. It is distinct from the open deliverables a study answer lists.

**Model**: A composition of component instances and quantity connections that expresses a computation. A model version identifies one immutable composition and its source.

**Model explanation**: The application-owned explanation of one model version: what it represents, its basis and reasoning, its calculation logic and its components' roles, with attached evidence. It is saved and frozen with the model version it explains and is never stored in the modeling service. Format 2 also owns explicit model limits and local component documentation (instance description and limits). Structured model/component assumptions remain at their existing model owner. Old component annotations are a retained fallback, not a second authoring home.
_Avoid_: Method step, modeling approach, method

**Component definition**: A reusable transformation with declared ports and source. A definition version identifies its exact form.

**Component instance**: A particular use of a component definition version within a model. Repeated instances remain distinct even when they share a definition.

**Quantity**: An input or output with scientific meaning and units at a particular component port. Its definition is distinct from its value in a configuration or run. The wire calls it a port.
_Avoid_: Variable

**Connection**: A directed transfer from a producer output to a consumer input within a model.

**Assumption**: An explicitly scoped condition or approximation on which a modeling choice or calculation depends: a statement with its attached evidence. Its owner is the study brief (a global assumption), a model, a component or a configuration. A condition proposed for a model but not yet implemented is a model or component assumption in a proposed state. It is the one concept for such statements; free-form notes are not a separate concept (a persisted `notes` field may still exist on the wire). Recording an assumption does not establish that it holds.
_Avoid_: Note, component note, configuration note

**Rationale**: The explanation for a choice of method, model or configuration. It may use assumptions and evidence, but is not synonymous with either.

**Evidence**: A retained source, observation or note used to support, challenge or contextualize a scientific statement. An evidence version identifies the exact cited content.

**Configuration**: An explicit set of inputs and numerical choices for an exact model version. A saved configuration is immutable. Criteria belong to the study brief, not to configurations.
_Avoid_: Case, setup, scenario

**Reference configuration**: A configuration version marked as a baseline for its model, typically the centre from which a calculation's points are generated. A model may have several. The mark can be moved or removed; it never changes or pins the configuration.
_Avoid_: Default configuration, template

**Experiments**:
The study workspace for preparing, executing and comparing numerical work for a selected model version. It contains analyses, configurations and runs; it is not an additional saved analysis or an alternative.
_Avoid_: Analysis workspace, calculations area, experiment as a synonym for run or analysis

**Analysis**: A purposeful numerical investigation for one model version, referencing a set of configurations, their selection or sampling design, criterion bindings and associated runs. A new version revises that same investigation; a complementary investigation is a distinct analysis. Configurations and runs may be reused across analyses and also exist independently. A saved analysis declares whether estimates are required and their accuracy limits. Launching pins its calculation evidence; completion requires the requested calculations and numerical validation. Changed settings require a new version.
_Avoid_: Calculation as a saved investigation, experiment as a saved object

**Criterion binding**: The link, inside an analysis version, from a study criterion to the output of that analysis's model version that measures it. A criterion without a binding is unresolved for that analysis, never met.
_Avoid_: Sample, batch

**Criterion**: An explicit requirement against which a computed output is evaluated: a study criterion evaluated through an analysis's criterion binding. It is distinct from an optimizer constraint or a condition of model applicability.

**Criterion evaluation**: The deterministic reading of a run's recorded output against a study criterion through a criterion binding: a constraint is met, not met or unresolved; an objective is measured (its value with units) or unresolved. An unresolved evaluation carries its reason and never counts as met. It does not establish scientific validity, applicability or feasibility.
_Avoid_: Assessment, criterion assessment, check result

**Run**: One execution of a configuration, with retained inputs, outputs and execution/scientific outcomes. It is distinct from the receipt acknowledging a command. A recorded run has been stored; recording says nothing about execution success, convergence or criteria.
_Avoid_: Job, calculation, case

**Result-linked input**: An input assigned from a specific retained run output with its exact provenance and unit interpretation. It is distinct from a live connection between models.

**Estimate**: A value predicted by a fitted surrogate built from one analysis version and its runs. An estimate is never a calculated result, and a displayed estimate is not a finding of validity.
_Avoid_: Prediction result, calculated value

**Surrogate validation**: The comparison of estimated outputs with calculated points held out from fitting, against declared error limits. Training and validation are point roles; either can have calculated results. A method-selection point is excluded from independent validation metrics. Passing numerical validation establishes agreement with the model, not physical validity.
_Avoid_: Check point, estimate check, estimate assessment

**Assessment**: An interpretation of specified results in the context of the study brief, criteria, assumptions and evidence. It is recorded as the conclusion of a study answer. Execution completion alone does not establish scientific validity. A criterion evaluation is one input to an assessment, not an assessment.
_Avoid_: Criterion evaluation, check result, validation, estimate check

**Study answer**: The study's single decision record. It has a draft and immutable versions. Each version maps every alternative to the calculation versions that back it, holds the alternatives × criteria comparison with cited calculations, runs and evidence (each with its relation: supports, challenges or context), the interpretation, the outcome, the decisive uncertainties, the next most valuable analysis, and the basis of its answer exploration. Each version pins the study brief version it answers.
_Avoid_: Synthesis, conclusion record, case answer, scientific answer, trade study

**Recommendation**: The outcome of a study answer: the alternative to pursue (go or no-go when there is one alternative), or no recommendation because the evidence is insufficient or contested, with the reason. It is never inferred from execution or criteria alone.
_Avoid_: Score, verdict, confidence level

**Decisive uncertainty**: An assumption, input or unresolved criterion that, within a stated range, would change the recommended alternative. Naming it is part of a study answer; it is distinct from output uncertainty that changes no decision.

**Next analysis**: The investigation a study answer judges most valuable before committing, with what it would resolve.

**Answer exploration**: The interactive figure of a study answer. It shows one alternative's calculation version against selected inputs and outcomes, or compares alternatives on a bound criterion output and shows where the preferred alternative changes across a shared input range. Moving its inputs or switching the alternative shown never creates a record; changing what the answer's figure shows is saved with a new answer version.
_Avoid_: Explorer, surrogate view

**Version**: An immutable saved state of a study brief, model, model explanation, component definition, configuration, calculation, evidence item or study answer. Saving a change creates a new version; earlier versions keep their identity and content.
_Avoid_: Revision, snapshot

**Revision**: The changing marker of an editable item's current state, such as a study or a model draft, used to detect that an edit is based on stale content. It is not a saved version and is never retained as history.
_Avoid_: Version

**Draft**: The mutable working state of an editable item, such as a model draft, the study brief draft, the study answer draft or a working annotation. It is never pinned by history; saving it creates a version, and a frozen copy (for example an annotation snapshot inside an evidence version) is a separate immutable record.

**Record format version**: The version of a stored record's shape, which says how the record is read. It is independent of the record's own versions: a newer format does not make a record newer or upgrade its meaning.
_Avoid_: Model version, schema upgrade

## Records and exchange

**Record**: A stored, identified piece of scientific work, such as a version, a run or an evidence item. History shows a record's own stored content and never substitutes current content.
_Avoid_: Package, file

**Portable model record**: A self-contained copy of a model's versions, component definitions, exact source and identity relationships, for import into a conforming modeling backend. Because it carries exact source, importing it can reproduce the exact model versions.
_Avoid_: Model package, package, model export file

**Execution bundle**: The frozen, self-contained input of one run: exact copies of what the run uses, its generated program, provenance and integrity information. It is assembled once for the run, checked again before execution and retained with the run.
_Avoid_: Execution package, package, job

**Computational record export**: A downloadable archive of exact retained runs with the configurations, models, evidence and provenance they used, for independent inspection. It carries retained history, not editable models, and is neither a portable model record nor a backup.
_Avoid_: Package, export (unqualified), backup

**Source document**: An uploaded file (for example a PDF, text, Markdown or CSV file) kept with exact versions and collections, which can be read, annotated, cited and extracted. Its bytes are retained in AiiDA, not in the application store.

**Authored document**: Text written inside the product, such as a study report. When it is cited, the cited text is frozen into an evidence version.

**XDSM view**: A diagram of a model version's components and the data flowing between them, drawn in the XDSM convention. It shows structure only: it is not executable source and cannot by itself reproduce a model version.
_Avoid_: XDSM model, executable diagram

## Workspace collaboration

**Organization**: The tenant boundary to which a user belongs. Membership does not by itself grant access to another user's workspace.
_Avoid_: Organization workspace

**Workspace**: A user-owned place for studies and related scientific resources. The owner can invite other members of the same organization to collaborate within it.

**Owner**: The user who owns a workspace, creates and edits its scientific work, and manages its invitations. There is no separate Author role; record attribution and organization administration remain distinct from workspace ownership.

**Reviewer**: A participant allowed to inspect work and record reviews within an authorized workspace. The role alone does not establish expertise or independence from the work being reviewed.

**Admin**: A person authorized to manage organization membership and administration. This role does not automatically grant access to private workspaces or scientific approval authority.

**Workspace invitation**: An owner's explicit invitation for a same-organization member to participate in the workspace under a stated role. It is distinct from joining the organization or receiving access to one shared resource.

**Method package**: A reusable scientific procedure with applicability requirements, evidence, model assets, configurations, checks and review requirements. A study's brief and answer record its particular application. It is the only concept called a package; portable model records, execution bundles and exports are not packages.

**Package release**: An immutable version of a method package and its specified assets. A release identifies what may be applied; it does not establish scientific approval for every use.

**Scientific review**: An attributed judgment about exact scientific work for a stated use, with its evidence, limitations and unresolved objections. It is distinct from execution success or a criterion being met. A review an agent records for a person is labelled as agent-recorded.

**Development run**: An execution used while building the product before the invited pilot's retention boundary. Development runs are disposable; retaining or migrating them is not a condition for delivering the pilot.

**Pilot run**: An execution retained for invited product use after the declared pilot retention boundary. It is subject to the product's scientific-history and recovery requirements rather than development cleanup rules.

## Retired terms

These concepts were removed from the product. Do not reintroduce them in the interface, API descriptions, documentation or new identifiers.

- **Modeling approach**, **method step**, **earlier work**: retired by ADR-0007. Their content belongs to the study brief, model explanations, model assumptions and study answer justifications.
- **Case**, **case answer**: retired by ADR-0006.
- **Calculation** for a run, component logic or the worker: a calculation is the set defined above (ADR-0009).

**Trash**: Recoverable removal of a study from the active Home list, with all records retained and a human Restore action. The existing archive/restore commands own this state; Trash is neither permanent deletion nor an access-control boundary.
