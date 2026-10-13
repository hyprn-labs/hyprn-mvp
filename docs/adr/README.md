# Architecture decision records

Format: [MADR](https://adr.github.io/madr/). One file per decision, `NNNN-short-title.md`, never rewritten once accepted; supersede with a new record instead.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-repository-strategy.md) | Repository strategy | Accepted |
| [0002](0002-agent-write-rights.md) | Agent write rights: agents write freely, but never delete, archive or restore | Superseded by [0003](0003-agent-write-rights-revised.md) |
| [0003](0003-agent-write-rights-revised.md) | Agent write rights, revised: only deletion of saved records, archive and restore, and access management are human-only | Accepted |
| [0004](0004-operation-ownership.md) | Unified operations and explicit ownership | Accepted |
| [0005](0005-reviewer-agents-record-reviews.md) | An agent acting for a Reviewer may record scientific reviews | Accepted |

Decisions spanning `hyprn-mvp` and `hyprn-platform` live here and are linked from `hyprn-platform/docs/adr/README.md`.
