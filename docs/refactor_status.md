# Refactor status (current)

Last reviewed: 2026-04-28.

## Scope and direction

The project is in an incremental refactor toward layered architecture:

- HA layer (platforms, flows, services, diagnostics)
- coordinator (HA adapter)
- core (device/domain logic)
- registers (definitions + codec + planning)
- scanner (capability discovery)
- transport (Modbus I/O)

## Hard constraints

The following constraints are active and must be preserved:

1. No legacy modules.
2. No compatibility shims.
3. No re-export shims.
4. No proxy modules.
5. `core/`, `transport/`, `registers/`, and `scanner/` must not import Home Assistant.
6. `coordinator.py` must not be moved yet.

## Current transitional note

Both forms currently exist in the repository:

- `custom_components/thessla_green_modbus/coordinator.py`
- `custom_components/thessla_green_modbus/coordinator/`

This is a temporary refactor stage. Until migration is complete, `coordinator.py` remains in place and should not be relocated.

## Documentation policy for refactor work

- Keep architecture docs aligned with real repository state.
- Do not document unsupported devices or speculative features.
- Do not create migration guides unless real migration code exists.
