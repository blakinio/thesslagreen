import pytest

from custom_components.thessla_green_modbus.device_scanner import _decode_setting_value
from custom_components.thessla_green_modbus.utils import _decode_bcd_time, _decode_register_time


def test_decode_register_time_valid():
    """Ensure byte-encoded HH:MM values decode correctly."""
    assert _decode_register_time(0x081E) == 510
    assert _decode_register_time(0x1234) == 1132
    assert _decode_register_time(0x0000) == 0


@pytest.mark.parametrize("value", [0x2460, 0x0960, -1])
def test_decode_register_time_invalid(value):
    """Values outside valid hour/minute ranges should return None."""
    assert _decode_register_time(value) is None


def test_decode_bcd_time_valid():
    """BCD and decimal HHMM values should be decoded correctly."""
    assert _decode_bcd_time(0x1234) == 754
    assert _decode_bcd_time(0x0800) == 480
    # Decimal fallback: BCD path invalid due to minutes > 59
    assert _decode_bcd_time(615) == 375


@pytest.mark.parametrize("value", [0x2460, 2400, -1, 0x1A59])
def test_decode_bcd_time_invalid(value):
    """Invalid BCD or decimal times should return None."""
    assert _decode_bcd_time(value) is None


def test_schedule_register_time_format():
    """Schedule registers decode to HH:MM string representation."""
    minutes = _decode_bcd_time(0x0815)
    assert minutes == 8 * 60 + 15
    assert f"{minutes // 60:02d}:{minutes % 60:02d}" == "08:15"


def test_decode_setting_value_valid():
    """Verify combined airflow/temperature registers decode correctly."""
    assert _decode_setting_value(0x3C28) == (60, 20.0)
    assert _decode_setting_value(0x6432) == (100, 25.0)
    assert _decode_setting_value(0x0000) == (0, 0.0)


@pytest.mark.parametrize("value", [-1, 0xFF28, 0x3DFF])
def test_decode_setting_value_invalid(value):
    """Values outside expected ranges should return None."""
    assert _decode_setting_value(value) is None
