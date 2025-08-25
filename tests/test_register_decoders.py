import asyncio
import struct

import pytest

from custom_components.thessla_green_modbus.registers.loader import (
    Register,
    get_registers_by_function,
)
from custom_components.thessla_green_modbus.scanner_core import (
    ThesslaGreenDeviceScanner,
)
from custom_components.thessla_green_modbus.scanner_helpers import (
    _decode_season_mode,
    _format_register_value,
)
from custom_components.thessla_green_modbus.utils import (
    _decode_aatt,
    _decode_bcd_time,
    _decode_register_time,
)


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
    reg = Register(function=3, address=0, name="schedule_test_start", access="rw", bcd=True)
    assert reg.decode(0x0815) == "08:15"
    assert reg.encode("08:15") == 0x0815


def test_register_decode_encode_aatt():
    reg = Register(
        function=3,
        address=0,
        name="setting_test",
        access="rw",
        extra={"aatt": True},
    )
    assert reg.decode(0x3C28) == (60, 20.0)
    assert reg.encode((60, 20)) == 0x3C28


def test_register_decode_unavailable_value():
    """Sentinel value 0x8000 should decode to None."""
    reg = Register(function=4, address=0, name="temp", access="ro")
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
        function=3,
        address=0,
        name="errors",
        access="rw",
        enum={1: "A", 2: "B", 4: "C"},
        extra={"bitmask": True},
    )
    assert reg.decode(5) == ["A", "C"]
    assert reg.encode(["A", "C"]) == 5


def test_register_encode_numeric_bounds():
    """Numeric registers enforce configured min/max limits."""
    reg = Register(function="holding", address=0, name="num", access="rw", min=0, max=10)
    assert reg.encode(0) == 0
    assert reg.encode(10) == 10
    with pytest.raises(ValueError):
        reg.encode(-1)
    with pytest.raises(ValueError):
        reg.encode(11)


def test_register_encode_enum_invalid():
    """Enum registers raise when provided invalid values."""
    reg = Register(function="holding", address=0, name="mode", access="rw", enum={0: "off", 1: "on"})
    with pytest.raises(ValueError):
        reg.encode("invalid")

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
        function=3,
        address=0,
        name="float_reg",
        access="rw",
        length=2,
        extra={"type": "f32"},
    )
    raw = reg.encode(12.34)
    assert isinstance(raw, list)
    assert reg.decode(raw) == pytest.approx(12.34, rel=1e-6)


def test_multi_register_decode_string() -> None:
    """Multi-register string values decode correctly."""
    reg = Register(
        function=3,
        address=0,
        name="string_reg",
        access="ro",
        length=3,
        extra={"type": "string"},
    )
    raw = [0x4142, 0x4344, 0x4500]  # "ABCDE"
    assert reg.decode(raw) == "ABCDE"


def test_multi_register_decode_float32() -> None:
    """Multi-register float values decode correctly."""
    reg = Register(
        function=3,
        address=0,
        name="float_multi",
        access="ro",
        length=2,
        extra={"type": "f32"},
    )
    value = 12.34
    raw_bytes = struct.pack(">f", value)
    raw = [int.from_bytes(raw_bytes[i : i + 2], "big") for i in (0, 2)]
    assert reg.decode(raw) == pytest.approx(value, rel=1e-6)


def test_multi_register_decode_int32() -> None:
    """Multi-register integer values decode correctly."""
    reg = Register(
        function=3,
        address=0,
        name="int_multi",
        access="ro",
        length=2,
        extra={"type": "i32"},
    )
    raw = [0x1234, 0x5678]
    assert reg.decode(raw) == 0x12345678
@pytest.fixture
def float32_register() -> Register:
    """Register representing a 32-bit floating point value."""
    return Register(
        function=3,
        address=0,
        name="float32_test",
        access="rw",
        length=2,
        extra={"type": "f32"},
    )


@pytest.fixture
def float64_register() -> Register:
    """Register representing a 64-bit floating point value."""
    return Register(
        function=3,
        address=0,
        name="float64_test",
        access="rw",
        length=4,
        extra={"type": "f64"},
    )


@pytest.fixture
def int32_register() -> Register:
    """Register representing a signed 32-bit integer."""
    return Register(
        function=3,
        address=0,
        name="int32_test",
        access="rw",
        length=2,
        extra={"type": "i32"},
    )


@pytest.fixture
def uint32_register() -> Register:
    """Register representing an unsigned 32-bit integer."""
    return Register(
        function=3,
        address=0,
        name="uint32_test",
        access="rw",
        length=2,
        extra={"type": "u32"},
    )


@pytest.fixture
def int64_register() -> Register:
    """Register representing a signed 64-bit integer."""
    return Register(
        function=3,
        address=0,
        name="int64_test",
        access="rw",
        length=4,
        extra={"type": "i64"},
    )


@pytest.fixture
def uint64_register() -> Register:
    """Register representing an unsigned 64-bit integer."""
    return Register(
        function=3,
        address=0,
        name="uint64_test",
        access="rw",
        length=4,
        extra={"type": "u64"},
    )


@pytest.mark.parametrize("value", [0.0, 12.5, -7.25, 1e20])
def test_register_float64_encode_decode(float64_register: Register, value: float) -> None:
    raw = float64_register.encode(value)
    assert float64_register.decode(raw) == pytest.approx(value)


@pytest.mark.parametrize("value", [0.0, 12.5, -7.25, 1e20])
def test_register_float64_little_endian(float64_register: Register, value: float) -> None:
    reg_le = Register(
        function=3,
        address=0,
        name="float64_le_test",
        access="rw",
        length=4,
        extra={"type": "f64", "endianness": "little"},
    )
    raw = reg_le.encode(value)
    assert reg_le.decode(raw) == pytest.approx(value)


@pytest.mark.parametrize("value", [12.5, -7.25])
def test_register_float32_encode_decode(float32_register: Register, value: float) -> None:
    raw = float32_register.encode(value)
    assert float32_register.decode(raw) == pytest.approx(value)


@pytest.mark.parametrize("value", [0, 2147483647, -1, -2147483648])
def test_register_int32_encode_decode(int32_register: Register, value: int) -> None:
    raw = int32_register.encode(value)
    assert int32_register.decode(raw) == value


@pytest.mark.parametrize("value", [0, 4294967295])
def test_register_uint32_encode_decode(uint32_register: Register, value: int) -> None:
    raw = uint32_register.encode(value)
    assert uint32_register.decode(raw) == value


@pytest.mark.parametrize("value", [1234567890123456789, -987654321098765432])
def test_register_int64_encode_decode(int64_register: Register, value: int) -> None:
    raw = int64_register.encode(value)
    assert int64_register.decode(raw) == value


@pytest.mark.parametrize("value", [0, 2**64 - 1])
def test_register_uint64_encode_decode(uint64_register: Register, value: int) -> None:
    raw = uint64_register.encode(value)
    assert uint64_register.decode(raw) == value
