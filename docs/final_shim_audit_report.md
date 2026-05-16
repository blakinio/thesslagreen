# Final Shim Audit Report

Branch: `refactor/final-shim-audit-cleanup`
Base: `main`

---

## Summary

A complete repository-wide audit for compatibility shims, re-export wrappers, legacy import
paths, placeholder modules, and stale cleanup documentation. All active shims identified were
removed or replaced with canonical imports. No behavior changes were made.

---

## Shims Found

| Item | Location | Type |
|------|----------|------|
| Dead `_crc16` / `_append_crc` aliases | `transport/crc.py:24–26` | Dead aliases |
| Empty placeholder | `registers/reference.py` | Zero-code placeholder |
| Empty placeholder | `transport/factory.py` | Zero-code placeholder |
| 15 dead options re-exports | `const.py:13–32` | Dead backward-compat re-exports |
| Dead `_build_map` re-export | `const.py:39` | Dead re-export |
| Dead `multi_register_sizes` re-export | `const.py:44` | Dead re-export (1 test caller updated) |
| Dead `_ENTITY_LOOKUP` re-export | `const.py:10` | Dead re-export |
| Stale module name in docstring | `scanner/register_map_cache.py:13` | Stale doc reference |

---

## Shims Removed

| Item | Action |
|------|--------|
| `transport/crc.py` dead aliases `_crc16`, `_append_crc` and their comment | Deleted |
| `registers/reference.py` empty placeholder | File deleted |
| `transport/factory.py` empty placeholder | File deleted |
| 15 options re-exports from `const.py` | Removed block; callers already used `.options` directly |
| `_build_map` re-export from `const.py` | Removed (zero callers) |
| `multi_register_sizes` re-export from `const.py` | Removed; test updated to canonical path |
| `_ENTITY_LOOKUP` re-export from `const.py` | Removed (zero callers) |

---

## Compatibility Surfaces Intentionally Retained

### `config_flow.py`

Home Assistant requires a `config_flow.py` file at the integration root. This is a mandatory
HA structural entrypoint, not a compatibility shim. It will always re-export `ConfigFlow` from
the `_config_flow/` internal package.

### Register map functions in `const.py`

`coil_registers`, `discrete_input_registers`, `holding_registers`, `input_registers` remain
imported in `const.py` because they are used internally by the `migrate_unique_id` function.
These are not re-exports for external callers; they are internal imports for function use.

### `_build_entity_lookup` in `const.py`

Used internally by `migrate_unique_id`. Retained.

---

## Import Paths Migrated

| File | Old import | New canonical import |
|------|-----------|---------------------|
| `tests/test_options_loading.py:27,39` | `const._load_json_option` | `custom_components.thessla_green_modbus.options._load_json_option` |
| `tests/test_options_loading.py:52` | `from const import multi_register_sizes` | `from custom_components.thessla_green_modbus.registers.maps import multi_register_sizes` |
| `tests/test_options_loading.py:80` | `const.async_setup_options` | `custom_components.thessla_green_modbus.options.async_setup_options` |
| `tests/test_options_loading.py:82` | `const.MODBUS_BAUD_RATES` | `custom_components.thessla_green_modbus.options.MODBUS_BAUD_RATES` |

---

## Stale Docs Cleaned

| Document | Issue | Fix |
|----------|-------|-----|
| `docs/final_shim_cleanup_report.md` | "Remaining Architectural Debt" stated `modbus_transport.py` still present; it was deleted in PR #1639 | Updated to reflect removal |
| `docs/final_architecture_cleanup.md` | "Const/entity lookup" section had inaccurate claims about what had/hadn't been removed from const.py | Updated with accurate record |
| `scanner/register_map_cache.py:13` | Docstring referenced old `scanner_register_maps` flat-file name | Updated to `scanner.register_maps` |

---

## Dependency Direction Check (Phase 5)

`core/` imports from `coordinator/` (12+ import sites across `client.py`, `client_connection.py`,
`client_registers.py`, `client_scanner.py`, `io_mixin.py`, `capabilities_mixin.py`).
This is an architectural layering violation (core/ → coordinator/ creates circular dependency risk),
but it cannot be fixed safely within the scope of this audit since it would require a major
restructuring of the `ThesslaGreenDeviceClient` implementation. The violation is documented here.

Expected direction: `coordinator/` → `core/`  
Actual direction: `core/` ↔ `coordinator/` (bidirectional imports)

This is pre-existing debt from the DeviceClient architecture introduced in PR #1633–#1637 and is
out of scope for a shim-only audit.

---

## Validation Results

| Gate | Result |
|------|--------|
| `python -m compileall -q custom_components tests tools` | PASS |
| `ruff check custom_components tests tools` | PASS |
| `ruff check --select I custom_components tests tools` | PASS |
| `ruff format --check custom_components tests tools` | PASS (430 files formatted) |
| `python tools/compare_registers_with_reference.py` | PASS (62 extras expected; 242 name mismatches pre-existing) |
| `python tools/check_maintainability.py` | PASS |
| `python tools/validate_entity_mappings.py` | PASS (366 entities validated) |
| `python tools/check_translations.py` | PASS — All translation keys present |

### pytest Environment Limitation

Environment runs Python 3.11.15. `pytest-homeassistant-custom-component>=0.13.309` requires
Python ≥3.12 and could not be installed. pytest could not collect tests. Compilation and static
analysis pass. Runtime tests should be run in a Python 3.12+ CI environment (GitHub Actions uses
Python 3.13 where the full suite passes).

---

## No Active Shim Markers Remain in Production Code

`rg "Compatibility shim|Compatibility re-exports|kept for compatibility|wrapper module|alias module" custom_components/thessla_green_modbus` → no matches.

---

## Behavior Confirmation

- No Modbus register addresses changed
- No register names changed
- No entity IDs changed
- No unique IDs changed
- No service IDs changed
- No translation keys changed
- No config/options flow behavior changed
- No new compatibility shims created
- No `modbus_helpers.py` reintroduced
- No `modbus_transport.py` reintroduced

---

## Remaining Architectural Debt

1. **core/ ↔ coordinator/ circular layering** — `core/` imports from `coordinator/`; this should
   flow one-way. Fixing requires a structural refactor of `ThesslaGreenDeviceClient`. Out of scope
   for this audit.

---

## Recommended Next Step

Real-device validation against a ThesslaGreen AirPack unit running Home Assistant with this
integration to confirm no regression in register reads, entity values, coordinator scan/update
behavior, and config/options flow.
