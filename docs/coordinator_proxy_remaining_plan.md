# Coordinator Proxy Remaining Plan

## Why Full Proxy Elimination Is Deferred

Full coordinator proxy elimination was explicitly deferred from this cleanup PR for the
following reasons:

1. **Hardware validation first.** The immediate priority is physical real-device testing
   with logs. A broad proxy migration before that carries meaningful risk: if a subtle
   behavioral difference surfaces during hardware validation, it is harder to attribute
   the cause when both proxy removal and hardware testing happen in the same window.

2. **Scope risk.** The coordinator proxy properties (`device_client`, and related
   pass-through accessors on `ThesslaGreenModbusCoordinator`) are referenced across
   many submodules. Removing them in bulk before verifying the full runtime loop
   against real hardware is unsafe.

3. **Partial migration danger.** Removing some proxies while leaving others means some
   call sites go direct and others go through the coordinator shim. This asymmetry
   makes bugs harder to trace during device testing.

## Current Accessor Name

The live device-client accessor added in the device-client redesign is **`device_client`**
on `ThesslaGreenModbusCoordinator`. It returns the `ThesslaGreenDeviceClient` instance.

## Why `coordinator.client` Cannot Serve as the DeviceClient Accessor

`coordinator.client` is the raw pymodbus client object (a `ModbusBaseClient` or compatible
type). `ThesslaGreenDeviceClient` wraps this client together with transport, scanner state,
and connection lifecycle helpers. Using `coordinator.client` directly in submodules that
need the full `DeviceClient` interface would bypass all of that logic and break the
abstraction layer.

## Safe Future Migration Strategy

Migrate coordinator proxy properties incrementally, one submodule at a time:

1. **Pick one submodule** (e.g. `coordinator/write_path.py` or `services/handlers_maintenance.py`)
   that currently imports from `coordinator` to reach device behaviour.

2. **Update that submodule** to accept a `ThesslaGreenDeviceClient` argument instead of
   going through the coordinator proxy. Add or update the corresponding unit tests.

3. **Update the call site** in the coordinator (or entry point) to pass `coordinator.device_client`
   directly to the submodule.

4. **Verify** the change with tests and, once hardware testing proceeds, with real-device logs.

5. **Repeat** for the next submodule only after the previous migration is confirmed stable.

6. **Remove proxy properties** (`coordinator.device_client` and any remaining shim accessors
   on the coordinator) only after **zero callers** remain that go through the proxy.

## Warning

Do **not** remove proxy properties in bulk before real-device validation. A mass removal
before hardware validation leaves no safe rollback path if the device behaves differently
than the mocked test environment.

## Tracking

See also:
- `docs/coordinator_proxy_cleanup.md` — prior inventory of proxy properties
- `docs/coordinator_proxy_migration_inventory.md` — migration inventory from previous PR
- `docs/device_client_redesign.md` — design rationale for `ThesslaGreenDeviceClient`
