# AssistantPane

AssistantPane is study-scoped. Its navigation slot appears above the conversation
context; the study title is followed directly by messages. On Home, Start a new
study and Switch study replace the conversation and composer with their form.
Cancel restores the attached conversation. A successful selection attaches only
the selected study; previous messages must not flash during loading.

Creation asks for name and study question. Autonomous agent is an explicit Off/On
switch, initially Off, green when On. The question is saved through the brief
primitive before any autonomous message is admitted. Setup retains command IDs
across uncertain responses. Autonomous work uses the existing study-scoped tools,
shared budget, scientific checks and stop control; it grants no extra authority.

Messages use compact left Assistant cards and right Engineer cards, with different
neutral tones and a visible author. Prose renders paragraphs, headings, emphasis,
lists, code and tables; raw HTML never executes. Tables scroll inside their card.
Safe source links use the shared opening control. No study-specific formatting.


The shared WorkspaceShell owns the dock and resize handle. The floating labelled
Assistant button exists only while the assistant is hidden. Opening it reserves
a right column; it never replaces an open details panel. Details remain between
the canvas and assistant at desktop widths. Both docks use the available viewport
height and keep header actions separate from scrolling content.

Expand to full width hides the reading region without unmounting its contents.
Exit full screen restores the previous canvas, details and dock width. Hide
assistant closes only the assistant and restores focus to its launcher. Escape
inside the assistant hides it; Escape inside a modal stays with that modal.
The separator supports pointer dragging, Left/Right keys, Home/double-click reset
and End maximum. Width uses bounded tenths of the shared dock token (80–180%,
maximum 60% of the stage, further bounded to preserve the reader when details are present). When the workspace cannot fit three readable columns, details stack within the reading region. At narrow widths the assistant stacks above the reader
and the separator is absent. No page may implement its own panel toggles.


Conversation activity and the dock's visibility have separate lifetimes. Hiding
an active conversation keeps its bounded status polling alive until the turn
settles; a hidden idle conversation does not poll continuously. A settled turn
invalidates the visible study readers once, after message catch-up, instead of
reloading the workspace on each chat poll. Updates belong to the attached study
and current authenticated session. Keep human editors and deliberately selected
saved versions intact; defer reader refresh until edits are saved or cancelled.


Blocked activity names the actual cause in plain language. Application transport failures
use “Application problem”, not “Needs attention”, which incorrectly implies the engineer
must supply scientific input. Conversation and saved work remain visible. The shared
AssistantActivity recipe explains the next action from the API capability: show Resume
only when can_resume is true. Unsupported or invalid documents offer Stop followed by
a new source request only when can_stop is true; otherwise explain that recovery requires
the application administrator. Never infer safe retry from an error label or resend a tool operation.
Large-document interruptions explain that the document response could not be processed,
without exposing its encoded body in chat. Recovery never implies repeating calculations.

## Waiting on an analysis

The activity card reads the current conversation's compact progress projection.
Use a neutral Calculating or Validating surrogate status, completed / total counts,
and the count of existing calculations reused when the owner supplies it. Reuse
is part of the total, never added to it. Link View analysis to that exact saved
version. The timestamp says Last progress observed: it records a changed owner
fact, not a heartbeat, estimated finish or proof that execution stalled.

The Assistant waits without further reasoning requests while HYPRN executes the
accepted analysis. Only backend terminal/recovery states warrant a failure or
Resume action. An unchanged timestamp alone never produces a stalled warning.
Progress disappears when the turn settles or changes. The card shares the existing
activity surface, wrapping prose and numeric type role in Light, Dark and narrow
layouts; it remains separated from the composer by the conversation layout.

## Observable activity details

Below the concise processing card, Activity details expands a chronological list
of the latest 40 observed tool steps for the current request. Each row has the
platform tool's catalogue title, redundant state label and observed start time;
finished steps may show elapsed observation time. Reviewer steps are labelled.
Arguments, source content, provider identities, private reasoning and raw results
never cross this public projection. Unknown tools have a neutral generic label.
A completed tool is not a scientifically valid result. Unconfirmed outcomes and
failed calls remain explicit; receiving a result without a success flag is only
Result received. No guessed percentages, finish estimates or stall alarms.

The disclosure sits outside the polite status live region so an expanded history
is not repeatedly announced. Rows wrap in narrow layouts, share token spacing,
and use the same surface in both themes. Updates come from existing conversation
polling, require study access and stop at the current turn boundary. This is an
observed activity log, not a transcript of internal reasoning or a new scheduler.
