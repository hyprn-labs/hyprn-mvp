# ContextualPanel

ContextualPanel wraps Panel with a stable heading and optional Back/Close controls. Docked and stacked presentations are nonmodal and never trap application focus. Focus moves to its heading on opening; Escape closes the active panel unless a modal descendant owns the event. The application restores the invoking control. Scientific readers preserve source selection, scroll and focus through Back and clear on owner/version/study/session/access change.

A reader opened inside a native dialog is hosted in that dialog so its controls remain operable. Its Escape closes only the reader and restores the trigger, preserving the parent editor. A scoped statement set displays every ClaimCard together; opening a source preserves the set scroll and selected source control for Back.
