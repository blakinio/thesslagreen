"""Entity mapping definitions for the ThesslaGreen Modbus integration."""

from typing import Any, Dict

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
    # Bypass settings
    "bypass_off": {
        "unit": "°C",
        "min": 0,
        "max": 40,
        "step": 0.5,
        "scale": 0.5,
    },
}

ENTITY_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
}
