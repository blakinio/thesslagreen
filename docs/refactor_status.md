# Refactor status (current)

Last reviewed: 2026-05-05.

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

## Current invariant verification snapshot (2026-05-05)

- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- HA imports in `core/transport/registers/scanner`: **none detected** by grep.
- Compatibility grep (`compat|shim|proxy|re-export|legacy`): informational matches present in docs/tests/comments/known compatibility code references.

## Required gate status snapshot (2026-05-05)

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches).
- `python tools/check_maintainability.py`: **pass**.
- `python tools/validate_entity_mappings.py`: **pass**.
- `pytest tests/ -q`: **pass** (with 4 skips).

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed.
- `HACS`: not executed.
- `ruff format --check`: **1 file drift** (`custom_components/thessla_green_modbus/mappings/_mapping_builders.py`).

## Remaining hotspots (current queue)

1. Coordinator size/branching (`coordinator/coordinator.py`, `coordinator/schedule.py`).
2. Scanner read/orchestration complexity (`scanner/io_read.py`, `scanner/core.py`).
3. Mapping build complexity (`mappings/_mapping_builders.py`).
4. Config-flow/device validation complexity (`config_flow.py`, `config_flow_device_validation.py`).

## Branch authority note

- Base branch for this audit work is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended.

## Readiness caveats

- **Release/HACS readiness:** not claimable (HACS/hassfest not executed in this run).
- **Real-device readiness:** not claimable from this verification run; no new on-device evidence captured.
