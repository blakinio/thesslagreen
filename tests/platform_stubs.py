"""Shared lightweight Home Assistant stubs for platform tests.

These are only used in tests that run without real Home Assistant installed.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace


def install_common_ha_stubs() -> None:
    """Install core HA modules and constants used by platform tests."""
    const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
    const.PERCENTAGE = "%"

    class UnitOfElectricPotential:  # pragma: no cover
        VOLT = "V"

    class UnitOfTemperature:  # pragma: no cover
        CELSIUS = "°C"

    class UnitOfTime:  # pragma: no cover
        SECONDS = "s"
        MINUTES = "min"
        HOURS = "h"
        DAYS = "d"

    class UnitOfVolumeFlowRate:  # pragma: no cover
        CUBIC_METERS_PER_HOUR = "m³/h"

    const.UnitOfElectricPotential = UnitOfElectricPotential
    const.UnitOfTemperature = UnitOfTemperature
    const.UnitOfTime = UnitOfTime
    const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")

    class AddEntitiesCallback:  # pragma: no cover
        pass

    entity_platform.AddEntitiesCallback = AddEntitiesCallback
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    helpers_uc = sys.modules.setdefault(
        "homeassistant.helpers.update_coordinator",
        types.ModuleType("homeassistant.helpers.update_coordinator"),
    )

    class DataUpdateCoordinator:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    class CoordinatorEntity:  # pragma: no cover
        def __init__(self, coordinator=None):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    helpers_uc.DataUpdateCoordinator = DataUpdateCoordinator
    helpers_uc.CoordinatorEntity = CoordinatorEntity

    binary_sensor_mod = types.ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorEntity:  # pragma: no cover
        pass

    class _BinarySensorDeviceClass:  # pragma: no cover
        def __getattr__(self, name):
            return name.lower()

    binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
    binary_sensor_mod.BinarySensorDeviceClass = _BinarySensorDeviceClass()
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod

    sensor_mod = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:  # pragma: no cover
        @property
        def native_unit_of_measurement(self):
            return getattr(self, "_attr_native_unit_of_measurement", None)

    class SensorDeviceClass:  # pragma: no cover
        TEMPERATURE = "temperature"
        VOLTAGE = "voltage"
        POWER = "power"
        ENERGY = "energy"
        EFFICIENCY = "efficiency"

    class SensorStateClass:  # pragma: no cover
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"

    sensor_mod.SensorEntity = SensorEntity
    sensor_mod.SensorDeviceClass = SensorDeviceClass
    sensor_mod.SensorStateClass = SensorStateClass
    sys.modules["homeassistant.components.sensor"] = sensor_mod


def install_select_stubs() -> None:
    """Install stubs required by select platform tests."""
    install_common_ha_stubs()
    select_mod = types.ModuleType("homeassistant.components.select")

    class SelectEntity:  # pragma: no cover
        pass

    select_mod.SelectEntity = SelectEntity
    sys.modules["homeassistant.components.select"] = select_mod


def install_switch_stubs() -> None:
    """Install stubs required by switch platform tests."""
    install_common_ha_stubs()
    switch_mod = types.ModuleType("homeassistant.components.switch")

    class SwitchEntity:  # pragma: no cover
        pass

    switch_mod.SwitchEntity = SwitchEntity
    sys.modules["homeassistant.components.switch"] = switch_mod


def install_sensor_platform_stubs() -> None:
    """Install stubs required by sensor platform setup tests."""
    install_common_ha_stubs()
    const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
    const.STATE_UNAVAILABLE = "unavailable"

    network_mod = types.ModuleType("homeassistant.util.network")
    network_mod.is_host_valid = lambda _host: True
    sys.modules["homeassistant.util.network"] = network_mod

    select_mod = types.ModuleType("homeassistant.components.select")

    class SelectEntity:  # pragma: no cover
        pass

    select_mod.SelectEntity = SelectEntity
    sys.modules["homeassistant.components.select"] = select_mod

    update_coord = sys.modules.setdefault(
        "homeassistant.helpers.update_coordinator",
        types.ModuleType("homeassistant.helpers.update_coordinator"),
    )

    class UpdateFailed(Exception):  # pragma: no cover
        pass

    update_coord.UpdateFailed = UpdateFailed


def install_binary_sensor_stubs() -> None:
    """Install stubs required by binary sensor platform tests."""
    install_common_ha_stubs()

    binary_sensor_mod = types.ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorEntity:  # pragma: no cover
        pass

    class BinarySensorDeviceClass:  # pragma: no cover
        RUNNING = "running"
        OPENING = "opening"
        POWER = "power"
        HEAT = "heat"
        CONNECTIVITY = "connectivity"
        PROBLEM = "problem"
        SAFETY = "safety"
        COLD = "cold"
        MOISTURE = "moisture"

    binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
    binary_sensor_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod

    network_mod = types.ModuleType("homeassistant.util.network")
    network_mod.is_host_valid = lambda _host: True
    sys.modules["homeassistant.util.network"] = network_mod


def install_climate_stubs() -> None:
    """Install stubs required by climate platform tests."""
    install_common_ha_stubs()
    const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

    class UnitOfTemperature:  # pragma: no cover
        CELSIUS = "°C"

    const.UnitOfTemperature = UnitOfTemperature
    const.ATTR_TEMPERATURE = "temperature"

    climate_mod = types.ModuleType("homeassistant.components.climate")

    class ClimateEntity:  # pragma: no cover
        pass

    class ClimateEntityFeature:  # pragma: no cover
        TARGET_TEMPERATURE = 1
        FAN_MODE = 2
        PRESET_MODE = 4
        TURN_ON = 8
        TURN_OFF = 16

    class HVACMode:  # pragma: no cover
        OFF = "off"
        AUTO = "auto"
        FAN_ONLY = "fan_only"

    class HVACAction:  # pragma: no cover
        OFF = "off"
        FAN = "fan"
        HEATING = "heating"
        COOLING = "cooling"
        IDLE = "idle"

    climate_mod.ClimateEntity = ClimateEntity
    climate_mod.ClimateEntityFeature = ClimateEntityFeature
    climate_mod.HVACMode = HVACMode
    climate_mod.HVACAction = HVACAction
    sys.modules["homeassistant.components.climate"] = climate_mod

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceInfo(dict):  # pragma: no cover
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    device_registry.DeviceInfo = DeviceInfo
    sys.modules["homeassistant.helpers.device_registry"] = device_registry


def install_fan_stubs() -> None:
    """Install stubs required by fan platform tests."""
    install_common_ha_stubs()
    fan_mod = types.ModuleType("homeassistant.components.fan")

    class FanEntity:  # pragma: no cover
        @property
        def speed_count(self):
            return getattr(self, "_attr_speed_count", None)

    class FanEntityFeature:  # pragma: no cover
        SET_SPEED = 1

    fan_mod.FanEntity = FanEntity
    fan_mod.FanEntityFeature = FanEntityFeature
    sys.modules["homeassistant.components.fan"] = fan_mod


def install_number_stubs() -> None:
    """Install stubs required by number platform tests."""
    install_common_ha_stubs()

    number_mod = types.ModuleType("homeassistant.components.number")

    class NumberEntity:  # pragma: no cover
        pass

    class NumberMode:  # pragma: no cover
        SLIDER = "slider"
        BOX = "box"

    number_mod.NumberEntity = NumberEntity
    number_mod.NumberMode = NumberMode
    sys.modules["homeassistant.components.number"] = number_mod

    helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    if not hasattr(helpers, "__path__"):
        helpers.__path__ = []
    entity_helper = types.ModuleType("homeassistant.helpers.entity")
    script_helper = types.ModuleType("homeassistant.helpers.script")
    helpers.entity = entity_helper
    helpers.script = script_helper
    sys.modules["homeassistant.helpers.script"] = script_helper
    script_helper._schedule_stop_scripts_after_shutdown = lambda *args, **kwargs: None

    class EntityCategory(str):  # pragma: no cover
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

        def __new__(cls, value):
            return str.__new__(cls, value)

    entity_helper.EntityCategory = EntityCategory
    sys.modules["homeassistant.helpers.entity"] = entity_helper

    coordinator_module = types.ModuleType("custom_components.thessla_green_modbus.coordinator")

    from custom_components.thessla_green_modbus.registers.loader import (
        get_register_definition,
        get_registers_by_function,
    )

    holding_registers = {r.name: r.address for r in get_registers_by_function("03")}

    class ThesslaGreenModbusCoordinator:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            self.available_registers = {"holding_registers": set()}
            self.capabilities = SimpleNamespace(basic_control=False)
            self.client = None
            self.slave_id = args[3] if len(args) > 3 else kwargs.get("slave_id", 0)
            self._register_maps = {"holding_registers": holding_registers}

        def get_register_map(self, register_type: str) -> dict[str, int]:
            return self._register_maps.get(register_type, {})

        async def _ensure_connection(self):
            return None

        async def async_request_refresh(self):
            return None

        def get_device_info(self):
            return {}

        async def async_write_register(self, *args, **kwargs):
            register, value = args[0], args[1]
            address = self._register_maps["holding_registers"][register]
            definition = get_register_definition(register)
            raw = definition.encode(value)
            await self.client.write_register(address, raw, slave=self.slave_id)
            return True

    coordinator_module.ThesslaGreenModbusCoordinator = ThesslaGreenModbusCoordinator
    sys.modules.setdefault("custom_components.thessla_green_modbus.coordinator", coordinator_module)


def install_text_stubs() -> None:
    """Install stubs required by text platform tests."""
    install_common_ha_stubs()

    text_mod = types.ModuleType("homeassistant.components.text")

    class TextEntity:  # pragma: no cover
        _attr_native_max: int = 100

    text_mod.TextEntity = TextEntity
    sys.modules["homeassistant.components.text"] = text_mod

    helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    if not hasattr(helpers, "__path__"):
        helpers.__path__ = []
    entity_helper = types.ModuleType("homeassistant.helpers.entity")
    script_helper = types.ModuleType("homeassistant.helpers.script")
    helpers.entity = entity_helper
    helpers.script = script_helper
    sys.modules["homeassistant.helpers.script"] = script_helper
    script_helper._schedule_stop_scripts_after_shutdown = lambda *args, **kwargs: None

    class EntityCategory(str):  # pragma: no cover
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

        def __new__(cls, value):
            return str.__new__(cls, value)

    entity_helper.EntityCategory = EntityCategory
    sys.modules["homeassistant.helpers.entity"] = entity_helper

    coordinator_module = types.ModuleType("custom_components.thessla_green_modbus.coordinator")

    class ThesslaGreenModbusCoordinator:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            self.available_registers = {"holding_registers": set()}
            self.capabilities = SimpleNamespace()
            self.client = None
            self.slave_id = kwargs.get("slave_id", 0)

        def get_register_map(self, register_type: str) -> dict:
            return {}

        async def async_request_refresh(self):
            return None

        def get_device_info(self):
            return {}

        async def async_write_register(self, *args, **kwargs):
            return True

    coordinator_module.ThesslaGreenModbusCoordinator = ThesslaGreenModbusCoordinator
    sys.modules.setdefault("custom_components.thessla_green_modbus.coordinator", coordinator_module)


def install_time_stubs() -> None:
    """Install stubs required by time platform tests."""
    install_common_ha_stubs()
    time_mod = types.ModuleType("homeassistant.components.time")

    class TimeEntity:  # pragma: no cover
        pass

    time_mod.TimeEntity = TimeEntity
    sys.modules["homeassistant.components.time"] = time_mod


def install_network_validation_stub() -> None:
    """Install lightweight homeassistant.util.network.is_host_valid stub."""
    network_module = SimpleNamespace(
        is_host_valid=lambda host: bool(host)
        and " " not in host
        and not host.replace(".", "").isdigit()
        and "." in host,
    )
    sys.modules.setdefault("homeassistant.util", SimpleNamespace(network=network_module))
    sys.modules.setdefault("homeassistant.util.network", network_module)


def install_registers_stub(
    registers_path: Path | None = None,
    *,
    force: bool = False,
    hash_value: str = "",
    registers_by_function: list | None = None,
    all_registers: list | None = None,
) -> None:
    """Install lightweight custom_components...registers and loader stubs."""
    registers_path = registers_path or Path("dummy")
    registers_by_function = registers_by_function or []
    all_registers = all_registers or []
    loader_stub = SimpleNamespace(
        plan_group_reads=lambda *args, **kwargs: [],
        get_registers_by_function=lambda *args, **kwargs: registers_by_function,
        get_all_registers=lambda *args, **kwargs: all_registers,
        registers_sha256=lambda *args, **kwargs: hash_value,
        load_registers=lambda *args, **kwargs: [],
        _REGISTERS_PATH=registers_path,
        RegisterDef=object,
    )

    registers_module = types.ModuleType("custom_components.thessla_green_modbus.registers")
    registers_module.__path__ = []
    registers_module.get_registers_by_function = loader_stub.get_registers_by_function
    registers_module.get_all_registers = loader_stub.get_all_registers
    registers_module.registers_sha256 = loader_stub.registers_sha256
    registers_module.plan_group_reads = loader_stub.plan_group_reads
    registers_module._REGISTERS_PATH = registers_path
    registers_module.REG_TEMPORARY_FLOW_START = 0
    registers_module.REG_TEMPORARY_TEMP_START = 0
    registers_module.loader = loader_stub

    if force:
        sys.modules["custom_components.thessla_green_modbus.registers"] = registers_module
        sys.modules["custom_components.thessla_green_modbus.registers.loader"] = loader_stub
    else:
        sys.modules.setdefault("custom_components.thessla_green_modbus.registers", registers_module)
        sys.modules.setdefault("custom_components.thessla_green_modbus.registers.loader", loader_stub)


def install_integration_package_stub(base_path: Path, max_batch_registers: int = 16) -> None:
    """Install lightweight integration package and const stubs for loader tests."""
    pkg = types.ModuleType("custom_components.thessla_green_modbus")
    pkg.__path__ = [str(base_path)]
    sys.modules.setdefault("custom_components.thessla_green_modbus", pkg)

    const_module = types.ModuleType("custom_components.thessla_green_modbus.const")
    const_module.MAX_BATCH_REGISTERS = max_batch_registers
    sys.modules.setdefault("custom_components.thessla_green_modbus.const", const_module)
