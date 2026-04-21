"""Static discrete/select/switch mappings for ThesslaGreen entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

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

__all__ = [
    "BINARY_SENSOR_ENTITY_MAPPINGS",
    "SELECT_ENTITY_MAPPINGS",
    "SWITCH_ENTITY_MAPPINGS",
]
