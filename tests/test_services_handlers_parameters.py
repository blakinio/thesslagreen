# mypy: ignore-errors
"""Split tests from test_services_handlers.py."""


from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.services import (
    async_setup_services,
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

