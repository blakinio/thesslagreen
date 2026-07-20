---
task_id: TASK-YYYYMMDD-short-slug
status: implementing
branch: <task-branch>
base_branch: main
created: YYYY-MM-DD
updated: YYYY-MM-DD
related_pr: ""
owned_paths:
  - <path/glob>
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  # Add task-specific architecture, contract, or program files here.
search_first: []
optional_reads: []
---

# <Task title>

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: YYYY-MM-DDTHH:MM:SSZ
head: UNKNOWN
branch: <task-branch>
pr: none
status: investigating
context_routes:
  - none
owned_paths:
  - <path/glob>
proven:
  - <current verified fact>
derived: []
unknown: []
conflicts: []
first_failure:
  marker: none
  evidence: none
rejected_hypotheses: []
changed_paths: []
validation:
  - command: not-run
    result: NOT_RUN
    evidence: none
blockers: []
next_action: <exactly one concrete next step>
```
