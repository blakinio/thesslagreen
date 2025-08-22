import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers import (
    get_registers_by_function,
    group_reads,
)


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


def test_group_reads_cover_all_functions() -> None:
    """Ensure group_reads plans cover all registers for each function."""

    for fn in ("01", "02", "03", "04"):
        regs = get_registers_by_function(fn)
        expected = sorted(r.address for r in regs)
        plans = [p for p in group_reads(max_block_size=32) if p.function == fn]
        addresses = [
            addr
            for plan in plans
            for addr in range(plan.address, plan.address + plan.length)
        ]
        assert addresses == expected
