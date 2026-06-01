# Coordinator Proxy Remaining Plan

## Audit Date

2026-05-17 — initial audit against `refactor/final-cleanup-before-device-validation`.
2026-05-29 — proxy count and delegate status updated to reflect post-#1684 state.

## Proxy Count at Document Creation

`coordinator/coordinator.py` originally contained **43 proxy properties** at document creation.
After slice-1 removed 5 property proxies, the current count is **35 proxy properties**.
Slices 2 and 3 removed method delegates only — those do not count toward the proxy property total.
See the dated update sections below for the full history.

The original 43 proxy properties (lines 177–512) covered:

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

## Removed Proxies (Prior Slices)

None in the initial PR. See dated update sections below for the full removal history.

## Retained Proxies and Why

Classification:

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

## 2026-05-26 slice-3 removal — IO ownership cleanup (this PR)

All 5 deferred delegates have now been removed from `coordinator.py`:

| Removed delegate | Replaced by |
|---|---|
| `_get_client_method` | `coordinator.device_client._get_client_method(...)` |
| `_mark_registers_failed` | `coordinator.device_client._mark_registers_failed(...)` |
| `_clear_register_failure` | `coordinator.device_client._clear_register_failure(...)` |
| `_find_register_name` | `coordinator.device_client._find_register_name(...)` |
| `_process_register_value` | `coordinator.device_client._process_register_value(...)` |

Additionally:
- `_ModbusIOMixin` removed from `ThesslaGreenModbusCoordinator` inheritance.
- `coordinator/update.py` changed from `coordinator._read_all_register_data()` to `coordinator.device_client._read_all_register_data()`, making `DeviceClient` the single IO owner for the entire read cycle.
- `coordinator/schedule.py` write-path call sites updated to use `self._device_client._call_modbus(self._device_client._get_client_method(...))` and `self._device_client._clear_register_failure(...)`.

### Why this was now safe

The 5 delegates were previously blocked because `core/read_batches.py` and `core/read_bits.py` take an `owner` argument and call `owner._mark_registers_failed(...)` etc. Before, `owner` was the coordinator; after the `update.py` change, `owner` is always `device_client` (which already implements all 4 protocol methods via `_DeviceClientRegistersMixin`). Since `ThesslaGreenDeviceClient` has `device_client = self`, the `owner.device_client.*` accesses work uniformly.

### _failed_registers fix (implicit improvement)

Previously, `read_batches.py` used `getattr(owner, "_failed_registers", set())` where `owner = coordinator`. Coordinator forwarded the attribute via a property proxy (removed in slice-1). After this change, `owner = device_client` which holds the actual `_failed_registers` set, so the “skip already-failed registers” optimization now works correctly.

### New tests added

`tests/test_coordinator_io_ownership.py` — 15 tests verifying:
1. Coordinator no longer exposes the 5 removed delegate methods
2. DeviceClient is the IO owner for all 5 methods
3. Update cycle routes calls through device_client (not coordinator)
4. Failed-register tracking works via device_client
5. Fan-percentage and dangerous-entity regressions guarded

## 2026-05-29 slice-4 — lifecycle boundary cleanup (this PR)

Inspected 8 HA lifecycle/connection adapter methods in coordinator:
`_ensure_connection`, `_ensure_connected`, `_try_direct_client_connect`,
`_disconnect_locked`, `_close_client_connection`, `_disconnect`, `_async_setup_client`,
`_test_connection`.

### Kept as intentional HA-boundary adapters (documented in docstrings)

| Method | Why kept |
|---|---|
| `_ensure_connection` | Active duck-typing entry point called by schedule, update, retry, client_registers submodules |
| `_disconnect_locked` | Passed as `disconnect_locked_fn` callback to `core/connection_lifecycle.py:29` |
| `_disconnect` | Called by errors.py, schedule.py, update.py, write_path.py, and async_shutdown |
| `_test_connection` | Called in production by `coordinator/lifecycle.py:37` during HA setup |
| `_async_setup_client` | Intentional test-facing helper (documented); mirrors HA start-up path for unit tests |

### Removed unused coordinator proxies

