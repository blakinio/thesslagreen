"""Tests for ThesslaGreen sensor platform setup."""

import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
setattr(const, "PERCENTAGE", "%")


class UnitOfTemperature:  # pragma: no cover - enum stub
    CELSIUS = "°C"


class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
    CUBIC_METERS_PER_HOUR = "m³/h"


class UnitOfElectricPotential:  # pragma: no cover - enum stub
    VOLT = "V"


const.UnitOfTemperature = UnitOfTemperature
const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate
const.UnitOfElectricPotential = UnitOfElectricPotential

sensor_mod = types.ModuleType("homeassistant.components.sensor")


class SensorEntity:  # pragma: no cover - simple stub
    pass


class SensorDeviceClass:  # pragma: no cover - enum stubs
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"


class SensorStateClass:  # pragma: no cover - enum stubs
    MEASUREMENT = "measurement"


sensor_mod.SensorEntity = SensorEntity
sensor_mod.SensorDeviceClass = SensorDeviceClass
sensor_mod.SensorStateClass = SensorStateClass
sys.modules["homeassistant.components.sensor"] = sensor_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.const import DOMAIN  # noqa: E402
from custom_components.thessla_green_modbus.sensor import (  # noqa: E402
    SENSOR_DEFINITIONS,
    async_setup_entry,
)


def test_async_setup_creates_all_sensors(mock_coordinator, mock_config_entry):
    """Ensure entities are created for all available sensor registers."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        available = {
            "input_registers": set(),
            "holding_registers": set(),
        }
        for name, definition in SENSOR_DEFINITIONS.items():
            available.setdefault(definition["register_type"], set()).add(name)
        mock_coordinator.available_registers = available

        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        assert len(SENSOR_DEFINITIONS) == 46  # nosec B101
        assert len(entities) == 46  # nosec B101

    asyncio.run(run_test())


def test_sensors_have_native_units(mock_coordinator, mock_config_entry):
    """Verify sensors expose the expected native_unit_of_measurement."""

    async def run_test() -> None:
        hass = MagicMock()
        hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        available = {
            "input_registers": set(),
            "holding_registers": set(),
        }
        for name, definition in SENSOR_DEFINITIONS.items():
            available.setdefault(definition["register_type"], set()).add(name)
        mock_coordinator.available_registers = available

        add_entities = MagicMock()
        await async_setup_entry(hass, mock_config_entry, add_entities)

        entities = add_entities.call_args[0][0]
        for entity in entities:
            expected = SENSOR_DEFINITIONS[entity._register_name].get("unit")
            assert (
                getattr(entity, "_attr_native_unit_of_measurement", None) == expected
            )  # nosec B101

    asyncio.run(run_test())
