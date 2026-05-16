# Final architecture cleanup status

## Inventory
- Inspected all files under `custom_components/thessla_green_modbus` (maxdepth 3) and scanned references in `custom_components`, `tests`, `tools`, `docs`, and `README.md`.
- Confirmed legacy compatibility modules existed for modbus transport/helpers/exceptions and root-level scanner helpers.

## Changes completed
- Root-level scanner helper modules were moved into `scanner/` (`device_info.py`, `helpers.py`, `register_maps.py`) and imports were updated.
- Root-level `_transport_retry.py` was moved to `transport/retry_logging.py` and transport imports were updated.
- `modbus_exceptions.py` pure re-export shim was removed; consumers now import from `pymodbus.exceptions`.
- `except BaseException` retry path in config flow runtime was narrowed to `CancelledError` + `Exception`.

## Compatibility shims
- `modbus_transport.py` has been removed. All callers import directly from canonical `transport.*` modules.
- `modbus_helpers.py` has been removed. All callers import directly from canonical `core.*` modules.

## Const/entity lookup
- `const.py` dead re-exports removed: `_ENTITY_LOOKUP`, all 15 options symbols (BYPASS_MODES,
  DAYS_OF_WEEK, FILTER_TYPES, GWC_MODES, MODBUS_BAUD_RATES, MODBUS_PARITY, MODBUS_PORTS,
  MODBUS_STOP_BITS, OPTIONS_PATH, PERIODS, RESET_TYPES, SPECIAL_MODE_OPTIONS,
  _get_options_init_lock, _load_json_option, async_setup_options), `_build_map`,
  `multi_register_sizes`.
- `_build_entity_lookup` retained in const.py — used internally by `migrate_unique_id`.
- Register map functions (`coil_registers`, `discrete_input_registers`, `holding_registers`,
  `input_registers`) retained in const.py — used internally by `migrate_unique_id`.
- `entity_lookup.py` is the cache owner. Canonical: `.options`, `.registers.maps`.

## Risky areas intentionally not changed
- No coordinator runtime redesign was performed (audit-only).
- No Modbus protocol behavior, entity IDs, unique IDs, service IDs, or register naming behavior was intentionally changed.

## Validation status
- Real-device validation remains **pending**.
- Quality scale assertions remain self-assessed until checklist evidence is collected.
- Checklist pending: TCP connection, scan, temperatures, airflow, climate/fan entities, number/select writes, special modes, clock sync, HA restart/reload, and 30–60 minute polling log review.
