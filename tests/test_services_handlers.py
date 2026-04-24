# mypy: ignore-errors
"""Tests for service handler functions in services.py."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.services import (
    _get_coordinator_from_entity_id,
    async_setup_services,
    async_unload_services,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Services:
    """Minimal service registry."""

    def __init__(self):
        self.handlers: dict = {}
        self.removed: list = []

    def async_register(self, _domain, service, handler, _schema):
        self.handlers[service] = handler

    def async_remove(self, _domain, service):
        self.removed.append(service)


class _Coordinator:
    """Minimal coordinator stub."""

    def __init__(self, write_result=True):
        self.async_write_register = AsyncMock(return_value=write_result)
        self.async_request_refresh = AsyncMock()
        self.effective_batch = 2
        self.available_registers = {
            "holding_registers": {r.name for r in get_registers_by_function("03")}
        }
        self.data = {}
        self.host = "127.0.0.1"
        self.port = 502
        self.slave_id = 1
        self.timeout = 5
        self.retry = 3
        self.scan_uart_settings = False
        self.unknown_registers = {}
        self.scanned_registers = {}


def _make_hass(coordinator=None):
    """Return a hass stub with a service registry and optional coordinator."""
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
    """Set up services and return the named handler with coordinator patched in."""
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coordinator)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


# ---------------------------------------------------------------------------
# _LogLevelManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_level_manager_set_and_restore():
    """_LogLevelManager.set_level changes log level and schedules restore."""
    from custom_components.thessla_green_modbus.services import _LogLevelManager

    hass = SimpleNamespace()
    called_with = {}

    def fake_call_later(_h, delay, cb):
        called_with["delay"] = delay
        called_with["cb"] = cb
        return lambda: None

    with patch(
        "custom_components.thessla_green_modbus.services.async_call_later",
        side_effect=fake_call_later,
    ):
        mgr = _LogLevelManager(hass)
        mgr.set_level(logging.DEBUG, 60)

    assert called_with["delay"] == 60
    target = logging.getLogger("custom_components.thessla_green_modbus")
    assert target.level == logging.DEBUG

    # Restore callback fires
    mgr._restore_level_callback(None)
    assert mgr._undo_callback is None


@pytest.mark.asyncio
async def test_log_level_manager_cancel_previous():
    """Calling set_level twice cancels the previous undo callback."""
    from custom_components.thessla_green_modbus.services import _LogLevelManager

    hass = SimpleNamespace()
    cancelled = []

    def fake_call_later(_h, _d, _cb):
        undo = MagicMock(side_effect=lambda: cancelled.append(True))
        return undo

    with patch(
        "custom_components.thessla_green_modbus.services.async_call_later",
        side_effect=fake_call_later,
    ):
        mgr = _LogLevelManager(hass)
        mgr.set_level(logging.DEBUG, 60)
        mgr.set_level(logging.INFO, 120)

    assert len(cancelled) == 1  # first undo was called


@pytest.mark.asyncio
async def test_log_level_manager_zero_duration():
    """set_level with duration=0 does not schedule a restore."""
    from custom_components.thessla_green_modbus.services import _LogLevelManager

    hass = SimpleNamespace()
    with patch("custom_components.thessla_green_modbus.services.async_call_later") as mock_later:
        mgr = _LogLevelManager(hass)
        mgr.set_level(logging.DEBUG, 0)
    mock_later.assert_not_called()


# ---------------------------------------------------------------------------
# set_debug_logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_debug_logging(monkeypatch):
    """set_debug_logging invokes _LogLevelManager.set_level."""
    coord = _Coordinator()
    hass = _make_hass(coord)
    handler = await _setup_and_get(hass, "set_debug_logging", coord, monkeypatch)

    from custom_components.thessla_green_modbus.services import _LogLevelManager

    with patch.object(_LogLevelManager, "set_level") as mock_set:
        call = _make_call({"level": "debug", "duration": 300})
        await handler(call)
        mock_set.assert_called_once_with(logging.DEBUG, 300)


# ---------------------------------------------------------------------------
# set_special_mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_special_mode_basic(monkeypatch):
    """set_special_mode writes special_mode register and refreshes."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 0})
    await handler(call)

    coord.async_write_register.assert_called_once_with("special_mode", 1, refresh=False)
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_special_mode_with_duration(monkeypatch):
    """set_special_mode writes duration register when available."""
    coord = _Coordinator()
    coord.available_registers = {"holding_registers": {"boost_duration"}}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 30})
    await handler(call)

    calls = coord.async_write_register.call_args_list
    assert any(c.args[0] == "special_mode" for c in calls)
    assert any(c.args[0] == "boost_duration" for c in calls)


