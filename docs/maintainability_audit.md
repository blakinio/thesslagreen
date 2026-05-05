# Maintainability Audit

Date: 2026-05-05 (UTC)

## Scope and constraints
- Verification-only run (no production/test/CI changes).
- Repository branch observed: `work`.
- Git remote output: empty.

## Exact commands run
1. `python -m pip install -q -r requirements-dev.txt`
2. `ruff check custom_components tests tools`
3. `ruff check --select I custom_components tests tools`
4. `ruff format --check custom_components tests tools`
5. `python -m compileall -q custom_components/thessla_green_modbus tests tools`
6. `python tools/compare_registers_with_reference.py`
7. `python tools/check_maintainability.py`
8. `pytest tests/ -q`
9. `python tools/validate_entity_mappings.py`
10. `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print`
11. `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/core custom_components/thessla_green_modbus/transport custom_components/thessla_green_modbus/registers custom_components/thessla_green_modbus/scanner || true`
12. `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs || true`
13. Metrics AST/size script (largest files/classes/functions).

## Required CI gate status

### ruff / compileall / register compare / maintainability
- **ruff check**: **FAIL** (21 violations; includes E402/F401/RUF022/I001).
- **ruff check --select I**: **FAIL** (1 import-order violation).
- **ruff format --check**: **FAIL**.
  - Ruff format drift count: **13 files would be reformatted**.
- **compileall**: **PASS**.
- **compare registers**: **PASS (script exit 0 with caveats)**.
  - Reference entries 294, integration entries 356, common 294.
  - Missing from integration: 0.
  - Extra in integration: 62.
  - Name mismatches on common addresses: 242.
- **maintainability check**: **PASS** (`Maintainability gate passed.`).

### pytest
- **FAIL**.
- Summary from run:
  - 58 failed
  - 1673 passed
  - 4 skipped
- Recurrent failure pattern includes `NameError: name 'DeviceCapabilities' is not defined` in scanner capability flow.

### entity mappings
- **PASS** (`OK: 366 entities validated`).

## Non-required tool status
- **black**: Not executed in this verification run.
- **isort**: Not executed in this verification run.
- **mypy**: Not executed in this verification run.
- **hassfest**: Not executed in this verification run.
- **HACS validation**: Not executed in this verification run.

## Largest code hotspots (current snapshot)

### Largest files (top 10 by non-empty lines)
1. `tests/test_scanner_coverage.py` — 2075
2. `tests/test_config_flow.py` — 1907
3. `tests/test_device_scanner.py` — 1589
4. `tests/test_coordinator_coverage.py` — 1519
5. `tests/test_services_handlers.py` — 1114
6. `tests/test_coordinator.py` — 931
7. `tests/test_modbus_transport.py` — 857
8. `custom_components/thessla_green_modbus/coordinator.py` — 738
9. `tests/test_optimized_integration.py` — 693
10. `tests/test_entity_mappings.py` — 683

### Largest classes (top 10)
1. `ThesslaGreenModbusCoordinator` (`coordinator.py`) — 674
2. `_CoordinatorScheduleMixin` (`_coordinator_schedule.py`) — 450
3. `ThesslaGreenDeviceScanner` (`scanner/core.py`) — 444
4. `ThesslaGreenClimate` (`climate.py`) — 333
5. `RegisterDefinition` (`registers/schema.py`) — 313
6. `RegisterDef` (`registers/register_def.py`) — 298
7. `RawRtuOverTcpTransport` (`modbus_transport_raw.py`) — 280
8. `ThesslaGreenFan` (`fan.py`) — 258
9. `_CoordinatorCapabilitiesMixin` (`_coordinator_capabilities.py`) — 237
10. `ConfigFlow` (`config_flow.py`) — 219

### Largest functions (top 10)
1. `_extend_entity_mappings_from_registers` — 245
2. `register_maintenance_services` — 192
3. `main` (`tools/validate_entity_mappings.py`) — 176
4. `read_holding` — 154
5. `validate_input_impl` — 151
6. `_post_process_data` — 149
7. `read_input` — 145
8. `async_write_registers` — 145
9. `register_parameter_services` — 139
10. `async_write_register` — 137

## Current remaining hotspots
- Scanner capability path instability (`DeviceCapabilities` NameError) causing broad scanner-related test failures.
- Lint debt remains active (unused imports, unsorted `__all__`, import ordering).
- Formatting drift detected in 13 files.
- Register naming divergence remains high (242 mismatches), although compare script exits successfully.

## Preserved architecture invariants
- `coordinator.py` exists in both expected locations:
  - `custom_components/thessla_green_modbus/coordinator/coordinator.py`
  - `custom_components/thessla_green_modbus/coordinator.py`
- No Home Assistant imports were detected in:
  - `core/`, `transport/`, `registers/`, `scanner/` paths checked by invariant command.
- Legacy/shim/proxy terms are still present in docs/tests and selected compatibility paths, but no CI or production restructuring was performed during this verification task.

## Release/HACS readiness caveat
- **Not release-ready under required gates** for this snapshot (ruff, format, pytest failing).
- **HACS readiness cannot be claimed** because HACS validation was not executed in this run.

## Real-device validation caveat
- No real-device validation evidence was executed or collected during this verification run.
- Hardware behavior/readback should be treated as unverified.

## Recommended next PRs
1. **Gate recovery PR (required first):** fix scanner capability regression (`DeviceCapabilities` NameError) and restore pytest pass on affected scanner suites.
2. **Lint/format gate recovery PR:** resolve ruff violations and apply formatting to remove the 13-file drift.
3. **Register naming alignment PR (optional but meaningful):** investigate and reconcile 242 register name mismatches if these are not intentional aliases.
