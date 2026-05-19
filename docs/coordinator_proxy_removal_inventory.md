# Coordinator Proxy Removal Inventory

- Device-domain state must be accessed via `coordinator.device_client`.
- Internal `coordinator.<state>` proxy access is deprecated; do not add new proxy usages.

## Completed (2026-05-19)

The scan-flag proxy group was removed.  Callers in `diagnostics.py`,
`coordinator/diagnostics.py`, and `services/handlers_data.py` were updated to
use `coordinator.device_client.X` directly.  Note: `register_groups.py` and
`scanner_kwargs.py` already received a `ThesslaGreenDeviceClient` as their
duck-typed `coordinator` argument, so those files needed no changes.

| Proxy | Status | Canonical replacement |
|---|---|---|
| `scan_uart_settings` | **removed** | `coordinator.device_client.scan_uart_settings` |
| `deep_scan` | **removed** | `coordinator.device_client.deep_scan` |
| `safe_scan` | **removed** | `coordinator.device_client.safe_scan` |
| `skip_missing_registers` | **removed** | `coordinator.device_client.skip_missing_registers` |

## Remaining proxies

The proxies below are required because coordinator submodule functions
(read_batches, retry, io_mixin, etc.) receive the coordinator as a duck-typed
`owner` and access these attributes directly, and/or entity platform files
access them on the coordinator.  Remove a proxy when its callers are updated
to use `coordinator.device_client.X` instead.

| Proxy | Canonical replacement |
|---|---|
| `config` | `coordinator.device_client.config` |
| `_device_name` | `coordinator.device_client._device_name` |
| `_resolved_connection_mode` | `coordinator.device_client._resolved_connection_mode` |
| `timeout` | `coordinator.device_client.timeout` |
| `retry` | `coordinator.device_client.retry` |
| `backoff` | `coordinator.device_client.backoff` |
| `backoff_jitter` | `coordinator.device_client.backoff_jitter` |
| `force_full_register_list` | `coordinator.device_client.force_full_register_list` |
| `effective_batch` | `coordinator.device_client.effective_batch` |
| `max_registers_per_request` | `coordinator.device_client.max_registers_per_request` |
| `client` | `coordinator.device_client.client` |
| `_transport` | `coordinator.device_client._transport` |
| `_client_lock` | `coordinator.device_client._client_lock` |
| `_write_lock` | `coordinator.device_client._write_lock` |
| `_update_in_progress` | `coordinator.device_client._update_in_progress` |
| `offline_state` | `coordinator.device_client.offline_state` |
| `capabilities` | `coordinator.device_client.capabilities` |
| `device_info` | `coordinator.device_client.device_info` |
| `available_registers` | `coordinator.device_client.available_registers` |
| `_register_maps` | `coordinator.device_client._register_maps` |
| `_reverse_maps` | `coordinator.device_client._reverse_maps` |
| `_input_registers_rev` | `coordinator.device_client._input_registers_rev` |
| `_holding_registers_rev` | `coordinator.device_client._holding_registers_rev` |
| `_register_groups` | `coordinator.device_client._register_groups` |
| `_failed_registers` | `coordinator.device_client._failed_registers` |
| `statistics` | `coordinator.device_client.statistics` |
| `device_scan_result` | `coordinator.device_client.device_scan_result` |
| `unknown_registers` | `coordinator.device_client.unknown_registers` |
| `scanned_registers` | `coordinator.device_client.scanned_registers` |
| `last_scan` | `coordinator.device_client.last_scan` |
