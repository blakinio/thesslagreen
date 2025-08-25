
from custom_components.thessla_green_modbus.registers.loader import Register


def test_coil_and_discrete_enum():
    """Registers for function 01 and 02 should decode enums correctly."""
    coil = Register(function=1, address=5, name="coil", access="ro", enum={0: "OFF", 1: "ON"})
    assert coil.decode(1) == "ON"
    assert coil.encode("OFF") == 0

    discrete = Register(function=2, address=0, name="discrete", access="ro", enum={0: "brak", 1: "jest"})
    assert discrete.decode(0) == "brak"
    assert discrete.encode("jest") == 1


def test_holding_multiplier_resolution_and_bcd():
    """Function 03 registers may use multiplier/resolution and BCD."""
    scaling = Register(function=3, address=4096, name="temp", access="rw", multiplier=0.5, resolution=0.5)
    assert scaling.decode(45) == 22.5
    assert scaling.encode(22.5) == 45

    schedule = Register(function=3, address=4097, name="schedule", access="rw", bcd=True)
    assert schedule.decode(0x0815) == "08:15"
    assert schedule.encode("08:15") == 0x0815


def test_input_extra_aatt_and_sentinel():
    """Function 04 registers support extra aatt and sentinel values."""
    combined = Register(function=4, address=16, name="combined", access="ro", extra={"aatt": True})
    assert combined.decode(0x3C28) == (60, 20.0)
    assert combined.encode((60, 20.0)) == 0x3C28

    sensor = Register(function=4, address=17, name="sensor", access="ro")
    assert sensor.decode(0x8000) is None
