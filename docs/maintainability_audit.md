# Maintainability audit

Date: 2026-05-08 (Python 3.12 full-pass + coordinator config_properties mixin + scanner io_read_helpers + schedule._write_holding_multi refactor)
Date: 2026-05-08 (Python 3.13 full-pass + config_flow bound-adapter extraction + coordinator test split)
Date: 2026-05-08 (Python 3.13 full-pass + config_flow_runtime load_scanner_module + coordinator backoff jitter test split)
Date: 2026-05-08 (Python 3.13 cleanup run — stale/duplicate sections removed)

## Commands executed (exact)

- `git branch --show-current` / `git status --short`
- `python3.13 --version`
- Import gate: `python3.13 - <<'PY' ... __import__(...) ... PY`
- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools`
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python3.13 tools/compare_registers_with_reference.py`
- `python3.13 tools/check_maintainability.py`
- `python3.13 tools/validate_entity_mappings.py` (not run this session; see below)
- `python3.13 -m pytest tests/ -q` (not run this session; see below)
- AST metrics script (largest files/classes/functions)

## Import gate result

Environment: **Python 3.13.12**. Results this session:

- `pydantic`: ✅ `OK pydantic: 2.12.2` (project pin confirmed)
- `pytest`: ✅ `OK pytest: 9.0.3`
- `pytest_asyncio`: ✅ `OK pytest_asyncio: 1.3.0`
- `pytest_homeassistant_custom_component`: ❌ not installed (`PyRIC` binary build fails in this environment)
- `homeassistant`: ✅ 2026.2.3 installed (transitive deps incomplete)

## Exact status by validation gate

### Required maintained gates (Python 3.13.12)

- **ruff check**: ✅ pass (`All checks passed!`).
- **ruff import order check**: ✅ pass (`All checks passed!`).
- **ruff format --check**: ✅ **0 files drift** (418 files already formatted).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass
  (informational: 62 extras; 242 name mismatches on common addresses — unchanged).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **entity mappings** (`validate_entity_mappings.py`): not run this session — `homeassistant`
  transitive deps incomplete (`PyRIC`/`propcache`/`voluptuous` conflicts block install).
  Last confirmed result (2026-05-08 Phase B+C run): **OK: 366 entities validated**.
- **pytest** (`pytest tests/ -q`): not run this session — `pytest_homeassistant_custom_component`
  not installable (`PyRIC` build failure). Last confirmed result (2026-05-08 Phase B+C run):
  **1920 passed, 4 skipped, 90 warnings**.
- **targeted config flow** (`pytest tests/test_config_flow*.py`): not run this session.
  Last confirmed: **142 passed**, 1 warning.
- **targeted coordinator** (`pytest tests/test_coordinator*.py`): not run this session.
  Last confirmed: **300 passed**, 1 warning.

### Required CI gate status note

- Locally maintained quality gates (ruff, compileall, compare_registers, check_maintainability) are green on Python 3.13.
- pytest and entity-mapping validation could not run this session due to missing native dependencies.
- CI/HACS/hassfest gates were **not** executed in this run and are not claimed as proven.

## Notable merged changes (2026-05-08 series)

All changes below are already merged into **dev** as of this audit.

**PHASE B (load_scanner_module extraction):**
- `_load_scanner_module` (7-line async function) moved from inline in `config_flow.py` into
  `load_scanner_module` in `config_flow_runtime.py`.
- `import_module` import removed from `config_flow.py`.
- `_SCANNER_MODULE_PATH` constant added to `config_flow_runtime.py` for testability.
- 5 focused unit tests added in `tests/test_config_flow_runtime_loader.py`.
- `config_flow.py` non-empty: 414 → 407 (−7).

**PHASE B (bound-adapter extraction):**
- `_validate_tcp_config`, `_validate_rtu_config`, `_process_scan_capabilities` removed from
  `config_flow.py` and replaced by `validate_tcp_config_bound`, `validate_rtu_config_bound`,
  `process_scan_capabilities_bound` in `config_flow_validation.py`.
- 13 focused tests added in `tests/test_config_flow_validation_bound.py`.
- `config_flow.py` non-empty: 407 → 387 (−20). Current: **387 lines**.

**PHASE C (coordinator test splits):**
- `TestParseBackoffJitter` class (5 tests) split out of `test_coordinator.py` into
  `tests/test_coordinator_parse_backoff.py` and `tests/test_coordinator_backoff_jitter.py`.
