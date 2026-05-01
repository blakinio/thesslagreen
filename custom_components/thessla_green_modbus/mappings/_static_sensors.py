"""Static sensor mappings for ThesslaGreen entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.entity import EntityCategory

from ._static_sensor_temperatures import (
    HOLDING_TEMPERATURE_SENSOR_MAPPINGS,
    INPUT_TEMPERATURE_SENSOR_MAPPINGS,
)


def _diagnostic_sensor_payload(
    translation_key: str,
    *,
    icon: str = "mdi:information",
    register_type: str = "input_registers",
) -> dict[str, Any]:
    """Build a standard diagnostic sensor payload."""
    return {
        "translation_key": translation_key,
        "icon": icon,
        "register_type": register_type,
        "entity_category": EntityCategory.DIAGNOSTIC,
    }


SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    # Temperature sensors (Input Registers)
    **INPUT_TEMPERATURE_SENSOR_MAPPINGS,
    # Air flow sensors
    "supply_flow_rate": {
        "translation_key": "supply_flow_rate_m3h",
        "icon": "mdi:fan-plus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flow_rate": {
        "translation_key": "exhaust_flow_rate_m3h",
        "icon": "mdi:fan-minus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "icon": "mdi:fan-plus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "icon": "mdi:fan-minus",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
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
        # Register 2: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        "value_map": {
            0: "monday",
            1: "tuesday",
            2: "wednesday",
            3: "thursday",
            4: "friday",
            5: "saturday",
            6: "sunday",
        },
    },
    "period": {
        "translation_key": "period",
        "icon": "mdi:clock-outline",
        "register_type": "input_registers",
        # Register 3: 0=slot 1, 1=slot 2, 2=slot 3, 3=slot 4
        "value_map": {0: "slot_1", 1: "slot_2", 2: "slot_3", 3: "slot_4"},
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
    "version_major": _diagnostic_sensor_payload("version_major"),
    "version_minor": _diagnostic_sensor_payload("version_minor"),
    "version_patch": _diagnostic_sensor_payload("version_patch"),
    "serial_number": _diagnostic_sensor_payload("serial_number", icon="mdi:barcode"),
    "cf_version": _diagnostic_sensor_payload("cf_version", register_type="holding_registers"),
    "exp_version": _diagnostic_sensor_payload(
        "exp_version",
        icon="mdi:information-outline",
        register_type="holding_registers",
    ),
    # Mode and status sensors
    "antifreeze_stage": {
        "translation_key": "antifreeze_stage",
        "icon": "mdi:snowflake-thermometer",
        "register_type": "holding_registers",
        # Register 4198: 0=FPX off, 1=FPX mode 1, 2=FPX mode 2
        "value_map": {0: "off", 1: "fpx1", 2: "fpx2"},
    },
    # gwc_mode and bypass_mode are read-only status registers (access="R") that
    # report the device's automatically-determined state. They are exposed as
    # sensors with a value_map rather than select entities so that HA does not
    # present a writable dropdown for registers that cannot accept writes.
    "gwc_mode": {
        "translation_key": "gwc_mode",
        "icon": "mdi:pipe",
        "register_type": "holding_registers",
        "value_map": {0: "off", 1: "auto", 2: "forced"},
    },
    "bypass_mode": {
        "translation_key": "bypass_mode",
        "icon": "mdi:pipe-leak",
        "register_type": "holding_registers",
        # Register 4330: 0=bypass inactive (HX active), 1=freeheating, 2=freecooling.
        # Both 1 and 2 mean the bypass damper is physically open.
        "value_map": {0: "inactive", 1: "freeheating", 2: "freecooling"},
    },
    # mode and season_mode are covered by SELECT_ENTITY_MAPPINGS (writable).
    "comfort_mode": {
        "translation_key": "comfort_mode",
        "icon": "mdi:home-heart",
        "register_type": "holding_registers",
        # Register 4305: 0=inactive, 1=heating function, 2=cooling function
        "value_map": {0: "inactive", 1: "heating", 2: "cooling"},
    },
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "icon": "mdi:waves",
        "register_type": "input_registers",
        # Register 271: 0=inactive, 1=active
        "value_map": {0: "inactive", 1: "active"},
    },
    # Filter replacement dates (read-only holding registers)
    "filter_supply_date_limit_get": {
        "translation_key": "filter_supply_date_limit_get",
        "icon": "mdi:calendar-filter",
        "register_type": "holding_registers",
    },
    "filter_exhaust_date_limit_get": {
        "translation_key": "filter_exhaust_date_limit_get",
        "icon": "mdi:calendar-filter",
        "register_type": "holding_registers",
    },
    # Configuration sensors from holding registers
    **HOLDING_TEMPERATURE_SENSOR_MAPPINGS,
    # lock_date — product-key expiry year (BCD-encoded, read-only)
    "lock_date": {
        "translation_key": "lock_date",
        "icon": "mdi:calendar-lock",
        "register_type": "holding_registers",
    },
    # required_temperature — read-only comfort-mode temperature setpoint display
    "required_temperature": {
        "translation_key": "required_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
    },
    # lock_date fields — product-key expiry date (read-only)
    "lock_date_00dd": {
        "translation_key": "lock_date_00dd",
        "icon": "mdi:calendar-lock",
        "register_type": "holding_registers",
    },
    "lock_date_00mm": {
        "translation_key": "lock_date_00mm",
        "icon": "mdi:calendar-lock",
        "register_type": "holding_registers",
    },
    "max_supply_air_flow_rate": {
        "translation_key": "max_supply_air_flow_rate",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "max_exhaust_air_flow_rate": {
        "translation_key": "max_exhaust_air_flow_rate",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "holding_registers",
    },
    "nominal_supply_air_flow": {
        "translation_key": "nominal_supply_air_flow",
        "icon": "mdi:fan-clock",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_exhaust_air_flow": {
        "translation_key": "nominal_exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
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
    # estimated_power and total_energy were register_type="calculated" and are
    # never instantiated by the sensor platform — removed until a
    # computed-register mechanism is implemented.
    # AHU stop alarm code (0 = no alarm, 1 = alarm type S active)
    "stop_ahu_code": {
        "translation_key": "stop_ahu_code",
        "icon": "mdi:alert-circle",
        "register_type": "holding_registers",
        # Register 4384: 0=no blocking alarm, 1=type S alarm (code 98)
        "value_map": {0: "none", 1: "alarm_s"},
    },
    # Derived / calculated sensors — values are produced by the coordinator's
    # _post_process_data and do not correspond to a single Modbus register.
    "device_clock": {
        "translation_key": "device_clock",
        "icon": "mdi:clock-outline",
        "device_class": None,
        "state_class": None,
        "unit": None,
        "register_type": "calculated",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "heat_recovery_efficiency": {
        "translation_key": "heat_recovery_efficiency",
        "icon": "mdi:heat-wave",
        "device_class": getattr(SensorDeviceClass, "EFFICIENCY", None),
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "calculated",
        "suggested_display_precision": 1,
    },
    "heat_recovery_power": {
        "translation_key": "heat_recovery_power",
        "icon": "mdi:radiator",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "calculated",
    },
    "electrical_power": {
        "translation_key": "electrical_power",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "calculated",
    },
}

__all__ = ["SENSOR_ENTITY_MAPPINGS"]
