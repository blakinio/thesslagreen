# Coordinator → DeviceClient Redesign

## Date: 2026-05-16
## Branch: claude/coordinator-deviceclient-redesign-ls3tr

---

## Architecture Summary

`ThesslaGreenModbusCoordinator` has been refactored into a thin Home Assistant
adapter.  All device-domain state and operations live in
`ThesslaGreenDeviceClient` (`core/client.py`).  The coordinator proxies its
device-state attributes to the client via Python data descriptors so that
existing coordinator submodule functions continue to work unchanged through
duck-typing.

### Ownership after refactor

| Layer | Responsibility |
|---|---|
| `ThesslaGreenDeviceClient` | Device state, connection lifecycle, transport selection, scanner orchestration, register read/write/groups, capabilities, diagnostics helpers |
| `ThesslaGreenModbusCoordinator` | HA integration boundary: `DataUpdateCoordinator`, config entry, reauth, `async_setup`/`async_shutdown`, property proxies |

---

## DeviceClient Public Interface

### Constructor
```python
ThesslaGreenDeviceClient(
    config: CoordinatorConfig,
    *,
    hass: HomeAssistant,
    effective_batch: int,
    resolved_connection_mode: str | None,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    entry: ConfigEntry | None = None,
)
```

### Connection lifecycle
| Method | Description |
|---|---|
| `async_ensure_connected()` | Establish connection via lifecycle impl |
| `async_disconnect()` | Graceful disconnect behind `_client_lock` |
| `async_close()` | Alias for `async_disconnect` |
| `async_test_connection()` | Probe connection via `_write_lock` |
| `_disconnect_locked()` | Disconnect without acquiring lock |
| `_ensure_connection()` | Duck-typing alias |
| `_disconnect()` | Duck-typing alias |
| `_close_client_connection()` | Close client object safely |

### Transport construction
| Method | Description |
|---|---|
| `_build_tcp_transport(mode)` | Build TCP/RTU-over-TCP transport |
| `_try_direct_client_connect(*, allow_parameterless_ctor)` | Connect via AsyncModbusTcpClient |
| `_build_transport_selector_fn()` | Return transport selector callable |

### Scanner / capabilities
| Method | Description |
|---|---|
| `_build_scanner_kwargs()` | Return scanner constructor kwargs |
| `async_create_scanner()` | Instantiate ThesslaGreenDeviceScanner |
| `async_scan_device()` | Run full device scan |
| `_normalise_available_registers(available)` | Canonicalise register name sets |

### Register operations
| Method | Description |
|---|---|
| `compute_register_groups()` | Pre-compute batch read groups |
| `_find_register_name(register_type, address)` | Reverse-map address → name |
| `_process_register_value(register_name, value)` | Decode raw register value |
| `_mark_registers_failed(names)` | Record failed register names |
| `_clear_register_failure(name)` | Remove from failed set |
| `_get_client_method(name)` | Get Modbus method or no-op |
| `async_write_register(register_name, value, ...)` | Write single register |

### Public API
| Method/Property | Description |
|---|---|
| `get_device_info()` | Returns copy of `device_info` dict |
| `get_capabilities()` | Returns `DeviceCapabilities` instance |
| `get_register_map(register_type)` | Returns register name→address map |
| `is_connected` | Property: transport/client connected status |
| `selected_transport` | Property: resolved connection mode |

### Owned state
| Attribute | Type | Description |
|---|---|---|
| `config` | `CoordinatorConfig` | Full config dataclass |
| `hass` | `HomeAssistant` | HA instance (for scanner) |
| `client` | `Any \| None` | pymodbus async client |
| `_transport` | `BaseModbusTransport \| None` | Active transport |
| `_client_lock` | `asyncio.Lock` | Serialises connection changes |
| `_write_lock` | `asyncio.Lock` | Serialises writes/tests |
| `offline_state` | `bool` | Whether device is known offline |
| `capabilities` | `DeviceCapabilities` | Scanned device capabilities |
| `device_info` | `dict` | Model, firmware, etc. |
| `available_registers` | `dict[str, set[str]]` | Per-type available register names |
| `_register_maps` | `dict[str, dict[str, int]]` | name → address maps |
| `_reverse_maps` | `dict[str, dict[int, str]]` | address → name maps |
| `_register_groups` | `dict[str, list[tuple]]` | Pre-computed batch groups |
| `_failed_registers` | `set[str]` | Registers that failed last read |
| `statistics` | `dict` | Read/error counters |
| `_consecutive_failures` | `int` | Consecutive update failures |
| `_max_failures` | `int` | Failure threshold |
| `_last_power_timestamp` | `datetime` | For energy calculation |
| `_total_energy` | `float` | Accumulated energy |

---

## Coordinator Property Proxies

All 40 device-domain attributes on the coordinator are data descriptors
(property with both getter and setter) that forward to `self._device_client`.
This means:

1. `coordinator.X = value` routes through the setter → stored in DeviceClient.
2. `coordinator.X` returns DeviceClient's value.
3. Instance `__dict__` assignment is prevented for proxied attributes.
4. Tests can still mock methods (non-data descriptors, not proxied) via instance
   attribute shadowing.

Proxied attributes (40 total):
`config`, `_device_name`, `_resolved_connection_mode`, `timeout`, `retry`,
`backoff`, `backoff_jitter`, `effective_batch`, `max_registers_per_request`,
`force_full_register_list`, `scan_uart_settings`, `deep_scan`, `safe_scan`,
`skip_missing_registers`, `client`, `_transport`, `_client_lock`, `_write_lock`,
`offline_state`, `_update_in_progress`, `capabilities`, `device_info`,
`available_registers`, `_register_maps`, `_reverse_maps`,
`_input_registers_rev`, `_holding_registers_rev`, `_coil_registers_rev`,
`_discrete_inputs_rev`, `_register_groups`, `_failed_registers`,
`device_scan_result`, `unknown_registers`, `scanned_registers`, `last_scan`,
`statistics`, `_consecutive_failures`, `_max_failures`,
`_last_power_timestamp`, `_total_energy`.

---

## Test Patch Compatibility

Tests that patch coordinator-level names continue to work:

- `coordinator.coordinator.AsyncModbusTcpClient` — DeviceClient's
  `_try_direct_client_connect` looks up this class through the coordinator
  package at call time so patches are visible.
- `coordinator.coordinator.ThesslaGreenDeviceScanner.create` — re-exported
  in coordinator.py namespace (`# noqa: F401`); patching the class method
  affects all callers including DeviceClient.
- `coord._ensure_connection = AsyncMock(...)` — coordinator method (not a
  property), instance attribute shadows the class method.
- `coord._disconnect_locked = AsyncMock(...)` — same pattern.

---

## Validation Results

| Gate | Result |
|---|---|
| `python -m compileall` | Clean |
| `pytest tests/` | 2082 passed, 4 skipped (baseline 2039 + 43 new) |
| `ruff check` | All checks passed |
| `ruff format --check` | 430 files already formatted |
| `check_translations.py` | All translation keys present |
| `validate_entity_mappings.py` | OK: 366 entities validated |
| `check_maintainability.py` | Maintainability gate passed |
| `compare_registers_with_reference.py` | Exit code 0 |

---

## Non-Goals / Out-of-Scope

- Entity IDs, unique IDs, service IDs — unchanged
- Register names, register addresses — unchanged
- Modbus protocol behaviour, scan behaviour — unchanged
- Translation structure, manifest structure — unchanged
- Coordinator submodule functions — unchanged (duck-typing still works)
- Clock sync behaviour — unchanged
- `modbus_helpers.py` compatibility surface — unchanged
