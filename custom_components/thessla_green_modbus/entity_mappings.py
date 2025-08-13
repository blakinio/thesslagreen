"""Entity mapping definitions for the ThesslaGreen Modbus integration.

This module also provides helpers for handling legacy entity IDs that were
renamed in newer versions of the integration.
"""

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)

from .const import SPECIAL_FUNCTION_MAP

_LOGGER = logging.getLogger(__name__)

# Map legacy entity suffixes to new domain and suffix pairs. Only a small
# subset of legacy names existed in early versions of the integration. These
# mappings allow services to transparently use the new entity IDs while warning
# users to update their automations.
LEGACY_ENTITY_ID_ALIASES: Dict[str, tuple[str, str]] = {
    # "number.rekuperator_predkosc" / "number.rekuperator_speed" → fan entity
    "rekuperator_predkosc": ("fan", "fan"),
    "rekuperator_speed": ("fan", "fan"),
}

_alias_warning_logged = False


def map_legacy_entity_id(entity_id: str) -> str:
    """Map a legacy entity ID to the new format.

    If the provided ``entity_id`` matches one of the known legacy aliases, the
    corresponding new entity ID is returned and a warning is logged exactly
    once to inform the user about the change.
    """

    global _alias_warning_logged

    if "." not in entity_id:
        return entity_id

    domain, object_id = entity_id.split(".", 1)
    suffix = object_id.rsplit("_", 1)[-1]
    if suffix not in LEGACY_ENTITY_ID_ALIASES:
        return entity_id

    new_domain, new_suffix = LEGACY_ENTITY_ID_ALIASES[suffix]
    parts = object_id.split("_")
    new_object_id = "_".join(parts[:-1] + [new_suffix]) if len(parts) > 1 else new_suffix
    new_entity_id = f"{new_domain}.{new_object_id}"

    if not _alias_warning_logged:
        _LOGGER.warning(
            "Legacy entity ID '%s' detected. Please update your automations to use '%s'",
            entity_id,
            new_entity_id,
        )
        _alias_warning_logged = True

    return new_entity_id


NUMBER_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "required_temperature": {
        "unit": "°C",
        "min": 16,
        "max": 26,
        "step": 0.5,
    },
    # Temperature limit registers
    "min_gwc_air_temperature": {
        "unit": "°C",
        "min": -20,
        "max": 50,
        "step": 0.5,
    },
    "max_gwc_air_temperature": {
        "unit": "°C",
        "min": -20,
        "max": 50,
        "step": 0.5,
    },
    "min_bypass_temperature": {
        "unit": "°C",
        "min": 0,
        "max": 40,
        "step": 0.5,
    },
    # Airflow coefficient registers
    "fan_speed_1_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "fan_speed_2_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "fan_speed_3_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "hood_supply_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "hood_exhaust_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "fireplace_supply_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "airing_bathroom_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "airing_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "contamination_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "empty_house_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "airing_switch_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "open_window_coef": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "bypass_coef_1": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    "bypass_coef_2": {
        "unit": "%",
        "min": 0,
        "max": 200,
        "step": 1,
    },
    # Airflow limit registers
    "max_supply_air_flow_rate": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "max_exhaust_air_flow_rate": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "nominal_supply_air_flow": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "nominal_exhaust_air_flow": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "max_supply_air_flow_rate_gwc": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "max_exhaust_air_flow_rate_gwc": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "nominal_supply_air_flow_gwc": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    "nominal_exhaust_air_flow_gwc": {
        "unit": "m³/h",
        "min": 0,
        "max": 500,
        "step": 5,
    },
    # Bypass settings
    "bypass_off": {
        "unit": "°C",
        "min": 0,
        "max": 40,
        "step": 0.5,
        "scale": 0.5,
    },
}