@pytest.mark.asyncio
async def test_set_special_mode_write_failure(monkeypatch):
    """set_special_mode stops if write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 0})
    await handler(call)

    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_special_mode_modbus_exception(monkeypatch):
    """_write_register logs error on ModbusException."""
    coord = _Coordinator()
    coord.async_write_register.side_effect = ModbusException("fail")
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 0})
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_airflow_schedule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_airflow_schedule_basic(monkeypatch):
    """set_airflow_schedule writes schedule registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 75,
        }
    )
    await handler(call)

    coord.async_request_refresh.assert_awaited_once()
    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "schedule_summer_mon_1" in written
    assert "setting_summer_mon_1" in written
    assert not any(k.endswith("_period1_end") for k in written)


@pytest.mark.asyncio
async def test_set_airflow_schedule_with_temperature(monkeypatch):
    """set_airflow_schedule writes temp register when provided."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "friday",
            "period": 2,
            "start_time": start,
            "airflow_rate": 50,
            "temperature": 22.0,
        }
    )
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "schedule_summer_fri_2" in written
    assert "setting_summer_fri_2" in written


@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_rate(monkeypatch):
    """_clamp_airflow_rate applies min/max from coordinator data."""
    coord = _Coordinator()
    coord.data = {"min_percentage": 10, "max_percentage": 80}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 200,  # above max, should be clamped to 80
        }
    )
    await handler(call)

    setting_calls = [
        c for c in coord.async_write_register.call_args_list if c.args[0] == "setting_summer_mon_1"
    ]
    assert setting_calls
    assert setting_calls[0].args[1] == (80 << 8)


@pytest.mark.asyncio
async def test_set_airflow_schedule_write_failure(monkeypatch):
    """set_airflow_schedule aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_bypass_parameters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_bypass_parameters_basic(monkeypatch):
    """set_bypass_parameters writes bypass_mode register."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_bypass_parameters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "auto"})
    await handler(call)

    coord.async_write_register.assert_called_once_with("bypass_mode", 0, refresh=False)
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_bypass_parameters_with_temperature(monkeypatch):
    """set_bypass_parameters writes min_bypass_temperature when provided."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_bypass_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "mode": "open",
            "min_outdoor_temperature": 15.0,
        }
    )
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "bypass_mode" in written
    assert "min_bypass_temperature" in written


@pytest.mark.asyncio
async def test_set_bypass_parameters_write_failure(monkeypatch):
    """set_bypass_parameters aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_bypass_parameters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "closed"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_gwc_parameters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_gwc_parameters_basic(monkeypatch):
    """set_gwc_parameters writes gwc_mode register."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_gwc_parameters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "auto"})
    await handler(call)

    coord.async_write_register.assert_called_once_with("gwc_mode", 1, refresh=False)
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_gwc_parameters_with_temps(monkeypatch):
    """set_gwc_parameters writes optional temperature registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_gwc_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "mode": "forced",
            "min_air_temperature": 5.0,
            "max_air_temperature": 35.0,
        }
    )
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "gwc_mode" in written
    assert "min_gwc_air_temperature" in written
    assert "max_gwc_air_temperature" in written


@pytest.mark.asyncio
async def test_set_gwc_parameters_write_failure(monkeypatch):
    """set_gwc_parameters aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_gwc_parameters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "off"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_air_quality_thresholds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_air_quality_thresholds_basic(monkeypatch):
    """set_air_quality_thresholds writes CO2 and humidity registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_air_quality_thresholds", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "co2_low": 600,
            "co2_medium": 900,
            "co2_high": 1200,
            "humidity_target": 50,
        }
    )
    await handler(call)

    written = {c.args[0]: c.args[1] for c in coord.async_write_register.call_args_list}
    assert written["co2_threshold_low"] == 600
    assert written["co2_threshold_medium"] == 900
    assert written["co2_threshold_high"] == 1200
    assert written["humidity_target"] == 50
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_air_quality_thresholds_partial(monkeypatch):
    """set_air_quality_thresholds skips None values."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_air_quality_thresholds", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "co2_low": 600})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert written == ["co2_threshold_low"]


