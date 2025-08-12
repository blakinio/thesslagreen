"""Entity mapping definitions for the ThesslaGreen Modbus integration."""
from typing import Any, Dict

NUMBER_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "required_temperature": {
        "unit": "°C",
        "min": 16,
        "max": 26,
        "step": 0.5,
        "scale": 0.5,
    }
}

ENTITY_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
}
