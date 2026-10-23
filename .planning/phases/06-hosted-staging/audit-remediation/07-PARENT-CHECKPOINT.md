# Performance and UX follow-up — in progress, 2026-10-23

User authorized the remaining generic fixes, identical before/after measurements
and staging deployment. No additional infrastructure, permission or budget change.
Unrelated planning/design edits are preserved. Plan: 07-PERFORMANCE-UX-PLAN.md.

Baseline: same completed staging run, five `NativeExecution.read_record` calls:
5.9935, 5.7698, 5.2172, 5.8837, 5.5532 seconds; median 5.7698 seconds.
The private benchmark saves the exact request/association and SHA-256 of the full
normalized returned record. After measurement must use those identical inputs and
produce the same full-record digest. No candidate model execution or store write.
Evidence: private hyprn-performance-ux-release/native-read-before.json.
The first attempt stopped before remote work because the temporary SSH key had
expired. Same identity/privileges renewed under continuing deployment authority;
the read-only baseline then passed.

Implementation partition:
- Native executor: one retained bundle verification and bounded bulk object reads;
  host-only code so numerical worker bytes and saved surrogate runtime pins stay
  unchanged. All original semantic/hash/bound/corruption checks remain.
- UI executor: preserve incoming study/version route on hosted sign-in; refresh
  displayed study state after settled Assistant work without overwriting drafts.
- Authoring executor: unique generated point names, explicit surrogate sample roles,
  intended criterion binding before launch, quantity naming guidance, and schema
  discriminator-aware errors. Recorded immutable configurations are not renamed.
- Parent: source closure registration, integration, exact artifacts and deployment.

Deployment stays on the existing reviewed platform commit. No migration or reset.
Current preparation generator already stages bindings as 0600; the older reset
publisher's 0644 failure does not require another live chmod or product workaround.
Private deployment packet is prepared from existing reproducible build/recovery
helpers and current sequence 20, promoting to 21 only after tests and real artifacts.
No release is claimed deployed at this checkpoint.
