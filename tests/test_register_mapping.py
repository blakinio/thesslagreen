import json
from pathlib import Path

import pytest
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
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
        by_func[fn][_to_snake_case(item["name"])] = addr

    for fn in ["01", "02", "03", "04"]:
        regs = {r.name: r.address for r in get_registers_by_function(fn)}
        assert regs == by_func[fn]


# ---------------------------------------------------------------------------
# register_map.py coverage tests
# ---------------------------------------------------------------------------


def _make_reg(**kwargs):
    """Return a minimal RegisterDef with required fields."""
    from custom_components.thessla_green_modbus.registers.register_def import RegisterDef

    defaults = {"function": 3, "address": 100, "name": "test_reg", "access": "RW"}
    defaults.update(kwargs)
    return RegisterDef(**defaults)


def test_infer_data_type_bool():
    """_infer_data_type returns 'bool' for max=1, min=0 registers (line 165)."""
    from custom_components.thessla_green_modbus.register_map import _infer_data_type

    reg = _make_reg(max=1, min=0)
    assert _infer_data_type(reg) == "bool"  # nosec B101


def test_model_variants_compact_in_information():
    """_model_variants detects 'AirPack Compact' from information field (line 189)."""
    from custom_components.thessla_green_modbus.register_map import _model_variants

    reg = _make_reg(information="For Compact units only")
    variants = _model_variants(reg)
    assert "AirPack Compact" in variants  # nosec B101


def test_model_variants_home_in_notes():
    """_model_variants detects 'AirPack Home' from notes field (line 191)."""
    from custom_components.thessla_green_modbus.register_map import _model_variants

    reg = _make_reg(notes="Specific to Home edition")
    variants = _model_variants(reg)
    assert "AirPack Home" in variants  # nosec B101


def test_build_register_map_skips_empty_name(monkeypatch):
    """build_register_map skips registers whose name is falsy (line 203)."""
    from custom_components.thessla_green_modbus import register_map as rm

    regs = [_make_reg(name=""), _make_reg(name="valid_test_reg", address=200)]
    monkeypatch.setattr(rm, "get_all_registers", lambda: regs)
    result = rm.build_register_map()
    assert "" not in result  # nosec B101
    assert "valid_test_reg" in result  # nosec B101


def test_build_register_map_skips_unknown_function(monkeypatch):
    """build_register_map skips registers with unknown function codes (line 206)."""
    from custom_components.thessla_green_modbus import register_map as rm

    regs = [
        _make_reg(function=99, name="bad_func_reg"),
        _make_reg(function=3, name="good_func_reg", address=201),
    ]
    monkeypatch.setattr(rm, "get_all_registers", lambda: regs)
    result = rm.build_register_map()
    assert "bad_func_reg" not in result  # nosec B101
    assert "good_func_reg" in result  # nosec B101
