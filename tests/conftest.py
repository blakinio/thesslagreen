# mypy: ignore-errors
"""Test configuration for ThesslaGreen Modbus integration."""

import asyncio
import importlib
import os
import sys
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

USE_REAL_HOMEASSISTANT = os.environ.get("THESSLA_GREEN_USE_HA", "0") == "1"

try:
    if not USE_REAL_HOMEASSISTANT:
        raise ModuleNotFoundError
    from homeassistant.util import dt as _ha_dt  # noqa: F401

    importlib.import_module("homeassistant.util")  # ensure util submodule is loaded for plugins
    import homeassistant as ha_module
    ha_module.components = importlib.import_module("homeassistant.components")
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
    event_helper = types.ModuleType("homeassistant.helpers.event")

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
        def __init__(self, *args, **kwargs):
            self.domain = args[0] if len(args) > 0 else kwargs.get("domain")
            self.service = args[1] if len(args) > 1 else kwargs.get("service")
            self.data = args[2] if len(args) > 2 else kwargs.get("data")

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

        def async_show_form(self, **kwargs):  # type: ignore[override]
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):  # type: ignore[override]
            return {"type": "create_entry", **kwargs}

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

    async def async_extract_entity_ids(hass, _service_call):
        return set()

    service_helper.async_extract_entity_ids = async_extract_entity_ids

    def async_call_later(_hass, _delay, action):
        if asyncio.iscoroutinefunction(action):
            return lambda: None
        return lambda: None

    event_helper.async_call_later = async_call_later

    def er_async_get(hass):
        return getattr(hass, "entity_registry", None)

    entity_registry.async_get = er_async_get
    helpers_pkg.update_coordinator = helpers
    helpers_pkg.device_registry = device_registry
    helpers_pkg.config_validation = cv
    helpers_pkg.selector = selector
    helpers_pkg.service = service_helper
    helpers_pkg.event = event_helper
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
    util.__path__ = []  # type: ignore[attr-defined]
    util_logging = types.ModuleType("homeassistant.util.logging")
    util_network = types.ModuleType("homeassistant.util.network")
    util_dt = types.ModuleType("homeassistant.util.dt")

    def log_exception(*args, **kwargs):  # pragma: no cover - simple no-op
        return None

    def utcnow():  # pragma: no cover - simple stub
        return datetime.utcnow()

    util_logging.log_exception = log_exception
    util.dt = util_dt
    util_dt.utcnow = utcnow
    util_dt.now = utcnow
    util.network = util_network
    util_network.is_host_valid = lambda *_args, **_kwargs: True
    util.logging = util_logging
    util.dt = types.SimpleNamespace(now=lambda: None, utcnow=lambda: None)
    ha.util = util

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers"] = helpers_pkg
    sys.modules["homeassistant.helpers.update_coordinator"] = helpers
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.service"] = service_helper
    sys.modules["homeassistant.helpers.event"] = event_helper
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry
    sys.modules["homeassistant.helpers.script"] = script_helper
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.util"] = util
    sys.modules["homeassistant.util.dt"] = util_dt
    sys.modules["homeassistant.util.logging"] = util_logging
    sys.modules["homeassistant.util.network"] = util_network
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow
    sys.modules["homeassistant.helpers.config_validation"] = cv
    sys.modules["homeassistant.helpers.selector"] = selector
    # Minimal util logging stub required by pytest_homeassistant_custom_component
    util = types.ModuleType("homeassistant.util")
    util.__path__ = []  # type: ignore[attr-defined]
    util_logging = types.ModuleType("homeassistant.util.logging")
    util_network = types.ModuleType("homeassistant.util.network")

    def log_exception(_format_err, *args):  # pragma: no cover - simple stub
        return None

    util_logging.log_exception = log_exception
    util.network = util_network
    util_network.is_host_valid = lambda *_args, **_kwargs: True
    util.logging = util_logging
    util.dt = types.SimpleNamespace(now=lambda: None, utcnow=lambda: None)
    ha.util = util
    sys.modules["homeassistant.util"] = util
    sys.modules["homeassistant.util.logging"] = util_logging
    sys.modules["homeassistant.util.network"] = util_network
    sys.modules["homeassistant.helpers.translation"] = translation
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
    helpers_pkg.translation = translation
    sys.modules["pymodbus"] = pymodbus
    sys.modules["pymodbus.client"] = pymodbus_client
    sys.modules["pymodbus.client.tcp"] = pymodbus_client_tcp
    sys.modules["pymodbus.exceptions"] = pymodbus_exceptions
    sys.modules["pymodbus.pdu"] = pymodbus_pdu
    sys.modules["pytest_homeassistant_custom_component.common"] = hacc_common


def _ensure_homeassistant_modules() -> None:
    ha_module = sys.modules.get("homeassistant")
    if ha_module is None:
        return

    def _ensure_module(name: str) -> types.ModuleType:
        module = sys.modules.get(name)
        if module is None:
            try:
                module = importlib.import_module(name)
            except ModuleNotFoundError:
                module = types.ModuleType(name)
                module.__path__ = []  # type: ignore[attr-defined]
                sys.modules[name] = module
        return module

    components = _ensure_module("homeassistant.components")
    helpers = _ensure_module("homeassistant.helpers")
    setattr(ha_module, "components", components)
    setattr(ha_module, "helpers", helpers)

    helpers_script = _ensure_module("homeassistant.helpers.script")
    if not hasattr(helpers_script, "_schedule_stop_scripts_after_shutdown"):
        helpers_script._schedule_stop_scripts_after_shutdown = lambda *args, **kwargs: None
    setattr(helpers, "script", helpers_script)

    components_network = _ensure_module("homeassistant.components.network")
    if not hasattr(components_network, "async_get_source_ip"):
        async def async_get_source_ip(*_args, **_kwargs):  # pragma: no cover - stub
            return "127.0.0.1"

        components_network.async_get_source_ip = async_get_source_ip
    setattr(components, "network", components_network)


import custom_components.thessla_green_modbus.registers.loader  # noqa: F401,E402

_ensure_homeassistant_modules()

helpers_uc = sys.modules.get("homeassistant.helpers.update_coordinator")
if helpers_uc is not None and not hasattr(helpers_uc, "CoordinatorEntity"):

    class CoordinatorEntity:  # pragma: no cover - simple stub
        def __init__(self, coordinator=None):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
            return cls

    helpers_uc.CoordinatorEntity = CoordinatorEntity

ha_const = sys.modules.get("homeassistant.const")
if ha_const is not None and not hasattr(ha_const, "PERCENTAGE"):
    ha_const.PERCENTAGE = "%"

DOMAIN = "thessla_green_modbus"


def pytest_configure() -> None:
    _ensure_homeassistant_modules()


def pytest_sessionstart(session) -> None:
    _ensure_homeassistant_modules()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item) -> None:
    _ensure_homeassistant_modules()


class CoordinatorMock(MagicMock):
    """MagicMock subclass with device_scan_result property."""

    def get_register_map(self, register_type: str) -> dict[str, int]:
        """Return register map for the given type."""
        return self._register_maps.get(register_type, {})

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
    from custom_components.thessla_green_modbus.const import (
        coil_registers,
        discrete_input_registers,
        holding_registers,
        input_registers,
    )

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
    coordinator._register_maps = {
        "input_registers": input_registers(),
        "holding_registers": holding_registers(),
        "coil_registers": coil_registers(),
        "discrete_inputs": discrete_input_registers(),
    }
    coordinator.force_full_register_list = False
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture(autouse=True)
def fail_on_log_exception():
    """Disable log exception check from HA test plugin."""
    yield
