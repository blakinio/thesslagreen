# Maintainability audit

Date: 2026-05-08 (Python 3.13 full-pass + scanner/io_read refactor)

## Commands executed (exact)

- `git branch --show-current`
- `git status --short`
- `python -m pip install --upgrade pip setuptools wheel`
- `python -m pip install -r requirements-dev.txt`
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
- Release tool availability: `pip show homeassistant hassfest hacs`, `hassfest --help`, `hacs --help`

## Import gate result

Environment: **Python 3.13.12**. All five required modules import successfully.

- `pydantic`: ✅ `OK pydantic: 2.12.2`
- `pytest`: ✅ `OK pytest: 9.0.0`
- `pytest_asyncio`: ✅ `OK pytest_asyncio: 1.3.0`
- `pytest_homeassistant_custom_component`: ✅ pass
- `homeassistant`: ✅ pass

## Exact status by validation gate

### Required maintained gates (Python 3.13.12)

- **ruff check**: ✅ pass (`All checks passed!`).
- **ruff import order check**: ✅ pass (`All checks passed!`).
- **ruff format --check**: ⚠️ **2 files would be reformatted** (see drift section below; down from 3).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass
  (informational: 62 extras; 242 name mismatches on common addresses — unchanged).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **entity mappings** (`validate_entity_mappings.py`): ✅ pass (`OK: 366 entities validated`).
- **pytest** (`pytest tests/ -q`): ✅ **1892 passed, 4 skipped**, 84 warnings in 14.30s.
- **coordinator split check**: ✅ pass (277 passed, 1 warning in 2.59s).

### Notable changes since previous audit (2026-05-08 3.11 run)

- Full test suite now runs on Python 3.13 — all gates green.
- `scanner/io_read_helpers.py` — ruff format drift **resolved** (lambda inline).
- `scanner/io_read.py` — `_run_holding_read_retry_loop` extracted; `read_holding` reduced from 92 → 29 lines; now mirrors `read_input` pattern.
- `scanner/io_read.py` non-empty lines: 694 → 708 (net +14 from added function scaffolding/docstring).

### Ruff format drift improvement

Format drift reduced from **3 files** (previous audit) to **2 files** (this run):

| Status | File |
|--------|------|
| ✅ resolved | `scanner/io_read_helpers.py` |
| ⚠️ still drifted | `tests/test_config_flow_helpers.py` |
| ⚠️ still drifted | `tests/test_modbus_helpers_call_flow.py` |

### Required CI gate status note

- All local maintained quality gates are green on Python 3.13.
- CI/HACS/hassfest gates were **not** executed in this run and are not claimed as proven.

## Ruff format drift

`ruff format --check custom_components tests tools` reports **2 files would be reformatted**
(down from 3 in the previous audit):

1. `tests/test_config_flow_helpers.py`
2. `tests/test_modbus_helpers_call_flow.py`

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
| 699 | `custom_components/thessla_green_modbus/coordinator/coordinator.py` |
| 708 | `custom_components/thessla_green_modbus/scanner/io_read.py` |
| 538 | `custom_components/thessla_green_modbus/modbus_helpers.py` |
| 468 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 454 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 440 | `tests/test_coordinator.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 431 | `tests/test_config_flow_helpers.py` |
| 422 | `tests/test_modbus_helpers_call_flow.py` |
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
| 79 | `read_bit_registers` | `scanner/io_read.py` |
| 77 | `_run_holding_read_retry_loop` | `scanner/io_read.py` (extracted) |

## Remaining hotspots

1. Coordinator concentration (`coordinator/coordinator.py` 699 lines, `ThesslaGreenModbusCoordinator` class 611 lines; `coordinator/schedule.py` 468 lines, `_CoordinatorScheduleMixin` 488 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 708 lines, `scanner/core.py` 454 lines). `read_holding` reduced to 29 lines (was 92); `read_bit_registers` (79 lines) is next candidate.
3. Mapping builder density (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 414 lines, `config_flow_device_validation.py`).
5. Two files with ruff format drift: `tests/test_config_flow_helpers.py`, `tests/test_modbus_helpers_call_flow.py`.

## Branch note (authoritative target)

- The working target branch is **dev**.
- **main** is **not** authoritative for this refactor/audit track.
- No `main -> dev` merge is recommended as part of this audit.
- This branch (`claude/dev-audit-refactor-SNaO3`) targets **dev** as PR base.

## Release readiness caveats

- **HACS/hassfest readiness is not proven** in this audit. `hassfest` and `hacs` are
  not installable PyPI packages; they run exclusively as GitHub Actions in CI.
  Release readiness via those gates must be verified through the CI pipeline.
- **Real-device validation is not proven** in this audit unless explicitly documented
  with device evidence. No on-device test evidence was captured in this run.
- `root manifest.json` is not flagged as a blocker unless tooling specifically requires it.
