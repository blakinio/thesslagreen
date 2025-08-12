"""Generate registers.py from modbus_registers.csv."""

from __future__ import annotations

import csv
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "custom_components" / "thessla_green_modbus" / "data" / "modbus_registers.csv"
OUTPUT_PATH = ROOT / "custom_components" / "thessla_green_modbus" / "registers.py"


def to_snake_case(name: str) -> str:
    """Convert a register name from the CSV to ``snake_case``."""
    replacements = {"flowrate": "flow_rate"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r"[\s\-/]", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"(?<=\D)(\d)", r"_\1", name)
    name = re.sub(r"__+", "_", name)
    name = name.lower()
    token_map = {"temp": "temperature"}
    tokens = [token_map.get(token, token) for token in name.split("_")]
    return "_".join(tokens)


def _build_register_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    """Create a register map with unique names."""
    rows.sort(key=lambda r: r[1])
    counts: dict[str, int] = {}
    for name, _ in rows:
        counts[name] = counts.get(name, 0) + 1
    seen: dict[str, int] = {}
    result: dict[str, int] = {}
    for name, addr in rows:
        if counts[name] > 1:
            idx = seen.get(name, 0) + 1
            seen[name] = idx
            key = f"{name}_{idx}"
        else:
            key = name
        result[key] = addr
    return result


def load_registers() -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    """Load registers from the CSV grouped by function code."""
    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(
            row for row in f if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            code = row["Function_Code"]
            name = to_snake_case(row["Register_Name"])
            addr = int(row["Address_DEC"])
            if code == "01":
                coil_rows.append((name, addr))
            elif code == "02":
                discrete_rows.append((name, addr))
            elif code == "04":
                input_rows.append((name, addr))
            elif code == "03":
                holding_rows.append((name, addr))
    coils = _build_register_map(coil_rows)
    discrete_inputs = _build_register_map(discrete_rows)
    input_regs = _build_register_map(input_rows)
    holding_regs = _build_register_map(holding_rows)
    coils = dict(sorted(coils.items(), key=lambda kv: kv[1]))
    discrete_inputs = dict(sorted(discrete_inputs.items(), key=lambda kv: kv[1]))
    input_regs = dict(sorted(input_regs.items(), key=lambda kv: kv[1]))
    holding_regs = dict(sorted(holding_regs.items(), key=lambda kv: kv[1]))
    return coils, discrete_inputs, input_regs, holding_regs


def write_file(
    coils: dict[str, int],
    discrete_inputs: dict[str, int],
    input_regs: dict[str, int],
    holding_regs: dict[str, int],
) -> None:
    """Write the registers module to :data:`OUTPUT_PATH`."""
    with OUTPUT_PATH.open("w", newline="\n") as f:
        f.write('"""Register definitions for the ThesslaGreen Modbus integration."""\n\n')
        f.write("from __future__ import annotations\n\n")
        f.write("# Generated from modbus_registers.csv\n\n")
        sections = [
            ("COIL_REGISTERS", coils),
            ("DISCRETE_INPUT_REGISTERS", discrete_inputs),
            ("INPUT_REGISTERS", input_regs),
            ("HOLDING_REGISTERS", holding_regs),
        ]
        for idx, (name, mapping) in enumerate(sections):
            f.write(f"{name}: dict[str, int] = {{\n")
            for key, addr in mapping.items():
                f.write(f'    "{key}": {addr},\n')
            if name == "HOLDING_REGISTERS":
                f.write("}\n")
            elif name == "INPUT_REGISTERS":
                f.write("}\n\n\n")
            else:
                f.write("}\n\n")


def main() -> None:
    coils, discrete_inputs, input_regs, holding_regs = load_registers()
    write_file(coils, discrete_inputs, input_regs, holding_regs)


if __name__ == "__main__":
    main()
