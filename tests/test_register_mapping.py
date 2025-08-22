import pytest
from custom_components.thessla_green_modbus.registers import get_registers_by_function


def _reg(fn: str, name: str):
    regs = get_registers_by_function(fn)
    return next(r for r in regs if r.name == name)


def test_register_mapping_and_scaling():
    coil = _reg("01", "duct_warter_heater_pump")
    assert coil.decode(1) == 1

    discrete = _reg("02", "duct_heater_protection")
    assert discrete.decode(0) == 0

    holding = _reg("03", "supplyAirTemperatureManual")
    assert holding.resolution == 0.5
    assert holding.encode(21.3) == 21
    assert holding.decode(21) == pytest.approx(21.0)

    inp = _reg("04", "outside_temperature")
    assert inp.multiplier == 0.1
    assert inp.decode(215) == pytest.approx(21.5)
    assert inp.encode(21.5) == 215
