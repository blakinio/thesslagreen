# Coordinator Proxy Migration Inventory

Generated: 2026-05-17  
Branch: `claude/cleanup-coordinator-proxy-Dns7J`

## Overview

`ThesslaGreenModbusCoordinator` owns ~40 properties that proxy to `self._device_client`
(a `ThesslaGreenDeviceClient` instance).  The coordinator's device-state attributes
(transport, capabilities, register maps, statistics, …) all delegate reads and writes
to the device client.  Coordinator submodule functions receive `self` (the coordinator)
via duck-typing and access these attributes directly.

---

## Proxy Inventory by Category

### Configuration proxies

| Property | Type | Classification |
|---|---|---|
| `config` | read/write | **runtime-required** — accessed by coordinator submodules (diagnostics, entity platform files) |
| `timeout` | read/write | **runtime-required** — set by `init_config`, read by IO paths |
| `retry` | read/write | **runtime-required** — set by `init_config` |
| `backoff` | read/write | **runtime-required** — set by `init_config`, used by retry logic |
| `backoff_jitter` | read/write | **runtime-required** — set by `init_config` |
| `force_full_register_list` | read/write | **runtime-required** — read by `scan.py`, platform files |
| `scan_uart_settings` | read/write | **runtime-required** — read by `scanner_kwargs.py`, `handlers_data.py`, `init_config.py` |
| `deep_scan` | read/write | **runtime-required** — read by `scanner_kwargs.py`, `diagnostics.py`, `init_config.py` |
| `safe_scan` | read/write | **runtime-required** — read by `register_groups.py`, `scanner_kwargs.py`, `__init__.py`, `init_config.py` |
| `skip_missing_registers` | read/write | **runtime-required** — read by `scan.py`, `scan_result.py`, `scanner_kwargs.py`, `init_config.py` |
| `effective_batch` | read/write | **runtime-required** — read by `diagnostics.py`, set by `init_config.py` |
| `max_registers_per_request` | read/write | **runtime-required** — set by `init_config.py` |

### Private config-like proxies (internal names)

| Property | Type | Classification |
|---|---|---|
| `_device_name` | read/write | **runtime-required** — read/written by `diagnostics.py`, `init_config.py`, `scan_result.py`, `coordinator._trigger_reauth` |
| `_resolved_connection_mode` | read/write | **runtime-required** — written by `init_config.py`, `scan_result.py`, read by `connection_lifecycle.py` |

### Connection-state proxies

| Property | Type | Classification |
|---|---|---|
| `client` | read/write | **runtime-required** — read by tests, `client_registers.py` fallback |
| `_transport` | read/write | **runtime-required** — read/written by `update.py`, `runtime_io.py`, `connection_lifecycle.py`, `state.py`, many tests |
| `_client_lock` | read/write | **runtime-required** — used in `connection_lifecycle.py`, `state.py`, `coordinator._disconnect`, many tests |
| `_write_lock` | read/write | **runtime-required** — used in `update.py`, `coordinator._test_connection`, many tests |
| `_update_in_progress` | read/write | **runtime-required** — read/written by `update_state.py`, tests |
| `offline_state` | read/write | **runtime-required** — written by `state.py` fallback; tests read it |

### Device info / capabilities proxies

| Property | Type | Classification |
|---|---|---|
| `capabilities` | read/write | **runtime-required** — read by entity platform files, tests |
| `device_info` | read/write | **runtime-required** — read by `_setup.py`, `scan_result.py`, `warn_missing_device_info`, entity platform files, tests |

### Register maps and groups proxies

| Property | Type | Classification |
|---|---|---|
| `available_registers` | read/write | **runtime-required** — read by `scan.py`, entity platform files, tests |
| `_register_maps` | read/write | **runtime-required** — read/written by `state.py`, `scan.py`, `register_groups.py`, tests |
| `_reverse_maps` | read/write | **runtime-required** — read/written by `state.py` |
| `_input_registers_rev` | read/write | **runtime-required** — set by `state.py` |
| `_holding_registers_rev` | read/write | **runtime-required** — set by `state.py` |
| `_coil_registers_rev` | read/write | **runtime-required** — set by `state.py` |
| `_discrete_inputs_rev` | read/write | **runtime-required** — set by `state.py` |
| `_register_groups` | read/write | **runtime-required** — read/written by `register_groups.py`, `state.py`, tests |
| `_failed_registers` | read/write | **runtime-required** — read/written by `update_state.py`, `runtime_state.py`, tests |

