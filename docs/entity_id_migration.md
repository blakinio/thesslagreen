# Entity ID migration

## Why this migration exists
Entity IDs may need controlled migration when naming rules or mapping strategy changes.

## What is migrated
TODO: verify migration scope from code (`custom_components/thessla_green_modbus/__init__.py` and migration helpers).

## What is not migrated
TODO: verify exclusions from migration code.

## How to check migration result
- Open entity registry after upgrade.
- Verify entity IDs expected by dashboards/automations.
- Check logs for migration warnings/errors.

## Known limitations
TODO: verify known limitations from code and changelog.

## Troubleshooting
- If IDs did not migrate as expected, inspect integration logs and diagnostics.
- Re-link automations/scripts to current entity IDs if required.
