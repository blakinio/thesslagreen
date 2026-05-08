# Maintainability audit

Date: 2026-05-08 (Python 3.13 full-pass + config_flow bound-adapter extraction + coordinator test split)

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

- `pydantic`: ✅ `OK pydantic: 2.13.4` (pip-installed; see Dependabot note)
- `pytest`: ✅ `OK pytest: 9.0.3`
- `pytest_asyncio`: ✅ `OK pytest_asyncio: 1.3.0`
- `pytest_homeassistant_custom_component`: ✅ pass
- `homeassistant`: ✅ pass

## Exact status by validation gate

### Required maintained gates (Python 3.13.12)

- **ruff check**: ✅ pass (`All checks passed!`).
- **ruff import order check**: ✅ pass (`All checks passed!`).
- **ruff format --check**: ✅ **0 files drift** (415 files already formatted).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass
  (informational: 62 extras; 242 name mismatches on common addresses — unchanged).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **entity mappings** (`validate_entity_mappings.py`): ✅ pass (`OK: 366 entities validated`).
- **pytest** (`pytest tests/ -q`): ✅ **1913 passed, 4 skipped**, 84 warnings in 14.74s.
- **coordinator split check**: ✅ pass (277 total — unchanged).

### Notable changes since previous audit (2026-05-08 config_flow + coordinator test cleanup)

- Full test suite runs on Python 3.13 — all gates green.
- **PHASE B — config_flow bound-adapter extraction**: Three adapter functions (`_validate_tcp_config`, `_validate_rtu_config`, `_process_scan_capabilities`) removed from `config_flow.py` and replaced with `validate_tcp_config_bound`, `validate_rtu_config_bound`, `process_scan_capabilities_bound` in `config_flow_validation.py`. 13 new focused tests added in `tests/test_config_flow_validation_bound.py`. `config_flow.py` non-empty lines: 414 → 394 (-20).
- **PHASE C — coordinator test split**: `TestParseBackoffJitter` class (5 tests) moved from `test_coordinator.py` to `tests/test_coordinator_parse_backoff.py`. Total coordinator tests unchanged (277). `test_coordinator.py` non-empty lines: 440 → 412 (-28).
- pytest count: **1913 passed** (up from 1900; +13 bound-adapter tests).
- Ruff format drift: **0 files** (415 files).

### Ruff format drift

`ruff format --check custom_components tests tools` reports **0 files would be reformatted**.

All 415 files are already formatted. ✅

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
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 417 | `custom_components/thessla_green_modbus/mappings/_static_discrete.py` |
| 412 | `tests/test_coordinator.py` |

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
4. Config-flow branching (`config_flow.py` 394 lines; reduced from 414 in previous audit).
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
- Pydantic version was **not changed**. `requirements-dev.txt` still pins `pydantic==2.12.2`; the pip-installed version in this environment is 2.13.4 due to an unrelated global install, but the project pin was not modified.
