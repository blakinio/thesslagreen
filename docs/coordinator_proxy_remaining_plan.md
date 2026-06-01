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

All coordinator delegates backed by `self._device_client.*` have been removed. The
**35 proxy properties** listed above remain, retained until real-device
validation confirms no consumer-visible behavior changes.

The remaining future work is removing proxy properties following the incremental path
documented in the “Future Removal Path” section above.

---

## 2026-06-01 A1-finish — remove coordinator indirection from connection_lifecycle

**Slice: A1-finish**

`core/connection_lifecycle.py:ensure_connected_lifecycle` previously received `coordinator: Any`
and accessed `coordinator.device_client.*` throughout — a double-indirection since callers
(in `client_connection.py`) already held `self` which is a `DeviceClient`.

### What changed

| File | Change |
|---|---|
| `core/connection_lifecycle.py` | Renamed param `coordinator` → `device_client`; added explicit `disconnect_locked_fn` keyword param; all `coordinator.device_client.*` → `device_client.*`; `coordinator._disconnect_locked` → `disconnect_locked_fn(...)` |
| `core/client_connection.py` | Call site updated: passes `self` as `device_client`, adds `disconnect_locked_fn=self._disconnect_locked` |

### Why no behavior change

`client_connection.py` previously passed `self` (a `DeviceClient`) as the `coordinator` arg.
Since `DeviceClient` has `device_client = self`, `coordinator.device_client.*` and
`device_client.*` produced the same result. The rename eliminates the indirection without
altering any value.

---

## 2026-06-01 A5 — migrate platform callers from coordinator proxy to device_client

**Slice: A5**

Migrated 10 call sites across 8 platform/entity files away from coordinator-level proxy
accesses to direct `coordinator.device_client.*` accesses.

### Migrated call sites

| File | Old | New |
|---|---|---|
| `number.py` (×2) | `coordinator.get_register_map(“holding_registers”)` | `coordinator.device_client.get_register_map(“holding_registers”)` |
| `sensor.py` | `coordinator.get_register_map(register_type)` | `coordinator.device_client.get_register_map(register_type)` |
| `binary_sensor.py` | `coordinator.get_register_map(register_type)` | `coordinator.device_client.get_register_map(register_type)` |
| `binary_sensor.py` | `coordinator.device_name` | `coordinator.device_client.device_name` |
| `climate.py` | `coordinator.device_name` | `coordinator.device_client.device_name` |
| `time.py` | `coordinator.get_register_map(register_type)` | `coordinator.device_client.get_register_map(register_type)` |
| `text.py` | `coordinator.get_register_map(register_type)` | `coordinator.device_client.get_register_map(register_type)` |
| `select.py` | `coordinator.get_register_map(register_type)` | `coordinator.device_client.get_register_map(register_type)` |
| `entity.py` | `self.coordinator.slave_id` | `self.coordinator.device_client.slave_id` |

Also added `device_name` property to `core/client.py` (`ThesslaGreenDeviceClient`) since it
was needed by platform callers and was not previously on the client.

### Skipped items (with reasons)

| Item | Reason |
|---|---|
| `coordinator.get_device_info` | Coordinator version returns full HA `DeviceInfo` dict with `identifiers`, `name`, `manufacturer`; `device_client.get_device_info()` returns raw `dict(self.device_info)` — behavior would change |
| `coordinator.get_diagnostic_data` | `device_client` has no `get_diagnostic_data`; coordinator version references `coordinator.scan_interval` (HA-level attribute) |
| `coordinator.scan_interval` | HA-level attribute set as `self.scan_interval = interval_seconds` in `__init__`; not a device-client proxy |
| `coordinator.host` / `coordinator.port` | Only callers are in `services/handlers_data.py` and `clock_sync.py`, which are outside A5 scope |

### Test fixture updates

| File | Change |
|---|---|
| `tests/conftest.py` | Added `coordinator.device_client.get_register_map = lambda rt: _register_maps.get(rt, {})` alongside existing mock |
| `tests/test_entity_unique_id.py` (×2) | Added `coordinator.device_client.slave_id = slave_id` |
| `tests/test_available_registers_schedule_time.py` (×2) | Added `coordinator.device_client.get_register_map.return_value = _REGISTER_MAP` |
| `tests/test_number.py` | Added `mock_coordinator.device_client.get_register_map = _map_fn` in `_make_number` helper |

---

## 2026-06-01 A6 — remove dead proxy methods from coordinator.py

**Slice: A6**

After A5 emptied the caller lists for two coordinator-level proxies, they were removed.

### Removed

| Removed | Was |
|---|---|
| `get_register_map` method | One-line delegate: `return self._device_client.get_register_map(register_type)` |
| `device_name` property | Delegated to `_device_name_impl(self)` from `coordinator/diagnostics.py` |
| Import `from .diagnostics import (device_name as _device_name_impl,)` | No longer needed after `device_name` removal |

### Size change

`coordinator/coordinator.py`: 477 lines → 466 lines (−11).

### Proxy property count

The 35 proxy **properties** listed in this document are unchanged — only method delegates
were removed in this slice.

### Why safe

Both methods had zero callers after A5. Confirmed by `grep -r` on `custom_components` and
`tests` before removal.
