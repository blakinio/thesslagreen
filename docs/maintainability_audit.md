# Maintainability audit

Date: 2026-04-30

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user)*
- `ruff check custom_components tests tools` *(passed)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `pytest tests/ -q` *(failed: 7 tests, 4 skipped)*
- `python tools/check_maintainability.py` *(passed)*

## 1) Largest files (by non-empty lines)

1. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (~746)
2. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (~632)
3. `tests/test_config_flow_user.py` (~583)
4. `tests/test_config_flow_helpers.py` (~537)
5. `tests/test_entity_mappings.py` (~526)
6. `tests/test_coordinator.py` (~502)
7. `custom_components/thessla_green_modbus/scanner/io_read.py` (~495)
8. `tests/test_register_loader.py` (~478)
9. `tests/test_scanner_io_coverage.py` (~472)
10. `tests/test_modbus_helpers.py` (~463)

Interpretation: hotspot pressure is still mixed test + production. Largest production hotspots are `coordinator/coordinator.py`, `mappings/_mapping_builders.py`, `scanner/io_read.py`, and `scanner/core.py`.

## 2) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (~690)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (~438)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (~432)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (~280)
5. `RegisterDef` in `registers/register_def.py` (~268)

## 3) Largest methods/functions

1. `read_holding` in `scanner/io_read.py` (~133)
2. `async_write_register` in `coordinator/schedule.py` (~133)
3. `verify_connection` in `scanner/setup.py` (~127)
4. `_post_process_data` in `coordinator/capabilities.py` (~127)
5. `run_full_scan` in `scanner/orchestration.py` (~125)
6. `register_maintenance_services` in `services_handlers_maintenance.py` (~122)
7. `validate_input_impl` in `config_flow_device_validation.py` (~120)
8. `read_input` in `scanner/io_read.py` (~113)
9. `scan_device` in `scanner/orchestration.py` (~110)
10. `register_parameter_services` in `services_handlers_parameters.py` (~109)

## 4) Completed refactors reflected in current dev state (merged PR batch #1449–#1454)

- #1449: scanner coverage split progressed (coverage now centered in `tests/test_scanner_io_coverage.py` and related focused suites).
- #1450: config-flow validation/schema helpers decomposed (hotspots now led by `test_config_flow_user.py` + `test_config_flow_helpers.py` instead of older monoliths).
- #1451: coordinator package public API tightened (tests and API contract checks target a minimal coordinator package surface).
- #1452: coordinator device/register-processing tests split into focused modules.
- #1453: mapping builder helper decomposition applied; `mappings/_mapping_builders.py` remains a key production hotspot but reduced from earlier monolith shape.
- #1454: maintenance service handler decomposition applied; `register_maintenance_services` remains one of the longer functions but extracted helper structure is present.

## 5) Current invariants and architectural constraints (verified)

- `coordinator/` is canonical.
- Top-level `custom_components/thessla_green_modbus/coordinator.py` is removed.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.
- Coordinator package public API is intentionally constrained (validated by package API tests).

Current audit flags to keep visible:

- Compatibility/proxy/re-export patterns still exist in selected non-coordinator modules (for example `modbus_transport_client.py`, `modbus_exceptions.py`, and explicit compatibility comments in `services.py`); these should not be expanded and should be evaluated for further cleanup only when safe.

## 6) Next recommended PRs

1. Split `custom_components/thessla_green_modbus/coordinator/coordinator.py` by moving additional update-cycle orchestration into existing `coordinator/*` helper modules.
2. Continue decomposing `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`, starting with `_extend_entity_mappings_from_registers` follow-up extraction.
3. Decompose `custom_components/thessla_green_modbus/scanner/io_read.py` (`read_holding`/`read_input`) into narrower I/O normalization helpers.
4. Split remaining broad config-flow tests in `tests/test_config_flow_user.py` and `tests/test_config_flow_helpers.py` into path-focused suites.
5. Further break down `register_maintenance_services` in `services_handlers_maintenance.py` to reduce coordinator-service coupling per function.

## 7) Validation outcome summary

- Full pytest: **failed** (7 failing tests, 4 skipped).
- Maintainability gate: **passed**.
