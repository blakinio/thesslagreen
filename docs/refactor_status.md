# Refactor status (current)

Last reviewed: 2026-05-29 (post-PR #1686; CI/Python 3.13 validation update).

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

- Target branch for ongoing work: **main**.
- Top-level `custom_components/thessla_green_modbus/coordinator.py`: **absent**.
- Canonical coordinator module: `custom_components/thessla_green_modbus/coordinator/coordinator.py`.
- Coordinator package API invariant: `__all__ == ["CoordinatorConfig", "ThesslaGreenModbusCoordinator"]`.
- HA imports in `core/transport/registers/scanner`: **none detected**.
- Entity mapping invariant: **367 entities**.

## Latest PR snapshot

Latest merged PR: **#1686 — ci/docs: require Python 3.13 validation and finalize cleanup follow-up**.

Previous PRs in this stabilization cycle:
- **#1685** — docs/refactor: plan pymodbus 4 migration and reduce core complexity
- **#1684** — refactor: finish coordinator device-client IO ownership cleanup
- **#1683** — dangerous/advanced entities: entity_category=config (remain enabled)
- **#1682** — fan percentage fix: clamp to 100 per HA spec

Changes in #1686:

- Ruff import-order and format checks are now **blocking** in the lint CI job.
- `compare_airpack4_vendor_coverage.py`, `check_translations.py` added to lint job.
- `ruff-adoption-signal` job removed.
- `docs/development_validation.md` added with Python 3.13 environment setup instructions.

Current file-size snapshot:

| Area | Total lines | Non-empty lines |
|---|---:|---:|
| `coordinator/coordinator.py` | 675 | 596 |
| `coordinator/schedule.py` | 433 | 380 |
| `scanner/io_read.py` | 813 | 732 |
| `scanner/core.py` | 478 | 433 |
| `config_flow.py` | 467 | 387 |

## Required gate status snapshot

Last complete successful validation (Python 3.13, CI post-#1686):

- `ruff check custom_components tests tools`: **pass**.
- `ruff check --select I custom_components tests tools`: **pass**.
- `ruff format --check custom_components tests tools`: **0 files drift**.
- `python3.13 -m compileall -q custom_components/thessla_green_modbus tests tools`: **pass**.
- `python3.13 tools/check_maintainability.py`: **Maintainability gate passed**.
- `python3.13 tools/validate_entity_mappings.py`: **OK: 367 entities validated**.
- `python3.13 -m pytest tests/ -q`: **1948 passed, 4 skipped** (last known CI run).

## Remaining hotspots

1. `scanner/io_read.py` — `_run_word_read_single_attempt` (70 lines, new), `read_bit_registers` (64 lines).
2. `scanner/core.py` — `__init__` (68 lines), `create` (52 lines) — mostly long parameter lists.
3. `coordinator/coordinator.py` — `from_params` (54 lines) — long parameter list pass-through.
4. `coordinator/schedule.py` — `_handle_write_attempt_exception` (45 lines).
5. Config-flow branching: `config_flow.py` — all within limits.

## Non-required tool status

- `black`: not executed.
- `isort`: not executed.
- `mypy`: not executed.
- `hassfest`: not available locally — CI runs it via GitHub Actions.
- `HACS`: not available locally — CI runs it via GitHub Actions.

## Branch note

- Target branch for all ongoing work and PR bases is **main**.
- `main` is the authoritative branch for this integration.

## Readiness caveats

- **HACS/hassfest readiness:** CI validates these on every push; check the Actions tab for current status.
- **Real-device readiness:** no on-device evidence was captured during this audit run. The `quality_scale: bronze` in `manifest.json` reflects current validated state. A silver upgrade requires real-device evidence committed to `docs/real_device_validation.md`.