| Removed | Why |
|---|---|
| `_ensure_connected` | One-line forwarder (`await self._device_client.async_ensure_connected()`); sole caller was `_ensure_connection` itself. Inlined. |
| `_try_direct_client_connect` | Zero callers on coordinator; `DeviceClient._try_direct_client_connect` is called directly via `self` inside `client_connection.py`. |
| `_close_client_connection` | Zero callers; `_disconnect_locked` in DeviceClient uses the `_close_client_connection_impl` function directly, never going through the coordinator proxy. |

### Why these are not HA-boundary adapters

Unlike `_ensure_connection` / `_disconnect_locked` / `_disconnect` (which satisfy a
duck-typing protocol consumed by coordinator submodules), the three removed methods were
never called from outside the class definition itself.  No production code, no tests, and
no protocol stubs required them on the coordinator.

### New tests

Three assertions added to `tests/test_coordinator_lifecycle.py`:
- `test_coordinator_no_ensure_connected`
- `test_coordinator_no_try_direct_client_connect`
- `test_coordinator_no_close_client_connection`

## Remaining delegates (none — cleanup complete)

All coordinator delegates backed by `self._device_client.*` have been removed.

The remaining future work is removing proxy properties following the incremental path
documented in the “Future Removal Path” section above.

## 2026-05-30 slice-5 — config property proxy and static method cleanup

### Baseline

After slices 1–4, coordinator still had:
- 9 config property proxies in `_CoordinatorConfigPropertiesMixin` (host, port, slave_id,
  connection_type, connection_mode, serial_port, baud_rate, parity, stop_bits)
- 2 unused static method proxies on `ThesslaGreenModbusCoordinator`
  (`_normalise_cached_register_name`, `_firmware_lacks_known_missing`)
- ~15 `_impl` delegate methods (all with active call sites in scan/lifecycle/internal modules)
- 4 `@property` definitions in coordinator.py itself (device_client, status_overview,
  performance_stats, device_name)

### Removed (8 proxies)

| Removed | Type | Why safe |
|---|---|---|
| `connection_type` (get/set) | Config property | Zero external call sites; callers use `device_client.config.connection_type` |
| `connection_mode` (get/set) | Config property | Zero external call sites; callers use `device_client.config.connection_mode` |
| `serial_port` (get/set) | Config property | Zero external call sites; callers use `device_client.config.serial_port` |
| `baud_rate` (get/set) | Config property | Zero external call sites; callers use `device_client.config.baud_rate` |
| `parity` (get/set) | Config property | Zero external call sites; callers use `device_client.config.parity` |
| `stop_bits` (get/set) | Config property | Zero external call sites; callers use `device_client.config.stop_bits` |
| `_normalise_cached_register_name` | Static method | Zero call sites; `core/scan_helpers.py` calls the function directly |
| `_firmware_lacks_known_missing` | Static method | Zero call sites; `coordinator/scan.py` calls the function directly |

### Kept as HA-boundary adapters (3 config proxies)

| Kept | Call sites | Why kept |
|---|---|---|
| `host` (get/set) | services/handlers_data, clock_sync, tests | Used by HA service handlers and clock sync |
| `port` (get/set) | services/handlers_data, tests | Used by HA service handlers |
| `slave_id` (get/set) | entity.py, core/runtime_io, core/read_common, services, tests | Used in entity unique_id generation, all read/write paths |

### Kept `_impl` delegates (deferred — C category)

All remaining `_impl` delegates on coordinator have active call sites in
`coordinator/scan.py`, `coordinator/lifecycle.py`, `coordinator/scan_result.py`,
or tests that mock them via `coord._method_name = MagicMock(...)`.

Removing these requires refactoring the coordinator submodule calling convention
(pass `DeviceClient` instead of `coordinator` to each submodule). This is
deferred until real-device validation.

| Deferred | Call sites |
|---|---|
| `_apply_scan_cache` | scan.py ×2, 10+ tests |
| `_load_full_register_list` | scan.py ×2, 6+ tests |
| `_store_scan_cache` | scan_result.py ×1 |
| `_get_scan_cache_from_entry` | scan.py ×1, 1 test |
| `_consume_config_flow_scan_cache` | scan.py ×1, 7+ tests |
| `_apply_scan_result` | coordinator.py ×1 (callback) |
| `_prepare_registers_for_setup` | lifecycle.py ×1, 1 test |
| `_warn_missing_device_info` | lifecycle.py ×1, 1 test |
| `_run_device_scan` | scan.py ×1, 6+ tests |
| `_normalise_available_registers` | scan_result.py ×1, scan.py ×1, 2 tests |

