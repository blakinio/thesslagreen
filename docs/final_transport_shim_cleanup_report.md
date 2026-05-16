# Final Transport Shim Cleanup Report

Branch: `claude/remove-final-shim-Kn2oC`
Base: `main`

## Objective

Remove the root-level compatibility shim
`custom_components/thessla_green_modbus/modbus_transport.py`
and all stale references to it.

## Finding: Shim Was Already Removed

The file `modbus_transport.py` was deleted in a prior commit (`ed88bb3c` —
"fix: repair broken transport imports and remove modbus_transport shim").
It does not exist on `main`. No production code, test code, or tooling
actively imports from it.

This pass removed the **three stale references** left over from when the
file existed.

## Changes Made

### 1. `tools/check_maintainability.py` — removed stale `STRICT_PATH_LIMITS` entry

The dict contained an entry for `modbus_transport.py` with custom size limits
`(930, 210)`. Since the file no longer exists the entry was dead code and
was removed.

### 2. `tests/test_error_contract.py` — updated logger name string

`test_cross_layer_retry_logging_contract` passed an arbitrary logger to
`log_transport_retry` using the old module path as its name:

```python
# Before
logger=logging.getLogger("custom_components.thessla_green_modbus.modbus_transport"),

# After
logger=logging.getLogger("custom_components.thessla_green_modbus.transport.retry_logging"),
```

The logger name is an arbitrary string (not an import); the test assertion
checks only for `"layer=transport"` in the output, not the logger name.
Updated to the canonical module where `log_transport_retry` is implemented.

### 3. `docs/final_architecture_cleanup.md` — corrected outdated claim

Updated the "Compatibility shims" section from "remains as a minimal shim"
to "has been removed. All callers import directly from canonical `transport.*`
modules."

## Canonical Transport Import Paths Now Used Everywhere

| Formerly from shim | Now from canonical module |
|--------------------|--------------------------|
| `calculate_backoff` | `transport.retry` |
| `classify_transport_error` | `transport.retry` |
| `should_retry` | `transport.retry` |
| `ErrorKind` | `transport.retry` |
| `RetryDecision` | `transport.retry` |
| `log_transport_retry` | `transport.retry_logging` |
| `apply_transport_backoff` | `transport.retry_logging` |

## Validation Results

| Check | Result |
|-------|--------|
| `python -m compileall -q custom_components tests tools` | PASS |
| `ruff check custom_components tests tools` | PASS |
| `ruff check --select I custom_components tests tools` | PASS |
| `ruff format --check custom_components tests tools` | PASS (432 files formatted) |
| `python tools/check_maintainability.py` | PASS |
| `python tools/check_translations.py` | PASS |
| `python tools/compare_registers_with_reference.py` | PASS (62 extras expected; 242 name mismatches pre-existing) |
| No merge conflict markers | PASS |
| No remaining `modbus_transport` active imports | PASS |
| No remaining compatibility shim markers in production code | PASS |

### pytest Environment Limitation

The environment runs Python 3.11.15.
`pytest-homeassistant-custom-component>=0.13.309` requires Python >= 3.12 and
could not be installed. pytest is not available in this environment.
Compilation and static analysis pass; runtime test results must be verified
in a Python 3.12+ CI environment.

## Confirmed No Behavior Changes

- No Modbus register addresses changed
- No register names changed
- No entity IDs changed
- No unique IDs changed
- No service IDs changed
- No translation keys changed
- No config/options flow behavior changed
- No new compatibility shims created

## Remaining Compatibility Surfaces

None. All references to `modbus_transport` are now exclusively:

- Historical notes in previously-written documentation files
- `test_modbus_transport_*.py` file names and docstrings (which are
  historical labels — the files import from canonical `transport.*` modules)

## Recommended Next Step

Real-device validation against a ThesslaGreen AirPack unit running HA with
this integration to confirm no regression in register reads, entity values,
or coordinator scan/update behavior.
