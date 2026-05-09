# mypy: ignore-errors
"""Tests for device clock synchronisation feature."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.clock_sync import (
    _parse_device_clock,
    _validate_drift,
    async_sync_device_clock,
    clock_sync_options,
    should_auto_sync,
    should_sync_on_start,
    sync_interval,
)
from custom_components.thessla_green_modbus.const import (
    CONF_SYNC_DEVICE_CLOCK_ENABLED,
    CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    CONF_SYNC_DEVICE_CLOCK_ON_START,
    DEFAULT_SYNC_DEVICE_CLOCK_ENABLED,
    DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_ON_START,
)
from custom_components.thessla_green_modbus.utils import encode_datetime_to_rtc_registers

# ---------------------------------------------------------------------------
# BCD encoding — known datetime values
# ---------------------------------------------------------------------------


def _to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def test_encode_datetime_bcd_structure():
    """encode_datetime_to_rtc_registers returns 4 uint16 register values."""
    dt = datetime.datetime(2024, 3, 15, 14, 30, 45)
    payload = encode_datetime_to_rtc_registers(dt)
    assert len(payload) == 4  # nosec B101
    assert all(isinstance(v, int) for v in payload)  # nosec B101
    assert all(0 <= v <= 0xFFFF for v in payload)  # nosec B101


def test_encode_datetime_yymm():
    """reg 0 encodes BCD year (2-digit) in high byte and BCD month in low byte."""
    dt = datetime.datetime(2024, 3, 15, 0, 0, 0)
    payload = encode_datetime_to_rtc_registers(dt)
    reg_yymm = payload[0]
    yy_bcd = (reg_yymm >> 8) & 0xFF
    mm_bcd = reg_yymm & 0xFF
    assert yy_bcd == _to_bcd(24)  # nosec B101
    assert mm_bcd == _to_bcd(3)   # nosec B101


def test_encode_datetime_ddtt():
    """reg 1 encodes BCD day in high byte and BCD weekday (Mon=0) in low byte."""
    dt = datetime.datetime(2024, 3, 15, 0, 0, 0)  # Friday = weekday 4
    payload = encode_datetime_to_rtc_registers(dt)
    reg_ddtt = payload[1]
    dd_bcd = (reg_ddtt >> 8) & 0xFF
    tt_bcd = reg_ddtt & 0xFF
    assert dd_bcd == _to_bcd(15)  # nosec B101
    assert tt_bcd == _to_bcd(4)   # Friday  # nosec B101


def test_encode_datetime_ggmm():
    """reg 2 encodes BCD hour in high byte and BCD minute in low byte."""
    dt = datetime.datetime(2024, 3, 15, 14, 30, 0)
    payload = encode_datetime_to_rtc_registers(dt)
    reg_ggmm = payload[2]
    hh_bcd = (reg_ggmm >> 8) & 0xFF
    mm_bcd = reg_ggmm & 0xFF
    assert hh_bcd == _to_bcd(14)  # nosec B101
    assert mm_bcd == _to_bcd(30)  # nosec B101


def test_encode_datetime_sscc():
    """reg 3 encodes BCD second in high byte; centiseconds always 0."""
    dt = datetime.datetime(2024, 3, 15, 14, 30, 45)
    payload = encode_datetime_to_rtc_registers(dt)
    reg_sscc = payload[3]
    ss_bcd = (reg_sscc >> 8) & 0xFF
    cc_bcd = reg_sscc & 0xFF
    assert ss_bcd == _to_bcd(45)  # nosec B101
    assert cc_bcd == 0x00         # nosec B101


def test_encode_datetime_midnight():
    """Midnight (00:00:00) encodes without errors."""
    dt = datetime.datetime(2000, 1, 1, 0, 0, 0)
    payload = encode_datetime_to_rtc_registers(dt)
    assert len(payload) == 4  # nosec B101


def test_encode_datetime_end_of_day():
    """23:59:59 encodes correctly."""
    dt = datetime.datetime(2099, 12, 31, 23, 59, 59)
    payload = encode_datetime_to_rtc_registers(dt)
    reg_ggmm = payload[2]
    hh = (reg_ggmm >> 8) & 0xFF
    mi = reg_ggmm & 0xFF
    assert hh == _to_bcd(23)  # nosec B101
    assert mi == _to_bcd(59)  # nosec B101


# ---------------------------------------------------------------------------
# Round-trip: encode → decoder in coordinator/capabilities.py
# ---------------------------------------------------------------------------


def _decode_rtc(values: list[int]) -> str | None:
    """Replicate _decode_device_clock from coordinator/capabilities.py."""
    raw_yymm, raw_ddtt, raw_ggmm, raw_sscc = values

    def _bcd(b: int) -> int:
        return ((b >> 4) & 0xF) * 10 + (b & 0xF)

    yy = _bcd((raw_yymm >> 8) & 0xFF)
    mm = _bcd(raw_yymm & 0xFF)
    dd = _bcd((raw_ddtt >> 8) & 0xFF)
    hh = _bcd((raw_ggmm >> 8) & 0xFF)
    mi = _bcd(raw_ggmm & 0xFF)
    ss = _bcd((raw_sscc >> 8) & 0xFF)
    year = 2000 + yy
    if 1 <= mm <= 12 and 1 <= dd <= 31 and hh <= 23 and mi <= 59 and ss <= 59:
        return f"{year:04d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}:{ss:02d}"
    return None


@pytest.mark.parametrize(
    "dt_str",
    [
        "2024-03-15T14:30:45",
        "2000-01-01T00:00:00",
        "2099-12-31T23:59:59",
        "2026-05-09T08:15:30",
    ],
)
def test_round_trip_encode_decode(dt_str: str):
    """Encoding then decoding with the existing decoder returns the same datetime."""
    dt = datetime.datetime.fromisoformat(dt_str)
    payload = encode_datetime_to_rtc_registers(dt)
    decoded = _decode_rtc(payload)
    assert decoded == dt_str  # nosec B101


# ---------------------------------------------------------------------------
# _parse_device_clock
# ---------------------------------------------------------------------------


def test_parse_device_clock_valid():
    assert _parse_device_clock("2024-03-15T14:30:45") == datetime.datetime(2024, 3, 15, 14, 30, 45)


def test_parse_device_clock_none():
    assert _parse_device_clock(None) is None


def test_parse_device_clock_empty():
    assert _parse_device_clock("") is None


def test_parse_device_clock_malformed():
    assert _parse_device_clock("not-a-date") is None


# ---------------------------------------------------------------------------
# _validate_drift
# ---------------------------------------------------------------------------


def test_validate_drift_within_threshold():
    written_at = datetime.datetime(2024, 3, 15, 14, 30, 45)
    device_clock = "2024-03-15T14:30:46"  # 1 second off
    assert _validate_drift(written_at, device_clock, 300, raise_on_failure=False)


def test_validate_drift_exceeds_threshold():
    written_at = datetime.datetime(2024, 3, 15, 14, 30, 0)
    device_clock = "2024-03-15T14:40:00"  # 600 seconds off
    result = _validate_drift(written_at, device_clock, 300, raise_on_failure=False)
    assert result is False  # nosec B101


def test_validate_drift_raises_on_failure():
    from homeassistant.exceptions import HomeAssistantError

    written_at = datetime.datetime(2024, 3, 15, 14, 30, 0)
    device_clock = "2024-03-15T14:40:00"  # 600 seconds off
    with pytest.raises(HomeAssistantError, match="drift"):
        _validate_drift(written_at, device_clock, 300, raise_on_failure=True)


def test_validate_drift_unavailable_no_raise():
    result = _validate_drift(
        datetime.datetime(2024, 3, 15, 14, 30, 0),
        None,
        300,
        raise_on_failure=False,
    )
    assert result is False  # nosec B101


def test_validate_drift_unavailable_raise():
    from homeassistant.exceptions import HomeAssistantError

    with pytest.raises(HomeAssistantError, match="read device clock"):
        _validate_drift(
            datetime.datetime(2024, 3, 15, 14, 30, 0),
            None,
            300,
            raise_on_failure=True,
        )


# ---------------------------------------------------------------------------
# async_sync_device_clock
# ---------------------------------------------------------------------------


def _make_coordinator(
    *,
    online: bool = True,
    write_result: bool = True,
    device_clock: str | None = "2024-03-15T14:30:45",
) -> MagicMock:
    coord = MagicMock()
    coord.last_update_success = online
    coord.async_write_registers = AsyncMock(return_value=write_result)
    coord.data = {"device_clock": device_clock}
    return coord


@pytest.mark.asyncio
async def test_sync_skipped_when_offline():
    """sync should return False and not write when coordinator is offline."""
    coord = _make_coordinator(online=False)
    now = datetime.datetime(2024, 3, 15, 14, 30, 45)
    result = await async_sync_device_clock(coord, now, 300, raise_on_failure=False)
    assert result is False  # nosec B101
    coord.async_write_registers.assert_not_called()


@pytest.mark.asyncio
async def test_sync_skipped_offline_raises():
    """Manual service raises HomeAssistantError when coordinator is offline."""
    from homeassistant.exceptions import HomeAssistantError

    coord = _make_coordinator(online=False)
    now = datetime.datetime(2024, 3, 15, 14, 30, 45)
    with pytest.raises(HomeAssistantError, match="offline"):
        await async_sync_device_clock(coord, now, 300, raise_on_failure=True)
    coord.async_write_registers.assert_not_called()


@pytest.mark.asyncio
async def test_sync_writes_expected_registers():
    """sync writes the correct BCD payload starting at address 0."""
    now = datetime.datetime(2024, 3, 15, 14, 30, 45)
    expected_values = encode_datetime_to_rtc_registers(now)
    # device clock matches written time exactly
    coord = _make_coordinator(device_clock="2024-03-15T14:30:45")
    result = await async_sync_device_clock(coord, now, 300)
    assert result is True  # nosec B101
    coord.async_write_registers.assert_called_once_with(
        start_address=0,
        values=expected_values,
        refresh=True,
    )


@pytest.mark.asyncio
async def test_sync_returns_false_on_write_failure():
    """sync returns False when write returns failure."""
    coord = _make_coordinator(write_result=False)
    now = datetime.datetime(2024, 3, 15, 14, 30, 0)
    result = await async_sync_device_clock(coord, now, 300, raise_on_failure=False)
    assert result is False  # nosec B101


@pytest.mark.asyncio
async def test_sync_raises_on_write_failure():
    """sync raises HomeAssistantError when write fails and raise_on_failure=True."""
    from homeassistant.exceptions import HomeAssistantError

    coord = _make_coordinator(write_result=False)
    now = datetime.datetime(2024, 3, 15, 14, 30, 0)
    with pytest.raises(HomeAssistantError, match="failure"):
        await async_sync_device_clock(coord, now, 300, raise_on_failure=True)


@pytest.mark.asyncio
async def test_sync_raises_on_modbus_exception():
    """sync raises HomeAssistantError when ModbusException occurs."""
    from custom_components.thessla_green_modbus.modbus_exceptions import ModbusException
    from homeassistant.exceptions import HomeAssistantError

    coord = _make_coordinator()
    coord.async_write_registers = AsyncMock(side_effect=ModbusException("boom"))
    now = datetime.datetime(2024, 3, 15, 14, 30, 0)
    with pytest.raises(HomeAssistantError, match="boom"):
        await async_sync_device_clock(coord, now, 300, raise_on_failure=True)


@pytest.mark.asyncio
async def test_sync_returns_false_on_modbus_exception_no_raise():
    """sync returns False on ModbusException when raise_on_failure=False."""
    from custom_components.thessla_green_modbus.modbus_exceptions import ModbusException

    coord = _make_coordinator()
    coord.async_write_registers = AsyncMock(side_effect=ModbusException("boom"))
    now = datetime.datetime(2024, 3, 15, 14, 30, 0)
    result = await async_sync_device_clock(coord, now, 300, raise_on_failure=False)
    assert result is False  # nosec B101


@pytest.mark.asyncio
async def test_sync_drift_validation_failure():
    """sync returns False when device clock drift exceeds threshold."""
    # device reports a time 1 hour off from written time
    coord = _make_coordinator(device_clock="2024-03-15T15:30:45")
    now = datetime.datetime(2024, 3, 15, 14, 30, 45)
    result = await async_sync_device_clock(coord, now, 300, raise_on_failure=False)
    assert result is False  # nosec B101


@pytest.mark.asyncio
async def test_sync_drift_validation_raise():
    """sync raises HomeAssistantError when drift exceeds threshold and raise_on_failure=True."""
    from homeassistant.exceptions import HomeAssistantError

    coord = _make_coordinator(device_clock="2024-03-15T15:30:45")
    now = datetime.datetime(2024, 3, 15, 14, 30, 45)
    with pytest.raises(HomeAssistantError, match="drift"):
        await async_sync_device_clock(coord, now, 300, raise_on_failure=True)


@pytest.mark.asyncio
async def test_sync_device_clock_unavailable_after_write():
    """sync returns False when device clock is None after write (no raise)."""
    coord = _make_coordinator(device_clock=None)
    now = datetime.datetime(2024, 3, 15, 14, 30, 45)
    result = await async_sync_device_clock(coord, now, 300, raise_on_failure=False)
    assert result is False  # nosec B101


# ---------------------------------------------------------------------------
# Options helpers
# ---------------------------------------------------------------------------


def test_clock_sync_options_defaults():
    opts = clock_sync_options({})
    assert opts[CONF_SYNC_DEVICE_CLOCK_ENABLED] == DEFAULT_SYNC_DEVICE_CLOCK_ENABLED  # nosec B101
    assert opts[CONF_SYNC_DEVICE_CLOCK_ON_START] == DEFAULT_SYNC_DEVICE_CLOCK_ON_START  # nosec B101
    assert opts[CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS] == DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS  # nosec B101
    assert opts[CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS] == DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS  # nosec B101


def test_clock_sync_options_custom():
    opts = clock_sync_options(
        {
            CONF_SYNC_DEVICE_CLOCK_ENABLED: True,
            CONF_SYNC_DEVICE_CLOCK_ON_START: True,
            CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: 12,
            CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: 60,
        }
    )
    assert opts[CONF_SYNC_DEVICE_CLOCK_ENABLED] is True  # nosec B101
    assert opts[CONF_SYNC_DEVICE_CLOCK_ON_START] is True  # nosec B101
    assert opts[CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS] == 12  # nosec B101
    assert opts[CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS] == 60  # nosec B101


def test_should_auto_sync_disabled_by_default():
    assert should_auto_sync({}) is False  # nosec B101


def test_should_auto_sync_enabled():
    assert should_auto_sync({CONF_SYNC_DEVICE_CLOCK_ENABLED: True}) is True  # nosec B101


def test_should_sync_on_start_disabled_by_default():
    assert should_sync_on_start({}) is False  # nosec B101


def test_should_sync_on_start_enabled():
    assert should_sync_on_start({CONF_SYNC_DEVICE_CLOCK_ON_START: True}) is True  # nosec B101


def test_sync_interval_default():
    from datetime import timedelta

    assert sync_interval({}) == timedelta(hours=DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS)  # nosec B101


def test_sync_interval_custom():
    from datetime import timedelta

    assert sync_interval({CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: 48}) == timedelta(hours=48)  # nosec B101


def test_sync_interval_clamped_min():
    from datetime import timedelta

    assert sync_interval({CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: 0}) == timedelta(hours=1)  # nosec B101


def test_sync_interval_clamped_max():
    from datetime import timedelta

    assert sync_interval({CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: 999}) == timedelta(hours=168)  # nosec B101


# ---------------------------------------------------------------------------
# Service registration
# ---------------------------------------------------------------------------


def test_sync_device_clock_service_registered():
    """sync_device_clock service is in REGISTERED_SERVICE_NAMES."""
    from custom_components.thessla_green_modbus.services import REGISTERED_SERVICE_NAMES

    assert "sync_device_clock" in REGISTERED_SERVICE_NAMES  # nosec B101


def test_sync_time_service_still_registered():
    """sync_time service is preserved for backward compatibility."""
    from custom_components.thessla_green_modbus.services import REGISTERED_SERVICE_NAMES

    assert "sync_time" in REGISTERED_SERVICE_NAMES  # nosec B101


# ---------------------------------------------------------------------------
# Manual service call — writes correct register values
# ---------------------------------------------------------------------------


class _Services:
    def __init__(self):
        self.handlers: dict = {}

    def async_register(self, _domain, service, handler, _schema):
        self.handlers[service] = handler

    def async_remove(self, _domain, service):
        pass


class _WritableCoordinator:
    def __init__(self, *, write_result=True, device_clock="2024-03-15T14:30:45"):
        self.last_update_success = True
        self.async_write_registers = AsyncMock(return_value=write_result)
        self.async_write_register = AsyncMock(return_value=write_result)
        self.async_request_refresh = AsyncMock()
        self.data = {"device_clock": device_clock}
        self.entry = SimpleNamespace(
            options={CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: 300}
        )
        self.effective_batch = 2
        self.available_registers = {"holding_registers": set()}
        self.host = "127.0.0.1"
        self.port = 502
        self.slave_id = 1
        self.timeout = 5
        self.retry = 3
        self.scan_uart_settings = False
        self.unknown_registers = {}
        self.scanned_registers = {}


def _make_hass(coordinator=None):
    hass = SimpleNamespace()
    hass.services = _Services()
    hass.data = {}
    hass.bus = SimpleNamespace(async_fire=MagicMock())
    if coordinator is not None:
        from custom_components.thessla_green_modbus.const import DOMAIN
        hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


def _make_call(data: dict):
    return SimpleNamespace(data=data)


async def _setup_and_get(hass, service_name, coordinator, monkeypatch):
    from custom_components.thessla_green_modbus import services as svc_mod
    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coordinator)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])
    from custom_components.thessla_green_modbus.services import async_setup_services
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


@pytest.mark.asyncio
async def test_sync_device_clock_service_writes_correct_payload(monkeypatch):
    """sync_device_clock service calls write_registers with the BCD payload."""
    import datetime as _dt_mod

    fake_now = _dt_mod.datetime(2024, 3, 15, 14, 30, 45)
    coord = _WritableCoordinator(device_clock="2024-03-15T14:30:45")
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod,
        "dt_util",
        type("DT", (), {"now": staticmethod(lambda: fake_now)})(),
    )
    handler = await _setup_and_get(hass, "sync_device_clock", coord, monkeypatch)
    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)

    expected = encode_datetime_to_rtc_registers(fake_now)
    coord.async_write_registers.assert_called_once_with(
        start_address=0,
        values=expected,
        refresh=True,
    )


@pytest.mark.asyncio
async def test_sync_device_clock_service_offline_raises(monkeypatch):
    """sync_device_clock raises HomeAssistantError when device is offline."""
    from homeassistant.exceptions import HomeAssistantError

    coord = _WritableCoordinator()
    coord.last_update_success = False
    hass = _make_hass()

    handler = await _setup_and_get(hass, "sync_device_clock", coord, monkeypatch)
    call = _make_call({"entity_id": ["climate.dev"]})
    with pytest.raises(HomeAssistantError):
        await handler(call)
    coord.async_write_registers.assert_not_called()


@pytest.mark.asyncio
async def test_sync_device_clock_service_drift_exceeded_raises(monkeypatch):
    """sync_device_clock raises HomeAssistantError when drift exceeds threshold."""
    from homeassistant.exceptions import HomeAssistantError

    # device clock is 1 hour ahead — exceeds 300s threshold
    coord = _WritableCoordinator(device_clock="2024-03-15T15:30:45")
    hass = _make_hass()

    import datetime as _dt_mod

    fake_now = _dt_mod.datetime(2024, 3, 15, 14, 30, 45)
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod,
        "dt_util",
        type("DT", (), {"now": staticmethod(lambda: fake_now)})(),
    )
    handler = await _setup_and_get(hass, "sync_device_clock", coord, monkeypatch)
    call = _make_call({"entity_id": ["climate.dev"]})
    with pytest.raises(HomeAssistantError, match="drift"):
        await handler(call)


# ---------------------------------------------------------------------------
# Auto-sync options — should_auto_sync / should_sync_on_start
# ---------------------------------------------------------------------------


def test_auto_sync_does_not_run_when_disabled():
    """Automatic sync must not occur when the option is disabled (default)."""
    # Default options — sync disabled
    opts = {}
    assert not should_auto_sync(opts)  # nosec B101
    # Explicit disable
    opts2 = {CONF_SYNC_DEVICE_CLOCK_ENABLED: False}
    assert not should_auto_sync(opts2)  # nosec B101


def test_on_start_sync_does_not_run_when_disabled():
    opts = {CONF_SYNC_DEVICE_CLOCK_ENABLED: True, CONF_SYNC_DEVICE_CLOCK_ON_START: False}
    assert not should_sync_on_start(opts)  # nosec B101


def test_on_start_sync_runs_when_enabled():
    opts = {CONF_SYNC_DEVICE_CLOCK_ENABLED: True, CONF_SYNC_DEVICE_CLOCK_ON_START: True}
    assert should_sync_on_start(opts)  # nosec B101
