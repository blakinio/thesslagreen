import json
from importlib import resources


def test_register_json_schema() -> None:
    """Validate basic structure of the JSON register file."""

    json_file = resources.files("custom_components.thessla_green_modbus.registers").joinpath(
        "thessla_green_registers_full.json"
    )
    data = json.loads(json_file.read_text(encoding="utf-8"))
    registers = data.get("registers", data) if isinstance(data, dict) else data
    assert isinstance(registers, list) and registers
    required = {"function", "address_dec", "name", "access"}
    for reg in registers:
        assert required <= reg.keys()
        assert isinstance(reg["function"], str)
        assert isinstance(reg["address_dec"], int)
        assert isinstance(reg["name"], str)
        assert reg["access"] in {"R", "RW", "W"}
        if reg["function"] in {"01", "02"}:
            assert reg["access"] == "R"
        if reg.get("enum") is not None:
            enum = reg["enum"]
            assert enum is None or isinstance(enum, dict)
            if enum:
                for key, val in enum.items():
                    assert isinstance(key, str)
                    assert isinstance(val, int | str)
        if "multiplier" in reg:
            mult = reg["multiplier"]
            assert mult is None or isinstance(mult, int | float)
            if mult is not None:
                assert mult > 0
        if "resolution" in reg:
            res = reg["resolution"]
            assert res is None or isinstance(res, int | float)
            if res is not None:
                assert res > 0
        if reg.get("multiplier") is not None:
            assert isinstance(reg["multiplier"], int | float)
            assert reg["multiplier"] > 0
        if reg.get("resolution") is not None:
            assert isinstance(reg["resolution"], int | float)
            assert reg["resolution"] > 0
        if "notes" in reg:
            assert isinstance(reg["notes"], str)
        if "extra" in reg:
            assert isinstance(reg["extra"], dict)
