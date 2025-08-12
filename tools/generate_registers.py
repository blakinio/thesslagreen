#!/usr/bin/env python3
"""Generate registers.py from modbus_registers.csv."""
import csv
import pathlib
import re
from typing import Dict, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / 'modbus_registers.csv'
OUTPUT_PATH = ROOT / 'custom_components' / 'thessla_green_modbus' / 'registers.py'

def to_snake_case(name: str) -> str:
    """Convert register name from CSV to snake_case."""
    replacements = {
        'flowrate': 'flow_rate',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r'[\s\-/]', '_', name)
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    name = re.sub(r'(?<=\D)(\d)', r'_\1', name)
    name = re.sub(r'__+', '_', name)
    return name.lower()

def _build_register_map(rows: list[tuple[str, int]]) -> Dict[str, int]:
    """Create a register map with unique names.

    When the same register name appears multiple times in the CSV, append a
    numeric suffix to make the identifier unique. The suffix starts at 1 to
    match existing expectations in the integration (e.g. ``device_name_1``).
    """

    rows.sort(key=lambda r: r[1])
    name_counts: Dict[str, int] = {}
    for name, _ in rows:
        name_counts[name] = name_counts.get(name, 0) + 1

    seen: Dict[str, int] = {}
    result: Dict[str, int] = {}
    for name, addr in rows:
        if name_counts[name] > 1:
            index = seen.get(name, 0) + 1
            seen[name] = index
            unique = f"{name}_{index}"
        else:
            unique = name
        result[unique] = addr
    return result


def load_registers() -> Tuple[Dict[str, int], Dict[str, int]]:
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []
    with CSV_PATH.open(newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['Function_Code']
            if not code or code.startswith('#'):
                continue
            name = to_snake_case(row['Register_Name'])
            addr = int(row['Address_DEC'])
            if code == '04':
                input_rows.append((name, addr))
            elif code == '03':
                holding_rows.append((name, addr))
    input_regs = _build_register_map(input_rows)
    holding_regs = _build_register_map(holding_rows)
    return input_regs, holding_regs

def write_file(input_regs: Dict[str, int], holding_regs: Dict[str, int]) -> None:
    with OUTPUT_PATH.open('w', newline='\n') as f:
        f.write("\"\"\"Register definitions for the ThesslaGreen Modbus integration.\"\"\"\n")
        f.write("from typing import Dict\n\n")
        f.write("# Generated from modbus_registers.csv\n")
        f.write("INPUT_REGISTERS: Dict[str, int] = {\n")
        for name, addr in input_regs.items():
            f.write(f"    '{name}': {addr},\n")
        f.write("}\n\n")
        f.write("HOLDING_REGISTERS: Dict[str, int] = {\n")
        for name, addr in holding_regs.items():
            f.write(f"    '{name}': {addr},\n")
        f.write("}\n")


def main() -> None:
    input_regs, holding_regs = load_registers()
    write_file(input_regs, holding_regs)

if __name__ == '__main__':
    main()
