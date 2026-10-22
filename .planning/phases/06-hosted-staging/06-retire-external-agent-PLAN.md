---
phase: 06-hosted-staging
plan: retire-external-agent
type: execute
autonomous: true
---

# Retire external agent connections

Owner: retire_external_mcp executor. Authority: IMPLEMENTATION-AMENDMENT.md.

Deliver the embedded Assistant as the only agent connection. Preserve the public
API, tool registry, delegated authority, journal, attribution and scientific tools.

1. Remove token CLI/HTTP/auth/storage entrypoints and unsupported surfaces.
   Coordinate store changes with hosted_postgres; regenerate public contracts.
2. Move existing security/runtime fixtures to embedded sessions, retain revocation,
   isolation, idempotency and secret-containment assertions. Remove obsolete token
   implementation tests and add negative retirement assertions.
3. Replace obsolete external connection guidance with the supported embedded path.

Verification: registered agent-tools, assistant, contracts and UI contract checks
as applicable; parent may integrate acceptance on committed batch. No live data,
provider calls, cloud operations or unrelated worktree edits.
