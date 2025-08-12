"""Tests for service helper mappings."""

import os
import sys
import types
from types import SimpleNamespace

# Stub Home Assistant and pymodbus modules for import
ha = types.ModuleType("homeassistant")
const = types.ModuleType("homeassistant.const")
core = types.ModuleType("homeassistant.core")
helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers_cv = types.ModuleType("homeassistant.helpers.config_validation")
helpers_dr = types.ModuleType("homeassistant.helpers.device_registry")
helpers_er = types.ModuleType("homeassistant.helpers.entity_registry")
helpers_service = types.ModuleType("homeassistant.helpers.service")
helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
helpers_pkg.config_validation = helpers_cv
helpers_pkg.device_registry = helpers_dr
helpers_pkg.entity_registry = helpers_er
helpers_pkg.service = helpers_service
helpers_pkg.update_coordinator = helpers
exceptions = types.ModuleType("homeassistant.exceptions")
config_entries = types.ModuleType("homeassistant.config_entries")
pymodbus = types.ModuleType("pymodbus")
pymodbus_client = types.ModuleType("pymodbus.client")
pymodbus_client_tcp = types.ModuleType("pymodbus.client.tcp")
pymodbus_exceptions = types.ModuleType("pymodbus.exceptions")
pymodbus_pdu = types.ModuleType("pymodbus.pdu")
vol = types.ModuleType("voluptuous")
class Schema:
    def __init__(self, *args, **kwargs):
        pass


def Required(key):
    return key


def Optional(key, **kwargs):
    return key


def In(values):
    return lambda x: x


def All(*args, **kwargs):
    return lambda x: x


def Coerce(_type):
    return lambda x: x


def Range(*args, **kwargs):
    return lambda x: x


vol.Schema = Schema
vol.Required = Required
vol.Optional = Optional
vol.In = In
vol.All = All
vol.Coerce = Coerce
vol.Range = Range
vol.Length = Range

# Define minimal constants and classes
const.CONF_HOST = "host"
const.CONF_PORT = "port"
const.CONF_SCAN_INTERVAL = "scan_interval"
const.CONF_NAME = "name"


class Platform:
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SELECT = "select"
    NUMBER = "number"
    SWITCH = "switch"
    CLIMATE = "climate"
    FAN = "fan"


const.Platform = Platform

class HomeAssistant:
    pass

class ServiceCall:
    pass

core.HomeAssistant = HomeAssistant
core.ServiceCall = ServiceCall

class ConfigEntry:
    def __init__(self, data=None):
        self.data = data or {}

config_entries.ConfigEntry = ConfigEntry

class DeviceInfo:
    pass

helpers_dr.DeviceInfo = DeviceInfo

class DataUpdateCoordinator:
    pass

helpers.DataUpdateCoordinator = DataUpdateCoordinator

class UpdateFailed(Exception):
    pass

helpers.UpdateFailed = UpdateFailed


async def async_extract_entity_ids(hass, call):
    return []

helpers_service.async_extract_entity_ids = async_extract_entity_ids


def er_async_get(hass):
    return getattr(hass, "entity_registry", None)


helpers_er.async_get = er_async_get


def entity_ids(value):
    return value


def time(value):
    return value


def string(value):
    return value


helpers_cv.entity_ids = entity_ids
helpers_cv.time = time
helpers_cv.string = string

class ConfigEntryNotReady(Exception):
    pass

exceptions.ConfigEntryNotReady = ConfigEntryNotReady

class AsyncModbusTcpClient:
    pass

pymodbus_client_tcp.AsyncModbusTcpClient = AsyncModbusTcpClient
pymodbus_client.tcp = pymodbus_client_tcp

class ModbusException(Exception):
    pass
class ConnectionException(Exception):
    pass

pymodbus_exceptions.ModbusException = ModbusException
pymodbus_exceptions.ConnectionException = ConnectionException

class ExceptionResponse:
    pass

pymodbus_pdu.ExceptionResponse = ExceptionResponse

# Register modules
modules = {
    "homeassistant": ha,
    "homeassistant.const": const,
    "homeassistant.core": core,
    "homeassistant.helpers": helpers_pkg,
    "homeassistant.helpers.config_validation": helpers_cv,
    "homeassistant.helpers.device_registry": helpers_dr,
    "homeassistant.helpers.service": helpers_service,
    "homeassistant.helpers.update_coordinator": helpers,
    "homeassistant.exceptions": exceptions,
    "homeassistant.config_entries": config_entries,
    "pymodbus": pymodbus,
    "pymodbus.client": pymodbus_client,
    "pymodbus.client.tcp": pymodbus_client_tcp,
    "pymodbus.exceptions": pymodbus_exceptions,
    "pymodbus.pdu": pymodbus_pdu,
    "voluptuous": vol,
}
for name, module in modules.items():
    sys.modules[name] = module

# Ensure repository root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib

services_module = importlib.reload(
    importlib.import_module("custom_components.thessla_green_modbus.services")
)
AIR_QUALITY_REGISTER_MAP = services_module.AIR_QUALITY_REGISTER_MAP


def test_air_quality_register_map():
    """Verify correct mapping of air quality parameters to register names."""
    assert AIR_QUALITY_REGISTER_MAP["co2_low"] == "co2_threshold_low"
    assert AIR_QUALITY_REGISTER_MAP["co2_medium"] == "co2_threshold_medium"
    assert AIR_QUALITY_REGISTER_MAP["co2_high"] == "co2_threshold_high"
    assert AIR_QUALITY_REGISTER_MAP["humidity_target"] == "humidity_target"


def test_get_coordinator_from_entity_id_multiple_devices():
    """Ensure coordinator lookup maps entities to correct coordinators."""
    hass = core.HomeAssistant()
    coord1 = object()
    coord2 = object()
    hass.data = {services_module.DOMAIN: {"entry1": coord1, "entry2": coord2}}

    class DummyRegistry:
        def __init__(self, mapping):
            self._mapping = mapping

        def async_get(self, entity_id):
            return self._mapping.get(entity_id)

    hass.entity_registry = DummyRegistry(
        {
            "sensor.dev1": SimpleNamespace(config_entry_id="entry1"),
            "sensor.dev2": SimpleNamespace(config_entry_id="entry2"),
        }
    )

    assert (
        services_module._get_coordinator_from_entity_id(hass, "sensor.dev1")
        is coord1
    )
    assert (
        services_module._get_coordinator_from_entity_id(hass, "sensor.dev2")
        is coord2
    )
