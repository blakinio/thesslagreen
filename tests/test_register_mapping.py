import pytest
from custom_components.thessla_green_modbus.registers import get_registers_by_function
from custom_components.thessla_green_modbus.utils import _to_snake_case

from pathlib import Path
import importlib.util
import json


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
    assert holding.encode(21.3) == 21
    assert holding.decode(21) == pytest.approx(21.0)

    enum_reg = _reg("03", "access_level")
    assert enum_reg.decode(1) == "serwis/instalator"
    assert enum_reg.encode("producent") == 3

    inp = _reg("04", "outside_temperature")
    assert inp.multiplier == 0.1
    assert inp.decode(215) == pytest.approx(21.5)
    assert inp.encode(21.5) == 215

    bit_reg = _reg("03", "E196_E199")
    assert bit_reg.decode(10) == ["E197", "E199"]
    assert bit_reg.encode(["E197", "E199"]) == 10


def test_static_register_maps_synced() -> None:
    """Generated register maps must match the JSON definitions."""

    json_path = Path(
        "custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json"
    )
    data = json.loads(json_path.read_text())
    by_func: dict[str, dict[str, int]] = {fn: {} for fn in ["01", "02", "03", "04"]}
    for item in data["registers"]:
        by_func[item["function"]][item["name"]] = int(item["address_dec"])

    spec = importlib.util.spec_from_file_location(
        "tg_registers", Path("custom_components/thessla_green_modbus/registers.py")
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    assert module.COIL_REGISTERS == by_func["01"]
    assert module.DISCRETE_INPUT_REGISTERS == by_func["02"]
    assert module.INPUT_REGISTERS == by_func["04"]
    assert module.HOLDING_REGISTERS == by_func["03"]
