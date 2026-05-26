# Maintainability audit

Date: 2026-05-08 (final cleanup release PR — phases A, B, E + docs).

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
- Baseline pytest: **1948 passed, 4 skipped**.
- Result: **kept**.

### PHASE B — scanner/io_read.py final focused cleanup

Files touched: `scanner/io_read.py`, `tests/test_scanner_io.py`.

Extractions and inlines:
1. Extracted `_run_word_read_single_attempt` from `_run_word_read_retry_loop`.
   - `_run_word_read_retry_loop`: 87 → 56 lines (36% reduction).
   - New `_run_word_read_single_attempt`: 70 lines (try/except attempt body).
2. Inlined 3 thin wrapper functions to maintain file within 820-line limit:
   - `_validate_register_response` (7 lines) → inlined into `_process_register_response`.
   - `_handle_terminal_read_failure` (3 lines) → inlined at 3 call sites (now direct `mark_failed_addresses`).
   - `_extend_or_abort_register_results` (8 lines) → inlined into `read_register_block` (now direct `append_read_block`).
3. Test updated: `test_extend_or_abort_register_results_handles_none_and_appends` renamed to
   `test_append_read_block_handles_none_and_appends` and updated to use `append_read_block` directly.
- `io_read.py` file: 797 → 813 lines (within 820-line strict limit).
- HA-independence invariant preserved.
- Targeted tests: 198 passed.
- Full gates after phase: **1948 passed, 4 skipped**.
- Result: **kept**.

### PHASE C — scanner/core.py final split

- Assessment: `scanner/core.py` is 478/760 line limit; `__init__` (68 lines) and `create` (52 lines)
  are both within the 210-line function limit.
- Both functions are already fully delegated minimal wrappers; apparent length is dominated by
  necessary parameter lists, not extractable logic.
- Result: **SKIPPED** — no meaningful extraction exists within safe bounds.

### PHASE D — coordinator/coordinator.py final split

- Assessment: `coordinator/coordinator.py` is 675/1200 line limit; `from_params` (54 lines) and
  `__init__` (47 lines) are both well under the 220-line function limit.
- Both functions are already fully delegated minimal wrappers; same pattern as scanner/core.py.
- Result: **SKIPPED** — no meaningful extraction exists within safe bounds.

### PHASE E — coordinator/schedule.py final split

Files touched: `coordinator/schedule.py`.

Extraction: `_locked_single_register_write` pulled from `async_write_register`.
- `async_write_register`: 49 → 30 lines (39% reduction).
- New `_locked_single_register_write`: 31 lines (prepare definition, encode, build plan, run attempts).
- `schedule.py` file: 420 → 433 lines (well within 1300-line default limit).
- Coordinator package API invariant preserved: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- Top-level `coordinator.py` remains absent.
- Targeted tests: 303 passed.
- Full gates after phase: **1948 passed, 4 skipped**.
- Result: **kept**.

### PHASE F — config_flow.py final cleanup

- Assessment: `config_flow.py` is 467/1000 line limit; max function `validate_input` at 36 lines
  (limit 220). All functions within all maintainability limits.
- Result: **SKIPPED** — optional phase; all functions within limits; diff manageable without it.

### PHASE G — release-readiness audit

- manifest.json: domain `thessla_green_modbus`, version `2.8.0`, homeassistant `2026.1.0`,
  integration_type `hub`. Status: **present and consistent**.
- pyproject.toml: version `2.8.0`, requires-python `>=3.13`. Status: **consistent with manifest**.
- hacs.json: present — name "ThesslaGreen Modbus", content_in_root: false, render_readme: true.
- **hassfest**: not available as installable CLI — **not proven locally**. CI runs it via GitHub Actions.
- **HACS CLI**: not available as installable CLI — **not proven locally**. CI runs it via GitHub Actions.
- Real-device validation: **not proven**.
- Release notes/tag/changelog: **not finalized**.
- Result: documented; no CI change made.

### PHASE H — docs/status refresh

- `docs/maintainability_audit.md`: refreshed with current state (this file).
- `docs/refactor_status.md`: refreshed.
- Result: **kept**.

## Architecture invariants snapshot

- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- `core/`, `transport/`, `registers/`, and `scanner/` do not import Home Assistant.
- Coordinator package API invariant: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- Entity mapping invariant: **366 entities**.

## Before / after metrics (this PR)

| File | Before (lines) | After (lines) | Notes |
|---|---:|---:|---|
| `scanner/io_read.py` (total) | 797 | **813** | +16 net |
| `scanner/io_read.py::_run_word_read_retry_loop` | 87 lines | **56 lines** | 36% reduction |
| `coordinator/schedule.py` (total) | 420 | **433** | +13 net |
| `coordinator/schedule.py::async_write_register` | 49 lines | **30 lines** | 39% reduction |

## Remaining hotspots

1. `scanner/io_read.py` — `_run_word_read_single_attempt` (70 lines, new), `read_bit_registers` (64 lines).
2. `scanner/core.py` — `__init__` (68 lines), `create` (52 lines) — long parameter lists, already minimal.
3. `coordinator/coordinator.py` — `from_params` (54 lines) — long parameter list pass-through.
4. `coordinator/schedule.py` — `_handle_write_attempt_exception` (45 lines).
5. Config-flow branching: `config_flow.py` — all within limits.

## Release-readiness status

| Item | Status |
|---|---|
| manifest.json | present, version 2.8.0, consistent |
| hacs.json | present |
| HACS validation | **not proven** (CLI unavailable locally; CI runs it) |
| hassfest validation | **not proven** (CLI unavailable locally; CI runs it) |
| Real-device validation | **not proven** |
| Release notes / tag | **not finalized** |
| Dependabot #1567 | not touched; pydantic version unchanged |

## Branch note

- The authoritative target branch is **main**.
- All active development and PR bases target `main` directly.

## Dependabot note

- **HACS/hassfest readiness:** CI runs hassfest and HACS validation on every push; check the Actions tab for the current status.
- **Real-device validation:** the `quality_scale: silver` in `manifest.json` is a self-assessed declaration. Independent real-device evidence has not been collected as part of this audit. Evidence should be documented in a dedicated section before claiming a higher quality scale.
