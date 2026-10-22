# Collections

CollectionStatus is the shared presentation contract for counts, coverage, local filtering,
loading, failure, retry and paging. Requests and cursor ownership stay in application code.

## Coverage and wording

An item count is the number of unique received records. It is never an unknown server total.
Only a successful response with a null continuation establishes completeness. Numeric cursor
zero is a valid continuation. Page length does not establish completeness.

Supply explicit singular and plural nouns (analysis/analyses, configuration version/configuration
versions, evidence record/evidence records). Show the selected model/version once in the enclosing
workspace selector; do not repeat “For this model version” above each collection. Filters search
received records only; label the control “Filter runs”, etc.

| State | Summary/status | Action |
|---|---|---|
| First read pending | Loading runs…; no count or empty claim | None |
| First read failed | Runs could not be loaded. | Retry loading runs |
| Partial success | 20 runs shown · More available | Load more runs |
| Exhaustive success | 23 runs | None |
| Partial local filter | 3 matches in 20 runs shown · More available | Load more runs |
| Exhaustive local filter | 3 matches in 23 runs | None |
| Partial no match | No matches in the runs shown. Load more runs or clear the filters. | Load more runs |
| Exhaustive no match | No runs match these filters. | None |
| Exhaustive empty | No runs yet. | Contextual creation guidance may follow |
| Appending | Existing count/coverage plus Loading more runs… | Disabled loading control |
| Append failed | More runs could not be loaded. The runs already shown are kept. | Retry loading more runs |
| Refreshing | Existing count/coverage plus Refreshing runs… | Disabled refresh control |
| Refresh failed | Runs could not be refreshed. The runs already shown are kept. | Retry refreshing runs |

Use “1 match”, “2 matches” and each noun's supplied singular/plural forms. A partial zero-row
response still has continuation; it must not claim exhaustive absence. Failures include the
specific safe API explanation below the standard status. Loading transport is quiet text,
never a scientific success/warning/status badge.

## Interaction and ownership

One typed state represents initial loading/failure or a successful collection with explicit
coverage and optional pending/failed append/refresh. Adopted consumers cannot supply arbitrary
count strings. CollectionToolbar remains a layout wrapper for actions or noncollection context.
CollectionStatus owns summary, no-match/empty copy, and named pagination/retry controls.

An append error preserves rows, order, local filter and successful cursor. Retry repeats the
captured failed request, never refreshes implicitly. A refresh starts at page one and replaces
rows only after success. Deduplicate exact identities while retaining server order. Do not
issue concurrent duplicate page requests. Separate mutation, inspection and polling errors.

Scope, actor and access changes invalidate all outstanding reads. Fence success, failure and
finally writes. Confirmed access loss clears rows, cursors, errors from the previous scope and
selected protected records. Late replies cannot clear the new scope's busy state.

Use shared Foundry flow/wrapping, existing Button sizing and tokens. All states must work in
both themes, narrow widths and native 200% zoom with named keyboard-accessible controls.

## Current consumers

Paged: configuration versions, analyses, runs, analysis runs and version history, estimates,
evidence library and picker, result picker, evidence version discovery and replacement.
Home uses exhaustive study lists only after api.list completes. Model, brief and answer
version owners already exhaust pages and retain their own loading gates; no redundant pager.
EvidenceIndex owner-read progress and exact record member counts are separate concepts.

## Object cards

Use ResourceCard for study, model, analysis, configuration and run lists. The count and collection actions share one wrapping row. The title is the
backend name; the owning collection supplies the count and paging, never a commentary banner.
`facts` provides up to three short, wrapping facts: version identity when needed to distinguish
saved records, one useful size (such as configurations or inputs), and a genuine state/mark.
Do not show internal binding counts, IDs, repeated scope, author stamps, or a narrated history
on cards. Scientific states come from their existing backend lifecycle projections.
Keep full identity, provenance and authorship in the object's record details. An analysis card
shows its version and configuration count; a configuration shows input count and reference
mark; a run shows execution status. Never invent a configuration version number from list order.
A collection count still counts the exact records returned, not inferred unique families.
