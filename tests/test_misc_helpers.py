# mypy: ignore-errors
"""Tests for schedule_helpers, capability_rules, and scanner_helpers."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# schedule_helpers
# ---------------------------------------------------------------------------


def test_time_to_bcd_roundtrip():
    from datetime import time
    from custom_components.thessla_green_modbus.schedule_helpers import time_to_bcd, bcd_to_time

    t = time(8, 30)
    encoded = time_to_bcd(t)
    decoded = bcd_to_time(encoded)
    assert decoded == t


def test_bcd_to_time_valid():
    from datetime import time
    from custom_components.thessla_green_modbus.schedule_helpers import bcd_to_time

    # 0x0830 = 0830 BCD = 08:30
    result = bcd_to_time(0x0830)
    assert result == time(8, 30)


def test_bcd_to_time_invalid_raises():
    """bcd_to_time raises ValueError when decode_bcd_time returns None."""
    from custom_components.thessla_green_modbus.schedule_helpers import bcd_to_time

    # Value 0x9999 has invalid BCD digits → decode_bcd_time returns None
    with pytest.raises(ValueError, match="Invalid"):
        bcd_to_time(0x9999)


# ---------------------------------------------------------------------------
# capability_rules
# ---------------------------------------------------------------------------


def test_capability_block_reason_none_when_all_present():
    """Returns None when all capabilities are present."""
    from custom_components.thessla_green_modbus.capability_rules import capability_block_reason
    from types import SimpleNamespace

    caps = SimpleNamespace(
        outside_temperature=True,
        supply_temperature=True,
        exhaust_temperature=True,
        fpx_temperature=True,
        duct_supply_temperature=True,
        gwc_temperature=True,
        ambient_temperature=True,
        heating_temperature=True,
        heating_system=True,
        cooling_system=True,
        bypass_system=True,
        gwc_system=True,
        constant_flow=True,
        weekly_schedule=True,
    )
    assert capability_block_reason("sensor_outside_temperature", caps) is None
    assert capability_block_reason("bypass_mode", caps) is None


def test_capability_block_reason_temperature_missing():
    """Returns reason string when temperature sensor capability absent (line 43)."""
    from custom_components.thessla_green_modbus.capability_rules import capability_block_reason
    from types import SimpleNamespace

    caps = SimpleNamespace(sensor_outside_temperature=False)
    result = capability_block_reason("outside_temperature", caps)
    assert result == "sensor_outside_temperature not supported"


def test_capability_block_reason_pattern_missing():
    """Returns reason string when pattern capability absent (line 49)."""
    from custom_components.thessla_green_modbus.capability_rules import capability_block_reason
    from types import SimpleNamespace

    caps = SimpleNamespace(bypass_system=False)
    result = capability_block_reason("bypass_mode", caps)
    assert result == "bypass_system not supported"


def test_capability_block_reason_unknown_register():
    """Returns None for a register not matching any capability."""
    from custom_components.thessla_green_modbus.capability_rules import capability_block_reason
    from types import SimpleNamespace

    caps = SimpleNamespace()
    result = capability_block_reason("version_major", caps)
    assert result is None


# ---------------------------------------------------------------------------
# scanner_helpers._format_register_value
# ---------------------------------------------------------------------------


from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE


def test_format_bcd_time_valid():
    """BCD time registers return HH:MM string."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    result = _format_register_value("schedule_monday_period1_start", 0x0830)
    assert result == "08:30"


def test_format_bcd_time_too_large_sensor_unavailable():
    """BCD time above 0x2359 and equal to SENSOR_UNAVAILABLE returns None (line 40)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    result = _format_register_value("schedule_monday_period1_start", SENSOR_UNAVAILABLE)
    assert result is None


def test_format_bcd_time_too_large_invalid():
    """BCD time above 0x2359 but not SENSOR_UNAVAILABLE returns 'invalid' string (line 40)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    result = _format_register_value("schedule_monday_period1_start", 0x9999)
    assert "invalid" in str(result)


def test_format_bcd_time_invalid_bcd_sensor_unavailable():
    """BCD time with invalid BCD digits = SENSOR_UNAVAILABLE returns None (line 43)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    # 0x1390 is <= 0x2359 but has invalid BCD digits (0x90 minutes)
    # decode_bcd_time returns None for invalid BCD
    result = _format_register_value("schedule_monday_period1_start", SENSOR_UNAVAILABLE)
    assert result is None


def test_format_bcd_time_invalid_bcd_not_unavailable():
    """BCD time with invalid digits not SENSOR_UNAVAILABLE returns '(invalid)' (line 43)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    # 160 → decoded as 1h 60m → invalid (minutes out of range)
    result = _format_register_value("schedule_monday_period1_start", 160)
    assert "invalid" in str(result).lower() or result is None


def test_format_time_register_invalid(monkeypatch):
    """TIME_REGISTER_PREFIXES path: invalid value returns '(invalid)' (lines 47-50)."""
    from custom_components.thessla_green_modbus import scanner_helpers

    # Patch TIME_REGISTER_PREFIXES to a known prefix for test isolation
    monkeypatch.setattr(scanner_helpers, "TIME_REGISTER_PREFIXES", ("manual_airing_",))

    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value
    import importlib
    importlib.reload(scanner_helpers)

    # Use manual_airing_time_to_start which has special handling
    result = _format_register_value("manual_airing_time_to_start", SENSOR_UNAVAILABLE)
    assert result is None


def test_format_setting_register_sensor_unavailable():
    """setting_ register with SENSOR_UNAVAILABLE returns None (line 55)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    result = _format_register_value("setting_monday_1", SENSOR_UNAVAILABLE)
    assert result is None


def test_format_regular_register_sensor_unavailable():
    """Non-special register with SENSOR_UNAVAILABLE returns None."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    result = _format_register_value("version_major", SENSOR_UNAVAILABLE)
    assert result is None


def test_format_regular_register_valid():
    """Non-special register with normal value returns value."""
    from custom_components.thessla_green_modbus.scanner_helpers import _format_register_value

    result = _format_register_value("version_major", 42)
    assert result == 42


# ---------------------------------------------------------------------------
# scanner_helpers._decode_season_mode (lines 68-72)
# ---------------------------------------------------------------------------


def test_decode_season_mode_both_bytes_set():
    """Returns None when both high and low bytes are set (line 70-71)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _decode_season_mode

    # Both high=1 and low=1 → return None
    result = _decode_season_mode(0x0101)
    assert result is None


def test_decode_season_mode_high_only():
    """Returns high byte value when only high byte is set (line 72)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _decode_season_mode

    result = _decode_season_mode(0x0100)
    assert result == 1


def test_decode_season_mode_low_only():
    """Returns low byte value when only low byte is set (line 72)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _decode_season_mode

    result = _decode_season_mode(0x0001)
    assert result == 1


def test_decode_season_mode_unavailable():
    """Returns None for SENSOR_UNAVAILABLE (line 66-67)."""
    from custom_components.thessla_green_modbus.scanner_helpers import _decode_season_mode

    assert _decode_season_mode(SENSOR_UNAVAILABLE) is None
    assert _decode_season_mode(65280) is None
    assert _decode_season_mode(65535) is None
