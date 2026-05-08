# Refactor status (current)

Last reviewed: 2026-05-08 (final cleanup release PR — phases A–G, Python 3.13.12).

Related document: `docs/maintainability_audit.md`

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

## Current invariant snapshot

- Target branch for ongoing work: **dev**.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- Coordinator package API invariant: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- HA imports in `core/transport/registers/scanner`: **none detected**.
- Entity mapping invariant: **366 entities**.

## Latest merged refactor snapshot

Latest PR (this document): **final cleanup release — phases B–E + docs**.

Changes in this PR:

- **Phase B** (`scanner/io_read.py`): extracted `_handle_register_error_response` from `_process_register_response`; 4 new tests.
- **Phase C** (`coordinator/coordinator.py` + `_coordinator_init.py`): extracted `apply_coordinator_config`; `__init__` reduced 61→47 lines.
- **Phase D** (`mappings/_mapping_builders.py`): extracted `_route_holding_register_to_mapping` from `_extend_entity_mappings_from_registers`; latter reduced 83→59 lines.
- **Phase E** (`scanner/selection.py`): extracted `_split_groups_around_missing` from `group_registers_for_batch_read`; 6 new tests.

Current file-size snapshot:

| Area | Size (non-empty lines) |
|---|---:|
| `coordinator/coordinator.py` | 596 |
| `coordinator/schedule.py` | 367 |
| `scanner/io_read.py` | 713 |
| `scanner/selection.py` | 119 |
| `mappings/_mapping_builders.py` | 466 |
| `scanner/core.py` | 433 |

## Required gate status snapshot

Last complete successful validation (Python 3.13.12):

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **0 files drift**.
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python3.13 tools/check_maintainability.py`: **Maintainability gate passed**.
- `python3.13 tools/validate_entity_mappings.py`: **OK: 366 entities validated**.
- `python3.13 -m pytest tests/ -q`: **1948 passed, 4 skipped**.

## Remaining hotspots

1. `scanner/io_read.py` — `_run_word_read_retry_loop` (87 lines), `read_bit_registers` (64 lines).
2. `scanner/core.py` — `__init__` (68 lines), `create` (52 lines) — mostly long parameter lists.
3. `coordinator/coordinator.py` — `from_params` (54 lines) — long parameter list pass-through.
4. `coordinator/schedule.py` — `async_write_register` (49 lines), `_handle_write_attempt_exception` (45 lines).
5. Config-flow branching: `config_flow.py`.

## Recommended next work

1. Consider extracting `_handle_bit_attempt_exception` from `read_bit_registers` in `scanner/io_read.py`.
2. `coordinator/schedule.py` write-path complexity still has extraction candidates.
3. Keep each PR narrow: one production extraction plus focused tests and refreshed docs.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not available locally — CI runs it via GitHub Actions.
- `HACS`: not available locally — CI runs it via GitHub Actions.

## Branch note

- Target branch for ongoing work and PR base is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended by this status document.

## Readiness caveats

- **HACS/hassfest readiness:** not claimable from local verification; CI runs those gates.
- **Real-device readiness:** not claimable from these refactor validations unless separate on-device evidence is captured.
- **Release notes/tag:** not finalized.

## Dependabot note

- PR #1567 is still separate from this refactor stream.
- Pydantic remains pinned at 2.12.2; this document does not change dependency versions.
