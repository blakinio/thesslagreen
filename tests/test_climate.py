"""Tests for climate entity scaling when writing registers."""

import sys
import types
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs for required modules
# ---------------------------------------------------------------------------

# homeassistant.const
const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))


class UnitOfTemperature:
    CELSIUS = "°C"


const.UnitOfTemperature = UnitOfTemperature
const.ATTR_TEMPERATURE = "temperature"

# homeassistant.components.climate
climate_mod = types.ModuleType("homeassistant.components.climate")


class ClimateEntity:  # pragma: no cover - simple stub
    pass


class ClimateEntityFeature:  # pragma: no cover - simple stub
    TARGET_TEMPERATURE = 1
    FAN_MODE = 2
    PRESET_MODE = 4
    TURN_ON = 8
    TURN_OFF = 16


class HVACMode:  # pragma: no cover - simple stub
    OFF = "off"
    AUTO = "auto"
    FAN_ONLY = "fan_only"


class HVACAction:  # pragma: no cover - simple stub
    pass


climate_mod.ClimateEntity = ClimateEntity
climate_mod.ClimateEntityFeature = ClimateEntityFeature
climate_mod.HVACMode = HVACMode
climate_mod.HVACAction = HVACAction
sys.modules["homeassistant.components.climate"] = climate_mod

# homeassistant.helpers.update_coordinator.CoordinatorEntity
helpers_uc = sys.modules.setdefault(
    "homeassistant.helpers.update_coordinator", types.ModuleType("hass.helpers.uc")
)


class CoordinatorEntity:  # pragma: no cover - simple stub
    def __init__(self, coordinator):
        self.coordinator = coordinator

    @classmethod
    def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
        return cls


helpers_uc.CoordinatorEntity = CoordinatorEntity

# homeassistant.helpers.entity_platform.AddEntitiesCallback
entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# homeassistant.helpers.device_registry.DeviceInfo
device_registry = types.ModuleType("homeassistant.helpers.device_registry")


class DeviceInfo(dict):  # pragma: no cover - simple dict-based stub
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


device_registry.DeviceInfo = DeviceInfo
sys.modules["homeassistant.helpers.device_registry"] = device_registry


# ---------------------------------------------------------------------------
# Actual imports after stubbing
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.climate import (
    HVAC_MODE_MAP,
    HVAC_MODE_REVERSE_MAP,
    ThesslaGreenClimate,
)
from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.multipliers import REGISTER_MULTIPLIERS
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS


class DummyClient:
    """Simple Modbus client stub capturing written values."""

    def __init__(self):
        self.writes = []

    async def write_register(self, address, value, slave=None):
        self.writes.append((address, value, slave))

        class Response:
            def isError(self):
                return False

        return Response()

    async def write_coil(self, address, value, slave=None):  # pragma: no cover - not used
        self.writes.append((address, value, slave))

        class Response:
            def isError(self):
                return False

        return Response()


@pytest.mark.asyncio
async def test_set_temperature_scaling():
    """Ensure temperatures are scaled before writing to Modbus."""

    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.client = DummyClient()
    coordinator._ensure_connection = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.available_registers["holding_registers"].update(
        {"comfort_temperature", "required_temperature"}
    )
    coordinator.capabilities.basic_control = True

    climate = ThesslaGreenClimate(coordinator)

    await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 21.5})

    addr_comfort = HOLDING_REGISTERS["comfort_temperature"]
    addr_required = HOLDING_REGISTERS["required_temperature"]
    expected = int(round(21.5 / REGISTER_MULTIPLIERS["comfort_temperature"]))

    assert coordinator.client.writes == [
        (addr_comfort, expected, coordinator.slave_id),
        (addr_required, expected, coordinator.slave_id),
    ]


def test_target_temperature_none_when_unavailable():
    """Return None when no target temperature register is present."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.capabilities.basic_control = True
    coordinator.data = {}

    climate = ThesslaGreenClimate(coordinator)

    assert climate.target_temperature is None

    coordinator.data["comfort_temperature"] = 20.0
    assert climate.target_temperature == 20.0


def test_hvac_mode_mappings():
    """Verify device modes map to and from Home Assistant HVAC modes."""
    assert HVAC_MODE_MAP[0] == HVACMode.AUTO
    assert HVAC_MODE_MAP[1] == HVACMode.FAN_ONLY
    assert HVAC_MODE_MAP[2] == HVACMode.FAN_ONLY

    assert HVAC_MODE_REVERSE_MAP[HVACMode.AUTO] == 0
    assert HVAC_MODE_REVERSE_MAP[HVACMode.FAN_ONLY] == 1
    assert HVAC_MODE_REVERSE_MAP[HVACMode.OFF] == 0
