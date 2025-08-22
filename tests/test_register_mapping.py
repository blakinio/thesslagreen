import pytest
from custom_components.thessla_green_modbus.registers import get_registers_by_function


def _reg(fn: str, name: str):
    regs = get_registers_by_function(fn)
    return next(r for r in regs if r.name == name)


def test_register_mapping_and_scaling():
    coil = _reg("01", "duct_water_heater_pump")
    assert coil.decode(1) == 1

    discrete = _reg("02", "fire_alarm")
    assert discrete.decode(0) == 0

    holding = _reg("03", "required_temperature")
    assert holding.resolution == 0.5
    assert holding.encode(21.3) == 43
    assert holding.decode(43) == pytest.approx(21.5)

    enum_reg = _reg("03", "special_mode")
    assert enum_reg.decode(8) == "fireplace"
    assert enum_reg.encode("summer") == 512

    inp = _reg("04", "outside_temperature")
    assert inp.multiplier == 0.1
    assert inp.decode(215) == pytest.approx(21.5)
    assert inp.encode(21.5) == 215
