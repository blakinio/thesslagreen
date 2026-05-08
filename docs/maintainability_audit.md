# Maintainability audit

Date: 2026-05-08 (final cleanup release PR — phases A–G).

## Commands covered by latest successful validation

Latest complete validation uses Python 3.13.12:

- `ruff check custom_components tests tools` — **pass**
- `ruff check --select I custom_components tests tools` — **pass**
- `ruff format --check custom_components tests tools` — **0 files drift** (419 already formatted)
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools` — **pass**
- `python3.13 tools/compare_registers_with_reference.py` — **pass**
- `python3.13 tools/check_maintainability.py` — **Maintainability gate passed**
- `python3.13 tools/validate_entity_mappings.py` — **OK: 366 entities validated**
- `python3.13 -m pytest tests/ -q` — **1948 passed, 4 skipped**

## Exact status by validation gate

- **ruff check**: pass.
- **ruff import order check**: pass.
- **ruff format --check**: 0 files drift.
- **compileall**: pass.
- **compare_registers**: pass.
- **maintainability** (`check_maintainability.py`): pass.
- **entity mappings** (`validate_entity_mappings.py`): pass — **366 entities**.
- **pytest** (`pytest tests/ -q`): **1948 passed, 4 skipped**.

## Import gate (Python 3.13.12)

```
OK pydantic: 2.12.2
OK pytest: 9.0.0
OK pytest_asyncio: 1.3.0
OK pytest_homeassistant_custom_component: installed
OK homeassistant: installed
```

## Final cleanup PR — phase log

### PHASE A — full Python >=3.12 health audit

- Python 3.13.12 interpreter used.
- All gates passed at baseline.
- Baseline pytest: 1938 passed, 4 skipped.
- Result: **kept**.

### PHASE B — scanner/io_read.py final focused cleanup

Files touched: `scanner/io_read.py`, `tests/test_scanner_io.py`.

Extraction: `_handle_register_error_response` pulled out of `_process_register_response`.
- `_process_register_response` reduced: 60 → 41 lines.
- New `_handle_register_error_response`: 42 lines (pure, testable error-branch classifier).
- 4 new focused tests added in `test_scanner_io.py`.
- HA-independence invariant preserved.
- Targeted tests: 89 passed.
- Full gates after phase: **1942 passed, 4 skipped**.
- Result: **kept**.

### PHASE C — coordinator/coordinator.py final focused cleanup

Files touched: `_coordinator_init.py`, `coordinator/coordinator.py`.

Extraction: `apply_coordinator_config` added to `_coordinator_init.py`.
- `ThesslaGreenModbusCoordinator.__init__` reduced: 61 → 47 lines.
- New `apply_coordinator_config`: 31 lines (assigns normalized config attrs to fresh instance).
- Coordinator package API invariant preserved: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- Top-level `coordinator.py` remains absent.
- Targeted tests: 307 passed.
- Full gates after phase: **1942 passed, 4 skipped**.
- Result: **kept**.

### PHASE D — mappings/_mapping_builders.py final focused cleanup

Files touched: `mappings/_mapping_builders.py`.

Extraction: `_route_holding_register_to_mapping` pulled from the per-register dispatch loop in `_extend_entity_mappings_from_registers`.
- `_extend_entity_mappings_from_registers` reduced: 83 → 59 lines.
- New `_route_holding_register_to_mapping`: 49 lines (routes one holding register to its bucket).
- Entity count stable: 366 entities validated.
- Targeted tests: 284 passed, 3 skipped.
- Full gates after phase: **1942 passed, 4 skipped**.
- Result: **kept**.

### PHASE E — scanner/core.py final focused cleanup

Files touched: `scanner/selection.py`, `tests/test_scanner_safe_scan.py`.

Extraction: `_split_groups_around_missing` pulled from `group_registers_for_batch_read` in `scanner/selection.py`.
- `group_registers_for_batch_read` reduced: 37 → 26 lines.
- New `_split_groups_around_missing`: 17 lines (pure function, no scanner dependency).
- 6 new focused unit tests added in `test_scanner_safe_scan.py`.
- HA-independence invariant preserved.
- Targeted tests: 198 passed.
- Full gates after phase: **1948 passed, 4 skipped**.
- Result: **kept**.

### PHASE F — release-readiness validation/audit

- manifest.json: domain `thessla_green_modbus`, version `2.8.0`, homeassistant `2026.1.0`, integration_type `hub`.
- pyproject.toml: version `2.8.0`, requires-python `>=3.13`.
- hacs.json: present — name "ThesslaGreen Modbus", content_in_root: false, render_readme: true.
- **hassfest**: not available as installable CLI in this environment — **not proven locally**.
- **HACS CLI**: not available as installable CLI in this environment — **not proven locally**.
- CI (`ci.yaml`) installs `hacs` pip package during test runs; HACS/hassfest gates run via GitHub Actions.
- Real-device validation: **not proven**.
- Release notes/tag/changelog: **not finalized**.
- Result: documented; no CI change made (hassfest/hacs not locally available).

### PHASE G — docs/status refresh

- `docs/maintainability_audit.md`: refreshed with current state (this file).
- `docs/refactor_status.md`: refreshed.
- Result: **kept**.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.
- Coordinator package API invariant: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- Entity mapping invariant: **366 entities**.

## Before / after metrics

| File | Before this PR | After this PR |
|---|---:|---:|
| `scanner/io_read.py` (non-empty lines) | 690 | **713** (+23 from new helper) |
| `scanner/io_read.py::_process_register_response` | 60 lines | **41 lines** |
| `coordinator/coordinator.py` (non-empty lines) | 606 | **596** |
| `coordinator/coordinator.py::__init__` | 61 lines | **47 lines** |
| `mappings/_mapping_builders.py` (non-empty lines) | 441 | **466** (+25 from new helper) |
| `mappings/_mapping_builders.py::_extend_entity_mappings_from_registers` | 83 lines | **59 lines** |
| `scanner/selection.py::group_registers_for_batch_read` | 37 lines | **26 lines** |
| `_coordinator_init.py` | 63 non-empty lines | **86 non-empty lines** (+23 from helper) |

## Remaining hotspots

1. `scanner/io_read.py` — `_run_word_read_retry_loop` (87 lines) and `read_bit_registers` (64 lines) remain.
2. `scanner/core.py` — `__init__` (68 lines) and `create` (52 lines) are parameter-list-heavy wrappers.
3. `coordinator/coordinator.py` — `from_params` (54 lines) is a long-signature pass-through.
4. `coordinator/schedule.py` — `async_write_register` (49 lines) and `_handle_write_attempt_exception` (45 lines).
5. Config-flow branching (`config_flow.py`) — not touched in this cycle.

## Release-readiness status

| Item | Status |
|---|---|
| manifest.json | present, version 2.8.0 |
| hacs.json | present |
| HACS validation | **not proven** (CLI unavailable locally; CI runs it) |
| hassfest validation | **not proven** (CLI unavailable locally; CI runs it) |
| Real-device validation | **not proven** |
| Release notes / tag | **not finalized** |
| Dependabot #1567 | not touched; pydantic version unchanged |

## Branch note

- The working target branch is **dev**.
- **main** is **not** authoritative for this refactor/audit track.
- No `main -> dev` merge is recommended as part of this audit.

## Dependabot note

- PR #1567 remains separate from this refactor/audit stream.
- This audit cleanup does not change dependency versions.
- pydantic version unchanged at 2.12.2.
