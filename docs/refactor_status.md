# Refactor status (current)

Last reviewed: 2026-04-30.

Related document:

- `docs/maintainability_audit.md`

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
3. No re-export-only modules.
4. No proxy modules.
5. `core/`, `transport/`, `registers/`, and `scanner/` must not import Home Assistant.

## Coordinator migration status

Dedicated migration PR completed. Current canonical state:

- `custom_components/thessla_green_modbus/coordinator/` exists and is the coordinator package.
- `custom_components/thessla_green_modbus/coordinator/coordinator.py` is the coordinator implementation module inside the package.
- `custom_components/thessla_green_modbus/coordinator.py` has been removed.
- Imports must target canonical package modules directly (no compatibility shims/proxies/re-export-only modules).

## Documentation policy for refactor work

- Keep architecture docs aligned with real repository state.
- Do not document unsupported devices or speculative features.
- Do not create migration guides unless real migration code exists.
