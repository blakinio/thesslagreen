# Maintainability audit

Date: 2026-04-29

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

1. `tests/test_scanner_coverage.py` (~1441)
2. `tests/test_coordinator_coverage.py` (~1364)
3. `tests/test_config_flow_validation.py` (~865)
4. `tests/test_device_scanner.py` (~840)
5. `tests/test_coordinator.py` (~787)
6. `custom_components/thessla_green_modbus/coordinator.py` (~736)
7. `tests/test_optimized_integration.py` (~693)
8. `tests/test_entity_mappings.py` (~683)
9. `tests/test_config_flow_user.py` (~638)
10. `tests/test_services_handlers_parameters.py` (~523)

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

1. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` (~210)
2. `main` in `tools/validate_entity_mappings.py` (~176)
3. `register_maintenance_services` in `services_handlers_maintenance.py` (~157)
4. `read_holding` in `scanner/io_read.py` (~154)
5. `validate_input_impl` in `config_flow_device_validation.py` (~151)
6. `_post_process_data` in `_coordinator_capabilities.py` (~149)
7. `read_input` in `scanner/io_read.py` (~145)
8. `async_write_registers` in `_coordinator_schedule.py` (~145)
9. `register_parameter_services` in `services_handlers_parameters.py` (~144)
10. `async_write_register` in `_coordinator_schedule.py` (~137)

Interpretation: mapping builders and service registration logic are strong candidates for decomposition into smaller pure helpers.

## 4) Files with mixed responsibilities

Priority mixed-responsibility candidates:

- `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`
  - still combines mapping extension orchestration with many transformation details; helper extraction has started but hotspot remains.
- `custom_components/thessla_green_modbus/services_handlers_maintenance.py`
  - still combines service registration, input normalization, and workflow logic.
- `custom_components/thessla_green_modbus/services_handlers_parameters.py`
  - still mixes validation/schema concerns and runtime execution paths.
- `custom_components/thessla_green_modbus/config_flow.py`
  - step orchestration remains broad, even after helper extraction into focused modules.
- `custom_components/thessla_green_modbus/diagnostics.py`
  - mixes diagnostics API shape and anomaly analysis internals.

## 5) Completed refactors reflected in current state

Completed since earlier audit cycle:

- Config-flow tests split by flow area (`test_config_flow_user/options/reauth/errors/validation/helpers`).
- Service handler tests split by domain (`maintenance/parameters/logging/modes/schedule/targets`).
- Coordinator tests split into focused modules (`setup/connection/scan/statistics/lifecycle/errors/offline` plus targeted helpers).
- Scanner tests split into focused modules (`setup/io/firmware/capabilities/full_scan/safe_scan`).
- Modbus transport tests split into focused modules (`base/raw/rtu/tcp/retry/lifecycle/errors`).
- Mapping helper extraction started (`mappings/_mapping_builders.py` remains active hotspot).
- Config-flow helper extraction completed (`config_flow_*` helper modules present and used).
- Service handler helper extraction completed (domain-focused service handler modules present).
- Coordinator IO facade removed.
- Register loader split completed (`registers/loader.py` + focused helper modules/tests).
- Transport retry/error contract introduced (`tests/test_error_contract.py` and focused transport tests).
- Scanner core facade cleanup completed (scanner modules now separated by responsibilities).

## 6) Next 5 safest refactor PRs

Ordered for low risk and high maintainability gain (excluding restricted coordinator/scanner/registers/transport boundary work):

1. **Continue helper extraction from `mappings/_mapping_builders.py`**
   - reduce the remaining ~210-line builder function via pure transformation helpers.
2. **Split `tests/test_scanner_coverage.py` by capability group**
   - keep scenarios but reduce one very large multipurpose test module.
3. **Split `tests/test_coordinator_coverage.py` by concern**
   - separate scheduling/statistics/error-coverage clusters into focused files.
4. **Reduce private-internal coupling in tests incrementally**
   - move underscore-import tests to public entrypoints where contracts are not private by design.
5. **Decompose `services_handlers_maintenance.py` registration workflow**
   - isolate schema/validation helpers from service wiring and execution paths.

## 7) Things not to touch yet

- `custom_components/thessla_green_modbus/coordinator.py` location and coordinator package migration.
- `_coordinator_*.py` boundary changes.
- `scanner/`, `registers/`, and `transport/` structural moves.
- Compatibility shims/proxy modules/re-export modules.
- Test rewrites that alter coordinator/scanner/register/transport behavioral coverage semantics.

## Notes

This audit intentionally avoids production code changes and focuses on mapping a low-risk refactor sequence for future PRs.
