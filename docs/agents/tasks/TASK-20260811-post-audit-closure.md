---
task_id: TASK-20260811-post-audit-closure
status: implementing
owner: codex
scope: close verified post-audit follow-ups
---

# TASK-20260811-post-audit-closure

## Objective

Close verified repository-local follow-ups discovered while re-auditing `main`: repair agent checkpoint validation coverage/state, synchronize canonical dependency documentation, and remove redundant sensor translation setup work without changing Home Assistant or Modbus contracts.

## Scope

- `.github/workflows/ci.yaml`
- `custom_components/thessla_green_modbus/sensor.py`
- `tests/test_sensor_platform.py`
- `docs/agents/tasks/`
- `docs/audits/deep_audit_2026-08-11.md`
- `docs/quality/STATUS.md`
- `docs/release_readiness.md`

## Checkpoint

```yaml
task_id: TASK-20260811-post-audit-closure
objective: Close verified repository-local post-audit follow-ups without changing public Home Assistant or Modbus contracts.
parent_objective: Complete safe repository-local follow-ups from the 2026-08-11 deep audit
branch: fix/close-audit-followups-20260811
base: main
head: 025a36f78b3629e47421afe1d06b372c1df3aafb
status: implementing
owned_paths:
  - .github/workflows/ci.yaml
  - custom_components/thessla_green_modbus/sensor.py
  - tests/test_sensor_platform.py
  - docs/agents/tasks/
  - docs/audits/deep_audit_2026-08-11.md
  - docs/quality/STATUS.md
  - docs/release_readiness.md
validation:
  - command: python tools/agents/checkpoint.py --tasks docs/agents/tasks --require-checkpoint
    result: NOT_RUN
  - command: pre-commit run --all-files
    result: NOT_RUN
  - command: pylint custom_components/thessla_green_modbus
    result: NOT_RUN
  - command: pytest -q
    result: NOT_RUN
blocked_on: []
last_verified_commit: 025a36f78b3629e47421afe1d06b372c1df3aafb
first_failure:
  marker: none
  evidence: none
next_action: Repair checkpoint governance/state and the verified sensor/documentation follow-ups, then run the mandated validation stack in CI.
```
