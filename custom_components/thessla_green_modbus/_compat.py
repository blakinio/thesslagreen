"""Compatibility re-exports for Home Assistant symbols used across the integration.

Manifest requires homeassistant>=2026.1.0 and python>=3.13, so all fallbacks
for running without Home Assistant have been removed. This module is now a
single import point for HA symbols used across the integration.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

COORDINATOR_BASE = DataUpdateCoordinator[dict[str, Any]]

__all__ = [
    "COORDINATOR_BASE",
    "EVENT_HOMEASSISTANT_STOP",
    "PERCENTAGE",
    "UTC",
    "BinarySensorDeviceClass",
    "DataUpdateCoordinator",
    "DeviceInfo",
    "EntityCategory",
    "SensorDeviceClass",
    "SensorStateClass",
    "UnitOfElectricPotential",
    "UnitOfPower",
    "UnitOfTemperature",
    "UnitOfTime",
    "UnitOfVolumeFlowRate",
    "UpdateFailed",
    "dt_util",
]
