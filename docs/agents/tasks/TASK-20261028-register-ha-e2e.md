# Home 3.11 register-to-HA acceptance

The owner requested actual HA actions for every applicable register, rather than
equating harness/unit coverage with live HA acceptance. Private evidence lives in
the task workspace `work/ha_*` and sibling `outputs/register-e2e`. Preserve the
existing 344 entity IDs and restore every mutated word immediately. Use only the
HA coordinator connection; a concurrent PC Modbus client causes contention.

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-10-28T18:19:14+01:00
task: TASK-20261028-register-ha-e2e
branch: codex/fix-home-311-filter-ack
head: b3c23bb36d8c4433e433765ca1ad1a80c48f2bd7
pr: https://github.com/blakinio/thesslagreen/pull/1807
status: ready
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
owned_paths:
  - custom_components/thessla_green_modbus/services/handlers_register_read.py
  - custom_components/thessla_green_modbus/core/schedule_values.py
  - tests/test_register_read_diagnostics.py
proven:
  - Fresh HA-owned reads cover all 357 definitions: 338 successful, 19 explicit device exceptions.
  - 177 distinct native HA actions passed write/read/restore and displayed/restored state checks, including both mode aliases.
  - New read_register_diagnostics service never writes and preserves atomic RTC/lock-date reads.
  - Live dashboard shows 80 percent on both fans, nonzero flows and no active alarms.
  - All 56 schedule temperatures passed set/read/display/clear/restore; actual dashboard save and clear buttons passed.
  - Comfort write-one remains zero; fixed coordinator now reports rejection and HA stays off, confirmed by logs.
  - Fan off/on preserves auto, manual and temporary modes and the existing 30/80 targets in actual HA.
  - Eleven additional main-action cases and three clock actions passed with physical readback.
  - All 265 responding writable definitions excluding the four progressing RTC words match the initial raw baseline.
  - Final registry preserves exactly the original 344 entity IDs; all 15 deployed production files match local SHA256.
  - HA presentation matches 331 direct values; two flow samples differ by 2 cubic metres per hour across acquisition times; no unexplained mismatch.
  - Loopback-only fault tests pass 17 transport cases and 54 individual alarm codes, with no physical fault injection.
derived:
  - Baseline includes 178 applicable native write cases; absent accessories and protected controls are separate.
unknown:
  - No documented firmware 3.11 calibration-start command has been established.
  - Factory/security/service resets, inactive alarm acknowledgement semantics and absent accessories have no blanket physical write acceptance.
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
  - custom_components/thessla_green_modbus/fan.py
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
  - tests/test_fan_resume_stored_operation.py
  - tests/test_dashboard_writable_entities.py
validation:
  - command: pytest tests/ --cov
    result: PASS
    evidence: 3598 passed, 3 skipped, 98.42 percent; all module gates pass; installed with SHA verification and backup.
  - command: ruff; format; mypy; translation and maintainability checks
    result: PASS
    evidence: Current production/test changes passed before live installation.
blockers: []
next_action: Review draft PR 1807 together with the explicit unsupported and untested command boundaries; applicable reversible live tests are complete.
```
