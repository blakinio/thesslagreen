---
task_id: TASK-20260811-firmware-coverage
status: implementing
owner: codex
scope: improve firmware identity semantics and scanner coverage without changing Modbus transport contracts
---

# Firmware identity and coverage hardening

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-11T14:49:00Z
head: ae3cdd7195088f207f5e87c74c519bb799676233
branch: feat/firmware-coverage-20260811
pr: null
status: implementing
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/audits/deep_audit_2026-08-11.md
owned_paths:
  - custom_components/thessla_green_modbus/scanner/firmware.py
  - tests/test_device_scanner_firmware.py
  - docs/agents/tasks/TASK-20260811-firmware-coverage.md
proven:
  - main baseline is ae3cdd7195088f207f5e87c74c519bb799676233 and post-merge CI run 31503102829 passed all mandatory jobs.
  - scanner/firmware.py treats a missing version_patch as expected on some older firmware but still leaves firmware Unknown and firmware_available false.
  - tests/test_device_scanner_firmware.py covers fully unavailable, full fallback, and partial bulk fallback cases but not the expected older-device case where major and minor exist and patch is absent.
  - the prior audit measured scanner/firmware.py among the lowest-covered integration modules.
derived:
  - major and minor together provide useful verified firmware identity when patch is genuinely unavailable on an older unit.
  - a conservative partial-version representation can improve identity without altering Modbus addresses, transport behavior, write semantics, entity IDs, or services.
unknown:
  - exact physical AirPack behavior of the newest main candidate; no live Home Assistant connector is currently exposed in this session.
  - whether repository-wide coverage will reach Silver thresholds from this bounded task alone.
conflicts: []
first_failure:
  marker: firmware-partial-version-semantics
  evidence: _apply_firmware_version_to_device logs missing patch at DEBUG as expected hardware behavior but sets firmware_available false and leaves firmware Unknown.
rejected_hypotheses:
  - missing version_patch always indicates a communication failure.
  - hardware-sensitive polling or restart-scan defaults should be changed without new physical-device measurements.
changed_paths:
  - docs/agents/tasks/TASK-20260811-firmware-coverage.md
validation:
  - command: GitHub inspection of main and post-merge CI 31503102829
    result: PASS
    evidence: baseline main and all mandatory CI jobs are green before this task.
  - command: focused firmware tests after implementation
    result: NOT_RUN
    evidence: implementation not yet committed.
blockers: []
next_action: Implement and test explicit major.minor partial firmware identity, then run the complete GitHub Actions matrix before merge.
```