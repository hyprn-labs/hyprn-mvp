---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-10-20T21:22:41.559Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 06 | unmet-truth | deployment/cloud_lifecycle.py |  | Native owner aggregate lifecycle and installed Linux artifact remain incomplete; continuation 06-05-NATIVE-PLAN.md owns delivery. | open |  | 2026-10-20T21:22:41.559Z |  |

````json
[
  {
    "id": 1,
    "kind": "unmet-truth",
    "phase": "06",
    "file": "deployment/cloud_lifecycle.py",
    "line": null,
    "description": "Native owner aggregate lifecycle and installed Linux artifact remain incomplete; continuation 06-05-NATIVE-PLAN.md owns delivery.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-20T21:22:41.559Z",
    "resolved_at": null,
    "milestone": null
  }
]
````
