# Refactor status (current)

Last reviewed: 2026-05-08 (Python 3.13 full-pass + coordinator io mixin + UART select extraction).

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

## Current invariant verification snapshot (2026-05-08 Phase B+C refresh)

- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- HA imports in `core/transport/registers/scanner`: **none detected** by grep.
- Compatibility grep (`compat|shim|proxy|re-export|legacy`): informational matches present in docs/tests/comments/known compatibility code references.

## Notable since previous snapshot (2026-05-08 modbus_helpers._encode_read_frame run)

- Full test suite validated on Python 3.13 — **1900 passed, 4 skipped**.
- Ruff format drift: **0 files** ✅.
- **PHASE B**: `_read_coils_transport` and `_read_discrete_inputs_transport` moved from
  `coordinator/coordinator.py` into `_ModbusIOMixin` in `coordinator/io.py`.
  `coordinator.py` reduced 699 → 666 non-empty lines; `ThesslaGreenModbusCoordinator` 611 → 577 AST lines.
- **PHASE C**: 6 UART/serial-port select entries extracted from `_static_discrete.py` into new
  `_static_discrete_uart.py`. `SELECT_ENTITY_MAPPINGS` now composed via `{..., **UART_SELECT_ENTITY_MAPPINGS}`.
  `_static_discrete.py` reduced 417 → ~363 non-empty lines. Entity count unchanged: 366.

## Required gate status snapshot (2026-05-08 Phase B+C run)

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **0 files drift** ✅.
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python3.13 tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches).
- `python3.13 tools/check_maintainability.py`: **pass** (`Maintainability gate passed.`).
- `python3.13 tools/validate_entity_mappings.py`: **pass** (`OK: 366 entities validated`).
- `python3.13 -m pytest tests/ -q`: **pass** — 1900 passed, 4 skipped, 84 warnings.
- Import gate (all 5 modules): **pass** on Python 3.13.
- Coordinator split check: **277 passed**, 1 warning.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed (runs as GitHub Action only; not a PyPI package).
- `HACS`: not executed (runs as GitHub Action only; not a PyPI package).

## Remaining hotspots (current queue)

1. Coordinator size/branching (`coordinator/coordinator.py` 666 lines, `coordinator/schedule.py` 468 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 454 lines).
3. Mapping build complexity (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 414 lines).
5. Ruff format drift: 0 files ✅.

## Branch note

- Target branch for ongoing work and PR base is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended by this audit.

## Readiness caveats

- **HACS/hassfest readiness:** not claimable (not executed in this run; these run as GitHub Actions only).
- **Real-device readiness:** not claimable from this verification run; no new on-device evidence captured.

## Dependabot note

- PR #1567 was **not touched** in this session.
- Pydantic version was **not changed** (installed: 2.12.2).
