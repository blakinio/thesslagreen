# Mutable Global State Inventory

Generated: 2026-05-17  
Branch: `claude/cleanup-coordinator-proxy-Dns7J`

---

## Overview

Six modules contain module-level mutable global state.  This document classifies
each variable, assesses cleanup risk, and records the action taken or deferred.

---

## 1. `_setup._platform_cache` → **CLEANED**

| Field | Value |
|---|---|
| Owner | `custom_components/thessla_green_modbus/_setup.py` |
| Old pattern | `_platform_cache: list[Any] \| None = None` + `global _platform_cache` |
| New pattern | `@functools.lru_cache(maxsize=1)` on `_get_platforms` |
| Type | Read-only lazy cache |
| Test references | None — `_platform_cache` never patched by tests |
| Risk | Low |

**Change:** Removed the `_platform_cache` sentinel, `global _platform_cache` guard, and
the manual if-check.  Replaced with `@functools.lru_cache(maxsize=1)` directly on
`_get_platforms`.  The call site in `async_setup_platforms` converts the `list[str]`
argument to `tuple` before calling (lru_cache requires hashable args).  The companion
`_get_platforms()` shim in `__init__.py` was updated to call with `tuple(PLATFORM_DOMAINS)`.

---

## 2. `entity_lookup._ENTITY_LOOKUP` → **RETAINED (test-monkeypatched)**

| Field | Value |
|---|---|
| Owner | `custom_components/thessla_green_modbus/entity_lookup.py` |
| Pattern | `_ENTITY_LOOKUP: dict \| None = None` + `global _ENTITY_LOOKUP` |
| Type | Read-only lazy cache |
| Test references | `monkeypatch.setattr(lookup_mod, "_ENTITY_LOOKUP", ...)` in 2 tests |
| Risk | Medium — tests patch the sentinel to `None` (force rebuild) or a fake dict |

**Decision: Retain as-is.**  Converting to `functools.cache` would break tests that
`monkeypatch.setattr(lookup_mod, "_ENTITY_LOOKUP", None)` to force a cache rebuild,
since `functools.cache` stores state on the function object rather than a module
attribute.  A `functools.cache` + explicit `cache_clear()` helper would work but
requires updating all monkeypatching test sites.  Deferred to a future PR focused
on test infrastructure.

---

## 3. `mappings._helpers._REGISTER_INFO_CACHE` → **RETAINED (test-monkeypatched)**

| Field | Value |
|---|---|
| Owner | `custom_components/thessla_green_modbus/mappings/_helpers.py` |
| Pattern | `_REGISTER_INFO_CACHE: dict \| None = None` + `global _REGISTER_INFO_CACHE` |
| Type | Read-only lazy cache with parent-module lookup |
| Test references | `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", ...)` in 10+ tests |
| Risk | High — tests patch the attribute on the module object directly |

**Decision: Retain as-is.**  The cache has a sophisticated parent-module lookup
(`sys.modules.get(__package__)`) so that `monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", …)`
in tests also affects the cache seen by `_get_register_info()`.  Converting to
`functools.cache` would break this pattern entirely.  Leave documented for future
DI or test-infrastructure refactor.

---

## 4. `scanner.register_maps.*` → **RETAINED (correct architecture)**

| Field | Value |
|---|---|
| Owner | `custom_components/thessla_green_modbus/scanner/register_maps.py` |
| Variables | `REGISTER_DEFINITIONS`, `INPUT_REGISTERS`, `HOLDING_REGISTERS`, `COIL_REGISTERS`, `DISCRETE_INPUT_REGISTERS`, `MULTI_REGISTER_SIZES`, `REGISTER_HASH` |
| Type | Hash-validated, invalidation-aware register map cache |
| Risk | Low — already consolidated in previous PR (PR #1642) |

**Decision: Retain as-is.**  This module is the single source of truth for register
maps in the scanner subsystem.  The hash-based invalidation (`REGISTER_HASH`) is
intentional behavior required for detecting register file changes at runtime.
`REGISTER_DEFINITIONS` clears and repopulates atomically when the hash changes.
This pattern is correct and well-tested.

---

## 5. `options._OPTIONS_INIT_LOCK` and option lists → **RETAINED (HA lifecycle)**

| Field | Value |
|---|---|
| Owner | `custom_components/thessla_green_modbus/options/__init__.py` |
| Variables | `_OPTIONS_INIT_LOCK`, `SPECIAL_MODE_OPTIONS`, `DAYS_OF_WEEK`, `PERIODS`, `BYPASS_MODES`, `GWC_MODES`, `FILTER_TYPES`, `RESET_TYPES`, `MODBUS_PORTS`, `MODBUS_BAUD_RATES`, `MODBUS_PARITY`, `MODBUS_STOP_BITS` |
| Type | Mutable lists populated during HA setup, then effectively read-only |
| Risk | High — changing would affect config/options flow behavior |

**Decision: Retain as-is.**  These lists are loaded from JSON option files
(`special_modes.json`, `days_of_week.json`, etc.) during HA startup via
`async_setup_options(hass)`.  A full DI rewrite would require threading the
loaded data through the options-flow and service-schema call paths.  This is
out of scope for a pre-device-test cleanup PR.  Leave documented for a future
DI refactor.

---

## Summary

| Global | Module | Action |
|---|---|---|
| `_platform_cache` | `_setup.py` | **Replaced** with `@functools.lru_cache` |
| `_ENTITY_LOOKUP` | `entity_lookup.py` | Retained — tests monkeypatch |
| `_REGISTER_INFO_CACHE` | `mappings/_helpers.py` | Retained — tests monkeypatch |
| `REGISTER_*` / `REGISTER_HASH` | `scanner/register_maps.py` | Retained — correct design |
| `_OPTIONS_INIT_LOCK` + option lists | `options/__init__.py` | Retained — HA lifecycle |
