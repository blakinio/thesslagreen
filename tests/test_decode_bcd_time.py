# mypy: ignore-errors
"""Tests for BCD time decoding."""

import pytest

from custom_components.thessla_green_modbus.utils import _decode_bcd_time


def test_decode_bcd_time_valid():
    """Decode a valid BCD time."""
    assert _decode_bcd_time(0x1234) == 1234  # nosec B101


def test_decode_bcd_time_2400():
    """Decode 24:00 to 00:00."""
    assert _decode_bcd_time(0x2400) == 0  # nosec B101


@pytest.mark.parametrize("value", [0x1A00, 0x2360, 0x9999])
def test_decode_bcd_time_malformed(value):
    """Return None for malformed BCD values."""
    assert _decode_bcd_time(value) is None  # nosec B101
