# Help center

`HelpCenter` is the same read-only learning surface from Home and from a study.
It introduces the delivered product, not a study-specific explanation or an API reference.
The existing route guards protect unsaved edits; opening help keeps the selected study.
Topic selection is local presentation state and never writes scientific records.

## Information hierarchy

- One page title, followed by named topic navigation and one topic article.
- Start here shows four interactive steps: Frame, Model, Calculate, Judge. Steps open
  the corresponding guidance; they do not launch calculations or author records.
- Each topic has a prominent title, a short introduction, paired concept/action
  cards and one key scientific distinction. Headings carry meaning, not decoration.
- Explain the relationship between primitives before introducing controls. A
  configuration supplies inputs, a run executes it, and an analysis groups the work.
- Training, method selection and validation are point roles, independent of whether
  their outputs are calculated. Passing surrogate validation means agreement with
  the model, never physical validity.
- Describe actual recovery capabilities without promises of automatic numerical
  success. Waiting for calculations is distinct from a stopped or uncertain execution.

## Shared layout and interaction

`ui/src/design/help.css` owns the recipe. All dimensions, type, spacing, borders and
surface colors use existing Contour tokens. Articles use raised Panel surfaces,
concept cards use sunken surfaces, and the key distinction uses a neutral rule.
No status color decorates ordinary educational content.

Topics use the shared Button with `aria-current`; keyboard activation moves focus
into the article heading. The ordered workflow remains readable without its visual
step numbers. At narrower widths the topic navigation wraps above the article, cards
become one column, and the workflow becomes two columns. Content grows naturally;
there are no clipped readings, internal scroll traps or fixed-height cards.

## Coverage and maintenance

Guidance covers brief and criteria, model graphs and quantities, immutable versions,
analyses/configurations/runs, sampling roles and accuracy, exploration and result
basis, evidence/assumptions/limits, and Assistant autonomy and recovery. It contains
no example study records, numerical claims, fake progress or external dependencies.
Update the relevant topic when a delivered platform interaction changes. Keep
section-specific Help buttons for local explanations; this center teaches the whole
workflow rather than repeating every form label.

`study-navigation.spec.ts` verifies Home/study access, dirty-editor guards, topic and
keyboard interactions, no writes, and all topics at desktop/narrow widths in both
themes. These are isolated UI checks, not a claim of live execution acceptance.
