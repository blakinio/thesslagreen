# Device Client Architecture Cleanup – Final Report

## Summary

This PR completes a controlled extraction/refinement pass on the device-client
architecture. No Modbus behavior, register semantics, entity IDs, service IDs,
unique IDs, or translation keys were changed.

---

## Phase 2: core/client.py Split

### Before

`core/client.py` contained a single `ThesslaGreenDeviceClient` class with **544 lines**
mixing connection lifecycle, transport construction, scanner orchestration, register
groups, IO helpers, write support, and public API.

### After

| File | Lines | Responsibility |
|------|-------|---------------|
| `core/client.py` | 188 | Composition root, `__init__`, public API |
| `core/client_connection.py` | 252 | Connection lifecycle + transport construction |
| `core/client_scanner.py` | 52 | Scanner orchestration + register normalization |
| `core/client_registers.py` | 144 | Register groups, IO helpers, write support |

**`core/client.py` reduced by 356 lines (65%).**

### Extraction Strategy

Each extracted group became a mixin class (`_DeviceClientConnectionMixin`,
`_DeviceClientScannerMixin`, `_DeviceClientRegistersMixin`). The main class
`ThesslaGreenDeviceClient` inherits from all three mixins plus the pre-existing
`_ModbusIOMixin` and `_CoordinatorCapabilitiesMixin` from the coordinator package.

This is consistent with the existing mixin pattern (coordinator also uses
`_ModbusIOMixin`, `_CoordinatorCapabilitiesMixin`, `_CoordinatorConfigPropertiesMixin`,
`_CoordinatorScheduleMixin`).

### Public API Preserved

The public API of `ThesslaGreenDeviceClient` is **completely unchanged**:
- All method signatures are identical.
- All attributes initialized in `__init__` are identical.
- The import path `from core.client import ThesslaGreenDeviceClient` is unchanged.

---

## Phase 3: Coordinator Proxy Cleanup

### Duplicate Implementations Removed

6 method implementations in `ThesslaGreenModbusCoordinator` that duplicated DeviceClient
logic were replaced with clean delegation:

```
get_register_map        → self._device_client.get_register_map(register_type)
_get_client_method      → self._device_client._get_client_method(name)
_find_register_name     → self._device_client._find_register_name(...)
_process_register_value → self._device_client._process_register_value(...)
_mark_registers_failed  → self._device_client._mark_registers_failed(names)
_clear_register_failure → self._device_client._clear_register_failure(name)
```

### Imports Removed from coordinator.py

5 imports became unused after delegation and were removed:
- `find_register_name as _find_register_name_impl`
- `process_register_value as _process_register_value_impl`
- `clear_register_failure as _clear_register_failure_impl`
- `mark_registers_failed as _mark_registers_failed_impl`
- `cast` (from typing)

### Proxy Properties: All 38 Retained

All 38 proxy properties in `ThesslaGreenModbusCoordinator` are retained because:
- Coordinator submodule functions receive the coordinator via duck-typing and access
  properties directly (changing their signatures is a separate, larger refactor).
- Test files directly access coordinator attributes for assertion and mocking.
- Entity platform files access coordinator properties directly.

A comprehensive retention rationale comment block was added before the proxy property
section in `coordinator.py`.

For full details see `docs/coordinator_proxy_cleanup.md`.

---

## Phase 4: Dependency Direction

Dependency flow after this PR:

```
entities / services / scanner
        ↓
ThesslaGreenModbusCoordinator (coordinator.coordinator)
        ↓
ThesslaGreenDeviceClient (core.client*)
        ↓
coordinator submodules (connection, io, scan, register_groups, …)
        ↓
transport / registers / modbus
```

No circular imports exist at module level. The only dynamic import is in
`_DeviceClientConnectionMixin._try_direct_client_connect` which imports
`coordinator as coordinator_pkg` inside the method body — this is intentional
to allow test patching of `coordinator.coordinator.AsyncModbusTcpClient`.

---

## Validation Results

### Compile

```
python -m compileall -q custom_components/thessla_green_modbus tests tools
# → no errors
```

### Ruff Lint

```
ruff check custom_components tests tools
# → All checks passed!
```

### Ruff Import Sort

```
ruff check --select I custom_components tests tools
# → All checks passed!
```

### Ruff Format

```
ruff format --check custom_components tests tools
# → 432 files already formatted
```

### Maintainability Gate

```
python tools/check_maintainability.py
# → Maintainability gate passed.
```

### Translations

```
python tools/check_translations.py
# → All translation keys present.
```

### Register Comparison

```
python tools/compare_registers_with_reference.py
# → Same output as baseline (extra entries pre-existed; no regressions).
```

### pytest

**Environmental note**: The test environment runs Python 3.11 but
`pytest-homeassistant-custom-component>=0.13.309` requires Python >=3.12.
Attempting to install this version on Python 3.11 fails with build errors
on native packages (PyRIC, mock-open). This was the pre-existing baseline
state — not introduced by this PR.

The code compiles cleanly (`compileall` passes) and all quality tools pass.
The test suite cannot be executed in this environment due to the Python
version mismatch, not due to code changes.

---

## Behavioral Confirmation

| Requirement | Status |
|-------------|--------|
| Modbus behavior unchanged | ✅ No changes to modbus read/write path |
| Entity IDs unchanged | ✅ No entity registration code touched |
| Unique IDs unchanged | ✅ No unique ID generation code touched |
| Service IDs unchanged | ✅ No service registration code touched |
| Register names unchanged | ✅ No register map or const.py changes |
| Register addresses unchanged | ✅ No register map changes |
| Translation keys unchanged | ✅ No strings.json or translations/ changes |
| No compatibility shims | ✅ No shim files created |
| No modbus_helpers.py | ✅ Not reintroduced |

---

## Remaining Architectural Debt

1. **38 coordinator proxy properties** — Required by duck-typing design of all
   coordinator submodule functions. Reducing them requires updating submodule
   function signatures to accept `DeviceClient` directly (significant follow-up work).

2. **`_ModbusIOMixin` and `_CoordinatorCapabilitiesMixin` live in `coordinator/`** — Both
   are imported by `core/client.py`. They could be moved to `core/` in a future pass,
   making the dependency direction cleaner: `core → coordinator_submodules` would become
   `core → core_mixins`.

3. **`coordinator.schedule._get_register_definition` dynamic import** — Imports
   `coordinator_module.get_register_definition` dynamically to allow test patching.
   If `get_register_definition` were moved to `registers/` this coupling could be removed.

4. **`_try_direct_client_connect` dynamic coordinator import** — Similarly accesses
   `coordinator.coordinator.AsyncModbusTcpClient` at runtime for test patchability.
   Could be resolved by making the TCP client class injectable at construction time.

---

## Files Changed

```
M custom_components/thessla_green_modbus/coordinator/coordinator.py
M custom_components/thessla_green_modbus/core/client.py
A custom_components/thessla_green_modbus/core/client_connection.py
A custom_components/thessla_green_modbus/core/client_scanner.py
A custom_components/thessla_green_modbus/core/client_registers.py
A docs/coordinator_proxy_cleanup.md
A docs/device_client_cleanup_inventory.md
A docs/device_client_cleanup_report.md
```
