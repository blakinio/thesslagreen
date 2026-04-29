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

