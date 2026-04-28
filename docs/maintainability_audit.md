# Maintainability audit

Date: 2026-04-28

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt`
- `ruff check custom_components tests tools`
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `pytest tests/ -q`
- `python tools/check_maintainability.py`

Results summary:

- Lint passed.
- Compile check passed.
- Test suite passed (with expected skips for optional extras such as `pypdf`).
- Maintainability gate script passed (`Maintainability gate passed.`).

## 1) Largest files (by non-empty lines)

Top maintainability pressure points:

1. `tests/test_scanner_coverage.py` (~2058)
2. `tests/test_config_flow.py` (~1907)
3. `tests/test_device_scanner.py` (~1565)
4. `tests/test_coordinator_coverage.py` (~1519)
5. `tests/test_services_handlers.py` (~1114)
6. `tests/test_coordinator.py` (~931)
7. `tests/test_modbus_transport.py` (~857)
8. `custom_components/thessla_green_modbus/coordinator.py` (~738)
9. `tests/test_optimized_integration.py` (~693)
10. `tests/test_entity_mappings.py` (~683)

Interpretation: maintainability risk is concentrated mostly in tests (very large multipurpose files), with one significant production hotspot (`coordinator.py`).

## 2) Largest classes

Top class-size hotspots:

1. `ThesslaGreenModbusCoordinator` in `coordinator.py` (~674 lines)
2. `_CoordinatorScheduleMixin` in `_coordinator_schedule.py` (~450)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (~432)
4. `ThesslaGreenClimate` in `climate.py` (~333)
5. `RegisterDefinition` in `registers/schema.py` (~313)

Interpretation: the coordinator/scheduler/scanner stack remains the core complexity center. Given current constraints, this should be monitored but not structurally moved yet.

## 3) Largest methods/functions

Top function-size hotspots:

1. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` (~245)
2. `register_maintenance_services` in `services_handlers_maintenance.py` (~192)
3. `main` in `tools/validate_entity_mappings.py` (~176)
4. `read_holding` in `scanner/io_read.py` (~154)
5. `validate_input_impl` in `config_flow_device_validation.py` (~151)
6. `_post_process_data` in `_coordinator_capabilities.py` (~149)
7. `read_input` in `scanner/io_read.py` (~145)
8. `async_write_registers` in `_coordinator_schedule.py` (~145)
9. `register_parameter_services` in `services_handlers_parameters.py` (~139)
10. `async_write_register` in `_coordinator_schedule.py` (~137)

Interpretation: mapping builders and service registration logic are strong candidates for decomposition into smaller pure helpers.

## 4) Files with mixed responsibilities

Priority mixed-responsibility candidates:

- `custom_components/thessla_green_modbus/services_handlers_maintenance.py`
  - mixes service registration, parameter validation, and business workflows.
- `custom_components/thessla_green_modbus/services_handlers_parameters.py`
  - mixes schema-level validation and runtime execution.
- `custom_components/thessla_green_modbus/config_flow.py`
  - contains step orchestration plus nontrivial validation/transform logic.
- `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`
  - handles loading, shaping, and extension logic in one location.
- `custom_components/thessla_green_modbus/diagnostics.py`
  - combines HA diagnostics API surface with anomaly analysis helpers.

## 5) Tests relying on private internals

Examples identified by underscore-import pattern:

- `tests/test_services_handlers.py` imports `_LogLevelManager`, `_validate_gwc_temperature_range`.
- `tests/test_entity_mappings.py` imports `_infer_icon`, `_parse_states`.
- `tests/test_modbus_helpers.py` imports `_SIG_CACHE`, `_get_signature`, `_mask_frame`, `_build_request_frame`, `_calculate_backoff_delay`.
- `tests/test_diagnostics.py` imports `_detect_data_anomalies`, `_run_executor_job`, `_redact_sensitive_data`.
- `tests/test_sensor_platform.py` imports `_format_error_status_code`.
- `tests/test_misc_helpers.py` / `tests/test_device_scanner.py` import scanner helper underscored functions.

Risk: these tests can over-couple to implementation details and make safe internal refactors harder.

## 6) Next 5 safest refactor PRs

Ordered for low risk and high maintainability gain (excluding restricted coordinator/scanner/registers/transport boundary work):

1. **Split `tests/test_config_flow.py` into focused test modules**
   - e.g. reauth, options, discovery, error paths.
2. **Split `tests/test_services_handlers.py` by service domain**
   - maintenance vs parameters vs logging behavior.
3. **Extract pure helper functions from `mappings/_mapping_builders.py`**
   - no behavior change; add direct unit tests for extracted helpers.
4. **Reduce private-internal coupling in tests**
   - prefer public entrypoints where feasible; retain targeted private tests only where contract-like.
5. **Isolate config-flow validation helpers from orchestration**
   - move validation/normalization utilities to dedicated helper module(s) with direct tests.

## 7) Things not to touch yet

- `custom_components/thessla_green_modbus/coordinator.py` location and coordinator package migration.
- `_coordinator_*.py` boundary changes.
- `scanner/`, `registers/`, and `transport/` structural moves.
- Compatibility shims/proxy modules/re-export modules.
- Test rewrites that alter coordinator/scanner/register/transport behavioral coverage semantics.

## Notes

This audit intentionally avoids production code changes and focuses on mapping a low-risk refactor sequence for future PRs.
