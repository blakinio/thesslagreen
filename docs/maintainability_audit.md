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
2. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (603)
3. `custom_components/thessla_green_modbus/scanner/io_read.py` (553)
4. `tests/test_entity_mappings.py` (526)
5. `tests/test_coordinator.py` (502)
6. `tests/test_register_loader.py` (478)
7. `tests/test_scanner_io_coverage.py` (472)
8. `tests/test_modbus_helpers.py` (463)
9. `custom_components/thessla_green_modbus/scanner/core.py` (477)
10. `tests/test_register_decoders.py` (455)
11. `custom_components/thessla_green_modbus/coordinator/schedule.py` (448)
12. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (438)
13. `custom_components/thessla_green_modbus/config_flow.py` (437)
14. `custom_components/thessla_green_modbus/modbus_helpers.py` (431)
15. `custom_components/thessla_green_modbus/const.py` (428)

Interpretation: the largest remaining production hotspots are still coordinator orchestration, mapping construction/static mapping modules, and scanner I/O/core.

## 3) Largest classes

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (650)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (460)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (449)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (293)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (254)
7. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (230)
8. `ConfigFlow` in `config_flow.py` (217)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenBinarySensor` in `binary_sensor.py` (175)

## 4) Largest functions/methods

1. `async_write_register` in `coordinator/schedule.py` (131)
2. `run_full_scan` in `scanner/orchestration.py` (125)
3. `register_maintenance_services` in `services_handlers_maintenance.py` (122)
4. `_post_process_data` in `coordinator/capabilities.py` (120)
5. `validate_input_impl` in `config_flow_device_validation.py` (120)
6. `scan_device` in `scanner/orchestration.py` (110)
7. `read_input` in `scanner/io_read.py` (105)
8. `read_with_retry` in `coordinator/retry.py` (106)
9. `async_write_registers` in `coordinator/schedule.py` (96)
10. `_call_modbus` in `modbus_helpers.py` (95)

## 5) Completed refactors reflected in current dev state (latest merged batch #1472-#1483)

- #1472, #1468, #1467: mapping-builder decomposition continued across multiple PRs; `_mapping_builders.py` remains largest mapping hotspot but helper extraction and duplication reduction progressed.
- #1473 and #1480: maintenance/parameter service handler decomposition continued; largest service registration methods remain candidates for deeper extraction.
- #1474 and #1465: coordinator update-cycle and implementation decomposition landed; monolithic coordinator responsibilities were pushed into helper/mixin boundaries.
- #1475, #1476, and #1482: scanner read-path/core/connection-verification decomposition landed; scanner logic is now more segmented across `io_read.py`, `orchestration.py`, and `setup.py`.
- #1477 and #1483: coordinator write scheduling and capability post-processing were decomposed, reducing peak method sizes and isolating write/capability responsibilities.
- #1478: raw transport helper complexity was reduced in `modbus_transport_raw.py`.

## 6) Current invariants and architectural constraints (verified)

- `coordinator/` is canonical.
- Top-level `custom_components/thessla_green_modbus/coordinator.py` is absent and must remain absent.
- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.

## 7) Remaining hotspots and recommended next PRs

1. Continue splitting `custom_components/thessla_green_modbus/coordinator/coordinator.py` (still 717 non-empty lines) by moving additional orchestration/state transitions into dedicated coordinator modules.
2. Continue decomposition of `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (603 lines), prioritizing extraction by domain slice and reducing cross-builder condition branching.
3. Continue scanner I/O decomposition in `custom_components/thessla_green_modbus/scanner/io_read.py` (553 lines), especially around `read_input` and shared error/normalization flows.
4. Reduce `custom_components/thessla_green_modbus/scanner/core.py` (477 lines) complexity by pushing remaining constructor/setup and state bookkeeping logic into narrower helpers.
5. Further decompose `register_maintenance_services` (122 lines) and related service registration helpers to reduce breadth and improve test targeting.

## 8) Validation outcome summary

- Full pytest: **passed** (4 skipped).
- Maintainability gate: **passed**.