# ---------------------------------------------------------------------------
# set_temperature_curve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_temperature_curve_basic(monkeypatch):
    """set_temperature_curve writes slope and offset."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_temperature_curve", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "slope": 2.5, "offset": 1.0})
    await handler(call)

    written = {c.args[0]: c.args[1] for c in coord.async_write_register.call_args_list}
    assert written["heating_curve_slope"] == 2.5
    assert written["heating_curve_offset"] == 1.0
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_temperature_curve_with_supply_temps(monkeypatch):
    """set_temperature_curve writes optional min/max supply registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_temperature_curve", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "slope": 1.5,
            "offset": 0.5,
            "max_supply_temp": 60.0,
            "min_supply_temp": 20.0,
        }
    )
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "max_supply_temperature" in written
    assert "min_supply_temperature" in written


@pytest.mark.asyncio
async def test_set_temperature_curve_write_failure(monkeypatch):
    """set_temperature_curve aborts when slope write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_temperature_curve", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "slope": 2.0, "offset": 0.0})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# reset_filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_filters_basic(monkeypatch):
    """reset_filters writes filter_change register."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_filters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "filter_type": "flat_filters"})
    await handler(call)

    coord.async_write_register.assert_called_once_with("filter_change", 2, refresh=False)
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_filters_write_failure(monkeypatch):
    """reset_filters aborts when write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_filters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "filter_type": "presostat"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# reset_settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_settings_user(monkeypatch):
    """reset_settings(user_settings) writes hard_reset_settings."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "user_settings"})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "hard_reset_settings" in written
    assert "hard_reset_schedule" not in written
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_settings_schedule(monkeypatch):
    """reset_settings(schedule_settings) writes hard_reset_schedule."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "schedule_settings"})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "hard_reset_settings" not in written
    assert "hard_reset_schedule" in written


@pytest.mark.asyncio
async def test_reset_settings_all(monkeypatch):
    """reset_settings(all_settings) writes both reset registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "all_settings"})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "hard_reset_settings" in written
    assert "hard_reset_schedule" in written


# ---------------------------------------------------------------------------
# start_pressure_test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_pressure_test_basic(monkeypatch):
    """start_pressure_test writes day and time registers."""
    import datetime

    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "start_pressure_test", coord, monkeypatch)

    fake_now = datetime.datetime(2024, 3, 11, 14, 30)  # Monday, 14:30
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod, "dt_util", type("DT", (), {"now": staticmethod(lambda: fake_now)})()
    )

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "pres_check_day_2" in written
    assert "pres_check_time_2" in written
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_pressure_test_write_failure(monkeypatch):
    """start_pressure_test aborts when day write fails."""
    import datetime

    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "start_pressure_test", coord, monkeypatch)

    fake_now = datetime.datetime(2024, 3, 11, 14, 30)
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod, "dt_util", type("DT", (), {"now": staticmethod(lambda: fake_now)})()
    )

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_modbus_parameters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_modbus_parameters_baud_rate(monkeypatch):
    """set_modbus_parameters writes baud rate register."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_modbus_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "port": "air_b",
            "baud_rate": "9600",
        }
    )
    await handler(call)

    written = {c.args[0]: c.args[1] for c in coord.async_write_register.call_args_list}
    assert "uart_0_baud" in written
    assert written["uart_0_baud"] == 1  # 9600 → index 1
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_modbus_parameters_all_params(monkeypatch):
    """set_modbus_parameters writes baud, parity and stop_bits."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_modbus_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "port": "air_a",
            "baud_rate": "19200",
            "parity": "even",
            "stop_bits": "2",
        }
    )
    await handler(call)

    written = {c.args[0]: c.args[1] for c in coord.async_write_register.call_args_list}
    assert "uart_1_baud" in written
    assert "uart_1_parity" in written
    assert "uart_1_stop" in written
    assert written["uart_1_parity"] == 1  # even


