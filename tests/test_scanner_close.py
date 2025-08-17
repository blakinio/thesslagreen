import asyncio
import logging
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)


# Stub minimal Home Assistant and pymodbus modules before importing the coordinator
ha = types.ModuleType("homeassistant")
const = types.ModuleType("homeassistant.const")
core = types.ModuleType("homeassistant.core")
helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
helpers_dr = types.ModuleType("homeassistant.helpers.device_registry")
helpers_script = types.ModuleType("homeassistant.helpers.script")
exceptions = types.ModuleType("homeassistant.exceptions")
config_entries = types.ModuleType("homeassistant.config_entries")
pymodbus = types.ModuleType("pymodbus")
pymodbus_client = types.ModuleType("pymodbus.client")
pymodbus_exceptions = types.ModuleType("pymodbus.exceptions")
pymodbus_pdu = types.ModuleType("pymodbus.pdu")
vol = types.ModuleType("voluptuous")
cc_services = types.ModuleType("custom_components.thessla_green_modbus.services")


async def async_setup_services(hass):
    pass


async def async_unload_services(hass):
    pass


cc_services.async_setup_services = async_setup_services
cc_services.async_unload_services = async_unload_services

# Minimal util.logging module required by pytest_homeassistant_custom_component
util = types.ModuleType("homeassistant.util")
util_logging = types.ModuleType("homeassistant.util.logging")


def log_exception(*_args, **_kwargs):  # pragma: no cover - simple stub
    return None


util_logging.log_exception = log_exception
util.logging = util_logging
ha.util = util


def _schedule_stop_scripts_after_shutdown(*_args, **_kwargs):  # pragma: no cover
    return None


helpers_script._schedule_stop_scripts_after_shutdown = _schedule_stop_scripts_after_shutdown

const.CONF_HOST = "host"
const.CONF_NAME = "name"
const.CONF_PORT = "port"


class Platform(str):
    def __new__(cls, value):
        return str.__new__(cls, value)


const.Platform = Platform


# Stubs for coordinator requirements
class DataUpdateCoordinator:
    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval

    async def async_request_refresh(self):
        pass

    async def async_shutdown(self):  # pragma: no cover - stub
        pass

    # Allow subscripting like DataUpdateCoordinator[dict[str, Any]]
    def __class_getitem__(cls, _):  # pragma: no cover - simple stub
        return cls


helpers_uc.DataUpdateCoordinator = DataUpdateCoordinator


class UpdateFailed(Exception):
    pass


helpers_uc.UpdateFailed = UpdateFailed
helpers_pkg.update_coordinator = helpers_uc
helpers_pkg.device_registry = helpers_dr
helpers_pkg.script = helpers_script


class DeviceInfo:
    pass


helpers_dr.DeviceInfo = DeviceInfo


class HomeAssistant:
    pass


core.HomeAssistant = HomeAssistant


class ServiceCall:
    pass


core.ServiceCall = ServiceCall


class ConfigEntryNotReady(Exception):
    pass


exceptions.ConfigEntryNotReady = ConfigEntryNotReady


class ConfigEntry:
    pass


config_entries.ConfigEntry = ConfigEntry


class AsyncModbusTcpClient:
    async def close(self):
        pass


class ModbusTcpClient:
    pass


pymodbus_client.AsyncModbusTcpClient = AsyncModbusTcpClient
pymodbus_client.ModbusTcpClient = ModbusTcpClient


class ModbusIOException(Exception):
    pass


pymodbus_exceptions.ModbusException = ModbusException
pymodbus_exceptions.ConnectionException = ConnectionException
pymodbus_exceptions.ModbusIOException = ModbusIOException


class ExceptionResponse:
    pass


pymodbus_pdu.ExceptionResponse = ExceptionResponse

sys.modules.update(
    {
        "homeassistant": ha,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers_pkg,
        "homeassistant.helpers.update_coordinator": helpers_uc,
        "homeassistant.helpers.device_registry": helpers_dr,
        "homeassistant.helpers.script": helpers_script,
        "homeassistant.exceptions": exceptions,
        "homeassistant.config_entries": config_entries,
        "homeassistant.util": util,
        "homeassistant.util.logging": util_logging,
        "pymodbus": pymodbus,
        "pymodbus.client": pymodbus_client,
        "pymodbus.exceptions": pymodbus_exceptions,
        "pymodbus.pdu": pymodbus_pdu,
        "voluptuous": vol,
        "custom_components.thessla_green_modbus.services": cc_services,
    }
)

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.device_scanner import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)


def test_async_setup_closes_scanner():
    """Ensure scanner is closed after async_setup."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        scanner = AsyncMock()
        scanner.scan_device.return_value = {
            "available_registers": {
                "input_registers": set(),
                "holding_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
            },
            "device_info": {},
            "capabilities": {},
        }
        scanner.close = AsyncMock()

        with patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenDeviceScanner",
            return_value=scanner,
        ):
            with patch.object(coordinator, "_test_connection", AsyncMock()):
                result = await coordinator.async_setup()

        assert result is True
        scanner.close.assert_awaited_once()

    import asyncio

    asyncio.run(run_test())


def test_async_setup_cancel_mid_scan(caplog):
    """Device scan cancellation closes scanner without errors."""

    async def run_test(caplog):
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        scan_event = asyncio.Event()
        scanner = AsyncMock()

        async def scan_side_effect():
            await scan_event.wait()

        scanner.scan_device.side_effect = scan_side_effect
        scanner.close = AsyncMock()

        with patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner),
        ):
            with patch.object(coordinator, "_test_connection", AsyncMock()):
                caplog.set_level(logging.DEBUG)
                setup_task = asyncio.create_task(coordinator.async_setup())
                await asyncio.sleep(0)
                setup_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await setup_task

        scanner.close.assert_awaited_once()
        assert not any(record.levelno >= logging.ERROR for record in caplog.records)
        assert "Device scan cancelled" in caplog.text

    asyncio.run(run_test(caplog))


def test_disconnect_closes_client():
    """Ensure _disconnect awaits client.close."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        client = AsyncMock()
        coordinator.client = client

        await coordinator._disconnect()

        client.close.assert_awaited_once()
        assert coordinator.client is None

    import asyncio

    asyncio.run(run_test())


def test_disconnect_closes_client_sync():
    """Ensure _disconnect handles sync client.close."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenModbusCoordinator(
            hass=hass,
            host="localhost",
            port=502,
            slave_id=1,
            name="Test",
            scan_interval=30,
            timeout=10,
            retry=3,
        )

        client = MagicMock()
        coordinator.client = client

        await coordinator._disconnect()

        client.close.assert_called_once()
        assert coordinator.client is None

    import asyncio

    asyncio.run(run_test())


def test_scan_device_closes_client_on_failure():
    """Ensure scan_device closes the client even when scan fails."""

    async def run_test():
        scanner = await ThesslaGreenDeviceScanner.create("localhost", 502)
        scanner.scan = AsyncMock(side_effect=ConnectionException("fail"))
        scanner.close = AsyncMock()

        with pytest.raises(ConnectionException):
            await scanner.scan_device()

        scanner.close.assert_awaited_once()

    import asyncio

    asyncio.run(run_test())


def test_close_handles_io_error():
    """Scanner.close should swallow errors from client.close."""

    async def run_test():
        scanner = await ThesslaGreenDeviceScanner.create("localhost", 502)
        client = AsyncMock()
        client.close.side_effect = OSError("boom")
        scanner._client = client

        # Should not raise despite underlying error
        await scanner.close()

        client.close.assert_called_once()
        assert scanner._client is None

    import asyncio

    asyncio.run(run_test())
