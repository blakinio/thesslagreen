import pytest
from custom_components.thessla_green_modbus.registers.loader import RegisterDef as Register


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


def test_decode_i16_negative():
    """raw >= 32768 is converted to signed negative."""
    reg = Register(function=3, address=0, name="test_i16", access="rw", extra={"type": "i16"})
    assert reg.decode(65535) == -1
    assert reg.decode(32768) == -32768


def test_encode_bcd_time_int_total_minutes():
    """BCD encode from int (total minutes) uses divmod."""
    reg = Register(function=3, address=0, name="schedule_test_start", access="rw", bcd=True)
    # 495 minutes = 8h 15m → same BCD as "08:15" = 2069
    assert reg.encode(495) == 2069


def test_encode_bcd_time_tuple_hours_minutes():
    """BCD encode from (hours, minutes) tuple."""
    reg = Register(function=3, address=0, name="schedule_test_start", access="rw", bcd=True)
    assert reg.encode((8, 15)) == 2069


def test_encode_bcd_time_list_hours_minutes():
    """BCD encode from [hours, minutes] list."""
    reg = Register(function=3, address=0, name="schedule_test_start", access="rw", bcd=True)
    assert reg.encode([8, 15]) == 2069


def test_encode_aatt_dict_airflow_pct_key():
    """AATT encode uses 'airflow_pct' key from dict."""
    reg = Register(function=3, address=0, name="setting_test", access="rw", extra={"aatt": True})
    # airflow_pct=60, temp_c=20.0 → same encoding as the roundtrip decode test
    result = reg.encode({"airflow_pct": 60, "temp_c": 20.0})
    assert result == 15400


def test_encode_aatt_scalar_airflow_temp_zero():
    """AATT encode treats scalar as airflow with temp=0."""
    reg = Register(function=3, address=0, name="setting_test", access="rw", extra={"aatt": True})
    result = reg.encode(60)
    # airflow=60, temp=0 → (60 << 8) | 0 = 15360
    assert result == (60 << 8)


def test_encode_enum_invalid_value_raises():
    """Encoding an unknown enum value raises ValueError."""
    reg = Register(
        function=3,
        address=0,
        name="test_enum",
        access="rw",
        enum={0: "off", 1: "on"},
    )
    with pytest.raises(ValueError, match="Invalid enum value"):
        reg.encode("unknown_state")


def test_multi_register_encode_string_enum():
    """Multi-reg encode resolves string value through enum."""
    reg = Register(
        function=3,
        address=0,
        name="test_multi",
        access="rw",
        length=2,
        enum={0: "stopped", 1: "running"},
    )
    words = reg.encode("running")
    assert isinstance(words, list)
    # raw_val = 1 → big-endian 4-byte: [0x0000, 0x0001]
    assert words == [0, 1]


def test_multi_register_encode_string_enum_not_found_raises():
    """Multi-reg encode raises ValueError when string label not in enum."""
    reg = Register(
        function=3,
        address=0,
        name="test_multi",
        access="rw",
        length=2,
        enum={0: "stopped", 1: "running"},
    )
    with pytest.raises(ValueError, match="Invalid enum value"):
        reg.encode("unknown")


# ---------------------------------------------------------------------------
# Additional encode/decode edge cases
# ---------------------------------------------------------------------------


def test_multi_register_temp_sentinel_all_32768():
    """Multi-reg temperature register with all words=32768 returns None."""
    reg = Register(function=3, address=0, name="inlet_temperature", access="ro", length=2)
    assert reg.decode([32768, 32768]) is None


def test_decode_single_register_from_sequence():
    """Sequence passed to single-register decode extracts first element."""
    reg = Register(function=3, address=0, name="mode", access="ro")
    assert reg.decode([42]) == 42


def test_decode_enum_string_keys():
    """Enum with string keys is found via str(raw) fallback."""
    reg = Register(function=3, address=0, name="st", access="ro", enum={"0": "off", "1": "on"})
    assert reg.decode(0) == "off"
    assert reg.decode(1) == "on"


