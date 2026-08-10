# mypy: ignore-errors
"""Service target and diagnostics handler tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.services import (
    _get_coordinator_from_entity_id,
    async_setup_services,
    async_unload_services,
)


class _AsyncLock:
    """Minimal async lock used by isolated scan tests."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Services:
    """Minimal service registry."""

    def __init__(self):
        self.handlers: dict = {}
        self.removed: list = []

    def async_register(self, _domain, service, handler, _schema=None, supports_response=None):
        self.handlers[service] = handler

    def async_remove(self, _domain, service):
        self.removed.append(service)


class _Coordinator:
    """Minimal coordinator stub."""

    def __init__(self, write_result=True):
        self.async_write_register = AsyncMock(return_value=write_result)
        self.async_request_refresh = AsyncMock()
        self.data = {}
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
            _write_lock=_AsyncLock(),
            async_disconnect=AsyncMock(),
            async_ensure_connected=AsyncMock(return_value=True),
            config=SimpleNamespace(
                host="127.0.0.1",
                port=502,
                slave_id=1,
                connection_type="tcp",
                connection_mode="tcp",
                serial_port="/dev/ttyUSB0",
                baud_rate=115200,
                parity="N",
                stop_bits=1,
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
    monkeypatch.setattr(
        svc_mod,
        "async_extract_entity_ids",
        AsyncMock(side_effect=lambda call: set(call.data["entity_id"])),
    )
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


@pytest.mark.asyncio
async def test_refresh_device_data(monkeypatch):
    """refresh_device_data calls async_request_refresh."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "refresh_device_data", coord, monkeypatch)

    await handler(_make_call({"entity_id": ["climate.dev"]}))

    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_unknown_registers(monkeypatch):
    """get_unknown_registers fires event with unknown-register data."""
    coord = _Coordinator()
    coord.device_client.unknown_registers = {"input": [100, 101]}
    coord.device_client.scanned_registers = {"input": [100]}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "get_unknown_registers", coord, monkeypatch)

    await handler(_make_call({"entity_id": ["climate.dev"]}))

    hass.bus.async_fire.assert_called_once()
    event_data = hass.bus.async_fire.call_args[0][1]
    assert event_data["unknown_registers"] == {"input": [100, 101]}


@pytest.mark.asyncio
async def test_scan_all_registers(monkeypatch):
    """scan_all_registers isolates the scanner and stores its result."""
    coord = _Coordinator()
    hass = _make_hass()

    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coord)
    monkeypatch.setattr(
        svc_mod,
        "async_extract_entity_ids",
        AsyncMock(side_effect=lambda call: set(call.data["entity_id"])),
    )

    scan_result = {"register_count": 10, "unknown_registers": {"input": [99]}}
    mock_scanner = SimpleNamespace(
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )
    mock_create = AsyncMock(return_value=mock_scanner)
    monkeypatch.setattr(svc_mod.ThesslaGreenDeviceScanner, "create", mock_create)

    await async_setup_services(hass)
    result = await hass.services.handlers["scan_all_registers"](
        _make_call({"entity_id": ["climate.dev"]})
    )

    assert result["climate.dev"]["summary"]["register_count"] == 10
    assert coord.device_client.device_scan_result == scan_result
    coord.device_client.async_disconnect.assert_awaited_once()
    coord.device_client.async_ensure_connected.assert_awaited_once()
    mock_scanner.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_all_registers_no_coordinator(monkeypatch):
    """A target with no loaded ThesslaGreen coordinator is rejected."""
    hass = _make_hass()
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: None)
    monkeypatch.setattr(
        svc_mod,
        "async_extract_entity_ids",
        AsyncMock(side_effect=lambda call: set(call.data["entity_id"])),
    )
    await async_setup_services(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.handlers["scan_all_registers"](
            _make_call({"entity_id": ["climate.dev"]})
        )


@pytest.mark.asyncio
async def test_async_unload_services():
    """Explicit development teardown removes registered services."""
    hass = _make_hass()
    await async_unload_services(hass)

    assert "set_special_mode" in hass.services.removed
    assert "set_debug_logging" in hass.services.removed


def test_get_coordinator_returns_none_for_unknown_entity():
    """Unknown registry entities do not resolve to a coordinator."""
    hass = SimpleNamespace()
    hass.entity_registry = SimpleNamespace(async_get=lambda _e: None)
    hass.data = {}

    assert _get_coordinator_from_entity_id(hass, "sensor.unknown") is None


def test_get_coordinator_returns_none_no_registry():
    """Missing registry state does not resolve to a coordinator."""
    hass = SimpleNamespace()
    hass.data = {}

    assert _get_coordinator_from_entity_id(hass, "sensor.unknown") is None


def test_get_coordinator_returns_none_when_runtime_data_missing():
    """Disabled/unloading entries without runtime_data do not resolve."""
    hass = SimpleNamespace()
    entry = SimpleNamespace(config_entry_id="entry1")
    hass.entity_registry = SimpleNamespace(async_get=lambda _e: entry)
    hass.config_entries = SimpleNamespace(
        async_get_entry=lambda _id: SimpleNamespace()
    )

    assert _get_coordinator_from_entity_id(hass, "sensor.device") is None


@pytest.mark.asyncio
async def test_extract_entity_ids_with_extractor_no_hass_arg():
    """The HA extractor receives exactly the service call argument."""
    from custom_components.thessla_green_modbus.services.targets import (
        extract_entity_ids_with_extractor,
    )

    received_args: list = []

    def recording_extractor(*args, **kwargs):
        received_args.extend(args)
        return {"sensor.one"}

    call = SimpleNamespace(data={"entity_id": "sensor.one"})
    result = await extract_entity_ids_with_extractor(
        SimpleNamespace(), call, extractor=recording_extractor
    )

    assert result == {"sensor.one"}
    assert received_args == [call]


@pytest.mark.asyncio
async def test_extract_entity_ids_with_extractor_async_contract():
    """The current Home Assistant async extractor is awaited."""
    from custom_components.thessla_green_modbus.services.targets import (
        extract_entity_ids_with_extractor,
    )

    call = SimpleNamespace(data={"entity_id": ["sensor.three"]})
    extractor = AsyncMock(return_value={"sensor.three"})

    result = await extract_entity_ids_with_extractor(
        SimpleNamespace(), call, extractor=extractor
    )

    assert result == {"sensor.three"}
    extractor.assert_awaited_once_with(call)


@pytest.mark.asyncio
async def test_extract_entity_ids_allows_indirect_target_without_entity_id():
    """Device/area/floor/label targets are delegated to Home Assistant."""
    from custom_components.thessla_green_modbus.services.targets import (
        extract_entity_ids_with_extractor,
    )

    call = SimpleNamespace(data={"area_id": ["utility_room"]})
    extractor = AsyncMock(return_value={"fan.airpack"})

    result = await extract_entity_ids_with_extractor(
        SimpleNamespace(), call, extractor=extractor
    )

    assert result == {"fan.airpack"}
    extractor.assert_awaited_once_with(call)
