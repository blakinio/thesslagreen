# Coordinator Proxy Removal Inventory

- Device-domain state must be accessed via `coordinator.device_client`.
- Internal `coordinator.<state>` proxy access is deprecated; do not add new proxy usages.

| Proxy | Migrate now | Canonical replacement |
|---|---|---|
| `config` | yes | `coordinator.device_client.config` |
| `_device_name` | yes | `coordinator.device_client._device_name` |
| `_resolved_connection_mode` | yes | `coordinator.device_client._resolved_connection_mode` |
| `timeout` | yes | `coordinator.device_client.timeout` |
| `retry` | yes | `coordinator.device_client.retry` |
| `backoff` | yes | `coordinator.device_client.backoff` |
| `backoff_jitter` | yes | `coordinator.device_client.backoff_jitter` |
| `force_full_register_list` | yes | `coordinator.device_client.force_full_register_list` |
| `scan_uart_settings` | yes | `coordinator.device_client.scan_uart_settings` |
| `deep_scan` | yes | `coordinator.device_client.deep_scan` |
| `safe_scan` | yes | `coordinator.device_client.safe_scan` |
| `skip_missing_registers` | yes | `coordinator.device_client.skip_missing_registers` |
| `effective_batch` | yes | `coordinator.device_client.effective_batch` |
| `max_registers_per_request` | yes | `coordinator.device_client.max_registers_per_request` |
| `client` | yes | `coordinator.client (raw pymodbus)` |
| `_transport` | yes | `coordinator.device_client._transport` |
| `_client_lock` | yes | `coordinator.device_client._client_lock` |
| `_write_lock` | yes | `coordinator.device_client._write_lock` |
| `_update_in_progress` | yes | `coordinator.device_client._update_in_progress` |
| `offline_state` | yes | `coordinator.device_client.offline_state` |
| `capabilities` | yes | `coordinator.device_client.capabilities` |
| `device_info` | yes | `coordinator.device_client.device_info` |
| `available_registers` | yes | `coordinator.device_client.available_registers` |
| `_register_maps` | yes | `coordinator.device_client._register_maps` |
| `_reverse_maps` | yes | `coordinator.device_client._reverse_maps` |
| `_input_registers_rev` | yes | `coordinator.device_client._input_registers_rev` |
| `_holding_registers_rev` | yes | `coordinator.device_client._holding_registers_rev` |
| `_coil_registers_rev` | yes | `coordinator.device_client._coil_registers_rev` |
| `_discrete_inputs_rev` | yes | `coordinator.device_client._discrete_inputs_rev` |
| `_register_groups` | yes | `coordinator.device_client._register_groups` |
| `_failed_registers` | yes | `coordinator.device_client._failed_registers` |
| `statistics` | yes | `coordinator.device_client.statistics` |
| `_consecutive_failures` | yes | `coordinator.device_client._consecutive_failures` |
| `_max_failures` | yes | `coordinator.device_client._max_failures` |
| `device_scan_result` | yes | `coordinator.device_client.device_scan_result` |
| `unknown_registers` | yes | `coordinator.device_client.unknown_registers` |
| `scanned_registers` | yes | `coordinator.device_client.scanned_registers` |
| `last_scan` | yes | `coordinator.device_client.last_scan` |
| `_last_power_timestamp` | yes | `coordinator.device_client._last_power_timestamp` |
| `_total_energy` | yes | `coordinator.device_client._total_energy` |