@pytest.mark.asyncio
async def test_set_modbus_parameters_write_failure(monkeypatch):
    """set_modbus_parameters aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_modbus_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "port": "air_b",
            "baud_rate": "9600",
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_device_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_device_name_short(monkeypatch):
    """set_device_name with short name uses chunked writes."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_device_name", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "device_name": "ABC"})
    await handler(call)

    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_device_name_long(monkeypatch):
    """set_device_name with 16+ chars delegates to single write."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_device_name", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "device_name": "ABCDEFGHIJKLMNOP"})
    await handler(call)

    coord.async_write_register.assert_awaited_once_with(
        "device_name", "ABCDEFGHIJKLMNOP", refresh=False
    )
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_device_name_long_write_failure(monkeypatch):
    """set_device_name with 16+ chars aborts on write error."""
    coord = _Coordinator()
    coord.async_write_register.side_effect = ConnectionException("fail")
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_device_name", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "device_name": "ABCDEFGHIJKLMNOP"})
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_device_name_short_write_failure(monkeypatch):
    """set_device_name aborts chunked writes on exception."""
    coord = _Coordinator()
    coord.async_write_register.side_effect = ModbusException("fail")
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_device_name", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "device_name": "HELLO"})
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# refresh_device_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_device_data(monkeypatch):
    """refresh_device_data calls async_request_refresh."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "refresh_device_data", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)

    coord.async_request_refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_unknown_registers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unknown_registers(monkeypatch):
    """get_unknown_registers fires event with unknown_registers data."""
    coord = _Coordinator()
    coord.unknown_registers = {"input": [100, 101]}
    coord.scanned_registers = {"input": [100]}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "get_unknown_registers", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)

    hass.bus.async_fire.assert_called_once()
    event_data = hass.bus.async_fire.call_args[0][1]
    assert "unknown_registers" in event_data
    assert event_data["unknown_registers"] == {"input": [100, 101]}


# ---------------------------------------------------------------------------
# scan_all_registers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_all_registers(monkeypatch):
    """scan_all_registers calls scanner.scan_device and stores result."""
    coord = _Coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])

    scan_result = {"register_count": 10, "unknown_registers": {"input": [99]}}

    mock_scanner = AsyncMock()
    mock_scanner.scan_device = AsyncMock(return_value=scan_result)
    mock_scanner.close = AsyncMock()

    mock_create = AsyncMock(return_value=mock_scanner)
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]

    call = _make_call({"entity_id": ["climate.dev"]})
    result = await handler(call)

    assert result is not None
    assert "climate.dev" in result
    assert result["climate.dev"]["summary"]["register_count"] == 10
    assert coord.device_scan_result == scan_result


@pytest.mark.asyncio
async def test_scan_all_registers_no_coordinator(monkeypatch):
    """scan_all_registers returns None when no coordinator found."""
    hass = _make_hass()
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: None)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])
    await async_setup_services(hass)
    handler = hass.services.handlers["scan_all_registers"]

    call = _make_call({"entity_id": ["climate.dev"]})
    result = await handler(call)

    assert result is None


# ---------------------------------------------------------------------------
# async_unload_services
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_unload_services():
    """async_unload_services removes all registered services."""
    hass = _make_hass()
    await async_unload_services(hass)

    assert "set_special_mode" in hass.services.removed
    assert "set_debug_logging" in hass.services.removed


# ---------------------------------------------------------------------------
# _get_coordinator_from_entity_id
# ---------------------------------------------------------------------------


def test_get_coordinator_returns_none_for_unknown_entity():
    """_get_coordinator_from_entity_id returns None if entity not in registry."""
    hass = SimpleNamespace()
    registry = SimpleNamespace(async_get=lambda _e: None)
    hass.entity_registry = registry
    hass.data = {}

    result = _get_coordinator_from_entity_id(hass, "sensor.unknown")
    assert result is None


