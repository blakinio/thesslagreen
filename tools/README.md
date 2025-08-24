# Tools

## Sort register JSON file

The register file should remain deterministically ordered by Modbus function code
and decimal address. Run the helper below to enforce the ordering:

```bash
python tools/sort_registers_json.py
```

By default the script operates on
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
but an alternate path may be supplied as an argument.
