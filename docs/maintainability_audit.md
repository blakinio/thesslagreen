# Maintainability audit

Date: 2026-05-04

## Commands executed (exact)

- `python -m pip install -q -r requirements-dev.txt`
- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools`
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python tools/compare_registers_with_reference.py`
- `python tools/check_maintainability.py`
- `pytest tests/ -q`
- `python tools/validate_entity_mappings.py`
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print`
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true`
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true`
- AST metrics script (largest files/classes/functions snapshot)

## Exact status by gate

### Required maintained gates

- **ruff check**: ✅ pass (`All checks passed!`).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass (informational output remains: 62 extras; 242 name mismatches on common addresses).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **pytest** (`pytest tests/ -q`): ❌ fail (`ModuleNotFoundError: pytest_homeassistant_custom_component`).
- **entity mappings** (`validate_entity_mappings.py`): ❌ fail (`ModuleNotFoundError: pydantic`).

### Non-required tools

- **black**: not executed in this run; not a required gate.
- **isort**: not executed in this run; not a required gate.
- **mypy**: not executed in this run; not a required gate.
- **hassfest**: not executed in this run; not a required gate.
- **HACS**: not executed in this run; readiness not claimable from this audit.

## Ruff format drift

- `ruff format --check custom_components tests tools`: reports **7 files would be reformatted**.

## Architecture invariants snapshot

- `find ... coordinator.py`: only `custom_components/thessla_green_modbus/coordinator/coordinator.py` found.
- No `homeassistant` imports detected under `core/`, `transport/`, `registers/`, `scanner/`.
- `compat|shim|proxy|re-export|legacy` grep returns informational matches (docs/tests/comments + known compatibility references); no new invariant claim beyond grep evidence.

## Largest files/classes/functions (current)

### Largest files (non-empty lines)

1. `custom_components/thessla_green_modbus/scanner/io_read.py` — 713
2. `custom_components/thessla_green_modbus/coordinator/coordinator.py` — 697
3. `tests/test_coordinator.py` — 502
4. `custom_components/thessla_green_modbus/modbus_helpers.py` — 498
5. `custom_components/thessla_green_modbus/coordinator/schedule.py` — 472
6. `custom_components/thessla_green_modbus/scanner/core.py` — 470
7. `custom_components/thessla_green_modbus/mappings/_static_discrete.py` — 444
8. `custom_components/thessla_green_modbus/config_flow.py` — 437
9. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` — 414
10. `tools/translate_register_descriptions.py` — 397

### Largest classes (AST span)

1. `ThesslaGreenModbusCoordinator` (`coordinator/coordinator.py`) — 612
2. `_CoordinatorScheduleMixin` (`coordinator/schedule.py`) — 492
3. `ThesslaGreenDeviceScanner` (`scanner/core.py`) — 441
4. `RawRtuOverTcpTransport` (`modbus_transport_raw.py`) — 334
5. `RegisterDef` (`registers/register_def.py`) — 268
6. `ThesslaGreenFan` (`fan.py`) — 251
7. `_CoordinatorCapabilitiesMixin` (`coordinator/capabilities.py`) — 230
8. `ConfigFlow` (`config_flow.py`) — 227
9. `BaseModbusTransport` (`modbus_transport_base.py`) — 210
10. `ThesslaGreenClimate` (`climate.py`) — 183

### Largest functions (AST span)

1. `register_maintenance_services` (`services_handlers_maintenance.py`) — 111
2. `test_force_full_register_list_integration` (`tests/test_force_full_register_list_integration.py`) — 110
3. `test_migrate_entity_unique_ids` (`tests/test_entity_unique_id.py`) — 107
4. `migrate_unique_id` (`unique_id_migration.py`) — 107
5. `_call_modbus` (`modbus_helpers.py`) — 106
6. `test_reauth_flow_success` (`tests/test_config_flow_reauth.py`) — 105
7. `validate_optimization_metrics` (`tests/run_optimization_tests.py`) — 104
8. `run` (`tests/test_force_full_register_list_integration.py`) — 103
9. `test_entity_counts_per_platform` (`tests/test_all_entity_creation.py`) — 100
10. `read_input_registers_optimized` (`_coordinator_read_batches.py`) — 100

## Current remaining hotspots

- Coordinator concentration: `coordinator/coordinator.py`, `coordinator/schedule.py`.
- Scanner complexity: `scanner/io_read.py`, `scanner/core.py`.
- Mapping assembly density: `mappings/_mapping_builders.py`.
- Config-flow branching density: `config_flow.py`, `config_flow_device_validation.py`.

## Readiness caveats

- **Required gates are not fully green** in this environment because `pytest` and `validate_entity_mappings.py` fail due to missing Python packages.
- **Release/HACS readiness** cannot be claimed because HACS validation was not executed.
- **Real-device validation** cannot be claimed from this run; no new device-evidence artifacts were produced.

## Next recommended PRs

1. **Gate-recovery PR:** ensure dev requirements include/import `pytest_homeassistant_custom_component` and `pydantic` in the verification environment, then rerun full maintained gates.
2. Optional formatting-only PR: apply `ruff format` drift cleanup (7 files) only after required gates are green.
3. Continue decomposition PRs for coordinator/scanner/mapping/config-flow hotspots once gates are green.
