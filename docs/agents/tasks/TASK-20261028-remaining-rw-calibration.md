# Remaining RW and Home 3.11 calibration

Continue from the completed register-to-HA acceptance without treating settings
readback as a physical calibration or absent-actuator test. Use only HA's existing
serialized Modbus connection and immediately restore any reversible mutation.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-28T18:53:00+01:00
task: TASK-20261028-remaining-rw-calibration
branch: codex/fix-home-311-filter-ack
head: b95d80ec46f4d88ad921590f75bacb14707f4656
pr: https://github.com/blakinio/thesslagreen/pull/1807
status: ready
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/tasks/TASK-20261028-register-ha-e2e.md
owned_paths:
  - custom_components/thessla_green_modbus/device_profile.py
  - tests/test_configuration_mode_firmware.py
  - custom_components/thessla_green_modbus/coordinator/schedule.py
  - custom_components/thessla_green_modbus/services/handlers_maintenance.py
  - custom_components/thessla_green_modbus/select.py
  - tests/test_review_regressions.py
  - docs/services/home-311-remaining-rw-and-calibration.md
proven:
  - Fresh HA state reports both fans at 80 percent, positive flows and no active alarms.
  - Manufacturer Home protocol page 5 documents configuration_mode 65 as filter control from firmware 4.75, not airflow calibration.
  - Command 65 is gated before I/O in named and raw writes and the service; unavailable option is omitted from the existing select.
  - Five independent implementations inspected at recorded SHAs; none supplies a Home 3.11 airflow-calibration sequence.
  - Fourteen additional native HA changes passed raw change, HA display and raw restore checks; gwc_off request 1 stayed 0 with correct HA error.
  - Fresh reads cover all 280 RW definitions, with 269 successful and 11 explicit exceptions; all 265 non-RTC responding RW words match baseline.
  - Installed four production files with backups and SHA256 checks; HA restarted and preserved 80 percent supply and exhaust with no alarms.
  - Live service and script trace reject AFC with the explicit firmware 4.75 requirement; configuration mode remains 0 and access remains user.
  - All 15 tested HA entity states returned to their original values, including asynchronously refreshed time entities.
derived:
  - Remaining RW includes command and protected words, not only ordinary settings.
  - Fourteen accessory setting-storage tests do not establish physical accessory function on this base-only installation.
unknown:
  - No documented firmware 3.11 airflow-calibration start command established.
  - Exact cause of gwc_off rejection is not established; do not infer firmware or equipment solely from it.
conflicts: []
first_failure:
  marker: missing-command-version-gate
  evidence: Former start_pressure_test allowed command 65 without checking documented firmware 4.75 minimum; now fixed and tested live.
rejected_hypotheses:
  - AFC filter control command 65 is an airflow calibration command for firmware 3.11.
changed_paths:
  - custom_components/thessla_green_modbus/device_profile.py
  - custom_components/thessla_green_modbus/coordinator/schedule.py
  - custom_components/thessla_green_modbus/services/handlers_maintenance.py
  - custom_components/thessla_green_modbus/select.py
  - tests/test_configuration_mode_firmware.py
  - tests/test_review_regressions.py
  - docs/services/home-311-remaining-rw-and-calibration.md
  - docs/agents/tasks/TASK-20261028-remaining-rw-calibration.md
validation:
  - command: pytest tests/ --cov
    result: PASS
    evidence: 3620 passed, 3 skipped, 98.4045 percent, all per-module coverage gates pass.
  - command: ruff check and format; mypy; translations; entity mappings; maintainability
    result: PASS
    evidence: Four production files installed and SHA-verified; physical evidence and remaining-96 CSV in sibling outputs/remaining-rw.
blockers:
  - Physical calibration acceptance requires a manufacturer or hardware verified Home 3.11 command and state sequence; no public source reviewed supplies it.
next_action: Review the scoped patch and remaining-96 matrix; obtain the Home 3.11 service command/state contract before implementing physical calibration.
```
