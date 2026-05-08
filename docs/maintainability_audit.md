# Maintainability audit

Date: 2026-05-08 (Python 3.13 full-pass + coordinator io mixin + UART select extraction)

## Commands executed (exact)

- `git branch --show-current`
- `git status --short`
- `uv venv .venv --python 3.13 && uv pip install -r requirements-dev.txt` (Python 3.13 venv)
- Import gate script:
  - `python - <<'PY' ... __import__(...) ... PY`
- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools`
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python tools/compare_registers_with_reference.py`
- `python tools/check_maintainability.py`
- `python tools/validate_entity_mappings.py`
- `pytest tests/ -q`
- AST metrics script (largest files/classes/functions snapshot)
- Coordinator split check: `pytest -q tests/test_coordinator_error_paths_split.py tests/test_coordinator.py tests/test_coordinator_*.py`

## Import gate result

Environment: **Python 3.13.12** (`.venv` via uv). All five required modules import successfully.

- `pydantic`: ✅ `OK pydantic: 2.12.2`
- `pytest`: ✅ `OK pytest: 9.0.0`
- `pytest_asyncio`: ✅ `OK pytest_asyncio: 1.3.0`
- `pytest_homeassistant_custom_component`: ✅ pass
- `homeassistant`: ✅ pass

## Exact status by validation gate

### Required maintained gates (Python 3.13.12)

- **ruff check**: ✅ pass (`All checks passed!`).
- **ruff import order check**: ✅ pass (`All checks passed!`).
- **ruff format --check**: ✅ **0 files drift** (414 files already formatted).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass
  (informational: 62 extras; 242 name mismatches on common addresses — unchanged).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **entity mappings** (`validate_entity_mappings.py`): ✅ pass (`OK: 366 entities validated`).
- **pytest** (`pytest tests/ -q`): ✅ **1900 passed, 4 skipped**, 84 warnings in ~12s.
- **coordinator split check**: ✅ pass (277 passed, 1 warning in 2.10s).

### Notable changes since previous audit (2026-05-08 modbus_helpers._encode_read_frame run)

- PHASE B: Extracted `_read_coils_transport` and `_read_discrete_inputs_transport` from
  `coordinator/coordinator.py` into `_ModbusIOMixin` in `coordinator/io.py`. These methods
  were already declared as abstract stubs in the mixin — now they are concrete implementations.
  `ConnectionException` import removed from `coordinator.py`; added to `io.py`.
  `coordinator.py` reduced from **699 → 666** non-empty lines.
  `ThesslaGreenModbusCoordinator` reduced from **611 → 577** AST lines.
- PHASE C: Extracted 6 UART/serial-port select mappings (`uart_0_baud`, `uart_0_parity`,
  `uart_0_stop`, `uart_1_baud`, `uart_1_parity`, `uart_1_stop`) from `_static_discrete.py`
  into new `_static_discrete_uart.py`. Pattern follows existing `_static_discrete_diagnostics.py`.
  `_static_discrete.py` reduced from **417 → ~363** non-empty lines.
  `SELECT_ENTITY_MAPPINGS` composed via `{..., **UART_SELECT_ENTITY_MAPPINGS}`.
  Entity count unchanged: **366**.

### Ruff format drift

`ruff format --check custom_components tests tools` reports **0 files would be reformatted**.

All 414 files are already formatted. ✅

### Required CI gate status note

