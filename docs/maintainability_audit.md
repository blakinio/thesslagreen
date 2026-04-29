# Maintainability audit

Date: 2026-04-29

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt`
- `ruff check custom_components tests tools` *(fails currently due to an existing test lint issue: `tests/test_device_scanner.py:253` unused local `result`)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `pytest tests/ -q` *(passed; 4 skipped)*
- `python tools/check_maintainability.py` *(passed)*

## 1) Largest files (by non-empty lines)

1. `tests/test_scanner_coverage.py` (~1255)
2. `tests/test_coordinator_coverage.py` (~1061)
3. `tests/test_config_flow_validation.py` (~865)
4. `tests/test_coordinator.py` (~743)
5. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (~737)
6. `tests/test_entity_mappings.py` (~683)
7. `tests/test_config_flow_user.py` (~638)
8. `tests/test_services_handlers_parameters.py` (~523)
9. `tests/test_config_flow_helpers.py` (~508)
10. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (~500)

Interpretation: the largest hotspots are still primarily in tests, while `coordinator/coordinator.py` and `mappings/_mapping_builders.py` remain the most notable production-scale modules.

## 2) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (~585)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (~408)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (~394)
4. `RegisterDefinition` in `registers/schema.py` (~273)
5. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (~246)

## 3) Largest methods/functions

1. `main` in `tools/validate_entity_mappings.py` (~156)
2. `register_maintenance_services` in `services_handlers_maintenance.py` (~146)
3. `read_holding` in `scanner/io_read.py` (~136)
4. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` (~133)
5. `async_write_register` in `coordinator/schedule.py` (~123)
6. `run_full_scan` in `scanner/orchestration.py` (~122)
7. `verify_connection` in `scanner/setup.py` (~121)
8. `_post_process_data` in `coordinator/capabilities.py` (~120)
9. `scan` in `scanner/orchestration.py` (~119)
10. `read_input` in `scanner/io_read.py` (~119)

## 4) Completed refactors reflected in current state (PRs #1411–#1421)

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

1. Split `tests/test_scanner_coverage.py` further by scanner flow domains (setup, I/O, orchestration, cache/error contracts).
2. Split `tests/test_coordinator_coverage.py` further by coordinator concern areas (init/config, read cycle, write flow, retry/reconnect, capabilities).
3. Decompose `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`, starting with `_extend_entity_mappings_from_registers` and `_load_discrete_mappings`.
4. Decompose `custom_components/thessla_green_modbus/services_handlers_maintenance.py` registration workflow into narrower helpers.
5. Reduce private helper coupling in tests where feasible by asserting package-level contracts.
