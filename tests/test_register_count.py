import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import get_all_registers
from custom_components.thessla_green_modbus.utils import _normalise_name


def test_get_all_registers_matches_json() -> None:
    """Loader should return same number of registers as JSON file."""
    json_path = Path(
        "custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json"
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    loaded = get_all_registers(json_path)
    assert len(loaded) == len(registers)

    json_names = {_normalise_name(r["name"]) for r in registers if r.get("name")}
    loaded_names = {r.name for r in loaded if r.name}
    assert json_names == loaded_names
