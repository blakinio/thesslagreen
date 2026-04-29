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

Interpretation: maintainability pressure is still concentrated mostly in tests, with one significant production hotspot (`coordinator.py`).

## 2) Largest classes

Top class-size hotspots:

1. `ThesslaGreenModbusCoordinator` in `coordinator.py` (~674 lines)
2. `_CoordinatorScheduleMixin` in `_coordinator_schedule.py` (~450)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (~432)
4. `ThesslaGreenClimate` in `climate.py` (~333)
5. `RegisterDefinition` in `registers/schema.py` (~313)

Interpretation: the coordinator/scheduler/scanner stack remains the core complexity center. Per current constraints, this should be reduced incrementally without moving `coordinator.py`.

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

Interpretation: mapping builders plus service registration/orchestration remain strong candidates for further decomposition into smaller pure helpers.

## 4) Files with mixed responsibilities

Priority mixed-responsibility candidates:

- `custom_components/thessla_green_modbus/services_handlers_maintenance.py`
  - mixes service registration, validation, and workflow orchestration.
- `custom_components/thessla_green_modbus/services_handlers_parameters.py`
  - mixes schema-level validation and runtime execution wiring.
- `custom_components/thessla_green_modbus/config_flow.py`
  - still combines step orchestration with some nontrivial branching.
- `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`
  - combines loading, shaping, and extension logic in one location.
- `custom_components/thessla_green_modbus/diagnostics.py`
  - combines diagnostics API handling with anomaly-analysis helpers.

## 5) Recently completed refactors reflected in repo state

Completed and visible in current repository layout:

1. **Config flow tests split by flow area**
   - focused modules exist (e.g. user, reauth, options, discovery, validation, helpers).
2. **Service handler tests split by domain**
   - focused modules exist for maintenance/parameters/modes/schedule/logging/targets and related areas.
3. **Coordinator tests split**
   - focused modules exist for setup, connection/transport, scan/capabilities, statistics, lifecycle, errors, offline, and coverage/contract paths.
4. **Scanner tests split**
   - focused modules exist for setup, I/O, orchestration, capabilities/firmware logic, and coverage scenarios.
5. **Modbus transport tests split**
   - focused modules exist for base/core, raw, RTU/TCP behavior, retry/backoff/lifecycle, compat and error paths.
6. **Config-flow helper extraction completed**
   - helper/validation/schema modules are present and used (`config_flow_helpers.py`, `config_flow_device_validation.py`, `config_flow_schema.py`, etc.).
7. **Service handler helper extraction completed**
   - helper modules are present and used (`services_handlers_helpers.py`, `services_handlers_maintenance_helpers.py`, `services_handlers_parameters_helpers.py`, etc.).
8. **Mapping helper extraction started**
   - mapping logic is partially centralized in helper/builder modules and remains an active hotspot.
9. **Coordinator IO facade removed**
   - coordinator path is flatter around direct mixin/helper usage (without reintroducing facade/proxy layer).
10. **Register loader split completed**
    - register loading/definition responsibilities are split across dedicated modules.
11. **Transport retry/error contract introduced**
    - transport retry/error behavior is covered with focused code/tests around explicit handling paths.
12. **Scanner core facade cleanup completed**
    - scanner structure reflects direct responsibilities without compatibility facade reintroduction.

## 6) Next 5 safest refactor PRs

Ordered for low risk and maintainability gain while honoring current constraints:

1. **Continue decomposing `mappings/_mapping_builders.py`**
   - extract pure transformation helpers (no behavior change) and add direct unit tests.
2. **Further split registration wiring in `services_handlers_maintenance.py`**
   - separate schema declaration, dispatch tables, and execution callbacks.
3. **Further split registration wiring in `services_handlers_parameters.py`**
   - isolate reusable schema/validation fragments and runtime write orchestration.
4. **Reduce private-internal test coupling where low-risk**
   - prefer public entrypoints when practical; keep private tests only where they represent stable contracts.
5. **Incrementally shrink large coordinator methods**
   - extract pure computation helpers only, while keeping `coordinator.py` in place and import paths stable.

## 7) Things not to touch yet

- Do not move `custom_components/thessla_green_modbus/coordinator.py` yet.
- Do not recreate `custom_components/thessla_green_modbus/coordinator/` until a dedicated real migration PR exists.
- No compatibility shims.
- No proxy modules.
- No re-export-only modules.
- No legacy modules.
- No structural moves across `scanner/`, `registers/`, and `transport/` boundaries in this stage.

## Notes

This audit is intentionally factual and repository-backed, with no speculative features and no migration-document content.
