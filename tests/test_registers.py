import csv
import importlib.util
import pathlib
import re
from tools.generate_registers import load_registers
def to_snake_case(name: str) -> str:
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



def load_csv_registers() -> tuple[dict[str, int], dict[str, int]]:
    input_regs: dict[str, int] = {}
    holding_regs: dict[str, int] = {}
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.csv")

def _build_register_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    rows.sort(key=lambda r: r[1])
    counts: dict[str, int] = {}
    for name, _ in rows:
        counts[name] = counts.get(name, 0) + 1
    seen: dict[str, int] = {}
    result: dict[str, int] = {}
    for name, addr in rows:
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name}_{seen[name]}"
        result[name] = addr
    return result


def load_csv_registers() -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/modbus_registers.csv")
    with csv_path.open(newline="") as f:
    coil_regs: dict[str, int] = {}
    discrete_regs: dict[str, int] = {}
    input_regs: dict[str, int] = {}
    holding_regs: dict[str, int] = {}
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.csv")
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Function_Code"]
            if not code or code.startswith("#"):
                continue
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
    return (
        _build_register_map(coil_rows),
        _build_register_map(discrete_rows),
        _build_register_map(input_rows),
        _build_register_map(holding_rows),
    )


def load_module_registers() -> (
    tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]
):
    module_path = pathlib.Path("custom_components/thessla_green_modbus/registers.py")
    spec = importlib.util.spec_from_file_location("registers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load registers module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        module.COIL_REGISTERS,
        module.DISCRETE_INPUT_REGISTERS,
        module.INPUT_REGISTERS,
        module.HOLDING_REGISTERS,
    )


def test_register_definitions_match_csv() -> None:
    csv_coil, csv_discrete, csv_input, csv_holding = load_csv_registers()
    mod_coil, mod_discrete, mod_input, mod_holding = load_module_registers()
    assert csv_coil == mod_coil  # nosec B101
    assert csv_discrete == mod_discrete  # nosec B101
    assert csv_input == mod_input  # nosec B101
    assert csv_holding == mod_holding  # nosec B101
    assert len(mod_input) == 28  # nosec B101
    assert len(mod_holding) == 282  # nosec B101
