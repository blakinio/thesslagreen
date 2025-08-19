# mypy: ignore-errors
"""Test configuration for ThesslaGreen Modbus integration."""

import os
import sys
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    import homeassistant.util  # ensure util submodule is loaded for plugins
    import homeassistant.util.dt  # noqa: F401
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
except ModuleNotFoundError:  # pragma: no cover - simplify test environment
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    config_entries = types.ModuleType("homeassistant.config_entries")
    helpers_pkg = types.ModuleType("homeassistant.helpers")
    helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    service_helper = types.ModuleType("homeassistant.helpers.service")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    def _async_entries_for_config_entry(*args, **kwargs):
        return []
    entity_registry.async_entries_for_config_entry = _async_entries_for_config_entry
    script_helper = types.ModuleType("homeassistant.helpers.script")
    script_helper._schedule_stop_scripts_after_shutdown = lambda *args, **kwargs: None
    exceptions = types.ModuleType("homeassistant.exceptions")
    const = types.ModuleType("homeassistant.const")
    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    cv = types.ModuleType("homeassistant.helpers.config_validation")
    selector = types.ModuleType("homeassistant.helpers.selector")
    translation = types.ModuleType("homeassistant.helpers.translation")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")

    class AddEntitiesCallback:  # pragma: no cover - simple stub
        pass

    entity_platform.AddEntitiesCallback = AddEntitiesCallback

    const.PERCENTAGE = "%"

    class UnitOfTemperature:  # pragma: no cover - enum stub
        CELSIUS = "°C"

    class UnitOfTime:  # pragma: no cover - enum stub
        HOURS = "h"
        DAYS = "d"
        SECONDS = "s"

    class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
        CUBIC_METERS_PER_HOUR = "m³/h"

    class UnitOfElectricPotential:  # pragma: no cover - enum stub
        VOLT = "V"

    const.UnitOfTemperature = UnitOfTemperature
    const.UnitOfTime = UnitOfTime
    const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate
    const.UnitOfElectricPotential = UnitOfElectricPotential

    async def async_get_translations(*args, **kwargs):  # pragma: no cover - stub
        return {}

    translation.async_get_translations = async_get_translations
    pymodbus = types.ModuleType("pymodbus")
    pymodbus_client = types.ModuleType("pymodbus.client")
    pymodbus_client_tcp = types.ModuleType("pymodbus.client.tcp")
    pymodbus_exceptions = types.ModuleType("pymodbus.exceptions")
    pymodbus_pdu = types.ModuleType("pymodbus.pdu")
    hacc_common = types.ModuleType("pytest_homeassistant_custom_component.common")

    components_pkg = types.ModuleType("homeassistant.components")
    sensor_comp = types.ModuleType("homeassistant.components.sensor")
    binary_sensor_comp = types.ModuleType("homeassistant.components.binary_sensor")

    class SensorDeviceClass:  # pragma: no cover - enum stub
        TEMPERATURE = "temperature"
        VOLTAGE = "voltage"
        POWER = "power"
        ENERGY = "energy"

    class SensorStateClass:  # pragma: no cover - enum stub
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"

    class SensorEntity:  # pragma: no cover - simple stub
        pass

        @property
        def native_unit_of_measurement(self):
            return getattr(self, "_attr_native_unit_of_measurement", None)
    sensor_comp.SensorDeviceClass = SensorDeviceClass
    sensor_comp.SensorStateClass = SensorStateClass
    sensor_comp.SensorEntity = SensorEntity

    class _BinaryMeta(type):  # pragma: no cover - generic fallback
        def __getattr__(cls, item):
            return item.lower()

    class BinarySensorDeviceClass(metaclass=_BinaryMeta):  # pragma: no cover - enum stub
        PROBLEM = "problem"
        RUNNING = "running"
        OPENING = "opening"
        CLOSING = "closing"

    binary_sensor_comp.BinarySensorDeviceClass = BinarySensorDeviceClass
    components_pkg.sensor = sensor_comp
    components_pkg.binary_sensor = binary_sensor_comp
    sys.modules["homeassistant.components"] = components_pkg
    sys.modules["homeassistant.components.sensor"] = sensor_comp
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_comp
    ha.const = const

    class MockConfigEntry:  # pragma: no cover - simplified stub
        def __init__(self, *, domain, data, options=None):
            self.domain = domain
            self.data = data
            self.options = options or {}
            self.entry_id = "mock_entry"
            self.title = data.get("name", "")

        def add_to_hass(self, _hass):
            return None

        def add_update_listener(self, listener):
             return listener

        def async_on_unload(self, func):
            return func

    hacc_common.MockConfigEntry = MockConfigEntry

    class HomeAssistant:  # type: ignore[override]
        async def async_add_executor_job(self, func, *args):  # minimal stub
            return func(*args)

    class ServiceCall:  # type: ignore[override]
        pass

    def callback(func):  # type: ignore[override]
        return func

    class ConfigEntry:  # type: ignore[override]
        pass

    class ConfigFlow:  # type: ignore[override]
        def __init_subclass__(cls, **kwargs):
            return

        async def async_set_unique_id(self, *args, **kwargs):
            return None

        def _abort_if_unique_id_configured(self):
            return None

        def async_show_form(self, **kwargs):  # type: ignore[override]
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):  # type: ignore[override]
            return {"type": "create_entry", **kwargs}

    class DataUpdateCoordinator:  # type: ignore[override]
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

        async def async_shutdown(self) -> None:  # pragma: no cover - stub
            return None

        @classmethod
        def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
            return cls

    class UpdateFailed(Exception):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    class HomeAssistantError(Exception):
        pass

    core.HomeAssistant = HomeAssistant
    core.ServiceCall = ServiceCall
    core.callback = callback
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.CONN_CLASS_LOCAL_POLL = "local_poll"

    class OptionsFlow:  # type: ignore[override]
        def __init_subclass__(cls, **kwargs):
            return

    config_entries.OptionsFlow = OptionsFlow
    helpers.DataUpdateCoordinator = DataUpdateCoordinator
    helpers.UpdateFailed = UpdateFailed

    class CoordinatorEntity:  # type: ignore[override]
        def __init__(self, coordinator=None):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
            return cls

    helpers.CoordinatorEntity = CoordinatorEntity

    class DeviceInfo:  # type: ignore[override]
        pass

    device_registry.DeviceInfo = DeviceInfo
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady
    exceptions.HomeAssistantError = HomeAssistantError
    const.CONF_HOST = "host"
    const.CONF_PORT = "port"
    const.CONF_SCAN_INTERVAL = "scan_interval"
    const.CONF_NAME = "name"
    data_entry_flow.FlowResult = dict

    # Minimal config validation helpers
    cv.string = str
    cv.port = int
    cv.boolean = bool
    cv.entity_ids = list
    cv.time = str

    # Minimal selector stubs
    class SelectSelectorConfig:  # type: ignore[override]
        def __init__(self, options=None, mode=None):
            self.options = options
            self.mode = mode

    class SelectSelector:  # type: ignore[override]
        def __init__(self, config):
            self.config = config

    class SelectSelectorMode:  # type: ignore[override]
        DROPDOWN = "dropdown"

    selector.SelectSelector = SelectSelector
    selector.SelectSelectorConfig = SelectSelectorConfig
    selector.SelectSelectorMode = SelectSelectorMode

    async def async_extract_entity_ids(hass, service_call):
        return set()

    service_helper.async_extract_entity_ids = async_extract_entity_ids

    def er_async_get(hass):
        return getattr(hass, "entity_registry", None)

    entity_registry.async_get = er_async_get
    helpers_pkg.update_coordinator = helpers
    helpers_pkg.device_registry = device_registry
    helpers_pkg.config_validation = cv
    helpers_pkg.selector = selector
    helpers_pkg.service = service_helper
    helpers_pkg.entity_registry = entity_registry
    helpers_pkg.script = script_helper

    # Minimal pymodbus stubs
    class ModbusTcpClient:  # type: ignore[override]
        pass

    class ModbusException(Exception):
        pass

    class ConnectionException(Exception):
        pass

    class ExceptionResponse:  # type: ignore[override]
        pass

    class AsyncModbusTcpClient:  # type: ignore[override]
        pass

    pymodbus_client_tcp.ModbusTcpClient = ModbusTcpClient
    pymodbus_client_tcp.AsyncModbusTcpClient = AsyncModbusTcpClient
    pymodbus_client.AsyncModbusTcpClient = AsyncModbusTcpClient
    pymodbus_client.tcp = pymodbus_client_tcp
    pymodbus.client = pymodbus_client
    pymodbus_exceptions.ModbusException = ModbusException
    pymodbus_exceptions.ConnectionException = ConnectionException
    pymodbus_pdu.ExceptionResponse = ExceptionResponse

    class Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        SELECT = "select"
        NUMBER = "number"
        SWITCH = "switch"
        CLIMATE = "climate"
        FAN = "fan"

    const.Platform = Platform

    # Minimal util.logging stub for pytest plugin compatibility
    util = types.ModuleType("homeassistant.util")
    util_logging = types.ModuleType("homeassistant.util.logging")
    util_dt = types.ModuleType("homeassistant.util.dt")

    def log_exception(*args, **kwargs):  # pragma: no cover - simple no-op
        return None

    def utcnow():  # pragma: no cover - simple stub
        return datetime.utcnow()

    util_logging.log_exception = log_exception
    util.dt = util_dt
    util_dt.utcnow = utcnow
    util_dt.now = utcnow
    util.logging = util_logging
    ha.util = util

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers"] = helpers_pkg
    sys.modules["homeassistant.helpers.update_coordinator"] = helpers
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.service"] = service_helper
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
    sys.modules["homeassistant.helpers.script"] = script_helper
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.util"] = util
    sys.modules["homeassistant.util.dt"] = util_dt
    sys.modules["homeassistant.util.logging"] = util_logging
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow
    sys.modules["homeassistant.helpers.config_validation"] = cv
    sys.modules["homeassistant.helpers.selector"] = selector
    sys.modules["homeassistant.helpers.translation"] = translation
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
    helpers_pkg.translation = translation
    sys.modules["pymodbus"] = pymodbus
    sys.modules["pymodbus.client"] = pymodbus_client
    sys.modules["pymodbus.client.tcp"] = pymodbus_client_tcp
    sys.modules["pymodbus.exceptions"] = pymodbus_exceptions
    sys.modules["pymodbus.pdu"] = pymodbus_pdu
    sys.modules["pytest_homeassistant_custom_component.common"] = hacc_common

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DOMAIN = "thessla_green_modbus"


