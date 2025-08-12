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
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    name = re.sub(r'(?<=\D)(\d)', r'_\1', name)
    name = re.sub(r'__+', '_', name)
    return name.lower()

def load_registers() -> Tuple[Dict[str, int], Dict[str, int]]:
    input_regs: Dict[str, int] = {}
    holding_regs: Dict[str, int] = {}
    with CSV_PATH.open(newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['Function_Code']
            if not code or code.startswith('#'):
                continue
            name = to_snake_case(row['Register_Name'])
            addr = int(row['Address_DEC'])
            if code == '04':
                input_regs[name] = addr
            elif code == '03':
                holding_regs[name] = addr
    input_regs = dict(sorted(input_regs.items(), key=lambda kv: kv[1]))
    holding_regs = dict(sorted(holding_regs.items(), key=lambda kv: kv[1]))
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
