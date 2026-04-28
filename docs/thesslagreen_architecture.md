# ThesslaGreen Modbus — Architecture Overview

## Goal
The architecture separates Home Assistant integration concerns from device/protocol logic.
Home Assistant should remain a thin adapter layer.

## Layers
- **HA Layer**: entry lifecycle, entity platforms, config flow, services, diagnostics/repairs.
- **Coordinator**: HA-facing update orchestration and availability state.
- **Core**: device domain logic (`read_snapshot`, `write`, capability scan orchestration).
- **Registers**: register definitions, schema, loader, codec, read planning.
- **Scanner**: capability/model/firmware probing logic.
- **Transport**: Modbus TCP/RTU/RTU-over-TCP communication and retry strategy.

## Dependency direction
HA platforms → Coordinator → Core → (Registers + Scanner) → Transport → Modbus client/socket.

## Forbidden dependencies
- `core/`, `transport/`, `registers/`, `scanner/` must not import Home Assistant.
- `coordinator/` must not execute direct Modbus I/O.

## Migration decisions
- No migration shims.
- Legacy logic should be rewritten into target layers and removed after migration.

## Non-negotiable rules
- `core/transport/registers/scanner` do not import Home Assistant.
- `coordinator` does not perform direct Modbus I/O.
- HA platforms do not decode raw register values.
- Register JSON is the source of truth for register definitions.
