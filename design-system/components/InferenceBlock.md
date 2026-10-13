# InferenceBlock

Assistant-originated content (a proposed edit, a prepared run, an explanation), framed so it can never be mistaken for computed or sourced fact.

- **The consumer provides** `title`, `kind` (`Proposal`, `Inference`, `Explanation`), `status`, the body (a readable change list or diff, never raw payloads), `basis` (SourceChips and computed Readouts it rests on) and `actions`.
- **Actions.** Proposals offer `Button variant="ai"` naming what it creates ("Save as a new model version", "Save configuration"), a secondary "Preview" and a quiet "Discard". Applying states what it creates and that nothing runs. A Proposal block holds a suggestion that a person applies; an agent's own tool writes are not proposals: they are saved directly, carry the "{agent} for {user}" attribution and appear in agent activity (ADR-0003).
- **Status.** `proposed` (not applied), `applied`, `discarded`, and `checking` while an interrupted operation's outcome is confirmed: show "Checking the outcome — don't resubmit" and keep manual work available.
- The dashed `ai` border marks machine origin; no gradients, no sparkles. Never use this block for content a person wrote.
