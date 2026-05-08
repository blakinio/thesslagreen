# Maintainability audit

Date: 2026-05-08 (Python 3.13 full-pass + schedule encode_write_value + scanner normalize_effective_batch)

## Commands executed (exact)

- `git branch --show-current`
- `git status --short`
- `python3.13 -m venv /tmp/venv313 && /tmp/venv313/bin/pip install ...` (Python 3.13 venv)
- Import gate script:
  - `python3.13 - <<'PY' ... __import__(...) ... PY`
- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools`
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python3.13 tools/compare_registers_with_reference.py`
- `python3.13 tools/check_maintainability.py`
- `python3.13 tools/validate_entity_mappings.py`
- `pytest tests/ -q`
- AST metrics script (largest files/classes/functions snapshot)
- `rg "from homeassistant|import homeassistant" custom_components/thessla_green_modbus/scanner`

## Import gate result

Environment: **Python 3.13.12** (`/tmp/venv313`). All five required modules import successfully.

- `pydantic`: ✅ `OK pydantic: 2.12.2`
- `pytest`: ✅ `OK pytest: 9.0.0`
- `pytest_asyncio`: ✅ `OK pytest_asyncio: 1.3.0`
- `pytest_homeassistant_custom_component`: ✅ pass
- `homeassistant`: ✅ pass

## Exact status by validation gate

### Required maintained gates (Python 3.13.12)

- **ruff check**: ✅ pass (`All checks passed!`).
- **ruff import order check**: ✅ pass (`All checks passed!`).
- **ruff format --check**: ✅ **0 files drift** (413 files already formatted).
- **compileall**: ✅ pass.
- **register compare** (`compare_registers_with_reference.py`): ✅ pass
  (informational: 62 extras; 242 name mismatches on common addresses — unchanged).
- **maintainability** (`check_maintainability.py`): ✅ pass (`Maintainability gate passed.`).
- **entity mappings** (`validate_entity_mappings.py`): ✅ pass (`OK: 366 entities validated`).
- **pytest** (`pytest tests/ -q`): ✅ **1915 passed, 4 skipped**, 90 warnings in 12.68s.

### Notable changes since previous audit (2026-05-08 modbus_helpers._encode_read_frame run)

**PHASE B — coordinator/schedule.py write-path cleanup:**

- `_encode_write_value` (55-line method) extracted from `_CoordinatorScheduleMixin` into
  standalone `encode_write_value` function in `coordinator/write_path.py`.
- `_CoordinatorScheduleMixin` class: **488 → 432 AST lines** (−56).
- `coordinator/schedule.py` non-empty lines: **468 → 419** (−49).
- `coordinator/write_path.py` non-empty lines: **63 → 118** (+55).
- 9 focused unit tests added in `tests/test_coordinator_register_writes.py`.
- coordinator package `__all__` invariant: `["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]` — unchanged.
- No top-level `coordinator.py` file created.

**PHASE C — scanner/core.py focused cleanup:**

- Inline batch-clamping logic in `ThesslaGreenDeviceScanner.__init__` extracted into
  `normalize_effective_batch(max_registers_per_request, *, max_batch)` in `scanner/setup.py`.
- `ThesslaGreenDeviceScanner.__init__`: **91 → 88 AST lines** (−3 inline lines replaced by 2-line call).
- `scanner/setup.py` gained 14-line `normalize_effective_batch` function (parallel to existing `normalize_backoff_jitter`).
- 7 focused unit tests added in `tests/test_device_scanner_setup.py`.
- Scanner HA-independence invariant: **no Home Assistant imports** detected.

**Test count change:** 1900 → 1909 → 1915 (+15 total from PHASE B + PHASE C).

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
| 451 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 440 | `tests/test_coordinator.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 419 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 417 | `custom_components/thessla_green_modbus/mappings/_static_discrete.py` |

### Largest classes (AST span, top 10)

| Lines | Class | File |
|------:|-------|------|
| 611 | `ThesslaGreenModbusCoordinator` | `coordinator/coordinator.py` |
| 432 | `_CoordinatorScheduleMixin` | `coordinator/schedule.py` (was 488) |
| 425 | `ThesslaGreenDeviceScanner` | `scanner/core.py` (was 428) |
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
| 91 | `verify_connection` | `scanner/setup.py` |

## PHASE B before/after metrics

| Metric | Before | After |
|--------|--------|-------|
| `_CoordinatorScheduleMixin` AST lines | 488 | 432 |
| `coordinator/schedule.py` non-empty | 468 | 419 |
| `coordinator/write_path.py` non-empty | 63 | 118 |
| New test functions | — | +9 |
| `_encode_write_value` in mixin | yes | **removed** |
| `encode_write_value` standalone in write_path | no | **added** |

## PHASE C before/after metrics

| Metric | Before | After |
|--------|--------|-------|
| `ThesslaGreenDeviceScanner.__init__` AST lines | 91 | 88 |
| Inline batch-clamp lines in `__init__` | 6 | 2 (delegation) |
| `normalize_effective_batch` in setup.py | no | **added** (14 lines) |
| New test functions | — | +7 |

## Remaining hotspots

1. Coordinator concentration (`coordinator/coordinator.py` 699 lines, `ThesslaGreenModbusCoordinator` 611 lines; `coordinator/schedule.py` 419 lines, `_CoordinatorScheduleMixin` 432 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 451 lines).
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
