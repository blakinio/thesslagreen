"""Generate registers.py from modbus_registers.csv."""


from __future__ import annotations
import csv
import pathlib
import re
from typing import Dict, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "custom_components" / "thessla_green_modbus" / "modbus_registers.csv"
OUTPUT_PATH = ROOT / "custom_components" / "thessla_green_modbus" / "registers.py"

# Legacy names mapped to their canonical versions
ALIASES = {
    "required_temp": "required_temperature",
    "supply_air_temperature_manual": "comfort_temperature",
}

# CSV names that should be renamed to canonical forms
RENAMES = {
    "supply_air_temperature_manual": "comfort_temperature",
}
def to_snake_case(name: str) -> str:
    """Convert a register name from the CSV to ``snake_case``.

    This mirrors the helper used in the tests to ensure consistent naming.
    """

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

def _build_register_map(rows: list[tuple[str, int]]) -> Dict[str, int]:
    """Create a register map with unique names.

    When the same register name appears multiple times in the CSV, append a
    numeric suffix to make the identifier unique. The suffix starts at 1 to
    match existing expectations in the integration (e.g. ``device_name_1``).
    """
def _build_register_map(rows: list[tuple[str, int]]) -> Dict[str, int]:
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


def _load_all_registers() -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, int]]:
    """Load register definitions from the CSV file."""

    coils: list[tuple[str, int]] = []
    discrete_inputs: list[tuple[str, int]] = []
    input_regs: list[tuple[str, int]] = []
    holding_regs: list[tuple[str, int]] = []
=======
def load_registers() -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, int]]:
    """Load registers from the CSV grouped by function code."""

    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []

    with CSV_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Function_Code"]
            if not code or code.startswith("#"):
                continue
            name = to_snake_case(row["Register_Name"])
            name = RENAMES.get(name, name)
            addr = int(row["Address_DEC"])
            if code == "01":

                coils.append((name, addr))
            elif code == "02":
                discrete_inputs.append((name, addr))
            elif code == "04":
                input_regs.append((name, addr))
            elif code == "03":
                holding_regs.append((name, addr))

    return (
        _build_register_map(coils),
        _build_register_map(discrete_inputs),
        _build_register_map(input_regs),
        _build_register_map(holding_regs),
    )


def load_registers() -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return input and holding register maps.

    This helper is used by unit tests that only need these two mappings.
    """

    _, _, input_regs, holding_regs = _load_all_registers()
    return input_regs, holding_regs

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

    for alias, canonical in ALIASES.items():
        for mapping in (coils, discrete_inputs, input_regs, holding_regs):
            if canonical in mapping:
                mapping[alias] = mapping[canonical]

    coils = dict(sorted(coils.items(), key=lambda kv: kv[1]))
    discrete_inputs = dict(sorted(discrete_inputs.items(), key=lambda kv: kv[1]))
    input_regs = dict(sorted(input_regs.items(), key=lambda kv: kv[1]))
    holding_regs = dict(sorted(holding_regs.items(), key=lambda kv: kv[1]))
    return coils, discrete_inputs, input_regs, holding_regs



def write_file(
    coils: Dict[str, int],
    discrete_inputs: Dict[str, int],
    input_regs: Dict[str, int],
    holding_regs: Dict[str, int],
) -> None:

    """Write the registers module to :data:`OUTPUT_PATH`."""

    """Write the registers module."""


    with OUTPUT_PATH.open("w", newline="\n") as f:
        f.write('"""Register definitions for the ThesslaGreen Modbus integration."""\n\n')
        f.write("from typing import Dict\n\n")
        f.write("# Generated from modbus_registers.csv\n")
        for name, mapping in [
            ("COIL_REGISTERS", coils),
            ("DISCRETE_INPUT_REGISTERS", discrete_inputs),
            ("INPUT_REGISTERS", input_regs),
            ("HOLDING_REGISTERS", holding_regs),
        ]:
            f.write(f"{name}: Dict[str, int] = {{\n")
            for key, addr in mapping.items():
                f.write(f"    '{key}': {addr},\n")
            f.write("}\n\n")


def main() -> None:
    coils, discrete_inputs, input_regs, holding_regs = _load_all_registers()
    write_file(coils, discrete_inputs, input_regs, holding_regs)


if __name__ == "__main__":
    main()

