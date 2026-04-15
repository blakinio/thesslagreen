"""Compatibility helpers for running integration code with/without Home Assistant."""

from __future__ import annotations

import datetime as dt
from typing import Any

UTC = getattr(dt, "UTC", dt.UTC)

try:
    from homeassistant.util import dt as dt_util
except (ModuleNotFoundError, ImportError):
    class _DTUtil:
        """Fallback minimal dt util."""

        @staticmethod
        def now() -> dt.datetime:
            return dt.datetime.now(UTC)

        @staticmethod
        def utcnow() -> dt.datetime:
            return dt.datetime.now(UTC)

    dt_util = _DTUtil()

try:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
except (ModuleNotFoundError, ImportError):

    class BinarySensorDeviceClass:  # type: ignore[no-redef]
        RUNNING = "running"
        OPENING = "opening"
        POWER = "power"
        HEAT = "heat"
        CONNECTIVITY = "connectivity"
        PROBLEM = "problem"
        SAFETY = "safety"
        MOISTURE = "moisture"


try:
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
except (ModuleNotFoundError, ImportError):

    class SensorDeviceClass:  # type: ignore[no-redef]
        TEMPERATURE = "temperature"
        VOLTAGE = "voltage"
        POWER = "power"
        ENERGY = "energy"
        EFFICIENCY = "efficiency"
        VOLUME_FLOW_RATE = "volume_flow_rate"

    class SensorStateClass:  # type: ignore[no-redef]
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"


try:
    from homeassistant.helpers.entity import EntityCategory
except (ModuleNotFoundError, ImportError):

    class EntityCategory:  # type: ignore[no-redef]
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"


try:
    from homeassistant.helpers.device_registry import DeviceInfo
except (ModuleNotFoundError, ImportError):

    class DeviceInfo:
        """Minimal fallback DeviceInfo for tests."""

        def __init__(self, **kwargs: Any) -> None:
            self._data: dict[str, Any] = dict(kwargs)

        def as_dict(self) -> dict[str, Any]:
            return dict(self._data)

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def __getattr__(self, item: str) -> Any:
            try:
                return self._data[item]
            except KeyError as exc:
                raise AttributeError(item) from exc


try:
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
except (ModuleNotFoundError, ImportError):
    EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"

try:
    from homeassistant.const import (
        PERCENTAGE,
        UnitOfElectricPotential,
        UnitOfPower,
        UnitOfTemperature,
        UnitOfTime,
        UnitOfVolumeFlowRate,
    )
except (ModuleNotFoundError, ImportError):
    PERCENTAGE = "%"

    class UnitOfElectricPotential:  # type: ignore[no-redef]
        VOLT = "V"

    class UnitOfPower:  # type: ignore[no-redef]
        WATT = "W"

    class UnitOfTemperature:  # type: ignore[no-redef]
        CELSIUS = "°C"

    class UnitOfTime:  # type: ignore[no-redef]
        HOURS = "h"
        DAYS = "d"
        SECONDS = "s"

    class UnitOfVolumeFlowRate:  # type: ignore[no-redef]
        CUBIC_METERS_PER_HOUR = "m³/h"


try:
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
except (ModuleNotFoundError, ImportError):

    class DataUpdateCoordinator:  # type: ignore[no-redef]
        pass


try:
    from homeassistant.helpers.update_coordinator import UpdateFailed
except (ModuleNotFoundError, ImportError):

    class UpdateFailed(Exception):  # type: ignore[no-redef]
        """Fallback update-failed exception."""


try:
    COORDINATOR_BASE = DataUpdateCoordinator[dict[str, Any]]
except TypeError:
    COORDINATOR_BASE = DataUpdateCoordinator
