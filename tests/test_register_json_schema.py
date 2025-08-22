import json
from pathlib import Path


def test_register_json_schema():
    data = json.loads(Path("thessla_green_registers_full.json").read_text(encoding="utf-8"))
    assert "registers" in data
    registers = data["registers"]
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
                assert isinstance(val, str)
        if "multiplier" in reg:
            assert isinstance(reg["multiplier"], (int, float))
        if "resolution" in reg:
            assert isinstance(reg["resolution"], (int, float))
