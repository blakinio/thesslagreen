"""Extracted diagnostic binary-sensor mappings from static discrete mappings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

DIAGNOSTIC_BINARY_SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
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

__all__ = ["DIAGNOSTIC_BINARY_SENSOR_ENTITY_MAPPINGS"]
