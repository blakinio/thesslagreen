"""Entity mapping definitions for the ThesslaGreen Modbus integration.

This module also provides helpers for handling legacy entity IDs that were
renamed in newer versions of the integration.
"""

from typing import Any, Dict
import logging


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
