from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.entity import EntityCategory


def diagnostic_sensor_payload(translation_key: str, *, icon: str = "mdi:information", register_type: str = "input_registers") -> dict[str, Any]:
    return {"translation_key": translation_key, "icon": icon, "register_type": register_type, "entity_category": EntityCategory.DIAGNOSTIC}


def airflow_sensor_mappings() -> dict[str, dict[str, Any]]:
    return {
        "supply_flow_rate": {"translation_key": "supply_flow_rate_m3h", "icon": "mdi:fan-plus", "device_class": SensorDeviceClass.VOLUME_FLOW_RATE, "state_class": SensorStateClass.MEASUREMENT, "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, "register_type": "input_registers"},
        "exhaust_flow_rate": {"translation_key": "exhaust_flow_rate_m3h", "icon": "mdi:fan-minus", "device_class": SensorDeviceClass.VOLUME_FLOW_RATE, "state_class": SensorStateClass.MEASUREMENT, "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, "register_type": "input_registers"},
        "supply_air_flow": {"translation_key": "supply_air_flow", "icon": "mdi:fan-plus", "device_class": SensorDeviceClass.VOLUME_FLOW_RATE, "state_class": SensorStateClass.MEASUREMENT, "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, "register_type": "holding_registers"},
        "exhaust_air_flow": {"translation_key": "exhaust_air_flow", "icon": "mdi:fan-minus", "device_class": SensorDeviceClass.VOLUME_FLOW_RATE, "state_class": SensorStateClass.MEASUREMENT, "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, "register_type": "holding_registers"},
    }
