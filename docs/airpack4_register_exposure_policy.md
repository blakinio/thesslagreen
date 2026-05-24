# AirPack4 Register Exposure Policy

This document describes the distinction between **register map coverage** and
**Home Assistant entity exposure**, and lists the policy for dangerous/action registers.

## Two layers of control

### Layer 1: Register map (`thessla_green_registers_full.json`)

The integration register map aims to include all vendor-documented registers so that:
- The coordinator can read/write any register on demand
- Services can reference registers by name
- Future entity additions do not require a new firmware-support cycle

A register being in the map does **not** mean it is exposed as an HA entity.

### Layer 2: Entity mappings (`mappings/`)

Only registers listed in entity mapping dictionaries (`SWITCH_ENTITY_MAPPINGS`,
`SELECT_ENTITY_MAPPINGS`, `NUMBER_ENTITY_MAPPINGS`, `SENSOR_ENTITY_MAPPINGS`, etc.)
are surfaced as HA entities visible to the user.

Registers in the map but absent from entity mappings are available for:
- Internal coordinator logic
- Developer/diagnostic services
- Future entity additions without code changes

## Dangerous / action register policy

The following registers require elevated caution. They are annotated here with
their current exposure status.

### Registers NOT exposed as entities (map only)

These are in the register map for completeness but are intentionally NOT exposed
as writable HA entities. They must not be added to entity mappings without a
dedicated security review.

| Register (integration name) | Vendor name | Reason |
|-----------------------------|-------------|--------|
| `filter_change_flag` / `filterChange` (write action) | `filterChange` | Write triggers filter replacement — destructive action |
| `lock_pass` (first word) | `lockPass1` | Device passphrase — security risk |
| `lockPass2` | `lockPass2` | Device passphrase — security risk |
| `uart_0_id` | `uart0Id` | Device bus ID — misconfiguration locks out device |
| `uart_1_id` | `uart1Id` | Device bus ID — misconfiguration locks out device |
| `deviceName` … `deviceName_8` | `deviceName`…`deviceName_8` | Multi-word string register — no safe HA entity type |

### Registers exposed as entities (pre-existing, intentional)

The following dangerous/action registers ARE exposed as HA entities. This is
pre-existing behavior that must not be removed without a deliberate breaking
change with a migration path.

| Register (integration name) | Entity type | Notes |
|-----------------------------|-------------|-------|
| `hard_reset_settings` | Switch | Resets device settings to factory defaults |
| `hard_reset_schedule` | Switch | Resets ventilation schedule to defaults |
| `configuration_mode` | Select | Enables/disables configuration mode |
| `access_level` | Select | Modbus access level control |
| `uart_0_baud` | Select | UART0 baud rate |
| `uart_0_parity` | Select | UART0 parity |
| `uart_0_stop` | Select | UART0 stop bits |
| `uart_1_baud` | Select | UART1 baud rate |
| `uart_1_parity` | Select | UART1 parity |
| `uart_1_stop` | Select | UART1 stop bits |
| `filter_change` | Select | Filter type selector (read: filter type; distinct from write-action filterChange) |
| `lock_flag` | Switch | Device lock state toggle |

### Alarm registers (read-only in practice, exposed as binary_sensor)

| Register | Vendor name | Notes |
|----------|-------------|-------|
| `e_197` | `E197` | Auto-reset alarm: installation regulation interrupted (FC03 0x20C7) |

## Risk metadata marking

Dangerous/advanced entities carry three optional fields in their mapping
dictionaries that are surfaced as `extra_state_attributes` at runtime:

| Field | Type | Values |
|-------|------|--------|
| `risk_level` | `str` | `"advanced"` |
| `risk_category` | `str` | `"destructive_action"`, `"communication_lockout"`, `"security_lock"`, `"advanced_configuration"` |
| `safety_warning` | `str` | Human-readable warning message |

These fields are set directly in the mapping dict of the entity (e.g. inside
`SWITCH_ENTITY_MAPPINGS`, `SELECT_ENTITY_MAPPINGS`, `UART_SELECT_ENTITY_MAPPINGS`,
`NUMBER_OVERRIDES`, or `TEXT_ENTITY_MAPPINGS`).  No changes are needed to the
platform files to propagate them — each platform's `extra_state_attributes`
property iterates over these three keys and includes any that are set.

Normal entities do **not** have these fields.  Absence of `risk_level` is the
signal that an entity is safe for everyday use.

The full inventory of marked entities is in
[`docs/airpack4_dangerous_entities_inventory.md`](airpack4_dangerous_entities_inventory.md).

## Adding new entity exposures for dangerous registers

Before exposing any of the "map only" registers as HA entities, ensure:

1. The register write semantics are safe for automation (idempotent, reversible)
2. A confirmation step or dedicated service handler exists if the action is destructive
3. The entity is disabled by default (`entity_registry_enabled_default=False`)
4. Tests cover the entity exposure and the write path
5. The change is documented in CHANGELOG.md
