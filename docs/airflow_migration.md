# Airflow migration

## Why migration exists
Airflow-related entities and semantics were adjusted to align runtime data representation and integration behavior.

## What changed
TODO: verify exact airflow migration scope from migration code.

## Old entities
TODO: verify exact old entity names from migration code.

## New entities
TODO: verify exact new entity names from migration code.

## How to verify after upgrade
- Open entity registry for integration entities.
- Confirm expected airflow entities are present and updating.
- Check history/statistics continuity where applicable.

## Troubleshooting
- If entities are missing, run capability scan and check diagnostics.
- If stale IDs remain, remove disabled/obsolete entities manually after verification.

## Rollback / manual cleanup
TODO: verify supported rollback path from code/release notes.
