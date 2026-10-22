# ContentColumn

The content column of a page. It owns the page's width and the spacing between its sections; screens never size a page, a section or a dialog themselves.

| `width` | Token | Pages |
|---|---|---|
| `reading` | `home-max` (1080px) | Studies, Overview, the approach page while it remains |
| `form` | `form-max` (720px) | New study, New model, Settings |
| `login` | `login-max` (480px) | Sign in |
| `full` | the canvas | Pages whose working area spans the canvas |

- Every section placed in the column spans its full width, so the study brief, the saved conclusion and every other Overview section line up.
- Sections are spaced by `space-4`; screens do not add vertical gaps between sections.
- A dialog that compares records (change preview) uses `DialogFrame width="wide"`, which takes `home-max`.
- A wide table may still scroll inside its own box at a token width (`min-width`).

`ui/check_component_ownership.py` rejects any screen CSS `width` or `max-width` that uses `home-max`, `page-max`, `form-max`, `login-max` or `dialog-max`.