def test_multi_register_decode_default_type():
    """length > 1, no extra type → default int.from_bytes path."""
    reg = Register(function=3, address=0, name="counter", access="ro", length=2)
    # [0, 100] → big-endian u32 = 100
    assert reg.decode([0, 100]) == 100


def test_multi_register_decode_with_resolution():
    """Multi-reg decode with resolution quantises value."""
    reg = Register(function=3, address=0, name="counter", access="ro", length=2, resolution=5)
    # [0, 103] → 103; round(103/5)=21; 21*5=105
    assert reg.decode([0, 103]) == 105


def test_multi_register_encode_non_string_invalid_raises():
    """Multi-reg encode raises when non-string value not in enum."""
    reg = Register(
        function=3,
        address=0,
        name="r",
        access="rw",
        length=2,
        enum={0: "stopped", 1: "running"},
    )
    with pytest.raises(ValueError, match="Invalid enum value"):
        reg.encode(99)


def test_multi_register_encode_below_min_raises():
    """Multi-reg encode raises when value is below minimum."""
    reg = Register(function=3, address=0, name="r", access="rw", length=2, min=0, max=100)
    with pytest.raises(ValueError, match="below minimum"):
        reg.encode(-5)


def test_multi_register_encode_above_max_raises():
    """Multi-reg encode raises when value is above maximum."""
    reg = Register(function=3, address=0, name="r", access="rw", length=2, min=0, max=100)
    with pytest.raises(ValueError, match="above maximum"):
        reg.encode(200)


def test_multi_register_encode_with_resolution():
    """Multi-reg encode applies resolution quantisation."""
    reg = Register(function=3, address=0, name="r", access="rw", length=2, resolution=10)
    # 15 / 10 = 1.5 → rounds to 2 → 2 * 10 = 20 → big-endian u32 → [0, 20]
    words = reg.encode(15)
    assert isinstance(words, list)
    assert len(words) == 2
    assert words == [0, 20]


def test_multi_register_encode_with_multiplier():
    """Multi-reg encode applies multiplier scaling."""
    reg = Register(function=3, address=0, name="r", access="rw", length=2, multiplier=0.1)
    # 1.0 / 0.1 = 10 → big-endian u32 → [0, 10]
    words = reg.encode(1.0)
    assert isinstance(words, list)
    assert len(words) == 2
    assert words == [0, 10]


def test_encode_bitmask_single_string():
    """Bitmask encode from a single string returns matching key."""
    reg = Register(
        function=3,
        address=0,
        name="flags",
        access="rw",
        enum={1: "flag_a", 2: "flag_b"},
        extra={"bitmask": True},
    )
    assert reg.encode("flag_a") == 1
    assert reg.encode("flag_b") == 2


def test_encode_enum_non_string_invalid_raises():
    """Single-reg encode raises when integer not in enum."""
    reg = Register(function=3, address=0, name="e", access="rw", enum={0: "off", 1: "on"})
    with pytest.raises(ValueError, match="Invalid enum value"):
        reg.encode(99)


def test_encode_i16_negative_to_unsigned():
    """i16 encode converts signed negative to unsigned two's complement."""
    reg = Register(function=3, address=0, name="t", access="rw", extra={"type": "i16"})
    assert reg.encode(-1) == 65535
    assert reg.encode(-32768) == 32768


def test_group_registers_consecutive():
    """group_registers groups consecutive addresses into ranges."""
    from custom_components.thessla_green_modbus.registers.loader import group_registers

    result = group_registers([0, 1, 2, 10, 11])
    assert isinstance(result, list)
    assert len(result) == 2


def test_encode_bitmask_integer_fallback():
    """Bitmask encode with an integer falls back to int(value)."""
    reg = Register(
        function=3,
        address=0,
        name="flags",
        access="rw",
        enum={1: "flag_a", 2: "flag_b"},
        extra={"bitmask": True},
    )
    assert reg.encode(3) == 3


def test_multi_register_decode_from_integer():
    """length > 1 with plain integer input splits via bit-shift."""
    reg = Register(function=3, address=0, name="counter", access="ro", length=2)
    # Pass a single u32 integer: 0x00010002 → words [1, 2] → big-endian int = 65538
    assert reg.decode(0x00010002) == 65538
