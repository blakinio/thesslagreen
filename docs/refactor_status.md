# Refactor status (current)

Last reviewed: 2026-05-08 (Python 3.13 full-pass + config_flow bound-adapter extraction + coordinator test split).

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

## Notable since previous snapshot (2026-05-08 config_flow + coordinator test cleanup)

- Full test suite validated on Python 3.13 — **1913 passed, 4 skipped** (+13 vs previous run).
- Ruff format drift: **0 files** (415 files).
- **PHASE B**: Three adapter functions removed from `config_flow.py`; replaced by `validate_tcp_config_bound`, `validate_rtu_config_bound`, `process_scan_capabilities_bound` in `config_flow_validation.py`. `config_flow.py` 414 → 394 non-empty lines. 13 new focused tests in `tests/test_config_flow_validation_bound.py`.
- **PHASE C**: `TestParseBackoffJitter` (5 test methods) moved from `test_coordinator.py` to `tests/test_coordinator_parse_backoff.py`. `test_coordinator.py` 440 → 412 non-empty lines; total coordinator test count unchanged at 277.

## Required gate status snapshot (2026-05-08 Python 3.13 run)

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **0 files drift** ✅.
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python3.13 tools/compare_registers_with_reference.py`: **pass** (informational: 62 extras, 242 name mismatches).
- `python3.13 tools/check_maintainability.py`: **pass** (`Maintainability gate passed.`).
- `python3.13 tools/validate_entity_mappings.py`: **pass** (`OK: 366 entities validated`).
- `python3.13 -m pytest tests/ -q`: **pass** — 1913 passed, 4 skipped, 84 warnings.
- Import gate (all 5 modules): **pass** on Python 3.13.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed (runs as GitHub Action only; not a PyPI package).
- `HACS`: not executed (runs as GitHub Action only; not a PyPI package).

## Remaining hotspots (current queue)

1. Coordinator size/branching (`coordinator/coordinator.py` 699 lines, `coordinator/schedule.py` 468 lines).
2. Scanner read/orchestration complexity (`scanner/io_read.py` 714 lines, `scanner/core.py` 454 lines).
3. Mapping build complexity (`mappings/_mapping_builders.py` 437 lines).
4. Config-flow branching (`config_flow.py` 394 lines; reduced from 414).
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
- Pydantic version was **not changed**. `requirements-dev.txt` still pins `pydantic==2.12.2`.