- All local maintained quality gates are green on Python 3.13.
- CI/HACS/hassfest gates were **not** executed in this run and are not claimed as proven.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py` only.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, `scanner/` do not import Home Assistant.
- `compat|shim|proxy|re-export|legacy` grep returns only informational matches
  in docs/tests/comments and known compatibility-reference strings.

## PHASE B summary

**Extraction: `_read_coils_transport` and `_read_discrete_inputs_transport` → `coordinator/io.py`**

Before:
- `coordinator/coordinator.py` non-empty: **699** lines
- `ThesslaGreenModbusCoordinator` AST span: **611** lines
- Methods were implemented in `coordinator.py`; `io.py` had abstract stubs

After:
- `coordinator/coordinator.py` non-empty: **666** lines (−33)
- `ThesslaGreenModbusCoordinator` AST span: **577** lines (−34)
- Implementations moved to `_ModbusIOMixin` in `coordinator/io.py`; stubs replaced with code
- `ConnectionException` import removed from `coordinator.py`; added to `io.py`

API invariant confirmed: `sorted(__all__) == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]` ✅

Path invariant confirmed: no `coordinator.py` at package root ✅

Targeted test result: **293 passed**, 1 warning ✅

## PHASE C summary

**Extraction: UART select mappings → `mappings/_static_discrete_uart.py`**

Before:
- `_static_discrete.py` non-empty: **417** lines
- 6 UART/serial-port entries inline in `SELECT_ENTITY_MAPPINGS`

After:
- `_static_discrete.py` non-empty: **~363** lines (−54)
- New `_static_discrete_uart.py` created with `UART_SELECT_ENTITY_MAPPINGS`
- `SELECT_ENTITY_MAPPINGS` composed via `{..., **UART_SELECT_ENTITY_MAPPINGS}`
- Pattern mirrors existing `_static_discrete_diagnostics.py` extraction

Entity count unchanged: **366** ✅

Targeted mapping test result: **284 passed**, 3 skipped ✅

## Largest files/classes/functions (current — 2026-05-08 Phase B+C refresh)

### Largest files (non-empty lines, top 10)

| Lines | Path |
|------:|------|
| 714 | `custom_components/thessla_green_modbus/scanner/io_read.py` |
| 666 | `custom_components/thessla_green_modbus/coordinator/coordinator.py` |
| 537 | `custom_components/thessla_green_modbus/modbus_helpers.py` |
| 468 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 454 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 440 | `tests/test_coordinator.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 414 | `custom_components/thessla_green_modbus/config_flow.py` |

### Largest classes (AST span, top 10)

| Lines | Class | File |
|------:|-------|------|
| 577 | `ThesslaGreenModbusCoordinator` | `coordinator/coordinator.py` |
| 488 | `_CoordinatorScheduleMixin` | `coordinator/schedule.py` |
| 428 | `ThesslaGreenDeviceScanner` | `scanner/core.py` |
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
| 98 | `async_setup_entry` | `sensor.py` |
| 92 | `run_full_scan` | `scanner/orchestration.py` |
| 91 | `__init__` | `scanner/core.py` |
| 89 | `validate` | `tools/validate_registers.py` |
| 86 | `_install_homeassistant_stubs` | `tools/validate_dashboard_entities.py` |
| 78 | `_call_modbus` | `modbus_helpers.py` |

## Remaining hotspots

1. Coordinator concentration (`coordinator/coordinator.py` 666 lines, `ThesslaGreenModbusCoordinator` 577 lines; `coordinator/schedule.py` 468 lines, `_CoordinatorScheduleMixin` 488 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 454 lines).
3. Mapping builder density (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 414 lines).
5. Ruff format drift: 0 files. ✅

## Branch note (authoritative target)

- The working target branch is **dev**.
- **main** is **not** authoritative for this refactor/audit track.
- No `main -> dev` merge is recommended as part of this audit.

## Release readiness caveats

- **HACS/hassfest readiness is not proven** in this audit. `hassfest` and `hacs` are
  not installable PyPI packages; they run exclusively as GitHub Actions in CI.
  Release readiness via those gates must be verified through the CI pipeline.
- **Real-device validation is not proven** in this audit unless explicitly documented
  with device evidence. No on-device test evidence was captured in this run.

## Dependabot note

- PR #1567 was **not touched** in this session.
- Pydantic version was **not changed** (installed: 2.12.2).