### Statistics and failure tracking proxies

| Property | Type | Classification |
|---|---|---|
| `statistics` | read/write | **runtime-required** — read by `diagnostics.py`, `number.py`, tests |
| `_consecutive_failures` | read/write | **runtime-required** — read/written by `errors.py`, `update_result.py`, `state.py`, tests |
| `_max_failures` | read/write | **runtime-required** — read by `errors.py`, set by `state.py`, tests |

### Scan-state proxies

| Property | Type | Classification |
|---|---|---|
| `device_scan_result` | read/write | **runtime-required** — read by `diagnostics.py`, `binary_sensor.py`, tests |
| `unknown_registers` | read/write | **runtime-required** — read by `diagnostics.py` |
| `scanned_registers` | read/write | **runtime-required** — set by `scan_result.py` |
| `last_scan` | read/write | **runtime-required** — read by `diagnostics.py` |

### Post-processing state proxies (capabilities mixin)

| Property | Type | Classification |
|---|---|---|
| `_last_power_timestamp` | read/write | **runtime-required** — written by `state.py`, read by `test_coordinator_post_process.py` |
| `_total_energy` | read/write | **runtime-required** — written by `state.py` |

---

## Zero External-Caller Proxies

After running the grep searches, **no proxies have zero external callers** — every
proxy is accessed by at least one of: a coordinator submodule, an entity platform
file, or a test.

Candidates examined but confirmed as runtime-required:
- `scan_uart_settings`: accessed by `services/handlers_data.py`, `core/scanner_kwargs.py`, `coordinator/init_config.py`
- `deep_scan`: accessed by `diagnostics.py`, `coordinator/diagnostics.py`, `core/scanner_kwargs.py`
- `safe_scan`: accessed by `__init__.py`, `core/register_groups.py`, `core/scanner_kwargs.py`
- `skip_missing_registers`: accessed by `coordinator/scan.py`, `coordinator/scan_result.py`, `core/scanner_kwargs.py`
- `_device_name`: accessed by `coordinator/diagnostics.py`, `coordinator/scan_result.py`, `coordinator/_trigger_reauth`

---

## Public Accessor Added (Phase 2)

A `device_client` property (no leading underscore) was added to the coordinator to
expose `_device_client` publicly.  This allows test code to migrate from
`coordinator._device_client` to `coordinator.device_client`.  The `_device_client`
attribute is retained for internal coordinator submodule use and backward compatibility
with existing test proxy-verification tests.

---

## Proposed Migration Path

**Current state:** All proxies are retained (correct).  All device-domain state lives
in `ThesslaGreenDeviceClient`; the coordinator's proxies provide duck-typing
compatibility for its submodule functions.

**Future removal path (per-proxy):**
1. For each proxy `coordinator.X`, update the submodule functions that accept
   `coordinator` as their duck-typed owner to instead accept a `DeviceClient`
   directly.
2. Once no submodule uses `coordinator.X`, the proxy can be deleted.
3. Entity platform files use `self.coordinator.X` — these need updating last, as
   they are the outermost callers.

**Recommended order** (lowest risk first):
1. Post-processing proxies (`_last_power_timestamp`, `_total_energy`) — only used
   by `_CoordinatorCapabilitiesMixin` which already lives in `core/`.
2. Statistics proxies (`statistics`, `_consecutive_failures`, `_max_failures`) —
   only used by a small set of submodules.
3. Scan-state proxies (`device_scan_result`, `unknown_registers`, `scanned_registers`,
   `last_scan`) — used by diagnostics and scan submodules.
4. Register-map proxies — heaviest usage, defer until all callers are updated.
5. Connection-state proxies — tightest coupling to async lifecycle; defer last.

**Scope of this PR:** Only the `device_client` public accessor was added.
All proxies are retained as documented above.
