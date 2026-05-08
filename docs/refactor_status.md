# Refactor status (current)

Last reviewed: 2026-05-08 (refresh after test recovery).

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

## Current invariant verification snapshot (2026-05-08 refresh)

- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- HA imports in `core/transport/registers/scanner`: **none detected** by grep.
- Compatibility grep (`compat|shim|proxy|re-export|legacy`): informational matches present in docs/tests/comments/known compatibility code references.

## Notable since previous snapshot (2026-05-08 pre-refresh)

- `scanner/io_read_helpers.py` — new scanner helper module added; has ruff format drift.
- `coordinator/coordinator.py` — slight growth (697 → 699 non-empty lines).
- `scanner/io_read.py` — reduced (704 → 694 non-empty lines).
- `modbus_helpers.py` — grown (522 → 538 non-empty lines).
- `config_flow.py` — reduced (428 → 414 non-empty lines).
- `tests/test_text.py` — ruff format drift resolved (removed from drift list).
- Ruff format drift reduced from **7 files** to **3 files**:
  - `scanner/io_read_helpers.py`, `tests/test_config_flow_helpers.py`, `tests/test_modbus_helpers_call_flow.py`.

## Required gate status snapshot (2026-05-08 refresh)

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **3 files drift**
  (scanner/io_read_helpers.py, tests/test_config_flow_helpers.py,
  tests/test_modbus_helpers_call_flow.py). Improved from 7 files in prior audit.
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches).
- `python tools/check_maintainability.py`: **pass**.
- `python tools/validate_entity_mappings.py`: **BLOCKED** — requires `homeassistant` (Python >=3.12); code is syntactically valid.
- `pytest tests/ -q`: **BLOCKED** — `pytest-homeassistant-custom-component` requires Python >=3.12; not available in Python 3.11 audit environment.
- Import gate (`pydantic`, `pytest`, `pytest_asyncio`): **pass** (3.11 env).
- Import gate (`pytest_homeassistant_custom_component`, `homeassistant`): **BLOCKED** — Python 3.11 env only; passes on Python 3.12 CI.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed (runs as GitHub Action only; not a PyPI package).
- `HACS`: not executed (runs as GitHub Action only; not a PyPI package).

## Remaining hotspots (current queue)

1. Coordinator size/branching (`coordinator/coordinator.py` 699 lines, `coordinator/schedule.py` 468 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 694 lines, `scanner/core.py` 454 lines).
3. Mapping build complexity (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow/device validation complexity (`config_flow.py` 414 lines, `config_flow_device_validation.py`).
5. Ruff format drift: 3 files (`scanner/io_read_helpers.py`, `tests/test_config_flow_helpers.py`, `tests/test_modbus_helpers_call_flow.py`).

## Branch note

- Target branch for ongoing work and PR base is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended by this audit.

## Readiness caveats

- **HACS/hassfest readiness:** not claimable (not executed in this run; these run as GitHub Actions only).
- **Real-device readiness:** not claimable from this verification run; no new on-device evidence captured.
