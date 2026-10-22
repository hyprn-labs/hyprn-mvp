# Study assistant

The existing Assistant action opens a side panel that compresses the workspace.
Closing or expanding it changes presentation only, never the conversation's
lifecycle. Conversation state is scoped to the selected study, not the page.

Use `AssistantPane`, `ConversationLog`, `ConversationMessage` and
`AssistantComposer`. Messages use the shared readable prose spacing, author label
and tonal surfaces. Content wraps; the panel owns scrolling. The composer stays
after the conversation, with Stop before the primary Send action on the right.
Enter sends through the same enabled action; Shift+Enter inserts a newline. IME
composition and repeated keydown events never send. An uncertain delivery keeps its original command and locks the text for retry.
A confirmed rejection (`outcome: unchanged`) keeps the text editable, shows the server's
specific diagnostic and returns to Send. A confirmed allowance refusal must not be labelled uncertain delivery or claim a message was sent.

Show actual application state: Working, Stopping, or a concise actionable error.
Do not infer that a scientific run succeeded because an assistant turn finished.
Unavailable configuration leaves the composer disabled. Access loss clears
protected content using the common API read fence. Do not fabricate a reply,
tool result, elapsed duration or completed status in the browser.

Keep message text inert. Neither provider output nor source evidence can inject
HTML, invoke an action or bypass the editor guards. Refresh and study switches
read the persisted conversation; they never submit a new message.

Messages name the agent **Assistant** and the human by the API-supplied name captured
with that message, regardless of the provider. Never substitute the current viewer
or their latest alias. Unknown legacy authors read **User**. Render names as inert,
wrapping text. Assistant messages sit to the left without a competing card border; human messages
sit to the right in a compact accent-soft bubble. Short messages fit their content,
with a shared maximum width and a clear opposite-side inset. Insets use shared spacing tokens and leave
room for wrapping in narrow panels. Internal child-agent reports are not messages
from the primary Assistant.

The panel header identifies its attached study. Opening a study switches the panel
to that study's persisted session. Home retains the last attached session and offers
Start a new study, Switch study, and continued conversation. Before a study exists,
ask for its name in the shared labelled form; create it through the public human
API, then open its conversation. Never dispatch an unscoped provider message.
Clear attachment and content on sign-out or loss of access.


Home presents one action row; selecting Start or Switch replaces that row with a
labelled, spaced form. Cancel and its primary action remain together at bottom right.
The study heading, Home form and message log have shared section gaps. Spending and
provider caps are administrative concerns, not panel content. Show an actionable diagnostic
if the shared allowance is unavailable. Never substitute an uncertain usage value with zero.
