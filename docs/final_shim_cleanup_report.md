# Final Shim Cleanup Report

Branch: `refactor/remove-final-shims`  
Base: `main`

## Removed Shim Files

| File | Reason for removal |
|------|--------------------|
| `custom_components/thessla_green_modbus/coordinator/io.py` | Pure re-export shim; no callers remained after coordinator/coordinator.py was already using `core.io_mixin` directly |
| `custom_components/thessla_green_modbus/coordinator/capabilities.py` | Partial re-export shim; two test callers updated to use canonical path |

## Import Paths Migrated

| File | Old import | New import |
|------|-----------|------------|
| `tests/test_coordinator_update.py` | `coordinator.capabilities._clamp_percentage` etc. | `core.capabilities_mixin._clamp_percentage` etc. |
| `tests/test_clock_sync.py` | `coordinator.capabilities._CoordinatorCapabilitiesMixin` | `core.capabilities_mixin._CoordinatorCapabilitiesMixin` |

Note: `tests/test_coordinator_update.py` was importing four helper functions
(`_clamp_percentage`, `_coerce_bypass_open`, `_flow_balance_status`,
`_normalise_capability_flag`) from `coordinator.capabilities`, but those functions
were never re-exported by that shim (the shim only exported `_CoordinatorCapabilitiesMixin`).
This was a pre-existing broken import; the canonical path in `core.capabilities_mixin` fixes it.

## Docstrings Updated

- `core/io_mixin.py` — removed stale mention of `coordinator/io.py` re-export
- `core/capabilities_mixin.py` — removed stale mention of `coordinator/capabilities.py` re-export

## Import Sorting Fixed

Ruff (isort) auto-corrected two import-block orderings broken by placing the
newly-direct `core.*` imports after `..utils` in:

- `coordinator/coordinator.py`
- `core/client.py`

## Remaining Compatibility Surfaces

None introduced by this PR.

`coordinator.capabilities` appearing in production code and tests refers to the
`.capabilities` **attribute** on `ThesslaGreenModbusCoordinator` instances (a
`DeviceCapabilities` object), not an import from the deleted module.

## Validation Results

| Check | Result |
|-------|--------|
| `python -m compileall -q custom_components tests tools` | PASS |
| `ruff check custom_components tests tools` | PASS |
| `ruff check --select I custom_components tests tools` | PASS |
| `ruff format --check custom_components tests tools` | PASS (432 files formatted) |
| `python tools/compare_registers_with_reference.py` | PASS (62 extras expected; 242 name mismatches pre-existing) |
| `python tools/check_maintainability.py` | PASS |
| `python tools/validate_entity_mappings.py` | PASS (366 entities) |
| `python tools/check_translations.py` | PASS |

### pytest Environment Limitation

The environment runs Python 3.11.15. `pytest-homeassistant-custom-component>=0.13.309`
requires Python >= 3.12 and could not be installed. pytest was not available.
Compilation and static analysis pass; runtime test results are unavailable in this
environment and should be run in a Python 3.12+ CI environment.

## Confirmed No Behavior Changes

- No Modbus register addresses changed
- No register names changed
- No entity IDs changed
- No unique IDs changed
- No service IDs changed
- No translation keys changed
- No config/options flow behavior changed
- No new compatibility shims created
- `modbus_helpers.py` not reintroduced

## Remaining Architectural Debt

None. `modbus_transport.py` was removed in commit `864539f6` (PR #1639).
See `docs/final_transport_shim_cleanup_report.md` for the full removal record.

## Recommended Next Step

Real-device validation against a ThesslaGreen AirPack unit running HA with this
integration to confirm no regression in register reads, entity values, or
coordinator scan/update behavior.
