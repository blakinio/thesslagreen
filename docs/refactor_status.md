# Refactor / Gate Status Snapshot

Date: 2026-05-05 (UTC)

## Overall state
- Required gates are **not green** in this verification run.
- This run was documentation-only; no production/test/CI files were changed.

## Gate outcomes (exact)
- `ruff check custom_components tests tools`: **FAIL** (21 issues).
- `ruff check --select I custom_components tests tools`: **FAIL** (1 issue).
- `ruff format --check custom_components tests tools`: **FAIL** (13 files drift).
- `python -m compileall -q custom_components/thessla_green_modbus tests tools`: **PASS**.
- `python tools/compare_registers_with_reference.py`: **PASS (exit 0; reports 62 extras, 242 name mismatches)**.
- `python tools/check_maintainability.py`: **PASS**.
- `pytest tests/ -q`: **FAIL** (58 failed, 1673 passed, 4 skipped).
- `python tools/validate_entity_mappings.py`: **PASS**.

## Key failure concentration
- Scanner capability flow regression (multiple suites failing with `NameError: DeviceCapabilities`).

## Invariants check summary
- Coordinator file locations confirmed by `find` command.
- No direct `homeassistant` imports detected in targeted core/transport/registers/scanner directories.
- Compat/shim/legacy text still present mostly in docs/tests and selected compatibility helpers.

## Non-required quality tool execution
- black: not run
- isort: not run
- mypy: not run
- hassfest: not run
- HACS validation: not run

## Readiness caveats
- **Cannot claim maintained-gate green state** on this snapshot.
- **Cannot claim HACS readiness** (validator not run).
- **Cannot claim real-device validation** (no device-backed evidence in this run).

## Next recommended PRs
1. Scanner gate-recovery PR for `DeviceCapabilities` regression.
2. Ruff/lint/format gate-recovery PR.
3. Optional register-name reconciliation PR for compare-script mismatches.
