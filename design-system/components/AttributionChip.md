# AttributionChip

Who acted, when a record was written through an assistant: "{agent} for {user}". It names the agent and the person it acted for, and nobody else: an agent's writes are direct, so there is no confirmer to name.

- **The consumer provides** `agent` (the agent's display name, for example "Codex (local)") and `user` (the display name of the person it acted for), each as its own field from the API. The chip composes the text; a consumer never passes or parses a combined string, so "for" is never doubled.
- **Anatomy.** The assistant mark (a solid `ai` square, `radius-xs`, with the iris glyph in `on-ai`, sized like the `StatusTag` mark, `aria-hidden`), then "{agent} for {user}" in `small`, `ink-2`, with the word "for" in `ink-muted`. The box has the `StatusTag` geometry in a neutral tone: `surface` ground, 1px `line` border, `radius-xs`, 2px `space-2` padding, `space-1` gap. It reads as metadata, not as a status.
- **Accessible text.** A visually hidden prefix "Assistant: " comes before the agent name, so a screen reader reads "Assistant: Codex (local) for {user}". The chip is not focusable and not interactive.
- **Names are never truncated.** Truncation would hide who acted. The chip wraps (`white-space: normal`, `min-width: 0`, `overflow-wrap: anywhere`) at narrow widths and at 200% zoom.
- **Names are untrusted text.** They render as plain text, never as markup or links.
- **When it appears.** Only when the record's receipt actor is an agent. A record a person wrote carries no chip: the absence of the chip means a person did it. Historical views show the attribution stored with that version or run, never a current name.
- **Where it sits.** At the end of a row's metadata line, after a heading's state tag, or first in the metadata line of an Agent activity row. Status tags stay at the right end of their row. One chip per record per screen.
- **Not a proposal.** The `ai` colour is limited to the mark. An agent's saved record is not assistant-suggested content, so it never sits in an `InferenceBlock`. A scientific review recorded by an assistant also carries the label "Recorded by an assistant" beside the chip.

Human names are captured from the effective display alias (account name when blank)
when a new attribution is created. Profile edits never change saved authorship;
legacy entries retain the account-name fallback. Every evidence and explanation
reader uses the same API-supplied names through RecordAttribution.
