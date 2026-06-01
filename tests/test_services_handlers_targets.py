# mypy: ignore-errors
"""Split tests from test_services_handlers.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
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
        self.data = {}
        self.host = "127.0.0.1"
        self.port = 502
        self.slave_id = 1
        self.device_client = SimpleNamespace(
            scan_uart_settings=False,
            effective_batch=2,
            available_registers={
                "holding_registers": {r.name for r in get_registers_by_function("03")}
            },
            timeout=5,
            retry=3,
            unknown_registers={},
            scanned_registers={},
            device_scan_result=None,
            config=SimpleNamespace(
                host="127.0.0.1",
                port=502,
                slave_id=1,
            ),
        )


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
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


# ---------------------------------------------------------------------------
# _LogLevelManager
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
    coord.device_client.unknown_registers = {"input": [100, 101]}
    coord.device_client.scanned_registers = {"input": [100]}
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
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])

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
    assert coord.device_client.device_scan_result == scan_result


@pytest.mark.asyncio
async def test_scan_all_registers_no_coordinator(monkeypatch):
    """scan_all_registers returns None when no coordinator found."""
    hass = _make_hass()
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: None)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
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


def test_get_coordinator_returns_none_when_runtime_data_missing():
    """_get_coordinator_from_entity_id returns None when config entry has no runtime_data.

    This covers the case where a config entry is disabled or in the process of
    being unloaded so runtime_data has not been set yet.
    """
    hass = SimpleNamespace()
    entry = SimpleNamespace(config_entry_id="entry1")
    hass.entity_registry = SimpleNamespace(async_get=lambda _e: entry)
    config_entry = SimpleNamespace()  # no runtime_data attribute
    hass.config_entries = SimpleNamespace(async_get_entry=lambda _id: config_entry)

    result = _get_coordinator_from_entity_id(hass, "sensor.device")
    assert result is None


# ---------------------------------------------------------------------------
# async_extract_entity_ids — called without hass (new HA API)
# ---------------------------------------------------------------------------


def test_extract_entity_ids_with_extractor_no_hass_arg():
    """extract_entity_ids_with_extractor calls extractor with only the call object.

    The HA helper async_extract_entity_ids no longer accepts hass; confirm the
    extractor receives exactly one positional argument (the service call).
    """
    from types import SimpleNamespace as NS

    from custom_components.thessla_green_modbus.services.targets import (
        extract_entity_ids_with_extractor,
    )

    received_args: list = []

    def recording_extractor(*args, **kwargs):
        received_args.extend(args)
        return {"sensor.one"}

    call = NS(data={"entity_id": "sensor.one"})
    hass = NS()

    result = extract_entity_ids_with_extractor(hass, call, extractor=recording_extractor)

    assert result == {"sensor.one"}
    assert len(received_args) == 1, "extractor must be called with exactly one arg (call)"
    assert received_args[0] is call


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
