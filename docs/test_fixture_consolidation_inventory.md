# Test Fixture Consolidation Inventory

Generated: 2026-05-17  
Branch: `claude/cleanup-coordinator-proxy-Dns7J`

---

## Overview

This document records repeated test-setup patterns across the test suite and
classifies which ones are safe to centralize in shared helper files.

---

## Existing Shared Helpers

### `tests/helpers_coordinator.py`

Contains:
- `_make_config_entry(data, options)` — minimal `ConfigEntry` mock
- `INPUT_REGISTERS`, `HOLDING_REGISTERS` — module-level register maps (loaded once)
- `coordinator` pytest fixture — creates a coordinator with `from_params` and fixed available registers

**Status:** Good baseline.  Used by `test_coordinator_*` split tests.

### `tests/helpers_modbus.py`

Currently **empty** (0 bytes).  No content yet.

### `tests/helpers_entity_data_correctness.py`

Contains entity-data correctness assertion helpers.  Well-structured, platform-specific.

### `tests/helpers_register_loader.py`

Contains register-loader test helpers.  Well-structured, loader-specific.

---

## Repeated Patterns Identified

### 1. `_make_coordinator()` / `ThesslaGreenModbusCoordinator.from_params`

Appears in **20+ test files**.  Typical pattern:

```python
def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass, host="192.168.1.1", port=502, slave_id=1,
        name="test", scan_interval=30, timeout=3, retry=2, **kwargs,
    )
```

Files with local `_make_coordinator` or equivalent:
- `test_device_client.py` — has `_make_coordinator`
- `test_coordinator_device_info.py` — inline `from_params`
- `test_coordinator_statistics.py` — inline `from_params`
- `test_coordinator_errors.py` — inline `from_params`
- `test_coordinator_reconnect.py` — inline `from_params`
- `test_coordinator_register_writes.py` — inline `from_params`
- `test_coordinator_update_success.py` — inline `from_params`
- `test_coordinator_offline.py` — inline `from_params`
- `test_coordinator_error_paths.py` — inline `from_params`
- `test_coordinator.py` — inline `from_params` (multiple sites)
- `test_coordinator_scan.py` — inline `from_params`
- `test_fan_percentage_limits.py` — inline `from_params`
- `test_rtu_transport.py` — inline `from_params`

**Classification:** Safe to centralize.  Already exists in `test_device_client.py`.
A good candidate for `tests/helpers_coordinator.py`.

### 2. `ThesslaGreenDeviceClient` direct creation

Appears in `test_device_client.py`.  Pattern:

```python
def _make_client(**kwargs) -> ThesslaGreenDeviceClient:
    config = _make_config()
    hass = MagicMock()
    return ThesslaGreenDeviceClient(config, hass=hass, effective_batch=100,
                                    resolved_connection_mode=None, backoff=0.5,
                                    backoff_jitter=None, **kwargs)
```

**Classification:** Safe to centralize in `tests/helpers_modbus.py` or
`tests/helpers_coordinator.py`.

### 3. Fake transport setup

Repeated in many tests:

```python
transport = MagicMock()
transport.is_connected.return_value = True
transport.read_holding_registers = AsyncMock(return_value=...)
coordinator._transport = transport
```

**Classification:** Safe candidate for `tests/helpers_modbus.py`.  However,
the specific return values differ per test — a factory that returns a configurable
fake transport is appropriate.

### 4. Config entry mock

`_make_config_entry` already in `helpers_coordinator.py`.  Still duplicated in a few
test files.  Harmless duplication — consolidate opportunistically.

---

## Safe Fixture Consolidation (This PR)

### Added to `tests/helpers_coordinator.py`

Added `make_coordinator_from_params()` — a shared factory wrapping
`ThesslaGreenModbusCoordinator.from_params` with canonical test defaults.
Tests can pass override kwargs.

### `tests/helpers_modbus.py`

The file was empty.  No changes made in this PR — adding helpers here requires
first auditing which mock patterns are stable across all test files.  Adding
the wrong default would silently change test semantics.  Deferred to a dedicated
fixture-cleanup PR.

### Test migration

`tests/test_device_client.py`: migrated all `coord._device_client` accesses to
`coord.device_client` (using the new public `device_client` property added in
Phase 2).  This is the only mechanical migration done in this PR.

---

## Deferred Items

| Pattern | Reason deferred |
|---|---|
| Centralize `_make_coordinator` across 20+ files | High blast radius; risk of silently changing test defaults |
| Add helpers to `helpers_modbus.py` | Empty file needs careful design before population |
| Migrate `from_params` inline calls | Safe but large scope — separate PR |
