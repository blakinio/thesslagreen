import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

# Stub minimal Home Assistant and pymodbus modules before importing the coordinator
ha = types.ModuleType("homeassistant")
const = types.ModuleType("homeassistant.const")
core = types.ModuleType("homeassistant.core")
helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
helpers_dr = types.ModuleType("homeassistant.helpers.device_registry")
exceptions = types.ModuleType("homeassistant.exceptions")
config_entries = types.ModuleType("homeassistant.config_entries")
pymodbus = types.ModuleType("pymodbus")
pymodbus_client = types.ModuleType("pymodbus.client")
pymodbus_exceptions = types.ModuleType("pymodbus.exceptions")
pymodbus_pdu = types.ModuleType("pymodbus.pdu")
vol = types.ModuleType("voluptuous")
cc_services = types.ModuleType("custom_components.thessla_green_modbus.services")

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

helpers_uc.DataUpdateCoordinator = DataUpdateCoordinator
class UpdateFailed(Exception):
    pass

helpers_uc.UpdateFailed = UpdateFailed
helpers_pkg.update_coordinator = helpers_uc
helpers_pkg.device_registry = helpers_dr

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

class ModbusException(Exception):
    pass

class ConnectionException(Exception):
    pass

class ModbusIOException(Exception):
    pass

pymodbus_exceptions.ModbusException = ModbusException
pymodbus_exceptions.ConnectionException = ConnectionException
pymodbus_exceptions.ModbusIOException = ModbusIOException

class ExceptionResponse:
    pass

pymodbus_pdu.ExceptionResponse = ExceptionResponse

sys.modules.update({
    "homeassistant": ha,
    "homeassistant.const": const,
    "homeassistant.core": core,
    "homeassistant.helpers": helpers_pkg,
    "homeassistant.helpers.update_coordinator": helpers_uc,
    "homeassistant.helpers.device_registry": helpers_dr,
    "homeassistant.exceptions": exceptions,
    "homeassistant.config_entries": config_entries,
    "pymodbus": pymodbus,
    "pymodbus.client": pymodbus_client,
    "pymodbus.exceptions": pymodbus_exceptions,
    "pymodbus.pdu": pymodbus_pdu,
    "voluptuous": vol,
    "custom_components.thessla_green_modbus.services": cc_services,
})

async def async_setup_services(hass):
    pass

async def async_unload_services(hass):
    pass

cc_services.async_setup_services = async_setup_services
cc_services.async_unload_services = async_unload_services

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator


def test_async_setup_closes_scanner():
    """Ensure scanner is closed after async_setup."""
    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenCoordinator(
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


def test_disconnect_closes_client():
    """Ensure _disconnect awaits client.close."""

    async def run_test():
        hass = MagicMock()
        coordinator = ThesslaGreenCoordinator(
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
