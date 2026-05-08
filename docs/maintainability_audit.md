# Maintainability audit

Date: 2026-05-08 (post-PR #1595 documentation cleanup).

## Commands covered by latest successful validation

Latest complete validation evidence comes from PR #1595, using Python 3.12:

- `ruff check custom_components tests tools`
- `ruff check --select I custom_components tests tools`
- `ruff format --check custom_components tests tools`
- `python3.12 -m compileall -q custom_components/thessla_green_modbus tests tools`
- `python3.12 tools/check_maintainability.py`
- `python3.12 tools/validate_entity_mappings.py`
- `python3.12 -m pytest tests/ -q`

## Exact status by validation gate

- **ruff check**: pass.
- **ruff import order check**: pass.
- **ruff format --check**: 0 files drift.
- **compileall**: pass.
- **maintainability** (`check_maintainability.py`): pass.
- **entity mappings** (`validate_entity_mappings.py`): pass — **366 entities**.
- **pytest** (`pytest tests/ -q`): **1938 passed, 4 skipped**.

Earlier Python 3.13 validation from the 2026-05-08 config-flow cleanup series remains historical context, but the latest full post-#1595 validation evidence is the Python 3.12 pass above.

## Notable merged changes (2026-05-08 series)

All changes below are already merged into **dev** as of this audit.

### Config-flow runtime extraction

- `_load_scanner_module` moved from inline in `config_flow.py` into `load_scanner_module` in `config_flow_runtime.py`.
- `import_module` import removed from `config_flow.py`.
- `_SCANNER_MODULE_PATH` constant added to `config_flow_runtime.py` for testability.
- 5 focused unit tests added in `tests/test_config_flow_runtime_loader.py`.

### Config-flow bound-adapter extraction

- `_validate_tcp_config`, `_validate_rtu_config`, `_process_scan_capabilities` removed from `config_flow.py`.
- Replaced by `validate_tcp_config_bound`, `validate_rtu_config_bound`, and `process_scan_capabilities_bound` in `config_flow_validation.py`.
- 13 focused tests added in `tests/test_config_flow_validation_bound.py`.

### Coordinator test splits

- `TestParseBackoffJitter` split out of `test_coordinator.py` into focused coordinator backoff/jitter test modules.
- No production behavior changed.

### Coordinator config property extraction

- 9 pairs of config-backed property getter/setter moved from `ThesslaGreenModbusCoordinator` into `_CoordinatorConfigPropertiesMixin` in `coordinator/config_properties.py`.
- `coordinator.py` non-empty lines reduced from 666 to 605.
- Coordinator package API invariant preserved.

### Scanner failure logging helper promotion

- `_mark_failed_addresses`, `_log_read_abort`, `_log_read_failure` moved from `scanner/io_read.py` to `scanner/io_read_helpers.py` as public helpers.
- `scanner/io_read.py` non-empty lines reduced from 714 to 701.
- HA-independence invariant preserved.

### Schedule write-path deduplication

- `_write_holding_multi` in `coordinator/schedule.py` now delegates to `_write_registers_payload` per chunk.
- Duplicated transport/client/fallback branching removed from that method.
- `coordinator/schedule.py` non-empty lines reduced from 419 to 401.
- Write/chunking/retry behavior unchanged.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant in the last validation snapshot.
- Coordinator package API invariant: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- Entity mapping invariant: **366 entities**.

## Current largest known production hotspots

| Area | Current known size |
|---|---:|
| `custom_components/thessla_green_modbus/scanner/io_read.py` | 701 non-empty lines |
| `custom_components/thessla_green_modbus/coordinator/coordinator.py` | 605 non-empty lines |
| `custom_components/thessla_green_modbus/scanner/core.py` | 451 non-empty lines |
| `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` | 437 non-empty lines |
| `custom_components/thessla_green_modbus/coordinator/schedule.py` | 401 non-empty lines |
| `custom_components/thessla_green_modbus/config_flow.py` | reduced by recent extractions; remeasure before next edit |

## Remaining hotspots

1. Coordinator size/branching (`coordinator/coordinator.py`, `coordinator/schedule.py`).
2. Scanner read/orchestration complexity (`scanner/io_read.py`, `scanner/core.py`).
3. Mapping builder density (`mappings/_mapping_builders.py`).
4. Config-flow branching (`config_flow.py`).
5. Large test modules where focused splits remain possible.

## Recommended next work

1. Continue with a focused extraction in `scanner/io_read.py` or `scanner/core.py`.
2. Alternatively reduce `mappings/_mapping_builders.py` if a cohesive helper extraction is visible.
3. Keep each PR narrow: one production extraction plus focused tests and refreshed docs.

## Branch note

- The working target branch is **dev**.
- **main** is **not** authoritative for this refactor/audit track.
- No `main -> dev` merge is recommended as part of this audit.

## Release readiness caveats

- **HACS/hassfest readiness is not proven** unless CI explicitly runs those actions.
- **Real-device validation is not proven** unless explicitly documented with device evidence.

## Dependabot note

- PR #1567 remains separate from this refactor/audit stream.
- This audit cleanup does not change dependency versions.