class CoordinatorMock(MagicMock):
    """MagicMock subclass with device_scan_result property."""

    @property
    def device_scan_result(self):  # type: ignore[override]
        return {
            "device_info": getattr(self, "device_info", {}),
            "capabilities": getattr(self, "capabilities", {}),
        }

    @device_scan_result.setter
    def device_scan_result(self, value):  # type: ignore[override]
        self.device_info = value.get("device_info", {})
        self.capabilities = value.get("capabilities", {})


@pytest.fixture
def hass():
    """Return a mock Home Assistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.domain = DOMAIN
    config_entry.entry_id = "test_entry_id"
    config_entry.data = {
        "host": "192.168.1.100",
        "port": 502,
        "slave_id": 10,
    }
    config_entry.options = {
        "scan_interval": 30,
        "timeout": 10,
        "retry": 3,
        "scan_uart_settings": False,
    }
    return config_entry


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator."""
    coordinator = CoordinatorMock()
    coordinator.host = "192.168.1.100"
    coordinator.port = 502
    coordinator.slave_id = 10
    coordinator.last_update_success = True
    coordinator.data = {
        "outside_temperature": 15.5,
        "supply_temperature": 20.0,
        "exhaust_temperature": 18.0,
        "mode": 0,
        "on_off_panel_mode": 1,
        "supply_percentage": 50,
    }
    coordinator.device_scan_result = {
        "device_info": {
            "device_name": "ThesslaGreen AirPack",
            "firmware": "4.85.0",
            "serial_number": "S/N: 1234 5678 9abc",
        },
        "capabilities": {
            "constant_flow": True,
            "gwc_system": True,
            "bypass_system": True,
        },
    }
    coordinator.available_registers = {
        "input_registers": {"outside_temperature", "supply_temperature", "exhaust_temperature"},
        "holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"},
        "coil_registers": {"power_supply_fans", "bypass"},
        "discrete_inputs": {"expansion", "contamination_sensor"},
        "calculated": {"estimated_power", "total_energy"},
    }
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture(autouse=True)
def fail_on_log_exception():
    """Disable log exception check from HA test plugin."""
    yield
