# Tools

Recurring validators/generators run by CI, the `validate-registers` pre-commit
hook, or `CLAUDE.md` §5. One-shot / manual utilities live in
[`tools/manual/`](manual/README.md) and are **not** part of the automated
pipeline.

## Validate register schema (smoke-check)

Run lightweight validation (without bootstrapping full Home Assistant):

```bash
pip install -r requirements-test-min.txt
python tools/validate_registers.py
```

The same command is wired into pre-commit via the `validate-registers` hook.

## Maintainability gate

```bash
python tools/check_maintainability.py
```

Checks file and function size thresholds (with configurable limits via CLI flags).

## Other recurring validators

| Script | Purpose |
|---|---|
| `validate_entity_mappings.py` | Verify entity mappings against the register map. |
| `check_translations.py` | Check translation keys are present and in sync across locales. |
| `compare_registers_with_reference.py` | Compare the register map with the vendor reference (`--show-renames`). |
| `compare_airpack4_vendor_coverage.py` | Regenerate and diff the AirPack4 vendor coverage docs. |
| `validate_dashboard_entities.py` | Validate entities referenced by `example_dashboard.yaml`. |

## Manual / one-shot tools

The register-JSON sorter (`sort_registers_json.py`), the strings generator
(`generate_strings.py`), and the entity-registry cleanup helper
(`cleanup_old_entities.py`) are manual utilities and now live in
[`tools/manual/`](manual/README.md).
