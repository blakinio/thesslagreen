from datetime import time

from custom_components.thessla_green_modbus.utils import (
    decode_bcd_time,
    decode_int16,
    decode_temp_01c,
    encode_bcd_time,
)


def test_decode_int16_signed() -> None:
    assert decode_int16(0) == 0
    assert decode_int16(1) == 1
    assert decode_int16(65535) == -1
    assert decode_int16(32768) == -32768


def test_decode_temp_01c() -> None:
    assert decode_temp_01c(32768) is None
    assert decode_temp_01c(10) == 1.0
    assert decode_temp_01c(65526) == -1.0


def test_bcd_time_roundtrip() -> None:
    value = time(6, 30)
    encoded = encode_bcd_time(value)
    assert decode_bcd_time(encoded) == value
