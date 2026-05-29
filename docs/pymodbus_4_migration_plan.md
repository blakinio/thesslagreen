# pymodbus 4.0 Migration Plan

**Status: Planning only — no code change in this document**
**Created: 2026-05-29**
**Related PR: #1685 (docs/refactor: plan pymodbus 4 migration and reduce core complexity)**

---

## 1. Current State

### Manifest requirement

```json
"requirements": ["pymodbus>=3.6.0,<4.0"]
```

### Why `<4.0` is intentionally pinned

- The integration targets the stable pymodbus 3.x API surface.
- pymodbus 4.0 is a new major version and may contain breaking API changes.
- The `<4.0` pin protects production installs from an unvalidated dependency upgrade.
- No one has tested the integration against pymodbus 4.x on a real device.
- Home Assistant currently installs pymodbus from the `requirements` list; if HA itself
  pins to 3.x, lifting our pin early would be a no-op. If HA lifts its pin before we do,
  our pin still protects us.

### Integration API surface against pymodbus

All Modbus I/O lives in `transport/` and is isolated from the HA layer. The
integration uses:

- `AsyncModbusTcpClient` / `AsyncModbusSerialClient` (TCP and RTU modes)
- `client.connect()` / `client.close()`
- `client.read_input_registers()` / `client.read_holding_registers()`
- `client.write_register()` / `client.write_registers()`
- `client.read_coils()` / `client.read_discrete_inputs()`
- Response objects: `.registers` / `.bits` attribute access
- Exception types: `ModbusException`, `ModbusIOException`, `ConnectionException`

---

## 2. Why pymodbus 4.0 Matters

- A major version bump signals that backwards compatibility is not guaranteed.
- Home Assistant may eventually update its bundled pymodbus or require 4.x.
- Custom integrations installed via HACS will follow HA's pymodbus version.
- Delaying migration planning means scrambling under time pressure when the pin
  eventually needs to be lifted.
- Proactive planning lets us do the migration on our own schedule with full
  test coverage.

---

## 3. Known Risk Areas to Verify

The following areas must be tested on pymodbus 4.x before the pin is lifted.
Each item represents a possible breaking-change surface.

### 3.1 Client construction

| Risk | Area | Notes |
|---|---|---|
| Constructor signature change | `AsyncModbusTcpClient` | New kwargs, renamed args, or dropped kwargs |
| Constructor signature change | `AsyncModbusSerialClient` | Same |
| `timeout` parameter behavior | Both | May have moved to a separate config object |
| `retry_on_empty` / retry config | Both | May have changed shape |
| `source_address` / framer args | Both | Framer API changed between 3.x versions |

### 3.2 Connection lifecycle

| Risk | Area | Notes |
|---|---|---|
| `connect()` return value | Both | Some 3.x versions return `bool`, 4.x may differ |
| `close()` / `transport.close()` | Both | Transport attribute shape may change |
| `is_socket_open()` or equivalent | Both | Property renamed in some releases |
| Re-connect after disconnect | Both | Behavior on repeated connect/close |

### 3.3 Register read API

| Risk | Area | Notes |
|---|---|---|
| `read_input_registers` signature | Both | `slave` → `device_id` rename in some versions |
| `read_holding_registers` signature | Both | Same |
| Response `.registers` attribute | Both | Could change shape or type |
| `count` vs positional arg | Both | Keyword arg enforcement |
| `no_response_expected` kwarg | Both | May be renamed or removed |

### 3.4 Coil/discrete read API

| Risk | Area | Notes |
|---|---|---|
| `read_coils` signature | Both | slave/device_id, count position |
| `read_discrete_inputs` signature | Both | Same |
| Response `.bits` attribute | Both | Could change type (list vs BooleanList) |

### 3.5 Register write API

| Risk | Area | Notes |
|---|---|---|
| `write_register` (single) | Both | Signature, slave/device_id |
| `write_registers` (multi) | Both | Values arg type, slave/device_id |

### 3.6 Exception handling

| Risk | Area | Notes |
|---|---|---|
| `ModbusIOException` hierarchy | Both | May move in exception tree |
| `ExceptionResponse` detection | Both | `isError()` vs `isinstance` |
| `ConnectionException` location | Both | Module path could change |
| `transaction_id` mismatch errors | TCP | May be surfaced differently |
| Timeout exception type | Both | `asyncio.TimeoutError` vs library type |

### 3.7 slave / device_id handling

pymodbus 3.x accepts `slave=<int>` on most calls; 4.x may rename to
`device_id` or handle it at client construction only. The integration
passes slave ID on each call in `transport/tcp.py` and `transport/rtu.py`.

### 3.8 RTU-specific

| Risk | Notes |
|---|---|
| Serial framer selection | `framer=ModbusRtuFramer` syntax may change |
| `serial_port` / `port` arg | May be renamed |
| Parity/stopbits kwargs | Could be wrapped in a SerialConfig object |

