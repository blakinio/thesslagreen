"""Compatibility re-exports for Home Assistant symbols used across the integration."""

from __future__ import annotations

import datetime as dt
from typing import Any

UTC = dt.timezone.utc  # noqa: UP017

try:
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
except (ImportError, ModuleNotFoundError, AttributeError):  # pragma: no cover - test stubs
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity import EntityCategory
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
    from homeassistant.util import dt as dt_util

    EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
    PERCENTAGE = "%"

    class UnitOfElectricPotential:  # type: ignore[no-redef]
        VOLT = "V"

    class UnitOfPower:  # type: ignore[no-redef]
        WATT = "W"

    class UnitOfTemperature:  # type: ignore[no-redef]
        CELSIUS = "°C"

    class UnitOfTime:  # type: ignore[no-redef]
        HOURS = "h"
        MINUTES = "min"
        DAYS = "d"
        SECONDS = "s"

    class UnitOfVolumeFlowRate:  # type: ignore[no-redef]
        CUBIC_METERS_PER_HOUR = "m³/h"

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
