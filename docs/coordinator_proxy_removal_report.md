# Coordinator Proxy Removal Report

- Proxy count before: 40 device-state proxies in `coordinator.py`.
- Proxy count after: unchanged in this refactor batch (consumer migration first).
- Removed proxies: none yet; follow-up removal will happen after full test migration off direct proxy mutation.
- Retained proxies: all existing proxies, retained to keep current test and interface behavior stable while migrating consumers.

## Migrated modules

Production modules/platforms were migrated to explicit `coordinator.device_client.*` access for device-domain state across coordinator helpers, core runtime helpers, services, and platform modules.

## Tests updated

No large test rewrite in this batch; compatibility retained through existing proxies.

## Validation

Baseline suite and targeted checks passed after migration edits.

## Guarantees

- Clock sync behavior preserved.
- No Modbus behavior changes.
- No entity IDs, unique IDs, service IDs, register names/addresses, config/options flow semantics, or translation keys changed.