### Kept `@property` definitions in coordinator.py

| Property | Why kept |
|---|---|
| `device_client` | Core abstraction — 220+ usages across entire codebase |
| `status_overview` | Used by `diagnostics.py` for HA diagnostics handler |
| `performance_stats` | Used by `diagnostics.py` for HA diagnostics handler |
| `device_name` | Used by entity platforms for device name |

### Proxy count after slice-5

- Config property proxies: **3** (host, port, slave_id) — down from 9
- Static method proxies: **1** (_parse_backoff_jitter) — down from 3
- `_impl` delegate methods: **~15** (unchanged — all deferred)
- `@property` in coordinator.py: **4** (unchanged — all kept)
- Total proxy surface reduction this slice: **8** removed

### Dangerous entity category verification

All three dangerous switch entities (`lock_flag`, `hard_reset_settings`,
`hard_reset_schedule`) already have `”category”: “config”` in their mapping
definitions. The switch platform applies `EntityCategory` correctly.
Tests in `test_airpack4_dangerous_entity_marking.py` verify this.
No code changes needed.

### Explicit confirmations

- No Modbus runtime behavior changes
- No register address/name changes
- No entity ID changes
- No service ID changes
- No translation key changes
- No pymodbus update
- No quality_scale update
- No core consolidation performed
- No core file moves
- No modbus_helpers.py reintroduced

### Next suggested slice

Refactor coordinator submodules (`scan.py`, `lifecycle.py`, `scan_result.py`) to
accept `DeviceClient` directly instead of `coordinator`. This would allow removing
the `_impl` delegate methods. Requires real-device validation first.

## 2026-06-01 slices A1–A4

### A1 — core/ parameter rename (coordinator→device_client)

Renamed the `coordinator` parameter to `device_client` in four core helper modules
that were always called with `ThesslaGreenDeviceClient` as their argument:
- `core/client_scanner.py:build_scanner_kwargs`
- `core/register_groups.py:compute_register_groups`
- `core/runtime_io.py:call_modbus` and `read_all_register_data` (also simplified
  `device_client.device_client.X` → `device_client.X`)
- `core/read_common.py:execute_read_call`, `log_read_retry`, `raise_for_error_response`

No behavioral change. `test_dependency_direction.py` continues to pass.

### A2 — Already complete

After slices 1–5, `coordinator/scan.py`, `write_path.py`, `diagnostics.py`, and
`lifecycle.py` all use `coordinator.device_client.X` for device-domain state.
Remaining accesses are coordinator methods or HA attributes (entry, hass,
scan_interval, data). No changes needed.

### A3 — services/handlers_data.py

Migrated `coordinator.host/port/slave_id` in `services/handlers_data.py` to
`coordinator.device_client.config.host/port/slave_id` (6 usages across
`scan_all_registers` and `validate_known_registers` handlers).

### A4 — Remaining production callers migrated; proxy properties RETAINED

Migrated remaining production callers:
- `clock_sync.py`: `coordinator.host` → `coordinator.device_client.config.host`
- `coordinator.py _test_connection`: `self.slave_id` → `self._device_client.slave_id`
- `coordinator/schedule.py` (3 sites): `self.slave_id` → `self._device_client.slave_id`

**Proxy properties host/port/slave_id in `_CoordinatorConfigPropertiesMixin` RETAINED.**

Reason: `entity.py` `unique_id` property uses `getattr(coordinator, "host", "")`,
`getattr(coordinator, "port", 0)`, and `coordinator.slave_id` for entity identity.
These cannot be removed without changing entity unique IDs (violates the no-unique-id-change
constraint). Tests that SET/ASSERT these properties remain valid callers.

### Proxy counter after A1–A4

- Config property proxies: **3** (host, port, slave_id) — unchanged from slice-5; RETAINED
- Static method proxies: **1** (_parse_backoff_jitter) — unchanged
- `_impl` delegate methods: **~10** (all deferred — active call sites in scan/lifecycle/tests)
- `@property` in coordinator.py: **4** (device_client, status_overview, performance_stats, device_name)
