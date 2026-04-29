"""Register and parameter-coercion scanner coverage tests."""

from unittest.mock import patch

import pytest
from custom_components.thessla_green_modbus.const import (
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


@pytest.mark.asyncio
async def test_param_coerce_backoff_invalid():
    """Lines 446-447: backoff='invalid' falls back to 0.0."""
    scanner = await _make_scanner(backoff="invalid")
    assert scanner.backoff == 0.0


@pytest.mark.asyncio
async def test_param_coerce_backoff_jitter_string_valid():
    """Lines 451-452: backoff_jitter='3.14' parsed to float."""
    scanner = await _make_scanner(backoff_jitter="3.14")
    assert scanner.backoff_jitter == pytest.approx(3.14)


@pytest.mark.asyncio
async def test_param_coerce_backoff_jitter_string_invalid():
    """Lines 453-454: backoff_jitter='bad' → jitter=None."""
    scanner = await _make_scanner(backoff_jitter="bad")
    assert scanner.backoff_jitter is None


@pytest.mark.asyncio
async def test_param_coerce_backoff_jitter_list():
    """Lines 455-458: backoff_jitter=[1.0, 2.0] → tuple."""
    scanner = await _make_scanner(backoff_jitter=[1.0, 2.0])
    assert scanner.backoff_jitter == (1.0, 2.0)


@pytest.mark.asyncio
async def test_param_coerce_backoff_jitter_list_invalid():
    """Lines 458-459: backoff_jitter=[None, 'x'] → jitter=None."""
    scanner = await _make_scanner(backoff_jitter=[None, "x"])
    assert scanner.backoff_jitter is None


@pytest.mark.asyncio
async def test_param_coerce_backoff_jitter_zero():
    """Lines 462-463: backoff_jitter=0 → jitter=0.0."""
    scanner = await _make_scanner(backoff_jitter=0)
    assert scanner.backoff_jitter == 0.0


@pytest.mark.asyncio
async def test_param_coerce_max_registers_string():
    """Lines 472-473: max_registers_per_request='16' parsed to int."""
    scanner = await _make_scanner(max_registers_per_request="16")
    assert scanner.effective_batch == 16


@pytest.mark.asyncio
async def test_param_coerce_max_registers_zero():
    """Lines 475-476: max_registers_per_request=0 → effective_batch=1."""
    scanner = await _make_scanner(max_registers_per_request=0)
    assert scanner.effective_batch == 1


@pytest.mark.asyncio
async def test_param_coerce_baud_rate_none():
    """Lines 490-491: baud_rate=None → DEFAULT_BAUD_RATE."""
    scanner = await _make_scanner(baud_rate=None)
    assert scanner.baud_rate == DEFAULT_BAUD_RATE


@pytest.mark.asyncio
async def test_param_coerce_parity_invalid():
    """Lines 493-494: parity='xyz' → DEFAULT_PARITY."""
    scanner = await _make_scanner(parity="xyz")
    assert scanner.parity == DEFAULT_PARITY.lower()


@pytest.mark.asyncio
async def test_param_coerce_stop_bits_invalid():
    """Lines 500-501: stop_bits=99 → DEFAULT_STOP_BITS."""
    scanner = await _make_scanner(stop_bits=99)
    assert scanner.stop_bits == DEFAULT_STOP_BITS


@pytest.mark.asyncio
async def test_is_valid_temperature_sensor_unavailable():
    """Temperature register with SENSOR_UNAVAILABLE means sensor not connected — register EXISTS."""
    scanner = await _make_scanner()
    scanner._register_ranges = {}
    # A register with 'temperature' in its name: 0x8000 means sensor disconnected, not absent
    result = scanner._is_valid_register_value("coolant_temperature_extra", SENSOR_UNAVAILABLE)
    assert result is True


@pytest.mark.asyncio
async def test_is_valid_bcd_time_invalid_value():
    """Lines 895-897: schedule register with invalid BCD time is invalid."""
    scanner = await _make_scanner()
    scanner._register_ranges = {}
    # 0x2500 → hours=25, invalid BCD and decimal 9472//100=94 also invalid
    result = scanner._is_valid_register_value("schedule_weekly_1", 0x2500)
    assert result is False


@pytest.mark.asyncio
async def test_is_valid_bcd_time_valid_value():
    """Lines 895-897: schedule register with valid BCD time passes."""
    scanner = await _make_scanner()
    scanner._register_ranges = {}
    # 0x0800 → BCD 08:00, valid
    result = scanner._is_valid_register_value("schedule_weekly_1", 0x0800)
    assert result is True


@pytest.mark.asyncio
async def test_param_coerce_max_registers_invalid_string():
    """Lines 473-474: max_registers_per_request='bad' → MAX_BATCH_REGISTERS."""
    from custom_components.thessla_green_modbus.scanner_helpers import MAX_BATCH_REGISTERS

    scanner = await _make_scanner(max_registers_per_request="bad")
    assert scanner.effective_batch == MAX_BATCH_REGISTERS


@pytest.mark.asyncio
async def test_stop_bits_map_returns_out_of_range():
    """Line 501: SERIAL_STOP_BITS_MAP returns 3 → clamped to DEFAULT_STOP_BITS."""
    with patch(
        "custom_components.thessla_green_modbus.scanner.core.SERIAL_STOP_BITS_MAP",
        {1: 3},
    ):
        scanner = await _make_scanner(stop_bits=1)
    assert scanner.stop_bits == DEFAULT_STOP_BITS

