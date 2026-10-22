# RecordBar

The inverse band that says "you are looking at history": shown whenever a run, a saved model version or the model or configuration a run used is open.

- **The consumer provides** `title` ("Saved run · read-only", "Saved version · read-only"), an optional `detail`, `returnLabel` ("Return to current model") and `onReturn`.
- Place it directly under the study tabs, full content width. While it is shown, editors are read-only and the page's primary action is removed, not disabled.
- `record` is used nowhere else in the product, so the mode is unmistakable in both themes.
