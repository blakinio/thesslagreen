"""Generate a legacy ``registers.py`` module from the JSON register data.

``thessla_green_registers_full.json`` is the canonical source of register
definitions and is used directly by the integration.  This helper script is
only needed when a static Python mapping is required for debugging or external
tools.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Path to the canonical JSON register definition file bundled with the
# integration.  ``registers.py`` is generated from this file and should never be
# edited manually.
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)
OUTPUT_PATH = ROOT / "custom_components" / "thessla_green_modbus" / "registers.py"


def sort_registers_json() -> None:
    """Sort the canonical JSON register file.

    The file is ordered first by Modbus function code and then by the
    decimal address to ensure deterministic diffs and easier manual
    inspection.
    """

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    registers = data.get("registers", data)
    registers.sort(
        key=lambda r: (int(str(r["function"])), int(r["address_dec"]))
    )
    JSON_PATH.write_text(
        json.dumps({"registers": registers}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _to_snake_case(name: str) -> str:
    """Convert register names to snake_case."""
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


def _normalise_name(name: str) -> str:
    fixes = {
        "duct_warter_heater_pump": "duct_water_heater_pump",
        "required_temp": "required_temperature",
        "specialmode": "special_mode",
    }
    snake = _to_snake_case(name)
    return fixes.get(snake, snake)


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


SNAKE_CASE = re.compile(r"^[a-z0-9_]+$")


def load_registers() -> tuple[
    dict[str, int], dict[str, int], dict[str, int], dict[str, int], dict[str, int]
]:
    """Load registers from the JSON file grouped by function."""
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    registers = data.get("registers", data)
    for reg in registers:
        name = reg["name"]
        if not SNAKE_CASE.fullmatch(name):
            raise ValueError(f"Register name '{name}' is not snake_case")

    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []
    multi_rows: list[tuple[str, str, int, int]] = []

    for reg in registers:
        name = _normalise_name(reg["name"])
        addr = int(reg["address_dec"])
        func_raw = str(reg["function"]).lower()
        length = int(reg.get("length", 1))

        if func_raw in {"01", "coil"}:
            coil_rows.append((name, addr))
            func = "coil"
        elif func_raw in {"02", "discrete"}:
            discrete_rows.append((name, addr))
            func = "discrete"
        elif func_raw in {"04", "input"}:
            input_rows.append((name, addr))
            func = "input"
        elif func_raw in {"03", "holding"}:
            holding_rows.append((name, addr))
            func = "holding"
        else:  # pragma: no cover - defensive
            continue

        if length > 1:
            multi_rows.append((func, name, addr, length))

    coils = _build_register_map(coil_rows)
    discrete_inputs = _build_register_map(discrete_rows)
    input_regs = _build_register_map(input_rows)
    holding_regs = _build_register_map(holding_rows)

    coils = dict(sorted(coils.items(), key=lambda kv: kv[1]))
    discrete_inputs = dict(sorted(discrete_inputs.items(), key=lambda kv: kv[1]))
    input_regs = dict(sorted(input_regs.items(), key=lambda kv: kv[1]))
    holding_regs = dict(sorted(holding_regs.items(), key=lambda kv: kv[1]))

    mapping_lookup = {
        "coil": coils,
        "discrete": discrete_inputs,
        "input": input_regs,
        "holding": holding_regs,
    }
    multi_sizes: list[tuple[str, int, int]] = []
    for func, name, addr, length in multi_rows:
        mapping = mapping_lookup[func]
        for key, value in mapping.items():
            if value == addr:
                multi_sizes.append((key, addr, length))
                break

    multi_sizes.sort(key=lambda item: item[1])
    multi_dict = {name: size for name, _, size in multi_sizes}

    return coils, discrete_inputs, input_regs, holding_regs, multi_dict


def write_file(
    coils: dict[str, int],
    discrete_inputs: dict[str, int],
    input_regs: dict[str, int],
    holding_regs: dict[str, int],
    multi_register_sizes: dict[str, int],
) -> None:
    """Write the registers module to :data:`OUTPUT_PATH`."""
    with OUTPUT_PATH.open("w", newline="\n") as f:
        f.write('"""Register definitions for the ThesslaGreen Modbus integration."""\n\n')
        f.write("from __future__ import annotations\n\n")
        f.write("# Generated from thessla_green_registers_full.json\n\n")

        sections = [
            ("COIL_REGISTERS", coils),
            ("DISCRETE_INPUT_REGISTERS", discrete_inputs),
        ]
        for name, mapping in sections:
            f.write(f"{name}: dict[str, int] = {{\n")
            for key, addr in mapping.items():
                f.write(f'    "{key}": {addr},\n')
            f.write("}\n\n")

        f.write(
            "# Sizes of holding register blocks that span multiple consecutive registers.\n"
        )
        f.write("# Each key is the starting register name and the value is the number of\n")
        f.write("# registers in that block.\n")
        f.write("MULTI_REGISTER_SIZES: dict[str, int] = {\n")
        for key, size in multi_register_sizes.items():
            f.write(f'    "{key}": {size},\n')
        f.write("}\n\n")

        sections = [
            ("INPUT_REGISTERS", input_regs),
            ("HOLDING_REGISTERS", holding_regs),
        ]
        for name, mapping in sections:
            f.write(f"{name}: dict[str, int] = {{\n")
            for key, addr in mapping.items():
                f.write(f'    "{key}": {addr},\n')
            f.write("}\n\n")


def main() -> None:
    sort_registers_json()
    coils, discrete_inputs, input_regs, holding_regs, multi_sizes = load_registers()
    write_file(coils, discrete_inputs, input_regs, holding_regs, multi_sizes)


if __name__ == "__main__":
    main()