SENSOR_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Temperature sensors
    "outside_temperature": {
        "translation_key": "outside_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "supply_temperature": {
        "translation_key": "supply_temperature",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "exhaust_temperature": {
        "translation_key": "exhaust_temperature",
        "icon": "mdi:thermometer-minus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "fpx_temperature": {
        "translation_key": "fpx_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "duct_supply_temperature": {
        "translation_key": "duct_supply_temperature",
        "icon": "mdi:thermometer-lines",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "gwc_temperature": {
        "translation_key": "gwc_temperature",
        "icon": "mdi:thermometer-low",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "ambient_temperature": {
        "translation_key": "ambient_temperature",
        "icon": "mdi:home-thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heating_temperature": {
        "translation_key": "heating_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    # System information
    "day_of_week": {
        "translation_key": "day_of_week",
        "icon": "mdi:calendar-week",
        "register_type": "input_registers",
    },
    "period": {
        "translation_key": "period",
        "icon": "mdi:clock-outline",
        "register_type": "input_registers",
    },
    "compilation_days": {
        "translation_key": "compilation_days",
        "icon": "mdi:calendar",
        "register_type": "input_registers",
    },
    "compilation_seconds": {
        "translation_key": "compilation_seconds",
        "icon": "mdi:timer",
        "register_type": "input_registers",
    },
    "serial_number_1": {
        "translation_key": "serial_number_1",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_2": {
        "translation_key": "serial_number_2",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_3": {
        "translation_key": "serial_number_3",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_4": {
        "translation_key": "serial_number_4",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_5": {
        "translation_key": "serial_number_5",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_6": {
        "translation_key": "serial_number_6",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    # Flow sensors
    "supply_flow_rate": {
        "translation_key": "supply_flow_rate",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flow_rate": {
        "translation_key": "exhaust_flow_rate",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "max_supply_air_flow_rate": {
        "translation_key": "max_supply_air_flow_rate",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "max_exhaust_air_flow_rate": {
        "translation_key": "max_exhaust_air_flow_rate",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_supply_air_flow": {
        "translation_key": "nominal_supply_air_flow",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_exhaust_air_flow": {
        "translation_key": "nominal_exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "bypass_off": {
        "translation_key": "bypass_off",
        "icon": "mdi:thermometer-off",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    # PWM control values
    "dac_supply": {
        "translation_key": "dac_supply",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "input_registers",
    },
    "dac_exhaust": {
        "translation_key": "dac_exhaust",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "input_registers",
    },
    "dac_heater": {
        "translation_key": "dac_heater",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "input_registers",
    },
    "dac_cooler": {
        "translation_key": "dac_cooler",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "input_registers",
    },
    # Percentage sensors
    "supply_percentage": {
        "translation_key": "supply_percentage",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "exhaust_percentage": {
        "translation_key": "exhaust_percentage",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "min_percentage": {
        "translation_key": "min_percentage",
        "icon": "mdi:percent-outline",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "max_percentage": {
        "translation_key": "max_percentage",
        "icon": "mdi:percent-outline",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
}

BINARY_SENSOR_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # System status (from coil registers)
    "duct_water_heater_pump": {
        "translation_key": "duct_water_heater_pump",
        "icon": "mdi:pump",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "bypass": {
        "translation_key": "bypass",
        "icon": "mdi:pipe-leak",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "coil_registers",
    },
    "info": {
        "translation_key": "info",
        "icon": "mdi:information",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "power_supply_fans": {
        "translation_key": "power_supply_fans",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "coil_registers",
    },
    "heating_cable": {
        "translation_key": "heating_cable",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "coil_registers",
    },
    "work_permit": {
        "translation_key": "work_permit",
        "icon": "mdi:check-circle",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "gwc": {
        "translation_key": "gwc",
        "icon": "mdi:pipe",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "hood_output": {
        "translation_key": "hood_output",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    # System status (from discrete inputs)
    "expansion": {
        "translation_key": "expansion",
        "icon": "mdi:expansion-card",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "contamination_sensor": {
        "translation_key": "contamination_sensor",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "duct_heater_protection": {
        "translation_key": "duct_heater_protection",
        "icon": "mdi:shield-heat",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "dp_duct_filter_overflow": {
        "translation_key": "dp_duct_filter_overflow",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "airing_sensor": {
        "translation_key": "airing_sensor",
        "icon": "mdi:motion-sensor",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_switch": {
        "translation_key": "airing_switch",
        "icon": "mdi:toggle-switch",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "airing_mini": {
        "translation_key": "airing_mini",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_3": {
        "translation_key": "fan_speed_3",
        "icon": "mdi:fan-speed-3",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_2": {
        "translation_key": "fan_speed_2",
        "icon": "mdi:fan-speed-2",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fan_speed_1": {
        "translation_key": "fan_speed_1",
        "icon": "mdi:fan-speed-1",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fireplace": {
        "translation_key": "fireplace",
        "icon": "mdi:fireplace",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "dp_ahu_filter_overflow": {
        "translation_key": "dp_ahu_filter_overflow",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "ahu_filter_protection": {
        "translation_key": "ahu_filter_protection",
        "icon": "mdi:shield",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "empty_house": {
        "translation_key": "empty_house",
        "icon": "mdi:home-outline",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "discrete_inputs",
    },
    "fire_alarm": {
        "translation_key": "fire_alarm",
        "icon": "mdi:fire",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "register_type": "discrete_inputs",
    },
    # Active modes (from input registers)
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "icon": "mdi:waves",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "water_removal_active": {
        "translation_key": "water_removal_active",
        "icon": "mdi:water-off",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "register_type": "input_registers",
    },
    # Device main status (from holding registers)
    "on_off_panel_mode": {
        "translation_key": "on_off_panel_mode",
        "icon": "mdi:power",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "holding_registers",
    },
}

SPECIAL_MODE_ICONS = {
    "boost": "mdi:rocket-launch",
    "eco": "mdi:leaf",
    "away": "mdi:airplane",
    "fireplace": "mdi:fireplace",
    "hood": "mdi:range-hood",
    "sleep": "mdi:weather-night",
    "party": "mdi:party-popper",
    "bathroom": "mdi:shower",
    "kitchen": "mdi:chef-hat",
    "summer": "mdi:white-balance-sunny",
    "winter": "mdi:snowflake",
}

SWITCH_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # System control switches from holding registers
    "on_off_panel_mode": {
        "icon": "mdi:power",
        "register": "on_off_panel_mode",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "on_off_panel_mode",
    },
}

for mode, bit in SPECIAL_FUNCTION_MAP.items():
    SWITCH_ENTITY_MAPPINGS[mode] = {
        "icon": SPECIAL_MODE_ICONS.get(mode, "mdi:toggle-switch"),
        "register": "special_mode",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": mode,
        "bit": bit,
    }

ENTITY_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
    "sensor": SENSOR_ENTITY_MAPPINGS,
    "binary_sensor": BINARY_SENSOR_ENTITY_MAPPINGS,
    "switch": SWITCH_ENTITY_MAPPINGS,
}
