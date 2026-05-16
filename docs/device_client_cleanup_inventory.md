# Device Client Cleanup – Architecture Inventory

## Summary

This document inventories the current architecture prior to the device-client cleanup pass.

## Current Proxy Count

The `ThesslaGreenModbusCoordinator` in `coordinator/coordinator.py` exposes **38 proxy property pairs** (getter + setter) that delegate to `self._device_client`:

| Group | Properties |
|-------|-----------|
| Config | `config`, `_device_name`, `_resolved_connection_mode` |
| Settings | `timeout`, `retry`, `backoff`, `backoff_jitter`, `force_full_register_list`, `scan_uart_settings`, `deep_scan`, `safe_scan`, `skip_missing_registers`, `effective_batch`, `max_registers_per_request` |
| Connection state | `client`, `_transport`, `_client_lock`, `_write_lock`, `_update_in_progress`, `offline_state` |
| Device info | `capabilities`, `device_info` |
| Register maps | `available_registers`, `_register_maps`, `_reverse_maps`, `_input_registers_rev`, `_holding_registers_rev`, `_coil_registers_rev`, `_discrete_inputs_rev`, `_register_groups`, `_failed_registers` |
| Statistics | `statistics`, `_consecutive_failures`, `_max_failures` |
| Scan state | `device_scan_result`, `unknown_registers`, `scanned_registers`, `last_scan` |
| Capabilities mixin | `_last_power_timestamp`, `_total_energy` |

## Coordinator-Owned State

All mutable device-domain state lives in `ThesslaGreenDeviceClient`. The coordinator owns:
- HA-specific lifecycle (`DataUpdateCoordinator` base class)
- `scan_interval` (HA update interval)
- `_reauth_scheduled` flag
- `_stop_listener` callback
- HA `entry` reference (via base class)

## Major Responsibility Groups in `core/client.py`

| Group | Lines | Methods |
|-------|-------|---------|
| Connection lifecycle | ~233–296 | `async_ensure_connected`, `async_disconnect`, `async_close`, `async_test_connection`, `_disconnect_locked`, `_ensure_connection`, `_disconnect`, `_close_client_connection` |
| Transport construction | ~301–389 | `_build_tcp_transport`, `_try_direct_client_connect`, `_build_transport_selector_fn` |
| Scanner orchestration | ~394–419 | `async_create_scanner`, `async_scan_device`, `_normalise_available_registers` |
| Register groups | ~424–432 | `compute_register_groups` |
| IO mixin helpers | ~437–467 | `_find_register_name`, `_process_register_value`, `_mark_registers_failed`, `_clear_register_failure`, `_get_client_method` |
| Write support | ~472–514 | `async_write_register` |
| Public API | ~519–544 | `get_device_info`, `get_capabilities`, `get_register_map`, `is_connected`, `selected_transport` |

## Helper Modules Depending on Coordinator Proxies

All coordinator submodules use duck-typing — they receive the coordinator (or device client)
as a parameter and access attributes directly. The key submodules are:

- `coordinator/runtime_io.py` — `client`, `_transport`, `timeout`, `retry`, `backoff`, `backoff_jitter`
- `coordinator/read_batches.py` — `_register_groups`, `available_registers`, `effective_batch`, `client`, `_transport`
- `coordinator/read_bits.py` — `_register_groups`, `effective_batch`, `client`, `_transport`
- `coordinator/register_groups.py` — `available_registers`, `_register_groups`, `safe_scan`, `effective_batch`
- `coordinator/scanner_kwargs.py` — nearly all scan/connection settings
- `coordinator/state.py` — initializes all device-domain state attributes
- `coordinator/scan_result.py` — `device_scan_result`, `_resolved_connection_mode`, `capabilities`, `available_registers`, `device_info`, `last_scan`
- `coordinator/update_result.py` — `statistics`, `_consecutive_failures`, `offline_state`
- `coordinator/errors.py` — `statistics`, `_consecutive_failures`, `_max_failures`, `offline_state`
- `services/handlers_data.py` — `timeout`, `retry`, `scan_uart_settings`, `effective_batch`, `unknown_registers`, `scanned_registers`

## External Callers of Coordinator Properties

### Entity Platform Files
- `available_registers`, `capabilities`, `force_full_register_list`, `device_info`, `statistics`, `device_scan_result`

### Test Files
- `available_registers`, `client`, `_transport`, `capabilities`, `device_info`, `retry`, `statistics`
- Tests also patch: `coordinator.coordinator.AsyncModbusTcpClient`

## Recommended Extraction Boundaries

Based on the responsibility groups in `core/client.py`:

1. **`core/client_connection.py`** — Connection lifecycle + transport construction (11 methods)
2. **`core/client_scanner.py`** — Scanner orchestration (3 methods)
3. **`core/client_registers.py`** — Register groups + IO helpers + write support (7 methods)
4. **`core/client.py`** — `__init__` + public API (5 methods/properties) → thin composition root

For coordinator proxies, all 38 properties must be retained to preserve duck-typing used
by coordinator submodule functions and tests. Duplicate method implementations (where the
coordinator re-implements logic instead of delegating) are the primary target for removal.
