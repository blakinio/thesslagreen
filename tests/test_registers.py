import csv  # handle CSV register definitions
import importlib.util
import pathlib
import re


def to_snake_case(name: str) -> str:
    replacements = {"flowrate": "flow_rate"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r"[\s\-/]", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"(?<=\D)(\d)", r"_\1", name)
    name = re.sub(r"__+", "_", name)
    return name.lower()


def load_csv_registers() -> tuple[dict[str, int], dict[str, int]]:
    input_regs: dict[str, int] = {}
    holding_regs: dict[str, int] = {}
    csv_path = pathlib.Path("custom_components/thessla_green_modbus/modbus_registers.csv")
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Function_Code"]
            if not code or code.startswith("#"):
                continue
            name = to_snake_case(row["Register_Name"])
            addr = int(row["Address_DEC"])
            if code == "04":
                input_regs[name] = addr
            elif code == "03":
                holding_regs[name] = addr
    return input_regs, holding_regs


def load_module_registers() -> tuple[dict[str, int], dict[str, int]]:
    module_path = pathlib.Path("custom_components/thessla_green_modbus/registers.py")
    spec = importlib.util.spec_from_file_location("registers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load registers module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.INPUT_REGISTERS, module.HOLDING_REGISTERS


def test_register_definitions_match_csv() -> None:
    csv_input, csv_holding = load_csv_registers()
    mod_input, mod_holding = load_module_registers()
    assert csv_input == mod_input  # nosec B101
    assert csv_holding == mod_holding  # nosec B101
