import importlib.util
import pathlib

from tools.generate_registers import load_registers


def load_module_registers() -> tuple[dict[str, int], dict[str, int]]:
    module_path = pathlib.Path("custom_components/thessla_green_modbus/registers.py")
    spec = importlib.util.spec_from_file_location("registers", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load registers module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.INPUT_REGISTERS, module.HOLDING_REGISTERS


def test_register_definitions_match_csv() -> None:
    csv_input, csv_holding = load_registers()
    mod_input, mod_holding = load_module_registers()
    assert csv_input == mod_input  # nosec B101
    assert csv_holding == mod_holding  # nosec B101
    assert len(mod_input) == 28
    assert len(mod_holding) == 282
