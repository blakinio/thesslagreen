# Maintainability audit

Date: 2026-05-04

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user and pip upgrade notice)*
- `ruff check custom_components tests tools` *(failed; `F811` duplicate `register_maintenance_services` + `F821` undefined `_build_reset_filters_handler` in `services_handlers_maintenance.py`)*
- `ruff check --select I custom_components tests tools` *(passed)*
- `ruff format --check custom_components tests tools` *(failed informationally; **5 files would be reformatted**)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `python tools/compare_registers_with_reference.py` *(passed; informational output: 62 extras and 242 name mismatches)*
- `python tools/check_maintainability.py` *(passed; `Maintainability gate passed.`)*
- `pytest tests/ -q` *(failed; 69 failed, 1801 passed, 4 skipped, 3 errors; dominant issue: `NameError: _build_reset_filters_handler`)*
- `python tools/validate_entity_mappings.py` *(passed; `OK: 366 entities validated`)*
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print` *(informational; found only `coordinator/coordinator.py`, i.e. package implementation module)*
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true` *(passed; no matches)*
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true` *(informational; matches include docs/policy/test text and existing known compatibility references in code)*

## 1) Current CI gates

Current required CI workflow gates remain:

1. **Lint gate**: `ruff check`, `compileall`, register-reference compare, maintainability check.
2. **Test gate**: `pytest --cov --cov-report=xml --cov-report=term -q` (+ coverage upload).
3. **Entity mappings gate**: `python tools/validate_entity_mappings.py`.

Current status from this audit run:

- Required lint gate: **failing** (`ruff check` red).
- Required test gate: **failing** (`pytest` red).
- Required entity-mappings gate: **passing**.
- Maintainability script: **passing**.

Non-required tools status in this audit window:

- `black`: not configured as a required gate.
- `isort`: not configured as a required gate.
- `mypy`: not configured as a required gate.
- `hassfest`: not configured as a required gate.
- HACS validation: not configured as a required gate and not executed in this run.

## 2) Fresh metrics snapshot

### Largest files (non-empty lines)

1. `custom_components/thessla_green_modbus/scanner/io_read.py` (713)
2. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (697)
3. `tests/test_coordinator.py` (502)
4. `custom_components/thessla_green_modbus/modbus_helpers.py` (498)
5. `custom_components/thessla_green_modbus/coordinator/schedule.py` (472)
6. `custom_components/thessla_green_modbus/scanner/core.py` (470)
7. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (444)
8. `custom_components/thessla_green_modbus/config_flow.py` (437)
9. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` (414)
10. `tools/translate_register_descriptions.py` (397)

### Largest classes (AST span)

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (612)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (492)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (441)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (334)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (251)
7. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (230)
8. `ConfigFlow` in `config_flow.py` (227)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenClimate` in `climate.py` (183)

### Largest functions (AST span)

1. `register_maintenance_services` in `custom_components/thessla_green_modbus/services_handlers_maintenance.py` (111)
2. `test_force_full_register_list_integration` in `tests/test_force_full_register_list_integration.py` (110)
3. `test_migrate_entity_unique_ids` in `tests/test_entity_unique_id.py` (107)
4. `migrate_unique_id` in `custom_components/thessla_green_modbus/unique_id_migration.py` (107)
5. `_call_modbus` in `custom_components/thessla_green_modbus/modbus_helpers.py` (106)
6. `test_reauth_flow_success` in `tests/test_config_flow_reauth.py` (105)
7. `validate_optimization_metrics` in `tests/run_optimization_tests.py` (104)
8. `run` in `tests/test_force_full_register_list_integration.py` (103)
9. `test_entity_counts_per_platform` in `tests/test_all_entity_creation.py` (100)
10. `read_input_registers_optimized` in `custom_components/thessla_green_modbus/_coordinator_read_batches.py` (100)

## 3) Completed cleanup PRs from latest batch

Based on `CHANGELOG.md`, the latest explicitly documented cleanup batch entries are:

- **2.7.0 — Dead fallback & pragma cleanup**
- **2.6.0 — Dead fallback cleanup**
- **2.5.1 — Config flow cleanup**

This audit run does **not** add a new cleanup completion; it documents current post-batch state only.

## 4) Remaining production hotspots

1. `services_handlers_maintenance.py` is currently the primary correctness hotspot (duplicate function definition + missing symbol).
2. `coordinator/coordinator.py` and `coordinator/schedule.py` remain the largest coordinator hotspots.
3. Scanner complexity remains concentrated in `scanner/io_read.py` and `scanner/core.py`.
4. Mapping assembly remains dense in `mappings/_mapping_builders.py`.
5. Flow validation remains dense in `config_flow.py` and `config_flow_device_validation.py`.

## 5) Remaining test hotspots

1. `tests/test_coordinator.py` remains a large integration-heavy test module.
2. Service-handler test suites are the dominant current failure surface due to maintenance-handler regression.
3. Register-loader error tests currently show 3 fixture errors (`registers` / `register` / `reg`).

## 6) Next recommended PRs

1. **Gate recovery PR (required first):** fix `services_handlers_maintenance.py` duplication/missing handler symbol, then re-run lint + tests.
2. **Follow-up gate recovery PR:** resolve register-loader fixture wiring errors if still present after maintenance-handler fix.
3. After green gates, continue targeted decomposition of coordinator/scanner/mappings/config-flow hotspots.
4. Keep optional formatting-only PR (`ruff format`) isolated.

## 7) CI hardening status

- `ruff check`: **fail**.
- `ruff import-order` (`ruff check --select I`): **pass**.
- `ruff format drift count`: **5 files** would be reformatted.
- `black`: **not a required gate**.
- `isort`: **not a required gate**.
- `mypy`: **not a required gate**.
- `hassfest`: **not a required gate**.
- `HACS`: **not a required gate / not validated in this run**.

## 8) Preserved invariants (audit status)

- No top-level `custom_components/thessla_green_modbus/coordinator.py` file.
- No Home Assistant imports under `core/`, `transport/`, `registers/`, `scanner/`.
- Entity mappings validation passes (`OK: 366 entities validated`).
- No new compatibility/proxy/re-export-only module was introduced in this task (informational grep still returns existing references).

## 9) Readiness summary

1. **Maintainability/refactor readiness**: maintainability script passes, but required lint/test gates are red.
2. **CI readiness**: not ready (not all required gates are green).
3. **Release/HACS readiness**: not demonstrated in this run; HACS validation not executed.
4. **Real device validation status**: not demonstrated in this run; register compare extras/name mismatches are informational and still require vendor/device confirmation.
