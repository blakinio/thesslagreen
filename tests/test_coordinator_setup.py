"""Coordinator setup/init focused tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
    _utcnow,
)


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


def test_utcnow_returns_timezone_aware_datetime():
    """_utcnow should always return timezone-aware datetime."""
    result = _utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# Group B — __init__ invalid parameter values (lines 310-376)
# ---------------------------------------------------------------------------


def test_coordinator_init_bad_backoff_falls_back():
    """ValueError in float(backoff) is caught; self.backoff = DEFAULT_BACKOFF (lines 310-313)."""
    coord = _make_coordinator(backoff="not_a_float")
    from custom_components.thessla_green_modbus.const import DEFAULT_BACKOFF

    assert coord.backoff == DEFAULT_BACKOFF


def test_coordinator_init_bad_baud_rate_falls_back():
    """ValueError in int(baud_rate) is caught; self.baud_rate = DEFAULT_BAUD_RATE (lines 348-351)."""
    coord = _make_coordinator(baud_rate="not_an_int")
    from custom_components.thessla_green_modbus.const import DEFAULT_BAUD_RATE

    assert coord.baud_rate == DEFAULT_BAUD_RATE


def test_coordinator_init_jitter_list_two_floats():
    """backoff_jitter as list with 2 elements creates tuple jitter (lines 323-327)."""
    coord = _make_coordinator(backoff_jitter=[0.1, 0.5])
    assert coord.backoff_jitter == (0.1, 0.5)


def test_coordinator_init_jitter_string_float():
    """backoff_jitter as string float is parsed to float (lines 318-322)."""
    coord = _make_coordinator(backoff_jitter="0.3")
    assert coord.backoff_jitter == 0.3


def test_coordinator_init_jitter_bad_string():
    """backoff_jitter as bad string falls back to None (lines 319-322)."""
    coord = _make_coordinator(backoff_jitter="bad")
    assert coord.backoff_jitter is None


def test_coordinator_init_jitter_zero():
    """backoff_jitter = 0 is stored as 0.0 (line 331-332)."""
    coord = _make_coordinator(backoff_jitter=0)
    assert coord.backoff_jitter == 0.0


