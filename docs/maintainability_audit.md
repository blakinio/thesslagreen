# Maintainability audit

Date: 2026-04-30

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user)*
- `ruff check custom_components tests tools` *(passed)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `python tools/compare_registers_with_reference.py` *(passed; reports 62 extra integration entries and 242 name mismatches to verify with vendor)*
- `python tools/check_maintainability.py` *(passed)*
- `pytest tests/ -q` *(passed; 4 skipped)*
- `python tools/validate_entity_mappings.py` *(passed; 366 entities validated)*

## 1) CI status and maintained CI gates

The repository CI workflow (`.github/workflows/ci.yaml`) currently enforces three jobs:

1. **Lint**: dependency install, `ruff check`, `python -m compileall`, `python tools/compare_registers_with_reference.py`, and `python tools/check_maintainability.py`.
2. **Tests**: `pytest --cov --cov-report=xml --cov-report=term -q` plus Codecov upload.
3. **Entity mappings validation**: `python tools/validate_entity_mappings.py`.

The local validation run used the same functional gates and all passed in this audit run.

## 2) Largest files (by non-empty lines)

1. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (717)
2. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (586)
3. `tests/test_entity_mappings.py` (526)
4. `custom_components/thessla_green_modbus/scanner/io_read.py` (520)
5. `tests/test_coordinator.py` (502)
6. `tests/test_register_loader.py` (478)
7. `tests/test_scanner_io_coverage.py` (472)
8. `tests/test_modbus_helpers.py` (463)
9. `custom_components/thessla_green_modbus/scanner/core.py` (461)
10. `tests/test_register_decoders.py` (455)
11. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (455)
12. `custom_components/thessla_green_modbus/mappings/_static_sensors.py` (437)
13. `custom_components/thessla_green_modbus/config_flow.py` (437)
14. `custom_components/thessla_green_modbus/modbus_helpers.py` (431)
15. `custom_components/thessla_green_modbus/coordinator/schedule.py` (430)

Interpretation: the largest remaining production hotspots are still coordinator orchestration, mapping construction/static mapping modules, and scanner I/O/core.

## 3) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (650)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (438)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (432)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (280)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (254)
7. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (237)
8. `ConfigFlow` in `config_flow.py` (217)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenBinarySensor` in `binary_sensor.py` (175)

## 4) Largest functions/methods

1. `async_write_register` in `coordinator/schedule.py` (133)
2. `verify_connection` in `scanner/setup.py` (127)
3. `_post_process_data` in `coordinator/capabilities.py` (127)
4. `run_full_scan` in `scanner/orchestration.py` (125)
5. `register_maintenance_services` in `services_handlers_maintenance.py` (122)
6. `validate_input_impl` in `config_flow_device_validation.py` (120)
7. `scan_device` in `scanner/orchestration.py` (110)
8. `read_holding` in `scanner/io_read.py` (110)
9. `register_parameter_services` in `services_handlers_parameters.py` (109)
10. `async_write_registers` in `coordinator/schedule.py` (109)

## 5) Completed refactors reflected in current dev state (latest merged batch #1449-#1454)

- #1449: scanner test coverage split and stabilization landed; scanner coverage is now concentrated in focused suites.
- #1450: config-flow validation/schema helper decomposition landed; legacy monolithic validation structure is reduced.
- #1451: coordinator package public API contract was tightened and tests now guard minimal package surface.
- #1452: coordinator device/register-processing tests were split into narrower modules.
- #1453: mapping-builder helper decomposition landed; `mappings/_mapping_builders.py` remains a top hotspot but is now explicitly staged for continued extraction.
- #1454: maintenance service handler decomposition landed; `register_maintenance_services` remains long but helper extraction is in place.

## 6) Current invariants and architectural constraints (verified)

- `coordinator/` is canonical.
- Top-level `custom_components/thessla_green_modbus/coordinator.py` is absent and must remain absent.
- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.

## 7) Remaining hotspots and recommended next PRs

1. Continue splitting `custom_components/thessla_green_modbus/coordinator/coordinator.py` by moving update-cycle responsibilities into existing coordinator mixins/modules.
2. Continue decomposition of `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` and static mapping modules where responsibilities overlap.
3. Split `custom_components/thessla_green_modbus/scanner/io_read.py` (`read_holding`/`read_input`) into smaller normalization/retry helpers.
4. Reduce `custom_components/thessla_green_modbus/scanner/core.py` complexity via orchestration helper extraction.
5. Decompose `register_maintenance_services` in `services_handlers_maintenance.py` to reduce function breadth and coordinator-service coupling.

## 8) Validation outcome summary

- Full pytest: **passed** (4 skipped).
- Maintainability gate: **passed**.
