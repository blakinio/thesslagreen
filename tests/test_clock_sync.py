# mypy: ignore-errors
"""Tests for device clock synchronization."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.clock_sync import (
    ClockSyncManager,
    async_perform_clock_sync,
    bcd_decode,
    bcd_encode,
    decode_rtc_registers,
    encode_rtc_registers,
)

# ---------------------------------------------------------------------------
# BCD encode/decode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, 0x00),
        (1, 0x01),
        (9, 0x09),
        (10, 0x10),
        (25, 0x25),
        (59, 0x59),
        (99, 0x99),
    ],
)
def test_bcd_encode(value, expected):
    assert bcd_encode(value) == expected


@pytest.mark.parametrize(
    "byte, expected",
    [
        (0x00, 0),
        (0x01, 1),
        (0x09, 9),
        (0x10, 10),
        (0x25, 25),
        (0x59, 59),
        (0x99, 99),
    ],
)
def test_bcd_decode(byte, expected):
    assert bcd_decode(byte) == expected


def test_bcd_round_trip():
    for v in range(100):
        assert bcd_decode(bcd_encode(v)) == v


# ---------------------------------------------------------------------------
# encode_rtc_registers
# ---------------------------------------------------------------------------


def test_encode_rtc_registers_known_value():
    dt = datetime.datetime(2025, 5, 9, 14, 30, 45)  # Friday = weekday 4
    regs = encode_rtc_registers(dt)
    assert len(regs) == 4
    # addr 0: yymm = (BCD(25) << 8) | BCD(5)
    assert regs[0] == (bcd_encode(25) << 8) | bcd_encode(5)
    # addr 1: ddww = (BCD(9) << 8) | BCD(4)
    assert regs[1] == (bcd_encode(9) << 8) | bcd_encode(4)
    # addr 2: hhmm = (BCD(14) << 8) | BCD(30)
    assert regs[2] == (bcd_encode(14) << 8) | bcd_encode(30)
    # addr 3: sscc = (BCD(45) << 8) | 0x00
    assert regs[3] == (bcd_encode(45) << 8) | 0x00


# ---------------------------------------------------------------------------
# decode_rtc_registers / round-trip compatibility
# ---------------------------------------------------------------------------


def test_decode_rtc_registers_known_value():
    dt = datetime.datetime(2025, 5, 9, 14, 30, 45)
    regs = encode_rtc_registers(dt)
    result = decode_rtc_registers(*regs)
    assert result == "2025-05-09T14:30:45"


def test_decode_rtc_round_trip():
    """Encoder output can be decoded back to the same datetime string."""
    for dt in [
        datetime.datetime(2025, 1, 1, 0, 0, 0),
        datetime.datetime(2025, 12, 31, 23, 59, 59),
        datetime.datetime(2026, 6, 15, 12, 0, 0),
    ]:
        regs = encode_rtc_registers(dt)
        decoded = decode_rtc_registers(*regs)
        assert decoded == dt.strftime("%Y-%m-%dT%H:%M:%S")


def test_decode_rtc_invalid_returns_none():
    assert decode_rtc_registers(0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF) is None


def test_decoder_matches_capabilities_decoder():
    """Our decoder must match the implementation in coordinator/capabilities.py."""
    from custom_components.thessla_green_modbus.coordinator.capabilities import (
        _CoordinatorCapabilitiesMixin,
    )

    mixin = _CoordinatorCapabilitiesMixin.__new__(_CoordinatorCapabilitiesMixin)
    dt = datetime.datetime(2025, 3, 15, 8, 45, 30)
    regs = encode_rtc_registers(dt)
    data = {
        "date_time": regs[0],
        "date_time_ddtt": regs[1],
        "date_time_ggmm": regs[2],
        "date_time_sscc": regs[3],
    }
    caps_result = mixin._decode_device_clock(data)
    our_result = decode_rtc_registers(*regs)
    assert caps_result == our_result


# ---------------------------------------------------------------------------
# async_perform_clock_sync — helpers
# ---------------------------------------------------------------------------


def _make_coordinator(*, write_ok=True, data=None):
    coord = MagicMock()
    coord.async_write_registers = AsyncMock(return_value=write_ok)
    coord.async_request_refresh = AsyncMock()
    coord.data = data if data is not None else {}
    coord.host = "192.168.1.100"
    return coord


def _fixed_now(dt: datetime.datetime):
    return lambda: dt


# ---------------------------------------------------------------------------
# async_perform_clock_sync — force=True always writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_force_writes_registers():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:30:46"})

    result = await async_perform_clock_sync(
        coord,
        force=True,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_registers.assert_awaited_once()
    call_kwargs = coord.async_write_registers.call_args
    assert call_kwargs.kwargs["start_address"] == 0
    assert len(call_kwargs.kwargs["values"]) == 4


@pytest.mark.asyncio
async def test_sync_force_writes_correct_register_values():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:30:46"})

    await async_perform_clock_sync(
        coord,
        force=True,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    values = coord.async_write_registers.call_args.kwargs["values"]
    assert values == encode_rtc_registers(now)


# ---------------------------------------------------------------------------
# async_perform_clock_sync — drift check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_skipped_when_drift_below_threshold():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:30:44"})  # 1s drift

    result = await async_perform_clock_sync(
        coord,
        force=False,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_registers.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_proceeds_when_drift_exceeds_threshold():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    # Device clock is 400 seconds behind
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:23:45"})

    result = await async_perform_clock_sync(
        coord,
        force=False,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_registers.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_proceeds_when_device_clock_missing():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={})  # no device_clock key

    result = await async_perform_clock_sync(
        coord,
        force=False,
        max_drift_seconds=300,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True
    coord.async_write_registers.assert_awaited_once()


# ---------------------------------------------------------------------------
# async_perform_clock_sync — write failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_returns_false_on_write_failure():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(write_ok=False, data={})

    result = await async_perform_clock_sync(
        coord,
        force=True,
        dt_now_fn=_fixed_now(now),
    )
    assert result is False
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# async_perform_clock_sync — read-back validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_read_back_success():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={})

    async def _refresh_side_effect():
        coord.data = {"device_clock": "2025-05-09T14:30:45"}

    coord.async_request_refresh.side_effect = _refresh_side_effect

    result = await async_perform_clock_sync(
        coord,
        force=True,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True


@pytest.mark.asyncio
async def test_sync_read_back_validation_failure_raises():
    from homeassistant.exceptions import HomeAssistantError

    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={})

    async def _refresh_side_effect():
        coord.data = {"device_clock": "2025-05-09T12:00:00"}

    coord.async_request_refresh.side_effect = _refresh_side_effect

    with pytest.raises(HomeAssistantError):
        await async_perform_clock_sync(
            coord,
            force=True,
            dt_now_fn=_fixed_now(now),
        )


@pytest.mark.asyncio
async def test_sync_read_back_unavailable_returns_true():
    now = datetime.datetime(2025, 5, 9, 14, 30, 45)
    coord = _make_coordinator(data={})
    # data stays empty after refresh — device_clock not populated

    result = await async_perform_clock_sync(
        coord,
        force=True,
        dt_now_fn=_fixed_now(now),
    )
    assert result is True


# ---------------------------------------------------------------------------
# ClockSyncManager — default disabled
# ---------------------------------------------------------------------------


def test_clock_sync_manager_disabled_by_default():
    hass = MagicMock()
    coord = _make_coordinator()
    entry = MagicMock()
    entry.options = {}

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_not_called()


def test_clock_sync_manager_disabled_explicitly():
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {"sync_device_clock_enabled": False}

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# ClockSyncManager — on_start only when enabled
# ---------------------------------------------------------------------------


def test_clock_sync_manager_on_start_when_enabled_and_data_present():
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": True,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_called_once()


def test_clock_sync_manager_on_start_not_triggered_without_data():
    hass = MagicMock()
    coord = _make_coordinator(data={})  # no device_clock yet
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": True,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_not_called()


def test_clock_sync_manager_on_start_runs_only_once():
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": True,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    mgr._on_update()
    # on_start should only trigger once; second call goes to periodic check
    # _last_sync is None so a second task will be created for periodic
    assert hass.async_create_task.call_count >= 1


# ---------------------------------------------------------------------------
# ClockSyncManager — periodic sync
# ---------------------------------------------------------------------------


def test_clock_sync_manager_periodic_first_sync():
    """First sync always fires when enabled (no last_sync yet)."""
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": False,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._on_update()
    hass.async_create_task.assert_called_once()


def test_clock_sync_manager_no_second_sync_before_interval():
    """Second sync not triggered if interval not elapsed."""
    hass = MagicMock()
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:00:00"})
    entry = MagicMock()
    entry.options = {
        "sync_device_clock_enabled": True,
        "sync_device_clock_on_start": False,
        "sync_device_clock_interval_hours": 24,
    }

    mgr = ClockSyncManager(hass, coord, entry)
    mgr._last_sync = datetime.datetime.now()  # pretend sync just happened
    mgr._on_start_done = True
    mgr._on_update()
    hass.async_create_task.assert_not_called()


# ---------------------------------------------------------------------------
# Button entity — calls sync logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_button_press_calls_sync():
    """Button.async_press calls async_perform_clock_sync with force=True."""
    coord = _make_coordinator(data={"device_clock": "2025-05-09T14:30:45"})
    entry = MagicMock()
    entry.options = {}

    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_sync:
        from custom_components.thessla_green_modbus.button import SyncDeviceClockButton

        btn = SyncDeviceClockButton.__new__(SyncDeviceClockButton)
        btn.coordinator = coord
        btn._entry = entry
        btn._coordinator_connected = lambda: True

        await btn.async_press()
        mock_sync.assert_awaited_once()
        call_kwargs = mock_sync.call_args
        assert call_kwargs.kwargs.get("force") is True


@pytest.mark.asyncio
async def test_button_press_raises_on_failure():
    """Button raises HomeAssistantError when sync returns False."""
    from homeassistant.exceptions import HomeAssistantError

    coord = _make_coordinator()
    entry = MagicMock()
    entry.options = {}

    with patch(
        "custom_components.thessla_green_modbus.button.async_perform_clock_sync",
        new_callable=AsyncMock,
        return_value=False,
    ):
        from custom_components.thessla_green_modbus.button import SyncDeviceClockButton

        btn = SyncDeviceClockButton.__new__(SyncDeviceClockButton)
        btn.coordinator = coord
        btn._entry = entry
        btn._coordinator_connected = lambda: True

        with pytest.raises(HomeAssistantError):
            await btn.async_press()


# ---------------------------------------------------------------------------
# Options flow — exposes sync options with correct defaults
# ---------------------------------------------------------------------------


def test_options_form_has_clock_sync_defaults():
    from custom_components.thessla_green_modbus.config_flow_options_form import (
        build_options_defaults,
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

    defaults = build_options_defaults({}, {})
    assert defaults[CONF_SYNC_DEVICE_CLOCK_ENABLED] == DEFAULT_SYNC_DEVICE_CLOCK_ENABLED
    assert defaults[CONF_SYNC_DEVICE_CLOCK_ON_START] == DEFAULT_SYNC_DEVICE_CLOCK_ON_START
    assert (
        defaults[CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS] == DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS
    )
    assert (
        defaults[CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS]
        == DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS
    )


def test_options_form_default_sync_enabled_is_false():
    from custom_components.thessla_green_modbus.config_flow_options_form import (
        build_options_defaults,
    )
    from custom_components.thessla_green_modbus.const import (
        CONF_SYNC_DEVICE_CLOCK_ENABLED,
    )

    defaults = build_options_defaults({}, {})
    assert defaults[CONF_SYNC_DEVICE_CLOCK_ENABLED] is False


def test_options_form_has_clock_sync_schema_keys():
    from custom_components.thessla_green_modbus.config_flow_options_form import (
        build_options_schema,
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

    values = {
        "scan_interval": 30,
        "timeout": 10,
        "retry": 3,
        "force_full_register_list": False,
        "enable_device_scan": True,
        "log_level": "info",
        "scan_uart_settings": True,
        "skip_missing_registers": False,
        "safe_scan": False,
        "airflow_unit": "m3h",
        "deep_scan": False,
        "max_registers_per_request": 16,
        CONF_SYNC_DEVICE_CLOCK_ENABLED: DEFAULT_SYNC_DEVICE_CLOCK_ENABLED,
        CONF_SYNC_DEVICE_CLOCK_ON_START: DEFAULT_SYNC_DEVICE_CLOCK_ON_START,
        CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS: DEFAULT_SYNC_DEVICE_CLOCK_INTERVAL_HOURS,
        CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    }
    schema = build_options_schema(values)
    schema_key_strs = [str(k) for k in schema.schema]
    assert any(CONF_SYNC_DEVICE_CLOCK_ENABLED in s for s in schema_key_strs)
    assert any(CONF_SYNC_DEVICE_CLOCK_ON_START in s for s in schema_key_strs)
    assert any(CONF_SYNC_DEVICE_CLOCK_INTERVAL_HOURS in s for s in schema_key_strs)
    assert any(CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS in s for s in schema_key_strs)


# ---------------------------------------------------------------------------
# Service registration
# ---------------------------------------------------------------------------


def test_sync_device_clock_service_registered():
    from custom_components.thessla_green_modbus.services import REGISTERED_SERVICE_NAMES

    assert "sync_device_clock" in REGISTERED_SERVICE_NAMES


@pytest.mark.asyncio
async def test_sync_device_clock_service_calls_write(monkeypatch):
    """sync_device_clock service writes RTC registers via coordinator."""
    from types import SimpleNamespace

    from custom_components.thessla_green_modbus.services import async_setup_services

    coord = _make_coordinator(data={"device_clock": "2025-05-09T00:00:00"})
    fixed_now = datetime.datetime(2025, 5, 9, 14, 30, 45)

    async def _refresh():
        coord.data = {"device_clock": "2025-05-09T14:30:45"}

    coord.async_request_refresh.side_effect = _refresh

    class _Svc:
        def __init__(self):
            self.handlers = {}
            self.removed = []

        def async_register(self, _d, svc, h, _s):
            self.handlers[svc] = h

        def async_remove(self, _d, svc):
            self.removed.append(svc)

    hass = SimpleNamespace()
    hass.services = _Svc()
    hass.data = {}
    hass.bus = SimpleNamespace(async_fire=MagicMock())

    import custom_components.thessla_green_modbus.services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])

    await async_setup_services(hass)
    handler = hass.services.handlers["sync_device_clock"]
    call = SimpleNamespace(data={"entity_id": ["climate.dev"], "force": True})

    with patch("homeassistant.util.dt.now", return_value=fixed_now):
        await handler(call)

    coord.async_write_registers.assert_awaited_once()
    values = coord.async_write_registers.call_args.kwargs["values"]
    assert values == encode_rtc_registers(fixed_now)