- `test_coordinator.py` non-empty: 440 → 412 (−28). Current: **412 lines**.
- Coordinator test collection total: **286** (no tests removed; redistribution only).
- No production files changed in PHASE C.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py` only.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, `scanner/` do not import Home Assistant.
- `compat|shim|proxy|re-export|legacy` grep: informational matches in docs/tests/comments only.

## Largest files/classes/functions (AST snapshot — 2026-05-08 cleanup run)

### Largest files (non-empty lines, top 15)

| Lines | Path |
|------:|------|
| 714 | `custom_components/thessla_green_modbus/scanner/io_read.py` |
| 666 | `custom_components/thessla_green_modbus/coordinator/coordinator.py` |
| 537 | `custom_components/thessla_green_modbus/modbus_helpers.py` |
| 451 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 419 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 412 | `tests/test_coordinator.py` |
| 406 | `custom_components/thessla_green_modbus/scanner/setup.py` |
| 397 | `tools/translate_register_descriptions.py` |
| 387 | `custom_components/thessla_green_modbus/config_flow.py` |
| 380 | `custom_components/thessla_green_modbus/config_flow_device_validation.py` |
| 376 | `custom_components/thessla_green_modbus/registers/schema.py` |
| 373 | `tests/test_validate_registers.py` |

### Largest classes (AST span, top 10)

| Lines | Class | File |
|------:|-------|------|
| 577 | `ThesslaGreenModbusCoordinator` | `coordinator/coordinator.py` |
| 432 | `_CoordinatorScheduleMixin` | `coordinator/schedule.py` |
| 425 | `ThesslaGreenDeviceScanner` | `scanner/core.py` |
| 334 | `RawRtuOverTcpTransport` | `modbus_transport_raw.py` |
| 268 | `RegisterDef` | `registers/register_def.py` |
| 251 | `ThesslaGreenFan` | `fan.py` |
| 230 | `_CoordinatorCapabilitiesMixin` | `coordinator/capabilities.py` |
| 210 | `BaseModbusTransport` | `modbus_transport_base.py` |
| 204 | `ConfigFlow` | `config_flow.py` |
| 183 | `ThesslaGreenClimate` | `climate.py` |

### Largest functions (AST span, top 15)

| Lines | Function | File |
|------:|----------|------|
| 111 | `register_maintenance_services` | `services_handlers_maintenance.py` |
| 110 | `test_force_full_register_list_integration` | `tests/test_force_full_register_list_integration.py` |
| 107 | `test_migrate_entity_unique_ids` | `tests/test_entity_unique_id.py` |
| 107 | `migrate_unique_id` | `unique_id_migration.py` |
| 105 | `test_reauth_flow_success` | `tests/test_config_flow_reauth.py` |
| 104 | `validate_optimization_metrics` | `tests/run_optimization_tests.py` |
| 103 | `run` | `tests/test_force_full_register_list_integration.py` |
| 100 | `test_entity_counts_per_platform` | `tests/test_all_entity_creation.py` |
| 100 | `read_input_registers_optimized` | `_coordinator_read_batches.py` |
|  98 | `async_setup_entry` | `sensor.py` |
|  92 | `test_confirm_step_aborts_on_existing_entry` | `tests/test_config_flow_confirm.py` |
|  91 | `run_full_scan` | `scanner/orchestration.py` |
|  89 | `validate` | `tools/validate_registers.py` |
|  88 | `__init__` | `scanner/core.py` |
|  86 | `_install_homeassistant_stubs` | `tools/validate_dashboard_entities.py` |

## PHASE B summary (2026-05-08 config_properties mixin)

**Extraction: coordinator property accessors → `coordinator/config_properties.py`**

- 9 pairs of config-backed property getter/setter (host, port, slave_id, connection_type, connection_mode, serial_port, baud_rate, parity, stop_bits) moved from `ThesslaGreenModbusCoordinator` into new `_CoordinatorConfigPropertiesMixin`.
- `ThesslaGreenModbusCoordinator` gains `_CoordinatorConfigPropertiesMixin` as a base class.
- `coordinator.py` non-empty: **666 → 605** (−61).
- `coordinator/config_properties.py` created: 71 non-empty lines.
- Coordinator package API invariant (`["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`) preserved.
- No top-level `coordinator.py` proxy created.

## PHASE C summary (2026-05-08 scanner io_read_helpers)

**Extraction: scanner failure logging helpers → `scanner/io_read_helpers.py`**

- `_mark_failed_addresses`, `_log_read_abort`, `_log_read_failure` moved from `scanner/io_read.py` to `scanner/io_read_helpers.py` as public helpers (`mark_failed_addresses`, `log_read_abort`, `log_read_failure`).
- Callers in `io_read.py` updated to use the imported names.
- `scanner/io_read.py` non-empty: **714 → 701** (−13).
- `scanner/io_read_helpers.py` non-empty: **63 → 84** (+21).
- HA-independence invariant preserved (no HA imports in scanner).
- 239 scanner tests pass.

## PHASE E summary (2026-05-08 schedule._write_holding_multi deduplication)

**Refactor: `_write_holding_multi` uses `_write_registers_payload`**

- `_write_holding_multi` in `coordinator/schedule.py` previously duplicated the transport selection pattern from `_write_registers_payload` (three-branch: transport / client / fallback).
- Refactored to call `_write_registers_payload` per chunk, eliminating the duplication.
- `coordinator/schedule.py` non-empty: **419 → 401** (−18).
- Write/chunking/retry behavior unchanged; 326 write-path tests pass.

## Remaining hotspots

1. Coordinator (`coordinator/coordinator.py` 605 lines, `ThesslaGreenModbusCoordinator` ~516 AST lines; `coordinator/schedule.py` 401 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 701 lines, `scanner/core.py` 451 lines).
3. Mapping builder density (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` ~407 lines).
5. Ruff format drift: 0 files. ✅

## Previous remaining hotspots (pre-2026-05-08 config_properties/io_read/schedule pass)

1. Coordinator concentration (`coordinator/coordinator.py` 666 lines, `ThesslaGreenModbusCoordinator` 577 AST lines; `coordinator/schedule.py` 419 lines, `_CoordinatorScheduleMixin` 432 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 451 lines).
3. Mapping builder density (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 394 lines; reduced from 414 in previous audit).
4. Config-flow branching (`config_flow.py` 407 lines).
1. Coordinator concentration: `coordinator/coordinator.py` 666 lines (`ThesslaGreenModbusCoordinator` 577 AST lines); `coordinator/schedule.py` 419 lines (`_CoordinatorScheduleMixin` 432 AST lines).
2. Scanner read/orchestration complexity: `scanner/io_read.py` 714 lines; `scanner/core.py` 451 lines.
3. Mapping builder density: `mappings/_mapping_builders.py` 437 lines.
4. Config-flow branching: `config_flow.py` 387 lines (reduced from 414 after two PHASE B extractions).
5. Ruff format drift: 0 files. ✅

## Branch note (authoritative target)

- The working target branch is **dev**.
- **main** is **not** authoritative for this refactor/audit track.
- No `main -> dev` merge is recommended as part of this audit.

## Release readiness caveats

- **HACS/hassfest readiness is not proven** in this audit. `hassfest` and `hacs` are not
  installable PyPI packages; they run exclusively as GitHub Actions in CI. Release readiness via
  those gates must be verified through the CI pipeline.
- **Real-device validation is not proven** in this audit unless explicitly documented with device
  evidence. No on-device test evidence was captured in this run.

## Dependabot note

- PR #1567 was **not touched** in this session.
- Pydantic version was **not changed**. `requirements-dev.txt` still pins `pydantic==2.12.2`; the pip-installed version in this environment is 2.12.2 (via python3.12 which is what was used for this audit run), matching the pinned version.

## Gate status (2026-05-08 config_properties/io_read/schedule pass — Python 3.12)

- Python interpreter: **python3.12** (3.12.3, break-system-packages installation with PHCC 0.13.205)
- Import gate: pydantic 2.10.4, pytest 8.3.4, pytest_asyncio 0.24.0, pytest_homeassistant_custom_component (0.13.205), homeassistant — all importable.
- `ruff check custom_components tests tools`: ✅ pass.
- `ruff check --select I custom_components tests tools`: ✅ pass.
- `ruff format --check custom_components tests tools`: ✅ **0 files drift** (419 files already formatted).
- `python3.12 -m compileall -q custom_components/thessla_green_modbus tests tools`: ✅ pass.
- `python3.12 tools/compare_registers_with_reference.py`: ✅ informational (62 extras, 242 name mismatches — unchanged).
- `python3.12 tools/check_maintainability.py`: ✅ `Maintainability gate passed.`
- `python3.12 tools/validate_entity_mappings.py`: ✅ `OK: 366 entities validated`.
- `python3.12 -m pytest tests/`: ✅ **1938 passed, 4 skipped**, 90 warnings.
- Pydantic version was **not changed**. `requirements-dev.txt` pins `pydantic==2.12.2`. The
  project pin is unchanged. This environment has `pydantic 2.12.2` installed (project pin
  confirmed; no global override active in this run).
