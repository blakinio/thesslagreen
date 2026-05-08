# Maintainability audit

Date: 2026-05-08 (post-hotspot cleanup PR — phases B–F).

## Commands covered by latest successful validation

Latest complete validation uses Python 3.13.12:

- `ruff check custom_components tests tools` — **pass**
- `ruff check --select I custom_components tests tools` — **pass**
- `ruff format --check custom_components tests tools` — **0 files drift** (419 already formatted)
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools` — **pass**
- `python3.13 tools/compare_registers_with_reference.py` — **pass**
- `python3.13 tools/check_maintainability.py` — **Maintainability gate passed**
- `python3.13 tools/validate_entity_mappings.py` — **OK: 366 entities validated**
- `python3.13 -m pytest tests/ -q` — **1938 passed, 4 skipped**

## Exact status by validation gate

- **ruff check**: pass.
- **ruff import order check**: pass.
- **ruff format --check**: 0 files drift.
- **compileall**: pass.
- **compare_registers**: pass.
- **maintainability** (`check_maintainability.py`): pass.
- **entity mappings** (`validate_entity_mappings.py`): pass — **366 entities**.
- **pytest** (`pytest tests/ -q`): **1938 passed, 4 skipped**.

## Notable merged changes (2026-05-08 series)

All changes below are already merged into **dev** as of this audit.

### Config-flow runtime extraction (merged, earlier PR)

- `_load_scanner_module` moved from inline in `config_flow.py` into `load_scanner_module` in `config_flow_runtime.py`.

### Config-flow bound-adapter extraction (merged, earlier PR)

- `_validate_tcp_config`, `_validate_rtu_config`, `_process_scan_capabilities` removed from `config_flow.py`.

### Coordinator config property extraction (merged, earlier PR)

- 9 pairs of config-backed property getter/setter moved into `_CoordinatorConfigPropertiesMixin`.
- `coordinator.py` non-empty lines reduced from 666 to 605.

### Scanner failure logging helper promotion (merged, earlier PR)

- `_mark_failed_addresses`, `_log_read_abort`, `_log_read_failure` moved to `scanner/io_read_helpers.py`.
- `scanner/io_read.py` non-empty lines reduced from 714 to 701.

### Schedule write-path deduplication (merged, earlier PR)

- `_write_holding_multi` delegates to `_write_registers_payload` per chunk.
- `coordinator/schedule.py` non-empty lines reduced from 419 to 401.

### Hotspot cleanup — PHASE B: scanner/io_read.py (this PR)

- Extracted `_run_word_read_retry_loop` as a shared core retry loop.
- `_run_input_read_retry_loop` (75 lines) and `_run_holding_read_retry_loop` (77 lines) are now thin 26-line wrappers.
- `scanner/io_read.py` non-empty lines: 701 → 690.
- HA-independence invariant preserved. 188 scanner tests pass.

### Hotspot cleanup — PHASE C: coordinator/coordinator.py (this PR)

- Extracted `_build_transport_selector_fn` method from the 60-line `_ensure_connected`.
- Removed dead duplicate docstring string from `_get_client_method`; simplified repeated getattr/callable pattern to a loop.
- `_ensure_connected` reduced from 60 → 17 lines.
- `coordinator.py` non-empty lines: 605 → 606 (same; inner function became named method).
- Coordinator package API invariant preserved. 307 coordinator tests pass.

### Hotspot cleanup — PHASE D: scanner/core.py (this PR)

- Extracted `apply_scanner_params` into `scanner/setup.py`.
- `ThesslaGreenDeviceScanner.__init__` reduced from 88 → 68 lines.
- `scanner/core.py` non-empty lines: 451 → 433.
- HA-independence invariant preserved. 188 scanner tests pass.

### Hotspot cleanup — PHASE E: mappings/_mapping_builders.py (this PR)

- Extracted `_resolve_base_helpers()` combining the identical 3-line resolver trio used in `_load_number_mappings` and `_load_discrete_mappings`.
- `_mapping_builders.py` non-empty lines: 437 → 441 (net +4 from new helper; both loaders simplified).
- 366 entities validated. 284 mapping tests pass.

### Hotspot cleanup — PHASE F: coordinator/schedule.py (this PR)

- Extracted `run_multi_register_write_attempts` into `coordinator/write_path.py`, mirroring existing `run_single_write_attempts`.
- `async_write_registers` reduced from 67 → 31 lines.
- `coordinator/schedule.py` non-empty lines: 401 → 367.
- All write/retry/lock/refresh behaviors unchanged. 303 coordinator tests pass.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant in the last validation snapshot.
- Coordinator package API invariant: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- Entity mapping invariant: **366 entities**.

## Current largest known production hotspots

| Area | Before | After this PR |
|---|---:|---:|
| `custom_components/thessla_green_modbus/scanner/io_read.py` | 701 | **690** |
| `custom_components/thessla_green_modbus/coordinator/coordinator.py` | 605 | 606 |
| `custom_components/thessla_green_modbus/scanner/core.py` | 451 | **433** |
| `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` | 437 | 441 |
| `custom_components/thessla_green_modbus/coordinator/schedule.py` | 401 | **367** |
| `custom_components/thessla_green_modbus/coordinator/write_path.py` | 118 | 184 (gained `run_multi_register_write_attempts`) |

## Remaining hotspots

1. `coordinator/coordinator.py` — `from_params` (54 lines) and `__init__` (61 lines) still large.
2. `scanner/io_read.py` — `_process_register_response` (60 lines) and `read_bit_registers` (64 lines) remain.
3. `scanner/core.py` — `create` (52 lines) and `_group_registers_for_batch_read` (24 lines).
4. `mappings/_mapping_builders.py` — `_extend_entity_mappings_from_registers` (83 lines) remains.
5. Config-flow branching (`config_flow.py`) — not touched in this cycle.

## Recommended next work

1. `_process_register_response` and `read_bit_registers` in `scanner/io_read.py` are the next extraction candidates.
2. `_extend_entity_mappings_from_registers` in `mappings/_mapping_builders.py` could be split by routing phase.
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
