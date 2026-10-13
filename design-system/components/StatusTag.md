# StatusTag

A state as shape + word + colour, following alarm priority so it survives colour-blindness, glare and greyscale.

| tone | mark | use for |
|---|---|---|
| `alarm` | filled diamond | failed, violated, invalid (priority 1) |
| `warning` | triangle | not converged, partial results, stale, needs review (priority 2) |
| `advisory` | ink-outlined yellow square | unassigned, not evaluated, not assessed (priority 3) |
| `ok` | filled circle | stored success only: completed, converged, met, passed |
| `inert` | hollow circle | not applicable, none defined, not started, read-only state labels |
| `running` | turning ring | in progress (the only animated mark; static under reduced motion) |

- **The consumer provides** the `tone` and a short word or two ("Partial results", "Not applicable"). Never a tag without words.
- Do not use `ok` for a live "normal" state; normal is the absence of a tag.
- Put a tag at the right end of a row, after the identifier, never before it.
