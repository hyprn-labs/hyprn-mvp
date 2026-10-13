# HYPRN MVP domain language

The shared language for HYPRN MVP scientific records and collaboration. Each term names one concept with one owner and lifecycle; an _Avoid_ line lists words that must not be used for that concept in the interface, API descriptions, documentation or new identifiers. A glossary entry does not imply that the capability is delivered: executable contracts live in `contracts/`, and product status lives in `docs/specs/`.

## Language

**Modeling approach**: The study-owned explanation of the connected method, its choices, assumptions, evidence, intended cases and links to exact model versions. Its saved versions retain the scientific rationale used by configurations and runs. It explains and references exact versions; it is never an executable or editable model graph.
_Avoid_: Approach graph, workflow, pipeline

**Method step**: A scientific contribution within an approach, with its rationale and intended or implemented transformations. It can refer to several model elements and is distinct from a computational scheduler task.

**Study**: The engineering question and shared context in which models, configurations, evidence and runs are organized. A study is archived and restored, never deleted.

**Model**: A composition of component instances and quantity connections that expresses a calculation. A model version identifies one immutable composition and its source.

**Component definition**: A reusable transformation with declared ports and source. A definition version identifies its exact form.

**Component instance**: A particular use of a component definition version within a model. Repeated instances remain distinct even when they share a definition.

**Quantity**: An input or output with scientific meaning and units at a particular component port. Its definition is distinct from its value in a configuration or run.

**Connection**: A directed transfer from a producer output to a consumer input within a model.

**Assumption**: An explicitly scoped condition or approximation on which a modeling choice or case depends: a statement with its attached evidence. It is the one concept for such statements; free-form notes are not a separate concept (a persisted `notes` field may still exist on the wire). Recording an assumption does not establish that it holds.
_Avoid_: Note, component note, configuration note

**Rationale**: The explanation for a choice of method, model or case. It may use assumptions and evidence, but is not synonymous with either.

**Evidence**: A retained source, observation or note used to support, challenge or contextualize a scientific statement. An evidence version identifies the exact cited content.

**Configuration**: A specified case using an exact model version, explicit input assignments, numerical choices, criteria and case context. A saved configuration is immutable.
_Avoid_: Case, setup, scenario

**Case**: A situation the Modeling approach intends to examine, with its question and rationale. A case may be linked to the configuration that specifies it: the case says why, the configuration says exactly what is computed.
_Avoid_: Configuration, run

**Criterion**: An explicit requirement against which a computed output is evaluated. It is distinct from an optimizer constraint or a condition of model applicability.

**Criterion evaluation**: The deterministic comparison of a run's recorded output with a criterion, giving met, not met or unresolved. It does not establish scientific validity, applicability or feasibility.
_Avoid_: Assessment, criterion assessment, check result

**Run**: One execution of a configuration, with retained inputs, outputs and execution/scientific outcomes. It is distinct from the receipt acknowledging a command. A recorded run has been stored; recording says nothing about execution success, convergence or criteria.
_Avoid_: Job, calculation, case

**Result-linked input**: An input assigned from a specific retained run output with its exact provenance and unit interpretation. It is distinct from a live connection between models.

**Assessment**: An interpretation of specified results in the context of the engineering question, criteria, assumptions and evidence. Execution completion alone does not establish scientific validity. A criterion evaluation is one input to an assessment, not an assessment.
_Avoid_: Criterion evaluation, check result, validation

**Version**: An immutable saved state of a model, component definition, configuration, evidence item or Modeling approach. Saving a change creates a new version; earlier versions keep their identity and content.
_Avoid_: Revision, snapshot

**Revision**: The changing marker of an editable item's current state, such as a study or a model draft, used to detect that an edit is based on stale content. It is not a saved version and is never retained as history.
_Avoid_: Version

**Draft**: The mutable working state of an editable item, such as a model draft, the approach draft or a working annotation. It is never pinned by history; saving it creates a version, and a frozen copy (for example an annotation snapshot inside an evidence version) is a separate immutable record.

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

**Method package**: A reusable scientific procedure with applicability requirements, evidence, model assets, cases, checks and review requirements. A study's Modeling approach records its particular application. It is the only concept called a package; portable model records, execution bundles and exports are not packages.

**Package release**: An immutable version of a method package and its specified assets. A release identifies what may be applied; it does not establish scientific approval for every use.

**Scientific review**: An attributed judgment about exact scientific work for a stated use, with its evidence, limitations and unresolved objections. It is distinct from execution success or a criterion being met. A review an agent records for a person is labelled as agent-recorded.

**Development run**: An execution used while building the product before the invited pilot's retention boundary. Development runs are disposable; retaining or migrating them is not a condition for delivering the pilot.

**Pilot run**: An execution retained for invited product use after the declared pilot retention boundary. It is subject to the product's scientific-history and recovery requirements rather than development cleanup rules.
