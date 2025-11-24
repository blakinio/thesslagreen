import json
from pathlib import Path

import pytest

from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)
from custom_components.thessla_green_modbus.utils import _to_snake_case


def _reg(fn: str, name: str):
    regs = get_registers_by_function(fn)
    norm_name = _to_snake_case(name)
    return next(r for r in regs if r.name == norm_name)


@pytest.mark.parametrize(
    ("variant", "canonical"),
    [
        ("1", "01"),
        ("01", "01"),
        ("coil", "01"),
        ("coils", "01"),
        ("2", "02"),
        ("02", "02"),
        ("discrete", "02"),
        ("discreteinputs", "02"),
        ("3", "03"),
        ("03", "03"),
        ("holding", "03"),
        ("holdingregisters", "03"),
        ("4", "04"),
        ("04", "04"),
        ("input", "04"),
        ("inputregisters", "04"),
    ],
)
def test_get_registers_by_function_variants(variant: str, canonical: str) -> None:
    """All variant names return the same register list."""

    assert get_registers_by_function(variant) == get_registers_by_function(canonical)


def test_register_mapping_and_scaling() -> None:
    """Decode/encode helpers honour enum and scaling metadata."""

    coil = _reg("01", "bypass")
    assert coil.decode(1) == "ON"
    assert coil.encode("ON") == 1

    discrete = _reg("02", "expansion")
    assert discrete.decode(0) == "brak"
    assert discrete.encode("jest") == 1

    holding = _reg("03", "supply_air_temperature_manual")
    assert holding.resolution == 0.5
    assert holding.encode(21.3) == 43
    assert holding.decode(43) == pytest.approx(21.5)

    enum_reg = _reg("03", "access_level")
    assert enum_reg.decode(1) == "serwis / instalator"
    assert enum_reg.encode("producent") == 3

    inp = _reg("04", "outside_temperature")
    assert inp.multiplier == 0.1
    assert inp.decode(215) == pytest.approx(21.5)
    assert inp.encode(21.5) == 215


def test_registers_match_json() -> None:
    """Registers loaded by the helper match the JSON definitions."""

    json_path = Path(
        "custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json"
    )
    data = json.loads(json_path.read_text())
    by_func: dict[str, dict[str, int]] = {fn: {} for fn in ["01", "02", "03", "04"]}
    for item in data["registers"]:
        fn = item["function"]
        addr = int(item["address_dec"])
        if fn == "02":
            addr -= 1
        elif fn == "03" and addr >= 111:
            addr -= 111
        by_func[fn][_to_snake_case(item["name"])] = addr

    for fn in ["01", "02", "03", "04"]:
        regs = {r.name: r.address for r in get_registers_by_function(fn)}
        assert regs == by_func[fn]
