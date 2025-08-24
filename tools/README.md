# Tools

## One-way CSV → JSON conversion workflow

`modbus_registers.csv` is a developer-only artifact used to generate the JSON register file consumed by the integration.

1. Edit `tools/modbus_registers.csv` as needed.
2. Run `python tools/convert_registers_csv_to_json.py`.
   - Input: `tools/modbus_registers.csv`
   - Output: `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
3. Commit the updated JSON file.

The CSV file is excluded from packages and must not be imported or accessed at runtime. The conversion is one-way: runtime code reads only the generated JSON.

## Sort register JSON file

The register file should remain deterministically ordered by Modbus function code
and decimal address. Run the helper below to enforce the ordering:

```bash
python tools/sort_registers_json.py
```

By default the script operates on
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
but an alternate path may be supplied as an argument.
