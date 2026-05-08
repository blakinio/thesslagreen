# Refactor status (current)

Last reviewed: 2026-05-08 (Python 3.12 full-pass + coordinator config_properties mixin + scanner io_read_helpers + schedule._write_holding_multi refactor).
Last reviewed: 2026-05-08 (Python 3.13 full-pass + config_flow bound-adapter extraction + coordinator test split).
Last reviewed: 2026-05-08 (Python 3.13 full-pass + config_flow_runtime load_scanner_module + coordinator backoff jitter test split).

Related document:

- `docs/maintainability_audit.md`

## Scope and direction

The project remains in incremental layered refactor:

- HA layer (platforms, flows, services, diagnostics)
- coordinator (HA adapter)
- core (device/domain logic)
- registers (definitions + codec + planning)
- scanner (capability discovery)
- transport (Modbus I/O)

## Hard constraints

The following constraints remain active and must be preserved:

1. No legacy modules.
2. No compatibility shims.
3. No re-export-only modules.
4. No proxy modules.
5. `core/`, `transport/`, `registers/`, and `scanner/` must not import Home Assistant.

## Current invariant verification snapshot (2026-05-08 load_scanner_module + backoff jitter split)

- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- HA imports in `core/transport/registers/scanner`: **none detected** by grep.
- Compatibility grep (`compat|shim|proxy|re-export|legacy`): informational matches present in docs/tests/comments/known compatibility code references.

## Notable since previous snapshot (2026-05-08 config_flow + coordinator test cleanup)

- Full test suite validated on Python 3.13 — **1913 passed, 4 skipped** (+13 vs previous run).
- Ruff format drift: **0 files** (415 files).
- **PHASE B**: Three adapter functions removed from `config_flow.py`; replaced by `validate_tcp_config_bound`, `validate_rtu_config_bound`, `process_scan_capabilities_bound` in `config_flow_validation.py`. `config_flow.py` 414 → 394 non-empty lines. 13 new focused tests in `tests/test_config_flow_validation_bound.py`.
- **PHASE C**: `TestParseBackoffJitter` (5 test methods) moved from `test_coordinator.py` to `tests/test_coordinator_parse_backoff.py`. `test_coordinator.py` 440 → 412 non-empty lines; total coordinator test count unchanged at 277.
## Notable since previous snapshot (2026-05-08 Phase B+C run)

- Full test suite validated on Python 3.13 — **1920 passed, 4 skipped**.
- Ruff format drift: **0 files** ✅.
- **PHASE B** — `_load_scanner_module` (7-line async function) moved from inline in `config_flow.py`
  into `load_scanner_module` in `config_flow_runtime.py`. `config_flow.py` non-empty: 414 → 407.
  `import_module` import removed from `config_flow.py`. `_SCANNER_MODULE_PATH` constant added for
  testability. 5 focused unit tests added in `tests/test_config_flow_runtime_loader.py`.
- **PHASE C** (test-only) — `TestParseBackoffJitter` class (5 tests) moved from `test_coordinator.py`
  into `test_coordinator_backoff_jitter.py`. `test_coordinator.py` non-empty: 440 → 412.
  Coordinator test collection total: **286 → 286** (unchanged). No production files changed.

## Required gate status snapshot (2026-05-08 load_scanner_module run)

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **0 files drift** (416 formatted) ✅.
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python3.13 tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches).
- `python3.13 tools/check_maintainability.py`: **pass** (`Maintainability gate passed.`).
- `python3.13 tools/validate_entity_mappings.py`: **pass** (`OK: 366 entities validated`).
- `python3.13 -m pytest tests/ -q`: **pass** — 1913 passed, 4 skipped, 84 warnings.
- `python3.13 -m pytest tests/ -q`: **pass** — 1920 passed, 4 skipped, 90 warnings.
- Import gate (all 5 modules): **pass** on Python 3.13.
- Coordinator tests: **300 passed**, 1 warning.
- Config flow tests: **142 passed**, 1 warning.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed (runs as GitHub Action only; not a PyPI package).
- `HACS`: not executed (runs as GitHub Action only; not a PyPI package).

## Notable since previous snapshot (2026-05-08 config_properties/io_read/schedule pass — Python 3.12)

- Full test suite validated on Python 3.12.3 — **1938 passed, 4 skipped**, 90 warnings.
- Ruff format drift: **0 files** (419 files) ✅.
- **PHASE B** — `_CoordinatorConfigPropertiesMixin` extracted from `ThesslaGreenModbusCoordinator`. Nine config-backed property pairs (host, port, slave_id, connection_type, connection_mode, serial_port, baud_rate, parity, stop_bits) moved to `coordinator/config_properties.py`. `coordinator.py` non-empty: 666 → 605 (−61). No public API change.
- **PHASE C** — `mark_failed_addresses`, `log_read_abort`, `log_read_failure` promoted from private helpers in `scanner/io_read.py` to public exports in `scanner/io_read_helpers.py`. `scanner/io_read.py` non-empty: 714 → 701 (−13).
- **PHASE E** — `_write_holding_multi` in `coordinator/schedule.py` refactored to use `_write_registers_payload` instead of duplicating the three-branch transport selection. `schedule.py` non-empty: 419 → 401 (−18).
- PHASE D (mappings): skipped — no safe focused extraction identified; 366 entity invariant preserved.
- PHASE F (test cleanup): skipped — coordinator tests already well-split across 9 files.

## Required gate status snapshot (2026-05-08 config_properties/io_read/schedule pass)

- `ruff check custom_components tests tools`: **pass** ✅.
- `ruff check --select I custom_components tests tools`: **pass** ✅.
- `ruff format --check custom_components tests tools`: **0 files drift** (419 formatted) ✅.
- `python3.12 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass** ✅.
- `python3.12 tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches) ✅.
- `python3.12 tools/check_maintainability.py`: **pass** (`Maintainability gate passed.`) ✅.
- `python3.12 tools/validate_entity_mappings.py`: **pass** (`OK: 366 entities validated`) ✅.
- `python3.12 -m pytest tests/ -q`: **pass** — **1938 passed, 4 skipped**, 90 warnings ✅.
- Import gate (all 5 required modules): **pass** on Python 3.12.3.
- HA-independence invariant (`scanner/` has no HA imports): **pass** ✅.
- Coordinator package API invariant (`__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`): **pass** ✅.
- Path invariant (no top-level `coordinator.py`): **pass** ✅.

## Remaining hotspots (current queue)

1. Coordinator size/branching (`coordinator/coordinator.py` 605 lines; `coordinator/schedule.py` 401 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 701 lines, `scanner/core.py` 451 lines).
3. Mapping build complexity (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` ~407 lines).
5. Ruff format drift: 0 files ✅.

## Previous remaining hotspots

1. Coordinator size/branching (`coordinator/coordinator.py` 666 lines, `coordinator/schedule.py` 419 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 451 lines).
3. Mapping build complexity (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 394 lines; reduced from 414).
4. Config-flow branching (`config_flow.py` 407 lines).
5. Ruff format drift: 0 files ✅.

## Branch note

- Target branch for ongoing work and PR base is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended by this audit.

## Readiness caveats

- **HACS/hassfest readiness:** not claimable (not executed in this run; these run as GitHub Actions only).
- **Real-device readiness:** not claimable from this verification run; no new on-device evidence captured.

## Dependabot note

- PR #1567 was **not touched** in any session.
- Pydantic version was **not changed**. `requirements-dev.txt` still pins `pydantic==2.12.2`.
