"""Entity mapping definitions for the ThesslaGreen Modbus integration."""
from typing import Any, Dict

NUMBER_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "required_temperature": {
        "unit": "°C",
        "min": 16,
        "max": 26,
        "step": 0.5,
        "scale": 0.5,
    },
    "max_supply_temperature": {
        "unit": "°C",
        "min": 15,
        "max": 45,
        "step": 0.5,
        "scale": 0.5,
    },
    "min_supply_temperature": {
        "unit": "°C",
        "min": 5,
        "max": 30,
        "step": 0.5,
        "scale": 0.5,
    },
    "heating_curve_slope": {
        "min": 0,
        "max": 10,
        "step": 0.1,
        "scale": 0.1,
    },
    "heating_curve_offset": {
        "unit": "°C",
        "min": -10,
        "max": 10,
        "step": 0.5,
        "scale": 0.5,
    },
    "boost_air_flow_rate": {
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
    },
    "boost_duration": {
        "unit": "min",
        "min": 0,
        "max": 240,
        "step": 1,
    },
    "humidity_target": {
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
    },
}

ENTITY_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
}
