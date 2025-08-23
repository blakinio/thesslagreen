import asyncio
import pytest

from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner_helpers import (
    _decode_season_mode,
    _format_register_value,
)
from custom_components.thessla_green_modbus.utils import (
    _decode_aatt,
    _decode_bcd_time,
    _decode_register_time,
)
from custom_components.thessla_green_modbus.registers.loader import Register
from custom_components.thessla_green_modbus.registers import get_registers_by_function


def test_decode_register_time_valid():
    """Ensure byte-encoded HH:MM values decode correctly."""
    assert _decode_register_time(0x081E) == 510
    assert _decode_register_time(0x1234) == 1132
    assert _decode_register_time(0x0000) == 0


@pytest.mark.parametrize("value", [0x2460, 0x0960, 0x8000, -1])
def test_decode_register_time_invalid(value):
    """Values outside valid hour/minute ranges should return None."""
    assert _decode_register_time(value) is None


def test_decode_bcd_time_valid():
    """BCD and decimal HHMM values should be decoded correctly."""
    assert _decode_bcd_time(0x1234) == 754
    assert _decode_bcd_time(0x0800) == 480
    # Decimal fallback: BCD path invalid due to minutes > 59
    assert _decode_bcd_time(615) == 375


@pytest.mark.parametrize("value", [0x2460, 2400, 0x8000, -1, 0x1A59])
def test_decode_bcd_time_invalid(value):
    """Invalid BCD or decimal times should return None."""
    assert _decode_bcd_time(value) is None


def test_schedule_register_time_format():
    """Schedule registers decode to HH:MM string representation."""
    minutes = _decode_bcd_time(0x0815)
    assert minutes == 8 * 60 + 15
    assert f"{minutes // 60:02d}:{minutes % 60:02d}" == "08:15"


def test_decode_aatt_value_valid():
    """Verify combined airflow/temperature registers decode correctly."""
    assert _decode_aatt(0x3C28) == (60, 20.0)
    assert _decode_aatt(0x6432) == (100, 25.0)
    assert _decode_aatt(0x0000) == (0, 0.0)


@pytest.mark.parametrize("value", [-1, 0xFF28, 0x3DFF, 0x8000])
def test_decode_aatt_value_invalid(value):
    """Values outside expected ranges should return None."""
    assert _decode_aatt(value) is None


def test_schedule_and_setting_defaults_valid():
    """Default schedule and setting values should pass range validation."""
    scanner = ThesslaGreenDeviceScanner("127.0.0.1", 502)
    _, ranges = asyncio.run(scanner._load_registers())
    scanner._register_ranges = ranges
    assert scanner._is_valid_register_value("schedule_winter_sun_3", 0x1000)
    assert scanner._is_valid_register_value("setting_summer_mon_1", 0x4100)


def test_register_decode_encode_bcd():
    reg = Register(function="holding", address=0, name="schedule_test_start", access="rw", bcd=True)
    assert reg.decode(0x0815) == "08:15"
    assert reg.encode("08:15") == 0x0815


def test_register_decode_encode_aatt():
    reg = Register(
        function="holding",
        address=0,
        name="setting_test",
        access="rw",
        extra={"aatt": True},
    )
    assert reg.decode(0x3C28) == (60, 20.0)
    assert reg.encode((60, 20)) == 0x3C28


def test_register_decode_unavailable_value():
    """Sentinel value 0x8000 should decode to None."""
    reg = Register(function="input", address=0, name="temp", access="ro")
    assert reg.decode(0x8000) is None


def test_decode_season_mode_special_value():
    """Season mode decoder should treat 0x8000 as undefined."""
    assert _decode_season_mode(0x8000) is None


def test_format_register_value_special_values():
    """Formatter should return None for sentinel values."""
    assert _format_register_value("schedule_test", 0x8000) is None
    assert _format_register_value("setting_test", 0x8000) is None


def test_register_bitmask_decode_encode():
    reg = Register(
        function="holding",
        address=0,
        name="errors",
        access="rw",
        enum={1: "A", 2: "B", 4: "C"},
        extra={"bitmask": True},
    )
    assert reg.decode(5) == ["A", "C"]
    assert reg.encode(["A", "C"]) == 5


def test_register_decode_encode_string_multi():
    reg = next(r for r in get_registers_by_function("03") if r.name == "device_name")
    value = "Test AirPack"
    raw = reg.encode(value)
    assert isinstance(raw, list) and len(raw) == reg.length
    assert reg.decode(raw) == value


def test_register_decode_encode_uint32():
    reg = next(r for r in get_registers_by_function("03") if r.name == "lock_pass")
    raw = [0x423F, 0x000F]
    assert reg.decode(raw) == 999999
    assert reg.encode(999999) == raw


def test_register_decode_encode_float32():
    reg = Register(
        function="holding",
        address=0,
        name="float_reg",
        access="rw",
        length=2,
        extra={"type": "float32"},
    )
    raw = reg.encode(12.34)
    assert isinstance(raw, list)
    assert reg.decode(raw) == pytest.approx(12.34, rel=1e-6)
