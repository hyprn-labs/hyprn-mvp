# Origin of the design system

The design system is the interface language of HYPRN MVP: its principles, layouts, scientific-state wording, naming rules, component behaviour and design tokens. It was written for HYPRN MVP and is maintained in this repository.

This directory is the authoritative copy for people and agents. No external copy, export or preview of the design system is authoritative or needs to remain available.

| File | Holds |
|---|---|
| `README.md` | Principles, content rules, visual foundations, iconography, implementation and checks |
| `Layouts.md` | Page compositions |
| `Scientific-states.md` | How values, outcomes, claims and progress are worded and marked |
| `Naming.md` | How records and identities are named in the interface |
| `Coherence.md` | Shared rules for composing records and their actions |
| `components/*.md` | Behaviour of each component |
| `tokens.json` | Token values; `ui/src/design/tokens.css` is generated from it |

The implementation is the typed React layer in `ui/src/design`. When the design system changes, update the text and `tokens.json` here first, regenerate `tokens.css` with `python3 ui/design_tokens.py`, port component changes into `ui/src/design`, then run `python3 ui/design_tokens.py --check`, `python3 ui/test_design_tooling.py`, `node ui/design_smoke.mjs`, `python3 ui/check_design_system.py` and the TypeScript check.
