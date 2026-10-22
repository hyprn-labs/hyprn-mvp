# ContextualPanel

ContextualPanel wraps Panel with a stable heading and optional Back/Close controls. Docked and stacked presentations are nonmodal and never trap application focus. Focus moves to its heading on opening; Escape closes the active panel unless a modal descendant owns the event. The application restores the invoking control. Readers clear on owner/version/study/session/access change.

A reader opened inside a native dialog is hosted in that dialog so its controls remain operable. Its Escape closes only the reader and restores the trigger, preserving the parent editor.

EvidenceDisclosure uses this panel with a single View evidence (n) action per item. Show all source records directly and restore the trigger on Close. Within a reader, EvidenceDisclosure renders its content directly; it never adds a nested evidence button. Nested evidence metadata may still use RecordDetails.

Docked readers are sticky at the workspace top gutter and fill the viewport down
to the bottom gutter. Their header stays outside the scrolling body. Use one
scroll region, not nested fixed-height readers. At stacked widths, keep a bounded
viewport-height reader with its Close button visible. Dialog-hosted panels remain
inside the parent modal boundary.

## Shared details geometry

Every global details reader uses `DetailsDock` with `ContextualPanel`: evidence, supporting results and other contextual records share the same surface,
curvature, header, padding and scrolling body. The dock owns the tokenized
`context-panel-width` (360px at desktop) and viewport height minus `space-8`.
Content length never changes panel height. At stacked widths, all readers use the
same available column width and retain the viewport-height boundary.

`DetailsLayer` preserves an inactive reader for Back without introducing an
auto-height wrapper. Screens must not set reader dimensions. Dialog-originated
readers use the same dock with `modal` placement: fixed at the right viewport
gutter, inside the invoking native dialog's top layer, with the same width and
height (clamped only to available viewport width). Closing returns to the dialog.
Embedded model-workbench inspectors and editing dialogs retain their own layout;
they are not alternate global details docks.

## Reader simplification and directional controls

There is no statement-details layer or Back to statements action. Claims open evidence directly; supporting records use their own reader. All DetailsDock readers share a header expansion toggle: left chevron expands the right-side reader, right chevron restores its width. The canvas remains mounted while hidden. Assistant full-width controls use the same PanelToggle recipe. Close remains a separate close action. Modal readers retain their native modal boundary when expanded.