---

## 4. Integration-Specific Test Matrix

Before the pin can be lifted, every scenario below must pass on pymodbus 4.x.

| # | Scenario | Test file | Expected result |
|---|---|---|---|
| 1 | Setup connection (TCP) | `test_device_scanner_setup.py` | connect completes, no exception |
| 2 | Setup connection (RTU) | `test_device_scanner_setup.py` | connect completes, no exception |
| 3 | Normal update read cycle | `test_coordinator_lifecycle.py` | all registers returned correctly |
| 4 | Input register reads | `test_scanner_io_input.py` | `.registers` values correct |
| 5 | Holding register reads | `test_scanner_io_holding.py` | `.registers` values correct |
| 6 | Coil reads | `test_scanner_full_scan_coverage.py` | `.bits` values correct |
| 7 | Discrete input reads | `test_scanner_full_scan_coverage.py` | `.bits` values correct |
| 8 | Single register write | `test_coordinator_register_writes.py` | no exception, register updated |
| 9 | Multi-register write | `test_coordinator_register_writes.py` | same |
| 10 | Temporary airflow 3-register block write | `test_coordinator_register_writes.py` | atomic write of 3 registers |
| 11 | RTC clock sync write + readback | `test_coordinator_lifecycle.py` | clock registers written, readback matches |
| 12 | Scanner fallback (named → full) | `test_scanner_state.py` | fallback path exercised |
| 13 | `validate_known_registers` service | `test_services_handlers_parameters_registration.py` | no exception, result dict returned |
| 14 | `scan_all_registers` with throttle | `test_scanner_full_scan_coverage.py` | delay_between_requests respected |
| 15 | Reconnect after cancelled batch | `test_scanner_cancelled_batch_reconnect.py` | reconnect occurs, next read succeeds |
| 16 | Device unavailable → reconnect → shutdown | `test_device_scanner_errors.py` | no stale state, shutdown clean |

All tests must pass on pymodbus 4.x before the pin is lifted.
Mock-based tests must also be updated to reflect any changed API shape.

---

## 5. Migration Strategy

**Step 1 — Create a migration branch**

```bash
git checkout -b feature/pymodbus-4-migration
```

Do NOT touch `main` until the migration is complete and validated.

**Step 2 — Relax the pin on the branch only**

In `manifest.json`:
```json
"requirements": ["pymodbus>=3.6.0,<5.0"]
```

Or, to target 4.x explicitly during migration testing:
```json
"requirements": ["pymodbus>=4.0,<5.0"]
```

Do NOT commit this change to `main`.

**Step 3 — Install pymodbus 4.x and run full test suite**

```bash
pip install "pymodbus>=4.0,<5.0"
pytest tests/ -q --tb=long
```

Expect failures. Collect them all before fixing.

**Step 4 — Run focused Modbus transport tests**

```bash
pytest tests/ -k "scanner or transport or device_scanner or modbus" -q --tb=long
```

**Step 5 — Fix each failure in isolation**

- Do not change register addresses, entity IDs, or service IDs while fixing.
- Fix only the transport/client call-site changes needed for 4.x API compatibility.
- Keep 3.x-specific code paths if HA may still require 3.x.

**Step 6 — Test against real AirPack4 device**

Before merging:
- Install the migration branch in a real HA instance with an AirPack4 device.
- Verify all items in `docs/real_device_validation.md` section 3.
- Capture log evidence and commit it.

**Step 7 — Update manifest and docs**

Only after real-device validation:
- Update `manifest.json` pin.
- Update `docs/real_device_validation.md` with evidence.
- Update this document to reflect the completed migration.

---

## 6. Explicit Non-Goals

The following are explicitly out of scope for the migration:

- No current code migration (the `<4.0` pin remains in `main` until migration is complete).
- No removal of pymodbus 3.x support until the migration branch is validated.
- No broad refactoring of transport modules during dependency migration.
- No entity, register, service, or translation changes during migration.
- No fan percentage, temperature, or RTC sync behavior changes.
- No quality_scale upgrade during migration.
- No removal of mock-based tests — all tests must continue to pass.

---

## 7. Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API breakage in client construction | High | High | Branch-isolated testing |
| `slave` → `device_id` rename | Medium | Medium | Grep all call sites in `transport/` |
| Exception hierarchy change | Medium | High | Run full error-path tests |
| Response attribute change | Medium | High | Unit tests with real response objects |
| RTU serial framer change | Medium | Medium | RTU-specific integration test |
| HA pymodbus version conflict | Low | High | Monitor HA core requirements |

---

## 8. File References

Key files to audit during migration:

```
transport/tcp.py
transport/rtu.py
transport/base.py
core/connection.py
core/client_connection.py
```

These are the only files that import from `pymodbus` directly. The rest of
the integration is isolated from pymodbus internals.
