# Refactor status (current)

Last reviewed: 2026-05-08.

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

## Current invariant verification snapshot (2026-05-08)

- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- HA imports in `core/transport/registers/scanner`: **none detected** by grep.
- Compatibility grep (`compat|shim|proxy|re-export|legacy`): informational matches present in docs/tests/comments/known compatibility code references.

## Notable since previous snapshot (2026-05-05)

- `coordinator/scan.py` added — focused scan sub-module extracted from coordinator.
- `tests/helpers_coordinator.py` added — shared coordinator fixture (46 lines);
  loaded as plugin via `tests/conftest.py` (`pytest_plugins`).
- `tests/test_coordinator_error_paths_split.py` added — split test file using shared fixture.
- `tests/test_coordinator.py` simplified — fixture moved to `helpers_coordinator.py`
  (shrank from 502 → 440 non-empty lines).

## Required gate status snapshot (2026-05-08)

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **7 files drift**
  (coordinator.py, scan.py, schedule.py, scanner/orchestration.py,
  test_config_flow_helpers.py, test_modbus_helpers_call_flow.py, test_text.py).
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches).
- `python tools/check_maintainability.py`: **pass**.
- `python tools/validate_entity_mappings.py`: **BLOCKED** — requires `homeassistant` (Python >=3.12); code is syntactically valid.
- `pytest tests/ -q`: **BLOCKED** — `pytest-homeassistant-custom-component` requires Python >=3.12; not available in Python 3.11 audit environment.
- `pytest -q tests/test_coordinator_error_paths_split.py tests/test_coordinator.py tests/test_coordinator_*.py`: **BLOCKED** — same reason; shared fixture and split test files are present and syntactically correct.
- Import gate (`pydantic`, `pytest`, `pytest_asyncio`): **pass** (3.11 env).
- Import gate (`pytest_homeassistant_custom_component`, `homeassistant`): **BLOCKED** — Python 3.11 env only; passes on Python 3.12 CI.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed.
- `HACS`: not executed.

## Remaining hotspots (current queue)

1. Coordinator size/branching (`coordinator/coordinator.py` 697 lines, `coordinator/schedule.py` 468 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 704 lines, `scanner/core.py` 454 lines).
3. Mapping build complexity (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow/device validation complexity (`config_flow.py` 428 lines, `config_flow_device_validation.py`).

## Branch note

- Target branch for ongoing work and PR base is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended by this audit.

## Readiness caveats

- **HACS/hassfest readiness:** not claimable (not executed in this run).
- **Real-device readiness:** not claimable from this verification run; no new on-device evidence captured.
