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
- **`make_coordinator(**kwargs)`** — NEW in this PR (see below)

### `tests/helpers_modbus.py`

Previously empty.  **Populated in this PR** with `make_config()` and `make_client()`
factories for `ThesslaGreenDeviceClient` test setup.

### `tests/helpers_entity_data_correctness.py`

Contains entity-data correctness assertion helpers.  Well-structured, platform-specific.

### `tests/helpers_register_loader.py`

Contains register-loader test helpers.  Well-structured, loader-specific.

---

## Repeated Patterns Identified

### 1. `_make_coordinator()` / `ThesslaGreenModbusCoordinator.from_params`

Was in **13+ test files** (identical boilerplate).  Typical pattern:

```python
def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass, host="192.168.1.1", port=502, slave_id=1,
        name="test", scan_interval=30, timeout=3, retry=2, **kwargs,
    )
```

**Classification:** Safe to centralize — all 13 copies were byte-for-byte identical.

**Action taken:** Added `make_coordinator(**kwargs)` to `tests/helpers_coordinator.py`.
Migrated the following files (11 test files + `test_device_client.py` already used
`_make_coordinator` from its local definition, now uses the shared one via alias):

- `test_coordinator_statistics.py`
- `test_coordinator_schedule.py`
- `test_coordinator_reconnect.py`
- `test_coordinator_error_paths.py`
- `test_coordinator_update.py`
- `test_coordinator_update_success.py`
- `test_coordinator_scan.py`
- `test_coordinator_read_cycle.py`
- `test_coordinator_package_api.py`
- `test_coordinator_retry_reconnect.py`
- `test_coordinator_availability.py`
- `test_coordinator_update_errors.py`
- `test_coordinator_device_info.py`

Each file imports: `from tests.helpers_coordinator import make_coordinator as _make_coordinator`
so all call sites remain unchanged (still call `_make_coordinator(...)`).

**Files NOT migrated** (custom `_make_coordinator` with different signature/defaults):
- `test_airflow_unit.py` — takes a `unit` positional parameter
- `test_clock_sync.py` — takes `write_ok` and `data` kwargs, uses MagicMock not real coordinator
- `test_text.py` — uses MagicMock not real coordinator

### 2. `ThesslaGreenDeviceClient` direct creation

Appeared in `test_device_client.py`.  Pattern:

```python
def _make_client(**kwargs) -> ThesslaGreenDeviceClient:
    config = _make_config()
    hass = MagicMock()
    return ThesslaGreenDeviceClient(config, hass=hass, effective_batch=100,
                                    resolved_connection_mode=None, backoff=0.5,
                                    backoff_jitter=None, **kwargs)
```

**Action taken:** Added `make_config()` and `make_client()` to `tests/helpers_modbus.py`.
The existing `_make_config` and `_make_client` in `test_device_client.py` were NOT removed
(to avoid changing that file) — future work can migrate them.

### 3. Fake transport setup

Repeated in many tests:

```python
transport = MagicMock()
transport.is_connected.return_value = True
transport.read_holding_registers = AsyncMock(return_value=...)
coordinator._transport = transport
```

**Classification:** Safe candidate for `tests/helpers_modbus.py`.  Deferred because
the specific return values differ per test — a factory needs more design thought.

### 4. Config entry mock

`_make_config_entry` already in `helpers_coordinator.py`.  Still duplicated in a few
test files.  Harmless duplication — consolidate in a future PR.

---

## Deferred Items

| Pattern | Reason deferred |
|---|---|
| Migrate `_make_coordinator` in `test_device_client.py` to use shared helper | Local `_make_coordinator` still present; removing requires re-reading file carefully |
| Fake transport factory in `helpers_modbus.py` | Return values differ per test; needs more design |
| Config entry mock deduplication | Harmless duplication; low priority |
| Migrate `from_params` inline calls in non-coordinator tests | Safe but large scope — separate PR |
