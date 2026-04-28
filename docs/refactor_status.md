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

Current active coordinator location:

- `custom_components/thessla_green_modbus/coordinator.py`

Current repository state:

- `custom_components/thessla_green_modbus/coordinator/` is **not present**.
- The old empty `coordinator/` scaffold was removed because it shadowed `coordinator.py` and broke imports.

Transition rule (current):

- `coordinator.py` remains in place and must not be moved in this stage.
- `coordinator/` must not be recreated until a dedicated future PR performs a real migration to a package layout.
- That future migration must update imports directly and must not use compatibility shims, re-export shims, or proxy modules.

## Documentation policy for refactor work

- Keep architecture docs aligned with real repository state.
- Do not document unsupported devices or speculative features.
- Do not create migration guides unless real migration code exists.
