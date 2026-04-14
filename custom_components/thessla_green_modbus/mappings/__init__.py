"""Entity mapping definitions for the ThesslaGreen Modbus integration.

Most entity descriptions are generated from the bundled register
metadata and can be extended or overridden by the dictionaries defined in
this module. This keeps the mapping definitions in sync with the register
specification while still allowing manual tweaks (for example to change
icons or alter the entity domain).

The module also provides helpers for handling legacy entity IDs that
were renamed in newer versions of the integration.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import TYPE_CHECKING, Any

from .._compat import (
    PERCENTAGE,
    BinarySensorDeviceClass,
    EntityCategory,
    SensorDeviceClass,
    SensorStateClass,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant

from ..const import (
    coil_registers as coil_registers,
)
from ..const import (
    discrete_input_registers as discrete_input_registers,
)
from ..const import (
    holding_registers as holding_registers,
)

# ---------------------------------------------------------------------------
# Submodule imports — each submodule owns its code; __init__ is the controller
# ---------------------------------------------------------------------------
from ._helpers import (
    _REGISTER_INFO_CACHE as _REGISTER_INFO_CACHE,
)
from ._helpers import (
    _get_register_info as _get_register_info,
)
from ._helpers import (
    _infer_icon as _infer_icon,
)
from ._helpers import (
    _load_translation_keys as _load_translation_keys,
)
from ._helpers import (
    _number_translation_keys as _number_translation_keys,
)
from ._helpers import (
    _parse_states as _parse_states,
)
from ._helpers import (
    get_all_registers as get_all_registers,
)
from ._loaders import (
    _build_entity_mappings as _build_entity_mappings,
)
from ._loaders import (
    _extend_entity_mappings_from_registers as _extend_entity_mappings_from_registers,
)
from ._loaders import (
    _load_discrete_mappings as _load_discrete_mappings,
)
from ._loaders import (
    _load_number_mappings as _load_number_mappings,
)
from .legacy import (
    LEGACY_ENTITY_ID_ALIASES as LEGACY_ENTITY_ID_ALIASES,
)
from .legacy import (
    LEGACY_ENTITY_ID_OBJECT_ALIASES as LEGACY_ENTITY_ID_OBJECT_ALIASES,
)
from .legacy import _alias_warning_logged as _alias_warning_logged
from .legacy import (
    map_legacy_entity_id as map_legacy_entity_id,
)
from .special_modes import SPECIAL_MODE_ICONS as SPECIAL_MODE_ICONS

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "BINARY_SENSOR_ENTITY_MAPPINGS",
    # entity mappings
    "ENTITY_MAPPINGS",
    # legacy
    "LEGACY_ENTITY_ID_ALIASES",
    "LEGACY_ENTITY_ID_OBJECT_ALIASES",
    "NUMBER_ENTITY_MAPPINGS",
    "NUMBER_OVERRIDES",
    "SELECT_ENTITY_MAPPINGS",
    "SENSOR_ENTITY_MAPPINGS",
    # special modes
    "SPECIAL_MODE_ICONS",
    "SWITCH_ENTITY_MAPPINGS",
    "TEXT_ENTITY_MAPPINGS",
    "TIME_ENTITY_MAPPINGS",
    # helpers
    "_REGISTER_INFO_CACHE",
    "_alias_warning_logged",
    # loaders
    "_build_entity_mappings",
    "_extend_entity_mappings_from_registers",
    "_get_register_info",
    "_infer_icon",
    "_load_discrete_mappings",
    "_load_number_mappings",
    "_load_translation_keys",
    "_number_translation_keys",
    "_parse_states",
    # setup
    "async_setup_entity_mappings",
    # const register accessors (re-exported so tests can monkeypatch via this module)
    "coil_registers",
    "discrete_input_registers",
    "get_all_registers",
    "holding_registers",
    "map_legacy_entity_id",
]


# Manual overrides for number entities (icons, custom units, etc.)
NUMBER_OVERRIDES: dict[str, dict[str, Any]] = {
    # Temperature setpoints — multiplier=0.5, so physical = raw × 0.5 (°C)
    # PDF raw range 20–90 → physical 10–45 °C, step 0.5 °C
    "supply_air_temperature_manual": {
        "icon": "mdi:thermometer-plus",
        "min": 10,
        "max": 45,
        "step": 0.5,
    },
    "supply_air_temperature_temporary": {
        "icon": "mdi:thermometer-plus",
        "min": 10,
        "max": 45,
        "step": 0.5,
    },
    "supply_air_temperature_temporary_4404": {
        "icon": "mdi:thermometer-plus",
        "min": 10,
        "max": 45,
        "step": 0.5,
    },
    # PDF raw 10–40 → physical 5–20 °C
    "min_bypass_temperature": {"icon": "mdi:thermometer-low", "min": 5, "max": 20, "step": 0.5},
    # PDF raw 30–60 → physical 15–30 °C
    "air_temperature_summer_free_heating": {
        "icon": "mdi:thermometer",
        "min": 15,
        "max": 30,
        "step": 0.5,
    },
    "air_temperature_summer_free_cooling": {
        "icon": "mdi:thermometer",
        "min": 15,
        "max": 30,
        "step": 0.5,
    },
    # PDF raw 0–20 → physical 0–10 °C
    "min_gwc_air_temperature": {"icon": "mdi:thermometer-low", "min": 0, "max": 10, "step": 0.5},
    # PDF raw 30–80 → physical 15–40 °C
    "max_gwc_air_temperature": {"icon": "mdi:thermometer-high", "min": 15, "max": 40, "step": 0.5},
    # PDF raw 0–10 → physical 0–5 °C
    "delta_t_gwc": {"icon": "mdi:thermometer-lines", "min": 0, "max": 5, "step": 0.5},
    # Air flow intensity setpoints (%), multiplier=1
    "air_flow_rate_manual": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "air_flow_rate_temporary": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "air_flow_rate_temporary_4401": {"icon": "mdi:fan", "min": 10, "max": 100, "step": 1},
    "max_supply_air_flow_rate": {"icon": "mdi:fan-plus", "min": 100, "max": 150, "step": 1},
    "max_exhaust_air_flow_rate": {"icon": "mdi:fan-minus", "min": 100, "max": 150, "step": 1},
    "max_supply_air_flow_rate_gwc": {"icon": "mdi:fan-plus", "min": 100, "max": 150, "step": 1},
    "max_exhaust_air_flow_rate_gwc": {"icon": "mdi:fan-minus", "min": 100, "max": 150, "step": 1},
    # Nominal (calibrated) air flow (m³/h)
    "nominal_supply_air_flow": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_exhaust_air_flow": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_supply_air_flow_gwc": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    "nominal_exhaust_air_flow_gwc": {"icon": "mdi:fan-clock", "min": 110, "max": 1900, "step": 1},
    # GWC timing
    "gwc_regen_period": {"icon": "mdi:timer", "min": 4, "max": 8, "step": 1},
    # Fan speed setpoints for AirS panel — speed 1/2/3 non-overlapping ranges
    "fan_speed_1_coef": {"icon": "mdi:speedometer", "min": 10, "max": 45, "step": 1},
    "fan_speed_2_coef": {"icon": "mdi:speedometer", "min": 46, "max": 75, "step": 1},
    "fan_speed_3_coef": {"icon": "mdi:speedometer", "min": 76, "max": 100, "step": 1},
    # Special-function intensity setpoints (%)
    "hood_supply_coef": {"icon": "mdi:stove", "min": 100, "max": 150, "step": 1},
    "hood_exhaust_coef": {"icon": "mdi:stove", "min": 100, "max": 150, "step": 1},
    "fireplace_supply_coef": {"icon": "mdi:fireplace", "min": 5, "max": 50, "step": 1},
    "airing_bathroom_coef": {"icon": "mdi:shower", "min": 100, "max": 150, "step": 1},
    "airing_coef": {"icon": "mdi:window-open", "min": 100, "max": 150, "step": 1},
    "contamination_coef": {"icon": "mdi:air-filter", "min": 100, "max": 150, "step": 1},
    "empty_house_coef": {"icon": "mdi:home-off", "min": 10, "max": 50, "step": 1},
    "airing_switch_coef": {"icon": "mdi:toggle-switch", "min": 100, "max": 150, "step": 1},
    "open_window_coef": {"icon": "mdi:window-open-variant", "min": 10, "max": 100, "step": 1},
    "bypass_coef_1": {"icon": "mdi:transfer", "min": 10, "max": 100, "step": 1},
    "bypass_coef_2": {"icon": "mdi:transfer", "min": 10, "max": 150, "step": 1},
    # Special-function timing (min)
    "airing_panel_mode_time": {"icon": "mdi:timer", "min": 1, "max": 45, "step": 1},
    "airing_switch_mode_time": {"icon": "mdi:timer", "min": 1, "max": 45, "step": 1},
    "airing_switch_mode_on_delay": {
        "icon": "mdi:timer-plus-outline",
        "min": 0,
        "max": 20,
        "step": 1,
    },
    "airing_switch_mode_off_delay": {
        "icon": "mdi:timer-minus-outline",
        "min": 0,
        "max": 20,
        "step": 1,
    },
    "fireplace_mode_time": {"icon": "mdi:timer", "min": 1, "max": 10, "step": 1},
    # Modbus port device IDs
    "uart_0_id": {"icon": "mdi:identifier", "min": 10, "max": 19, "step": 1},
    "uart_1_id": {"icon": "mdi:identifier", "min": 10, "max": 19, "step": 1},
    # Filter wear thresholds (0–127 %)
    "cfgszf_fn_new": {"icon": "mdi:filter-check", "min": 0, "max": 127, "step": 1},
    "cfgszf_fw_new": {"icon": "mdi:filter-check", "min": 0, "max": 127, "step": 1},
    # RTC calibration register (0–255, signed offset encoded as unsigned; no SI unit)
    "rtc_cal": {"icon": "mdi:clock-edit", "min": 0, "max": 255, "step": 1, "unit": None},
    # lock_pass — product key passphrase, first 16-bit word (0–0x423f = 16959)
    "lock_pass": {"icon": "mdi:lock", "min": 0, "max": 16959, "step": 1},
}


# ---------------------------------------------------------------------------
# Entity configurations
# ---------------------------------------------------------------------------

# Number entity mappings loaded from register metadata during setup
NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}
SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
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
    "version_major": {
        "translation_key": "version_major",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "version_minor": {
        "translation_key": "version_minor",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "version_patch": {
        "translation_key": "version_patch",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "serial_number": {
        "translation_key": "serial_number",
        "icon": "mdi:barcode",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cf_version": {
        "translation_key": "cf_version",
        "icon": "mdi:information",
        "register_type": "holding_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "exp_version": {
        "translation_key": "exp_version",
        "icon": "mdi:information-outline",
        "register_type": "holding_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
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
    "supply_air_temperature_manual": {
        "translation_key": "supply_air_temperature_manual",
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

SELECT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "mode": {
        "icon": "mdi:cog",
        "translation_key": "mode",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
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
    "gwc_regen": {
        "icon": "mdi:heat-wave",
        "translation_key": "gwc_regen",
        "states": {"inactive": 0, "daily_schedule": 1, "temperature_diff": 2},
        "register_type": "holding_registers",
    },
    "bypass_user_mode": {
        "icon": "mdi:pipe-valve",
        "translation_key": "bypass_user_mode",
        "states": {"mode_1": 1, "mode_2": 2, "mode_3": 3},
        "register_type": "holding_registers",
    },
    "cfg_mode_1": {
        "icon": "mdi:tune",
        "translation_key": "cfg_mode_1",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "cfg_mode_2": {
        "icon": "mdi:tune",
        "translation_key": "cfg_mode_2",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "configuration_mode": {
        "icon": "mdi:cog-outline",
        "translation_key": "configuration_mode",
        "states": {"normal": 0, "duct_filter_pressure": 47, "afc_filter_pressure": 65},
        "register_type": "holding_registers",
    },
    "pres_check_day": {
        "icon": "mdi:calendar-week",
        "translation_key": "pres_check_day",
        "states": {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        },
        "register_type": "holding_registers",
    },
    "pres_check_day_4432": {
        "icon": "mdi:calendar-week",
        "translation_key": "pres_check_day_4432",
        "states": {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        },
        "register_type": "holding_registers",
    },
    "access_level": {
        "icon": "mdi:account-key",
        "translation_key": "access_level",
        "states": {"user": 0, "service": 1, "manufacturer": 3},
        "register_type": "holding_registers",
    },
    "special_mode": {
        "icon": "mdi:lightning-bolt",
        "translation_key": "special_mode",
        "states": {
            "none": 0,
            "hood": 1,
            "fireplace": 2,
            "airing_doorbell": 3,
            "airing_switch": 4,
            "airing_hygrostat": 5,
            "airing_air_quality": 6,
            "airing_manual": 7,
            "airing_auto": 8,
            "airing_manual_timed": 9,
            "open_windows": 10,
            "empty_house": 11,
        },
        "register_type": "holding_registers",
    },
    "language": {
        "icon": "mdi:translate",
        "translation_key": "language",
        "states": {"pl": 0, "en": 1, "ru": 2, "uk": 3, "sk": 4},
        "register_type": "holding_registers",
    },
    "uart_0_baud": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_baud",
        "states": {
            "baud_4800": 0,
            "baud_9600": 1,
            "baud_14400": 2,
            "baud_19200": 3,
            "baud_28800": 4,
            "baud_38400": 5,
            "baud_57600": 6,
            "baud_76800": 7,
            "baud_115200": 8,
        },
        "register_type": "holding_registers",
    },
    "uart_0_parity": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_parity",
        "states": {"none": 0, "even": 1, "odd": 2},
        "register_type": "holding_registers",
    },
    "uart_0_stop": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_0_stop",
        "states": {"one": 0, "two": 1},
        "register_type": "holding_registers",
    },
    "uart_1_baud": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_baud",
        "states": {
            "baud_4800": 0,
            "baud_9600": 1,
            "baud_14400": 2,
            "baud_19200": 3,
            "baud_28800": 4,
            "baud_38400": 5,
            "baud_57600": 6,
            "baud_76800": 7,
            "baud_115200": 8,
        },
        "register_type": "holding_registers",
    },
    "uart_1_parity": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_parity",
        "states": {"none": 0, "even": 1, "odd": 2},
        "register_type": "holding_registers",
    },
    "uart_1_stop": {
        "icon": "mdi:serial-port",
        "translation_key": "uart_1_stop",
        "states": {"one": 0, "two": 1},
        "register_type": "holding_registers",
    },
    # ERV (secondary heater) operating mode — 3 fixed options
    "cfg_post_heater_mode": {
        "icon": "mdi:radiator",
        "translation_key": "cfg_post_heater_mode",
        "states": {"off": 0, "mode_1": 1, "mode_2": 2},
        "register_type": "holding_registers",
    },
}

BINARY_SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
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
        "inverted": True,  # NC contact: True = circuit closed = no alarm, False = alarm triggered
    },
    # Active modes (from input registers)
    "water_removal_active": {
        "translation_key": "water_removal_active",
        "icon": "mdi:water-off",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "register_type": "input_registers",
    },
    # on_off_panel_mode is covered by SWITCH_ENTITY_MAPPINGS which provides
    # both read and control capability — no separate binary sensor needed.
    "gwc_regen_flag": {
        "translation_key": "gwc_regen_flag",
        "icon": "mdi:heat-wave",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "holding_registers",
    },
    # Antifreeze (FPX) activation flag — read-only boolean holding register
    "antifreeze_mode": {
        "translation_key": "antifreeze_mode",
        "icon": "mdi:snowflake-alert",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "holding_registers",
    },
    # Filter alarm flags (f_ prefix → diagnostic binary sensors)
    "f_142": {
        "translation_key": "f_142",
        "icon": "mdi:filter-remove",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    "f_143": {
        "translation_key": "f_143",
        "icon": "mdi:filter-remove",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    "f_146": {
        "translation_key": "f_146",
        "icon": "mdi:filter-alert",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    "f_147": {
        "translation_key": "f_147",
        "icon": "mdi:filter-alert",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "holding_registers",
    },
    # Secondary heater (ERV) status
    "post_heater_on": {
        "translation_key": "post_heater_on",
        "icon": "mdi:radiator",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "holding_registers",
    },
}

SWITCH_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    # System control switches from holding registers
    "on_off_panel_mode": {
        "icon": "mdi:power",
        "register": "on_off_panel_mode",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "on_off_panel_mode",
    },
    "bypass_off": {
        "icon": "mdi:pipe-valve",
        "register": "bypass_off",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "bypass_off",
    },
    "gwc_off": {
        "icon": "mdi:heat-wave",
        "register": "gwc_off",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "gwc_off",
    },
    "hard_reset_settings": {
        "icon": "mdi:restore",
        "register": "hard_reset_settings",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "hard_reset_settings",
    },
    "hard_reset_schedule": {
        "icon": "mdi:restore-alert",
        "register": "hard_reset_schedule",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "hard_reset_schedule",
    },
    "comfort_mode_panel": {
        "icon": "mdi:sofa",
        "register": "comfort_mode_panel",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "comfort_mode_panel",
    },
    "airflow_rate_change_flag": {
        "icon": "mdi:air-filter",
        "register": "airflow_rate_change_flag",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "airflow_rate_change_flag",
    },
    "temperature_change_flag": {
        "icon": "mdi:thermometer-alert",
        "register": "temperature_change_flag",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "temperature_change_flag",
    },
    "lock_flag": {
        "icon": "mdi:lock",
        "register": "lock_flag",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "lock_flag",
    },
}

# Discrete entity mappings and special modes are populated during setup

# Time entity mappings for writable BCD HHMM registers
TIME_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}

# Text entities — ASCII string registers exposed as HA text controls
TEXT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "device_name": {
        "translation_key": "device_name",
        "icon": "mdi:rename",
        "register_type": "holding_registers",
        "max_length": 16,
    },
}

# Aggregated entity mappings for all platforms
ENTITY_MAPPINGS: dict[str, dict[str, dict[str, Any]]] = {}


def _run_build_entity_mappings() -> None:
    """Build entity mappings; delegates to _loaders._build_entity_mappings."""
    _build_entity_mappings()


async def async_setup_entity_mappings(hass: HomeAssistant | None = None) -> None:
    """Asynchronously build entity mappings."""

    if hass is not None:
        await hass.async_add_executor_job(_run_build_entity_mappings)
    else:
        _run_build_entity_mappings()


try:  # pragma: no cover - handle partially initialized module
    _HAS_HA = importlib.util.find_spec("homeassistant") is not None
except (ImportError, ValueError):
    _HAS_HA = False

_run_build_entity_mappings()
