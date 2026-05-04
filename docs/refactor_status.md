# Refactor status (current)

Last reviewed: 2026-05-04.

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

## Current invariant verification snapshot (2026-05-04)

- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- HA imports in `core/transport/registers/scanner`: **none detected**.
- Entity mapping validation: **passes** (`OK: 366 entities validated`).
- Maintainability gate: **passes**.
- Full test suite (`pytest tests/ -q`): **fails** (69 failed, 1801 passed, 4 skipped).
- Lint gate (`ruff check custom_components tests tools`): **fails** (`F811` + `F821` in `services_handlers_maintenance.py`).

## Latest cleanup-batch outcome

- This audit run did **not** confirm a fully green post-cleanup state.
- Regressions are currently concentrated in maintenance service registration (`register_maintenance_services` duplication / missing symbol), causing both lint and test failures.
- Maintainability and entity-mapping checks remain green.

## Remaining hotspots (next PR queue)

1. **Gate-recovery first:** fix maintenance service registration regression so required CI gates are green again.
2. Coordinator decomposition (`coordinator/coordinator.py`, `coordinator/schedule.py`).
3. Scanner read-path decomposition (`scanner/io_read.py`, `scanner/core.py`).
4. Mapping builder decomposition (`mappings/_mapping_builders.py`).
5. Config-flow validation branch extraction (`config_flow_device_validation.py`).
6. Large test module splits after gate recovery (`tests/test_coordinator.py`, scanner/config-flow suites).

## CI hardening status

- Required now: `ruff check`, compileall, register-reference compare, maintainability check, pytest+coverage, entity mappings validation.
- Current state in this audit: `compileall`, register compare, maintainability, entity mappings are green; `ruff check` and `pytest` are red.
- Informational/non-required now: `ruff check --select I` (not re-run after lint failure), `ruff format --check` (drift not refreshed in this run; last known 108 files).
- Not currently required: `black`, `isort`, `mypy`, `hassfest`, HACS validation.

## Documentation policy for refactor work

- Keep architecture docs aligned with current repository state.
- Do not document speculative capabilities as completed.
- Keep readiness claims split across:
  1. maintainability/refactor readiness,
  2. CI readiness,
  3. release/HACS readiness,
  4. real device validation evidence.
