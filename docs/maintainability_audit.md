# Maintainability audit

Date: 2026-05-08 (Python 3.13 full-pass + modbus_helpers._encode_read_frame refactor)

## Commands executed (exact)

- `git branch --show-current`
- `git status --short`
- `uv pip install -r requirements-dev.txt` (Python 3.13 venv)
- Import gate script:
  - `python - <<'PY' ... __import__(...) ... PY`
- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools || true`
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python tools/compare_registers_with_reference.py`
- `python tools/check_maintainability.py`
- `python tools/validate_entity_mappings.py`
- `pytest tests/ -q`
- AST metrics script (largest files/classes/functions snapshot)
- `find custom_components/thessla_green_modbus -maxdepth 2 -name "coordinator.py" -print`
- `rg "from homeassistant|import homeassistant" core/ transport/ registers/ scanner/`
- `rg "compat|shim|proxy|re-export|legacy" custom_components tests docs`

## Import gate result

Environment: **Python 3.13.12** (`.venv-py313`). All five required modules import successfully.

- `pydantic`: ✅ `OK pydantic: 2.12.2`
- `pytest`: ✅ `OK pytest: 9.0.0`
- `pytest_asyncio`: ✅ `OK pytest_asyncio: 1.3.0`
- `pytest_homeassistant_custom_component`: ✅ pass
- `homeassistant`: ✅ pass

## Exact status by validation gate

### Required maintained gates (Python 3.13.12)

- **ruff check**: ✅ pass (`All checks passed!`).
- **ruff import order check**: ✅ pass (`All checks passed!`).
- **ruff format --check**: ✅ **0 files drift** (413 files already formatted — improved from 2 files in prior audit).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass
  (informational: 62 extras; 242 name mismatches on common addresses — unchanged).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **entity mappings** (`validate_entity_mappings.py`): ✅ pass (`OK: 366 entities validated`).
- **pytest** (`pytest tests/ -q`): ✅ **1900 passed, 4 skipped**, 84 warnings in 12.13s.
- **coordinator split check**: ✅ pass (277 passed, 1 warning in 2.01s).

### Notable changes since previous audit (2026-05-08 scanner/io_read refactor run)

- Full test suite runs on Python 3.13 — all gates green.
- `modbus_helpers.py` — `_encode_read_frame` extracted from `_build_request_frame`; function reduced from 56 → 42 AST lines; `_READ_FC` dict added.
- Ruff format drift: **0 files** (down from 2 in previous audit; prior drift in `test_config_flow_helpers.py` and `test_modbus_helpers_call_flow.py` was resolved upstream).
- pytest count: **1900 passed** (up from 1892; 3 new tests for `_encode_read_frame`, `read_input_registers`, `read_holding_registers` paths).

### Ruff format drift

`ruff format --check custom_components tests tools` reports **0 files would be reformatted**.

All 413 files are already formatted. ✅

### Required CI gate status note

- All local maintained quality gates are green on Python 3.13.
- CI/HACS/hassfest gates were **not** executed in this run and are not claimed as proven.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py` only.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, `scanner/` do not import Home Assistant.
- `compat|shim|proxy|re-export|legacy` grep returns only informational matches
  in docs/tests/comments and known compatibility-reference strings.

## Largest files/classes/functions (current — 2026-05-08 refresh)

### Largest files (non-empty lines, top 10)

| Lines | Path |
|------:|------|
| 714 | `custom_components/thessla_green_modbus/scanner/io_read.py` |
| 699 | `custom_components/thessla_green_modbus/coordinator/coordinator.py` |
| 537 | `custom_components/thessla_green_modbus/modbus_helpers.py` |
| 468 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 454 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 440 | `tests/test_coordinator.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 417 | `custom_components/thessla_green_modbus/mappings/_static_discrete.py` |

### Largest classes (AST span, top 10)

| Lines | Class | File |
|------:|-------|------|
| 611 | `ThesslaGreenModbusCoordinator` | `coordinator/coordinator.py` |
| 488 | `_CoordinatorScheduleMixin` | `coordinator/schedule.py` |
| 428 | `ThesslaGreenDeviceScanner` | `scanner/core.py` |
| 334 | `RawRtuOverTcpTransport` | `modbus_transport_raw.py` |
| 268 | `RegisterDef` | `registers/register_def.py` |
| 251 | `ThesslaGreenFan` | `fan.py` |
| 230 | `_CoordinatorCapabilitiesMixin` | `coordinator/capabilities.py` |
| 210 | `BaseModbusTransport` | `modbus_transport_base.py` |
| 204 | `ConfigFlow` | `config_flow.py` |
| 183 | `ThesslaGreenClimate` | `climate.py` |

### Largest functions (AST span, top 10)

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
| 78 | `_call_modbus` | `modbus_helpers.py` |
| 42 | `_build_request_frame` | `modbus_helpers.py` (was 56) |

## Remaining hotspots

1. Coordinator concentration (`coordinator/coordinator.py` 699 lines, `ThesslaGreenModbusCoordinator` 611 lines; `coordinator/schedule.py` 468 lines, `_CoordinatorScheduleMixin` 488 lines).
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
