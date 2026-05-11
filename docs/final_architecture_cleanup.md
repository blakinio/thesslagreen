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
- `modbus_transport.py` remains as a minimal shim to avoid abrupt external breakage; it now directly re-exports from canonical `transport.retry`.
- `modbus_helpers.py` remains due to broad test and potential external compatibility surface; future removal should be staged.

## Const/entity lookup
- `const.py` compatibility wrapper block for `_ENTITY_LOOKUP` and unique-id wrappers removed.
- `entity_lookup.py` is now the cache owner.

## Risky areas intentionally not changed
- No coordinator runtime redesign was performed (audit-only).
- No Modbus protocol behavior, entity IDs, unique IDs, service IDs, or register naming behavior was intentionally changed.

## Validation status
- Real-device validation remains **pending**.
- Quality scale assertions remain self-assessed until checklist evidence is collected.
- Checklist pending: TCP connection, scan, temperatures, airflow, climate/fan entities, number/select writes, special modes, clock sync, HA restart/reload, and 30–60 minute polling log review.
