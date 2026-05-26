# Final Shim Audit Inventory

Branch: `refactor/final-shim-audit-cleanup`
Base: `main`
Generated during Phase 1 of the final repository-wide shim audit.

---

## Active Shims Found and Removed

### 1. Dead aliases in `transport/crc.py`

**Type:** Dead module-level aliases  
**File:** `custom_components/thessla_green_modbus/transport/crc.py` (lines 24–26)  
**Content:**
```python
# Aliases used by tests and compatibility shims
_crc16 = crc16
_append_crc = append_crc
```
**Status:** Active production code  
**Callers:** None. Tests create their own aliases via `import crc16 as _crc16`; no code imports `_crc16` or `_append_crc` from this module.  
**Action:** Removed aliases and comment.  
**Canonical replacement:** `from .crc import crc16`, `from .crc import append_crc`

---

### 2. Empty placeholder `registers/reference.py`

**Type:** Reserved module placeholder (zero code lines)  
**File:** `custom_components/thessla_green_modbus/registers/reference.py`  
**Content:** `"""Reserved module placeholder for future static register references."""` (docstring only)  
**Status:** Active production code (importable but empty)  
**Callers:** None  
**Action:** Deleted.

---

### 3. Empty placeholder `transport/factory.py`

**Type:** Reserved module placeholder (zero code lines)  
**File:** `custom_components/thessla_green_modbus/transport/factory.py`  
**Content:** `"""Reserved module placeholder for future transport factory abstractions."""` (docstring only)  
**Status:** Active production code (importable but empty)  
**Callers:** None  
**Action:** Deleted.

---

### 4. Dead options re-exports in `const.py`

**Type:** Dead re-export block (backward compatibility shims)  
**File:** `custom_components/thessla_green_modbus/const.py` (lines 13–32)  
**Symbols removed:**
- `BYPASS_MODES`, `DAYS_OF_WEEK`, `FILTER_TYPES`, `GWC_MODES`
- `MODBUS_BAUD_RATES`, `MODBUS_PARITY`, `MODBUS_PORTS`, `MODBUS_STOP_BITS`
- `OPTIONS_PATH`, `PERIODS`, `RESET_TYPES`, `SPECIAL_MODE_OPTIONS`
- `_get_options_init_lock`, `_load_json_option`, `async_setup_options`

**Status:** Active production code (re-exports with no callers)  
**Callers:** None. All production code imports directly from `.options`. One test file (`test_options_loading.py`) accessed these via `const.*` and was updated to use canonical imports.  
**Action:** Removed re-export block. Updated `tests/test_options_loading.py`.  
**Canonical replacement:** `from .options import <symbol>` / `from custom_components.thessla_green_modbus.options import <symbol>`

---

### 5. Dead `_build_map` re-export in `const.py`

**Type:** Dead re-export  
**File:** `custom_components/thessla_green_modbus/const.py` (line 39)  
**Status:** Active production code (re-export with no callers)  
**Callers:** None  
**Action:** Removed re-export.  
**Canonical replacement:** `from .registers.maps import _build_map`

---

### 6. Dead `multi_register_sizes` re-export in `const.py`

**Type:** Dead re-export  
**File:** `custom_components/thessla_green_modbus/const.py` (line 44)  
**Status:** Active production code (re-export with one test caller)  
**Callers:** `tests/test_options_loading.py:52` — updated to import from canonical path.  
**Action:** Removed re-export. Updated `tests/test_options_loading.py`.  
**Canonical replacement:** `from custom_components.thessla_green_modbus.registers.maps import multi_register_sizes`

---

### 7. Dead `_ENTITY_LOOKUP` re-export in `const.py`

**Type:** Dead re-export  
**File:** `custom_components/thessla_green_modbus/const.py` (line 10)  
**Status:** Active production code (re-export with no callers)  
**Callers:** None (tests patch `entity_lookup._ENTITY_LOOKUP` directly)  
**Action:** Removed re-export.  
**Canonical replacement:** `from .entity_lookup import _ENTITY_LOOKUP`

---

### 8. Stale docstring in `scanner/register_map_cache.py`

**Type:** Stale module name in docstring  
**File:** `custom_components/thessla_green_modbus/scanner/register_map_cache.py:13`  
**Content:** `"""Synchronize cached register hash from scanner_register_maps."""`  
**Status:** Stale reference to old flat-file name `scanner_register_maps` (removed long ago)  
**Action:** Updated to `scanner.register_maps` (canonical package path).

---

## Items Inspected and Retained (Justified)

### `config_flow.py`

**Type:** HA-required entrypoint module  
**File:** `custom_components/thessla_green_modbus/config_flow.py`  
**Comment:** "re-exported here so that the canonical import path continues to work"  
**Justification:** Home Assistant requires a `config_flow.py` file with the `ConfigFlow` class at the integration root. The `_config_flow/` package is the internal implementation. This is a mandatory HA structural requirement, not a compatibility shim.  
**Action:** Retained as-is.

### Register map functions in `const.py`

**Symbols:** `coil_registers`, `discrete_input_registers`, `holding_registers`, `input_registers`  
**Justification:** Used internally by `migrate_unique_id` at lines 317–321. Not re-exports for external callers; internal imports needed for function implementation.  
**Action:** Retained. Updated comment from "backward compatibility" to "used internally."

### `_build_entity_lookup` in `const.py`

**Justification:** Used internally by `migrate_unique_id` at line 316.  
**Action:** Retained.

### `modbus/__init__.py`

**Type:** Package init (zero code lines, only docstring)  
**Justification:** Required as a Python package init for the `modbus/` package which contains real modules (`call.py`, `client_close.py`, `frame_logging.py`, `framer.py`).  
**Action:** Retained.

### `coordinator/__init__.py`

**Type:** Package init (5 code lines)  
**Justification:** Exports `ThesslaGreenModbusCoordinator` — the integration's primary coordinator class. Legitimate public API.  
**Action:** Retained.

---

## Stale Documentation Found and Updated

### `docs/final_shim_cleanup_report.md`

**Issue:** "Remaining Architectural Debt" section stated `modbus_transport.py` was still present. That file was deleted in commit `864539f6` (PR #1639) before this audit.  
**Action:** Updated to reflect removal.

### `docs/final_architecture_cleanup.md`

**Issue:** "Const/entity lookup" section stated `_ENTITY_LOOKUP` had been removed from const.py in a prior PR; in fact it persisted until this audit.  
**Action:** Updated with accurate record of what was removed in this PR.

---

## No Additional Shims Found

Scanned with:
- `rg -n "Compatibility shim|re-export|reexport|shim|legacy import|backward compat" custom_components tests tools docs`
- `rg -n "modbus_helpers|modbus_transport|modbus_exceptions|scanner_helpers|scanner_register_maps|scanner_device_info|config_flow_runtime|config_flow_validation|config_flow_options_form|coordinator\.io|coordinator\.capabilities"` (as import paths)
- File-shape audit for modules with ≤12 code lines

No additional active shims were identified beyond those listed above.