def test_get_coordinator_returns_none_no_registry():
    """_get_coordinator_from_entity_id returns None if no entity_registry attr."""
    hass = SimpleNamespace()
    hass.data = {}

    result = _get_coordinator_from_entity_id(hass, "sensor.unknown")
    assert result is None


# ---------------------------------------------------------------------------
# _extract_entity_ids — line 121 (no entity_id key)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_no_entity_id_is_noop(monkeypatch):
    """Handler silently exits when call.data has no entity_id key."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "refresh_device_data", coord, monkeypatch)

    # Pass a call with no entity_id — _extract_entity_ids returns set()
    call = _make_call({})
    await handler(call)

    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# _clamp_airflow_rate edge cases (lines 292-293, 296-297, 301)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_bad_min(monkeypatch):
    """_clamp_airflow_rate falls back to 0 when min_percentage is non-numeric."""
    coord = _Coordinator()
    coord.data = {"min_percentage": "bad", "max_percentage": 100}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_bad_max(monkeypatch):
    """_clamp_airflow_rate falls back to 150 when max_percentage is non-numeric."""
    coord = _Coordinator()
    coord.data = {"min_percentage": 10, "max_percentage": "bad"}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "tuesday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 80,
        }
    )
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_inverted_bounds(monkeypatch):
    """_clamp_airflow_rate clamps when max < min (max is set to min)."""
    coord = _Coordinator()
    coord.data = {"min_percentage": 60, "max_percentage": 30}  # inverted
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "wednesday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 10,  # below both, should clamp to 60 (min==max after fix)
        }
    )
    await handler(call)

    setting_calls = [
        c for c in coord.async_write_register.call_args_list if c.args[0] == "setting_summer_wed_1"
    ]
    assert setting_calls
    assert setting_calls[0].args[1] == (60 << 8)


# ---------------------------------------------------------------------------
# set_special_mode — duration write failure (lines 361-366)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_special_mode_duration_write_failure(monkeypatch):
    """set_special_mode continues when duration register write fails."""
    coord = _Coordinator()
    # First write (special_mode) succeeds; second (duration) fails
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    coord.available_registers = {"holding_registers": {"boost_duration"}}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 30})
    await handler(call)

    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_airflow_schedule — specific step write failures (lines 439-440, 448-449, 459-460)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_airflow_schedule_setting_write_failure(monkeypatch):
    """set_airflow_schedule aborts when AATT setting write fails (2nd write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_airflow_schedule_start_write_failure(monkeypatch):
    """set_airflow_schedule aborts when start write fails (1st write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 2,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_airflow_schedule_temp_write_failure(monkeypatch):
    """set_airflow_schedule aborts when AATT write fails with temperature."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 3,
            "start_time": start,
            "airflow_rate": 50,
            "temperature": 22.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_bypass_parameters — min_temp write failure (lines 495-496)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_bypass_parameters_min_temp_write_failure(monkeypatch):
    """set_bypass_parameters aborts when min_temperature write fails."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_bypass_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "mode": "auto",
            "min_outdoor_temperature": 5.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_gwc_parameters — min/max temp write failures (lines 532-533, 543-544)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_gwc_parameters_min_temp_write_failure(monkeypatch):
    """set_gwc_parameters aborts when min_air_temperature write fails."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_gwc_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "mode": "auto",
            "min_air_temperature": 5.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_gwc_parameters_max_temp_write_failure(monkeypatch):
    """set_gwc_parameters aborts when max_air_temperature write fails."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_gwc_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "mode": "auto",
            "min_air_temperature": 5.0,
            "max_air_temperature": 35.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


def test_set_bypass_parameters_schema_accepts_negative_min_temperature():
    """Bypass validator accepts full device range including negative values."""
    from custom_components.thessla_green_modbus.services import (
        _validate_bypass_temperature_range,
    )

    payload = {"min_outdoor_temperature": -10.0}
    assert _validate_bypass_temperature_range(payload) == payload


def test_set_bypass_parameters_schema_rejects_too_low_temperature():
    """Bypass validator rejects values below supported device range."""
    from custom_components.thessla_green_modbus.services import (
        _validate_bypass_temperature_range,
    )

    with pytest.raises(Exception, match=r"-20.0\.\.40.0"):
        _validate_bypass_temperature_range({"min_outdoor_temperature": -25.0})


def test_gwc_schema_rejects_min_ge_max():
    """Cross-field validator enforces min_air_temperature < max_air_temperature."""
    from custom_components.thessla_green_modbus.services import _validate_gwc_temperature_range

    with pytest.raises(Exception, match="strictly less than"):
        _validate_gwc_temperature_range({"min_air_temperature": 20.0, "max_air_temperature": 20.0})


# ---------------------------------------------------------------------------
# set_air_quality_thresholds — write failure path (lines 573-575, 578)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_air_quality_thresholds_write_failure(monkeypatch):
    """set_air_quality_thresholds aborts when a register write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_air_quality_thresholds", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "co2_low": 600,
            "co2_medium": 900,
        }
    )
    await handler(call)

    coord.async_request_refresh.assert_not_awaited()
    # Only one write should have been attempted (failed on first)
    assert coord.async_write_register.call_count == 1


