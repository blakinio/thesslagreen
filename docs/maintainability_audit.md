# Maintainability audit

Date: 2026-05-08 (Python 3.13 full-pass + config_flow bound-adapter extraction + coordinator test split)
Date: 2026-05-08 (Python 3.13 full-pass + config_flow_runtime load_scanner_module + coordinator backoff jitter test split)

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
- **ruff format --check**: ✅ **0 files drift** (413 files already formatted).
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
- **pytest** (`pytest tests/ -q`): ✅ **1920 passed, 4 skipped**, 90 warnings in 14.87s.

### Notable changes since previous audit (2026-05-08 modbus_helpers._encode_read_frame run)

**PHASE B — config_flow_runtime.py: extract load_scanner_module:**

- `_load_scanner_module` (7-line async function) moved from inline in `config_flow.py` into
  `load_scanner_module` function in `config_flow_runtime.py`.
- `config_flow.py` now imports `load_scanner_module as _load_scanner_module` from runtime module.
- `import_module` import removed from `config_flow.py`.
- `_SCANNER_MODULE_PATH` constant added to `config_flow_runtime.py` for testability.
- 5 focused unit tests added in `tests/test_config_flow_runtime_loader.py`.

**PHASE C — test_coordinator.py: move TestParseBackoffJitter test group:**

- `TestParseBackoffJitter` class (5 tests, 37 lines) moved from `tests/test_coordinator.py`
  into new `tests/test_coordinator_backoff_jitter.py`.
- `DEFAULT_BACKOFF_JITTER` import removed from `test_coordinator.py` (no longer needed).
- `test_coordinator.py` non-empty lines: **440 → 412** (−28).
- Test collection total: **286 → 286** (unchanged, redistribution only).
- No production files changed in PHASE C.

**Test count change:** 1915 → 1920 (+5 from PHASE B new tests).

### Ruff format drift

`ruff format --check custom_components tests tools` reports **0 files would be reformatted**.

All 415 files are already formatted. ✅
All 416 files are already formatted. ✅

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

**Extraction: `_load_scanner_module` → `config_flow_runtime.load_scanner_module`**

Before:
- `config_flow.py` non-empty: **414** lines
- `_load_scanner_module` inline in `config_flow.py` (7-line async function)
- `config_flow_runtime.py` non-empty: **48** lines
- No tests for scanner module loading isolation

After:
- `config_flow.py` non-empty: **407** lines (−7)
- `config_flow_runtime.py` non-empty: **62** lines (+14)
- `load_scanner_module` function + `_SCANNER_MODULE_PATH` constant added to runtime module
- 5 focused tests added in `tests/test_config_flow_runtime_loader.py`

Step names, form schemas, error keys, abort reasons, reauth/reconfigure/options behavior: all unchanged ✅

Targeted config flow test result: **142 passed**, 1 warning ✅

## PHASE C summary

**Test-only split: `TestParseBackoffJitter` → `tests/test_coordinator_backoff_jitter.py`**

Before:
- `test_coordinator.py` non-empty: **440** lines
- `TestParseBackoffJitter` class (5 tests) inline in `test_coordinator.py`
- `DEFAULT_BACKOFF_JITTER` import present but only used by that class

After:
- `test_coordinator.py` non-empty: **412** lines (−28)
- New `tests/test_coordinator_backoff_jitter.py` with `TestParseBackoffJitter` (5 tests)
- `DEFAULT_BACKOFF_JITTER` import removed from `test_coordinator.py`
- Coordinator test collection: **286 → 286** (unchanged) ✅

No production files changed in PHASE C ✅

Coordinator targeted test result: **300 passed**, 1 warning ✅

## Largest files/classes/functions (current — 2026-05-08 Phase B+C refresh)

### Largest files (non-empty lines, top 10)

| Lines | Path |
|------:|------|
| 714 | `custom_components/thessla_green_modbus/scanner/io_read.py` |
| 666 | `custom_components/thessla_green_modbus/coordinator/coordinator.py` |
| 537 | `custom_components/thessla_green_modbus/modbus_helpers.py` |
| 468 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 454 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 417 | `custom_components/thessla_green_modbus/mappings/_static_discrete.py` |
| 412 | `tests/test_coordinator.py` |
| 451 | `custom_components/thessla_green_modbus/scanner/core.py` |
| 437 | `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` |
| 433 | `tests/test_config_flow_helpers.py` |
| 420 | `tests/test_modbus_helpers_call_flow.py` |
| 419 | `custom_components/thessla_green_modbus/coordinator/schedule.py` |
| 412 | `tests/test_coordinator.py` |
| 407 | `custom_components/thessla_green_modbus/config_flow.py` |

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
| 91 | `verify_connection` | `scanner/setup.py` |

## PHASE B before/after metrics

| Metric | Before | After |
|--------|--------|-------|
| `config_flow.py` non-empty | 414 | 407 |
| `config_flow_runtime.py` non-empty | 48 | 62 |
| `_load_scanner_module` inline in config_flow.py | yes | **removed** |
| `load_scanner_module` in config_flow_runtime.py | no | **added** |
| `_SCANNER_MODULE_PATH` constant | no | **added** |
| New test functions | — | +5 |
| `import_module` import in config_flow.py | yes | **removed** |

## PHASE C before/after metrics

| Metric | Before | After |
|--------|--------|-------|
| `test_coordinator.py` non-empty | 440 | 412 |
| `TestParseBackoffJitter` in test_coordinator.py | yes | **moved** |
| `test_coordinator_backoff_jitter.py` | absent | **created** |
| Coordinator test count total | 286 | 286 (unchanged) |
| `DEFAULT_BACKOFF_JITTER` import in test_coordinator.py | yes | **removed** |

## Coordinator collection comparison

```
before count: 286
after count: 286
missing: []
added: []
```

## Remaining hotspots

1. Coordinator concentration (`coordinator/coordinator.py` 666 lines, `ThesslaGreenModbusCoordinator` 577 AST lines; `coordinator/schedule.py` 419 lines, `_CoordinatorScheduleMixin` 432 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 451 lines).
3. Mapping builder density (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 394 lines; reduced from 414 in previous audit).
4. Config-flow branching (`config_flow.py` 407 lines).
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
