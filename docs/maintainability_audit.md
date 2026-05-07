# Maintainability audit

Date: 2026-05-05

## Branch note

- Working target branch is **dev**.
- `main` is **not** authoritative for this audit refresh.
- No `main -> dev` merge is recommended as part of this work.

## Commands executed (exact)

- `git branch --show-current`
- `git status --short`
- `python -m pip install --upgrade pip setuptools wheel`
- `python -m pip install -r requirements-dev.txt`
- import gate script for `pydantic`, `pytest`, `pytest_asyncio`, `pytest_homeassistant_custom_component`, `homeassistant`
- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools || true`
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python tools/compare_registers_with_reference.py`
- `python tools/check_maintainability.py`
- `python tools/validate_entity_mappings.py`
- `pytest tests/ -q`
- AST metrics script (largest files/classes/functions)
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print`
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true`
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true`

## Exact status by gate

### Import gate result

- ✅ `OK pydantic`
- ✅ `OK pytest`
- ✅ `OK pytest_asyncio`
- ✅ `OK pytest_homeassistant_custom_component`
- ✅ `OK homeassistant`

### Required maintained gates

- ✅ `ruff check custom_components tests tools` (`All checks passed!`).
- ✅ `ruff check --select I custom_components tests tools` (`All checks passed!`).
- ✅ `python -m compileall -q custom_components/thessla_green_modbus tests tools`.
- ✅ `python tools/compare_registers_with_reference.py` (informational output only: 62 extras; 242 name mismatches on common addresses).
- ✅ `python tools/check_maintainability.py` (`Maintainability gate passed.`).
- ✅ `python tools/validate_entity_mappings.py` (`OK: 366 entities validated`).
- ✅ `pytest tests/ -q` (pass; 4 skipped tests).

### Pytest skips

- `tests/test_entity_data_correctness_number.py`: three skipped checks (min/max/step assertions already explicitly covered).
- `tests/test_register_pdf_mapping.py`: skipped because `pypdf` is unavailable in this environment.

## Ruff format drift

- `ruff format --check custom_components tests tools || true`: **1 file would be reformatted**.
- Drift file: `custom_components/thessla_green_modbus/mappings/_mapping_builders.py`.

## Architecture invariants snapshot

- `find ... coordinator.py`: only `custom_components/thessla_green_modbus/coordinator/coordinator.py` found.
- HA imports in `core/transport/registers/scanner`: **none detected** by grep.
- `compat|shim|proxy|re-export|legacy` grep: informational matches in docs/tests/comments and known compatibility-related references; no new compatibility-layer creation in this audit task.

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
9. `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` — 433
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

## Remaining hotspots

- Coordinator concentration: `coordinator/coordinator.py`, `coordinator/schedule.py`.
- Scanner complexity: `scanner/io_read.py`, `scanner/core.py`.
- Mapping assembly density: `mappings/_mapping_builders.py`.
- Config-flow branching density: `config_flow.py`, `config_flow_device_validation.py`.

## Release readiness caveat

- HACS/hassfest readiness is **not proven** in this audit because neither HACS validation nor hassfest was run.
- Real-device validation is **not proven** in this audit because no hardware verification artifacts were produced.
