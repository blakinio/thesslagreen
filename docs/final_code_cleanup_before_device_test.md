# Final Code Cleanup Before Device Validation

Branch: `claude/cleanup-coordinator-proxy-Dns7J`  
Date: 2026-05-17  
Base branch: `main` (origin/main @ `f7b66c6`)

---

## Summary

This PR performs the last code-only cleanup batch before physical real-device testing.
It covers three areas: coordinator proxy migration, mutable global state cleanup, and
test fixture consolidation.  No Modbus behavior changed.  No entity IDs, unique IDs,
service IDs, register names, register addresses, translation keys, or config/options
flow behavior changed.

---

## Baseline Import Bug Fixes

Three import bugs were introduced by the previous cleanup PR (commit `451bae6`, merged
as PR #1642) which removed re-exports from `const.py` without updating all callers.
These were fixed as a baseline repair before any refactoring:

| File | Bug | Fix |
|---|---|---|
| `mappings/_mapping_builders.py` | `from ..const import coil_registers, discrete_input_registers, holding_registers` → ImportError | Changed to `from ..registers.maps import ...` |
| `coordinator/coordinator.py` | `from ..const import input_registers` → ImportError | Changed to `from ..registers.maps import input_registers` |
| `coordinator/state.py` | `from ..const import coil_registers, discrete_input_registers, holding_registers, input_registers` → ImportError | Changed to `from ..registers.maps import ...` |

---

## Phase 1-2 — Coordinator Proxy Migration

### Inventory

All ~40 proxy properties in `ThesslaGreenModbusCoordinator` are classified as
**runtime-required** — they are accessed by coordinator submodule functions via
duck-typing, by entity platform files, and by tests.  No proxy has zero callers.
See `docs/coordinator_proxy_migration_inventory.md` for the full table.

### Changes Made

**Added public `device_client` property** to `coordinator/coordinator.py`:

```python
@property
def device_client(self) -> ThesslaGreenDeviceClient:
    """Return the underlying DeviceClient instance."""
    return self._device_client
```

This exposes the underlying `ThesslaGreenDeviceClient` via a stable public API,
allowing tests to access it without using the private `_device_client` attribute.

**Migrated `tests/test_device_client.py`**: All test assertions that accessed
`coord._device_client` directly were updated to use `coord.device_client`.
This is a pure mechanical migration — same behavior, cleaner API.

### Proxies Retained

All proxy properties are retained with the documented rationale in `coordinator.py`.
The block comment explains:

> Coordinator submodules (runtime_io, read_batches, read_bits, register_groups,
> scan_result, state, etc.) receive `self` (the coordinator) as their duck-typed
> owner and access these attributes directly.

Future removal path: when a submodule is updated to accept a `DeviceClient` instead
of the coordinator, the corresponding proxy can be removed at that point.

---

## Phase 3-4 — Mutable Global State Cleanup

See `docs/mutable_global_state_inventory.md` for the full inventory.

### Changed

**`_setup._platform_cache`** — replaced manual sentinel + `global` keyword with
`@functools.lru_cache(maxsize=1)` on `_get_platforms`:

- Removed: `_platform_cache: list[Any] | None = None`
- Removed: `global _platform_cache` + manual cache guard
- Added: `@functools.lru_cache(maxsize=1)` decorator on `_get_platforms`
- Updated: call site converts `list[str]` to `tuple` before passing
- Updated: `__init__.py` shim updated to call `_get_platforms(tuple(PLATFORM_DOMAINS))`

### Retained (Documented)

| Global | Reason retained |
|---|---|
| `entity_lookup._ENTITY_LOOKUP` | Tests monkeypatch `_ENTITY_LOOKUP` to `None`/fake dict; converting to `functools.cache` would break them |
| `mappings._helpers._REGISTER_INFO_CACHE` | Tests monkeypatch `em._REGISTER_INFO_CACHE`; the parent-module lookup pattern is essential for test compatibility |
| `scanner.register_maps.*` + `REGISTER_HASH` | Correct architecture — hash-validated, invalidation-aware; already consolidated as single source of truth in PR #1642 |
| `options.*` lists + `_OPTIONS_INIT_LOCK` | Populated during HA setup from JSON files; DI rewrite would affect config/options flow behavior — out of scope |

---

## Phase 5-6 — Test Fixture Consolidation

See `docs/test_fixture_consolidation_inventory.md` for the full inventory.

### Inventoried

- ~20 test files call `ThesslaGreenModbusCoordinator.from_params` with near-identical parameters
- `tests/helpers_coordinator.py` already has a shared `coordinator` fixture and `_make_config_entry`
- `tests/helpers_modbus.py` is empty

### Changed

**`tests/test_device_client.py`**: Migrated all `coord._device_client` to
`coord.device_client` (12 sites) — consistent with the new public property.

### Deferred

Centralizing the `_make_coordinator` / `from_params` pattern across 20+ test files
has a high blast radius and risk of silently changing test defaults.  This is deferred
to a dedicated fixture-cleanup PR.  `helpers_modbus.py` remains empty — adding wrong
defaults would silently break tests.

---

## Validation Results

| Check | Result |
|---|---|
| `python -m compileall -q` | PASS |
| `ruff check` | PASS |
| `ruff check --select I` (import order) | PASS |
| `ruff format --check` | PASS |
| `tools/validate_entity_mappings.py` | PASS — 366 entities validated |
| `tools/check_maintainability.py` | PASS — gate passed |
| `tools/check_translations.py` | PASS — all translation keys present |
| `tools/compare_registers_with_reference.py` | PASS (expected delta — extra registers are device extensions) |
| `git diff --check` | PASS — no whitespace issues |
| Merge conflict markers | PASS — none found |
| Forbidden patterns (shims, removed modules) | PASS — none found |

### Pytest Status

**NOT RUN** — Python 3.11 environment; package requires Python ≥3.13
(`pytest-homeassistant-custom-component<0.13.317,>=0.13.309` requires Python ≥3.12).
All changed files pass `compileall` (syntax-correct) and `ruff` (lint-clean).

---

## Files Changed

| File | Change |
|---|---|
| `custom_components/thessla_green_modbus/__init__.py` | Updated `_get_platforms` call to pass `tuple` |
| `custom_components/thessla_green_modbus/_setup.py` | Replaced `_platform_cache` global with `@functools.lru_cache` |
| `custom_components/thessla_green_modbus/coordinator/coordinator.py` | Fixed `input_registers` import; added `device_client` property |
| `custom_components/thessla_green_modbus/coordinator/state.py` | Fixed register map imports (from `..registers.maps`) |
| `custom_components/thessla_green_modbus/mappings/_mapping_builders.py` | Fixed register map imports (from `..registers.maps`) |
| `tests/test_device_client.py` | Migrated `coord._device_client` → `coord.device_client` (12 sites) |
| `docs/coordinator_proxy_migration_inventory.md` | New — proxy classification |
| `docs/mutable_global_state_inventory.md` | New — global state classification |
| `docs/test_fixture_consolidation_inventory.md` | New — fixture duplication map |
| `docs/final_code_cleanup_before_device_test.md` | New — this report |

---

## Confirmations

- No Modbus behavior changed.
- Entity IDs: **unchanged** — no entity.py modifications.
- Unique IDs: **unchanged** — no unique_id_migration changes.
- Service IDs: **unchanged** — no services changes.
- Register names: **unchanged**.
- Register addresses: **unchanged**.
- Translation keys: **unchanged** — verified by `check_translations.py`.
- Config/options flow behavior: **unchanged** — `_config_flow/` and `options/` not touched.
- No compatibility shims created.
- No removed shims reintroduced.
- No test coverage weakened.

---

## Remaining Technical Debt

| Item | Status | Recommended Action |
|---|---|---|
| Coordinator proxy removal | Deferred | Migrate submodules to accept `DeviceClient` directly, then remove proxies one by one |
| `entity_lookup._ENTITY_LOOKUP` → `functools.cache` | Deferred | Update test monkeypatching sites + add `cache_clear()` |
| `mappings._helpers._REGISTER_INFO_CACHE` → `functools.cache` | Deferred | Requires test infrastructure refactor |
| `options.*` DI rewrite | Deferred | Requires coordinator redesign |
| Test fixture centralization (`helpers_modbus.py`) | Deferred | Design shared helpers carefully to avoid changing test semantics |
| Centralize `from_params` calls in 20+ test files | Deferred | Safe but large scope — dedicated fixture PR |

---

## Recommended Next Step

**Physical real-device validation** — connect an AirPack4 unit, run the integration
under Home Assistant, and verify:

1. All entities load correctly (sensor, binary_sensor, climate, fan, select, number, switch, text, time, button)
2. Register reads work (FC03, FC04) within batch limits
3. Register writes work (services: set_mode, set_fan_speed, etc.)
4. Device scan completes and capabilities are detected
5. Schedule read/write round-trips correctly
6. Clock sync (if enabled) works
7. No repeated Modbus exceptions in the HA log

See `docs/real_device_validation.md` for the full test protocol.
