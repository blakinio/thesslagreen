# Maintainability audit

Date: 2026-05-04

## Inputs and checks

Executed:

- `python -m pip install -q -r requirements-dev.txt` *(passed; pip warning about root user and pip upgrade notice)*
- `ruff check custom_components tests tools` *(failed; `F811` duplicate `register_maintenance_services` + `F821` undefined `_build_reset_filters_handler` in `services_handlers_maintenance.py`)*
- `ruff check --select I custom_components tests tools` *(not executed because the required `ruff check` gate already failed in this run)*
- `ruff format --check custom_components tests tools || true` *(not executed in this run due to earlier lint failure; latest documented drift from previous audit remains `108 files would be reformatted`)*
- `python -m compileall -q custom_components/thessla_green_modbus tests tools` *(passed)*
- `python tools/compare_registers_with_reference.py` *(passed; informational output: 62 extras and 242 name mismatches)*
- `python tools/check_maintainability.py` *(passed; `Maintainability gate passed.`)*
- `pytest tests/ -q` *(failed; 69 failures, 1801 passed, 4 skipped; dominant failure: `NameError: _build_reset_filters_handler`)*
- `python tools/validate_entity_mappings.py` *(passed; `OK: 366 entities validated`)*
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print` *(informational; found only `coordinator/coordinator.py`, i.e. package implementation module)*
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true` *(passed; no matches)*
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true` *(informational; matches include policy/docs/tests text plus known compatibility references and shim usage in production code paths)*

## 1) Current CI gates

Current required CI workflow gates remain:

1. **Lint gate**: `ruff check`, `compileall`, register-reference compare, maintainability check.
2. **Test gate**: `pytest --cov --cov-report=xml --cov-report=term -q` (+ coverage upload).
3. **Entity mappings gate**: `python tools/validate_entity_mappings.py`.

Current status from this audit run:

- Required lint gate: **failing** (ruff check failure).
- Required test gate: **failing** (pytest failures).
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

1. `custom_components/thessla_green_modbus/coordinator/coordinator.py` (697)
2. `custom_components/thessla_green_modbus/scanner/io_read.py` (691)
3. `tests/test_coordinator.py` (502)
4. `custom_components/thessla_green_modbus/modbus_helpers.py` (498)
5. `custom_components/thessla_green_modbus/coordinator/schedule.py` (474)
6. `custom_components/thessla_green_modbus/scanner/core.py` (470)
7. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` (438)
8. `custom_components/thessla_green_modbus/config_flow.py` (435)
9. `tests/test_register_loader.py` (402)
10. `tools/translate_register_descriptions.py` (397)

### Largest classes (AST span)

1. `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` (612)
2. `_CoordinatorScheduleMixin` in `coordinator/schedule.py` (496)
3. `ThesslaGreenDeviceScanner` in `scanner/core.py` (441)
4. `RawRtuOverTcpTransport` in `modbus_transport_raw.py` (334)
5. `RegisterDef` in `registers/register_def.py` (268)
6. `ThesslaGreenFan` in `fan.py` (249)
7. `ConfigFlow` in `config_flow.py` (225)
8. `_CoordinatorCapabilitiesMixin` in `coordinator/capabilities.py` (223)
9. `BaseModbusTransport` in `modbus_transport_base.py` (210)
10. `ThesslaGreenBinarySensor` in `binary_sensor.py` (175)

### Largest functions (AST span)

1. `test_force_full_register_list_integration` in `tests/test_force_full_register_list_integration.py` (110)
2. `test_migrate_entity_unique_ids` in `tests/test_entity_unique_id.py` (107)
3. `migrate_unique_id` in `custom_components/thessla_green_modbus/unique_id_migration.py` (107)
4. `_call_modbus` in `custom_components/thessla_green_modbus/modbus_helpers.py` (106)
5. `test_reauth_flow_success` in `tests/test_config_flow_reauth.py` (105)
6. `validate_optimization_metrics` in `tests/run_optimization_tests.py` (104)
7. `run` in `tests/test_force_full_register_list_integration.py` (103)
8. `test_entity_counts_per_platform` in `tests/test_all_entity_creation.py` (100)
9. `read_input_registers_optimized` in `custom_components/thessla_green_modbus/_coordinator_read_batches.py` (100)
10. `register_maintenance_services` in `custom_components/thessla_green_modbus/services_handlers_maintenance.py` (98)

## 3) Completed refactor/cleanup batch status

No additional cleanup batch was completed in this audit run. Repository state currently shows regressions in service-handler wiring (`register_maintenance_services`) that block required lint/test gates, so this is not a “post-cleanup-green” snapshot.

## 4) Remaining production hotspots

1. `coordinator/coordinator.py` and `_CoordinatorScheduleMixin` remain the largest coordinator hotspots.
2. Scanner path still concentrates complexity in `scanner/io_read.py` and `scanner/core.py`.
3. Service handling currently has a correctness regression in `services_handlers_maintenance.py` (duplicate function definition + missing handler symbol).
4. Mapping composition remains concentrated in `mappings/_mapping_builders.py` and static mapping modules.
5. `config_flow.py` + `config_flow_device_validation.py` still carry large flow/validation paths.

## 5) Remaining test hotspots

1. `tests/test_coordinator.py` and `tests/test_register_loader.py` remain large files.
2. Service-handler suites currently expose the dominant breakage surface (69 failures in this run) and should be stabilized before any further structural test splitting.

## 6) Next recommended PRs

1. **Fix-forward PR (highest priority):** restore single authoritative `register_maintenance_services` implementation and missing handler symbol wiring so ruff + pytest return green.
2. After gate recovery, continue decomposition PRs for coordinator/scanner/mapping-builder/config-flow hotspots.
3. Keep optional formatting-only PR (`ruff format`) isolated from functional cleanup.

## 7) CI hardening status

- `ruff check`: **fail**.
- `ruff import-order signal` (`ruff check --select I`): **not executed in this run**.
- `ruff format drift count`: **not refreshed in this run** (last known: 108 files would be reformatted).
- `black`: **not a current required gate**.
- `isort`: **not a current required gate**.
- `mypy`: **not a current required gate**.
- `hassfest`: **not a current required gate**.
- `HACS`: **not a current required gate / not validated here**.

## 8) Preserved invariants (audit status)

- No top-level `custom_components/thessla_green_modbus/coordinator.py` file.
- No Home Assistant imports under `core/`, `transport/`, `registers/`, `scanner/`.
- Entity mappings validation passes (`OK: 366 entities validated`).
- No new compatibility/proxy/re-export-only module was introduced in this audit task; informational grep still reports compatibility terms and existing shim references that should be handled in dedicated cleanup.

## 9) Readiness summary

1. **Maintainability/refactor readiness**: maintainability script passes, but required lint/test gates are currently red due to service-handler regression.
2. **CI readiness**: not ready (required gates not all green).
3. **Release/HACS readiness**: not demonstrated by this run; HACS validation was not executed.
4. **Real device validation status**: not demonstrated in this run; register-compare extras/name mismatches remain informational and require vendor/device confirmation.
