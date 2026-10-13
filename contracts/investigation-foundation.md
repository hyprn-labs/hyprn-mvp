# Investigation records: compatibility notes

Rules that keep approach references, citations and worker diagnostics exact and backward compatible. No identifier, historical record, digest or wire schema is rewritten by any of them.

## Version-scoped ports

Approach references keep their existing schema: binding pins the exact model
revision, instance pins the exact definition version, and port_id selects a port
within that version. A source-only revision may retain multiple definition
versions sharing stable port IDs. Both application closure validation and
independent worker admission index the global inventory by
`(definition_version_id, port_id)` and reject duplicates within that scope,
including duplicate entries in the definition-local inventory. They require
exact correspondence between local and global port records. No IDs, historical
snapshots, digests, wire schemas, or stored records are rewritten.

## Citation validation parity

Current `ConfigurationRequest3`/`4` authoring rejects duplicate evidence-version IDs
within one input provenance or criterion citation list before compatibility or
save. Existing Diagnostic fields identify the exact duplicate array index and
port/criterion ID, with `duplicate_evidence` code and a curated message. Citing
the same evidence in different fields remains valid. The worker independently
validates distinct citation lists before importing candidate code. Existing
schema definitions and historical records are unchanged.

## Bounded diagnostic text

Results protocol 1 and its `execution.message` field are unchanged. New
worker failures can include a bounded source-literal assertion/raise message and
`[source sources/<sha256>.py:<line>; instance <uuid>; definition <uuid>]`.
The source path is a retained bundle-relative authored identity, never a host
path. Stored records keep their original messages; readers never retrofit
diagnostics. Execution/scientific outcomes, output availability and missing-value
semantics are unchanged.

Before candidate execution, the worker checks retained hashes and exact source
body correspondence under the recorded indentation/BOM/line-ending transforms,
then registers the generated authored method's code identity. Diagnostics use a
matching traceback code identity and mapped range only. A literal is reported
only for the matching built-in exception type at an actual raise instruction;
an exception during an assertion condition cannot claim its assertion message.
No candidate imports, evaluation or execution are added to preview/save/modeling.

Exception objects, arguments, locals, full tracebacks and arbitrary exception
formatting are never exposed. Dynamic/unmapped messages and custom exception
types are deliberately not recovered (custom types use `Exception`). A proved
location can remain useful even without message text. Missing, ambiguous or
unproved mappings and optional AST-parser failures omit the diagnostic instead
of guessing coordinates or rejecting otherwise valid execution.

Only literal text already retained in authored source is considered. It is
bounded to 512 printable characters, control/bidi characters and whitespace are
normalized, and recognized path/credential-like text is withheld. Mathematical
comparisons (`<`, `>`, `&`) remain intact and clients render the result as text,
never HTML or a navigation command. This is a conservative disclosure policy,
not a general guarantee that arbitrary secrets embedded in source can be found.

`ApproachIssue1` is unchanged: missing instance/port/connection/assumption or
binding references identify the exact step/reference JSON pointer and validated
resource IDs in curated text. The normal authorization boundary still runs first;
unknown/foreign external resources retain nondisclosing access errors. Other
closure corruption retains its generic fallback rather than arbitrary exception
text. Configuration errors use the existing Diagnostic contract.
