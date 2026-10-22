# PageHeader

One header for every record and collection page (Studies, Models, a model, Evidence, Settings, configurations, run history and runs).

- **Links row** (optional, normal flow above the header): `returnTo` renders the one ReturnLink; `links` holds related forward links.
- **Title column:** the page title (`h1` for pages outside a study, `h2` inside one). `titleEditor` replaces the visible title with an editable name while the heading stays for assistive technology. `details` holds the RecordDetails trigger, RecordState and attribution, in that order.
- **Commands column:** `controls` (the VersionSelect) then `actions`. Commands start on the title row and wrap below at narrow widths.

**ReturnLink** is the only return control, with an underlined label and the shared back arrow in one focus target. Its label is typed to start with "Return to " and names the destination (Return to all models, Return to run history, Return to Overview). RecordBar keeps its own return inside the read-only band.

**VersionSelect** is the only version choice: "Draft" and "Version <number>".

Rows in a collection use ResourceCard (`level` 3 below a page `h2`), never a local row recipe. `ui/check_component_ownership.py` rejects local heading, return and row classes, "Back to" or arrow returns, and hand-built version labels.

Embedded record readers may use level 3. A containing Panel then omits its own title;
the embedded header owns title, metadata and commands exactly once.

VersionSelect may offer an explicit placeholder when a publication target has not
been chosen. A target selector belongs in the publication dialog, not the reading
surface. Reading always follows the parent record's selected version.


## Revising saved records

Models, configurations and analyses use `RecordState state="saved"` while reading
an immutable version. No editing fields or edit commands are active in that reader,
including an empty model explanation. Inspecting settings uses saved values and selected choices; no disabled editing form.

Use the shared `CreateVersionAction` (Create new version) to enter authoring. It
prepares changes; it does not overwrite or immediately save the original. Saving
remains a separate explicit action. Existing navigation and unsaved-change guards
remain in force; pending commands disable the transition.

- Models offer this on the unique latest saved version, identified by parent links,
  never list order. The action opens the current model draft and preserves any work
  already there; its tooltip states this. The Draft selector and Return to current
  model are explicit ways to resume that same draft. Older versions remain readers.
- Configurations copy the exact saved values, units, provenance and model pin into
  an unsaved draft; saving produces a distinct configuration version.
- Analyses enable the selected latest version's settings only after this action;
  historical settings stay read-only. Cancel/reopen restores the saved settings.

Do not use a bare Edit action on a saved record, hide the selected source mode, or
substitute a current record for a historical pin. Draft records retain their own
Edit/Save controls; this rule does not make saved drafts immutable versions.

Version numbers come from recorded metadata or complete unbranched model ancestry, never list order. If unavailable, show `Saved · <identifier>`; keep full identities in record details. VersionSelect owns its visible label unless the surrounding field already labels it.
