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
- In record metadata, compose tags, counts and attribution as separate children of
  the shared `hf-record-metadata` row. Its `space-2` gap provides clearance between
  badge borders and neighboring text in both inline and wrapped layouts. Wrap text
  such as an input count in a span; do not concatenate it directly onto a tag or add
  screen-specific badge margins. The shared recipe and its ownership check govern
  the spacing; browser acceptance measures the rendered clearance.

## Record states and placement

RecordState shares this badge recipe: saved draft/version uses ok (green), new draft
uses advisory (yellow), and unsaved changes uses warning (amber). Execution uses its
existing completed/failed/running mapping. The words identify what succeeded: Saved
means persisted, Completed means execution finished; neither establishes validity.
Record pages place the badge after Record details and before attribution beneath the
owner title. These are noninteractive state badges, not Save action buttons. Read-only
and reference-only tags can remain neutral; they do not describe an operation outcome.
