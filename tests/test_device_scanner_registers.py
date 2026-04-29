"""Device scanner register formatting/validation tests."""

import logging
from unittest.mock import patch

import pytest
from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value
from custom_components.thessla_green_modbus.utils import (
    _decode_aatt,
    _decode_bcd_time,
    _decode_register_time,
)

pytestmark = pytest.mark.asyncio

async def test_is_valid_register_value():
    """Test register value validation."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    scanner._register_ranges["supply_percentage"] = (0, 100)
    scanner._register_ranges["min_percentage"] = (0, 100)
    scanner._register_ranges["max_percentage"] = (0, 120)

    # Valid values
    assert scanner._is_valid_register_value("test_register", 100) is True
    assert scanner._is_valid_register_value("test_register", 0) is True

    # SENSOR_UNAVAILABLE (0x8000) means the register EXISTS but sensor is not connected.
    # The register must produce an entity (shown as "unavailable" in HA), so return True.
    assert scanner._is_valid_register_value("outside_temperature", SENSOR_UNAVAILABLE) is True
    assert scanner._is_valid_register_value("supply_flow_rate", SENSOR_UNAVAILABLE) is True

    # Mode values respect allowed set
    assert scanner._is_valid_register_value("mode", 1) is True
    assert scanner._is_valid_register_value("mode", 3) is False

    # Range from register metadata
    assert scanner._is_valid_register_value("supply_percentage", 100) is True
    with patch.object(scanner, "_log_invalid_value") as log_mock:
        assert scanner._is_valid_register_value("supply_percentage", 200) is False
        log_mock.assert_not_called()

    # Dynamic percentage limits should accept device-provided values
    assert scanner._is_valid_register_value("min_percentage", 20) is True
    assert scanner._is_valid_register_value("max_percentage", 120) is True

    assert scanner._is_valid_register_value("min_percentage", -1) is False
    assert scanner._is_valid_register_value("max_percentage", 200) is False
    with patch.object(scanner, "_log_invalid_value") as log_mock:
        assert scanner._is_valid_register_value("min_percentage", -1) is False
        assert scanner._is_valid_register_value("max_percentage", 200) is False
        log_mock.assert_not_called()
    # HH:MM time registers
    scanner._register_ranges["schedule_start_time"] = (0, 2359)
    assert scanner._is_valid_register_value("schedule_start_time", 2078) is True
    assert scanner._is_valid_register_value("schedule_start_time", 2048) is True
    assert scanner._is_valid_register_value("schedule_start_time", 9312) is False
    assert scanner._is_valid_register_value("schedule_start_time", 2400) is False
    # BCD encoded times should also be recognized as valid
    assert scanner._is_valid_register_value("schedule_winter_mon_4", 8704) is True
    # Typical schedule and setting values
    assert scanner._is_valid_register_value("schedule_summer_mon_1", 1024) is True
    assert scanner._is_valid_register_value("setting_winter_mon_1", 12844) is True

async def test_decode_register_time():
    """Verify time decoding for HH:MM byte-encoded values."""
    assert _decode_register_time(1024) == 240
    assert _decode_register_time(2078) == 510
    assert _decode_register_time(4660) == 1132
    assert _decode_register_time(9312) is None
    assert _decode_register_time(2400) is None

async def test_decode_bcd_time():
    """Verify time decoding for both BCD and decimal values."""
    assert _decode_bcd_time(1024) == 240
    assert _decode_bcd_time(4660) == 754
    assert _decode_bcd_time(2048) == 480
    assert _decode_bcd_time(9312) is None
    assert _decode_bcd_time(2400) is None

async def test_decode_aatt_value():
    """Verify decoding of combined airflow and temperature settings."""
    assert _decode_aatt(15400) == {"airflow_pct": 60, "temp_c": 20.0}
    assert _decode_aatt(12844) == {"airflow_pct": 50, "temp_c": 22.0}
    assert _decode_aatt(-1) is None
    assert _decode_aatt(65320) is None

async def test_format_register_value_schedule():
    """Formatted schedule registers should render as HH:MM."""
    assert _format_register_value("schedule_summer_mon_1", 1557) == "06:15"

async def test_format_register_value_manual_airing_le():
    """Little-endian manual airing times should decode correctly."""
    assert _format_register_value("manual_airing_time_to_start", 7688) == "08:30"

async def test_format_register_value_airing_schedule():
    """Airing schedule registers should render as HH:MM."""
    assert _format_register_value("airing_summer_mon", 1557) == "06:15"

async def test_format_register_value_airing_durations():
    """Airing mode duration registers should return raw minute values."""
    assert _format_register_value("airing_panel_mode_time", 15) == 15
    assert _format_register_value("airing_switch_mode_time", 30) == 30
    assert _format_register_value("airing_switch_mode_on_delay", 5) == 5
    assert _format_register_value("airing_switch_mode_off_delay", 10) == 10
    assert _format_register_value("airing_switch_coef", 2) == 2

async def test_format_register_value_setting():
    """Formatted setting registers should show percent and temperature."""
    assert _format_register_value("setting_winter_mon_1", 15400) == "60% @ 20°C"

async def test_format_register_value_invalid_time():
    """Invalid time registers should show raw hex with invalid marker."""
    assert _format_register_value("schedule_summer_mon_1", 9216) == "9216 (invalid)"

async def test_log_invalid_value_debug_when_not_verbose(caplog):
    """Invalid values log at DEBUG level when not verbose."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.DEBUG
    assert "Invalid value for test_register: raw=1 decoded=1" in caplog.text

    caplog.clear()
    scanner._log_invalid_value("test_register", 1)

    assert not caplog.records

async def test_log_invalid_value_info_then_debug_when_verbose(caplog):
    """First invalid value logs INFO when verbose, then DEBUG."""
    scanner = ThesslaGreenDeviceScanner("host", 502, verbose_invalid_values=True)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.INFO
    assert "raw=1" in caplog.text

    caplog.clear()
    scanner._log_invalid_value("test_register", 1)

    assert caplog.records[0].levelno == logging.DEBUG
    assert "raw=1" in caplog.text

async def test_log_invalid_value_raw_and_formatted(caplog):
    """Log includes both raw hex and decoded representation."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("schedule_time", 5632)

    assert "raw=5632" in caplog.text
    assert "decoded=16:00" in caplog.text

async def test_log_invalid_value_invalid_time(caplog):
    """Logs include formatted string for invalid time values."""
    scanner = ThesslaGreenDeviceScanner("host", 502)

    caplog.set_level(logging.DEBUG)
    scanner._log_invalid_value("schedule_time", 9216)

    assert "raw=9216" in caplog.text
    assert "decoded=9216 (invalid)" in caplog.text
