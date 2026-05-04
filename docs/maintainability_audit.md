# Maintainability audit

Date: 2026-05-04

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user and pip upgrade notice)*
- `ruff check custom_components tests tools` *(passed)*
- `ruff check --select I custom_components tests tools` *(passed)*
- `ruff format --check custom_components tests tools || true` *(informational; failed with `108 files would be reformatted`)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `python tools/compare_registers_with_reference.py` *(passed; informational output: 62 extras and 242 name mismatches)*
- `python tools/check_maintainability.py` *(passed; `Maintainability gate passed.`)*
- `pytest tests/ -q` *(passed; 4 skipped)*
- `python tools/validate_entity_mappings.py` *(passed; `OK: 366 entities validated`)*
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print` *(informational; found only `coordinator/coordinator.py`, i.e. package implementation module)*
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true` *(passed; no matches)*
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true` *(informational; matches include policy/docs/tests text plus known legacy-compat references outside the forbidden invariants)*

## 1) Current CI gates

Current required CI workflow gates remain:

1. **Lint gate**: `ruff check`, `compileall`, register-reference compare, maintainability check.
2. **Test gate**: `pytest --cov --cov-report=xml --cov-report=term -q` (+ coverage upload).
3. **Entity mappings gate**: `python tools/validate_entity_mappings.py`.

Non-required tools status in this audit window:

- `black`: not configured as a required gate.
- `isort`: not configured as a required gate.
- `mypy`: not configured as a required gate.
- `hassfest`: not configured as a required gate.
- HACS validation: not configured as a required gate.

## 2) Fresh metrics snapshot

### Largest files (non-empty lines)

1. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (711)
2. `custom_components/thessla_green_modbus/scanner/io_read.py` (684)
3. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (514)
4. `custom_components/thessla_green_modbus/coordinator/schedule.py` (503)
5. `tests/test_coordinator.py` (502)
6. `custom_components/thessla_green_modbus/modbus_helpers.py` (498)
7. `custom_components/thessla_green_modbus/scanner/core.py` (470)
8. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (438)
9. `custom_components/thessla_green_modbus/config_flow.py` (432)
10. `tests/test_register_loader.py` (402)

### Largest classes (AST span)

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (625)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (528)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (441)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (334)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (249)
7. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (223)
8. `ConfigFlow` in `config_flow.py` (221)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenBinarySensor` in `binary_sensor.py` (175)

### Largest functions (AST span)

1. `register_maintenance_services` in `services_handlers_maintenance.py` (128)
2. `validate_input_impl` in `config_flow_device_validation.py` (111)
3. `_call_modbus` in `modbus_helpers.py` (106)
4. `read_input_registers_optimized` in `_coordinator_read_batches.py` (100)
5. `async_setup_entry` in `sensor.py` (98)
6. `read_bit_registers` in `scanner/io_read.py` (94)
7. `run_full_scan` in `scanner/orchestration.py` (91)
8. `scan` in `scanner/orchestration.py` (83)
9. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` (83)
10. `async_write_register` in `coordinator/schedule.py` (81)

## 3) Completed refactor batch status

The latest cleanup batch is reflected in current structure and checks (maintainability + full tests + entity mapping validation all pass). The previously tracked cleanup items (#1492-#1501 in project history) remain consistent with current codebase shape, and no rollback indicators were found in this audit run.

## 4) Remaining production hotspots

1. `coordinator/coordinator.py` and `_CoordinatorScheduleMixin` remain the largest coordinator hotspots.
2. Scanner path still concentrates complexity in `scanner/io_read.py` and `scanner/core.py`.
3. Mapping composition remains concentrated in `mappings/_mapping_builders.py`.
4. `config_flow.py` + `config_flow_device_validation.py` still carry large flow/validation paths.
5. Service registration remains top-heavy in `register_maintenance_services`.

## 5) Remaining test hotspots

Largest tests by file size still include `tests/test_coordinator.py`, `tests/test_register_loader.py`, and other large scanner/config-flow suites. Next cleanup should continue splitting broad integration-heavy files into narrower behavior-focused suites.

## 6) Next recommended PRs

1. Split coordinator update-cycle and lifecycle orchestration out of `coordinator/coordinator.py`.
2. Extract grouped-read planning/error normalization helpers from `scanner/io_read.py`.
3. Decompose `_mapping_builders.py` by domain/entity family.
4. Isolate config-flow runtime validation branches from `validate_input_impl`.
5. Split `register_maintenance_services` into schema wiring, handler factories, and registration loops.
6. Break large coordinator/scanner tests into focused sub-suites mirroring production-module boundaries.

## 7) CI hardening status

- `ruff check`: **pass**.
- `ruff import-order signal` (`ruff check --select I`): **pass**.
- `ruff format drift count`: **108 files would be reformatted**.
- `black`: **not a current required gate**.
- `isort`: **not a current required gate**.
- `mypy`: **not a current required gate**.
- `hassfest`: **not a current required gate**.
- `HACS`: **not a current required gate**.

## 8) Preserved invariants (audit status)

- No top-level `custom_components/thessla_green_modbus/coordinator.py` file.
- No Home Assistant imports under `core/`, `transport/`, `registers/`, `scanner/`.
- Entity mappings validation passes (`OK: 366 entities validated`).
- Architectural policy still requires no compatibility shims/proxy modules/re-export-only modules; however, informational grep still reports compatibility-related references and shim code paths that should be addressed in follow-up cleanup PRs.

## 9) Readiness summary

1. **Maintainability/refactor readiness**: good incremental progress; maintainability gate passes, but large hotspots remain.
2. **CI readiness**: required gates are passing.
3. **Release/HACS readiness**: not fully evidenced in this audit because hassfest/HACS checks are not active gates.
4. **Real device validation status**: not proven by this document; compare script signals vendor-name mismatches/extras as informational and requires device/vendor confirmation.
