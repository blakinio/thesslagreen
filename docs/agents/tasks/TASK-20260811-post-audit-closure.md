---
task_id: TASK-20260811-post-audit-closure
status: implementing
owner: codex
scope: close verified post-audit follow-ups
---

# Post-audit closure

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-11T13:30:00Z
head: 94dd5021d5126bc99cffc79e208d0093d9525bb0
branch: fix/close-audit-followups-20260811
pr: none
status: implementing
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/deep_audit_2026-08-11.md
owned_paths:
  - .github/workflows/ci.yaml
  - custom_components/thessla_green_modbus/sensor.py
  - tests/test_sensor_platform.py
  - docs/agents/tasks/
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - main head was 025a36f78b3629e47421afe1d06b372c1df3aafb when this branch was created.
  - PR #1765 is merged and its final main CI completed successfully with 1402 tests passing on Python 3.13.
  - CI currently validates two task checkpoints explicitly instead of the complete task directory.
  - TASK-20260811-deep-audit-cleanup.md does not satisfy the current shared checkpoint contract.
  - manifest.json and pyproject.toml both require pymodbus>=3.6.1,<4.0; canonical quality/release docs match that bound.
  - sensor platform setup loads translation data that the inspected error sensor classes store but do not consume.
derived:
  - The remaining repository-local follow-ups can be closed with bounded governance and sensor setup changes.
unknown:
  - Post-hardening reconnect and 24-72 hour soak behavior on a physical AirPack.
conflicts: []
first_failure:
  marker: checkpoint-governance-coverage
  evidence: .github/workflows/ci.yaml names only the two 2026-08-10 task files, leaving the 2026-08-11 checkpoint unchecked.
rejected_hypotheses:
  - An open pull request or issue was waiting to be completed before this task.
  - Canonical dependency documentation is stale relative to current main.
changed_paths:
  - docs/agents/tasks/TASK-20260811-post-audit-closure.md
validation:
  - command: python tools/agents/checkpoint.py --tasks docs/agents/tasks --require-checkpoint
    result: NOT_RUN
    evidence: Full-directory checkpoint validation is not yet wired into CI on this branch.
  - command: pre-commit run --all-files
    result: NOT_RUN
    evidence: Validation will run after the bounded implementation is committed.
  - command: pylint custom_components/thessla_green_modbus
    result: NOT_RUN
    evidence: Validation will run after the bounded implementation is committed.
  - command: pytest -q
    result: NOT_RUN
    evidence: Validation will run after the bounded implementation is committed.
blockers: []
next_action: Repair the invalid historical checkpoint, expand CI checkpoint coverage, and remove the redundant sensor translation setup path with regression coverage.
```
