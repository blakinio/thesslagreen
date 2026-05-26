# Coordinator Proxy Remaining Plan

## Audit Date

2026-05-17 — audited against `refactor/final-cleanup-before-device-validation`.

## Current Proxy Count

`coordinator/coordinator.py` contains **43 proxy properties** (lines 177–512), covering:

- Configuration (12 properties): `config`, `_device_name`, `_resolved_connection_mode`, `timeout`,
  `retry`, `backoff`, `backoff_jitter`, `force_full_register_list`, `scan_uart_settings`,
  `deep_scan`, `safe_scan`, `skip_missing_registers`, `effective_batch`, `max_registers_per_request`
- Connection state (6 properties): `client`, `_transport`, `_client_lock`, `_write_lock`,
  `_update_in_progress`, `offline_state`
- Device info / capabilities (2 properties): `capabilities`, `device_info`
- Register maps (8 properties): `available_registers`, `_register_maps`, `_reverse_maps`,
  `_input_registers_rev`, `_holding_registers_rev`, `_coil_registers_rev`, `_discrete_inputs_rev`,
  `_register_groups`, `_failed_registers`
- Statistics and failure tracking (3 properties): `statistics`, `_consecutive_failures`, `_max_failures`
- Scan state (4 properties): `device_scan_result`, `unknown_registers`, `scanned_registers`, `last_scan`
- Post-processing state (2 properties): `_last_power_timestamp`, `_total_energy`
- DeviceClient accessor (1 property): `device_client`

Plus 3 additional `@property` definitions at lines 857–875 (not device-client proxies).

## Removed Proxies (This PR)

None. All proxies are in active use by runtime code or tests (see classification below).

## Retained Proxies and Why

All proxy properties are retained. Classification:

### runtime-required

Properties accessed by coordinator submodules (`lifecycle.py`, `update.py`, `write_path.py`,
`scan.py`, `errors.py`, `schedule.py`, `runtime.py`, etc.) which currently receive `coordinator`
as their argument and access device state through it.

- `device_client` — submodule entry point for DeviceClient access
- `config` — read/write during options reload
- `client`, `_transport`, `_client_lock`, `_write_lock` — connection management
- `_update_in_progress`, `offline_state` — update-cycle state tracking
- `capabilities` — entity availability checks
- `available_registers`, `_register_maps`, `_register_groups`, `_failed_registers` — register access
- `statistics`, `_consecutive_failures`, `_max_failures` — failure and backoff logic
- `device_scan_result`, `scanned_registers`, `last_scan` — scan lifecycle

### entity-required

Properties accessed by HA entity platforms that receive `coordinator` as their injected
dependency.

- `available_registers`, `force_full_register_list` — sensor/switch/number/fan entity setup
- `capabilities` — climate, fan, binary_sensor entity feature flags
- `offline_state` — entity `available` property

### test-required

Properties set or read by unit tests that construct a `ThesslaGreenModbusCoordinator` and
then mutate its state directly to exercise specific code paths (e.g.
`coordinator._consecutive_failures = 1`, `coordinator.available_registers = {...}`).

All of the above runtime-required and entity-required properties also appear in tests in
this way; they are doubly-needed.

## Removed Coordinator Re-exports (This PR)

- `disconnect` — was re-exported from `coordinator/__init__.py` as
  `from ..core import disconnect as disconnect`. Only `tests/test_coordinator_disconnect.py`
  imported it via coordinator. That test was updated to import directly from
  `custom_components.thessla_green_modbus.core import disconnect`. The re-export is removed.

## Future Removal Path

Remove proxy properties incrementally after real-device validation, following the strategy
documented below:

1. **Pick one submodule** (e.g. `coordinator/write_path.py` or `services/handlers_maintenance.py`)
   that currently receives `coordinator` as an argument to reach device state.

2. **Update that submodule** to accept a `ThesslaGreenDeviceClient` argument directly.
   Add or update the corresponding unit tests.

