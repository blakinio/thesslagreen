# mypy: ignore-errors
"""Tests for BCD time decoding."""

from datetime import time

import pytest

from custom_components.thessla_green_modbus.utils import decode_bcd_time


def test_decode_bcd_time_valid():
    """Decode a valid BCD time."""
    assert decode_bcd_time(4660) == time(12, 34)  # nosec B101


def test_decode_bcd_time_2400():
    """Decode 24:00 to 00:00."""
    assert decode_bcd_time(9216) == time(0, 0)  # nosec B101


@pytest.mark.parametrize("value", [6656, 9056, 39321, 65535])
def test_decode_bcd_time_malformed(value):
    """Return None for malformed BCD values."""
    assert decode_bcd_time(value) is None  # nosec B101
