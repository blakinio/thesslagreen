# Home 3.11 register-to-HA acceptance

The owner requested actual HA actions for every applicable register, rather than
equating harness/unit coverage with live HA acceptance. Private evidence lives in
the task workspace `work/ha_*` and sibling `outputs/register-e2e`. Preserve the
existing 344 entity IDs and restore every mutated word immediately. Use only the
HA coordinator connection; a concurrent PC Modbus client causes contention.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-28T17:20:00+01:00
task: TASK-20261028-register-ha-e2e
branch: codex/fix-home-311-filter-ack
head: c0d4a1e8b0454c436d9065992f14b6d57e8d981c
pr: https://github.com/blakinio/thesslagreen/pull/1807
status: validating
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
owned_paths:
  - custom_components/thessla_green_modbus/services/handlers_register_read.py
  - custom_components/thessla_green_modbus/core/schedule_values.py
  - tests/test_register_read_diagnostics.py
proven:
  - Fresh HA-owned reads cover all 357 definitions: 338 successful, 19 explicit device exceptions.
  - 170 distinct native HA actions passed write/read/restore and displayed/restored state checks.
  - New read_register_diagnostics service never writes and preserves atomic RTC/lock-date reads.
  - Live dashboard shows 80 percent on both fans, nonzero flows and no active alarms.
  - All 56 schedule temperatures passed set/read/display/clear/restore; actual dashboard save and clear buttons passed.
  - Comfort write-one remains zero; fixed coordinator now reports rejection and HA stays off, confirmed by logs.
derived:
  - Baseline includes 178 applicable native write cases; absent accessories and protected controls are separate.
unknown:
  - Corrected mode aliases cfg_mode_1 and cfg_mode_2 and final mode action need live acceptance after restart.
  - No documented firmware 3.11 calibration-start command has been established.
conflicts: []
first_failure:
  marker: schedule-temperature-clear
  evidence: Existing service could set TT but could not restore unset TT; explicit clear_temperature added.
rejected_hypotheses:
  - An immediate old HA state proves the write failed; time/text refresh asynchronously.
  - A write acknowledgement establishes that the device applied the setting; comfort remained zero after writing one.
changed_paths:
  - custom_components/thessla_green_modbus/services/handlers_register_read.py
  - custom_components/thessla_green_modbus/coordinator/schedule.py
  - custom_components/thessla_green_modbus/clock_sync.py
  - custom_components/thessla_green_modbus/services/handlers_maintenance.py
  - custom_components/thessla_green_modbus/manifest.json
  - pyproject.toml
  - requirements.txt
  - custom_components/thessla_green_modbus/services/handlers_schedule.py
  - custom_components/thessla_green_modbus/core/schedule_values.py
  - custom_components/thessla_green_modbus/select.py
  - custom_components/thessla_green_modbus/services/schema.py
  - custom_components/thessla_green_modbus/services/__init__.py
  - custom_components/thessla_green_modbus/services.yaml
  - custom_components/thessla_green_modbus/strings.json
  - custom_components/thessla_green_modbus/translations/en.json
  - custom_components/thessla_green_modbus/translations/pl.json
  - tests/test_register_read_diagnostics.py
  - tests/test_schedule_temperature_roundtrip.py
  - tests/test_write_readback.py
  - tests/test_clock_sync.py
  - tests/test_quality_scale_services_maintenance_remaining.py
  - tests/test_home_hardware_acceptance_guards.py
validation:
  - command: pytest tests/ --cov
    result: PASS
    evidence: 3594 passed, 3 skipped, 98.42 percent; all module gates pass; installed with SHA verification and backup.
  - command: ruff; format; mypy; translation and maintainability checks
    result: PASS
    evidence: Current production/test changes passed before live installation.
blockers: []
next_action: After HA restarts, retake cfg_mode_1 and cfg_mode_2 and mode actions, then verify the complete configuration restoration and final raw-to-HA matrix.
```
