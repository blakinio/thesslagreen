# Tools

## Sort register JSON file

The register file should remain deterministically ordered by Modbus function code
and decimal address. Run the helper below to enforce the ordering:

```bash
python tools/sort_registers_json.py
```

By default the script operates on
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
but an alternate path may be supplied as an argument. Other helper scripts import
this module to ensure the sorting logic lives in a single place.

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
