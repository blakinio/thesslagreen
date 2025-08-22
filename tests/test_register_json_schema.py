import json
from pathlib import Path


def test_register_json_schema() -> None:
    """Validate basic structure of the JSON register file."""

    json_path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "thessla_green_modbus"
        / "registers"
        / "thessla_green_registers_full.json"
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    registers = data.get("registers", data) if isinstance(data, dict) else data
    assert isinstance(registers, list) and registers
    required = {"function", "address_dec", "name"}
    for reg in registers:
        assert required <= reg.keys()
        assert isinstance(reg["function"], str)
        assert isinstance(reg["address_dec"], int)
        assert isinstance(reg["name"], str)
        if "enum" in reg:
            enum = reg["enum"]
            assert isinstance(enum, dict) and enum
            for key, val in enum.items():
                assert isinstance(key, str)
                assert isinstance(val, (int, str))
        if "multiplier" in reg:
            assert isinstance(reg["multiplier"], (int, float))
            assert reg["multiplier"] > 0
        if "resolution" in reg:
            assert isinstance(reg["resolution"], (int, float))
            assert reg["resolution"] > 0
        if "notes" in reg:
            assert isinstance(reg["notes"], str)
        if "extra" in reg:
            assert isinstance(reg["extra"], dict)
