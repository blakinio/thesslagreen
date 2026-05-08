# Refactor status (current)

Last reviewed: 2026-05-08 (post-PR #1595 documentation cleanup).

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
- HA imports in `core/transport/registers/scanner`: **none detected** in the last validation pass.
- Entity mapping invariant: **366 entities** in the last successful validation pass.

## Latest merged refactor snapshot

Latest merged PR: **#1595 — Extract coordinator config properties & refactor schedule write logic**.

Merged changes:

- `_CoordinatorConfigPropertiesMixin` extracted to `coordinator/config_properties.py`.
- Nine config-backed property pairs moved out of `ThesslaGreenModbusCoordinator`.
- Scanner failure logging helpers promoted to `scanner/io_read_helpers.py`.
- `_write_holding_multi` in `coordinator/schedule.py` now delegates to `_write_registers_payload` per chunk.

Current post-PR #1595 file-size snapshot from that PR:

| Area | Current size |
|---|---:|
| `coordinator/coordinator.py` | 605 non-empty lines |
| `coordinator/schedule.py` | 401 non-empty lines |
| `scanner/io_read.py` | 701 non-empty lines |

## Required gate status snapshot

Last complete successful validation from PR #1595:

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **0 files drift**.
- `python3.12 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python3.12 tools/check_maintainability.py`: **pass**.
- `python3.12 tools/validate_entity_mappings.py`: **pass** — **366 entities**.
- `python3.12 -m pytest tests/ -q`: **1938 passed, 4 skipped**.

Earlier Python 3.13 validation from the 2026-05-08 cleanup/config-flow series remains useful historical context, but the latest full post-#1595 test evidence is the Python 3.12 pass above.

## Remaining hotspots

1. Coordinator size/branching: `coordinator/coordinator.py` and `coordinator/schedule.py`.
2. Scanner read/orchestration complexity: `scanner/io_read.py` and `scanner/core.py`.
3. Mapping builder density: `mappings/_mapping_builders.py`.
4. Config-flow branching: `config_flow.py`.
5. Large test modules, where focused splits remain possible.

## Recommended next work

1. Continue with a focused extraction in `scanner/io_read.py` or `scanner/core.py`.
2. Alternatively reduce `mappings/_mapping_builders.py` if a cohesive helper extraction is visible.
3. Keep each PR narrow: one production extraction plus focused tests and refreshed docs.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not executed locally.
- `HACS`: not executed locally.

## Branch note

- Target branch for ongoing work and PR base is **dev**.
- `main` is not authoritative for this stream.
- No `main -> dev` merge is recommended by this status document.

## Readiness caveats

- **HACS/hassfest readiness:** not claimable from local verification unless CI explicitly runs those actions.
- **Real-device readiness:** not claimable from these refactor validations unless separate on-device evidence is captured.

## Dependabot note

- PR #1567 is still separate from this refactor stream.
- Pydantic remains pinned in the project; this document does not change dependency versions.
