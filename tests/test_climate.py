"""Tests for climate entity scaling when writing registers."""

import sys
import types
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

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

from custom_components.thessla_green_modbus.climate import (  # noqa: E402
    HVAC_MODE_MAP,
    HVAC_MODE_REVERSE_MAP,
    ThesslaGreenClimate,
    async_setup_entry,
)
from custom_components.thessla_green_modbus.coordinator import (  # noqa: E402
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.registers.loader import (  # noqa: E402
    get_register_definition,
    get_registers_by_function,
)

HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}
from custom_components.thessla_green_modbus.const import DOMAIN  # noqa: E402


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
    coordinator.available_registers["holding_registers"].add("required_temperature")
    coordinator.capabilities.basic_control = True

    climate = ThesslaGreenClimate(coordinator)

    await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 21.5})

    addr_required = HOLDING_REGISTERS["required_temperature"]
    expected = get_register_definition("required_temperature").encode(21.5)

    assert coordinator.client.writes == [(addr_required, expected, coordinator.slave_id)]


def test_target_temperature_none_when_unavailable():
    """Return None when no target temperature register is present."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.capabilities.basic_control = True
    coordinator.data = {}

    climate = ThesslaGreenClimate(coordinator)

    assert climate.target_temperature is None

    coordinator.data["required_temperature"] = 20.0
    assert climate.target_temperature == 20.0


def test_hvac_mode_off_uses_on_off_panel_mode():
    """Ensure OFF is driven by on_off_panel_mode, not mapped to AUTO."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.capabilities.basic_control = True
    coordinator.data = {"on_off_panel_mode": 0, "mode": 0}

    climate = ThesslaGreenClimate(coordinator)

    assert climate.hvac_mode == HVACMode.OFF


def test_hvac_mode_auto_when_panel_on():
    """Ensure AUTO is reported when the panel is on and mode is automatic."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.capabilities.basic_control = True
    coordinator.data = {"on_off_panel_mode": 1, "mode": 0}

    climate = ThesslaGreenClimate(coordinator)

    assert climate.hvac_mode == HVACMode.AUTO


def test_fan_modes_respect_min_max_limits():
    """Fan modes should honor dynamic min/max limits up to 150%."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.data = {"min_percentage": 20, "max_percentage": 150}

    climate = ThesslaGreenClimate(coordinator)

    assert climate.fan_modes[0] == "20%"
    assert climate.fan_modes[-1] == "150%"


def test_fan_mode_clamps_to_max_percentage():
    """Fan mode string should clamp to max percentage."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.data = {
        "min_percentage": 10,
        "max_percentage": 150,
        "air_flow_rate_manual": 160,
    }

    climate = ThesslaGreenClimate(coordinator)

    assert climate.fan_mode == "150%"


def test_hvac_mode_mappings():
    """Verify device modes map to and from Home Assistant HVAC modes."""
    assert HVAC_MODE_MAP[0] == HVACMode.AUTO
    assert HVAC_MODE_MAP[1] == HVACMode.FAN_ONLY
    assert HVAC_MODE_MAP[2] == HVACMode.FAN_ONLY

    assert HVAC_MODE_REVERSE_MAP[HVACMode.AUTO] == 0
    assert HVAC_MODE_REVERSE_MAP[HVACMode.FAN_ONLY] == 1
    assert HVACMode.OFF not in HVAC_MODE_REVERSE_MAP


@pytest.mark.asyncio
async def test_set_hvac_mode_turns_on_before_mode():
    """Setting HVAC mode should power on before changing the mode register."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {"on_off_panel_mode": 0}

    climate = ThesslaGreenClimate(coordinator)

    await climate.async_set_hvac_mode(HVACMode.AUTO)

    assert coordinator.async_write_register.await_args_list[:2] == [
        call("on_off_panel_mode", 1, refresh=False),
        call("mode", 0, refresh=False),
    ]


@pytest.mark.asyncio
async def test_set_temperature_temporary_mode_uses_multi_write():
    """Temporary mode should use the 3-register block and avoid permanent writes."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator(hass, "host", 502, 1, "dev", timedelta(seconds=1))
    coordinator.data = {"mode": 2}
    coordinator.async_write_temporary_temperature = AsyncMock(return_value=True)
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    climate = ThesslaGreenClimate(coordinator)

    await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 22.0})

    coordinator.async_write_temporary_temperature.assert_awaited_once_with(22.0, refresh=False)
    coordinator.async_write_register.assert_not_called()
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_force_full_register_list_creates_climate(mock_coordinator, mock_config_entry):
    """Climate entity created when forcing full register list."""

    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    mock_coordinator.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
        "calculated": set(),
    }
    mock_coordinator.force_full_register_list = True
    mock_coordinator.capabilities.basic_control = False

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    entities = add_entities.call_args[0][0]
    assert any(isinstance(e, ThesslaGreenClimate) for e in entities)  # nosec B101
