"""Validate SENSOR_DEFINITIONS register mapping."""

import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
const.PERCENTAGE = "%"


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


class SensorDeviceClass:  # pragma: no cover - enum stub
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
    POWER = "power"
    ENERGY = "energy"


class SensorStateClass:  # pragma: no cover - enum stub
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


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
# Actual test
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.entity_mappings import (  # noqa: E402
    ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.registers.loader import (  # noqa: E402
    get_registers_by_function,
)

SENSOR_DEFINITIONS = ENTITY_MAPPINGS.get("sensor", {})

INPUT_REGISTERS = {r.name for r in get_registers_by_function("04")}
HOLDING_REGISTERS = {r.name for r in get_registers_by_function("03")}


def test_sensor_register_mapping() -> None:
    """Each sensor must map to the correct register dictionary."""
    for register_name, sensor_def in SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        if register_type == "input_registers":
            assert register_name in INPUT_REGISTERS
            assert register_name not in HOLDING_REGISTERS
        elif register_type == "holding_registers":
            assert register_name in HOLDING_REGISTERS
            assert register_name not in INPUT_REGISTERS
        elif register_type == "calculated":
            assert register_name not in INPUT_REGISTERS
            assert register_name not in HOLDING_REGISTERS
        else:
            pytest.fail(f"Unknown register_type {register_type} for {register_name}")
