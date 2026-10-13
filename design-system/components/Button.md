# Button

The single button component. `primary` appears at most once per view, for the action the page exists for ("Run this configuration", "Save model version").

- **Variants.** `secondary` (default) for everything else; `quiet` for inline and tertiary actions ("View all runs", "Edit"); `ai` only to apply an assistant proposal; `danger` only inside a confirmation that names what will be affected.
- **Sizes.** `desk` (36px, `control-desk`) by default; `sm` (28px) inside dense rows and the record bar; `floor` (48px, `control-floor`) on touch and shared displays.
- **Icons.** Pass `icon` as a React node (for example an `ActionIcon` inline SVG); it sits before the label and is decorative. Icon-only buttons, including the "…" menu triggers, need a meaningful `aria-label`.
- **Disabled.** Disable only when the reason is shown next to the button ("Save the configuration before running."). A disabled primary without a reason is a bug.
- **Toggles.** Pass `aria-pressed` or `aria-expanded` with `aria-controls` for panel toggles ("Hide Details"); pressed renders in `accent-soft`.
- The consumer provides the label (a verb phrase in sentence case), `onClick`, and `type="submit"` inside forms.

## Placement

- Frequent diagram and source actions are direct, compact toolbar buttons. Help opens a named dialog. Operational actions never hide inside vaguely named disclosures ("Source tools") or float over help text.
- Model header order: version select, "Save model version" (draft only), "Create configuration", "Model actions" menu (rename, reload, import, export). Component actions stay in the canvas toolbar; the source toolbar holds only Expand and Collapse. Source import keeps its exact-byte safeguards.
- `ActionDialog` (a button that opens a named dialog) accepts the compact `sm` size for help, evidence and file actions.
