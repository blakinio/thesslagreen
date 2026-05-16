# Coordinator Proxy Cleanup

## Summary

All 38 proxy properties in `ThesslaGreenModbusCoordinator` are **retained** because they
are required by coordinator submodule duck-typing (submodule functions receive the
coordinator as an untyped owner and access state via `owner.attr`).

What was cleaned up:

- Removed 4 imports that were only used in now-delegated method implementations.
- Replaced 6 duplicate method implementations with delegation to `_device_client`.
- Added a block documentation comment explaining the proxy retention rationale.
- Removed unused `cast` import after delegation.

## Removed Proxies

None removed — all 38 properties retained for reasons documented below.

## Retained Proxies

All proxy properties are retained. Grouped by reason:

### Required by coordinator submodule functions (duck-typing)

Coordinator submodules (`runtime_io`, `read_batches`, `read_bits`, `register_groups`,
`scan_result`, `state`, `errors`, `update_result`, `scanner_kwargs`, `init_config`, etc.)
receive the coordinator as an untyped owner parameter and access these attributes:

| Property | Used by submodules |
|----------|--------------------|
| `config` | `init_config`, `device_info`, `lifecycle` |
| `_device_name` | `init_config`, `diagnostics`, `scan_result` |
| `_resolved_connection_mode` | `init_config`, `connection_lifecycle`, `scan_result` |
| `timeout` | `runtime_io`, `scanner_kwargs`, `handlers_data` |
| `retry` | `runtime_io`, `scanner_kwargs`, `read_common`, `retry`, `handlers_data` |
| `backoff` | `runtime_io`, `scanner_kwargs` |
| `backoff_jitter` | `runtime_io`, `scanner_kwargs` |
| `force_full_register_list` | `init_config`, `scanner_kwargs` |
| `scan_uart_settings` | `init_config`, `scanner_kwargs`, `handlers_data` |
| `deep_scan` | `init_config`, `scanner_kwargs` |
| `safe_scan` | `init_config`, `scanner_kwargs`, `register_groups` |
| `skip_missing_registers` | `init_config`, `scanner_kwargs` |
| `effective_batch` | `register_groups`, `read_batches`, `read_bits`, `scanner_kwargs`, `handlers_data` |
| `max_registers_per_request` | `init_config` |
| `client` | `runtime_io`, `read_batches`, `read_bits`, `schedule`, `update` |
| `_transport` | `runtime_io`, `read_batches`, `read_bits`, `schedule`, `update`, `retry`, `state` |
| `_client_lock` | `connection_lifecycle`, `state` |
| `_write_lock` | `update`, `state` |
| `_update_in_progress` | `update_state` |
| `offline_state` | `state`, `update_result`, `errors`, `diagnostics` |
| `capabilities` | `capabilities_mixin`, `scan`, `scan_result` |
| `device_info` | `state`, `scan`, `scan_result`, `diagnostics` |
| `available_registers` | `state`, `scan`, `scan_result`, `read_batches`, `read_bits`, `register_groups` |
| `_register_maps` | `state`, `scan` |
| `_reverse_maps` | `state` |
| `_input_registers_rev` | `state` |
| `_holding_registers_rev` | `state` |
| `_coil_registers_rev` | `state` |
| `_discrete_inputs_rev` | `state` |
| `_register_groups` | `state`, `register_groups`, `read_batches`, `read_bits` |
| `_failed_registers` | `state`, `runtime_state`, `read_batches` |
| `statistics` | `state`, `update_result`, `errors`, `read_batches` |
| `_consecutive_failures` | `errors`, `update_result`, `state` |
| `_max_failures` | `errors`, `state` |
| `device_scan_result` | `scan`, `scan_result` |
| `unknown_registers` | `state`, `scan_result`, `handlers_data` |
| `scanned_registers` | `state`, `scan_result`, `handlers_data` |
| `last_scan` | `state`, `scan_result` |
| `_last_power_timestamp` | `capabilities_mixin` |
| `_total_energy` | `capabilities_mixin`, `state` |

### Also required by external callers

The following proxies are also directly accessed by entity platform files and tests:

- `available_registers` — all entity platforms (sensor, switch, fan, number, …)
- `capabilities` — entity platforms (sensor, switch, climate, …) and tests
- `device_info` — sensor.py, _setup.py and tests
- `statistics` — number.py, switch.py, fan.py and tests
- `device_scan_result` — binary_sensor.py, sensor.py, diagnostics.py
- `client` — tests (direct attribute access for mock assertions)
- `_transport` — tests (direct attribute access for mock assertions)
- `retry` — tests
- `force_full_register_list` — entity platforms and diagnostics.py

## Duplicate Implementations Removed

Six method implementations in `ThesslaGreenModbusCoordinator` that duplicated DeviceClient
logic were replaced with delegation calls:

| Method | Before | After |
|--------|--------|-------|
| `get_register_map` | `cast(dict[str, int], self._register_maps.get(...))` | `self._device_client.get_register_map(...)` |
| `_get_client_method` | Full implementation iterating `(self._transport, self.client)` | `self._device_client._get_client_method(name)` |
| `_find_register_name` | `_find_register_name_impl(self._reverse_maps, ...)` | `self._device_client._find_register_name(...)` |
| `_process_register_value` | `_process_register_value_impl(...)` | `self._device_client._process_register_value(...)` |
| `_mark_registers_failed` | `_mark_registers_failed_impl(self, names)` | `self._device_client._mark_registers_failed(names)` |
| `_clear_register_failure` | `_clear_register_failure_impl(self, name)` | `self._device_client._clear_register_failure(name)` |

## Imports Removed from coordinator.py

- `from .register_processing import find_register_name as _find_register_name_impl`
- `from .register_processing import process_register_value as _process_register_value_impl`
- `from .runtime_state import clear_register_failure as _clear_register_failure_impl`
- `from .runtime_state import mark_registers_failed as _mark_registers_failed_impl`
- `from typing import cast` (no longer needed after delegation)

## Future Removal Path

Proxy properties can be removed one-by-one as their consuming submodules are
updated to accept a `DeviceClient` directly instead of the coordinator. Recommended
approach:

1. Update a coordinator submodule to accept `DeviceClient | ThesslaGreenModbusCoordinator`
   via a `Protocol` or union type.
2. Remove the corresponding proxy property from the coordinator.
3. Update callers of the coordinator method to go through `coordinator._device_client`.

High-value candidates for future removal (internal-only usage):
- `_update_in_progress` — only accessed by `update_state` module
- `_last_power_timestamp`, `_total_energy` — only accessed by `capabilities_mixin`
- `_input_registers_rev`, `_holding_registers_rev`, `_coil_registers_rev`, `_discrete_inputs_rev` — only accessed during initialization in `state.py`
