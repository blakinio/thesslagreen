# Maintainability audit

Date: 2026-04-29

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt`
- `ruff check custom_components tests tools` *(passed)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `pytest tests/ -q` *(passed; 4 skipped)*
- `python tools/check_maintainability.py` *(passed)*

## 1) Largest files (by non-empty lines)

1. `tests/test_scanner_coverage.py` (~1171)
2. `tests/test_config_flow_validation.py` (~865)
3. `tests/test_coordinator_update_cycle.py` (~829)
4. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (~746)
5. `tests/test_coordinator.py` (~743)
6. `tests/test_entity_mappings.py` (~683)
7. `tests/test_config_flow_user.py` (~638)
8. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (~567)
9. `tests/test_services_handlers_parameters.py` (~523)
10. `tests/test_config_flow_helpers.py` (~508)

Interpretation: hotspot pressure remains test-heavy; the largest production modules are still `coordinator/coordinator.py`, `mappings/_mapping_builders.py`, and scanner I/O helpers (`scanner/io_read.py`).

## 2) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (~690)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (~438)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (~432)
4. `RegisterDefinition` in `registers/schema.py` (~313)
5. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (~280)

## 3) Largest methods/functions

1. `main` in `tools/validate_entity_mappings.py` (~176)
2. `read_holding` in `scanner/io_read.py` (~143)
3. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` (~143)
4. `async_write_register` in `coordinator/schedule.py` (~133)
5. `verify_connection` in `scanner/setup.py` (~127)
6. `_post_process_data` in `coordinator/capabilities.py` (~127)
7. `run_full_scan` in `scanner/orchestration.py` (~125)
8. `register_maintenance_services` in `services_handlers_maintenance.py` (~125)
9. `read_input` in `scanner/io_read.py` (~125)
10. `validate_input_impl` in `config_flow_device_validation.py` (~114)

## 4) Completed refactors reflected in current dev state (latest merged PR batch #1411–#1421)

- Diagnostics helper split completed.
- Service metadata/translations consistency alignment completed.
- Tooling/CI alignment completed.
- Optimized integration test split completed.
- Registers codec helper extraction completed.
- Transport layer cleanup completed.
- Climate helper extraction completed.
- Scanner/device-scanner register and coverage test splits completed.
- Coordinator register-write test split completed.
- Coordinator schedule/capabilities helper extraction completed.

## 5) Current invariants and architectural constraints (verified)

- `coordinator/` is canonical.
- Top-level `custom_components/thessla_green_modbus/coordinator.py` is removed.
- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- No legacy modules.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.

## 6) Next recommended PRs

1. Continue splitting `tests/test_scanner_coverage.py` into focused behavior suites (setup, I/O, orchestration, cache/error contracts).
2. Further split coordinator-focused tests around update cycle vs retry/offline/error paths to reduce per-file coupling.
3. Decompose `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`, starting with `_extend_entity_mappings_from_registers` and discrete mapping load helpers.
4. Refactor `custom_components/thessla_green_modbus/scanner/io_read.py` (`read_holding`/`read_input`) into narrower read/normalize helpers.
5. Decompose `custom_components/thessla_green_modbus/services_handlers_maintenance.py` registration workflow into smaller composable helpers.
