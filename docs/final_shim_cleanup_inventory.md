# Final Shim Cleanup Inventory

Generated during `refactor/remove-final-shims` branch work.

## Shim Files Found

### 1. `custom_components/thessla_green_modbus/coordinator/io.py`

**Type:** Pure re-export shim  
**Content:** `from ..core.io_mixin import _ModbusIOMixin; __all__ = ["_ModbusIOMixin"]`  
**Canonical module:** `custom_components.thessla_green_modbus.core.io_mixin`  
**Removable:** Yes — zero callers remain after this PR

**Callers before this PR:**
- None. `coordinator/coordinator.py` already imports directly from `core.io_mixin`.

---

### 2. `custom_components/thessla_green_modbus/coordinator/capabilities.py`

**Type:** Partial re-export shim  
**Content:** `from ..core.capabilities_mixin import _CoordinatorCapabilitiesMixin; __all__ = ["_CoordinatorCapabilitiesMixin"]`  
**Canonical module:** `custom_components.thessla_green_modbus.core.capabilities_mixin`  
**Removable:** Yes — after updating two test files

**Callers before this PR:**
- `tests/test_clock_sync.py:110` — `from coordinator.capabilities import _CoordinatorCapabilitiesMixin` (lazy, inside function body)
- `tests/test_coordinator_update.py:9` — `from coordinator.capabilities import _clamp_percentage, _coerce_bypass_open, _flow_balance_status, _normalise_capability_flag`
  - **Note:** These four helper functions are NOT re-exported by the shim (shim only exports `_CoordinatorCapabilitiesMixin`). This import was already broken at baseline.

---

## Other Compatibility Surfaces Checked

No additional shims found in:
- `coordinator/__init__.py` — exports only `CoordinatorConfig`, `ThesslaGreenModbusCoordinator`
- `core/__init__.py` — clean
- Production entity files (`sensor.py`, `climate.py`, etc.) — use `coordinator.capabilities` as an attribute name on the coordinator object, not as an import path — these are unrelated

## Canonical Import Paths (After Cleanup)

| Symbol | Canonical path |
|--------|----------------|
| `_ModbusIOMixin` | `custom_components.thessla_green_modbus.core.io_mixin` |
| `_CoordinatorCapabilitiesMixin` | `custom_components.thessla_green_modbus.core.capabilities_mixin` |
| `_clamp_percentage` | `custom_components.thessla_green_modbus.core.capabilities_mixin` |
| `_coerce_bypass_open` | `custom_components.thessla_green_modbus.core.capabilities_mixin` |
| `_flow_balance_status` | `custom_components.thessla_green_modbus.core.capabilities_mixin` |
| `_normalise_capability_flag` | `custom_components.thessla_green_modbus.core.capabilities_mixin` |

## Remaining Legacy Paths (None)

All legacy import paths are removed by this PR. No new shims are introduced.
