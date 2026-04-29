# Maintainability audit

Date: 2026-04-29

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt`
- `ruff check custom_components tests tools`
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `pytest tests/ -q`
- `python tools/check_maintainability.py`

## 1) Largest files (by non-empty lines)

1. `tests/test_scanner_coverage.py` (~1441)
2. `tests/test_coordinator_coverage.py` (~1364)
3. `tests/test_config_flow_validation.py` (~865)
4. `tests/test_device_scanner.py` (~840)
5. `tests/test_coordinator.py` (~787)
6. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (~736)
7. `tests/test_optimized_integration.py` (~693)
8. `tests/test_entity_mappings.py` (~683)
9. `tests/test_config_flow_user.py` (~638)
10. `tests/test_services_handlers_parameters.py` (~523)

Interpretation: pressure remains primarily in test modules, with the coordinator package implementation (`coordinator/coordinator.py`) still the main production hotspot.

## 2) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (~674)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (~450)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (~432)
4. `ThesslaGreenClimate` in `climate.py` (~333)
5. `RegisterDefinition` in `registers/schema.py` (~313)

## 3) Largest methods/functions

1. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` (~210)
2. `main` in `tools/validate_entity_mappings.py` (~176)
3. `validate_input_impl` in `config_flow_device_validation.py` (~151)
4. `register_maintenance_services` in `services_handlers_maintenance.py` (~151)
5. `_post_process_data` in `coordinator/capabilities.py` (~149)
6. `async_write_registers` in `coordinator/schedule.py` (~145)
7. `async_write_register` in `coordinator/schedule.py` (~137)
8. `read_holding` in `scanner/io_read.py` (~135)
9. `build_connection_schema` in `config_flow_schema.py` (~135)
10. `scan` in `scanner/orchestration.py` (~131)

## 4) Completed refactors reflected in current state

- Coordinator package migration completed (`coordinator/` canonical; old top-level `coordinator.py` removed).
- Services dispatch/validation helper cleanup completed (`services_dispatch.py` and `services_validation.py` active).
- Scanner I/O read helper cleanup completed (`scanner/io_read.py` and related split modules active).
- Platform/entity helper cleanup completed.

## 5) Next recommended PRs

1. Further split `tests/test_scanner_coverage.py` by capability areas.
2. Further split `tests/test_coordinator_coverage.py` by behavior domains.
3. Decompose `mappings/_mapping_builders.py` large transformation function.
4. Decompose `services_handlers_maintenance.py` registration workflow.
5. Reduce private coupling in tests by favoring package-level contracts where practical.

## 6) Constraints to keep

- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- No legacy modules.
- `core/`, `transport/`, `registers/`, and `scanner/` must not import Home Assistant.
