# Coordinator → DeviceClient Redesign Plan

## Date: 2026-05-16
## Branch: claude/coordinator-deviceclient-redesign-ls3tr
## Baseline commit: main (2039 passed, 4 skipped)

---

## Coordinator Public Methods/Properties to Preserve

| Method/Property | Description |
|---|---|
| `__init__(hass, config, *, entry)` | Constructor |
| `from_params(hass, host, port, slave_id, ...)` | Factory classmethod |
| `_parse_backoff_jitter(value)` | Static method |
| `get_register_map(register_type)` | Return register name→address mapping |
| `async_setup()` | Device scan / setup |
| `async_shutdown()` | Shutdown and disconnect |
| `get_diagnostic_data()` | Diagnostics dict |
| `get_device_info()` | Device info dict |
| `status_overview` | Property: online/offline summary |
| `performance_stats` | Property: performance statistics |
| `device_name` | Property: display name |
| `host/port/slave_id/connection_type/etc.` | Config properties via _CoordinatorConfigPropertiesMixin |

## Coordinator Direct Imports Before Refactor (from scanner/transport/registers)

```python
from ..scanner import (DeviceCapabilities, ThesslaGreenDeviceScanner, is_request_cancelled_error)
from ..transport.base import BaseModbusTransport
from ..registers.read_planner import group_reads
from ..registers.register_def import RegisterDef
from ..register_defs_cache import get_register_definitions
from ..errors import CannotConnect
```

These are the imports to eliminate from coordinator.py by moving the operations into DeviceClient.

## Current Helper Modules Used by Coordinator

Coordinator imports from ~35 coordinator submodule files:
- `capabilities.py` - _CoordinatorCapabilitiesMixin (post-processing, power, efficiency)
- `config_normalization.py` - scan interval normalization
- `config_properties.py` - _CoordinatorConfigPropertiesMixin (host/port/etc. properties)
- `connection.py` - transport building, direct TCP client connect
- `connection_lifecycle.py` - ensure_connected_lifecycle orchestration
- `connection_state.py` - connection state transitions
- `connection_test.py` - initial connection test
- `device_info.py` - device scan orchestration
- `diagnostics.py` - status_overview, performance_stats, get_diagnostic_data
- `disconnect.py` - graceful disconnect
- `errors.py` - update error handling
- `factory.py` - build_config_from_params
- `init_config.py` - normalize_runtime_config, apply_coordinator_config
- `io.py` - _ModbusIOMixin (all register read methods)
- `lifecycle.py` - async_setup orchestration
- `models.py` - CoordinatorConfig
- `register_groups.py` - compute_register_groups
- `register_processing.py` - find_register_name, process_register_value
- `retry.py` - _PermanentModbusError, read_with_retry
- `runtime.py` - normalize_backoff, parse_backoff_jitter
- `runtime_io.py` - call_modbus, read_all_register_data
- `runtime_state.py` - mark_registers_failed, clear_register_failure
- `scan.py` - scan cache management
- `scan_result.py` - apply_scan_result
- `scanner_kwargs.py` - build_scanner_kwargs
- `schedule.py` - _CoordinatorScheduleMixin (write path)
- `state.py` - initialize_runtime_state, normalize_serial_settings
- `transport_select.py` - select_auto_transport
- `update.py` - async_update_data, run_update_cycle
- `update_result.py` - apply_success_result
- `update_state.py` - begin_update_cycle, finish_update_cycle
- `write_path.py` - encode_write_value, write orchestration

## Proposed DeviceClient Responsibilities

The `ThesslaGreenDeviceClient` (at `core/client.py`) owns:

### Connection Lifecycle
- `async_ensure_connected()` - establish connection via transport/client
- `async_disconnect()` - graceful disconnect with lock
- `async_close()` - force close resources
- `_disconnect_locked()` - disconnect without acquiring locks
- Transport building: `_build_tcp_transport()`, `_build_rtu_transport()`
- Transport selection: `_build_transport_selector_fn()`, `_try_direct_client_connect()`

### Scanner/Capabilities
- `async_scan_device()` - run ThesslaGreenDeviceScanner, return result
- `apply_scan_result()` - store scan results in device state
- Capabilities access: `get_capabilities()`

### Register Read Path
- Inherits `_ModbusIOMixin` for batch read methods
- `async_update_data()` - run full update cycle
- `_read_all_register_data()` - read all register groups

### Register Write Path
- Inherits `_CoordinatorScheduleMixin` for write methods
- `async_write_register()` - write single register with retry
- `async_write_registers()` - write multiple registers

### Data Post-Processing
- Inherits `_CoordinatorCapabilitiesMixin` for post-processing, power, efficiency

