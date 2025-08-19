"""Entity mapping definitions for the ThesslaGreen Modbus integration.

This module also provides helpers for handling legacy entity IDs that were
renamed in newer versions of the integration.
"""

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

try:  # pragma: no cover - use HA constants when available
    from homeassistant.const import (
        UnitOfElectricPotential,
        UnitOfTemperature,
        UnitOfTime,
        UnitOfVolumeFlowRate,
    )
except Exception:  # pragma: no cover - executed only in tests

    class UnitOfElectricPotential:  # type: ignore[no-redef]
        VOLT = "V"

    class UnitOfTemperature:  # type: ignore[no-redef]
        CELSIUS = "°C"

    class UnitOfTime:  # type: ignore[no-redef]
        HOURS = "h"
        DAYS = "d"
        SECONDS = "s"

    class UnitOfVolumeFlowRate:  # type: ignore[no-redef]
        CUBIC_METERS_PER_HOUR = "m³/h"


try:  # pragma: no cover - fallback for tests without full HA constants
    from homeassistant.const import PERCENTAGE
except Exception:  # pragma: no cover - executed only in tests
    PERCENTAGE = "%"

from .const import SPECIAL_FUNCTION_MAP

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy entity ID mapping
# ---------------------------------------------------------------------------
# Map legacy entity suffixes to new domain and suffix pairs. Only a small
# subset of legacy names existed in early versions of the integration. These
# mappings allow services to transparently use the new entity IDs while warning
# users to update their automations.
LEGACY_ENTITY_ID_ALIASES: Dict[str, tuple[str, str]] = {
    # Keys are suffixes of legacy entity_ids.
    # "number.rekuperator_predkosc" / "number.rekuperator_speed" → fan entity
    "predkosc": ("fan", "fan"),
    "speed": ("fan", "fan"),
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
            "Legacy entity ID '%s' detected. Please update automations to use '%s'.",
            entity_id,
            new_entity_id,
        )
        _alias_warning_logged = True

    return new_entity_id


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _load_number_mappings() -> dict[str, dict[str, Any]]:
    """Load number entity configurations from CSV data.

    This function reads register configurations and dynamically creates
    number entity mappings with proper min/max/step values.
    """
    from .data.modbus_registers import get_register_info

    number_configs: dict[str, dict[str, Any]] = {}

    # Define registers that should be number entities
    number_registers: dict[str, dict[str, str | None]] = {
        # Temperature control
        "required_temperature": {"unit": "°C", "icon": "mdi:thermometer"},
        "supply_air_temperature_manual": {"unit": "°C", "icon": "mdi:thermometer-plus"},
        "supply_air_temperature_temporary_1": {"unit": "°C", "icon": "mdi:thermometer-plus"},
        "supply_air_temperature_temporary_2": {"unit": "°C", "icon": "mdi:thermometer-plus"},
        "min_bypass_temperature": {"unit": "°C", "icon": "mdi:thermometer-low"},
        "air_temperature_summer_free_heating": {"unit": "°C", "icon": "mdi:thermometer"},
        "air_temperature_summer_free_cooling": {"unit": "°C", "icon": "mdi:thermometer"},
        "bypass_off": {"unit": "°C", "icon": "mdi:thermometer-off"},
        # Air flow control
        "air_flow_rate_manual": {"unit": "m³/h", "icon": "mdi:fan"},
        "max_supply_air_flow_rate": {"unit": "m³/h", "icon": "mdi:fan-plus"},
        "max_exhaust_air_flow_rate": {"unit": "m³/h", "icon": "mdi:fan-minus"},
        "nominal_supply_air_flow": {"unit": "m³/h", "icon": "mdi:fan-clock"},
        "nominal_exhaust_air_flow": {"unit": "m³/h", "icon": "mdi:fan-clock"},
        "max_supply_air_flow_rate_gwc": {"unit": "m³/h", "icon": "mdi:fan-plus"},
        "max_exhaust_air_flow_rate_gwc": {"unit": "m³/h", "icon": "mdi:fan-minus"},
        "nominal_supply_air_flow_gwc": {"unit": "m³/h", "icon": "mdi:fan-clock"},
        "nominal_exhaust_air_flow_gwc": {"unit": "m³/h", "icon": "mdi:fan-clock"},
        # Access and timing
        "access_level": {"unit": None, "icon": "mdi:account-key"},
        # GWC parameters
        "min_gwc_air_temperature": {"unit": "°C", "icon": "mdi:thermometer-low"},
        "max_gwc_air_temperature": {"unit": "°C", "icon": "mdi:thermometer-high"},
        "gwc_regen_period": {"unit": "h", "icon": "mdi:timer"},
        "delta_t_gwc": {"unit": "°C", "icon": "mdi:thermometer-lines"},
    }

    for register, config in number_registers.items():
        try:
            reg_info = get_register_info(register)
            if reg_info:
                number_configs[register] = {
                    "unit": config["unit"],
                    "icon": config["icon"],
                    "min": reg_info.get("min", 0),
                    "max": reg_info.get("max", 100),
                    "step": reg_info.get("step", 1),
                    "scale": reg_info.get("scale", 1),
                }
        except Exception:
            # Fallback to static configuration
            number_configs[register] = {
                "unit": config["unit"],
                "icon": config["icon"],
                "min": 0,
                "max": 100,
                "step": 1,
            }

    return number_configs


