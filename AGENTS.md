# hyprn-mvp — agent instructions

- This is the product repository. Infrastructure belongs in `../hyprn-platform`.
- Decisions live in `docs/adr/` (MADR); read `docs/adr/0001-repository-strategy.md` first. Current specifications live in `docs/specs/`.
- No absolute paths in code. Every location is a variable: flag → `HYPRN_MVP_*` environment variable → installation configuration → per-OS default from the path-policy module → otherwise ask the user. Never invent a path.
- Live data, stores, logs and scratch never go in this repository or in a cloud-synced folder.
- `CLAUDE.md` is intentionally absent: Claude Code and Codex both read this file.