### Device State
Owns all device-domain mutable state:
- Connection: `client`, `_transport`, `_client_lock`, `_write_lock`, `offline_state`
- Device info: `capabilities`, `device_info`, `_device_name`
- Register maps: `_register_maps`, `_reverse_maps`, `_register_groups`, `_failed_registers`
- Scan results: `available_registers`, `device_scan_result`, `scanned_registers`, `unknown_registers`, `last_scan`
- Statistics: `statistics`, `_consecutive_failures`, `_max_failures`
- Post-process: `_last_power_timestamp`, `_total_energy`, `_total_energy`
- Config: `config`, `timeout`, `retry`, `backoff`, `backoff_jitter`, `effective_batch`, etc.

## Coordinator Responsibilities After Refactor

The `ThesslaGreenModbusCoordinator` retains:

### HA Integration Boundary
- `DataUpdateCoordinator` base class, `_async_update_data()` override
- `async_setup()`, `async_shutdown()` - HA lifecycle
- Config entry management: `self.entry`, stop listener
- Reauthentication: `_trigger_reauth()`
- `enable_device_scan` (from entry options)

### Public API Preservation
- All public methods/properties from the "to preserve" table above
- Private methods that coordinator submodule functions call (delegating to DeviceClient)
- Properties that proxy device state to DeviceClient

### Coordinator-Specific Helpers
- `_CoordinatorConfigPropertiesMixin` (host/port/etc. accessors)
- HA diagnostics formatting
- HA-specific setup/unload

## Coordinator Property Proxies (for backward compat)

These coordinator properties delegate to `self._device_client`:
```
client, _transport, _client_lock, _write_lock, offline_state,
capabilities, device_info, available_registers,
_register_maps, _reverse_maps, _register_groups, _failed_registers,
_input_registers_rev, _holding_registers_rev, _coil_registers_rev, _discrete_inputs_rev,
statistics, _consecutive_failures, _max_failures,
device_scan_result, unknown_registers, scanned_registers, last_scan,
_last_power_timestamp, _total_energy, _update_in_progress,
_resolved_connection_mode, config,
timeout, retry, backoff, backoff_jitter,
effective_batch, max_registers_per_request,
force_full_register_list, scan_uart_settings, deep_scan, safe_scan, skip_missing_registers,
_device_name
```

## Out-of-Scope Items

- Changing Modbus protocol behavior
- Changing entity/unique/service/register IDs
- Changing translations or manifest
- Changing dependencies
- Removing coordinator submodule functions
- Removing coordinator public API
- Changing clock sync behavior
- Removing modbus_helpers.py compatibility surface

## Risk List

1. **Property proxy breaks HA DataUpdateCoordinator**: Properties with setters on coordinator may conflict with HA internals → Mitigated by keeping HA-specific attrs as plain attributes
2. **Mixin MRO conflicts**: DeviceClient inheriting from coordinator mixins may cause import cycles → Mitigated by careful import ordering
3. **Circular imports**: core.client imports from coordinator.*, coordinator.* imports from core.client → Avoided by not having coordinator submodule functions import from core
4. **asyncio.Lock sharing**: Properties returning same Lock object from DeviceClient → Safe, same object is returned
5. **Missed property setter**: Coordinator submodule function assigns to coordinator attribute without a setter → Caught by tests
6. **scan_result._normalise_available_registers**: Called on coordinator from apply_scan_result → Kept as coordinator method that delegates to impl
7. **hass in DeviceClient**: Scanner needs hass → DeviceClient stores hass reference

## Validation Plan

For each phase:
1. `python -m compileall` - no import errors
2. `pytest tests/ -q` - all 2039 tests pass
3. `ruff check` - no lint errors
4. `ruff format --check` - properly formatted
5. Tools: `check_translations`, `validate_entity_mappings`, `check_maintainability`, `compare_registers_with_reference`

## Removed Code (to track)

None removed in Phase 4. Phase 5 cleanup will remove:
- Direct coordinator imports of scanner/transport/registers (moved to DeviceClient)
- Redundant coordinator wrapper methods once DeviceClient is fully wired

---

## Phase Status

- [x] Phase 0: Baseline verified (2039 passed, 4 skipped)
- [x] Phase 1: Inventory documented
- [ ] Phase 2: DeviceClient interface defined (core/client.py)
- [ ] Phase 3: Contract tests added
- [ ] Phase 4: DeviceClient wired into coordinator
- [ ] Phase 5: Responsibility migration
- [ ] Phase 6: Public API preserved and verified
- [ ] Phase 7: Dead code removed (if any)
- [ ] Phase 8: Architecture quality gates
- [ ] Phase 9: Full validation