# ---------------------------------------------------------------------------
# Entity configurations
# ---------------------------------------------------------------------------

# Number entity mappings loaded from register metadata
NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = _load_number_mappings()
SENSOR_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    # Temperature sensors (Input Registers)
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
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "gwc_temperature": {
        "translation_key": "gwc_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "ambient_temperature": {
        "translation_key": "ambient_temperature",
        "icon": "mdi:thermometer",
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
    # Air flow sensors
    "supply_flow_rate": {
        "translation_key": "supply_flow_rate_m3h",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flow_rate": {
        "translation_key": "exhaust_flow_rate_m3h",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
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
    # System information sensors
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
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTime.DAYS,
        "register_type": "input_registers",
    },
    "compilation_seconds": {
        "translation_key": "compilation_seconds",
        "icon": "mdi:timer",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTime.SECONDS,
        "register_type": "input_registers",
    },
    "version_major": {
        "translation_key": "version_major",
        "icon": "mdi:information",
        "register_type": "input_registers",
    },
    "version_minor": {
        "translation_key": "version_minor",
        "icon": "mdi:information",
        "register_type": "input_registers",
    },
    "version_patch": {
        "translation_key": "version_patch",
        "icon": "mdi:information",
        "register_type": "input_registers",
    },
    "serial_number_1": {
        "translation_key": "serial_number_1",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
    },
    "serial_number_2": {
        "translation_key": "serial_number_2",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
    },
    "serial_number_3": {
        "translation_key": "serial_number_3",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
    },
    "serial_number_4": {
        "translation_key": "serial_number_4",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
    },
    "serial_number_5": {
        "translation_key": "serial_number_5",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
    },
    "serial_number_6": {
        "translation_key": "serial_number_6",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
    },
    # Mode and status sensors
    "antifreeze_mode": {
        "translation_key": "antifreeze_mode",
        "icon": "mdi:snowflake-alert",
        "register_type": "input_registers",
    },
    "mode": {
        "translation_key": "mode",
        "icon": "mdi:cog",
        "register_type": "input_registers",
    },
    "season_mode": {
        "translation_key": "season_mode",
        "icon": "mdi:weather-sunny",
        "register_type": "input_registers",
    },
    "gwc_mode": {
        "translation_key": "gwc_mode",
        "icon": "mdi:pipe",
        "register_type": "input_registers",
    },
    "bypass_mode": {
        "translation_key": "bypass_mode",
        "icon": "mdi:pipe-leak",
        "register_type": "input_registers",
    },
    "comfort_mode": {
        "translation_key": "comfort_mode",
        "icon": "mdi:home-heart",
        "register_type": "input_registers",
    },
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "icon": "mdi:waves",
        "register_type": "input_registers",
    },
    # Configuration sensors from holding registers
    "supply_air_temperature_manual": {
        "translation_key": "supply_air_temperature_manual",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "supply_air_temperature_temporary_1": {
        "translation_key": "supply_air_temperature_temporary_1",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "supply_air_temperature_temporary_2": {
        "translation_key": "supply_air_temperature_temporary_2",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "min_bypass_temperature": {
        "translation_key": "min_bypass_temperature",
        "icon": "mdi:thermometer-low",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "air_temperature_summer_free_heating": {
        "translation_key": "air_temperature_summer_free_heating",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "air_temperature_summer_free_cooling": {
        "translation_key": "air_temperature_summer_free_cooling",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "required_temp": {
        "translation_key": "required_temp",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    "max_supply_air_flow_rate": {
        "translation_key": "max_supply_air_flow_rate",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "max_exhaust_air_flow_rate": {
        "translation_key": "max_exhaust_air_flow_rate",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_supply_air_flow": {
        "translation_key": "nominal_supply_air_flow",
        "icon": "mdi:fan-clock",
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
    # PWM control values (napięcia wentylatorów)
    "dac_supply": {
        "translation_key": "dac_supply",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    "dac_exhaust": {
        "translation_key": "dac_exhaust",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    "dac_heater": {
        "translation_key": "dac_heater",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    "dac_cooler": {
        "translation_key": "dac_cooler",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfElectricPotential.VOLT,
        "register_type": "holding_registers",
    },
    # Derived power sensors
    "estimated_power": {
        "translation_key": "estimated_power",
        "icon": "mdi:flash",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "W",
        "register_type": "calculated",
    },
    "total_energy": {
        "translation_key": "total_energy",
        "icon": "mdi:counter",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": "kWh",
        "register_type": "calculated",
    },
    # Coefficients and intensive settings
    "fan_speed_1_coef": {
        "translation_key": "fan_speed_1_coef",
        "icon": "mdi:speedometer",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "fan_speed_2_coef": {
        "translation_key": "fan_speed_2_coef",
        "icon": "mdi:speedometer",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "fan_speed_3_coef": {
        "translation_key": "fan_speed_3_coef",
        "icon": "mdi:speedometer",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "hood_supply_coef": {
        "translation_key": "hood_supply_coef",
        "icon": "mdi:stove",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "hood_exhaust_coef": {
        "translation_key": "hood_exhaust_coef",
        "icon": "mdi:stove",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "intensive_supply": {
        "translation_key": "intensive_supply",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "intensive_exhaust": {
        "translation_key": "intensive_exhaust",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    # Calculated metrics
    "calculated_efficiency": {
        "translation_key": "calculated_efficiency",
        "icon": "mdi:percent",
        "device_class": getattr(SensorDeviceClass, "EFFICIENCY", "efficiency"),
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
}

SELECT_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "mode": {
        "icon": "mdi:cog",
        "translation_key": "mode",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "bypass_mode": {
        "icon": "mdi:pipe-leak",
        "translation_key": "bypass_mode",
        "states": {"auto": 0, "open": 1, "closed": 2},
        "register_type": "holding_registers",
    },
    "gwc_mode": {
        "icon": "mdi:pipe",
        "translation_key": "gwc_mode",
        "states": {"off": 0, "auto": 1, "forced": 2},
        "register_type": "holding_registers",
    },
    "season_mode": {
        "icon": "mdi:weather-partly-snowy",
        "translation_key": "season_mode",
        "states": {"winter": 0, "summer": 1},
        "register_type": "holding_registers",
    },
    "filter_change": {
        "icon": "mdi:filter-variant",
        "translation_key": "filter_change",
        "states": {
            "presostat": 1,
            "flat_filters": 2,
            "cleanpad": 3,
            "cleanpad_pure": 4,
        },
        "register_type": "holding_registers",
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
    "hood_switch": {
        "translation_key": "hood_switch",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
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

ENTITY_MAPPINGS: dict[str, dict[str, dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
    "sensor": SENSOR_ENTITY_MAPPINGS,
    "binary_sensor": BINARY_SENSOR_ENTITY_MAPPINGS,
    "switch": SWITCH_ENTITY_MAPPINGS,
    "select": SELECT_ENTITY_MAPPINGS,
}
