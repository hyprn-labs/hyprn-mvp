# Study creation

Canvas New study and Assistant Start a new study render the same `StudyCreation`
composition. Application state and command recovery belong to that owner; controls
use the existing `FormField`, `TextInput`, `TextArea`, `ToggleField` and `FormActions`
recipes. No surface-specific label, padding, colour or action order is introduced.

Fields remain visible in this order:

1. Study name — required.
2. Study question — required, multiline.
3. Autonomous agent — off by default. Its hint explains that enabling it completes
   the brief, executes the study and prepares the answer.

Cancel sits before the highlighted Create study action, together at the bottom
right. Fields lock during an attempt. If setup is incomplete, Continue setup uses
its original command identities; it never creates a replacement study. An already
saved study can be opened without restarting setup. Unknown creation stays subject
to the shared pending-command recovery, not a fresh submission.

Both entry points create through the public human API, save the supplied question
in the brief, then submit the scoped autonomous request only when explicitly
selected. Manual creation never starts the Assistant. No scientific defaults or
study-specific wording are added. Navigating away does not allow a late completion
to replace the new page. Protected content still follows the API session fence.