3. **Update the call site** in the coordinator to pass `coordinator.device_client` to
   the submodule.

4. **Verify** with tests and with real-device logs once hardware validation is underway.

5. **Repeat** for the next submodule only after the previous migration is confirmed stable.

6. **Remove proxy properties** only after zero callers remain that go through the proxy.

## Why Bulk Removal Is Deferred

- **Hardware validation first.** A broad proxy migration before real-device testing makes
  it harder to attribute bugs during validation.
- **Scope risk.** Proxy properties span many submodules. Bulk removal before validating
  the full runtime loop on hardware is unsafe.
- **Asymmetry danger.** Removing some proxies while leaving others creates tracing
  difficulties if a device-level bug surfaces.

## Why `coordinator.client` Cannot Serve as the DeviceClient Accessor

`coordinator.client` is the raw pymodbus client object (`ModbusBaseClient` or compatible).
`ThesslaGreenDeviceClient` wraps this together with transport, scanner state, and connection
lifecycle helpers. Using `coordinator.client` where the full DeviceClient interface is needed
would bypass that logic and break the abstraction.

## Tracking

See also:
- `docs/coordinator_proxy_cleanup.md` — prior inventory of proxy properties
- `docs/coordinator_proxy_migration_inventory.md` — migration inventory from previous PR
- `docs/device_client_redesign.md` — design rationale for `ThesslaGreenDeviceClient`

## 2026-05-18 update

Consumer code has been migrated to prefer `coordinator.device_client` for device-domain state. Remaining proxy removals are deferred until direct proxy mutations in tests are fully migrated.


## 2026-05-18 slice-1 removal

Removed first internal proxy slice from `coordinator.py`: `_last_power_timestamp`, `_total_energy`, `_consecutive_failures`, `_max_failures`, `_failed_registers` (40 -> 35). These were safe because all runtime/test callers now use `coordinator.device_client.*`.

## 2026-05-26 slice-2 removal

Removed five more thin delegate methods from `coordinator.py`:

| Removed delegate | Replaced by |
|---|---|
| `_build_scanner_kwargs()` | Not needed on coordinator; `core/client_scanner.py` calls it on `DeviceClient` directly |
| `_create_scanner()` | Not needed; `_run_device_scan` already uses `self._device_client.async_create_scanner` |
| `_build_transport_selector_fn()` | Not needed; `client_connection.py` calls it on `DeviceClient` directly |
| `_compute_register_groups()` | `coordinator/lifecycle.py` updated to call `coordinator.device_client.compute_register_groups()` |
| `_build_tcp_transport()` | Test call sites updated to `coord.device_client._build_tcp_transport(...)` |

Updated call sites: `coordinator/lifecycle.py:36`, `tests/test_coordinator_lifecycle.py`, `tests/test_coordinator_capabilities.py`, `tests/test_coordinator_package_api.py`, `tests/test_cleanup_audit.py`.

## Remaining delegates (deferred)

The following delegates remain in `coordinator.py` and are deferred because their call sites span core IO modules (`read_batches.py`, `read_bits.py`) that use the `_ModbusIOMixin` protocol:

| Delegate | Risk to remove | Reason |
|---|---|---|
| `_get_client_method` | Medium | Called from `coordinator/schedule.py` (`self._get_client_method(...)`) which receives coordinator as `self` |
| `_mark_registers_failed` | High | Called from `core/read_batches.py` and `core/read_bits.py` via `owner._mark_registers_failed(...)` where `owner` may be coordinator |
| `_clear_register_failure` | High | Same — core IO mixin protocol |
| `_find_register_name` | High | Same — core IO mixin protocol |
| `_process_register_value` | High | Same — core IO mixin protocol |

These can only be removed safely after the read path is fully moved to `DeviceClient` and the coordinator is removed from `_ModbusIOMixin` inheritance. That requires removing `_ModbusIOMixin` from the coordinator's base class list and moving the update data path, which is a larger refactor gated on real-device validation completion.

