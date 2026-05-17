# Final Cleanup Before Device Validation — Report

**Branch:** `claude/fix-ruff-coordinator-cleanup-vhKlw`
**Date:** 2026-05-17
**Base branch:** `main`

---

## Summary

This report documents the safe cleanup completed before real-device validation.
No Modbus behavior was changed. Entity IDs, unique IDs, service IDs, register names,
register addresses, config/options flow behavior, and translation keys are unchanged.

---

## Phase 1 — Ruff Formatting Fix

**Status: ALREADY FIXED (prior PR #1655)**

`ruff format --check custom_components tests tools` reports:
```
433 files already formatted
```

`ruff check` and `ruff check --select I` both report `All checks passed!`.

The `core/models.py` formatting fix was applied in the prior merge
(`style: format coordinator config model`, commit `88eb1ba`).

---

## Phase 2 — Coordinator Disconnect Re-export

**Decision: REMOVED**

**Before:**
```python
# coordinator/__init__.py
from ..core import disconnect as disconnect  # intentionally not in __all__
```

**After:** The re-export line was removed. The coordinator package now exports only:
- `CoordinatorConfig`
- `ThesslaGreenModbusCoordinator`

**Test update:** `tests/test_coordinator_disconnect.py` was updated to import
`disconnect` from the canonical location:
```python
# Before
from custom_components.thessla_green_modbus.coordinator import disconnect
# After
from custom_components.thessla_green_modbus.core import disconnect
```

**Justification:** Only one test file imported `disconnect` via the coordinator.
The canonical location is `custom_components.thessla_green_modbus.core.disconnect`.
The re-export was not in `__all__` and served no runtime purpose; it was a leftover
from an intermediate refactor state.

`test_api_contracts.py::test_coordinator_package_public_api_is_minimal` verifies
`coordinator.__all__ == {"CoordinatorConfig", "ThesslaGreenModbusCoordinator"}` — this
test is now consistent with the actual exported names.

---

## Phase 3 — Coordinator Proxy Audit

**Decision: ALL PROXIES RETAINED — no safe removals identified**

`coordinator/coordinator.py` contains **43 proxy properties** (lines 177–512)
delegating to `self._device_client`. All were audited for usage across
`custom_components/`, `tests/`, and `tools/`.

**Classification result:**

| Category | Count | Status |
|----------|-------|--------|
| runtime-required | 25 | Retained — used by coordinator submodules |
| entity-required | 6 | Retained — accessed by HA platform entity classes |
| test-required | 43 | Retained — all proxies are also accessed in tests |
| obsolete/unused | 0 | None found |

No proxy properties were removed. The full audit and future migration path are
documented in `docs/coordinator_proxy_remaining_plan.md`.

**Reasoning for full deferral:**
- All 43 proxies have active callers in either production code or tests (usually both).
- A partial removal would create asymmetry that complicates debugging during device validation.
- The safe migration path (one submodule at a time, with test verification) should be
  followed after real-device validation confirms stable runtime behavior.

---

## Phase 4 — const.py Domain-Map Audit

**Decision: ALL THREE DEFERRED — no moves performed**

The three domain-specific structures in `const.py` were audited:

| Constant | Callers (production) | Callers (tests) | Decision |
|----------|----------------------|-----------------|----------|
| `SPECIAL_FUNCTION_MAP` | 3 files (`climate.py`, `services/__init__.py`, `mappings/_loaders.py`) | 4+ test files | **Deferred** |
| `KNOWN_MISSING_REGISTERS` | 5 files (coordinator, scanner) | 4+ test files | **Deferred** |
| `SENSOR_UNAVAILABLE_REGISTERS` | 2 files (`scanner/capabilities.py`, `core/register_processing.py`) | 2 test files | **Deferred** |

**Reasoning for deferral:**
- Moving any of these would require updating 7–14 import statements across production and
  test code — a non-trivial diff with meaningful risk of a missed import.
- `SPECIAL_FUNCTION_MAP` is also imported via `climate.py` in some tests
  (`from custom_components.thessla_green_modbus.climate import SPECIAL_FUNCTION_MAP`),
  meaning a move would require additional test updates to avoid a cascading rename.
- None of the moves would change runtime behavior; the risk-to-benefit ratio is unfavorable
  before hardware validation.
- The values themselves are not changed.

**Recommended future action:** Move `SENSOR_UNAVAILABLE_REGISTERS` first (fewest callers),
then `SPECIAL_FUNCTION_MAP`, then `KNOWN_MISSING_REGISTERS` — one at a time, after
device validation.

---

## Phase 5 — Real-Device Validation Documentation

**Status: TEMPLATE UPDATED — validation NOT YET COMPLETED**

`docs/real_device_validation.md` was updated with:

1. Status header changed from "TEMPLATE ONLY" to **"NOT YET COMPLETED"** (clearer wording).

2. **New test sections added:**
   - §4.11 Options Flow Update
   - §4.12 Special Modes (Boost / Eco / Away / Others)
   - §4.13 Clock Sync
   - §4.14 Diagnostics
   - §4.15 Service Calls
   - §4.16 Log Review (No Traceback) — replaces old §4.11

3. **New evidence fields added:**
   - Connection type (TCP / RTU / TCP_RTU)
   - Slave ID
   - Integration version / commit SHA
   - Debug log excerpt
   - Known limitations

The document explicitly states validation has not been completed.
The release gate (§7) was updated to reference test cases 4.1–4.16.

---

## Phase 6 — Stale-Path Audit

**Status: CLEAN — no active stale imports**

Search for removed module import paths:

| Pattern | Active imports found |
|---------|---------------------|
| `modbus_helpers` | None in production/tests (only in docs as historical notes) |
| `modbus_transport` | None as imports (test file names only) |
| `modbus_exceptions` | None as imports (used as dict key `"modbus_exceptions"`, not import path) |
| `scanner.const`, `scanner.utils` | None |
| `transport.error_contract` | None |
| `config_flow_runtime`, `config_flow_validation`, `config_flow_options_form` | None in active code (docs only) |
| `coordinator.io` | None |
| `coordinator.capabilities` (as import path) | None (used as attribute access `coordinator.capabilities`, which is correct) |

Search for leftover markers:

| Pattern | Found |
|---------|-------|
| `Compatibility shim` | Docs only (historical cleanup records) |
| `Compatibility re-exports` | Docs only |
| `legacy re-export` | None |
| `deprecated import path` | None |
| `TODO` | `tools/translate_register_descriptions.py` only (tool-generated marker, not production code) |
| `FIXME` | None in production or test code |

---

## Phase 7 — Validation Results

| Check | Result |
|-------|--------|
| `python -m compileall -q custom_components tests tools` | PASS |
| `ruff check custom_components tests tools` | PASS |
| `ruff check --select I custom_components tests tools` | PASS |
| `ruff format --check custom_components tests tools` | PASS (433 files) |
| `pytest` collection | CANNOT RUN — environment is Python 3.11; test suite requires Python 3.13 (`pytest-homeassistant-custom-component>=0.13.309` requires `>=3.13`) |
| `tools/compare_registers_with_reference.py` | Completed (62 extras, 0 missing — pre-existing baseline) |
| `tools/check_maintainability.py` | PASS — maintainability gate passed |
| `tools/validate_entity_mappings.py` | PASS — 366 entities validated |
| `tools/check_translations.py` | PASS — all translation keys present |

**pytest environment note:** The test suite requires `pytest-homeassistant-custom-component>=0.13.309`
which requires Python 3.13. The remote execution environment provides Python 3.11. This is a
pre-existing environment constraint; tests are expected to pass in CI where Python 3.13 is used.

---

## Phase 8 — Safety Checks

| Check | Result |
|-------|--------|
| Merge conflict markers | None (docs mention the pattern as search text, not actual markers) |
| `git diff --check` | PASS — no whitespace errors |
| Changed files | 4 files (see below) |

**Changed files:**
1. `custom_components/thessla_green_modbus/coordinator/__init__.py` — removed disconnect re-export
2. `tests/test_coordinator_disconnect.py` — updated import to canonical `core` module
3. `docs/coordinator_proxy_remaining_plan.md` — updated with current audit results
4. `docs/real_device_validation.md` — added missing test sections and evidence fields

---

## Remaining Debt

| Item | Status | Recommended Action |
|------|--------|--------------------|
| Coordinator proxy properties (43) | Deferred | Remove one submodule at a time after real-device validation |
| `SPECIAL_FUNCTION_MAP` in const.py | Deferred | Move to `services/special_functions.py` or `mappings/special_modes.py` after validation |
| `KNOWN_MISSING_REGISTERS` in const.py | Deferred | Move to `registers/missing.py` after validation |
| `SENSOR_UNAVAILABLE_REGISTERS` in const.py | Deferred (lowest risk) | Move to `registers/sentinels.py` after validation |
| pytest in this environment | Environment limit | Runs in CI on Python 3.13 |

---

## Recommended Next Step

**Real-device validation on physical ThesslaGreen AirPack hardware.**

Follow `docs/real_device_validation.md` test cases 4.1–4.16.
Record results in the Evidence Record section.
Only after all test cases are marked Pass should the release gate (§7) be considered satisfied.