# ---------------------------------------------------------------------------
# set_temperature_curve — step write failures (lines 610-611, 621-622, 632-633)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_temperature_curve_offset_write_failure(monkeypatch):
    """set_temperature_curve aborts when offset write fails (2nd write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_temperature_curve", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "slope": 2.0, "offset": 1.0})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_temperature_curve_max_supply_write_failure(monkeypatch):
    """set_temperature_curve aborts when max_supply write fails (3rd write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_temperature_curve", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "slope": 2.0,
            "offset": 1.0,
            "max_supply_temp": 60.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_temperature_curve_min_supply_write_failure(monkeypatch):
    """set_temperature_curve aborts when min_supply write fails (4th write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_temperature_curve", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "slope": 2.0,
            "offset": 1.0,
            "max_supply_temp": 60.0,
            "min_supply_temp": 20.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# reset_settings — write failure paths (lines 677-678, 688-689)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_settings_user_write_failure(monkeypatch):
    """reset_settings(user_settings) aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "user_settings"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_settings_schedule_write_failure(monkeypatch):
    """reset_settings(schedule_settings) aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "schedule_settings"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_settings_all_first_write_failure(monkeypatch):
    """reset_settings(all_settings) aborts when user settings write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "all_settings"})
    await handler(call)
    # Only one write attempted (user settings failed)
    assert coord.async_write_register.call_count == 1
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# start_pressure_test — time write failure (lines 722-723)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_pressure_test_time_write_failure(monkeypatch):
    """start_pressure_test aborts when pres_check_time write fails (2nd write)."""
    import datetime

    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "start_pressure_test", coord, monkeypatch)

    fake_now = datetime.datetime(2024, 3, 11, 14, 30)
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod, "dt_util", type("DT", (), {"now": staticmethod(lambda: fake_now)})()
    )

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_modbus_parameters — parity/stop write failures (lines 779-780, 790-791)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_modbus_parameters_parity_write_failure(monkeypatch):
    """set_modbus_parameters aborts when parity write fails (2nd write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_modbus_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "port": "air_b",
            "baud_rate": "9600",
            "parity": "even",
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_modbus_parameters_stop_write_failure(monkeypatch):
    """set_modbus_parameters aborts when stop_bits write fails (3rd write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_modbus_parameters", coord, monkeypatch)

    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "port": "air_b",
            "baud_rate": "9600",
            "parity": "none",
            "stop_bits": "2",
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_device_name — write_result=False paths (lines 811-812, 827-829)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_device_name_long_write_result_false(monkeypatch):
    """set_device_name with 16+ chars aborts when write returns False."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_device_name", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "device_name": "ABCDEFGHIJKLMNOP"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_device_name_short_write_result_false(monkeypatch):
    """set_device_name with short name aborts when a chunk write returns False."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_device_name", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "device_name": "HELLO"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()
